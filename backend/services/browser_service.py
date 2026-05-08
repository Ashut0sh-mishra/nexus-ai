"""Browser automation stub.

Browser-use / Playwright are heavy optional dependencies and are intentionally
omitted from the default backend image to keep dependency resolution clean.
This module preserves the public surface used by `agent.tools` so the rest of
the system never has to special-case the missing dependency.

To enable real browser automation later:
    pip install browser-use playwright
    playwright install chromium
and replace this stub with the full Playwright-backed implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("nexus.services.browser")

_DISABLED_MSG = "Browser tool disabled - install browser-use separately"


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "data": self.data, "error": self.error, "meta": self.meta}


class BrowserService:
    """No-op browser service. Always returns disabled ToolResult."""

    _instance: "BrowserService | None" = None

    def __new__(cls) -> "BrowserService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def _disabled(self) -> ToolResult:
        return ToolResult(ok=False, error=_DISABLED_MSG)

    async def restart(self) -> ToolResult:
        return await self._disabled()

    async def navigate(self, url: str) -> ToolResult:
        return await self._disabled()

    async def view(self) -> ToolResult:
        return await self._disabled()

    async def click(self, selector: str) -> ToolResult:
        return await self._disabled()

    async def input(self, selector: str, text: str) -> ToolResult:
        return await self._disabled()

    async def move_mouse(self, x: int, y: int) -> ToolResult:
        return await self._disabled()

    async def press_key(self, key: str) -> ToolResult:
        return await self._disabled()

    async def select_option(self, selector: str, value: str) -> ToolResult:
        return await self._disabled()

    async def scroll(self, dy: int) -> ToolResult:
        return await self._disabled()

    async def console_exec(self, script: str) -> ToolResult:
        return await self._disabled()

    async def console_view(self) -> ToolResult:
        return await self._disabled()


async def browse_url(url: str) -> str:
    return f"Browser tool disabled - install browser-use separately"
