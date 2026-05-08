// design/spacing.js — semantic spacing presets + layout primitives.
//
// `space` (in tokens.js) is the raw scale. This file gives those numbers
// **roles** so a renderer never has to remember "the slide canvas uses px-12".
// It also exports `Stack` / `Cluster` / `Inline` for one-liner layouts that
// always honour the rhythm.

import { space } from "./tokens.js";


// ─── Semantic spacing ───────────────────────────────────────────────────────
// Slide-canvas-level rhythm. Tweak here, and every layout obeys.
export const slideSpacing = Object.freeze({
  // Outer padding for the slide content area (16:9 canvas).
  padX: space[12], //  3rem  — 48px
  padY: space[10], // 2.5rem — 40px
  // Major vertical breaks inside the slide.
  sectionGap: space[8],   // 2rem    — between hero block and detail block
  blockGap: space[6],     // 1.5rem  — between content blocks
  // Title rhythm
  eyebrowToTitle: space[2], // 0.5rem
  titleToBody: space[6],    // 1.5rem
  titleToSubtitle: space[3],// 0.75rem
  subtitleToBody: space[6], // 1.5rem
  // Card internals
  cardPad: space[5],   // 1.25rem
  cardGap: space[3],   // 0.75rem
  cardBlockGap: space[4], // 1rem
});

// Tailwind class equivalents — for callers that prefer className.
// Keep in lock-step with the rem values above.
export const slideSpacingClass = Object.freeze({
  padX: "px-12",
  padY: "py-10",
  sectionGap: "gap-8",
  blockGap: "gap-6",
  eyebrowToTitle: "mb-2",
  titleToBody: "mb-6",
  titleToSubtitle: "mb-3",
  subtitleToBody: "mb-6",
  cardPad: "p-5",
  cardGap: "gap-3",
  cardBlockGap: "gap-4",
});

// ─── Layout primitives ──────────────────────────────────────────────────────
// Use these instead of writing `flex flex-col gap-6` for the 200th time.

/** Vertical stack with consistent gap. */
export function Stack({ children, gap = "blockGap", as: Tag = "div", className = "", style = {} }) {
  return (
    <Tag
      className={`flex flex-col ${className}`}
      style={{ gap: slideSpacing[gap] || gap, ...style }}
    >
      {children}
    </Tag>
  );
}

/** Horizontal row that wraps; for tag/chip clusters. */
export function Cluster({ children, gap = "cardGap", align = "center", className = "", style = {} }) {
  return (
    <div
      className={`flex flex-wrap ${className}`}
      style={{ gap: slideSpacing[gap] || gap, alignItems: align, ...style }}
    >
      {children}
    </div>
  );
}

/** Horizontal row, no wrap. */
export function Inline({ children, gap = "cardGap", align = "center", className = "", style = {} }) {
  return (
    <div
      className={`flex ${className}`}
      style={{ gap: slideSpacing[gap] || gap, alignItems: align, ...style }}
    >
      {children}
    </div>
  );
}

/** Responsive auto-sizing grid. `cols` can be a number or "auto-fit". */
export function Grid({
  children,
  cols = 2,
  gap = "blockGap",
  rowAuto = true,
  className = "",
  style = {},
}) {
  const gridTemplateColumns =
    cols === "auto-fit"
      ? "repeat(auto-fit, minmax(14rem, 1fr))"
      : `repeat(${cols}, minmax(0, 1fr))`;
  return (
    <div
      className={`grid ${className}`}
      style={{
        gridTemplateColumns,
        gap: slideSpacing[gap] || gap,
        gridAutoRows: rowAuto ? "minmax(min-content, max-content)" : undefined,
        ...style,
      }}
    >
      {children}
    </div>
  );
}
