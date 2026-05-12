/**
 * Normalize raw slide data coming from the backend into a stable shape that
 * `SlideRenderer` can consume regardless of small upstream variations.
 *
 * The set of valid layouts is sourced from the canonical layout registry
 * (`../design/layouts.registry.json`) so this file can never drift from the
 * backend normalizer or the renderer's layout map.
 */

import {
  CANONICAL_LAYOUTS,
  FALLBACK_LAYOUT,
  resolveLayoutName,
} from "../design/registry.js";

const VALID_LAYOUTS = new Set(CANONICAL_LAYOUTS);

export function normalizeSlide(raw, index = 0) {
  if (!raw || typeof raw !== "object") {
    return {
      id: `slide-${index}`,
      layout: "title",
      title: "Untitled slide",
      subtitle: "",
    };
  }
  // Resolve through the registry so canonical names pass through, future
  // aliases are honored, and unknowns collapse to FALLBACK_LAYOUT instead
  // of being silently re-typed as a title slide.
  const resolved = resolveLayoutName(raw.layout);
  const layout = VALID_LAYOUTS.has(resolved.canonical)
    ? resolved.canonical
    : FALLBACK_LAYOUT;
  const base = {
    id: raw.id || `slide-${index}`,
    layout,
    title: raw.title || "",
    subtitle: raw.subtitle || "",
    eyebrow: raw.eyebrow || "",
    // Phase 5: preserve any source/evidence metadata the backend attached
    // (Phase 4 fills this for stats / chart / numeric prose slides). The
    // slide renderer itself ignores this field — it's only consumed by
    // SourceEvidencePanel.
    sources: Array.isArray(raw.sources) ? raw.sources : [],
    // Phase 6AF: per-slide claim-level citations attached by the backend
    // pipeline (services.claim_citation_service via agent.citation_attach).
    // Each entry is { path, claim_text, marker, supported, basis, score,
    // source_id, source_url, source_title }. SlideRenderer reads `marker`
    // to draw small superscripts next to bullets/stats; CitationsPanel
    // continues to fetch the deck-level report from the API for the full
    // grouped view.
    citations: Array.isArray(raw.citations) ? raw.citations : [],
    // Phase 6AH-A1: per-slide intent metadata produced by the backend
    // pipeline (agent/slide_intent.py). Used by StorylineRibbon and the
    // upcoming reasoning drawer to surface the agent's narrative plan.
    // The slide renderer itself ignores this field; renderer code path
    // is unchanged.
    intent:
      raw.intent && typeof raw.intent === "object" && !Array.isArray(raw.intent)
        ? {
            narrative_role: raw.intent.narrative_role || "",
            tone: raw.intent.tone || "",
            density: raw.intent.density || "",
            communication_goal: raw.intent.communication_goal || "",
          }
        : null,
    // Phase 6AJ: short narrative bridge written by editorial_pass when
    // consecutive slides have an intent.narrative_role. ≤ 9 words.
    // Surfaced in SlideReasoningDrawer; renderers ignore it.
    transition: typeof raw.transition === "string" ? raw.transition : "",
    // Phase 6AK: cinematic hero marker set by agent.cinematic_marker.
    // Renderer-only signal — bigstat / section_divider / attributed-quote
    // slides whose `is_hero === true` are promoted to full-bleed
    // cinematic variants. Exporters and the canonical layout contract
    // ignore this field.
    is_hero: raw.is_hero === true,
  };
  switch (layout) {
    case "bullets":
      return { ...base, bullets: Array.isArray(raw.bullets) ? raw.bullets : [] };
    case "two-col":
      return {
        ...base,
        columns: Array.isArray(raw.columns)
          ? raw.columns.slice(0, 2).map((c) => ({
              heading: c?.heading || "",
              body: c?.body || "",
            }))
          : [],
      };
    case "quote":
      return {
        ...base,
        quote: raw.quote || raw.title || "",
        attribution: raw.attribution || "",
      };
    case "stats":
      return {
        ...base,
        stats: Array.isArray(raw.stats)
          ? raw.stats.slice(0, 3).map((s) => ({
              value: String(s?.value ?? ""),
              label: s?.label || "",
            }))
          : [],
      };
    case "chart": {
      const cd =
        raw.chart_data && typeof raw.chart_data === "object"
          ? raw.chart_data
          : {};
      const labels = Array.isArray(cd.labels) ? cd.labels.map(String) : [];
      const values = Array.isArray(cd.values)
        ? cd.values.map((v) => {
            const n = Number(
              String(v).replace(/,/g, "").replace(/\$/g, "").trim()
            );
            return Number.isFinite(n) ? n : 0;
          })
        : [];
      const pairs = Math.min(labels.length, values.length);
      const chartType = ["bar", "line", "doughnut"].includes(
        String(raw.chart_type || "bar").toLowerCase()
      )
        ? String(raw.chart_type).toLowerCase()
        : "bar";
      return {
        ...base,
        chart_type: chartType,
        chart_data: {
          labels: labels.slice(0, pairs),
          values: values.slice(0, pairs),
          unit: cd.unit || "",
          source: cd.source || "",
        },
      };
    }
    case "closing":
      return { ...base, cta: raw.cta || "" };
    default:
      return base;
  }
}

export function normalizeSlides(arr) {
  if (!Array.isArray(arr)) return [];
  return arr.map(normalizeSlide);
}
