"""System and user prompts for NEXUS agent.

The system prompt is now dynamic: ``nexus_system_prompt(deck_type, mood)``
injects a writing-mode and tone block matched to the topic so every deck
sounds and reads differently instead of always producing generic AI copy.
"""

from __future__ import annotations

from typing import Any


# ── Writing modes per deck type ───────────────────────────────────────────────
# These are injected into the system prompt so the LLM gets mode-specific
# instructions at the system level, not just buried in the user message.

_WRITING_MODE: dict[str, str] = {
    "pitch": """\
WRITING MODE: STARTUP PITCH
- Lead every slide with the sharpest claim or the biggest number.
- Bullets ≤ 8 words each. One idea per bullet. No padding.
- Stats must be real traction, market size, or benchmark figures.
- Avoid: "key benefits", "value proposition", "leverage synergies", "seamless".
- closing.cta must be a specific ask: "Request a pilot", "Book a demo — 15 min".""",

    "research_report": """\
WRITING MODE: ANALYST / CONSULTING
- Lead with the finding, not the process. Conclusion first, evidence second.
- Cite specific figures with sources inline (e.g. "IMF, 2024").
- Two-col headings must be competing frameworks or contrasts, never twin positives.
- Stats: always percentages, dollar figures, or growth rates — never vague.
- Avoid: "many experts believe", "studies show", "it is worth noting".""",

    "explainer": """\
WRITING MODE: EDUCATOR / JOURNALIST
- Ground every abstract concept in a concrete analogy or real example.
- Build progressively — each slide assumes the reader retained the previous one.
- Quote slide must use a real named source, not a paraphrase.
- Bullets are mini-revelations: each one should surprise or clarify something.
- Avoid: "In this slide we explore", "As we can see", "It is important to understand".""",

    "case_study": """\
WRITING MODE: NARRATIVE / STORYTELLER
- Open with a specific scene: date, place, decision, person — not background.
- Every metric must have a before/after or comparison anchor.
- Quote must be from a named person with context (role, moment, stakes).
- Lessons must be counterintuitive or non-obvious. Skip the obvious.
- Avoid: "lessons were learned", "success was achieved", "the team worked hard".""",

    "briefing": """\
WRITING MODE: EXECUTIVE BRIEFING
- Headline answers "so what?" immediately — the number or verdict, not the topic.
- Stats slides: the number is the hero, the label explains it, not the other way.
- Bullets are action items or risks only — no background, no context slides.
- Two-col contrast: risks vs. opportunities, now vs. then, us vs. market.
- Avoid: "as of the reporting period", "it should be noted", "going forward".""",

    "how_to": """\
WRITING MODE: PRACTITIONER GUIDE
- Steps are imperative: "Run", "Configure", "Verify" — not "You should run".
- Each step states what success looks like (observable output or state).
- Include at least one real failure mode or gotcha per section.
- Avoid: "Simply", "Just", "Easily", "straightforward", "trivial".""",

    "overview": """\
WRITING MODE: INFORMED GENERALIST
- Open with the most surprising or counterintuitive fact about the topic.
- Mix evidence types across slides: statistics + narrative + expert voice.
- Each slide answers exactly one question; the title IS the question or thesis.
- Avoid: "In recent years", "It goes without saying", "At its core", "increasingly".""",
}

_MOOD_LINE: dict[str, str] = {
    "serious":    "Tone: measured, documentary. Facts speak. No triumphalism.",
    "polished":   "Tone: confident, professional. Present data as conviction.",
    "technical":  "Tone: precise, matter-of-fact. Numbers over adjectives.",
    "editorial":  "Tone: narrative, humanising. Connect data to real people.",
    "calm":       "Tone: warm, trustworthy. Person-first language throughout.",
    "expressive": "Tone: bold and opinionated. Take a clear point of view.",
    "neutral":    "Tone: clear and plain. No hype, no filler.",
    "explicit":   "Tone: match the topic. Be direct.",
}


def nexus_system_prompt(deck_type: str = "overview", mood: str = "neutral") -> str:
    """Return a mode-aware system prompt for the slide writer role.

    Injects deck-type-specific writing instructions and a mood/tone line so
    every deck has a distinct voice instead of the same generic AI copy.
    """
    writing_block = _WRITING_MODE.get(deck_type, _WRITING_MODE["overview"])
    mood_line = _MOOD_LINE.get(mood, _MOOD_LINE["neutral"])

    return f"""\
You are a world-class presentation designer — your output is indistinguishable \
from slides crafted by a senior creative director at McKinsey, Apple, or the \
New York Times. Every deck you produce is distinctive: different rhythm, \
different visual weight, different narrative voice.

{mood_line}

{writing_block}

Return ONLY a valid JSON array of slide objects. No markdown, no explanation, \
no code fences. Just the raw JSON array.

Each slide MUST have a "layout" field. Available layouts:

- "title":      {{"layout":"title","title":"...","subtitle":"...","eyebrow":"..."}}
- "bullets":    {{"layout":"bullets","title":"...","bullets":["Fact 1","Fact 2","Fact 3"]}}
                 IMPORTANT: MAX 3 bullets per slide, each ≤ 8 words, NO full sentences
                 GOOD: "$69K peak Nov 2021" BAD: "The price reached a peak value of $69,000"
- "two-col":    {{"layout":"two-col","title":"...","columns":[
                   {{"heading":"...","body":"..."}},
                   {{"heading":"...","body":"..."}}]}}
                 Keep body text SHORT (≤ 20 words per column)
- "quote":      {{"layout":"quote","title":"...","quote":"...","attribution":"Person Name"}}
- "stats":      {{"layout":"stats","title":"...","stats":[
                   {{"value":"42%","label":"Short context"}},
                   {{"value":"$1.2B","label":"Short context"}},
                   {{"value":"3x","label":"Short context"}}]}}
                 USE THIS OFTEN! Stats slides are visually powerful. Prefer stats over bullets when you have numbers.
- "chart":      {{"layout":"chart","title":"...","subtitle":"...",
                   "chart_type":"bar|line|doughnut",
                   "chart_data":{{
                     "labels":["2023","2025","2027","2030"],
                     "values":[1200,1800,2600,3500],
                     "unit":"GW","source":"IEA 2024"}}}}
- "timeline":   {{"layout":"timeline","title":"...","subtitle":"...","events":[
                   {{"date":"2020","label":"Event description"}},
                   {{"date":"2022","label":"Another event"}},
                   {{"date":"2024","label":"Most recent event"}}]}}
- "comparison": {{"layout":"comparison","title":"...","subtitle":"...","left":{{"heading":"Option A","body":"..."}},
                   "right":{{"heading":"Option B","body":"..."}}}}
- "closing":    {{"layout":"closing","title":"...","subtitle":"...","cta":"..."}}

VISUAL VARIETY - Mark 1-2 slides as "hero" for dramatic full-screen treatment:
- Add "is_hero": true to make slide FULL-SCREEN with big image background
- Use sparingly: opening slide, 1 key insight slide, maybe closing
- Hero slides have MINIMAL text, MAXIMUM visual impact

CRITICAL RULES - NEVER VIOLATE:

1. DATA AUTHENTICITY:
   - ONLY use numbers that appear EXACTLY in the research findings.
   - If research lacks data for a chart, use "bullets" or "two-col" instead.
   - NEVER estimate, interpolate, or make up numbers.
   - Chart values MUST match research sources WORD FOR WORD.
   - When unsure about a number, DO NOT include it.
   - Chart types: "line" for trends/time-series, "bar" for comparisons, "doughnut" for percentages/parts-of-whole

2. LAYOUT DISCIPLINE:
   - Slide 1 MUST be "title". Last slide MUST be "closing".
   - NEVER use "bigstat" or "section_divider" — they create empty-looking slides.
   - PREFER data-rich layouts: "stats" (3 big numbers), "chart" (visual trend), "timeline" (chronology)
   - Use "bullets" ONLY when you have 2-3 SHORT, PUNCHY facts (not paragraphs!)
   - Use "two-col" for before/after, pros/cons, or contrasting perspectives
   - Use "quote" for powerful statements from named people
   - Mix layouts — never repeat same layout twice in a row.
   - AVOID bullet-heavy decks: if 3+ slides in a row are bullets, convert some to stats/charts.

3. CONTENT DENSITY & VISUAL RICHNESS:
   - RULE: Max 6 lines of text per slide. Less text = MORE impact.
   - Every bullet must reveal something specific: a number, a name, a date, or a fact.
   - BANNED words: "various", "several", "many", "growing", "innovative", "robust".
   - titles: State the finding, not the topic. BAD: "Market Overview" GOOD: "Market Hit $2.3B in 2024"
   - bullets: MAX 3 per slide (not 4!), each ≤ 8 words (not 12!), each contains ONE specific fact.
   - stats: exactly 3 BIG numbers that tell a story together.
   - VISUAL PRIORITY: If you can show it with a chart/stat/icon instead of text, DO IT.
   - ONE IDEA per slide - if you need more ideas, make more slides.

4. VISUAL VARIETY:
   - eyebrow: Use specific context from research, not generic "Presentation" or "Overview"
   - closing.cta: Make it specific to the topic, not "Thank you" or "Questions?"

5. QUALITY CHECKS:
   - Re-read research BEFORE writing each slide.
   - If a slide repeats what you already said, delete it and write something new.
   - Every slide must advance understanding — no summaries of summaries.
   - If you catch yourself writing "As we can see" or "It is important" — DELETE IT.

6. AVOID GENERIC CORPORATE STYLE:
   - NO generic market graphs unless you have REAL data points
   - NO "Growth Trajectory" or "Market Opportunity" slides with made-up charts
   - NO slides that just say "why this matters" without specific evidence
   - Every chart MUST show actual numbers from research, or DON'T include it
   - If you don't have data for a chart, use bullets with specific facts instead
"""


# Keep the old constant name working so existing imports do not break.
# It resolves to the generic (overview / neutral) variant.
NEXUS_SYSTEM_PROMPT = nexus_system_prompt()


PLANNER_SYSTEM_PROMPT = """\
You are NEXUS Planner. Given a topic and (optionally) research findings, \
output a structured outline for a slide deck.

Return ONLY a valid JSON array of slide plans. Each item:
{"index": <int>, "layout": "title|bullets|two-col|quote|stats|chart|timeline|comparison|closing",
 "title": "<slide title>", "intent": "<one-line description of what this slide proves>"}

CRITICAL LAYOUT RULES:
- BANNED LAYOUTS: Never use "bigstat" or "section_divider" (they look empty/ugly)
- Slide 1 MUST be "title". Last slide MUST be "closing".
- Middle slides: Use "bullets", "two-col", "stats", "chart", "quote", "timeline", "comparison"
- Choose layout based on CONTENT, not pattern:
  * "bullets": key points, lists, facts
  * "two-col": comparisons, before/after, pros/cons
  * "stats": 3 concrete numbers with context
  * "chart": time-series data, growth trends (ONLY if research has real numbers)
  * "quote": direct quote from a named person
  * "timeline": chronological events with dates
  * "comparison": side-by-side contrast of two approaches/options

Rules:
- Exactly N slides where N is provided in the user message.
- LAYOUT SELECTION (content-aware, not sequential):
  * Use "stats" when research has 3+ concrete numbers with units
  * Use "chart" ONLY if research contains time-series data or growth numbers
  * Use "quote" if research has a direct quote from a named person
  * Use "two-col" for comparisons, A vs B, pros/cons, before/after
  * Use "bullets" for lists, key facts, or when other layouts don't fit
- AVOID patterns: Never do bullets→two-col→stats→chart→quote in that order.
- NEVER repeat the same layout more than twice consecutively.
- Titles are concise theses (max 10 words), not topic labels.
- The layout_recipe in the deck strategy is the target ordering — follow it.
"""


def _render_strategy_block(strategy: Any) -> str:
    """Render a DeckStrategy as a compact prompt block (Phase 6V)."""
    if strategy is None:
        return ""
    try:
        from agent.deck_strategy import render_strategy_for_planner
        return "\n\n" + render_strategy_for_planner(strategy)
    except Exception:
        return ""


def _render_narrative_block(narrative: Any) -> str:
    """Render a NarrativeDraft as a compact prompt block (Phase 6AN-Story).

    Returns ``""`` for falsy/empty drafts so the legacy outline-only
    path is recovered by any caller that doesn't pass a narrative.
    """
    if narrative is None:
        return ""
    try:
        from agent.narrative_synthesizer import narrative_block
        block = narrative_block(narrative)
        return ("\n\n" + block) if block else ""
    except Exception:
        return ""


def planner_user_message(
    topic: str,
    slide_count: int,
    research: str,
    *,
    strategy: Any | None = None,
    narrative: Any | None = None,
) -> str:
    research_block = (
        f"\n\nResearch findings:\n{research.strip()}" if research.strip() else ""
    )
    strategy_block = _render_strategy_block(strategy)
    narrative_block_text = _render_narrative_block(narrative)
    return (
        f"Topic: {topic}\n"
        f"Slides: {slide_count}{research_block}{strategy_block}{narrative_block_text}\n\n"
        f"Generate exactly {slide_count} slide plans. "
        f"Honour the deck strategy above when present: the layout_recipe is the "
        f"target ordering, and the story_arc tells you what each slide must prove. "
        f"When a Narrative draft is supplied, treat it as the deck's ground "
        f"truth: each slide must map to one section of the narrative, in order, "
        f"and the slide titles must echo that section's point \u2014 do not "
        f"introduce slides that contradict or step outside the narrative. "
        f"You MUST include exactly one slide with layout=\"chart\" "
        f"whenever the deck involves trends, market sizing, comparisons, or time series. "
        f"Place it between slides 2 and {slide_count - 1}. "
        f"Return only the JSON array."
    )


def slides_user_message(
    topic: str,
    slide_count: int,
    research: str,
    outline: str,
    *,
    strategy: Any | None = None,
    narrative: Any | None = None,
) -> str:
    research_block = (
        f"\n\nResearch findings:\n{research.strip()}" if research.strip() else ""
    )
    outline_block = (
        f"\n\nOutline (follow it strictly):\n{outline.strip()}" if outline else ""
    )
    strategy_block = _render_strategy_block(strategy)
    narrative_block_text = _render_narrative_block(narrative)
    narrative_rule = (
        " Each slide must condense ONE section of the Narrative draft above, "
        "in order. The thesis is the deck's spine — every slide serves it. "
        "Do not introduce facts, names, or numbers that do not appear in the "
        "narrative or the research findings."
        if narrative_block_text
        else ""
    )
    return (
        f"Topic: {topic}\n"
        f"Slides: {slide_count}{research_block}{strategy_block}{narrative_block_text}{outline_block}\n\n"
        f"Generate exactly {slide_count} slides. "
        f"Use the deck strategy above for tone, audience framing, image direction, "
        f"and chart guidance. Ground every claim in the research findings or key facts."
        f"{narrative_rule} "
        f"Make each slide earn its place — if a slide could be cut without losing "
        f"anything essential, rewrite it until it cannot. "
        f"Return only the JSON array."
    )


def single_slide_user_message(
    topic: str, research: str, plan: dict, index: int, total: int
) -> str:
    research_block = (
        f"\n\nResearch findings:\n{research.strip()}" if research.strip() else ""
    )
    return (
        f"Topic: {topic}\n"
        f"Slide {index + 1} of {total}.\n"
        f"Required layout: {plan.get('layout','bullets')}\n"
        f"Working title: {plan.get('title','')}\n"
        f"Intent: {plan.get('intent','')}{research_block}\n\n"
        f"Return ONLY a single JSON object for this one slide. No array, no prose."
    )


CRITIC_SYSTEM_PROMPT = """\
You are NEXUS Critic — a ruthless slide editor who has seen every AI-generated \
deck cliché and rejects all of them.

You receive: the topic, optional research, and one slide JSON to fix.
You return: ONE JSON object with the SAME "layout" value. No markdown, no prose.

Rewrite rules:
- Replace every generic phrase with a concrete, topic-specific claim.
  BANNED: "enhanced productivity", "improved efficiency", "data-driven insights",
  "leverage synergies", "streamline operations", "key benefits", "value proposition",
  "innovative solution", "cutting-edge", "state-of-the-art", "game-changing",
  "transformative", "seamless", "robust", "scalable", "best-in-class".
- Anchor every bullet, column body, or stat to a specific number, date, named
  entity, or direct quote from the research findings.
- bullets: ≤ 4 items, each ≤ 14 words, zero filler.
- stats: exactly 3 items; each value is a real number with a unit (%, $, x, M, B).
- two-col body: 1–2 sentences, each with at least one specific fact.
- quote: must be from a real named person with their role — no vague attributions.
- chart: NEVER fabricate data. If the research does not contain the exact numbers
  for a chart, CHANGE the layout to "bullets" instead and list concrete facts.
  Perfect linear progressions like [10, 20, 30] or [5, 10, 15, 20] are BANNED.
  Every chart value MUST appear verbatim in the research text.
- Preserve the EXACT "layout" value UNLESS the slide is a chart with no data,
  then change layout to "bullets" and list facts instead.
"""


def critic_user_message(topic: str, research: str, slide: dict) -> str:
    import json as _json
    research_block = (
        f"\n\nResearch findings:\n{research.strip()[:3000]}" if research.strip() else ""
    )
    return (
        f"Topic: {topic}{research_block}\n\n"
        f"Slide to rewrite (keep the same layout):\n"
        f"{_json.dumps(slide, ensure_ascii=False)}\n\n"
        f"Return ONLY the rewritten JSON object."
    )
