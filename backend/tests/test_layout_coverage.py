"""Phase 1A regression tests: canonical layout coverage.

These tests guard the contract that the backend agent's notion of "valid
layouts" is exactly what the canonical registry says, and that every
canonical layout survives ``NexusAgentLoop._normalize_slides`` instead of
being silently rewritten to ``bullets`` (or anything else).

They intentionally avoid pulling in ``backend.tests.conftest`` /
``database.connection`` so they can be exercised in isolation by anyone
running ``python -m pytest --noconftest backend/tests/test_layout_coverage.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure ``backend/`` is on sys.path when this file is invoked directly
# (e.g. via ``python -m pytest`` from the repo root) so the ``agent``
# package resolves the same way it does inside the container.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.layouts_registry import (  # noqa: E402
    CANONICAL_LAYOUTS,
    FALLBACK_LAYOUT,
    LAYOUT_ALIASES,
    normalize_layout,
)
from agent.loop import NexusAgentLoop, _VALID_LAYOUTS  # noqa: E402
from agent.planner import Planner, _VALID_LAYOUTS as PLANNER_VALID_LAYOUTS  # noqa: E402


_REGISTRY_JSON = _BACKEND_ROOT / "agent" / "layouts.registry.json"
_FRONTEND_REGISTRY_JSON = (
    _BACKEND_ROOT.parent / "frontend" / "src" / "design" / "layouts.registry.json"
)


def _load_registry_names(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return [entry["name"] for entry in data["layouts"]]


# --------------------------------------------------------------------------
# Registry parity
# --------------------------------------------------------------------------

def test_backend_valid_layouts_matches_registry() -> None:
    """The backend's _VALID_LAYOUTS set must equal the canonical registry."""
    registry_names = _load_registry_names(_REGISTRY_JSON)
    assert set(_VALID_LAYOUTS) == set(registry_names), (
        "_VALID_LAYOUTS drifted from layouts.registry.json"
    )
    assert set(_VALID_LAYOUTS) == set(CANONICAL_LAYOUTS), (
        "_VALID_LAYOUTS drifted from CANONICAL_LAYOUTS"
    )


def test_backend_and_frontend_registry_files_match() -> None:
    """The two registry copies (backend + frontend) must stay byte-aligned.

    When the backend test runs in a container that does not mount the
    frontend tree (the default in this repo's docker-compose), this check
    is skipped because the JS-side ``scripts/verify-layouts.mjs`` already
    enforces the same parity from the frontend side.
    """
    if not _FRONTEND_REGISTRY_JSON.exists():
        pytest.skip(
            "frontend registry not reachable from backend test runtime; "
            "parity is enforced by scripts/verify-layouts.mjs instead."
        )
    backend_data = json.loads(_REGISTRY_JSON.read_text(encoding="utf-8"))
    frontend_data = json.loads(_FRONTEND_REGISTRY_JSON.read_text(encoding="utf-8"))
    assert backend_data == frontend_data, (
        "backend/agent/layouts.registry.json and "
        "frontend/src/design/layouts.registry.json have drifted"
    )


def test_fallback_layout_is_canonical() -> None:
    assert FALLBACK_LAYOUT in CANONICAL_LAYOUTS


def test_aliases_only_target_canonical_layouts() -> None:
    for src, target in LAYOUT_ALIASES.items():
        assert target in CANONICAL_LAYOUTS, (
            f"alias {src!r} -> {target!r} but {target!r} is not canonical"
        )


# --------------------------------------------------------------------------
# Round-trip per canonical layout
# --------------------------------------------------------------------------

def _seed_slide(layout: str, idx: int) -> dict:
    """Build a minimal slide payload that should survive normalization."""
    if layout == "title":
        return {
            "layout": "title",
            "title": f"Title {idx}",
            "subtitle": "Sub",
            "eyebrow": "Eye",
        }
    if layout == "bullets":
        return {
            "layout": "bullets",
            "title": f"Bullets {idx}",
            "bullets": ["a", "b", "c"],
        }
    if layout == "two-col":
        return {
            "layout": "two-col",
            "title": f"Two-col {idx}",
            "columns": [
                {"heading": "L", "body": "left body"},
                {"heading": "R", "body": "right body"},
            ],
        }
    if layout == "quote":
        return {
            "layout": "quote",
            "title": f"Quote {idx}",
            "quote": "To be or not to be",
            "attribution": "Shakespeare",
        }
    if layout == "stats":
        return {
            "layout": "stats",
            "title": f"Stats {idx}",
            "stats": [
                {"value": "42", "label": "answer"},
                {"value": "7", "label": "wonders"},
            ],
        }
    if layout == "chart":
        return {
            "layout": "chart",
            "title": f"Chart {idx}",
            "chart_type": "bar",
            "chart_data": {
                "labels": ["A", "B", "C"],
                "values": [1, 2, 3],
                "unit": "k",
                "source": "test",
            },
        }
    if layout == "closing":
        return {
            "layout": "closing",
            "title": f"Closing {idx}",
            "subtitle": "Thanks",
            "cta": "Questions?",
        }
    # Phase 6AA — single dominant metric.
    if layout == "bigstat":
        return {
            "layout": "bigstat",
            "title": f"Bigstat {idx}",
            "value": "93%",
            "label": "Adoption",
            "subtitle": "Across the cohort",
        }
    # Phase 6AA — typography pause.
    if layout == "section_divider":
        return {
            "layout": "section_divider",
            "title": f"Part {idx}",
            "eyebrow": "Continued",
            "subtitle": "Implications",
        }
    # Phase 6AC — chronology of dated events.
    if layout == "timeline":
        return {
            "layout": "timeline",
            "title": f"Timeline {idx}",
            "subtitle": "",
            "events": [
                {"date": "1980", "label": "Event A"},
                {"date": "1985", "label": "Event B"},
                {"date": "1990", "label": "Event C"},
            ],
        }
    # Phase 6AC — left/right contrast.
    if layout == "comparison":
        return {
            "layout": "comparison",
            "title": f"Comparison {idx}",
            "subtitle": "",
            "left": {"heading": "Before", "body": "Manual workflows."},
            "right": {"heading": "After", "body": "Automated pipeline."},
        }
    raise AssertionError(f"unknown canonical layout: {layout}")


@pytest.mark.parametrize("layout", list(CANONICAL_LAYOUTS))
def test_normalize_preserves_canonical_layout(layout: str) -> None:
    """Every canonical layout must survive _normalize_slides when present.

    The normalizer pins slide[0]=title and slide[-1]=closing and also
    auto-promotes a stats slide to chart when no chart is present, so we
    seed a chart slide alongside non-edge layouts to exercise the
    layout-preservation contract specifically.
    """
    if layout == "title":
        slides = [
            _seed_slide("title", 0),
            _seed_slide("bullets", 1),
            _seed_slide("chart", 2),
            _seed_slide("closing", 3),
        ]
        normalized = NexusAgentLoop._normalize_slides(slides, len(slides), "topic")
        assert normalized[0]["layout"] == "title"
        return
    if layout == "closing":
        slides = [
            _seed_slide("title", 0),
            _seed_slide("bullets", 1),
            _seed_slide("chart", 2),
            _seed_slide("closing", 3),
        ]
        normalized = NexusAgentLoop._normalize_slides(slides, len(slides), "topic")
        assert normalized[-1]["layout"] == "closing"
        return

    # Always include a chart sibling so the loop's stats->chart
    # auto-promotion does not interfere with the layout under test.
    middle = [_seed_slide(layout, 1)]
    if layout != "chart":
        middle.append(_seed_slide("chart", 2))
    slides = [_seed_slide("title", 0), *middle, _seed_slide("closing", 99)]
    normalized = NexusAgentLoop._normalize_slides(slides, len(slides), "topic")
    assert len(normalized) == len(slides)
    assert normalized[1]["layout"] == layout, (
        f"layout {layout!r} was rewritten to {normalized[1]['layout']!r}"
    )


def test_unknown_layout_falls_back_to_fallback_not_silently_dropped() -> None:
    slides = [
        _seed_slide("title", 0),
        {"layout": "totally-not-a-real-layout", "title": "X"},
        _seed_slide("chart", 2),
        _seed_slide("closing", 3),
    ]
    normalized = NexusAgentLoop._normalize_slides(slides, len(slides), "topic")
    assert normalized[1]["layout"] == FALLBACK_LAYOUT
    # And the registry's normalize_layout helper agrees:
    assert normalize_layout("totally-not-a-real-layout") == FALLBACK_LAYOUT


def test_normalize_layout_canonical_passthrough() -> None:
    for name in CANONICAL_LAYOUTS:
        assert normalize_layout(name) == name
        assert normalize_layout(name.upper()) == name
        assert normalize_layout(f"  {name}  ") == name


# --------------------------------------------------------------------------
# Planner round-trip — Phase 1A.1
# --------------------------------------------------------------------------

def test_planner_valid_layouts_matches_registry() -> None:
    """Planner._VALID_LAYOUTS must equal the canonical registry.

    This guards against the Phase 1A.1 drift where ``planner.py`` carried
    its own hardcoded set that was missing ``chart``.
    """
    assert set(PLANNER_VALID_LAYOUTS) == set(CANONICAL_LAYOUTS)


def _planner_outline_json(layout: str) -> str:
    """Build a single-item JSON outline that Planner._parse_outline accepts."""
    return json.dumps(
        [
            {
                "layout": layout,
                "title": f"{layout} title",
                "intent": f"intent for {layout}",
            }
        ]
    )


@pytest.mark.parametrize("layout", list(CANONICAL_LAYOUTS))
def test_planner_preserves_canonical_layout(layout: str) -> None:
    """Every canonical layout (including ``chart``) must survive
    ``Planner._parse_outline`` instead of being collapsed to ``bullets``.
    """
    parsed = Planner._parse_outline(_planner_outline_json(layout))
    assert len(parsed) == 1
    assert parsed[0]["layout"] == layout, (
        f"planner rewrote {layout!r} -> {parsed[0]['layout']!r}"
    )


def test_planner_unknown_layout_falls_back_to_fallback_layout() -> None:
    parsed = Planner._parse_outline(
        _planner_outline_json("definitely-not-a-real-layout")
    )
    assert len(parsed) == 1
    assert parsed[0]["layout"] == FALLBACK_LAYOUT


def test_planner_chart_layout_not_lost() -> None:
    """Regression test for the Phase 1A.1 drift: ``chart`` was missing from
    the planner's hardcoded whitelist. It must now pass through.
    """
    parsed = Planner._parse_outline(_planner_outline_json("chart"))
    assert parsed[0]["layout"] == "chart"

