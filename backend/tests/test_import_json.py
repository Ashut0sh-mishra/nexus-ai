"""Phase 6AN-JsonImport \u2014 /api/import/json endpoint tests.

Mirrors the in-memory SQLite + dependency-override pattern used by
``test_import_pptx.py``. The Celery enqueue path is monkeypatched to a
no-op so the tests are hermetic; the seed-write side-effect on disk
uses a temp ``MEMORY_DIR`` provided by ``tmp_path``.
"""

from __future__ import annotations

from typing import AsyncIterator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from database.connection import get_db
from database.models import Base, SlideDeck, Task
from main import app


async def _setup_app(tmp_path):
    settings.MEMORY_DIR = tmp_path  # isolate seed_research writes
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with Session() as s:
            yield s

    app.dependency_overrides[get_db] = _override
    return Session, engine


async def _teardown(engine):
    app.dependency_overrides.clear()
    await engine.dispose()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    )


@pytest.fixture(autouse=True)
def _stub_celery(monkeypatch):
    """No-op the Celery enqueue so import_json tests don't hit a broker."""
    class _StubTask:
        def delay(self, *args, **kwargs):
            return None

    import workers.tasks as wt

    monkeypatch.setattr(wt, "run_generation_task", _StubTask())


# ── direct slides path ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_json_direct_slides_persists_done_task(tmp_path):
    Session, engine = await _setup_app(tmp_path)
    try:
        payload = {
            "topic": "Quarterly Review",
            "theme": "Editorial",
            "slides": [
                {
                    "layout": "title",
                    "title": "Quarterly Review",
                    "eyebrow": "FY26",
                    "subtitle": "FY26 Q1",
                },
                {
                    "layout": "bullets",
                    "title": "Highlights",
                    "bullets": ["Revenue up 38%", "ARR crossed $42M"],
                },
            ],
        }
        async with _client() as c:
            r = await c.post("/api/import/json", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["mode"] == "direct"
        assert body["status"] == "done"
        assert body["slide_count"] == 2

        async with Session() as s:
            task = (
                await s.execute(select(Task).where(Task.id == body["task_id"]))
            ).scalar_one()
            deck = (
                await s.execute(
                    select(SlideDeck).where(SlideDeck.task_id == body["task_id"])
                )
            ).scalar_one()
            assert task.status == "done"
            assert task.progress_pct == 100.0
            assert task.search_web is False
            assert deck.slide_count == 2
    finally:
        await _teardown(engine)


@pytest.mark.asyncio
async def test_import_json_direct_invalid_slides_400(tmp_path):
    Session, engine = await _setup_app(tmp_path)
    try:
        payload = {
            "topic": "broken deck",
            "slides": [{"layout": "totally-not-a-layout", "title": "x"}],
        }
        async with _client() as c:
            r = await c.post("/api/import/json", json=payload)
        assert r.status_code == 400
        body = r.json()
        assert body["detail"]["error"] == "invalid_deck"
    finally:
        await _teardown(engine)


# ── seed-research generate path ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_json_seed_data_enqueues_pending_task(tmp_path):
    Session, engine = await _setup_app(tmp_path)
    try:
        payload = {
            "topic": "Acme Corp deep dive",
            "slide_count": 6,
            "data": {
                "company": "Acme Corp",
                "revenue_2025": "$42M",
                "growth_yoy": "38%",
                "key_people": ["Jane Doe (CEO)", "Bob Smith (CTO)"],
            },
        }
        async with _client() as c:
            r = await c.post("/api/import/json", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["mode"] == "generate"
        assert body["status"] == "pending"
        task_id = body["task_id"]

        async with Session() as s:
            task = (
                await s.execute(select(Task).where(Task.id == task_id))
            ).scalar_one()
            assert task.status == "pending"
            assert task.search_web is False
            assert task.slide_count == 6

        # Seed file should land in the per-task memory dir.
        seed_json = tmp_path / task_id / "seed_research.json"
        seed_txt = tmp_path / task_id / "seed_research.txt"
        assert seed_json.exists()
        assert seed_txt.exists()
        assert "Acme Corp" in seed_txt.read_text(encoding="utf-8")
    finally:
        await _teardown(engine)


@pytest.mark.asyncio
async def test_import_json_missing_payload_400(tmp_path):
    Session, engine = await _setup_app(tmp_path)
    try:
        async with _client() as c:
            r = await c.post(
                "/api/import/json",
                json={"topic": "no payload here"},
            )
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "missing_payload"
    finally:
        await _teardown(engine)


@pytest.mark.asyncio
async def test_import_json_short_topic_422(tmp_path):
    Session, engine = await _setup_app(tmp_path)
    try:
        async with _client() as c:
            r = await c.post(
                "/api/import/json",
                json={"topic": "ab", "data": {"x": 1}},
            )
        # Pydantic min_length=4 rejects with 422 before the route runs.
        assert r.status_code == 422
    finally:
        await _teardown(engine)


@pytest.mark.asyncio
async def test_import_json_string_data_serializes_verbatim(tmp_path):
    Session, engine = await _setup_app(tmp_path)
    try:
        payload = {
            "topic": "raw notes import",
            "data": "Plain text notes\nLine two with a number 42.",
        }
        async with _client() as c:
            r = await c.post("/api/import/json", json=payload)
        assert r.status_code == 200, r.text
        task_id = r.json()["task_id"]
        seed_txt = (tmp_path / task_id / "seed_research.txt").read_text(encoding="utf-8")
        assert "Plain text notes" in seed_txt
        assert "Line two with a number 42." in seed_txt
    finally:
        await _teardown(engine)
