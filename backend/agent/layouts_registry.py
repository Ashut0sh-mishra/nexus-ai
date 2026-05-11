"""Canonical NEXUS slide layout registry — backend loader.

Single source of truth lives in ``frontend/src/design/layouts.registry.json``.
Reading the same JSON keeps the backend normalizer
(``backend/agent/loop.py``) and the frontend parser
(``frontend/src/utils/slideParser.js``) from drifting.

If the JSON is missing at runtime we fall back to a small in-process default
so production never crashes on a packaging miss; the layout-coverage tests
fail loudly when that default does not match the registry, so this only
matters in degraded environments.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("nexus.agent.layouts_registry")

# The canonical registry file. A byte-identical copy lives at
# ``frontend/src/design/layouts.registry.json``; the verify-layouts script
# fails CI if the two ever drift. We read the backend-side copy here so the
# backend container does not need access to the frontend tree.
_REGISTRY_PATH = Path(__file__).resolve().parent / "layouts.registry.json"

# Last-resort default kept in sync with layouts.registry.json. The
# test ``test_backend_valid_layouts_matches_registry`` asserts these
# match, so any drift fails CI.
_DEFAULT_LAYOUTS: tuple[str, ...] = (
    "title",
    "bullets",
    "two-col",
    "quote",
    "stats",
    "chart",
    "closing",
)
_DEFAULT_FALLBACK = "bullets"


def _load_registry() -> dict[str, Any]:
    try:
        with _REGISTRY_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("registry root is not an object")
        return data
    except FileNotFoundError:
        logger.warning(
            "layouts_registry.json_missing path=%s using default layouts",
            _REGISTRY_PATH,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "layouts_registry.json_invalid path=%s err=%s using default layouts",
            _REGISTRY_PATH,
            exc,
        )
    return {
        "layouts": [{"name": n, "exported": True} for n in _DEFAULT_LAYOUTS],
        "aliases": {},
        "fallback": _DEFAULT_FALLBACK,
    }


_RAW = _load_registry()

_layout_entries: list[dict[str, Any]] = [
    e for e in (_RAW.get("layouts") or []) if isinstance(e, dict) and e.get("name")
]

CANONICAL_LAYOUTS: tuple[str, ...] = tuple(str(e["name"]) for e in _layout_entries)
EXPORT_SUPPORTED: frozenset[str] = frozenset(
    str(e["name"]) for e in _layout_entries if e.get("exported")
)
LAYOUT_ALIASES: dict[str, str] = {
    str(k).strip().lower(): str(v).strip().lower()
    for k, v in (_RAW.get("aliases") or {}).items()
    if isinstance(k, str) and isinstance(v, str)
}
FALLBACK_LAYOUT: str = str(_RAW.get("fallback") or _DEFAULT_FALLBACK)

_CANONICAL_SET: frozenset[str] = frozenset(CANONICAL_LAYOUTS)


def normalize_layout(raw: Any) -> str:
    """Map an arbitrary raw layout value to a canonical layout name.

    Canonical layouts pass through unchanged. Known aliases are resolved.
    Anything else collapses to ``FALLBACK_LAYOUT`` so downstream code can
    always assume a valid renderer exists.
    """
    if not isinstance(raw, str):
        return FALLBACK_LAYOUT
    name = raw.strip().lower()
    if name in _CANONICAL_SET:
        return name
    aliased = LAYOUT_ALIASES.get(name)
    if aliased and aliased in _CANONICAL_SET:
        return aliased
    return FALLBACK_LAYOUT


__all__ = [
    "CANONICAL_LAYOUTS",
    "EXPORT_SUPPORTED",
    "LAYOUT_ALIASES",
    "FALLBACK_LAYOUT",
    "normalize_layout",
]
