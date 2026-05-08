// design/theme-engine.js — palette catalog + resolver.
//
// Single source of truth for slide palettes. Editor chrome reads from
// design/tokens.js; SLIDE content reads from here.
//
// A palette has the shape:
//   { bg, surface, accent, accentSoft, text, muted, border }
//
// Older palettes only exposed { bg, accent, text, muted } — `palettize()`
// fills in the missing fields deterministically so callers always get the
// full shape. New palettes should specify all 7 fields explicitly.

// ─── Catalog ────────────────────────────────────────────────────────────────
// 60+ premium themes. Names roughly match slidesalad.com's catalog so each
// new deck feels like a different template.
const RAW_THEMES = {
  // — Originals (kept for backward compatibility) —
  "light-pro": { bg: "#FFFFFF",                                                accent: "#F59E0B", text: "#111827", muted: "#6B7280" },
  Editorial:   { bg: "linear-gradient(135deg,#0F0F14 0%,#1A1A22 100%)",        accent: "#A78BFA", text: "#F5F5F7", muted: "#9A9AA5" },
  Pixel:       { bg: "linear-gradient(135deg,#101820 0%,#1A2A33 100%)",        accent: "#34D399", text: "#F1FAEE", muted: "#94A3B8" },
  Vellum:      { bg: "linear-gradient(135deg,#FAF7F2 0%,#EFE9DD 100%)",        accent: "#A0522D", text: "#1F1A14", muted: "#6B5E4A" },
  Dossier:     { bg: "linear-gradient(135deg,#0B1220 0%,#1E293B 100%)",        accent: "#60A5FA", text: "#E2E8F0", muted: "#94A3B8" },
  // — Light, vivid —
  Complete:    { bg: "linear-gradient(135deg,#FFFFFF 0%,#F1F5F9 100%)", accent: "#2563EB", text: "#0F172A", muted: "#64748B" },
  Golden:      { bg: "linear-gradient(135deg,#FFFBEB 0%,#FEF3C7 100%)", accent: "#D97706", text: "#1C1917", muted: "#78716C" },
  Simplicity:  { bg: "#FFFFFF",                                          accent: "#0EA5E9", text: "#0F172A", muted: "#64748B" },
  Marketing:   { bg: "linear-gradient(135deg,#FEF2F2 0%,#FEE2E2 100%)", accent: "#DC2626", text: "#1A0A0A", muted: "#78716C" },
  Proposal:    { bg: "linear-gradient(135deg,#F5F3FF 0%,#EDE9FE 100%)", accent: "#7C3AED", text: "#1E1B2E", muted: "#6B6B7B" },
  Strategy:    { bg: "linear-gradient(135deg,#ECFEFF 0%,#CFFAFE 100%)", accent: "#0891B2", text: "#083344", muted: "#475569" },
  Launch:      { bg: "linear-gradient(135deg,#FFF7ED 0%,#FFEDD5 100%)", accent: "#EA580C", text: "#1C1917", muted: "#78716C" },
  Growth:      { bg: "linear-gradient(135deg,#F0FDF4 0%,#BBF7D0 100%)", accent: "#16A34A", text: "#0E1F17", muted: "#475569" },
  Plan:        { bg: "linear-gradient(135deg,#EFF6FF 0%,#DBEAFE 100%)", accent: "#2563EB", text: "#0C1E2E", muted: "#64748B" },
  Pitch:       { bg: "linear-gradient(135deg,#FAF5FF 0%,#E9D5FF 100%)", accent: "#9333EA", text: "#1F0A2E", muted: "#6B5B7B" },
  Sales:       { bg: "linear-gradient(135deg,#FEF2F2 0%,#FECACA 100%)", accent: "#E11D48", text: "#1F0A14", muted: "#78716C" },
  Plan2:       { bg: "linear-gradient(135deg,#F0FDFA 0%,#CCFBF1 100%)", accent: "#0D9488", text: "#0E1F1A", muted: "#475569" },
  Multi:       { bg: "linear-gradient(135deg,#FEFCE8 0%,#FEF08A 100%)", accent: "#CA8A04", text: "#1C1917", muted: "#78716C" },
  Stunning:    { bg: "linear-gradient(135deg,#FDF4FF 0%,#FAE8FF 100%)", accent: "#C026D3", text: "#1F0A1F", muted: "#6B5263" },
  Profile:     { bg: "linear-gradient(135deg,#F8FAFC 0%,#E2E8F0 100%)", accent: "#1E40AF", text: "#0F172A", muted: "#475569" },
  Annual:      { bg: "linear-gradient(135deg,#F1F5F9 0%,#CBD5E1 100%)", accent: "#0F766E", text: "#0F172A", muted: "#475569" },
  Review:      { bg: "linear-gradient(135deg,#FEFEFE 0%,#F3F4F6 100%)", accent: "#7C3AED", text: "#111827", muted: "#6B7280" },
  Minimal:     { bg: "#FAFAFA",                                          accent: "#18181B", text: "#09090B", muted: "#71717A" },
  Simple:      { bg: "#FFFFFF",                                          accent: "#10B981", text: "#0F172A", muted: "#64748B" },
  Elegant:     { bg: "linear-gradient(135deg,#FAF7F2 0%,#F3E8DD 100%)", accent: "#92400E", text: "#1F1610", muted: "#78716C" },
  Modern:      { bg: "linear-gradient(135deg,#F0F9FF 0%,#E0F2FE 100%)", accent: "#0369A1", text: "#0C1E2E", muted: "#475569" },
  Creative:    { bg: "linear-gradient(135deg,#FFE4E6 0%,#FECDD3 100%)", accent: "#BE123C", text: "#1F0A14", muted: "#78716C" },
  Clean:       { bg: "#FFFFFF",                                          accent: "#475569", text: "#0F172A", muted: "#94A3B8" },
  // — Bold dark —
  Onyx:        { bg: "linear-gradient(135deg,#000000 0%,#1F2937 100%)", accent: "#F59E0B", text: "#FAFAFA", muted: "#9CA3AF" },
  Cobalt:      { bg: "linear-gradient(135deg,#0C1844 0%,#1E3A8A 100%)", accent: "#FBBF24", text: "#F9FAFB", muted: "#94A3B8" },
  Emerald:     { bg: "linear-gradient(135deg,#022C22 0%,#064E3B 100%)", accent: "#34D399", text: "#ECFDF5", muted: "#9CA3AF" },
  Plum:        { bg: "linear-gradient(135deg,#1E0A2E 0%,#3B0764 100%)", accent: "#E879F9", text: "#FAF5FF", muted: "#A78BFA" },
  Crimson:     { bg: "linear-gradient(135deg,#1A0A0A 0%,#7F1D1D 100%)", accent: "#FCA5A5", text: "#FEF2F2", muted: "#FDA4AF" },
  Midnight:    { bg: "linear-gradient(135deg,#020617 0%,#0F172A 100%)", accent: "#38BDF8", text: "#F1F5F9", muted: "#94A3B8" },
  Forest:      { bg: "linear-gradient(135deg,#14532D 0%,#166534 100%)", accent: "#FDE047", text: "#F0FDF4", muted: "#A7F3D0" },
  Rose:        { bg: "linear-gradient(135deg,#4C0519 0%,#881337 100%)", accent: "#FDA4AF", text: "#FFF1F2", muted: "#FECDD3" },
  Carbon:      { bg: "linear-gradient(135deg,#0A0A0A 0%,#262626 100%)", accent: "#84CC16", text: "#FAFAFA", muted: "#A1A1AA" },
  // — Vibrant gradient —
  Sunrise:     { bg: "linear-gradient(135deg,#FF6B6B 0%,#FFE66D 100%)", accent: "#1A1A2E", text: "#1A1A2E", muted: "#3F3F46" },
  Aurora:      { bg: "linear-gradient(135deg,#A8EDEA 0%,#FED6E3 100%)", accent: "#7C3AED", text: "#1A0A2E", muted: "#5B5563" },
  Tropical:    { bg: "linear-gradient(135deg,#FCCB90 0%,#D57EEB 100%)", accent: "#0F172A", text: "#0F172A", muted: "#3F3F46" },
  Lagoon:      { bg: "linear-gradient(135deg,#43E97B 0%,#38F9D7 100%)", accent: "#0F172A", text: "#0F172A", muted: "#374151" },
  Coral:       { bg: "linear-gradient(135deg,#FF9A8B 0%,#FF6A88 100%)", accent: "#1A0A14", text: "#1A0A14", muted: "#52525B" },
  Ice:         { bg: "linear-gradient(135deg,#E0EAFC 0%,#CFDEF3 100%)", accent: "#1E40AF", text: "#0F172A", muted: "#64748B" },
  Peach:       { bg: "linear-gradient(135deg,#FFE0C7 0%,#FFB199 100%)", accent: "#9A3412", text: "#1C1917", muted: "#78716C" },
  // — Bright single-color —
  Sunset:      { bg: "linear-gradient(135deg,#FFF5F1 0%,#FFE4D6 100%)", accent: "#F97316", text: "#1C1917", muted: "#78716C" },
  Ocean:       { bg: "linear-gradient(135deg,#F0F9FF 0%,#DBEAFE 100%)", accent: "#0284C7", text: "#0C1E2E", muted: "#475569" },
  Mint:        { bg: "linear-gradient(135deg,#F0FDF4 0%,#D1FAE5 100%)", accent: "#059669", text: "#0E1F17", muted: "#475569" },
  Berry:       { bg: "linear-gradient(135deg,#FDF2F8 0%,#FCE7F3 100%)", accent: "#DB2777", text: "#1F0A14", muted: "#6B5263" },
  Slate:       { bg: "linear-gradient(135deg,#F8FAFC 0%,#E2E8F0 100%)", accent: "#0F172A", text: "#0F172A", muted: "#475569" },
  Lemon:       { bg: "linear-gradient(135deg,#FEFCE8 0%,#FEF9C3 100%)", accent: "#65A30D", text: "#1C1917", muted: "#78716C" },
  Lavender:    { bg: "linear-gradient(135deg,#FAF5FF 0%,#F3E8FF 100%)", accent: "#7C3AED", text: "#1E1B2E", muted: "#6B5B7B" },
  Sand:        { bg: "linear-gradient(135deg,#FAF7F2 0%,#EFE9DD 100%)", accent: "#92400E", text: "#1F1A14", muted: "#6B5E4A" },
  Linen:       { bg: "linear-gradient(135deg,#FFFAF0 0%,#FEF3E2 100%)", accent: "#B45309", text: "#1C1917", muted: "#78716C" },
  Mist:        { bg: "linear-gradient(135deg,#F8FAFC 0%,#F1F5F9 100%)", accent: "#475569", text: "#0F172A", muted: "#64748B" },
  Cerulean:    { bg: "linear-gradient(135deg,#ECFEFF 0%,#A5F3FC 100%)", accent: "#0E7490", text: "#083344", muted: "#475569" },
  Whiteboard:  { bg: "#FFFFFF",                                          accent: "#2563EB", text: "#0F172A", muted: "#64748B" },
  Sketch:      { bg: "#FAFAF9",                                          accent: "#525252", text: "#171717", muted: "#737373" },
  Glamour:     { bg: "linear-gradient(135deg,#1A0A1F 0%,#2D0B3D 100%)", accent: "#F0ABFC", text: "#FAF5FF", muted: "#C4B5FD" },
  Amber:       { bg: "linear-gradient(135deg,#FFFBEB 0%,#FDE68A 100%)", accent: "#B45309", text: "#1C1917", muted: "#78716C" },
  Arctic:      { bg: "linear-gradient(135deg,#F0F9FF 0%,#E0F2FE 100%)", accent: "#0369A1", text: "#0C1E2E", muted: "#475569" },
  Neon:        { bg: "linear-gradient(135deg,#0A0A0A 0%,#171717 100%)", accent: "#22D3EE", text: "#FAFAFA", muted: "#A1A1AA" },
  Basalt:      { bg: "linear-gradient(135deg,#1F2937 0%,#374151 100%)", accent: "#F59E0B", text: "#F9FAFB", muted: "#9CA3AF" },
};

// Detect "is this a dark palette?" by looking at the text color luminance.
function isDarkPalette(p) {
  const m = String(p.text || "#000").match(/^#?([0-9a-f]{6})$/i);
  if (!m) return false;
  const v = parseInt(m[1], 16);
  const r = (v >> 16) & 255, g = (v >> 8) & 255, b = v & 255;
  // If text is bright, the palette is dark.
  return (0.299 * r + 0.587 * g + 0.114 * b) > 180;
}

// Fill in missing fields. Newer code can request `surface`, `accentSoft`,
// `border` without crashing on the legacy 4-key palettes.
function palettize(raw) {
  const dark = isDarkPalette(raw);
  return Object.freeze({
    ...raw,
    surface: raw.surface || (dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.04)"),
    accentSoft: raw.accentSoft || `${raw.accent}1A`,   // ~10% alpha
    border: raw.border || (dark ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.08)"),
    isDark: dark,
  });
}

const themePalettes = Object.freeze(
  Object.fromEntries(Object.entries(RAW_THEMES).map(([k, v]) => [k, palettize(v)])),
);

export const THEME_NAMES = Object.freeze(Object.keys(themePalettes));

/** Resolve a theme name to a full palette. Falls back to "Complete". */
export function paletteFor(theme) {
  return themePalettes[theme] || themePalettes.Complete;
}

/** Get the raw catalog (mostly for the gallery / theme picker). */
export function allPalettes() {
  return themePalettes;
}
