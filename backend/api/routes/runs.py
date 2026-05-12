"""Phase 6AH-A4 — Read-only AgentRun timeline endpoint.

Exposes the AgentRun + AgentStep rows that ``workers/runtime_trail.py``
writes during pipeline-trail mode. The frontend consumes this to render
the "watch it think" timeline panel.

Read-only. Public (no auth) by design — runs are scoped to a task_id
that is already public via /api/status. No mutation, no DB writes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from database.connection import SessionLocal
from database.models import AgentRun, AgentStep

router = APIRouter()


def _step_to_dict(step: AgentStep) -> dict[str, Any]:
    return {
        "step_index": step.step_index,
        "kind": step.kind,
        "action": step.action,
        "status": step.status,
        "input": step.input_json or {},
        "output": step.output_json or {},
        "error": step.error,
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "completed_at": (
            step.completed_at.isoformat() if step.completed_at else None
        ),
    }


def _run_to_dict(run: AgentRun, steps: list[AgentStep]) -> dict[str, Any]:
    return {
        "run_id": run.id,
        "task_id": run.task_id,
        "goal": run.goal,
        "status": run.status,
        "step_count": run.step_count,
        "max_steps": run.max_steps,
        "meta": run.meta or {},
        "error_msg": run.error_msg,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": (
            run.completed_at.isoformat() if run.completed_at else None
        ),
        "steps": [_step_to_dict(s) for s in steps],
    }


@router.get("/runs/by-task/{task_id}")
async def get_run_by_task(task_id: str) -> dict[str, Any]:
    """Return the most recent AgentRun (with all steps) for a task.

    Returns 404 when no AgentRun has been opened for the task. The
    pipeline-trail observer only opens a run when
    ``NEXUS_RUNTIME_DRIVES_GENERATE`` is enabled, so the absence of a
    run is a normal, not-found condition (not an error).
    """
    async with SessionLocal() as db:
        res = await db.execute(
            select(AgentRun)
            .where(AgentRun.task_id == task_id)
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
        run = res.scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=404, detail="No agent run for task")
        steps_res = await db.execute(
            select(AgentStep)
            .where(AgentStep.run_id == run.id)
            .order_by(AgentStep.step_index.asc())
        )
        steps = list(steps_res.scalars().all())
        return _run_to_dict(run, steps)


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Return a single AgentRun by id (with all steps)."""
    async with SessionLocal() as db:
        res = await db.execute(select(AgentRun).where(AgentRun.id == run_id))
        run = res.scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        steps_res = await db.execute(
            select(AgentStep)
            .where(AgentStep.run_id == run.id)
            .order_by(AgentStep.step_index.asc())
        )
        steps = list(steps_res.scalars().all())
        return _run_to_dict(run, steps)
