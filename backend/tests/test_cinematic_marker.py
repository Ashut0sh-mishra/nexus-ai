"""Phase 6AK — cinematic_marker tests."""

from __future__ import annotations

from agent.cinematic_marker import mark_hero_moments


def test_handles_non_list():
    out, summary = mark_hero_moments(None)  # type: ignore[arg-type]
    assert out == []
    assert summary["total"] == 0


def test_marks_first_bigstat_only():
    slides = [
        {"layout": "title", "title": "A"},
        {"layout": "bigstat", "value": "42%"},
        {"layout": "bigstat", "value": "99%"},
    ]
    out, summary = mark_hero_moments(slides)
    assert out[0].get("is_hero", False) is False
    assert out[1].get("is_hero") is True
    assert out[2].get("is_hero", False) is False
    assert summary["bigstat"] == 1
    assert summary["total"] == 1


def test_marks_first_section_divider_only():
    slides = [
        {"layout": "section_divider", "title": "Part I"},
        {"layout": "section_divider", "title": "Part II"},
    ]
    out, summary = mark_hero_moments(slides)
    assert out[0].get("is_hero") is True
    assert out[1].get("is_hero", False) is False
    assert summary["section_divider"] == 1


def test_quote_requires_attribution():
    slides = [
        {"layout": "quote", "quote": "Anonymous wisdom."},
        {"layout": "quote", "quote": "With name.", "attribution": "Da Vinci"},
        {"layout": "quote", "quote": "Later.", "attribution": "Edison"},
    ]
    out, summary = mark_hero_moments(slides)
    assert out[0].get("is_hero", False) is False
    assert out[1].get("is_hero") is True
    assert out[2].get("is_hero", False) is False
    assert summary["quote"] == 1


def test_marks_one_of_each_kind():
    slides = [
        {"layout": "title", "title": "T"},
        {"layout": "section_divider", "title": "Setup"},
        {"layout": "bigstat", "value": "10×"},
        {"layout": "quote", "quote": "x", "attribution": "Z"},
        {"layout": "closing", "title": "End"},
    ]
    out, summary = mark_hero_moments(slides)
    is_hero = [s.get("is_hero", False) for s in out]
    assert is_hero == [False, True, True, True, False]
    assert summary["total"] == 3
    assert summary["bigstat"] == 1
    assert summary["section_divider"] == 1
    assert summary["quote"] == 1


def test_is_additive_does_not_touch_other_fields():
    slides = [
        {
            "layout": "bigstat",
            "value": "42%",
            "label": "growth",
            "sources": [{"url": "https://x"}],
            "citations": [{"path": "stats[0]", "marker": 1, "supported": True}],
            "intent": {"narrative_role": "evidence"},
        }
    ]
    out, _ = mark_hero_moments(slides)
    s = out[0]
    assert s["is_hero"] is True
    assert s["sources"] == slides[0]["sources"]
    assert s["citations"] == slides[0]["citations"]
    assert s["intent"] == slides[0]["intent"]
    assert s["value"] == "42%"
    assert s["label"] == "growth"


def test_no_hero_slides_emits_empty_summary():
    slides = [
        {"layout": "title", "title": "T"},
        {"layout": "bullets", "title": "X", "bullets": ["a"]},
    ]
    out, summary = mark_hero_moments(slides)
    assert all("is_hero" not in s for s in out)
    assert summary["total"] == 0
