"""Phase 6I — Tests for runtime-driven /api/generate behind feature flag.

Goal of this suite:

1. With ``NEXUS_RUNTIME_DRIVES_GENERATE=False`` (default), /api/generate
   behavior is unchanged: 202 + ``{task_id, status}``, no AgentRun rows
   are written, no agent_run_id in the response payload.
2. With ``NEXUS_RUNTIME_DRIVES_GENERATE=True``, the route additionally
   creates exactly one AgentRun (linked via ``task_id``) and writes a
   single ``thought`` AgentStep, the run is marked ``done``, and the
   response payload still satisfies the existing live-eval adapter
   contract (``task_id`` present, JSON parseable).
3. With the flag on but step persistence failing, the API still returns
   202 with the task_id, the AgentRun row exists, and its status is
   ``failed`` — the failure is recorded, not raised.
4. The Celery enqueue path is monkeypatched to a no-op so no Redis is
   required and these tests stay offline.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from database.connection import get_db
from database.models import AgentRun, AgentStep, Base, Task
from main import app


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://t")


async def _setup_app(monkeypatch=None):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db_override() -> AsyncIterator[AsyncSession]:
        async with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db_override
    return Session, engine


async def _teardown_app(engine):
    app.dependency_overrides.clear()
    await engine.dispose()


def _patch_celery_noop(monkeypatch):
    """Replace ``workers.tasks.run_generation_task.delay`` with a no-op
    so /api/generate never reaches Redis during these offline tests."""
    import workers.tasks as wt

    class _NoopAsyncResult:
        id = "noop-task"

    def _noop_delay(*_args, **_kwargs):  # signature-compatible
        return _NoopAsyncResult()

    monkeypatch.setattr(wt.run_generation_task, "delay", _noop_delay, raising=True)


# ── flag OFF: behavior unchanged ───────────────────────────────────────────

def test_generate_flag_off_response_shape_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "NEXUS_RUNTIME_DRIVES_GENERATE", False, raising=True)
    _patch_celery_noop(monkeypatch)

    async def _go():
        Session, engine = await _setup_app()
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/generate",
                    json={
                        "topic": "Quarterly business review for Q2",
                        "slide_count": 8,
                        "theme": "Editorial",
                        "search_web": False,
                    },
                )
            assert r.status_code == 202, r.text
            body = r.json()
            # Existing contract: exactly the pre-6I public fields. The
            # response must NOT include `agent_run_id` (not even as null)
            # when the feature flag is off — Phase 6I-Fix.
            assert set(body.keys()) == {"task_id", "status"}, body
            assert "agent_run_id" not in body
            assert isinstance(body["task_id"], str) and body["task_id"]
            assert body["status"] == "pending"

            # No AgentRun rows should have been written.
            async with Session() as s:
                runs = (await s.execute(select(AgentRun))).scalars().all()
                assert runs == []
                steps = (await s.execute(select(AgentStep))).scalars().all()
                assert steps == []
                # The Task row exists.
                tasks = (await s.execute(select(Task))).scalars().all()
                assert len(tasks) == 1
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# ── flag ON: AgentRun + AgentStep persisted ────────────────────────────────

def test_generate_flag_on_persists_run_and_step(monkeypatch):
    monkeypatch.setattr(settings, "NEXUS_RUNTIME_DRIVES_GENERATE", True, raising=True)
    _patch_celery_noop(monkeypatch)

    async def _go():
        Session, engine = await _setup_app()
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/generate",
                    json={
                        "topic": "Investor pitch for an AI startup",
                        "slide_count": 10,
                        "theme": "Editorial",
                        "search_web": False,
                    },
                )
            assert r.status_code == 202, r.text
            body = r.json()
            # Existing contract preserved.
            assert isinstance(body.get("task_id"), str) and body["task_id"]
            assert body.get("status") == "pending"
            # Phase 6I addition: agent_run_id surfaced.
            assert isinstance(body.get("agent_run_id"), str) and body["agent_run_id"]

            async with Session() as s:
                runs = (await s.execute(select(AgentRun))).scalars().all()
                assert len(runs) == 1
                run = runs[0]
                assert run.id == body["agent_run_id"]
                assert run.task_id == body["task_id"]
                assert run.status == "done"
                assert run.goal.startswith("Investor pitch")
                assert (run.meta or {}).get("phase") == "6I"
                assert (run.meta or {}).get("dispatch_only") is True

                steps = (
                    await s.execute(
                        select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.step_index)
                    )
                ).scalars().all()
                assert len(steps) == 1
                assert steps[0].kind == "thought"
                assert steps[0].status == "ok"
                assert (steps[0].input_json or {}).get("dispatch") == "celery"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_generate_flag_on_response_compatible_with_live_eval_adapter(monkeypatch):
    """The live-eval adapter only requires ``task_id`` in the JSON body
    of POST /api/generate. Phase 6I must not break that."""
    monkeypatch.setattr(settings, "NEXUS_RUNTIME_DRIVES_GENERATE", True, raising=True)
    _patch_celery_noop(monkeypatch)

    async def _go():
        Session, engine = await _setup_app()
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/generate",
                    json={
                        "topic": "Education deck on photosynthesis",
                        "slide_count": 6,
                        "theme": "Editorial",
                        "search_web": False,
                    },
                )
            assert r.status_code == 202, r.text
            body = r.json()
            # Mirror the live-eval adapter's check.
            task_id = body.get("task_id")
            assert task_id, f"adapter would raise LiveGenerationError: {body!r}"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# ── flag ON, persistence failure: API does not crash, failure recorded ────

def test_generate_flag_on_step_failure_records_failed_run(monkeypatch):
    monkeypatch.setattr(settings, "NEXUS_RUNTIME_DRIVES_GENERATE", True, raising=True)
    _patch_celery_noop(monkeypatch)

    # Make append_step raise inside the route's runtime-dispatch helper.
    import api.routes.generate as gen_mod
    import services.agent_run_service as ars

    real_append = ars.append_step

    async def _exploding_append(*_args, **_kwargs):
        raise RuntimeError("boom: simulated step persistence failure")

    monkeypatch.setattr(ars, "append_step", _exploding_append, raising=True)
    # The route imports append_step lazily inside the helper; re-import path
    # is ``services.agent_run_service.append_step``, so the monkeypatch above
    # is sufficient. Sanity:
    assert gen_mod._record_runtime_dispatch is not None

    async def _go():
        Session, engine = await _setup_app()
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/generate",
                    json={
                        "topic": "Market research summary on EV adoption",
                        "slide_count": 8,
                        "theme": "Editorial",
                        "search_web": False,
                    },
                )
            # API must not crash even if runtime persistence fails.
            assert r.status_code == 202, r.text
            body = r.json()
            assert body.get("task_id")
            assert body.get("status") == "pending"
            # The run row should still exist; helper attempts a finish_run
            # with status="failed" after rollback.
            async with Session() as s:
                runs = (await s.execute(select(AgentRun))).scalars().all()
                assert len(runs) == 1, "AgentRun row must record the failure"
                assert runs[0].status == "failed"
                assert (runs[0].error_msg or "").startswith("dispatch_record_failed")
                # No AgentStep rows because append_step always raised.
                steps = (await s.execute(select(AgentStep))).scalars().all()
                assert steps == []
        finally:
            # Restore append_step explicitly for any subsequent tests.
            monkeypatch.setattr(ars, "append_step", real_append, raising=True)
            await _teardown_app(engine)

    asyncio.run(_go())
