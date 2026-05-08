"""Manus-style markdown-first content pipeline.

Manus's observed workflow (from the user's screenshots):
  1. Multi-source research — fan out queries, scrape diverse authentic sources
  2. Write a structured *markdown* draft (one H2 section per slide)
  3. Refine the markdown (Original \u2192 Modified diff)
  4. Convert markdown sections into slide JSON

This module owns steps 1-4. The agent loop calls ``run_markdown_pipeline``
which returns a list of slide dicts ready for the existing assembler /
critic / image / chart steps.

All four files are persisted to the task's memory directory so the user
(and ourselves) can inspect the intermediate artifacts:

    storage/agent_memory/<task_id>/raw_research.md
    storage/agent_memory/<task_id>/deck_draft.md
    storage/agent_memory/<task_id>/deck_final.md
    storage/agent_memory/<task_id>/sources.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from agent.memory import AgentMemory
from services.claude_service import ClaudeService
from services.search_service import SearchService

logger = logging.getLogger("nexus.agent.markdown_pipeline")


# ── Step 1: multi-source research ──────────────────────────────────────────

# Per-category sub-query templates. Manus fans out a single topic into 4-6
# focused queries to cover different facets.
_SUBQUERY_TEMPLATES: dict[str, list[str]] = {
    "history": [
        "{topic} timeline key dates",
        "{topic} causes and consequences",
        "{topic} key figures and leaders",
        "{topic} historical impact statistics",
        "{topic} primary sources and accounts",
    ],
    "research": [
        "{topic} latest peer-reviewed findings",
        "{topic} systematic review meta-analysis",
        "{topic} key statistics and figures",
        "{topic} methodology limitations",
    ],
    "tutorial": [
        "{topic} step by step tutorial",
        "{topic} best practices",
        "{topic} common pitfalls",
        "{topic} code example",
    ],
    "pitch": [
        "{topic} market size 2025",
        "{topic} competitors comparison",
        "{topic} growth statistics",
        "{topic} customer testimonials",
    ],
    "data": [
        "{topic} latest report numbers",
        "{topic} year over year growth",
        "{topic} industry benchmark",
        "{topic} forecast",
    ],
    "brand": [
        "{topic} brand identity",
        "{topic} visual style",
        "{topic} story",
    ],
    "explainer": [
        "{topic} explained",
        "{topic} how it works",
        "{topic} examples",
        "{topic} key concepts",
    ],
}

_DEFAULT_SUBQUERIES = _SUBQUERY_TEMPLATES["explainer"]


async def run_research(
    topic: str,
    *,
    profile: dict[str, Any],
    search: SearchService,
    memory: AgentMemory,
) -> tuple[str, list[dict[str, Any]]]:
    """Fan out 4-5 focused sub-queries and collate results into a markdown brief.

    Returns ``(raw_research_markdown, sources)``. Always succeeds; degrades to
    an empty brief if every search call fails.
    """
    category = str(profile.get("category") or "explainer")
    templates = _SUBQUERY_TEMPLATES.get(category, _DEFAULT_SUBQUERIES)
    subqueries = [t.format(topic=topic) for t in templates]

    # Multi-hop research is on by default for fact-heavy categories
    # (history / research / explainer / data) and when the global flag is
    # set to "deep". Each sub-query becomes a deep_search call: top pages
    # are fetched, entities extracted, follow-up search fired.
    try:
        from config import settings as _settings
        depth = str(getattr(_settings, "RESEARCH_DEPTH", "deep")).lower()
    except Exception:
        depth = "deep"
    deep = depth == "deep" and category in {
        "history", "research", "explainer", "data", "tutorial"
    }

    sem = asyncio.Semaphore(3)

    async def _one(q: str) -> tuple[str, str, list[dict[str, Any]]]:
        async with sem:
            try:
                if deep and hasattr(search, "deep_search"):
                    summary, srcs = await search.deep_search(
                        q, max_results=4, fetch_pages=2, do_second_hop=False
                    )
                else:
                    summary, srcs = await search.search(q, max_results=4)
                return q, summary or "", srcs or []
            except Exception as exc:
                logger.warning("research.subquery_failed", extra={"q": q, "err": str(exc)})
                return q, "", []

    results = await asyncio.gather(*[_one(q) for q in subqueries])

    # Build a markdown research brief grouped by sub-query.
    md_lines: list[str] = [f"# Research Brief: {topic}", ""]
    all_sources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for q, summary, srcs in results:
        md_lines.append(f"## {q}")
        md_lines.append("")
        if summary:
            md_lines.append(summary.strip())
            md_lines.append("")
        if srcs:
            md_lines.append("**Sources:**")
            for s in srcs:
                title = (s.get("title") or "")[:120]
                url = s.get("url") or ""
                snippet = (s.get("snippet") or "")[:200].replace("\n", " ")
                md_lines.append(f"- [{title}]({url}) \u2014 {snippet}")
                if url and url not in seen_urls:
                    all_sources.append(s)
                    seen_urls.add(url)
            md_lines.append("")

    raw_md = "\n".join(md_lines)
    memory.write_artifact("raw_research.md", raw_md)
    memory.write_artifact("sources.json", json.dumps(all_sources, indent=2))
    logger.info(
        "research.done",
        extra={"subqueries": len(subqueries), "sources": len(all_sources)},
    )
    return raw_md, all_sources


# ── Step 2: draft writer ───────────────────────────────────────────────────

_DRAFT_SYSTEM_PROMPT = """You are NEXUS Draft Writer — a senior content
strategist who writes the FULL TEXT of a slide deck as a structured markdown
document, before any layout or visual decisions are made.

Output rules:
- Output is ONE markdown document. No JSON. No code fences around the doc.
- First line: `# <Deck Title>` (one H1, the deck title).
- Then EXACTLY {slide_count} sections, each starting with `## <Slide Title>`.
- The first ## is the opener; the last ## is the closing/CTA.
- Inside each `##` section, write the body of that slide:
    * Use bullets (`- `) when listing 3-6 points
    * Use a markdown table when comparing 3+ rows of structured data
    * Use a `> ` block for an expert quote with attribution (`> "..." \u2014 Person, Role`)
    * Use a fenced ```chart block for chart specs:
        ```chart
        type: bar
        title: <chart title>
        labels: [A, B, C, D]
        values: [1, 2, 3, 4]
        unit: <unit>
        source: <source>
        ```
    * Use **bold** for key terms, *italic* sparingly
- Every factual claim should come from the research brief — cite inline with
  `(Source: <name>)` when it adds credibility.
- Write the FULL prose (the editorial profile word target applies PER SECTION).
- Do NOT mention slide numbers, layouts, or design instructions in the output.
- Do NOT add a "Sources" section at the end \u2014 inline citations only.
"""


def _draft_user_message(
    topic: str,
    slide_count: int,
    research_md: str,
    profile: dict[str, Any],
) -> str:
    from agent.topic_classifier import style_guidance_block
    style = style_guidance_block(profile)
    research_block = research_md.strip()[:6000] or "(no research available)"
    return (
        f"Topic: {topic}\n"
        f"Slide count: {slide_count}\n"
        f"Editorial profile: {profile.get('category')} (mood: {profile.get('mood')})"
        f"{style}\n\n"
        f"Research brief (use these facts \u2014 do not invent):\n"
        f"{research_block}\n\n"
        f"Write the full deck as markdown now. Exactly {slide_count} `##` "
        f"sections. Hit the per-section word target."
    )


async def run_draft(
    topic: str,
    slide_count: int,
    research_md: str,
    profile: dict[str, Any],
    *,
    claude: ClaudeService,
    memory: AgentMemory,
) -> tuple[str, int, float]:
    system = _DRAFT_SYSTEM_PROMPT.replace("{slide_count}", str(slide_count))
    user = _draft_user_message(topic, slide_count, research_md, profile)
    # Use the high-quality WRITING_MODEL chain for actual prose; falls back
    # to the standard chain if no premium provider key is set.
    writer = getattr(claude, "complete_writing", claude.complete)
    text, tokens, cost = await writer(
        system=system,
        user=user,
        max_tokens=6000,
        temperature=0.65,
    )
    md = _strip_doc_fences(text)
    memory.write_artifact("deck_draft.md", md)
    return md, tokens, cost


# ── Step 3: refiner ────────────────────────────────────────────────────────

_REFINER_SYSTEM_PROMPT = """You are NEXUS Refiner. You receive a markdown
slide-deck draft and return an improved version of THE SAME markdown document.

Improvements you make:
- Tighten weak prose; replace generic phrases with specific facts from the draft.
- Ensure every section has the right density (no thin sections, no walls of text).
- Make sure consecutive sections do NOT repeat the same facts/numbers.
- Verify all tables have aligned columns and no empty cells.
- Verify chart blocks have valid types (bar/line/pie/doughnut/area), real labels
  and values, and a source.
- Keep the SAME number of `##` sections. Keep the H1 title.

Output: ONE markdown document only. No diff format. No commentary. No fences
around the whole doc.
"""


async def run_refine(
    draft_md: str,
    profile: dict[str, Any],
    *,
    claude: ClaudeService,
    memory: AgentMemory,
) -> tuple[str, int, float]:
    from agent.topic_classifier import style_guidance_block
    style = style_guidance_block(profile)
    user = (
        f"Editorial profile: {profile.get('category')}{style}\n\n"
        f"Draft to refine:\n\n{draft_md}"
    )
    writer = getattr(claude, "complete_writing", claude.complete)
    text, tokens, cost = await writer(
        system=_REFINER_SYSTEM_PROMPT,
        user=user,
        max_tokens=6000,
        temperature=0.4,
    )
    md = _strip_doc_fences(text)
    memory.write_artifact("deck_final.md", md)
    return md, tokens, cost


# ── Step 4: markdown \u2192 slide JSON parser ─────────────────────────────────

_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_QUOTE_RE = re.compile(r"^>\s+(.+)$", re.MULTILINE)
_CHART_BLOCK_RE = re.compile(r"```chart\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_TABLE_LINE_RE = re.compile(r"^\s*\|.+\|\s*$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$", re.MULTILINE)
# Pools of bullet-driven visual layouts. Keep title/closing/chart/table/quote
# out of these — those are content-driven and chosen earlier.
# `_DEFINITION_LAYOUTS` are good when bullets are "Term: definition" pairs.
# `_SIMPLE_LAYOUTS` work for plain bullet lists.
_DEFINITION_LAYOUTS = ("bento", "feature-grid", "callout", "roadmap", "process")
_SIMPLE_LAYOUTS = ("bullets", "agenda", "callout", "pyramid", "matrix-2x2", "two-col")
_NUMBER_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*%?)\b")
_STEP_HINT_RE = re.compile(r"\b(step|phase|stage|milestone)\b", re.I)



def parse_markdown_to_slides(
    md: str,
    *,
    fallback_topic: str,
    slide_count: int,
) -> list[dict[str, Any]]:
    """Convert the final markdown into a list of slide dicts.

    Layout selection per section is deterministic:
        * has chart block          \u2192 "chart"
        * has table                \u2192 "table"
        * has > quote              \u2192 "quote"
        * has 3+ bullets only      \u2192 "bullets"
        * has 2 sub-headings (###) \u2192 "two-col"
        * otherwise                \u2192 "bullets" (paragraph split into points)

    First section becomes "title", last becomes "closing".
    """
    if not md or not md.strip():
        return []

    h1 = _H1_RE.search(md)
    deck_title = (h1.group(1) if h1 else fallback_topic).strip()

    # Split on H2 boundaries.
    parts = re.split(r"\n##\s+", md)
    # parts[0] is the preamble (H1 + intro before first ##); skip it.
    sections: list[tuple[str, str]] = []
    for chunk in parts[1:]:
        # First line of chunk is the section title; rest is body.
        nl = chunk.find("\n")
        if nl == -1:
            sections.append((chunk.strip(), ""))
        else:
            sections.append((chunk[:nl].strip(), chunk[nl + 1 :].strip()))

    if not sections:
        return []

    slides: list[dict[str, Any]] = []
    for i, (title, body) in enumerate(sections):
        is_first = i == 0
        is_last = i == len(sections) - 1
        slide = _section_to_slide(
            title, body, is_first=is_first, is_last=is_last, deck_title=deck_title
        )
        slide["index"] = i
        slides.append(slide)

    # Pad / trim to slide_count.
    while len(slides) < slide_count:
        slides.append({
            "index": len(slides),
            "layout": "bullets",
            "title": f"Section {len(slides) + 1}",
            "bullets": [],
        })
    slides = slides[:slide_count]
    # Force first/last layout types.
    if slides:
        slides[0]["layout"] = "title"
        slides[-1]["layout"] = "closing"
    return slides


def _section_to_slide(
    title: str,
    body: str,
    *,
    is_first: bool,
    is_last: bool,
    deck_title: str,
) -> dict[str, Any]:
    body = body.strip()

    # Detect chart block first (priority).
    chart_match = _CHART_BLOCK_RE.search(body)
    if chart_match:
        chart = _parse_chart_block(chart_match.group(1))
        return {
            "layout": "chart",
            "title": title,
            "chart_data": chart,
            "chart_type": chart.get("chart_type", "bar"),
            "labels": chart.get("labels", []),
            "values": chart.get("values", []),
            "unit": chart.get("unit", ""),
            "source": chart.get("source", ""),
        }

    # Table?
    table = _parse_table(body)
    if table:
        return {
            "layout": "table",
            "title": title,
            "headers": table["headers"],
            "rows": table["rows"],
        }

    # Quote?
    quote_match = _QUOTE_RE.search(body)
    if quote_match and len(_QUOTE_RE.findall(body)) >= 1 and len(body) < 600:
        quote_text, attribution = _split_quote(quote_match.group(1).strip())
        return {
            "layout": "quote",
            "title": title,
            "quote": quote_text,
            "attribution": attribution,
        }

    # Bullets?
    bullets = [m.group(1).strip() for m in _BULLET_RE.finditer(body)]
    bullets = [_strip_md_inline(b) for b in bullets if b.strip()]

    if is_first:
        # Title slide: prefer the FIRST SHORT sentence as a tagline, not the
        # whole intro paragraph (which is often a long stats dump).
        first_para = _first_paragraph(body)
        sents = _split_sentences(first_para)
        if sents:
            tag = sents[0]
            # If the first sentence is itself huge, trim at a comma/word.
            if len(tag) > 140:
                cut = tag.rfind(",", 0, 140)
                tag = (tag[:cut] if cut > 60 else tag[:140].rsplit(" ", 1)[0]) + "…"
        else:
            tag = first_para[:140]
        return {
            "layout": "title",
            "title": deck_title or title,
            "subtitle": title if (deck_title and deck_title != title) else tag,
            "tagline": tag,
            "eyebrow": "Presentation",
        }

    if is_last:
        # Closing slide — use FULL first paragraph (trimmed at a sentence
        # boundary, never mid-word).
        first_para = _first_paragraph(body)
        msg = first_para or title
        if len(msg) > 700:
            msg = msg[:700]
            cut = max(msg.rfind(". "), msg.rfind("! "), msg.rfind("? "))
            if cut > 200:
                msg = msg[: cut + 1]
            else:
                msg = msg.rsplit(" ", 1)[0] + "…"
        return {
            "layout": "closing",
            "title": title,
            "message": msg,
            "cta": (bullets[0] if bullets else ""),
            "tagline": "Generated by NEXUS",
        }

    if bullets and len(bullets) >= 2:
        return _build_visual_slide(title, body, bullets, is_first=is_first)

    # Fallback: long paragraph \u2192 split into bullets by sentence.
    sentences = _split_sentences(body)
    if len(sentences) >= 3:
        synth = [_strip_md_inline(s) for s in sentences[:5]]
        return _build_visual_slide(title, body, synth, is_first=is_first)

    # Last resort: paragraph card.
    return {
        "layout": "bullets",
        "title": title,
        "bullets": [_strip_md_inline(body[:280])] if body else [],
    }


def _build_visual_slide(
    title: str,
    body: str,
    bullets: list[str],
    *,
    is_first: bool,
) -> dict[str, Any]:
    """Pick a visually-rich layout based on bullet shape + a deterministic
    rotation hash so consecutive slides do not all look the same.
    """
    n = len(bullets)
    has_definitions = sum(
        1 for b in bullets if ":" in b and len(b.split(":", 1)[0]) <= 40
    ) >= max(2, n // 2)
    is_steps = bool(_STEP_HINT_RE.search(title) or _STEP_HINT_RE.search(body))
    big_number = _NUMBER_RE.search(body)

    # Single dominant metric -> spotlight slide.
    if big_number and n <= 3 and any(ch in big_number.group(1) for ch in "%,."):
        try:
            num = big_number.group(1)
            label = body.split(num, 1)[1][:80].strip(" .,:;-") or title
            return {
                "layout": "metric-spotlight",
                "title": title,
                "eyebrow": title[:40].upper(),
                "stats": [{"value": num, "label": label}],
                "subtitle": _first_paragraph(body)[:160],
            }
        except Exception:
            pass

    # Numbered procedure / phases -> process or roadmap.
    if is_steps and 3 <= n <= 6:
        layout = "roadmap" if n <= 5 else "process"
        return {"layout": layout, "title": title, "bullets": bullets[:6]}

    # Definition-style bullets -> grid layouts that show head + body.
    if has_definitions:
        pool = _DEFINITION_LAYOUTS
        if n >= 6:
            picked = pool[(hash(title) >> 3) % len(pool)]
        elif n in (4, 5):
            picked = pool[(hash(title) >> 3) % 3]  # bento / feature-grid / callout
        else:
            picked = "callout"
        cap = {"bento": 6, "feature-grid": 4, "callout": 4, "roadmap": 5, "process": 5}.get(picked, 6)
        return {
            "layout": picked,
            "title": title,
            "bullets": bullets[:cap],
            "eyebrow": title.split(":", 1)[0][:40].upper() if ":" in title else "",
        }

    # Plain bullets - deterministic rotation across the simple pool.
    h = abs(hash(title))
    pool = _SIMPLE_LAYOUTS
    if n == 2:
        pool = ("two-col", "comparison", "callout")
    elif n == 3:
        pool = ("pyramid", "agenda", "callout", "two-col")
    elif n >= 7:
        pool = ("agenda", "bullets")
    picked = pool[h % len(pool)]
    cap = {
        "matrix-2x2": 4, "pyramid": 3, "two-col": 4,
        "comparison": 4, "callout": 4, "agenda": 6,
    }.get(picked, 6)
    out: dict[str, Any] = {
        "layout": picked,
        "title": title,
        "bullets": bullets[:cap],
    }
    if picked in ("two-col", "comparison") and n >= 2:
        mid = (n + 1) // 2
        out["columns"] = [
            {"heading": "", "body": " \u2022 ".join(bullets[:mid])},
            {"heading": "", "body": " \u2022 ".join(bullets[mid:cap])},
        ]
    return out


def _parse_table(body: str) -> dict[str, Any] | None:
    lines = [ln for ln in body.splitlines() if _TABLE_LINE_RE.match(ln)]
    if len(lines) < 3:
        return None
    # Drop the separator row (---|---).
    if not re.search(r"\|\s*-{3,}", lines[1]):
        return None
    header_cells = _split_table_row(lines[0])
    rows = [_split_table_row(ln) for ln in lines[2:] if ln.strip()]
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not header_cells or not rows:
        return None
    return {"headers": header_cells, "rows": rows}


def _split_table_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return [_strip_md_inline(c) for c in cells]


def _parse_chart_block(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {"chart_type": "bar", "labels": [], "values": [], "unit": "", "source": ""}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key == "type":
            out["chart_type"] = val.lower()
        elif key == "title":
            out["title"] = val
        elif key == "labels":
            out["labels"] = _parse_list_value(val)
        elif key == "values":
            out["values"] = [_to_number(x) for x in _parse_list_value(val)]
        elif key in ("unit", "units"):
            out["unit"] = val
        elif key == "source":
            out["source"] = val
    return out


def _parse_list_value(val: str) -> list[str]:
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        val = val[1:-1]
    return [v.strip().strip('"').strip("'") for v in val.split(",") if v.strip()]


def _to_number(x: str) -> float | int | str:
    s = str(x).replace(",", "").replace("%", "").strip()
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return x


def _split_quote(s: str) -> tuple[str, str]:
    # Split on em-dash, en-dash, or " - " for attribution.
    for sep in ("\u2014", "\u2013", " - "):
        if sep in s:
            q, _, a = s.rpartition(sep)
            return q.strip().strip('"').strip("'"), a.strip()
    return s.strip().strip('"').strip("'"), ""


def _first_paragraph(body: str) -> str:
    for para in body.split("\n\n"):
        p = para.strip()
        if p and not p.startswith(("-", "*", ">", "|", "#", "```")):
            return _strip_md_inline(p)
    return ""


def _split_sentences(body: str) -> list[str]:
    plain = re.sub(r"```[\s\S]*?```", " ", body)
    plain = re.sub(r"\n+", " ", plain).strip()
    # Protect common abbreviations whose period must NOT end a sentence.
    abbrevs = (
        r"Dr|Mr|Mrs|Ms|Prof|Sr|Jr|St|Inc|Ltd|Co|Corp|U\.S|U\.K|U\.N|"
        r"e\.g|i\.e|etc|vs|approx|cf|No|Vol|Fig|Eq|Eqs|Sec|Ch"
    )
    plain = re.sub(rf"\b({abbrevs})\.", lambda m: m.group(1) + "\u2024", plain)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z“‘])", plain)
    sentences = [s.replace("\u2024", ".") for s in sentences]
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def _strip_md_inline(s: str) -> str:
    # Strip ** _ ` markers; keep the text.
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s.strip()


def _strip_doc_fences(text: str) -> str:
    """Remove a stray ```markdown ... ``` wrapper around the whole doc."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:markdown|md)?\s*\n", "", s)
        if s.endswith("```"):
            s = s[: -3].rstrip()
    return s


# ── Public entry point ────────────────────────────────────────────────────

async def run_markdown_pipeline(
    topic: str,
    slide_count: int,
    profile: dict[str, Any],
    *,
    claude: ClaudeService,
    search: SearchService,
    memory: AgentMemory,
    on_progress=None,
    prepend_research: str = "",
) -> tuple[list[dict[str, Any]], int, float, str]:
    """Run research \u2192 draft \u2192 refine \u2192 parse and return slide dicts.

    Returns ``(slides, total_tokens, total_cost, final_md)``.
    """
    total_tokens = 0
    total_cost = 0.0

    if on_progress:
        await on_progress("Researching from multiple sources...", 18.0, "search")
    research_md, _sources = await run_research(
        topic, profile=profile, search=search, memory=memory
    )
    if prepend_research:
        research_md = prepend_research.strip() + "\n\n" + (research_md or "")

    if on_progress:
        await on_progress("Writing structured markdown draft...", 32.0, "draft")
    draft_md, t1, c1 = await run_draft(
        topic, slide_count, research_md, profile, claude=claude, memory=memory
    )
    total_tokens += t1
    total_cost += c1

    if on_progress:
        await on_progress("Refining the draft...", 55.0, "refine")
    try:
        final_md, t2, c2 = await run_refine(
            draft_md, profile, claude=claude, memory=memory
        )
        total_tokens += t2
        total_cost += c2
    except Exception as exc:
        logger.warning("markdown_pipeline.refine_failed", extra={"err": str(exc)})
        final_md = draft_md

    if on_progress:
        await on_progress("Converting markdown to slides...", 78.0, "assemble")
    slides = parse_markdown_to_slides(
        final_md, fallback_topic=topic, slide_count=slide_count
    )
    return slides, total_tokens, total_cost, final_md
