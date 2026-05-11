"""Phase 3 — source_grounding helpers + deck source warnings."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.deck_quality import build_deck_quality_report  # noqa: E402
from agent.source_grounding import (  # noqa: E402
    attach_sources_to_slide,
    build_deck_source_report,
    extract_claim_candidates_from_slide,
    extract_sources_from_tool_result,
    normalize_source,
    slide_has_source_metadata,
)


# ── normalize_source ─────────────────────────────────────────────────────
def test_normalize_source_basic():
    rec = normalize_source(
        {
            "title": "IRENA Renewable Capacity 2024",
            "url": "https://irena.org/x",
            "snippet": "Solar capacity rose 32% YoY",
        },
        provider="info_search_web",
    )
    assert rec is not None
    assert rec["title"].startswith("IRENA")
    assert rec["url"] == "https://irena.org/x"
    assert rec["confidence"] in {"high", "medium", "low", "unknown"}
    assert rec["provider"] == "info_search_web"
    assert isinstance(rec["observed_at"], str)
    assert rec["metadata"] == {}


def test_normalize_source_returns_none_for_empty():
    assert normalize_source({}) is None
    assert normalize_source(None) is None
    assert normalize_source({"unrelated": "x"}) is None


def test_normalize_source_truncates_long_snippet():
    long_snip = "x" * 5000
    rec = normalize_source({"url": "https://e.com", "snippet": long_snip})
    assert rec is not None
    assert len(rec["snippet"]) <= 600


# ── extract_sources_from_tool_result ─────────────────────────────────────
def test_extract_sources_from_info_search_web_shape():
    tool_output = {
        "ok": True,
        "data": {
            "summary": "AI growing fast.",
            "sources": [
                {"title": "Stanford AI Index", "url": "https://aiindex.org",
                 "snippet": "GPU spend doubled in 2024"},
                {"title": "Empty"},  # only title — still extractable
                {"unrelated": "skip me"},  # nothing useful → skipped
            ],
        },
        "error": None,
        "meta": {},
    }
    out = extract_sources_from_tool_result("info_search_web", tool_output)
    assert len(out) == 2
    assert out[0]["url"] == "https://aiindex.org"
    assert out[1]["title"] == "Empty"


def test_extract_sources_from_browser_view():
    out = extract_sources_from_tool_result(
        "browser_view",
        {"ok": True, "data": {"url": "https://x", "title": "X", "text": "Hello"}},
    )
    assert len(out) == 1
    assert out[0]["url"] == "https://x"
    assert out[0]["provider"] == "browser_view"


def test_extract_sources_returns_empty_for_unknown_or_failed():
    assert extract_sources_from_tool_result("idle", {"ok": True, "data": {"idle": True}}) == []
    assert extract_sources_from_tool_result("info_search_web", {"ok": False, "data": None}) == []
    assert extract_sources_from_tool_result("", {"ok": True, "data": {"sources": []}}) == []


# ── extract_claim_candidates_from_slide ──────────────────────────────────
def test_extract_claim_candidates_stats():
    slide = {
        "layout": "stats",
        "stats": [
            {"value": "32%", "label": "YoY growth"},
            {"value": "1.2bn", "label": "users"},
        ],
    }
    cands = extract_claim_candidates_from_slide(slide)
    assert len(cands) == 2
    assert cands[0]["path"] == "stats[0]"


def test_extract_claim_candidates_chart():
    slide = {
        "layout": "chart",
        "chart_data": {"labels": ["2022", "2023"], "values": [100, 145], "unit": "GW"},
    }
    cands = extract_claim_candidates_from_slide(slide)
    assert len(cands) == 2
    assert "GW" in cands[0]["snippet"]


def test_extract_claim_candidates_bullets_with_numbers():
    slide = {"layout": "bullets", "title": "x", "bullets": ["No number", "Up 42% in 2024"]}
    cands = extract_claim_candidates_from_slide(slide)
    paths = [c["path"] for c in cands]
    assert "bullets[1]" in paths
    assert "bullets[0]" not in paths


# ── attach_sources_to_slide ──────────────────────────────────────────────
def test_attach_sources_does_not_mutate_input():
    slide = {"layout": "stats", "stats": [{"value": "10", "label": "x"}]}
    before = dict(slide)
    raw = [{"title": "T", "url": "https://x", "snippet": "S"}]
    out = attach_sources_to_slide(slide, raw)
    assert slide == before
    assert isinstance(out["sources"], list) and len(out["sources"]) == 1
    assert out["sources"][0]["url"] == "https://x"


# ── build_deck_source_report / slide_has_source_metadata ─────────────────
def test_slide_has_source_metadata_recognises_chart_data_source():
    slide = {"layout": "chart", "chart_data": {"source": "IRENA", "labels": [], "values": []}}
    assert slide_has_source_metadata(slide) is True


def test_slide_has_source_metadata_negative():
    assert slide_has_source_metadata({"layout": "stats", "stats": []}) is False
    assert slide_has_source_metadata("nope") is False


def test_build_deck_source_report_warns_for_stats_without_source():
    deck = [
        {"layout": "title", "title": "T"},
        {"layout": "stats", "stats": [{"value": "1", "label": "x"}]},
    ]
    rep = build_deck_source_report(deck)
    codes = [w["code"] for w in rep["warnings"]]
    assert "missing_source" in codes
    assert rep["stats_slide_count"] == 1


def test_build_deck_source_report_no_warning_for_chart_with_source():
    deck = [
        {"layout": "chart", "chart_data": {"source": "IRENA", "labels": ["a"], "values": [1]}}
    ]
    rep = build_deck_source_report(deck)
    assert rep["warnings"] == []
    assert rep["chart_slide_count"] == 1
    assert rep["slides_with_sources"] == 1


def test_build_deck_source_report_warns_for_chart_without_source():
    deck = [
        {"layout": "chart", "chart_data": {"labels": ["a"], "values": [1]}, "title": "x", "subtitle": ""}
    ]
    rep = build_deck_source_report(deck)
    assert rep["warnings"] and rep["warnings"][0]["code"] == "missing_source"


# ── deck_quality integration: source_warnings surfaced ───────────────────
def test_deck_quality_report_carries_source_warnings():
    deck = [
        {
            "id": "t",
            "layout": "title",
            "title": "T",
            "subtitle": "S",
            "eyebrow": "E",
        },
        {
            "id": "s",
            "layout": "stats",
            "title": "Numbers",
            "stats": [{"value": "10", "label": "alpha"}, {"value": "20", "label": "beta"}],
        },
        {
            "id": "c",
            "layout": "closing",
            "title": "Bye",
            "subtitle": "",
            "cta": "Q&A",
        },
    ]
    rep = build_deck_quality_report(deck)
    # The schema is fine — ok=True even though the stats slide has no source.
    assert rep.ok is True
    assert any(w["layout"] == "stats" and w["code"] == "missing_source"
               for w in rep.source_warnings)
    assert rep.summary["source_warnings"] == len(rep.source_warnings)
