/**
 * Phase 6O — frontend theme registry mirror.
 *
 * Hand-mirrored from ``backend/agent/themes_registry.py`` so the deck
 * preview, editor (`SlideRenderer`), presenter, and shared view all
 * resolve themes through a single map. Token values match the backend
 * registry colors and the legacy palettes already used by
 * ``backend/services/export_service.py`` so PPTX/PDF exports look the
 * same as the on-screen preview.
 *
 * Legacy display names ("Editorial", "Pixel", "Vellum", "Dossier",
 * "light-pro") are first-class keys here; ``paletteFor`` falls back to
 * Editorial for unknown names so existing decks keep rendering.
 *
 * The frontend can also call ``GET /api/themes`` to refresh from the
 * backend, but rendering does not block on that fetch — the static
 * mirror below is always sufficient to draw a slide.
 */

export const themePalettes = {
  "light-pro": {
    bg: "#FFFFFF",
    accent: "#F59E0B",
    text: "#111827",
    muted: "#6B7280",
    chartPalette: ["#F59E0B", "#0EA5E9", "#10B981", "#8B5CF6", "#EF4444", "#6B7280"],
  },
  Editorial: {
    bg: "linear-gradient(135deg,#0F0F14 0%,#1A1A22 100%)",
    accent: "#A78BFA",
    text: "#F5F5F7",
    muted: "#9A9AA5",
    chartPalette: ["#A78BFA", "#60A5FA", "#34D399", "#F59E0B", "#F472B6", "#22D3EE"],
  },
  Pixel: {
    bg: "linear-gradient(135deg,#101820 0%,#1A2A33 100%)",
    accent: "#34D399",
    text: "#F1FAEE",
    muted: "#94A3B8",
    chartPalette: ["#34D399", "#22D3EE", "#A78BFA", "#F472B6", "#FBBF24", "#60A5FA"],
  },
  Vellum: {
    bg: "linear-gradient(135deg,#FAF7F2 0%,#EFE9DD 100%)",
    accent: "#A0522D",
    text: "#1F1A14",
    muted: "#6B5E4A",
    chartPalette: ["#A0522D", "#3F6B7A", "#6B8E23", "#C46A2C", "#8E5A8A", "#2F6F75"],
  },
  Dossier: {
    bg: "linear-gradient(135deg,#0B1220 0%,#1E293B 100%)",
    accent: "#60A5FA",
    text: "#E2E8F0",
    muted: "#94A3B8",
    chartPalette: ["#60A5FA", "#38BDF8", "#A78BFA", "#34D399", "#FBBF24", "#F472B6"],
  },
  Whiteboard: {
    bg: "#FFFFFF",
    accent: "#374151",
    text: "#111827",
    muted: "#9CA3AF",
    chartPalette: ["#374151", "#0EA5E9", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444"],
  },
  Sketch: {
    bg: "linear-gradient(135deg,#F9F5F0 0%,#F2EDE6 100%)",
    accent: "#292524",
    text: "#1C1917",
    muted: "#78716C",
    chartPalette: ["#292524", "#A16207", "#166534", "#1D4ED8", "#7C3AED", "#B91C1C"],
  },
  Glamour: {
    bg: "linear-gradient(135deg,#120A1A 0%,#1E0F2E 100%)",
    accent: "#D4AF37",
    text: "#FDF6E3",
    muted: "#C9A870",
    chartPalette: ["#D4AF37", "#F472B6", "#A78BFA", "#60A5FA", "#34D399", "#FB923C"],
  },
  Amber: {
    bg: "linear-gradient(135deg,#1C1000 0%,#2D1C00 100%)",
    accent: "#F59E0B",
    text: "#FEF3C7",
    muted: "#D97706",
    chartPalette: ["#F59E0B", "#FBBF24", "#FCD34D", "#F97316", "#EF4444", "#10B981"],
  },
  Arctic: {
    bg: "linear-gradient(135deg,#EFF6FF 0%,#DBEAFE 100%)",
    accent: "#1D4ED8",
    text: "#1E3A5F",
    muted: "#3B82F6",
    chartPalette: ["#1D4ED8", "#2563EB", "#0EA5E9", "#38BDF8", "#7DD3FC", "#0284C7"],
  },
  Cerulean: {
    bg: "linear-gradient(135deg,#0C2340 0%,#163260 100%)",
    accent: "#38BDF8",
    text: "#F0F9FF",
    muted: "#7DD3FC",
    chartPalette: ["#38BDF8", "#60A5FA", "#A78BFA", "#34D399", "#FBBF24", "#F472B6"],
  },
  Cobalt: {
    bg: "linear-gradient(135deg,#05082A 0%,#0D1660 100%)",
    accent: "#6366F1",
    text: "#EEF2FF",
    muted: "#818CF8",
    chartPalette: ["#6366F1", "#818CF8", "#38BDF8", "#34D399", "#FBBF24", "#F472B6"],
  },
  Emerald: {
    bg: "linear-gradient(135deg,#052E16 0%,#064E3B 100%)",
    accent: "#34D399",
    text: "#ECFDF5",
    muted: "#6EE7B7",
    chartPalette: ["#34D399", "#10B981", "#A3E635", "#60A5FA", "#FBBF24", "#F472B6"],
  },
  Basalt: {
    bg: "linear-gradient(135deg,#0A0A0A 0%,#18181B 100%)",
    accent: "#A1A1AA",
    text: "#FAFAFA",
    muted: "#71717A",
    chartPalette: ["#A1A1AA", "#60A5FA", "#34D399", "#FBBF24", "#F472B6", "#FB923C"],
  },
  Mist: {
    bg: "linear-gradient(135deg,#F1F5F9 0%,#E2E8F0 100%)",
    accent: "#475569",
    text: "#1E293B",
    muted: "#94A3B8",
    chartPalette: ["#475569", "#0EA5E9", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444"],
  },
  Onyx: {
    bg: "#09090B",
    accent: "#FAFAFA",
    text: "#FAFAFA",
    muted: "#71717A",
    chartPalette: ["#FAFAFA", "#E4E4E7", "#60A5FA", "#34D399", "#FBBF24", "#F472B6"],
  },
  Sand: {
    bg: "linear-gradient(135deg,#FEFCE8 0%,#FEF9C3 100%)",
    accent: "#92400E",
    text: "#1C1207",
    muted: "#78716C",
    chartPalette: ["#92400E", "#B45309", "#D97706", "#65A30D", "#0891B2", "#7C3AED"],
  },
  Neon: {
    bg: "linear-gradient(135deg,#020617 0%,#0A0A1F 100%)",
    accent: "#4ADE80",
    text: "#F0FFF4",
    muted: "#86EFAC",
    chartPalette: ["#4ADE80", "#22D3EE", "#F472B6", "#FBBF24", "#A78BFA", "#60A5FA"],
  },
  Linen: {
    bg: "linear-gradient(135deg,#FAF0E6 0%,#F5E6D3 100%)",
    accent: "#7C2D12",
    text: "#2C1810",
    muted: "#92400E",
    chartPalette: ["#7C2D12", "#A16207", "#15803D", "#1D4ED8", "#7C3AED", "#B91C1C"],
  },
};

export const DEFAULT_THEME_NAME = "Editorial";

/**
 * Resolve a theme name to its palette. Accepts legacy mixed-case names
 * (``Pixel``, ``Editorial``) as well as exact matches. Unknown names
 * fall back to the default theme so the renderer never throws.
 */
export function paletteFor(theme) {
  if (theme && Object.prototype.hasOwnProperty.call(themePalettes, theme)) {
    return themePalettes[theme];
  }
  // Case-insensitive secondary match (handles e.g. "editorial").
  if (typeof theme === "string") {
    const lower = theme.toLowerCase();
    for (const key of Object.keys(themePalettes)) {
      if (key.toLowerCase() === lower) return themePalettes[key];
    }
  }
  return themePalettes[DEFAULT_THEME_NAME];
}

export function listThemeNames() {
  return Object.keys(themePalettes);
}
