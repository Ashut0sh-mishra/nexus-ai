"""Phase 6Q — Job lifecycle endpoints.

Surfaces the lifecycle vocabulary defined in
``services.lifecycle_service`` and exposes user-driven actions:

    GET  /api/lifecycle/{task_id}         → status payload
    POST /api/lifecycle/{task_id}/cancel  → request cancellation
    POST /api/lifecycle/{task_id}/retry   → re-run from scratch
    POST /api/lifecycle/{task_id}/resume  → re-run from scratch (no
                                            persisted checkpoint; honest
                                            ``from_checkpoint=False``)

The legacy ``GET /api/status/{task_id}`` SSE stream remains the live
progress feed; this router is the side-channel for state queries and
control actions, mirroring the AgenticSeek / Suna control surface.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from services import lifecycle_service as lc

logger = logging.getLogger("nexus.api.lifecycle")

router = APIRouter()


def _enqueue(task_id: str) -> bool:
    """Best-effort Celery dispatch. Returns ``True`` on enqueue.

    Failure (e.g. Redis down) is reported as 503 by the caller. Imported
    locally so tests that monkeypatch ``workers.tasks.run_generation_task``
    pick up the patched version.
    """
    from workers.tasks import run_generation_task

    run_generation_task.delay(task_id)
    return True


@router.get("/lifecycle/{task_id}")
async def get_lifecycle(task_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    task = await lc.load_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return lc.status_payload(task)


@router.post("/lifecycle/{task_id}/cancel")
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        task = await lc.request_cancel(db, task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "invalid_transition", "code": str(exc)},
        )
    return lc.status_payload(task)


@router.post("/lifecycle/{task_id}/retry")
async def retry_task(task_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        task = await lc.reset_for_retry(db, task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "invalid_transition", "code": str(exc)},
        )
    try:
        _enqueue(task.id)
    except Exception as exc:
        logger.warning(
            "lifecycle.retry.enqueue_failed",
            extra={"task_id": task_id, "err": str(exc)},
        )
        raise HTTPException(
            status_code=503,
            detail="Background queue is unavailable. Is Redis running?",
        ) from exc
    payload = lc.status_payload(task)
    payload["from_checkpoint"] = False
    return payload


@router.post("/lifecycle/{task_id}/resume")
async def resume_task(task_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Resume a cancelled/failed run.

    There is no persisted mid-run checkpoint, so this is identical on
    the wire to ``retry``: the same task row is re-enqueued from
    scratch. The response includes ``from_checkpoint=False`` to keep
    the contract honest for the frontend.
    """
    try:
        task = await lc.reset_for_retry(db, task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Task not found")
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "invalid_transition", "code": str(exc)},
        )
    try:
        _enqueue(task.id)
    except Exception as exc:
        logger.warning(
            "lifecycle.resume.enqueue_failed",
            extra={"task_id": task_id, "err": str(exc)},
        )
        raise HTTPException(
            status_code=503,
            detail="Background queue is unavailable. Is Redis running?",
        ) from exc
    payload = lc.status_payload(task)
    payload["from_checkpoint"] = False
    return payload
