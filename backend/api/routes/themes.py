"""Phase 6O — read-only theme registry endpoints.

Surfaces ``backend/agent/themes_registry.py`` over HTTP so the frontend
preview/editor/presenter/share/export surfaces can resolve a single
source of truth for design tokens. No DB, no LLM, no side effects.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agent.themes_registry import (
    BUILTIN_THEMES,
    DEFAULT_THEME_ID,
    LEGACY_THEME_ALIASES,
    SCHEMA_VERSION,
    get_theme,
    list_theme_ids,
)

router = APIRouter()


@router.get("/themes")
async def list_themes() -> dict:
    """Return all built-in themes plus the legacy display-name aliases."""

    themes = [BUILTIN_THEMES[tid].to_tokens() for tid in list_theme_ids()]
    return {
        "schema_version": SCHEMA_VERSION,
        "default_theme_id": DEFAULT_THEME_ID,
        "themes": themes,
        "aliases": dict(LEGACY_THEME_ALIASES),
    }


@router.get("/themes/{theme_id}")
async def get_theme_endpoint(theme_id: str) -> dict:
    """Return tokens for a single theme. Resolves legacy display names too."""

    try:
        theme = get_theme(theme_id, strict=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return theme.to_tokens()
