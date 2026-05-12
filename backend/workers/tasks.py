"""Celery tasks — runs the agent loop and publishes SSE progress to Redis."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import redis as redis_sync
from sqlalchemy import select

from config import settings
from database.connection import SessionLocal
from database.models import Task
from workers.celery_app import celery_app

logger = logging.getLogger("nexus.workers.tasks")

PROGRESS_CHANNEL_PREFIX = "nexus:task:progress:"


def _channel(task_id: str) -> str:
    return f"{PROGRESS_CHANNEL_PREFIX}{task_id}"


def _make_publisher(task_id: str):
    """Return an async callback that publishes progress to the Redis channel.

    Phase 6R: the legacy ``(message, progress_pct, step, **extra)`` callback
    signature is preserved at the call sites inside the agent loop, but the
    payload is now produced by ``RunEventEmitter`` so every frame carries a
    canonical ``event`` type, monotonic ``sequence`` and ISO ``timestamp``.
    """
    from services.run_events import RunEventEmitter

    client = redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
    channel = _channel(task_id)

    async def publish_raw(payload: dict[str, Any]) -> None:
        try:
            await asyncio.to_thread(client.publish, channel, json.dumps(payload))
        except Exception as exc:  # never let SSE break the loop
            logger.warning("tasks.publish_failed", extra={"err": str(exc)})

    emitter = RunEventEmitter(task_id, publish_raw)
    return emitter.on_progress


async def _load_task(task_id: str) -> Task | None:
    async with SessionLocal() as session:
        res = await session.execute(select(Task).where(Task.id == task_id))
        return res.scalar_one_or_none()


async def _run(task_id: str, min_sources: int = 0) -> None:
    # Dispose any cached async engine connections so asyncpg protocols are
    # rebuilt on this asyncio loop. Without this, the second Celery task in
    # the worker process raises "got Future ... attached to a different loop"
    # because the pooled connection was bound to the previous (closed) loop.
    from database.connection import engine as _async_engine

    try:
        await _async_engine.dispose()
    except Exception as exc:  # pragma: no cover
        logger.warning("tasks.engine_dispose_failed", extra={"err": str(exc)})

    from agent.loop import NexusAgentLoop
    from services.lifecycle_service import JobCancelled, mark_cancelled
    from workers.runtime_trail import maybe_wrap_for_runtime_trail

    task = await _load_task(task_id)
    if task is None:
        logger.error("tasks.task_not_found", extra={"task_id": task_id})
        return

    inner_publisher = _make_publisher(task_id)
    # Phase 6AG: if the API opened a pipeline-trail AgentRun for this task
    # (because NEXUS_RUNTIME_DRIVES_GENERATE=true), wrap the publisher so
    # each pipeline milestone is mirrored onto AgentStep rows and the run
    # is finalised when the loop terminates. ``observer`` is ``None`` when
    # no run was opened — the legacy callback is then used verbatim.
    publisher, observer = await maybe_wrap_for_runtime_trail(task_id, inner_publisher)
    loop = NexusAgentLoop()
    # Hard ceiling: a hung provider call must never freeze a Celery worker.
    # 12 slides x ~30s/slide worst-case + provider 429 backoff/retries + overhead
    # = 10 min ceiling. Raised from 300s after Phase 6U-Rebench observed
    # `tasks.timeout` on the two 12-slide prompts (mkt-001, evid-001) under
    # Groq + OpenRouter 429 cascades. Still bounded so a hung provider cannot
    # freeze a Celery worker indefinitely.
    TASK_TIMEOUT_SECONDS = 600
    try:
        await asyncio.wait_for(
            loop.run(
                task_id=task.id,
                topic=task.topic,
                slide_count=task.slide_count or 8,
                theme=task.theme or "Editorial",
                search_web=bool(task.search_web),
                on_progress=publisher,
                min_sources=int(min_sources or 0),
            ),
            timeout=TASK_TIMEOUT_SECONDS,
        )
    except JobCancelled:
        logger.info("tasks.cancelled", extra={"task_id": task_id})
        try:
            async with SessionLocal() as session:
                await mark_cancelled(session, task_id)
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "tasks.mark_cancelled_failed", extra={"task_id": task_id}
            )
        if observer is not None:
            await observer.finalize_unexpected(status="cancelled", error="job_cancelled")
    except asyncio.TimeoutError:
        logger.error("tasks.timeout", extra={"task_id": task_id, "limit": TASK_TIMEOUT_SECONDS})
        await publisher(
            f"Generation exceeded {TASK_TIMEOUT_SECONDS}s and was aborted.",
            100.0,
            "failed",
            status="failed",
            error="timeout",
        )
        # Best-effort: mark task failed in DB.
        try:
            async with SessionLocal() as session:
                res = await session.execute(select(Task).where(Task.id == task_id))
                t = res.scalar_one_or_none()
                if t is not None:
                    t.status = "failed"
                    t.current_step = "failed"
                    t.error_msg = "timeout"
                    session.add(t)
                    await session.commit()
        except Exception:
            pass
        if observer is not None:
            await observer.finalize_unexpected(status="failed", error="timeout")
    finally:
        try:
            await _async_engine.dispose()
        except Exception:
            pass


@celery_app.task(name="nexus.run_generation_task", bind=True, max_retries=0)
def run_generation_task(self, task_id: str, min_sources: int = 0) -> dict[str, Any]:
    """Entry point invoked by `run_generation_task.delay(task.id)`."""
    logger.info("tasks.start", extra={"task_id": task_id, "min_sources": min_sources})
    try:
        asyncio.run(_run(task_id, int(min_sources or 0)))
        return {"task_id": task_id, "status": "done"}
    except Exception as exc:
        logger.exception("tasks.failed", extra={"task_id": task_id})
        # The agent loop already marks the DB row failed and emits a final SSE
        # event; we just surface the error to Celery's result backend.
        return {"task_id": task_id, "status": "failed", "error": str(exc)}
