"""GET /api/artifacts/{task_id}/{name} \u2014 expose agent intermediate artifacts.

Manus-style transparency: lets the user fetch the raw research, the deck
draft, the refined draft, and the source list that the agent produced for a
given task. Read-only. No auth (artifacts live under the task scope; if the
task is private, the file 404s).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

from config import settings

logger = logging.getLogger("nexus.api.artifacts")

router = APIRouter()

# Whitelist of artifact filenames the agent writes. Anything else \u2192 404.
_ALLOWED = {
    "raw_research.md",
    "deck_draft.md",
    "deck_final.md",
    "sources.json",
    "outline.json",
    "profile.json",
    "research.txt",
    "todo.md",
}


def _safe_path(task_id: str, name: str) -> Path:
    if not task_id or "/" in task_id or ".." in task_id:
        raise HTTPException(status_code=400, detail="invalid task_id")
    if name not in _ALLOWED:
        raise HTTPException(status_code=404, detail="unknown artifact")
    return settings.MEMORY_DIR / task_id / name


@router.get("/artifacts/{task_id}", tags=["artifacts"])
async def list_artifacts(task_id: str) -> dict:
    """Return which artifacts exist for this task, with sizes."""
    root = settings.MEMORY_DIR / task_id
    if not root.exists():
        return {"task_id": task_id, "artifacts": []}
    out = []
    for name in sorted(_ALLOWED):
        p = root / name
        if p.exists():
            out.append({"name": name, "size": p.stat().st_size})
    return {"task_id": task_id, "artifacts": out}


@router.get("/artifacts/{task_id}/{name}", tags=["artifacts"])
async def get_artifact(task_id: str, name: str):
    path = _safe_path(task_id, name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("artifact.read_failed", extra={"err": str(exc)})
        raise HTTPException(status_code=500, detail="read failed")
    if name.endswith(".json"):
        import json
        try:
            return JSONResponse(json.loads(text or "null"))
        except json.JSONDecodeError:
            return PlainTextResponse(text, media_type="application/json")
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")
