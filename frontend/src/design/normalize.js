// design/normalize.js — canonical slide-content normalizer.
//
// Goal: every renderer receives a slide whose shape exactly matches the
// schema declared in layouts.registry.json — no more renderer-side regex
// extraction or guessing about whether the LLM emitted `events[].year`
// vs `events[].date`.
//
// Call once at the boundary (SlideRenderer wraps every slide before
// dispatch). Idempotent — running it twice is a no-op.

import { resolveLayoutName, FALLBACK_LAYOUT } from "./registry.js";

const STAT_RE = /(\$\s?\d[\d,]*(?:\.\d+)?\s*[KMBkmb]?|\d+(?:\.\d+)?\s*[%KMBkmb]?)/;

/** Coerce a value to a string, dropping null/undefined cleanly. */
function s(v) { return v == null ? "" : String(v); }

/** Normalize stats so every entry has {value, label, caption?}. */
function normalizeStats(input) {
  if (!Array.isArray(input)) return [];
  return input
    .map((it) => {
      if (!it) return null;
      if (typeof it === "string") {
        const m = it.match(/^([^a-zA-Z]*\d[\d.,KMB%kmb$\s]*)[\s—–-]+(.+)$/);
        return m ? { value: m[1].trim(), label: m[2].trim() } : { value: it, label: "" };
      }
      const value = s(it.value ?? it.metric ?? it.number ?? it.amount);
      const label = s(it.label ?? it.metric_label ?? it.title ?? it.name);
      const caption = s(it.caption ?? it.note ?? it.trend ?? "") || undefined;
      const trend = it.trend ?? it.delta ?? null;            // optional sign indicator
      return value || label ? { value, label, caption, trend } : null;
    })
    .filter(Boolean);
}

/** Normalize timeline events so every entry has {year, title, body?}. */
function normalizeEvents(input) {
  if (!Array.isArray(input)) return [];
  return input
    .map((it) => {
      if (!it) return null;
      if (typeof it === "string") return { year: "", title: it };
      const year = s(it.year ?? it.date ?? it.when ?? it.time);
      const title = s(it.title ?? it.label ?? it.event ?? it.name);
      const body = s(it.body ?? it.description ?? it.detail ?? "") || undefined;
      return year || title ? { year, title, body } : null;
    })
    .filter(Boolean);
}

/** Normalize tables so {headers: string[], rows: string[][]}. */
function normalizeTable(slide) {
  let headers = Array.isArray(slide.headers) ? slide.headers.map(s) : null;
  let rows = Array.isArray(slide.rows) ? slide.rows.map((r) => (Array.isArray(r) ? r.map(s) : [s(r)])) : [];
  // Common LLM mistake: headers embedded as rows[0]. If headers missing AND
  // first row looks header-ish (all alpha words, no numbers), promote it.
  if (!headers && rows.length > 1) {
    const first = rows[0];
    const looksLikeHeaders = first.every((c) => /^[A-Za-z][\w\s%/-]*$/.test(c) && !/\d/.test(c));
    if (looksLikeHeaders) {
      headers = first;
      rows = rows.slice(1);
    }
  }
  return { headers: headers || [], rows };
}

/** Normalize bullets to a string[] (max 12). */
function normalizeBullets(input) {
  if (!Array.isArray(input)) return [];
  return input.map(s).map((b) => b.trim()).filter(Boolean).slice(0, 12);
}

/** Normalize columns so each has {heading, body}. */
function normalizeColumns(input) {
  if (!Array.isArray(input)) return [];
  return input
    .map((c) => (typeof c === "string"
      ? { heading: "", body: c }
      : { heading: s(c?.heading ?? c?.title ?? c?.label), body: s(c?.body ?? c?.description ?? c?.text) }))
    .filter((c) => c.heading || c.body);
}

/** Per-layout last-mile coercions (e.g. metric-spotlight → ensure stats[0]). */
function coerceForLayout(slide, layout) {
  if (layout === "metric-spotlight" && (!slide.stats || !slide.stats.length)) {
    // Hoist legacy `metric` / `metric_label` into the canonical stats[0] shape.
    const value = s(slide.metric);
    const label = s(slide.metric_label);
    if (value || label) {
      slide.stats = [{ value, label }];
    } else {
      // Last-resort regex on title/body so the renderer never receives an
      // empty stats array for this layout.
      const hay = [slide.title, slide.subtitle, slide.body, ...(slide.bullets || [])]
        .filter(Boolean).join(" ");
      const m = hay.match(STAT_RE);
      if (m) slide.stats = [{ value: m[0].trim(), label: "" }];
    }
  }
  if (layout === "kpi" && (!slide.stats || !slide.stats.length)) {
    // Try to pull from bullets like "82% retention" → {value:"82%", label:"retention"}
    slide.stats = normalizeStats(slide.bullets || []);
  }
  return slide;
}

/**
 * Normalize a slide payload coming off the API.
 * - Resolves aliases → canonical layout name.
 * - Coerces every variant field name to the schema declared in layouts.registry.json.
 * - Idempotent.
 *
 * Returns: { slide, meta: { canonical, aliased, supported, input } }
 */
export function normalizeSlideContent(rawSlide) {
  const slide = { ...(rawSlide || {}) };

  // 1. Resolve layout
  const meta = resolveLayoutName(slide.layout);
  slide.layout = meta.canonical || FALLBACK_LAYOUT;
  if (meta.aliased) slide._layout_alias = meta.input;
  if (!meta.supported) slide._layout_unsupported = meta.input;

  // 2. Normalize text fields — trim & default.
  slide.title = s(slide.title).trim();
  slide.subtitle = s(slide.subtitle).trim();
  slide.eyebrow = s(slide.eyebrow).trim();
  slide.body = s(slide.body).trim();

  // 3. Normalize collections
  slide.bullets = normalizeBullets(slide.bullets);
  slide.columns = normalizeColumns(slide.columns);
  slide.stats = normalizeStats(slide.stats);
  slide.events = normalizeEvents(slide.events);
  const tbl = normalizeTable(slide);
  slide.headers = tbl.headers;
  slide.rows = tbl.rows;

  // 4. Per-layout last-mile coercions
  coerceForLayout(slide, slide.layout);

  return { slide, meta };
}

/** Bulk-normalize a deck. */
export function normalizeDeck(slides) {
  if (!Array.isArray(slides)) return [];
  return slides.map((s) => normalizeSlideContent(s).slide);
}
