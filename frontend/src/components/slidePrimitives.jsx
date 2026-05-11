/**
 * Phase 6AE — Cinematic visual primitives.
 *
 * A small, deterministic composition kit that the Phase 6AA / 6AC layouts
 * (and any future layouts) build from. Each primitive is:
 *
 *   • presentational only (no data fetching, no state, no effects),
 *   • theme-palette aware (every component takes the palette `p`),
 *   • size/variant configurable (small set of enumerated values; no
 *     free-form className soup),
 *   • exporter-irrelevant (these are frontend-only renderer concerns —
 *     the backend PPTX/HTML exporter is unaffected by this file).
 *
 * Why this exists: before 6AE every layout duplicated the same Tailwind
 * fragments — eyebrow rules ("text-xs uppercase tracking-[0.28em]"),
 * hero metric containers, quote framing, etc. Extracting them as
 * primitives means new layouts compose instead of restating, and a
 * future themability change touches one file instead of seven.
 *
 * Compatibility: this module is additive. The legacy seven layouts
 * (title / bullets / two-col / quote / stats / chart / closing) are NOT
 * refactored to use these primitives in 6AE — refactoring tested code
 * has a non-zero regression budget that we are deliberately skipping.
 * Only the four Phase-6AA/6AC layouts are migrated to compose from
 * primitives in this phase.
 *
 * Locked rules:
 *   - No arbitrary runtime HTML generation.
 *   - No new dependencies.
 *   - No props that pass raw className strings (closed-set variants only).
 *   - No state, no effects, no portals.
 */

import React from "react";

// ── Tokens ────────────────────────────────────────────────────────────────────
//
// A tiny set of size + alignment enums. We deliberately do NOT expose
// arbitrary Tailwind classes through props: that's what causes layouts
// to drift back into duplicated handcrafted structures.

const TITLE_SIZE_CLASS = {
  sm: "text-2xl md:text-3xl",
  md: "text-3xl md:text-4xl",
  lg: "text-5xl md:text-6xl",
  xl: "text-6xl md:text-7xl",
};

const HERO_METRIC_SIZE_CLASS = {
  md: "text-[5.5rem] md:text-[6.5rem]",
  lg: "text-[8rem] md:text-[10rem]",
  xl: "text-[10rem] md:text-[12rem]",
};

const ALIGN_CLASS = {
  left: "items-start text-left",
  center: "items-center text-center",
};

// ── Eyebrow ───────────────────────────────────────────────────────────────────
//
// Small uppercase label that sits above titles, value clusters, and
// section breaks. The single most-duplicated fragment in the prior
// layouts; consolidating it here is the highest-leverage primitive.

export function Eyebrow({ children, p, tone = "muted", spacing = "wide" }) {
  if (!children) return null;
  const tracking = spacing === "extra" ? "tracking-[0.36em]" : "tracking-[0.28em]";
  const color = tone === "accent" ? p.accent : p.muted;
  return (
    <div className={`text-xs uppercase ${tracking}`} style={{ color }}>
      {children}
    </div>
  );
}

// ── Header ────────────────────────────────────────────────────────────────────
//
// Title block with optional eyebrow and subtitle. Used as the lead for
// most non-cover slides. ``size`` controls the title scale; ``align``
// switches between left-stack and centered framing.

export function Header({
  eyebrow,
  title,
  subtitle,
  p,
  size = "md",
  align = "left",
}) {
  if (!title && !eyebrow && !subtitle) return null;
  const titleClass = TITLE_SIZE_CLASS[size] || TITLE_SIZE_CLASS.md;
  const alignClass = ALIGN_CLASS[align] || ALIGN_CLASS.left;
  return (
    <div className={`flex flex-col ${alignClass}`}>
      {eyebrow && <Eyebrow p={p}>{eyebrow}</Eyebrow>}
      {title && (
        <h2
          className={`${eyebrow ? "mt-2" : ""} font-semibold leading-tight ${titleClass}`}
          style={{ color: p.text }}
        >
          {title}
        </h2>
      )}
      {subtitle && (
        <p
          className="mt-2 max-w-3xl text-sm leading-relaxed"
          style={{ color: p.muted }}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}

// ── HeroMetric ────────────────────────────────────────────────────────────────
//
// Single dominant value with optional label and supporting subtitle.
// Used by the ``bigstat`` layout and (in the future) by any layout that
// wants to anchor itself in a single number.

export function HeroMetric({ value, label, subtitle, p, size = "lg" }) {
  const sizeClass = HERO_METRIC_SIZE_CLASS[size] || HERO_METRIC_SIZE_CLASS.lg;
  return (
    <div className="flex flex-col items-start justify-center">
      <div
        className={`font-black leading-[0.9] tabular-nums ${sizeClass}`}
        style={{ color: p.accent }}
      >
        {value || "—"}
      </div>
      {label && (
        <div
          className="mt-3 max-w-2xl text-lg uppercase tracking-widest"
          style={{ color: p.text }}
        >
          {label}
        </div>
      )}
      {subtitle && (
        <div className="mt-4 max-w-xl text-base leading-relaxed" style={{ color: p.muted }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}

// ── NarrativeQuote ────────────────────────────────────────────────────────────
//
// Large pull-quote with attribution. Two variants mirror the existing
// quote layout (centered / side rule); a third "edge" reserves a left
// vertical bar for editorial framing.

export function NarrativeQuote({ quote, attribution, p, variant = "centered" }) {
  if (!quote) return null;
  if (variant === "side") {
    return (
      <figure className="flex h-full flex-col justify-center pl-6"
        style={{ borderLeft: `3px solid ${p.accent}` }}>
        <blockquote
          className="text-2xl font-medium leading-snug md:text-3xl"
          style={{ color: p.text }}
        >
          “{quote}”
        </blockquote>
        {attribution && (
          <figcaption className="mt-4 text-sm uppercase tracking-widest" style={{ color: p.muted }}>
            — {attribution}
          </figcaption>
        )}
      </figure>
    );
  }
  // centered (default) and "edge" both use the same framing with
  // different decorative rules.
  return (
    <figure className="flex h-full flex-col items-center justify-center text-center">
      <blockquote
        className="max-w-3xl text-3xl font-semibold leading-snug md:text-4xl"
        style={{ color: p.text }}
      >
        “{quote}”
      </blockquote>
      {attribution && (
        <figcaption className="mt-6 text-sm uppercase tracking-widest" style={{ color: p.muted }}>
          — {attribution}
        </figcaption>
      )}
    </figure>
  );
}

// ── TimelineSpine ─────────────────────────────────────────────────────────────
//
// Horizontal chronology rail with date nodes. Used by the ``timeline``
// layout. Events ([{date, label}]) are clamped to 6 by the renderer
// (the schema enforces the same cap).

export function TimelineSpine({ events, p }) {
  const clean = (events || []).filter((e) => e && (e.date || e.label)).slice(0, 6);
  const n = clean.length || 1;
  return (
    <div className="relative h-full">
      {/* Spine */}
      <div
        className="absolute left-0 right-0 top-6 h-px"
        style={{ background: p.accent, opacity: 0.35 }}
      />
      <div className="grid h-full" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
        {clean.map((e, i) => (
          <TimelineNode key={i} event={e} p={p} />
        ))}
      </div>
    </div>
  );
}

function TimelineNode({ event, p }) {
  return (
    <div className="relative flex flex-col items-start pr-6">
      <div
        className="z-10 mb-3 h-3 w-3 rounded-full ring-4"
        style={{ background: p.accent, boxShadow: `0 0 0 4px ${p.bg}` }}
      />
      <div
        className="text-xs font-bold uppercase tracking-[0.18em] tabular-nums"
        style={{ color: p.accent }}
      >
        {event.date || "—"}
      </div>
      <div className="mt-1 text-sm leading-snug" style={{ color: p.text }}>
        {event.label || ""}
      </div>
    </div>
  );
}

// ── ComparisonAxis ────────────────────────────────────────────────────────────
//
// Vertical center axis with a labeled badge ("vs" by default). Used by
// the ``comparison`` layout to mark the divide between two sides.

export function ComparisonAxis({ p, label = "vs" }) {
  return (
    <div className="relative flex items-center justify-center">
      <div className="absolute inset-y-4 w-px" style={{ background: p.accent, opacity: 0.3 }} />
      <span
        className="rounded-full border px-3 py-1 text-[10px] font-bold uppercase tracking-[0.22em]"
        style={{
          borderColor: p.accent,
          color: p.accent,
          background: p.bg,
        }}
      >
        {label}
      </span>
    </div>
  );
}

// ── SectionDividerBlock ───────────────────────────────────────────────────────
//
// Typography pause: eyebrow + giant title + thin rule + optional
// subtitle. Used by the ``section_divider`` layout. The block is
// deliberately self-contained so it can also be reused inline inside
// any future layout that wants a sub-section pause.

export function SectionDividerBlock({ eyebrow, title, subtitle, p }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-14 py-12 text-center">
      {eyebrow && <Eyebrow p={p} tone="accent" spacing="extra">{eyebrow}</Eyebrow>}
      <h1
        className="mt-6 max-w-4xl text-5xl font-extrabold leading-tight tracking-tight md:text-7xl"
        style={{ color: p.text }}
      >
        {title}
      </h1>
      <div
        className="mt-8 h-px w-24"
        style={{ background: p.accent, opacity: 0.6 }}
      />
      {subtitle && (
        <p className="mt-6 max-w-xl text-base leading-relaxed" style={{ color: p.muted }}>
          {subtitle}
        </p>
      )}
    </div>
  );
}

// ── VisualCallout ─────────────────────────────────────────────────────────────
//
// Highlighted block for emphasis inside any layout. Two visual variants:
//   - "border" (default): thin accent border, transparent fill.
//   - "fill":              accent-tinted background, no border.
// Children are rendered as-is; the callout supplies framing only.

export function VisualCallout({ children, p, variant = "border", padding = "md" }) {
  const padClass = padding === "lg" ? "p-6" : padding === "sm" ? "p-3" : "p-4";
  const baseStyle =
    variant === "fill"
      ? { background: `${p.accent}1A`, color: p.text }
      : {
          border: `1px solid ${p.accent}55`,
          color: p.text,
        };
  return (
    <div className={`rounded-xl ${padClass}`} style={baseStyle}>
      {children}
    </div>
  );
}

// ── ComparisonSide ────────────────────────────────────────────────────────────
//
// One side of a comparison block. Reused by the ``comparison`` layout;
// kept here so that any future layout that wants a left/right framing
// can drop the same primitive in.

export function ComparisonSide({ block, position, p }) {
  const sideEyebrow = position === "left" ? "Side A" : "Side B";
  return (
    <div className="flex flex-col items-start">
      <Eyebrow p={p}>{sideEyebrow}</Eyebrow>
      <h3 className="mt-2 text-xl font-bold leading-snug md:text-2xl" style={{ color: p.text }}>
        {(block && block.heading) || ""}
      </h3>
      <p className="mt-3 text-sm leading-relaxed" style={{ color: p.muted }}>
        {(block && block.body) || ""}
      </p>
    </div>
  );
}

// ── SlideFrame ────────────────────────────────────────────────────────────────
//
// The standard 14-padding flex column wrapper that all the Phase-6AA/6AC
// layouts share. Splitting it out here keeps the top-level layout
// components narrowly focused on COMPOSITION rather than scaffolding.

export function SlideFrame({ children, p, padding = "lg", direction = "col" }) {
  const padClass = padding === "lg" ? "px-14 py-12" : padding === "md" ? "px-12 py-10" : "px-8 py-8";
  const flexClass = direction === "row" ? "flex-row" : "flex-col";
  return (
    <div
      className={`flex h-full ${flexClass} ${padClass}`}
      style={{ color: p.text }}
    >
      {children}
    </div>
  );
}

// ── Public surface ────────────────────────────────────────────────────────────
//
// Default export bundles the primitive set so callers can do:
//   import primitives from "../components/slidePrimitives.jsx";
//   primitives.Header(...)
// but the named exports above are the preferred import shape.

export default {
  Eyebrow,
  Header,
  HeroMetric,
  NarrativeQuote,
  TimelineSpine,
  ComparisonAxis,
  ComparisonSide,
  SectionDividerBlock,
  VisualCallout,
  SlideFrame,
};
