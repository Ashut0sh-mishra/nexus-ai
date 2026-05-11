"""Phase 6V — DeckStrategy unit tests.

Self-contained: pulls only ``agent.deck_strategy`` and
``agent.art_direction``. Mirrors the import pattern used by the other
phase test files in this folder so it runs cleanly under the project's
docker pytest gate without ``conftest.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.art_direction import infer_art_direction  # noqa: E402
from agent.deck_strategy import (  # noqa: E402
    DECK_TYPE_BRIEFING,
    DECK_TYPE_CASE_STUDY,
    DECK_TYPE_EXPLAINER,
    DECK_TYPE_HOW_TO,
    DECK_TYPE_OVERVIEW,
    DECK_TYPE_PITCH,
    DECK_TYPE_RESEARCH_REPORT,
    DECK_TYPES,
    DeckStrategy,
    build_deck_strategy,
    render_strategy_for_planner,
)


def _build(topic: str, *, slide_count: int = 8, research: str = "", sources=None):
    art = infer_art_direction(topic, "luxury-dark")
    return build_deck_strategy(
        topic=topic,
        slide_count=slide_count,
        art_direction=art,
        research=research,
        research_sources=sources or [],
    )


# ── shape ────────────────────────────────────────────────────────────────


def test_strategy_has_all_spec_fields() -> None:
    s = _build("AI in healthcare")
    d = s.to_dict()
    expected = {
        "deck_type",
        "audience",
        "thesis",
        "story_arc",
        "tone",
        "visual_direction",
        "layout_recipe",
        "research_questions",
        "key_facts",
        "source_notes",
        "image_style",
        "chart_guidance",
        "research_quality",
    }
    assert expected.issubset(d.keys())
    assert isinstance(s, DeckStrategy)


def test_strategy_is_json_serialisable() -> None:
    s = _build("Quarterly business review")
    payload = json.dumps(s.to_dict())
    assert "deck_type" in payload


def test_render_contains_section_labels() -> None:
    s = _build("Renewable energy market")
    text = render_strategy_for_planner(s)
    for label in (
        "Deck strategy:",
        "type:",
        "audience:",
        "thesis:",
        "story_arc:",
        "layout_recipe:",
        "Research questions:",
        "Key facts:",
        "Source notes:",
    ):
        assert label in text


# ── deck-type classification ─────────────────────────────────────────────


def test_classification_research_report() -> None:
    s = _build("Global EV market analysis 2024 outlook")
    assert s.deck_type == DECK_TYPE_RESEARCH_REPORT


def test_classification_pitch() -> None:
    s = _build("Series A pitch deck for our fintech startup")
    assert s.deck_type == DECK_TYPE_PITCH


def test_classification_how_to() -> None:
    s = _build("How to deploy a Postgres cluster on Kubernetes")
    assert s.deck_type == DECK_TYPE_HOW_TO


def test_classification_explainer() -> None:
    s = _build("What is retrieval augmented generation explained")
    assert s.deck_type == DECK_TYPE_EXPLAINER


def test_classification_case_study() -> None:
    s = _build("Case study: lessons from our 2022 incident retrospective")
    assert s.deck_type == DECK_TYPE_CASE_STUDY


def test_classification_briefing() -> None:
    s = _build("Weekly executive status update for the platform team")
    assert s.deck_type == DECK_TYPE_BRIEFING


def test_classification_overview_for_generic() -> None:
    s = _build("Sunset over the Atlantic")
    assert s.deck_type == DECK_TYPE_OVERVIEW
    assert s.deck_type in DECK_TYPES


# ── differentiation ──────────────────────────────────────────────────────


def test_different_deck_types_produce_different_layout_recipes() -> None:
    pitch = _build("Series A pitch deck")
    research = _build("Solar industry market analysis")
    explainer = _build("How it works: explainer on diffusion models")
    # First slide is always title and last is always closing, but the
    # *middle* of the recipe should diverge across deck types.
    assert pitch.layout_recipe[1:-1] != research.layout_recipe[1:-1]
    assert pitch.layout_recipe[1:-1] != explainer.layout_recipe[1:-1]
    assert research.layout_recipe[1:-1] != explainer.layout_recipe[1:-1]


def test_different_deck_types_produce_different_story_arcs() -> None:
    pitch = _build("Series A pitch deck")
    research = _build("Solar industry market analysis")
    assert pitch.story_arc != research.story_arc


# ── slide-count scaling ──────────────────────────────────────────────────


def test_layout_recipe_trims_for_smaller_slide_count() -> None:
    s = _build("Solar industry market analysis", slide_count=4)
    assert len(s.layout_recipe) == 4
    assert s.layout_recipe[0] == "title"
    assert s.layout_recipe[-1] == "closing"


def test_layout_recipe_pads_for_larger_slide_count() -> None:
    s = _build("Solar industry market analysis", slide_count=14)
    assert len(s.layout_recipe) == 14
    assert s.layout_recipe[0] == "title"
    assert s.layout_recipe[-1] == "closing"


# ── research-quality rating ──────────────────────────────────────────────


def test_research_quality_none_with_no_inputs() -> None:
    s = _build("AI in healthcare", research="", sources=[])
    assert s.research_quality == "none"


def test_research_quality_thin_with_one_source() -> None:
    s = _build(
        "AI in healthcare",
        research="Short blurb.",
        sources=[{"url": "https://example.com/a", "title": "A"}],
    )
    assert s.research_quality == "thin"


def test_research_quality_rich_with_many_sources() -> None:
    s = _build(
        "AI in healthcare",
        research="Long body. " * 20,
        sources=[
            {"url": "https://a.example/1", "title": "One"},
            {"url": "https://b.example/2", "title": "Two"},
            {"url": "https://c.example/3", "title": "Three"},
        ],
    )
    assert s.research_quality == "rich"


# ── key-fact extraction ──────────────────────────────────────────────────


def test_extract_key_facts_picks_up_numbers_with_context() -> None:
    research = (
        "Industry revenue reached $4.2 trillion in 2024, up sharply. "
        "Adoption hit 93% of enterprise users worldwide. "
        "Latency improved 3.5x compared with the prior baseline."
    )
    s = _build("Cloud computing market", research=research)
    joined = " | ".join(s.key_facts).lower()
    assert "4.2 trillion" in joined
    assert "93%" in joined or "93 %" in joined
    assert any("3.5x" in f.lower() or "3.5 x" in f.lower() for f in s.key_facts)


def test_source_notes_summarise_unique_urls() -> None:
    s = _build(
        "AI in healthcare",
        sources=[
            {"url": "https://nature.com/article-1", "title": "Diagnostic AI study"},
            {"url": "https://nature.com/article-1", "title": "duplicate"},
            {"url": "https://who.int/report", "title": "WHO Report"},
        ],
    )
    assert len(s.source_notes) == 2
    text = " | ".join(s.source_notes)
    assert "Diagnostic AI study" in text
    assert "WHO Report" in text


# ── chart guidance differs by deck type ─────────────────────────────────


def test_chart_guidance_research_recommends_chart() -> None:
    s = _build("Solar industry market analysis", research="$4.2 trillion in 2024")
    assert "chart" in s.chart_guidance.lower()


def test_chart_guidance_how_to_skips_charts() -> None:
    s = _build("How to deploy Postgres on Kubernetes")
    assert "skip" in s.chart_guidance.lower() or "unless" in s.chart_guidance.lower()
