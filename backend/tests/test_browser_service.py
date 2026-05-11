"""Default-path browser service tests.

These run in CI with Playwright NOT installed (or BROWSER_ENABLED=false). They
verify that the browser surface fails-soft and that the 29-tool registry is
intact.
"""

from __future__ import annotations

import asyncio
import importlib

import pytest

from config import settings
from services import browser_service as bs_module
from services.browser_service import BrowserService, ToolResult, _DISABLED_MSG


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_browser_service_singleton_identity():
    a = BrowserService()
    b = BrowserService()
    assert a is b


def test_browser_disabled_when_setting_off(monkeypatch):
    monkeypatch.setattr(settings, "BROWSER_ENABLED", False, raising=False)
    assert BrowserService.is_available() is False
    svc = BrowserService()

    async def _check():
        for call in (
            svc.restart(),
            svc.navigate("https://example.com"),
            svc.view(),
            svc.click("#x"),
            svc.input("#x", "y"),
            svc.move_mouse(1, 2),
            svc.press_key("Enter"),
            svc.select_option("#s", "v"),
            svc.scroll(100),
            svc.console_exec("1+1"),
        ):
            res = await call
            assert isinstance(res, ToolResult)
            assert res.ok is False
            assert res.error == _DISABLED_MSG

    asyncio.run(_check())


def test_browser_disabled_when_playwright_missing(monkeypatch):
    # Force the module-level flag off, which is what an ImportError would do.
    monkeypatch.setattr(bs_module, "_PLAYWRIGHT_AVAILABLE", False, raising=False)
    monkeypatch.setattr(settings, "BROWSER_ENABLED", True, raising=False)
    assert BrowserService.is_available() is False
    svc = BrowserService()

    async def _check():
        res = await svc.navigate("https://example.com")
        assert res.ok is False
        assert res.error == _DISABLED_MSG

    asyncio.run(_check())


def test_tool_result_shape_disabled(monkeypatch):
    monkeypatch.setattr(settings, "BROWSER_ENABLED", False, raising=False)
    svc = BrowserService()
    res = asyncio.run(svc.view())
    d = res.to_dict()
    assert set(d.keys()) == {"ok", "data", "error", "meta"}
    assert d["ok"] is False
    assert isinstance(d["error"], str) and d["error"]


def test_tools_registry_has_29_entries_and_browser_names(monkeypatch):
    monkeypatch.setattr(settings, "BROWSER_ENABLED", False, raising=False)
    # Re-import tools module to make sure no regression on its import-time assert.
    from agent import tools as tools_module
    importlib.reload(tools_module)
    assert len(tools_module.TOOLS) == 29
    expected_browser = {
        "browser_view",
        "browser_navigate",
        "browser_restart",
        "browser_click",
        "browser_input",
        "browser_move_mouse",
        "browser_press_key",
        "browser_select_option",
        "browser_scroll_up",
        "browser_scroll_down",
        "browser_console_exec",
        "browser_console_view",
    }
    assert expected_browser.issubset(set(tools_module.TOOLS.keys()))


def test_tools_browser_disabled_returns_structured_error(monkeypatch):
    monkeypatch.setattr(settings, "BROWSER_ENABLED", False, raising=False)
    from agent import tools as tools_module
    importlib.reload(tools_module)

    async def _check():
        for name in (
            "browser_view",
            "browser_navigate",
            "browser_restart",
            "browser_click",
            "browser_input",
            "browser_move_mouse",
            "browser_press_key",
            "browser_select_option",
            "browser_scroll_up",
            "browser_scroll_down",
            "browser_console_exec",
            "browser_console_view",
        ):
            fn = tools_module.TOOLS[name]
            # Provide minimal kwargs so signature checks pass.
            kwargs = {}
            if name == "browser_navigate":
                kwargs = {"url": "https://example.com"}
            elif name in ("browser_click",):
                kwargs = {"selector": "#x"}
            elif name == "browser_input":
                kwargs = {"selector": "#x", "text": "y"}
            elif name == "browser_move_mouse":
                kwargs = {"x": 1, "y": 2}
            elif name == "browser_press_key":
                kwargs = {"key": "Enter"}
            elif name == "browser_select_option":
                kwargs = {"selector": "#s", "value": "v"}
            elif name == "browser_console_exec":
                kwargs = {"script": "1+1"}
            res = await fn(**kwargs)
            d = res.to_dict()
            assert d["ok"] is False
            assert isinstance(d["error"], str) and d["error"]

    asyncio.run(_check())
