"""Phase 6R — structured run-event emitter tests.

These tests are Redis-free: they record every emitted payload into an in-memory
list via the ``publish_raw`` hook so we can assert event shape and order
without booting a worker. Terminal behaviour for cancelled / failed / done
is asserted explicitly because Phase 6Q closes the SSE stream on those
statuses and the canonical event names must round-trip cleanly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from services.run_events import EVENT_TYPES, RunEventEmitter

REQUIRED_FIELDS = {
    "task_id",
    "event",
    "stage",
    "message",
    "progress_pct",
    "timestamp",
    "sequence",
}


def _record():
    out: list[dict[str, Any]] = []

    async def publish_raw(payload: dict[str, Any]) -> None:
        out.append(payload)

    return out, publish_raw


def _assert_shape(payload: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - payload.keys()
    assert not missing, f"missing required fields: {missing}"
    assert payload["event"] in EVENT_TYPES, payload["event"]
    assert isinstance(payload["sequence"], int) and payload["sequence"] >= 1
    # timestamp must be parseable ISO-8601
    ts = payload["timestamp"].replace("Z", "+00:00")
    datetime.fromisoformat(ts)
    assert isinstance(payload["progress_pct"], float)


@pytest.mark.asyncio
async def test_emitter_assigns_required_fields_and_monotonic_sequence():
    out, publish_raw = _record()
    em = RunEventEmitter("t1", publish_raw)

    await em.on_progress("Analyzing", 8.0, "analyze")
    await em.on_progress("Researching", 18.0, "search")
    await em.on_progress("Planning", 28.0, "plan")

    assert len(out) >= 3
    for p in out:
        _assert_shape(p)
        assert p["task_id"] == "t1"

    seqs = [p["sequence"] for p in out]
    assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))


@pytest.mark.asyncio
async def test_stage_transition_synthesises_stage_completed():
    out, publish_raw = _record()
    em = RunEventEmitter("t2", publish_raw)

    await em.on_progress("Analyzing", 8.0, "analyze")
    await em.on_progress("Researching", 18.0, "search")

    events = [p["event"] for p in out]
    # First call: stage_started for analyze.
    assert events[0] == "stage_started"
    assert out[0]["stage"] == "analyze"
    # Transition synthesises stage_completed for analyze, then stage_started for search.
    assert "stage_completed" in events
    completed = next(p for p in out if p["event"] == "stage_completed")
    assert completed["stage"] == "analyze"
    last = out[-1]
    assert last["event"] == "stage_started"
    assert last["stage"] == "search"


@pytest.mark.asyncio
async def test_slide_event_maps_to_slide_ready_and_carries_slide_index():
    out, publish_raw = _record()
    em = RunEventEmitter("t3", publish_raw)

    await em.on_progress("Writing slide 1", 35.0, "generate")
    await em.on_progress(
        "Wrote slide 1",
        45.0,
        "generate",
        event="slide",
        slide_index=0,
        slide_total=8,
        slide={"layout": "title", "title": "Hello"},
    )

    slide_evts = [p for p in out if p["event"] == "slide_ready"]
    assert len(slide_evts) == 1
    p = slide_evts[0]
    _assert_shape(p)
    assert p["slide_index"] == 0
    assert p["slide_total"] == 8
    assert p["slide"]["title"] == "Hello"
    assert p["stage"] == "generate"


@pytest.mark.asyncio
async def test_terminal_done_emits_run_succeeded_and_closes_stage():
    out, publish_raw = _record()
    em = RunEventEmitter("t4", publish_raw)

    await em.on_progress("Saving", 96.0, "save")
    await em.on_progress("Done!", 100.0, "done", status="done")

    events = [p["event"] for p in out]
    assert events[-1] == "run_succeeded"
    # Best-effort stage_completed for ``save`` is synthesised before terminal.
    assert "stage_completed" in events
    sc = [p for p in out if p["event"] == "stage_completed"]
    assert sc[-1]["stage"] == "save"
    assert out[-1]["status"] == "done"


@pytest.mark.asyncio
async def test_terminal_failed_emits_run_failed_with_error():
    out, publish_raw = _record()
    em = RunEventEmitter("t5", publish_raw)

    await em.on_progress("Generating", 50.0, "generate")
    await em.on_progress(
        "Generation failed: boom",
        100.0,
        "failed",
        status="failed",
        error="boom",
    )

    assert out[-1]["event"] == "run_failed"
    assert out[-1]["status"] == "failed"
    assert out[-1]["error"] == "boom"


@pytest.mark.asyncio
async def test_terminal_cancelled_emits_run_cancelled():
    out, publish_raw = _record()
    em = RunEventEmitter("t6", publish_raw)

    await em.on_progress("Analyzing", 8.0, "analyze")
    await em.on_progress(
        "Generation cancelled by user.",
        100.0,
        "cancelled",
        status="cancelled",
    )

    assert out[-1]["event"] == "run_cancelled"
    assert out[-1]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_event_order_preserves_emission_order():
    out, publish_raw = _record()
    em = RunEventEmitter("t7", publish_raw)

    await em.on_progress("a", 1.0, "analyze")
    await em.on_progress("p", 2.0, "plan")
    await em.on_progress("g", 3.0, "generate")
    await em.on_progress(
        "slide",
        4.0,
        "generate",
        event="slide",
        slide_index=0,
        slide={"layout": "title"},
    )
    await em.on_progress("done", 100.0, "done", status="done")

    seqs = [p["sequence"] for p in out]
    assert seqs == sorted(seqs)
    # Order: analyze-start, analyze-complete, plan-start, plan-complete,
    #        generate-start, slide_ready, generate-complete, run_succeeded.
    types = [p["event"] for p in out]
    assert types[0] == "stage_started"
    assert types[-1] == "run_succeeded"
    # slide_ready must come before run_succeeded
    assert types.index("slide_ready") < types.index("run_succeeded")


@pytest.mark.asyncio
async def test_back_compat_step_and_status_aliases_present():
    """Existing Phase 6Q SSE consumers read ``step`` and ``status``;
    Phase 6R must keep both alongside the new ``stage`` and ``event``."""
    out, publish_raw = _record()
    em = RunEventEmitter("t8", publish_raw)

    await em.on_progress("Analyzing", 8.0, "analyze")
    p = out[0]
    assert p["step"] == p["stage"] == "analyze"
    assert p["status"] == "running"


@pytest.mark.asyncio
async def test_idempotent_terminal_does_not_resynthesise_stage_completed():
    out, publish_raw = _record()
    em = RunEventEmitter("t9", publish_raw)

    await em.on_progress("save", 96.0, "save")
    await em.on_progress("done", 100.0, "done", status="done")
    # If somehow another terminal frame arrives we should not synthesise a
    # second stage_completed for ``save``.
    await em.on_progress("done again", 100.0, "done", status="done")

    sc = [p for p in out if p["event"] == "stage_completed" and p["stage"] == "save"]
    assert len(sc) == 1


@pytest.mark.asyncio
async def test_explicit_source_found_and_citation_checked_round_trip():
    out, publish_raw = _record()
    em = RunEventEmitter("t10", publish_raw)

    await em.on_progress(
        "Found source: example.com",
        18.5,
        "search",
        event="source_found",
    )
    await em.on_progress(
        "Citation checked for slide 2",
        93.0,
        "critique",
        event="citation_checked",
        slide_index=1,
    )

    types = [p["event"] for p in out]
    assert "source_found" in types
    assert "citation_checked" in types
    cc = next(p for p in out if p["event"] == "citation_checked")
    assert cc["slide_index"] == 1
