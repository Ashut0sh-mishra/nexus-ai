"""Slide outline planner — Claude generates a todo.md style structure first."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agent.layouts_registry import (
    CANONICAL_LAYOUTS,
    FALLBACK_LAYOUT,
    normalize_layout,
)
from agent.prompts import PLANNER_SYSTEM_PROMPT, planner_user_message
from services.claude_service import ClaudeService

logger = logging.getLogger("nexus.agent.planner")

# Valid slide layouts come from the canonical registry. Do NOT reintroduce a
# hardcoded literal here — it will diverge from agent/loop.py and the
# frontend renderer. ``scripts/verify-layouts.mjs`` enforces this.
_VALID_LAYOUTS = frozenset(CANONICAL_LAYOUTS)


class Planner:
    """Builds a slide-by-slide outline before content generation."""

    def __init__(self, claude: ClaudeService | None = None) -> None:
        self.claude = claude or ClaudeService()

    async def plan(
        self,
        topic: str,
        slide_count: int,
        research: str,
        *,
        strategy: Any | None = None,
    ) -> tuple[list[dict[str, Any]], int, float]:
        """Return (outline, tokens_used, cost_usd).

        ``strategy`` is an optional :class:`agent.deck_strategy.DeckStrategy`
        artifact built before planning (Phase 6V). When supplied, it is
        rendered into the user prompt so the LLM knows the deck's
        intended type, story arc, audience, and layout recipe. Older
        callers that do not pass ``strategy`` continue to work unchanged.
        """
        user_msg = planner_user_message(
            topic, slide_count, research or "", strategy=strategy
        )
        try:
            # Phase 6W: prefer role-routed model (planner). Fall back to the
            # legacy ``complete`` interface for ClaudeService stand-ins/fakes
            # that don't implement ``complete_for_role`` yet.
            if hasattr(self.claude, "complete_for_role"):
                text, tokens, cost = await self.claude.complete_for_role(
                    role="planner",
                    system=PLANNER_SYSTEM_PROMPT,
                    user=user_msg,
                    max_tokens=2048,
                )
            else:
                text, tokens, cost = await self.claude.complete(
                    system=PLANNER_SYSTEM_PROMPT,
                    user=user_msg,
                    max_tokens=2048,
                )
        except Exception as exc:
            logger.warning("planner.claude_failed_falling_back", extra={"err": str(exc)})
            return self._fallback_outline(topic, slide_count, strategy=strategy), 0, 0.0

        outline = self._parse_outline(text)
        if not outline:
            logger.warning("planner.parse_empty_using_fallback")
            outline = self._fallback_outline(topic, slide_count, strategy=strategy)

        outline = self._enforce_constraints(outline, slide_count)
        return outline, tokens, cost

    # ── parsing ────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_outline(text: str) -> list[dict[str, Any]]:
        if not text:
            return []
        cleaned = text.strip()
        # strip optional ```json fences
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        # find the first JSON array if Claude added stray prose
        match = re.search(r"\[\s*[\s\S]*\]\s*$", cleaned)
        if match:
            cleaned = match.group(0)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        out: list[dict[str, Any]] = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            # Resolve through the canonical registry so unknown values fall
            # back to FALLBACK_LAYOUT and (future) aliases route to canonical.
            layout = normalize_layout(item.get("layout"))
            if layout not in _VALID_LAYOUTS:
                layout = FALLBACK_LAYOUT
            out.append(
                {
                    "index": i,
                    "layout": layout,
                    "title": str(item.get("title") or "").strip()[:140],
                    "intent": str(item.get("intent") or "").strip()[:280],
                }
            )
        return out

    @staticmethod
    def _enforce_constraints(
        outline: list[dict[str, Any]], slide_count: int
    ) -> list[dict[str, Any]]:
        if not outline:
            return outline
        # Trim or pad to exact slide_count.
        if len(outline) > slide_count:
            outline = outline[:slide_count]
        while len(outline) < slide_count:
            outline.append(
                {
                    "index": len(outline),
                    "layout": "bullets",
                    "title": f"Section {len(outline) + 1}",
                    "intent": "Supporting content.",
                }
            )
        # First / last layouts.
        outline[0]["layout"] = "title"
        outline[-1]["layout"] = "closing"
        for i, item in enumerate(outline):
            item["index"] = i
        return outline

    @staticmethod
    def _fallback_outline(
        topic: str, slide_count: int, *, strategy: Any | None = None
    ) -> list[dict[str, Any]]:
        # Phase 6V: when a deck strategy was supplied, prefer its
        # ``layout_recipe`` for the fallback rotation so a research
        # report does not look like a pitch when the LLM is unavailable.
        recipe: list[str] | None = None
        story_arc: list[str] = []
        if strategy is not None:
            try:
                recipe = list(getattr(strategy, "layout_recipe", []) or [])
                story_arc = list(getattr(strategy, "story_arc", []) or [])
            except Exception:
                recipe = None
                story_arc = []
        if not recipe:
            recipe = ["title", "bullets", "two-col", "stats", "quote", "chart", "two-col", "closing"]

        # Trim/pad recipe to slide_count without ever dropping the
        # opening or closing slot.
        if slide_count <= 0:
            slide_count = 1
        if len(recipe) > slide_count:
            recipe = [recipe[0]] + recipe[1 : 1 + (slide_count - 2)] + [recipe[-1]]
            recipe = recipe[:slide_count]
        while len(recipe) < slide_count:
            # alternate filler that does not duplicate the previous layout
            filler = "two-col" if recipe[-2] == "bullets" else "bullets"
            recipe.insert(-1, filler)

        outline: list[dict[str, Any]] = []
        for i, layout in enumerate(recipe):
            intent = (
                story_arc[i] if i < len(story_arc) and story_arc[i] else "Supporting evidence."
            )
            if i == 0:
                title = topic
            elif i == len(recipe) - 1:
                title = "Wrap up"
            else:
                title = f"{topic} — {intent}"[:140]
            outline.append(
                {
                    "index": i,
                    "layout": layout,
                    "title": title,
                    "intent": intent,
                }
            )
        return outline[:slide_count]
