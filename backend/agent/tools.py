"""Manus-style 29-tool surface for the NEXUS agent.

This module exposes the same tool *names* and shapes that the leaked Manus
system prompt uses, so future agentic features (CodeAct planning, browser
automation, deploys, etc.) can be wired in incrementally without changing the
public API surface.

Each tool is implemented as an `async` callable returning a `ToolResult`. Only
the tools required by the slide-generation pipeline have full implementations
today; the rest return a structured "not_supported_in_this_runtime" result so
that an agent loop never crashes on an unimplemented call.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from config import settings
from services.search_service import SearchService

try:  # playwright is optional
    from services.browser_service import BrowserService  # type: ignore
    _BROWSER_AVAILABLE = bool(BrowserService.is_available())
except Exception as _exc:  # pragma: no cover
    BrowserService = None  # type: ignore
    _BROWSER_AVAILABLE = False

logger = logging.getLogger("nexus.agent.tools")


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "data": self.data, "error": self.error, "meta": self.meta}


def _safe_workspace_path(rel: str) -> Path:
    """Resolve a path within the per-task sandbox workspace, blocking traversal."""
    base = settings.STORAGE_DIR / "workspace"
    base.mkdir(parents=True, exist_ok=True)
    p = (base / rel).resolve()
    if base.resolve() not in p.parents and p != base.resolve():
        raise PermissionError(f"path escapes workspace: {rel}")
    return p


# ── messaging ─────────────────────────────────────────────────────────────
async def message_notify_user(message: str, **_: Any) -> ToolResult:
    logger.info("tool.message_notify_user", extra={"message": message[:200]})
    return ToolResult(ok=True, data={"delivered": True})


async def message_ask_user(message: str, **_: Any) -> ToolResult:
    # In a non-interactive backend run we surface but do not block.
    logger.info("tool.message_ask_user", extra={"message": message[:200]})
    return ToolResult(ok=True, data={"asked": True, "answer": None})


# ── files ─────────────────────────────────────────────────────────────────
async def file_read(path: str, **_: Any) -> ToolResult:
    try:
        p = _safe_workspace_path(path)
        text = p.read_text(encoding="utf-8")
        return ToolResult(ok=True, data=text)
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc))


async def file_write(path: str, content: str, **_: Any) -> ToolResult:
    try:
        p = _safe_workspace_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult(ok=True, data={"path": str(p), "bytes": len(content.encode("utf-8"))})
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc))


async def file_str_replace(path: str, old: str, new: str, **_: Any) -> ToolResult:
    try:
        p = _safe_workspace_path(path)
        text = p.read_text(encoding="utf-8")
        if old not in text:
            return ToolResult(ok=False, error="old string not found")
        replaced = text.replace(old, new, 1)
        p.write_text(replaced, encoding="utf-8")
        return ToolResult(ok=True, data={"replacements": 1})
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc))


async def file_find_in_content(pattern: str, path: str = ".", **_: Any) -> ToolResult:
    try:
        root = _safe_workspace_path(path)
        if not root.exists():
            return ToolResult(ok=True, data=[])
        results: list[dict] = []
        targets = [root] if root.is_file() else list(root.rglob("*"))
        for f in targets:
            if not f.is_file():
                continue
            try:
                for n, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                    if pattern in line:
                        results.append({"file": str(f), "line": n, "text": line.strip()})
            except OSError:
                continue
        return ToolResult(ok=True, data=results[:200])
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc))


async def file_find_by_name(name: str, path: str = ".", **_: Any) -> ToolResult:
    try:
        root = _safe_workspace_path(path)
        if not root.exists():
            return ToolResult(ok=True, data=[])
        return ToolResult(
            ok=True, data=[str(p) for p in root.rglob(name) if p.is_file()][:200]
        )
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc))


# ── shell ─────────────────────────────────────────────────────────────────
_SHELL_PROCS: dict[str, asyncio.subprocess.Process] = {}


async def shell_exec(command: str, cwd: str = ".", timeout: int = 30, **_: Any) -> ToolResult:
    try:
        workdir = _safe_workspace_path(cwd)
        workdir.mkdir(parents=True, exist_ok=True)
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return ToolResult(ok=False, error=f"timeout after {timeout}s")
        return ToolResult(
            ok=proc.returncode == 0,
            data={
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", "ignore"),
                "stderr": stderr.decode("utf-8", "ignore"),
            },
        )
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc))


async def shell_view(name: str = "default", **_: Any) -> ToolResult:
    proc = _SHELL_PROCS.get(name)
    if proc is None:
        return ToolResult(ok=False, error="no such shell session")
    return ToolResult(ok=True, data={"pid": proc.pid, "running": proc.returncode is None})


async def shell_wait(name: str = "default", timeout: int = 30, **_: Any) -> ToolResult:
    proc = _SHELL_PROCS.get(name)
    if proc is None:
        return ToolResult(ok=False, error="no such shell session")
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
        return ToolResult(ok=True, data={"returncode": proc.returncode})
    except asyncio.TimeoutError:
        return ToolResult(ok=False, error="timeout")


async def shell_write_to_process(name: str, data: str, **_: Any) -> ToolResult:
    proc = _SHELL_PROCS.get(name)
    if proc is None or proc.stdin is None:
        return ToolResult(ok=False, error="no writable shell session")
    try:
        proc.stdin.write(data.encode("utf-8"))
        await proc.stdin.drain()
        return ToolResult(ok=True, data={"bytes": len(data)})
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc))


async def shell_kill_process(name: str = "default", **_: Any) -> ToolResult:
    proc = _SHELL_PROCS.pop(name, None)
    if proc is None:
        return ToolResult(ok=False, error="no such shell session")
    try:
        proc.kill()
        return ToolResult(ok=True, data={"killed": True})
    except ProcessLookupError:
        return ToolResult(ok=True, data={"killed": False})


# ── browser ───────────────────────────────────────────────────────────────
class _BrowserDisabled:
    async def _disabled(self, *_, **__):
        return ToolResult(ok=False, error="browser tool disabled - install browser-use/playwright separately")

    def __getattr__(self, _name):
        return self._disabled

_browser = BrowserService() if _BROWSER_AVAILABLE else _BrowserDisabled()


async def browser_view(**_: Any) -> ToolResult:
    return await _browser.view()


async def browser_navigate(url: str, **_: Any) -> ToolResult:
    return await _browser.navigate(url)


async def browser_restart(**_: Any) -> ToolResult:
    return await _browser.restart()


async def browser_click(selector: str, **_: Any) -> ToolResult:
    return await _browser.click(selector)


async def browser_input(selector: str, text: str, **_: Any) -> ToolResult:
    return await _browser.input(selector, text)


async def browser_move_mouse(x: int, y: int, **_: Any) -> ToolResult:
    return await _browser.move_mouse(x, y)


async def browser_press_key(key: str, **_: Any) -> ToolResult:
    return await _browser.press_key(key)


async def browser_select_option(selector: str, value: str, **_: Any) -> ToolResult:
    return await _browser.select_option(selector, value)


async def browser_scroll_up(pixels: int = 400, **_: Any) -> ToolResult:
    return await _browser.scroll(-abs(pixels))


async def browser_scroll_down(pixels: int = 400, **_: Any) -> ToolResult:
    return await _browser.scroll(abs(pixels))


async def browser_console_exec(script: str, **_: Any) -> ToolResult:
    return await _browser.console_exec(script)


async def browser_console_view(**_: Any) -> ToolResult:
    return await _browser.console_view()


# ── search ────────────────────────────────────────────────────────────────
_search = SearchService()


async def info_search_web(query: str, max_results: int = 5, **_: Any) -> ToolResult:
    try:
        text, sources = await _search.search(query, max_results=max_results)
        return ToolResult(ok=True, data={"summary": text, "sources": sources})
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc))


# ── deploy / output / control (stubs that return structured "unsupported") ─
async def deploy_expose_port(port: int, **_: Any) -> ToolResult:
    return ToolResult(
        ok=False,
        error="not_supported_in_this_runtime",
        meta={"hint": f"would expose port {port}"},
    )


async def deploy_apply_deployment(name: str, **_: Any) -> ToolResult:
    return ToolResult(
        ok=False,
        error="not_supported_in_this_runtime",
        meta={"hint": f"would deploy {name}"},
    )


async def make_manus_page(title: str, content: str, **_: Any) -> ToolResult:
    """Persist a markdown page artifact under workspace/pages/."""
    try:
        slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-") or "page"
        path = f"pages/{slug}.md"
        await file_write(path, f"# {title}\n\n{content}\n")
        return ToolResult(ok=True, data={"path": path})
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc))


async def idle(**_: Any) -> ToolResult:
    return ToolResult(ok=True, data={"idle": True})


# ── registry ──────────────────────────────────────────────────────────────
TOOLS: dict[str, Callable[..., Awaitable[ToolResult]]] = {
    "message_notify_user": message_notify_user,
    "message_ask_user": message_ask_user,
    "file_read": file_read,
    "file_write": file_write,
    "file_str_replace": file_str_replace,
    "file_find_in_content": file_find_in_content,
    "file_find_by_name": file_find_by_name,
    "shell_exec": shell_exec,
    "shell_view": shell_view,
    "shell_wait": shell_wait,
    "shell_write_to_process": shell_write_to_process,
    "shell_kill_process": shell_kill_process,
    "browser_view": browser_view,
    "browser_navigate": browser_navigate,
    "browser_restart": browser_restart,
    "browser_click": browser_click,
    "browser_input": browser_input,
    "browser_move_mouse": browser_move_mouse,
    "browser_press_key": browser_press_key,
    "browser_select_option": browser_select_option,
    "browser_scroll_up": browser_scroll_up,
    "browser_scroll_down": browser_scroll_down,
    "browser_console_exec": browser_console_exec,
    "browser_console_view": browser_console_view,
    "info_search_web": info_search_web,
    "deploy_expose_port": deploy_expose_port,
    "deploy_apply_deployment": deploy_apply_deployment,
    "make_manus_page": make_manus_page,
    "idle": idle,
}


async def call_tool(name: str, **kwargs: Any) -> ToolResult:
    """Dispatch by tool name. Unknown tools return a structured error."""
    fn = TOOLS.get(name)
    if fn is None:
        return ToolResult(ok=False, error=f"unknown tool: {name}")
    try:
        return await fn(**kwargs)
    except TypeError as exc:
        return ToolResult(ok=False, error=f"bad arguments to {name}: {exc}")
    except Exception as exc:
        logger.exception("tool.unhandled", extra={"tool": name})
        return ToolResult(ok=False, error=str(exc))


# Sanity check at import time: 29 tools, exactly like Manus.
assert len(TOOLS) == 29, f"expected 29 tools, found {len(TOOLS)}"
