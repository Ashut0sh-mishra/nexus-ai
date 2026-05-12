"""Tests for Phase 6AL-Visuals image direction.

Covers the new ``NexusAgentLoop._scrub_image_prompt`` and
``NexusAgentLoop._direct_image_prompt`` helpers plus the expanded
``_IMAGE_LAYOUTS`` set. These are pure functions; no LLM, no network.
"""
from __future__ import annotations

from agent.loop import NexusAgentLoop


def test_image_layouts_now_include_hero_moments():
    # Phase 6AL-Visuals: image placement inversion.
    layouts = NexusAgentLoop._IMAGE_LAYOUTS
    # Pre-6AL set.
    assert "title" in layouts
    assert "bullets" in layouts
    assert "two-col" in layouts
    assert "closing" in layouts
    # Newly added hero moments.
    assert "quote" in layouts
    assert "bigstat" in layouts
    assert "section_divider" in layouts
    # Data-dense layouts must STAY image-free.
    assert "stats" not in layouts
    assert "chart" not in layouts
    assert "comparison" not in layouts
    assert "timeline" not in layouts


def test_scrub_strips_banned_stock_words():
    raw = "A calming, serene image of a modern professional team meeting"
    out = NexusAgentLoop._scrub_image_prompt(raw)
    lowered = out.lower()
    assert "calming" not in lowered
    assert "serene" not in lowered
    assert "modern" not in lowered
    assert "professional" not in lowered


def test_scrub_word_boundary_preserves_substrings():
    # "abstract" is banned but "extraction" must survive.
    out = NexusAgentLoop._scrub_image_prompt("oil extraction site at dusk")
    assert "extraction" in out


def test_scrub_handles_empty_and_none():
    assert NexusAgentLoop._scrub_image_prompt("") == ""
    assert NexusAgentLoop._scrub_image_prompt(None) == ""  # type: ignore[arg-type]


def test_direct_prompt_appends_cinematic_suffix():
    out = NexusAgentLoop._direct_image_prompt("rain on harbor at dawn, long lens")
    # Subject preserved.
    assert "rain on harbor at dawn" in out
    # Cinematic suffix present.
    assert "35mm" in out
    assert "editorial photography" in out
    assert "no text" in out
    assert "no logos" in out


def test_direct_prompt_falls_back_when_subject_scrubbed_empty():
    # All-banned input still produces a usable prompt.
    out = NexusAgentLoop._direct_image_prompt("abstract minimal clean simple")
    assert "documentary scene" in out
    assert "editorial photography" in out


def test_direct_prompt_scrubs_then_appends():
    out = NexusAgentLoop._direct_image_prompt(
        "a calming abstract corporate handshake at sunset"
    )
    lowered = out.lower()
    # Banned words gone.
    assert "calming" not in lowered
    assert "abstract" not in lowered
    assert "corporate" not in lowered
    # Suffix present.
    assert "cinematic composition" in lowered
