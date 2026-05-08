"""PPTX + PDF export, with R2 or local-filesystem storage."""

from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path
from typing import Any, Iterable

import httpx
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Inches, Pt

from config import settings
from services.storage_service import StorageService

logger = logging.getLogger("nexus.services.export")

# 16:9 master dimensions in EMU
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


# Theme palette (matches the React renderer).
# Each entry: bg, text, muted, accent + optional heading_font / body_font.
# When a slide carries `_font_heading` / `_font_body` (stamped by the agent
# loop from the topic_classifier profile), those override the theme defaults.
_DEF_HEAD = "Inter"
_DEF_BODY = "Inter"

THEMES: dict[str, dict[str, str]] = {
    # ── Original five (kept verbatim for backwards compat) ────────────────
    "light-pro": {"bg": "FFFFFF", "text": "111827", "muted": "6B7280", "accent": "F59E0B", "heading_font": "Inter", "body_font": "Inter"},
    "Editorial": {"bg": "0F0F14", "text": "F5F5F7", "muted": "9A9AA5", "accent": "A78BFA", "heading_font": "Playfair Display", "body_font": "Inter"},
    "Pixel":     {"bg": "101820", "text": "F1FAEE", "muted": "94A3B8", "accent": "34D399", "heading_font": "Poppins", "body_font": "Inter"},
    "Vellum":    {"bg": "FAF7F2", "text": "1F1A14", "muted": "6B5E4A", "accent": "A0522D", "heading_font": "Playfair Display", "body_font": "EB Garamond"},
    "Dossier":   {"bg": "0B1220", "text": "E2E8F0", "muted": "94A3B8", "accent": "60A5FA", "heading_font": "Inter", "body_font": "Inter"},

    # ── Dark / bold ───────────────────────────────────────────────────────
    "Onyx":      {"bg": "1A1A2E", "text": "F8F8FF", "muted": "9CA3AF", "accent": "D4AF37", "heading_font": "Cinzel", "body_font": "Inter"},
    "Midnight":  {"bg": "0D1117", "text": "E2E8F0", "muted": "94A3B8", "accent": "38BDF8", "heading_font": "Inter", "body_font": "Inter"},
    "Carbon":    {"bg": "1F2937", "text": "F9FAFB", "muted": "9CA3AF", "accent": "F97316", "heading_font": "Montserrat", "body_font": "Inter"},
    "Basalt":    {"bg": "111827", "text": "F3F4F6", "muted": "9CA3AF", "accent": "10B981", "heading_font": "Inter", "body_font": "Inter"},
    "Crimson":   {"bg": "1B0E10", "text": "F8E8E8", "muted": "B89090", "accent": "DC2626", "heading_font": "Playfair Display", "body_font": "Inter"},
    "Cobalt":    {"bg": "0B2545", "text": "EEF4ED", "muted": "8DA9C4", "accent": "FBBF24", "heading_font": "Montserrat", "body_font": "Inter"},
    "Emerald":   {"bg": "022C22", "text": "ECFDF5", "muted": "6EE7B7", "accent": "34D399", "heading_font": "Inter", "body_font": "Inter"},
    "Forest":    {"bg": "14352B", "text": "F0FDF4", "muted": "86EFAC", "accent": "65A30D", "heading_font": "Merriweather", "body_font": "Inter"},
    "Plum":      {"bg": "2E1065", "text": "F5F3FF", "muted": "C4B5FD", "accent": "F472B6", "heading_font": "Playfair Display", "body_font": "Inter"},
    "Rose":      {"bg": "4C0519", "text": "FFF1F2", "muted": "FDA4AF", "accent": "FB7185", "heading_font": "Playfair Display", "body_font": "Inter"},
    "Neon":      {"bg": "0A0A0F", "text": "F1F5F9", "muted": "64748B", "accent": "A3E635", "heading_font": "Orbitron", "body_font": "Rajdhani"},
    "Glamour":   {"bg": "0A0A0A", "text": "F5E6C8", "muted": "B89968", "accent": "D4AF37", "heading_font": "Playfair Display", "body_font": "Inter"},

    # ── Pitch / Business ──────────────────────────────────────────────────
    "Pitch":     {"bg": "0D1117", "text": "FFFFFF", "muted": "94A3B8", "accent": "00D084", "heading_font": "Montserrat", "body_font": "Open Sans"},
    "Sales":     {"bg": "FFFFFF", "text": "0F172A", "muted": "64748B", "accent": "2563EB", "heading_font": "Montserrat", "body_font": "Inter"},
    "Strategy":  {"bg": "F8FAFC", "text": "0F172A", "muted": "475569", "accent": "0EA5E9", "heading_font": "Inter", "body_font": "Inter"},
    "Plan":      {"bg": "FFFFFF", "text": "1E293B", "muted": "64748B", "accent": "6366F1", "heading_font": "Inter", "body_font": "Inter"},
    "Plan2":     {"bg": "F1F5F9", "text": "0F172A", "muted": "64748B", "accent": "8B5CF6", "heading_font": "Inter", "body_font": "Inter"},
    "Profile":   {"bg": "FFFFFF", "text": "111827", "muted": "6B7280", "accent": "EC4899", "heading_font": "Playfair Display", "body_font": "Inter"},
    "Launch":    {"bg": "FFFFFF", "text": "111827", "muted": "6B7280", "accent": "EF4444", "heading_font": "Montserrat", "body_font": "Inter"},
    "Growth":    {"bg": "F0FDF4", "text": "14532D", "muted": "16A34A", "accent": "22C55E", "heading_font": "Inter", "body_font": "Inter"},
    "Annual":    {"bg": "FFFFFF", "text": "0F172A", "muted": "475569", "accent": "0F766E", "heading_font": "Merriweather", "body_font": "Inter"},
    "Review":    {"bg": "F9FAFB", "text": "111827", "muted": "6B7280", "accent": "0891B2", "heading_font": "Inter", "body_font": "Inter"},
    "Complete":  {"bg": "FFFFFF", "text": "0F172A", "muted": "64748B", "accent": "F59E0B", "heading_font": "Inter", "body_font": "Inter"},
    "Marketing": {"bg": "FFFFFF", "text": "111827", "muted": "6B7280", "accent": "F43F5E", "heading_font": "Poppins", "body_font": "Inter"},
    "Proposal":  {"bg": "FFFFFF", "text": "0F172A", "muted": "475569", "accent": "1D4ED8", "heading_font": "Merriweather", "body_font": "Inter"},

    # ── Light / minimal ───────────────────────────────────────────────────
    "Minimal":   {"bg": "FFFFFF", "text": "000000", "muted": "9CA3AF", "accent": "111111", "heading_font": "Inter", "body_font": "Inter"},
    "Simple":    {"bg": "FFFFFF", "text": "1F2937", "muted": "9CA3AF", "accent": "3B82F6", "heading_font": "Inter", "body_font": "Inter"},
    "Simplicity":{"bg": "FAFAFA", "text": "1F2937", "muted": "9CA3AF", "accent": "F59E0B", "heading_font": "Inter", "body_font": "Inter"},
    "Clean":     {"bg": "FFFFFF", "text": "111827", "muted": "9CA3AF", "accent": "14B8A6", "heading_font": "Inter", "body_font": "Inter"},
    "Modern":    {"bg": "FFFFFF", "text": "0F172A", "muted": "64748B", "accent": "8B5CF6", "heading_font": "Inter", "body_font": "Inter"},
    "Elegant":   {"bg": "FFFFFF", "text": "1F1A14", "muted": "6B5E4A", "accent": "B45309", "heading_font": "Playfair Display", "body_font": "EB Garamond"},
    "Stunning":  {"bg": "FFFFFF", "text": "0F172A", "muted": "64748B", "accent": "EC4899", "heading_font": "Playfair Display", "body_font": "Inter"},
    "Creative":  {"bg": "FFF7ED", "text": "1C1917", "muted": "78716C", "accent": "EA580C", "heading_font": "Poppins", "body_font": "Inter"},
    "Whiteboard":{"bg": "FFFFFF", "text": "1F2937", "muted": "6B7280", "accent": "0EA5E9", "heading_font": "Architects Daughter", "body_font": "Inter"},
    "Sketch":    {"bg": "FAFAF9", "text": "292524", "muted": "78716C", "accent": "F43F5E", "heading_font": "Architects Daughter", "body_font": "Inter"},
    "Golden":    {"bg": "FFFBEB", "text": "78350F", "muted": "B45309", "accent": "D97706", "heading_font": "Playfair Display", "body_font": "Inter"},

    # ── Vibrant gradient / bright ─────────────────────────────────────────
    "Sunrise":   {"bg": "FFEDD5", "text": "7C2D12", "muted": "C2410C", "accent": "F97316", "heading_font": "Poppins", "body_font": "Inter"},
    "Sunset":    {"bg": "FEF2F2", "text": "7F1D1D", "muted": "B91C1C", "accent": "EF4444", "heading_font": "Poppins", "body_font": "Inter"},
    "Aurora":    {"bg": "0F172A", "text": "F1F5F9", "muted": "94A3B8", "accent": "A855F7", "heading_font": "Inter", "body_font": "Inter"},
    "Tropical":  {"bg": "ECFDF5", "text": "064E3B", "muted": "059669", "accent": "10B981", "heading_font": "Poppins", "body_font": "Inter"},
    "Lagoon":    {"bg": "ECFEFF", "text": "164E63", "muted": "0E7490", "accent": "06B6D4", "heading_font": "Inter", "body_font": "Inter"},
    "Coral":     {"bg": "FFF1F2", "text": "9F1239", "muted": "BE185D", "accent": "F43F5E", "heading_font": "Poppins", "body_font": "Inter"},
    "Ice":       {"bg": "F0F9FF", "text": "0C4A6E", "muted": "0369A1", "accent": "0EA5E9", "heading_font": "Inter", "body_font": "Inter"},
    "Peach":     {"bg": "FFF7ED", "text": "9A3412", "muted": "C2410C", "accent": "F97316", "heading_font": "Poppins", "body_font": "Inter"},

    # ── Bright single-color ───────────────────────────────────────────────
    "Ocean":     {"bg": "EFF6FF", "text": "1E3A8A", "muted": "1D4ED8", "accent": "3B82F6", "heading_font": "Inter", "body_font": "Inter"},
    "Mint":      {"bg": "F0FDF4", "text": "14532D", "muted": "16A34A", "accent": "10B981", "heading_font": "Inter", "body_font": "Inter"},
    "Berry":     {"bg": "FAF5FF", "text": "581C87", "muted": "7E22CE", "accent": "A855F7", "heading_font": "Playfair Display", "body_font": "Inter"},
    "Slate":     {"bg": "F8FAFC", "text": "0F172A", "muted": "64748B", "accent": "475569", "heading_font": "Inter", "body_font": "Inter"},
    "Lemon":     {"bg": "FEFCE8", "text": "713F12", "muted": "A16207", "accent": "EAB308", "heading_font": "Poppins", "body_font": "Inter"},
    "Lavender":  {"bg": "F5F3FF", "text": "4C1D95", "muted": "7C3AED", "accent": "8B5CF6", "heading_font": "Playfair Display", "body_font": "Inter"},
    "Sand":      {"bg": "FAF7F2", "text": "57452A", "muted": "8B7355", "accent": "B45309", "heading_font": "Merriweather", "body_font": "Inter"},
    "Linen":     {"bg": "FAF6F1", "text": "44403C", "muted": "78716C", "accent": "0F766E", "heading_font": "Playfair Display", "body_font": "EB Garamond"},
    "Mist":      {"bg": "F1F5F9", "text": "1E293B", "muted": "64748B", "accent": "0EA5E9", "heading_font": "Inter", "body_font": "Inter"},
    "Cerulean":  {"bg": "F0F9FF", "text": "0C4A6E", "muted": "0369A1", "accent": "0284C7", "heading_font": "Inter", "body_font": "Inter"},
    "Arctic":    {"bg": "F8FAFC", "text": "0F172A", "muted": "94A3B8", "accent": "0EA5E9", "heading_font": "Inter", "body_font": "Inter"},
    "Amber":     {"bg": "FFFBEB", "text": "78350F", "muted": "B45309", "accent": "F59E0B", "heading_font": "Merriweather", "body_font": "Inter"},
    "Multi":     {"bg": "FFFFFF", "text": "0F172A", "muted": "64748B", "accent": "8B5CF6", "heading_font": "Inter", "body_font": "Inter"},

    # ── Special / Manus reference ─────────────────────────────────────────
    "Monument":  {"bg": "F5F0E8", "text": "2C1810", "muted": "8B6F47", "accent": "8B0000", "heading_font": "Cinzel", "body_font": "EB Garamond"},

    # ── User-spec additions (HONEST_STATUS round 3) ───────────────────────
    "Ember":     {"bg": "1C1917", "text": "FAFAF9", "muted": "A8A29E", "accent": "EA580C", "heading_font": "Montserrat", "body_font": "Inter"},
    "Ivory":     {"bg": "FFFFF0", "text": "1A1A1A", "muted": "6B6B5A", "accent": "B8860B", "heading_font": "Playfair Display", "body_font": "EB Garamond"},
    "Sage":      {"bg": "F7FDF7", "text": "1A2E1A", "muted": "86A886", "accent": "059669", "heading_font": "Merriweather", "body_font": "Inter"},
    "Copper":    {"bg": "1C1210", "text": "FAF5F0", "muted": "B8A090", "accent": "B87333", "heading_font": "Playfair Display", "body_font": "Inter"},
    "Royal":     {"bg": "1A0A2E", "text": "F5F0FF", "muted": "9B8BC4", "accent": "7C3AED", "heading_font": "Playfair Display", "body_font": "Inter"},
    "Terracotta":{"bg": "2C1A10", "text": "FFF5EB", "muted": "C4A080", "accent": "C2452D", "heading_font": "Merriweather", "body_font": "Inter"},
    "Chrome":    {"bg": "F4F4F5", "text": "18181B", "muted": "A1A1AA", "accent": "3F3F46", "heading_font": "Inter", "body_font": "Inter"},
}


def _palette_for(theme: str) -> dict[str, str]:
    """Look up a theme palette case-insensitively. Falls back to Minimal."""
    if not theme:
        return THEMES["Minimal"]
    if theme in THEMES:
        return THEMES[theme]
    lower = theme.lower()
    for k, v in THEMES.items():
        if k.lower() == lower:
            return v
    logger.warning("export.theme_unknown_using_minimal", extra={"theme": theme})
    return THEMES["Minimal"]


def _hex_to_rgb(hex_str: str) -> RGBColor:
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class ExportService:
    def __init__(self, storage: StorageService | None = None) -> None:
        self.storage = storage or StorageService()

    # ── public ────────────────────────────────────────────────────────────
    async def export_pptx(
        self, task_id: str, slides: list[dict[str, Any]], theme: str
    ) -> tuple[str, int]:
        return await asyncio.to_thread(self._export_pptx_sync, task_id, slides, theme)

    async def export_pdf(
        self, task_id: str, slides: list[dict[str, Any]], theme: str
    ) -> tuple[str, int]:
        return await asyncio.to_thread(self._export_pdf_sync, task_id, slides, theme)

    # ── pptx ──────────────────────────────────────────────────────────────
    def _export_pptx_sync(
        self, task_id: str, slides: list[dict[str, Any]], theme: str
    ) -> tuple[str, int]:
        palette = _palette_for(theme)
        prs = Presentation()
        prs.slide_width = SLIDE_W
        prs.slide_height = SLIDE_H

        for slide in slides:
            self._render_slide(prs, slide, palette)

        buf = io.BytesIO()
        prs.save(buf)
        data = buf.getvalue()
        filename = f"{task_id}.pptx"
        url = self.storage.put(
            filename,
            data,
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        logger.info("export.pptx_ok", extra={"task_id": task_id, "size": len(data)})
        return url, len(data)

    def _render_slide(
        self, prs: Presentation, slide: dict[str, Any], palette: dict[str, str]
    ) -> None:
        layout = (slide.get("layout") or "title").lower()
        # Per-slide profile overrides (font_pair, accent) stamped by the agent
        # loop. Allows the same theme to render Cinzel for a history deck and
        # Orbitron for a tech deck without changing the theme name.
        heading_font = (
            (slide.get("_font_heading") or "").strip()
            or palette.get("heading_font")
            or _DEF_HEAD
        )
        body_font = (
            (slide.get("_font_body") or "").strip()
            or palette.get("body_font")
            or _DEF_BODY
        )
        accent_override = str(slide.get("_accent_override") or "").lstrip("#")
        palette = {
            **palette,
            "heading_font": heading_font,
            "body_font": body_font,
        }
        if len(accent_override) == 6:
            palette["accent"] = accent_override
        # Stash on instance so _add_text (called in many places) can read it
        # without forcing a signature change at every call site.
        self._cur_palette = palette
        s = prs.slides.add_slide(prs.slide_layouts[6])  # blank
        self._add_background(s, palette["bg"])

        # Hero image (best-effort; never blocks export).
        image_bytes = self._fetch_image(slide.get("image_url"))
        if image_bytes:
            if layout in ("closing", "section"):
                # Full-bleed with semi-transparent dark scrim.
                s.shapes.add_picture(
                    io.BytesIO(image_bytes), 0, 0, width=SLIDE_W, height=SLIDE_H
                )
                scrim = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
                scrim.line.fill.background()
                scrim.fill.solid()
                scrim.fill.fore_color.rgb = _hex_to_rgb(palette["bg"])
                scrim.fill.transparency = 0.35
                scrim.shadow.inherit = False
            elif layout in ("bullets", "two-col"):
                # Right-side panel covering ~38% of the width.
                pic_w = Inches(5.0)
                s.shapes.add_picture(
                    io.BytesIO(image_bytes),
                    SLIDE_W - pic_w,
                    0,
                    width=pic_w,
                    height=SLIDE_H,
                )
            # NOTE: title layout owns its own image placement (right panel)
            # via _render_title's split-screen composition.

        if layout == "title":
            self._render_title(s, slide, palette, image_bytes=image_bytes)
        elif layout == "section":
            self._render_section(s, slide, palette, image_bytes=image_bytes)
        elif layout == "bullets":
            self._render_bullets(s, slide, palette, has_image=bool(image_bytes))
        elif layout == "two-col":
            self._render_two_col(s, slide, palette, has_image=bool(image_bytes))
        elif layout == "comparison":
            self._render_comparison(s, slide, palette)
        elif layout == "kpi":
            self._render_kpi(s, slide, palette)
        elif layout == "quote":
            self._render_quote(s, slide, palette)
        elif layout == "stats":
            self._render_stats(s, slide, palette)
        elif layout == "chart":
            self._render_chart(s, slide, palette)
        elif layout == "timeline":
            self._render_timeline(s, slide, palette)
        elif layout == "closing":
            self._render_closing(s, slide, palette)
        elif layout == "hero":
            self._render_hero(s, slide, palette, image_bytes=image_bytes)
        elif layout == "bento":
            self._render_bento(s, slide, palette)
        elif layout == "agenda":
            self._render_agenda(s, slide, palette)
        elif layout == "roadmap":
            self._render_roadmap(s, slide, palette)
        elif layout == "metric-spotlight":
            self._render_metric_spotlight(s, slide, palette)
        elif layout == "process":
            self._render_process(s, slide, palette)
        elif layout == "pyramid":
            self._render_pyramid(s, slide, palette)
        elif layout == "matrix-2x2":
            self._render_matrix_2x2(s, slide, palette)
        elif layout == "feature-grid":
            self._render_feature_grid(s, slide, palette)
        elif layout == "callout":
            self._render_callout(s, slide, palette)
        else:
            self._render_title(s, slide, palette)

    @staticmethod
    def _fetch_image(url: str | None) -> bytes | None:
        if not url:
            return None
        # Pollinations can rate-limit (429) on bursts. Retry with light backoff.
        delays = [0.0, 1.5, 3.5]
        for attempt, delay in enumerate(delays):
            if delay:
                import time as _t

                _t.sleep(delay)
            try:
                with httpx.Client(timeout=25.0, follow_redirects=True) as client:
                    r = client.get(url)
                if r.status_code == 429 and attempt < len(delays) - 1:
                    continue
                r.raise_for_status()
                ct = r.headers.get("content-type", "")
                if not ct.startswith("image/"):
                    return None
                return r.content
            except Exception as exc:
                if attempt == len(delays) - 1:
                    logger.warning(
                        "export.image_fetch_failed",
                        extra={"err": str(exc), "url": url[:120]},
                    )
        return None

    @staticmethod
    def _quickchart_url(slide: dict[str, Any], p: dict[str, str]) -> str:
        """Build a QuickChart.io URL that renders a Chart.js config to PNG."""
        import json as _json
        from urllib.parse import quote as _quote

        # Prefer the renderer-ready envelope produced by chart_service.
        envelope = slide.get("chart") if isinstance(slide.get("chart"), dict) else None
        if envelope and envelope.get("chartjs_config"):
            cfg = envelope["chartjs_config"]
            chart_type = str(cfg.get("type") or "bar").lower()
            if chart_type not in {"bar", "line", "doughnut", "pie", "scatter"}:
                chart_type = "bar"
            payload = _json.dumps(cfg, separators=(",", ":"))
            return (
                "https://quickchart.io/chart"
                f"?c={_quote(payload)}&backgroundColor=transparent&w=1100&h=520"
            )

        cd = slide.get("chart_data") or {}
        labels = cd.get("labels") or []
        values = cd.get("values") or []
        unit = cd.get("unit") or ""
        chart_type = (slide.get("chart_type") or "bar").lower()
        if chart_type not in {"bar", "line", "doughnut"}:
            chart_type = "bar"

        accent = f"#{p['accent']}"
        muted = f"#{p['muted']}"
        is_light = p.get("bg", "").upper().startswith("FFF") or p.get("bg", "").upper().startswith("FAF")
        grid_color = "rgba(0,0,0,0.08)" if is_light else "rgba(255,255,255,0.10)"
        tick_color = muted

        if chart_type == "doughnut":
            doughnut_palette = [accent, "#34D399", "#60A5FA", "#F472B6", "#FBBF24", "#A78BFA"]
            bg_colors = doughnut_palette[: len(labels)] or [accent]
            datasets = [
                {
                    "data": values,
                    "backgroundColor": bg_colors,
                    "borderWidth": 0,
                }
            ]
        else:
            datasets = [
                {
                    "label": f"Value ({unit})" if unit else "Value",
                    "data": values,
                    "backgroundColor": accent + "CC",
                    "borderColor": accent,
                    "borderWidth": 2,
                    "fill": chart_type == "line",
                    "tension": 0.35,
                }
            ]

        scales = {} if chart_type == "doughnut" else {
            "x": {"grid": {"color": grid_color}, "ticks": {"color": tick_color}},
            "y": {
                "grid": {"color": grid_color},
                "ticks": {"color": tick_color},
                "beginAtZero": True,
            },
        }

        config = {
            "type": chart_type,
            "data": {"labels": labels, "datasets": datasets},
            "options": {
                "plugins": {"legend": {"display": chart_type == "doughnut"}},
                "scales": scales,
            },
        }
        encoded = _quote(_json.dumps(config, ensure_ascii=False), safe="")
        # White background so the PNG looks correct on light themes; transparent
        # would be ideal but QuickChart uses white by default.
        return (
            f"https://quickchart.io/chart?w=900&h=420&bkg=transparent&c={encoded}"
        )

    @staticmethod
    def _add_background(slide, hex_color: str) -> None:
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
        shape.line.fill.background()
        shape.fill.solid()
        shape.fill.fore_color.rgb = _hex_to_rgb(hex_color)
        shape.shadow.inherit = False

    def _add_text(
        self,
        slide,
        text: str,
        left: int,
        top: int,
        width: int,
        height: int,
        *,
        size: int,
        color: str,
        bold: bool = False,
        align: str = "left",
        italic: bool = False,
        font_name: str | None = None,
    ):
        from pptx.enum.text import PP_ALIGN

        # Pick heading vs body font from the current palette unless the caller
        # forces a specific font_name. Heuristic: bold + size >= 22 is a
        # heading; everything else is body.
        if not font_name:
            pal = getattr(self, "_cur_palette", None) or {}
            if bold and size >= 22:
                font_name = pal.get("heading_font") or _DEF_HEAD
            else:
                font_name = pal.get("body_font") or _DEF_BODY

        tb = slide.shapes.add_textbox(left, top, width, height)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Pt(0)
        tf.margin_top = tf.margin_bottom = Pt(0)
        tf.text = text or ""
        for para in tf.paragraphs:
            para.alignment = {
                "left": PP_ALIGN.LEFT,
                "center": PP_ALIGN.CENTER,
                "right": PP_ALIGN.RIGHT,
            }.get(align, PP_ALIGN.LEFT)
            for run in para.runs:
                run.font.size = Pt(size)
                run.font.bold = bold
                run.font.italic = italic
                run.font.color.rgb = _hex_to_rgb(color)
                run.font.name = font_name
        return tb

    def _render_title(
        self,
        slide,
        data: dict[str, Any],
        p: dict[str, str],
        *,
        image_bytes: bytes | None = None,
    ) -> None:
        # Manus-style split-screen: text column on the left (~58% wide),
        # vivid accent panel with a stylized disc on the right (~42% wide).
        left_w = Inches(7.7)   # 58% of 13.333"
        right_x = left_w
        right_w = SLIDE_W - left_w

        # Right panel: solid accent fill
        panel = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, right_x, 0, right_w, SLIDE_H)
        panel.line.fill.background()
        panel.fill.solid()
        panel.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
        panel.shadow.inherit = False

        # Optional image inside the right panel (clipped to the panel rect).
        if image_bytes:
            slide.shapes.add_picture(
                io.BytesIO(image_bytes),
                right_x,
                0,
                width=right_w,
                height=SLIDE_H,
            )
            # Soft tint so the panel still reads as the accent color.
            tint = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, right_x, 0, right_w, SLIDE_H
            )
            tint.line.fill.background()
            tint.fill.solid()
            tint.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
            tint.fill.transparency = 0.55
            tint.shadow.inherit = False

        # Stylized disc in the center of the right panel.
        disc_size = Inches(3.4)
        disc_x = right_x + (right_w - disc_size) / 2
        disc_y = (SLIDE_H - disc_size) / 2
        disc = slide.shapes.add_shape(MSO_SHAPE.OVAL, disc_x, disc_y, disc_size, disc_size)
        disc.fill.solid()
        # Slightly lighter than the accent so it reads as a sun-like glow.
        disc.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
        disc.line.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        disc.line.width = Pt(2)
        disc.shadow.inherit = False

        # Center glyph on the disc.
        self._add_text(
            slide, "\u2726",
            disc_x, disc_y, disc_size, disc_size,
            size=56, color="#FFFFFF", bold=True, align="center",
        )

        # LEFT — eyebrow / title / subtitle / footer
        eyebrow = (data.get("eyebrow") or "Presentation").upper()
        self._add_text(
            slide, eyebrow,
            Inches(0.9), Inches(0.8), Inches(6.6), Inches(0.4),
            size=11, color=p["muted"], bold=True,
        )

        # Title split into two stacked lines (second line in accent color).
        full_title = (data.get("title") or "").strip()
        words = full_title.split()
        split_idx = max(1, (len(words) + 1) // 2) if len(words) > 1 else 1
        title_top = " ".join(words[:split_idx])
        title_bottom = " ".join(words[split_idx:])

        self._add_text(
            slide, title_top.upper(),
            Inches(0.9), Inches(2.6), Inches(6.6), Inches(1.2),
            size=54, color=p["text"], bold=True,
        )
        if title_bottom:
            self._add_text(
                slide, title_bottom.upper(),
                Inches(0.9), Inches(3.7), Inches(6.6), Inches(1.2),
                size=54, color=p["accent"], bold=True,
            )

        if data.get("subtitle"):
            self._add_text(
                slide, data["subtitle"],
                Inches(0.9), Inches(5.1), Inches(6.6), Inches(1.4),
                size=16, color=p["muted"],
            )

        self._add_text(
            slide, "POWERED BY NEXUS",
            Inches(0.9), Inches(6.7), Inches(6.6), Inches(0.4),
            size=9, color=p["muted"], bold=True,
        )

    def _render_bullets(
        self,
        slide,
        data: dict[str, Any],
        p: dict[str, str],
        *,
        has_image: bool = False,
    ) -> None:
        text_w = Inches(7.0) if has_image else Inches(11.7)
        bullet_text_w = Inches(6.5) if has_image else Inches(11.3)
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.6), text_w, Inches(1.0),
            size=32, color=p["text"], bold=True,
        )
        bullets: Iterable[str] = data.get("bullets") or []
        y = 2.0
        for b in bullets:
            self._add_text(
                slide, "•",
                Inches(0.8), Inches(y), Inches(0.4), Inches(0.6),
                size=20, color=p["accent"], bold=True,
            )
            self._add_text(
                slide, str(b),
                Inches(1.3), Inches(y), bullet_text_w, Inches(0.9),
                size=18, color=p["text"],
            )
            y += 1.05

    def _render_two_col(
        self,
        slide,
        data: dict[str, Any],
        p: dict[str, str],
        *,
        has_image: bool = False,
    ) -> None:
        title_w = Inches(7.0) if has_image else Inches(11.7)
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.6), title_w, Inches(1.0),
            size=32, color=p["text"], bold=True,
        )
        cols = (data.get("columns") or [])[:2]
        if has_image:
            col_w = Inches(7.0)
            for i, c in enumerate(cols):
                y = 2.0 + i * 2.6
                self._add_text(
                    slide, (c.get("heading") or "").strip(),
                    Inches(0.8), Inches(y), col_w, Inches(0.6),
                    size=18, color=p["accent"], bold=True,
                )
                self._add_text(
                    slide, (c.get("body") or "").strip(),
                    Inches(0.8), Inches(y + 0.7), col_w, Inches(1.8),
                    size=15, color=p["text"],
                )
            return
        col_w = Inches(5.6)
        for i, c in enumerate(cols):
            x = Inches(0.8 + i * 6.0)
            self._add_text(
                slide, (c.get("heading") or "").strip(),
                x, Inches(2.0), col_w, Inches(0.6),
                size=18, color=p["accent"], bold=True,
            )
            self._add_text(
                slide, (c.get("body") or "").strip(),
                x, Inches(2.7), col_w, Inches(4.2),
                size=15, color=p["text"],
            )

    def _render_quote(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, "“",
            Inches(1), Inches(1.6), Inches(11.3), Inches(1.5),
            size=72, color=p["accent"], bold=True, align="center",
        )
        self._add_text(
            slide, data.get("quote") or data.get("title", ""),
            Inches(1.5), Inches(3.0), Inches(10.3), Inches(2.4),
            size=28, color=p["text"], italic=True, align="center",
        )
        if data.get("attribution"):
            self._add_text(
                slide, f"— {data['attribution']}",
                Inches(1.5), Inches(5.6), Inches(10.3), Inches(0.6),
                size=14, color=p["muted"], align="center",
            )

    def _render_stats(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
            size=32, color=p["text"], bold=True,
        )
        stats = (data.get("stats") or [])[:3]
        gap = 0.4
        col_w = (13.333 - 1.6 - 2 * gap) / 3
        for i, s in enumerate(stats):
            x = Inches(0.8 + i * (col_w + gap))
            self._add_text(
                slide, str(s.get("value", "")),
                x, Inches(2.6), Inches(col_w), Inches(1.6),
                size=56, color=p["accent"], bold=True, align="center",
            )
            self._add_text(
                slide, str(s.get("label", "")),
                x, Inches(4.4), Inches(col_w), Inches(0.8),
                size=14, color=p["muted"], align="center",
            )

    def _render_chart(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        # Title + optional subtitle
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.8),
            size=30, color=p["text"], bold=True,
        )
        if data.get("subtitle"):
            self._add_text(
                slide, data["subtitle"],
                Inches(0.8), Inches(1.3), Inches(11.7), Inches(0.5),
                size=14, color=p["muted"],
            )

        # Prefer the renderer-ready envelope produced by chart_service.
        envelope = data.get("chart") if isinstance(data.get("chart"), dict) else None
        pptx_config = envelope.get("pptx_config") if envelope else None

        if pptx_config:
            labels = list(pptx_config.get("categories") or [])
            series_specs = list(pptx_config.get("series") or [])
            unit = pptx_config.get("unit") or ""
            source = envelope.get("source") or ""
            chart_type_raw = (envelope.get("type") or "bar").lower()
            xl_type = self._xl_type_for(pptx_config.get("xl_chart_type"), chart_type_raw)
            show_legend = bool(pptx_config.get("show_legend"))
            palette = list(pptx_config.get("palette") or [])
        else:
            cd = data.get("chart_data") or {}
            labels = cd.get("labels") or []
            primary_values = cd.get("values") or []
            unit = cd.get("unit") or ""
            source = cd.get("source") or ""
            chart_type_raw = (data.get("chart_type") or "bar").lower()
            xl_type = self._xl_type_for(None, chart_type_raw)
            series_specs = (
                [{"label": f"Value ({unit})" if unit else "Value", "values": primary_values}]
                if primary_values
                else []
            )
            show_legend = chart_type_raw in {"doughnut", "pie"}
            palette = []

        if not labels or not series_specs or not series_specs[0].get("values"):
            self._add_text(
                slide, "No chart data",
                Inches(0.8), Inches(3.5), Inches(11.7), Inches(0.6),
                size=14, color=p["muted"], align="center",
            )
            return

        chart_data = CategoryChartData()
        chart_data.categories = [str(x) for x in labels]
        for spec in series_specs:
            chart_data.add_series(
                str(spec.get("label") or "Value"),
                [float(v) for v in (spec.get("values") or [])],
            )

        # Chart frame: leaves room for source line at the bottom.
        chart_x = Inches(0.8)
        chart_y = Inches(2.0)
        chart_w = Inches(11.7)
        chart_h = Inches(4.6)
        graphic = slide.shapes.add_chart(
            xl_type, chart_x, chart_y, chart_w, chart_h, chart_data
        )
        chart = graphic.chart

        # Style: hide legend for single-series bar/line, keep for share charts.
        if show_legend or len(series_specs) > 1:
            chart.has_legend = True
            chart.legend.position = XL_LEGEND_POSITION.RIGHT
            chart.legend.include_in_layout = False
        else:
            chart.has_legend = False

        # Color the series with the theme accent / palette.
        try:
            for i, series in enumerate(chart.series):
                color_hex = (
                    series_specs[i].get("color")
                    if i < len(series_specs) and series_specs[i].get("color")
                    else (palette[i % len(palette)] if palette else f"#{p['accent']}")
                )
                color_hex = str(color_hex).lstrip("#")
                rgb = _hex_to_rgb(color_hex)
                fill = series.format.fill
                fill.solid()
                fill.fore_color.rgb = rgb
                line = series.format.line
                line.color.rgb = rgb
        except Exception:  # pragma: no cover - defensive
            pass

        # Source / unit caption.
        caption_parts = []
        if unit:
            caption_parts.append(f"Units: {unit}")
        if source:
            caption_parts.append(f"Source: {source}")
        if caption_parts:
            self._add_text(
                slide, "    \u2022    ".join(caption_parts),
                Inches(0.8), Inches(6.7), Inches(11.7), Inches(0.4),
                size=11, color=p["muted"],
            )

    @staticmethod
    def _xl_type_for(xl_name: str | None, chart_type: str) -> "XL_CHART_TYPE":
        name_map = {
            "COLUMN_CLUSTERED": XL_CHART_TYPE.COLUMN_CLUSTERED,
            "LINE": XL_CHART_TYPE.LINE,
            "PIE": XL_CHART_TYPE.PIE,
            "DOUGHNUT": XL_CHART_TYPE.DOUGHNUT,
            "AREA": XL_CHART_TYPE.AREA,
            "XY_SCATTER": XL_CHART_TYPE.XY_SCATTER,
        }
        if xl_name and xl_name in name_map:
            return name_map[xl_name]
        type_map = {
            "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
            "line": XL_CHART_TYPE.LINE,
            "pie": XL_CHART_TYPE.PIE,
            "doughnut": XL_CHART_TYPE.DOUGHNUT,
            "area": XL_CHART_TYPE.AREA,
            "scatter": XL_CHART_TYPE.XY_SCATTER,
        }
        return type_map.get(chart_type, XL_CHART_TYPE.COLUMN_CLUSTERED)

    def _render_section(
        self,
        slide,
        data: dict[str, Any],
        p: dict[str, str],
        *,
        image_bytes: bytes | None = None,
    ) -> None:
        # Big number on the left, eyebrow + title stacked on the right.
        number = (data.get("section_number") or "").strip()
        if number:
            self._add_text(
                slide, number,
                Inches(0.6), Inches(2.0), Inches(3.5), Inches(3.5),
                size=180, color=p["accent"], bold=True, align="center",
            )
            text_x = Inches(4.5)
            text_w = Inches(8.0)
        else:
            text_x = Inches(1.2)
            text_w = Inches(11.0)

        eyebrow = (data.get("eyebrow") or "Section").upper()
        self._add_text(
            slide, eyebrow,
            text_x, Inches(2.6), text_w, Inches(0.5),
            size=14, color=p["accent"], bold=True,
        )
        self._add_text(
            slide, (data.get("title") or "").upper(),
            text_x, Inches(3.2), text_w, Inches(2.0),
            size=48, color=p["text"], bold=True,
        )
        if data.get("subtitle"):
            self._add_text(
                slide, data["subtitle"],
                text_x, Inches(5.4), text_w, Inches(1.4),
                size=16, color=p["muted"],
            )

    def _render_kpi(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.6), Inches(11.7), Inches(0.9),
            size=30, color=p["text"], bold=True,
        )
        if data.get("subtitle"):
            self._add_text(
                slide, data["subtitle"],
                Inches(0.8), Inches(1.4), Inches(11.7), Inches(0.5),
                size=14, color=p["muted"],
            )
        kpis = (data.get("kpis") or [])[:4]
        if not kpis:
            self._add_text(
                slide, "No KPI data",
                Inches(0.8), Inches(3.5), Inches(11.7), Inches(0.6),
                size=14, color=p["muted"], align="center",
            )
            return
        n = len(kpis)
        gap = 0.3
        margin = 0.8
        avail = 13.333 - 2 * margin - (n - 1) * gap
        col_w = avail / n
        card_top = 2.4
        card_h = 4.2
        for i, k in enumerate(kpis):
            x_in = margin + i * (col_w + gap)
            x = Inches(x_in)
            w = Inches(col_w)
            # Card background
            card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(card_top), w, Inches(card_h)
            )
            card.line.color.rgb = _hex_to_rgb(p["accent"])
            card.line.width = Pt(1)
            card.fill.solid()
            card.fill.fore_color.rgb = _hex_to_rgb(p["bg"])
            card.shadow.inherit = False

            # Big value
            self._add_text(
                slide, str(k.get("value", "")),
                x, Inches(card_top + 0.4), w, Inches(1.6),
                size=48, color=p["accent"], bold=True, align="center",
            )
            # Delta (with arrow if direction set)
            delta = str(k.get("delta", "")).strip()
            direction = str(k.get("direction", "")).strip().lower()
            if delta:
                arrow = (
                    "\u25B2 " if direction in ("up", "positive", "increase")
                    else "\u25BC " if direction in ("down", "negative", "decrease")
                    else ""
                )
                self._add_text(
                    slide, f"{arrow}{delta}",
                    x, Inches(card_top + 2.0), w, Inches(0.5),
                    size=14, color=p["accent"] if direction != "down" else p["muted"],
                    bold=True, align="center",
                )
            # Label
            self._add_text(
                slide, str(k.get("label", "")).upper(),
                x, Inches(card_top + 2.6), w, Inches(0.6),
                size=12, color=p["text"], bold=True, align="center",
            )
            # Sublabel
            sub = str(k.get("sublabel", "")).strip()
            if sub:
                self._add_text(
                    slide, sub,
                    x, Inches(card_top + 3.2), w, Inches(0.8),
                    size=11, color=p["muted"], align="center",
                )

    def _render_comparison(
        self, slide, data: dict[str, Any], p: dict[str, str]
    ) -> None:
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
            size=30, color=p["text"], bold=True,
        )
        items = (data.get("items") or [])[:2]
        if len(items) < 2:
            # Fallback: render whatever is present as a single column.
            for i, c in enumerate(items):
                self._add_text(
                    slide, c.get("heading", ""),
                    Inches(0.8), Inches(2.0 + i * 2.4), Inches(11.7), Inches(0.6),
                    size=20, color=p["accent"], bold=True,
                )
                self._add_text(
                    slide, c.get("body", ""),
                    Inches(0.8), Inches(2.7 + i * 2.4), Inches(11.7), Inches(1.6),
                    size=15, color=p["text"],
                )
            return

        col_w_in = 5.6
        gap_in = 0.5
        left_x = Inches(0.8)
        right_x = Inches(0.8 + col_w_in + gap_in)
        col_w = Inches(col_w_in)
        card_top = 2.0
        card_h = 4.6

        # Two cards side by side.
        for i, (x, c) in enumerate(((left_x, items[0]), (right_x, items[1]))):
            border_color = p["accent"] if i == 0 else p["muted"]
            card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(card_top), col_w, Inches(card_h)
            )
            card.line.color.rgb = _hex_to_rgb(border_color)
            card.line.width = Pt(2 if i == 0 else 1)
            card.fill.solid()
            card.fill.fore_color.rgb = _hex_to_rgb(p["bg"])
            card.shadow.inherit = False

            self._add_text(
                slide, str(c.get("heading", "")).upper(),
                x, Inches(card_top + 0.3), col_w, Inches(0.6),
                size=20, color=p["accent"] if i == 0 else p["text"],
                bold=True, align="center",
            )
            sub = str(c.get("subtitle", "")).strip()
            if sub:
                self._add_text(
                    slide, sub,
                    x, Inches(card_top + 0.95), col_w, Inches(0.5),
                    size=12, color=p["muted"], align="center",
                )
            points = c.get("points") or []
            y = card_top + 1.6
            for pt in points[:4]:
                self._add_text(
                    slide, "\u2022",
                    Inches(x.inches + 0.35), Inches(y),
                    Inches(0.3), Inches(0.6),
                    size=16, color=p["accent"], bold=True,
                )
                self._add_text(
                    slide, str(pt),
                    Inches(x.inches + 0.7), Inches(y),
                    Inches(col_w_in - 0.9), Inches(0.7),
                    size=13, color=p["text"],
                )
                y += 0.7
            if not points and c.get("body"):
                self._add_text(
                    slide, str(c["body"]),
                    Inches(x.inches + 0.4), Inches(card_top + 1.6),
                    Inches(col_w_in - 0.8), Inches(2.6),
                    size=13, color=p["text"],
                )

        # Center "vs" badge.
        divider = (data.get("divider") or "vs").strip().upper()
        badge_size = Inches(1.0)
        badge_x = Inches(0.8 + col_w_in + (gap_in - 1.0) / 2)
        badge_y = Inches(card_top + (card_h - 1.0) / 2)
        badge = slide.shapes.add_shape(
            MSO_SHAPE.OVAL, badge_x, badge_y, badge_size, badge_size
        )
        badge.fill.solid()
        badge.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
        badge.line.fill.background()
        badge.shadow.inherit = False
        self._add_text(
            slide, divider,
            badge_x, badge_y, badge_size, badge_size,
            size=18, color="FFFFFF", bold=True, align="center",
        )

    def _render_timeline(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
            size=30, color=p["text"], bold=True,
        )
        events = (data.get("events") or [])[:5]
        if not events:
            self._add_text(
                slide, "No timeline data",
                Inches(0.8), Inches(3.5), Inches(11.7), Inches(0.6),
                size=14, color=p["muted"], align="center",
            )
            return

        n = len(events)
        margin = 0.8
        avail = 13.333 - 2 * margin
        step = avail / max(n - 1, 1) if n > 1 else 0
        track_y = 4.1
        # Horizontal track line.
        track = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(margin),
            Inches(track_y),
            Inches(avail),
            Pt(2),
        )
        track.line.fill.background()
        track.fill.solid()
        track.fill.fore_color.rgb = _hex_to_rgb(p["muted"])
        track.shadow.inherit = False

        node_size = Inches(0.45)
        col_w_in = min(2.6, avail / max(n, 1))
        for i, e in enumerate(events):
            cx_in = margin + (step * i if n > 1 else avail / 2)
            cx = Inches(cx_in)
            # Node
            node_x = Inches(cx_in - node_size.inches / 2)
            node_y = Inches(track_y - node_size.inches / 2 + 0.01)
            node = slide.shapes.add_shape(
                MSO_SHAPE.OVAL, node_x, node_y, node_size, node_size
            )
            node.fill.solid()
            node.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
            node.line.color.rgb = _hex_to_rgb(p["bg"])
            node.line.width = Pt(2)
            node.shadow.inherit = False

            # Label position alternates above/below the track.
            text_x = Inches(max(margin, cx_in - col_w_in / 2))
            text_w = Inches(col_w_in)
            above = i % 2 == 0
            year_y = 2.2 if above else 4.7
            title_y = 2.7 if above else 5.2
            desc_y = 3.1 if above else 5.6
            self._add_text(
                slide, str(e.get("year", "")),
                text_x, Inches(year_y), text_w, Inches(0.45),
                size=14, color=p["accent"], bold=True, align="center",
            )
            self._add_text(
                slide, str(e.get("title", "")),
                text_x, Inches(title_y), text_w, Inches(0.4),
                size=13, color=p["text"], bold=True, align="center",
            )
            desc = str(e.get("desc", "")).strip()
            if desc:
                self._add_text(
                    slide, desc,
                    text_x, Inches(desc_y), text_w, Inches(1.0),
                    size=10, color=p["muted"], align="center",
                )

    # ── New visual-diversity layouts (HONEST_STATUS round 4) ───────────────
    def _render_hero(
        self,
        slide,
        data: dict[str, Any],
        p: dict[str, str],
        *,
        image_bytes: bytes | None = None,
    ) -> None:
        # Vertical accent strip on the far left + oversize title.
        strip = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), Inches(0.8), Inches(0.18), Inches(5.9)
        )
        strip.line.fill.background()
        strip.fill.solid()
        strip.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
        strip.shadow.inherit = False
        self._add_text(
            slide, str(data.get("eyebrow") or "INTRODUCING").upper(),
            Inches(0.7), Inches(1.0), Inches(11.0), Inches(0.5),
            size=12, color=p["accent"], bold=True,
        )
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.7), Inches(1.7), Inches(11.5), Inches(2.6),
            size=64, color=p["text"], bold=True,
        )
        if data.get("subtitle"):
            self._add_text(
                slide, data["subtitle"],
                Inches(0.7), Inches(4.5), Inches(11.5), Inches(1.4),
                size=22, color=p["muted"],
            )

    def _render_bento(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.9),
            size=30, color=p["text"], bold=True,
        )
        # Pull cards from `bullets` (split on ":") OR `stats` OR `columns`.
        raw = data.get("bullets") or []
        cards: list[dict[str, str]] = []
        if raw:
            for b in raw[:6]:
                txt = str(b)
                if ":" in txt:
                    h, body = txt.split(":", 1)
                    cards.append({"head": h.strip(), "body": body.strip()})
                else:
                    cards.append({"head": "", "body": txt.strip()})
        elif data.get("stats"):
            for s in (data.get("stats") or [])[:6]:
                cards.append({"head": str(s.get("value", "")), "body": str(s.get("label", ""))})
        cards = cards[:6]
        cols, rows = 3, 2
        margin, gap = 0.8, 0.25
        avail_w = 13.333 - 2 * margin - (cols - 1) * gap
        col_w = avail_w / cols
        avail_h = 5.4
        card_h = (avail_h - (rows - 1) * gap) / rows
        top0 = 1.6
        for i, c in enumerate(cards):
            row, col = divmod(i, cols)
            x = Inches(margin + col * (col_w + gap))
            y = Inches(top0 + row * (card_h + gap))
            w, h = Inches(col_w), Inches(card_h)
            shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
            shp.line.color.rgb = _hex_to_rgb(p["muted"])
            shp.line.width = Pt(0.75)
            shp.fill.solid()
            shp.fill.fore_color.rgb = _hex_to_rgb(p["bg"])
            shp.shadow.inherit = False
            if c["head"]:
                self._add_text(
                    slide, c["head"],
                    x, Inches(top0 + row * (card_h + gap) + 0.3),
                    w, Inches(0.7),
                    size=22, color=p["accent"], bold=True, align="center",
                )
                self._add_text(
                    slide, c["body"],
                    x, Inches(top0 + row * (card_h + gap) + 1.1),
                    w, Inches(card_h - 1.3),
                    size=12, color=p["text"], align="center",
                )
            else:
                self._add_text(
                    slide, c["body"],
                    x, Inches(top0 + row * (card_h + gap) + 0.4),
                    w, Inches(card_h - 0.6),
                    size=14, color=p["text"], align="center",
                )

    def _render_agenda(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", "Agenda"),
            Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.0),
            size=36, color=p["text"], bold=True,
        )
        items = list(data.get("bullets") or [])[:6]
        y = 2.0
        for i, it in enumerate(items, 1):
            self._add_text(
                slide, f"{i:02d}",
                Inches(0.8), Inches(y), Inches(1.2), Inches(0.8),
                size=44, color=p["accent"], bold=True,
            )
            self._add_text(
                slide, str(it),
                Inches(2.2), Inches(y + 0.15), Inches(10.3), Inches(0.7),
                size=20, color=p["text"],
            )
            y += 0.85

    def _render_roadmap(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.9),
            size=28, color=p["text"], bold=True,
        )
        raw = data.get("bullets") or [s.get("label", "") for s in (data.get("stats") or [])]
        stages: list[dict[str, str]] = []
        for b in raw[:5]:
            txt = str(b)
            if ":" in txt:
                h, body = txt.split(":", 1)
                stages.append({"head": h.strip(), "body": body.strip()})
            else:
                stages.append({"head": txt.strip()[:24], "body": ""})
        n = len(stages) or 1
        margin, gap = 0.8, 0.2
        col_w = (13.333 - 2 * margin - (n - 1) * gap) / n
        top = 2.6
        for i, st in enumerate(stages):
            x_in = margin + i * (col_w + gap)
            x, w = Inches(x_in), Inches(col_w)
            shp = slide.shapes.add_shape(
                MSO_SHAPE.PENTAGON if i < n - 1 else MSO_SHAPE.RECTANGLE,
                x, Inches(top), w, Inches(0.9),
            )
            shp.fill.solid()
            shp.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
            shp.line.fill.background()
            shp.shadow.inherit = False
            self._add_text(
                slide, f"STAGE {i + 1}",
                x, Inches(top + 0.12), w, Inches(0.3),
                size=10, color=p["bg"], bold=True, align="center",
            )
            self._add_text(
                slide, st["head"],
                x, Inches(top + 0.42), w, Inches(0.5),
                size=14, color=p["bg"], bold=True, align="center",
            )
            if st["body"]:
                self._add_text(
                    slide, st["body"],
                    x, Inches(top + 1.2), w, Inches(2.5),
                    size=12, color=p["text"], align="center",
                )

    def _render_metric_spotlight(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        stats = data.get("stats") or []
        primary = stats[0] if stats else {"value": data.get("title", ""), "label": ""}
        self._add_text(
            slide, str(data.get("eyebrow") or "KEY METRIC").upper(),
            Inches(0.8), Inches(0.8), Inches(11.7), Inches(0.5),
            size=12, color=p["accent"], bold=True,
        )
        self._add_text(
            slide, str(primary.get("value", "")),
            Inches(0.8), Inches(1.6), Inches(11.7), Inches(3.2),
            size=140, color=p["accent"], bold=True, align="center",
        )
        self._add_text(
            slide, str(primary.get("label", "")),
            Inches(0.8), Inches(5.0), Inches(11.7), Inches(1.0),
            size=24, color=p["text"], align="center",
        )
        if data.get("subtitle"):
            self._add_text(
                slide, data["subtitle"],
                Inches(1.5), Inches(6.1), Inches(10.3), Inches(0.8),
                size=14, color=p["muted"], align="center", italic=True,
            )

    def _render_process(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.9),
            size=28, color=p["text"], bold=True,
        )
        items = list(data.get("bullets") or [])[:5]
        y = 1.7
        for i, it in enumerate(items, 1):
            txt = str(it)
            head, body = (txt.split(":", 1) + [""])[:2]
            disc = slide.shapes.add_shape(
                MSO_SHAPE.OVAL, Inches(0.9), Inches(y), Inches(0.7), Inches(0.7),
            )
            disc.fill.solid()
            disc.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
            disc.line.fill.background()
            disc.shadow.inherit = False
            self._add_text(
                slide, str(i),
                Inches(0.9), Inches(y + 0.05), Inches(0.7), Inches(0.6),
                size=20, color=p["bg"], bold=True, align="center",
            )
            self._add_text(
                slide, head.strip(),
                Inches(1.9), Inches(y), Inches(10.5), Inches(0.5),
                size=18, color=p["text"], bold=True,
            )
            if body.strip():
                self._add_text(
                    slide, body.strip(),
                    Inches(1.9), Inches(y + 0.5), Inches(10.5), Inches(0.6),
                    size=12, color=p["muted"],
                )
            y += 1.05

    def _render_pyramid(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.9),
            size=28, color=p["text"], bold=True,
        )
        tiers = list(data.get("bullets") or [])[:3]
        # Tier widths shrink toward the top (3 = top, 1 = bottom).
        tier_specs = [
            {"w": 3.0, "y": 1.8, "label": "TIER 1"},
            {"w": 5.5, "y": 3.2, "label": "TIER 2"},
            {"w": 8.0, "y": 4.6, "label": "TIER 3"},
        ]
        cx = 13.333 / 2
        for i, tier in enumerate(tiers):
            spec = tier_specs[min(i, 2)]
            w = spec["w"]
            x = cx - w / 2
            shp = slide.shapes.add_shape(
                MSO_SHAPE.TRAPEZOID,
                Inches(x), Inches(spec["y"]), Inches(w), Inches(1.1),
            )
            shp.fill.solid()
            shp.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
            shp.line.fill.background()
            shp.shadow.inherit = False
            self._add_text(
                slide, str(tier),
                Inches(x), Inches(spec["y"] + 0.3), Inches(w), Inches(0.6),
                size=16, color=p["bg"], bold=True, align="center",
            )

    def _render_matrix_2x2(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.8),
            size=26, color=p["text"], bold=True,
        )
        # Quadrant labels from bullets[0..3] OR columns[0..3]
        cells = list(data.get("bullets") or [])[:4]
        if not cells:
            cols = data.get("columns") or []
            cells = [
                f"{c.get('heading', '')}: {c.get('body', '')}" for c in cols[:4]
            ]
        while len(cells) < 4:
            cells.append("")
        # 2x2 grid
        cell_w, cell_h = 5.6, 2.4
        gap = 0.25
        x0 = (13.333 - (2 * cell_w + gap)) / 2
        y0 = 1.5
        positions = [
            (x0, y0), (x0 + cell_w + gap, y0),
            (x0, y0 + cell_h + gap), (x0 + cell_w + gap, y0 + cell_h + gap),
        ]
        for i, (xv, yv) in enumerate(positions):
            shp = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Inches(xv), Inches(yv),
                Inches(cell_w), Inches(cell_h),
            )
            shp.line.color.rgb = _hex_to_rgb(p["accent"])
            shp.line.width = Pt(1)
            shp.fill.solid()
            shp.fill.fore_color.rgb = _hex_to_rgb(p["bg"])
            shp.shadow.inherit = False
            self._add_text(
                slide, f"Q{i + 1}",
                Inches(xv + 0.2), Inches(yv + 0.15),
                Inches(1.0), Inches(0.4),
                size=11, color=p["accent"], bold=True,
            )
            self._add_text(
                slide, str(cells[i]),
                Inches(xv + 0.3), Inches(yv + 0.7),
                Inches(cell_w - 0.6), Inches(cell_h - 0.9),
                size=14, color=p["text"],
            )

    def _render_feature_grid(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.8), Inches(0.5), Inches(11.7), Inches(0.9),
            size=28, color=p["text"], bold=True,
        )
        items = list(data.get("bullets") or [])[:4]
        cols = 2
        rows = 2
        margin, gap = 0.8, 0.3
        col_w = (13.333 - 2 * margin - (cols - 1) * gap) / cols
        row_h = 2.4
        top0 = 2.0
        for i, it in enumerate(items):
            txt = str(it)
            head, body = (txt.split(":", 1) + [""])[:2]
            row, col = divmod(i, cols)
            x_in = margin + col * (col_w + gap)
            y_in = top0 + row * (row_h + gap)
            x, y = Inches(x_in), Inches(y_in)
            w, h = Inches(col_w), Inches(row_h)
            # Icon-look initial chip
            chip = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                x, y, Inches(0.7), Inches(0.7),
            )
            chip.fill.solid()
            chip.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
            chip.line.fill.background()
            chip.shadow.inherit = False
            initial = (head.strip() or txt)[:1].upper() or "•"
            self._add_text(
                slide, initial,
                x, Inches(y_in + 0.05), Inches(0.7), Inches(0.6),
                size=22, color=p["bg"], bold=True, align="center",
            )
            self._add_text(
                slide, head.strip() or txt[:60],
                Inches(x_in + 0.9), y, Inches(col_w - 0.9), Inches(0.7),
                size=18, color=p["text"], bold=True,
            )
            if body.strip():
                self._add_text(
                    slide, body.strip(),
                    Inches(x_in + 0.9), Inches(y_in + 0.8),
                    Inches(col_w - 0.9), Inches(row_h - 0.9),
                    size=12, color=p["muted"],
                )

    def _render_callout(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        # Big accent panel on the left with the headline; supporting bullets right.
        panel = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(5.5), Inches(7.5)
        )
        panel.fill.solid()
        panel.fill.fore_color.rgb = _hex_to_rgb(p["accent"])
        panel.line.fill.background()
        panel.shadow.inherit = False
        self._add_text(
            slide, str(data.get("eyebrow") or "KEY MESSAGE").upper(),
            Inches(0.6), Inches(1.0), Inches(4.6), Inches(0.5),
            size=12, color=p["bg"], bold=True,
        )
        self._add_text(
            slide, data.get("title", ""),
            Inches(0.6), Inches(1.7), Inches(4.6), Inches(4.5),
            size=34, color=p["bg"], bold=True,
        )
        bullets = list(data.get("bullets") or [])[:4]
        y = 1.0
        for b in bullets:
            self._add_text(
                slide, "→",
                Inches(6.0), Inches(y), Inches(0.5), Inches(0.6),
                size=22, color=p["accent"], bold=True,
            )
            self._add_text(
                slide, str(b),
                Inches(6.6), Inches(y + 0.05), Inches(6.2), Inches(1.4),
                size=16, color=p["text"],
            )
            y += 1.5

    def _render_closing(self, slide, data: dict[str, Any], p: dict[str, str]) -> None:
        self._add_text(
            slide, data.get("title", "Thank you"),
            Inches(1), Inches(2.6), Inches(11.3), Inches(1.6),
            size=44, color=p["text"], bold=True, align="center",
        )
        if data.get("subtitle"):
            self._add_text(
                slide, data["subtitle"],
                Inches(1.5), Inches(4.2), Inches(10.3), Inches(1.0),
                size=18, color=p["muted"], align="center",
            )
        if data.get("cta"):
            self._add_text(
                slide, data["cta"],
                Inches(4.5), Inches(5.4), Inches(4.3), Inches(0.7),
                size=18, color=p["bg"], bold=True, align="center",
            )

    # ── pdf ───────────────────────────────────────────────────────────────
    def _export_pdf_sync(
        self, task_id: str, slides: list[dict[str, Any]], theme: str
    ) -> tuple[str, int]:
        try:
            from weasyprint import HTML
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "weasyprint is not installed or its system deps are missing"
            ) from exc

        palette = _palette_for(theme)
        html = self._slides_to_html(slides, palette)
        pdf_bytes = HTML(string=html).write_pdf()
        filename = f"{task_id}.pdf"
        url = self.storage.put(filename, pdf_bytes, content_type="application/pdf")
        logger.info("export.pdf_ok", extra={"task_id": task_id, "size": len(pdf_bytes)})
        return url, len(pdf_bytes)

    def _slides_to_html(self, slides: list[dict[str, Any]], p: dict[str, str]) -> str:
        from html import escape

        bg, text, muted, accent = p["bg"], p["text"], p["muted"], p["accent"]
        css = f"""
        @page {{ size: 13.333in 7.5in; margin: 0; }}
        body {{ margin:0; font-family:Inter,system-ui,sans-serif; }}
        .slide {{ width:13.333in; height:7.5in; box-sizing:border-box;
                  padding:0.8in; page-break-after:always;
                  background:#{bg}; color:#{text}; position:relative; }}
        .slide:last-child {{ page-break-after:auto; }}
        .eyebrow {{ font-size:11pt; letter-spacing:0.2em; color:#{accent};
                   text-transform:uppercase; text-align:center; margin-bottom:0.3in; }}
        h1.title {{ font-size:48pt; font-weight:600; text-align:center;
                   line-height:1.05; margin:0; }}
        .subtitle {{ font-size:18pt; color:#{muted}; text-align:center;
                    margin-top:0.4in; }}
        h2 {{ font-size:30pt; font-weight:600; margin:0 0 0.4in 0; }}
        ul {{ list-style:none; padding:0; margin:0; }}
        li {{ font-size:18pt; margin:0.3in 0; padding-left:0.4in; position:relative; }}
        li::before {{ content:"•"; color:#{accent}; position:absolute;
                     left:0; font-weight:700; }}
        .cols {{ display:flex; gap:0.4in; }}
        .col {{ flex:1; border:1px solid #{accent}55; border-radius:14px; padding:0.4in; }}
        .col h3 {{ color:#{accent}; font-size:18pt; margin:0 0 0.2in 0; }}
        .col p {{ font-size:14pt; color:#{text}; margin:0; line-height:1.5; }}
        .quote {{ display:flex; flex-direction:column; align-items:center;
                 justify-content:center; height:100%; text-align:center; }}
        .quote .mark {{ font-size:80pt; color:#{accent}; line-height:0.6;
                       margin-bottom:0.4in; }}
        .quote blockquote {{ font-size:26pt; font-style:italic; max-width:9in;
                            margin:0; }}
        .quote .attr {{ font-size:13pt; color:#{muted}; margin-top:0.4in;
                       letter-spacing:0.15em; text-transform:uppercase; }}
        .stats {{ display:flex; gap:0.3in; margin-top:0.4in; }}
        .stat {{ flex:1; border:1px solid #{accent}55; border-radius:14px;
                padding:0.5in; text-align:center; }}
        .stat .v {{ font-size:50pt; font-weight:600; color:#{accent}; }}
        .stat .l {{ font-size:13pt; color:#{muted}; margin-top:0.15in;
                   letter-spacing:0.1em; text-transform:uppercase; }}
        .closing {{ display:flex; flex-direction:column; align-items:center;
                   justify-content:center; height:100%; text-align:center; }}
        .cta {{ display:inline-block; margin-top:0.5in; padding:0.2in 0.6in;
               background:#{accent}; color:#{bg}; border-radius:14px;
               font-weight:600; font-size:16pt; }}
        .chart-wrap {{ width:100%; height:4.6in; display:flex; align-items:center;
                      justify-content:center; margin-top:0.2in; }}
        .chart-wrap img {{ max-width:100%; max-height:100%; }}
        .chart-caption {{ margin-top:0.2in; font-size:11pt; color:#{muted}; }}
        .section-num {{ position:absolute; left:0.4in; top:1.6in; font-size:160pt;
                       font-weight:700; color:#{accent}; line-height:1; }}
        .section-body {{ position:absolute; left:4.5in; top:2.6in; right:0.8in; }}
        .section-body .eyebrow {{ text-align:left; margin:0; color:#{accent}; }}
        .section-body h1 {{ font-size:42pt; margin:0.2in 0 0.3in; line-height:1.05; }}
        .section-body p {{ font-size:14pt; color:#{muted}; margin:0; }}
        .kpis {{ display:flex; gap:0.3in; margin-top:0.3in; }}
        .kpi {{ flex:1; border:1px solid #{accent}55; border-radius:14px;
               padding:0.4in; text-align:center; }}
        .kpi .v {{ font-size:42pt; font-weight:700; color:#{accent}; line-height:1; }}
        .kpi .d {{ font-size:13pt; color:#{accent}; margin-top:0.1in; }}
        .kpi .l {{ font-size:12pt; color:#{text}; margin-top:0.15in;
                  letter-spacing:0.1em; text-transform:uppercase; font-weight:600; }}
        .kpi .s {{ font-size:11pt; color:#{muted}; margin-top:0.1in; }}
        .compare {{ display:flex; gap:0.5in; align-items:stretch; margin-top:0.3in;
                   position:relative; }}
        .compare .side {{ flex:1; border:1px solid #{accent}55; border-radius:14px;
                         padding:0.4in; }}
        .compare .side.b {{ border-color:#{muted}; }}
        .compare .side h3 {{ color:#{accent}; font-size:18pt; margin:0 0 0.15in;
                            text-align:center; text-transform:uppercase; }}
        .compare .side.b h3 {{ color:#{text}; }}
        .compare .side .sub {{ font-size:11pt; color:#{muted}; text-align:center;
                              margin-bottom:0.2in; }}
        .compare ul li {{ font-size:13pt; margin:0.15in 0; }}
        .vs {{ position:absolute; left:50%; top:50%; transform:translate(-50%,-50%);
              width:0.8in; height:0.8in; background:#{accent}; color:#fff;
              border-radius:50%; display:flex; align-items:center;
              justify-content:center; font-weight:700; font-size:14pt; }}
        .timeline {{ display:flex; justify-content:space-between; margin-top:1.5in;
                    position:relative; padding:0.6in 0.3in; }}
        .timeline::before {{ content:""; position:absolute; left:0.3in; right:0.3in;
                            top:50%; height:2px; background:#{muted}; }}
        .tl-event {{ flex:1; text-align:center; position:relative; }}
        .tl-event .node {{ width:0.4in; height:0.4in; border-radius:50%;
                          background:#{accent}; margin:0 auto; position:relative;
                          z-index:1; border:3px solid #{bg}; }}
        .tl-event .y {{ font-size:13pt; color:#{accent}; font-weight:700;
                       margin-top:0.15in; }}
        .tl-event .t {{ font-size:12pt; color:#{text}; font-weight:600;
                       margin-top:0.05in; }}
        .tl-event .d {{ font-size:10pt; color:#{muted}; margin-top:0.05in; }}
        """
        out = [f"<html><head><style>{css}</style></head><body>"]
        for s in slides:
            layout = (s.get("layout") or "title").lower()
            out.append('<section class="slide">')
            if layout == "title":
                out.append(f'<div class="eyebrow">{escape(s.get("eyebrow") or "Presentation")}</div>')
                out.append(f'<h1 class="title">{escape(s.get("title", ""))}</h1>')
                if s.get("subtitle"):
                    out.append(f'<div class="subtitle">{escape(s["subtitle"])}</div>')
            elif layout == "bullets":
                out.append(f'<h2>{escape(s.get("title", ""))}</h2><ul>')
                for b in (s.get("bullets") or [])[:6]:
                    out.append(f"<li>{escape(str(b))}</li>")
                out.append("</ul>")
            elif layout == "two-col":
                out.append(f'<h2>{escape(s.get("title", ""))}</h2><div class="cols">')
                for c in (s.get("columns") or [])[:2]:
                    out.append(
                        f'<div class="col"><h3>{escape(c.get("heading", ""))}</h3>'
                        f'<p>{escape(c.get("body", ""))}</p></div>'
                    )
                out.append("</div>")
            elif layout == "quote":
                out.append('<div class="quote"><div class="mark">“</div>')
                out.append(f'<blockquote>{escape(s.get("quote", s.get("title", "")))}</blockquote>')
                if s.get("attribution"):
                    out.append(f'<div class="attr">— {escape(s["attribution"])}</div>')
                out.append("</div>")
            elif layout == "stats":
                out.append(f'<h2>{escape(s.get("title", ""))}</h2><div class="stats">')
                for st in (s.get("stats") or [])[:3]:
                    out.append(
                        f'<div class="stat"><div class="v">{escape(str(st.get("value", "")))}</div>'
                        f'<div class="l">{escape(str(st.get("label", "")))}</div></div>'
                    )
                out.append("</div>")
            elif layout == "chart":
                out.append(f'<h2>{escape(s.get("title", ""))}</h2>')
                if s.get("subtitle"):
                    out.append(
                        f'<div style="font-size:13pt;color:#{muted};margin-top:-0.2in;'
                        f'margin-bottom:0.2in;">{escape(s["subtitle"])}</div>'
                    )
                chart_url = self._quickchart_url(s, p)
                out.append(f'<div class="chart-wrap"><img src="{escape(chart_url)}"/></div>')
                cd = s.get("chart_data") or {}
                cap_parts = []
                if cd.get("unit"):
                    cap_parts.append(f"Units: {escape(str(cd['unit']))}")
                if cd.get("source"):
                    cap_parts.append(f"Source: {escape(str(cd['source']))}")
                if cap_parts:
                    out.append(
                        f'<div class="chart-caption">{"  &bull;  ".join(cap_parts)}</div>'
                    )
            elif layout == "closing":
                out.append('<div class="closing">')
                out.append(f'<h1 class="title">{escape(s.get("title", "Thank you"))}</h1>')
                if s.get("subtitle"):
                    out.append(f'<div class="subtitle">{escape(s["subtitle"])}</div>')
                if s.get("cta"):
                    out.append(f'<div class="cta">{escape(s["cta"])}</div>')
                out.append("</div>")
            elif layout == "section":
                num = (s.get("section_number") or "").strip()
                if num:
                    out.append(f'<div class="section-num">{escape(num)}</div>')
                out.append('<div class="section-body">')
                out.append(
                    f'<div class="eyebrow">{escape((s.get("eyebrow") or "Section"))}</div>'
                )
                out.append(f'<h1>{escape(s.get("title", ""))}</h1>')
                if s.get("subtitle"):
                    out.append(f'<p>{escape(s["subtitle"])}</p>')
                out.append("</div>")
            elif layout == "kpi":
                out.append(f'<h2>{escape(s.get("title", ""))}</h2>')
                if s.get("subtitle"):
                    out.append(
                        f'<div style="font-size:13pt;color:#{muted};'
                        f'margin-top:-0.2in;margin-bottom:0.2in;">'
                        f'{escape(s["subtitle"])}</div>'
                    )
                out.append('<div class="kpis">')
                for k in (s.get("kpis") or [])[:4]:
                    direction = str(k.get("direction") or "").lower()
                    arrow = (
                        "&#x25B2; " if direction in ("up", "positive", "increase")
                        else "&#x25BC; " if direction in ("down", "negative", "decrease")
                        else ""
                    )
                    delta = str(k.get("delta", "")).strip()
                    out.append('<div class="kpi">')
                    out.append(f'<div class="v">{escape(str(k.get("value", "")))}</div>')
                    if delta:
                        out.append(f'<div class="d">{arrow}{escape(delta)}</div>')
                    out.append(f'<div class="l">{escape(str(k.get("label", "")))}</div>')
                    if k.get("sublabel"):
                        out.append(f'<div class="s">{escape(str(k["sublabel"]))}</div>')
                    out.append("</div>")
                out.append("</div>")
            elif layout == "comparison":
                out.append(f'<h2>{escape(s.get("title", ""))}</h2>')
                items = (s.get("items") or [])[:2]
                out.append('<div class="compare">')
                for i, c in enumerate(items):
                    cls = "side" if i == 0 else "side b"
                    out.append(f'<div class="{cls}">')
                    out.append(f'<h3>{escape(c.get("heading", ""))}</h3>')
                    if c.get("subtitle"):
                        out.append(f'<div class="sub">{escape(c["subtitle"])}</div>')
                    pts = c.get("points") or []
                    if pts:
                        out.append("<ul>")
                        for pt in pts[:4]:
                            out.append(f"<li>{escape(str(pt))}</li>")
                        out.append("</ul>")
                    elif c.get("body"):
                        out.append(f'<p style="font-size:13pt;">{escape(c["body"])}</p>')
                    out.append("</div>")
                if len(items) == 2:
                    div = (s.get("divider") or "vs").upper()
                    out.append(f'<div class="vs">{escape(div)}</div>')
                out.append("</div>")
            elif layout == "timeline":
                out.append(f'<h2>{escape(s.get("title", ""))}</h2>')
                out.append('<div class="timeline">')
                for e in (s.get("events") or [])[:5]:
                    out.append('<div class="tl-event">')
                    out.append('<div class="node"></div>')
                    out.append(f'<div class="y">{escape(str(e.get("year", "")))}</div>')
                    out.append(f'<div class="t">{escape(str(e.get("title", "")))}</div>')
                    if e.get("desc"):
                        out.append(f'<div class="d">{escape(str(e["desc"]))}</div>')
                    out.append("</div>")
                out.append("</div>")
            out.append("</section>")
        out.append("</body></html>")
        return "".join(out)
