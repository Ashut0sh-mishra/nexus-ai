"""Phase 6AF — tests for the in-pipeline citation attach module.

Pure offline tests. No DB. No HTTP. No LLM. No filesystem writes.

These tests verify the **integration** contract: ``attach_citations_to_deck``
takes a list of slide dicts (as produced by the loop right before
``_save_deck``), runs the deterministic mapper, and writes a
``citations`` array onto each slide without mutating any other field.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.citation_attach import attach_citations_to_deck  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures (small, hand-curated decks — one per claim basis)
# ---------------------------------------------------------------------------


def _stats_deck() -> list[dict]:
    return [
        {
            "id": "slide-1",
            "layout": "title",
            "title": "Q1 Sales",
            "subtitle": "Internal update",
        },
        {
            "id": "slide-2",
            "layout": "stats",
            "title": "Revenue Growth",
            "stats": [
                {"value": "42%", "label": "YoY revenue growth"},
                {"value": "18M", "label": "New ARR"},
            ],
            "sources": [
                {
                    "id": "https://example.com/q1",
                    "url": "https://example.com/q1",
                    "title": "Q1 Earnings Call",
                    "snippet": "Revenue grew 42% YoY and new ARR reached 18 million.",
                }
            ],
        },
        {
            "id": "slide-3",
            "layout": "closing",
            "title": "Thanks",
            "subtitle": "Questions?",
        },
    ]


def _no_sources_deck() -> list[dict]:
    return [
        {
            "id": "slide-1",
            "layout": "bullets",
            "title": "Topics",
            "bullets": [
                "Customer expansion accelerated significantly in Q1.",
                "Churn fell to historic lows.",
            ],
        },
    ]


def _bullets_with_phrase_match_deck() -> list[dict]:
    return [
        {
            "id": "slide-1",
            "layout": "bullets",
            "title": "Highlights",
            "bullets": [
                "AI adoption among enterprises doubled this year.",
                "Random unrelated marketing claim.",
            ],
            "sources": [
                {
                    "id": "https://example.com/ai",
                    "url": "https://example.com/ai",
                    "title": "AI Adoption Report 2026",
                    "snippet": "AI adoption among enterprises doubled this year, the report finds.",
                }
            ],
        }
    ]


# ---------------------------------------------------------------------------
# Contract: shape, additivity, determinism
# ---------------------------------------------------------------------------


def test_returns_list_and_summary_with_required_keys():
    out, summary = attach_citations_to_deck(_stats_deck())
    assert isinstance(out, list)
    assert len(out) == 3
    for k in (
        "total_claims",
        "supported",
        "unsupported",
        "by_basis",
        "support_rate",
        "slides_with_citations",
    ):
        assert k in summary, f"summary missing key {k!r}"


def test_every_slide_gets_a_citations_array():
    out, _ = attach_citations_to_deck(_stats_deck())
    for s in out:
        assert isinstance(s.get("citations"), list), s


def test_existing_fields_untouched():
    deck = _stats_deck()
    snapshot = [dict(s) for s in deck]
    out, _ = attach_citations_to_deck(deck)
    for original, new in zip(snapshot, out):
        for k, v in original.items():
            if k == "citations":
                continue
            assert new.get(k) == v, (
                f"slide field {k!r} mutated: {v!r} -> {new.get(k)!r}"
            )


def test_input_list_is_not_mutated_in_place():
    deck = _stats_deck()
    before_keys = [set(s.keys()) for s in deck]
    attach_citations_to_deck(deck)
    after_keys = [set(s.keys()) for s in deck]
    assert before_keys == after_keys, "input deck mutated in place"


def test_determinism_same_input_same_output():
    out1, sum1 = attach_citations_to_deck(_stats_deck())
    out2, sum2 = attach_citations_to_deck(_stats_deck())
    assert out1 == out2
    assert sum1 == sum2


# ---------------------------------------------------------------------------
# Marker semantics
# ---------------------------------------------------------------------------


def test_supported_numeric_claim_gets_marker_one():
    out, summary = attach_citations_to_deck(_stats_deck())
    stats_slide = out[1]
    cites = stats_slide["citations"]
    # Both stats are numerically sourced by the same single source.
    supported = [c for c in cites if c["supported"]]
    assert len(supported) >= 1
    # All supported claims point at the slide's first (and only) source,
    # so the marker must be 1 for every supported claim.
    for c in supported:
        assert c["marker"] == 1
        assert c["source_url"] == "https://example.com/q1"
    assert summary["supported"] >= 1
    assert summary["slides_with_citations"] == 1


def test_unsupported_claim_has_marker_zero():
    out, summary = attach_citations_to_deck(_no_sources_deck())
    cites = out[0]["citations"]
    assert cites, "expected claims to be extracted from bullets"
    for c in cites:
        assert c["supported"] is False
        assert c["marker"] == 0
        assert c["basis"] == "no_match"
    assert summary["slides_with_citations"] == 0
    assert summary["supported"] == 0


def test_phrase_match_basis_is_recorded():
    out, _ = attach_citations_to_deck(_bullets_with_phrase_match_deck())
    cites = out[0]["citations"]
    bases = {c["basis"] for c in cites}
    assert "exact_phrase" in bases or "keyword_overlap" in bases


def test_marker_numbers_are_per_slide():
    deck = [
        # Two separate stats slides each with their own source — markers
        # must restart at 1 on the second slide, not continue from the first.
        {
            "id": "slide-1",
            "layout": "stats",
            "title": "A",
            "stats": [{"value": "10%", "label": "growth"}],
            "sources": [
                {
                    "id": "https://a.example",
                    "url": "https://a.example",
                    "title": "A",
                    "snippet": "growth was 10% this year",
                }
            ],
        },
        {
            "id": "slide-2",
            "layout": "stats",
            "title": "B",
            "stats": [{"value": "20%", "label": "growth"}],
            "sources": [
                {
                    "id": "https://b.example",
                    "url": "https://b.example",
                    "title": "B",
                    "snippet": "growth was 20% this year",
                }
            ],
        },
    ]
    out, _ = attach_citations_to_deck(deck)
    for s in out:
        supported = [c for c in s["citations"] if c["supported"]]
        if supported:
            assert max(c["marker"] for c in supported) == 1


# ---------------------------------------------------------------------------
# Defensive paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, "x", 42, {}])
def test_non_list_input_returns_empty(bad):
    out, summary = attach_citations_to_deck(bad)
    assert out == []
    assert summary["total_claims"] == 0
    assert summary["slides_with_citations"] == 0


def test_non_dict_slides_pass_through_unchanged():
    deck = [None, "x", {"id": "slide-1", "layout": "title", "title": "T"}]
    out, _ = attach_citations_to_deck(deck)
    assert out[0] is None
    assert out[1] == "x"
    assert isinstance(out[2].get("citations"), list)


def test_empty_deck():
    out, summary = attach_citations_to_deck([])
    assert out == []
    assert summary["total_claims"] == 0
    assert summary["slides_with_citations"] == 0
