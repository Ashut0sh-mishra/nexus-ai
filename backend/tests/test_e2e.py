"""End-to-end integration tests for the NEXUS backend.

Exercises:
- /api/health
- OpenAPI schema quality
- POST /api/generate -> task created (Celery stubbed)
- Direct seeding of `deck_slides` to simulate the worker output
- Slide CRUD: GET deck, GET slide, PUT, POST reorder, DELETE
- POST /api/share + GET /api/share/{token}
"""

from __future__ import annotations

import pytest

from database.models import Slide, SlideDeck, Task


# ---------------------------------------------------------------------------
# Health + OpenAPI
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert "provider" in body and "model" in body


@pytest.mark.asyncio
async def test_openapi_schema_quality(client):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()

    assert spec["info"]["title"].endswith("API")
    tag_names = {t["name"] for t in spec.get("tags", [])}
    for required in {"generate", "slides", "status", "export", "share", "upload", "auth"}:
        assert required in tag_names, f"missing tag: {required}"

    expected = [
        ("/api/generate", "post"),
        ("/api/slides/{task_id}", "get"),
        ("/api/slides/{task_id}/{slide_id}", "put"),
        ("/api/slides/{task_id}/{slide_id}", "delete"),
        ("/api/slides/{task_id}/reorder", "post"),
        ("/api/status/{task_id}", "get"),
    ]
    for path, method in expected:
        op = spec["paths"][path][method]
        assert op.get("summary"), f"{method.upper()} {path} missing summary"


# ---------------------------------------------------------------------------
# /api/generate
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_creates_pending_task(client):
    payload = {
        "topic": "The future of clean energy in India",
        "slide_count": 6,
        "theme": "auto",
        "search_web": False,
        "audience": "executives",
        "tone": "confident",
        "industry": "energy",
    }
    r = await client.post("/api/generate", json=payload)
    assert r.status_code == 202, r.text
    body = r.json()
    assert "task_id" in body
    assert body["status"] in ("pending", "queued")


@pytest.mark.asyncio
async def test_generate_validation(client):
    # `topic` < 4 chars must fail.
    r = await client.post("/api/generate", json={"topic": "no"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Slide CRUD lifecycle
# ---------------------------------------------------------------------------
async def _seed_completed_deck(db_session, *, n: int = 3) -> tuple[str, list[str]]:
    """Insert a Task + SlideDeck + N Slide rows, return (task_id, slide_ids)."""
    task = Task(
        topic="Seeded test deck",
        slide_count=n,
        theme="Editorial",
        status="done",
        progress_pct=100.0,
        current_step="done",
    )
    db_session.add(task)
    await db_session.flush()

    slides_blob = []
    slide_ids: list[str] = []
    for i in range(1, n + 1):
        s = Slide(
            task_id=task.id,
            slide_number=i,
            slide_type="bullets",
            title=f"Slide {i}",
            subtitle=f"Subtitle {i}",
            content_json={"bullets": [f"Point {i}.1", f"Point {i}.2"]},
        )
        db_session.add(s)
        await db_session.flush()
        slide_ids.append(s.id)
        slides_blob.append(
            {
                "id": s.id,
                "slide_number": i,
                "layout": "bullets",
                "title": s.title,
                "subtitle": s.subtitle,
                "bullets": [f"Point {i}.1", f"Point {i}.2"],
            }
        )

    deck = SlideDeck(
        task_id=task.id,
        slide_data=slides_blob,
        theme="Editorial",
        slide_count=n,
    )
    db_session.add(deck)
    await db_session.commit()
    return task.id, slide_ids


@pytest.mark.asyncio
async def test_slide_lifecycle(client, db_session):
    task_id, slide_ids = await _seed_completed_deck(db_session, n=3)

    # 1. GET /slides/{task_id}
    r = await client.get(f"/api/slides/{task_id}")
    assert r.status_code == 200, r.text
    deck = r.json()
    assert deck["slide_count"] == 3
    assert [s["title"] for s in deck["slides"]] == ["Slide 1", "Slide 2", "Slide 3"]

    # 2. GET single slide
    r = await client.get(f"/api/slides/{task_id}/{slide_ids[0]}")
    assert r.status_code == 200
    assert r.json()["title"] == "Slide 1"

    # 3. PUT update
    r = await client.put(
        f"/api/slides/{task_id}/{slide_ids[0]}",
        json={"title": "Updated Slide 1", "speaker_notes": "Speak slowly"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Updated Slide 1"
    assert body["speaker_notes"] == "Speak slowly"

    # 4. POST reorder (reverse the deck)
    new_order = list(reversed(slide_ids))
    r = await client.post(
        f"/api/slides/{task_id}/reorder",
        json={"slide_ids": new_order},
    )
    assert r.status_code == 200, r.text
    reordered = r.json()["slides"]
    # First slide should now be the original Slide 3.
    assert reordered[0]["title"] == "Slide 3"
    # Updated title should now be at the end.
    assert reordered[-1]["title"] == "Updated Slide 1"

    # 5. DELETE last slide -> deck has 2 left.
    r = await client.delete(f"/api/slides/{task_id}/{slide_ids[0]}")
    assert r.status_code == 200, r.text
    after_delete = r.json()
    assert after_delete["slide_count"] == 2
    # Slide numbers must be 1..N after renumber.
    nums = [s["slide_number"] for s in after_delete["slides"]]
    assert nums == [1, 2]


@pytest.mark.asyncio
async def test_slide_404(client):
    r = await client.get("/api/slides/does-not-exist")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Share
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_share_create_and_view(client, db_session):
    task_id, _ = await _seed_completed_deck(db_session, n=2)

    r = await client.post("/api/share", json={"task_id": task_id, "ttl_days": 7})
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    assert token

    r = await client.get(f"/api/share/{token}")
    assert r.status_code == 200
    body = r.json()
    # The view payload must include a slide list of some shape.
    assert "task_id" in body or "slides" in body or "deck" in body


@pytest.mark.asyncio
async def test_share_for_unfinished_task_409(client, db_session):
    task = Task(
        topic="Still cooking",
        status="running",
        progress_pct=42.0,
        current_step="searching",
    )
    db_session.add(task)
    await db_session.commit()

    r = await client.post("/api/share", json={"task_id": task.id})
    assert r.status_code == 409
