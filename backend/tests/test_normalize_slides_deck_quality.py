"""Phase 6U — generated slides must satisfy ``validate_deck``.

The 6T benchmark surfaced ``deck_quality_ok`` true on only 1/11 decks.
The leading cause was ``_normalize_slides`` pinning the first/last
slides to ``title``/``closing`` without seeding the layout-required
fields (subtitle/eyebrow/cta), so the strict validator rejected them.

``agent.deck_repair.repair_for_validator`` is the pre-save pass that
fills those safe, layout-local defaults. These tests cover the field
shapes the validator requires for each layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.deck_repair import repair_for_validator  # noqa: E402
from agent.slide_schema import validate_deck  # noqa: E402


def _ok(slides: list[dict]) -> bool:
    results = validate_deck(slides)
    return all(r.ok for r in results)


def test_title_missing_subtitle_eyebrow_is_repaired() -> None:
    slides = [{"id": "s0", "layout": "title", "title": "Hello"}]
    repaired = repair_for_validator(slides)
    assert _ok(repaired)
    assert repaired[0]["subtitle"] == ""
    assert repaired[0]["eyebrow"] == "Presentation"


def test_closing_missing_subtitle_cta_is_repaired() -> None:
    slides = [{"id": "s0", "layout": "closing", "title": "Thanks"}]
    repaired = repair_for_validator(slides)
    assert _ok(repaired)
    assert repaired[0]["subtitle"] == ""
    assert isinstance(repaired[0]["cta"], str) and repaired[0]["cta"]


def test_chart_missing_subtitle_unit_source_is_repaired() -> None:
    slides = [
        {
            "id": "s0",
            "layout": "chart",
            "title": "Capacity",
            "chart_type": "bar",
            "chart_data": {
                "labels": ["2022", "2023"],
                "values": [100.0, 145.0],
            },
        }
    ]
    repaired = repair_for_validator(slides)
    assert _ok(repaired)
    cd = repaired[0]["chart_data"]
    assert cd["unit"] == ""
    assert cd["source"] == ""
    assert repaired[0]["subtitle"] == ""


def test_quote_missing_attribution_is_repaired() -> None:
    slides = [
        {
            "id": "s0",
            "layout": "quote",
            "title": "Voice",
            "quote": "Innovation distinguishes leaders from followers.",
        }
    ]
    repaired = repair_for_validator(slides)
    assert _ok(repaired)
    assert repaired[0]["attribution"] == ""


def test_full_deck_satisfies_validator_after_repair() -> None:
    deck = [
        {"id": "s0", "layout": "title", "title": "Energy"},
        {
            "id": "s1",
            "layout": "bullets",
            "title": "Drivers",
            "bullets": ["Solar", "Battery", "Policy"],
        },
        {
            "id": "s2",
            "layout": "two-col",
            "title": "Compare",
            "columns": [
                {"heading": "Pros", "body": "Cleaner."},
                {"heading": "Cons", "body": "Intermittent."},
            ],
        },
        {
            "id": "s3",
            "layout": "quote",
            "title": "Voice",
            "quote": "The best way to predict the future is to invent it.",
        },
        {
            "id": "s4",
            "layout": "stats",
            "title": "Numbers",
            "stats": [
                {"value": "30%", "label": "Adoption"},
                {"value": "$5B", "label": "Investment"},
            ],
        },
        {
            "id": "s5",
            "layout": "chart",
            "title": "Capacity",
            "chart_type": "bar",
            "chart_data": {"labels": ["A", "B"], "values": [1.0, 2.0]},
        },
        {"id": "s6", "layout": "closing", "title": "Wrap"},
    ]
    repaired = repair_for_validator(deck)
    results = validate_deck(repaired)
    assert all(
        r.ok for r in results
    ), [(i, [e.code for e in r.errors]) for i, r in enumerate(results) if not r.ok]


def test_repair_does_not_invent_bullet_content() -> None:
    # A ``bullets`` slide with no bullets list is genuinely incomplete.
    # Repair must NOT invent bullet content; the validator should still
    # flag it. This guards against scope creep on the repair pass.
    slides = [{"id": "s0", "layout": "bullets", "title": "Empty"}]
    repaired = repair_for_validator(slides)
    results = validate_deck(repaired)
    assert not all(r.ok for r in results)


def test_repair_passes_through_non_dict_slides() -> None:
    out = repair_for_validator([None, "not a slide", {"id": "s", "layout": "title", "title": "OK"}])  # type: ignore[list-item]
    assert out[0] is None
    assert out[1] == "not a slide"
    # The valid title slide gains subtitle/eyebrow defaults.
    assert out[2].get("subtitle") == ""
    assert out[2].get("eyebrow") == "Presentation"
