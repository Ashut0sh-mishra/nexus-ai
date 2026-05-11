"""Phase 6M — deterministic topic-aware art direction.

Given a free-text topic and an optional user-supplied theme, return a
fitting visual direction for the generated deck. Pure-Python and
deterministic: no LLM, no network, no randomness, no filesystem writes.

Why this exists
---------------
Before Phase 6M, every generated deck rendered with the frontend's
``light-pro`` template (bright white + amber/orange accent) regardless
of subject. That looked wrong for serious topics — a deck about armed
conflict, geopolitics, or crisis response should not look like a startup
pitch. This helper picks one of the existing renderable theme names so a
**war/conflict** topic gets a restrained documentary palette while
**business/sales** keeps its polished corporate look.

Contract
--------
The selected ``theme`` is one of the legacy display-name strings that
both the frontend ``SlideRenderer.themePalettes`` and the backend
``services.export_service.THEMES`` already render: ``"light-pro"``,
``"Editorial"``, ``"Pixel"``, ``"Vellum"``, or ``"Dossier"``. This means
art-direction never breaks rendering or export — every value it can
return is already known to both surfaces. The companion ``theme_id`` is
the canonical Phase-6L registry id, useful for downstream tooling.

Inference triggers when the user has not made an explicit choice. By
convention an empty string ``""``, ``"auto"`` (case-insensitive), or
``None`` mean "auto". Any other value is respected verbatim and only
``mood`` / ``rationale`` are added.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final


# Stable category ids surfaced in ``ArtDirection.category`` and exposed
# as a public constant so tests and downstream consumers can refer to
# them without string-matching.
CATEGORY_CONFLICT: Final = "conflict"
CATEGORY_BUSINESS: Final = "business"
CATEGORY_TECHNICAL: Final = "technical"
CATEGORY_HISTORY: Final = "history"
CATEGORY_HUMAN: Final = "human"
CATEGORY_CREATIVE: Final = "creative"
CATEGORY_GENERIC: Final = "generic"


# Sentinel values that mean "infer from topic". Any other supplied
# ``theme`` is treated as an explicit user override.
_AUTO_SENTINELS: frozenset[str] = frozenset({"", "auto"})

# Themes that the user historically got as a default but that look wrong
# for serious topics. We do NOT auto-override these silently — explicit
# is explicit. They are listed here only for documentation.
_LEGACY_DEFAULTS_FOR_REFERENCE: frozenset[str] = frozenset({"light-pro", "Editorial"})


@dataclass(frozen=True)
class ArtDirection:
    """Resolved visual direction for a deck.

    Attributes
    ----------
    theme:
        Legacy display-name string for the renderer. One of
        ``light-pro``, ``Editorial``, ``Pixel``, ``Vellum``, ``Dossier``.
    theme_id:
        Canonical Phase-6L registry id (``nexus-default``,
        ``nexus-light``).
    mood:
        Short lowercase mood label (``"serious"``, ``"polished"``, ...).
    rationale:
        One-sentence explanation of why the theme was chosen, suitable
        for surfacing to the user or logging into a step record.
    category:
        One of the ``CATEGORY_*`` constants, or ``"explicit"`` when the
        user supplied a non-default theme verbatim.
    palette_hint:
        Short tuple of accent colors that downstream renderers MAY use
        for charts or accents. The renderer's existing per-theme palette
        is the source of truth; this is a recommendation only.
    """

    theme: str
    theme_id: str
    mood: str
    rationale: str
    category: str
    palette_hint: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "theme": self.theme,
            "theme_id": self.theme_id,
            "mood": self.mood,
            "rationale": self.rationale,
            "category": self.category,
            "palette_hint": list(self.palette_hint),
        }


# ── Keyword corpora per category ──────────────────────────────────────────
# Word boundaries are added at match time. Order matters only for
# tie-breaking (see ``_select_category``); the first category in this
# list wins on a tie so ``conflict`` outranks ``business`` for "war
# economy" prompts.

_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        CATEGORY_CONFLICT,
        (
            "war", "wars", "warfare", "conflict", "conflicts", "battle",
            "battles", "combat", "military", "army", "soldier", "soldiers",
            "weapon", "weapons", "missile", "missiles", "drone strike",
            "geopolitics", "geopolitical", "invasion", "invaded", "siege",
            "ceasefire", "armed", "insurgency", "terrorism", "terrorist",
            "genocide", "atrocity", "atrocities", "refugee", "refugees",
            "humanitarian crisis", "casualties", "casualty", "ukraine",
            "russia", "gaza", "syria", "yemen", "afghanistan", "iraq",
            "nato", "ww2", "wwii", "world war", "cold war",
        ),
    ),
    (
        CATEGORY_BUSINESS,
        (
            "business", "company", "startup", "startups", "saas", "b2b",
            "b2c", "sales", "marketing funnel", "go-to-market", "go to market",
            "gtm", "pitch", "pitch deck", "investor", "investors", "vc",
            "venture", "fundraising", "fundraise", "series a", "series b",
            "ipo", "revenue", "arr", "mrr", "kpi", "kpis", "okrs",
            "product launch", "launching", "growth strategy", "p&l",
            "profit", "profitability", "ebitda", "valuation", "roi",
        ),
    ),
    (
        CATEGORY_TECHNICAL,
        (
            "ai", "artificial intelligence", "machine learning", "ml",
            "deep learning", "neural network", "neural networks",
            "transformer", "transformers", "llm", "llms",
            "language model", "language models", "foundation model",
            "foundation models", "data science", "data engineering",
            "algorithm", "algorithms", "research paper", "physics",
            "chemistry", "biology", "genomics", "neuroscience", "robotics",
            "quantum", "quantum computing", "kubernetes",
            "cloud architecture", "infrastructure", "devops", "engineering",
            "compiler", "operating system", "cybersecurity", "cryptography",
            "blockchain", "semiconductor",
        ),
    ),
    (
        CATEGORY_HISTORY,
        (
            "history", "historical", "ancient", "medieval", "renaissance",
            "revolution", "empire", "dynasty", "civilization", "archaeology",
            "literature", "philosophy", "education", "curriculum", "lesson",
            "lecture", "syllabus", "textbook", "classroom",
        ),
    ),
    (
        CATEGORY_HUMAN,
        (
            "healthcare", "health care", "medicine", "medical", "clinical",
            "patient", "patients", "hospital", "nursing", "public health",
            "epidemic", "pandemic", "vaccine", "vaccines", "mental health",
            "wellness", "climate", "climate change", "sustainability",
            "renewable", "renewables", "carbon", "emissions", "biodiversity",
            "ecology", "environment", "social impact", "nonprofit", "ngo",
            "poverty", "inequality", "human rights", "community",
        ),
    ),
    (
        CATEGORY_CREATIVE,
        (
            "design", "designer", "branding", "brand", "creative",
            "advertising", "ad campaign", "marketing campaign", "fashion",
            "art", "artist", "music", "film", "filmmaking", "photography",
            "typography", "illustration", "ux", "ui", "product design",
            "storytelling",
        ),
    ),
)


# Mapping from category to (theme_legacy_name, theme_id, mood, palette_hint).
# Theme names are restricted to those rendered by both the frontend
# ``SlideRenderer.themePalettes`` and the backend
# ``services.export_service.THEMES`` so every art direction is renderable
# without a renderer change.
_CATEGORY_DIRECTION: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    # Dark navy/blue intelligence-brief look. Restrained, no orange, no
    # bright purple. Reads as serious / documentary.
    CATEGORY_CONFLICT: (
        "Dossier",
        "nexus-default",
        "serious",
        ("#60A5FA", "#94A3B8", "#E2E8F0"),
    ),
    # Light, polished, professional corporate. Amber accent on white.
    CATEGORY_BUSINESS: (
        "light-pro",
        "nexus-light",
        "polished",
        ("#F59E0B", "#111827", "#6B7280"),
    ),
    # Cool dark, green-cyan tech accent. Reads as precise / engineering.
    CATEGORY_TECHNICAL: (
        "Pixel",
        "nexus-default",
        "technical",
        ("#34D399", "#94A3B8", "#F1FAEE"),
    ),
    # Warm paper, serif headings. Reads as editorial / textbook.
    CATEGORY_HISTORY: (
        "Vellum",
        "nexus-light",
        "editorial",
        ("#A0522D", "#6B5E4A", "#1F1A14"),
    ),
    # Warm but calm — same Vellum surface, different mood label so the
    # rationale reads correctly for healthcare / climate / social-impact.
    CATEGORY_HUMAN: (
        "Vellum",
        "nexus-light",
        "calm",
        ("#A0522D", "#6B5E4A", "#1F1A14"),
    ),
    # Expressive purple accent on dark editorial surface.
    CATEGORY_CREATIVE: (
        "Editorial",
        "nexus-default",
        "expressive",
        ("#A78BFA", "#9A9AA5", "#F5F5F7"),
    ),
    # Generic fallback — same as the prior default; documented so it is
    # explicit rather than implicit.
    CATEGORY_GENERIC: (
        "Editorial",
        "nexus-default",
        "neutral",
        ("#A78BFA", "#9A9AA5", "#F5F5F7"),
    ),
}


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _count_keyword_hits(topic_norm: str, keywords: tuple[str, ...]) -> int:
    hits = 0
    for kw in keywords:
        # Use word-boundary matching for single tokens, substring matching
        # for multi-word phrases. ``re.escape`` guards against any future
        # metacharacters in the corpora.
        if " " in kw:
            if kw in topic_norm:
                hits += 1
        else:
            if re.search(rf"\b{re.escape(kw)}\b", topic_norm):
                hits += 1
    return hits


def _select_category(topic: str) -> str:
    """Return the best category id for ``topic`` (or ``CATEGORY_GENERIC``).

    Deterministic: the score is the number of keyword hits per category;
    on a tie, the category that appears first in ``_CATEGORY_KEYWORDS``
    wins, so e.g. ``conflict`` outranks ``business`` for "war economy".
    """

    if not topic or not topic.strip():
        return CATEGORY_GENERIC

    norm = _normalize(topic)
    best_cat = CATEGORY_GENERIC
    best_score = 0
    for cat, kws in _CATEGORY_KEYWORDS:
        score = _count_keyword_hits(norm, kws)
        if score > best_score:
            best_cat = cat
            best_score = score
    return best_cat


def _is_auto(theme: str | None) -> bool:
    if theme is None:
        return True
    return theme.strip().lower() in _AUTO_SENTINELS


def _direction_for_category(cat: str, *, topic: str) -> ArtDirection:
    theme, theme_id, mood, palette = _CATEGORY_DIRECTION[cat]
    rationale = _RATIONALE_BY_CATEGORY[cat].format(
        theme=theme, mood=mood, topic_preview=topic.strip()[:80] or "your topic",
    )
    return ArtDirection(
        theme=theme,
        theme_id=theme_id,
        mood=mood,
        rationale=rationale,
        category=cat,
        palette_hint=palette,
    )


_RATIONALE_BY_CATEGORY: dict[str, str] = {
    CATEGORY_CONFLICT: (
        "Topic reads as conflict / geopolitics / crisis; chose {theme} "
        "for a {mood}, restrained documentary look instead of a bright "
        "default template."
    ),
    CATEGORY_BUSINESS: (
        "Topic reads as business / sales / startup; chose {theme} for a "
        "clean, {mood} corporate look."
    ),
    CATEGORY_TECHNICAL: (
        "Topic reads as science / technology / AI / research; chose "
        "{theme} for a cool, {mood} surface."
    ),
    CATEGORY_HISTORY: (
        "Topic reads as education / history; chose {theme} for a warm, "
        "readable {mood} surface."
    ),
    CATEGORY_HUMAN: (
        "Topic reads as healthcare / climate / social impact; chose "
        "{theme} for a warm, {mood}, trustworthy surface."
    ),
    CATEGORY_CREATIVE: (
        "Topic reads as creative / design / marketing; chose {theme} "
        "for a higher-contrast, {mood} surface."
    ),
    CATEGORY_GENERIC: (
        "Topic did not match a curated category; kept {theme} as the "
        "{mood} default."
    ),
}


def infer_art_direction(topic: str, theme: str | None = None) -> ArtDirection:
    """Resolve the art direction for a deck.

    Parameters
    ----------
    topic:
        The free-text deck topic from the user. Empty / whitespace input
        is allowed and resolves to the generic default.
    theme:
        Optional user-supplied theme. ``None``, ``""`` and ``"auto"``
        (case-insensitive, whitespace-tolerant) trigger inference. Any
        other value is treated as an explicit override and is returned
        verbatim with a generic ``mood`` / ``rationale``.

    Returns
    -------
    ArtDirection
        Frozen dataclass with ``theme`` (legacy display name),
        ``theme_id`` (Phase-6L registry id), ``mood``, ``rationale``,
        ``category``, and a ``palette_hint`` tuple.
    """

    if not _is_auto(theme):
        # Respect explicit user choice. Resolve theme_id best-effort via
        # the registry's legacy alias map; on miss, fall back to the
        # default registry id. This never raises.
        from agent.themes_registry import (
            DEFAULT_THEME_ID,
            LEGACY_THEME_ALIASES,
            BUILTIN_THEMES,
        )

        explicit = theme.strip()  # type: ignore[union-attr]
        norm = explicit.lower()
        if norm in BUILTIN_THEMES:
            theme_id = norm
        else:
            theme_id = LEGACY_THEME_ALIASES.get(norm, DEFAULT_THEME_ID)
        return ArtDirection(
            theme=explicit,
            theme_id=theme_id,
            mood="explicit",
            rationale=(
                f"User explicitly selected theme {explicit!r}; "
                "art-direction inference skipped."
            ),
            category="explicit",
            palette_hint=(),
        )

    cat = _select_category(topic)
    return _direction_for_category(cat, topic=topic)


__all__ = [
    "ArtDirection",
    "infer_art_direction",
    "CATEGORY_CONFLICT",
    "CATEGORY_BUSINESS",
    "CATEGORY_TECHNICAL",
    "CATEGORY_HISTORY",
    "CATEGORY_HUMAN",
    "CATEGORY_CREATIVE",
    "CATEGORY_GENERIC",
]
