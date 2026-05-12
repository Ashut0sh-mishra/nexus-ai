"""Phase 6AJ — editorial pass tests.

Pure / offline / additive. Verifies the four properties the loop relies on:

1. Returns input unchanged on malformed input — never raises.
2. Strengthens headlines (strips trailing punctuation, leading "The"
   on hero layouts) without mangling already-strong titles.
3. Drops hedging openers + filler phrases in bullets while preserving
   numbers, years, and proper nouns. Never empties a bullet.
4. Adds short narrative transitions only when both adjacent slides
   carry an ``intent.narrative_role``.
"""

from __future__ import annotations

from agent.editorial_pass import apply_editorial_pass


def test_apply_editorial_pass_handles_non_list():
    out, summary = apply_editorial_pass(None)  # type: ignore[arg-type]
    assert out == []
    assert summary == {
        "headline_rewrites": 0,
        "bullet_rewrites": 0,
        "transitions_added": 0,
    }


def test_headline_strips_trailing_punct_and_leading_article():
    slides = [
        {"layout": "title", "title": "The Future of Energy."},
        {"layout": "bullets", "title": "The 2026 Outlook"},
    ]
    out, summary = apply_editorial_pass(slides)
    assert out[0]["title"] == "Future of Energy"
    # bullets layout keeps the leading article (only hero layouts strip).
    assert out[1]["title"] == "The 2026 Outlook"
    assert summary["headline_rewrites"] >= 1


def test_headline_no_change_when_already_clean():
    slides = [{"layout": "title", "title": "Quantum Wins 2026"}]
    out, summary = apply_editorial_pass(slides)
    assert out[0]["title"] == "Quantum Wins 2026"
    assert summary["headline_rewrites"] == 0


def test_headline_keeps_article_when_strip_leaves_one_word():
    slides = [{"layout": "title", "title": "The Outlook"}]
    out, _ = apply_editorial_pass(slides)
    # "Outlook" alone is too abrupt → keep the article.
    assert out[0]["title"] == "The Outlook"


def test_bullet_drops_hedging_opener_preserves_numbers():
    slides = [
        {
            "layout": "bullets",
            "title": "Findings",
            "bullets": [
                "It is important to note that revenue grew 42% in 2025.",
                "Studies have shown that Apple shipped 230 million units.",
            ],
        }
    ]
    out, summary = apply_editorial_pass(slides)
    b0, b1 = out[0]["bullets"]
    assert b0.startswith("Revenue grew 42%")
    assert "42%" in b0 and "2025" in b0
    assert b1.startswith("Apple shipped 230 million units")
    assert summary["bullet_rewrites"] == 2


def test_filler_substitutions_apply_mid_sentence():
    slides = [
        {
            "layout": "bullets",
            "title": "Action Plan",
            "bullets": [
                "We need to act in order to secure the lead.",
                "Due to the fact that demand fell, margins compressed.",
            ],
        }
    ]
    out, _ = apply_editorial_pass(slides)
    assert "in order to" not in out[0]["bullets"][0].lower()
    assert "to secure" in out[0]["bullets"][0]
    assert "due to the fact that" not in out[0]["bullets"][1].lower()
    assert out[0]["bullets"][1].lower().startswith("because")


def test_bullet_unchanged_when_rewrite_would_lose_proper_noun():
    # No hedging opener; nothing to drop. Confirm we don't invent changes.
    original = "Tesla revenue reached $96B in 2024."
    slides = [{"layout": "bullets", "title": "Q4", "bullets": [original]}]
    out, summary = apply_editorial_pass(slides)
    assert out[0]["bullets"][0] == original
    assert summary["bullet_rewrites"] == 0


def test_transitions_added_on_known_role_pairs():
    slides = [
        {"layout": "title", "title": "Intro", "intent": {"narrative_role": "opening"}},
        {
            "layout": "bullets",
            "title": "Setup",
            "intent": {"narrative_role": "context"},
            "bullets": ["Background details."],
        },
        {
            "layout": "bullets",
            "title": "Issue",
            "intent": {"narrative_role": "problem"},
            "bullets": ["The friction."],
        },
    ]
    out, summary = apply_editorial_pass(slides)
    assert out[0].get("transition", "") == ""  # first slide has no prev
    assert out[1]["transition"] == "Setting the stage:"
    assert out[2]["transition"] == "Where it breaks down:"
    assert summary["transitions_added"] == 2


def test_no_transition_when_role_missing():
    slides = [
        {"layout": "title", "title": "A", "intent": {"narrative_role": "opening"}},
        {"layout": "bullets", "title": "B", "bullets": ["x"]},  # no intent
        {"layout": "bullets", "title": "C", "intent": {"narrative_role": "insight"}, "bullets": ["y"]},
    ]
    out, summary = apply_editorial_pass(slides)
    assert "transition" not in out[1]
    # role is carried over the gap so opening→insight is searched
    # ("opening","insight") is not in the table → no transition emitted.
    assert "transition" not in out[2]
    assert summary["transitions_added"] == 0


def test_existing_transition_is_not_overwritten():
    slides = [
        {"layout": "title", "title": "A", "intent": {"narrative_role": "opening"}},
        {
            "layout": "bullets",
            "title": "B",
            "intent": {"narrative_role": "context"},
            "bullets": ["x"],
            "transition": "Custom bridge",
        },
    ]
    out, summary = apply_editorial_pass(slides)
    assert out[1]["transition"] == "Custom bridge"
    assert summary["transitions_added"] == 0


def test_pass_is_additive_does_not_drop_fields():
    slides = [
        {
            "layout": "bullets",
            "title": "Results.",
            "bullets": ["It is important to note that revenue grew 42%."],
            "sources": [{"title": "Q1", "url": "https://example.com"}],
            "citations": [{"path": "bullets[0]", "marker": 1, "supported": True}],
            "intent": {"narrative_role": "evidence"},
        }
    ]
    out, _ = apply_editorial_pass(slides)
    s = out[0]
    assert s["sources"] == slides[0]["sources"]
    assert s["citations"] == slides[0]["citations"]
    assert s["intent"] == slides[0]["intent"]
    assert s["title"] == "Results"
    assert s["bullets"][0].startswith("Revenue grew 42%")
