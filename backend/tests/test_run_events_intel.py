"""Phase 6X / 6Y — visible-cognition + design-decision SSE event coverage.

These tests are Redis-free: they record every emitted payload via the
``publish_raw`` hook so we can assert event-type round-tripping and
extra-field passthrough without booting a worker.

Covers:
* ``research_note``      (Phase 6X) — research snippet emitted to UI Intel Panel.
* ``outline_ready``      (Phase 6X) — slide-plan list passed through.
* ``source_found``       (Phase 6X) — per-source URL events with ``url`` extra.
* ``design_decision``    (Phase 6Y / 6AB / 6AD) — design rationale events with
                          arbitrary ``decision`` / ``value`` / ``rationale`` fields.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.run_events import (  # noqa: E402
    EVENT_TYPES,
    RunEventEmitter,
    _EXPLICIT_EVENT_MAP,
)


def _record():
    out: list[dict[str, Any]] = []

    async def publish_raw(payload: dict[str, Any]) -> None:
        out.append(payload)

    return out, publish_raw


# ── Phase 6X: new event types are registered in the canonical vocabulary ───


def test_phase_6x_event_types_registered() -> None:
    """``research_note`` and ``outline_ready`` must be canonical event types."""
    assert "research_note" in EVENT_TYPES
    assert "outline_ready" in EVENT_TYPES
    assert "source_found" in EVENT_TYPES
    # Phase 6Y addition.
    assert "design_decision" in EVENT_TYPES


def test_phase_6x_explicit_event_map_routes_intel_events() -> None:
    """The legacy ``event=`` kwarg in extra must round-trip cleanly."""
    assert _EXPLICIT_EVENT_MAP["research_note"] == "research_note"
    assert _EXPLICIT_EVENT_MAP["outline_ready"] == "outline_ready"
    assert _EXPLICIT_EVENT_MAP["source_found"] == "source_found"
    assert _EXPLICIT_EVENT_MAP["design_decision"] == "design_decision"


# ── Phase 6X: research_note payload survives through the emitter ───────────


@pytest.mark.asyncio
async def test_research_note_round_trips_with_message_body() -> None:
    out, publish_raw = _record()
    em = RunEventEmitter("t-research", publish_raw)

    research_blob = "Long-form research text describing the topic." * 5
    await em.on_progress(
        research_blob,
        23.5,
        "search",
        event="research_note",
    )

    notes = [p for p in out if p["event"] == "research_note"]
    assert len(notes) == 1
    note = notes[0]
    assert note["message"] == research_blob
    assert note["task_id"] == "t-research"
    assert note["stage"] == "search"
    assert isinstance(note["sequence"], int) and note["sequence"] >= 1


# ── Phase 6X: outline_ready carries the slide-plan list as ``outline`` ─────


@pytest.mark.asyncio
async def test_outline_ready_carries_outline_list() -> None:
    out, publish_raw = _record()
    em = RunEventEmitter("t-outline", publish_raw)

    outline_payload = [
        {"i": 1, "layout": "title", "title": "Cover"},
        {"i": 2, "layout": "bullets", "title": "Context"},
        {"i": 3, "layout": "stats", "title": "Numbers"},
    ]
    await em.on_progress(
        "Slide structure planned",
        29.0,
        "plan",
        event="outline_ready",
        outline=outline_payload,
    )

    outline_events = [p for p in out if p["event"] == "outline_ready"]
    assert len(outline_events) == 1
    evt = outline_events[0]
    assert evt["outline"] == outline_payload
    assert evt["stage"] == "plan"


# ── Phase 6X: source_found per-URL events with ``url`` field ───────────────


@pytest.mark.asyncio
async def test_source_found_carries_url_field() -> None:
    out, publish_raw = _record()
    em = RunEventEmitter("t-src", publish_raw)

    await em.on_progress(
        "Britannica article",
        19.0,
        "search",
        event="source_found",
        url="https://example.com/article",
    )

    src_events = [p for p in out if p["event"] == "source_found"]
    assert len(src_events) == 1
    evt = src_events[0]
    assert evt["url"] == "https://example.com/article"
    assert evt["message"] == "Britannica article"


@pytest.mark.asyncio
async def test_multiple_source_found_events_get_distinct_sequences() -> None:
    out, publish_raw = _record()
    em = RunEventEmitter("t-multi-src", publish_raw)

    for i in range(5):
        await em.on_progress(
            f"Source {i}",
            19.0,
            "search",
            event="source_found",
            url=f"https://example.com/{i}",
        )

    src_events = [p for p in out if p["event"] == "source_found"]
    assert len(src_events) == 5
    sequences = [p["sequence"] for p in src_events]
    assert sequences == sorted(sequences) and len(sequences) == len(set(sequences))


# ── Phase 6Y: design_decision carries arbitrary decision / value / rationale ─


@pytest.mark.asyncio
async def test_design_decision_round_trip_with_all_fields() -> None:
    out, publish_raw = _record()
    em = RunEventEmitter("t-design", publish_raw)

    await em.on_progress(
        "Deck type: research_report",
        24.5,
        "strategy",
        event="design_decision",
        decision="deck_type",
        value="research_report",
        rationale="Topic mentions market analysis.",
    )

    events = [p for p in out if p["event"] == "design_decision"]
    assert len(events) == 1
    evt = events[0]
    assert evt["decision"] == "deck_type"
    assert evt["value"] == "research_report"
    assert evt["rationale"] == "Topic mentions market analysis."
    assert evt["stage"] == "strategy"


@pytest.mark.asyncio
async def test_design_decision_passes_complex_values_through() -> None:
    """Phase 6AD beat sequences and rhythm arrays must pass through unmodified."""
    out, publish_raw = _record()
    em = RunEventEmitter("t-complex", publish_raw)

    beats = ["setup", "escalation", "turning_point", "consequence", "aftermath"]
    rhythm = [
        {"i": 1, "role": "opening", "density": "low"},
        {"i": 2, "role": "evidence", "density": "high"},
    ]

    await em.on_progress(
        "Narrative beats",
        25.3,
        "strategy",
        event="design_decision",
        decision="narrative_beats",
        value=beats,
    )
    await em.on_progress(
        "Pacing",
        91.0,
        "assemble",
        event="design_decision",
        decision="intent_rhythm",
        value=rhythm,
    )

    events = [p for p in out if p["event"] == "design_decision"]
    assert len(events) == 2
    assert events[0]["value"] == beats
    assert events[1]["value"] == rhythm


# ── Backward compatibility: unknown ``event=`` strings do not crash ────────


@pytest.mark.asyncio
async def test_unknown_event_passes_through_without_crashing() -> None:
    """An unknown ``event=`` string must not raise — the emitter is
    forward-compatible with event types added in future phases. The
    payload is emitted so the frontend can render a generic row rather
    than hide the event."""
    out, publish_raw = _record()
    em = RunEventEmitter("t-unknown", publish_raw)

    # Must not raise. The emitter passes unknown event types through
    # unchanged so the frontend keeps the stream running while a future
    # phase adds proper handling.
    await em.on_progress(
        "Unknown",
        50.0,
        "generate",
        event="not_a_real_event",
    )

    assert len(out) >= 1
    last = out[-1]
    # Required envelope fields are still populated.
    for key in ("task_id", "event", "stage", "message", "progress_pct", "sequence", "timestamp"):
        assert key in last, f"missing envelope field: {key}"
