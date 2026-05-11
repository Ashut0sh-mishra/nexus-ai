"""Live Playwright tests for BrowserService.

Skipped unless ``BROWSER_LIVE=1`` AND Playwright is importable AND Chromium
is installed. Uses only data:/file: URLs — no external network.

Run with::

    BROWSER_LIVE=1 BROWSER_ENABLED=true python -m pytest tests/test_browser_service_live.py
"""

from __future__ import annotations

import asyncio
import os
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("playwright")

if os.environ.get("BROWSER_LIVE") != "1":
    pytest.skip("BROWSER_LIVE != 1 — skipping live Playwright tests", allow_module_level=True)

from config import settings  # noqa: E402

# Force-enable for this module.
settings.BROWSER_ENABLED = True

from services.browser_service import BrowserService  # noqa: E402


HTML = textwrap.dedent(
    """
    <!doctype html>
    <html><head><title>NEXUS Live Test</title></head>
    <body>
      <input id="i" />
      <select id="s"><option value="a">a</option><option value="b">b</option></select>
      <button id="b">click</button>
    </body></html>
    """
).strip()


def _write_html(tmp_path: Path) -> str:
    f = tmp_path / "page.html"
    f.write_text(HTML, encoding="utf-8")
    return f.as_uri()


@pytest.fixture(autouse=True)
def _clean_singleton():
    yield
    asyncio.run(BrowserService().shutdown())


def test_navigate_view_local_file(tmp_path):
    url = _write_html(tmp_path)

    async def _run():
        svc = BrowserService()
        nav = await svc.navigate(url)
        assert nav.ok, nav.error
        view = await svc.view()
        assert view.ok, view.error
        assert view.data["title"] == "NEXUS Live Test"
        assert view.data["url"].startswith("file://")
        assert view.data["screenshot_b64"] and len(view.data["screenshot_b64"]) > 100

    asyncio.run(_run())


def test_input_select_console(tmp_path):
    url = _write_html(tmp_path)

    async def _run():
        svc = BrowserService()
        assert (await svc.navigate(url)).ok
        assert (await svc.input("#i", "hello")).ok
        assert (await svc.select_option("#s", "b")).ok
        val = await svc.console_exec("document.getElementById('i').value")
        assert val.ok and val.data["result"] == "hello"
        sel = await svc.console_exec("document.getElementById('s').value")
        assert sel.ok and sel.data["result"] == "b"
        click = await svc.click("#b")
        assert click.ok

    asyncio.run(_run())


def test_navigate_timeout_returns_structured_error(monkeypatch):
    monkeypatch.setattr(settings, "BROWSER_NAV_TIMEOUT_MS", 500, raising=False)

    async def _run():
        svc = BrowserService()
        await svc.shutdown()  # ensure fresh start picks up new timeout
        res = await svc.navigate("http://127.0.0.1:1")
        assert res.ok is False
        assert isinstance(res.error, str) and res.error

    asyncio.run(_run())


def test_restart_recycles_session(tmp_path):
    url = _write_html(tmp_path)

    async def _run():
        svc = BrowserService()
        assert (await svc.navigate(url)).ok
        assert (await svc.restart()).ok
        view = await svc.view()
        assert view.ok
        # After restart, page is the default blank page.
        assert view.data["title"] in ("", "about:blank") or view.data["url"].startswith("about:")

    asyncio.run(_run())
