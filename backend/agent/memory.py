"""File-based agent memory — todo.md style state per task.

Mirrors the Manus pattern: every step appends to / mutates a small set of
plain-text and JSON files inside `backend/.memory/<task_id>/`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger("nexus.agent.memory")


class AgentMemory:
    """Per-task scratch space backed by files (no DB needed).

    Layout under MEMORY_DIR / task_id:
        todo.md         — human-readable checklist
        outline.json    — planner output
        research.txt    — raw research findings
        slides/*.json   — one JSON file per generated slide
    """

    def __init__(self, task_id: str) -> None:
        if not task_id:
            raise ValueError("task_id is required")
        self.task_id = task_id
        self.root: Path = settings.MEMORY_DIR / task_id
        self.slides_dir: Path = self.root / "slides"
        self.root.mkdir(parents=True, exist_ok=True)
        self.slides_dir.mkdir(parents=True, exist_ok=True)

    # ── todo.md ────────────────────────────────────────────────────────────
    def write_todo(self, outline: list[dict[str, Any]]) -> None:
        lines = [f"# Task {self.task_id}", f"_Created: {self._now()}_", ""]
        for i, item in enumerate(outline):
            lines.append(
                f"- [ ] **{i + 1:02d}** ({item.get('layout','?')}): {item.get('title','')}"
            )
        try:
            (self.root / "todo.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("memory.write_todo_failed", extra={"err": str(exc)})

    def mark_todo_done(self, index: int) -> None:
        path = self.root / "todo.md"
        if not path.exists():
            return
        try:
            text = path.read_text(encoding="utf-8")
            marker = f"**{index + 1:02d}**"
            new = text.replace(f"- [ ] {marker}", f"- [x] {marker}", 1)
            path.write_text(new, encoding="utf-8")
        except OSError as exc:
            logger.warning("memory.mark_done_failed", extra={"err": str(exc)})

    # ── structured artifacts ───────────────────────────────────────────────
    def write_outline(self, outline: list[dict[str, Any]]) -> None:
        self._write_json(self.root / "outline.json", outline)

    def read_outline(self) -> list[dict[str, Any]]:
        return self._read_json(self.root / "outline.json", default=[])

    def write_research(self, text: str) -> None:
        try:
            (self.root / "research.txt").write_text(text or "", encoding="utf-8")
        except OSError as exc:
            logger.warning("memory.write_research_failed", extra={"err": str(exc)})

    def read_research(self) -> str:
        path = self.root / "research.txt"
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def write_slide(self, index: int, slide: dict[str, Any]) -> None:
        self._write_json(self.slides_dir / f"{index:03d}.json", slide)

    def write_artifact(self, name: str, data: Any) -> None:
        """Persist a generic JSON artifact under the run's memory root.

        Phase 6V uses this for the deck-strategy artifact ("strategy.json")
        so the strategy is observable alongside ``research.txt``,
        ``outline.json`` and the per-slide files. ``name`` is treated as
        a leaf filename: any path separators are stripped to keep writes
        inside ``self.root``.
        """
        safe = (name or "").replace("/", "_").replace("\\", "_").strip()
        if not safe:
            return
        self._write_json(self.root / safe, data)

    def read_slides(self) -> list[dict[str, Any]]:
        slides: list[dict[str, Any]] = []
        for path in sorted(self.slides_dir.glob("*.json")):
            data = self._read_json(path, default=None)
            if isinstance(data, dict):
                slides.append(data)
        return slides

    # ── internals ──────────────────────────────────────────────────────────
    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        try:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except (OSError, TypeError) as exc:
            logger.warning(
                "memory.write_json_failed", extra={"path": str(path), "err": str(exc)}
            )

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default
