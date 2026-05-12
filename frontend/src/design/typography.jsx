// design/typography.js — type scale + ready-made text components.
//
// Use the components, not raw <h1>/<p>. They guarantee:
//   - consistent line-height + tracking across the deck
//   - palette-aware color (passes the active palette through `p` prop)
//   - one place to retune the whole product if a designer says
//     "make every body text 1px bigger".
//
// The scale is FLUID (clamp): readable on the editor preview AND on
// full-screen export PNGs. Sizes are tuned for the 16:9 slide canvas.

// ─── Scale (raw values for inline style or python mirror) ───────────────────
// Phase 6AI-B2 — widened display→body ratio for more cinematic hierarchy.
// Display + h1 sizes scale higher and tighter; body sizes are unchanged so
// reading remains comfortable. Letter-spacing tightens on the upper end.
export const typeScale = Object.freeze({
  display: { size: "clamp(3rem, 6vw, 5.5rem)",     weight: 800, lh: 1.0,  tracking: "-0.025em" },
  h1:      { size: "clamp(2.5rem, 4.5vw, 4rem)",   weight: 800, lh: 1.05, tracking: "-0.02em" },
  h2:      { size: "clamp(1.875rem, 3.2vw, 2.75rem)", weight: 700, lh: 1.12, tracking: "-0.012em" },
  h3:      { size: "clamp(1.25rem, 2vw, 1.75rem)", weight: 700, lh: 1.2,  tracking: "-0.005em" },
  h4:      { size: "clamp(1rem, 1.4vw, 1.25rem)",   weight: 700, lh: 1.3,  tracking: "0" },
  body:    { size: "clamp(0.875rem, 1.1vw, 1rem)",  weight: 400, lh: 1.55, tracking: "0" },
  bodyLg:  { size: "clamp(1rem, 1.3vw, 1.125rem)",  weight: 400, lh: 1.55, tracking: "0" },
  caption: { size: "0.75rem",                       weight: 500, lh: 1.4,  tracking: "0.01em" },
  eyebrow: { size: "0.6875rem",                     weight: 600, lh: 1.2,  tracking: "0.32em" },
  mono:    { size: "0.6875rem",                     weight: 500, lh: 1.2,  tracking: "0.18em" },
});

// Build a `style` object from a scale entry. Keeps JSX terse.
function styleFor(key, extra = {}) {
  const s = typeScale[key];
  return {
    fontSize: s.size,
    fontWeight: s.weight,
    lineHeight: s.lh,
    letterSpacing: s.tracking,
    ...extra,
  };
}

// ─── Components ─────────────────────────────────────────────────────────────
// Every component takes a `p` (palette) so it can color itself correctly
// against the active theme. `as` lets callers override the HTML tag.

export function Display({ children, p, as: Tag = "h1", className = "", style = {} }) {
  return (
    <Tag className={className} style={{ color: p?.text, ...styleFor("display"), ...style }}>
      {children}
    </Tag>
  );
}

export function Title({ children, p, size = "h2", as, className = "", style = {} }) {
  const Tag = as || (size === "h1" ? "h1" : size === "h3" ? "h3" : "h2");
  return (
    <Tag className={className} style={{ color: p?.text, ...styleFor(size), ...style }}>
      {children}
    </Tag>
  );
}

export function Subtitle({ children, p, className = "", style = {} }) {
  if (!children) return null;
  return (
    <p className={className} style={{ color: p?.muted, ...styleFor("bodyLg"), ...style }}>
      {children}
    </p>
  );
}

export function Body({ children, p, size = "body", className = "", style = {} }) {
  return (
    <p className={className} style={{ color: p?.text, ...styleFor(size), ...style }}>
      {children}
    </p>
  );
}

export function Caption({ children, p, className = "", style = {} }) {
  return (
    <span className={className} style={{ color: p?.muted, ...styleFor("caption"), ...style }}>
      {children}
    </span>
  );
}

export function Eyebrow({ children, p, tint, className = "", style = {} }) {
  if (!children) return null;
  return (
    <div
      className={`uppercase ${className}`}
      style={{ color: tint || p?.accent, ...styleFor("eyebrow"), ...style }}
    >
      {children}
    </div>
  );
}

export function Mono({ children, p, tint, className = "", style = {} }) {
  return (
    <span
      className={`uppercase ${className}`}
      style={{ color: tint || p?.muted, fontFamily: "ui-monospace, SFMono-Regular, monospace", ...styleFor("mono"), ...style }}
    >
      {children}
    </span>
  );
}
