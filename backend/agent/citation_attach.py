"""Phase 6AF — attach claim-level citations to slides in-pipeline.

Thin, deterministic adapter around
:func:`services.claim_citation_service.map_deck_citations`. Runs
inside :class:`agent.loop.NexusAgentLoop` after ``repair_for_validator``
and writes a ``citations`` array onto each source-bearing slide.

Design rules (kept narrow on purpose):

* No LLM calls, no network, no randomness, no I/O.
* Reads from ``slide["sources"]`` and the deck-level sources only —
  nothing the mapper itself does not already see.
* Stable input → stable output. Marker numbers ``[n]`` are assigned
  per slide in the order each ``source_id`` first appears for that
  slide, so re-running on the same deck yields identical markers.
* Additive: writes ``slide["citations"]`` only. The existing
  ``slide["sources"]`` array, validator contract, intent block and
  beat metadata are untouched. Slides with no supported claims get
  ``slide["citations"] = []`` (still additive, never removed).
* Defensive: on any error returns the input slides unchanged.

Output shape per slide::

    slide["citations"] = [
        {
            "path": "bullets[1]",
            "claim_text": "Revenue grew 42% YoY.",
            "marker": 1,
            "supported": True,
            "basis": "numeric_match",
            "score": 0.85,
            "source_id": "https://example.com/q1",
            "source_url": "https://example.com/q1",
            "source_title": "Q1 Earnings Call",
        },
        ...
    ]

Deck-level summary (returned by :func:`attach_citations_to_deck`)
matches the ``map_deck_citations`` summary plus a ``slides_with_citations``
counter so callers can emit a ``citation_checked`` progress event.
"""

from __future__ import annotations

from typing import Any

from services.claim_citation_service import map_deck_citations

__all__ = ["attach_citations_to_deck"]


def _slide_source_ids(slide: dict) -> list[str]:
    """Return the ordered list of source identifiers attached to a slide.

    Mirrors the ``_source_id`` resolution rule used by
    :mod:`services.claim_citation_service` so marker assignment lines up
    with the mapper's ``source_id`` field exactly.
    """
    out: list[str] = []
    seen: set[str] = set()
    for src in slide.get("sources") or []:
        if not isinstance(src, dict):
            continue
        for key in ("id", "url", "title"):
            v = src.get(key)
            if isinstance(v, str) and v.strip():
                sid = v.strip()
                if sid not in seen:
                    seen.add(sid)
                    out.append(sid)
                break
    return out


def attach_citations_to_deck(slides: Any) -> tuple[list[dict], dict[str, Any]]:
    """Attach a deterministic ``citations`` array to each slide.

    Returns ``(new_slides, summary)``. ``new_slides`` is always a list;
    on malformed input it is ``[]`` and ``summary`` is the empty
    ``map_deck_citations`` summary. The function never raises.
    """
    if not isinstance(slides, list):
        return [], _empty_summary()

    try:
        report = map_deck_citations({"slides": slides})
    except Exception:  # pragma: no cover — defensive; mapper is pure
        return [dict(s) if isinstance(s, dict) else s for s in slides], _empty_summary()

    claims_by_slide: dict[int, list[dict[str, Any]]] = {}
    for c in report.get("claims") or []:
        if not isinstance(c, dict):
            continue
        idx = c.get("slide_index")
        if not isinstance(idx, int):
            continue
        claims_by_slide.setdefault(idx, []).append(c)

    out: list[dict] = []
    slides_with_citations = 0
    for i, slide in enumerate(slides):
        if not isinstance(slide, dict):
            out.append(slide)
            continue
        new_slide = dict(slide)
        per_slide_claims = claims_by_slide.get(i, [])
        # Build slide-local marker map: each new source_id gets the next
        # integer in [1..N] based on first-appearance order across the
        # supported claims, falling back to the slide's own ``sources``
        # ordering if a claim cites a deck-level source not on the slide.
        marker_map: dict[str, int] = {}
        for sid in _slide_source_ids(new_slide):
            marker_map.setdefault(sid, len(marker_map) + 1)

        citations: list[dict[str, Any]] = []
        for c in per_slide_claims:
            sid = c.get("source_id")
            supported = bool(c.get("supported"))
            if supported and isinstance(sid, str) and sid:
                marker = marker_map.setdefault(sid, len(marker_map) + 1)
            else:
                marker = 0  # unsupported / no source → no rendered marker
            citations.append(
                {
                    "path": c.get("path"),
                    "claim_text": c.get("claim_text", ""),
                    "marker": marker,
                    "supported": supported,
                    "basis": c.get("basis", "no_match"),
                    "score": float(c.get("score") or 0.0),
                    "source_id": sid if isinstance(sid, str) else None,
                    "source_url": c.get("source_url"),
                    "source_title": c.get("source_title"),
                }
            )

        new_slide["citations"] = citations
        if any(cc["marker"] > 0 for cc in citations):
            slides_with_citations += 1
        out.append(new_slide)

    summary = dict(report.get("summary") or _empty_summary())
    summary["slides_with_citations"] = slides_with_citations
    return out, summary


def _empty_summary() -> dict[str, Any]:
    return {
        "total_claims": 0,
        "supported": 0,
        "unsupported": 0,
        "by_basis": {
            "exact_phrase": 0,
            "numeric_match": 0,
            "keyword_overlap": 0,
            "no_match": 0,
        },
        "support_rate": 0.0,
        "slides_with_citations": 0,
    }
