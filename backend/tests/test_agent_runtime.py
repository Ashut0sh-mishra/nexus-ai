"""Phase 2 — AgentRuntime tests.

Pure in-memory SQLite + a fake planner that returns scripted JSON actions.
No real LLM calls, no network, no Playwright.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent.runtime import (
    Action,
    AgentRuntime,
    RuntimeConfig,
    parse_action,
)
from database.models import AgentRun, AgentStep, Base


def _new_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init())
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


def _scripted_planner(scripts):
    """Return an async planner that yields *scripts* in order.

    Each script entry can be a JSON-serializable dict (auto-encoded), a raw
    string, or an Exception instance which will be raised.
    """
    queue = list(scripts)

    async def _plan(_goal, _history):
        if not queue:
            raise RuntimeError("planner exhausted")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, dict):
            return json.dumps(item)
        return str(item)

    return _plan


# ── parse_action ──────────────────────────────────────────────────────────
def test_parse_action_valid_final():
    a, err = parse_action('{"kind":"final","text":"hello"}')
    assert err is None
    assert a == Action(kind="final", text="hello")


def test_parse_action_valid_tool_with_fence():
    raw = "thinking...\n```json\n{\"kind\":\"tool\",\"name\":\"idle\",\"args\":{}}\n```"
    a, err = parse_action(raw)
    assert err is None
    assert a.kind == "tool" and a.name == "idle" and a.args == {}


def test_parse_action_rejects_garbage():
    a, err = parse_action("not json at all")
    assert a is None and err == "planner_output_not_json"


def test_parse_action_rejects_unknown_kind():
    a, err = parse_action('{"kind":"weird"}')
    assert a is None and "invalid_kind" in err


def test_parse_action_rejects_tool_without_name():
    a, err = parse_action('{"kind":"tool","args":{}}')
    assert a is None and err == "tool_action_missing_name"


# ── runtime: happy path ──────────────────────────────────────────────────
def test_runtime_happy_path_final_first_step():
    Session, _ = _new_session_factory()
    planner = _scripted_planner([{"kind": "final", "text": "done!"}])
    rt = AgentRuntime(planner, RuntimeConfig(max_steps=5))

    async def _go():
        async with Session() as s:
            res = await rt.run(s, goal="say done")
            assert res.status == "done"
            assert res.final_text == "done!"
            # 1 thought + 1 final = 2 persisted steps
            run = await s.get(AgentRun, res.run_id)
            assert run.status == "done"
            assert run.step_count == 2

    asyncio.run(_go())


def test_runtime_runs_idle_tool_then_finals():
    Session, _ = _new_session_factory()
    planner = _scripted_planner([
        {"kind": "tool", "name": "idle", "args": {}},
        {"kind": "final", "text": "ok"},
    ])
    rt = AgentRuntime(planner, RuntimeConfig(max_steps=5))

    async def _go():
        async with Session() as s:
            res = await rt.run(s, goal="idle then end")
            assert res.status == "done"
            kinds = [r.kind for r in res.steps]
            # thought(tool) + observation(ok) + thought(final) + final
            assert kinds == ["thought", "observation", "thought", "final"]
            assert res.steps[1].output.get("ok") is True

    asyncio.run(_go())


# ── runtime: safety / errors ─────────────────────────────────────────────
def test_runtime_unknown_tool_records_error():
    Session, _ = _new_session_factory()
    planner = _scripted_planner([
        {"kind": "tool", "name": "no_such_tool", "args": {}},
        {"kind": "final", "text": "recovered"},
    ])
    rt = AgentRuntime(planner, RuntimeConfig(max_steps=5, max_tool_failures=3))

    async def _go():
        async with Session() as s:
            res = await rt.run(s, goal="recover")
            assert res.status == "done"
            obs = [r for r in res.steps if r.kind == "observation"]
            assert obs and obs[0].error == "unknown_tool"

    asyncio.run(_go())


def test_runtime_disallowed_tool_blocked_by_allowlist():
    Session, _ = _new_session_factory()
    planner = _scripted_planner([
        {"kind": "tool", "name": "shell_exec", "args": {"command": "echo x"}},
        {"kind": "final", "text": "stop"},
    ])
    rt = AgentRuntime(
        planner,
        RuntimeConfig(max_steps=5, allowed_tools={"idle", "info_search_web"}),
    )

    async def _go():
        async with Session() as s:
            res = await rt.run(s, goal="blocked")
            obs = [r for r in res.steps if r.kind == "observation"]
            assert obs[0].error == "tool_not_allowed"

    asyncio.run(_go())


def test_runtime_max_failures_terminates():
    Session, _ = _new_session_factory()
    planner = _scripted_planner([
        "garbage",
        {"kind": "tool", "name": "no_such", "args": {}},
        {"kind": "tool", "name": "no_such", "args": {}},
    ])
    rt = AgentRuntime(planner, RuntimeConfig(max_steps=10, max_tool_failures=3))

    async def _go():
        async with Session() as s:
            res = await rt.run(s, goal="fail fast")
            assert res.status == "failed"
            assert "max_failures_exceeded" in (res.error or "")

    asyncio.run(_go())


def test_runtime_max_steps_terminates_when_no_final():
    Session, _ = _new_session_factory()
    # Always return a benign message that never ends the loop.
    scripts = [{"kind": "message", "text": f"step {i}"} for i in range(10)]
    planner = _scripted_planner(scripts)
    rt = AgentRuntime(planner, RuntimeConfig(max_steps=4, max_tool_failures=99))

    async def _go():
        async with Session() as s:
            res = await rt.run(s, goal="never ends")
            assert res.status == "failed"
            assert res.error == "max_steps_exceeded"
            # 4 thought steps recorded
            assert sum(1 for r in res.steps if r.kind == "thought") == 4

    asyncio.run(_go())


def test_runtime_planner_timeout_marks_failed():
    Session, _ = _new_session_factory()

    async def _slow_planner(_goal, _history):
        await asyncio.sleep(5)
        return '{"kind":"final","text":"never"}'

    rt = AgentRuntime(_slow_planner, RuntimeConfig(max_steps=3, per_step_timeout=0.05))

    async def _go():
        async with Session() as s:
            res = await rt.run(s, goal="timeout")
            assert res.status == "failed"
            assert res.error == "planner_timeout"

    asyncio.run(_go())


def test_runtime_persists_steps_in_db():
    Session, _ = _new_session_factory()
    planner = _scripted_planner([
        {"kind": "tool", "name": "idle", "args": {}},
        {"kind": "final", "text": "bye"},
    ])
    rt = AgentRuntime(planner, RuntimeConfig(max_steps=5))

    async def _go():
        async with Session() as s:
            res = await rt.run(s, goal="persist check")
            run = await s.get(AgentRun, res.run_id)
            assert run.status == "done"
            assert run.step_count == 4  # thought,obs,thought,final
            # Each step should be retrievable.
            from sqlalchemy import select
            q = await s.execute(select(AgentStep).where(AgentStep.run_id == res.run_id).order_by(AgentStep.step_index))
            rows = list(q.scalars().all())
            assert [r.step_index for r in rows] == [0, 1, 2, 3]
            assert rows[0].kind == "thought"
            assert rows[1].kind == "observation"
            assert rows[1].output_json["ok"] is True

    asyncio.run(_go())
