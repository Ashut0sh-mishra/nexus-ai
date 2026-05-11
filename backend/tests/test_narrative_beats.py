"""Phase 6AD — narrative beat extraction tests.

Validates the deterministic beat sequence derivation:
* canonical 6-beat vocabulary,
* always returns ``slide_count``-length list,
* setup pinned at slot 0, aftermath pinned at slot -1,
* arc normalisation for known and unknown beat strings,
* research-side promotion fires only on unambiguous keyword matches,
* beat-transition indices are monotonic and skip the first slot.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.narrative_beats import (  # noqa: E402
    BEAT_AFTERMATH,
    BEAT_ESCALATION,
    BEAT_SETUP,
    BEAT_SUPPORT,
    BEAT_TURNING_POINT,
    CANONICAL_BEATS,
    beat_transition_indices,
    derive_beats,
    normalize_arc,
    role_from_beat,
)


# ── Vocabulary contract ────────────────────────────────────────────────────


def test_canonical_beats_is_immutable_tuple_of_known_strings() -> None:
    assert isinstance(CANONICAL_BEATS, tuple)
    assert BEAT_SETUP in CANONICAL_BEATS
    assert BEAT_ESCALATION in CANONICAL_BEATS
    assert BEAT_TURNING_POINT in CANONICAL_BEATS
    assert BEAT_AFTERMATH in CANONICAL_BEATS
    assert BEAT_SUPPORT in CANONICAL_BEATS


# ── derive_beats: shape contract ──────────────────────────────────────────


def test_derive_beats_returns_exactly_slide_count_items() -> None:
    for n in (1, 2, 4, 8, 12):
        beats = derive_beats(slide_count=n)
        assert len(beats) == n
        assert all(b in CANONICAL_BEATS for b in beats)


def test_derive_beats_pins_first_setup_and_last_aftermath() -> None:
    beats = derive_beats(slide_count=8)
    assert beats[0] == BEAT_SETUP
    assert beats[-1] == BEAT_AFTERMATH


def test_derive_beats_handles_zero_and_one_slide() -> None:
    assert derive_beats(slide_count=0) == []
    assert derive_beats(slide_count=1) == [BEAT_SETUP]


# ── Arc normalisation ─────────────────────────────────────────────────────


def test_normalize_arc_maps_known_strings() -> None:
    arc = ["context", "finding", "implication", "ask"]
    canonical = normalize_arc(arc)
    assert canonical == [BEAT_SETUP, BEAT_ESCALATION, "consequence", BEAT_AFTERMATH]


def test_normalize_arc_unknown_string_falls_back_to_support() -> None:
    canonical = normalize_arc(["context", "mystery_beat", "ask"])
    assert canonical[0] == BEAT_SETUP
    assert canonical[1] == BEAT_SUPPORT  # unknown → support
    assert canonical[2] == BEAT_AFTERMATH


def test_normalize_arc_empty_returns_empty() -> None:
    assert normalize_arc(None) == []
    assert normalize_arc([]) == []


# ── Arc threading: middle slides reflect the arc ──────────────────────────


def test_derive_beats_with_arc_threads_arc_across_middle_slides() -> None:
    arc = ["context", "finding", "implication", "ask"]
    beats = derive_beats(slide_count=6, story_arc=arc)
    assert beats[0] == BEAT_SETUP
    assert beats[-1] == BEAT_AFTERMATH
    # Middle slides should not be all support — the arc is non-trivial.
    middle = beats[1:-1]
    assert any(b != BEAT_SUPPORT for b in middle)


# ── Research-side turning-point promotion ─────────────────────────────────


def test_research_keyword_promotes_escalation_to_turning_point() -> None:
    """Research carrying 'however' or similar must promote one
    escalation slide to turning_point — placed as late as possible."""
    arc = ["context", "finding", "implication", "ask"]
    research = (
        "Background context. The system worked well at first. However, "
        "the conditions changed unexpectedly and the situation escalated."
    )
    beats = derive_beats(slide_count=8, story_arc=arc, research=research)
    assert BEAT_TURNING_POINT in beats
    # Pinned ends remain unchanged.
    assert beats[0] == BEAT_SETUP
    assert beats[-1] == BEAT_AFTERMATH


def test_research_without_keyword_does_not_promote_turning_point() -> None:
    arc = ["context", "finding", "implication", "ask"]
    research = "Background context. The system worked well consistently."
    beats = derive_beats(slide_count=8, story_arc=arc, research=research)
    # Without a turning-point keyword, promotion does not fire.
    # (The arc-normalised middle does not contain turning_point itself.)
    assert BEAT_TURNING_POINT not in beats[1:-1]


# ── role_from_beat round-trip ─────────────────────────────────────────────


def test_role_from_beat_maps_canonical_beats_to_intent_roles() -> None:
    assert role_from_beat(BEAT_SETUP) == "context"
    assert role_from_beat(BEAT_ESCALATION) == "evidence"
    assert role_from_beat(BEAT_TURNING_POINT) == "turning_point"
    assert role_from_beat(BEAT_AFTERMATH) == "synthesis"
    # Unknown beats fall back to "support".
    assert role_from_beat("unknown_beat_name") == "support"


# ── Beat transition indices ───────────────────────────────────────────────


def test_beat_transition_indices_are_monotonic_and_skip_index_zero() -> None:
    beats = [BEAT_SETUP, BEAT_SETUP, BEAT_ESCALATION, BEAT_TURNING_POINT, BEAT_AFTERMATH]
    transitions = beat_transition_indices(beats)
    assert transitions == [2, 3, 4]
    assert all(i > 0 for i in transitions)
    assert transitions == sorted(transitions)


def test_beat_transition_indices_empty_when_all_same() -> None:
    assert beat_transition_indices([BEAT_SETUP] * 5) == []
