// design/tokens.js — single source of truth for all visual constants.
//
// Everything visual in the app (editor chrome, slide renderers, exporters)
// must read from here. Adding a hardcoded `text-3xl` or `px-12` anywhere
// else is a regression — extend the scale instead.
//
// All scales are exported as both:
//   - raw token values (numbers / hex strings)        → for inline `style={}`
//                                                       and the python mirror.
//   - tailwind class strings                          → for JSX `className`.
// Keep the two in sync: if you change `space.6` from 1.5rem to 1.75rem,
// also bump `spaceClass.6` so Tailwind agrees.
//
// .js (not .ts) because the rest of the frontend is JSX. The shapes are
// frozen + JSDoc-typed so editors still autocomplete.

// ─── 1. SPACING SCALE ───────────────────────────────────────────────────────
// 4px base. Names match Tailwind's `1` = 0.25rem convention so the class
// strings below stay obvious.
export const space = Object.freeze({
  0: "0",
  1: "0.25rem", //  4px — hairline
  2: "0.5rem",  //  8px — chip padding
  3: "0.75rem", // 12px — small gaps
  4: "1rem",    // 16px — default body gap
  5: "1.25rem", // 20px — card padding
  6: "1.5rem",  // 24px — block gap
  7: "1.75rem", // 28px — title→body editorial breathing (Phase 6AI-B3)
  8: "2rem",    // 32px — section gap
  10: "2.5rem", // 40px — slide vertical padding
  12: "3rem",   // 48px — slide horizontal padding
  14: "3.5rem", // 56px — wider editorial outer padding (Phase 6AI-B3)
  16: "4rem",   // 64px — title→body breathing room on hero layouts
  20: "5rem",   // 80px — major section breaks
  24: "6rem",   // 96px — outer canvas margins
});

// ─── 2. RADIUS SCALE ────────────────────────────────────────────────────────
export const radius = Object.freeze({
  none: "0",
  sm: "0.375rem",  //  6px — input corners
  md: "0.625rem",  // 10px — small cards
  lg: "1rem",      // 16px — content cards
  xl: "1.25rem",   // 20px — feature cards
  "2xl": "1.5rem", // 24px — hero panels
  full: "9999px",  // chips / avatars
});

// ─── 3. SHADOW / ELEVATION ──────────────────────────────────────────────────
// Six tiers. Use `card` for resting cards, `elevated` for hover/active,
// `slide` for the outer slide canvas, `popover` for floating UI (menus,
// theme picker), `accent` for tinted glows on CTA cards.
export const shadow = Object.freeze({
  none: "none",
  sm: "0 1px 2px 0 rgba(0,0,0,0.05)",
  card: "0 4px 12px -2px rgba(0,0,0,0.08), 0 2px 4px -2px rgba(0,0,0,0.04)",
  elevated: "0 12px 28px -8px rgba(0,0,0,0.18), 0 4px 8px -4px rgba(0,0,0,0.06)",
  slide: "0 24px 48px -16px rgba(0,0,0,0.40), 0 8px 16px -8px rgba(0,0,0,0.20)",
  popover: "0 16px 32px -8px rgba(0,0,0,0.20), 0 4px 8px -4px rgba(0,0,0,0.08)",
});
// Accent-tinted glow factory — pass any palette accent.
export function accentGlow(hex, alpha = 0.35) {
  return `0 12px 32px -8px ${hex}${Math.round(alpha * 255).toString(16).padStart(2, "0")}`;
}

// ─── 4. ANIMATION / MOTION ──────────────────────────────────────────────────
export const motion = Object.freeze({
  duration: { instant: 80, fast: 150, base: 220, slow: 360, slower: 560 },
  // Reusable easing functions — match Tailwind's defaults plus a custom
  // "emphasized" curve for slide enter animations (Material-3 style).
  ease: {
    standard: [0.2, 0, 0, 1],
    emphasized: [0.3, 0, 0, 1],
    decelerate: [0, 0, 0, 1],
    accelerate: [0.3, 0, 1, 1],
  },
});

// ─── 5. NEUTRAL & SEMANTIC COLORS ───────────────────────────────────────────
// Theme-agnostic neutrals used by editor chrome (NOT slide content — slide
// colors come from the active palette in theme-engine.js).
export const color = Object.freeze({
  // Editor chrome
  bg: "#0B0B10",
  surface: "#15151D",
  surfaceAlt: "#1C1C26",
  border: "#2A2A36",
  borderSubtle: "#1F1F2A",
  text: "#F5F5F7",
  textMuted: "#9A9AA5",
  // Semantic
  success: "#10B981",
  warning: "#F59E0B",
  danger: "#EF4444",
  info: "#3B82F6",
});

// 6 deterministic accent tints used to color rotating cards in feature/bento
// layouts. Single source — SlideLayouts and SlideRenderer both import from here.
export const accentTints = Object.freeze([
  "#3B82F6", // blue
  "#A855F7", // purple
  "#10B981", // emerald
  "#F59E0B", // amber
  "#EF4444", // red
  "#06B6D4", // cyan
]);

// ─── 6. ICON SIZE SCALE ─────────────────────────────────────────────────────
// In rem so they scale with parent font.
export const iconSize = Object.freeze({
  xs: "0.875rem", // 14px — inline w/ caption
  sm: "1rem",     // 16px — bullet markers
  md: "1.25rem",  // 20px — card heads
  lg: "1.5rem",   // 24px — feature badges
  xl: "2rem",     // 32px — hero badges
});

// ─── 7. Z-INDEX SCALE ───────────────────────────────────────────────────────
export const z = Object.freeze({
  base: 0,
  raised: 10,
  sticky: 20,
  overlay: 40,
  modal: 60,
  toast: 80,
});

// ─── 8. DETERMINISTIC HASH ──────────────────────────────────────────────────
// Single shared hash so SlideLayouts + SlideRenderer + future export
// renderers all pick the same variant for the same seed string.
export function hashString(s) {
  let h = 2166136261;
  const str = String(s || "");
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = (h * 16777619) >>> 0;
  }
  return h >>> 0;
}

export function tintFor(seed, idx = 0) {
  return accentTints[(hashString(seed) + idx) % accentTints.length];
}
