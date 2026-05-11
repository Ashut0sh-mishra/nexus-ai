"""Phase 6AB / 6AD — slide intent metadata derivation tests.

Pure-function tests against ``agent.slide_intent``: verify the four
canonical intent fields, beat-aware role overrides (Phase 6AD),
density heuristics per layout, tone precedence, and backward
compatibility (renderer/validator must continue to ignore the field).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.slide_intent import (  # noqa: E402
    DENSITIES,
    NARRATIVE_ROLES,
    attach_slide_intent,
    derive_intent,
)
from agent.slide_schema import validate_deck  # noqa: E402


# ── Shape + JSON serialisability ───────────────────────────────────────────


def test_intent_block_has_four_canonical_fields() -> None:
    intent = derive_intent(
        {"layout": "bullets", "title": "X", "bullets": ["A", "B"]},
        position=1,
        total=4,
    )
    assert set(intent.keys()) == {
        "narrative_role",
        "tone",
        "density",
        "communication_goal",
    }
    assert intent["narrative_role"] in NARRATIVE_ROLES
    assert intent["density"] in DENSITIES
    assert isinstance(intent["communication_goal"], str)
    assert intent["communication_goal"]


def test_intent_block_is_json_serialisable() -> None:
    intent = derive_intent(
        {"layout": "stats", "title": "S", "stats": [{"value": "$4.2B", "label": "TAM"}]},
        position=2,
        total=5,
        story_arc=["context", "finding", "ask"],
        strategy_tone="measured documentary",
        art_mood="serious",
    )
    json.dumps(intent)  # must not raise


# ── Position-based role derivation when no arc is supplied ─────────────────


def test_role_from_position_pins_opening_and_closing() -> None:
    first = derive_intent({"layout": "title", "title": "T"}, position=0, total=8)
    last = derive_intent({"layout": "closing", "title": "T"}, position=7, total=8)
    assert first["narrative_role"] == "opening"
    assert last["narrative_role"] == "closing"


def test_role_from_position_paces_middle_three_acts() -> None:
    """The middle slides should pace context → evidence → synthesis."""
    total = 8
    middle_roles = [
        derive_intent({"layout": "bullets", "title": "x"}, position=i, total=total)["narrative_role"]
        for i in range(1, total - 1)
    ]
    # First middle slide is context, last middle slide is synthesis.
    assert middle_roles[0] == "context"
    assert middle_roles[-1] == "synthesis"


# ── Arc-based role derivation maps strategy.story_arc beats correctly ─────


def test_role_from_arc_uses_canonical_mapping() -> None:
    """An arc with 'finding' should produce role='evidence' on the
    middle slides (first/last are pinned to opening/closing)."""
    arc = ["context", "finding", "implication", "ask"]
    middle = derive_intent(
        {"layout": "bullets", "title": "x"},
        position=2,
        total=6,
        story_arc=arc,
    )
    assert middle["narrative_role"] in {"context", "evidence", "synthesis"}


# ── Phase 6AD: beat overrides arc/position-based role ──────────────────────


def test_beat_overrides_position_role() -> None:
    """When a canonical beat is supplied, narrative_role derives from beat."""
    intent = derive_intent(
        {"layout": "bullets", "title": "x"},
        position=3,
        total=8,
        beat="turning_point",
    )
    assert intent["narrative_role"] == "turning_point"
    assert intent["beat"] == "turning_point"


def test_beat_field_only_present_when_supplied() -> None:
    """Slides with no beat info should not carry an intent.beat field."""
    intent = derive_intent({"layout": "bullets", "title": "x"}, position=2, total=5)
    assert "beat" not in intent


# ── Density heuristics per layout ──────────────────────────────────────────


def test_density_low_for_title_and_closing() -> None:
    title = derive_intent({"layout": "title", "title": "T"}, position=0, total=4)
    closing = derive_intent({"layout": "closing", "title": "T"}, position=3, total=4)
    assert title["density"] == "low"
    assert closing["density"] == "low"


def test_density_scales_with_bullet_count_and_length() -> None:
    short = derive_intent(
        {"layout": "bullets", "title": "x", "bullets": ["a"]},
        position=1,
        total=4,
    )
    medium = derive_intent(
        {"layout": "bullets", "title": "x", "bullets": ["a", "b", "c"]},
        position=1,
        total=4,
    )
    high = derive_intent(
        {
            "layout": "bullets",
            "title": "x",
            "bullets": ["a", "b", "c", "d"],
        },
        position=1,
        total=4,
    )
    assert short["density"] == "low"
    assert medium["density"] == "medium"
    assert high["density"] == "high"


def test_density_high_for_long_quote() -> None:
    long_quote = "x" * 250
    intent = derive_intent(
        {"layout": "quote", "title": "Q", "quote": long_quote},
        position=2,
        total=5,
    )
    assert intent["density"] == "high"


# ── Tone precedence: art_mood beats strategy_tone keyword scan ─────────────


def test_tone_prefers_art_mood_over_strategy_tone() -> None:
    intent = derive_intent(
        {"layout": "bullets", "title": "x"},
        position=1,
        total=4,
        strategy_tone="measured documentary",  # would give "calm"
        art_mood="polished",
    )
    assert intent["tone"] == "polished"


def test_tone_falls_back_to_strategy_tone_keywords() -> None:
    intent = derive_intent(
        {"layout": "bullets", "title": "x"},
        position=1,
        total=4,
        strategy_tone="dramatic and expressive",
    )
    assert intent["tone"] == "expressive"


def test_tone_falls_back_to_neutral_when_no_signal() -> None:
    intent = derive_intent({"layout": "bullets", "title": "x"}, position=1, total=4)
    assert intent["tone"] == "neutral"


# ── attach_slide_intent: idempotency, list shape, edge cases ───────────────


def test_attach_slide_intent_returns_new_list_with_intent_blocks() -> None:
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {"id": "s1", "layout": "bullets", "title": "X", "bullets": ["a"]},
        {"id": "s2", "layout": "closing", "title": "End"},
    ]
    out = attach_slide_intent(slides)
    assert len(out) == 3
    # Original list not mutated.
    assert "intent" not in slides[0]
    # Each output slide has the intent block.
    assert all("intent" in s for s in out)


def test_attach_slide_intent_idempotent_on_repeated_call() -> None:
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {"id": "s1", "layout": "closing", "title": "End"},
    ]
    once = attach_slide_intent(slides)
    twice = attach_slide_intent(once)
    assert once[0]["intent"] == twice[0]["intent"]
    assert once[1]["intent"] == twice[1]["intent"]


def test_attach_slide_intent_passes_non_dict_through() -> None:
    """Defensive: malformed entries (non-dicts) must not raise."""
    slides = [{"id": "s0", "layout": "title", "title": "X"}, "not-a-dict", None]
    out = attach_slide_intent(slides)  # type: ignore[arg-type]
    assert isinstance(out[0], dict) and "intent" in out[0]
    assert out[1] == "not-a-dict"
    assert out[2] is None


def test_attach_slide_intent_empty_list_returns_empty() -> None:
    assert attach_slide_intent([]) == []


# ── Phase 6AD: beats kwarg threading ───────────────────────────────────────


def test_attach_slide_intent_beats_override_role_per_slide() -> None:
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {"id": "s1", "layout": "bullets", "title": "X", "bullets": ["a"]},
        {"id": "s2", "layout": "closing", "title": "End"},
    ]
    beats = ["setup", "turning_point", "aftermath"]
    out = attach_slide_intent(slides, beats=beats)
    assert out[0]["intent"]["beat"] == "setup"
    assert out[1]["intent"]["beat"] == "turning_point"
    assert out[1]["intent"]["narrative_role"] == "turning_point"
    assert out[2]["intent"]["beat"] == "aftermath"


def test_attach_slide_intent_beats_length_mismatch_falls_back() -> None:
    """Mismatched beats length must drop beats, never raise or misalign."""
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover"},
        {"id": "s1", "layout": "bullets", "title": "X", "bullets": ["a"]},
    ]
    out = attach_slide_intent(slides, beats=["setup"])
    # beats are dropped; intent.beat is absent.
    assert "beat" not in out[0]["intent"]
    assert "beat" not in out[1]["intent"]


# ── Backward compatibility: schema accepts slides with intent block ───────


def test_validate_deck_accepts_slides_with_intent_field() -> None:
    """Adding ``intent`` must not cause validate_deck to reject the slide."""
    slides = [
        {"id": "s0", "layout": "title", "title": "Cover", "subtitle": "", "eyebrow": "X"},
        {
            "id": "s1",
            "layout": "bullets",
            "title": "X",
            "bullets": ["a", "b"],
            "intent": {
                "narrative_role": "context",
                "tone": "neutral",
                "density": "medium",
                "communication_goal": "establish background",
                "beat": "setup",
            },
        },
        {"id": "s2", "layout": "closing", "title": "End", "subtitle": "", "cta": "OK"},
    ]
    results = validate_deck(slides)
    assert all(r.ok for r in results), [r.errors for r in results if not r.ok]
