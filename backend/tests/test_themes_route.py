"""Phase 6O — tests for the read-only ``/api/themes`` endpoint and for
the legacy-display-name resolution that now lives in
``backend/agent/themes_registry.py``.

Pure offline. No network, no LLM, no Celery, no live eval.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from agent.themes_registry import (
    BUILTIN_THEMES,
    DEFAULT_THEME_ID,
    LEGACY_THEME_ALIASES,
    get_theme,
    resolve_theme,
)


# ── Registry-level checks (no HTTP) ────────────────────────────────────────


@pytest.mark.parametrize(
    "legacy_name,expected_id",
    [
        ("light-pro", "light-pro"),
        ("Editorial", "nexus-default"),  # alias
        ("Pixel", "pixel"),
        ("Vellum", "nexus-light"),  # alias
        ("Dossier", "dossier"),
    ],
)
def test_all_five_legacy_display_names_resolve(legacy_name, expected_id):
    t = get_theme(legacy_name)
    assert t.theme_id == expected_id


def test_each_legacy_name_has_distinct_accent_color():
    accents = {
        name: get_theme(name).colors["accent"]
        for name in ("light-pro", "Editorial", "Pixel", "Vellum", "Dossier")
    }
    # Five distinct accent colors → themes are visually meaningful.
    assert len(set(accents.values())) == 5, accents


def test_resolve_theme_for_pixel_dossier_lightpro_decks():
    for legacy in ("Pixel", "Dossier", "light-pro"):
        deck = {"theme": legacy}
        t = resolve_theme(deck)
        # All three are now first-class theme ids (lowercased).
        assert t.theme_id == legacy.lower()


def test_aliases_only_cover_editorial_and_vellum():
    # Phase 6O: Pixel/Dossier/light-pro are first-class themes, so aliases
    # are intentionally limited to the two themes that were already aliased
    # in Phase 6L (editorial → nexus-default, vellum → nexus-light).
    assert set(LEGACY_THEME_ALIASES.keys()) == {"editorial", "vellum"}


def test_builtin_themes_includes_all_five_legacy_ids():
    for tid in ("nexus-default", "nexus-light", "pixel", "dossier", "light-pro"):
        assert tid in BUILTIN_THEMES, tid


# ── HTTP route checks ──────────────────────────────────────────────────────


def _client():
    from main import app

    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def test_get_themes_returns_all_themes_and_aliases():
    async def _go():
        async with _client() as c:
            r = await c.get("/api/themes")
            assert r.status_code == 200, r.text
            body = r.json()
            assert "schema_version" in body
            assert body["default_theme_id"] == DEFAULT_THEME_ID
            ids = sorted(t["theme_id"] for t in body["themes"])
            for tid in ("dossier", "light-pro", "nexus-default", "nexus-light", "pixel"):
                assert tid in ids
            # Each theme exposes structured token groups.
            for t in body["themes"]:
                assert "colors" in t and "accent" in t["colors"]
                assert "fonts" in t
                assert "chart_palette" in t and len(t["chart_palette"]) >= 3
            assert body["aliases"] == dict(LEGACY_THEME_ALIASES)

    asyncio.run(_go())


def test_get_theme_by_legacy_display_name():
    async def _go():
        async with _client() as c:
            for name, expected_id in [
                ("Pixel", "pixel"),
                ("Editorial", "nexus-default"),
                ("light-pro", "light-pro"),
                ("Dossier", "dossier"),
                ("Vellum", "nexus-light"),
            ]:
                r = await c.get(f"/api/themes/{name}")
                assert r.status_code == 200, (name, r.text)
                assert r.json()["theme_id"] == expected_id

    asyncio.run(_go())


def test_get_theme_unknown_returns_404():
    async def _go():
        async with _client() as c:
            r = await c.get("/api/themes/no-such-theme")
            assert r.status_code == 404

    asyncio.run(_go())


# ── Exporter integration check ─────────────────────────────────────────────


def test_export_service_themes_dict_now_derives_from_registry():
    """Phase 6O wired ``ExportService.THEMES`` through the registry."""

    from services.export_service import THEMES

    # All five legacy keys still resolvable for backwards compatibility.
    for name in ("light-pro", "Editorial", "Pixel", "Vellum", "Dossier"):
        p = THEMES[name]
        assert "bg" in p and "text" in p and "muted" in p and "accent" in p
        # Hex strings stored without the leading '#' for python-pptx.
        for k in ("bg", "text", "muted", "accent"):
            assert "#" not in p[k], (name, k, p[k])
        # Phase 6O adds a comma-joined chart_palette for QuickChart.
        assert "chart_palette" in p
        assert len(p["chart_palette"].split(",")) >= 3

    # Exporter accents must match the registry accents (single source).
    for name in ("light-pro", "Editorial", "Pixel", "Vellum", "Dossier"):
        registry_accent = get_theme(name).colors["accent"].lstrip("#").lower()
        assert THEMES[name]["accent"].lower() == registry_accent
