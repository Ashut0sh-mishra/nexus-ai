"""Phase 6AB — deterministic per-slide intent metadata.

Pure-Python derivation of an ``intent`` block per slide. The block carries
four fields:

* ``narrative_role``   — where the slide sits in the deck arc
                          (``opening``, ``context``, ``evidence``,
                          ``turning_point``, ``synthesis``, ``closing``,
                          ``divider``, ``support``).
* ``tone``             — short emotional descriptor pulled from the
                          existing ``ArtDirection.mood`` and
                          ``DeckStrategy.tone`` (``serious``, ``polished``,
                          ``technical``, ``editorial``, ``calm``,
                          ``expressive``, ``neutral``).
* ``density``          — ``low`` | ``medium`` | ``high``. Derived from the
                          slide's content shape (number of bullets,
                          presence of stats/chart, quote length).
* ``communication_goal`` — one short verb phrase describing what the
                          slide wants to do. Derived from
                          ``narrative_role`` plus layout.

This module is intentionally:
* deterministic (no LLM, no network, no randomness),
* additive (the renderer ignores ``intent`` if it does not understand it),
* nullable (every field is optional; ``attach_slide_intent`` never raises).

The block is attached to every slide as ``slide["intent"] = {...}``. The
existing ``slide_schema.validate_deck`` does not require ``intent`` and
does not reject unknown top-level slide keys, so adding the block is
schema-safe with no migration.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("nexus.agent.slide_intent")


# ── Public field vocabularies ──────────────────────────────────────────────

NARRATIVE_ROLES: tuple[str, ...] = (
    "opening",
    "context",
    "evidence",
    "turning_point",
    "synthesis",
    "closing",
    "divider",
    "support",
)

DENSITIES: tuple[str, ...] = ("low", "medium", "high")

# Default tone when no signal is available. Mirrors the
# ``nexus_system_prompt`` default mood so the intent block agrees with
# what the writer prompt was told to do.
_DEFAULT_TONE = "neutral"


# ── Narrative-role inference ───────────────────────────────────────────────


def _role_for_position(position: int, total: int) -> str:
    """Default role purely from position when nothing else is known."""
    if total <= 1:
        return "opening"
    if position == 0:
        return "opening"
    if position == total - 1:
        return "closing"
    # Three-act pacing for the middle: context → evidence → synthesis.
    middle_progress = (position - 1) / max(total - 2, 1)
    if middle_progress < 0.34:
        return "context"
    if middle_progress < 0.67:
        return "evidence"
    return "synthesis"


def _role_from_arc(position: int, total: int, story_arc: list[str] | None) -> str:
    """Map the slide position into the strategy ``story_arc`` when available.

    ``DeckStrategy.story_arc`` is a short list of arc beats (e.g.
    ``["context", "finding", "evidence", "implication", "ask"]``). We map
    each beat to a canonical narrative role and stretch the arc evenly
    across the deck so a 5-beat arc on an 8-slide deck still produces a
    sensible role per slide.
    """
    if not story_arc:
        return _role_for_position(position, total)

    arc_to_role: dict[str, str] = {
        # Common Nexus arc beats (`DeckStrategy.story_arc` strings).
        "context": "context",
        "background": "context",
        "setup": "context",
        "intro": "opening",
        "introduction": "opening",
        "finding": "evidence",
        "findings": "evidence",
        "evidence": "evidence",
        "data": "evidence",
        "analysis": "evidence",
        "implication": "synthesis",
        "implications": "synthesis",
        "insight": "synthesis",
        "synthesis": "synthesis",
        "ask": "closing",
        "cta": "closing",
        "call to action": "closing",
        "summary": "closing",
        "conclusion": "closing",
        "turning point": "turning_point",
        "shift": "turning_point",
        "twist": "turning_point",
    }

    if position == 0:
        return "opening"
    if position == total - 1:
        return "closing"

    # Stretch the arc across the middle slides only (skip first + last).
    middle_idx = position - 1
    middle_total = max(total - 2, 1)
    arc_idx = min(int(middle_idx / middle_total * len(story_arc)), len(story_arc) - 1)
    beat = (story_arc[arc_idx] or "").strip().lower()
    return arc_to_role.get(beat, _role_for_position(position, total))


# ── Tone inference ─────────────────────────────────────────────────────────


def _tone_from_strategy(strategy_tone: str | None, art_mood: str | None) -> str:
    """Pick a single short tone word from strategy/art-direction inputs.

    ``DeckStrategy.tone`` is free text (e.g. ``"measured documentary"``).
    ``ArtDirection.mood`` is a short label (``"serious"`` / ``"polished"``
    / ``"technical"`` / ``"editorial"`` / ``"calm"`` / ``"expressive"`` /
    ``"neutral"``). Prefer the art-direction mood when present; fall back
    to a keyword scan over the strategy tone string.
    """
    if isinstance(art_mood, str) and art_mood.strip():
        return art_mood.strip().lower()

    text = (strategy_tone or "").strip().lower()
    if not text:
        return _DEFAULT_TONE

    keyword_to_tone: tuple[tuple[str, str], ...] = (
        ("documentary", "serious"),
        ("grave", "serious"),
        ("solemn", "serious"),
        ("polished", "polished"),
        ("confident", "polished"),
        ("technical", "technical"),
        ("analytical", "technical"),
        ("editorial", "editorial"),
        ("calm", "calm"),
        ("measured", "calm"),
        ("expressive", "expressive"),
        ("dramatic", "expressive"),
    )
    for kw, tone in keyword_to_tone:
        if kw in text:
            return tone
    return _DEFAULT_TONE


# ── Density inference ──────────────────────────────────────────────────────


def _density_from_content(slide: dict[str, Any]) -> str:
    """Heuristic: count text payload + child structures.

    The intent here is communicative, not metric: a quote slide with a
    long quote is ``high`` density; a closing slide with one CTA is
    ``low``; a 3-bullet slide with short bullets is ``medium``.
    """
    layout = slide.get("layout") or ""
    if layout == "title":
        return "low"
    if layout == "closing":
        # ``closing`` cards usually carry a CTA + short subtitle. Even a
        # busy closing slide reads as low density visually because there
        # is no list / chart / column structure.
        return "low"
    if layout == "quote":
        quote_len = len((slide.get("quote") or "").strip())
        if quote_len > 220:
            return "high"
        if quote_len > 80:
            return "medium"
        return "low"
    if layout == "stats":
        n = len([s for s in (slide.get("stats") or []) if isinstance(s, dict)])
        return "high" if n >= 3 else "medium"
    if layout == "chart":
        # A chart by itself is medium; with 6+ data points it reads as
        # higher density. We do not introspect chart_data deeply here.
        chart_data = slide.get("chart_data") or {}
        labels = chart_data.get("labels") or []
        return "high" if isinstance(labels, list) and len(labels) >= 6 else "medium"
    if layout == "two-col":
        cols = slide.get("columns") or []
        body_len = sum(len((c.get("body") or "")) for c in cols if isinstance(c, dict))
        return "high" if body_len > 320 else "medium"
    if layout == "bullets":
        bullets = [b for b in (slide.get("bullets") or []) if isinstance(b, str) and b.strip()]
        n = len(bullets)
        avg = sum(len(b) for b in bullets) / max(n, 1)
        if n >= 4 or avg > 90:
            return "high"
        if n >= 2:
            return "medium"
        return "low"
    return "medium"


# ── Communication goal inference ───────────────────────────────────────────

# Short verb-phrase per role × layout combination. The goal is a single
# sentence-fragment that the AI-reasoning panel renders verbatim.
_GOAL_BY_ROLE: dict[str, str] = {
    "opening": "set the stage and frame the topic",
    "context": "establish the necessary background",
    "evidence": "present the supporting facts",
    "turning_point": "mark the dramatic shift",
    "synthesis": "connect the evidence into an insight",
    "closing": "land the takeaway and close",
    "divider": "create a pause in the rhythm",
    "support": "supply additional detail",
}

_LAYOUT_GOAL_OVERRIDE: dict[str, str] = {
    "quote": "let a voice carry the moment",
    "chart": "show the trend in data",
    "stats": "anchor the case in numbers",
    "two-col": "compare two perspectives side by side",
}


def _goal_for(role: str, layout: str) -> str:
    if layout in _LAYOUT_GOAL_OVERRIDE:
        return _LAYOUT_GOAL_OVERRIDE[layout]
    return _GOAL_BY_ROLE.get(role, "advance the deck")


# ── Public API ─────────────────────────────────────────────────────────────


def derive_intent(
    slide: dict[str, Any],
    *,
    position: int,
    total: int,
    story_arc: list[str] | None = None,
    strategy_tone: str | None = None,
    art_mood: str | None = None,
    beat: str | None = None,
) -> dict[str, Any]:
    """Return a fresh ``intent`` dict for a single slide.

    Pure function — the input slide is never mutated. The output is
    JSON-serialisable. All four fields are always present so the
    frontend can rely on the shape; ``narrative_role`` and ``tone``
    fall back to safe defaults when no signal is available.

    Phase 6AD: when a canonical ``beat`` is supplied, it overrides the
    arc/position-derived ``narrative_role``. Beats come from
    :mod:`agent.narrative_beats` and are computed once per deck so all
    slides share a consistent dramatic shape.
    """
    layout = (slide.get("layout") or "").strip().lower() or "bullets"
    if beat:
        # Lazy import to avoid an import cycle if the beats module ever
        # needs to read intent metadata in the future.
        from agent.narrative_beats import role_from_beat
        role = role_from_beat(beat)
    else:
        role = _role_from_arc(position, total, story_arc)
    tone = _tone_from_strategy(strategy_tone, art_mood)
    density = _density_from_content(slide)
    goal = _goal_for(role, layout)
    intent: dict[str, Any] = {
        "narrative_role": role,
        "tone": tone,
        "density": density,
        "communication_goal": goal,
    }
    if beat:
        intent["beat"] = beat
    return intent


def attach_slide_intent(
    slides: list[dict[str, Any]],
    *,
    story_arc: list[str] | None = None,
    strategy_tone: str | None = None,
    art_mood: str | None = None,
    beats: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Attach an ``intent`` block to every slide. Idempotent and total.

    Mirrors the ``attach_research_sources_to_deck`` pattern from
    ``agent.source_grounding``: best-effort, never raises, returns a new
    list with each slide rebuilt as ``{**slide, "intent": ...}`` so the
    original list is not mutated. Slides that are not dicts pass through
    untouched.

    Phase 6AD: ``beats`` (one canonical beat per slide, length must
    match ``len(slides)``) is the new dramatic-shape signal. When
    supplied, each slide's ``narrative_role`` is derived from its beat
    instead of from arc / position. ``intent.beat`` is also stored on
    the slide so downstream consumers (UI panel, recommender) can read
    the beat directly without re-deriving it.
    """
    if not isinstance(slides, list) or not slides:
        return slides if isinstance(slides, list) else []

    # If beats were supplied but the length disagrees, drop them rather
    # than risk a misaligned per-slide assignment.
    if beats is not None and len(beats) != len(slides):
        logger.warning(
            "slide_intent.beats_length_mismatch",
            extra={"beats_len": len(beats), "slides_len": len(slides)},
        )
        beats = None

    out: list[dict[str, Any]] = []
    total = len(slides)
    for i, slide in enumerate(slides):
        if not isinstance(slide, dict):
            out.append(slide)
            continue
        try:
            intent = derive_intent(
                slide,
                position=i,
                total=total,
                story_arc=story_arc,
                strategy_tone=strategy_tone,
                art_mood=art_mood,
                beat=beats[i] if beats else None,
            )
            out.append({**slide, "intent": intent})
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("slide_intent.derive_failed", extra={"err": str(exc), "i": i})
            out.append(slide)
    return out


__all__ = [
    "NARRATIVE_ROLES",
    "DENSITIES",
    "derive_intent",
    "attach_slide_intent",
]
