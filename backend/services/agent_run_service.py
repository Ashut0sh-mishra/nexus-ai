"""Agent run service — pure helpers for AgentRun / AgentStep / Artifact.

Phase 1 storage layer for the dynamic tool-calling loop. The existing 6-step
slide pipeline does not use this yet; it lands in Phase 2.

All helpers accept an ``AsyncSession`` so callers control transaction
boundaries. Nothing here imports the agent loop, the tool registry, or
anything else that could create a cycle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AgentRun, AgentStep, Artifact


async def create_run(
    session: AsyncSession,
    *,
    goal: str,
    task_id: Optional[str] = None,
    user_id: Optional[str] = None,
    max_steps: int = 20,
    meta: Optional[dict[str, Any]] = None,
) -> AgentRun:
    run = AgentRun(
        goal=goal,
        task_id=task_id,
        user_id=user_id,
        max_steps=max_steps,
        status="running",
        meta=dict(meta or {}),
    )
    session.add(run)
    await session.flush()
    return run


async def append_step(
    session: AsyncSession,
    *,
    run_id: str,
    kind: str,
    action: Optional[str] = None,
    input_json: Optional[dict[str, Any]] = None,
    output_json: Optional[dict[str, Any]] = None,
    status: str = "ok",
    error: Optional[str] = None,
) -> AgentStep:
    if kind not in ("thought", "action", "observation", "final"):
        raise ValueError(f"invalid step kind: {kind}")
    # Atomically compute next step_index from the run's step counter.
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise LookupError(f"agent run not found: {run_id}")
    idx = run.step_count
    run.step_count = idx + 1
    step = AgentStep(
        run_id=run_id,
        step_index=idx,
        kind=kind,
        action=action,
        status=status,
        input_json=dict(input_json or {}),
        output_json=dict(output_json or {}),
        error=error,
        completed_at=datetime.now(timezone.utc),
    )
    session.add(step)
    await session.flush()
    return step


async def record_artifact(
    session: AsyncSession,
    *,
    artifact_type: str,
    run_id: Optional[str] = None,
    task_id: Optional[str] = None,
    title: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
    file_url: Optional[str] = None,
) -> Artifact:
    art = Artifact(
        run_id=run_id,
        task_id=task_id,
        artifact_type=artifact_type,
        title=title,
        meta=dict(meta or {}),
        file_url=file_url,
    )
    session.add(art)
    await session.flush()
    return art


async def finish_run(
    session: AsyncSession,
    *,
    run_id: str,
    status: str = "done",
    error: Optional[str] = None,
) -> AgentRun:
    if status not in ("done", "failed", "cancelled"):
        raise ValueError(f"invalid terminal status: {status}")
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise LookupError(f"agent run not found: {run_id}")
    run.status = status
    run.error_msg = error
    run.completed_at = datetime.now(timezone.utc)
    await session.flush()
    return run


async def get_run_with_steps(
    session: AsyncSession, run_id: str
) -> Optional[AgentRun]:
    """Load a run; SQLAlchemy lazy-loads ``steps`` on access within session."""
    return await session.get(AgentRun, run_id)


async def list_artifacts_for_run(
    session: AsyncSession, run_id: str
) -> list[Artifact]:
    result = await session.execute(
        select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.created_at)
    )
    return list(result.scalars().all())
