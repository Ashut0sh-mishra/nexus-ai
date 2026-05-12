"""Phase 6AG — bridge that records real pipeline phases onto an AgentRun.

This module is the bridge that makes the runtime feature flag actually
mean something. When ``NEXUS_RUNTIME_DRIVES_GENERATE=true``,
``/api/generate`` opens an :class:`AgentRun` (status ``running``) and the
Celery worker passes its progress callback through
:class:`PipelineTrailObserver`, which:

* writes one :class:`AgentStep` per pipeline phase milestone (search,
  strategy, plan, generate, critique, save, …);
* records significant payloads (source urls, design decisions, slide
  ready / critique events, narrative beats, citation summary) as
  ``observation`` steps so the run becomes a queryable trail;
* finalises the run with ``done`` / ``failed`` / ``cancelled`` once the
  pipeline terminates.

Everything here is **defensive**: any DB failure inside the observer is
logged and swallowed. The observer must never raise into the loop or the
worker — the legacy SSE / DB pipeline is the contract that callers care
about; this is purely an additive trail.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import select

from database.connection import SessionLocal
from database.models import AgentRun
from services.agent_run_service import append_step, finish_run

logger = logging.getLogger("nexus.workers.runtime_trail")


# Progress callback signature used throughout the loop.
ProgressCallback = Callable[..., Awaitable[None]]


# ── stages we always record as a step ─────────────────────────────────────
# Recording every progress call would balloon the trail (the loop fires
# ~50–80 events per deck). We instead record one step per *new* stage
# transition plus a curated allow-list of explicit events.
_STAGE_SET = {
    "analyze",
    "search",
    "strategy",
    "plan",
    "generate",
    "intent",
    "recommend",
    "critic",
    "images",
    "repair",
    "citations",
    "save",
    "done",
    "failed",
    "cancelled",
}

_MILESTONE_EVENTS = {
    "stage_started",
    "stage_completed",
    "slide_ready",
    "outline_ready",
    "deck_saved",
    "citation_checked",
    "narrative_beats_ready",
    "deck_critique",
    "run_completed",
    "run_failed",
    "run_cancelled",
}

_TERMINAL_EVENTS = {"run_completed", "run_failed", "run_cancelled"}
_TERMINAL_STATUS = {
    "done": "done",
    "completed": "done",
    "success": "done",
    "failed": "failed",
    "error": "failed",
    "cancelled": "cancelled",
}


async def _find_open_run_id(task_id: str) -> Optional[str]:
    """Return the most recent running AgentRun for ``task_id`` or ``None``.

    Each ``/api/generate`` call opens at most one pipeline-trail AgentRun
    (the route is single-shot), so picking the latest running row is
    unambiguous in practice; we order by ``created_at`` just to be safe.
    """
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                select(AgentRun)
                .where(AgentRun.task_id == task_id, AgentRun.status == "running")
                .order_by(AgentRun.created_at.desc())
            )
            run = result.scalars().first()
            return run.id if run is not None else None
    except Exception:
        logger.exception("runtime_trail.lookup_failed", extra={"task_id": task_id})
        return None


class PipelineTrailObserver:
    """Wrap a progress callback so each milestone is mirrored to an AgentRun.

    Constructed with a known ``agent_run_id`` and the *inner* callback the
    worker would have used anyway (the Redis SSE publisher). All progress
    calls pass through to the inner callback verbatim. The observer
    additionally writes ``AgentStep`` rows for milestone events and
    finalises the run once a terminal status is observed.

    The observer is single-threaded by virtue of Celery's asyncio.run
    invocation; we use a fresh ``SessionLocal()`` per write so we never
    contend with the loop's own DB sessions.
    """

    def __init__(self, agent_run_id: str, inner: ProgressCallback) -> None:
        self._run_id = agent_run_id
        self._inner = inner
        self._seen_stages: set[str] = set()
        self._terminal_recorded = False

    async def __call__(
        self,
        message: str,
        progress_pct: float,
        step: str,
        **extra: Any,
    ) -> None:
        # Always pass through to the legacy callback first — never let
        # observer failures degrade the SSE contract.
        try:
            await self._inner(message, progress_pct, step, **extra)
        except Exception:
            logger.exception("runtime_trail.inner_callback_failed")

        try:
            await self._record(message, progress_pct, step, extra)
        except Exception:
            logger.exception(
                "runtime_trail.record_failed",
                extra={"run_id": self._run_id, "stage": step},
            )

    # ── internal ─────────────────────────────────────────────────────────
    async def _record(
        self,
        message: str,
        progress_pct: float,
        step: str,
        extra: dict[str, Any],
    ) -> None:
        status = str(extra.get("status") or "running")
        event = str(extra.get("event") or "")
        stage = str(step or "")

        terminal_status = _TERMINAL_STATUS.get(status)
        is_terminal_event = event in _TERMINAL_EVENTS

        # 1) Terminal: finalize the run and stop.
        if terminal_status or is_terminal_event:
            if self._terminal_recorded:
                return
            self._terminal_recorded = True
            final_status = terminal_status or (
                "done" if event == "run_completed"
                else "cancelled" if event == "run_cancelled"
                else "failed"
            )
            await self._safe_append(
                kind="final",
                action=stage or final_status,
                output_json={
                    "stage": stage,
                    "message": message[:500],
                    "progress_pct": float(progress_pct),
                    "event": event or None,
                    "status": final_status,
                },
                status="ok" if final_status == "done" else "error",
                error=extra.get("error"),
            )
            await self._safe_finish(
                status=final_status,
                error=extra.get("error") or (None if final_status == "done" else f"status={status}"),
            )
            return

        # 2) Curated milestone events get an observation step.
        if event and event in _MILESTONE_EVENTS:
            await self._safe_append(
                kind="observation",
                action=stage or event,
                input_json={"event": event},
                output_json={
                    "stage": stage,
                    "message": message[:500],
                    "progress_pct": float(progress_pct),
                    "event": event,
                },
            )
            return

        # 3) New stage transition (no explicit event) → record once.
        if stage and stage in _STAGE_SET and stage not in self._seen_stages:
            self._seen_stages.add(stage)
            await self._safe_append(
                kind="observation",
                action=stage,
                output_json={
                    "stage": stage,
                    "message": message[:500],
                    "progress_pct": float(progress_pct),
                },
            )

    async def _safe_append(self, **kwargs: Any) -> None:
        try:
            async with SessionLocal() as session:
                await append_step(session, run_id=self._run_id, **kwargs)
                await session.commit()
        except Exception:
            logger.exception(
                "runtime_trail.append_step_failed",
                extra={"run_id": self._run_id, "kind": kwargs.get("kind")},
            )

    async def _safe_finish(self, *, status: str, error: Optional[str]) -> None:
        try:
            async with SessionLocal() as session:
                await finish_run(session, run_id=self._run_id, status=status, error=error)
                await session.commit()
        except Exception:
            logger.exception(
                "runtime_trail.finish_run_failed",
                extra={"run_id": self._run_id, "status": status},
            )

    async def finalize_unexpected(self, *, status: str, error: Optional[str]) -> None:
        """Force-finalise the run from outside the progress stream.

        Used by the worker's outermost exception handler so the runtime
        trail never dangles in ``running`` when the loop crashes before
        emitting a terminal progress event (timeout, unhandled
        exception, JobCancelled).
        """
        if self._terminal_recorded:
            return
        self._terminal_recorded = True
        await self._safe_finish(status=status, error=error)


async def maybe_wrap_for_runtime_trail(
    task_id: str,
    inner: ProgressCallback,
) -> tuple[ProgressCallback, Optional[PipelineTrailObserver]]:
    """Return ``(callback, observer)`` — observer is None when no AgentRun exists.

    ``callback`` is always safe to use as the loop's ``on_progress``: it
    is either the unmodified ``inner`` or an instrumented wrapper.
    """
    run_id = await _find_open_run_id(task_id)
    if not run_id:
        return inner, None
    observer = PipelineTrailObserver(run_id, inner)
    return observer, observer


__all__ = ["PipelineTrailObserver", "maybe_wrap_for_runtime_trail"]
