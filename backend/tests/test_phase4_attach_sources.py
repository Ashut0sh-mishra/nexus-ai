"""Phase 4 — attach_research_sources_to_deck behaviour + warning interaction."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.deck_quality import build_deck_quality_report  # noqa: E402
from agent.source_grounding import (  # noqa: E402
    attach_research_sources_to_deck,
    build_deck_source_report,
)


_RAW_SOURCES = [
    {"title": "IRENA Renewable Capacity 2024", "url": "https://www.irena.org/x",
     "snippet": "Solar capacity rose 32% YoY"},
    {"title": "IEA World Energy Outlook", "url": "https://www.iea.org/wo",
     "snippet": "Investment up 20%."},
    {"title": "OECD Energy Mix", "url": "https://oecd.org/em",
     "snippet": "Coal share declining."},
    {"title": "Should-be-dropped", "url": "", "snippet": ""},  # nothing usable
]


def _stats_slide():
    return {
        "id": "s1", "layout": "stats", "title": "Numbers",
        "stats": [
            {"value": "32%", "label": "growth"},
            {"value": "1.2bn", "label": "users"},
        ],
    }


def _chart_slide(*, with_source=False):
    cd = {"labels": ["2022", "2023"], "values": [100, 145], "unit": "GW"}
    if with_source:
        cd["source"] = "IRENA"
    return {"id": "c1", "layout": "chart", "title": "Capacity",
            "subtitle": "GW", "chart_data": cd}


def _title_slide():
    return {"id": "t1", "layout": "title", "title": "Topic",
            "subtitle": "S", "eyebrow": "E"}


# ── attach: stats slides ──────────────────────────────────────────────────
def test_attach_attaches_to_stats_slide_and_caps_at_three():
    deck = [_title_slide(), _stats_slide()]
    out = attach_research_sources_to_deck(deck, _RAW_SOURCES)
    # Title untouched.
    assert "sources" not in out[0]
    # Stats got up to 3 normalised sources.
    srcs = out[1]["sources"]
    assert isinstance(srcs, list)
    assert 1 <= len(srcs) <= 3
    assert all("confidence" in s for s in srcs)
    # Original input not mutated.
    assert "sources" not in deck[1]


# ── attach: chart slides ──────────────────────────────────────────────────
def test_attach_sets_chart_data_source_when_empty():
    deck = [_chart_slide(with_source=False)]
    out = attach_research_sources_to_deck(deck, _RAW_SOURCES)
    cd = out[0]["chart_data"]
    assert cd["source"] == "IRENA Renewable Capacity 2024"
    assert isinstance(out[0]["sources"], list) and len(out[0]["sources"]) >= 1
    # Input untouched.
    assert deck[0]["chart_data"].get("source", "") == ""


def test_attach_does_not_overwrite_existing_chart_source():
    deck = [_chart_slide(with_source=True)]
    out = attach_research_sources_to_deck(deck, _RAW_SOURCES)
    assert out[0]["chart_data"]["source"] == "IRENA"


def test_attach_uses_url_host_when_title_missing():
    deck = [_chart_slide(with_source=False)]
    out = attach_research_sources_to_deck(
        deck,
        [{"url": "https://www.example.com/path", "snippet": "x"}],
    )
    assert out[0]["chart_data"]["source"] == "example.com"


# ── attach: empty input ───────────────────────────────────────────────────
def test_attach_no_sources_means_no_mutation():
    deck = [_stats_slide(), _chart_slide(with_source=False)]
    out = attach_research_sources_to_deck(deck, [])
    assert "sources" not in out[0]
    assert out[1]["chart_data"].get("source", "") == ""


def test_attach_drops_garbage_sources():
    deck = [_stats_slide()]
    out = attach_research_sources_to_deck(
        deck, [{"unrelated": "x"}, {"title": ""}],
    )
    # Nothing usable → nothing attached.
    assert "sources" not in out[0]


# ── attach: prose slides only when claim-bearing ──────────────────────────
def test_attach_skips_bullets_with_no_numbers():
    deck = [{"id": "b", "layout": "bullets", "title": "x", "bullets": ["alpha", "beta"]}]
    out = attach_research_sources_to_deck(deck, _RAW_SOURCES)
    assert "sources" not in out[0]


def test_attach_attaches_to_bullets_with_numbers():
    deck = [{"id": "b", "layout": "bullets", "title": "x",
             "bullets": ["No number", "Up 42% in 2024"]}]
    out = attach_research_sources_to_deck(deck, _RAW_SOURCES)
    assert isinstance(out[0]["sources"], list) and out[0]["sources"]


# ── interaction with deck-quality source_warnings ─────────────────────────
def test_attach_eliminates_stats_source_warning():
    deck = [_stats_slide()]
    rep_before = build_deck_source_report(deck)
    assert any(w["code"] == "missing_source" for w in rep_before["warnings"])
    after = attach_research_sources_to_deck(deck, _RAW_SOURCES)
    rep_after = build_deck_source_report(after)
    assert rep_after["warnings"] == []


def test_attach_eliminates_chart_source_warning():
    deck = [_chart_slide(with_source=False)]
    after = attach_research_sources_to_deck(deck, _RAW_SOURCES)
    rep = build_deck_source_report(after)
    assert rep["warnings"] == []


def test_chart_with_empty_source_still_warns_when_no_sources_given():
    deck = [_chart_slide(with_source=False)]
    after = attach_research_sources_to_deck(deck, [])
    rep = build_deck_source_report(after)
    assert rep["warnings"] and rep["warnings"][0]["code"] == "missing_source"


def test_full_deck_quality_report_loses_source_warnings_after_attach():
    deck = [_title_slide(), _stats_slide(), _chart_slide(with_source=False)]
    rep_before = build_deck_quality_report(deck)
    assert rep_before.summary["source_warnings"] >= 2
    after = attach_research_sources_to_deck(deck, _RAW_SOURCES)
    # patch ids to keep schema validator happy (already valid in the helpers).
    rep_after = build_deck_quality_report(after)
    assert rep_after.summary["source_warnings"] == 0


# ── non-mutation guarantee ────────────────────────────────────────────────
def test_attach_does_not_mutate_input_list_or_slides():
    deck = [_stats_slide(), _chart_slide(with_source=False)]
    snap = [dict(s) for s in deck]
    snap_chart = dict(deck[1]["chart_data"])
    _ = attach_research_sources_to_deck(deck, _RAW_SOURCES)
    assert deck[0] == snap[0]
    assert deck[1] == snap[1]
    assert deck[1]["chart_data"] == snap_chart
