"""Phase 6AA — bigstat + section_divider deterministic upgrade tests.

Validates the recommender's posture: never replaces planner output
unless the upgrade is unambiguous; never silently drops content;
preserves pinned first/last slides; never mutates the input list.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.layout_recommender import recommend_layouts  # noqa: E402


# ── Phase 6AA: bigstat upgrade — single dominant metric ────────────────────


def test_bigstat_upgrades_dominant_first_stat() -> None:
    """A stats slide where the first value dwarfs the rest by ≥3× upgrades."""
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {
            "id": "s1",
            "layout": "stats",
            "title": "Market",
            "stats": [
                {"value": "$4,200", "label": "TAM ($B)"},
                {"value": "$50", "label": "SAM ($B)"},
                {"value": "$10", "label": "SOM ($B)"},
            ],
            "intent": {"density": "medium"},
        },
        {"id": "s2", "layout": "closing", "title": "End"},
    ]
    out, upgrades = recommend_layouts(slides)
    assert out[1]["layout"] == "bigstat"
    assert out[1]["value"] == "$4,200"
    assert out[1]["label"] == "TAM ($B)"
    assert any(u["from"] == "stats" and u["to"] == "bigstat" for u in upgrades)


def test_bigstat_skips_when_density_is_high() -> None:
    """High-density stats slides are deliberately retained as a 3-up grid."""
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {
            "id": "s1",
            "layout": "stats",
            "title": "Market",
            "stats": [
                {"value": "$4,200", "label": "TAM"},
                {"value": "$50", "label": "SAM"},
                {"value": "$10", "label": "SOM"},
            ],
            "intent": {"density": "high"},
        },
        {"id": "s2", "layout": "closing", "title": "End"},
    ]
    out, upgrades = recommend_layouts(slides)
    assert out[1]["layout"] == "stats"
    assert not any(u["to"] == "bigstat" for u in upgrades)


def test_bigstat_skips_when_no_dominance() -> None:
    """Stats with similar magnitudes stay as a stats grid."""
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {
            "id": "s1",
            "layout": "stats",
            "title": "Comparison",
            "stats": [
                {"value": "100", "label": "A"},
                {"value": "95", "label": "B"},
                {"value": "90", "label": "C"},
            ],
            "intent": {"density": "low"},
        },
        {"id": "s2", "layout": "closing", "title": "End"},
    ]
    out, upgrades = recommend_layouts(slides)
    assert out[1]["layout"] == "stats"
    assert not any(u["to"] == "bigstat" for u in upgrades)


def test_bigstat_upgrades_single_stat_with_parsable_value() -> None:
    """A stats slide with exactly one stat is dominant by definition."""
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {
            "id": "s1",
            "layout": "stats",
            "title": "Headline",
            "stats": [{"value": "93%", "label": "Adoption"}],
            "intent": {"density": "low"},
        },
        {"id": "s2", "layout": "closing", "title": "End"},
    ]
    out, _ = recommend_layouts(slides)
    assert out[1]["layout"] == "bigstat"
    assert out[1]["value"] == "93%"


# ── Phase 6AA: section_divider upgrade — turning point + low density ──────


def test_section_divider_upgrades_turning_point_low_density_short_bullets() -> None:
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {
            "id": "s1",
            "layout": "bullets",
            "title": "Everything Changes",
            "bullets": ["A new era"],  # short, single bullet
            "intent": {"narrative_role": "turning_point", "density": "low"},
        },
        {"id": "s2", "layout": "closing", "title": "End"},
    ]
    out, upgrades = recommend_layouts(slides)
    assert out[1]["layout"] == "section_divider"
    assert out[1]["subtitle"] == "A new era"  # short bullet preserved
    assert any(u["to"] == "section_divider" for u in upgrades)


def test_section_divider_refuses_when_long_bullets_would_be_lost() -> None:
    """The recommender must refuse upgrades that drop substantive content."""
    long_bullet = "x" * 100  # > 60 char threshold
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {
            "id": "s1",
            "layout": "bullets",
            "title": "Pivot Point",
            "bullets": [long_bullet, "shorter"],
            "intent": {"narrative_role": "turning_point", "density": "low"},
        },
        {"id": "s2", "layout": "closing", "title": "End"},
    ]
    out, upgrades = recommend_layouts(slides)
    assert out[1]["layout"] == "bullets"
    assert not any(u["to"] == "section_divider" for u in upgrades)


# ── Pinned-end protection: first / last slides are never re-layouted ──────


def test_first_and_last_slides_are_never_upgraded() -> None:
    """Even if criteria match, slot 0 and slot -1 remain pinned."""
    slides = [
        # First slide deliberately matches stats→bigstat criteria, but is
        # pinned to title by upstream normalization. The recommender must
        # not touch it.
        {
            "id": "s0",
            "layout": "stats",
            "title": "Cover",
            "stats": [{"value": "$1B", "label": "X"}],
            "intent": {"density": "low"},
        },
        {"id": "s1", "layout": "bullets", "title": "Mid", "bullets": ["a"]},
        # Last slide deliberately matches turning_point→section_divider
        # criteria, but must remain untouched.
        {
            "id": "s2",
            "layout": "bullets",
            "title": "End",
            "bullets": ["x"],
            "intent": {"narrative_role": "turning_point", "density": "low"},
        },
    ]
    out, _ = recommend_layouts(slides)
    assert out[0]["layout"] == "stats"
    assert out[2]["layout"] == "bullets"


# ── Defensive: non-dict slides pass through, empty list returns empty ─────


def test_non_dict_slides_pass_through_unchanged() -> None:
    out, upgrades = recommend_layouts([{"layout": "title", "title": "X"}, "junk", None])  # type: ignore[arg-type]
    assert out[1] == "junk"
    assert out[2] is None
    assert upgrades == []


def test_empty_list_returns_empty() -> None:
    out, upgrades = recommend_layouts([])
    assert out == []
    assert upgrades == []


# ── Input list is never mutated (functional contract) ─────────────────────


def test_recommend_layouts_does_not_mutate_input() -> None:
    original = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {
            "id": "s1",
            "layout": "stats",
            "title": "Headline",
            "stats": [{"value": "93%", "label": "Adoption"}],
            "intent": {"density": "low"},
        },
        {"id": "s2", "layout": "closing", "title": "End"},
    ]
    snapshot = [{**s, "stats": list(s.get("stats", []))} for s in original]
    recommend_layouts(original)
    assert original[1]["layout"] == snapshot[1]["layout"]
    assert original[1]["stats"] == snapshot[1]["stats"]
