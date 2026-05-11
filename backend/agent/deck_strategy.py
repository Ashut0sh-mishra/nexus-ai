"""Phase 6V — research-first deck strategy.

The pre-6V pipeline ran ``topic -> search -> planner -> slides`` with no
intermediate "what kind of deck is this" step. Decks therefore tended
to share the same structure: title, three bullets, two-col, stats,
chart, closing — even when the topic clearly called for a different
shape (a market-research report and a how-it-works explainer should
not look the same).

This module is the missing layer. ``build_deck_strategy`` derives a
:class:`DeckStrategy` from the topic, the (already-harvested) research
text, the harvested ``research_sources`` list, and the existing
:func:`agent.art_direction.infer_art_direction` output. It is
deterministic, dependency-light, and pure-Python:

* No LLM call. Strategy must be cheap and testable.
* No network. Sources have already been harvested by the loop.
* No randomness. Same inputs always produce the same strategy.

Reference projects we drew *ideas* from (no code, prompts, or templates
copied):

* **Manus**: surface a visible per-stage trace and an "artifact" object
  the rest of the run can read. ``DeckStrategy`` is that artifact.
* **OpenManus / Suna**: separate planner from executor; give the
  planner a richer typed context object instead of a raw research
  string. ``DeckStrategy`` is that context.
* **browser-use**: prefer evidence-first, observation-then-action
  shapes. The strategy records ``key_facts`` extracted from research
  and a ``research_quality`` honesty rating so the planner can adapt.
* **Presenton**: presentation-specific pipeline language ("story arc",
  "layout recipe"). We use those words but the implementation is
  NEXUS-native.
* **AgenticSeek**: routing-by-category. The :func:`_classify_deck_type`
  helper picks one of seven NEXUS-defined ``DeckType`` values from the
  topic text.

The strategy intentionally reuses the existing
:mod:`agent.art_direction` category system so we do not invent a second,
parallel taxonomy.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Final

from agent.art_direction import (
    CATEGORY_BUSINESS,
    CATEGORY_CONFLICT,
    CATEGORY_CREATIVE,
    CATEGORY_GENERIC,
    CATEGORY_HISTORY,
    CATEGORY_HUMAN,
    CATEGORY_TECHNICAL,
    ArtDirection,
)

logger = logging.getLogger("nexus.agent.deck_strategy")


# ── Public types ───────────────────────────────────────────────────────────

# NEXUS-native deck types. Distinct from art-direction categories because a
# *single* art category (e.g. business) can host many deck shapes (pitch,
# market-research report, internal status update). Strategy chooses both
# axes independently.
DECK_TYPE_RESEARCH_REPORT: Final = "research_report"
DECK_TYPE_PITCH: Final = "pitch"
DECK_TYPE_EXPLAINER: Final = "explainer"
DECK_TYPE_CASE_STUDY: Final = "case_study"
DECK_TYPE_BRIEFING: Final = "briefing"
DECK_TYPE_HOW_TO: Final = "how_to"
DECK_TYPE_OVERVIEW: Final = "overview"

DECK_TYPES: tuple[str, ...] = (
    DECK_TYPE_RESEARCH_REPORT,
    DECK_TYPE_PITCH,
    DECK_TYPE_EXPLAINER,
    DECK_TYPE_CASE_STUDY,
    DECK_TYPE_BRIEFING,
    DECK_TYPE_HOW_TO,
    DECK_TYPE_OVERVIEW,
)


@dataclass(frozen=True)
class DeckStrategy:
    """Structured pre-plan artifact consumed by the planner and generator.

    All fields are JSON-serialisable (lists / dicts of primitives) so the
    object can be persisted as a step record or surfaced via SSE without
    custom encoding. ``layout_recipe`` is a planner *hint*, not a hard
    constraint — the planner is free to use a different layout per
    slide as long as it respects the requested slide count and
    first-slide / last-slide rules.
    """

    deck_type: str
    audience: str
    thesis: str
    story_arc: list[str]
    tone: str
    visual_direction: str
    layout_recipe: list[str]
    research_questions: list[str]
    key_facts: list[str]
    source_notes: list[str]
    image_style: str
    chart_guidance: str
    research_quality: str  # "rich" | "thin" | "none"

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable view used for logging / SSE / step records."""
        return asdict(self)


# ── Inputs / heuristics ────────────────────────────────────────────────────


# Signal keywords for classifying the *shape* of the deck (not the
# subject domain — that lives in ``art_direction``). Order matters: the
# first deck type whose keyword set scores highest wins; ties resolve to
# the order below so the most specific shapes outrank generic overview.
_DECK_TYPE_KEYWORDS: tuple[tuple[str, frozenset[str]], ...] = (
    (
        DECK_TYPE_RESEARCH_REPORT,
        frozenset(
            {
                "market",
                "research",
                "analysis",
                "report",
                "industry",
                "competitor",
                "competitive",
                "landscape",
                "outlook",
                "forecast",
                "size",
                "growth",
                "share",
                "tam",
                "sam",
                "som",
            }
        ),
    ),
    (
        DECK_TYPE_PITCH,
        frozenset(
            {
                "pitch",
                "investor",
                "investors",
                "fundraise",
                "fundraising",
                "seed",
                "series",
                "round",
                "deck",
                "startup",
                "valuation",
                "raise",
            }
        ),
    ),
    (
        DECK_TYPE_CASE_STUDY,
        frozenset(
            {
                "case",
                "study",
                "post-mortem",
                "postmortem",
                "incident",
                "retrospective",
                "lessons",
                "outcome",
                "results from",
            }
        ),
    ),
    (
        DECK_TYPE_BRIEFING,
        frozenset(
            {
                "briefing",
                "brief",
                "status",
                "update",
                "weekly",
                "monthly",
                "quarterly",
                "review",
                "summary",
                "stakeholder",
                "board",
                "exec",
                "executive",
            }
        ),
    ),
    (
        DECK_TYPE_HOW_TO,
        frozenset(
            {
                "how to",
                "step-by-step",
                "step by step",
                "guide",
                "tutorial",
                "walkthrough",
                "playbook",
                "implementation",
                "setup",
                "deploy",
                "deploying",
            }
        ),
    ),
    (
        DECK_TYPE_EXPLAINER,
        frozenset(
            {
                "what is",
                "introduction to",
                "intro to",
                "explained",
                "explainer",
                "primer",
                "fundamentals",
                "basics",
                "concepts",
                "how it works",
            }
        ),
    ),
)


# Per-deck-type recipe. Length is a *target*, not a hard count — the
# loop already enforces the user-requested ``slide_count``. The recipe
# tells the planner the *order* it should aim for; the planner is free
# to repeat or skip items to fit the requested length.
_LAYOUT_RECIPES: dict[str, list[str]] = {
    DECK_TYPE_RESEARCH_REPORT: [
        "title",
        "bullets",  # context / why this matters
        "stats",  # market sizing
        "chart",  # trend
        "two-col",  # competitive view
        "bullets",  # key findings
        "quote",  # external voice
        "two-col",  # implications / risks
        "closing",
    ],
    DECK_TYPE_PITCH: [
        "title",
        "two-col",  # problem / opportunity
        "bullets",  # solution
        "stats",  # traction
        "chart",  # growth
        "bullets",  # business model
        "two-col",  # team / GTM
        "closing",  # ask
    ],
    DECK_TYPE_EXPLAINER: [
        "title",
        "bullets",  # what it is
        "two-col",  # how it works
        "bullets",  # building blocks
        "quote",  # canonical voice
        "stats",  # scale / impact
        "two-col",  # use cases vs limitations
        "closing",
    ],
    DECK_TYPE_CASE_STUDY: [
        "title",
        "bullets",  # context
        "two-col",  # situation / complication
        "stats",  # metrics
        "chart",  # before / after
        "quote",  # principal voice
        "bullets",  # lessons learned
        "closing",
    ],
    DECK_TYPE_BRIEFING: [
        "title",
        "stats",  # the headline numbers
        "bullets",  # what changed
        "chart",  # trend or comparison
        "two-col",  # risks / opportunities
        "bullets",  # next steps
        "closing",
    ],
    DECK_TYPE_HOW_TO: [
        "title",
        "bullets",  # prerequisites
        "two-col",  # step 1 / step 2
        "two-col",  # step 3 / step 4
        "bullets",  # validation / verification
        "quote",  # tip
        "closing",
    ],
    DECK_TYPE_OVERVIEW: [
        "title",
        "bullets",
        "two-col",
        "stats",
        "chart",
        "quote",
        "two-col",
        "closing",
    ],
}


# Story arc by deck type. Free-form short phrases the planner can use
# verbatim in slide ``intent`` fields. Kept terse so ``slides_user_message``
# can include them without blowing token budgets.
_STORY_ARCS: dict[str, list[str]] = {
    DECK_TYPE_RESEARCH_REPORT: [
        "frame the question",
        "size the market",
        "show the trend",
        "compare the players",
        "surface findings",
        "external corroboration",
        "implications",
        "what to do",
    ],
    DECK_TYPE_PITCH: [
        "hook",
        "problem",
        "solution",
        "traction",
        "growth",
        "model",
        "team",
        "ask",
    ],
    DECK_TYPE_EXPLAINER: [
        "open the question",
        "define the thing",
        "show how it works",
        "name the parts",
        "ground it in a real voice",
        "scale and stakes",
        "use vs limits",
        "summarise",
    ],
    DECK_TYPE_CASE_STUDY: [
        "set the scene",
        "context",
        "situation and complication",
        "metrics",
        "before and after",
        "voice of the protagonist",
        "lessons",
        "wrap",
    ],
    DECK_TYPE_BRIEFING: [
        "headline",
        "the numbers",
        "what changed",
        "trend",
        "risks vs opportunities",
        "next steps",
        "close",
    ],
    DECK_TYPE_HOW_TO: [
        "open",
        "what you need",
        "first half of the procedure",
        "second half of the procedure",
        "verify it worked",
        "tip",
        "wrap",
    ],
    DECK_TYPE_OVERVIEW: [
        "open",
        "context",
        "key dimensions",
        "scale",
        "trend",
        "voice",
        "perspectives",
        "wrap",
    ],
}


_TONE_BY_ART_CATEGORY: dict[str, str] = {
    CATEGORY_CONFLICT: "measured, documentary, no triumphalism",
    CATEGORY_BUSINESS: "confident, plain, evidence-driven",
    CATEGORY_TECHNICAL: "precise, neutral, cite numbers",
    CATEGORY_HISTORY: "calm, narrative, anchored in dates",
    CATEGORY_HUMAN: "warm, careful, person-first language",
    CATEGORY_CREATIVE: "bold, vivid, opinionated",
    CATEGORY_GENERIC: "clear, plain, no hype",
}


_IMAGE_STYLE_BY_ART_CATEGORY: dict[str, str] = {
    CATEGORY_CONFLICT: "documentary photography, muted tones, no graphic violence",
    CATEGORY_BUSINESS: "clean editorial photography, modern offices, dataviz overlays",
    CATEGORY_TECHNICAL: "minimal abstract diagrams, schematic line art, no stock people",
    CATEGORY_HISTORY: "archival photography, sepia or duotone, period-correct",
    CATEGORY_HUMAN: "candid documentary photography, real people, soft daylight",
    CATEGORY_CREATIVE: "high-contrast editorial illustration, brand-leaning",
    CATEGORY_GENERIC: "clean editorial photography, neutral backgrounds",
}


# ── Public API ─────────────────────────────────────────────────────────────


def build_deck_strategy(
    *,
    topic: str,
    slide_count: int,
    art_direction: ArtDirection | None,
    research: str | None,
    research_sources: list[dict[str, Any]] | None,
) -> DeckStrategy:
    """Derive a :class:`DeckStrategy` from the harvested inputs.

    All inputs are optional except ``topic``. Missing inputs degrade
    gracefully — e.g. with no research the strategy still produces a
    valid plan, marks ``research_quality="none"`` and emits empty
    ``key_facts`` / ``source_notes`` so the caller knows the deck will
    rely on the planner / LLM rather than evidence.
    """

    safe_topic = (topic or "").strip()
    deck_type = _classify_deck_type(safe_topic)
    art_cat = (art_direction.category if art_direction else CATEGORY_GENERIC) or CATEGORY_GENERIC
    if art_cat == "explicit":
        # User picked a theme but we still need a tone bucket. Default
        # to the generic neutral tone rather than guessing.
        art_cat = CATEGORY_GENERIC

    audience = _infer_audience(deck_type, safe_topic)
    thesis = _build_thesis(safe_topic, deck_type)
    story_arc = list(_STORY_ARCS.get(deck_type, _STORY_ARCS[DECK_TYPE_OVERVIEW]))
    tone = _TONE_BY_ART_CATEGORY.get(art_cat, _TONE_BY_ART_CATEGORY[CATEGORY_GENERIC])
    visual_direction = _build_visual_direction(art_direction, deck_type)
    layout_recipe = _select_layout_recipe(deck_type, slide_count)
    questions = _build_research_questions(safe_topic, deck_type)

    research_text = (research or "").strip()
    sources = research_sources or []
    key_facts = _extract_key_facts(research_text)
    source_notes = _summarise_sources(sources)
    research_quality = _rate_research_quality(research_text, sources)

    image_style = _IMAGE_STYLE_BY_ART_CATEGORY.get(
        art_cat, _IMAGE_STYLE_BY_ART_CATEGORY[CATEGORY_GENERIC]
    )
    chart_guidance = _build_chart_guidance(deck_type, key_facts)

    strategy = DeckStrategy(
        deck_type=deck_type,
        audience=audience,
        thesis=thesis,
        story_arc=story_arc,
        tone=tone,
        visual_direction=visual_direction,
        layout_recipe=layout_recipe,
        research_questions=questions,
        key_facts=key_facts,
        source_notes=source_notes,
        image_style=image_style,
        chart_guidance=chart_guidance,
        research_quality=research_quality,
    )
    logger.info(
        "deck_strategy.built",
        extra={
            "deck_type": deck_type,
            "audience": audience,
            "research_quality": research_quality,
            "key_fact_count": len(key_facts),
            "source_count": len(source_notes),
        },
    )
    return strategy


def render_strategy_for_planner(strategy: DeckStrategy) -> str:
    """Compact human-readable rendering used inside planner / slide prompts.

    The render is small (a few short lines) so it does not blow LLM
    context on top of the existing research block. Each section is
    prefixed with a stable label so the LLM and downstream parsers can
    address them by name.
    """
    arc = " -> ".join(strategy.story_arc) if strategy.story_arc else "(none)"
    recipe = ", ".join(strategy.layout_recipe) if strategy.layout_recipe else "(none)"
    facts = "\n".join(f"  - {f}" for f in strategy.key_facts[:6]) or "  - (none yet)"
    questions = "\n".join(f"  - {q}" for q in strategy.research_questions[:6]) or "  - (none)"
    sources = "\n".join(f"  - {s}" for s in strategy.source_notes[:6]) or "  - (none)"
    return (
        f"Deck strategy:\n"
        f"  type: {strategy.deck_type}\n"
        f"  audience: {strategy.audience}\n"
        f"  thesis: {strategy.thesis}\n"
        f"  tone: {strategy.tone}\n"
        f"  visual_direction: {strategy.visual_direction}\n"
        f"  story_arc: {arc}\n"
        f"  layout_recipe: {recipe}\n"
        f"  image_style: {strategy.image_style}\n"
        f"  chart_guidance: {strategy.chart_guidance}\n"
        f"  research_quality: {strategy.research_quality}\n"
        f"Research questions:\n{questions}\n"
        f"Key facts:\n{facts}\n"
        f"Source notes:\n{sources}"
    )


# ── Internal helpers ───────────────────────────────────────────────────────


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _classify_deck_type(topic: str) -> str:
    if not topic:
        return DECK_TYPE_OVERVIEW
    norm = _normalize(topic)
    best = DECK_TYPE_OVERVIEW
    best_score = 0
    for deck_type, kws in _DECK_TYPE_KEYWORDS:
        score = 0
        for kw in kws:
            if " " in kw:
                if kw in norm:
                    score += 1
            else:
                if re.search(rf"\b{re.escape(kw)}\b", norm):
                    score += 1
        if score > best_score:
            best_score = score
            best = deck_type
    return best


def _infer_audience(deck_type: str, topic: str) -> str:
    if deck_type == DECK_TYPE_PITCH:
        return "investors and prospective partners"
    if deck_type == DECK_TYPE_RESEARCH_REPORT:
        return "decision-makers evaluating a market or option"
    if deck_type == DECK_TYPE_BRIEFING:
        return "executives or stakeholders catching up quickly"
    if deck_type == DECK_TYPE_HOW_TO:
        return "practitioners following along to implement something"
    if deck_type == DECK_TYPE_CASE_STUDY:
        return "peers learning from a concrete past project"
    if deck_type == DECK_TYPE_EXPLAINER:
        return "curious non-experts who want to understand the topic"
    return "a general professional audience"


def _build_thesis(topic: str, deck_type: str) -> str:
    t = topic.strip() or "the topic"
    if deck_type == DECK_TYPE_RESEARCH_REPORT:
        return f"What the data says about {t}, and what to do with it."
    if deck_type == DECK_TYPE_PITCH:
        return f"Why {t} is a fundable opportunity right now."
    if deck_type == DECK_TYPE_EXPLAINER:
        return f"What {t} actually is and how it works in plain language."
    if deck_type == DECK_TYPE_CASE_STUDY:
        return f"What {t} teaches that generalises beyond this one case."
    if deck_type == DECK_TYPE_BRIEFING:
        return f"What changed in {t} this period and why it matters."
    if deck_type == DECK_TYPE_HOW_TO:
        return f"A reliable, repeatable way to {t}."
    return f"A grounded perspective on {t}."


def _build_visual_direction(art: ArtDirection | None, deck_type: str) -> str:
    if art is None:
        base = "clean editorial layout, restrained accent colour"
    else:
        base = f"{art.theme} theme, mood {art.mood}"
    density = {
        DECK_TYPE_RESEARCH_REPORT: "data-dense; favour charts and stats over hero photos",
        DECK_TYPE_PITCH: "high-contrast hero slides; one clear number per slide",
        DECK_TYPE_EXPLAINER: "diagram-friendly; avoid heavy stats unless meaningful",
        DECK_TYPE_CASE_STUDY: "before/after pairings; one strong quote",
        DECK_TYPE_BRIEFING: "scan-first; large numbers; minimal prose",
        DECK_TYPE_HOW_TO: "step grids; numbered structure; minimal photography",
        DECK_TYPE_OVERVIEW: "balanced mix of stats, charts and prose",
    }.get(deck_type, "balanced mix of stats, charts and prose")
    return f"{base}; {density}"


def _select_layout_recipe(deck_type: str, slide_count: int) -> list[str]:
    base = list(_LAYOUT_RECIPES.get(deck_type, _LAYOUT_RECIPES[DECK_TYPE_OVERVIEW]))
    if slide_count <= 0:
        return base
    if slide_count == len(base):
        return base
    if slide_count < len(base):
        # Drop from the middle, keep the open and the close.
        keep = [base[0]] + base[1 : 1 + (slide_count - 2)] + [base[-1]]
        return keep[:slide_count]
    # slide_count > len(base) — pad the middle with bullets/two-col
    # alternation so we never repeat the same layout three times in a
    # row when stretching a recipe.
    pad_pool = ["bullets", "two-col"]
    out = base[:-1]
    while len(out) + 1 < slide_count:
        out.append(pad_pool[len(out) % len(pad_pool)])
    out.append(base[-1])
    return out


def _build_research_questions(topic: str, deck_type: str) -> list[str]:
    t = topic.strip() or "the topic"
    common = [
        f"What are the most-cited recent figures on {t}?",
        f"Which credible sources cover {t} in depth?",
    ]
    by_type = {
        DECK_TYPE_RESEARCH_REPORT: [
            f"What is the size and growth rate of {t}?",
            f"Who are the leading and emerging players in {t}?",
            f"What recent inflection points have changed {t}?",
        ],
        DECK_TYPE_PITCH: [
            f"What pain point does {t} solve, with evidence?",
            f"What traction or comparable benchmarks exist for {t}?",
        ],
        DECK_TYPE_EXPLAINER: [
            f"What concrete mechanism makes {t} work?",
            f"What everyday analogy helps a non-expert understand {t}?",
        ],
        DECK_TYPE_CASE_STUDY: [
            f"What measurable outcomes does {t} report?",
            f"What did {t} explicitly try and reject before settling on its answer?",
        ],
        DECK_TYPE_BRIEFING: [
            f"What changed in {t} this period?",
            f"What metric most clearly tracks the change in {t}?",
        ],
        DECK_TYPE_HOW_TO: [
            f"What are the prerequisites for {t}?",
            f"Where do most practitioners get stuck in {t}?",
        ],
        DECK_TYPE_OVERVIEW: [
            f"What matters most to know about {t} in five minutes?",
        ],
    }
    return common + by_type.get(deck_type, [])


# Match a number followed by an optional unit/suffix and at least a few
# context words afterwards. Captures "$4.2 trillion in 2024 revenue", "93% of users",
# "3.5x faster", etc. This is a lossy heuristic — the planner LLM is the
# one that ultimately uses the facts; this just gives it a starting list.
_FACT_RE = re.compile(
    r"(?P<num>(?:\$|€|£)?\d[\d,]*(?:\.\d+)?\s*"
    r"(?:%|x|bn|m|k|mw|gw|kwh|tb|gb|°c|°f|trillion|billion|million|thousand)?)"
    r"\s+[A-Za-z][\w\- ]{4,80}",
    re.IGNORECASE,
)


def _extract_key_facts(research_text: str) -> list[str]:
    if not research_text:
        return []
    facts: list[str] = []
    seen: set[str] = set()
    # Operate on the first ~4k chars; anything beyond that rarely
    # surfaces useful figures and the regex cost stays predictable.
    sample = research_text[:4000]
    for m in _FACT_RE.finditer(sample):
        # Build a short, normalised fact phrase: take ~120 chars from
        # the match start. Strip trailing punctuation.
        start = m.start()
        end = min(start + 120, len(sample))
        phrase = sample[start:end].strip().rstrip(".,;:")
        # Single-line; collapse whitespace and trim trailing fragments
        # at sentence boundaries so we don't carry unrelated words.
        phrase = re.sub(r"\s+", " ", phrase)
        # Split on sentence-terminating punctuation (period followed by
        # whitespace) so we don't truncate decimals like "$4.2 trillion".
        m_end = re.search(r"[.!?]\s", phrase)
        if m_end:
            phrase = phrase[: m_end.start()]
        if len(phrase) < 10:
            continue
        norm = phrase.lower()
        if norm in seen:
            continue
        seen.add(norm)
        facts.append(phrase)
        if len(facts) >= 8:
            break
    return facts


def _summarise_sources(sources: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen_urls: set[str] = set()
    for src in sources or []:
        if not isinstance(src, dict):
            continue
        url = str(src.get("url") or "").strip()
        title = str(src.get("title") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        host = ""
        if url:
            m = re.search(r"https?://([^/]+)/?", url)
            if m:
                host = m.group(1)
        label_bits = [b for b in (title, host) if b]
        if not label_bits:
            continue
        out.append(" — ".join(label_bits)[:160])
        if len(out) >= 8:
            break
    return out


def _rate_research_quality(text: str, sources: list[dict[str, Any]]) -> str:
    src_count = sum(1 for s in (sources or []) if isinstance(s, dict))
    text_len = len(text or "")
    if src_count == 0 and text_len == 0:
        return "none"
    if src_count >= 3 or text_len >= 500:
        return "rich"
    return "thin"


def _build_chart_guidance(deck_type: str, key_facts: list[str]) -> str:
    has_numbers = any(re.search(r"\d", f) for f in key_facts)
    if deck_type in {
        DECK_TYPE_RESEARCH_REPORT,
        DECK_TYPE_BRIEFING,
        DECK_TYPE_PITCH,
    }:
        if has_numbers:
            return (
                "Include one chart slide. Prefer a bar or line chart with "
                "labels drawn from the harvested key facts. Cite the source "
                "in chart_data.source."
            )
        return (
            "Include one chart slide if a defensible trend or comparison "
            "exists; otherwise prefer a stats slide with cited values."
        )
    if deck_type == DECK_TYPE_CASE_STUDY:
        return "If a chart is included, make it before/after — two-bar comparison."
    if deck_type == DECK_TYPE_EXPLAINER:
        return "Charts optional; only include one if it clarifies a mechanism."
    if deck_type == DECK_TYPE_HOW_TO:
        return "Skip charts unless a verification metric is genuinely useful."
    return "Use a chart only when it adds information beyond the prose."


__all__ = [
    "DECK_TYPES",
    "DECK_TYPE_RESEARCH_REPORT",
    "DECK_TYPE_PITCH",
    "DECK_TYPE_EXPLAINER",
    "DECK_TYPE_CASE_STUDY",
    "DECK_TYPE_BRIEFING",
    "DECK_TYPE_HOW_TO",
    "DECK_TYPE_OVERVIEW",
    "DeckStrategy",
    "build_deck_strategy",
    "render_strategy_for_planner",
]
