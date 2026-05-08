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

    def write_profile(self, profile: dict[str, Any]) -> None:
        """Persist the editorial profile (topic_classifier output)."""
        self._write_json(self.root / "profile.json", profile or {})

    def read_profile(self) -> dict[str, Any]:
        return self._read_json(self.root / "profile.json", default={})

    def write_artifact(self, name: str, content: str) -> None:
        """Write an arbitrary text artifact (markdown, json string, etc.).

        Used by the markdown pipeline to expose ``raw_research.md``,
        ``deck_draft.md``, ``deck_final.md``, and ``sources.json`` so the
        user can inspect every step the agent took.
        """
        try:
            (self.root / name).write_text(content or "", encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "memory.write_artifact_failed",
                extra={"name": name, "err": str(exc)},
            )

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
