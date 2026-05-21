/**
 * Phase 6P — defaults for new / re-laid-out slides.
 *
 * The shapes returned here are designed to pass `agent.slide_schema.validate_deck`
 * on the backend (see `backend/agent/slide_schema.py`). Every required field
 * is present; required non-empty fields use placeholder copy that the user
 * can immediately edit.
 */

import { CANONICAL_LAYOUTS } from "../design/registry.js";

const VALID = new Set(CANONICAL_LAYOUTS);

let _seq = 0;
function _nextId() {
  _seq += 1;
  return `slide-${Date.now().toString(36)}-${_seq}`;
}

/** Return a freshly-minted, valid blank slide for the given layout. */
export function makeBlankSlide(layout = "bullets") {
  const lay = VALID.has(layout) ? layout : "bullets";
  const base = { id: _nextId(), layout: lay, sources: [] };
  switch (lay) {
    case "title":
      return {
        ...base,
        title: "New title",
        subtitle: "",
        eyebrow: "",
      };
    case "bullets":
      return {
        ...base,
        title: "New section",
        subtitle: "",
        eyebrow: "",
        bullets: ["First point"],
      };
    case "two-col":
      return {
        ...base,
        title: "Comparison",
        subtitle: "",
        eyebrow: "",
        columns: [
          { heading: "Column A", body: "Body A" },
          { heading: "Column B", body: "Body B" },
        ],
      };
    case "quote":
      return {
        ...base,
        title: "Quote",
        subtitle: "",
        eyebrow: "",
        quote: "A short, memorable quote.",
        attribution: "",
      };
    case "stats":
      return {
        ...base,
        title: "Key numbers",
        subtitle: "",
        eyebrow: "",
        stats: [{ value: "00", label: "Metric" }],
      };
    case "chart":
      return {
        ...base,
        title: "Chart",
        subtitle: "",
        eyebrow: "",
        chart_type: "bar",
        chart_data: {
          labels: ["A", "B", "C"],
          values: [1, 2, 3],
          unit: "",
          source: "",
        },
      };
    case "closing":
      return {
        ...base,
        title: "Thank you",
        subtitle: "",
        eyebrow: "",
        cta: "",
      };
    case "bigstat":
      return {
        ...base,
        title: "Headline number",
        value: "00",
        label: "Metric",
        subtitle: "",
      };
    case "section_divider":
      return {
        ...base,
        title: "New section",
        eyebrow: "",
        subtitle: "",
      };
    case "timeline":
      return {
        ...base,
        title: "Timeline",
        subtitle: "",
        events: [
          { date: "2023", label: "First milestone" },
          { date: "2024", label: "Second milestone" },
          { date: "2025", label: "Third milestone" },
        ],
      };
    case "comparison":
      return {
        ...base,
        title: "Comparison",
        subtitle: "",
        left: { heading: "Side A", body: "Body A" },
        right: { heading: "Side B", body: "Body B" },
      };
    default:
      return {
        ...base,
        layout: "bullets",
        title: "New section",
        subtitle: "",
        eyebrow: "",
        bullets: ["First point"],
      };
  }
}

/**
 * Convert a slide to a new layout while preserving title where possible
 * and filling required fields with valid defaults. Keeps `id` and any
 * `sources` array. The returned slide always passes the per-layout
 * required-fields contract enforced by the backend schema.
 */
export function convertSlideLayout(slide, nextLayout) {
  if (!slide || typeof slide !== "object") return makeBlankSlide(nextLayout);
  if (!VALID.has(nextLayout)) return slide;
  if (slide.layout === nextLayout) return slide;

  const blank = makeBlankSlide(nextLayout);
  const carried = {
    id: slide.id || blank.id,
    sources: Array.isArray(slide.sources) ? slide.sources : [],
  };
  // Best-effort title preservation across layouts that have a title.
  const carryTitle = typeof slide.title === "string" && slide.title.trim()
    ? slide.title
    : null;

  switch (nextLayout) {
    case "title":
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        subtitle: typeof slide.subtitle === "string" ? slide.subtitle : "",
        eyebrow: typeof slide.eyebrow === "string" ? slide.eyebrow : "",
      };
    case "bullets": {
      const existing = Array.isArray(slide.bullets)
        ? slide.bullets.filter((b) => typeof b === "string" && b.trim())
        : [];
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        bullets: existing.length ? existing : blank.bullets,
      };
    }
    case "two-col": {
      const cols = Array.isArray(slide.columns) ? slide.columns : [];
      const safe = cols
        .slice(0, 2)
        .map((c) => ({
          heading: c?.heading && c.heading.trim() ? c.heading : "Column",
          body: c?.body && c.body.trim() ? c.body : "Body",
        }));
      while (safe.length < 1) safe.push({ heading: "Column A", body: "Body A" });
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        columns: safe,
      };
    }
    case "quote":
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        quote: (typeof slide.quote === "string" && slide.quote.trim())
          ? slide.quote
          : (carryTitle || blank.quote),
        attribution: typeof slide.attribution === "string" ? slide.attribution : "",
      };
    case "stats": {
      const stats = Array.isArray(slide.stats) ? slide.stats : [];
      const safe = stats
        .slice(0, 3)
        .map((s) => ({
          value: s?.value != null && String(s.value).trim() ? String(s.value) : "00",
          label: s?.label && String(s.label).trim() ? String(s.label) : "Metric",
        }));
      while (safe.length < 1) safe.push({ value: "00", label: "Metric" });
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        stats: safe,
      };
    }
    case "chart": {
      const cd = slide.chart_data && typeof slide.chart_data === "object" ? slide.chart_data : {};
      const labels = Array.isArray(cd.labels) ? cd.labels.map(String) : [];
      const values = Array.isArray(cd.values)
        ? cd.values.map((v) => {
            const n = Number(v);
            return Number.isFinite(n) ? n : 0;
          })
        : [];
      const pairs = Math.min(labels.length, values.length);
      const safeLabels = pairs > 0 ? labels.slice(0, pairs) : blank.chart_data.labels;
      const safeValues = pairs > 0 ? values.slice(0, pairs) : blank.chart_data.values;
      const ctype = ["bar", "line", "doughnut"].includes(
        String(slide.chart_type || "").toLowerCase()
      )
        ? String(slide.chart_type).toLowerCase()
        : "bar";
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        subtitle: typeof slide.subtitle === "string" ? slide.subtitle : "",
        chart_type: ctype,
        chart_data: {
          labels: safeLabels,
          values: safeValues,
          unit: typeof cd.unit === "string" ? cd.unit : "",
          source: typeof cd.source === "string" ? cd.source : "",
        },
      };
    }
    case "closing":
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        subtitle: typeof slide.subtitle === "string" ? slide.subtitle : "",
        cta: typeof slide.cta === "string" ? slide.cta : "",
      };
    case "bigstat": {
      // Carry a value from an existing stats slide if present.
      const firstStat = Array.isArray(slide.stats) && slide.stats[0] ? slide.stats[0] : null;
      const val = slide.value != null && String(slide.value).trim()
        ? String(slide.value)
        : firstStat && String(firstStat.value ?? "").trim()
          ? String(firstStat.value)
          : blank.value;
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        value: val,
        label: slide.label || (firstStat && firstStat.label) || "",
        subtitle: typeof slide.subtitle === "string" ? slide.subtitle : "",
      };
    }
    case "section_divider":
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        eyebrow: typeof slide.eyebrow === "string" ? slide.eyebrow : "",
        subtitle: typeof slide.subtitle === "string" ? slide.subtitle : "",
      };
    case "timeline": {
      const ev = Array.isArray(slide.events) ? slide.events : [];
      const safe = ev
        .slice(0, 6)
        .map((e) => ({
          date: e?.date && String(e.date).trim() ? String(e.date) : "—",
          label: e?.label && String(e.label).trim() ? String(e.label) : "Event",
        }));
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        subtitle: typeof slide.subtitle === "string" ? slide.subtitle : "",
        events: safe.length ? safe : blank.events,
      };
    }
    case "comparison": {
      const l = slide.left && typeof slide.left === "object" ? slide.left : {};
      const r = slide.right && typeof slide.right === "object" ? slide.right : {};
      return {
        ...blank,
        ...carried,
        title: carryTitle || blank.title,
        subtitle: typeof slide.subtitle === "string" ? slide.subtitle : "",
        left: {
          heading: l.heading && l.heading.trim() ? l.heading : "Side A",
          body: l.body && l.body.trim() ? l.body : "Body A",
        },
        right: {
          heading: r.heading && r.heading.trim() ? r.heading : "Side B",
          body: r.body && r.body.trim() ? r.body : "Body B",
        },
      };
    }
    default:
      return blank;
  }
}

export const SUPPORTED_LAYOUTS = [
  "title",
  "bullets",
  "two-col",
  "quote",
  "stats",
  "chart",
  "closing",
  "bigstat",
  "section_divider",
  "timeline",
  "comparison",
];
