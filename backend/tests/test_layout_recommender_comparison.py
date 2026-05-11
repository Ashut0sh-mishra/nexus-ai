"""Phase 6AC — two-col→comparison deterministic upgrade tests.

Validates that the recommender's comparison upgrader:
* fires when the slide title carries an explicit cue (`vs`,
  `before/after`, etc.),
* fires when the column headings form a known antonym pair,
* refuses to fire when either side is missing heading or body,
* leaves non-two-col slides alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.layout_recommender import recommend_layouts  # noqa: E402


def _wrap(middle_slide: dict) -> list[dict]:
    return [
        {"id": "s0", "layout": "title", "title": "Cover"},
        middle_slide,
        {"id": "s2", "layout": "closing", "title": "End"},
    ]


# ── Title-cue based upgrade ────────────────────────────────────────────────


def test_comparison_upgrades_when_title_has_vs_cue() -> None:
    out, upgrades = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "two-col",
        "title": "On-prem vs Cloud",
        "columns": [
            {"heading": "On-premise", "body": "Capex heavy, full control."},
            {"heading": "Cloud", "body": "Opex model, elastic scale."},
        ],
    }))
    assert out[1]["layout"] == "comparison"
    assert out[1]["left"] == {"heading": "On-premise", "body": "Capex heavy, full control."}
    assert out[1]["right"] == {"heading": "Cloud", "body": "Opex model, elastic scale."}
    assert any(u["to"] == "comparison" for u in upgrades)


def test_comparison_upgrades_when_title_has_before_after_cue() -> None:
    out, _ = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "two-col",
        "title": "Before and after the migration",
        "columns": [
            {"heading": "Phase 1", "body": "Manual workflows; 3-day cycle time."},
            {"heading": "Phase 2", "body": "Automated pipeline; 4-hour cycle time."},
        ],
    }))
    assert out[1]["layout"] == "comparison"


# ── Antonym-pair heading match ─────────────────────────────────────────────


def test_comparison_upgrades_on_problem_solution_heading_pair() -> None:
    out, upgrades = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "two-col",
        "title": "What we found",  # no cue in title
        "columns": [
            {"heading": "The Problem", "body": "Latency is unbounded."},
            {"heading": "Our Solution", "body": "Bounded queue with bulkhead."},
        ],
    }))
    assert out[1]["layout"] == "comparison"
    assert any(
        "contrast pair" in u.get("reason", "").lower() for u in upgrades
    )


def test_comparison_upgrades_on_pros_cons_heading_pair() -> None:
    out, _ = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "two-col",
        "title": "Tradeoffs",
        "columns": [
            {"heading": "Pros", "body": "Faster delivery; smaller blast radius."},
            {"heading": "Cons", "body": "Higher operational complexity."},
        ],
    }))
    assert out[1]["layout"] == "comparison"


# ── Refuse when either side is missing required content ───────────────────


def test_comparison_refuses_when_side_missing_body() -> None:
    out, upgrades = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "two-col",
        "title": "Before vs After",
        "columns": [
            {"heading": "Before", "body": "Manual."},
            {"heading": "After", "body": ""},  # empty body
        ],
    }))
    assert out[1]["layout"] == "two-col"
    assert not any(u["to"] == "comparison" for u in upgrades)


# ── Non-two-col layouts pass through unchanged ─────────────────────────────


def test_comparison_skips_bullets_layout() -> None:
    """A bullets slide whose title carries 'vs' must NOT upgrade — the
    upgrader is two-col-shaped only."""
    out, upgrades = recommend_layouts(_wrap({
        "id": "s1",
        "layout": "bullets",
        "title": "On-prem vs Cloud",
        "bullets": ["On-prem is heavy", "Cloud is elastic"],
    }))
    assert out[1]["layout"] == "bullets"
    assert not any(u["to"] == "comparison" for u in upgrades)
