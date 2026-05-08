"""Canonical layout registry — loads the shared JSON spec.

The JSON file lives at `frontend/src/design/layouts.registry.json` so that
both backend and frontend consume the same source of truth. If the file is
missing (e.g. backend container built without the frontend tree), we fall
back to the inline copy below — but `scripts/verify_layouts.mjs` will fail
CI if the inline copy and the JSON drift.

Edit only the JSON. Run `npm run verify:layouts` after any change.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("nexus.agent.layouts_registry")

# Resolution order — first hit wins.
_CANDIDATE_PATHS = [
    # Repo layout (dev): backend/agent/ → ../../frontend/src/design/...
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "design" / "layouts.registry.json",
    # Container layout: assume frontend bundle is mounted alongside.
    Path("/app/frontend/src/design/layouts.registry.json"),
]

# Inline fallback — keep in sync with the JSON. Verified by CI.
_INLINE_FALLBACK: dict[str, Any] = {
    "version": 1,
    "layouts": [
        {"name": n, "exported": e}
        for n, e in [
            ("title", True), ("section", True), ("bullets", True), ("two-col", True),
            ("comparison", True), ("kpi", True), ("quote", True), ("stats", True),
            ("chart", True), ("table", False), ("timeline", True), ("image-focus", False),
            ("closing", True), ("hero", True), ("bento", True), ("agenda", True),
            ("roadmap", True), ("metric-spotlight", True), ("process", True),
            ("pyramid", True), ("matrix-2x2", True), ("feature-grid", True), ("callout", True),
        ]
    ],
    "aliases": {
        "chart_focus": "chart", "chart-focus": "chart",
        "image_text": "image-focus", "image-text": "image-focus",
        "kpi_grid": "kpi", "kpi-grid": "kpi", "kpis": "kpi",
        "bullet_list": "bullets", "bullet-list": "bullets", "list": "bullets",
        "versus": "comparison", "vs": "comparison",
        "two_col": "two-col", "twocol": "two-col", "two-column": "two-col",
        "grid": "bento", "cards": "bento", "bento-grid": "bento",
        "icon-cards": "feature-grid",
        "toc": "agenda", "table-of-contents": "agenda",
        "timeline-horizontal": "roadmap", "journey": "roadmap",
        "steps": "process", "workflow": "process", "flow": "process",
        "hierarchy": "pyramid", "stack": "pyramid",
        "quadrant": "matrix-2x2", "2x2": "matrix-2x2", "matrix": "matrix-2x2",
        "features": "feature-grid", "feature_grid": "feature-grid",
        "highlight": "callout",
        "big-number": "metric-spotlight", "big_metric": "metric-spotlight",
        "big_number": "metric-spotlight", "metric": "metric-spotlight",
        "banner": "hero", "cover": "title",
    },
    "fallback": "bullets",
}


def _load() -> dict[str, Any]:
    for path in _CANDIDATE_PATHS:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover — surface but keep booting
                logger.warning("layouts.registry.json failed to parse at %s: %s", path, exc)
    logger.info("layouts.registry.json not found; using inline fallback")
    return _INLINE_FALLBACK


_REGISTRY = _load()

CANONICAL_LAYOUTS: set[str] = {l["name"] for l in _REGISTRY["layouts"]}
EXPORT_SUPPORTED: set[str] = {l["name"] for l in _REGISTRY["layouts"] if l.get("exported", False)}
LAYOUT_ALIASES: dict[str, str] = dict(_REGISTRY.get("aliases", {}))
FALLBACK_LAYOUT: str = _REGISTRY.get("fallback", "bullets")


def normalize_layout(raw: str) -> str:
    """Resolve any layout name (canonical or alias) to a canonical name.

    Falls back to the configured fallback layout for unknown inputs.
    """
    key = (raw or "").strip().lower()
    if key in CANONICAL_LAYOUTS:
        return key
    return LAYOUT_ALIASES.get(key, FALLBACK_LAYOUT)


def is_supported_in_export(name: str) -> bool:
    """True iff the given canonical layout name has a PPTX renderer."""
    return normalize_layout(name) in EXPORT_SUPPORTED
