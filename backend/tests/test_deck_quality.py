"""Phase 1C — DeckQualityReport + RepairAction telemetry tests.

These tests intentionally do NOT use ``backend/tests/conftest.py`` (which
is currently blocked by a SQLite NullPool / pool_size mismatch in
``database.connection``). They run cleanly under::

    python -m pytest --noconftest -p no:cacheprovider \\
        tests/test_deck_quality.py -v

They use the same direct sys.path insert pattern as
``tests/test_layout_coverage.py`` so importing ``agent.loop`` does not
require a conftest.
"""

from __future__ import annotations

import copy
import logging
import sys
from pathlib import Path

import pytest

# Ensure ``backend/`` is on sys.path so the ``agent`` package resolves.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.deck_quality import (  # noqa: E402
    DeckQualityReport,
    RepairAction,
    build_deck_quality_report,
)


# ── Fixture decks ──────────────────────────────────────────────────────────


VALID_DECK: list[dict] = [
    {
        "id": "slide-000",
        "layout": "title",
        "title": "Renewable Energy",
        "subtitle": "A 2026 Outlook",
        "eyebrow": "Presentation",
    },
    {
        "id": "slide-001",
        "layout": "bullets",
        "title": "Drivers",
        "bullets": ["Solar costs", "Battery", "Policy"],
    },
    {
        "id": "slide-002",
        "layout": "chart",
        "title": "Capacity",
        "chart_type": "bar",
        "chart_data": {
            "labels": ["2022", "2023"],
            "values": [100.0, 145.0],
            "unit": "GW",
            "source": "IRENA",
        },
        "subtitle": "Solar capacity",
    },
    {
        "id": "slide-003",
        "layout": "closing",
        "title": "Thanks",
        "subtitle": "",
        "cta": "Q&A",
    },
]


def _chart_missing_subtitle_deck() -> list[dict]:
    deck = copy.deepcopy(VALID_DECK)
    # Slide index 2 is the chart; drop the slide-level subtitle to make
    # it violate the tightened Phase 1B.1 contract.
    del deck[2]["subtitle"]
    return deck


# ── 1. Valid deck → ok=True, no errors, no repair actions ──────────────────


def test_build_report_returns_ok_for_valid_deck():
    report = build_deck_quality_report(VALID_DECK)
    assert isinstance(report, DeckQualityReport)
    assert report.ok is True
    assert report.slide_count == len(VALID_DECK)
    assert report.valid_count == len(VALID_DECK)
    assert report.invalid_count == 0
    assert report.errors == []
    assert report.repair_actions == []


# ── 2. Invalid deck (chart missing subtitle) → structured surface ──────────


def test_build_report_flags_invalid_chart_missing_subtitle():
    deck = _chart_missing_subtitle_deck()
    report = build_deck_quality_report(deck)
    assert report.ok is False
    assert report.slide_count == len(deck)
    assert report.invalid_count >= 1
    assert report.valid_count == report.slide_count - report.invalid_count

    # At least one structured error record must point at chart slide #2.
    matches = [
        e
        for e in report.errors
        if e["slide_index"] == 2
        and e["layout"] == "chart"
        and e["path"] == "subtitle"
        and e["code"] == "missing"
    ]
    assert matches, report.errors
    assert isinstance(matches[0]["message"], str) and matches[0]["message"]


def test_build_report_emits_repair_actions_marked_not_applied():
    deck = _chart_missing_subtitle_deck()
    report = build_deck_quality_report(deck)

    repairs = [
        r
        for r in report.repair_actions
        if r.slide_index == 2 and r.path == "subtitle" and r.code == "missing"
    ]
    assert repairs, report.repair_actions
    repair = repairs[0]
    assert isinstance(repair, RepairAction)
    assert repair.layout == "chart"
    assert repair.action == "not_applied"
    assert repair.before is None
    assert repair.after is None


# ── 3. Report must NOT mutate the caller's input ───────────────────────────


def test_build_report_does_not_mutate_input():
    deck = _chart_missing_subtitle_deck()
    snapshot = copy.deepcopy(deck)
    _ = build_deck_quality_report(deck)
    assert deck == snapshot, "build_deck_quality_report must not mutate input"


# ── 4. Non-list input is surfaced as a deck-level error ────────────────────


def test_build_report_handles_non_list_payload():
    report = build_deck_quality_report("not a list")
    assert isinstance(report, DeckQualityReport)
    assert report.ok is False
    assert report.slide_count == 0
    assert report.valid_count == 0
    assert report.invalid_count == 0
    assert report.errors and report.errors[0]["code"] == "invalid_payload"
    assert report.summary.get("deck_payload") == "invalid"


# ── 5. Serialization shape ─────────────────────────────────────────────────


def test_repair_action_to_dict_shape():
    repair = RepairAction(
        slide_index=1,
        layout="chart",
        path="subtitle",
        code="missing",
        message="m",
    )
    d = repair.to_dict()
    assert set(d.keys()) == {
        "slide_index",
        "layout",
        "path",
        "code",
        "message",
        "action",
        "before",
        "after",
    }
    assert d["action"] == "not_applied"


def test_deck_quality_report_to_dict_shape():
    report = build_deck_quality_report(VALID_DECK)
    d = report.to_dict()
    assert set(d.keys()) == {
        "ok",
        "slide_count",
        "valid_count",
        "invalid_count",
        "errors",
        "repair_actions",
        "repair_preview",
        "summary",
        "source_warnings",
    }
    assert isinstance(d["repair_actions"], list)
    assert isinstance(d["summary"], dict)
    assert isinstance(d["source_warnings"], list)


# ── 6. _normalize_slides telemetry: deck-quality summary + per-slide ───────
#
# These tests prove the report is wired into the live normalization
# pipeline and is the single source of truth for telemetry.


def test_normalize_slides_logs_deck_quality_summary(caplog):
    from agent.loop import NexusAgentLoop  # noqa: E402

    caplog.set_level(logging.INFO, logger="nexus.agent.loop")
    slides = [
        {"layout": "title", "title": "T", "subtitle": "S", "eyebrow": "E"},
        {"layout": "bullets", "title": "B", "bullets": ["a", "b"]},
        {"layout": "closing", "title": "Bye", "subtitle": "", "cta": "Thanks"},
    ]
    out = NexusAgentLoop._normalize_slides(slides, len(slides), "topic")
    assert len(out) == 3

    msgs = [r.getMessage() for r in caplog.records]
    assert any(
        "loop.deck_quality_report" in m
        and "slide_count=3" in m
        and "repairs_needed=" in m
        for m in msgs
    ), msgs


def test_normalize_slides_still_logs_validation_failure_for_safety_net(caplog):
    """P1-2 regression: the stats→chart safety-net must now produce a
    chart slide that already satisfies the tightened schema (slide-level
    ``subtitle`` carried forward / defaulted to ""). The previously-required
    ``loop.slide_validation_failed layout=chart path=subtitle code=missing``
    warning must NOT be emitted for this self-inflicted case anymore."""
    from agent.loop import NexusAgentLoop  # noqa: E402

    caplog.set_level(logging.WARNING, logger="nexus.agent.loop")
    slides = [
        {"layout": "title", "title": "T", "subtitle": "S", "eyebrow": "E"},
        {
            "layout": "stats",
            "title": "Numbers",
            "stats": [
                {"value": "10", "label": "alpha"},
                {"value": "20", "label": "beta"},
            ],
        },
        {"layout": "closing", "title": "Bye", "subtitle": "", "cta": "Thanks"},
    ]
    out = NexusAgentLoop._normalize_slides(slides, len(slides), "topic")
    # Safety-net still promotes a stats slide to chart…
    assert any(s["layout"] == "chart" for s in out), [s["layout"] for s in out]
    # …and the promoted chart slide now carries a (possibly empty) subtitle.
    chart_slide = next(s for s in out if s["layout"] == "chart")
    assert "subtitle" in chart_slide
    assert isinstance(chart_slide["subtitle"], str)

    warning_msgs = [
        r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    ]
    assert not any(
        "loop.slide_validation_failed" in m
        and "layout=chart" in m
        and "path=subtitle" in m
        and "code=missing" in m
        for m in warning_msgs
    ), warning_msgs
