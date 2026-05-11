"""Phase 1 — AgentRun / AgentStep / Artifact storage tests.

Uses an isolated in-memory SQLite engine so these tests never touch the real
database and never depend on the project conftest.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import AgentRun, AgentStep, Artifact, Base
from services.agent_run_service import (
    append_step,
    create_run,
    finish_run,
    list_artifacts_for_run,
    record_artifact,
)


def _new_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init())
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def test_create_run_persists_minimal_fields():
    Session = _new_session_factory()

    async def _run():
        async with Session() as s:
            run = await create_run(s, goal="say hello", max_steps=5)
            await s.commit()
            assert run.id and len(run.id) == 36
            assert run.goal == "say hello"
            assert run.status == "running"
            assert run.max_steps == 5
            assert run.step_count == 0

    asyncio.run(_run())


def test_append_step_increments_index_and_records_payload():
    Session = _new_session_factory()

    async def _run():
        async with Session() as s:
            run = await create_run(s, goal="multi-step")
            await s.commit()

            s1 = await append_step(s, run_id=run.id, kind="thought", input_json={"plan": "search"})
            s2 = await append_step(
                s, run_id=run.id, kind="action", action="info_search_web",
                input_json={"query": "x"}, output_json={"summary": "y"},
            )
            s3 = await append_step(
                s, run_id=run.id, kind="observation", output_json={"hits": 3},
            )
            await s.commit()

            assert (s1.step_index, s2.step_index, s3.step_index) == (0, 1, 2)
            assert s2.action == "info_search_web"
            assert s2.output_json == {"summary": "y"}
            refreshed = await s.get(AgentRun, run.id)
            assert refreshed.step_count == 3

    asyncio.run(_run())


def test_invalid_step_kind_rejected():
    Session = _new_session_factory()

    async def _run():
        async with Session() as s:
            run = await create_run(s, goal="bad")
            await s.commit()
            with pytest.raises(ValueError):
                await append_step(s, run_id=run.id, kind="garbage")

    asyncio.run(_run())


def test_record_artifact_and_list():
    Session = _new_session_factory()

    async def _run():
        async with Session() as s:
            run = await create_run(s, goal="emit")
            await s.commit()
            await record_artifact(
                s, artifact_type="deck", run_id=run.id,
                title="Test Deck", meta={"slides": 3}, file_url="/tmp/x.pptx",
            )
            await record_artifact(
                s, artifact_type="source", run_id=run.id,
                title="example.com", meta={"url": "https://example.com"},
            )
            await s.commit()

            arts = await list_artifacts_for_run(s, run.id)
            assert len(arts) == 2
            assert {a.artifact_type for a in arts} == {"deck", "source"}

    asyncio.run(_run())


def test_finish_run_transitions_status():
    Session = _new_session_factory()

    async def _run():
        async with Session() as s:
            run = await create_run(s, goal="done")
            await s.commit()
            done = await finish_run(s, run_id=run.id, status="done")
            await s.commit()
            assert done.status == "done"
            assert done.completed_at is not None
            with pytest.raises(ValueError):
                await finish_run(s, run_id=run.id, status="not-a-status")

    asyncio.run(_run())


def test_finish_run_failed_records_error():
    Session = _new_session_factory()

    async def _run():
        async with Session() as s:
            run = await create_run(s, goal="boom")
            await s.commit()
            done = await finish_run(s, run_id=run.id, status="failed", error="kaboom")
            await s.commit()
            assert done.status == "failed"
            assert done.error_msg == "kaboom"

    asyncio.run(_run())
