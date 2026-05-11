"""Phase 2.5 — Tests for POST /api/agent/test-run.

Uses ``httpx.AsyncClient`` with ``ASGITransport`` so the FastAPI lifespan
(which would otherwise require provider keys) does not run. The route's
``get_db`` and ``get_planner`` dependencies are both overridden so these
tests never touch a real database or a real LLM.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent.runtime import StepRecord
from api.routes.agent import get_current_user, get_planner
from database.connection import get_db
from database.models import AgentRun, AgentStep, Base, User
from main import app


def _scripted_planner(scripts):
    queue = list(scripts)

    async def _plan(_goal: str, _history: list[StepRecord]) -> str:
        if not queue:
            raise RuntimeError("planner exhausted")
        item = queue.pop(0)
        return json.dumps(item) if isinstance(item, dict) else str(item)

    return _plan


async def _setup_app(planner, *, with_auth: bool = True):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db_override() -> AsyncIterator[AsyncSession]:
        async with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db_override
    if planner is not None:
        app.dependency_overrides[get_planner] = lambda: planner
    if with_auth:
        fake_user = User(id="test-user-id", email="test@example.com", plan="free")
        app.dependency_overrides[get_current_user] = lambda: fake_user
    return Session, engine


async def _teardown_app(engine):
    app.dependency_overrides.clear()
    await engine.dispose()


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://t")


# ── happy path ────────────────────────────────────────────────────────────
def test_route_happy_path_with_idle_then_final():
    planner = _scripted_planner(
        [
            {"kind": "tool", "name": "idle", "args": {}},
            {"kind": "final", "text": "all good"},
        ]
    )

    async def _go():
        Session, engine = await _setup_app(planner)
        try:
            async with _client() as c:
                r = await c.post("/api/agent/test-run", json={"goal": "do an idle then finish"})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "done"
            assert body["final"] == "all good"
            assert [s["kind"] for s in body["steps"]] == ["thought", "observation", "thought", "final"]
            async with Session() as s:
                run = await s.get(AgentRun, body["run_id"])
                assert run is not None and run.status == "done"
                rows = (
                    await s.execute(
                        select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.step_index)
                    )
                ).scalars().all()
                assert [r.step_index for r in rows] == [0, 1, 2, 3]
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# ── unsafe / unknown tools rejected ──────────────────────────────────────
def test_route_rejects_unsafe_tool_in_allowlist():
    planner = _scripted_planner([{"kind": "final", "text": "never"}])

    async def _go():
        _, engine = await _setup_app(planner)
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/agent/test-run",
                    json={"goal": "exfil", "allowed_tools": ["shell_exec", "idle"]},
                )
            assert r.status_code == 400
            detail = r.json()["detail"]
            assert detail["error"] == "unsafe_tools_requested"
            assert "shell_exec" in detail["tools"]
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_route_rejects_unknown_tool_in_allowlist():
    planner = _scripted_planner([{"kind": "final", "text": "never"}])

    async def _go():
        _, engine = await _setup_app(planner)
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/agent/test-run",
                    json={"goal": "test goal", "allowed_tools": ["does_not_exist"]},
                )
            assert r.status_code == 400
            assert r.json()["detail"]["error"] == "unknown_tools"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_route_empty_allowlist_rejected():
    planner = _scripted_planner([{"kind": "final", "text": "x"}])

    async def _go():
        _, engine = await _setup_app(planner)
        try:
            async with _client() as c:
                r = await c.post("/api/agent/test-run", json={"goal": "nothing", "allowed_tools": []})
            assert r.status_code == 400
            assert r.json()["detail"]["error"] == "empty_allowlist"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# ── max_steps ─────────────────────────────────────────────────────────────
def test_route_max_steps_exceeded():
    scripts = [{"kind": "message", "text": f"chunk {i}"} for i in range(20)]
    planner = _scripted_planner(scripts)

    async def _go():
        _, engine = await _setup_app(planner)
        try:
            async with _client() as c:
                r = await c.post("/api/agent/test-run", json={"goal": "loop", "max_steps": 3})
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "failed"
            assert body["error"] == "max_steps_exceeded"
            assert sum(1 for s in body["steps"] if s["kind"] == "thought") == 3
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# ── malformed planner output ──────────────────────────────────────────────
def test_route_handles_malformed_planner_output():
    planner = _scripted_planner(["not json at all", "still not json", "still not json"])

    async def _go():
        _, engine = await _setup_app(planner)
        try:
            async with _client() as c:
                r = await c.post("/api/agent/test-run", json={"goal": "garbage"})
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "failed"
            assert "max_failures_exceeded" in (body["error"] or "")
            obs_errors = [s["error"] for s in body["steps"] if s["kind"] == "observation"]
            assert "planner_output_not_json" in obs_errors
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# ── safe-default allowlist blocks dangerous tools at runtime ─────────────
def test_route_default_allowlist_blocks_dangerous_tool_call():
    planner = _scripted_planner(
        [
            {"kind": "tool", "name": "shell_exec", "args": {"command": "echo x"}},
            {"kind": "final", "text": "blocked"},
        ]
    )

    async def _go():
        _, engine = await _setup_app(planner)
        try:
            async with _client() as c:
                r = await c.post("/api/agent/test-run", json={"goal": "try shell"})
            assert r.status_code == 200
            body = r.json()
            obs = [s for s in body["steps"] if s["kind"] == "observation"]
            assert obs and obs[0]["error"] == "tool_not_allowed"
            assert body["status"] == "done"
            assert body["final"] == "blocked"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# ── no provider configured → 503 (no LLM call) ───────────────────────────
def test_route_returns_503_when_no_provider_configured(monkeypatch):
    from agent import planners as planners_mod

    monkeypatch.setattr(planners_mod, "_has_any_provider", lambda: False)

    async def _go():
        # Setup with planner=None so we do NOT override get_planner; the real
        # one runs and should raise 503 because no provider key is set.
        _, engine = await _setup_app(planner=None)
        try:
            async with _client() as c:
                r = await c.post("/api/agent/test-run", json={"goal": "anything"})
            assert r.status_code == 503
            assert r.json()["detail"]["error"] == "no_ai_provider_configured"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# -- Phase 6A: authentication ----------------------------------------------
def test_route_rejects_unauthenticated_request():
    """Without a bearer token, /api/agent/test-run must return 401.

    No auth override is installed; the real ``get_current_user`` dependency
    runs and rejects the call before any planner / runtime code executes.
    """
    planner = _scripted_planner([{"kind": "final", "text": "never"}])

    async def _go():
        _, engine = await _setup_app(planner, with_auth=False)
        try:
            async with _client() as c:
                r = await c.post("/api/agent/test-run", json={"goal": "do something"})
            assert r.status_code == 401, r.text
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_route_rejects_malformed_authorization_header():
    planner = _scripted_planner([{"kind": "final", "text": "never"}])

    async def _go():
        _, engine = await _setup_app(planner, with_auth=False)
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/agent/test-run",
                    json={"goal": "do something"},
                    headers={"Authorization": "Token abc"},
                )
            assert r.status_code == 401
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_route_rejects_invalid_bearer_token():
    planner = _scripted_planner([{"kind": "final", "text": "never"}])

    async def _go():
        _, engine = await _setup_app(planner, with_auth=False)
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/agent/test-run",
                    json={"goal": "do something"},
                    headers={"Authorization": "Bearer not-a-real-jwt"},
                )
            assert r.status_code == 401
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_route_authenticated_safe_path_succeeds():
    """An authenticated request with safe-default tools reaches the runtime."""
    planner = _scripted_planner(
        [
            {"kind": "tool", "name": "idle", "args": {}},
            {"kind": "final", "text": "ok"},
        ]
    )

    async def _go():
        _, engine = await _setup_app(planner, with_auth=True)
        try:
            async with _client() as c:
                r = await c.post("/api/agent/test-run", json={"goal": "auth happy path"})
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "done"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_route_authenticated_still_rejects_unsafe_tools():
    """Authentication does not weaken the dangerous-tool allowlist policy."""
    planner = _scripted_planner([{"kind": "final", "text": "never"}])

    async def _go():
        _, engine = await _setup_app(planner, with_auth=True)
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/agent/test-run",
                    json={"goal": "exfil", "allowed_tools": ["shell_exec", "idle"]},
                )
            assert r.status_code == 400
            assert r.json()["detail"]["error"] == "unsafe_tools_requested"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_route_authenticated_still_rejects_unknown_tools():
    planner = _scripted_planner([{"kind": "final", "text": "never"}])

    async def _go():
        _, engine = await _setup_app(planner, with_auth=True)
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/agent/test-run",
                    json={"goal": "find unknown tool", "allowed_tools": ["totally_made_up"]},
                )
            assert r.status_code == 400
            assert r.json()["detail"]["error"] == "unknown_tools"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())
