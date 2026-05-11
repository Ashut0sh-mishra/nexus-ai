"""Phase 6L — deterministic backend theme registry.

Maps a ``theme_id`` to a structured set of presentation design tokens
(colors, fonts, spacing, radius, chart palette) so downstream renderers,
exporters, and audits can resolve theming from a single source of truth.

Scope (intentionally narrow):
* Pure-Python, deterministic, side-effect free.
* No LLM, no network, no filesystem writes.
* Does not change the 7 canonical layouts or any existing API contract.
* Does not auto-mutate decks; integration is via opt-in helpers
  (``resolve_theme`` / ``apply_theme``) that consumers may call.

Design notes:
* The legacy renderer in ``backend/services/export_service.py`` keeps its
  own minimal ``THEMES`` palette keyed by display names like
  ``"Editorial"`` / ``"Pixel"``. This registry is a richer parallel
  source-of-truth keyed by stable, lowercase ``theme_id`` slugs and
  exposes the same accent/bg/text colors plus extra structured tokens
  (fonts, spacing, radius, chart palette). Legacy display names are
  resolved through ``LEGACY_THEME_ALIASES`` so existing decks keep
  working without schema changes.
* Adding ``theme_id`` to deck metadata is **optional**. If a deck does
  not carry one, ``resolve_theme`` falls back to the default theme.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"

DEFAULT_THEME_ID = "nexus-default"


@dataclass(frozen=True)
class Theme:
    """A frozen, structured set of presentation design tokens."""

    theme_id: str
    display_name: str
    colors: Mapping[str, str]
    fonts: Mapping[str, str]
    spacing: Mapping[str, int]
    radius: Mapping[str, int]
    chart_palette: tuple[str, ...]

    def to_tokens(self) -> dict[str, Any]:
        """Return a plain-dict, JSON-safe view of the theme tokens."""

        return {
            "schema_version": SCHEMA_VERSION,
            "theme_id": self.theme_id,
            "display_name": self.display_name,
            "colors": dict(self.colors),
            "fonts": dict(self.fonts),
            "spacing": dict(self.spacing),
            "radius": dict(self.radius),
            "chart_palette": list(self.chart_palette),
        }


# ── Built-in themes ────────────────────────────────────────────────────────
# Two themes are required by Phase 6L: a default that is compatible with the
# current renderer's "Editorial" palette, and at least one alternate.

_NEXUS_DEFAULT = Theme(
    theme_id="nexus-default",
    display_name="Nexus Default",
    colors={
        "bg": "#0F0F14",
        "surface": "#16161D",
        "text": "#F5F5F7",
        "muted": "#9A9AA5",
        "accent": "#A78BFA",
        "accent_alt": "#7C3AED",
        "border": "#2A2A33",
    },
    fonts={
        "heading": "Inter, system-ui, sans-serif",
        "body": "Inter, system-ui, sans-serif",
        "mono": "JetBrains Mono, ui-monospace, monospace",
    },
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=(
        "#A78BFA",
        "#60A5FA",
        "#34D399",
        "#F59E0B",
        "#F472B6",
        "#22D3EE",
    ),
)


_NEXUS_LIGHT = Theme(
    theme_id="nexus-light",
    display_name="Nexus Light",
    colors={
        "bg": "#FAF7F2",
        "surface": "#FFFFFF",
        "text": "#1F1A14",
        "muted": "#6B5E4A",
        "accent": "#A0522D",
        "accent_alt": "#7A3E22",
        "border": "#E5DED2",
    },
    fonts={
        "heading": "Source Serif Pro, Georgia, serif",
        "body": "Inter, system-ui, sans-serif",
        "mono": "JetBrains Mono, ui-monospace, monospace",
    },
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=(
        "#A0522D",
        "#3F6B7A",
        "#6B8E23",
        "#C46A2C",
        "#8E5A8A",
        "#2F6F75",
    ),
)


# Phase 6O — register the remaining three legacy display names as
# first-class themes with structured tokens. The token values mirror the
# existing palettes hard-coded in ``backend/services/export_service.py``
# and ``frontend/src/components/SlideRenderer.jsx`` so the registry can
# act as the single source of truth across preview, editor, presenter,
# share, and export. Theme ids are stored lowercase; ``_normalize_id``
# lowercases lookups, so legacy mixed-case names like ``"Pixel"`` /
# ``"Dossier"`` continue to resolve.

_PIXEL = Theme(
    theme_id="pixel",
    display_name="Pixel",
    colors={
        "bg": "#101820",
        "surface": "#1A2A33",
        "text": "#F1FAEE",
        "muted": "#94A3B8",
        "accent": "#34D399",
        "accent_alt": "#22D3EE",
        "border": "#1F2A36",
    },
    fonts={
        "heading": "Inter, system-ui, sans-serif",
        "body": "Inter, system-ui, sans-serif",
        "mono": "JetBrains Mono, ui-monospace, monospace",
    },
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=(
        "#34D399",
        "#22D3EE",
        "#A78BFA",
        "#F472B6",
        "#FBBF24",
        "#60A5FA",
    ),
)


_DOSSIER = Theme(
    theme_id="dossier",
    display_name="Dossier",
    colors={
        "bg": "#0B1220",
        "surface": "#1E293B",
        "text": "#E2E8F0",
        "muted": "#94A3B8",
        "accent": "#60A5FA",
        "accent_alt": "#38BDF8",
        "border": "#1F2A40",
    },
    fonts={
        "heading": "Source Serif Pro, Georgia, serif",
        "body": "Inter, system-ui, sans-serif",
        "mono": "JetBrains Mono, ui-monospace, monospace",
    },
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=(
        "#60A5FA",
        "#38BDF8",
        "#A78BFA",
        "#34D399",
        "#FBBF24",
        "#F472B6",
    ),
)


_LIGHT_PRO = Theme(
    theme_id="light-pro",
    display_name="Light Pro",
    colors={
        "bg": "#FFFFFF",
        "surface": "#F8FAFC",
        "text": "#111827",
        "muted": "#6B7280",
        "accent": "#F59E0B",
        "accent_alt": "#D97706",
        "border": "#E5E7EB",
    },
    fonts={
        "heading": "Inter, system-ui, sans-serif",
        "body": "Inter, system-ui, sans-serif",
        "mono": "JetBrains Mono, ui-monospace, monospace",
    },
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=(
        "#F59E0B",
        "#0EA5E9",
        "#10B981",
        "#8B5CF6",
        "#EF4444",
        "#6B7280",
    ),
)


_WHITEBOARD = Theme(
    theme_id="whiteboard",
    display_name="Whiteboard",
    colors={"bg": "#FFFFFF", "surface": "#F9FAFB", "text": "#111827", "muted": "#9CA3AF",
            "accent": "#374151", "accent_alt": "#1F2937", "border": "#E5E7EB"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#374151", "#0EA5E9", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444"),
)

_SKETCH = Theme(
    theme_id="sketch",
    display_name="Sketch",
    colors={"bg": "#F9F5F0", "surface": "#F2EDE6", "text": "#1C1917", "muted": "#78716C",
            "accent": "#292524", "accent_alt": "#44403C", "border": "#D6CFC5"},
    fonts={"heading": "Georgia, serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#292524", "#A16207", "#166534", "#1D4ED8", "#7C3AED", "#B91C1C"),
)

_GLAMOUR = Theme(
    theme_id="glamour",
    display_name="Glamour",
    colors={"bg": "#120A1A", "surface": "#1E0F2E", "text": "#FDF6E3", "muted": "#C9A870",
            "accent": "#D4AF37", "accent_alt": "#B8960C", "border": "#2E1A44"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#D4AF37", "#F472B6", "#A78BFA", "#60A5FA", "#34D399", "#FB923C"),
)

_AMBER = Theme(
    theme_id="amber",
    display_name="Amber",
    colors={"bg": "#1C1000", "surface": "#2D1C00", "text": "#FEF3C7", "muted": "#D97706",
            "accent": "#F59E0B", "accent_alt": "#D97706", "border": "#3D2800"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#F59E0B", "#FBBF24", "#FCD34D", "#F97316", "#EF4444", "#10B981"),
)

_ARCTIC = Theme(
    theme_id="arctic",
    display_name="Arctic",
    colors={"bg": "#EFF6FF", "surface": "#DBEAFE", "text": "#1E3A5F", "muted": "#3B82F6",
            "accent": "#1D4ED8", "accent_alt": "#1E40AF", "border": "#BFDBFE"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#1D4ED8", "#2563EB", "#0EA5E9", "#38BDF8", "#7DD3FC", "#0284C7"),
)

_CERULEAN = Theme(
    theme_id="cerulean",
    display_name="Cerulean",
    colors={"bg": "#0C2340", "surface": "#163260", "text": "#F0F9FF", "muted": "#7DD3FC",
            "accent": "#38BDF8", "accent_alt": "#0EA5E9", "border": "#1A3A6E"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#38BDF8", "#60A5FA", "#A78BFA", "#34D399", "#FBBF24", "#F472B6"),
)

_COBALT = Theme(
    theme_id="cobalt",
    display_name="Cobalt",
    colors={"bg": "#05082A", "surface": "#0D1660", "text": "#EEF2FF", "muted": "#818CF8",
            "accent": "#6366F1", "accent_alt": "#4F46E5", "border": "#1E2070"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#6366F1", "#818CF8", "#38BDF8", "#34D399", "#FBBF24", "#F472B6"),
)

_EMERALD = Theme(
    theme_id="emerald",
    display_name="Emerald",
    colors={"bg": "#052E16", "surface": "#064E3B", "text": "#ECFDF5", "muted": "#6EE7B7",
            "accent": "#34D399", "accent_alt": "#10B981", "border": "#065F46"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#34D399", "#10B981", "#A3E635", "#60A5FA", "#FBBF24", "#F472B6"),
)

_BASALT = Theme(
    theme_id="basalt",
    display_name="Basalt",
    colors={"bg": "#0A0A0A", "surface": "#18181B", "text": "#FAFAFA", "muted": "#71717A",
            "accent": "#A1A1AA", "accent_alt": "#D4D4D8", "border": "#27272A"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#A1A1AA", "#60A5FA", "#34D399", "#FBBF24", "#F472B6", "#FB923C"),
)

_MIST = Theme(
    theme_id="mist",
    display_name="Mist",
    colors={"bg": "#F1F5F9", "surface": "#E2E8F0", "text": "#1E293B", "muted": "#94A3B8",
            "accent": "#475569", "accent_alt": "#334155", "border": "#CBD5E1"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#475569", "#0EA5E9", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444"),
)

_ONYX = Theme(
    theme_id="onyx",
    display_name="Onyx",
    colors={"bg": "#09090B", "surface": "#18181B", "text": "#FAFAFA", "muted": "#71717A",
            "accent": "#FAFAFA", "accent_alt": "#E4E4E7", "border": "#27272A"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#FAFAFA", "#E4E4E7", "#60A5FA", "#34D399", "#FBBF24", "#F472B6"),
)

_SAND = Theme(
    theme_id="sand",
    display_name="Sand",
    colors={"bg": "#FEFCE8", "surface": "#FEF9C3", "text": "#1C1207", "muted": "#78716C",
            "accent": "#92400E", "accent_alt": "#B45309", "border": "#FDE68A"},
    fonts={"heading": "Georgia, serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#92400E", "#B45309", "#D97706", "#65A30D", "#0891B2", "#7C3AED"),
)

_NEON = Theme(
    theme_id="neon",
    display_name="Neon",
    colors={"bg": "#020617", "surface": "#0A0A1F", "text": "#F0FFF4", "muted": "#86EFAC",
            "accent": "#4ADE80", "accent_alt": "#22C55E", "border": "#14231A"},
    fonts={"heading": "Inter, system-ui, sans-serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#4ADE80", "#22D3EE", "#F472B6", "#FBBF24", "#A78BFA", "#60A5FA"),
)

_LINEN = Theme(
    theme_id="linen",
    display_name="Linen",
    colors={"bg": "#FAF0E6", "surface": "#F5E6D3", "text": "#2C1810", "muted": "#92400E",
            "accent": "#7C2D12", "accent_alt": "#9A3412", "border": "#E8D5C0"},
    fonts={"heading": "Georgia, serif", "body": "Inter, system-ui, sans-serif",
           "mono": "JetBrains Mono, ui-monospace, monospace"},
    spacing={"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40},
    radius={"sm": 4, "md": 8, "lg": 16},
    chart_palette=("#7C2D12", "#A16207", "#15803D", "#1D4ED8", "#7C3AED", "#B91C1C"),
)


BUILTIN_THEMES: dict[str, Theme] = {
    _NEXUS_DEFAULT.theme_id: _NEXUS_DEFAULT,
    _NEXUS_LIGHT.theme_id: _NEXUS_LIGHT,
    _PIXEL.theme_id: _PIXEL,
    _DOSSIER.theme_id: _DOSSIER,
    _LIGHT_PRO.theme_id: _LIGHT_PRO,
    _WHITEBOARD.theme_id: _WHITEBOARD,
    _SKETCH.theme_id: _SKETCH,
    _GLAMOUR.theme_id: _GLAMOUR,
    _AMBER.theme_id: _AMBER,
    _ARCTIC.theme_id: _ARCTIC,
    _CERULEAN.theme_id: _CERULEAN,
    _COBALT.theme_id: _COBALT,
    _EMERALD.theme_id: _EMERALD,
    _BASALT.theme_id: _BASALT,
    _MIST.theme_id: _MIST,
    _ONYX.theme_id: _ONYX,
    _SAND.theme_id: _SAND,
    _NEON.theme_id: _NEON,
    _LINEN.theme_id: _LINEN,
}


# Legacy names used by ``backend/services/export_service.py`` and the existing
# ``Task.theme`` column. They resolve to a built-in theme so existing decks
# (with ``theme="Editorial"`` etc.) keep working without DB migrations.
# Phase 6O note: ``pixel`` / ``dossier`` / ``light-pro`` are now first-class
# theme ids (resolved directly via ``BUILTIN_THEMES``), so they intentionally
# do not appear here. Mixed-case display names like ``"Pixel"`` still match
# because ``_normalize_id`` lowercases lookups.
LEGACY_THEME_ALIASES: dict[str, str] = {
    "editorial": "nexus-default",
    "vellum": "nexus-light",
    # Phase 6O design invariant restored (Phase 6X–6AE acceptance pass):
    # the 14 themes promoted to first-class entries in ``BUILTIN_THEMES``
    # (whiteboard / sketch / glamour / amber / arctic / cerulean / cobalt /
    # emerald / basalt / mist / onyx / sand / neon / linen) resolve directly
    # via ``BUILTIN_THEMES`` because ``_normalize_id`` already lowercases
    # the lookup. Adding ``"whiteboard": "whiteboard"`` etc. as self-aliases
    # is redundant and breaks the test invariant
    # ``test_aliases_only_cover_editorial_and_vellum``. Self-aliases must
    # never be added here; only legacy display-name → canonical-id
    # translations belong in this dict.
}


# ── Public helpers ─────────────────────────────────────────────────────────


def list_theme_ids() -> list[str]:
    """Return all built-in theme ids in deterministic (sorted) order."""

    return sorted(BUILTIN_THEMES.keys())


def _normalize_id(theme_id: Any) -> str | None:
    if not isinstance(theme_id, str):
        return None
    s = theme_id.strip()
    if not s:
        return None
    return s.lower()


def get_theme(theme_id: Any, *, strict: bool = False) -> Theme:
    """Resolve a theme by id with safe, deterministic fallback.

    * Exact match against ``BUILTIN_THEMES`` (case-insensitive).
    * Then ``LEGACY_THEME_ALIASES`` (case-insensitive).
    * If ``strict`` is True and nothing matches, raises ``ValueError``.
    * Otherwise falls back to the default theme.
    """

    norm = _normalize_id(theme_id)
    if norm is not None:
        if norm in BUILTIN_THEMES:
            return BUILTIN_THEMES[norm]
        alias = LEGACY_THEME_ALIASES.get(norm)
        if alias is not None and alias in BUILTIN_THEMES:
            return BUILTIN_THEMES[alias]

    if strict:
        raise ValueError(
            f"unknown theme_id: {theme_id!r}; known={list_theme_ids()}"
        )
    return BUILTIN_THEMES[DEFAULT_THEME_ID]


def resolve_theme(deck: Any, *, strict: bool = False) -> Theme:
    """Resolve the theme for a deck dict.

    Reads ``theme_id`` first (Phase 6L canonical key), then falls back to
    the legacy ``theme`` field, then to the default theme. Non-dict input
    yields the default theme.
    """

    if not isinstance(deck, dict):
        return BUILTIN_THEMES[DEFAULT_THEME_ID]
    candidate = deck.get("theme_id")
    if _normalize_id(candidate) is None:
        candidate = deck.get("theme")
    return get_theme(candidate, strict=strict)


def apply_theme(deck: Mapping[str, Any], theme_id: Any = None) -> dict[str, Any]:
    """Return a new deck dict annotated with resolved theme tokens.

    * Does **not** mutate the input.
    * Sets ``theme_id`` to the resolved canonical id.
    * Sets ``theme_tokens`` to the structured token dict.
    * Leaves all other deck fields (including ``slides``) untouched.
    * If ``theme_id`` argument is None, the value is read from the deck
      (``theme_id`` then legacy ``theme``).
    """

    if not isinstance(deck, Mapping):
        raise TypeError("deck must be a mapping")

    if theme_id is None:
        theme = resolve_theme(deck)
    else:
        theme = get_theme(theme_id)

    out: dict[str, Any] = dict(deck)
    out["theme_id"] = theme.theme_id
    out["theme_tokens"] = theme.to_tokens()
    return out


# Token field names that ``apply_theme`` is allowed to add or change. Used
# by tests to assert that theming a deck does not perturb anything else.
THEME_DERIVED_KEYS: frozenset[str] = frozenset({"theme_id", "theme_tokens"})


__all__ = [
    "SCHEMA_VERSION",
    "DEFAULT_THEME_ID",
    "Theme",
    "BUILTIN_THEMES",
    "LEGACY_THEME_ALIASES",
    "THEME_DERIVED_KEYS",
    "list_theme_ids",
    "get_theme",
    "resolve_theme",
    "apply_theme",
]
