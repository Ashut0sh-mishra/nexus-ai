import { useMemo, useState } from "react";
import SlideRenderer from "../components/SlideRenderer.jsx";
import { CANONICAL_LAYOUTS, LAYOUT_ALIASES, THEME_NAMES } from "../design/index.js";

// Visual smoke-test gallery for every layout the renderer supports.
// Visit `/gallery` (or `/gallery?theme=Onyx`) to see one slide per layout
// rendered side-by-side. Used as a screenshot baseline for regressions.

const SAMPLE_BULLETS = [
  "Awareness — discover the brand through search and social referrals",
  "Consideration: shortlist by feature comparison and pricing",
  "Decision: convert via free trial or sales-led demo",
  "Onboarding — first value within 7 days drives long-term retention",
  "Expansion: cross-sell adjacent modules to power users",
  "Advocacy — net promoter score above 60 fuels organic growth",
];

const SAMPLE_COLUMNS = [
  { heading: "Pros", body: "Faster onboarding. Lower TCO. Better integrations." },
  { heading: "Cons", body: "Vendor lock-in risk. Requires retraining ops team." },
];

function sampleSlide(layout) {
  const base = {
    id: `gallery-${layout}`,
    layout,
    eyebrow: "Section 02",
    title: titleFor(layout),
    subtitle:
      "Sample subtitle — used to validate spacing and typography across every layout.",
    bullets: SAMPLE_BULLETS,
    columns: SAMPLE_COLUMNS,
  };
  switch (layout) {
    case "title":
      return { ...base, layout: "title", subtitle: "An end-to-end visual smoke test", tagline: "" };
    case "stats":
      return {
        ...base,
        stats: [
          { value: "82%", label: "User retention" },
          { value: "4.6×", label: "ROI vs. baseline" },
          { value: "120K", label: "Decks generated" },
        ],
      };
    case "chart":
      return {
        ...base,
        chart_type: "bar",
        chart_data: { labels: ["Q1", "Q2", "Q3", "Q4"], values: [12, 18, 22, 31], unit: "M" },
      };
    case "table":
      return {
        ...base,
        headers: ["Region", "Revenue", "Growth"],
        rows: [
          ["NA", "$4.2M", "+18%"],
          ["EMEA", "$2.7M", "+12%"],
          ["APAC", "$1.9M", "+34%"],
        ],
      };
    case "timeline":
      return {
        ...base,
        events: [
          { year: "2022", title: "Founded" },
          { year: "2023", title: "Seed round" },
          { year: "2024", title: "Series A" },
          { year: "2025", title: "Profitability" },
        ],
      };
    case "quote":
      return { ...base, quote: "The best decks tell stories — not facts.", attribution: "— Edward Tufte" };
    case "metric-spotlight":
      return { ...base, stats: [{ value: "62%", label: "Activation rate" }], bullets: SAMPLE_BULLETS.slice(1, 4) };
    case "kpi":
      return {
        ...base,
        stats: [
          { value: "82%", label: "Retention" },
          { value: "4.6×", label: "ROI" },
          { value: "120K", label: "Decks" },
          { value: "+34%", label: "YoY growth" },
        ],
      };
    case "matrix-2x2":
      return { ...base, axis: { x: "Effort →", y: "Impact ↑" } };
    case "hero":
      return { ...base, image_url: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200" };
    case "callout":
      return { ...base, callout: "Spend 80% of your time on the slides that matter — kill the rest." };
    case "comparison":
      return { ...base, columns: SAMPLE_COLUMNS };
    case "section":
      return { ...base, eyebrow: "Part 02", subtitle: "A divider slide between major sections." };
    case "image-focus":
      return { ...base, image_url: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1200" };
    default:
      return base;
  }
}

function titleFor(layout) {
  return layout
    .split(/[-_ ]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ") + " Layout";
}

// Drive the gallery from the canonical registry — guarantees coverage of
// every layout the backend may emit. Sorted for stable snapshot order.
const ALL_LAYOUTS = [...CANONICAL_LAYOUTS].sort();

const THEMES = THEME_NAMES || ["light-pro", "Editorial", "Onyx", "Cobalt", "Sunset", "Whiteboard"];

export default function Gallery() {
  const [theme, setTheme] = useState("light-pro");
  const slides = useMemo(() => ALL_LAYOUTS.map(sampleSlide), []);
  const aliasCount = Object.keys(LAYOUT_ALIASES).length;

  return (
    <div className="min-h-screen bg-nexus-bg p-8 text-white">
      <header className="mx-auto mb-8 flex max-w-7xl items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold">Slide Layout Gallery</h1>
          <p className="mt-1 text-sm text-white/60">
            {ALL_LAYOUTS.length} layouts registered · {aliasCount} aliases · zero TitleSlide fallback
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-white/70">
          Theme:
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            className="rounded-lg border border-white/15 bg-black/30 px-3 py-1.5 text-sm"
          >
            {THEMES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
      </header>
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-8 md:grid-cols-2">
        {slides.map((s) => (
          <figure key={s.layout} data-layout={s.layout} className="space-y-2">
            <figcaption className="text-xs font-mono uppercase tracking-widest text-white/60">
              layout = "{s.layout}"
            </figcaption>
            <SlideRenderer slide={s} theme={theme} deckSeed={`gallery::${s.layout}`} />
          </figure>
        ))}
      </div>
    </div>
  );
}
