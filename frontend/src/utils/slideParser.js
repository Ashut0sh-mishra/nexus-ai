/**
 * Normalize raw slide data coming from the backend into a stable shape that
 * `SlideRenderer` can consume regardless of small upstream variations.
 *
 * Accepts both the canonical NEXUS schema and the flatter Manus-style schema
 * the LLM may emit (col1_title/col1_content, top-level labels/values, etc.).
 */

const VALID_LAYOUTS = new Set([
  "title",
  "section",
  "bullets",
  "two-col",
  "comparison",
  "kpi",
  "quote",
  "stats",
  "chart",
  "table",
  "timeline",
  "image-focus",
  "closing",
]);

function asNumber(v) {
  if (typeof v === "number") return v;
  if (v == null) return 0;
  const cleaned = String(v).replace(/[$,%\s]/g, "");
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : 0;
}

export function normalizeSlide(raw, index = 0) {
  if (!raw || typeof raw !== "object") {
    return {
      id: `slide-${index}`,
      layout: "title",
      title: "Untitled slide",
      subtitle: "",
    };
  }
  const layout = VALID_LAYOUTS.has(raw.layout) ? raw.layout : "title";
  const base = {
    id: raw.id || `slide-${index}`,
    layout,
    title: raw.title || "",
    subtitle: raw.subtitle || "",
    eyebrow: raw.eyebrow || raw.tagline || "",
    image_url: raw.image_url || "",
  };
  switch (layout) {
    case "title":
      return { ...base, tagline: raw.tagline || "" };
    case "bullets":
      return {
        ...base,
        section: raw.section || "",
        bullets: Array.isArray(raw.bullets) ? raw.bullets.slice(0, 4) : [],
      };
    case "two-col": {
      let columns = [];
      if (Array.isArray(raw.columns) && raw.columns.length) {
        columns = raw.columns.slice(0, 2).map((c) => ({
          heading: c?.heading || c?.title || "",
          body: c?.body || c?.content || "",
        }));
      } else {
        for (const n of [1, 2]) {
          const heading = raw[`col${n}_title`] || "";
          const body = raw[`col${n}_content`] || "";
          if (heading || body) columns.push({ heading, body });
        }
      }
      return { ...base, columns };
    }
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
              trend: s?.trend ? String(s.trend) : "",
            }))
          : [],
      };
    case "chart": {
      const cd = raw.chart_data && typeof raw.chart_data === "object" ? raw.chart_data : {};
      const labels = Array.isArray(cd.labels)
        ? cd.labels
        : Array.isArray(raw.labels)
          ? raw.labels
          : [];
      const valuesRaw = Array.isArray(cd.values)
        ? cd.values
        : Array.isArray(raw.values)
          ? raw.values
          : [];
      const values = valuesRaw.map(asNumber);
      let chartType = String(raw.chart_type || cd.chart_type || "bar").toLowerCase();
      if (chartType === "pie") chartType = "doughnut";
      if (!["bar", "line", "doughnut"].includes(chartType)) chartType = "bar";
      return {
        ...base,
        chart_type: chartType,
        chart_data: {
          labels: labels.map(String),
          values,
          unit: cd.unit || raw.unit || "",
          source: cd.source || raw.source || "",
        },
      };
    }
    case "table": {
      const headers = Array.isArray(raw.headers) ? raw.headers.map(String).slice(0, 6) : [];
      const rows = Array.isArray(raw.rows)
        ? raw.rows
            .slice(0, 8)
            .map((r) => (Array.isArray(r) ? r.slice(0, 6).map((c) => String(c ?? "")) : []))
        : [];
      return { ...base, headers, rows };
    }
    case "timeline": {
      const events = Array.isArray(raw.events)
        ? raw.events.slice(0, 6).map((e) => ({
            year: String(e?.year ?? ""),
            title: e?.title || "",
            desc: e?.desc || e?.description || "",
          }))
        : [];
      return { ...base, events };
    }
    case "image-focus":
      return {
        ...base,
        caption: raw.caption || raw.subtitle || "",
        image_prompt: raw.image_prompt || "",
      };
    case "section":
      return {
        ...base,
        section_number: String(raw.section_number || raw.number || ""),
      };
    case "kpi": {
      const list = Array.isArray(raw.kpis)
        ? raw.kpis
        : Array.isArray(raw.stats)
          ? raw.stats
          : [];
      return {
        ...base,
        kpis: list.slice(0, 4).map((k) => ({
          value: String(k?.value ?? ""),
          label: k?.label || "",
          sublabel: k?.sublabel || k?.description || "",
          delta: k?.delta || k?.trend || "",
          direction: String(k?.direction || "").toLowerCase(),
        })),
      };
    }
    case "comparison": {
      let items = [];
      if (Array.isArray(raw.items) && raw.items.length) {
        items = raw.items;
      } else if (Array.isArray(raw.columns)) {
        items = raw.columns;
      }
      const normalized = items.slice(0, 2).map((c) => ({
        heading: c?.heading || c?.title || "",
        subtitle: c?.subtitle || c?.tagline || "",
        points: Array.isArray(c?.points)
          ? c.points.slice(0, 4).map(String)
          : Array.isArray(c?.bullets)
            ? c.bullets.slice(0, 4).map(String)
            : [],
        body: c?.body || "",
      }));
      return {
        ...base,
        items: normalized,
        divider: raw.divider || "vs",
      };
    }
    case "closing":
      return {
        ...base,
        message: raw.message || "",
        cta: raw.cta || "",
        tagline: raw.tagline || "",
      };
    default:
      return base;
  }
}

export function normalizeSlides(arr) {
  if (!Array.isArray(arr)) return [];
  return arr.map(normalizeSlide);
}
