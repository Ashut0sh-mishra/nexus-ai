"""Phase 3 — runtime artifact recording + route response artifact summary.

These tests use a fake tool registered in ``agent.tools.TOOLS`` so the
runtime can dispatch a ``ToolResult`` shaped like ``info_search_web`` without
touching the network or any provider key.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent import tools as tools_mod
from agent.runtime import AgentRuntime, RuntimeConfig
from agent.tools import ToolResult
from api.routes.agent import get_current_user, get_planner
from database.connection import get_db
from database.models import Artifact, Base, User
from main import app


def _scripted_planner(scripts):
    queue = list(scripts)

    async def _plan(_g, _h):
        if not queue:
            raise RuntimeError("planner exhausted")
        item = queue.pop(0)
        return json.dumps(item) if isinstance(item, dict) else str(item)

    return _plan


# ── runtime: artifacts for successful info_search_web ────────────────────
def test_runtime_records_source_artifacts_for_search_observation(monkeypatch):
    fake_payload = {
        "summary": "AI capex doubled.",
        "sources": [
            {"title": "Stanford AI Index", "url": "https://aiindex.org",
             "snippet": "GPU spend doubled in 2024"},
            {"title": "OECD AI Outlook", "url": "https://oecd.org/ai",
             "snippet": "Adoption rates climbing"},
        ],
    }

    async def _fake_search(query: str, max_results: int = 5):
        return ToolResult(ok=True, data=fake_payload)

    monkeypatch.setitem(tools_mod.TOOLS, "info_search_web", _fake_search)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _go():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        planner = _scripted_planner([
            {"kind": "tool", "name": "info_search_web", "args": {"query": "ai capex"}},
            {"kind": "final", "text": "found"},
        ])
        rt = AgentRuntime(planner, RuntimeConfig(max_steps=4))
        async with Session() as s:
            res = await rt.run(s, goal="search for ai capex")
            assert res.status == "done"
            arts = (await s.execute(select(Artifact).where(Artifact.run_id == res.run_id))).scalars().all()
            assert len(arts) == 2
            assert {a.artifact_type for a in arts} == {"source"}
            urls = {a.meta.get("url") for a in arts}
            assert urls == {"https://aiindex.org", "https://oecd.org/ai"}
            for a in arts:
                assert a.meta["tool"] == "info_search_web"
                assert a.meta["confidence"] in {"high", "medium", "low", "unknown"}
        await engine.dispose()

    asyncio.run(_go())


def test_runtime_records_no_artifact_for_failed_tool(monkeypatch):
    async def _fake_search(query: str, max_results: int = 5):
        return ToolResult(ok=False, error="search_failed")

    monkeypatch.setitem(tools_mod.TOOLS, "info_search_web", _fake_search)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _go():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        planner = _scripted_planner([
            {"kind": "tool", "name": "info_search_web", "args": {"query": "x"}},
            {"kind": "final", "text": "done"},
        ])
        rt = AgentRuntime(planner, RuntimeConfig(max_steps=4))
        async with Session() as s:
            res = await rt.run(s, goal="search and proceed")
            arts = (await s.execute(select(Artifact).where(Artifact.run_id == res.run_id))).scalars().all()
            assert arts == []
        await engine.dispose()

    asyncio.run(_go())


# ── route: response includes artifact summary ────────────────────────────
async def _setup_route_app(planner):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db_override() -> AsyncIterator[AsyncSession]:
        async with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_planner] = lambda: planner
    fake_user = User(id="test-user-id", email="test@example.com", plan="free")
    app.dependency_overrides[get_current_user] = lambda: fake_user
    return Session, engine


def test_route_response_includes_artifact_summary(monkeypatch):
    fake_payload = {
        "summary": "X.",
        "sources": [
            {"title": "A", "url": "https://a", "snippet": "a"},
            {"title": "B", "url": "https://b", "snippet": "b"},
        ],
    }

    async def _fake_search(query: str, max_results: int = 5):
        return ToolResult(ok=True, data=fake_payload)

    monkeypatch.setitem(tools_mod.TOOLS, "info_search_web", _fake_search)

    planner = _scripted_planner([
        {"kind": "tool", "name": "info_search_web", "args": {"query": "demo"}},
        {"kind": "final", "text": "ok"},
    ])

    async def _go():
        _, engine = await _setup_route_app(planner)
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                r = await c.post("/api/agent/test-run", json={"goal": "find sources for demo"})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "done"
            assert "artifacts" in body
            assert body["artifacts"]["sources"] == 2
            assert body["artifacts"]["total"] == 2
            assert body["artifacts"]["by_type"].get("source") == 2
            # The response stays small — no raw source payloads embedded.
            assert "snippet" not in json.dumps(body["artifacts"])
        finally:
            app.dependency_overrides.clear()
            await engine.dispose()

    asyncio.run(_go())
