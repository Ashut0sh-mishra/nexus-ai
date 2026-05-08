"""HTML → PNG renderer for slide previews / thumbnails.

Optional dependency. Install with::

    pip install playwright
    playwright install chromium

If Playwright is not installed, ``render_html_to_png`` returns ``None`` and
callers MUST treat that as "no thumbnail available" rather than failing.

Usage
-----
    from services.slide_renderer import render_html_to_png

    png_bytes = await render_html_to_png(html, width=1920, height=1080)
    if png_bytes:
        storage.put("thumb.png", png_bytes, content_type="image/png")

Performance notes
-----------------
- The first call spins up a browser context (~500 ms cold-start).
- Subsequent calls within the same process reuse a singleton browser via
  ``_get_browser()`` so 10 slides take roughly 10 * (render + screenshot).
- Always call ``shutdown_browser()`` at process exit to release Chromium.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final, Optional

logger = logging.getLogger(__name__)

# Lazy-imported Playwright. Kept None until first successful render.
try:  # pragma: no cover - optional dep
    from playwright.async_api import (  # type: ignore
        Browser,
        async_playwright,
    )

    _PLAYWRIGHT_AVAILABLE = True
except Exception:  # pragma: no cover
    Browser = None  # type: ignore[assignment]
    async_playwright = None  # type: ignore[assignment]
    _PLAYWRIGHT_AVAILABLE = False


_DEFAULT_W: Final[int] = 1920
_DEFAULT_H: Final[int] = 1080
_DEFAULT_TIMEOUT_MS: Final[int] = 8000

# Process-singleton browser. Guarded by an asyncio lock so concurrent renders
# do not race to start two Chromium instances.
_browser_lock: asyncio.Lock | None = None
_browser: Optional["Browser"] = None  # type: ignore[type-arg]
_playwright_ctx = None  # holds the result of async_playwright().start()


def is_available() -> bool:
    """Return True iff Playwright is importable in this process."""
    return _PLAYWRIGHT_AVAILABLE


def _ensure_lock() -> asyncio.Lock:
    global _browser_lock
    if _browser_lock is None:
        _browser_lock = asyncio.Lock()
    return _browser_lock


async def _get_browser() -> Optional["Browser"]:  # type: ignore[type-arg]
    """Return a process-wide Chromium browser, launching one if needed."""
    global _browser, _playwright_ctx
    if not _PLAYWRIGHT_AVAILABLE:
        return None
    async with _ensure_lock():
        if _browser is not None:
            return _browser
        try:
            _playwright_ctx = await async_playwright().start()  # type: ignore[union-attr]
            _browser = await _playwright_ctx.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            logger.info("slide_renderer.browser_started")
            return _browser
        except Exception as exc:
            logger.warning("slide_renderer.launch_failed", extra={"err": str(exc)})
            _browser = None
            _playwright_ctx = None
            return None


async def shutdown_browser() -> None:
    """Release the singleton Chromium. Safe to call multiple times."""
    global _browser, _playwright_ctx
    async with _ensure_lock():
        if _browser is not None:
            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None
        if _playwright_ctx is not None:
            try:
                await _playwright_ctx.stop()
            except Exception:
                pass
            _playwright_ctx = None


async def render_html_to_png(
    html: str,
    *,
    width: int = _DEFAULT_W,
    height: int = _DEFAULT_H,
    device_scale_factor: float = 1.0,
    wait_for_fonts: bool = True,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
) -> bytes | None:
    """Render a self-contained HTML string to a PNG screenshot.

    Returns ``None`` if Playwright is unavailable or rendering fails — the
    caller should treat this as "no thumbnail" and continue.
    """
    if not html:
        return None
    browser = await _get_browser()
    if browser is None:
        return None

    context = None
    page = None
    try:
        context = await browser.new_context(
            viewport={"width": int(width), "height": int(height)},
            device_scale_factor=float(device_scale_factor),
        )
        page = await context.new_page()
        await page.set_content(html, wait_until="networkidle", timeout=timeout_ms)
        if wait_for_fonts:
            try:
                await page.evaluate("document.fonts && document.fonts.ready")
            except Exception:
                pass  # non-fatal
        png = await page.screenshot(type="png", full_page=False, omit_background=False)
        return png
    except Exception as exc:
        logger.warning("slide_renderer.render_failed", extra={"err": str(exc)})
        return None
    finally:
        try:
            if page is not None:
                await page.close()
        except Exception:
            pass
        try:
            if context is not None:
                await context.close()
        except Exception:
            pass


def slide_to_html(slide: dict, palette: dict) -> str:
    """Build a minimal self-contained HTML document for a single slide.

    This is intentionally simple — bullet/title/quote/stats only — so the
    PNG preview carries the right palette and font without pulling in the
    full PPTX render pipeline. Extend per-layout as needed.
    """
    bg = palette.get("bg", "FFFFFF")
    text = palette.get("text", "111111")
    muted = palette.get("muted", "888888")
    accent = palette.get("accent", "2563EB")
    head_font = palette.get("heading_font", "Inter")
    body_font = palette.get("body_font", "Inter")

    layout = (slide.get("layout") or "bullets").lower()
    title = (slide.get("title") or "").strip()
    subtitle = (slide.get("subtitle") or "").strip()
    bullets = slide.get("bullets") or []
    quote = (slide.get("quote") or "").strip()
    attribution = (slide.get("attribution") or "").strip()

    body_html = ""
    if layout == "title":
        body_html = (
            f'<h1>{_esc(title)}</h1>'
            f'<p class="sub">{_esc(subtitle)}</p>'
        )
    elif layout == "quote" and quote:
        body_html = (
            f'<div class="quote">&ldquo;{_esc(quote)}&rdquo;</div>'
            f'<div class="attr">— {_esc(attribution)}</div>'
        )
    else:
        body_html = (
            f'<h2>{_esc(title)}</h2>'
            + "".join(f'<li>{_esc(str(b))}</li>' for b in bullets[:6])
        )
        if body_html.endswith("</li>"):
            body_html = body_html.replace("<li>", "<ul><li>", 1) + "</ul>"

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>"
        f"@import url('https://fonts.googleapis.com/css2?family={head_font.replace(' ', '+')}"
        f":wght@400;700&family={body_font.replace(' ', '+')}:wght@400;500&display=swap');"
        "html,body{margin:0;padding:0;width:100%;height:100%;}"
        f"body{{background:#{bg};color:#{text};"
        f"font-family:'{body_font}',sans-serif;padding:5vh 6vw;box-sizing:border-box;}}"
        f"h1,h2{{font-family:'{head_font}',serif;color:#{text};margin:0 0 .4em 0;}}"
        "h1{font-size:6vw;line-height:1.1;}"
        "h2{font-size:3.5vw;line-height:1.15;}"
        f".sub{{color:#{muted};font-size:2vw;margin-top:1em;}}"
        f".quote{{color:#{text};font-size:3vw;font-style:italic;line-height:1.3;}}"
        f".attr{{color:#{muted};font-size:1.4vw;margin-top:1em;}}"
        f"ul{{list-style:none;padding:0;margin:0;}}"
        f"li{{font-size:1.8vw;color:#{text};padding:.6em 0 .6em 1.4em;position:relative;}}"
        f"li:before{{content:'\\2022';color:#{accent};position:absolute;left:0;font-weight:700;}}"
        "</style></head><body>"
        + body_html
        + "</body></html>"
    )


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


__all__ = [
    "is_available",
    "render_html_to_png",
    "shutdown_browser",
    "slide_to_html",
]
