"""Slide outline planner — Claude generates a todo.md style structure first."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agent.prompts import PLANNER_SYSTEM_PROMPT, planner_user_message
from agent.layouts_registry import (
    CANONICAL_LAYOUTS as _VALID_LAYOUTS,
    LAYOUT_ALIASES as _LAYOUT_ALIASES,
    normalize_layout as _normalize_layout,
)
from services.claude_service import ClaudeService

logger = logging.getLogger("nexus.agent.planner")

_VALID_CHART_TYPES = {"bar", "line", "pie", "doughnut", "area"}
_VALID_TEXT_DENSITY = {"low", "medium", "high"}


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
        context: dict[str, Any] | None = None,
        audience: str | None = None,
        tone: str | None = None,
        industry: str | None = None,
    ) -> tuple[list[dict[str, Any]], int, float]:
        """Return (outline, tokens_used, cost_usd).

        ``context`` is an optional dict with shape:
            {
              "business_intelligence": {chart_opportunities, kpi_candidates,
                                        insights, data_tables},
              "files": [{filename, file_type, preview}, ...],
            }
        """
        intelligence = (context or {}).get("business_intelligence") or {}

        user_msg = planner_user_message(
            topic,
            slide_count,
            research or "",
            context=context,
            audience=audience,
            tone=tone,
            industry=industry,
        )
        try:
            text, tokens, cost = await self.claude.complete(
                system=PLANNER_SYSTEM_PROMPT,
                user=user_msg,
                max_tokens=2560,
            )
        except Exception as exc:
            logger.warning("planner.claude_failed_falling_back", extra={"err": str(exc)})
            outline = self._fallback_outline(topic, slide_count, intelligence)
            return outline, 0, 0.0

        outline = self._parse_outline(text)
        if not outline:
            logger.warning("planner.parse_empty_using_fallback")
            outline = self._fallback_outline(topic, slide_count, intelligence)

        outline = self._enforce_constraints(outline, slide_count)
        outline = self._allocate_intelligence(outline, intelligence)
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
            layout = _normalize_layout(str(item.get("layout") or ""))
            entry: dict[str, Any] = {
                "index": i,
                "layout": layout,
                "suggested_layout": layout,
                "title": str(item.get("title") or "").strip()[:140],
                "intent": str(item.get("intent") or "").strip()[:280],
            }

            # Optional schema fields — pass through when valid.
            chart_type = str(item.get("chart_type") or "").strip().lower()
            if chart_type in _VALID_CHART_TYPES:
                entry["chart_type"] = chart_type

            cds = item.get("chart_data_source")
            if isinstance(cds, str) and cds.strip():
                entry["chart_data_source"] = cds.strip()[:64]

            img = item.get("image_prompt")
            if isinstance(img, str) and img.strip():
                entry["image_prompt"] = img.strip()[:280]

            ve = item.get("visual_elements")
            if isinstance(ve, list):
                cleaned_ve = [str(v).strip()[:40] for v in ve if str(v).strip()]
                if cleaned_ve:
                    entry["visual_elements"] = cleaned_ve[:6]

            density = str(item.get("text_density") or "").strip().lower()
            if density in _VALID_TEXT_DENSITY:
                entry["text_density"] = density

            kpi_refs = item.get("kpi_refs")
            if isinstance(kpi_refs, list):
                ints = [int(x) for x in kpi_refs if isinstance(x, (int, float))]
                if ints:
                    entry["kpi_refs"] = ints[:6]

            table_ref = item.get("table_ref")
            if isinstance(table_ref, (int, float)):
                entry["table_ref"] = int(table_ref)

            out.append(entry)
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
                    "suggested_layout": "bullets",
                    "title": f"Section {len(outline) + 1}",
                    "intent": "Supporting content.",
                }
            )
        # First / last layouts.
        outline[0]["layout"] = "title"
        outline[0]["suggested_layout"] = "title"
        outline[-1]["layout"] = "closing"
        outline[-1]["suggested_layout"] = "closing"
        for i, item in enumerate(outline):
            item["index"] = i
        return outline

    # ── BI auto-allocation ─────────────────────────────────────────────────
    @staticmethod
    def _allocate_intelligence(
        outline: list[dict[str, Any]],
        intelligence: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Attach BI artifacts (charts/tables/KPIs) to slides.

        Fills ``chart_data_source`` / ``table_ref`` / ``kpi_refs`` for slides
        whose layout matches but where the LLM omitted them. This guarantees
        every detected chart_opportunity / data_table surfaces on at least one
        slide.
        """
        if not intelligence:
            return outline

        charts = list(intelligence.get("chart_opportunities") or [])
        tables = list(intelligence.get("data_tables") or [])
        kpis = list(intelligence.get("kpi_candidates") or [])

        used_charts: set[int] = set()
        used_tables: set[int] = set()
        used_kpis: set[int] = set()

        # First pass: respect what the LLM already chose.
        for s in outline:
            cds = s.get("chart_data_source")
            if isinstance(cds, str) and cds.startswith("chart:"):
                try:
                    used_charts.add(int(cds.split(":", 1)[1]))
                except ValueError:
                    pass
            tr = s.get("table_ref")
            if isinstance(tr, int):
                used_tables.add(tr)
            kr = s.get("kpi_refs")
            if isinstance(kr, list):
                used_kpis.update(int(x) for x in kr if isinstance(x, int))

        # Second pass: fill gaps on matching slides.
        for s in outline:
            layout = s.get("layout")
            if layout == "chart" and "chart_data_source" not in s:
                for i, c in enumerate(charts):
                    if i in used_charts:
                        continue
                    s["chart_data_source"] = f"chart:{i}"
                    s.setdefault("chart_type", str(c.get("chart_type") or "bar"))
                    used_charts.add(i)
                    break
            elif layout == "table" and "table_ref" not in s and tables:
                for i in range(len(tables)):
                    if i in used_tables:
                        continue
                    s["table_ref"] = i
                    used_tables.add(i)
                    break
            elif layout == "stats" and "kpi_refs" not in s and kpis:
                refs: list[int] = []
                for i in range(len(kpis)):
                    if i in used_kpis:
                        continue
                    refs.append(i)
                    used_kpis.add(i)
                    if len(refs) >= 3:
                        break
                if refs:
                    s["kpi_refs"] = refs

        # Third pass: if there are still un-allocated chart/table opportunities,
        # promote suitable middle slides (bullets) to chart/table slides so the
        # data surfaces.
        def _free_middle_slot() -> dict[str, Any] | None:
            for s in outline[1:-1]:
                if s.get("layout") == "bullets" and "chart_data_source" not in s and "table_ref" not in s:
                    return s
            return None

        for i, c in enumerate(charts):
            if i in used_charts:
                continue
            slot = _free_middle_slot()
            if not slot:
                break
            slot["layout"] = "chart"
            slot["suggested_layout"] = "chart"
            slot["chart_data_source"] = f"chart:{i}"
            slot["chart_type"] = str(c.get("chart_type") or "bar")
            metric = str(c.get("metric") or "Trend")[:60]
            if not slot.get("title"):
                slot["title"] = metric
            used_charts.add(i)

        for i in range(len(tables)):
            if i in used_tables:
                continue
            slot = _free_middle_slot()
            if not slot:
                break
            slot["layout"] = "table"
            slot["suggested_layout"] = "table"
            slot["table_ref"] = i
            used_tables.add(i)

        return outline

    # ── fallback ───────────────────────────────────────────────────────────
    @staticmethod
    def _fallback_outline(
        topic: str,
        slide_count: int,
        intelligence: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        rotation = ["bullets", "two-col", "stats", "quote", "chart"]
        outline: list[dict[str, Any]] = [
            {
                "index": 0,
                "layout": "title",
                "suggested_layout": "title",
                "title": topic,
                "intent": "Open the deck.",
            }
        ]
        for i in range(1, slide_count - 1):
            layout = rotation[(i - 1) % len(rotation)]
            outline.append(
                {
                    "index": i,
                    "layout": layout,
                    "suggested_layout": layout,
                    "title": f"{topic} — part {i}",
                    "intent": "Supporting evidence.",
                }
            )
        outline.append(
            {
                "index": slide_count - 1,
                "layout": "closing",
                "suggested_layout": "closing",
                "title": "Thank you",
                "intent": "Call to action.",
            }
        )
        outline = outline[:slide_count]
        # Even fallback should attach available BI artifacts.
        return Planner._allocate_intelligence(outline, intelligence)
