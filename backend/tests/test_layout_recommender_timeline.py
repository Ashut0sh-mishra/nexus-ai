"""Phase 6AC — bullets→timeline deterministic upgrade tests.

Validates that the recommender's timeline upgrader:
* fires only when ≥3 bullets parse cleanly as ``date — label`` pairs,
* refuses to fire if any non-dated bullet would be silently dropped,
* honours the 6-event cap from the schema validator,
* recognises the five date-format patterns,
* leaves non-bullets slides alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.layout_recommender import recommend_layouts  # noqa: E402


def _wrap(middle_slide: dict) -> list[dict]:
    """Pin first/last slides; the upgrader only touches the middle."""
    return [
        {"id": "s0", "layout": "title", "title": "Cover"},
        middle_slide,
        {"id": "s2", "layout": "closing", "title": "End"},
    ]


# ── Year-only pattern: ``1980 — Iraq invades`` ─────────────────────────────


def test_year_only_dates_upgrade_to_timeline() -> None:
    out, upgrades = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "bullets",
        "title": "Major events",
        "bullets": [
            "1980 — Iraq invades Iran",
            "1982 — Iran counter-offensive",
            "1988 — Ceasefire under UN Resolution 598",
        ],
    }))
    assert out[1]["layout"] == "timeline"
    events = out[1]["events"]
    assert len(events) == 3
    assert events[0] == {"date": "1980", "label": "Iraq invades Iran"}
    assert events[2] == {"date": "1988", "label": "Ceasefire under UN Resolution 598"}
    assert any(u["to"] == "timeline" for u in upgrades)


# ── Mixed date formats are all accepted ────────────────────────────────────


def test_multiple_date_formats_all_recognised() -> None:
    out, _ = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "bullets",
        "title": "Mixed history",
        "bullets": [
            "September 1980 — Invasion launched",
            "Q3 2024 — Product launch announced",
            "2024-01-15 — Ceasefire signed",
            "1980s — Decade of attrition",
        ],
    }))
    assert out[1]["layout"] == "timeline"
    assert len(out[1]["events"]) == 4


# ── Refuse when any non-dated bullet would be silently dropped ────────────


def test_timeline_refuses_when_mixed_with_non_dated_bullets() -> None:
    """Mixed lists (some dated, some not) must NOT upgrade — losing a
    non-dated bullet would silently drop user-meaningful content."""
    out, upgrades = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "bullets",
        "title": "Highlights",
        "bullets": [
            "1980 — Iraq invades Iran",
            "1982 — Iran counter-offensive",
            "1988 — Ceasefire signed",
            "Geopolitical implications were profound",  # non-dated
        ],
    }))
    assert out[1]["layout"] == "bullets"
    assert not any(u["to"] == "timeline" for u in upgrades)


# ── Refuse when fewer than 3 dated bullets ─────────────────────────────────


def test_timeline_refuses_when_fewer_than_three_dated_bullets() -> None:
    out, _ = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "bullets",
        "title": "Sparse",
        "bullets": [
            "1980 — Invasion",
            "1988 — Ceasefire",
        ],
    }))
    assert out[1]["layout"] == "bullets"


# ── Six-event cap: events beyond 6 are clamped ─────────────────────────────


def test_timeline_clamps_events_to_six() -> None:
    out, _ = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "bullets",
        "title": "Decades",
        "bullets": [
            "1980 — A",
            "1981 — B",
            "1982 — C",
            "1983 — D",
            "1984 — E",
            "1985 — F",
            "1986 — G",  # would be 7th
        ],
    }))
    # Note: bullets schema clamps at 4 already in normalize, but the
    # recommender runs on the post-normalize slides where the list could
    # be longer if the planner produced a richer chronology slide. The
    # recommender's own clamp protects the timeline schema (max 6).
    assert out[1]["layout"] == "timeline"
    assert len(out[1]["events"]) <= 6


# ── Non-bullets layouts are not touched ────────────────────────────────────


def test_timeline_skips_two_col_layouts() -> None:
    out, upgrades = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "two-col",
        "title": "Side by side",
        "columns": [
            {"heading": "1980", "body": "Invasion"},
            {"heading": "1988", "body": "Ceasefire"},
        ],
    }))
    assert out[1]["layout"] == "two-col"
    assert not any(u["to"] == "timeline" for u in upgrades)
