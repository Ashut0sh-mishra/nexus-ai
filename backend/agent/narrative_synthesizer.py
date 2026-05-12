"""Phase 6AN-Story: story-first narrative synthesis.

The pre-6AN pipeline went:

    research blob  ->  outline of slide titles  ->  write each slide

Each slide was generated in isolation against an abstract intent like
"prove the market is big". With no continuous story in front of the
writer, the LLM produced eight independently-correct slides that did
not feel like one deck \u2014 the textbook "AI-generated" symptom.

This module inserts a missing step between research/strategy and
outline: a single LLM call that writes a **~500-word narrative draft**
of the deck before the slide skeleton is planned. Five paragraphs,
mapped to the strategy's story arc, anchored on the harvested research
with named entities and concrete numbers.

Both the planner and the writer then receive this narrative as the
deck's **ground truth**. The writer is told that each slide must
condense one section of the narrative; new facts not present in the
narrative are forbidden.

The module follows the additive contract the rest of the pipeline uses:

* Kill switch ``NEXUS_DISABLE_NARRATIVE=true`` returns an empty
  narrative so the legacy path is one env var away.
* Any LLM/parse failure degrades to an empty narrative; the pipeline
  keeps working exactly as before.
* Pure synchronous helpers (``compose_narrative_prompt``,
  ``narrative_block``) are exported separately so they can be unit
  tested without an LLM.

Public surface:

    NarrativeDraft (dataclass) \u2014 ``thesis``, ``sections``, ``raw``.
    async synthesize_narrative(...) -> tuple[NarrativeDraft, tokens, cost]
    narrative_block(draft) -> str  # injection block for prompts
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


logger = logging.getLogger(__name__)

_KILL_SWITCH_ENV = "NEXUS_DISABLE_NARRATIVE"

# Hard cap on narrative size so it never blows the writer's context.
# Five paragraphs at ~80\u2013120 words each is the target.
_MAX_NARRATIVE_CHARS = 3_500


AiCall = Callable[..., Awaitable[tuple[str, int, float]]]


@dataclass(frozen=True)
class NarrativeSection:
    """One arc beat in the narrative draft."""

    beat: str  # e.g. "problem", "turning_point", "evidence"
    heading: str  # short editor-style label
    body: str  # one paragraph of prose, 1\u20133 sentences typically


@dataclass(frozen=True)
class NarrativeDraft:
    """The deck's prose-first ground truth.

    ``thesis`` is the deck's single-sentence point of view; the writer
    and planner are told that every slide must serve this thesis.
    ``sections`` is the ordered list of paragraphs matching the
    strategy's story arc.
    ``raw`` is the unparsed LLM response, retained so we can show it
    in the AI-reasoning panel and so that pre-6AN behaviour is
    recoverable by inspection.
    """

    thesis: str = ""
    sections: tuple[NarrativeSection, ...] = field(default_factory=tuple)
    raw: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.thesis and not self.sections


_EMPTY_DRAFT = NarrativeDraft()


def compose_narrative_prompt(
    *,
    topic: str,
    research: str,
    deck_type: str,
    audience: str,
    tone: str,
    thesis_hint: str,
    story_arc: list[str],
    key_facts: list[str],
    slide_count: int,
) -> tuple[str, str]:
    """Build the (system, user) prompt for the narrative synthesizer.

    Separated from :func:`synthesize_narrative` so the prompt itself
    can be unit tested without an LLM mock.
    """
    arc = story_arc or ["problem", "evidence", "implication"]
    arc_str = " -> ".join(arc)
    facts_str = "\n".join(f"  - {f}" for f in key_facts[:8]) or "  - (none)"
    research_str = (research or "").strip()
    if not research_str:
        research_str = "(no harvested research \u2014 rely on widely-known facts)"
    research_str = research_str[:6_000]

    system = (
        "You are an editor writing the brief that a deck designer will "
        "lay out. You return ONE JSON object with two keys: 'thesis' "
        "(a single sentence stating the deck's point of view) and "
        "'sections' (an ordered array of arc beats). Each section is "
        "{beat, heading, body}. Body is ONE paragraph of plain prose, "
        "1\u20133 sentences, that names real entities and cites real "
        "numbers from the research. No bullet points. No slide titles. "
        "No markdown. No preamble. JSON only."
    )

    user = (
        f"Topic: {topic}\n"
        f"Deck type: {deck_type}\n"
        f"Audience: {audience}\n"
        f"Tone: {tone}\n"
        f"Working thesis (you may sharpen): {thesis_hint or '(none yet)'}\n"
        f"Slide count target: {slide_count}\n\n"
        f"Story arc beats (use these as section.beat values, in this order):\n"
        f"  {arc_str}\n\n"
        f"Key facts to lean on:\n{facts_str}\n\n"
        f"Research findings:\n---\n{research_str}\n---\n\n"
        f"Write the editor's brief now. Constraints:\n"
        f"- One paragraph per beat, in the given arc order.\n"
        f"- Every paragraph must reference a specific named entity, "
        f"date, or number from the research findings or key facts.\n"
        f"- Forbidden language: 'enhanced productivity', 'leverage', "
        f"'streamline', 'innovative solution', 'cutting-edge', "
        f"'game-changing', 'transformative', 'seamless', 'robust', "
        f"'scalable', 'best-in-class', 'data-driven insights'.\n"
        f"- The thesis must take a position, not summarize the topic. "
        f"Avoid 'this deck explores' / 'this presentation covers'.\n"
        f"- Total length: 350\u2013650 words across all paragraphs.\n\n"
        f"Return ONLY the JSON object."
    )
    return system, user


def _strip_fences(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned


def _parse_narrative(raw: str) -> NarrativeDraft:
    """Lenient parser \u2014 returns an empty draft on any structural issue.

    Accepts the documented schema ``{thesis, sections:[{beat,heading,body}]}``
    plus a couple of common shape drifts (sections as dict-of-paragraphs,
    sections as list-of-strings) so a sloppy LLM response still produces
    usable output. Anything truly unparseable degrades to ``_EMPTY_DRAFT``
    so the legacy pipeline keeps running.
    """
    cleaned = _strip_fences(raw or "")
    if not cleaned:
        return _EMPTY_DRAFT
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
    except Exception:
        return _EMPTY_DRAFT
    if not isinstance(data, dict):
        return _EMPTY_DRAFT

    thesis_raw = data.get("thesis") or data.get("Thesis") or ""
    thesis = str(thesis_raw).strip()

    sections_raw = data.get("sections") or data.get("Sections") or []
    parsed: list[NarrativeSection] = []
    total_chars = 0
    if isinstance(sections_raw, list):
        for entry in sections_raw:
            if isinstance(entry, dict):
                beat = str(entry.get("beat") or entry.get("Beat") or "").strip()
                heading = str(entry.get("heading") or entry.get("Heading") or "").strip()
                body = str(entry.get("body") or entry.get("Body") or "").strip()
            elif isinstance(entry, str):
                beat = ""
                heading = ""
                body = entry.strip()
            else:
                continue
            if not body:
                continue
            section = NarrativeSection(
                beat=beat or "section",
                heading=heading,
                body=body,
            )
            parsed.append(section)
            total_chars += len(body)
            if total_chars >= _MAX_NARRATIVE_CHARS:
                break
    elif isinstance(sections_raw, dict):
        for beat_key, body in sections_raw.items():
            if not isinstance(body, str) or not body.strip():
                continue
            parsed.append(
                NarrativeSection(
                    beat=str(beat_key).strip() or "section",
                    heading="",
                    body=body.strip(),
                )
            )
            total_chars += len(body)
            if total_chars >= _MAX_NARRATIVE_CHARS:
                break

    if not thesis and not parsed:
        return _EMPTY_DRAFT
    return NarrativeDraft(
        thesis=thesis,
        sections=tuple(parsed),
        raw=raw,
    )


async def synthesize_narrative(
    *,
    topic: str,
    research: str,
    deck_type: str,
    audience: str,
    tone: str,
    thesis_hint: str,
    story_arc: list[str],
    key_facts: list[str],
    slide_count: int,
    ai_call: AiCall | None,
) -> tuple[NarrativeDraft, int, float]:
    """Run the narrative LLM call. Always safe; returns empty on failure.

    Returns ``(draft, tokens, cost)``. When ``ai_call`` is ``None`` (or
    the kill switch is set, or the LLM fails) returns an empty draft;
    callers must therefore treat an empty draft as "no narrative
    available" and proceed with the legacy outline-only path.
    """
    if os.environ.get(_KILL_SWITCH_ENV, "").lower() in ("1", "true", "yes"):
        return _EMPTY_DRAFT, 0, 0.0
    if ai_call is None:
        return _EMPTY_DRAFT, 0, 0.0
    if not (topic and topic.strip()):
        return _EMPTY_DRAFT, 0, 0.0

    system, user = compose_narrative_prompt(
        topic=topic,
        research=research,
        deck_type=deck_type,
        audience=audience,
        tone=tone,
        thesis_hint=thesis_hint,
        story_arc=story_arc,
        key_facts=key_facts,
        slide_count=slide_count,
    )

    try:
        text, tokens, cost = await ai_call(
            role="analyze",
            system=system,
            user=user,
            max_tokens=1_400,
            temperature=0.55,
        )
    except Exception as exc:
        logger.warning(
            "narrative_synth.ai_call_failed",
            extra={"topic": topic[:80], "err": str(exc)},
        )
        return _EMPTY_DRAFT, 0, 0.0

    draft = _parse_narrative(text or "")
    if draft.is_empty:
        logger.warning(
            "narrative_synth.unparseable",
            extra={"topic": topic[:80], "snippet": (text or "")[:160]},
        )
        return _EMPTY_DRAFT, tokens, cost

    logger.info(
        "narrative_synth.ok",
        extra={
            "topic": topic[:80],
            "sections": len(draft.sections),
            "thesis_chars": len(draft.thesis),
            "tokens": tokens,
        },
    )
    return draft, tokens, cost


def narrative_block(draft: NarrativeDraft) -> str:
    """Render a narrative draft as a prompt-injection block.

    Returns an empty string when the draft is empty so callers can
    safely concatenate without conditionals. The returned block leads
    with a stable header so the LLM can address it by name.
    """
    if draft.is_empty:
        return ""
    parts: list[str] = ["Narrative draft (ground truth \u2014 do not contradict):"]
    if draft.thesis:
        parts.append(f"Thesis: {draft.thesis}")
    for sec in draft.sections:
        label = sec.heading or sec.beat or "section"
        parts.append(f"[{label}] {sec.body}")
    return "\n".join(parts)


__all__ = [
    "NarrativeDraft",
    "NarrativeSection",
    "compose_narrative_prompt",
    "narrative_block",
    "synthesize_narrative",
]
