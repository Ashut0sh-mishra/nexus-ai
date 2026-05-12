"""Phase 6AA — deterministic post-planner layout upgrader.

The planner emits a layout per slide chosen from the seven legacy
canonical layouts (``title``, ``bullets``, ``two-col``, ``quote``,
``stats``, ``chart``, ``closing``). The recommender runs *after*
``_normalize_slides`` and ``attach_slide_intent`` and looks for two
specific upgrade conditions where a more expressive Phase-6AA layout
is unambiguously better:

* ``bigstat``         — a slide with one dominant single metric
                          (one stats item, or a numeric stats payload
                          where the first value visually dwarfs the
                          rest), AND ``intent.density`` is low / medium.
* ``section_divider`` — a slide whose ``intent.narrative_role`` is
                          ``turning_point`` AND ``intent.density`` is
                          ``low``. Drops bullet bodies because section
                          dividers are pure typography.

The recommender NEVER:

* Replaces the planner's layout when the upgrade conditions are not
  unambiguously met.
* Mutates the input list (returns a new list of new dicts).
* Touches the first slide (always ``title``) or the last slide
  (always ``closing``) — those are pinned by ``_normalize_slides``.
* Invents content. The upgrade only re-shapes existing fields and
  drops fields the new layout cannot use.

Returns ``(slides, upgrades)`` where ``upgrades`` is a list of
``{slide_index, from, to, reason}`` records the loop emits as
``design_decision`` events so the UI can show why the upgrade fired.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("nexus.agent.layout_recommender")


# ── Heuristics ─────────────────────────────────────────────────────────────


_NUMERIC_VALUE_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")

# Phase 6AC — patterns that mark a bullet/heading as a chronology event.
# Order: most specific first. The capture group is the date token; the
# remainder of the bullet becomes the event label.
_DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 1980, 2024, 1879
    re.compile(r"^\s*(\d{4})\s*[—–\-:]\s*(.+?)\s*$"),
    # September 22, 1980 — Iraq invades / Sep 1980: ...
    re.compile(
        r"^\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
        r"(?:\s+\d{1,2})?(?:,?\s+\d{4})?)\s*[—–\-:]\s*(.+?)\s*$",
        re.IGNORECASE,
    ),
    # 2024-01-15: ...
    re.compile(r"^\s*(\d{4}-\d{2}(?:-\d{2})?)\s*[—–\-:]\s*(.+?)\s*$"),
    # Q1 2024 — ...
    re.compile(r"^\s*(Q[1-4]\s+\d{4})\s*[—–\-:]\s*(.+?)\s*$", re.IGNORECASE),
    # 1980s — ...
    re.compile(r"^\s*(\d{4}s)\s*[—–\-:]\s*(.+?)\s*$"),
)

# Phase 6AC — keyword pairs that signal an explicit comparison. Detection
# requires BOTH columns to mention contrast cues, OR the slide title to
# carry an explicit "X vs Y" / "Before / After" framing.
_COMPARISON_TITLE_RE = re.compile(
    r"\b(vs\.?|versus|before\s+(?:and|/|vs\.?)\s+after|then\s+(?:and|vs\.?)\s+now"
    r"|old\s+(?:vs\.?|/)\s+new|with\s+(?:and|vs\.?)\s+without)\b",
    re.IGNORECASE,
)
_COMPARISON_HEADING_PAIRS: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (frozenset({"before"}), frozenset({"after"})),
    (frozenset({"old"}), frozenset({"new"})),
    (frozenset({"current", "today", "now"}), frozenset({"future", "tomorrow", "next"})),
    (frozenset({"with"}), frozenset({"without"})),
    (frozenset({"pros", "advantages", "benefits"}), frozenset({"cons", "drawbacks", "risks"})),
    (frozenset({"problem"}), frozenset({"solution"})),
    (frozenset({"challenge"}), frozenset({"response"})),
)


def _looks_dominant_metric(stats: list[dict[str, Any]]) -> bool:
    """Return True when the first stat numerically dwarfs the rest.

    Definition of "dwarfs": parsable numeric values, the first value's
    absolute magnitude is at least 3x the largest of the others, OR
    there is only one stat. We strip currency / percent / unit suffixes
    so ``"$4.2B"`` and ``"93%"`` parse cleanly.
    """
    if not stats:
        return False
    if len(stats) == 1:
        # Single stat is dominant by definition only when it has a
        # parsable value (otherwise upgrading hides a real defect).
        v = _parse_number(stats[0].get("value"))
        return v is not None
    nums = [_parse_number(s.get("value")) for s in stats]
    if any(n is None for n in nums):
        return False
    head, *rest = nums
    head_abs = abs(head)
    rest_max = max((abs(x) for x in rest), default=0.0)
    if head_abs == 0:
        return False
    return head_abs >= 3.0 * rest_max if rest_max > 0 else True


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value)
    match = _NUMERIC_VALUE_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _intent(slide: dict[str, Any]) -> dict[str, Any]:
    intent = slide.get("intent")
    return intent if isinstance(intent, dict) else {}


# ── Upgraders (return None when the slide is unchanged) ────────────────────


def _try_bigstat_upgrade(slide: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    """Promote a stats slide carrying one dominant metric to ``bigstat``.

    Only fires when:
    * Current layout is ``stats``.
    * ``stats[0]`` exists, has a non-empty value, and either is the
      only stat or numerically dwarfs the rest.
    * Intent density is not ``high`` (``high`` means we WANT the full
      grid; downgrading to one number would lose information).
    """
    if slide.get("layout") != "stats":
        return None
    stats = slide.get("stats")
    if not isinstance(stats, list) or not stats:
        return None
    first = stats[0]
    if not isinstance(first, dict):
        return None
    value = str(first.get("value") or "").strip()
    if not value:
        return None
    if not _looks_dominant_metric(stats):
        return None

    density = (_intent(slide).get("density") or "").lower()
    if density == "high":
        return None

    upgraded = {
        **{k: v for k, v in slide.items() if k != "stats"},
        "layout": "bigstat",
        "value": value,
        "label": str(first.get("label") or "").strip(),
        # Preserve any subtitle the planner produced; bigstat uses it
        # as a one-line framing under the hero number.
        "subtitle": str(slide.get("subtitle") or "").strip(),
    }
    rest_count = max(0, len(stats) - 1)
    reason = (
        f"Single dominant metric '{value}'"
        + (f" (other {rest_count} stat(s) trail by ≥3×)" if rest_count else "")
        + "."
    )
    return upgraded, reason


def _try_section_divider_upgrade(
    slide: dict[str, Any],
) -> tuple[dict[str, Any], str] | None:
    """Promote a low-density turning_point slide to ``section_divider``.

    Phase 6AD broadens the trigger: a slide whose intent ``beat`` is
    ``turning_point`` (regardless of density) also qualifies, because
    beat-based turning points are explicit dramatic-shape signals.

    Other conditions:
    * Current layout is ``bullets`` (the most common low-impact slot).
    * If the slide carries no beat-based turning_point signal, the
      legacy fallback still applies: ``narrative_role`` is
      ``turning_point`` AND density is ``low``.
    * Bullets list is empty or all bullets are short blurbs (≤ 60
      chars). We will drop bullets, so we refuse to upgrade if doing
      so would lose substantive content.
    """
    if slide.get("layout") != "bullets":
        return None
    intent = _intent(slide)
    beat = (intent.get("beat") or "").lower()
    role = (intent.get("narrative_role") or "").lower()
    density = (intent.get("density") or "").lower()
    is_beat_turning = beat == "turning_point"
    is_role_turning = role == "turning_point" and density == "low"
    if not (is_beat_turning or is_role_turning):
        return None

    bullets = slide.get("bullets") or []
    if not isinstance(bullets, list):
        return None
    # Refuse to upgrade if any bullet is long-form — the recommender
    # would otherwise drop substantive content.
    long_bullets = [b for b in bullets if isinstance(b, str) and len(b) > 60]
    if long_bullets:
        return None

    # Promote the first short bullet (if any) to subtitle so we don't
    # silently lose it.
    subtitle_seed = ""
    for b in bullets:
        if isinstance(b, str) and b.strip():
            subtitle_seed = b.strip()
            break

    upgraded = {
        **{k: v for k, v in slide.items() if k != "bullets"},
        "layout": "section_divider",
        "eyebrow": "",
        "subtitle": subtitle_seed,
    }
    if is_beat_turning:
        reason = "Narrative beat reaches turning point — typography pause marks the shift."
    else:
        reason = "Turning-point slide with low density — typography pause beats bullet list."
    return upgraded, reason


def _extract_timeline_events(bullets: list[Any]) -> list[dict[str, str]]:
    """Parse a bullets list into ``[{date, label}, ...]``.

    Returns the events that match a date pattern, in original order.
    Bullets that do not match are skipped. The caller decides whether
    the count is high enough to justify a timeline upgrade.
    """
    out: list[dict[str, str]] = []
    for b in bullets:
        if not isinstance(b, str):
            continue
        text = b.strip()
        if not text:
            continue
        for pat in _DATE_PATTERNS:
            m = pat.match(text)
            if m:
                date = m.group(1).strip()
                label = m.group(2).strip()
                if date and label:
                    out.append({"date": date, "label": label})
                break
    return out


def _try_timeline_upgrade(slide: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    """Promote a bullets slide whose entries are dated events into ``timeline``.

    Only fires when:
    * Current layout is ``bullets``.
    * At least 3 of the bullets parse cleanly as ``date — label``.
    * All parsed events come from a matching pattern (no mixing
      "1980 — Invasion" with random non-dated bullets that would be lost).
    """
    if slide.get("layout") != "bullets":
        return None
    bullets = slide.get("bullets") or []
    if not isinstance(bullets, list) or len(bullets) < 3:
        return None
    events = _extract_timeline_events(bullets)
    if len(events) < 3:
        return None
    # Refuse to upgrade if it would silently drop a substantive bullet
    # — any non-dated bullet present means we would lose information.
    non_dated = [
        b for b in bullets if isinstance(b, str) and b.strip() and not _is_dated_bullet(b)
    ]
    if non_dated:
        return None

    upgraded = {
        **{k: v for k, v in slide.items() if k != "bullets"},
        "layout": "timeline",
        "events": events[:6],
        "subtitle": str(slide.get("subtitle") or "").strip(),
    }
    reason = f"Detected {len(events)} dated events — chronology beats bullet list."
    return upgraded, reason


def _is_dated_bullet(text: str) -> bool:
    if not isinstance(text, str):
        return False
    return any(pat.match(text.strip()) for pat in _DATE_PATTERNS)


def _try_comparison_upgrade(slide: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    """Promote a two-col slide carrying explicit contrast into ``comparison``.

    Only fires when:
    * Current layout is ``two-col``.
    * Either the slide title carries an explicit comparison cue (``vs``,
      ``before/after``, ``old vs new``, etc.), OR both column headings
      are drawn from a known antonym pair (``before``↔``after``,
      ``problem``↔``solution``, …).
    * Both columns have a non-empty heading and body.

    The body content is preserved verbatim — comparison is just a
    re-shaping of two-col into a more expressive primitive.
    """
    if slide.get("layout") != "two-col":
        return None
    cols = slide.get("columns") or []
    if not isinstance(cols, list) or len(cols) < 2:
        return None
    left_col, right_col = cols[0], cols[1]
    if not isinstance(left_col, dict) or not isinstance(right_col, dict):
        return None
    left_heading = (left_col.get("heading") or "").strip()
    right_heading = (right_col.get("heading") or "").strip()
    left_body = (left_col.get("body") or "").strip()
    right_body = (right_col.get("body") or "").strip()
    if not (left_heading and right_heading and left_body and right_body):
        return None

    title = slide.get("title") or ""
    title_match = bool(_COMPARISON_TITLE_RE.search(title))
    pair_match = _matches_comparison_pair(left_heading, right_heading)
    if not (title_match or pair_match):
        return None

    upgraded = {
        **{k: v for k, v in slide.items() if k != "columns"},
        "layout": "comparison",
        "left": {"heading": left_heading, "body": left_body},
        "right": {"heading": right_heading, "body": right_body},
        "subtitle": str(slide.get("subtitle") or "").strip(),
    }
    if pair_match:
        reason = f"Headings form contrast pair ('{left_heading}' vs '{right_heading}')."
    else:
        reason = "Title carries explicit comparison framing."
    return upgraded, reason


def _matches_comparison_pair(left: str, right: str) -> bool:
    left_words = {w for w in re.findall(r"\b\w+\b", left.lower())}
    right_words = {w for w in re.findall(r"\b\w+\b", right.lower())}
    for l_set, r_set in _COMPARISON_HEADING_PAIRS:
        if (left_words & l_set) and (right_words & r_set):
            return True
        if (left_words & r_set) and (right_words & l_set):
            return True
    return False


_UPGRADERS = (
    _try_bigstat_upgrade,
    _try_section_divider_upgrade,
    _try_timeline_upgrade,
    _try_comparison_upgrade,
    None,  # placeholder; assigned below after _try_quote_upgrade is defined
)


# ── Phase 6AI-B7 — Quote enforcement ──────────────────────────────────────

# A bullet that looks like a quote: starts and ends with a quotation mark
# OR contains an em-dash attribution after a long string. We require the
# quoted body to be at least 8 words so we don't promote one-liners.
_QUOTE_DELIMS = ("\u201c", "\u201d", "\u2018", "\u2019", "\"", "'")
_ATTRIBUTION_RE = re.compile(r"\s+[—–-]\s+([A-Z][A-Za-z .'’\-]{2,80})\s*$")


def _looks_like_quote(text: str) -> tuple[str, str] | None:
    """Return (quote_text, attribution) when the bullet reads like a quote."""
    if not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None
    attribution = ""
    quote_body = raw
    m = _ATTRIBUTION_RE.search(raw)
    if m:
        attribution = m.group(1).strip()
        quote_body = raw[: m.start()].strip()
    starts_quoted = quote_body[:1] in _QUOTE_DELIMS
    ends_quoted = quote_body[-1:] in _QUOTE_DELIMS
    if starts_quoted and ends_quoted:
        # strip outer quotes
        quote_body = quote_body[1:-1].strip()
    elif not (starts_quoted or attribution):
        return None
    word_count = len(re.findall(r"\w+", quote_body))
    if word_count < 8:
        return None
    return quote_body, attribution


def _try_quote_upgrade(slide: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    """Promote a bullets slide whose first long bullet reads like a quote.

    Conservative: only fires when bullets has exactly one entry that
    looks like a quote, OR when the longest bullet is unambiguously a
    quoted snippet ≥8 words. Never drops other substantive bullets —
    if there are 2+ non-quote bullets, the upgrade is refused.
    """
    if slide.get("layout") != "bullets":
        return None
    bullets = slide.get("bullets") or []
    if not isinstance(bullets, list) or not bullets:
        return None
    candidate: tuple[str, str] | None = None
    other_substantive = 0
    for b in bullets:
        parsed = _looks_like_quote(b)
        if parsed is not None and candidate is None:
            candidate = parsed
        elif isinstance(b, str) and b.strip() and len(b.strip()) > 12:
            other_substantive += 1
    if candidate is None or other_substantive >= 2:
        return None
    quote_body, attribution = candidate
    word_count = len(re.findall(r"\w+", quote_body))
    upgraded = {
        **{k: v for k, v in slide.items() if k != "bullets"},
        "layout": "quote",
        "quote": quote_body,
        "attribution": attribution,
    }
    reason = (
        f"Detected a {word_count}-word quoted statement"
        + (f" attributed to {attribution}" if attribution else "")
        + " — quote layout carries the voice."
    )
    return upgraded, reason


# Patch the placeholder in _UPGRADERS so the registration order is
# stable and other upgraders run first (quote is the most aggressive
# rewrite — it discards bullet structure).
_UPGRADERS = tuple(u for u in _UPGRADERS if u is not None) + (_try_quote_upgrade,)


# ── Phase 6AI-B1 — Hero-slide enforcement ─────────────────────────────────


def enforce_hero(
    slides: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Ensure the deck has at least one hero ``bigstat`` slide.

    Runs *after* ``recommend_layouts``. If the deck already contains a
    ``bigstat`` slide anywhere, this is a no-op. Otherwise the function
    looks for the best candidate to promote — preferring a ``stats``
    slide in the first half of the deck, falling back to any later
    ``stats`` slide. The promotion uses ``stats[0]`` as the hero
    metric. Never touches the first slide (always ``title``) or the
    last slide (always ``closing``).

    Returns ``(slides, upgrades)`` where ``upgrades`` is at most one
    record (or empty when no candidate exists). Each upgrade record
    matches the ``recommend_layouts`` shape so the loop can emit the
    same ``design_decision`` event for it.
    """
    if not isinstance(slides, list) or len(slides) < 3:
        return (slides if isinstance(slides, list) else [], [])

    # Already have a hero?
    for s in slides:
        if isinstance(s, dict) and s.get("layout") == "bigstat":
            return slides, []

    last = len(slides) - 1
    midpoint = max(1, len(slides) // 2)

    def _candidate_score(idx: int, slide: dict[str, Any]) -> int | None:
        if idx == 0 or idx == last:
            return None
        if slide.get("layout") != "stats":
            return None
        stats = slide.get("stats")
        if not isinstance(stats, list) or not stats:
            return None
        first = stats[0] if isinstance(stats[0], dict) else None
        if not first:
            return None
        value = str(first.get("value") or "").strip()
        if not value:
            return None
        # Earlier slides score higher (lower idx). Slides in the first
        # half score better than later. A slight bonus for a parsable
        # number.
        score = 100 - idx * 5
        if idx <= midpoint:
            score += 20
        if _parse_number(value) is not None:
            score += 5
        return score

    best_idx: int | None = None
    best_score = -1
    for i, s in enumerate(slides):
        if not isinstance(s, dict):
            continue
        score = _candidate_score(i, s)
        if score is not None and score > best_score:
            best_idx = i
            best_score = score

    if best_idx is None:
        return slides, []

    target = slides[best_idx]
    stats = target.get("stats") or []
    first = stats[0] if (stats and isinstance(stats[0], dict)) else {}
    value = str(first.get("value") or "").strip()
    label = str(first.get("label") or "").strip()
    promoted = {
        **{k: v for k, v in target.items() if k != "stats"},
        "layout": "bigstat",
        "value": value,
        "label": label,
        "subtitle": str(target.get("subtitle") or "").strip(),
    }
    out = list(slides)
    out[best_idx] = promoted
    upgrades = [
        {
            "slide_index": best_idx + 1,
            "from": "stats",
            "to": "bigstat",
            "reason": (
                "Hero enforcement — deck lacked a single dominant moment; "
                f"promoted slide {best_idx + 1}'s headline metric '{value}' "
                "to a full-bleed hero."
            ),
        }
    ]
    return out, upgrades


# ── Phase 6AI-B6 — Section divider auto-insertion ─────────────────────────


def insert_section_dividers(
    slides: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Insert a single ``section_divider`` near the deck midpoint.

    Only fires when:
    * The deck has at least 7 slides.
    * No ``section_divider`` is already present.
    * A reasonable insertion point (between two non-pinned slides) exists.

    The inserted divider's ``title`` mirrors the title of the slide that
    follows it (so the divider reads as a chapter header). Pure-Python,
    deterministic, additive.
    """
    if not isinstance(slides, list) or len(slides) < 7:
        return (slides if isinstance(slides, list) else [], [])
    for s in slides:
        if isinstance(s, dict) and s.get("layout") == "section_divider":
            return slides, []
    last = len(slides) - 1
    insert_at = max(2, min(last - 1, len(slides) // 2))
    next_slide = slides[insert_at] if isinstance(slides[insert_at], dict) else {}
    follow_title = str(next_slide.get("title") or "").strip() or "Next"
    divider = {
        "id": f"divider-{insert_at}",
        "layout": "section_divider",
        "eyebrow": "Section",
        "title": follow_title,
        "subtitle": "",
    }
    out = list(slides[:insert_at]) + [divider] + list(slides[insert_at:])
    upgrades = [
        {
            "slide_index": insert_at + 1,
            "from": None,
            "to": "section_divider",
            "reason": (
                f"Long deck ({len(slides)} slides) had no chapter break — "
                f"inserted a typography pause before '{follow_title}'."
            ),
        }
    ]
    return out, upgrades


# ── Public API ─────────────────────────────────────────────────────────────


def recommend_layouts(
    slides: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply deterministic per-slide layout upgrades.

    Pure function — returns a new list. The first and last slides are
    always preserved (pinned by ``_normalize_slides``). Failures in any
    individual upgrader are isolated; the original slide passes through.

    Returns ``(slides, upgrades)`` where ``upgrades`` is a list of
    ``{slide_index (1-based), from, to, reason}`` records suitable for
    direct emission as ``design_decision`` events.
    """
    if not isinstance(slides, list) or not slides:
        return (slides if isinstance(slides, list) else [], [])

    out: list[dict[str, Any]] = []
    upgrades: list[dict[str, Any]] = []
    last = len(slides) - 1

    for i, slide in enumerate(slides):
        if not isinstance(slide, dict):
            out.append(slide)
            continue
        # Never re-layout pinned ends.
        if i == 0 or i == last:
            out.append(slide)
            continue
        original_layout = slide.get("layout")
        chosen: dict[str, Any] = slide
        for upgrader in _UPGRADERS:
            try:
                result = upgrader(slide)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "layout_recommender.upgrader_failed",
                    extra={"err": str(exc), "fn": upgrader.__name__},
                )
                continue
            if result is not None:
                upgraded, reason = result
                chosen = upgraded
                upgrades.append(
                    {
                        "slide_index": i + 1,
                        "from": original_layout,
                        "to": upgraded["layout"],
                        "reason": reason,
                    }
                )
                break  # Stop on first successful upgrade.
        out.append(chosen)

    return out, upgrades


__all__ = ["recommend_layouts", "enforce_hero", "insert_section_dividers"]
