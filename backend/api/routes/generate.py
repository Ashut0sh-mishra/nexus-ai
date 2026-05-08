"""POST /api/generate — enqueue a slide generation task."""

from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import Task

logger = logging.getLogger("nexus.api.generate")

router = APIRouter()


# ── topic sanitization ───────────────────────────────────────────────────
# Phrases users tend to prepend to their actual topic. Stripping these gives
# Wikipedia/Wikidata a clean noun-phrase topic and keeps the title slide from
# saying "Generate Ppt On Ai And Brain Uses".
_INSTRUCTION_PREFIX_RE = re.compile(
    r"""^\s*(?:please\s+)?(?:can\s+you\s+)?(?:could\s+you\s+)?(?:i\s+(?:want|need)\s+(?:you\s+to\s+)?)?
        (?:make|create|generate|build|design|produce|prepare|give\s+me|do)
        \s+(?:me\s+|us\s+)?
        (?:an?\s+|the\s+)?
        (?:slide\s+deck|deck|slides?|presentation|ppt|pptx|powerpoint|pitch|report)
        \s+(?:on|about|for|covering|regarding|titled|called|of|over|around)\s+
    """,
    re.I | re.X,
)
_TRAILING_INSTRUCTION_RE = re.compile(
    r"""\s+(?:please|asap|now|in\s+\d+\s+slides?|with\s+\d+\s+slides?|"""
    r"""for\s+(?:my|our|the)\s+(?:presentation|talk|class|meeting))\s*\.?\s*$""",
    re.I | re.X,
)


def _sanitize_topic(raw: str, max_len: int = 200) -> str:
    """Turn a free-form user prompt into a clean topic noun-phrase."""
    if not raw:
        return raw
    t = raw.strip().strip("\"'`")
    # Repeatedly strip leading instruction phrases (e.g. "please make a deck about ai uses")
    for _ in range(3):
        new = _INSTRUCTION_PREFIX_RE.sub("", t).strip()
        if new == t:
            break
        t = new
    t = _TRAILING_INSTRUCTION_RE.sub("", t).strip(" .,:;-")
    # Trim trailing punctuation/quotes left over.
    t = t.strip("\"'`")
    if not t:
        return raw.strip()  # never return empty; fall back to original
    # Title-case ALL CAPS or all lowercase prompts so the title slide looks good,
    # but preserve short acronyms / numeric tokens (AI, USA, WW2, 5G).
    _STOP = {"a", "an", "the", "and", "or", "of", "in", "on", "to", "for",
             "by", "at", "vs", "with", "from", "as", "is", "it"}
    if t.isupper() or (t.islower() and len(t.split()) >= 2):
        words = t.split()
        out_words: list[str] = []
        for i, w in enumerate(words):
            lw = w.lower()
            if lw in _STOP and i > 0:
                out_words.append(lw)
            elif lw in _STOP:
                # Leading stop word: title-case it instead of treating as acronym.
                out_words.append(lw[:1].upper() + lw[1:])
            elif len(w) <= 4 and any(c.isdigit() for c in w):
                out_words.append(w.upper())
            elif len(w) <= 3 and w.isalpha():
                out_words.append(w.upper())
            else:
                out_words.append(w[:1].upper() + w[1:])
        t = " ".join(out_words)
    return t[:max_len]


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=4, max_length=2000)
    slide_count: int = Field(8, ge=4, le=20)
    # "auto" lets the agent loop pick the most fitting theme for the topic.
    theme: str = Field("auto", max_length=64)
    search_web: bool = True
    user_id: Optional[str] = None
    # Optional context: file IDs from POST /api/upload that the agent should
    # ground the deck in. Accepts both list[str] and JSON-array form.
    file_ids: Optional[list[str]] = Field(default=None)
    audience: Optional[str] = Field(default=None, max_length=64)
    tone: Optional[str] = Field(default=None, max_length=64)
    industry: Optional[str] = Field(default=None, max_length=64)

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, v: str) -> str:
        return v.strip()


class GenerateResponse(BaseModel):
    task_id: str
    status: str


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=202,
    summary="Create a deck-generation task and enqueue it.",
    description=(
        "Persists a `Task`, optionally links uploaded files (`file_ids`), and "
        "enqueues the agent loop on the Celery worker. Returns immediately "
        "with `task_id` \u2014 subscribe to `/status/{task_id}` for live progress "
        "or poll `/slides/{task_id}` once `status` reaches `done`."
    ),
    responses={
        503: {"description": "Background queue (Redis/Celery) unavailable."},
    },
)
async def create_generation_task(
    payload: GenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """Create a task row and enqueue the Celery worker."""
    trace_id = getattr(request.state, "trace_id", "-")
    # Strip instruction phrases ("generate ppt on X", "make a deck about X",
    # "create slides for X") from the user prompt so research/Wikipedia and the
    # title slide get a clean noun-phrase topic instead of an instruction.
    clean_topic = _sanitize_topic(payload.topic)
    try:
        task = Task(
            user_id=payload.user_id,
            topic=clean_topic,
            slide_count=payload.slide_count,
            theme=payload.theme,
            search_web=payload.search_web,
            status="pending",
            current_step="queued",
            progress_pct=0.0,
            context_sources=payload.file_ids or None,
            audience=payload.audience,
            tone=payload.tone,
            industry=payload.industry,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        # Link uploaded files to this task so the worker can pick them up
        # via the UploadedFile.task_id == task_id query in the agent loop.
        if payload.file_ids:
            from database.models import UploadedFile

            await db.execute(
                UploadedFile.__table__.update()
                .where(UploadedFile.id.in_(payload.file_ids))
                .where(UploadedFile.task_id.is_(None))
                .values(task_id=task.id)
            )
            await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("generate.create_task_failed", extra={"trace_id": trace_id})
        raise HTTPException(status_code=500, detail="Could not create task.") from exc

    # Enqueue async work. Import locally so the API process doesn't pull in
    # heavy worker-only deps (browser_use / playwright) on cold start.
    try:
        from workers.tasks import run_generation_task

        run_generation_task.delay(task.id)
    except Exception as exc:
        logger.warning(
            "generate.enqueue_failed_running_inline",
            extra={"trace_id": trace_id, "task_id": task.id, "err": str(exc)},
        )
        # If Celery/Redis is unreachable, mark the task failed rather than
        # leaving it dangling. Inline execution would block the request.
        task.status = "failed"
        task.error_msg = f"Queue unavailable: {exc}"
        db.add(task)
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Background queue is unavailable. Is Redis running?",
        ) from exc

    logger.info(
        "generate.queued",
        extra={"trace_id": trace_id, "task_id": task.id, "topic": payload.topic[:80]},
    )
    return GenerateResponse(task_id=task.id, status="pending")
