"""Phase 6AN — in-process generation for single-container deploys.

On Hugging Face Spaces (and any single ephemeral container) running a
separate Celery worker that consumes from Redis is fragile: the worker
process and the web process share one container, and cross-process queue
consumption frequently stalls. This module runs the agent loop **inside
the web process** via ``asyncio.create_task`` instead.

Gated by ``settings.NEXUS_INLINE_GENERATION``. When false (default,
docker-compose / Fly with a dedicated worker), nothing here is used and
generation flows through Celery exactly as before.

Key difference from ``workers.tasks._run``: it does NOT dispose the shared
async engine. ``_run`` disposes it because each Celery task runs on a
fresh asyncio loop; here we run on the web app's own loop where the
engine is already correctly bound, so disposing it would break the live
server. SSE progress still flows through the same Redis pub/sub publisher
(Redis runs locally in the container).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from database.connection import SessionLocal
from database.models import Task
from workers.tasks import _make_publisher

logger = logging.getLogger("nexus.workers.inline")

# Same ceiling as the Celery path so a hung provider can't run forever.
TASK_TIMEOUT_SECONDS = 600


async def run_generation_inline(task_id: str, min_sources: int = 0) -> None:
    """Run the agent loop in-process. Never raises to the caller."""
    from agent.loop import NexusAgentLoop
    from services.lifecycle_service import JobCancelled, mark_cancelled

    publisher = _make_publisher(task_id)

    async with SessionLocal() as session:
        res = await session.execute(select(Task).where(Task.id == task_id))
        task = res.scalar_one_or_none()
    if task is None:
        logger.error("inline.task_not_found", extra={"task_id": task_id})
        return

    loop = NexusAgentLoop()
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
        logger.info("inline.done", extra={"task_id": task_id})
    except JobCancelled:
        logger.info("inline.cancelled", extra={"task_id": task_id})
        try:
            async with SessionLocal() as session:
                await mark_cancelled(session, task_id)
        except Exception:  # pragma: no cover - defensive
            logger.exception("inline.mark_cancelled_failed", extra={"task_id": task_id})
    except asyncio.TimeoutError:
        logger.error("inline.timeout", extra={"task_id": task_id})
        await _fail(task_id, publisher, "timeout", TASK_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - inline runner must never propagate
        logger.exception("inline.failed", extra={"task_id": task_id})
        await _fail(task_id, publisher, str(exc), None)


async def _fail(task_id: str, publisher, error: str, timeout: int | None) -> None:
    msg = (
        f"Generation exceeded {timeout}s and was aborted."
        if timeout is not None
        else f"Generation failed: {error}"
    )
    try:
        await publisher(msg, 100.0, "failed", status="failed", error=error)
    except Exception:  # pragma: no cover
        pass
    try:
        async with SessionLocal() as session:
            res = await session.execute(select(Task).where(Task.id == task_id))
            t = res.scalar_one_or_none()
            if t is not None:
                t.status = "failed"
                t.current_step = "failed"
                t.error_msg = error
                session.add(t)
                await session.commit()
    except Exception:  # pragma: no cover
        pass


__all__ = ["run_generation_inline"]
