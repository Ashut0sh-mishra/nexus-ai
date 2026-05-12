"""NEXUS 6-step agent loop — Manus-style: analyze → search → plan → generate → assemble → save."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select

from agent.deck_repair import repair_for_validator
from agent.layouts_registry import (
    CANONICAL_LAYOUTS,
    FALLBACK_LAYOUT,
    normalize_layout,
)
from agent.memory import AgentMemory
from agent.planner import Planner
from agent.prompt_intent import extract_slide_count
from agent.prompts import nexus_system_prompt, slides_user_message
from agent.prompts import CRITIC_SYSTEM_PROMPT, critic_user_message
from database.connection import SessionLocal
from database.models import SlideDeck, Task
from services.claude_service import ClaudeService
from services.lifecycle_service import JobCancelled
from services.search_service import SearchService

logger = logging.getLogger("nexus.agent.loop")

ProgressCallback = Callable[[str, float, str], Awaitable[None]]

# Valid slide layouts come from the canonical registry. Do NOT reintroduce a
# hardcoded literal here — it will diverge from the frontend renderer.
_VALID_LAYOUTS = frozenset(CANONICAL_LAYOUTS)


class NexusAgentLoop:
    """Orchestrates the full slide generation pipeline for a single task."""

    def __init__(
        self,
        claude: ClaudeService | None = None,
        search: SearchService | None = None,
        planner: Planner | None = None,
    ) -> None:
        self.claude = claude or ClaudeService()
        self.search = search or SearchService()
        self.planner = planner or Planner(claude=self.claude)

    async def _ai_call(
        self,
        *,
        role: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> tuple[str, int, float]:
        """Phase 6W: route via ``complete_for_role`` when available, else
        fall back to ``complete`` so ClaudeService stand-ins/fakes that
        don't implement role routing keep working unchanged."""
        if hasattr(self.claude, "complete_for_role"):
            return await self.claude.complete_for_role(
                role=role,
                system=system,
                user=user,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        return await self.claude.complete(
            system=system, user=user, max_tokens=max_tokens, temperature=temperature
        )

    # ── Phase 6W: research compression (summarize role) ──────────────────
    # Threshold above which raw research is summarized before reaching the
    # planner / writer. Below this we keep full text to avoid information
    # loss on small decks. ~10k chars ≈ ~2.5k tokens.
    _RESEARCH_SUMMARIZE_THRESHOLD = 10_000

    async def _summarize_long_research(
        self, topic: str, research: str
    ) -> tuple[str, int, float]:
        """Compress harvested research via the ``summarize`` role when long.

        Returns ``(text, tokens, cost)``. If research is short or summarize
        fails, returns the original text unchanged with zero tokens/cost.
        Source metadata is preserved separately by the caller; this only
        compresses the narrative blob.
        """
        if not research or len(research) < self._RESEARCH_SUMMARIZE_THRESHOLD:
            return research, 0, 0.0
        try:
            text, tokens, cost = await self._ai_call(
                role="summarize",
                system=(
                    "You compress research notes into dense, fact-preserving "
                    "summaries. Keep all numbers, dates, names, and citations. "
                    "Drop filler, marketing language, and duplicates. Plain text only."
                ),
                user=(
                    f"Topic: {topic}\n\n"
                    f"Compress the following research to <= 1500 words while "
                    f"preserving every concrete figure, date, and source mention.\n\n"
                    f"---\n{research}\n---"
                ),
                max_tokens=2048,
                temperature=0.2,
            )
            if text and len(text) < len(research):
                logger.info(
                    "loop.research_summarized",
                    extra={"orig_chars": len(research), "new_chars": len(text)},
                )
                return text, tokens, cost
        except Exception as exc:
            logger.warning("loop.summarize_failed", extra={"err": str(exc)})
        return research, 0, 0.0

    async def _json_fix_retry(
        self, raw_text: str, *, expected: str = "array"
    ) -> tuple[str, int, float]:
        """Phase 6W: ask the ``json_fix`` role to repair malformed model output.

        Used when ``_parse_slides_array``/``_parse_single_slide`` fails on the
        primary writer output. Returns ``(repaired_text, tokens, cost)``; the
        caller is responsible for re-parsing. On any error returns the input
        text unchanged with zero tokens/cost so callers can fall through to
        the existing deterministic fallback path.
        """
        if not raw_text or not raw_text.strip():
            return raw_text, 0, 0.0
        target = "JSON array of slide objects" if expected == "array" else "single JSON slide object"
        try:
            text, tokens, cost = await self._ai_call(
                role="json_fix",
                system=(
                    "You repair malformed JSON. Output ONLY valid JSON matching "
                    "the requested shape. No prose, no code fences, no commentary."
                ),
                user=(
                    f"The following text was supposed to be a {target} but failed to parse. "
                    f"Repair it and return ONLY the valid JSON.\n\n---\n{raw_text}\n---"
                ),
                max_tokens=4096,
                temperature=0.0,
            )
            return text or raw_text, tokens, cost
        except Exception as exc:
            logger.warning("loop.json_fix_failed", extra={"err": str(exc)})
            return raw_text, 0, 0.0

    async def run(
        self,
        task_id: str,
        topic: str,
        slide_count: int,
        theme: str,
        search_web: bool,
        on_progress: ProgressCallback,
        min_sources: int = 0,
    ) -> dict[str, Any]:
        memory = AgentMemory(task_id)
        total_tokens = 0
        total_cost = 0.0
        model_used = self.claude.active_model
        research_sources: list[dict[str, Any]] = []
        # Resolved at strategy step; used to build a mode-specific system prompt.
        _deck_type = "overview"
        _mood = "neutral"
        # Phase 6AD: per-slide narrative beats. Computed once after
        # strategy is built; threaded into ``attach_slide_intent`` and
        # ``recommend_layouts`` so all downstream consumers see the
        # same dramatic shape.
        _beats: list[str] = []

        # Phase 6U: honour explicit slide-count requests embedded in the
        # prompt ("Produce a 12-slide ..."). This overrides the API
        # default of 8 — the user told us how many slides they want, so
        # the planner must respect that instead of the field default.
        hinted = extract_slide_count(topic)
        if hinted is not None and hinted != slide_count:
            logger.info(
                "loop.slide_count_override topic_hint=%d field=%d", hinted, slide_count
            )
            slide_count = hinted

        try:
            # 1 — ANALYZE
            await on_progress("Analyzing your topic...", 8.0, "analyze")
            await self._mark_running(task_id, "analyze", 8.0)

            # Phase 6AM-Grounding: topic expansion.
            # Short/vague prompts ("ai", "create ppt on ai") cause the
            # search step to return disambiguation noise (Wikipedia
            # stubs about unrelated subjects). We expand into 3-5
            # specific queries BEFORE search so the harvester has real
            # angles to ground on. The expander degrades to [topic]
            # under env kill switch, LLM failure, or already-specific
            # input \u2014 the pipeline keeps working unchanged in those
            # cases. Tokens are charged to ``total_tokens`` so the
            # frontend cost panel stays accurate.
            search_queries: list[str] = [topic]
            try:
                from agent.topic_expander import expand_topic, canonicalize_topic

                expanded, exp_tokens, exp_cost = await expand_topic(
                    topic, ai_call=self._ai_call, max_queries=5
                )
                if expanded:
                    search_queries = expanded
                total_tokens += exp_tokens
                total_cost += exp_cost
                # Replace the topic the rest of the pipeline sees with
                # the canonicalized form so meta-verbs ("create ppt on")
                # don't leak into the planner / writer / image prompts.
                canon = canonicalize_topic(topic)
                if canon:
                    topic = canon
                if len(search_queries) > 1:
                    await on_progress(
                        f"Expanded to {len(search_queries)} search angles.",
                        12.0,
                        "analyze",
                        event="design_decision",
                        decision="topic_expanded",
                        value={
                            "queries": search_queries,
                            "tokens": exp_tokens,
                        },
                    )
            except Exception as exc:
                logger.warning("loop.topic_expander_failed", extra={"err": str(exc)})

            # 2 — SEARCH
            research = ""
            # Phase 6AN-JsonImport: when the task was created by the
            # POST /api/import/json endpoint, the user-supplied data has
            # already been written to the memory dir as
            # ``seed_research.json`` (or ``seed_research.txt``). Use it
            # as the research blob and skip the web-search step entirely
            # \u2014 the generator should ground on the user's data, not
            # Wikipedia. ``search_web`` is set to False on those tasks,
            # so this branch is only reachable when there is in fact a
            # seed file to read; the legacy path is untouched.
            seed_research_text = ""
            try:
                from pathlib import Path as _Path
                _seed_root = memory.root  # type: ignore[attr-defined]
                _seed_json = _seed_root / "seed_research.json"
                _seed_txt = _seed_root / "seed_research.txt"
                if _seed_json.exists():
                    import json as _json
                    seed_research_text = _json.dumps(
                        _json.loads(_seed_json.read_text(encoding="utf-8")),
                        ensure_ascii=False, indent=2,
                    )
                elif _seed_txt.exists():
                    seed_research_text = _seed_txt.read_text(encoding="utf-8")
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.seed_research_read_failed", extra={"err": str(exc)})
                seed_research_text = ""
            if seed_research_text.strip():
                research = seed_research_text[:20_000]
                await on_progress(
                    "Grounding on user-supplied data.",
                    18.0,
                    "search",
                    event="design_decision",
                    decision="seed_research",
                    value={"chars": len(research)},
                    rationale=(
                        "Skipped web search; the deck is generated from the "
                        "JSON payload provided with the import."
                    ),
                )
            elif search_web:
                await on_progress("Researching topic on the web...", 18.0, "search")
                await self._mark_running(task_id, "search", 18.0)
                try:
                    # Phase 6AM-Grounding: when expansion produced
                    # multiple queries, run each through the search
                    # backend in sequence and merge results. Dedupe by
                    # URL. The harvest path's built-in riders still
                    # apply for the FIRST query when min_sources is set.
                    if len(search_queries) > 1:
                        seen_urls: set[str] = set()
                        merged_sources: list[dict[str, Any]] = []
                        summary_parts: list[str] = []
                        for qi, q in enumerate(search_queries):
                            try:
                                if (
                                    qi == 0
                                    and min_sources
                                    and hasattr(self.search, "harvest")
                                ):
                                    sub_research, sub_sources = (
                                        await self.search.harvest(
                                            q,
                                            target_min=min_sources,
                                            max_total=8,
                                        )
                                    )
                                else:
                                    sub_research, sub_sources = (
                                        await self.search.search(q, max_results=4)
                                    )
                            except Exception as exc:
                                logger.warning(
                                    "loop.search_query_failed",
                                    extra={"q": q[:80], "err": str(exc)},
                                )
                                continue
                            if isinstance(sub_research, str) and sub_research.strip():
                                summary_parts.append(sub_research.strip())
                            for s in sub_sources or []:
                                if not isinstance(s, dict):
                                    continue
                                url = str(s.get("url") or "").strip()
                                key = url or str(s)
                                if key in seen_urls:
                                    continue
                                seen_urls.add(key)
                                merged_sources.append(s)
                                if len(merged_sources) >= 12:
                                    break
                            if len(merged_sources) >= 12:
                                break
                        research = "\n\n".join(summary_parts[:3]).strip()
                        search_sources = merged_sources
                    elif min_sources and hasattr(self.search, "harvest"):
                        research, search_sources = await self.search.harvest(
                            topic, target_min=min_sources, max_total=12
                        )
                    else:
                        research, search_sources = await self.search.search(
                            topic, max_results=6
                        )
                    if isinstance(search_sources, list):
                        research_sources = list(search_sources)
                except Exception as exc:
                    logger.warning("loop.search_failed", extra={"err": str(exc)})
                    research = ""
            memory.write_research(research)

            # Emit per-source events so the frontend can show live source cards.
            for src in research_sources[:8]:
                src_title = (src.get("title") or src.get("url") or "Source")[:100]
                src_url = src.get("url") or ""
                await on_progress(src_title, 19.0, "search", event="source_found", url=src_url)

            # Phase 6W: compress very long research before it reaches planner
            # and writer. Source metadata stays intact in ``research_sources``;
            # only the narrative blob is summarized.
            if research:
                research, _stok, _scost = await self._summarize_long_research(
                    topic, research
                )
                total_tokens += _stok
                total_cost += _scost

            # Emit research snippet for live intel panel.
            if research:
                await on_progress(research[:800], 23.5, "search", event="research_note")

            # 2b — STRATEGY (Phase 6V)
            # Build a structured deck-strategy artifact from the topic +
            # harvested research + art-direction. The planner and the
            # batch-generator now read from this artifact instead of just
            # the raw research blob, so different deck types produce
            # different layout orders, story arcs, and visual directions.
            await on_progress("Building deck strategy...", 24.0, "strategy")
            try:
                from agent.art_direction import infer_art_direction
                from agent.deck_strategy import build_deck_strategy

                art = infer_art_direction(topic, theme)
                strategy = build_deck_strategy(
                    topic=topic,
                    slide_count=slide_count,
                    art_direction=art,
                    research=research,
                    research_sources=research_sources,
                )
                memory.write_artifact("strategy.json", strategy.to_dict())
                _deck_type = strategy.deck_type
                _mood = art.mood

                # Narrate design decisions so the user can see the AI's
                # reasoning. These events are surface-only (no schema impact).
                try:
                    await on_progress(
                        f"Deck type: {strategy.deck_type}",
                        24.5, "strategy",
                        event="design_decision",
                        decision="deck_type",
                        value=strategy.deck_type,
                        rationale=(strategy.thesis or "")[:240],
                    )
                    await on_progress(
                        f"Mood: {art.mood}",
                        24.7, "strategy",
                        event="design_decision",
                        decision="mood",
                        value=art.mood,
                        rationale=art.rationale,
                        category=art.category,
                    )
                    if strategy.story_arc:
                        await on_progress(
                            f"Story arc: {' → '.join(strategy.story_arc[:5])}",
                            24.9, "strategy",
                            event="design_decision",
                            decision="story_arc",
                            value=list(strategy.story_arc),
                            rationale=f"{strategy.deck_type} decks pace as: {' → '.join(strategy.story_arc)}",
                        )
                    if strategy.layout_recipe:
                        await on_progress(
                            f"Layout recipe: {', '.join(strategy.layout_recipe[:6])}",
                            25.1, "strategy",
                            event="design_decision",
                            decision="layout_recipe",
                            value=list(strategy.layout_recipe),
                            rationale=f"Tone: {strategy.tone}; visual: {strategy.visual_direction}",
                        )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("loop.design_decision_emit_failed", extra={"err": str(exc)})

                # Phase 6AD: derive narrative beats from the strategy
                # arc + research signals. Pure-Python; never raises.
                try:
                    from agent.narrative_beats import derive_beats
                    _beats = derive_beats(
                        slide_count=slide_count,
                        story_arc=list(strategy.story_arc) if strategy else None,
                        research=research,
                    )
                    if _beats:
                        memory.write_artifact("narrative_beats.json", {"beats": _beats})
                        await on_progress(
                            f"Narrative beats: {' → '.join(_beats[:7])}",
                            25.3, "strategy",
                            event="design_decision",
                            decision="narrative_beats",
                            value=list(_beats),
                            rationale=(
                                "Documentary beat sequence derived from the deck strategy "
                                "and research signals; drives per-slide intent and section "
                                "divider placement."
                            ),
                        )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("loop.narrative_beats_failed", extra={"err": str(exc)})
                    _beats = []
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.strategy_failed", extra={"err": str(exc)})
                strategy = None
            await on_progress(
                "Research strategy ready.",
                26.0,
                "strategy",
            )

            # 2c — NARRATIVE SYNTHESIS (Phase 6AN-Story)
            # Write the deck's prose-first ground truth before we plan
            # slide titles. One LLM call produces a ~500-word editor's
            # brief mapped to the strategy's story arc; both the planner
            # and the writer then consume it so every slide condenses a
            # paragraph of one coherent story instead of being invented
            # in isolation. Degrades to None on kill switch or failure;
            # the legacy outline-only path keeps working.
            narrative = None
            try:
                from agent.narrative_synthesizer import synthesize_narrative
                key_facts: list[str] = []
                audience = ""
                tone = ""
                thesis_hint = ""
                story_arc_list: list[str] = []
                if strategy is not None:
                    key_facts = list(getattr(strategy, "key_facts", []) or [])
                    audience = getattr(strategy, "audience", "") or ""
                    tone = getattr(strategy, "tone", "") or ""
                    thesis_hint = getattr(strategy, "thesis", "") or ""
                    story_arc_list = list(getattr(strategy, "story_arc", []) or [])
                draft, n_tokens, n_cost = await synthesize_narrative(
                    topic=topic,
                    research=research,
                    deck_type=_deck_type,
                    audience=audience,
                    tone=tone,
                    thesis_hint=thesis_hint,
                    story_arc=story_arc_list,
                    key_facts=key_facts,
                    slide_count=slide_count,
                    ai_call=self._ai_call,
                )
                total_tokens += n_tokens
                total_cost += n_cost
                if not draft.is_empty:
                    narrative = draft
                    memory.write_artifact(
                        "narrative.json",
                        {
                            "thesis": draft.thesis,
                            "sections": [
                                {"beat": s.beat, "heading": s.heading, "body": s.body}
                                for s in draft.sections
                            ],
                        },
                    )
                    try:
                        await on_progress(
                            (draft.thesis or "Narrative drafted.")[:240],
                            27.0,
                            "strategy",
                            event="design_decision",
                            decision="narrative",
                            value={
                                "thesis": draft.thesis,
                                "sections": [
                                    {"beat": s.beat, "heading": s.heading}
                                    for s in draft.sections
                                ],
                            },
                            rationale=(
                                "Story-first draft written before the slide "
                                "skeleton. Each slide condenses one section."
                            ),
                        )
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning(
                            "loop.narrative_emit_failed", extra={"err": str(exc)}
                        )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.narrative_failed", extra={"err": str(exc)})
                narrative = None

            # 3 — PLAN
            await on_progress("Planning slide structure...", 28.0, "plan")
            await self._mark_running(task_id, "plan", 28.0)
            outline, p_tokens, p_cost = await self.planner.plan(
                topic, slide_count, research, strategy=strategy, narrative=narrative
            )
            total_tokens += p_tokens
            total_cost += p_cost
            memory.write_outline(outline)
            memory.write_todo(outline)

            # Emit outline so the frontend can show the planned slide structure.
            if outline:
                _outline_titles = [
                    {"i": i + 1, "layout": p.get("layout", ""), "title": p.get("title", "")}
                    for i, p in enumerate(outline)
                ]
                await on_progress(
                    "Slide structure planned",
                    29.0,
                    "plan",
                    event="outline_ready",
                    outline=_outline_titles,
                )

            # 4 — GENERATE
            slides: list[dict[str, Any]] = []
            try:
                slides, g_tokens, g_cost = await self._generate_all_at_once(
                    topic, slide_count, research, outline, on_progress, memory,
                    strategy=strategy,
                    deck_type=_deck_type,
                    mood=_mood,
                    narrative=narrative,
                )
                total_tokens += g_tokens
                total_cost += g_cost
            except Exception as exc:
                logger.warning(
                    "loop.batch_generate_failed_falling_back", extra={"err": str(exc)}
                )
                slides = []

            if not slides:
                slides, g_tokens, g_cost = await self._generate_per_slide(
                    topic, research, outline, on_progress, memory,
                    deck_type=_deck_type,
                    mood=_mood,
                )
                total_tokens += g_tokens
                total_cost += g_cost

            # 5 — ASSEMBLE
            await on_progress("Finalizing presentation...", 90.0, "assemble")
            await self._mark_running(task_id, "assemble", 90.0)
            slides = self._normalize_slides(slides, slide_count, topic)

            # Phase 4: attach research sources to source-bearing layouts.
            # Advisory only — never invents sources, never fails generation.
            try:
                from agent.source_grounding import attach_research_sources_to_deck
                slides = attach_research_sources_to_deck(slides, research_sources)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.attach_sources_failed", extra={"err": str(exc)})

            # Phase 6AB: attach per-slide intent metadata. Pure function;
            # never invents content; renderer ignores it if unrecognised.
            try:
                from agent.slide_intent import attach_slide_intent
                slides = attach_slide_intent(
                    slides,
                    story_arc=list(strategy.story_arc) if strategy else None,
                    strategy_tone=strategy.tone if strategy else None,
                    art_mood=_mood,
                    beats=_beats if _beats else None,
                )
                # Surface the per-slide intent rhythm in the AI-reasoning
                # panel so the user can see the narrative pacing decision.
                try:
                    rhythm = [
                        {
                            "i": i + 1,
                            "role": (s.get("intent") or {}).get("narrative_role"),
                            "density": (s.get("intent") or {}).get("density"),
                        }
                        for i, s in enumerate(slides)
                        if isinstance(s, dict)
                    ]
                    if rhythm:
                        await on_progress(
                            f"Pacing: {' · '.join(r['role'] or '?' for r in rhythm[:8])}",
                            91.0, "assemble",
                            event="design_decision",
                            decision="intent_rhythm",
                            value=rhythm,
                            rationale=f"Per-slide narrative role and density across {len(rhythm)} slides.",
                        )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("loop.intent_rhythm_emit_failed", extra={"err": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.attach_intent_failed", extra={"err": str(exc)})

            # Phase 6AA: deterministic layout upgrader. Uses the intent
            # metadata attached above plus the slide's own content shape
            # to promote stats→bigstat / bullets→section_divider when
            # the upgrade is unambiguous. Never replaces planner choices
            # otherwise. Re-normalises so the new layouts pick up their
            # canonical field shape, then re-attaches intent so the
            # rhythm event reflects the upgrades.
            try:
                from agent.layout_recommender import (
                    recommend_layouts,
                    enforce_hero,
                    insert_section_dividers,
                )
                slides, _layout_upgrades = recommend_layouts(slides)
                # Phase 6AI-B1 — guarantee at least one hero moment.
                _slides_after_hero, _hero_upgrades = enforce_hero(slides)
                if _hero_upgrades:
                    slides = _slides_after_hero
                    _layout_upgrades = list(_layout_upgrades) + list(_hero_upgrades)
                # Phase 6AI-B6 — chapter break for long decks.
                _slides_after_div, _div_upgrades = insert_section_dividers(slides)
                if _div_upgrades:
                    slides = _slides_after_div
                    _layout_upgrades = list(_layout_upgrades) + list(_div_upgrades)
                if _layout_upgrades:
                    slides = self._normalize_slides(slides, slide_count, topic)
                    try:
                        from agent.slide_intent import attach_slide_intent
                        slides = attach_slide_intent(
                            slides,
                            story_arc=list(strategy.story_arc) if strategy else None,
                            strategy_tone=strategy.tone if strategy else None,
                            art_mood=_mood,
                        )
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning("loop.attach_intent_failed", extra={"err": str(exc)})
                    # One design_decision per upgrade so the AI-reasoning
                    # panel shows the audit trail.
                    for u in _layout_upgrades:
                        try:
                            await on_progress(
                                f"Slide {u['slide_index']}: {u['from']} → {u['to']}",
                                91.5, "assemble",
                                event="design_decision",
                                decision="layout_upgrade",
                                value=u,
                                rationale=u.get("reason") or "",
                            )
                        except Exception as exc:  # pragma: no cover - defensive
                            logger.warning(
                                "loop.layout_upgrade_emit_failed",
                                extra={"err": str(exc)},
                            )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.layout_recommender_failed", extra={"err": str(exc)})

            # 5b — CRITIC (rewrite weak slides for Manus-level specificity)
            try:
                slides, c_tokens, c_cost = await self._critique_and_rewrite(
                    topic, research, slides, on_progress
                )
                total_tokens += c_tokens
                total_cost += c_cost
                slides = self._normalize_slides(slides, slide_count, topic)
                # Re-attach: critic may have rewritten chart/stats slides.
                try:
                    from agent.source_grounding import attach_research_sources_to_deck
                    slides = attach_research_sources_to_deck(slides, research_sources)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("loop.attach_sources_failed", extra={"err": str(exc)})
                # Re-attach intent — critic may have changed layout / density.
                try:
                    from agent.slide_intent import attach_slide_intent
                    slides = attach_slide_intent(
                        slides,
                        story_arc=list(strategy.story_arc) if strategy else None,
                        strategy_tone=strategy.tone if strategy else None,
                        art_mood=_mood,
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("loop.attach_intent_failed", extra={"err": str(exc)})
            except Exception as exc:
                logger.warning("loop.critic_failed", extra={"err": str(exc)})

            # 5c — IMAGES (hero visual per slide via Pollinations)
            try:
                slides, i_tokens, i_cost = await self._add_hero_images(
                    topic, slides, on_progress
                )
                total_tokens += i_tokens
                total_cost += i_cost
            except Exception as exc:
                logger.warning("loop.images_failed", extra={"err": str(exc)})

            # 6 — SAVE
            await on_progress("Saving your slides...", 96.0, "save")
            # Phase 6U: final pass that fills layout-local defaults
            # (title.subtitle/eyebrow, closing.subtitle/cta, chart.subtitle,
            # quote.attribution, chart_data.unit/source) so the deck
            # satisfies ``validate_deck`` before persisting. The leading
            # cause of the 6T ``deck_quality_ok=1/11`` regression was the
            # safety-net inside ``_normalize_slides`` that pins
            # ``out[0].layout='title'`` and ``out[-1].layout='closing'``
            # without seeding the required fields for those layouts. The
            # repair pass closes that gap without inventing content.
            try:
                slides = repair_for_validator(slides)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.deck_repair_failed", extra={"err": str(exc)})

            # Phase 6AJ: deterministic editorial polish.
            # Strengthens titles, drops hedging openers / generic phrases
            # in bullets, and adds short narrative transitions where
            # consecutive slides have an ``intent.narrative_role``.
            # Pure / offline / additive — never raises, never removes
            # numbers, years, or proper nouns. Runs after repair so the
            # rewritten copy still satisfies the validator contract.
            try:
                from agent.editorial_pass import apply_editorial_pass
                slides, editorial_summary = apply_editorial_pass(slides)
                try:
                    await on_progress(
                        f"Edited {editorial_summary.get('headline_rewrites', 0)} titles, "
                        f"{editorial_summary.get('bullet_rewrites', 0)} bullets; "
                        f"added {editorial_summary.get('transitions_added', 0)} transitions.",
                        96.5,
                        "save",
                        event="editorial_pass",
                        editorial_summary=editorial_summary,
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("loop.editorial_event_failed", extra={"err": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.editorial_pass_failed", extra={"err": str(exc)})

            # Phase 6AL-Voice: deterministic editorial-voice pass.
            # Rewrites category-label headlines ("Problem Statement",
            # "Traction Metrics", "Investment Ask") into authored
            # sentences derived from existing slide content, drops
            # filler subtitles ("A Fundable Story", "Join Our Mission"),
            # scrubs debug-grade transitions ("Setting the stage:",
            # "What the data shows:"), and rewrites button-shaped
            # closings into declarative titles. Pure / offline /
            # deterministic / additive — no LLM, no network, never
            # raises, exporter-safe. Kill-switch:
            # NEXUS_DISABLE_VOICE_PASS=true.
            try:
                from agent.voice_pass import apply_voice_pass
                slides, voice_summary = apply_voice_pass(slides)
                if (
                    voice_summary.get("headline_rewrites", 0)
                    + voice_summary.get("subtitle_kills", 0)
                    + voice_summary.get("transition_scrubs", 0)
                    + voice_summary.get("closing_rewrites", 0)
                    > 0
                ):
                    try:
                        await on_progress(
                            f"Voice pass: "
                            f"{voice_summary.get('headline_rewrites', 0)} headline(s), "
                            f"{voice_summary.get('subtitle_kills', 0)} filler subtitle(s), "
                            f"{voice_summary.get('transition_scrubs', 0)} transition(s), "
                            f"{voice_summary.get('closing_rewrites', 0)} closing(s) rewritten.",
                            96.6,
                            "save",
                            event="design_decision",
                            decision="voice_pass",
                            value=voice_summary,
                            rationale="Replaced category-label headlines and filler copy with authored deck voice.",
                        )
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning("loop.voice_event_failed", extra={"err": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.voice_pass_failed", extra={"err": str(exc)})

            # Phase 6AK: mark cinematic hero moments. Writes is_hero=True
            # on the first bigstat / section_divider / attributed quote
            # so the renderer can promote them into full-bleed cinematic
            # variants. Pure / offline / additive — renderer-only flag,
            # ignored by exporters.
            try:
                from agent.cinematic_marker import mark_hero_moments
                slides, hero_summary = mark_hero_moments(slides)
                if hero_summary.get("total", 0) > 0:
                    try:
                        await on_progress(
                            f"Marked {hero_summary.get('total', 0)} cinematic moment(s).",
                            96.8,
                            "save",
                            event="design_decision",
                            decision="cinematic_hero",
                            value=hero_summary,
                            rationale="Promoted hero slides for full-bleed cinematic rendering.",
                        )
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning("loop.cinematic_event_failed", extra={"err": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.cinematic_marker_failed", extra={"err": str(exc)})

            # Phase 6AF: deterministic claim-level citation attach.
            # Runs after repair so citations target the final, validator-
            # accepted slides. Pure / offline / additive — never raises,
            # never mutates ``sources``, and only writes ``slide["citations"]``.
            try:
                from agent.citation_attach import attach_citations_to_deck
                slides, citation_summary = attach_citations_to_deck(slides)
                try:
                    await on_progress(
                        f"Cited {citation_summary.get('supported', 0)}/"
                        f"{citation_summary.get('total_claims', 0)} claims "
                        f"across {citation_summary.get('slides_with_citations', 0)} slides.",
                        97.0,
                        "save",
                        event="citation_checked",
                        citation_summary=citation_summary,
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("loop.citation_event_failed", extra={"err": str(exc)})
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("loop.citation_attach_failed", extra={"err": str(exc)})

            await self._save_deck(task_id, slides, theme, total_tokens, total_cost, model_used)

            await on_progress("Done! Your slides are ready.", 100.0, "done", status="done")
            return {"slides": slides, "tokens": total_tokens, "cost_usd": total_cost}

        except JobCancelled as exc:
            # Phase 6Q: graceful cancel. Worker top-level finalizes the
            # row via ``lifecycle_service.mark_cancelled`` and the SSE
            # stream closes once the ``cancelled`` event is published.
            logger.info(
                "loop.cancelled",
                extra={"task_id": task_id, "stage": str(exc) or "unknown"},
            )
            await on_progress(
                "Generation cancelled by user.",
                100.0,
                "cancelled",
                status="cancelled",
            )
            raise
        except Exception as exc:
            logger.exception("loop.failed", extra={"task_id": task_id})
            await self._mark_failed(task_id, str(exc))
            await on_progress(f"Generation failed: {exc}", 100.0, "failed", status="failed", error=str(exc))
            raise

    # ── generation strategies ─────────────────────────────────────────────
    async def _generate_all_at_once(
        self,
        topic: str,
        slide_count: int,
        research: str,
        outline: list[dict[str, Any]],
        on_progress: ProgressCallback,
        memory: AgentMemory,
        *,
        strategy: Any | None = None,
        deck_type: str = "overview",
        mood: str = "neutral",
        narrative: Any | None = None,
    ) -> tuple[list[dict[str, Any]], int, float]:
        await on_progress(f"Writing slides 1 of {slide_count}...", 35.0, "generate")
        outline_text = "\n".join(
            f"{i + 1}. ({p['layout']}) {p['title']} — {p['intent']}"
            for i, p in enumerate(outline)
        )
        user_msg = slides_user_message(
            topic, slide_count, research, outline_text,
            strategy=strategy, narrative=narrative,
        )
        text, tokens, cost = await self._ai_call(
            role="writer",
            system=nexus_system_prompt(deck_type, mood),
            user=user_msg,
            max_tokens=8096,
        )
        slides = self._parse_slides_array(text)
        if not slides:
            # Phase 6W: try a single json_fix repair before giving up.
            repaired, rtok, rcost = await self._json_fix_retry(text, expected="array")
            tokens += rtok
            cost += rcost
            if repaired and repaired != text:
                slides = self._parse_slides_array(repaired)
        if not slides:
            return [], tokens, cost
        for i, slide in enumerate(slides[:slide_count]):
            memory.write_slide(i, slide)
            memory.mark_todo_done(i)
            pct = 35.0 + (i + 1) * (50.0 / slide_count)
            await on_progress(
                f"Writing slide {i + 1} of {slide_count}...",
                min(pct, 85.0),
                "generate",
                event="slide",
                slide_index=i,
                slide_total=slide_count,
                slide=slide,
            )
        return slides[:slide_count], tokens, cost

    async def _generate_per_slide(
        self,
        topic: str,
        research: str,
        outline: list[dict[str, Any]],
        on_progress: ProgressCallback,
        memory: AgentMemory,
        *,
        deck_type: str = "overview",
        mood: str = "neutral",
    ) -> tuple[list[dict[str, Any]], int, float]:
        from agent.prompts import single_slide_user_message

        slides: list[dict[str, Any]] = []
        total_tokens = 0
        total_cost = 0.0
        n = len(outline)
        # OpenManus-style stuck detection: track raw responses to avoid the
        # LLM repeating identical bad output across attempts.
        seen_responses: set[str] = set()
        MAX_ATTEMPTS = 2

        for i, plan in enumerate(outline):
            pct = 35.0 + (i + 1) * (50.0 / max(n, 1))
            await on_progress(
                f"Writing slide {i + 1} of {n}...", min(pct, 85.0), "generate"
            )
            base_user = single_slide_user_message(topic, research, plan, i, n)
            slide = None
            for attempt in range(MAX_ATTEMPTS):
                # Perturb prompt + temperature on retry to break repeat loops.
                user_msg = base_user
                temp = 0.7
                if attempt > 0:
                    user_msg = (
                        base_user
                        + "\n\nThe previous attempt produced unusable output. "
                        "Try a different angle, use specific numbers, and return ONLY valid JSON."
                    )
                    temp = 0.95
                try:
                    text, tokens, cost = await self._ai_call(
                        role="writer",
                        system=nexus_system_prompt(deck_type, mood),
                        user=user_msg,
                        max_tokens=2048,
                        temperature=temp,
                    )
                    total_tokens += tokens
                    total_cost += cost
                    fingerprint = (text or "").strip()[:200]
                    if fingerprint and fingerprint in seen_responses:
                        logger.info(
                            "loop.stuck_detected_retrying", extra={"i": i, "attempt": attempt}
                        )
                        continue
                    if fingerprint:
                        seen_responses.add(fingerprint)
                    slide = self._parse_single_slide(text)
                    if slide is not None:
                        break
                    # Phase 6W: one json_fix retry before next attempt/fallback.
                    repaired, rtok, rcost = await self._json_fix_retry(
                        text, expected="object"
                    )
                    total_tokens += rtok
                    total_cost += rcost
                    if repaired and repaired != text:
                        slide = self._parse_single_slide(repaired)
                        if slide is not None:
                            break
                except Exception as exc:
                    logger.warning(
                        "loop.single_slide_failed",
                        extra={"i": i, "attempt": attempt, "err": str(exc)},
                    )
            if slide is None:
                slide = self._fallback_slide(plan, i, n, topic)
            if slide is None:
                slide = self._fallback_slide(plan, i, n, topic)
            slides.append(slide)
            memory.write_slide(i, slide)
            memory.mark_todo_done(i)
            await on_progress(
                f"Wrote slide {i + 1} of {n}.",
                min(35.0 + (i + 1) * (50.0 / max(n, 1)), 85.0),
                "generate",
                event="slide",
                slide_index=i,
                slide_total=n,
                slide=slide,
            )
        return slides, total_tokens, total_cost

    # ── critic pass ───────────────────────────────────────────────────────
    _BLAND_PHRASES = (
        "enhanced productivity",
        "improved efficiency",
        "improved decision",
        "data-driven insight",
        "personalized customer",
        "increased accuracy",
        "leverage synergies",
        "streamline operations",
        "key insight",
        "drive value",
        "cutting-edge",
        "state-of-the-art",
        "next-generation",
        "innovative solution",
        "seamless integration",
        "unlock potential",
        "transform industries",
        "revolutionize",
    )

    @classmethod
    def _is_weak(cls, slide: dict[str, Any]) -> bool:
        """Heuristic: bland phrases or no concrete data → needs critic rewrite."""
        layout = slide.get("layout")
        if layout in ("title", "closing"):
            return False  # Don't waste tokens rewriting titles/closings.

        # Collect all visible text from the slide.
        chunks: list[str] = [str(slide.get("title") or "")]
        if layout == "bullets":
            chunks.extend(str(b) for b in (slide.get("bullets") or []))
        elif layout == "two-col":
            for c in slide.get("columns") or []:
                if isinstance(c, dict):
                    chunks.append(str(c.get("heading") or ""))
                    chunks.append(str(c.get("body") or ""))
        elif layout == "stats":
            for s in slide.get("stats") or []:
                if isinstance(s, dict):
                    chunks.append(str(s.get("value") or ""))
                    chunks.append(str(s.get("label") or ""))
        elif layout == "quote":
            chunks.append(str(slide.get("quote") or ""))
            chunks.append(str(slide.get("attribution") or ""))

        text = " ".join(chunks).lower()
        if not text.strip():
            return True

        # Bland phrase detection.
        for phrase in cls._BLAND_PHRASES:
            if phrase in text:
                return True

        # Stats slide must have real numeric values.
        if layout == "stats":
            for s in slide.get("stats") or []:
                val = str(s.get("value") if isinstance(s, dict) else "")
                if not re.search(r"\d", val):
                    return True

        # Bullets/two-col: weak if NO bullet/body has any digit, year, or proper noun.
        if layout in ("bullets", "two-col"):
            joined = " ".join(chunks[1:])  # exclude title
            has_signal = bool(
                re.search(r"\d", joined)
                or re.search(r"\b(19|20)\d{2}\b", joined)  # year
                or re.search(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+", joined)  # proper noun pair
            )
            if not has_signal:
                return True

        return False

    async def _critique_and_rewrite(
        self,
        topic: str,
        research: str,
        slides: list[dict[str, Any]],
        on_progress: ProgressCallback,
    ) -> tuple[list[dict[str, Any]], int, float]:
        """For each weak slide, ask the LLM to rewrite it with specifics."""
        weak_indices = [i for i, s in enumerate(slides) if self._is_weak(s)]
        if not weak_indices:
            logger.info("critic.all_strong", extra={"n": len(slides)})
            return slides, 0, 0.0

        await on_progress(
            f"Refining {len(weak_indices)} slide(s)...", 92.0, "critique"
        )
        logger.info(
            "critic.rewriting", extra={"weak": weak_indices, "total": len(slides)}
        )

        total_tokens = 0
        total_cost = 0.0
        out = list(slides)

        async def _rewrite_one(idx: int) -> None:
            nonlocal total_tokens, total_cost
            original = out[idx]
            try:
                text, tokens, cost = await self._ai_call(
                    role="critic",
                    system=CRITIC_SYSTEM_PROMPT,
                    user=critic_user_message(topic, research, original),
                    max_tokens=1024,
                )
                total_tokens += tokens
                total_cost += cost
                rewritten = self._parse_single_slide(text)
                if rewritten and rewritten.get("layout") == original.get("layout"):
                    rewritten["id"] = original.get("id")
                    out[idx] = rewritten
                    # Push the refined slide to the live preview.
                    try:
                        await on_progress(
                            f"Refined slide {idx + 1}.",
                            93.0,
                            "critique",
                            event="slide",
                            slide_index=idx,
                            slide_total=len(out),
                            slide=rewritten,
                        )
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning(
                    "critic.rewrite_failed", extra={"i": idx, "err": str(exc)}
                )

        # Rewrite up to 4 slides in parallel to keep total time reasonable.
        sem = asyncio.Semaphore(4)

        async def _bound(idx: int) -> None:
            async with sem:
                await _rewrite_one(idx)

        await asyncio.gather(*(_bound(i) for i in weak_indices))
        return out, total_tokens, total_cost

    # ── hero images ────────────────────────────────────────────────────────
    # Phase 6AL-Visuals: image placement inversion.
    # Image-bearing layouts now include the hero moments (quote, bigstat,
    # section_divider). Stats / chart / table / comparison / timeline stay
    # image-free because they're data-dense. The renderer is responsible
    # for full-bleed vs right-panel composition; this method only attaches.
    _IMAGE_LAYOUTS = {
        "title", "bullets", "two-col", "closing",
        "quote", "bigstat", "section_divider",
    }

    # Phase 6AL-Visuals: banned vocabulary that turns Pollinations into a
    # stock-photo machine. We rewrite anything matching one of these words
    # out of LLM-generated prompts before sending them downstream.
    _IMAGE_BANNED_WORDS = (
        "calming", "serene", "peaceful", "tranquil",
        "growing", "vibrant", "modern", "professional", "corporate",
        "beautiful", "stunning", "amazing", "perfect", "wonderful",
        "abstract", "minimal", "minimalist", "clean", "simple",
        "background", "wallpaper", "stock", "generic",
        "businessman", "businesswoman", "team meeting", "handshake",
        "lightbulb", "rocket", "graph going up", "thumbs up",
    )

    # Phase 6AL-Visuals: deterministic cinematic suffix appended to every
    # image prompt. Forces editorial / documentary photography feel and
    # blocks Pollinations' default "AI slop" aesthetic. Kept additive so
    # weak LLM output still produces atmospheric imagery.
    _IMAGE_CINEMATIC_SUFFIX = (
        "shot on 35mm film, shallow depth of field, golden hour lighting, "
        "editorial photography, atmospheric, cinematic composition, "
        "muted color grading, no text, no logos, no watermarks"
    )

    @classmethod
    def _scrub_image_prompt(cls, raw: str) -> str:
        """Strip banned vocabulary; collapse whitespace. Never returns empty."""
        cleaned = (raw or "").strip()
        if not cleaned:
            return ""
        lowered = cleaned.lower()
        for word in cls._IMAGE_BANNED_WORDS:
            if word in lowered:
                # Word-boundary replacement so "abstract" doesn't nuke
                # "extraction"; case-insensitive.
                cleaned = re.sub(
                    rf"\b{re.escape(word)}\b", "", cleaned, flags=re.IGNORECASE
                )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
        return cleaned

    @classmethod
    def _direct_image_prompt(cls, subject: str) -> str:
        """Compose subject + cinematic suffix into the final Pollinations brief."""
        subj = cls._scrub_image_prompt(subject)
        if not subj:
            subj = "documentary scene"
        return f"{subj}, {cls._IMAGE_CINEMATIC_SUFFIX}"

    async def _add_hero_images(
        self,
        topic: str,
        slides: list[dict[str, Any]],
        on_progress: ProgressCallback,
    ) -> tuple[list[dict[str, Any]], int, float]:
        """Attach a Pollinations image URL to slides that benefit from a visual."""
        from services.image_service import pollinations_url

        target_indices = [
            i for i, s in enumerate(slides) if s.get("layout") in self._IMAGE_LAYOUTS
        ]
        if not target_indices:
            return slides, 0, 0.0

        await on_progress("Generating slide imagery...", 94.0, "images")

        # ONE LLM call to generate cinematic visual subjects for every
        # target slide. The model is asked for SUBJECT + LIGHTING + LENS
        # + MOOD — never style adjectives. We append the editorial suffix
        # deterministically so the final prompt is always cinematic even
        # if the LLM output is weak.
        prompts: list[str] = []
        tokens = 0
        cost = 0.0
        try:
            indexed = "\n".join(
                f"{i + 1}. layout={slides[i].get('layout')} title={slides[i].get('title','')}"
                for i in target_indices
            )
            user = (
                f"Topic: {topic}\n\n"
                f"Slides needing a cinematic image:\n{indexed}\n\n"
                f"You are an art director briefing a documentary photographer.\n"
                f"For EACH slide, write ONE concrete visual brief (max 22 words) "
                f"specifying a SUBJECT, a LIGHTING condition, and a CAMERA framing.\n\n"
                f"Examples of GOOD briefs:\n"
                f"- 'rain-slicked harbor at dawn, fishermen pulling nets, long lens, side light'\n"
                f"- 'half-empty warehouse with single forklift, fluorescent overhead, wide angle, deep shadow'\n"
                f"- 'analyst's desk at night, blue monitor glow on face, 50mm portrait, shallow focus'\n\n"
                f"DO NOT use words like: calming, serene, vibrant, modern, professional, "
                f"abstract, beautiful, stunning, background. No stock-photo cliches "
                f"(handshakes, lightbulbs, arrows pointing up, team meetings).\n"
                f"DO use specific subjects, real places, named lighting, real lens choices.\n\n"
                f"Return ONLY a JSON array of strings in slide order. No prose."
            )
            text, tokens, cost = await self._ai_call(
                role="vision",
                system=(
                    "You are an art director writing cinematic image briefs. "
                    "You return only a JSON array of strings, each describing "
                    "a concrete subject, lighting, and lens."
                ),
                user=user,
                max_tokens=700,
                temperature=0.5,
            )
            cleaned = self._strip_fences(text)
            match = re.search(r"\[[\s\S]*\]", cleaned)
            if match:
                cleaned = match.group(0)
            data = json.loads(cleaned)
            if isinstance(data, list):
                prompts = [str(p) for p in data]
        except Exception as exc:
            logger.warning("images.prompt_gen_failed", extra={"err": str(exc)})
            prompts = []

        # Fallback: if the LLM failed or under-delivered, synthesize a
        # subject from the slide title. The cinematic suffix is appended
        # by _direct_image_prompt regardless of source.
        if len(prompts) < len(target_indices):
            for i in target_indices[len(prompts):]:
                t = slides[i].get("title") or topic
                prompts.append(f"documentary scene illustrating {t}, low key lighting, 35mm")

        for slot, idx in enumerate(target_indices):
            raw = prompts[slot] if slot < len(prompts) else topic
            final_prompt = self._direct_image_prompt(raw)
            slides[idx]["image_url"] = pollinations_url(final_prompt, seed=idx + 1)
            slides[idx]["image_prompt"] = final_prompt

        logger.info(
            "images.attached", extra={"count": len(target_indices), "total": len(slides)}
        )
        return slides, tokens, cost


    @staticmethod
    def _strip_fences(text: str) -> str:
        cleaned = (text or "").strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    @classmethod
    def _parse_slides_array(cls, text: str) -> list[dict[str, Any]]:
        cleaned = cls._strip_fences(text)
        match = re.search(r"\[\s*[\s\S]*\]", cleaned)
        if match:
            cleaned = match.group(0)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return [s for s in data if isinstance(s, dict)]

    @classmethod
    def _parse_single_slide(cls, text: str) -> dict[str, Any] | None:
        cleaned = cls._strip_fences(text)
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            cleaned = match.group(0)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    @classmethod
    def _normalize_slides(
        cls, slides: list[dict[str, Any]], slide_count: int, topic: str
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, raw in enumerate(slides):
            # Resolve via the canonical registry so aliases (when added)
            # and unknown values both go through one path.
            layout = normalize_layout(raw.get("layout"))
            if layout not in _VALID_LAYOUTS:
                layout = FALLBACK_LAYOUT
            base = {
                "id": f"slide-{i:03d}",
                "layout": layout,
                "title": str(raw.get("title") or "").strip(),
            }
            if layout == "title":
                base.update(
                    {
                        "subtitle": str(raw.get("subtitle") or "").strip(),
                        "eyebrow": str(raw.get("eyebrow") or "Presentation").strip(),
                    }
                )
            elif layout == "bullets":
                bullets = raw.get("bullets") or []
                if not isinstance(bullets, list):
                    bullets = []
                base["bullets"] = [str(b).strip() for b in bullets if str(b).strip()][:4]
            elif layout == "two-col":
                cols = raw.get("columns") or []
                if not isinstance(cols, list):
                    cols = []
                base["columns"] = [
                    {
                        "heading": str(c.get("heading") or "").strip(),
                        "body": str(c.get("body") or "").strip(),
                    }
                    for c in cols[:2]
                    if isinstance(c, dict)
                ]
            elif layout == "quote":
                base["quote"] = str(raw.get("quote") or raw.get("title") or "").strip()
                base["attribution"] = str(raw.get("attribution") or "").strip()
            elif layout == "stats":
                stats = raw.get("stats") or []
                if not isinstance(stats, list):
                    stats = []
                base["stats"] = [
                    {
                        "value": str(s.get("value") or "").strip(),
                        "label": str(s.get("label") or "").strip(),
                    }
                    for s in stats[:3]
                    if isinstance(s, dict)
                ]
            elif layout == "chart":
                cd = raw.get("chart_data") or {}
                if not isinstance(cd, dict):
                    cd = {}
                labels = cd.get("labels") or []
                values = cd.get("values") or []
                if not isinstance(labels, list):
                    labels = []
                if not isinstance(values, list):
                    values = []
                # Coerce values to numbers; pair length to labels.
                numeric: list[float] = []
                for v in values:
                    try:
                        numeric.append(float(str(v).replace(",", "").replace("$", "")))
                    except (TypeError, ValueError):
                        numeric.append(0.0)
                pairs = min(len(labels), len(numeric))
                base["chart_type"] = (
                    str(raw.get("chart_type") or "bar").strip().lower() or "bar"
                )
                if base["chart_type"] not in {"bar", "line", "doughnut"}:
                    base["chart_type"] = "bar"
                base["chart_data"] = {
                    "labels": [str(x).strip() for x in labels[:pairs]],
                    "values": numeric[:pairs],
                    "unit": str(cd.get("unit") or "").strip(),
                    "source": str(cd.get("source") or "").strip(),
                }
                base["subtitle"] = str(raw.get("subtitle") or "").strip()
            elif layout == "closing":
                base["subtitle"] = str(raw.get("subtitle") or "").strip()
                base["cta"] = str(raw.get("cta") or "Thank you").strip()
            elif layout == "bigstat":
                # Phase 6AA — preserve value / label / subtitle. If the
                # source slide carries a stats[] array (because the
                # recommender upgraded it), fall back to its first stat.
                stats_first = None
                stats = raw.get("stats")
                if isinstance(stats, list) and stats and isinstance(stats[0], dict):
                    stats_first = stats[0]
                base["value"] = str(
                    raw.get("value")
                    or (stats_first.get("value") if stats_first else "")
                    or ""
                ).strip()
                base["label"] = str(
                    raw.get("label")
                    or (stats_first.get("label") if stats_first else "")
                    or ""
                ).strip()
                base["subtitle"] = str(raw.get("subtitle") or "").strip()
            elif layout == "section_divider":
                # Phase 6AA — typography-only block. Eyebrow/subtitle
                # default to empty so the validator accepts the slide.
                base["eyebrow"] = str(raw.get("eyebrow") or "").strip()
                base["subtitle"] = str(raw.get("subtitle") or "").strip()
            elif layout == "timeline":
                # Phase 6AC — chronology of dated events. Up to 6 events
                # are kept; each event is sanitized into {date, label}.
                events = raw.get("events") or []
                if not isinstance(events, list):
                    events = []
                base["events"] = [
                    {
                        "date": str(e.get("date") or "").strip(),
                        "label": str(e.get("label") or "").strip(),
                    }
                    for e in events[:6]
                    if isinstance(e, dict)
                ]
                base["subtitle"] = str(raw.get("subtitle") or "").strip()
            elif layout == "comparison":
                # Phase 6AC — side-by-side comparison. Both sides are
                # sanitized; missing sides default to empty heading/body
                # so the deck-repair pass + validator surface the gap.
                left = raw.get("left") or {}
                right = raw.get("right") or {}
                if not isinstance(left, dict):
                    left = {}
                if not isinstance(right, dict):
                    right = {}
                base["left"] = {
                    "heading": str(left.get("heading") or "").strip(),
                    "body": str(left.get("body") or "").strip(),
                }
                base["right"] = {
                    "heading": str(right.get("heading") or "").strip(),
                    "body": str(right.get("body") or "").strip(),
                }
                base["subtitle"] = str(raw.get("subtitle") or "").strip()
            out.append(base)

        # pad / trim to slide_count
        while len(out) < slide_count:
            out.append(
                cls._fallback_slide(
                    {"layout": "bullets", "title": f"Section {len(out) + 1}", "intent": ""},
                    len(out),
                    slide_count,
                    topic,
                )
            )
        out = out[:slide_count]
        if out:
            out[0]["layout"] = "title"
            out[-1]["layout"] = "closing"

        # Safety net: ensure at least ONE chart slide. If the model produced
        # none, convert a stats slide (numeric values present) into a chart.
        has_chart = any(s.get("layout") == "chart" for s in out)
        if not has_chart:
            for s in out[1:-1]:
                if s.get("layout") != "stats":
                    continue
                stats = s.get("stats") or []
                labels: list[str] = []
                values: list[float] = []
                for item in stats:
                    raw_v = str(item.get("value", ""))
                    cleaned = raw_v.replace("$", "").replace(",", "").replace("%", "").strip()
                    # take leading numeric portion
                    num = ""
                    for ch in cleaned:
                        if ch.isdigit() or ch in {".", "-"}:
                            num += ch
                        else:
                            break
                    try:
                        v = float(num)
                    except ValueError:
                        continue
                    labels.append(str(item.get("label", "")).strip()[:24] or f"Item {len(values) + 1}")
                    values.append(v)
                if len(values) >= 2:
                    s["layout"] = "chart"
                    s["chart_type"] = "bar"
                    s["chart_data"] = {
                        "labels": labels,
                        "values": values,
                        "unit": "",
                        "source": s.get("source", ""),
                    }
                    # P1-2: chart slides require a slide-level ``subtitle``
                    # per the tightened schema. The safety-net previously
                    # produced chart slides without it, generating a
                    # self-inflicted validation warning on every deck. Carry
                    # forward whatever the source stats slide had, default "".
                    s["subtitle"] = s.get("subtitle", "")
                    s.pop("stats", None)
                    break

        # Phase 1C: non-repairing deck-quality telemetry. Build a
        # structured ``DeckQualityReport`` from the normalized deck and
        # log per-slide failures + a deck-level summary. We do NOT
        # mutate ``out`` and we do NOT reject slides — this is
        # observability only until a repair pipeline lands later.
        try:
            from agent.deck_quality import build_deck_quality_report  # local import to avoid app/db cycles

            report = build_deck_quality_report(out)
            for record in report.errors:
                logger.warning(
                    "loop.slide_validation_failed slide=%d layout=%s path=%s code=%s message=%s",
                    record["slide_index"],
                    record["layout"],
                    record["path"],
                    record["code"],
                    record["message"],
                )
            logger.info(
                "loop.deck_quality_report ok=%s slide_count=%d valid=%d invalid=%d repairs_needed=%d",
                report.ok,
                report.slide_count,
                report.valid_count,
                report.invalid_count,
                len(report.repair_actions),
            )
        except Exception as exc:  # pragma: no cover — telemetry must never break generation
            logger.warning("loop.slide_validation_telemetry_failed err=%s", exc)

        return out

    @staticmethod
    def _fallback_slide(plan: dict, index: int, total: int, topic: str) -> dict[str, Any]:
        layout = plan.get("layout", "bullets")
        title = plan.get("title") or f"Slide {index + 1}"
        if layout == "title":
            return {"id": f"slide-{index:03d}", "layout": "title", "title": topic, "subtitle": title, "eyebrow": "Presentation"}
        if layout == "closing":
            return {"id": f"slide-{index:03d}", "layout": "closing", "title": title, "subtitle": "", "cta": "Thank you"}
        return {
            "id": f"slide-{index:03d}",
            "layout": "bullets",
            "title": title,
            "bullets": [
                "Key insight one.",
                "Key insight two.",
                "Key insight three.",
            ],
        }

    # ── DB writes ─────────────────────────────────────────────────────────
    async def _mark_running(self, task_id: str, step: str, pct: float) -> None:
        async with SessionLocal() as session:
            res = await session.execute(select(Task).where(Task.id == task_id))
            task = res.scalar_one_or_none()
            if task is None:
                return
            # Phase 6Q: cancel checkpoint. The lifecycle endpoint flips
            # ``Task.status`` to ``cancelling``; the loop honours it at
            # every stage transition and exits via :class:`JobCancelled`.
            if task.status == "cancelling":
                raise JobCancelled(step)
            task.status = "running"
            task.current_step = step
            task.progress_pct = pct
            session.add(task)
            await session.commit()

    async def _mark_failed(self, task_id: str, err: str) -> None:
        async with SessionLocal() as session:
            res = await session.execute(select(Task).where(Task.id == task_id))
            task = res.scalar_one_or_none()
            if task is None:
                return
            task.status = "failed"
            task.current_step = "failed"
            task.progress_pct = 100.0
            task.error_msg = err[:2000]
            task.completed_at = datetime.now(timezone.utc)
            session.add(task)
            await session.commit()

    async def _save_deck(
        self,
        task_id: str,
        slides: list[dict[str, Any]],
        theme: str,
        tokens: int,
        cost: float,
        model_used: str,
    ) -> None:
        async with SessionLocal() as session:
            existing = await session.execute(
                select(SlideDeck).where(SlideDeck.task_id == task_id)
            )
            deck = existing.scalar_one_or_none()
            if deck is None:
                deck = SlideDeck(
                    task_id=task_id,
                    slide_data=slides,
                    theme=theme,
                    slide_count=len(slides),
                )
                session.add(deck)
            else:
                deck.slide_data = slides
                deck.theme = theme
                deck.slide_count = len(slides)
                session.add(deck)

            res = await session.execute(select(Task).where(Task.id == task_id))
            task = res.scalar_one_or_none()
            if task is not None:
                task.status = "done"
                task.current_step = "done"
                task.progress_pct = 100.0
                task.tokens_used = tokens
                task.cost_usd = round(cost, 6)
                task.model_used = model_used
                task.completed_at = datetime.now(timezone.utc)
                session.add(task)

            await session.commit()
