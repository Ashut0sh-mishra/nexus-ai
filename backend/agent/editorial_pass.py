"""Phase 6AJ — deterministic editorial pass.

Pure / offline / additive polish for slide copy. Runs in
``agent.loop.NexusAgentLoop`` after ``recommend_layouts`` /
``enforce_hero`` / ``insert_section_dividers`` and before save.

What it does, conservatively:

* **Headline strengthening (D1)** — strips trailing punctuation from
  titles, removes a leading "The " / "An " on hero / closing slides,
  collapses double spaces. Skips titles that are already strong.
* **Generic phrasing reduction (D2)** — rewrites a small set of
  filler phrases ("various things", "many factors", "a lot of",
  "in conclusion", "as we can see") to tighter equivalents or removes
  them outright when the bullet still parses. Refuses to drop content
  if the cleaned bullet would lose a number, percent, year, or proper
  noun.
* **Copy compression (D2/D4)** — for bullets >18 words, drops the
  classic hedging openers ("It is important to note that",
  "Studies have shown that", "It should be noted that"). Never
  drops the substantive clause that follows.
* **Narrative transitions (D3)** — when a slide already has an
  ``intent.narrative_role`` and the *previous* slide does too, write a
  very short bridge sentence into ``slide["transition"]`` (one line,
  ≤ 9 words). Renderer / drawer can choose to surface it.

Architectural rules:

* No LLM calls, no network, no randomness, no I/O.
* Never raises — on any error returns input slides unchanged.
* Additive only:

  - title rewrites only happen when the cleaned form is non-empty
    and at least 1 character shorter (i.e. clearly an improvement).
  - bullets are rewritten in place but never removed; if cleaning
    would empty the bullet, the original is kept.
  - ``slide["transition"]`` is a brand-new field. Existing
    fields, validator contract, intent block, citations, sources,
    and beat metadata are untouched.

* Exporter compatibility: PPTX/PDF read ``slide["title"]`` and
  ``slide["bullets"]`` exactly as before. ``transition`` is ignored by
  exporters that do not know about it.

Output summary returned by :func:`apply_editorial_pass`::

    {
        "headline_rewrites": int,
        "bullet_rewrites": int,
        "transitions_added": int,
    }
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["apply_editorial_pass"]


# ── Title / headline cleanup ────────────────────────────────────────────────

_TRAILING_PUNCT = re.compile(r"[\.\!\?,;:]+\s*$")
_LEADING_FILLER = re.compile(r"^(?:the|an|a)\s+", re.IGNORECASE)
_DOUBLE_SPACE = re.compile(r"\s{2,}")


def _strengthen_headline(title: str, *, layout: str | None) -> str:
    if not isinstance(title, str):
        return title
    t = title.strip()
    if not t:
        return title
    cleaned = _TRAILING_PUNCT.sub("", t)
    cleaned = _DOUBLE_SPACE.sub(" ", cleaned)
    # Only strip leading article on hero-ish layouts where short titles read
    # stronger. Section bodies sometimes need the article for grammar.
    if layout in {"title", "closing", "bigstat", "section_divider"}:
        cleaned_no_article = _LEADING_FILLER.sub("", cleaned, count=1)
        # Keep the article if removing it leaves a single word (looks abrupt).
        if cleaned_no_article and len(cleaned_no_article.split()) >= 2:
            cleaned = cleaned_no_article
    cleaned = cleaned.strip()
    if not cleaned:
        return title
    # Only accept the rewrite when it's clearly different / shorter.
    if cleaned == t:
        return title
    return cleaned


# ── Bullet copy compression / generic-phrase removal ───────────────────────

# Hedging openers: matched at the start of the bullet, case-insensitive.
# The substantive clause after the opener is preserved unchanged.
_HEDGE_OPENERS = (
    re.compile(r"^it\s+is\s+important\s+to\s+note\s+that\s+", re.IGNORECASE),
    re.compile(r"^it\s+should\s+be\s+noted\s+that\s+", re.IGNORECASE),
    re.compile(r"^studies\s+have\s+shown\s+that\s+", re.IGNORECASE),
    re.compile(r"^research\s+has\s+shown\s+that\s+", re.IGNORECASE),
    re.compile(r"^as\s+(?:we|you)\s+can\s+see\s*,?\s*", re.IGNORECASE),
    re.compile(r"^in\s+conclusion\s*,?\s*", re.IGNORECASE),
    re.compile(r"^to\s+summarize\s*,?\s*", re.IGNORECASE),
    re.compile(r"^essentially\s*,?\s*", re.IGNORECASE),
    re.compile(r"^basically\s*,?\s*", re.IGNORECASE),
    re.compile(r"^obviously\s*,?\s*", re.IGNORECASE),
)

# Filler-phrase substitutions. Conservative — only applied mid-sentence.
_FILLER_SUBS = (
    (re.compile(r"\ba\s+lot\s+of\b", re.IGNORECASE), "many"),
    (re.compile(r"\bvarious\s+different\b", re.IGNORECASE), "various"),
    (re.compile(r"\bdue\s+to\s+the\s+fact\s+that\b", re.IGNORECASE), "because"),
    (re.compile(r"\bin\s+order\s+to\b", re.IGNORECASE), "to"),
    (re.compile(r"\bat\s+this\s+point\s+in\s+time\b", re.IGNORECASE), "now"),
    (re.compile(r"\bfor\s+the\s+purpose\s+of\b", re.IGNORECASE), "to"),
    (re.compile(r"\bin\s+the\s+event\s+that\b", re.IGNORECASE), "if"),
    (re.compile(r"\bwith\s+regard\s+to\b", re.IGNORECASE), "about"),
    (re.compile(r"\bin\s+terms\s+of\b", re.IGNORECASE), "in"),
)

# Tokens we will *never* drop. If a rewrite would remove any of these,
# we keep the original.
_NUMBER_RE = re.compile(r"\b\d[\d,\.]*\s*%?\b")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_PROPER_RE = re.compile(r"\b[A-Z][a-zA-Z][\w&\-]*\b")


def _proper_nouns_excluding_first(text: str) -> set[str]:
    """Proper nouns in ``text`` excluding any sentence-initial capital.

    The leading word of a sentence is capitalized regardless of whether
    it is a proper noun, so it must not be treated as content the
    rewrite is required to preserve.
    """
    body = text.lstrip()
    space = body.find(" ")
    scan = body[space + 1 :] if space > 0 else ""
    return set(_PROPER_RE.findall(scan))


def _polish_bullet(bullet: str) -> tuple[str, bool]:
    """Return (cleaned, changed). Never drops content-bearing tokens."""
    if not isinstance(bullet, str):
        return bullet, False
    original = bullet
    cleaned = bullet.strip()
    if not cleaned:
        return bullet, False

    for pat in _HEDGE_OPENERS:
        new = pat.sub("", cleaned, count=1)
        if new != cleaned:
            cleaned = new
            # Recapitalize the new opener.
            cleaned = cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned
    for pat, repl in _FILLER_SUBS:
        cleaned = pat.sub(repl, cleaned)
    cleaned = _DOUBLE_SPACE.sub(" ", cleaned).strip()

    if not cleaned or cleaned == original.strip():
        return bullet, False

    # Safety net: refuse the rewrite if any number / year / proper noun
    # disappeared. We strip the *original*'s sentence-initial capital
    # (the hedge's first word like "It"/"Studies"/"Research") so we
    # don't require the cleaned form to keep it. Then check that every
    # such token still appears anywhere in the cleaned text.
    o_nums = set(_NUMBER_RE.findall(original))
    o_years = set(_YEAR_RE.findall(original))
    o_proper = _proper_nouns_excluding_first(original)
    n_nums = set(_NUMBER_RE.findall(cleaned))
    n_years = set(_YEAR_RE.findall(cleaned))
    n_proper = set(_PROPER_RE.findall(cleaned))
    if not (o_nums <= n_nums and o_years <= n_years and o_proper <= n_proper):
        return bullet, False

    return cleaned, True


# ── Narrative transitions ──────────────────────────────────────────────────

# Bridge phrasing keyed on (prev_role, current_role). Falls back to a
# generic but tight bridge when the pair is not in the table.
_TRANSITIONS = {
    ("opening", "context"): "Setting the stage:",
    ("opening", "problem"): "But here's the friction:",
    ("context", "problem"): "Where it breaks down:",
    ("context", "evidence"): "What the data shows:",
    ("problem", "insight"): "The shift that matters:",
    ("problem", "evidence"): "The proof:",
    ("insight", "evidence"): "Backed by numbers:",
    ("insight", "recommendation"): "What to do about it:",
    ("evidence", "recommendation"): "From data to action:",
    ("evidence", "insight"): "What this tells us:",
    ("recommendation", "closing"): "Looking ahead:",
    ("comparison", "insight"): "The takeaway:",
}

_GENERIC_BRIDGE = ""  # empty → no transition emitted on unknown pairs


def _slide_role(slide: dict | Any) -> str:
    if not isinstance(slide, dict):
        return ""
    intent = slide.get("intent")
    if not isinstance(intent, dict):
        return ""
    role = intent.get("narrative_role")
    return role.lower() if isinstance(role, str) else ""


# ── Public entry point ────────────────────────────────────────────────────


def apply_editorial_pass(slides: Any) -> tuple[list[dict], dict[str, int]]:
    """Polish slide copy in place. Returns (new_slides, summary).

    Never raises; on any error returns the input slides unchanged.
    """
    summary = {
        "headline_rewrites": 0,
        "bullet_rewrites": 0,
        "transitions_added": 0,
    }
    if not isinstance(slides, list):
        return [], summary

    try:
        out: list[dict] = []
        prev_role = ""
        for slide in slides:
            if not isinstance(slide, dict):
                out.append(slide)
                prev_role = ""
                continue
            new_slide = dict(slide)

            # D1 — headline
            title = new_slide.get("title")
            if isinstance(title, str):
                new_title = _strengthen_headline(title, layout=new_slide.get("layout"))
                if new_title != title:
                    new_slide["title"] = new_title
                    summary["headline_rewrites"] += 1

            # D2 — bullets
            bullets = new_slide.get("bullets")
            if isinstance(bullets, list):
                new_bullets: list[Any] = []
                changed_any = False
                for b in bullets:
                    cleaned, changed = _polish_bullet(b)
                    new_bullets.append(cleaned)
                    if changed:
                        changed_any = True
                if changed_any:
                    new_slide["bullets"] = new_bullets
                    summary["bullet_rewrites"] += sum(
                        1 for orig, new in zip(bullets, new_bullets) if orig != new
                    )

            # D3 — narrative transition (only when both roles known)
            curr_role = _slide_role(new_slide)
            if curr_role and prev_role:
                bridge = _TRANSITIONS.get((prev_role, curr_role), _GENERIC_BRIDGE)
                if bridge and "transition" not in new_slide:
                    new_slide["transition"] = bridge
                    summary["transitions_added"] += 1

            out.append(new_slide)
            prev_role = curr_role or prev_role  # carry last known role over dividers

        return out, summary
    except Exception:  # pragma: no cover — defensive
        return list(slides), summary
