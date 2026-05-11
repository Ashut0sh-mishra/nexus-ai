"""Phase 6U — pre-save deck repair pass that satisfies ``validate_deck``.

Phase 6T benchmarking surfaced a corpus-wide gap: ``deck_quality_ok``
was true on only 1 of 11 generated decks. The dominant failure mode is
the safety-net at the bottom of
:func:`agent.loop.NexusAgentLoop._normalize_slides` that pins
``out[0]["layout"] = "title"`` and ``out[-1]["layout"] = "closing"``
without rebuilding the layout-specific fields. The validator then
flags the missing ``subtitle`` / ``eyebrow`` / ``cta`` keys.

This module is a tiny *destructive* repair pass — unlike
:mod:`agent.deck_quality` which is observability-only — that fills in
safe, layout-local defaults so the deck satisfies the strict
:func:`agent.slide_schema.validate_deck` contract before it is saved.

Scope (intentionally narrow):

* Add missing ``subtitle`` / ``eyebrow`` keys on ``title`` slides.
* Add missing ``subtitle`` / ``cta`` keys on ``closing`` slides.
* Add missing ``subtitle`` key on ``chart`` slides.
* Add missing ``attribution`` key on ``quote`` slides.
* Add missing ``unit`` / ``source`` keys on ``chart_data``.
* Coerce non-string optional text fields to strings.

Out of scope (do NOT add here):

* Inventing bullet content, stat values, chart numbers, or column
  bodies. These are *not* safe defaults — a missing bullet list means
  the slide is genuinely incomplete and that is a generation problem,
  not a contract problem.
* Rewriting wrong-type primitives that would change semantics.
* Inventing source URLs.
"""

from __future__ import annotations

from typing import Any


def _ensure_str(slide: dict[str, Any], key: str, default: str = "") -> bool:
    if key not in slide or not isinstance(slide.get(key), str):
        slide[key] = default
        return True
    return False


def _repair_title(slide: dict[str, Any]) -> bool:
    changed = False
    changed |= _ensure_str(slide, "subtitle", "")
    changed |= _ensure_str(slide, "eyebrow", "Presentation")
    return changed


def _repair_closing(slide: dict[str, Any]) -> bool:
    changed = False
    changed |= _ensure_str(slide, "subtitle", "")
    changed |= _ensure_str(slide, "cta", "Thank you")
    return changed


def _repair_quote(slide: dict[str, Any]) -> bool:
    return _ensure_str(slide, "attribution", "")


def _repair_chart(slide: dict[str, Any]) -> bool:
    changed = _ensure_str(slide, "subtitle", "")
    cd = slide.get("chart_data")
    if isinstance(cd, dict):
        if "unit" not in cd or not isinstance(cd.get("unit"), str):
            cd["unit"] = ""
            changed = True
        if "source" not in cd or not isinstance(cd.get("source"), str):
            cd["source"] = ""
            changed = True
    return changed


def _repair_bigstat(slide: dict[str, Any]) -> bool:
    """Phase 6AA — seed bigstat optional keys.

    ``value`` is required and must carry semantic content; we never
    invent it. ``label`` and ``subtitle`` are seeded as empty strings
    so the validator accepts the slide while still surfacing a missing
    ``value`` as a real defect upstream.
    """
    changed = _ensure_str(slide, "label", "")
    changed |= _ensure_str(slide, "subtitle", "")
    return changed


def _repair_section_divider(slide: dict[str, Any]) -> bool:
    """Phase 6AA — seed section_divider optional keys."""
    changed = _ensure_str(slide, "eyebrow", "")
    changed |= _ensure_str(slide, "subtitle", "")
    return changed


def _repair_timeline(slide: dict[str, Any]) -> bool:
    """Phase 6AC — seed timeline optional keys.

    ``events`` is required and must carry semantic content; we never
    invent dates / labels. ``subtitle`` is seeded as an empty string.
    """
    return _ensure_str(slide, "subtitle", "")


def _repair_comparison(slide: dict[str, Any]) -> bool:
    """Phase 6AC — seed comparison optional keys.

    ``left`` and ``right`` blocks are required; we never invent their
    headings/bodies. Only ``subtitle`` is seeded.
    """
    return _ensure_str(slide, "subtitle", "")


_LAYOUT_REPAIRERS = {
    "title": _repair_title,
    "closing": _repair_closing,
    "quote": _repair_quote,
    "chart": _repair_chart,
    "bigstat": _repair_bigstat,
    "section_divider": _repair_section_divider,
    "timeline": _repair_timeline,
    "comparison": _repair_comparison,
}


def repair_for_validator(slides: Any) -> list[dict[str, Any]]:
    """Apply safe, layout-local defaults so ``validate_deck`` accepts the deck.

    Returns a *new* list of slide dicts (shallow-copied so callers that
    cache the input list are not surprised). Slides that are not dicts
    are passed through unchanged. The function never invents content
    fields (bullets, columns, stats, chart values).
    """

    if not isinstance(slides, list):
        return slides  # type: ignore[return-value]

    out: list[dict[str, Any]] = []
    for raw in slides:
        if not isinstance(raw, dict):
            out.append(raw)  # preserved verbatim; validator will flag it
            continue
        slide = dict(raw)
        # Ensure every slide has a string title; the validator rejects
        # missing/empty titles and most layouts share that requirement.
        if not isinstance(slide.get("title"), str) or not slide["title"].strip():
            slide["title"] = str(slide.get("title") or "Slide").strip() or "Slide"
        layout = slide.get("layout")
        repairer = _LAYOUT_REPAIRERS.get(str(layout) if isinstance(layout, str) else "")
        if repairer is not None:
            repairer(slide)
        out.append(slide)
    return out


__all__ = ["repair_for_validator"]
