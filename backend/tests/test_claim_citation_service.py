"""Phase 6K - Offline tests for the deterministic claim-citation mapper.

Pure unit tests. No DB. No HTTP. No LLM. No filesystem writes. Use only
the gold corpus at ``backend/tests/fixtures/citation_gold.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.claim_citation_service import (  # noqa: E402
    SCHEMA_VERSION,
    extract_claims,
    map_deck_citations,
    match_claim_to_sources,
    summarize_mappings,
)
from tests.fixtures.citation_gold import gold_cases  # noqa: E402


# ---------------------------------------------------------------------------
# Schema / shape contract
# ---------------------------------------------------------------------------


_RECORD_KEYS = {
    "slide_index",
    "layout",
    "path",
    "claim_text",
    "numbers",
    "supported",
    "basis",
    "score",
    "source_id",
    "source_url",
    "source_title",
    "supports",
}

_SUMMARY_KEYS = {
    "total_claims",
    "supported",
    "unsupported",
    "by_basis",
    "support_rate",
}

_BY_BASIS_KEYS = {"exact_phrase", "numeric_match", "keyword_overlap", "no_match"}


def test_map_deck_returns_documented_shape() -> None:
    case = gold_cases()[0]
    report = map_deck_citations(case["deck"])
    assert set(report.keys()) == {"schema_version", "claims", "summary"}
    assert report["schema_version"] == SCHEMA_VERSION
    assert isinstance(report["claims"], list) and report["claims"], "case 1 must produce >=1 claim"
    for rec in report["claims"]:
        assert set(rec.keys()) == _RECORD_KEYS, rec
        assert isinstance(rec["supported"], bool)
        assert rec["basis"] in _BY_BASIS_KEYS
        assert 0.0 <= float(rec["score"]) <= 1.0
        assert isinstance(rec["supports"], list)
        for s in rec["supports"]:
            assert set(s.keys()) == {"source_id", "source_url", "source_title", "score", "basis"}
            assert s["basis"] in _BY_BASIS_KEYS
            assert 0.0 <= float(s["score"]) <= 1.0

    assert set(report["summary"].keys()) == _SUMMARY_KEYS
    assert set(report["summary"]["by_basis"].keys()) == _BY_BASIS_KEYS
    assert report["summary"]["total_claims"] == len(report["claims"])


def test_map_deck_empty_input() -> None:
    rep = map_deck_citations({})
    assert rep["schema_version"] == SCHEMA_VERSION
    assert rep["claims"] == []
    assert rep["summary"]["total_claims"] == 0
    assert rep["summary"]["support_rate"] == 0.0


def test_map_deck_handles_non_dict() -> None:
    # Defensive: must not raise on garbage input.
    rep = map_deck_citations(None)  # type: ignore[arg-type]
    assert rep["claims"] == []


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_map_deck_is_deterministic_under_source_reorder() -> None:
    case = gold_cases()[3]  # multi-source case
    deck = dict(case["deck"])
    rep_a = map_deck_citations(deck)
    deck_b = {
        "sources": list(reversed(deck.get("sources") or [])),
        "slides": deck["slides"],
    }
    rep_b = map_deck_citations(deck_b)
    # The sorted source_id ordering means best-pick is identical regardless
    # of input source order.
    assert rep_a == rep_b


# ---------------------------------------------------------------------------
# Per-case behavioural assertions over the gold corpus
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", gold_cases(), ids=lambda c: c["id"])
def test_gold_case_claim_outcomes(case: dict) -> None:
    report = map_deck_citations(case["deck"])
    by_key = {(c["slide_index"], c["path"]): c for c in report["claims"]}
    expected = case["expected"]

    # Every expected claim location must be present in the report.
    for key, exp in expected.items():
        assert key in by_key, f"{case['id']}: missing mapping for {key}; got {sorted(by_key.keys())}"
        rec = by_key[key]
        assert rec["supported"] is exp["supported"], (
            f"{case['id']} {key}: expected supported={exp['supported']}, got {rec}"
        )

        if "basis" in exp:
            allowed = exp["basis"] if isinstance(exp["basis"], (set, frozenset)) else {exp["basis"]}
            assert rec["basis"] in allowed, (
                f"{case['id']} {key}: basis {rec['basis']!r} not in {allowed}"
            )

        if exp["supported"]:
            allowed_ids = exp.get("source_ids") or set()
            if allowed_ids:
                assert rec["source_id"] in allowed_ids, (
                    f"{case['id']} {key}: best source_id {rec['source_id']!r} not in {allowed_ids}"
                )
            min_supports = exp.get("min_supports")
            if min_supports:
                # All allowed source ids must appear among supports.
                support_ids = {s["source_id"] for s in rec["supports"]}
                assert support_ids >= allowed_ids, (
                    f"{case['id']} {key}: supports {support_ids} missing some of {allowed_ids}"
                )
                assert len(rec["supports"]) >= min_supports
        else:
            assert rec["source_id"] is None
            assert rec["supports"] == []
            assert rec["score"] == 0.0


# ---------------------------------------------------------------------------
# Targeted invariants pulled out of the gold corpus
# ---------------------------------------------------------------------------


def test_unsupported_claim_explicitly_marked_no_match() -> None:
    case = next(c for c in gold_cases() if c["id"] == "C3-unsupported-claim")
    rep = map_deck_citations(case["deck"])
    rec = rep["claims"][0]
    assert rec["supported"] is False
    assert rec["basis"] == "no_match"
    assert rec["score"] == 0.0
    assert rec["source_id"] is None


def test_numeric_claim_not_misattributed_to_unrelated_source() -> None:
    case = next(c for c in gold_cases() if c["id"] == "C5-wrong-number-guard")
    rep = map_deck_citations(case["deck"])
    rec = rep["claims"][0]
    # 32% != 12%; no spurious numeric match.
    assert rec["basis"] != "numeric_match"
    # In this case overall token overlap is too thin -> unsupported.
    assert rec["supported"] is False


def test_filler_and_empty_slides_produce_no_claims() -> None:
    deck = {
        "sources": [],
        "slides": [
            {"layout": "title", "title": "Agenda", "subtitle": ""},
            {"layout": "bullets", "title": "Q&A", "bullets": []},
            {"layout": "bullets", "title": "Thank you", "bullets": ["thank you"]},
        ],
    }
    rep = map_deck_citations(deck)
    assert rep["claims"] == []
    assert rep["summary"]["total_claims"] == 0


def test_summary_counts_and_rate_consistent_with_claims_list() -> None:
    case = gold_cases()[1]  # numeric stats case
    rep = map_deck_citations(case["deck"])
    s = rep["summary"]
    assert s["total_claims"] == len(rep["claims"])
    assert s["supported"] + s["unsupported"] == s["total_claims"]
    assert sum(s["by_basis"].values()) == s["total_claims"]
    assert 0.0 <= s["support_rate"] <= 1.0
    # All three stats are supported by the same source -> support_rate == 1.0.
    assert s["support_rate"] == 1.0


def test_corpus_aggregate_precision_proxy() -> None:
    """Across all gold cases, supported predictions should be correct
    (per-case ``source_ids``) at high precision.

    Precision proxy = (correct supported predictions) / (supported predictions).
    Recall proxy   = (correct supported predictions) / (gold-positive cases).
    With this conservative mapper we expect both >= 0.9 on the corpus.
    """
    correct = 0
    predicted_supported = 0
    gold_positive = 0
    for case in gold_cases():
        rep = map_deck_citations(case["deck"])
        by_key = {(c["slide_index"], c["path"]): c for c in rep["claims"]}
        for key, exp in case["expected"].items():
            if exp["supported"]:
                gold_positive += 1
            rec = by_key.get(key)
            if rec is None:
                continue
            if rec["supported"]:
                predicted_supported += 1
                allowed = exp.get("source_ids") or set()
                if exp["supported"] and (not allowed or rec["source_id"] in allowed):
                    correct += 1
    precision = correct / predicted_supported if predicted_supported else 1.0
    recall = correct / gold_positive if gold_positive else 1.0
    assert precision >= 0.9, f"precision proxy too low: {precision}"
    assert recall >= 0.9, f"recall proxy too low: {recall}"


# ---------------------------------------------------------------------------
# extract_claims direct unit checks
# ---------------------------------------------------------------------------


def test_extract_claims_skips_non_factual_title() -> None:
    slide = {"layout": "bullets", "title": "Engineering Roadmap", "bullets": ["build the thing properly"]}
    claims = extract_claims(slide, slide_index=2)
    assert all(c["path"] != "title" for c in claims)
    assert any(c["path"] == "bullets[0]" for c in claims)


def test_extract_claims_keeps_numeric_title() -> None:
    slide = {"layout": "bullets", "title": "Revenue grew 42% in Q1", "bullets": []}
    claims = extract_claims(slide, slide_index=0)
    assert any(c["path"] == "title" for c in claims)


def test_match_claim_to_sources_no_sources_returns_unsupported() -> None:
    claim = {
        "slide_index": 0,
        "layout": "bullets",
        "path": "bullets[0]",
        "text": "Some claim with multiple words",
        "numbers": [],
    }
    rec = match_claim_to_sources(claim, [])
    assert rec["supported"] is False
    assert rec["basis"] == "no_match"
    assert rec["source_id"] is None


def test_summarize_mappings_handles_empty() -> None:
    s = summarize_mappings([])
    assert s["total_claims"] == 0
    assert s["support_rate"] == 0.0
