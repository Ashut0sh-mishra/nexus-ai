"""Phase 6M — tests for deterministic topic-aware art direction.

These tests cover the public ``infer_art_direction`` API and its
documented contract:

* Sentinel inputs (``""`` / ``"auto"`` / ``None``) trigger inference.
* Any other ``theme`` is respected verbatim.
* War / conflict topics map to the documentary ``Dossier`` theme, not
  the bright ``light-pro`` / ``Editorial`` defaults.
* Business / sales / startup topics map to ``light-pro``.
* AI / science / technical topics map to ``Pixel``.
* Education / history maps to ``Vellum``.
* Healthcare / climate / social-impact maps to ``Vellum`` (calm mood).
* Creative / design / branding maps to ``Editorial``.
* Generic / unclassified topics fall back to ``Editorial``.
* Inference is deterministic — calling twice returns equal values.
"""

from __future__ import annotations

import pytest

from agent.art_direction import (
    CATEGORY_BUSINESS,
    CATEGORY_CONFLICT,
    CATEGORY_CREATIVE,
    CATEGORY_GENERIC,
    CATEGORY_HISTORY,
    CATEGORY_HUMAN,
    CATEGORY_TECHNICAL,
    ArtDirection,
    infer_art_direction,
)


# ── Sentinel handling ─────────────────────────────────────────────────────


@pytest.mark.parametrize("sentinel", ["", "auto", "AUTO", "  Auto  ", None])
def test_sentinels_trigger_inference(sentinel):
    ad = infer_art_direction("The 2022 Russia–Ukraine war", sentinel)
    # Anything other than the explicit-override branch.
    assert ad.category != "explicit"
    assert ad.theme in {"Dossier", "light-pro", "Editorial", "Pixel", "Vellum"}


def test_explicit_user_theme_is_respected():
    ad = infer_art_direction("anything at all about war", "Pixel")
    assert ad.theme == "Pixel"
    assert ad.category == "explicit"
    assert ad.mood == "explicit"
    assert "explicitly selected" in ad.rationale


def test_explicit_user_theme_with_whitespace_is_normalized():
    ad = infer_art_direction("startup pitch", "  Vellum  ")
    assert ad.theme == "Vellum"
    assert ad.category == "explicit"


# ── Category routing ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "topic, expected_category, expected_theme",
    [
        # War / conflict / geopolitics
        ("The Russia–Ukraine war and its global impact", CATEGORY_CONFLICT, "Dossier"),
        ("Modern military drone warfare", CATEGORY_CONFLICT, "Dossier"),
        ("Geopolitical fallout of the Gaza conflict", CATEGORY_CONFLICT, "Dossier"),
        # Business / startup / sales
        ("Series A pitch deck for a B2B SaaS startup", CATEGORY_BUSINESS, "light-pro"),
        ("Q4 sales kickoff and revenue forecast", CATEGORY_BUSINESS, "light-pro"),
        ("Go-to-market strategy for our new product launch", CATEGORY_BUSINESS, "light-pro"),
        # Science / AI / technical
        ("State of large language models in 2025", CATEGORY_TECHNICAL, "Pixel"),
        ("An overview of quantum computing algorithms", CATEGORY_TECHNICAL, "Pixel"),
        ("Cybersecurity threats in cloud infrastructure", CATEGORY_TECHNICAL, "Pixel"),
        # Education / history
        ("A high-school history lesson on the Roman Empire", CATEGORY_HISTORY, "Vellum"),
        ("Renaissance literature and philosophy syllabus", CATEGORY_HISTORY, "Vellum"),
        # Healthcare / climate / social impact
        ("Public health response to a pandemic", CATEGORY_HUMAN, "Vellum"),
        ("Climate change and renewable energy adoption", CATEGORY_HUMAN, "Vellum"),
        ("Mental health in modern workplaces", CATEGORY_HUMAN, "Vellum"),
        # Creative / design / branding
        ("Brand identity and typography for a fashion label", CATEGORY_CREATIVE, "Editorial"),
        ("Storytelling in product design and UX", CATEGORY_CREATIVE, "Editorial"),
    ],
)
def test_category_routing(topic, expected_category, expected_theme):
    ad = infer_art_direction(topic, "auto")
    assert ad.category == expected_category, (
        f"topic={topic!r} expected={expected_category} got={ad.category}"
    )
    assert ad.theme == expected_theme


def test_unclassified_topic_falls_back_to_editorial():
    ad = infer_art_direction("xyzzy plover frob", "auto")
    assert ad.category == CATEGORY_GENERIC
    assert ad.theme == "Editorial"
    assert ad.mood == "neutral"


def test_empty_topic_falls_back_to_editorial():
    ad = infer_art_direction("   ", "auto")
    assert ad.category == CATEGORY_GENERIC
    assert ad.theme == "Editorial"


# ── Tie-breaking: conflict outranks business ──────────────────────────────


def test_conflict_outranks_business_on_tie():
    # Both "war" and "revenue" hit; conflict comes first in priority.
    ad = infer_art_direction("war economy and revenue impact", "auto")
    assert ad.category == CATEGORY_CONFLICT
    assert ad.theme == "Dossier"


# ── Determinism ───────────────────────────────────────────────────────────


def test_inference_is_deterministic():
    a = infer_art_direction("AI safety research at frontier labs", "auto")
    b = infer_art_direction("AI safety research at frontier labs", "auto")
    assert a == b
    assert isinstance(a, ArtDirection)


# ── Rationale shape ───────────────────────────────────────────────────────


def test_rationale_is_human_readable_for_inferred_themes():
    ad = infer_art_direction("Geopolitical analysis of the Ukraine war", "auto")
    assert ad.theme == "Dossier"
    # One-sentence-ish, mentions the chosen theme name explicitly.
    assert "Dossier" in ad.rationale
    assert len(ad.rationale) <= 240


def test_to_dict_round_trips_keys():
    ad = infer_art_direction("startup pitch deck", "auto")
    d = ad.to_dict()
    assert d["theme"] == ad.theme
    assert d["theme_id"] == ad.theme_id
    assert d["mood"] == ad.mood
    assert d["category"] == ad.category
    assert d["rationale"] == ad.rationale
    assert d["palette_hint"] == list(ad.palette_hint)
