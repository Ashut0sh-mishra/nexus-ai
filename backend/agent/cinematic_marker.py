"""Phase 6AK — mark cinematic hero moments on a deck.

Deterministic, additive marker pass. Reads the already-normalized deck
(post-citation-attach, post-editorial) and writes a tiny boolean
``slide["is_hero"]`` field on the slides that should render with the
cinematic variants:

* The **first** ``bigstat`` slide in the deck (this is THE single
  dominant moment — already chosen by ``layout_recommender.enforce_hero``
  when no native bigstat exists).
* The **first** ``section_divider`` slide (the deck's chapter break).
* The **first** ``quote`` slide whose attribution is non-empty (a
  documentary-style anchor moment; pure quote slides without
  attribution stay in their default variant).

Architectural rules (kept narrow on purpose):

* No LLM calls, no network, no randomness, no I/O.
* Pure / offline / never raises — on any error the input slides are
  returned unchanged.
* Additive only: writes ``is_hero`` only. Existing fields, the
  validator contract, the intent block, the citations, the sources,
  and the beat metadata are untouched. Slides without a cinematic
  promotion get no field added (keeps the JSON small and
  exporter-irrelevant).
* Exporter compatibility: PPTX/PDF do not read ``is_hero``. The flag
  is renderer-only.
"""

from __future__ import annotations

from typing import Any

__all__ = ["mark_hero_moments"]


_HERO_LAYOUTS_ONCE: tuple[str, ...] = ("bigstat", "section_divider")


def _first_index_with_layout(slides: list[Any], layout: str) -> int:
    for i, slide in enumerate(slides):
        if isinstance(slide, dict) and slide.get("layout") == layout:
            return i
    return -1


def _first_quote_with_attribution(slides: list[Any]) -> int:
    for i, slide in enumerate(slides):
        if (
            isinstance(slide, dict)
            and slide.get("layout") == "quote"
            and isinstance(slide.get("attribution"), str)
            and slide["attribution"].strip()
        ):
            return i
    return -1


def mark_hero_moments(slides: Any) -> tuple[list[dict], dict[str, int]]:
    """Return ``(new_slides, summary)`` with ``is_hero`` set on hero slides.

    Never raises. ``summary`` counts how many slides were promoted per
    layout so the loop can emit a single ``design_decision`` event.
    """
    summary = {"bigstat": 0, "section_divider": 0, "quote": 0, "total": 0}
    if not isinstance(slides, list):
        return [], summary

    try:
        hero_indices: set[int] = set()
        for layout in _HERO_LAYOUTS_ONCE:
            idx = _first_index_with_layout(slides, layout)
            if idx >= 0:
                hero_indices.add(idx)
                summary[layout] += 1
        q_idx = _first_quote_with_attribution(slides)
        if q_idx >= 0:
            hero_indices.add(q_idx)
            summary["quote"] += 1
        summary["total"] = len(hero_indices)

        out: list[dict] = []
        for i, slide in enumerate(slides):
            if not isinstance(slide, dict):
                out.append(slide)
                continue
            if i in hero_indices:
                new_slide = dict(slide)
                new_slide["is_hero"] = True
                out.append(new_slide)
            else:
                out.append(slide)
        return out, summary
    except Exception:  # pragma: no cover - defensive
        return list(slides), summary
