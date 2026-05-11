"""Phase 6D — Deterministic deck fixtures for offline evaluator tests.

Each builder returns a fully-formed deck dict (``slides`` + optional
``sources``) shaped to either pass or fail a specific prompt's evaluator
checks. No network, no LLM, no randomness.
"""

from __future__ import annotations

from typing import Any


def _slide_title(title: str = "Phase 6D Title", subtitle: str = "Phase 6D Sub") -> dict[str, Any]:
    return {"layout": "title", "title": title, "subtitle": subtitle}


def _slide_bullets(items: list[str] | None = None) -> dict[str, Any]:
    return {
        "layout": "bullets",
        "title": "Bullets",
        "bullets": items or ["alpha", "bravo", "charlie"],
    }


def _slide_two_col() -> dict[str, Any]:
    return {
        "layout": "two-col",
        "title": "Two Col",
        "left": {"heading": "L", "body": "left body"},
        "right": {"heading": "R", "body": "right body"},
    }


def _slide_quote() -> dict[str, Any]:
    return {
        "layout": "quote",
        "quote": "evaluation is a contract",
        "attribution": "phase 6d",
    }


def _slide_stats() -> dict[str, Any]:
    return {
        "layout": "stats",
        "title": "Stats",
        "stats": [
            {"value": "42", "label": "alpha"},
            {"value": "77", "label": "bravo"},
            {"value": "93", "label": "charlie"},
        ],
    }


def _slide_chart() -> dict[str, Any]:
    return {
        "layout": "chart",
        "title": "Chart",
        "chart": {
            "type": "bar",
            "labels": ["Q1", "Q2", "Q3"],
            "values": [10, 20, 30],
            "unit": "USD",
            "source_label": "FY24",
        },
    }


def _slide_closing() -> dict[str, Any]:
    return {
        "layout": "closing",
        "title": "Closing",
        "subtitle": "Thanks",
        "cta": "ship it",
    }


def passing_deck_for_inv_001() -> dict[str, Any]:
    """Deck designed to pass the inv-001 prompt requirements.

    inv-001 requires: title, bullets, stats, two-col, closing; chart_required=true;
    needs_external_sources=true with min_sources=2; 8..12 slides.
    """

    slides: list[dict[str, Any]] = [
        _slide_title("Investor Pitch", "Vertical Legal AI"),
        _slide_bullets(["Problem", "Market", "Wedge"]),
        _slide_stats(),
        _slide_two_col(),
        _slide_chart(),
        _slide_bullets(["Traction", "Team"]),
        _slide_bullets(["Roadmap"]),
        _slide_closing(),
    ]
    return {
        "slides": slides,
        "sources": [
            {"url": "https://example.com/legal-ai-market", "title": "Legal AI 2025"},
            {"url": "https://example.com/competitor-landscape", "title": "Vertical AI"},
        ],
    }


def failing_deck_for_inv_001_missing_layouts_and_sources() -> dict[str, Any]:
    """Deck that fails inv-001: no chart, no two-col, no stats, zero sources.

    Should be detected by:
      * required_layouts_missing includes "chart", "two-col", "stats"
      * chart_requirement_met is False
      * external_source_expectation_met is False
      * source_count < min_sources
    """

    slides: list[dict[str, Any]] = [
        _slide_title("Bad Pitch", "Sub"),
        _slide_bullets(["only bullets"]),
        _slide_bullets(["still only bullets"]),
        _slide_closing(),
    ]
    return {"slides": slides, "sources": []}


def passing_deck_for_biz_001() -> dict[str, Any]:
    """Deck for biz-001 (internal, no chart, no sources required, 5..8 slides)."""

    slides: list[dict[str, Any]] = [
        _slide_title("Q1 Sales Update", "B2B SaaS"),
        _slide_bullets(["Revenue", "Pipeline", "Wins"]),
        _slide_stats(),
        _slide_two_col(),
        _slide_closing(),
    ]
    return {"slides": slides}


def deck_with_invalid_slide_count() -> dict[str, Any]:
    """Two-slide deck — fails biz-001's min_slides=5 window check."""

    return {"slides": [_slide_title(), _slide_closing()]}
