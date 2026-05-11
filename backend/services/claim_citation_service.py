"""Phase 6K - Deterministic claim-to-source citation mapper.

This module attaches **claim-level** citation evidence to slides in a
fully deterministic, offline manner. It is intentionally narrow:

* No LLM calls.
* No network calls. No browser.
* No randomness. No background threads. No filesystem writes.
* Stable input -> stable output (sources are sorted by source_id, ties
  are broken by source_id lexicographically).

The mapper is a *reporter*, not a generator: it does not invent claims
and it does not invent evidence. Its job is to surface, for every
factual claim it can identify in a deck, the best-supporting source(s)
already attached to the deck or its slides, with an explicit reason
(``basis``) and a numeric ``score``. Unsupported claims are marked
``supported=False`` with ``basis="no_match"``.

It is a separate module from :mod:`agent.source_grounding` on purpose:
``source_grounding.extract_claim_candidates_from_slide`` is numeric-only
and is wired into deck-quality reporting; the broader claim extraction
required for citation mapping (full bullets, stats, chart points, etc.)
lives here so the existing numeric grounding contract is unchanged.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"

# Tokenisation / matching tunables. Kept small + deterministic.
_TOKEN_RE = re.compile(r"[A-Za-z0-9%]+")
# Numbers: integers, decimals, percents, with optional unit suffix.
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?\s?(?:%|percent|bn|billion|million|m|k|x)?",
    re.IGNORECASE,
)

# Unit synonyms -> canonical class. Anything unrecognised falls through as "".
_UNIT_CANON = {
    "%": "%",
    "percent": "%",
    "m": "m",
    "million": "m",
    "b": "b",
    "bn": "b",
    "billion": "b",
    "k": "k",
    "x": "x",
}

_STOPWORDS = frozenset(
    """
    a an and are as at be been being by do does for from has have he her his
    i if in into is it its itself me my of on or our ours she so than that
    the their theirs them then there these they this those to too us was we
    were what when where which who whom why will with you your yours
    """.split()
)

# Generic filler-only fragments that should never be treated as claims.
_FILLER_LITERALS = frozenset(
    {
        "agenda",
        "outline",
        "introduction",
        "summary",
        "thank you",
        "thanks",
        "questions",
        "q&a",
        "qa",
        "closing",
        "next steps",
        "appendix",
    }
)

# Minimum keyword-overlap fraction (Jaccard over content tokens) to call a
# match a "keyword_overlap" support. Tuned conservatively so weakly related
# sources do not get attached to claims they do not actually support.
_KEYWORD_OVERLAP_MIN = 0.34


# ---------------------------------------------------------------------------
# Tokenisation helpers
# ---------------------------------------------------------------------------


def _tokens(text: str) -> list[str]:
    if not isinstance(text, str) or not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _content_tokens(text: str) -> set[str]:
    return {t for t in _tokens(text) if t and t not in _STOPWORDS and len(t) > 1}


def _numbers(text: str) -> list[str]:
    """Return a deterministic list of canonical numbers found in ``text``.

    Each number is normalised to the form ``"<digits>[.<digits>][<unit>]"``
    where ``<unit>`` is one of ``{"%","m","b","k","x",""}`` so that
    synonyms like ``42M`` and ``42 million`` collapse to ``"42m"`` and
    ``93%`` and ``93 percent`` both collapse to ``"93%"``.
    """
    if not isinstance(text, str) or not text:
        return []
    out: list[str] = []
    for raw in _NUMBER_RE.findall(text):
        s = raw.strip().lower()
        if not s:
            continue
        # Split off optional trailing unit.
        m = re.match(
            r"^([0-9][0-9,]*(?:\.[0-9]+)?)\s*([a-z%]*)$",
            s,
        )
        if not m:
            continue
        digits = m.group(1).replace(",", "").rstrip(".")
        unit_raw = m.group(2)
        unit = _UNIT_CANON.get(unit_raw, "")
        out.append(f"{digits}{unit}")
    return out


def _is_filler(text: str) -> bool:
    norm = " ".join(_tokens(text))
    return norm in _FILLER_LITERALS


def _claim_is_substantive(text: str) -> bool:
    """A claim must have either >=3 content tokens OR contain a number."""
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped or _is_filler(stripped):
        return False
    if _numbers(stripped):
        return True
    return len(_content_tokens(stripped)) >= 3


# ---------------------------------------------------------------------------
# Source normalisation
# ---------------------------------------------------------------------------


def _source_text(src: dict) -> str:
    parts: list[str] = []
    for k in ("title", "snippet"):
        v = src.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    return " . ".join(parts)


def _source_id(src: dict, fallback_index: int) -> str:
    for k in ("id", "url", "title"):
        v = src.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return f"src#{fallback_index}"


def _collect_sources(deck: dict) -> list[dict[str, Any]]:
    """Collect deck-level + per-slide sources, deduplicated by source_id.

    Sort key is the source_id so output is deterministic regardless of
    input order.
    """
    if not isinstance(deck, dict):
        return []
    bag: dict[str, dict[str, Any]] = {}
    counter = 0
    for src in deck.get("sources") or []:
        if isinstance(src, dict):
            sid = _source_id(src, counter)
            counter += 1
            bag.setdefault(sid, dict(src) | {"_id": sid})
    for slide in deck.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        for src in slide.get("sources") or []:
            if isinstance(src, dict):
                sid = _source_id(src, counter)
                counter += 1
                bag.setdefault(sid, dict(src) | {"_id": sid})
    return sorted(bag.values(), key=lambda s: s["_id"])


# ---------------------------------------------------------------------------
# Claim extraction (broader than agent.source_grounding's numeric-only one)
# ---------------------------------------------------------------------------


def extract_claims(slide: Any, slide_index: int = 0) -> list[dict[str, Any]]:
    """Return claim records ``{slide_index, layout, path, text, numbers}``.

    Conservatively skips empty strings, generic filler ("Agenda", "Q&A", ...),
    pure non-factual headings, and titles without numeric content. Numeric
    titles ARE retained because numbers in titles are factual claims.
    """
    if not isinstance(slide, dict):
        return []
    layout = str(slide.get("layout") or "").lower()
    out: list[dict[str, Any]] = []

    def _emit(path: str, text: str) -> None:
        if not isinstance(text, str):
            return
        text = text.strip()
        if not _claim_is_substantive(text):
            return
        out.append(
            {
                "slide_index": slide_index,
                "layout": layout,
                "path": path,
                "text": text,
                "numbers": _numbers(text),
            }
        )

    if layout == "stats":
        for i, item in enumerate(slide.get("stats") or []):
            if isinstance(item, dict):
                value = str(item.get("value") or "").strip()
                label = str(item.get("label") or "").strip()
                if value or label:
                    _emit(f"stats[{i}]", f"{value} {label}".strip())

    elif layout == "chart":
        cd = slide.get("chart_data") or {}
        if isinstance(cd, dict):
            labels = cd.get("labels") or []
            values = cd.get("values") or []
            unit = str(cd.get("unit") or "").strip()
            for i, (lab, val) in enumerate(zip(labels, values)):
                _emit(f"chart_data[{i}]", f"{lab}: {val}{unit}".strip())

    elif layout == "two-col":
        for i, col in enumerate(slide.get("columns") or []):
            if isinstance(col, dict):
                _emit(f"columns[{i}].body", str(col.get("body") or ""))

    elif layout == "quote":
        _emit("quote", str(slide.get("quote") or ""))

    # Always: bullets, and title only if numeric.
    for i, b in enumerate(slide.get("bullets") or []):
        if isinstance(b, str):
            _emit(f"bullets[{i}]", b)
    title = slide.get("title")
    if isinstance(title, str) and _numbers(title):
        _emit("title", title)

    return out


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _phrase_substring_hit(claim_tokens: list[str], src_text: str) -> bool:
    """True if at least 3 consecutive claim content-tokens occur as a
    substring in the source text (lowercased), using a tokenised join.
    """
    if len(claim_tokens) < 3:
        return False
    src_norm = " " + " ".join(_tokens(src_text)) + " "
    # Walk windows of 3 content-tokens (ignoring stopwords) over the claim.
    content = [t for t in claim_tokens if t not in _STOPWORDS and len(t) > 1]
    if len(content) < 3:
        return False
    for i in range(len(content) - 2):
        window = " " + " ".join(content[i : i + 3]) + " "
        if window in src_norm:
            return True
    return False


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = a & b
    if not inter:
        return 0.0
    union = a | b
    return len(inter) / len(union)


def _score_one(
    claim: dict[str, Any], src: dict[str, Any]
) -> tuple[float, str]:
    """Return ``(score, basis)`` for a single (claim, source) pair.

    Score is in [0.0, 1.0]; basis is one of
    ``{"exact_phrase","numeric_match","keyword_overlap","no_match"}``.
    """
    src_text = _source_text(src)
    if not src_text:
        return 0.0, "no_match"

    claim_text = claim.get("text") or ""
    claim_tokens = _tokens(claim_text)
    claim_content = _content_tokens(claim_text)
    src_content = _content_tokens(src_text)
    overlap = _jaccard(claim_content, src_content)

    # 1) Exact phrase: at least 3 consecutive content-tokens of the claim
    #    appear in the source text. Strong signal.
    if _phrase_substring_hit(claim_tokens, src_text):
        return 1.0, "exact_phrase"

    # 2) Numeric match: every number in the claim must also appear in the
    #    source. We additionally require *some* content-token overlap so a
    #    coincidental "42 million dogs" does not falsely attribute an
    #    unrelated source. The bar here is intentionally low because
    #    stat-style claims are very terse ("42M Revenue") - canonical
    #    number+unit normalisation is doing most of the disambiguation
    #    work and the low overlap floor only filters topic-disjoint
    #    sources.
    claim_numbers = claim.get("numbers") or []
    if claim_numbers:
        src_numbers = set(_numbers(src_text))
        all_present = all(n in src_numbers for n in claim_numbers)
        if all_present and overlap >= 0.05:
            return 0.85, "numeric_match"

    # 3) Keyword overlap above threshold.
    if overlap >= _KEYWORD_OVERLAP_MIN:
        return round(overlap, 4), "keyword_overlap"

    return 0.0, "no_match"


def match_claim_to_sources(
    claim: dict[str, Any],
    sources: list[dict[str, Any]],
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    """Match a single claim against the deck's sources.

    Returns one citation-mapping record. ``supported`` is ``True`` iff at
    least one source matched with a non-``no_match`` basis. The record
    includes the **best** match (highest score, ties broken by sorted
    source_id) plus up to ``top_k`` matches in ``supports``.
    """
    matches: list[tuple[float, str, dict[str, Any]]] = []
    for src in sources or []:
        if not isinstance(src, dict):
            continue
        score, basis = _score_one(claim, src)
        if basis != "no_match":
            matches.append((score, basis, src))

    matches.sort(key=lambda t: (-t[0], t[2].get("_id") or ""))

    record: dict[str, Any] = {
        "slide_index": claim.get("slide_index", 0),
        "layout": claim.get("layout"),
        "path": claim.get("path"),
        "claim_text": claim.get("text", ""),
        "numbers": list(claim.get("numbers") or []),
        "supported": False,
        "basis": "no_match",
        "score": 0.0,
        "source_id": None,
        "source_url": None,
        "source_title": None,
        "supports": [],
    }

    if matches:
        best_score, best_basis, best_src = matches[0]
        record["supported"] = True
        record["basis"] = best_basis
        record["score"] = float(best_score)
        record["source_id"] = best_src.get("_id")
        record["source_url"] = best_src.get("url") if isinstance(best_src.get("url"), str) else None
        record["source_title"] = (
            best_src.get("title") if isinstance(best_src.get("title"), str) else None
        )
        for score, basis, src in matches[:top_k]:
            record["supports"].append(
                {
                    "source_id": src.get("_id"),
                    "source_url": src.get("url") if isinstance(src.get("url"), str) else None,
                    "source_title": src.get("title") if isinstance(src.get("title"), str) else None,
                    "score": float(score),
                    "basis": basis,
                }
            )

    return record


# ---------------------------------------------------------------------------
# Public API: deck-level mapping + summary
# ---------------------------------------------------------------------------


def map_deck_citations(deck: Any) -> dict[str, Any]:
    """Return a deterministic claim-level citation report for a deck.

    Output shape::

        {
          "schema_version": "1.0",
          "claims": [ <citation-mapping record>, ... ],
          "summary": {
            "total_claims": int,
            "supported": int,
            "unsupported": int,
            "by_basis": {"exact_phrase": n, "numeric_match": n,
                        "keyword_overlap": n, "no_match": n},
            "support_rate": float in [0,1],
          }
        }
    """
    if not isinstance(deck, dict):
        return {
            "schema_version": SCHEMA_VERSION,
            "claims": [],
            "summary": _empty_summary(),
        }

    sources = _collect_sources(deck)

    claims: list[dict[str, Any]] = []
    for i, slide in enumerate(deck.get("slides") or []):
        for c in extract_claims(slide, slide_index=i):
            claims.append(match_claim_to_sources(c, sources))

    return {
        "schema_version": SCHEMA_VERSION,
        "claims": claims,
        "summary": summarize_mappings(claims),
    }


def summarize_mappings(claims: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate counts/rates from a list of citation-mapping records."""
    by_basis = {
        "exact_phrase": 0,
        "numeric_match": 0,
        "keyword_overlap": 0,
        "no_match": 0,
    }
    total = 0
    supported = 0
    for c in claims or []:
        total += 1
        basis = c.get("basis") or "no_match"
        if basis not in by_basis:
            by_basis[basis] = 0
        by_basis[basis] += 1
        if c.get("supported"):
            supported += 1
    unsupported = total - supported
    rate = (supported / total) if total else 0.0
    return {
        "total_claims": total,
        "supported": supported,
        "unsupported": unsupported,
        "by_basis": by_basis,
        "support_rate": round(rate, 4),
    }


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
    }
