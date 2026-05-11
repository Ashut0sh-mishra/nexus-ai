"""Phase 6N — tests for ``GET /api/slides/{task_id}/citations``.

Asserts the new read-only endpoint:

* Returns the canonical ``map_deck_citations`` shape (with ``task_id``
  added).
* Returns a useful empty-but-shaped report for a deck that has no
  sources.
* Marks unsupported / weak claims when sources are present but the
  claim does not match — these must not be hidden from the UI.
* Returns 404 for unknown tasks and 409 for non-done tasks.
* Degrades to an empty report (not 404) when the ``SlideDeck`` row is
  missing for a done task.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.connection import get_db
from database.models import Base, SlideDeck, Task
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


def _seed_done_task(Session, *, task_id: str, slides: list[dict]):
    async def _go():
        async with Session() as s:
            s.add(
                Task(
                    id=task_id,
                    topic="topic",
                    slide_count=len(slides),
                    theme="Editorial",
                    status="done",
                )
            )
            s.add(
                SlideDeck(
                    task_id=task_id,
                    slide_data=slides,
                    theme="Editorial",
                    slide_count=len(slides),
                )
            )
            await s.commit()

    return _go()


# ── 1. Empty / no-sources deck still returns a useful shape ───────────────


def test_citations_empty_when_deck_has_no_sources():
    async def _go():
        Session, engine = await _setup_app()
        try:
            slides = [
                {
                    "id": "s0",
                    "layout": "title",
                    "title": "An overview",
                    "subtitle": "",
                    "eyebrow": "",
                },
                {
                    "id": "s1",
                    "layout": "bullets",
                    "title": "Three points",
                    "bullets": ["one", "two", "three"],
                },
            ]
            await _seed_done_task(Session, task_id="t-empty", slides=slides)
            async with _client() as c:
                r = await c.get("/api/slides/t-empty/citations")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["task_id"] == "t-empty"
            assert body["schema_version"]
            assert "claims" in body and isinstance(body["claims"], list)
            assert "summary" in body
            # No sources ⇒ everything that does count as a claim is
            # surfaced as unsupported. Whether claims are extracted at
            # all depends on the corpus; the contract is just that the
            # summary is internally consistent.
            s = body["summary"]
            assert s["total_claims"] == s["supported"] + s["unsupported"]
            assert s["supported"] == 0  # no sources can support anything
            assert 0.0 <= s["support_rate"] <= 1.0
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# ── 2. Supported and unsupported claims both surface ──────────────────────


def test_citations_marks_supported_and_unsupported_claims():
    async def _go():
        Session, engine = await _setup_app()
        try:
            # One stat that matches a source; one stat that does not.
            slides = [
                {
                    "id": "s0",
                    "layout": "stats",
                    "title": "Adoption",
                    "stats": [
                        {"value": "42%", "label": "of teams use the tool"},
                        {"value": "9001", "label": "is over nine thousand"},
                    ],
                    "sources": [
                        {
                            "title": "Industry survey 2025",
                            "url": "https://example.com/survey",
                            "snippet": "42% of teams reported using the tool weekly.",
                        }
                    ],
                }
            ]
            await _seed_done_task(Session, task_id="t-mix", slides=slides)
            async with _client() as c:
                r = await c.get("/api/slides/t-mix/citations")
            assert r.status_code == 200, r.text
            body = r.json()
            claims = body["claims"]
            assert len(claims) >= 2

            supported = [c for c in claims if c["supported"]]
            unsupported = [c for c in claims if not c["supported"]]
            assert supported, "expected at least one supported claim"
            assert unsupported, "expected unsupported claims to be visible"

            # The supported claim should expose source title/url.
            top = supported[0]
            assert top["source_url"] == "https://example.com/survey"
            assert top["source_title"] == "Industry survey 2025"
            assert top["basis"] in {"exact_phrase", "numeric_match", "keyword_overlap"}
            assert isinstance(top["score"], float)

            # The unsupported claim must keep ``basis="no_match"``.
            for u in unsupported:
                assert u["basis"] == "no_match"
                assert u["source_url"] is None
                assert u["source_title"] is None

            # Summary counters reflect the mix.
            s = body["summary"]
            assert s["total_claims"] == len(claims)
            assert s["supported"] == len(supported)
            assert s["unsupported"] == len(unsupported)
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# ── 3. Per-slide grouping is possible via slide_index ─────────────────────


def test_citations_include_slide_index_for_grouping():
    async def _go():
        Session, engine = await _setup_app()
        try:
            slides = [
                {
                    "id": "s0",
                    "layout": "bullets",
                    "title": "First",
                    "bullets": [
                        "Revenue grew 42% year over year in 2024.",
                    ],
                    "sources": [
                        {
                            "title": "Annual report",
                            "url": "https://example.com/annual",
                            "snippet": "Revenue grew 42% year over year in 2024.",
                        }
                    ],
                },
                {
                    "id": "s1",
                    "layout": "bullets",
                    "title": "Second",
                    "bullets": ["A totally unrelated point about cats."],
                },
            ]
            await _seed_done_task(Session, task_id="t-grp", slides=slides)
            async with _client() as c:
                r = await c.get("/api/slides/t-grp/citations")
            assert r.status_code == 200, r.text
            claims = r.json()["claims"]
            indices = {c["slide_index"] for c in claims}
            # Both slides should produce at least one claim each.
            assert 0 in indices
            assert 1 in indices
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


# ── 4. Error surfaces ─────────────────────────────────────────────────────


def test_citations_404_for_unknown_task():
    async def _go():
        _, engine = await _setup_app()
        try:
            async with _client() as c:
                r = await c.get("/api/slides/does-not-exist/citations")
            assert r.status_code == 404
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_citations_409_when_task_not_done():
    async def _go():
        Session, engine = await _setup_app()
        try:
            async with Session() as s:
                s.add(
                    Task(
                        id="t-pending",
                        topic="x",
                        slide_count=0,
                        theme="Editorial",
                        status="pending",
                    )
                )
                await s.commit()
            async with _client() as c:
                r = await c.get("/api/slides/t-pending/citations")
            assert r.status_code == 409
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())


def test_citations_empty_report_when_done_task_has_no_deck_row():
    async def _go():
        Session, engine = await _setup_app()
        try:
            async with Session() as s:
                # Task done but SlideDeck never persisted.
                s.add(
                    Task(
                        id="t-no-deck",
                        topic="x",
                        slide_count=0,
                        theme="Editorial",
                        status="done",
                    )
                )
                await s.commit()
            async with _client() as c:
                r = await c.get("/api/slides/t-no-deck/citations")
            assert r.status_code == 200
            body = r.json()
            assert body["task_id"] == "t-no-deck"
            assert body["claims"] == []
            assert body["summary"]["total_claims"] == 0
        finally:
            await _teardown_app(engine)

    asyncio.run(_go())
