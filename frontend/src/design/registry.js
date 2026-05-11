/**
 * Canonical NEXUS slide layout registry — frontend loader.
 *
 * Single source of truth lives in `layouts.registry.json`. Any module that
 * needs to know which slide layouts are valid MUST import from this file
 * instead of hardcoding its own list. The backend
 * (`backend/agent/layouts_registry.py`) reads the same JSON file so backend
 * and frontend can never drift.
 */

import registry from "./layouts.registry.json";

const layoutEntries = Array.isArray(registry.layouts) ? registry.layouts : [];

export const CANONICAL_LAYOUTS = Object.freeze(
  layoutEntries.map((entry) => entry.name)
);

export const EXPORT_SUPPORTED = Object.freeze(
  layoutEntries.filter((entry) => entry.exported).map((entry) => entry.name)
);

export const LAYOUT_ALIASES = Object.freeze({
  ...(registry.aliases || {}),
});

export const FALLBACK_LAYOUT = registry.fallback || "bullets";

const CANONICAL_SET = new Set(CANONICAL_LAYOUTS);

/**
 * Resolve a raw layout string to a canonical layout name.
 *
 * Returns an object so callers can tell the difference between
 *   - input was already canonical (canonical === input)
 *   - input was a known alias (aliased === true)
 *   - input was unknown and fell back to FALLBACK_LAYOUT (fallback === true)
 */
export function resolveLayoutName(raw) {
  const input = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (input && CANONICAL_SET.has(input)) {
    return { canonical: input, aliased: false, fallback: false, input };
  }
  if (input && Object.prototype.hasOwnProperty.call(LAYOUT_ALIASES, input)) {
    const target = LAYOUT_ALIASES[input];
    if (CANONICAL_SET.has(target)) {
      return { canonical: target, aliased: true, fallback: false, input };
    }
  }
  return { canonical: FALLBACK_LAYOUT, aliased: false, fallback: true, input };
}
