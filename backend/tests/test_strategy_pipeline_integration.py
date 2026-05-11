"""Phase 6V — strategy/planner/repair pipeline integration test.

This test exercises the new ``topic -> strategy -> planner -> repair ->
validate`` shape end-to-end *without* spinning up the full
``NexusAgentLoop`` (which would require a DB and Claude). It verifies
the four invariants the user asked Phase 6V to preserve:

1. An explicit slide-count from the prompt is honoured by
   ``extract_slide_count`` and propagated through ``build_deck_strategy``
   and the planner.
2. After ``repair_for_validator`` the deck passes ``validate_deck``.
3. The strategy ``layout_recipe`` actually influences planner output
   (different deck types → different middle layouts even via fallback).
4. Strategy is JSON-serialisable for memory.write_artifact / SSE.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.art_direction import infer_art_direction  # noqa: E402
from agent.deck_repair import repair_for_validator  # noqa: E402
from agent.deck_strategy import (  # noqa: E402
    DECK_TYPE_HOW_TO,
    DECK_TYPE_RESEARCH_REPORT,
    build_deck_strategy,
)
from agent.planner import Planner  # noqa: E402
from agent.prompt_intent import extract_slide_count  # noqa: E402
from agent.slide_schema import validate_deck  # noqa: E402


class _StubClaude:
    """Always raises so the planner falls back deterministically.

    The fallback path is deliberately driven by the strategy's
    ``layout_recipe`` (Phase 6V), which is exactly what we want to
    assert here.
    """

    async def complete(self, *, system: str, user: str, max_tokens: int):
        raise RuntimeError("LLM disabled in pipeline test")


def _run(coro):
    return asyncio.run(coro)


def test_explicit_slide_count_propagates_through_strategy() -> None:
    topic = "Produce a 12-slide solar industry market analysis"
    hinted = extract_slide_count(topic)
    assert hinted == 12

    strategy = build_deck_strategy(
        topic=topic,
        slide_count=hinted,
        art_direction=infer_art_direction(topic, "luxury-dark"),
        research="",
        research_sources=[],
    )
    assert len(strategy.layout_recipe) == 12

    planner = Planner(claude=_StubClaude())  # type: ignore[arg-type]
    outline, _, _ = _run(planner.plan(topic, hinted, "", strategy=strategy))
    assert len(outline) == 12
    assert outline[0]["layout"] == "title"
    assert outline[-1]["layout"] == "closing"


def test_repaired_deck_passes_validation() -> None:
    """The strategy + planner outline yields layouts the validator
    accepts once the slides are filled with realistic content and
    passed through ``repair_for_validator`` (which fills layout-local
    defaults). The point of the test is to confirm Phase 6V did not
    introduce a layout outside the canonical registry."""

    topic = "Solar industry market analysis"
    strategy = build_deck_strategy(
        topic=topic,
        slide_count=8,
        art_direction=infer_art_direction(topic, "luxury-dark"),
        research="Industry revenue reached $4.2 trillion in 2024.",
        research_sources=[
            {"url": "https://example.com/a", "title": "Solar Market 2024"},
        ],
    )
    planner = Planner(claude=_StubClaude())  # type: ignore[arg-type]
    outline, _, _ = _run(planner.plan(topic, 8, "research blob", strategy=strategy))

    # Per-layout minimum content stub. The full pipeline gets these from
    # the LLM; the test fills them locally so we can isolate validator
    # behaviour from LLM behaviour.
    layout_stubs: dict[str, dict[str, object]] = {
        "title": {"subtitle": "An overview"},
        "bullets": {"bullets": ["Point one", "Point two", "Point three"]},
        "two-col": {
            "columns": [
                {"heading": "Left", "body": "Detail A"},
                {"heading": "Right", "body": "Detail B"},
            ],
        },
        "stats": {
            "stats": [
                {"value": "$4.2T", "label": "2024 revenue"},
                {"value": "12%", "label": "YoY growth"},
                {"value": "150GW", "label": "capacity"},
            ],
        },
        "quote": {"quote": "Solar is the cheapest electricity in history.", "attribution": "IEA"},
        "chart": {
            "chart_type": "bar",
            "chart_data": {
                "labels": ["2022", "2023", "2024"],
                "values": [3.1, 3.7, 4.2],
                "source": "IEA",
            },
        },
        "closing": {"call_to_action": "Read the full report."},
    }

    slides = []
    for item in outline:
        layout = item["layout"]
        slide = {"layout": layout, "title": item["title"]}
        slide.update(layout_stubs.get(layout, {}))
        slides.append(slide)

    repaired = repair_for_validator(slides)
    results = validate_deck(repaired)
    failures = [r for r in results if not r.ok]
    assert not failures, f"validation failed: {[(r.layout, r.errors) for r in failures]}"


def test_layout_recipe_differs_by_deck_type_through_planner() -> None:
    research_strategy = build_deck_strategy(
        topic="Solar industry market analysis 2024 outlook",
        slide_count=8,
        art_direction=infer_art_direction("Solar industry market analysis", "luxury-dark"),
        research="",
        research_sources=[],
    )
    how_to_strategy = build_deck_strategy(
        topic="How to deploy a Postgres cluster on Kubernetes",
        slide_count=8,
        art_direction=infer_art_direction("How to deploy Postgres", "luxury-dark"),
        research="",
        research_sources=[],
    )
    assert research_strategy.deck_type == DECK_TYPE_RESEARCH_REPORT
    assert how_to_strategy.deck_type == DECK_TYPE_HOW_TO

    planner = Planner(claude=_StubClaude())  # type: ignore[arg-type]
    research_outline, _, _ = _run(
        planner.plan("Solar industry market analysis", 8, "", strategy=research_strategy)
    )
    how_to_outline, _, _ = _run(
        planner.plan("How to deploy Postgres", 8, "", strategy=how_to_strategy)
    )

    research_mid = [s["layout"] for s in research_outline][1:-1]
    how_to_mid = [s["layout"] for s in how_to_outline][1:-1]
    assert research_mid != how_to_mid
    # How-to decks should not feature a ``stats`` slide in the recipe.
    assert "stats" not in how_to_mid
    # Research-report decks should include ``stats`` somewhere.
    assert "stats" in research_mid


def test_strategy_serialises_for_memory_artifact() -> None:
    strategy = build_deck_strategy(
        topic="Quarterly executive briefing",
        slide_count=6,
        art_direction=infer_art_direction("Quarterly executive briefing", "luxury-dark"),
        research="Revenue grew 12% quarter-over-quarter.",
        research_sources=[
            {"url": "https://internal.example.com/q3", "title": "Q3 Results"},
        ],
    )
    blob = json.dumps(strategy.to_dict())
    parsed = json.loads(blob)
    assert parsed["deck_type"]
    assert parsed["layout_recipe"]
    assert parsed["research_quality"] in {"rich", "thin", "none"}
