"""Browser automation service (Playwright-backed, opt-in).

Disabled by default so the standard backend image and CI behavior are
unchanged. To enable:

    1. Set ``BROWSER_ENABLED=true`` in the environment.
    2. Ensure Playwright is installed: ``pip install playwright`` and
       ``python -m playwright install chromium``.

When disabled or when Playwright is not importable, every method returns a
structured :class:`ToolResult` with ``ok=False``; no exceptions leak. This
keeps the agent tool surface stable in both modes.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from config import settings

logger = logging.getLogger("nexus.services.browser")

_DISABLED_MSG = "Browser tool disabled - set BROWSER_ENABLED=true and install playwright"

# Detect Playwright at import time without crashing the module.
try:  # pragma: no cover - exercised via env
    from playwright.async_api import async_playwright  # type: ignore
    from playwright.async_api import Error as PWError  # type: ignore
    from playwright.async_api import TimeoutError as PWTimeoutError  # type: ignore

    _PLAYWRIGHT_AVAILABLE = True
except Exception:  # pragma: no cover - missing dep is the expected default
    async_playwright = None  # type: ignore
    PWError = Exception  # type: ignore
    PWTimeoutError = Exception  # type: ignore
    _PLAYWRIGHT_AVAILABLE = False


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "data": self.data, "error": self.error, "meta": self.meta}


def _disabled_result() -> ToolResult:
    return ToolResult(ok=False, error=_DISABLED_MSG)


class BrowserService:
    """Singleton wrapper around a single Playwright Chromium page.

    Lazy-starts on first real call. All methods are exception-safe and return
    a :class:`ToolResult`. When disabled, every method returns the same
    structured disabled error.
    """

    _instance: "BrowserService | None" = None

    def __new__(cls) -> "BrowserService":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._init_state()  # type: ignore[attr-defined]
            cls._instance = inst
        return cls._instance

    # ── lifecycle ────────────────────────────────────────────────────────
    def _init_state(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = asyncio.Lock()
        self._console_messages: list[str] = []

    @classmethod
    def is_available(cls) -> bool:
        """True only when Playwright is importable AND BROWSER_ENABLED is on."""
        return bool(_PLAYWRIGHT_AVAILABLE and getattr(settings, "BROWSER_ENABLED", False))

    async def _ensure_started(self) -> Optional[ToolResult]:
        """Start Playwright lazily. Returns a disabled ToolResult on failure."""
        if not self.is_available():
            return _disabled_result()
        if self._page is not None:
            return None
        async with self._lock:
            if self._page is not None:
                return None
            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=bool(settings.BROWSER_HEADLESS),
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                self._context = await self._browser.new_context(
                    viewport={
                        "width": int(settings.BROWSER_VIEWPORT_WIDTH),
                        "height": int(settings.BROWSER_VIEWPORT_HEIGHT),
                    },
                )
                self._context.set_default_timeout(int(settings.BROWSER_TIMEOUT_MS))
                self._context.set_default_navigation_timeout(
                    int(settings.BROWSER_NAV_TIMEOUT_MS)
                )
                self._page = await self._context.new_page()
                self._page.on(
                    "console",
                    lambda msg: self._console_messages.append(f"[{msg.type}] {msg.text}"),
                )
                return None
            except Exception as exc:  # pragma: no cover - launch failure path
                logger.exception("browser.start_failed")
                await self._safe_shutdown()
                return ToolResult(ok=False, error=f"browser start failed: {exc}")

    async def _safe_shutdown(self) -> None:
        for attr in ("_page", "_context", "_browser"):
            obj = getattr(self, attr, None)
            if obj is not None:
                try:
                    await obj.close()
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._console_messages = []

    async def shutdown(self) -> ToolResult:
        await self._safe_shutdown()
        return ToolResult(ok=True, data={"shutdown": True})

    # ── helpers ──────────────────────────────────────────────────────────
    async def _guarded(self, fn):
        if not self.is_available():
            return _disabled_result()
        started = await self._ensure_started()
        if started is not None:
            return started
        try:
            return await fn()
        except PWTimeoutError as exc:
            return ToolResult(ok=False, error=f"timeout: {exc}")
        except PWError as exc:
            return ToolResult(ok=False, error=f"playwright error: {exc}")
        except Exception as exc:
            logger.exception("browser.unhandled")
            return ToolResult(ok=False, error=str(exc))

    # ── public methods (preserve signatures from the previous stub) ─────
    async def restart(self) -> ToolResult:
        if not self.is_available():
            return _disabled_result()
        await self._safe_shutdown()
        started = await self._ensure_started()
        if started is not None:
            return started
        return ToolResult(ok=True, data={"restarted": True})

    async def navigate(self, url: str) -> ToolResult:
        async def _do():
            assert self._page is not None
            response = await self._page.goto(url, wait_until="domcontentloaded")
            title = await self._page.title()
            status = response.status if response is not None else None
            return ToolResult(
                ok=True,
                data={"url": self._page.url, "title": title, "status": status},
            )

        return await self._guarded(_do)

    async def view(self) -> ToolResult:
        async def _do():
            assert self._page is not None
            try:
                shot = await self._page.screenshot(type="png", full_page=False)
                screenshot_b64 = base64.b64encode(shot).decode("ascii")
            except Exception:
                screenshot_b64 = None
            title = await self._page.title()
            return ToolResult(
                ok=True,
                data={
                    "url": self._page.url,
                    "title": title,
                    "viewport": {
                        "width": int(settings.BROWSER_VIEWPORT_WIDTH),
                        "height": int(settings.BROWSER_VIEWPORT_HEIGHT),
                    },
                    "screenshot_b64": screenshot_b64,
                },
            )

        return await self._guarded(_do)

    async def click(self, selector: str) -> ToolResult:
        async def _do():
            assert self._page is not None
            await self._page.click(selector)
            return ToolResult(ok=True, data={"clicked": selector})

        return await self._guarded(_do)

    async def input(self, selector: str, text: str) -> ToolResult:
        async def _do():
            assert self._page is not None
            await self._page.fill(selector, text)
            return ToolResult(ok=True, data={"selector": selector, "filled": True})

        return await self._guarded(_do)

    async def move_mouse(self, x: int, y: int) -> ToolResult:
        async def _do():
            assert self._page is not None
            await self._page.mouse.move(int(x), int(y))
            return ToolResult(ok=True, data={"x": int(x), "y": int(y)})

        return await self._guarded(_do)

    async def press_key(self, key: str) -> ToolResult:
        async def _do():
            assert self._page is not None
            await self._page.keyboard.press(key)
            return ToolResult(ok=True, data={"key": key})

        return await self._guarded(_do)

    async def select_option(self, selector: str, value: str) -> ToolResult:
        async def _do():
            assert self._page is not None
            await self._page.select_option(selector, value)
            return ToolResult(ok=True, data={"selector": selector, "value": value})

        return await self._guarded(_do)

    async def scroll(self, dy: int) -> ToolResult:
        async def _do():
            assert self._page is not None
            await self._page.evaluate("(y) => window.scrollBy(0, y)", int(dy))
            return ToolResult(ok=True, data={"dy": int(dy)})

        return await self._guarded(_do)

    async def console_exec(self, script: str) -> ToolResult:
        async def _do():
            assert self._page is not None
            result = await self._page.evaluate(script)
            return ToolResult(ok=True, data={"result": result})

        return await self._guarded(_do)

    async def console_view(self) -> ToolResult:
        if not self.is_available():
            return _disabled_result()
        return ToolResult(ok=True, data={"messages": list(self._console_messages)})


async def browse_url(url: str) -> str:
    """Convenience helper kept for backward-compat callers."""
    if not BrowserService.is_available():
        return _DISABLED_MSG
    svc = BrowserService()
    res = await svc.navigate(url)
    if not res.ok:
        return res.error or _DISABLED_MSG
    view = await svc.view()
    if view.ok and isinstance(view.data, dict):
        return f"{view.data.get('title', '')} — {view.data.get('url', url)}"
    return url
