"""Phase 6Q — Job lifecycle service.

Maps the legacy ``Task.status`` strings to a clean lifecycle vocabulary
and exposes helpers to request cancel, mark cancelled, and reset for
retry. The lifecycle vocabulary is the contract that
``/api/lifecycle/*`` routes and the frontend share; the legacy
``Task.status`` values (``pending``/``running``/``done``/``failed``) are
preserved on disk so older clients (export, share, status SSE) keep
working unchanged.

Lifecycle states::

    queued       → Task.status == "pending"
    running      → Task.status == "running"
    cancelling   → Task.status == "cancelling"   (new in 6Q)
    cancelled    → Task.status == "cancelled"    (new in 6Q)
    failed       → Task.status == "failed"
    succeeded    → Task.status == "done"

Cancel is signalled by writing ``Task.status = "cancelling"``. The agent
loop polls this at every safe checkpoint via
:func:`is_cancelling` and raises :class:`JobCancelled` to exit
gracefully. The worker top-level catches that and calls
:func:`mark_cancelled` to write the terminal row + publish the final
SSE event.

Retry and resume both re-enqueue the same ``task_id`` after resetting
the row's progress fields. There is no persisted mid-run checkpoint, so
``resume`` is documented as ``from_checkpoint=False`` (honest fallback,
identical to retry on the wire).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Task

logger = logging.getLogger("nexus.services.lifecycle")


class JobCancelled(Exception):
    """Raised inside the agent loop when a cancel was requested.

    Caught at the worker top-level so the error log stays clean; the
    Task row is marked ``cancelled`` and the final SSE event is
    published with ``status="cancelled"``.
    """


# ── Vocabulary ────────────────────────────────────────────────────────────

LIFECYCLE_STATES: tuple[str, ...] = (
    "queued",
    "running",
    "cancelling",
    "cancelled",
    "failed",
    "succeeded",
)

TERMINAL_STATES: frozenset[str] = frozenset({"cancelled", "failed", "succeeded"})


_FROM_TASK: dict[str, str] = {
    "pending": "queued",
    "running": "running",
    "cancelling": "cancelling",
    "cancelled": "cancelled",
    "failed": "failed",
    "done": "succeeded",
}


def to_lifecycle_state(task_status: str | None) -> str:
    """Map a legacy ``Task.status`` value to its lifecycle state."""
    if not task_status:
        return "queued"
    return _FROM_TASK.get(task_status, task_status)


def allowed_actions(state: str) -> list[str]:
    """Return the action names the API permits for a given state."""
    if state in {"queued", "running"}:
        return ["cancel"]
    if state in {"cancelled", "failed"}:
        return ["retry", "resume"]
    # cancelling, succeeded → no further user action
    return []


# ── Reads ─────────────────────────────────────────────────────────────────


async def load_task(db: AsyncSession, task_id: str) -> Optional[Task]:
    res = await db.execute(select(Task).where(Task.id == task_id))
    return res.scalar_one_or_none()


async def is_cancelling(db: AsyncSession, task_id: str) -> bool:
    """Best-effort cancel poll for the agent loop. Never raises."""
    try:
        task = await load_task(db, task_id)
    except Exception:  # pragma: no cover - defensive
        logger.exception("lifecycle.is_cancelling.read_failed", extra={"task_id": task_id})
        return False
    if task is None:
        return False
    return task.status == "cancelling"


def status_payload(task: Task) -> dict:
    """Public status payload used by ``GET /api/lifecycle/{task_id}``."""
    state = to_lifecycle_state(task.status)
    return {
        "task_id": task.id,
        "state": state,
        "status": task.status,
        "stage": task.current_step or "",
        "progress_pct": float(task.progress_pct or 0.0),
        "error": task.error_msg,
        "topic": task.topic,
        "slide_count": task.slide_count,
        "theme": task.theme,
        "is_terminal": state in TERMINAL_STATES,
        "allowed_actions": allowed_actions(state),
    }


# ── Mutations ─────────────────────────────────────────────────────────────


async def request_cancel(db: AsyncSession, task_id: str) -> Task:
    """Request cancellation. The worker observes ``Task.status`` and exits.

    Idempotent for ``cancelling``. Raises ``ValueError`` with a stable
    code in the message when the current state does not allow cancel.
    """
    task = await load_task(db, task_id)
    if task is None:
        raise LookupError("task_not_found")
    state = to_lifecycle_state(task.status)
    if state == "cancelling":
        return task
    if state not in {"queued", "running"}:
        raise ValueError(f"cancel_not_allowed_in_state:{state}")
    task.status = "cancelling"
    task.current_step = "cancelling"
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def mark_cancelled(db: AsyncSession, task_id: str) -> Optional[Task]:
    """Finalize a cancellation. Called from the worker after the loop exits."""
    task = await load_task(db, task_id)
    if task is None:
        return None
    task.status = "cancelled"
    task.current_step = "cancelled"
    task.progress_pct = 100.0
    task.completed_at = datetime.now(timezone.utc)
    if not task.error_msg:
        task.error_msg = "Cancelled by user"
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def reset_for_retry(db: AsyncSession, task_id: str) -> Task:
    """Reset progress fields so the same row can be re-run.

    Allowed only from ``cancelled`` or ``failed``. Does NOT enqueue the
    Celery task — the route does that after this returns.
    """
    task = await load_task(db, task_id)
    if task is None:
        raise LookupError("task_not_found")
    state = to_lifecycle_state(task.status)
    if state not in {"cancelled", "failed"}:
        raise ValueError(f"retry_not_allowed_in_state:{state}")
    task.status = "pending"
    task.current_step = "queued"
    task.progress_pct = 0.0
    task.error_msg = None
    task.completed_at = None
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task
