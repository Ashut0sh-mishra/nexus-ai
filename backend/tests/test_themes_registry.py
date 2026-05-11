"""Phase 6L — tests for the deterministic backend theme registry.

Pure offline tests. No network, no LLM, no filesystem writes, no DB.
"""

from __future__ import annotations

import copy

import pytest

from agent.themes_registry import (
    BUILTIN_THEMES,
    DEFAULT_THEME_ID,
    LEGACY_THEME_ALIASES,
    SCHEMA_VERSION,
    THEME_DERIVED_KEYS,
    Theme,
    apply_theme,
    get_theme,
    list_theme_ids,
    resolve_theme,
)
from agent.slide_schema import validate_deck


# ── Sample deck fixture ────────────────────────────────────────────────────

def _sample_deck() -> dict:
    return {
        "task_id": "phase6l-001",
        "topic": "Phase 6L theme registry smoke",
        "theme": "Editorial",  # legacy field, intentionally present
        "slide_count": 3,
        "slides": [
            {
                "layout": "title",
                "title": "Phase 6L",
                "subtitle": "Theme tokens, deterministic.",
                "eyebrow": "",
            },
            {
                "layout": "bullets",
                "title": "Why a theme registry",
                "bullets": [
                    "Single source of truth for design tokens.",
                    "Decouples theme id from the legacy palette dict.",
                    "Enables theme-aware testing.",
                ],
            },
            {
                "layout": "closing",
                "title": "Summary",
                "subtitle": "Phase 6L is surface infrastructure only.",
                "cta": "",
            },
        ],
    }


# ── Registry shape ─────────────────────────────────────────────────────────


def test_schema_version_is_string():
    assert isinstance(SCHEMA_VERSION, str)
    assert SCHEMA_VERSION


def test_registry_contains_default_and_alternate():
    ids = list_theme_ids()
    assert DEFAULT_THEME_ID in ids
    assert "nexus-light" in ids
    assert len(ids) >= 2


def test_registry_keys_match_theme_ids():
    for key, theme in BUILTIN_THEMES.items():
        assert isinstance(theme, Theme)
        assert key == theme.theme_id


def test_list_theme_ids_is_sorted_and_deterministic():
    a = list_theme_ids()
    b = list_theme_ids()
    assert a == b
    assert a == sorted(a)


def test_each_theme_exposes_required_token_groups():
    required_color_keys = {"bg", "text", "muted", "accent"}
    required_font_keys = {"heading", "body"}
    required_spacing_keys = {"sm", "md", "lg"}
    required_radius_keys = {"sm", "md"}

    for theme in BUILTIN_THEMES.values():
        assert isinstance(theme.theme_id, str) and theme.theme_id
        assert isinstance(theme.display_name, str) and theme.display_name
        assert required_color_keys.issubset(theme.colors.keys())
        assert required_font_keys.issubset(theme.fonts.keys())
        assert required_spacing_keys.issubset(theme.spacing.keys())
        assert required_radius_keys.issubset(theme.radius.keys())
        assert isinstance(theme.chart_palette, tuple)
        assert len(theme.chart_palette) >= 3
        # Every color is a hex-ish string starting with '#'.
        for v in theme.colors.values():
            assert isinstance(v, str)
            assert v.startswith("#") and len(v) in (4, 7, 9)
        # Spacing/radius are non-negative ints.
        for v in list(theme.spacing.values()) + list(theme.radius.values()):
            assert isinstance(v, int) and v >= 0


def test_to_tokens_round_trip():
    theme = BUILTIN_THEMES[DEFAULT_THEME_ID]
    tokens = theme.to_tokens()
    assert tokens["theme_id"] == theme.theme_id
    assert tokens["display_name"] == theme.display_name
    assert tokens["colors"] == dict(theme.colors)
    assert tokens["fonts"] == dict(theme.fonts)
    assert tokens["spacing"] == dict(theme.spacing)
    assert tokens["radius"] == dict(theme.radius)
    assert tokens["chart_palette"] == list(theme.chart_palette)
    assert tokens["schema_version"] == SCHEMA_VERSION


# ── get_theme behavior ─────────────────────────────────────────────────────


def test_get_theme_known_id_returns_exact_theme():
    t = get_theme("nexus-light")
    assert t.theme_id == "nexus-light"


def test_get_theme_is_case_insensitive():
    a = get_theme("NEXUS-DEFAULT")
    b = get_theme("nexus-default")
    assert a is b


def test_get_theme_unknown_falls_back_to_default():
    t = get_theme("does-not-exist")
    assert t.theme_id == DEFAULT_THEME_ID


def test_get_theme_unknown_strict_raises():
    with pytest.raises(ValueError):
        get_theme("does-not-exist", strict=True)


def test_get_theme_none_or_empty_falls_back_to_default():
    for v in (None, "", "   ", 42, [], {}):
        t = get_theme(v)
        assert t.theme_id == DEFAULT_THEME_ID


def test_legacy_alias_resolves():
    for legacy, canonical in LEGACY_THEME_ALIASES.items():
        t = get_theme(legacy)
        assert t.theme_id == canonical
        # Aliases are case-insensitive.
        t2 = get_theme(legacy.upper())
        assert t2.theme_id == canonical


def test_get_theme_is_deterministic():
    for tid in list_theme_ids():
        a = get_theme(tid)
        b = get_theme(tid)
        assert a is b


# ── resolve_theme behavior ─────────────────────────────────────────────────


def test_resolve_theme_prefers_theme_id_over_legacy_theme():
    deck = {"theme_id": "nexus-light", "theme": "Editorial"}
    assert resolve_theme(deck).theme_id == "nexus-light"


def test_resolve_theme_falls_back_to_legacy_theme_field():
    deck = {"theme": "Editorial"}
    # Editorial aliases to nexus-default.
    assert resolve_theme(deck).theme_id == "nexus-default"


def test_resolve_theme_non_dict_input_returns_default():
    for v in (None, 0, "string", [1, 2], object()):
        assert resolve_theme(v).theme_id == DEFAULT_THEME_ID


def test_resolve_theme_unknown_field_falls_back_to_default():
    deck = {"theme_id": "no-such", "theme": "no-such-either"}
    assert resolve_theme(deck).theme_id == DEFAULT_THEME_ID


# ── apply_theme + deck integrity ───────────────────────────────────────────


def test_apply_theme_does_not_mutate_input():
    deck = _sample_deck()
    snapshot = copy.deepcopy(deck)
    _ = apply_theme(deck, "nexus-light")
    assert deck == snapshot


def test_apply_theme_only_changes_theme_derived_fields():
    deck = _sample_deck()
    a = apply_theme(deck, "nexus-default")
    b = apply_theme(deck, "nexus-light")

    # Same deck-derived keys, same values, except for theme-derived ones.
    assert set(a.keys()) == set(b.keys())
    diff_keys = {k for k in a.keys() if a[k] != b[k]}
    assert diff_keys.issubset(THEME_DERIVED_KEYS)
    assert diff_keys, "switching themes must change at least theme-derived fields"

    # And specifically the slides payload is byte-identical.
    assert a["slides"] == b["slides"]
    assert a["topic"] == b["topic"]
    assert a["slide_count"] == b["slide_count"]


def test_apply_theme_resolved_id_canonical():
    deck = _sample_deck()
    out = apply_theme(deck, "Editorial")  # legacy alias
    assert out["theme_id"] == "nexus-default"
    assert out["theme_tokens"]["theme_id"] == "nexus-default"


def test_apply_theme_unknown_id_falls_back_to_default():
    deck = _sample_deck()
    out = apply_theme(deck, "no-such-theme")
    assert out["theme_id"] == DEFAULT_THEME_ID


def test_apply_theme_reads_from_deck_when_arg_omitted():
    deck = dict(_sample_deck(), theme_id="nexus-light")
    out = apply_theme(deck)
    assert out["theme_id"] == "nexus-light"


def test_apply_theme_rejects_non_mapping():
    with pytest.raises(TypeError):
        apply_theme("not-a-deck", "nexus-default")  # type: ignore[arg-type]


def test_apply_theme_preserves_slide_validation():
    """Phase 6L must not break the canonical 7-layout slide schema."""
    deck = _sample_deck()
    out = apply_theme(deck, "nexus-light")
    results = validate_deck(out["slides"])
    assert all(r.ok for r in results), [
        e.to_dict() for r in results for e in r.errors
    ]


def test_apply_theme_is_deterministic():
    deck = _sample_deck()
    a = apply_theme(deck, "nexus-light")
    b = apply_theme(deck, "nexus-light")
    assert a == b


# ── No legacy palette regression ───────────────────────────────────────────


def test_legacy_export_palette_still_imports():
    """Phase 6L must not have replaced the legacy renderer palette."""
    from services.export_service import THEMES

    # The legacy renderer keeps its own palette keyed by display names.
    # We do not require Phase 6L to migrate it; we just assert it still
    # exists so existing exports keep working.
    assert "Editorial" in THEMES
    assert THEMES["Editorial"]["accent"]
