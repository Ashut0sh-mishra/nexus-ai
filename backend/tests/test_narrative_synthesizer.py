"""Tests for Phase 6AN-Story narrative synthesizer."""
from __future__ import annotations

import json
import os

import pytest

from agent.narrative_synthesizer import (
    NarrativeDraft,
    NarrativeSection,
    compose_narrative_prompt,
    narrative_block,
    synthesize_narrative,
)


# ── compose_narrative_prompt ──────────────────────────────────────────────


def test_prompt_includes_topic_and_arc() -> None:
    system, user = compose_narrative_prompt(
        topic="agentic AI in 2026",
        research="OpenAI launched GPT-5 in 2025. Anthropic released Claude 4.",
        deck_type="research_report",
        audience="executives",
        tone="rigorous",
        thesis_hint="Agentic AI is the next platform shift.",
        story_arc=["problem", "evidence", "implication", "ask"],
        key_facts=["Market $50B by 2027"],
        slide_count=8,
    )
    assert "agentic AI in 2026" in user
    assert "problem -> evidence -> implication -> ask" in user
    assert "Market $50B by 2027" in user
    assert "rigorous" in user
    assert "JSON" in system


def test_prompt_handles_empty_research_and_arc() -> None:
    system, user = compose_narrative_prompt(
        topic="anything",
        research="",
        deck_type="overview",
        audience="",
        tone="",
        thesis_hint="",
        story_arc=[],
        key_facts=[],
        slide_count=5,
    )
    # Fallback arc supplied so the prompt is never empty.
    assert "problem -> evidence -> implication" in user
    assert "(none)" in user


def test_prompt_truncates_research() -> None:
    huge = "x" * 20_000
    _, user = compose_narrative_prompt(
        topic="t",
        research=huge,
        deck_type="overview",
        audience="",
        tone="",
        thesis_hint="",
        story_arc=["a"],
        key_facts=[],
        slide_count=5,
    )
    # Truncation cap is 6_000 chars of research; allow a tiny slack for
    # incidental 'x' characters elsewhere in the prompt boilerplate.
    assert user.count("x") <= 6_010
    assert user.count("x") >= 5_900


# ── narrative_block ───────────────────────────────────────────────────────


def test_block_empty_draft_returns_empty_string() -> None:
    assert narrative_block(NarrativeDraft()) == ""


def test_block_renders_thesis_and_sections() -> None:
    draft = NarrativeDraft(
        thesis="The market is consolidating.",
        sections=(
            NarrativeSection(beat="problem", heading="The squeeze", body="Three vendors hold 80%."),
            NarrativeSection(beat="evidence", heading="", body="Revenue fell 12% in Q3."),
        ),
        raw="{}",
    )
    block = narrative_block(draft)
    assert "Narrative draft" in block
    assert "Thesis: The market is consolidating." in block
    assert "[The squeeze]" in block
    assert "[evidence]" in block  # falls back to beat when heading empty
    assert "Three vendors hold 80%." in block


# ── _parse_narrative (via synthesize_narrative with fake ai_call) ─────────


async def _fake_ai_call_factory(response_text: str):
    async def _call(*, role, system, user, max_tokens, temperature=0.7):
        return response_text, 123, 0.0042
    return _call


@pytest.mark.asyncio
async def test_synthesize_parses_valid_json() -> None:
    response = json.dumps({
        "thesis": "Agentic AI will displace SaaS UIs by 2028.",
        "sections": [
            {"beat": "problem", "heading": "SaaS plateau", "body": "Adoption flat since 2023."},
            {"beat": "evidence", "heading": "", "body": "Claude/GPT agents now hit 60% task success."},
            {"beat": "implication", "heading": "Org chart shift", "body": "Buyers will go direct to models."},
        ],
    })
    ai_call = await _fake_ai_call_factory(response)
    draft, tokens, cost = await synthesize_narrative(
        topic="agentic AI",
        research="some research",
        deck_type="research_report",
        audience="execs",
        tone="rigorous",
        thesis_hint="",
        story_arc=["problem", "evidence", "implication"],
        key_facts=[],
        slide_count=8,
        ai_call=ai_call,
    )
    assert tokens == 123
    assert cost == pytest.approx(0.0042)
    assert not draft.is_empty
    assert draft.thesis.startswith("Agentic AI")
    assert len(draft.sections) == 3
    assert draft.sections[0].beat == "problem"
    assert draft.sections[0].heading == "SaaS plateau"


@pytest.mark.asyncio
async def test_synthesize_strips_code_fences() -> None:
    response = (
        "```json\n"
        + json.dumps({"thesis": "T", "sections": [{"beat": "x", "heading": "", "body": "B"}]})
        + "\n```"
    )
    ai_call = await _fake_ai_call_factory(response)
    draft, _, _ = await synthesize_narrative(
        topic="t", research="", deck_type="overview", audience="", tone="",
        thesis_hint="", story_arc=["x"], key_facts=[], slide_count=3,
        ai_call=ai_call,
    )
    assert not draft.is_empty
    assert draft.thesis == "T"


@pytest.mark.asyncio
async def test_synthesize_returns_empty_on_garbage() -> None:
    ai_call = await _fake_ai_call_factory("this is not json at all")
    draft, tokens, _ = await synthesize_narrative(
        topic="t", research="", deck_type="overview", audience="", tone="",
        thesis_hint="", story_arc=["x"], key_facts=[], slide_count=3,
        ai_call=ai_call,
    )
    assert draft.is_empty
    # Tokens still accounted (the LLM was called and billed).
    assert tokens == 123


@pytest.mark.asyncio
async def test_synthesize_returns_empty_on_ai_failure() -> None:
    async def _boom(**kwargs):
        raise RuntimeError("network down")
    draft, tokens, cost = await synthesize_narrative(
        topic="t", research="", deck_type="overview", audience="", tone="",
        thesis_hint="", story_arc=["x"], key_facts=[], slide_count=3,
        ai_call=_boom,
    )
    assert draft.is_empty
    assert tokens == 0
    assert cost == 0.0


@pytest.mark.asyncio
async def test_synthesize_kill_switch_short_circuits(monkeypatch) -> None:
    monkeypatch.setenv("NEXUS_DISABLE_NARRATIVE", "true")
    sentinel_called = {"v": False}

    async def _should_not_run(**kwargs):
        sentinel_called["v"] = True
        return "{}", 0, 0.0

    draft, tokens, cost = await synthesize_narrative(
        topic="t", research="", deck_type="overview", audience="", tone="",
        thesis_hint="", story_arc=["x"], key_facts=[], slide_count=3,
        ai_call=_should_not_run,
    )
    assert draft.is_empty
    assert tokens == 0
    assert cost == 0.0
    assert sentinel_called["v"] is False


@pytest.mark.asyncio
async def test_synthesize_without_ai_call_returns_empty() -> None:
    draft, tokens, cost = await synthesize_narrative(
        topic="t", research="", deck_type="overview", audience="", tone="",
        thesis_hint="", story_arc=["x"], key_facts=[], slide_count=3,
        ai_call=None,
    )
    assert draft.is_empty
    assert tokens == 0
    assert cost == 0.0


@pytest.mark.asyncio
async def test_synthesize_accepts_dict_sections_shape_drift() -> None:
    # LLM sometimes returns sections as a dict keyed by beat instead of
    # an array. The parser should still extract them.
    response = json.dumps({
        "thesis": "Spine.",
        "sections": {
            "problem": "Paragraph one with a specific number 42.",
            "evidence": "Paragraph two with another entity OpenAI.",
        },
    })
    ai_call = await _fake_ai_call_factory(response)
    draft, _, _ = await synthesize_narrative(
        topic="t", research="", deck_type="overview", audience="", tone="",
        thesis_hint="", story_arc=["problem", "evidence"], key_facts=[], slide_count=3,
        ai_call=ai_call,
    )
    assert not draft.is_empty
    assert len(draft.sections) == 2
    bodies = {s.body for s in draft.sections}
    assert any("42" in b for b in bodies)


# ── prompt integration: narrative block is injected into writer/planner ──


def test_slides_user_message_injects_narrative() -> None:
    from agent.prompts import slides_user_message

    draft = NarrativeDraft(
        thesis="Markets consolidate.",
        sections=(NarrativeSection(beat="problem", heading="", body="Three vendors hold 80%."),),
        raw="{}",
    )
    msg = slides_user_message(
        topic="market consolidation",
        slide_count=5,
        research="Some research.",
        outline="1. (title) Intro",
        narrative=draft,
    )
    assert "Narrative draft" in msg
    assert "Markets consolidate." in msg
    assert "Three vendors hold 80%." in msg
    # Anti-invention rule wired in.
    assert "Do not introduce facts" in msg


def test_slides_user_message_without_narrative_unchanged() -> None:
    from agent.prompts import slides_user_message

    msg = slides_user_message(
        topic="t",
        slide_count=3,
        research="R",
        outline="1. (title) X",
    )
    assert "Narrative draft" not in msg
    assert "Do not introduce facts" not in msg


def test_planner_user_message_injects_narrative() -> None:
    from agent.prompts import planner_user_message

    draft = NarrativeDraft(
        thesis="T.",
        sections=(NarrativeSection(beat="x", heading="", body="Body."),),
        raw="{}",
    )
    msg = planner_user_message("topic", 5, "research", narrative=draft)
    assert "Narrative draft" in msg
    assert "each slide must map to one section" in msg
