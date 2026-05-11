"""Phase 6AD — narrative beat extraction.

The pre-6AD pipeline ran ``research → strategy → planner → slides`` with
``DeckStrategy.story_arc`` as the only narrative signal. The arc is
useful but coarse — beats like "context", "finding", "ask" describe
slide *purpose* but not *dramatic shape*. Documentary storytelling
(the Manus quality bar) needs a richer beat vocabulary that captures:

* setup        — establish the world before the action
* escalation   — rising tension, stakes building
* turning_point — the dramatic shift; ``before`` ends, ``after`` begins
* consequence   — fallout of the shift
* aftermath     — long-tail legacy / current state

This module derives a per-slide beat sequence from the existing
``DeckStrategy`` (and optionally the research blob, when keyword
signals are unambiguous). It is intentionally:

* deterministic (pure-Python, no LLM, no network, no randomness),
* additive (callers that don't pass beats see the prior behaviour),
* nullable-safe (``derive_beats`` always returns a list of the right
  length, padded with ``"support"`` if no signal is available),
* read-only (never mutates ``DeckStrategy``).

The beat sequence influences three downstream layers:

1. ``slide_intent.attach_slide_intent`` — beat overrides position-based
   ``narrative_role`` derivation when present.
2. ``layout_recommender.recommend_layouts`` — beat transitions become
   ``section_divider`` candidates (escalation→turning_point in particular).
3. SSE ``design_decision`` events — the beat sequence is emitted so the
   AI Reasoning panel shows the dramatic shape of the deck.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

logger = logging.getLogger("nexus.agent.narrative_beats")


# ── Public vocab ──────────────────────────────────────────────────────────

BEAT_SETUP = "setup"
BEAT_ESCALATION = "escalation"
BEAT_TURNING_POINT = "turning_point"
BEAT_CONSEQUENCE = "consequence"
BEAT_AFTERMATH = "aftermath"
BEAT_SUPPORT = "support"  # neutral filler when no signal is present

CANONICAL_BEATS: tuple[str, ...] = (
    BEAT_SETUP,
    BEAT_ESCALATION,
    BEAT_TURNING_POINT,
    BEAT_CONSEQUENCE,
    BEAT_AFTERMATH,
    BEAT_SUPPORT,
)

# Mapping from narrative_role (used by ``slide_intent``) to canonical beat.
# Used the other direction too: beat → role for the intent override path.
ROLE_FROM_BEAT: dict[str, str] = {
    BEAT_SETUP: "context",
    BEAT_ESCALATION: "evidence",
    BEAT_TURNING_POINT: "turning_point",
    BEAT_CONSEQUENCE: "synthesis",
    BEAT_AFTERMATH: "synthesis",
    BEAT_SUPPORT: "support",
}


# ── Strategy.story_arc → beat normalisation ───────────────────────────────

# DeckStrategy.story_arc strings are free-form per deck type. Map the
# common ones onto canonical beats. Order does not matter — this is a
# direct lookup.
_ARC_BEAT_MAP: dict[str, str] = {
    # Setup-class
    "context": BEAT_SETUP,
    "background": BEAT_SETUP,
    "setup": BEAT_SETUP,
    "intro": BEAT_SETUP,
    "introduction": BEAT_SETUP,
    "baseline": BEAT_SETUP,
    "the problem": BEAT_SETUP,
    "problem": BEAT_SETUP,
    # Escalation-class
    "finding": BEAT_ESCALATION,
    "findings": BEAT_ESCALATION,
    "evidence": BEAT_ESCALATION,
    "data": BEAT_ESCALATION,
    "analysis": BEAT_ESCALATION,
    "rising action": BEAT_ESCALATION,
    "stakes": BEAT_ESCALATION,
    "escalation": BEAT_ESCALATION,
    # Turning-point-class
    "turning point": BEAT_TURNING_POINT,
    "turning_point": BEAT_TURNING_POINT,
    "shift": BEAT_TURNING_POINT,
    "twist": BEAT_TURNING_POINT,
    "the moment": BEAT_TURNING_POINT,
    "decision": BEAT_TURNING_POINT,
    "pivot": BEAT_TURNING_POINT,
    # Consequence-class
    "implication": BEAT_CONSEQUENCE,
    "implications": BEAT_CONSEQUENCE,
    "insight": BEAT_CONSEQUENCE,
    "synthesis": BEAT_CONSEQUENCE,
    "fallout": BEAT_CONSEQUENCE,
    "result": BEAT_CONSEQUENCE,
    "outcome": BEAT_CONSEQUENCE,
    # Aftermath-class
    "ask": BEAT_AFTERMATH,
    "cta": BEAT_AFTERMATH,
    "call to action": BEAT_AFTERMATH,
    "summary": BEAT_AFTERMATH,
    "conclusion": BEAT_AFTERMATH,
    "legacy": BEAT_AFTERMATH,
    "today": BEAT_AFTERMATH,
    "current state": BEAT_AFTERMATH,
}


# ── Research-side signal probes ───────────────────────────────────────────

# Conservative: only flip the default if research carries unambiguous
# turning-point language. We do NOT use these to invent beats from thin
# air — they only escalate one slide's beat from "escalation" to
# "turning_point" when a strong signal is detected.
_TURNING_POINT_SIGNALS = re.compile(
    r"\b(?:however|but\s+then|suddenly|unexpectedly|the\s+turning\s+point"
    r"|everything\s+changed|in\s+a\s+stunning|crossed\s+the\s+rubicon"
    r"|catastrophic|breakthrough|inflection\s+point)\b",
    re.IGNORECASE,
)


# ── Public API ────────────────────────────────────────────────────────────


def normalize_arc(story_arc: Iterable[Any] | None) -> list[str]:
    """Map a ``DeckStrategy.story_arc`` to canonical beat names.

    Unrecognised arc beats become ``BEAT_SUPPORT`` so downstream
    consumers always see a list of canonical beats. Returns ``[]`` for
    empty / None inputs.
    """
    if not story_arc:
        return []
    out: list[str] = []
    for raw in story_arc:
        if not isinstance(raw, str):
            out.append(BEAT_SUPPORT)
            continue
        key = raw.strip().lower()
        out.append(_ARC_BEAT_MAP.get(key, BEAT_SUPPORT))
    return out


def derive_beats(
    *,
    slide_count: int,
    story_arc: Iterable[Any] | None = None,
    research: str | None = None,
) -> list[str]:
    """Return one canonical beat per slide.

    Strategy:
    1. Pin the first beat to ``setup`` and the last beat to ``aftermath``
       — those positions are already pinned in the deck (title / closing).
    2. For the middle slides, stretch the (normalised) story_arc evenly.
       If story_arc is empty, fall back to a default 5-beat shape.
    3. If ``research`` carries a strong turning-point signal AND the
       middle contains an ``escalation`` beat, escalate the *last*
       escalation slide to ``turning_point`` so the dramatic shift sits
       at a real position in the deck.

    Always returns a list of length ``slide_count``. Never raises.
    """
    if slide_count <= 0:
        return []
    if slide_count == 1:
        return [BEAT_SETUP]

    beats: list[str] = [BEAT_SUPPORT] * slide_count
    beats[0] = BEAT_SETUP
    beats[-1] = BEAT_AFTERMATH

    canonical_arc = normalize_arc(story_arc)
    middle_count = slide_count - 2
    if middle_count > 0:
        if canonical_arc:
            # Filter the arc down to the middle beats (drop arc-pinned
            # setup/aftermath since those already own slot 0 / -1).
            interior_arc = [
                b for b in canonical_arc if b not in (BEAT_SETUP, BEAT_AFTERMATH)
            ] or canonical_arc
            for i in range(middle_count):
                arc_idx = min(
                    int(i / max(middle_count, 1) * len(interior_arc)),
                    len(interior_arc) - 1,
                )
                beats[i + 1] = interior_arc[arc_idx]
        else:
            # No arc → default documentary shape stretched over the middle.
            default = [
                BEAT_SETUP,
                BEAT_ESCALATION,
                BEAT_TURNING_POINT,
                BEAT_CONSEQUENCE,
                BEAT_AFTERMATH,
            ]
            for i in range(middle_count):
                idx = min(int(i / max(middle_count, 1) * len(default)), len(default) - 1)
                beats[i + 1] = default[idx]

    # Promote a single escalation beat to turning_point if research
    # signals a real shift. We promote the LAST escalation slide so the
    # shift lands as late as possible (more dramatic).
    if research and isinstance(research, str) and _TURNING_POINT_SIGNALS.search(research):
        if BEAT_TURNING_POINT not in beats[1:-1]:
            for i in range(slide_count - 2, 0, -1):
                if beats[i] == BEAT_ESCALATION:
                    beats[i] = BEAT_TURNING_POINT
                    break

    return beats


def role_from_beat(beat: str) -> str:
    """Map a canonical beat to a ``slide_intent.narrative_role`` value."""
    return ROLE_FROM_BEAT.get(beat, "support")


def beat_transition_indices(beats: list[str]) -> list[int]:
    """Return slide indices (0-based) where the beat changes.

    Useful for placing section dividers at major narrative transitions.
    The first slide is never returned (it always starts a beat by
    definition); transitions before ``aftermath`` are the most
    dramatically meaningful.
    """
    transitions: list[int] = []
    for i in range(1, len(beats)):
        if beats[i] != beats[i - 1]:
            transitions.append(i)
    return transitions


__all__ = [
    "BEAT_SETUP",
    "BEAT_ESCALATION",
    "BEAT_TURNING_POINT",
    "BEAT_CONSEQUENCE",
    "BEAT_AFTERMATH",
    "BEAT_SUPPORT",
    "CANONICAL_BEATS",
    "ROLE_FROM_BEAT",
    "normalize_arc",
    "derive_beats",
    "role_from_beat",
    "beat_transition_indices",
]
