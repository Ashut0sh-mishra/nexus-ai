"""Phase 6M — integration tests for topic-aware art direction in /api/generate.

The route should:

* When ``theme`` is the auto sentinel (``""`` or ``"auto"``), persist
  ``Task.theme`` as the inferred legacy display name (e.g. ``Dossier``
  for war / conflict topics).
* When ``theme`` is any explicit value, persist it verbatim with no
  inference. ``"Editorial"`` is intentionally treated as explicit so the
  pre-6M response-shape contract (covered by
  ``test_runtime_generate_route``) remains green.

Celery dispatch is monkeypatched to a no-op so these tests stay offline.
"""

from __future__ import annotations

from typing import AsyncIterator

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from database.connection import get_db
from database.models import Base, Task
from main import app


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://t")


async def _setup_app():
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
    import workers.tasks as wt

    class _NoopAsyncResult:
        id = "noop-task"

    def _noop_delay(*_args, **_kwargs):
        return _NoopAsyncResult()

    monkeypatch.setattr(wt.run_generation_task, "delay", _noop_delay, raising=True)


def test_war_topic_with_auto_theme_persists_dossier(monkeypatch):
    monkeypatch.setattr(settings, "NEXUS_RUNTIME_DRIVES_GENERATE", False, raising=True)
    _patch_celery_noop(monkeypatch)

    import asyncio

    async def _go():
        Session, engine = await _setup_app()
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/generate",
                    json={
                        "topic": "Geopolitical analysis of the Russia–Ukraine war",
                        "slide_count": 8,
                        "theme": "auto",
                        "search_web": False,
                    },
                )
            assert r.status_code == 202, r.text
            body = r.json()
            # Pre-6I response contract is preserved.
            assert set(body.keys()) == {"task_id", "status"}, body

            async with Session() as s:
                tasks = (await s.execute(select(Task))).scalars().all()
                assert len(tasks) == 1
                assert tasks[0].theme == "Dossier"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_blank_theme_with_business_topic_persists_light_pro(monkeypatch):
    monkeypatch.setattr(settings, "NEXUS_RUNTIME_DRIVES_GENERATE", False, raising=True)
    _patch_celery_noop(monkeypatch)

    import asyncio

    async def _go():
        Session, engine = await _setup_app()
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/generate",
                    json={
                        "topic": "Series A pitch deck for our B2B SaaS startup",
                        "slide_count": 8,
                        "theme": "",
                        "search_web": False,
                    },
                )
            assert r.status_code == 202, r.text
            async with Session() as s:
                tasks = (await s.execute(select(Task))).scalars().all()
                assert len(tasks) == 1
                assert tasks[0].theme == "light-pro"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_explicit_theme_is_respected_even_for_war_topic(monkeypatch):
    monkeypatch.setattr(settings, "NEXUS_RUNTIME_DRIVES_GENERATE", False, raising=True)
    _patch_celery_noop(monkeypatch)

    import asyncio

    async def _go():
        Session, engine = await _setup_app()
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/generate",
                    json={
                        "topic": "Modern military drone warfare",
                        "slide_count": 8,
                        "theme": "Pixel",
                        "search_web": False,
                    },
                )
            assert r.status_code == 202, r.text
            async with Session() as s:
                tasks = (await s.execute(select(Task))).scalars().all()
                assert len(tasks) == 1
                assert tasks[0].theme == "Pixel"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_editorial_default_remains_editorial_no_inference(monkeypatch):
    """Pre-6M clients sent ``theme="Editorial"`` to mean "API default".
    We treat this as explicit so the existing response-shape contract
    in ``test_runtime_generate_route`` keeps passing."""
    monkeypatch.setattr(settings, "NEXUS_RUNTIME_DRIVES_GENERATE", False, raising=True)
    _patch_celery_noop(monkeypatch)

    import asyncio

    async def _go():
        Session, engine = await _setup_app()
        try:
            async with _client() as c:
                r = await c.post(
                    "/api/generate",
                    json={
                        "topic": "The Russia–Ukraine war and its global impact",
                        "slide_count": 8,
                        "theme": "Editorial",
                        "search_web": False,
                    },
                )
            assert r.status_code == 202, r.text
            async with Session() as s:
                tasks = (await s.execute(select(Task))).scalars().all()
                assert len(tasks) == 1
                # Explicit Editorial is respected; no inference override.
                assert tasks[0].theme == "Editorial"
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())
