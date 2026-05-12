"""Phase 6AG — tests for the worker-side pipeline-trail observer.

The route (Phase 6I/6AG) opens an :class:`AgentRun` in ``running``
state and the worker is responsible for appending pipeline-phase steps
and finalising it. These tests pin that behavior so item #3 of the
"Known Gaps" list cannot regress silently.

The tests do not run the real ``NexusAgentLoop``; they exercise the
observer in isolation through a fake progress stream. A separate
end-to-end test would require Redis + Celery and is out of scope here.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import AsyncIterator

# conftest.py stubs ``workers`` and ``workers.tasks`` in ``sys.modules``
# with an in-memory ``types.ModuleType`` whose ``__path__`` is ``[]``, so
# the FastAPI app can import the stubbed Celery task without pulling in
# Redis. That stub blocks ``import workers.runtime_trail`` because the
# empty ``__path__`` hides every real submodule. Repair the stub's
# ``__path__`` to point at the real workers directory; the stubbed
# ``workers.tasks`` already in ``sys.modules`` is untouched (tests of
# the Celery route still rely on it).
_workers_stub = sys.modules.get("workers")
if _workers_stub is not None and not getattr(_workers_stub, "__path__", None):
    _real_workers = Path(__file__).resolve().parent.parent / "workers"
    _workers_stub.__path__ = [str(_real_workers)]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import AgentRun, AgentStep, Base, Task


# ── shared fixtures ───────────────────────────────────────────────────────

def _build_inmemory_db_factory():
    """Create an in-memory async SQLite engine + sessionmaker.

    Patches ``database.connection.SessionLocal`` so the observer (which
    opens its own sessions) writes into this test database instead of
    the real one.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, Session


async def _seed_task_and_run(Session, *, status_meta="pipeline_trail") -> tuple[str, str]:
    """Insert a Task + open AgentRun. Returns (task_id, run_id)."""
    async with Session() as s:
        task = Task(
            topic="Phase 6AG worker trail test",
            slide_count=6,
            theme="Editorial",
            search_web=False,
            status="pending",
        )
        s.add(task)
        await s.flush()
        run = AgentRun(
            goal=task.topic,
            task_id=task.id,
            status="running",
            max_steps=12,
            meta={"phase": "6AG", "mode": status_meta},
        )
        s.add(run)
        await s.commit()
        return task.id, run.id


# ── tests ─────────────────────────────────────────────────────────────────

def test_observer_appends_stage_steps_and_finalises_run(monkeypatch):
    """Fire a typical progress stream and assert the trail is recorded."""

    async def _go():
        engine, Session = _build_inmemory_db_factory()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Point the observer's SessionLocal at our in-memory engine.
        import workers.runtime_trail as rt

        monkeypatch.setattr(rt, "SessionLocal", Session, raising=True)

        try:
            task_id, run_id = await _seed_task_and_run(Session)

            inner_calls: list[tuple] = []

            async def _inner(message, progress_pct, step, **extra):
                inner_calls.append((message, progress_pct, step, dict(extra)))

            cb, observer = await rt.maybe_wrap_for_runtime_trail(task_id, _inner)
            assert observer is not None
            assert cb is observer

            # Simulate the loop's progress stream — three stages, one
            # milestone event mid-stream, then a terminal ``done`` status.
            await cb("Analyzing your topic...", 8.0, "analyze")
            await cb("Researching web...", 18.0, "search")
            await cb("example.com", 19.0, "search", event="source_found", url="https://x")
            await cb("Building strategy...", 24.0, "strategy")
            await cb("Planning slide structure...", 28.0, "plan")
            await cb("Outline ready", 30.0, "plan", event="outline_ready")
            await cb("Saving deck...", 95.0, "save")
            await cb("Done", 100.0, "done", status="done")

            # The inner callback must have been called for every progress event.
            assert len(inner_calls) == 8

            # AgentRun: finalised to done.
            async with Session() as s:
                run = (
                    await s.execute(select(AgentRun).where(AgentRun.id == run_id))
                ).scalar_one()
                assert run.status == "done"
                assert run.completed_at is not None

                steps = (
                    await s.execute(
                        select(AgentStep)
                        .where(AgentStep.run_id == run_id)
                        .order_by(AgentStep.step_index)
                    )
                ).scalars().all()

            # One step per new stage transition + one for outline_ready
            # milestone + one ``final``. ``source_found`` is intentionally
            # NOT in the milestone allow-list (too noisy), so it is not
            # recorded as a step.
            kinds = [(s.kind, s.action) for s in steps]
            assert ("observation", "analyze") in kinds
            assert ("observation", "search") in kinds
            assert ("observation", "strategy") in kinds
            assert ("observation", "plan") in kinds
            assert ("observation", "save") in kinds
            assert ("observation", "plan") in kinds  # also outline_ready event
            # The terminal step must be the ``final`` kind.
            assert steps[-1].kind == "final"
            assert steps[-1].status == "ok"
            # Source-found is filtered out as noise.
            assert not any(
                (s.input_json or {}).get("event") == "source_found" for s in steps
            )
        finally:
            await engine.dispose()

    asyncio.run(_go())


def test_observer_finalize_unexpected_marks_failed(monkeypatch):
    """If the worker times out before a terminal progress event fires,
    ``finalize_unexpected`` must close out the run."""

    async def _go():
        engine, Session = _build_inmemory_db_factory()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        import workers.runtime_trail as rt

        monkeypatch.setattr(rt, "SessionLocal", Session, raising=True)
        try:
            task_id, run_id = await _seed_task_and_run(Session)

            async def _noop(*_a, **_kw):
                pass

            cb, observer = await rt.maybe_wrap_for_runtime_trail(task_id, _noop)
            assert observer is not None

            await cb("Analyzing...", 8.0, "analyze")
            await observer.finalize_unexpected(status="failed", error="timeout")

            async with Session() as s:
                run = (await s.execute(select(AgentRun))).scalar_one()
                assert run.status == "failed"
                assert run.error_msg == "timeout"
        finally:
            await engine.dispose()

    asyncio.run(_go())


def test_observer_absent_when_no_running_run(monkeypatch):
    """If no pipeline-trail AgentRun was opened (flag off path), the
    helper returns the inner callback unmodified and observer=None."""

    async def _go():
        engine, Session = _build_inmemory_db_factory()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        import workers.runtime_trail as rt

        monkeypatch.setattr(rt, "SessionLocal", Session, raising=True)
        try:
            async with Session() as s:
                task = Task(
                    topic="No runtime trail",
                    slide_count=6,
                    theme="Editorial",
                    search_web=False,
                    status="pending",
                )
                s.add(task)
                await s.commit()
                task_id = task.id

            async def _inner(*_a, **_kw):
                pass

            cb, observer = await rt.maybe_wrap_for_runtime_trail(task_id, _inner)
            assert observer is None
            assert cb is _inner
        finally:
            await engine.dispose()

    asyncio.run(_go())


def test_observer_swallows_inner_callback_errors(monkeypatch):
    """Observer must never let inner-callback failures break the loop."""

    async def _go():
        engine, Session = _build_inmemory_db_factory()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        import workers.runtime_trail as rt

        monkeypatch.setattr(rt, "SessionLocal", Session, raising=True)
        try:
            task_id, _run_id = await _seed_task_and_run(Session)

            async def _exploding(*_a, **_kw):
                raise RuntimeError("redis exploded")

            cb, observer = await rt.maybe_wrap_for_runtime_trail(task_id, _exploding)
            assert observer is not None
            # Must not raise even though inner callback always raises.
            await cb("Analyzing...", 8.0, "analyze")
            await cb("Done", 100.0, "done", status="done")

            async with Session() as s:
                run = (await s.execute(select(AgentRun))).scalar_one()
                # Terminal handling still ran despite inner errors.
                assert run.status == "done"
        finally:
            await engine.dispose()

    asyncio.run(_go())
