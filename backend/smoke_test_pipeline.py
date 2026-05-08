"""Smoke test for the slide pipeline end-to-end (no LLM, no network).

Runs inside the backend container. Exercises:
  1. THEMES coverage      — every name in theme_picker resolves
  2. Layout dispatch      — every canonical layout produces a slide without raising
  3. PPTX export          — assembles a multi-layout deck and writes to /tmp
  4. slide_renderer       — html builder works (PNG step optional / skipped)

Exit code 0 = pass, non-zero = fail.
"""

from __future__ import annotations

import io
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _section(title: str) -> None:
    print(f"\n===== {title} =====")


def main() -> int:
    failures: list[str] = []

    # 1) THEMES coverage
    _section("THEMES coverage")
    try:
        from services.export_service import THEMES, _palette_for
        from agent import theme_picker as _tp

        # Collect every theme name the picker can emit, from any internal list.
        names: set[str] = set()
        for buckets in (getattr(_tp, "_BUCKETS", []) or []):
            try:
                _, lst = buckets
                names.update(lst)
            except Exception:
                pass
        names.update(getattr(_tp, "_FALLBACK_THEMES", []) or [])
        names.discard("auto-pick")
        present = sum(1 for n in names if _palette_for(n))
        print(f"  THEMES dict size: {len(THEMES)}")
        print(f"  picker themes resolved: {present}/{len(names)}")
        if present != len(names):
            missing = [n for n in names if not any(k.lower() == n.lower() for k in THEMES)]
            failures.append(f"missing themes: {missing}")
    except Exception as exc:
        failures.append(f"themes step crashed: {exc}")
        traceback.print_exc()

    # 2) Layout dispatch + 3) PPTX export
    _section("Layout dispatch + PPTX export")
    try:
        from services.export_service import ExportService, _palette_for

        layouts_to_test = [
            "title", "section", "bullets", "two-col", "comparison",
            "kpi", "quote", "stats", "timeline", "closing",
            "hero", "bento", "agenda", "roadmap", "metric-spotlight",
            "process", "pyramid", "matrix-2x2", "feature-grid", "callout",
        ]
        slides = []
        for i, layout in enumerate(layouts_to_test):
            slides.append({
                "layout": layout,
                "title": f"Slide {i + 1}: {layout}",
                "subtitle": "Smoke-test subtitle",
                "eyebrow": "TEST",
                "bullets": [
                    "Discovery: identify the user segment driving 60% of revenue",
                    "Insight: 23% of churned users left within the first 14 days",
                    "Action: build an onboarding journey targeting day 0–14",
                    "Outcome: pilot reduced 30-day churn from 23% to 14% (Q3 2025)",
                ],
                "stats": [
                    {"value": "$8.4B", "label": "TAM (2026)"},
                    {"value": "23%", "label": "YoY growth"},
                    {"value": "147", "label": "Pilots shipped"},
                ],
                "columns": [
                    {"heading": "Before", "body": "Manual onboarding, 14-day TTV"},
                    {"heading": "After", "body": "Guided activation, 3-day TTV"},
                ],
                "events": [
                    {"year": "2024", "title": "Pilot", "desc": "Stealth launch"},
                    {"year": "2025", "title": "GA", "desc": "Public release"},
                    {"year": "2026", "title": "Scale", "desc": "Enterprise tier"},
                ],
                "quote": "We shipped a deck in five minutes that took a team of three a week.",
                "attribution": "Sample User, Founder",
                "cta": "Get started",
            })

        svc = ExportService()
        # Use the sync entry point with a deterministic task_id for the smoke test.
        path, size = svc._export_pptx_sync("smoke_test_deck", slides, theme="Minimal")
        print(f"  ok: layouts={len(layouts_to_test)} bytes={size} path={path}")
        if size <= 0:
            failures.append("pptx export produced empty file")
    except Exception as exc:
        failures.append(f"pptx export crashed: {exc}")
        traceback.print_exc()

    # 4) slide_renderer — html only (skip PNG if Playwright not installed)
    _section("slide_renderer.slide_to_html")
    try:
        from services.slide_renderer import is_available, slide_to_html
        from services.export_service import _palette_for

        html = slide_to_html(
            {"layout": "bullets", "title": "Hello", "bullets": ["A", "B", "C"]},
            _palette_for("Minimal"),
        )
        print(f"  html length: {len(html)} bytes")
        print(f"  playwright available: {is_available()}")
        if "<h2>Hello</h2>" not in html or "<li>A</li>" not in html:
            failures.append("slide_to_html missing expected fragments")
    except Exception as exc:
        failures.append(f"slide_renderer crashed: {exc}")
        traceback.print_exc()

    # ── verdict
    _section("RESULT")
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — pipeline smoke test green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
