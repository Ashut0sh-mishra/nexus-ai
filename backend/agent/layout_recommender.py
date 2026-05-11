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
)


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


__all__ = ["recommend_layouts"]
