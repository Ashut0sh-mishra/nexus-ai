"""Slide CRUD endpoints.

Routes
------
- ``GET    /api/slides/{task_id}``                        — full deck
- ``GET    /api/slides/{task_id}/{slide_id}``             — one slide
- ``PUT    /api/slides/{task_id}/{slide_id}``             — patch one slide
- ``DELETE /api/slides/{task_id}/{slide_id}``             — drop one slide
- ``POST   /api/slides/{task_id}/reorder``                — reorder list
- ``POST   /api/slides/{task_id}/{slide_id}/regenerate``  — AI rewrite

``slide_id`` is the UUID primary key of a ``Slide`` row in ``deck_slides``.

All mutating endpoints rebuild ``SlideDeck.slide_data`` (the JSON blob the
existing renderer / export pipeline reads) so downstream consumers stay in
sync without needing schema-aware joins.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.prompts import CRITIC_SYSTEM_PROMPT, critic_user_message
from database.connection import get_db
from database.models import Slide, SlideDeck, Task
from services.claude_service import ClaudeService

logger = logging.getLogger("nexus.api.slides")

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────────────────
def slide_row_to_dict(row: Slide) -> dict[str, Any]:
    """Inverse of ``NexusAgentLoop._slide_dict_to_row_kwargs``.

    Reassembles a flat slide payload (the shape the renderer / export expects)
    from the column-split representation in ``deck_slides``.
    """
    out: dict[str, Any] = {
        "id": row.id,
        "slide_id": row.id,
        "slide_number": row.slide_number,
        "layout": row.slide_type or "bullets",
        "title": row.title or "",
    }
    if row.subtitle:
        out["subtitle"] = row.subtitle

    # content_json carries layout-specific fields (bullets, columns, kpis, …).
    if isinstance(row.content_json, dict):
        for k, v in row.content_json.items():
            out.setdefault(k, v)

    # chart_data_json stores the legacy fields plus an optional processed
    # envelope under "envelope".
    if isinstance(row.chart_data_json, dict):
        cd = dict(row.chart_data_json)
        envelope = cd.pop("envelope", None)
        for k in ("chart_type", "labels", "values", "unit", "source", "datasets"):
            if k in cd:
                out[k] = cd[k]
        if any(k in cd for k in ("labels", "values", "unit", "source")):
            out["chart_data"] = {
                k: cd[k]
                for k in ("labels", "values", "unit", "source")
                if k in cd
            }
        if isinstance(envelope, dict):
            out["chart"] = envelope

    # image_data_json holds either the recommend_images envelope or a
    # legacy {url, prompt} pair.
    if isinstance(row.image_data_json, dict):
        img = row.image_data_json
        if img.get("url"):
            out["image_url"] = img["url"]
        if img.get("prompt"):
            out["image_prompt"] = img["prompt"]
        # Keep the full envelope when present.
        if any(k in img for k in ("source", "placement", "credit", "alt")):
            out["image"] = img

    if isinstance(row.layout_metadata, dict):
        for k, v in row.layout_metadata.items():
            out.setdefault(k, v)

    if row.speaker_notes:
        out["speaker_notes"] = row.speaker_notes

    return out


def slide_dict_to_row_kwargs(
    slide_number: int, slide: dict[str, Any]
) -> dict[str, Any]:
    """Local copy of the loop's payload→column splitter.

    Imported lazily to avoid pulling the full agent stack into request paths.
    """
    from agent.loop import NexusAgentLoop  # local import keeps cold-start light

    return NexusAgentLoop._slide_dict_to_row_kwargs(slide_number - 1, slide)


async def _resync_deck_blob(db: AsyncSession, task_id: str) -> list[dict[str, Any]]:
    """Rebuild ``SlideDeck.slide_data`` (JSON blob) from current ``Slide`` rows.

    Returns the new ordered slide-dict list.
    """
    res = await db.execute(
        select(Slide).where(Slide.task_id == task_id).order_by(Slide.slide_number)
    )
    rows = list(res.scalars().all())
    slides = [slide_row_to_dict(r) for r in rows]

    deck_res = await db.execute(select(SlideDeck).where(SlideDeck.task_id == task_id))
    deck = deck_res.scalar_one_or_none()
    if deck is not None:
        deck.slide_data = slides
        deck.slide_count = len(slides)
        db.add(deck)
    return slides


async def _renumber(db: AsyncSession, task_id: str) -> None:
    """Compact ``slide_number`` to 1..N after a delete/reorder.

    The unique ``(task_id, slide_number)`` constraint forces a two-pass
    update: bump every row by a large offset, then write the final values.
    """
    res = await db.execute(
        select(Slide).where(Slide.task_id == task_id).order_by(Slide.slide_number)
    )
    rows = list(res.scalars().all())
    OFFSET = 100_000
    for r in rows:
        r.slide_number += OFFSET
        db.add(r)
    await db.flush()
    for new_num, r in enumerate(rows, start=1):
        r.slide_number = new_num
        db.add(r)
    await db.flush()


async def _load_slide(
    db: AsyncSession, task_id: str, slide_id: str
) -> Slide:
    res = await db.execute(
        select(Slide).where(Slide.task_id == task_id, Slide.id == slide_id)
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Slide not found")
    return row


def _strip_fences(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_single_slide(text: str) -> dict[str, Any] | None:
    cleaned = _strip_fences(text)
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


# ── request models ───────────────────────────────────────────────────────────
class SlideUpdate(BaseModel):
    """Patch payload for a single slide.

    Any subset of editor-relevant fields may be supplied. Unknown keys are
    accepted and merged into ``content_json`` so layout-specific extensions
    keep round-tripping through the editor without losing data.
    """

    model_config = {"extra": "allow"}

    title: str | None = None
    subtitle: str | None = None
    layout: str | None = None
    speaker_notes: str | None = None


class ReorderRequest(BaseModel):
    slide_ids: list[str] = Field(..., min_length=1, description="New order")


class RegenerateRequest(BaseModel):
    instruction: str | None = Field(
        default=None,
        description="Optional user guidance for the rewrite.",
    )
    keep_layout: bool = True


# ── routes ───────────────────────────────────────────────────────────────────
@router.get(
    "/slides/{task_id}",
    summary="Get the full slide deck for a task.",
    description=(
        "Returns the canonical slide list, theme, and topic for a generation task. "
        "Reads from the per-row `deck_slides` store when available so any edits "
        "made via PUT/DELETE/reorder are reflected immediately."
    ),
    responses={
        404: {"description": "Task or deck not found."},
        409: {"description": "Task is still running; slides not ready yet."},
    },
)
async def get_deck(task_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    res = await db.execute(select(Task).where(Task.id == task_id))
    task = res.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    deck_res = await db.execute(select(SlideDeck).where(SlideDeck.task_id == task_id))
    deck = deck_res.scalar_one_or_none()

    # Prefer the per-row store when available so edits show up immediately.
    rows_res = await db.execute(
        select(Slide).where(Slide.task_id == task_id).order_by(Slide.slide_number)
    )
    rows = list(rows_res.scalars().all())
    if rows:
        slides = [slide_row_to_dict(r) for r in rows]
    elif deck is not None:
        slides = deck.slide_data or []
    else:
        if task.status != "done":
            raise HTTPException(
                status_code=409,
                detail=f"Task is {task.status}, slides not ready yet.",
            )
        raise HTTPException(status_code=404, detail="Slide deck not found")

    return {
        "task_id": task.id,
        "topic": task.topic,
        "theme": (deck.theme if deck else None),
        "slide_count": len(slides),
        "slides": slides,
    }


@router.get(
    "/slides/{task_id}/{slide_id}",
    summary="Get a single slide.",
    responses={404: {"description": "Slide not found."}},
)
async def get_slide(
    task_id: str, slide_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    row = await _load_slide(db, task_id, slide_id)
    return slide_row_to_dict(row)


@router.put(
    "/slides/{task_id}/{slide_id}",
    summary="Update a single slide (partial patch).",
    description=(
        "Applies a JSON merge patch to the slide. Unknown fields are preserved in "
        "`content_json` so layout-specific extensions round-trip cleanly."
    ),
    responses={404: {"description": "Slide not found."}},
)
async def update_slide(
    task_id: str,
    slide_id: str,
    payload: SlideUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await _load_slide(db, task_id, slide_id)

    # Merge incoming fields onto the current slide dict, then re-split.
    current = slide_row_to_dict(row)
    update = payload.model_dump(exclude_none=True)
    # Strip identity / housekeeping fields the client may echo back.
    for k in ("id", "slide_id", "slide_number"):
        update.pop(k, None)
    merged = {**current, **update}

    kwargs = slide_dict_to_row_kwargs(row.slide_number, merged)
    # slide_number stays put on a PUT; reorder uses its own endpoint.
    kwargs.pop("slide_number", None)
    for k, v in kwargs.items():
        setattr(row, k, v)
    db.add(row)
    await db.flush()
    await _resync_deck_blob(db, task_id)
    await db.commit()
    await db.refresh(row)
    logger.info("slides.update", extra={"task_id": task_id, "slide_id": slide_id})
    return slide_row_to_dict(row)


@router.delete(
    "/slides/{task_id}/{slide_id}",
    summary="Delete a slide and renumber the rest of the deck.",
    responses={404: {"description": "Slide not found."}},
)
async def delete_slide(
    task_id: str, slide_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    row = await _load_slide(db, task_id, slide_id)
    await db.delete(row)
    await db.flush()
    await _renumber(db, task_id)
    slides = await _resync_deck_blob(db, task_id)
    await db.commit()
    logger.info(
        "slides.delete",
        extra={"task_id": task_id, "slide_id": slide_id, "remaining": len(slides)},
    )
    return {"task_id": task_id, "slide_count": len(slides), "slides": slides}


@router.post(
    "/slides/{task_id}/reorder",
    summary="Reorder all slides in a deck.",
    description=(
        "`slide_ids` must be a permutation of every slide in the deck — the "
        "endpoint returns 400 otherwise."
    ),
    responses={
        400: {"description": "`slide_ids` is not a permutation of the deck."},
        404: {"description": "Task has no slides."},
    },
)
async def reorder_slides(
    task_id: str,
    payload: ReorderRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(Slide).where(Slide.task_id == task_id))
    rows = {r.id: r for r in res.scalars().all()}
    if not rows:
        raise HTTPException(status_code=404, detail="No slides for task")

    requested = list(payload.slide_ids)
    if set(requested) != set(rows.keys()):
        raise HTTPException(
            status_code=400,
            detail="slide_ids must be a permutation of the deck's slide IDs.",
        )

    # Two-pass update (offset, then final) to dodge the unique constraint.
    OFFSET = 100_000
    for r in rows.values():
        r.slide_number += OFFSET
        db.add(r)
    await db.flush()
    for new_num, sid in enumerate(requested, start=1):
        rows[sid].slide_number = new_num
        db.add(rows[sid])
    await db.flush()

    slides = await _resync_deck_blob(db, task_id)
    await db.commit()
    logger.info(
        "slides.reorder", extra={"task_id": task_id, "n": len(requested)}
    )
    return {"task_id": task_id, "slide_count": len(slides), "slides": slides}


@router.post(
    "/slides/{task_id}/{slide_id}/regenerate",
    summary="Regenerate a single slide using the AI critic.",
    description=(
        "Re-runs the critic prompt on this slide with optional user `instruction`. "
        "Set `keep_layout` to false to allow the model to switch layouts."
    ),
    responses={
        404: {"description": "Slide or task not found."},
        502: {"description": "Model failed or returned invalid JSON."},
    },
)
async def regenerate_slide(
    task_id: str,
    slide_id: str,
    payload: RegenerateRequest = Body(default_factory=RegenerateRequest),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await _load_slide(db, task_id, slide_id)

    task_res = await db.execute(select(Task).where(Task.id == task_id))
    task = task_res.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    current = slide_row_to_dict(row)
    topic = task.topic or current.get("title", "")
    research = ""  # research findings are not persisted per-slide

    user = critic_user_message(topic, research, current)
    if payload.instruction:
        user = f"{user}\n\nUser guidance: {payload.instruction.strip()[:1000]}"

    claude = ClaudeService()
    try:
        text, tokens, cost = await claude.complete(
            system=CRITIC_SYSTEM_PROMPT,
            user=user,
            max_tokens=1024,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("slides.regenerate_failed", extra={"err": str(exc)})
        raise HTTPException(status_code=502, detail="Slide regeneration failed") from exc

    rewritten = _parse_single_slide(text)
    if not rewritten:
        raise HTTPException(status_code=502, detail="Model returned invalid JSON")

    if payload.keep_layout:
        rewritten["layout"] = current.get("layout") or row.slide_type
    rewritten["id"] = row.id

    kwargs = slide_dict_to_row_kwargs(row.slide_number, rewritten)
    kwargs.pop("slide_number", None)
    for k, v in kwargs.items():
        setattr(row, k, v)
    db.add(row)
    await db.flush()
    await _resync_deck_blob(db, task_id)
    await db.commit()
    await db.refresh(row)

    logger.info(
        "slides.regenerate",
        extra={"task_id": task_id, "slide_id": slide_id, "tokens": tokens, "cost": cost},
    )
    return {
        "slide": slide_row_to_dict(row),
        "tokens": tokens,
        "cost_usd": round(cost, 6),
    }


# ── PRD §14: duplicate slide ─────────────────────────────────────────────────
@router.post(
    "/slides/{task_id}/{slide_id}/duplicate",
    summary="Duplicate a slide and insert it directly after the source.",
    responses={404: {"description": "Slide not found."}},
)
async def duplicate_slide(
    task_id: str, slide_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    src = await _load_slide(db, task_id, slide_id)
    insert_at = src.slide_number + 1

    # Shift everyone at >= insert_at by +OFFSET, then settle to +1.
    res = await db.execute(
        select(Slide).where(Slide.task_id == task_id).order_by(Slide.slide_number)
    )
    rows = list(res.scalars().all())
    OFFSET = 100_000
    for r in rows:
        if r.slide_number >= insert_at:
            r.slide_number += OFFSET
            db.add(r)
    await db.flush()
    for r in rows:
        if r.slide_number >= OFFSET:
            r.slide_number = r.slide_number - OFFSET + 1
            db.add(r)
    await db.flush()

    payload = slide_row_to_dict(src)
    payload.pop("id", None)
    payload.pop("slide_id", None)
    kwargs = slide_dict_to_row_kwargs(insert_at, payload)
    new_row = Slide(task_id=task_id, **kwargs)
    db.add(new_row)
    await db.flush()
    slides = await _resync_deck_blob(db, task_id)
    await db.commit()
    await db.refresh(new_row)
    logger.info(
        "slides.duplicate",
        extra={"task_id": task_id, "src": slide_id, "new": new_row.id},
    )
    return {
        "task_id": task_id,
        "slide": slide_row_to_dict(new_row),
        "slide_count": len(slides),
    }


# ── PRD §14: replace image (URL or asset_id) ─────────────────────────────────
class ImageReplaceRequest(BaseModel):
    image_url: str | None = None
    asset_id: str | None = None
    alt: str | None = None
    placement: str | None = None  # background | side | icon | atmospheric
    prompt: str | None = None


@router.post(
    "/slides/{task_id}/{slide_id}/image",
    summary="Replace a slide's image (by URL, asset_id, or AI prompt).",
    responses={404: {"description": "Slide / asset not found."}},
)
async def replace_image(
    task_id: str,
    slide_id: str,
    payload: ImageReplaceRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await _load_slide(db, task_id, slide_id)

    url = (payload.image_url or "").strip()
    source = "manual"
    credit: dict[str, Any] | None = None

    if not url and payload.asset_id:
        from database.models import Asset  # local import to avoid cycles
        asset = (
            await db.execute(select(Asset).where(Asset.id == payload.asset_id))
        ).scalar_one_or_none()
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        url = asset.file_url or asset.file_path
        source = asset.source or "asset"
        credit = asset.credit_json if isinstance(asset.credit_json, dict) else None

    if not url and payload.prompt:
        # Pollinations fallback — no API key required.
        from urllib.parse import quote
        url = f"https://image.pollinations.ai/prompt/{quote(payload.prompt)}?width=1280&height=720&nologo=true"
        source = "pollinations"

    if not url:
        raise HTTPException(
            status_code=400,
            detail="Provide image_url, asset_id, or prompt.",
        )

    img: dict[str, Any] = dict(row.image_data_json or {})
    img["url"] = url
    img["source"] = source
    if payload.alt:
        img["alt"] = payload.alt
    if payload.placement:
        img["placement"] = payload.placement
    if payload.prompt:
        img["prompt"] = payload.prompt
    if credit:
        img["credit"] = credit
    row.image_data_json = img
    db.add(row)
    await db.flush()
    await _resync_deck_blob(db, task_id)
    await db.commit()
    await db.refresh(row)

    logger.info(
        "slides.image_replace",
        extra={"task_id": task_id, "slide_id": slide_id, "source": source},
    )
    return {"slide": slide_row_to_dict(row)}


# ── PRD §15: AI quick-actions ────────────────────────────────────────────────
class QuickActionRequest(BaseModel):
    """Pick exactly one of: action OR custom_instruction."""

    action: str | None = Field(
        default=None,
        description="One of: rewrite | simplify | visualize | shorten | expand | tone",
    )
    tone: str | None = Field(
        default=None,
        description="When action='tone': target tone (formal|casual|persuasive|...).",
    )
    custom_instruction: str | None = None


_QUICK_ACTION_PROMPTS = {
    "rewrite": "Rewrite the slide for clarity and impact while keeping the same meaning, layout, and bullet count.",
    "simplify": "Simplify the language to a 7th-grade reading level. Keep the same layout and bullet count. Strip jargon.",
    "shorten": "Cut every bullet to <= 8 words. Keep the same layout and bullet count.",
    "expand": "Expand each bullet with one extra concrete detail or supporting data point. Keep the same layout.",
    "visualize": (
        "Make this slide more visually compelling. Reduce text density. "
        "If the layout is text-only, suggest converting to one of: image-focus, "
        "chart, stats, kpi, or comparison. Add an image_prompt describing a "
        "cinematic editorial visual that fits the topic."
    ),
    "tone": "Rewrite the slide in a {tone} tone. Keep the same layout and bullet count.",
}


@router.post(
    "/slides/{task_id}/{slide_id}/quick-action",
    summary="Run an AI quick-action on the slide (rewrite, simplify, visualize, tone, etc.).",
    responses={
        400: {"description": "Unknown action."},
        404: {"description": "Slide not found."},
        502: {"description": "Model failure."},
    },
)
async def quick_action(
    task_id: str,
    slide_id: str,
    payload: QuickActionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await _load_slide(db, task_id, slide_id)
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    instruction = (payload.custom_instruction or "").strip()
    if not instruction:
        action = (payload.action or "").lower()
        template = _QUICK_ACTION_PROMPTS.get(action)
        if not template:
            raise HTTPException(
                status_code=400,
                detail=f"action must be one of: {', '.join(_QUICK_ACTION_PROMPTS)}",
            )
        if action == "tone":
            tone = (payload.tone or "professional").strip()
            instruction = template.format(tone=tone)
        else:
            instruction = template

    current = slide_row_to_dict(row)
    user = critic_user_message(task.topic or "", "", current)
    user = f"{user}\n\nUser guidance: {instruction[:1000]}"

    claude = ClaudeService()
    try:
        text, tokens, cost = await claude.complete(
            system=CRITIC_SYSTEM_PROMPT, user=user, max_tokens=1024
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("slides.quick_action_failed", extra={"err": str(exc)})
        raise HTTPException(status_code=502, detail="Quick action failed") from exc

    rewritten = _parse_single_slide(text)
    if not rewritten:
        raise HTTPException(status_code=502, detail="Model returned invalid JSON")

    rewritten["id"] = row.id
    # Visualize action may switch layout; everything else preserves it.
    if (payload.action or "").lower() != "visualize":
        rewritten["layout"] = current.get("layout") or row.slide_type

    kwargs = slide_dict_to_row_kwargs(row.slide_number, rewritten)
    kwargs.pop("slide_number", None)
    for k, v in kwargs.items():
        setattr(row, k, v)
    db.add(row)
    await db.flush()
    await _resync_deck_blob(db, task_id)
    await db.commit()
    await db.refresh(row)

    logger.info(
        "slides.quick_action",
        extra={
            "task_id": task_id,
            "slide_id": slide_id,
            "action": payload.action,
            "tokens": tokens,
        },
    )
    return {
        "slide": slide_row_to_dict(row),
        "tokens": tokens,
        "cost_usd": round(cost, 6),
    }


# ── PRD §14: bulk autosave ───────────────────────────────────────────────────
class BulkUpdateRequest(BaseModel):
    """Body for `POST /slides/{task_id}/bulk` (autosave-friendly)."""

    slides: list[dict[str, Any]] = Field(..., description="List of {id, ...patch}")


@router.post(
    "/slides/{task_id}/bulk",
    summary="Apply patches to many slides in a single request (used for autosave).",
)
async def bulk_update(
    task_id: str,
    payload: BulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    res = await db.execute(select(Slide).where(Slide.task_id == task_id))
    rows = {r.id: r for r in res.scalars().all()}
    if not rows:
        raise HTTPException(status_code=404, detail="No slides for task")

    updated = 0
    for patch in payload.slides:
        sid = (patch or {}).get("id") or (patch or {}).get("slide_id")
        if not sid or sid not in rows:
            continue
        row = rows[sid]
        current = slide_row_to_dict(row)
        merged = {**current, **{k: v for k, v in patch.items() if k not in {"id", "slide_id", "slide_number"}}}
        kwargs = slide_dict_to_row_kwargs(row.slide_number, merged)
        kwargs.pop("slide_number", None)
        for k, v in kwargs.items():
            setattr(row, k, v)
        db.add(row)
        updated += 1
    await db.flush()
    slides = await _resync_deck_blob(db, task_id)
    await db.commit()
    logger.info("slides.bulk_update", extra={"task_id": task_id, "updated": updated})
    return {"task_id": task_id, "updated": updated, "slide_count": len(slides)}


