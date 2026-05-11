"""GET / PUT /api/slides/{task_id} — full slide JSON for a completed task."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import SlideDeck, Task
from agent.deck_quality import attach_quality_report
from agent.slide_schema import validate_deck
from services.claim_citation_service import map_deck_citations

logger = logging.getLogger("nexus.api.slides")

router = APIRouter()


@router.get("/slides/{task_id}")
async def get_slides(task_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    res = await db.execute(select(Task).where(Task.id == task_id))
    task = res.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Task is {task.status}, slides not ready yet.",
        )

    deck_res = await db.execute(select(SlideDeck).where(SlideDeck.task_id == task_id))
    deck = deck_res.scalar_one_or_none()
    if deck is None:
        raise HTTPException(status_code=404, detail="Slide deck not found")

    deck_data = deck.slide_data or []
    payload = {
        "task_id": task.id,
        "topic": task.topic,
        "theme": deck.theme,
        "slide_count": deck.slide_count,
        "slides": deck_data,
    }
    # Phase 1D: surface the non-destructive DeckQualityReport on the
    # response. Computed on read; not persisted; backward-compatible.
    return attach_quality_report(payload, deck_data)


# ── Phase 6L-UX-Fix: server-side persistence of edited decks ──────────────


class SlideDeckUpdateRequest(BaseModel):
    """Payload accepted by ``PUT /api/slides/{task_id}``.

    ``slides`` must be a list of slide dicts; each is validated via
    :func:`agent.slide_schema.validate_deck` before any DB write. ``theme``
    is optional; when present, the existing ``SlideDeck.theme`` value is
    overwritten with it. No new task is created and no migration runs —
    edits are saved in-place on the existing ``SlideDeck`` row.
    """

    slides: list[dict[str, Any]] = Field(..., min_length=1)
    theme: str | None = Field(default=None, max_length=64)


@router.put("/slides/{task_id}")
async def update_slides(
    task_id: str,
    payload: SlideDeckUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Persist user-edited slides for an existing completed task.

    Validation contract:
    * Task must exist and be ``status == "done"`` (same precondition as GET).
    * ``slides`` must validate cleanly via ``validate_deck``; on any error,
      respond 400 and leave the existing ``SlideDeck`` row untouched.
    * On success, ``slide_data`` / ``slide_count`` / ``theme`` (if provided)
      are updated in place; the response shape matches GET.
    """

    res = await db.execute(select(Task).where(Task.id == task_id))
    task = res.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Task is {task.status}, slides not ready yet.",
        )

    deck_res = await db.execute(select(SlideDeck).where(SlideDeck.task_id == task_id))
    deck = deck_res.scalar_one_or_none()
    if deck is None:
        raise HTTPException(status_code=404, detail="Slide deck not found")

    # Validate every slide against the canonical contract. Any failure ⇒
    # 400 with structured per-slide errors and the existing deck is NOT
    # overwritten.
    results = validate_deck(payload.slides)
    invalid = [
        {
            "index": i,
            "layout": r.layout,
            "errors": [e.to_dict() for e in r.errors],
        }
        for i, r in enumerate(results)
        if not r.ok
    ]
    if invalid:
        logger.info(
            "slides.put_rejected",
            extra={"task_id": task_id, "invalid_count": len(invalid)},
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_deck",
                "message": "One or more slides failed validation; deck not saved.",
                "invalid_slides": invalid,
            },
        )

    # All slides valid — persist normalized payloads (canonical layout name
    # pinned, content fields unchanged). Existing row is updated in-place
    # so PPTX/PDF/share continue to read from the same SlideDeck source.
    normalized_slides: list[dict[str, Any]] = [r.normalized for r in results if r.normalized is not None]
    deck.slide_data = normalized_slides
    deck.slide_count = len(normalized_slides)
    if payload.theme:
        deck.theme = payload.theme
    db.add(deck)
    await db.commit()
    await db.refresh(deck)

    logger.info(
        "slides.put_ok",
        extra={"task_id": task_id, "slide_count": deck.slide_count, "theme": deck.theme},
    )

    response = {
        "task_id": task.id,
        "topic": task.topic,
        "theme": deck.theme,
        "slide_count": deck.slide_count,
        "slides": deck.slide_data or [],
    }
    return attach_quality_report(response, deck.slide_data or [])


# ── Phase 6N: claim-level citations report for a saved deck ───────────────


@router.get("/slides/{task_id}/citations")
async def get_slides_citations(
    task_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """Return the deterministic claim-level citation report for a deck.

    Uses :func:`services.claim_citation_service.map_deck_citations` so the
    matching algorithm is **not** duplicated. Behavior:

    * 404 if the task does not exist.
    * 409 if the task is not yet ``done`` (same precondition as GET).
    * If the ``SlideDeck`` row is missing, returns the empty report rather
      than 404 — the report endpoint is read-only and should degrade
      gracefully for decks that were never persisted.
    * Always returns the report shape from ``map_deck_citations`` plus
      ``task_id``. ``claims`` is grouped by slide via the embedded
      ``slide_index`` field; the frontend folds claims by that key.
    * If the deck has no source-bearing slides, ``claims`` will still be
      populated (with ``supported=False`` / ``basis="no_match"``); the
      summary makes the "no evidence" state explicit.
    """

    res = await db.execute(select(Task).where(Task.id == task_id))
    task = res.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Task is {task.status}, slides not ready yet.",
        )

    deck_res = await db.execute(select(SlideDeck).where(SlideDeck.task_id == task_id))
    deck = deck_res.scalar_one_or_none()
    slides = deck.slide_data if (deck is not None and deck.slide_data) else []

    # ``map_deck_citations`` accepts a deck-shaped dict. We pass the
    # slides as-is; per-slide ``sources`` arrays are picked up via the
    # service's own ``_collect_sources`` helper.
    report = map_deck_citations({"slides": slides})
    report["task_id"] = task.id
    return report
