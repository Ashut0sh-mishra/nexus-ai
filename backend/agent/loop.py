"""NEXUS 6-step agent loop — Manus-style: analyze → search → plan → generate → assemble → save."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select

from agent.memory import AgentMemory
from agent.planner import Planner
from agent.prompts import (
    NEXUS_SYSTEM_PROMPT,
    TOPIC_ANALYZER_SYSTEM_PROMPT,
    build_slide_prompt,
    slides_user_message,
)
from agent.prompts import CRITIC_SYSTEM_PROMPT, critic_user_message
from agent.theme_picker import is_auto, resolve_theme
from agent.topic_classifier import classify_topic
from database.connection import SessionLocal
from database.models import Slide, SlideDeck, Task, UploadedFile
from services.claude_service import ClaudeService
from services.chart_service import process_chart_data
from services.search_service import SearchService

logger = logging.getLogger("nexus.agent.loop")

ProgressCallback = Callable[[str, float, str], Awaitable[None]]

_VALID_LAYOUTS = {
    "title",
    "section",
    "bullets",
    "two-col",
    "comparison",
    "kpi",
    "quote",
    "stats",
    "chart",
    "table",
    "timeline",
    "image-focus",
    "closing",
}


# Map the lowercase theme keywords the topic-analyzer LLM is asked to return
# onto the canonical theme names the renderer actually knows. Any unknown
# value yields "" so the caller can fall back to the keyword-bucket picker.
_LLM_THEME_MAP: dict[str, str] = {
    "editorial": "Editorial",
    "light-pro": "light-pro",
    "lightpro": "light-pro",
    "light_pro": "light-pro",
    "dossier": "Dossier",
    "vellum": "Vellum",
    "pixel": "Pixel",
    "dark-pro": "Editorial",
    "darkpro": "Editorial",
    "dark_pro": "Editorial",
}


def _map_llm_theme(name: str) -> str:
    if not name:
        return ""
    return _LLM_THEME_MAP.get(name.strip().lower(), "")


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

    async def run(
        self,
        task_id: str,
        topic: str,
        slide_count: int,
        theme: str,
        search_web: bool,
        on_progress: ProgressCallback,
    ) -> dict[str, Any]:
        memory = AgentMemory(task_id)
        total_tokens = 0
        total_cost = 0.0
        model_used = self.claude.active_model

        original_theme = theme

        # Editorial profile (Manus-style): drives word target, fonts, accent
        # color and image strategy. Always rule-based, never blocks.
        topic_profile = classify_topic(topic)
        memory.write_profile(topic_profile)

        try:
            # 1 — ANALYZE (AI-driven topic analysis)
            await on_progress("Analyzing your topic...", 6.0, "analyze")
            await self._mark_running(task_id, "analyze", 6.0)
            analysis: dict[str, Any] = {}
            try:
                analysis, a_tokens, a_cost = await self._analyze_topic(topic)
                total_tokens += a_tokens
                total_cost += a_cost
            except Exception as exc:
                logger.warning("loop.analyze_failed", extra={"err": str(exc)})
                analysis = {}

            # Apply analysis: theme override (only when caller asked for auto)
            # and slide_count fallback when caller passed 0/None.
            # Note: we intentionally ignore the LLM's `best_theme` suggestion
            # here because it tends to collapse onto a small set (Editorial /
            # Dossier) regardless of topic, which makes every deck look the
            # same. Instead we always go through resolve_theme(topic, seed)
            # which rotates across the full 50-theme catalog per task_id.
            # When user picked Auto, prefer the editorial-profile theme
            # (it directly encodes the Manus findings per topic category).
            if is_auto(original_theme) and topic_profile.get("theme"):
                resolved_theme = resolve_theme(topic_profile["theme"], topic, seed=task_id)
            else:
                resolved_theme = resolve_theme(original_theme, topic, seed=task_id)
            theme = resolved_theme

            if not slide_count or slide_count <= 0:
                slide_count = int(analysis.get("ideal_slide_count") or 8)
            slide_count = max(4, min(20, int(slide_count)))

            topic_type = str(analysis.get("topic_type") or "").strip()
            tone = str(analysis.get("tone") or "").strip()
            detect_msg_bits: list[str] = []
            if topic_type:
                detect_msg_bits.append(f"{topic_type.title()} topic")
            if theme:
                detect_msg_bits.append(f"{theme} theme")
            if tone:
                detect_msg_bits.append(f"{tone} tone")
            detect_msg = (
                "Detected: " + " \u00b7 ".join(detect_msg_bits)
                if detect_msg_bits
                else "Topic analyzed."
            )
            await on_progress(
                detect_msg,
                10.0,
                "analyze",
                event="analysis",
                analysis=analysis,
                theme=theme,
                slide_count=slide_count,
            )
            if is_auto(original_theme) and theme:
                await on_progress(
                    f"Picked theme: {theme}.",
                    11.0,
                    "analyze",
                    event="theme",
                    theme=theme,
                )

            # 2 — SEARCH + 3 PLAN + 4 GENERATE
            # Markdown-first pipeline (Manus-style): research \u2192 deck_draft.md
            # \u2192 deck_final.md \u2192 slide JSON. Falls back to legacy JSON pipeline
            # on failure.
            from config import settings as _settings
            slides: list[dict[str, Any]] = []
            research = ""
            research_data: dict[str, Any] = {}
            outline: list[dict[str, Any]] = []
            use_md = bool(getattr(_settings, "USE_MARKDOWN_PIPELINE", True)) and search_web

            # 1.5 — VERIFIED RESEARCH (Manus-style fact-first)
            # Pull real facts from Wikipedia/Wikidata/REST Countries/etc BEFORE
            # any LLM generates content. Stops hallucinations.
            if search_web:
                try:
                    from services.research_pipeline import (
                        research_topic, format_research_for_prompt,
                    )
                    await on_progress(
                        "Researching verified facts from multiple sources...",
                        14.0, "research",
                    )
                    await self._mark_running(task_id, "research", 14.0)
                    research_data = await research_topic(
                        topic,
                        (topic_profile or {}).get("category", "explainer"),
                        depth=getattr(_settings, "RESEARCH_DEPTH", "deep"),
                    )
                    if research_data.get("sources_used"):
                        research = format_research_for_prompt(research_data)
                        try:
                            memory.write_artifact(
                                "research_data.json",
                                json.dumps(research_data, ensure_ascii=False, indent=2),
                            )
                        except Exception:
                            pass
                        await on_progress(
                            f"Verified facts gathered from "
                            f"{len(research_data['sources_used'])} sources.",
                            16.0, "research",
                            event="research",
                            sources=research_data["sources_used"],
                            facts_count=len(research_data.get("key_facts", [])),
                        )
                        logger.info(
                            "loop.research_pipeline_ok",
                            extra={
                                "sources": research_data["sources_used"],
                                "facts": len(research_data.get("key_facts", [])),
                                "from_cache": research_data.get("_from_cache", False),
                            },
                        )
                except Exception as exc:
                    logger.warning(
                        "loop.research_pipeline_failed",
                        extra={"err": str(exc)},
                    )
                    research_data = {}

            # 1.6 \u2014 DESIGN REFERENCE (Manus-style structural inspiration)
            # Pull recommended layout sequence + slide count + palette from
            # local reference index (and best-effort SlideShare). We bias
            # the planner with STRUCTURE only \u2014 never copy text.
            design_ref: dict[str, Any] = {}
            try:
                from services.reference_service import (
                    get_design_inspiration, format_design_reference_for_prompt,
                )
                await on_progress(
                    "Analyzing professional presentation patterns...",
                    17.0, "research",
                )
                design_ref = await get_design_inspiration(
                    topic, (topic_profile or {}).get("category", "explainer"),
                )
                ref_block = format_design_reference_for_prompt(design_ref)
                if ref_block:
                    # Prepend to research so both markdown pipeline and the
                    # legacy planner see it as part of their context.
                    research = (ref_block + "\n\n" + research) if research else ref_block
                    try:
                        memory.write_artifact(
                            "design_reference.json",
                            json.dumps(design_ref, ensure_ascii=False, indent=2),
                        )
                    except Exception:
                        pass
                    rec_count = design_ref.get("recommended_slide_count")
                    if rec_count and (not slide_count or slide_count <= 0):
                        slide_count = max(4, min(20, int(rec_count)))
                    logger.info(
                        "loop.design_reference_ok",
                        extra={
                            "layouts": len(design_ref.get("recommended_layouts") or []),
                            "slideshare": len(design_ref.get("slideshare_examples") or []),
                            "sample_count": (design_ref.get("local_reference") or {}).get("sample_count", 0),
                        },
                    )
            except Exception as exc:
                logger.warning(
                    "loop.design_reference_failed",
                    extra={"err": str(exc)},
                )

            if use_md:
                try:
                    from agent.markdown_pipeline import run_markdown_pipeline
                    md_slides, md_tokens, md_cost, final_md = await run_markdown_pipeline(
                        topic,
                        slide_count,
                        topic_profile,
                        claude=self.claude,
                        search=self.search,
                        memory=memory,
                        on_progress=on_progress,
                        prepend_research=research,
                    )
                    total_tokens += md_tokens
                    total_cost += md_cost
                    if md_slides:
                        slides = md_slides
                        # Synthesize an outline-shaped list for downstream
                        # critic / image / chart steps that read it.
                        outline = [
                            {
                                "index": i,
                                "layout": s.get("layout", "bullets"),
                                "title": s.get("title", ""),
                                "intent": "",
                            }
                            for i, s in enumerate(slides)
                        ]
                        memory.write_outline(outline)
                        memory.write_todo(outline)
                        # Use the final markdown as research context for critic.
                        research = final_md or ""
                        memory.write_research(research)
                        logger.info(
                            "loop.markdown_pipeline_ok",
                            extra={"slides": len(slides)},
                        )
                except Exception as exc:
                    logger.warning(
                        "loop.markdown_pipeline_failed_falling_back",
                        extra={"err": str(exc)},
                    )
                    slides = []

            # Legacy fallback: search \u2192 plan \u2192 generate
            if not slides:
                if search_web and not research:
                    await on_progress("Researching topic on the web...", 18.0, "search")
                    await self._mark_running(task_id, "search", 18.0)
                    try:
                        research, _sources = await self.search.search(topic, max_results=6)
                    except Exception as exc:
                        logger.warning("loop.search_failed", extra={"err": str(exc)})
                        research = ""
                memory.write_research(research)

                await on_progress("Planning slide structure...", 28.0, "plan")
                await self._mark_running(task_id, "plan", 28.0)
                task_ctx, audience, tone_meta, industry = await self._load_task_context(task_id)
                outline, p_tokens, p_cost = await self.planner.plan(
                    topic,
                    slide_count,
                    research,
                    context=task_ctx,
                    audience=audience,
                    tone=tone_meta or tone or None,
                    industry=industry,
                )
                total_tokens += p_tokens
                total_cost += p_cost
                memory.write_outline(outline)
                memory.write_todo(outline)

                target_words = int((topic_profile or {}).get("word_target") or 60)
                prefer_per_slide = target_words >= 90
                if prefer_per_slide:
                    logger.info(
                        "loop.using_per_slide_generation",
                        extra={"category": topic_profile.get("category"), "target": target_words},
                    )
                    try:
                        slides, g_tokens, g_cost = await self._generate_per_slide(
                            topic, research, outline, on_progress, memory, analysis,
                            profile=topic_profile, context=task_ctx,
                        )
                        total_tokens += g_tokens
                        total_cost += g_cost
                    except Exception as exc:
                        logger.warning(
                            "loop.per_slide_generate_failed_falling_back",
                            extra={"err": str(exc)},
                        )
                        slides = []

                if not slides:
                    try:
                        slides, g_tokens, g_cost = await self._generate_all_at_once(
                            topic, slide_count, research, outline, on_progress, memory, analysis,
                            profile=topic_profile, context=task_ctx,
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
                        topic, research, outline, on_progress, memory, analysis,
                        profile=topic_profile, context=task_ctx,
                    )
                    total_tokens += g_tokens
                    total_cost += g_cost

            # 5 — ASSEMBLE
            await on_progress("Finalizing presentation...", 90.0, "assemble")
            await self._mark_running(task_id, "assemble", 90.0)
            slides = self._normalize_slides(slides, slide_count, topic)

            # 5b — CRITIC (rewrite weak slides for Manus-level specificity)
            try:
                slides, c_tokens, c_cost = await self._critique_and_rewrite(
                    topic, research, slides, on_progress, profile=topic_profile,
                )
                total_tokens += c_tokens
                total_cost += c_cost
                slides = self._normalize_slides(slides, slide_count, topic)
            except Exception as exc:
                logger.warning("loop.critic_failed", extra={"err": str(exc)})

            # 5b.2 — FACT CHECK against verified research
            if research_data:
                try:
                    from services.fact_checker import verify_slides
                    slides = await verify_slides(slides, research_data)
                    flagged = sum(1 for s in slides if isinstance(s, dict) and s.get("_fact_check"))
                    if flagged:
                        await on_progress(
                            f"Fact-check flagged {flagged} slide(s) for review.",
                            89.0, "assemble",
                            event="fact_check", flagged=flagged,
                        )
                except Exception as exc:
                    logger.warning("loop.fact_check_failed", extra={"err": str(exc)})

            # 5c — IMAGES (hero visual per slide via Pollinations)
            try:
                slides, i_tokens, i_cost = await self._add_hero_images(
                    topic, slides, on_progress, profile=topic_profile,
                    images_context=(research_data or {}).get("images_context") or [],
                )
                total_tokens += i_tokens
                total_cost += i_cost
            except Exception as exc:
                logger.warning("loop.images_failed", extra={"err": str(exc)})

            # 5d — CHART PROCESSING (renderer-ready chartjs+pptx config)
            try:
                slides = self._process_charts(slides, theme)
            except Exception as exc:
                logger.warning("loop.charts_failed", extra={"err": str(exc)})

            # 6 — SAVE
            # Stamp the editorial profile's fonts + accent onto every slide so
            # the PPTX exporter can pick them up without us threading profile
            # through the export route. Idempotent — uses setdefault.
            try:
                fp = (topic_profile or {}).get("font_pair") or {}
                heading_font = (fp.get("heading") or "Inter").strip() or "Inter"
                body_font = (fp.get("body") or "Inter").strip() or "Inter"
                accent = (topic_profile or {}).get("accent_color") or ""
                for s in slides:
                    if isinstance(s, dict):
                        s.setdefault("_font_heading", heading_font)
                        s.setdefault("_font_body", body_font)
                        if accent:
                            s.setdefault("_accent_override", accent)
            except Exception as exc:
                logger.warning(
                    "loop.profile_stamp_failed",
                    extra={"err": str(exc), "err_type": type(exc).__name__},
                    exc_info=True,
                )

            await on_progress("Saving your slides...", 96.0, "save")
            await self._save_deck(task_id, slides, theme, total_tokens, total_cost, model_used)

            await on_progress("Done! Your slides are ready.", 100.0, "done", status="done")

            # PRD §16 — fire deck.completed webhook (best-effort).
            try:
                from api.routes.webhooks import dispatch_event
                await dispatch_event(
                    "deck.completed",
                    {"task_id": task_id, "topic": topic, "slide_count": len(slides), "theme": theme},
                )
            except Exception as exc:  # pragma: no cover
                logger.debug("loop.webhook_completed_failed", extra={"err": str(exc)})

            return {"slides": slides, "tokens": total_tokens, "cost_usd": total_cost}

        except Exception as exc:
            logger.exception("loop.failed", extra={"task_id": task_id})
            await self._mark_failed(task_id, str(exc))
            await on_progress(f"Generation failed: {exc}", 100.0, "failed", status="failed", error=str(exc))
            try:
                from api.routes.webhooks import dispatch_event
                await dispatch_event(
                    "deck.failed",
                    {"task_id": task_id, "topic": topic, "error": str(exc)},
                )
            except Exception:  # pragma: no cover
                pass
            raise

    # ── generation strategies ─────────────────────────────────────────────
    async def _analyze_topic(self, topic: str) -> tuple[dict[str, Any], int, float]:
        """Ask the LLM to classify the topic and propose theme/length/tone."""
        text, tokens, cost = await self.claude.complete(
            system=TOPIC_ANALYZER_SYSTEM_PROMPT,
            user=f"Analyze this topic: {topic}",
            max_tokens=512,
            temperature=0.2,
        )
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            return {}, tokens, cost
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}, tokens, cost
        if not isinstance(data, dict):
            return {}, tokens, cost
        logger.info("loop.topic_analysis", extra={"analysis": data})
        return data, tokens, cost

    async def _generate_all_at_once(
        self,
        topic: str,
        slide_count: int,
        research: str,
        outline: list[dict[str, Any]],
        on_progress: ProgressCallback,
        memory: AgentMemory,
        analysis: dict[str, Any] | None = None,
        *,
        profile: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int, float]:
        await on_progress(f"Writing slides 1 of {slide_count}...", 35.0, "generate")
        outline_text = "\n".join(
            f"{i + 1}. ({p['layout']}) {p['title']} — {p['intent']}"
            for i, p in enumerate(outline)
        )
        user_msg = slides_user_message(
            topic, slide_count, research, outline_text, profile=profile
        )
        system_prompt = (
            build_slide_prompt(topic, analysis, research)
            if analysis
            else NEXUS_SYSTEM_PROMPT
        )
        text, tokens, cost = await self.claude.complete(
            system=system_prompt,
            user=user_msg,
            max_tokens=8096,
        )
        slides = self._parse_slides_array(text)
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
        analysis: dict[str, Any] | None = None,
        *,
        profile: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int, float]:
        from agent.prompts import single_slide_user_message

        system_prompt = (
            build_slide_prompt(topic, analysis, research)
            if analysis
            else NEXUS_SYSTEM_PROMPT
        )

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
            base_user = single_slide_user_message(
                topic, research, plan, i, n,
                profile=profile,
                prior_slides=slides[-3:] if slides else None,
                context=context,
            )
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
                    text, tokens, cost = await self.claude.complete(
                        system=system_prompt,
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
        if layout in ("title", "closing", "chart", "table", "timeline", "image-focus"):
            return False  # Don't waste tokens rewriting titles/closings/structured layouts.

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
        *,
        profile: dict[str, Any] | None = None,
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
                text, tokens, cost = await self.claude.complete(
                    system=CRITIC_SYSTEM_PROMPT,
                    user=critic_user_message(topic, research, original, profile=profile),
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
    async def _add_hero_images(
        self,
        topic: str,
        slides: list[dict[str, Any]],
        on_progress: ProgressCallback,
        *,
        profile: dict[str, Any] | None = None,
        images_context: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int, float]:
        """Attach a recommended image (stock or AI) per slide.

        Stock APIs (Unsplash → Pexels) are used when ``UNSPLASH_ACCESS_KEY`` /
        ``PEXELS_API_KEY`` are set; otherwise we fall back to a Pollinations
        URL with a layout-tuned prompt. Layouts like ``chart``/``stats``/
        ``quote`` are skipped because the recommender returns ``None`` for
        compositions that already carry their own visual.

        Honors the editorial profile's ``image_strategy``: history / research
        decks ship with no images at all, data decks only on title/closing,
        and pitch / brand decks get full hero treatment.
        """
        from services.image_service import recommend_images, should_have_image_for_profile

        target_indices = [
            i for i, s in enumerate(slides)
            if should_have_image_for_profile(s.get("layout"), profile)
        ]
        if not target_indices:
            logger.info(
                "images.skipped_by_profile",
                extra={
                    "category": (profile or {}).get("category"),
                    "strategy": (profile or {}).get("image_strategy"),
                },
            )
            return slides, 0, 0.0

        await on_progress("Generating slide imagery...", 94.0, "images")

        # PRD §20: parallel image fetch — bounded so we don't hammer stock APIs.
        import asyncio
        semaphore = asyncio.Semaphore(4)

        async def _one(i: int) -> tuple[int, dict | None]:
            async with semaphore:
                try:
                    rec = await recommend_images(
                        slides[i], topic=topic, seed=i + 1,
                        images_context=images_context,
                    )
                    return i, rec
                except Exception as exc:
                    logger.warning(
                        "images.recommend_failed", extra={"i": i, "err": str(exc)}
                    )
                    return i, None

        results = await asyncio.gather(*[_one(i) for i in target_indices])

        attached = 0
        for i, rec in results:
            if not rec or not rec.get("url"):
                continue
            slides[i]["image"] = rec
            slides[i]["image_url"] = rec["url"]
            slides[i]["image_prompt"] = rec.get("prompt") or slides[i].get(
                "image_prompt", ""
            )
            attached += 1

        logger.info(
            "images.attached", extra={"count": attached, "total": len(slides)}
        )
        return slides, 0, 0.0


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
            layout = str(raw.get("layout") or "").strip().lower()
            if layout not in _VALID_LAYOUTS:
                layout = "bullets"
            base = {
                "id": f"slide-{i:03d}",
                "layout": layout,
                "title": str(raw.get("title") or "").strip(),
            }
            if layout == "title":
                # NB: do NOT fall back to `tagline` for the eyebrow — the
                # tagline is the long opening sentence and would overflow the
                # eyebrow band on the title slide.
                eyebrow = str(raw.get("eyebrow") or "Presentation").strip()
                if len(eyebrow) > 60:
                    eyebrow = eyebrow[:60].rsplit(" ", 1)[0] + "…"
                base.update(
                    {
                        "subtitle": str(raw.get("subtitle") or "").strip(),
                        "eyebrow": eyebrow,
                        "tagline": str(raw.get("tagline") or "").strip(),
                    }
                )
            elif layout == "bullets":
                bullets = raw.get("bullets") or []
                if not isinstance(bullets, list):
                    bullets = []
                base["bullets"] = [str(b).strip() for b in bullets if str(b).strip()][:4]
                base["section"] = str(raw.get("section") or "").strip()
            elif layout == "two-col":
                cols_raw = raw.get("columns")
                if isinstance(cols_raw, list) and cols_raw:
                    cols = [
                        {
                            "heading": str(c.get("heading") or c.get("title") or "").strip(),
                            "body": str(c.get("body") or c.get("content") or "").strip(),
                        }
                        for c in cols_raw[:2]
                        if isinstance(c, dict)
                    ]
                else:
                    # Accept flat schema: col1_title/col1_content/col2_title/col2_content.
                    cols = []
                    for n in (1, 2):
                        h = str(raw.get(f"col{n}_title") or "").strip()
                        b = str(raw.get(f"col{n}_content") or "").strip()
                        if h or b:
                            cols.append({"heading": h, "body": b})
                base["columns"] = cols
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
                        "trend": str(s.get("trend") or "").strip(),
                    }
                    for s in stats[:3]
                    if isinstance(s, dict)
                ]
            elif layout == "chart":
                cd = raw.get("chart_data") or {}
                if not isinstance(cd, dict):
                    cd = {}
                # Accept flat schema (labels/values/unit/source at root) too.
                labels = cd.get("labels") or raw.get("labels") or []
                values = cd.get("values") or raw.get("values") or []
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
                ct = str(raw.get("chart_type") or "bar").strip().lower() or "bar"
                if ct == "pie":
                    ct = "doughnut"
                if ct not in {"bar", "line", "doughnut"}:
                    ct = "bar"
                base["chart_type"] = ct
                base["chart_data"] = {
                    "labels": [str(x).strip() for x in labels[:pairs]],
                    "values": numeric[:pairs],
                    "unit": str(cd.get("unit") or raw.get("unit") or "").strip(),
                    "source": str(cd.get("source") or raw.get("source") or "").strip(),
                }
                base["subtitle"] = str(raw.get("subtitle") or "").strip()
            elif layout == "closing":
                base["subtitle"] = str(
                    raw.get("subtitle") or raw.get("message") or ""
                ).strip()
                base["message"] = str(raw.get("message") or "").strip()
                base["cta"] = str(raw.get("cta") or "Thank you").strip()
                base["tagline"] = str(raw.get("tagline") or "").strip()
            elif layout == "table":
                headers = raw.get("headers") or []
                rows = raw.get("rows") or []
                if not isinstance(headers, list):
                    headers = []
                if not isinstance(rows, list):
                    rows = []
                base["headers"] = [str(h).strip() for h in headers][:6]
                base["rows"] = [
                    [str(c).strip() for c in (r if isinstance(r, list) else [])][:6]
                    for r in rows[:8]
                ]
            elif layout == "timeline":
                events = raw.get("events") or []
                if not isinstance(events, list):
                    events = []
                base["events"] = [
                    {
                        "year": str(e.get("year") or "").strip(),
                        "title": str(e.get("title") or "").strip(),
                        "desc": str(e.get("desc") or e.get("description") or "").strip(),
                    }
                    for e in events[:6]
                    if isinstance(e, dict)
                ]
            elif layout == "image-focus":
                base["caption"] = str(raw.get("caption") or raw.get("subtitle") or "").strip()
                base["image_prompt"] = str(raw.get("image_prompt") or "").strip()
            elif layout == "section":
                base["eyebrow"] = str(
                    raw.get("eyebrow") or raw.get("section") or "Section"
                ).strip()
                base["subtitle"] = str(
                    raw.get("subtitle") or raw.get("description") or ""
                ).strip()
                base["section_number"] = str(
                    raw.get("section_number") or raw.get("number") or ""
                ).strip()
            elif layout == "kpi":
                kpis_raw = raw.get("kpis") or raw.get("stats") or []
                if not isinstance(kpis_raw, list):
                    kpis_raw = []
                base["kpis"] = [
                    {
                        "value": str(k.get("value") or "").strip(),
                        "label": str(k.get("label") or "").strip(),
                        "sublabel": str(
                            k.get("sublabel") or k.get("description") or ""
                        ).strip(),
                        "delta": str(k.get("delta") or k.get("trend") or "").strip(),
                        "direction": str(k.get("direction") or "").strip().lower(),
                    }
                    for k in kpis_raw[:4]
                    if isinstance(k, dict)
                ]
                base["subtitle"] = str(raw.get("subtitle") or "").strip()
            elif layout == "comparison":
                items_raw = raw.get("items") or raw.get("columns") or []
                if not isinstance(items_raw, list):
                    items_raw = []
                items: list[dict[str, Any]] = []
                for c in items_raw[:2]:
                    if not isinstance(c, dict):
                        continue
                    points = c.get("points") or c.get("bullets") or []
                    if not isinstance(points, list):
                        points = []
                    items.append(
                        {
                            "heading": str(
                                c.get("heading") or c.get("title") or ""
                            ).strip(),
                            "subtitle": str(
                                c.get("subtitle") or c.get("tagline") or ""
                            ).strip(),
                            "points": [str(p).strip() for p in points if str(p).strip()][:4],
                            "body": str(c.get("body") or "").strip(),
                        }
                    )
                # Accept flat schema as a fallback.
                if not items:
                    for n in (1, 2):
                        h = str(raw.get(f"col{n}_title") or "").strip()
                        b = str(raw.get(f"col{n}_content") or "").strip()
                        if h or b:
                            items.append(
                                {"heading": h, "subtitle": "", "points": [], "body": b}
                            )
                base["items"] = items
                base["divider"] = str(raw.get("divider") or "vs").strip()
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
                    s.pop("stats", None)
                    break
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

    # ── context loading ───────────────────────────────────────────────────
    async def _load_task_context(
        self, task_id: str
    ) -> tuple[dict[str, Any], str | None, str | None, str | None]:
        """Load Task metadata + uploaded files + aggregate BI for the planner.

        Returns ``(context, audience, tone, industry)`` where ``context`` has
        the shape expected by ``Planner.plan``::

            {
              "business_intelligence": {chart_opportunities, kpi_candidates,
                                        insights, data_tables},
              "files": [{filename, file_type, preview}, ...],
            }
        """
        ctx: dict[str, Any] = {}
        audience: str | None = None
        tone: str | None = None
        industry: str | None = None
        try:
            async with SessionLocal() as session:
                t_res = await session.execute(select(Task).where(Task.id == task_id))
                task = t_res.scalar_one_or_none()
                if task is None:
                    return ctx, None, None, None
                audience = task.audience or None
                tone = task.tone or None
                industry = task.industry or None

                # Uploaded files explicitly attached to this task. Also include
                # files referenced by Task.context_sources (file_id list).
                wanted_ids: list[str] = []
                src = task.context_sources
                if isinstance(src, list):
                    wanted_ids = [str(x) for x in src if x]

                f_res = await session.execute(
                    select(UploadedFile).where(UploadedFile.task_id == task_id)
                )
                files = list(f_res.scalars().all())
                if wanted_ids:
                    extra_res = await session.execute(
                        select(UploadedFile).where(UploadedFile.id.in_(wanted_ids))
                    )
                    seen = {f.id for f in files}
                    for ef in extra_res.scalars().all():
                        if ef.id not in seen:
                            files.append(ef)

                if not files:
                    return ctx, audience, tone, industry

                file_summaries: list[dict[str, Any]] = []
                charts: list[dict[str, Any]] = []
                kpis: list[dict[str, Any]] = []
                tables: list[dict[str, Any]] = []
                insights: list[str] = []
                # Defensive: legacy rows may carry the uuid_-prefixed disk name.
                _UUID_PREFIX = re.compile(r"^[0-9a-f]{32}_")
                for f in files:
                    preview = (f.extracted_text or "").strip()
                    # Keep the full preview for small files (LLM context)
                    # and a generous slice for larger ones. Newlines are
                    # preserved so JSON / Markdown structure survives.
                    if preview:
                        preview = preview[:12000]
                    display_name = _UUID_PREFIX.sub("", f.filename or "")
                    file_summaries.append(
                        {
                            "id": f.id,
                            "filename": display_name or f.filename,
                            "file_type": f.file_type,
                            "preview": preview,
                        }
                    )
                    data = f.extracted_data_json or {}
                    if not isinstance(data, dict):
                        continue
                    bi = data.get("business_intelligence") or {}
                    if not isinstance(bi, dict):
                        continue
                    if isinstance(bi.get("chart_opportunities"), list):
                        charts.extend(bi["chart_opportunities"])
                    if isinstance(bi.get("kpi_candidates"), list):
                        kpis.extend(bi["kpi_candidates"])
                    if isinstance(bi.get("data_tables"), list):
                        tables.extend(bi["data_tables"])
                    if isinstance(bi.get("insights"), list):
                        insights.extend(str(x) for x in bi["insights"])

                ctx["files"] = file_summaries
                if charts or kpis or tables or insights:
                    ctx["business_intelligence"] = {
                        "chart_opportunities": charts,
                        "kpi_candidates": kpis,
                        "data_tables": tables,
                        "insights": insights,
                    }
        except Exception as exc:
            logger.warning("loop.load_context_failed", extra={"err": str(exc)})
        return ctx, audience, tone, industry

    # ── DB writes ─────────────────────────────────────────────────────────
    async def _mark_running(self, task_id: str, step: str, pct: float) -> None:
        async with SessionLocal() as session:
            res = await session.execute(select(Task).where(Task.id == task_id))
            task = res.scalar_one_or_none()
            if task is None:
                return
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

            # Write per-slide rows into deck_slides. Re-runs replace the
            # previous rows so slide_number stays stable and the unique
            # (task_id, slide_number) constraint never trips.
            old_rows = await session.execute(
                select(Slide).where(Slide.task_id == task_id)
            )
            for row in old_rows.scalars().all():
                await session.delete(row)
            await session.flush()
            for idx, slide in enumerate(slides):
                kwargs = self._slide_dict_to_row_kwargs(idx, slide)
                session.add(Slide(task_id=task_id, **kwargs))

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

    # ── chart processing ──────────────────────────────────────────────────
    @staticmethod
    def _process_charts(
        slides: list[dict[str, Any]], theme: str
    ) -> list[dict[str, Any]]:
        """Run every chart-bearing slide through ``process_chart_data``.

        Mutates each slide in place, attaching a ``chart`` envelope under the
        key ``slide["chart"]`` (chartjs_config + pptx_config + processed
        labels/values). Leaves the legacy ``chart_data`` / ``chart_type``
        fields untouched so the existing renderer keeps working.
        """
        for s in slides:
            if not isinstance(s, dict):
                continue
            has_chart = (
                s.get("layout") == "chart"
                or "chart_data" in s
                or "datasets" in s
                or ("labels" in s and "values" in s)
            )
            if not has_chart:
                continue
            try:
                envelope = process_chart_data(s, theme=theme, title=s.get("title"))
            except Exception as exc:
                logger.warning("loop.process_chart_failed", extra={"err": str(exc)})
                envelope = None
            if envelope:
                s["chart"] = envelope
                # Backfill missing legacy fields so downstream renderers that
                # still read top-level keys keep working.
                if "chart_type" not in s:
                    s["chart_type"] = envelope["type"]
                if "chart_data" not in s:
                    s["chart_data"] = {
                        "labels": envelope["labels"],
                        "values": envelope["values"],
                        "unit": envelope.get("unit") or "",
                        "source": envelope.get("source") or "",
                    }
        return slides

    # ── slide dict → Slide ORM row ────────────────────────────────────────
    @staticmethod
    def _slide_dict_to_row_kwargs(idx: int, slide: dict[str, Any]) -> dict[str, Any]:
        """Map a generated slide payload onto ``Slide`` column kwargs.

        Splits the payload across:
        - ``content_json``       — the bulk of the layout-specific body
        - ``chart_data_json``    — chart fields (when layout=="chart")
        - ``image_data_json``    — image url/prompt (when present)
        - ``layout_metadata``    — planner-emitted hints (chart_data_source,
                                   kpi_refs, table_ref, visual_elements,
                                   text_density, suggested_layout)
        """
        if not isinstance(slide, dict):
            slide = {}
        layout = str(slide.get("layout") or "bullets").strip() or "bullets"
        title = str(slide.get("title") or "").strip()[:512]
        subtitle_src = (
            slide.get("subtitle")
            or slide.get("section")
            or slide.get("tagline")
        )
        subtitle = str(subtitle_src).strip()[:512] if subtitle_src else None
        speaker_notes = slide.get("speaker_notes")
        if isinstance(speaker_notes, str):
            speaker_notes = speaker_notes.strip() or None
        else:
            speaker_notes = None

        chart_keys = {"chart_type", "labels", "values", "unit", "source", "datasets"}
        chart_data: dict[str, Any] | None = None
        if layout == "chart" or any(k in slide for k in ("labels", "values", "datasets")):
            picked = {k: slide[k] for k in chart_keys if k in slide}
            if picked:
                chart_data = picked
        # Prefer the processed envelope (with chartjs_config + pptx_config)
        # when the chart_service has run.
        envelope = slide.get("chart")
        if isinstance(envelope, dict):
            chart_data = {**(chart_data or {}), "envelope": envelope}

        image_data: dict[str, Any] | None = None
        envelope_img = slide.get("image")
        if isinstance(envelope_img, dict) and envelope_img.get("url"):
            image_data = dict(envelope_img)
        elif slide.get("image_url") or slide.get("image_prompt"):
            image_data = {
                "url": slide.get("image_url"),
                "prompt": slide.get("image_prompt"),
            }

        meta_keys = (
            "suggested_layout",
            "chart_data_source",
            "kpi_refs",
            "table_ref",
            "visual_elements",
            "text_density",
            "intent",
        )
        layout_meta = {k: slide[k] for k in meta_keys if k in slide}
        layout_meta = layout_meta or None

        # content_json holds everything else so the editor can round-trip the
        # full payload without losing layout-specific fields.
        excluded = (
            chart_keys
            | {"image_url", "image_prompt", "image", "speaker_notes", "title",
               "subtitle", "section", "tagline", "layout", "id", "chart"}
            | set(meta_keys)
        )
        content = {k: v for k, v in slide.items() if k not in excluded}

        return {
            "slide_number": idx + 1,
            "slide_type": layout[:32],
            "title": title,
            "subtitle": subtitle,
            "content_json": content or None,
            "chart_data_json": chart_data,
            "image_data_json": image_data,
            "speaker_notes": speaker_notes,
            "layout_metadata": layout_meta,
        }
