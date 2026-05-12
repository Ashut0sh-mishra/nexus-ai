"""Phase 6AL-Voice — deterministic editorial-voice pass.

Pure / offline / additive content-layer polish for slide copy. Runs in
``agent.loop.NexusAgentLoop`` AFTER ``editorial_pass`` and BEFORE
``cinematic_marker``.

What it does, conservatively:

* **A1 — Headline rewriter.** Detects category-label headlines
  ("Problem Statement", "Traction Metrics", "Investment Ask",
  "Overview", "Conclusion", …) and replaces them with an authored
  sentence derived from existing slide content. No LLM, no network.
  Strategies in priority order:

    1. Promote a meaningful ``subtitle`` to the title.
    2. For ``bigstat``: synthesize ``"{value} {label}"`` (e.g.
       "25% monthly user growth").
    3. For ``closing`` with a button-shaped ``cta``: promote the
       imperative ``cta`` (e.g. "Request a Pilot") to the title.
    4. If no rewrite is safe → leave the title untouched.

* **A2 — Subtitle filler killer.** Drops subtitles that match a
  banlist of vague AI-generated phrases ("A Fundable Story",
  "Join Our Mission", "An Overview", "Key Insights", "Our Story",
  …), or that exactly equal / are a substring of the title, or
  that contain the placeholder "No prompt for …".

* **A3 — Transition sanitizer.** Strips ``slide["transition"]`` when
  it matches a set of debug-grade bridge phrases the prior editorial
  pass may have inserted ("Setting the stage:", "What the data shows:",
  "Up next:", …). The transitions are interstitial labels, not deck
  voice, and they ship as content otherwise. The renderer treats a
  missing transition the same as an empty one.

* **A4 — Closing rewriter.** For ``layout == "closing"`` slides whose
  ``title`` is a category label and whose ``cta`` is a short
  imperative ("Get Started", "Request a Pilot — 15 Min"), the title
  takes the cta phrasing and the cta field is cleared (renderer
  re-derives a button label from it later if needed).

Architectural rules:

* **No LLM calls, no network, no randomness, no I/O.**
* **Never raises** — on any error returns input slides unchanged.
* **Additive only**:

  - title rewrites only happen when a *clearly safer* replacement is
    available from the slide's own content. If nothing safer exists,
    the original title is kept.
  - subtitles are removed (set to ``""``), not mutated.
  - transitions are removed (key deleted), not mutated.
  - no new fields are introduced. Schema unchanged. Validator
    contract preserved.

* **Exporter compatibility**: PPTX/PDF read ``slide["title"]`` and
  ``slide["subtitle"]`` exactly as before. Removing a generic
  subtitle is the same as if the planner had left it empty.

* **Kill switch**: ``NEXUS_DISABLE_VOICE_PASS=true`` short-circuits
  the pass to a no-op without removing the import.

Output summary returned by :func:`apply_voice_pass`::

    {
        "headline_rewrites": int,
        "subtitle_kills": int,
        "transition_scrubs": int,
        "closing_rewrites": int,
    }
"""

from __future__ import annotations

import os
import re
from typing import Any

__all__ = ["apply_voice_pass"]


# ── A1 — Category-label headline detection ─────────────────────────────────

# A category-label headline is a *slide-type name*, not a sentence.
# Examples from real Phase 6AK output:
#   "Problem Statement", "Traction Metrics", "Investment Ask",
#   "Daily Wellness Tools", "Monthly Active Users", "Growing Demand".
# We match either:
#   - a fixed single-word label  ("Overview", "Conclusion", …)
#   - a "<Adjective?> <Domain> <Slot>" pattern where Slot is one of a
#     small fixed vocabulary of slide-type names.
_LABEL_SLOTS = (
    "statement",
    "metrics",
    "metric",
    "ask",
    "asks",
    "update",
    "updates",
    "tools",
    "plan",
    "plans",
    "analysis",
    "results",
    "result",
    "strategy",
    "approach",
    "review",
    "outlook",
    "summary",
    "overview",
    "introduction",
    "highlights",
    "insights",
    "insight",
    "recommendations",
    "recommendation",
    "conclusions",
    "conclusion",
    "background",
    "context",
    "objectives",
    "objective",
    "goals",
    "goal",
    "agenda",
    "roadmap",
)

_SINGLE_LABEL_WORDS = {
    "overview",
    "introduction",
    "summary",
    "conclusion",
    "background",
    "context",
    "agenda",
    "objectives",
    "goals",
    "highlights",
    "insights",
    "recommendations",
    "results",
    "metrics",
    "approach",
    "strategy",
    "problem",
    "solution",
    "traction",
    "market",
    "team",
    "outlook",
    "roadmap",
}

_LABEL_HEAD_PATTERN = re.compile(
    r"^(?P<head>[A-Za-z][\w\-]*(?:\s+[A-Za-z][\w\-]*){0,3})\s+(?P<slot>"
    + "|".join(_LABEL_SLOTS)
    + r")\.?$",
    re.IGNORECASE,
)


def _is_category_label(title: str) -> bool:
    if not isinstance(title, str):
        return False
    t = title.strip().strip(".:")
    if not t:
        return False
    words = t.split()
    if len(words) == 1 and t.lower() in _SINGLE_LABEL_WORDS:
        return True
    if len(words) <= 5 and _LABEL_HEAD_PATTERN.match(t):
        return True
    return False


# ── A2 — Generic subtitle banlist ──────────────────────────────────────────

# Exact-match (case-insensitive) generic subtitles observed in real
# Phase 6AK output. Conservative: only kills what is plainly filler.
_GENERIC_SUBTITLES = {
    "a fundable story",
    "join our mission",
    "an overview",
    "key insights",
    "key takeaways",
    "our story",
    "our approach",
    "our mission",
    "our vision",
    "the solution",
    "the problem",
    "the opportunity",
    "moving forward",
    "looking ahead",
    "in summary",
    "in conclusion",
    "what's next",
    "next steps",
}

# Placeholder strings that should never ship.
_PLACEHOLDER_PATTERNS = (
    re.compile(r"^\s*no\s+prompt\s+for\s+slide", re.IGNORECASE),
    re.compile(r"^\s*sample\s+subtitle", re.IGNORECASE),
    re.compile(r"^\s*lorem\s+ipsum", re.IGNORECASE),
    re.compile(r"^\s*tbd\s*$", re.IGNORECASE),
    re.compile(r"^\s*todo\s*:?\s*$", re.IGNORECASE),
)


def _is_filler_subtitle(subtitle: str, *, title: str) -> bool:
    if not isinstance(subtitle, str):
        return False
    s = subtitle.strip()
    if not s:
        return False
    norm = s.lower().strip(".:")
    if norm in _GENERIC_SUBTITLES:
        return True
    for pat in _PLACEHOLDER_PATTERNS:
        if pat.search(s):
            return True
    if isinstance(title, str) and title.strip():
        t_norm = title.strip().lower()
        if norm == t_norm:
            return True
        # subtitle is a substring of the title (or vice versa) → redundant.
        if len(norm) >= 4 and (norm in t_norm or t_norm in norm):
            return True
    return False


# ── A3 — Debug-grade transition phrases (from editorial_pass) ──────────────

# These were inserted by ``editorial_pass._TRANSITIONS``. They read as
# interstitial labels, not deck voice. We strip them.
_DEBUG_TRANSITIONS = {
    "setting the stage:",
    "but here's the friction:",
    "where it breaks down:",
    "what the data shows:",
    "the shift that matters:",
    "the proof:",
    "backed by numbers:",
    "what to do about it:",
    "from data to action:",
    "what this tells us:",
    "looking ahead:",
    "the takeaway:",
    "up next:",
    "now:",
}


def _is_debug_transition(transition: str) -> bool:
    if not isinstance(transition, str):
        return False
    return transition.strip().lower() in _DEBUG_TRANSITIONS


# ── A4 — Closing button-shaped CTA detection ───────────────────────────────

# CTAs that read like buttons. When the title is a category label and
# the cta is one of these, the cta becomes the title.
_BUTTON_CTA_VERBS = (
    "request",
    "book",
    "schedule",
    "try",
    "get",
    "start",
    "sign up",
    "join",
    "contact",
    "talk",
    "reach out",
    "learn more",
    "explore",
    "begin",
    "apply",
    "register",
    "subscribe",
    "download",
)

_CTA_PATTERN = re.compile(
    r"^(?:" + "|".join(re.escape(v) for v in _BUTTON_CTA_VERBS) + r")\b",
    re.IGNORECASE,
)


def _is_button_cta(cta: str) -> bool:
    if not isinstance(cta, str):
        return False
    s = cta.strip()
    if not s or len(s) > 40:
        return False
    return bool(_CTA_PATTERN.match(s))


# ── A1 helpers: pick a safe replacement title from existing content ────────

def _looks_meaningful_subtitle(subtitle: str, *, title: str) -> bool:
    """Subtitle is a candidate to *replace* the title.

    Must be non-empty, non-filler, contain a content word, and be
    different from the title.
    """
    if not isinstance(subtitle, str):
        return False
    s = subtitle.strip()
    if not s or len(s) > 80:
        return False
    if _is_filler_subtitle(s, title=title):
        return False
    if len(s.split()) < 2:
        return False
    return True


def _bigstat_synthesized_title(slide: dict) -> str | None:
    """For bigstat: ``"{value} {label}"`` if both are usable."""
    value = slide.get("value")
    label = slide.get("label")
    if not isinstance(value, str) or not isinstance(label, str):
        return None
    v = value.strip()
    lab = label.strip()
    if not v or not lab:
        return None
    if len(lab.split()) > 6:
        return None
    # Lowercase the label unless it starts with a proper noun
    # (heuristic: keep capitalization as-is — labels are usually
    # already short noun phrases like "Monthly User Growth").
    composed = f"{v} {lab}"
    return composed if len(composed) <= 60 else None


def _rewrite_title(slide: dict) -> str | None:
    """Return a replacement title or ``None`` if no safe rewrite exists."""
    title = slide.get("title")
    if not isinstance(title, str) or not _is_category_label(title):
        return None

    layout = slide.get("layout") or ""

    # Strategy 1: meaningful subtitle → promote.
    subtitle = slide.get("subtitle")
    if isinstance(subtitle, str) and _looks_meaningful_subtitle(subtitle, title=title):
        return subtitle.strip().rstrip(".")

    # Strategy 2: bigstat synthesis.
    if layout == "bigstat":
        synth = _bigstat_synthesized_title(slide)
        if synth:
            return synth

    # Strategy 3: closing with button-shaped cta.
    if layout == "closing":
        cta = slide.get("cta")
        if isinstance(cta, str) and _is_button_cta(cta):
            return cta.strip().rstrip(".")

    # No safe rewrite — keep the original title.
    return None


# ── Public entry point ─────────────────────────────────────────────────────


def apply_voice_pass(slides: Any) -> tuple[list[dict], dict[str, int]]:
    """Polish slide voice in place. Returns (new_slides, summary).

    Deterministic, additive, never raises. Kill-switch:
    ``NEXUS_DISABLE_VOICE_PASS=true``.
    """
    summary = {
        "headline_rewrites": 0,
        "subtitle_kills": 0,
        "transition_scrubs": 0,
        "closing_rewrites": 0,
    }
    if not isinstance(slides, list):
        return [], summary

    if os.environ.get("NEXUS_DISABLE_VOICE_PASS", "").lower() == "true":
        return list(slides), summary

    try:
        out: list[dict] = []
        for slide in slides:
            if not isinstance(slide, dict):
                out.append(slide)
                continue
            new_slide = dict(slide)

            # A3 — transition sanitizer (do first; may inform A4).
            transition = new_slide.get("transition")
            if isinstance(transition, str) and _is_debug_transition(transition):
                new_slide.pop("transition", None)
                summary["transition_scrubs"] += 1

            # A2 — subtitle filler killer (do before A1 so A1 doesn't
            # promote a filler subtitle).
            subtitle = new_slide.get("subtitle")
            if isinstance(subtitle, str) and _is_filler_subtitle(
                subtitle, title=new_slide.get("title", "")
            ):
                new_slide["subtitle"] = ""
                summary["subtitle_kills"] += 1

            # A1 — headline rewriter (and A4 — closing rewriter, which
            # is a special case of A1 routed by layout).
            rewritten = _rewrite_title(new_slide)
            if rewritten is not None and rewritten != new_slide.get("title"):
                old_layout = new_slide.get("layout") or ""
                new_slide["title"] = rewritten
                summary["headline_rewrites"] += 1
                if old_layout == "closing":
                    summary["closing_rewrites"] += 1
                    # The cta has been promoted to title; clear it so the
                    # renderer does not show the same text twice.
                    if isinstance(new_slide.get("cta"), str) and new_slide.get(
                        "cta", ""
                    ).strip().rstrip(".") == rewritten:
                        new_slide["cta"] = ""
                # If we promoted a subtitle to title, blank the
                # subtitle so the renderer does not show duplicate text.
                if (
                    isinstance(slide.get("subtitle"), str)
                    and slide.get("subtitle", "").strip().rstrip(".") == rewritten
                ):
                    new_slide["subtitle"] = ""

            out.append(new_slide)

        return out, summary
    except Exception:  # pragma: no cover — defensive
        return list(slides), summary
