"""Tests for Phase 6AM-Grounding topic expander."""
from __future__ import annotations

import json
import os

import pytest

from agent.topic_expander import canonicalize_topic, expand_topic


# ── canonicalize_topic ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("create ppt on ai", "ai"),
        ("Create PPT on AI", "AI"),
        ("create a ppt about renewable energy", "renewable energy"),
        ("make a presentation about climate change in 2026", "climate change in 2026"),
        ("Make ppt on India elections", "India elections"),
        ("build a deck on quantum computing", "quantum computing"),
        ("generate ppt on the future of work", "the future of work"),
        ("ppt about agentic ai systems", "agentic ai systems"),
        ("slides for sales kickoff", "sales kickoff"),
        ("  spaced   topic   ", "spaced topic"),
        ("already-clean topic", "already-clean topic"),
        ("AI safety", "AI safety"),
        ("", ""),
    ],
)
def test_canonicalize_strips_meta_verbs(raw: str, expected: str) -> None:
    assert canonicalize_topic(raw) == expected


def test_canonicalize_handles_non_string() -> None:
    assert canonicalize_topic(None) == ""  # type: ignore[arg-type]
    assert canonicalize_topic(123) == ""  # type: ignore[arg-type]


def test_canonicalize_trims_trailing_punctuation() -> None:
    assert canonicalize_topic("create ppt on AI safety.") == "AI safety"


# ── expand_topic ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expand_returns_topic_only_when_ai_call_missing() -> None:
    queries, tokens, cost = await expand_topic("ai", ai_call=None)
    assert queries == ["ai"]
    assert tokens == 0
    assert cost == 0.0


@pytest.mark.asyncio
async def test_expand_returns_empty_for_empty_input() -> None:
    queries, _, _ = await expand_topic("", ai_call=None)
    assert queries == []


@pytest.mark.asyncio
async def test_expand_strips_meta_verbs_even_without_llm() -> None:
    queries, _, _ = await expand_topic("create ppt on AI safety", ai_call=None)
    assert queries == ["AI safety"]


@pytest.mark.asyncio
async def test_expand_respects_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_DISABLE_TOPIC_EXPANSION", "true")
    calls: list[Any] = []  # noqa: F821 - intentional

    async def fake_ai(**kwargs):  # pragma: no cover - must not run
        calls.append(kwargs)
        return "[]", 0, 0.0

    queries, tokens, _ = await expand_topic("ai", ai_call=fake_ai)
    assert queries == ["ai"]
    assert calls == []
    assert tokens == 0


@pytest.mark.asyncio
async def test_expand_skips_llm_for_long_specific_topics() -> None:
    called = False

    async def fake_ai(**_kwargs):
        nonlocal called
        called = True
        return "[]", 0, 0.0

    long_topic = "AI agents in enterprise customer support 2026 with grounded retrieval"
    queries, _, _ = await expand_topic(long_topic, ai_call=fake_ai)
    assert queries == [long_topic]
    assert called is False


@pytest.mark.asyncio
async def test_expand_uses_llm_and_dedupes() -> None:
    async def fake_ai(**_kwargs):
        payload = json.dumps([
            "AI market size 2026",
            "OpenAI Anthropic Google AI revenue",
            "Stanford AI Index 2026 key findings",
            "ai",  # duplicate of base topic, must be dropped
            "ai overview",  # paraphrase, must be dropped
        ])
        return payload, 42, 0.001

    queries, tokens, cost = await expand_topic(
        "create ppt on ai", ai_call=fake_ai, max_queries=5
    )
    # First entry is always the canonicalized base topic.
    assert queries[0] == "ai"
    # LLM proposals are appended; paraphrases dropped.
    assert "AI market size 2026" in queries
    assert "OpenAI Anthropic Google AI revenue" in queries
    assert "Stanford AI Index 2026 key findings" in queries
    assert "ai overview" not in queries
    # Cap respected.
    assert len(queries) <= 5
    # Cost surfaced.
    assert tokens == 42
    assert cost == pytest.approx(0.001)


@pytest.mark.asyncio
async def test_expand_recovers_from_fenced_response() -> None:
    async def fake_ai(**_kwargs):
        return '```json\n["AI Index 2026", "OpenAI revenue 2026"]\n```', 10, 0.0

    queries, _, _ = await expand_topic("ai", ai_call=fake_ai)
    assert "AI Index 2026" in queries
    assert "OpenAI revenue 2026" in queries


@pytest.mark.asyncio
async def test_expand_recovers_from_garbage_response() -> None:
    async def fake_ai(**_kwargs):
        return "I'm sorry, I can't comply with that.", 5, 0.0

    queries, _, _ = await expand_topic("ai", ai_call=fake_ai)
    assert queries == ["ai"]


@pytest.mark.asyncio
async def test_expand_recovers_from_ai_exception() -> None:
    async def fake_ai(**_kwargs):
        raise RuntimeError("provider down")

    queries, _, _ = await expand_topic("ai", ai_call=fake_ai)
    assert queries == ["ai"]


@pytest.mark.asyncio
async def test_expand_respects_max_queries() -> None:
    async def fake_ai(**_kwargs):
        return json.dumps([
            "AI market size 2026",
            "AI Index 2026 findings",
            "OpenAI revenue 2026",
            "Anthropic 2026 model",
            "AI safety 2026",
            "AI regulation EU 2026",
        ]), 30, 0.0

    queries, _, _ = await expand_topic("ai", ai_call=fake_ai, max_queries=3)
    assert len(queries) == 3
    assert queries[0] == "ai"


@pytest.mark.asyncio
async def test_expand_max_queries_one_returns_topic_only() -> None:
    async def fake_ai(**_kwargs):  # pragma: no cover - must not run
        return "[]", 0, 0.0

    queries, _, _ = await expand_topic("ai", ai_call=fake_ai, max_queries=1)
    assert queries == ["ai"]
