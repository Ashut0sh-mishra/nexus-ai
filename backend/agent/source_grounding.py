"""Phase 3 — Source-grounding & evidence helpers.

Pure, dependency-light helpers that turn raw tool outputs (today: web search
results and browser observations) into normalised ``SourceEvidence`` records,
extract claim candidates from generated slides, and report which slides are
making numeric/factual claims **without** any source metadata.

This module deliberately does not import the database layer, the FastAPI app,
or the slide schema validator. Everything here is JSON-safe and side-effect
free so it can be unit-tested in isolation and reused from the runtime,
the deck quality report, and (later) the deck generation pipeline.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# Snippet truncation hard cap: protects DB rows and API payloads from blowing
# up if a tool returns very large bodies of text (e.g. browser_view).
_MAX_SNIPPET = 600
_MAX_TITLE = 240
_MAX_URL = 1024

_VALID_CONFIDENCE = {"high", "medium", "low", "unknown"}


# ── normalize ─────────────────────────────────────────────────────────────
def normalize_source(raw: Any, *, provider: str = "unknown") -> dict[str, Any] | None:
    """Coerce a raw search/browser result into a JSON-safe evidence record.

    Returns ``None`` for inputs that have no useful identity (no url, no
    title, no snippet). Never raises.
    """
    if not isinstance(raw, dict):
        return None

    url = _trim(_first_str(raw, ("url", "link", "href", "source_url")), _MAX_URL)
    title = _trim(_first_str(raw, ("title", "name", "heading")), _MAX_TITLE)
    snippet = _trim(
        _first_str(raw, ("snippet", "excerpt", "content", "summary", "description", "text")),
        _MAX_SNIPPET,
    )

    if not (url or title or snippet):
        return None

    confidence = raw.get("confidence")
    if confidence not in _VALID_CONFIDENCE:
        # Heuristic: a real URL with non-empty snippet → "medium"; otherwise low.
        confidence = "medium" if (url and snippet) else "low"

    observed_at = (
        raw.get("retrieved_at")
        or raw.get("observed_at")
        or datetime.now(timezone.utc).isoformat()
    )
    if not isinstance(observed_at, str):
        observed_at = str(observed_at)

    meta_in = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    meta: dict[str, Any] = {}
    for k, v in meta_in.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            meta[str(k)[:64]] = v if not isinstance(v, str) else v[:300]

    return {
        "title": title or None,
        "url": url or None,
        "snippet": snippet or None,
        "provider": str(raw.get("provider") or provider)[:64],
        "observed_at": observed_at,
        "confidence": confidence,
        "metadata": meta,
    }


def _first_str(raw: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        v = raw.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


# ── extract from tool output ──────────────────────────────────────────────
_BROWSER_TOOLS_WITH_OBSERVATION = {
    "browser_view",
    "browser_navigate",
    "browser_click",
    "browser_scroll_up",
    "browser_scroll_down",
}


def extract_sources_from_tool_result(
    tool_name: str, tool_output: Any
) -> list[dict[str, Any]]:
    """Pull evidence records out of a successful tool's ``ToolResult.to_dict``.

    The runtime calls this only for ``ok=True`` observations. Unknown tools
    or empty payloads return ``[]``. Never raises.
    """
    if not tool_name or not isinstance(tool_output, dict):
        return []
    data = tool_output.get("data")
    if data is None:
        return []

    sources: list[dict[str, Any]] = []

    if tool_name == "info_search_web":
        raw_sources = data.get("sources") if isinstance(data, dict) else None
        if isinstance(raw_sources, list):
            for item in raw_sources:
                rec = normalize_source(item, provider="info_search_web")
                if rec is not None:
                    sources.append(rec)
        return sources

    if tool_name in _BROWSER_TOOLS_WITH_OBSERVATION:
        # Browser tools today return either a string body or a dict with a
        # "url"/"title"/"text" shape via BrowserService. Treat the whole
        # data payload as a single evidence record.
        candidate: dict[str, Any]
        if isinstance(data, dict):
            candidate = dict(data)
        else:
            candidate = {"snippet": str(data)}
        rec = normalize_source(candidate, provider=tool_name)
        if rec is not None:
            sources.append(rec)
        return sources

    return sources


# ── slide claim/source helpers ────────────────────────────────────────────
_NUMBER_RE = re.compile(r"\b\d[\d,\.]*\s?(?:%|percent|bn|m|million|billion|k|x)?\b", re.I)


def extract_claim_candidates_from_slide(slide: Any) -> list[dict[str, Any]]:
    """Surface fields that *look* like factual / numeric claims.

    Pure heuristic: it never decides whether a claim is true. Output is a
    list of ``{slide_index?, layout?, path, snippet}`` records useful for
    pairing with sources later.
    """
    if not isinstance(slide, dict):
        return []
    layout = slide.get("layout")
    out: list[dict[str, Any]] = []

    if layout == "stats":
        for i, item in enumerate(slide.get("stats") or []):
            if not isinstance(item, dict):
                continue
            value = str(item.get("value") or "").strip()
            label = str(item.get("label") or "").strip()
            if value:
                out.append({
                    "layout": layout,
                    "path": f"stats[{i}]",
                    "snippet": f"{value} {label}".strip(),
                })

    elif layout == "chart":
        cd = slide.get("chart_data") or {}
        if isinstance(cd, dict):
            labels = cd.get("labels") or []
            values = cd.get("values") or []
            unit = str(cd.get("unit") or "").strip()
            for i, (lab, val) in enumerate(zip(labels, values)):
                out.append({
                    "layout": layout,
                    "path": f"chart_data[{i}]",
                    "snippet": f"{lab}: {val}{unit}".strip(),
                })

    else:
        # Generic prose fields.
        for path in ("title", "subtitle", "quote"):
            val = slide.get(path)
            if isinstance(val, str) and _NUMBER_RE.search(val):
                out.append({"layout": layout, "path": path, "snippet": val[:_MAX_SNIPPET]})
        for i, b in enumerate(slide.get("bullets") or []):
            if isinstance(b, str) and _NUMBER_RE.search(b):
                out.append({"layout": layout, "path": f"bullets[{i}]", "snippet": b[:_MAX_SNIPPET]})

    return out


def attach_sources_to_slide(slide: Any, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a *new* slide dict with normalised ``sources`` attached.

    Does not mutate the input. Filters/normalises the supplied sources via
    :func:`normalize_source`. Caps the attached list at 8 entries to keep
    slide payloads small.
    """
    if not isinstance(slide, dict):
        return {"sources": []}
    out = dict(slide)
    norm: list[dict[str, Any]] = []
    for s in sources or []:
        rec = normalize_source(s) if not _looks_normalised(s) else s
        if rec is not None:
            norm.append(rec)
    out["sources"] = norm[:8]
    return out


def _looks_normalised(obj: Any) -> bool:
    return (
        isinstance(obj, dict)
        and "confidence" in obj
        and "observed_at" in obj
        and "provider" in obj
    )


# ── deck-level source advisory ────────────────────────────────────────────
def slide_has_source_metadata(slide: Any) -> bool:
    if not isinstance(slide, dict):
        return False
    if isinstance(slide.get("sources"), list) and slide["sources"]:
        return True
    if isinstance(slide.get("citations"), list) and slide["citations"]:
        return True
    layout = slide.get("layout")
    if layout == "chart":
        cd = slide.get("chart_data") or {}
        if isinstance(cd, dict) and isinstance(cd.get("source"), str) and cd["source"].strip():
            return True
    return False


def build_deck_source_report(slides: Any) -> dict[str, Any]:
    """Return advisory ``source_warnings`` for stats/chart slides.

    Pure observability — never mutates and never invents sources. The shape
    is small and JSON-safe so it can be embedded inside
    :class:`agent.deck_quality.DeckQualityReport.summary` or surfaced via
    its own field.
    """
    warnings: list[dict[str, Any]] = []
    if not isinstance(slides, list):
        return {"warnings": warnings, "stats_slide_count": 0, "chart_slide_count": 0,
                "slides_with_sources": 0}

    stats_n = 0
    chart_n = 0
    with_src = 0
    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        layout = slide.get("layout")
        if slide_has_source_metadata(slide):
            with_src += 1
        if layout == "stats":
            stats_n += 1
            if not slide_has_source_metadata(slide):
                warnings.append({
                    "slide_index": idx,
                    "layout": "stats",
                    "code": "missing_source",
                    "message": "Stats slide has no source/evidence metadata.",
                })
        elif layout == "chart":
            chart_n += 1
            cd = slide.get("chart_data") or {}
            cd_source = isinstance(cd, dict) and bool(str(cd.get("source") or "").strip())
            if not cd_source and not slide_has_source_metadata(slide):
                warnings.append({
                    "slide_index": idx,
                    "layout": "chart",
                    "code": "missing_source",
                    "message": "Chart slide has no chart_data.source and no evidence metadata.",
                })

    return {
        "warnings": warnings,
        "stats_slide_count": stats_n,
        "chart_slide_count": chart_n,
        "slides_with_sources": with_src,
    }


# ── deck-level attach (Phase 4) ───────────────────────────────────────────
_MAX_SOURCES_PER_SLIDE = 3
# Layouts where attaching deck-level research sources is defensible without a
# claim-specific match. Title / closing slides are intentionally excluded.
_LAYOUTS_ALWAYS_ATTACH = {"stats", "chart"}
# Layouts that carry prose where a numeric claim *might* benefit from sources.
_LAYOUTS_MAYBE_ATTACH = {"bullets", "two-col", "quote"}


def _domain_from_url(url: str) -> str:
    if not isinstance(url, str) or "://" not in url:
        return ""
    rest = url.split("://", 1)[1]
    host = rest.split("/", 1)[0]
    # Strip a leading "www."
    if host.startswith("www."):
        host = host[4:]
    return host


def _defensible_chart_source_label(src: dict[str, Any]) -> str:
    """Pick a short, defensible label for ``chart_data.source``.

    Prefers the source title; falls back to the host of the URL. Never
    invents a label out of thin air. Returns ``""`` if nothing usable.
    """
    title = (src.get("title") or "").strip()
    if title:
        return title[:120]
    host = _domain_from_url(src.get("url") or "")
    return host[:120]


def attach_research_sources_to_deck(
    slides: Any, sources: Any
) -> list[dict[str, Any]]:
    """Return a *new* list of slides with research sources attached.

    Behaviour:
      * Normalises the supplied ``sources`` once (drops junk).
      * For ``stats`` and ``chart`` slides → attaches up to
        ``_MAX_SOURCES_PER_SLIDE`` normalised sources under ``slide["sources"]``.
      * For ``chart`` slides → if ``chart_data.source`` is empty, sets it
        to a defensible label (source title, else URL host). Never invents.
      * For ``bullets`` / ``two-col`` / ``quote`` slides → attaches sources
        only if :func:`extract_claim_candidates_from_slide` reports numeric
        claims on the slide.
      * Title / closing slides are left unchanged.
      * If ``slide["sources"]`` is already a non-empty list, leaves it.
      * If ``sources`` is empty / unusable, returns the input list unchanged
        (no new keys added).
      * Never mutates the supplied list or its slide dicts.
    """
    if not isinstance(slides, list) or not slides:
        return slides if isinstance(slides, list) else []

    normalised: list[dict[str, Any]] = []
    if isinstance(sources, list):
        for s in sources:
            rec = s if _looks_normalised(s) else normalize_source(s, provider="info_search_web")
            if rec is not None:
                normalised.append(rec)

    if not normalised:
        # Nothing to attach. Leave slides alone — DeckQualityReport will warn.
        return [dict(s) if isinstance(s, dict) else s for s in slides]

    capped = normalised[:_MAX_SOURCES_PER_SLIDE]
    primary = capped[0]
    primary_label = _defensible_chart_source_label(primary)

    out: list[dict[str, Any]] = []
    for slide in slides:
        if not isinstance(slide, dict):
            out.append(slide)
            continue
        layout = slide.get("layout")
        new_slide = dict(slide)

        existing = new_slide.get("sources")
        already_has_sources = isinstance(existing, list) and len(existing) > 0

        should_attach = False
        if layout in _LAYOUTS_ALWAYS_ATTACH:
            should_attach = True
        elif layout in _LAYOUTS_MAYBE_ATTACH:
            if extract_claim_candidates_from_slide(slide):
                should_attach = True

        if should_attach and not already_has_sources:
            new_slide["sources"] = list(capped)

        if layout == "chart":
            cd = new_slide.get("chart_data")
            if isinstance(cd, dict):
                new_cd = dict(cd)
                cur_src = str(new_cd.get("source") or "").strip()
                if not cur_src and primary_label:
                    new_cd["source"] = primary_label
                new_slide["chart_data"] = new_cd

        out.append(new_slide)

    return out
