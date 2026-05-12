"""Tests for Phase 6AL-Voice deterministic editorial-voice pass."""
from __future__ import annotations

import os

from agent.voice_pass import apply_voice_pass


def test_handles_non_list():
    out, summary = apply_voice_pass(None)  # type: ignore[arg-type]
    assert out == []
    assert summary == {
        "headline_rewrites": 0,
        "subtitle_kills": 0,
        "transition_scrubs": 0,
        "closing_rewrites": 0,
    }


def test_kill_switch_short_circuits(monkeypatch):
    monkeypatch.setenv("NEXUS_DISABLE_VOICE_PASS", "true")
    slides = [{"id": "s0", "title": "Problem Statement", "subtitle": "Stress is winning"}]
    out, summary = apply_voice_pass(slides)
    assert out == slides
    assert summary["headline_rewrites"] == 0


# ── A1 — Headline rewriter ─────────────────────────────────────────────────


def test_category_label_promotes_meaningful_subtitle():
    slides = [
        {
            "id": "s0",
            "layout": "bullets",
            "title": "Problem Statement",
            "subtitle": "Stress is winning across millennials",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["title"] == "Stress is winning across millennials"
    # Promoted subtitle is cleared so it does not duplicate as body copy.
    assert out[0]["subtitle"] == ""
    assert summary["headline_rewrites"] == 1


def test_bigstat_synthesizes_title_from_value_and_label():
    slides = [
        {
            "id": "s4",
            "layout": "bigstat",
            "title": "Traction Metrics",
            "value": "25%",
            "label": "Monthly User Growth",
            "subtitle": "",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["title"] == "25% Monthly User Growth"
    assert summary["headline_rewrites"] == 1


def test_closing_promotes_button_cta_to_title():
    slides = [
        {
            "id": "s5",
            "layout": "closing",
            "title": "Investment Ask",
            "cta": "Request a Pilot — 15 Min",
            "subtitle": "",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["title"] == "Request a Pilot — 15 Min"
    assert out[0]["cta"] == ""
    assert summary["headline_rewrites"] == 1
    assert summary["closing_rewrites"] == 1


def test_non_category_title_is_left_alone():
    slides = [
        {
            "id": "s0",
            "layout": "bullets",
            "title": "Stress is winning",
            "subtitle": "Anything",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["title"] == "Stress is winning"
    assert summary["headline_rewrites"] == 0


def test_category_label_with_no_safe_replacement_kept():
    slides = [
        {
            "id": "s0",
            "layout": "bullets",
            "title": "Problem Statement",
            "subtitle": "",
            "bullets": ["A", "B"],
        }
    ]
    out, summary = apply_voice_pass(slides)
    # No subtitle, not bigstat / closing → no safe rewrite available.
    assert out[0]["title"] == "Problem Statement"
    assert summary["headline_rewrites"] == 0


def test_filler_subtitle_is_not_promoted_to_title():
    slides = [
        {
            "id": "s0",
            "layout": "bullets",
            "title": "Problem Statement",
            "subtitle": "A Fundable Story",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["title"] == "Problem Statement"
    # And the filler subtitle was killed.
    assert out[0]["subtitle"] == ""
    assert summary["subtitle_kills"] == 1


def test_single_word_label_detected():
    slides = [
        {
            "id": "s0",
            "layout": "bullets",
            "title": "Overview",
            "subtitle": "Where Q1 stood at quarter-end",
        }
    ]
    out, _ = apply_voice_pass(slides)
    assert out[0]["title"] == "Where Q1 stood at quarter-end"


# ── A2 — Subtitle filler killer ───────────────────────────────────────────


def test_kills_generic_subtitle():
    slides = [
        {
            "id": "s0",
            "title": "Wellness App Opportunity",
            "subtitle": "A Fundable Story",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["subtitle"] == ""
    assert summary["subtitle_kills"] == 1


def test_kills_placeholder_subtitle():
    slides = [
        {
            "id": "s0",
            "title": "Investment Ask",
            "subtitle": "No prompt for slide 4",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["subtitle"] == ""
    assert summary["subtitle_kills"] == 1


def test_kills_redundant_subtitle_matching_title():
    slides = [
        {
            "id": "s3",
            "title": "Wellness App Market Growth",
            "subtitle": "Wellness App Market Growth",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["subtitle"] == ""
    assert summary["subtitle_kills"] == 1


def test_keeps_meaningful_subtitle():
    slides = [
        {
            "id": "s4",
            "title": "Activation",
            "subtitle": "Up from 41% before the onboarding redesign.",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["subtitle"] == "Up from 41% before the onboarding redesign."
    assert summary["subtitle_kills"] == 0


# ── A3 — Transition sanitizer ─────────────────────────────────────────────


def test_scrubs_debug_transition():
    slides = [
        {"id": "s1", "title": "Problem", "transition": "Setting the stage:"},
        {"id": "s2", "title": "Data", "transition": "What the data shows:"},
    ]
    out, summary = apply_voice_pass(slides)
    assert "transition" not in out[0]
    assert "transition" not in out[1]
    assert summary["transition_scrubs"] == 2


def test_keeps_non_debug_transition():
    slides = [
        {
            "id": "s1",
            "title": "Where it goes from here",
            "transition": "Seven minutes. Build with us.",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["transition"] == "Seven minutes. Build with us."
    assert summary["transition_scrubs"] == 0


# ── A4 — Closing rewriter ─────────────────────────────────────────────────


def test_closing_with_non_button_cta_keeps_title_unchanged():
    slides = [
        {
            "id": "s5",
            "layout": "closing",
            "title": "Where we go from here",  # already authored
            "cta": "Request a Pilot",
        }
    ]
    out, summary = apply_voice_pass(slides)
    assert out[0]["title"] == "Where we go from here"
    assert out[0]["cta"] == "Request a Pilot"
    assert summary["closing_rewrites"] == 0


# ── Cross-cutting safety ──────────────────────────────────────────────────


def test_never_drops_non_dict_entries():
    slides = ["string", None, 42, {"id": "s0", "title": "Overview", "subtitle": "Real subtitle here"}]
    out, _ = apply_voice_pass(slides)  # type: ignore[arg-type]
    assert out[0] == "string"
    assert out[1] is None
    assert out[2] == 42
    assert out[3]["title"] == "Real subtitle here"


def test_preserves_unrelated_fields():
    slides = [
        {
            "id": "s0",
            "layout": "bigstat",
            "title": "Traction Metrics",
            "value": "25%",
            "label": "Monthly User Growth",
            "subtitle": "",
            "is_hero": True,
            "citations": [{"path": "value", "supported": True}],
            "intent": {"tone": "explicit", "density": "low"},
        }
    ]
    out, _ = apply_voice_pass(slides)
    assert out[0]["is_hero"] is True
    assert out[0]["citations"] == [{"path": "value", "supported": True}]
    assert out[0]["intent"] == {"tone": "explicit", "density": "low"}
    assert out[0]["value"] == "25%"
    assert out[0]["label"] == "Monthly User Growth"
