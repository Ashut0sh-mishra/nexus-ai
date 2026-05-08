"""Deck version snapshots for undo / history (PRD §14)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_optional_user
from database.connection import get_db
from database.models import DeckVersion, Slide, SlideDeck, Task, User

logger = logging.getLogger("nexus.api.versions")
router = APIRouter()


def _serialize(v: DeckVersion, *, include_snapshot: bool = False) -> dict[str, Any]:
    out = {
        "id": v.id,
        "task_id": v.task_id,
        "version": v.version,
        "label": v.label,
        "created_by": v.created_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }
    if include_snapshot:
        out["snapshot"] = v.snapshot_json
    return out


@router.get(
    "/decks/{task_id}/versions",
    summary="List version snapshots for a deck (newest first).",
)
async def list_versions(
    task_id: str, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(DeckVersion)
            .where(DeckVersion.task_id == task_id)
            .order_by(DeckVersion.version.desc())
        )
    ).scalars().all()
    return [_serialize(r) for r in rows]


@router.post(
    "/decks/{task_id}/versions",
    summary="Snapshot the current deck state as a new version.",
)
async def create_version(
    task_id: str,
    label: Optional[str] = Body(default=None, embed=True),
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    rows = (
        await db.execute(
            select(Slide).where(Slide.task_id == task_id).order_by(Slide.slide_number)
        )
    ).scalars().all()
    deck = (
        await db.execute(select(SlideDeck).where(SlideDeck.task_id == task_id))
    ).scalar_one_or_none()

    snapshot = {
        "topic": task.topic,
        "theme": deck.theme if deck else task.theme,
        "slides": [
            {
                "id": r.id,
                "slide_number": r.slide_number,
                "slide_type": r.slide_type,
                "title": r.title,
                "subtitle": r.subtitle,
                "content_json": r.content_json,
                "chart_data_json": r.chart_data_json,
                "image_data_json": r.image_data_json,
                "speaker_notes": r.speaker_notes,
                "layout_metadata": r.layout_metadata,
                "design_tokens": r.design_tokens,
            }
            for r in rows
        ],
    }

    next_version = (
        await db.execute(
            select(func.coalesce(func.max(DeckVersion.version), 0)).where(
                DeckVersion.task_id == task_id
            )
        )
    ).scalar_one() + 1

    v = DeckVersion(
        task_id=task_id,
        version=next_version,
        label=label,
        snapshot_json=snapshot,
        created_by=(user.id if user else None),
    )
    db.add(v)
    await db.commit()
    await db.refresh(v)
    logger.info("decks.version_create", extra={"task_id": task_id, "version": next_version})
    return _serialize(v)


@router.get(
    "/decks/{task_id}/versions/{version}",
    summary="Fetch a specific deck snapshot (full slide data).",
)
async def get_version(
    task_id: str, version: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    v = (
        await db.execute(
            select(DeckVersion).where(
                DeckVersion.task_id == task_id, DeckVersion.version == version
            )
        )
    ).scalar_one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return _serialize(v, include_snapshot=True)


@router.post(
    "/decks/{task_id}/versions/{version}/restore",
    summary="Restore the deck to a prior snapshot. Current state is auto-snapshotted first.",
)
async def restore_version(
    task_id: str,
    version: int,
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    v = (
        await db.execute(
            select(DeckVersion).where(
                DeckVersion.task_id == task_id, DeckVersion.version == version
            )
        )
    ).scalar_one_or_none()
    if v is None:
        raise HTTPException(status_code=404, detail="Version not found")

    snapshot = v.snapshot_json or {}
    new_slides = snapshot.get("slides") or []

    # Auto-snapshot current state before restoring (so restore is undoable).
    current = (
        await db.execute(
            select(Slide).where(Slide.task_id == task_id).order_by(Slide.slide_number)
        )
    ).scalars().all()
    if current:
        cur_snap = {
            "topic": (await db.execute(select(Task.topic).where(Task.id == task_id))).scalar_one(),
            "slides": [
                {
                    "id": r.id, "slide_number": r.slide_number,
                    "slide_type": r.slide_type, "title": r.title, "subtitle": r.subtitle,
                    "content_json": r.content_json, "chart_data_json": r.chart_data_json,
                    "image_data_json": r.image_data_json, "speaker_notes": r.speaker_notes,
                    "layout_metadata": r.layout_metadata, "design_tokens": r.design_tokens,
                }
                for r in current
            ],
        }
        next_v = (
            await db.execute(
                select(func.coalesce(func.max(DeckVersion.version), 0)).where(
                    DeckVersion.task_id == task_id
                )
            )
        ).scalar_one() + 1
        db.add(DeckVersion(
            task_id=task_id, version=next_v, label=f"auto-before-restore-v{version}",
            snapshot_json=cur_snap, created_by=(user.id if user else None),
        ))

    # Wipe + reinsert.
    await db.execute(delete(Slide).where(Slide.task_id == task_id))
    await db.flush()
    for entry in new_slides:
        db.add(Slide(
            task_id=task_id,
            slide_number=entry.get("slide_number") or 1,
            slide_type=entry.get("slide_type") or "content",
            title=entry.get("title") or "",
            subtitle=entry.get("subtitle"),
            content_json=entry.get("content_json"),
            chart_data_json=entry.get("chart_data_json"),
            image_data_json=entry.get("image_data_json"),
            speaker_notes=entry.get("speaker_notes"),
            layout_metadata=entry.get("layout_metadata"),
            design_tokens=entry.get("design_tokens"),
        ))
    await db.flush()

    # Resync the JSON-blob deck row.
    deck = (
        await db.execute(select(SlideDeck).where(SlideDeck.task_id == task_id))
    ).scalar_one_or_none()
    if deck is not None:
        from api.routes.slides import slide_row_to_dict, _resync_deck_blob  # late import
        await _resync_deck_blob(db, task_id)

    await db.commit()
    logger.info("decks.version_restore", extra={"task_id": task_id, "version": version})
    return {"task_id": task_id, "restored_to": version, "slide_count": len(new_slides)}
