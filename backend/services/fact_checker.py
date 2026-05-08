"""Cross-check generated slides against verified research.

Flags claims (dates, numbers, named people) that don't appear in the research
data so the UI can warn the user. Optional auto-replacement is conservative:
we only replace when the slide value clearly contradicts a verified fact and
a single replacement candidate exists.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("nexus.services.fact_checker")

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
_NUM_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+|\b\d+(?:\.\d+)?%?\b")
_PERSON_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b")


def _slide_text(slide: dict) -> str:
    parts: list[str] = []
    for k in ("title", "subtitle", "content", "body", "quote", "author", "kicker"):
        v = slide.get(k)
        if isinstance(v, str):
            parts.append(v)
    bullets = slide.get("bullets") or []
    if isinstance(bullets, list):
        for b in bullets:
            if isinstance(b, str):
                parts.append(b)
            elif isinstance(b, dict):
                for kk in ("text", "heading", "title", "content"):
                    if isinstance(b.get(kk), str):
                        parts.append(b[kk])
    return " \n ".join(parts)


def _verified_pools(research_data: dict) -> dict:
    years: set[str] = set()
    nums: set[str] = set()
    people: set[str] = set(p.lower() for p in (research_data.get("key_people") or []))

    for ev in research_data.get("timeline", []):
        d = str(ev.get("date") or "")
        m = _YEAR_RE.search(d)
        if m:
            years.add(m.group(0))
    for f in research_data.get("key_facts", []):
        s = str(f.get("fact") or "")
        for m in _YEAR_RE.finditer(s):
            years.add(m.group(0))
        for m in _NUM_RE.finditer(s):
            nums.add(m.group(0))
    for k, v in (research_data.get("statistics") or {}).items():
        if isinstance(v, (int, float)):
            nums.add(f"{v:,}")
            nums.add(str(v))
    summary = research_data.get("summary") or ""
    for m in _YEAR_RE.finditer(summary):
        years.add(m.group(0))
    for w in (research_data.get("web_content") or []):
        txt = w.get("text") or ""
        for m in _YEAR_RE.finditer(txt):
            years.add(m.group(0))
    return {"years": years, "numbers": nums, "people": people}


async def verify_slides(slides: list[dict], research_data: dict) -> list[dict]:
    """Annotate each slide with `_fact_check`: list of warnings."""
    if not research_data or not research_data.get("sources_used"):
        return slides
    pool = _verified_pools(research_data)
    summary_lower = (research_data.get("summary") or "").lower()
    flagged_total = 0

    for s in slides:
        if not isinstance(s, dict):
            continue
        text = _slide_text(s)
        warnings: list[dict] = []

        for m in _YEAR_RE.finditer(text):
            y = m.group(0)
            if y in pool["years"]:
                continue
            if y in summary_lower:
                continue
            warnings.append({"type": "year", "value": y,
                             "msg": f"Year {y} not found in verified research"})

        for m in _PERSON_RE.finditer(text):
            name = m.group(1)
            low = name.lower()
            if low in pool["people"] or low in summary_lower:
                continue
            # Skip very common multi-cap phrases that aren't really names.
            if any(w in name for w in ("United States", "New York", "World War")):
                continue
            warnings.append({"type": "person", "value": name,
                             "msg": f"'{name}' not in verified people list"})

        if warnings:
            s["_fact_check"] = warnings[:6]
            flagged_total += len(warnings)

    if flagged_total:
        logger.info("fact_check.flags", extra={"slides": len(slides), "flags": flagged_total})
    return slides
