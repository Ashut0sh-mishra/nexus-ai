"""Phase 6V — verify Planner threads DeckStrategy into the LLM prompt.

We monkey-patch the planner's ``ClaudeService.complete`` to capture the
``user`` message it would have sent. When a strategy is supplied, the
rendered strategy block must appear; when none is supplied the prompt
must remain shaped like the pre-6V baseline (no ``Deck strategy:``
header).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.art_direction import infer_art_direction  # noqa: E402
from agent.deck_strategy import build_deck_strategy  # noqa: E402
from agent.planner import Planner  # noqa: E402


class _FakeClaude:
    """Minimal stand-in that records the prompt and returns a JSON outline."""

    def __init__(self) -> None:
        self.last_user: str | None = None

    async def complete(self, *, system: str, user: str, max_tokens: int):
        self.last_user = user
        # Deterministic 5-slide outline — passes _parse_outline + _enforce_constraints.
        outline_json = (
            "["
            '{"layout":"title","title":"T","intent":"open"},'
            '{"layout":"bullets","title":"B","intent":"context"},'
            '{"layout":"two-col","title":"C","intent":"compare"},'
            '{"layout":"stats","title":"S","intent":"numbers"},'
            '{"layout":"closing","title":"End","intent":"wrap"}'
            "]"
        )
        return outline_json, 100, 0.0


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_planner_includes_strategy_block_in_prompt() -> None:
    fake = _FakeClaude()
    planner = Planner(claude=fake)  # type: ignore[arg-type]
    strategy = build_deck_strategy(
        topic="Solar industry market analysis",
        slide_count=5,
        art_direction=infer_art_direction("Solar industry market analysis", "luxury-dark"),
        research="Industry revenue reached $4.2 trillion in 2024.",
        research_sources=[
            {"url": "https://example.com/a", "title": "Solar Market 2024"},
        ],
    )

    outline, tokens, cost = _run(
        planner.plan("Solar industry market analysis", 5, "research blob", strategy=strategy)
    )

    assert fake.last_user is not None
    assert "Deck strategy:" in fake.last_user
    assert "layout_recipe:" in fake.last_user
    # Strategy-derived deck type should propagate into the prompt.
    assert strategy.deck_type in fake.last_user
    assert len(outline) == 5
    assert tokens == 100


def test_planner_default_when_no_strategy() -> None:
    fake = _FakeClaude()
    planner = Planner(claude=fake)  # type: ignore[arg-type]
    outline, _tokens, _cost = _run(planner.plan("AI in healthcare", 5, "some research"))
    assert fake.last_user is not None
    assert "Deck strategy:" not in fake.last_user
    assert len(outline) == 5


def test_planner_fallback_uses_strategy_layout_recipe() -> None:
    """If Claude raises, the fallback outline should follow the strategy
    recipe (title-first, closing-last, middle differs by deck type)."""

    class _BoomClaude:
        async def complete(self, *, system: str, user: str, max_tokens: int):
            raise RuntimeError("no LLM available")

    planner = Planner(claude=_BoomClaude())  # type: ignore[arg-type]

    pitch_strategy = build_deck_strategy(
        topic="Series A pitch deck",
        slide_count=8,
        art_direction=infer_art_direction("Series A pitch deck", "luxury-dark"),
        research="",
        research_sources=[],
    )
    research_strategy = build_deck_strategy(
        topic="Solar industry market analysis",
        slide_count=8,
        art_direction=infer_art_direction("Solar industry market analysis", "luxury-dark"),
        research="",
        research_sources=[],
    )

    pitch_outline, _, _ = _run(
        planner.plan("Series A pitch deck", 8, "", strategy=pitch_strategy)
    )
    research_outline, _, _ = _run(
        planner.plan("Solar industry market analysis", 8, "", strategy=research_strategy)
    )

    pitch_layouts = [s["layout"] for s in pitch_outline]
    research_layouts = [s["layout"] for s in research_outline]

    assert pitch_layouts[0] == "title"
    assert pitch_layouts[-1] == "closing"
    assert research_layouts[0] == "title"
    assert research_layouts[-1] == "closing"
    # Middle structure should differ between deck types.
    assert pitch_layouts[1:-1] != research_layouts[1:-1]
