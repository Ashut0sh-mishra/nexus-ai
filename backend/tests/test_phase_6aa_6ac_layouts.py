"""Phases 6AA + 6AC — coverage for the 4 new canonical layouts.

Asserts:
* schema validator accepts well-formed slides for each layout,
* schema validator rejects malformed payloads,
* deck_repair seeds the optional fields the validator requires,
* registry recognises all 4 layouts as canonical,
* layouts list count = 11 (was 7 pre-6AA).
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.deck_repair import repair_for_validator  # noqa: E402
from agent.layouts_registry import CANONICAL_LAYOUTS  # noqa: E402
from agent.slide_schema import validate_deck, validate_slide  # noqa: E402


# ── Registry contract ──────────────────────────────────────────────────────


def test_registry_contains_all_phase_6aa_6ac_layouts() -> None:
    """Phase 6AA shipped bigstat + section_divider; 6AC shipped timeline + comparison."""
    for name in ("bigstat", "section_divider", "timeline", "comparison"):
        assert name in CANONICAL_LAYOUTS, name


def test_canonical_layouts_count_is_eleven() -> None:
    assert len(CANONICAL_LAYOUTS) == 11


# ── bigstat schema ─────────────────────────────────────────────────────────


def test_bigstat_validates_with_value_and_label() -> None:
    result = validate_slide({
        "id": "s0",
        "layout": "bigstat",
        "title": "Adoption",
        "value": "93%",
        "label": "Active users",
        "subtitle": "",
    })
    assert result.ok, result.errors


def test_bigstat_missing_value_fails_validation() -> None:
    result = validate_slide({
        "id": "s0",
        "layout": "bigstat",
        "title": "Adoption",
    })
    assert not result.ok
    codes = {e.code for e in result.errors}
    assert "missing" in codes


def test_bigstat_repair_seeds_optional_fields_only() -> None:
    """``value`` is required and must NOT be invented by repair."""
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover", "subtitle": "", "eyebrow": "X"},
        {"id": "s1", "layout": "bigstat", "title": "X", "value": "93%"},
        {"id": "s2", "layout": "closing", "title": "End", "subtitle": "", "cta": "OK"},
    ]
    repaired = repair_for_validator(slides)
    assert all(r.ok for r in validate_deck(repaired)), [
        r.errors for r in validate_deck(repaired) if not r.ok
    ]
    assert repaired[1]["value"] == "93%"  # never invented
    assert repaired[1]["label"] == ""
    assert repaired[1]["subtitle"] == ""


# ── section_divider schema ─────────────────────────────────────────────────


def test_section_divider_validates_with_title_only() -> None:
    result = validate_slide({
        "id": "s0",
        "layout": "section_divider",
        "title": "Part Two",
        "eyebrow": "",
        "subtitle": "",
    })
    assert result.ok, result.errors


def test_section_divider_repair_seeds_eyebrow_and_subtitle() -> None:
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover", "subtitle": "", "eyebrow": "X"},
        {"id": "s1", "layout": "section_divider", "title": "Part Two"},
        {"id": "s2", "layout": "closing", "title": "End", "subtitle": "", "cta": "OK"},
    ]
    repaired = repair_for_validator(slides)
    assert all(r.ok for r in validate_deck(repaired))
    assert repaired[1]["eyebrow"] == ""
    assert repaired[1]["subtitle"] == ""


# ── timeline schema ────────────────────────────────────────────────────────


def test_timeline_validates_with_dated_events() -> None:
    result = validate_slide({
        "id": "s0",
        "layout": "timeline",
        "title": "Major events",
        "subtitle": "",
        "events": [
            {"date": "1980", "label": "Invasion"},
            {"date": "1982", "label": "Counter-offensive"},
            {"date": "1988", "label": "Ceasefire"},
        ],
    })
    assert result.ok, result.errors


def test_timeline_rejects_more_than_six_events() -> None:
    result = validate_slide({
        "id": "s0",
        "layout": "timeline",
        "title": "Decades",
        "subtitle": "",
        "events": [{"date": str(1980 + i), "label": f"E{i}"} for i in range(7)],
    })
    assert not result.ok
    codes = {e.code for e in result.errors}
    assert "too_many" in codes


def test_timeline_rejects_event_missing_date_or_label() -> None:
    result = validate_slide({
        "id": "s0",
        "layout": "timeline",
        "title": "Bad",
        "subtitle": "",
        "events": [{"date": "1980", "label": ""}],
    })
    assert not result.ok


def test_timeline_repair_seeds_subtitle_only() -> None:
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover", "subtitle": "", "eyebrow": "X"},
        {
            "id": "s1",
            "layout": "timeline",
            "title": "T",
            "events": [
                {"date": "1980", "label": "A"},
                {"date": "1985", "label": "B"},
                {"date": "1990", "label": "C"},
            ],
        },
        {"id": "s2", "layout": "closing", "title": "End", "subtitle": "", "cta": "OK"},
    ]
    repaired = repair_for_validator(slides)
    assert all(r.ok for r in validate_deck(repaired))
    assert repaired[1]["subtitle"] == ""
    # events are not invented by the repair pass.
    assert len(repaired[1]["events"]) == 3


# ── comparison schema ──────────────────────────────────────────────────────


def test_comparison_validates_with_left_and_right_blocks() -> None:
    result = validate_slide({
        "id": "s0",
        "layout": "comparison",
        "title": "On-prem vs Cloud",
        "subtitle": "",
        "left": {"heading": "On-prem", "body": "Capex heavy."},
        "right": {"heading": "Cloud", "body": "Opex elastic."},
    })
    assert result.ok, result.errors


def test_comparison_rejects_missing_side() -> None:
    result = validate_slide({
        "id": "s0",
        "layout": "comparison",
        "title": "Half",
        "subtitle": "",
        "left": {"heading": "On-prem", "body": "Capex heavy."},
        # right intentionally missing
    })
    assert not result.ok


def test_comparison_rejects_empty_heading_or_body() -> None:
    result = validate_slide({
        "id": "s0",
        "layout": "comparison",
        "title": "X",
        "subtitle": "",
        "left": {"heading": "", "body": "..."},
        "right": {"heading": "After", "body": ""},
    })
    assert not result.ok
