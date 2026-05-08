// design/registry.js — single source of truth for layout names + aliases.
//
// The CANONICAL data lives in `layouts.registry.json` and is consumed by:
//   - this module (frontend),
//   - `backend/agent/layouts_registry.py` (server),
//   - `scripts/verify-layouts.mjs` (CI parity check).
//
// Edit the JSON; never hardcode a layout list anywhere else.

import registry from "./layouts.registry.json";

/** Canonical, never-aliased layout names. */
export const CANONICAL_LAYOUTS = Object.freeze(
  registry.layouts.map((l) => l.name),
);

/** Subset that the PPTX exporter knows how to render. */
export const EXPORT_SUPPORTED = Object.freeze(
  new Set(registry.layouts.filter((l) => l.exported).map((l) => l.name)),
);

/** Lookup table: alias -> canonical name. */
export const LAYOUT_ALIASES = Object.freeze({ ...registry.aliases });

/** Schema documentation per layout (used by UnsupportedLayoutSlide hints). */
export const LAYOUT_SCHEMAS = Object.freeze(
  Object.fromEntries(registry.layouts.map((l) => [l.name, l.schema])),
);

/** Default layout when nothing else resolves. */
export const FALLBACK_LAYOUT = registry.fallback;

/** Resolve any input string to {canonical, aliased, supported}. */
export function resolveLayoutName(raw) {
  const key = String(raw || "").toLowerCase().trim();
  if (!key) return { canonical: FALLBACK_LAYOUT, aliased: false, supported: false, input: raw };
  if (CANONICAL_LAYOUTS.includes(key)) return { canonical: key, aliased: false, supported: true, input: raw };
  const aliased = LAYOUT_ALIASES[key];
  if (aliased && CANONICAL_LAYOUTS.includes(aliased)) {
    return { canonical: aliased, aliased: true, supported: true, input: raw };
  }
  return { canonical: FALLBACK_LAYOUT, aliased: false, supported: false, input: raw };
}
