"""POST /api/generate — enqueue a slide generation task."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from agent.art_direction import infer_art_direction
from config import settings
from database.connection import get_db
from database.models import Task

logger = logging.getLogger("nexus.api.generate")

router = APIRouter()


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=4, max_length=2000)
    slide_count: int = Field(8, ge=4, le=20)
    theme: str = Field("Editorial", max_length=64)
    search_web: bool = True
    user_id: Optional[str] = None
    # Phase 6U: optional minimum number of unique sources the generator
    # should harvest before plan/generate. ``0`` (default) preserves the
    # pre-6U single-shot search behaviour. When positive, the loop calls
    # :meth:`SearchService.harvest` and keeps gathering across follow-up
    # queries until either the target is met or providers are exhausted.
    min_sources: int = Field(0, ge=0, le=20)

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, v: str) -> str:
        return v.strip()


class GenerateResponse(BaseModel):
    task_id: str
    status: str
    # Phase 6I: only populated when NEXUS_RUNTIME_DRIVES_GENERATE=true and
    # the AgentRun dispatch trail was successfully persisted. Always None
    # in default (flag-off) deployments — the live-eval adapter and
    # frontend ignore unknown extra fields, but we keep the default-off
    # contract identical to pre-6I.
    agent_run_id: Optional[str] = None


async def _record_runtime_dispatch(
    db: AsyncSession,
    *,
    task_id: str,
    user_id: Optional[str],
    payload: "GenerateRequest",
    trace_id: str,
) -> Optional[str]:
    """Phase 6I — persist an AgentRun + thought step for this generate call.

    Returns the run id if persistence (or recorded-failure) succeeded.
    Returns ``None`` only if the AgentRun row itself could not be created.
    A persistence failure inside the run is captured by marking the run
    ``failed`` rather than crashing the API. This function commits its own
    transactions; the route must commit Task before calling it.
    """
    # Local imports keep the route cheap when the flag is off.
    from agent.runtime import RuntimeConfig
    from services.agent_run_service import append_step, create_run, finish_run

    try:
        run = await create_run(
            db,
            goal=payload.topic,
            task_id=task_id,
            user_id=user_id,
            max_steps=RuntimeConfig().max_steps,
            meta={
                "phase": "6I",
                "dispatch_only": True,
                "theme": payload.theme,
                "slide_count": payload.slide_count,
                "search_web": payload.search_web,
            },
        )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception(
            "generate.runtime_dispatch.create_run_failed",
            extra={"trace_id": trace_id, "task_id": task_id},
        )
        return None

    try:
        await append_step(
            db,
            run_id=run.id,
            kind="thought",
            input_json={
                "dispatch": "celery",
                "topic_preview": payload.topic[:200],
                "slide_count": payload.slide_count,
                "theme": payload.theme,
                "search_web": payload.search_web,
            },
        )
        await finish_run(db, run_id=run.id, status="done")
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.warning(
            "generate.runtime_dispatch.step_or_finish_failed",
            extra={"trace_id": trace_id, "task_id": task_id, "err": str(exc)},
        )
        try:
            await finish_run(
                db,
                run_id=run.id,
                status="failed",
                error=f"dispatch_record_failed: {exc}",
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception(
                "generate.runtime_dispatch.finish_failed",
                extra={"trace_id": trace_id, "task_id": task_id},
            )
    return run.id


@router.post(
    "/generate",
    response_model=GenerateResponse,
    response_model_exclude_none=True,
    status_code=202,
)
async def create_generation_task(
    payload: GenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """Create a task row and enqueue the Celery worker."""
    trace_id = getattr(request.state, "trace_id", "-")

    # Phase 6M — topic-aware art direction. The Pydantic default for
    # ``theme`` is ``"Editorial"``; only inputs that are ``""`` or
    # ``"auto"`` (case-insensitive) are treated as auto. Any other value,
    # including ``"Editorial"`` from older clients, is respected as an
    # explicit user choice. ``infer_art_direction`` is deterministic and
    # never raises.
    art_direction = infer_art_direction(payload.topic, payload.theme)
    effective_theme = art_direction.theme
    logger.info(
        "generate.art_direction",
        extra={
            "trace_id": trace_id,
            "input_theme": payload.theme,
            "effective_theme": effective_theme,
            "category": art_direction.category,
            "mood": art_direction.mood,
            "rationale": art_direction.rationale,
        },
    )

    try:
        task = Task(
            user_id=payload.user_id,
            topic=payload.topic,
            slide_count=payload.slide_count,
            theme=effective_theme,
            search_web=payload.search_web,
            status="pending",
            current_step="queued",
            progress_pct=0.0,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
    except Exception as exc:
        await db.rollback()
        logger.exception("generate.create_task_failed", extra={"trace_id": trace_id})
        raise HTTPException(status_code=500, detail="Could not create task.") from exc

    # Phase 6I — feature-flagged runtime dispatch trail. Default OFF.
    agent_run_id: Optional[str] = None
    if settings.NEXUS_RUNTIME_DRIVES_GENERATE:
        agent_run_id = await _record_runtime_dispatch(
            db,
            task_id=task.id,
            user_id=payload.user_id,
            payload=payload,
            trace_id=trace_id,
        )

    # Enqueue async work. Import locally so the API process doesn't pull in
    # heavy worker-only deps (browser_use / playwright) on cold start.
    try:
        from workers.tasks import run_generation_task

        run_generation_task.delay(task.id, payload.min_sources)
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
        extra={
            "trace_id": trace_id,
            "task_id": task.id,
            "topic": payload.topic[:80],
            "agent_run_id": agent_run_id,
        },
    )
    return GenerateResponse(
        task_id=task.id, status="pending", agent_run_id=agent_run_id
    )
