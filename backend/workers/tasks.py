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
    """Return an async callback that publishes progress to the Redis channel."""
    client = redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
    channel = _channel(task_id)

    async def publish(message: str, progress_pct: float, step: str, **extra: Any) -> None:
        payload: dict[str, Any] = {
            "task_id": task_id,
            "status": extra.pop("status", "running"),
            "progress_pct": float(progress_pct),
            "step": step,
            "message": message,
        }
        # Pass through structured event payloads (e.g. event="slide", data={...})
        # so the SSE consumer can render artifacts as they’re finalized,
        # mirroring browser-use’s register_new_step_callback pattern.
        for k, v in extra.items():
            payload[k] = v
        try:
            await asyncio.to_thread(client.publish, channel, json.dumps(payload))
        except Exception as exc:  # never let SSE break the loop
            logger.warning("tasks.publish_failed", extra={"err": str(exc)})

    return publish


async def _load_task(task_id: str) -> Task | None:
    async with SessionLocal() as session:
        res = await session.execute(select(Task).where(Task.id == task_id))
        return res.scalar_one_or_none()


async def _run(task_id: str) -> None:
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

    task = await _load_task(task_id)
    if task is None:
        logger.error("tasks.task_not_found", extra={"task_id": task_id})
        return

    publisher = _make_publisher(task_id)
    loop = NexusAgentLoop()
    # Hard ceiling: a hung provider call must never freeze a Celery worker.
    # 8 slides x ~30s/slide worst-case + overhead = 5 min ceiling.
    TASK_TIMEOUT_SECONDS = 300
    try:
        await asyncio.wait_for(
            loop.run(
                task_id=task.id,
                topic=task.topic,
                slide_count=task.slide_count or 8,
                theme=task.theme or "Editorial",
                search_web=bool(task.search_web),
                on_progress=publisher,
            ),
            timeout=TASK_TIMEOUT_SECONDS,
        )
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
    finally:
        try:
            await _async_engine.dispose()
        except Exception:
            pass


@celery_app.task(name="nexus.run_generation_task", bind=True, max_retries=0)
def run_generation_task(self, task_id: str) -> dict[str, Any]:
    """Entry point invoked by `run_generation_task.delay(task.id)`."""
    logger.info("tasks.start", extra={"task_id": task_id})
    try:
        asyncio.run(_run(task_id))
        return {"task_id": task_id, "status": "done"}
    except Exception as exc:
        logger.exception("tasks.failed", extra={"task_id": task_id})
        # The agent loop already marks the DB row failed and emits a final SSE
        # event; we just surface the error to Celery's result backend.
        return {"task_id": task_id, "status": "failed", "error": str(exc)}
