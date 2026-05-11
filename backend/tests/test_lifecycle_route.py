"""Phase 6Q — Job lifecycle endpoints and cancel signal.

These tests exercise the new ``/api/lifecycle/*`` surface end-to-end and
prove the cancel signal flows from the route into a backing
``Task.status`` value the worker can poll.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.connection import get_db
from database.models import Base, Task
from main import app


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://t")


async def _setup_app(*, status: str = "pending"):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db_override() -> AsyncIterator[AsyncSession]:
        async with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db_override

    task_id = "task-lc-test"
    async with Session() as s:
        s.add(
            Task(
                id=task_id,
                topic="Renewables",
                slide_count=6,
                theme="Editorial",
                status=status,
                current_step="analyze" if status == "running" else "queued",
                progress_pct=42.0 if status == "running" else 0.0,
            )
        )
        await s.commit()

    return Session, engine, task_id


async def _teardown(engine):
    app.dependency_overrides.clear()
    await engine.dispose()


def _patch_celery_noop(monkeypatch):
    import workers.tasks as wt

    class _NoopAsyncResult:
        id = "noop-task"

    seen: dict[str, int] = {"calls": 0}

    def _noop_delay(*_args, **_kwargs):
        seen["calls"] += 1
        return _NoopAsyncResult()

    monkeypatch.setattr(wt.run_generation_task, "delay", _noop_delay, raising=True)
    return seen


# ── 1. GET status payload ────────────────────────────────────────────────


def test_lifecycle_get_returns_payload_for_running_task():
    async def _go():
        Session, engine, task_id = await _setup_app(status="running")
        try:
            async with _client() as c:
                r = await c.get(f"/api/lifecycle/{task_id}")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["task_id"] == task_id
            assert body["state"] == "running"
            assert body["status"] == "running"
            assert body["is_terminal"] is False
            assert body["allowed_actions"] == ["cancel"]
            assert body["progress_pct"] == 42.0
        finally:
            await _teardown(engine)

    asyncio.run(_go())


def test_lifecycle_get_404_when_missing():
    async def _go():
        _, engine, _ = await _setup_app()
        try:
            async with _client() as c:
                r = await c.get("/api/lifecycle/does-not-exist")
            assert r.status_code == 404
        finally:
            await _teardown(engine)

    asyncio.run(_go())


# ── 2. State mapping ─────────────────────────────────────────────────────


def test_lifecycle_legacy_status_maps_to_lifecycle_state():
    async def _go():
        Session, engine, task_id = await _setup_app(status="done")
        try:
            async with _client() as c:
                r = await c.get(f"/api/lifecycle/{task_id}")
            body = r.json()
            assert body["state"] == "succeeded"
            assert body["is_terminal"] is True
            assert body["allowed_actions"] == []
        finally:
            await _teardown(engine)

    asyncio.run(_go())


# ── 3. Cancel ────────────────────────────────────────────────────────────


def test_cancel_marks_cancelling():
    async def _go():
        Session, engine, task_id = await _setup_app(status="running")
        try:
            async with _client() as c:
                r = await c.post(f"/api/lifecycle/{task_id}/cancel")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["state"] == "cancelling"
            assert body["status"] == "cancelling"

            async with Session() as s:
                t = (
                    await s.execute(select(Task).where(Task.id == task_id))
                ).scalar_one()
                assert t.status == "cancelling"
                assert t.current_step == "cancelling"
        finally:
            await _teardown(engine)

    asyncio.run(_go())


def test_cancel_idempotent():
    async def _go():
        Session, engine, task_id = await _setup_app(status="running")
        try:
            async with _client() as c:
                r1 = await c.post(f"/api/lifecycle/{task_id}/cancel")
                r2 = await c.post(f"/api/lifecycle/{task_id}/cancel")
            assert r1.status_code == 200
            assert r2.status_code == 200
            assert r2.json()["state"] == "cancelling"
        finally:
            await _teardown(engine)

    asyncio.run(_go())


def test_cancel_rejected_for_terminal_task():
    async def _go():
        Session, engine, task_id = await _setup_app(status="done")
        try:
            async with _client() as c:
                r = await c.post(f"/api/lifecycle/{task_id}/cancel")
            assert r.status_code == 409
            assert r.json()["detail"]["error"] == "invalid_transition"
        finally:
            await _teardown(engine)

    asyncio.run(_go())


# ── 4. Retry / Resume ────────────────────────────────────────────────────


def test_retry_re_enqueues_after_failure(monkeypatch):
    seen = _patch_celery_noop(monkeypatch)

    async def _go():
        Session, engine, task_id = await _setup_app(status="failed")
        async with Session() as s:
            t = (
                await s.execute(select(Task).where(Task.id == task_id))
            ).scalar_one()
            t.error_msg = "boom"
            t.progress_pct = 70.0
            s.add(t)
            await s.commit()
        try:
            async with _client() as c:
                r = await c.post(f"/api/lifecycle/{task_id}/retry")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["state"] == "queued"
            assert body["from_checkpoint"] is False
            assert body["error"] is None
            assert body["progress_pct"] == 0.0
            assert seen["calls"] == 1

            async with Session() as s:
                t = (
                    await s.execute(select(Task).where(Task.id == task_id))
                ).scalar_one()
                assert t.status == "pending"
                assert t.error_msg is None
        finally:
            await _teardown(engine)

    asyncio.run(_go())


def test_resume_is_honest_retry_from_scratch(monkeypatch):
    seen = _patch_celery_noop(monkeypatch)

    async def _go():
        Session, engine, task_id = await _setup_app(status="cancelled")
        try:
            async with _client() as c:
                r = await c.post(f"/api/lifecycle/{task_id}/resume")
            assert r.status_code == 200, r.text
            body = r.json()
            # Documented honest fallback: there is no persisted
            # mid-run checkpoint, so resume == retry on the wire.
            assert body["from_checkpoint"] is False
            assert body["state"] == "queued"
            assert seen["calls"] == 1
        finally:
            await _teardown(engine)

    asyncio.run(_go())


def test_retry_rejected_for_running_task(monkeypatch):
    _patch_celery_noop(monkeypatch)

    async def _go():
        Session, engine, task_id = await _setup_app(status="running")
        try:
            async with _client() as c:
                r = await c.post(f"/api/lifecycle/{task_id}/retry")
            assert r.status_code == 409
        finally:
            await _teardown(engine)

    asyncio.run(_go())


# ── 5. Cancel signal observable by the loop ──────────────────────────────


def test_loop_observes_cancel_via_task_status():
    """The cancel signal is implemented as ``Task.status == 'cancelling'``.

    The agent loop's ``_mark_running`` checkpoint reads this and raises
    :class:`JobCancelled`. We exercise that directly without spinning up
    the full loop, because the route -> DB write is the contract the
    worker depends on.
    """
    from services.lifecycle_service import JobCancelled, request_cancel

    async def _go():
        Session, engine, task_id = await _setup_app(status="running")
        try:
            async with Session() as s:
                await request_cancel(s, task_id)

            from agent.loop import NexusAgentLoop

            # Patch SessionLocal used inside the loop to point at the
            # in-memory engine, so ``_mark_running`` reads our row.
            import agent.loop as agent_loop_mod

            original_session_local = agent_loop_mod.SessionLocal
            agent_loop_mod.SessionLocal = Session
            try:
                loop_obj = NexusAgentLoop.__new__(NexusAgentLoop)
                raised = False
                try:
                    await loop_obj._mark_running(task_id, "analyze", 10.0)
                except JobCancelled:
                    raised = True
                assert raised, "loop did not honour cancel signal"
            finally:
                agent_loop_mod.SessionLocal = original_session_local
        finally:
            await _teardown(engine)

    asyncio.run(_go())
