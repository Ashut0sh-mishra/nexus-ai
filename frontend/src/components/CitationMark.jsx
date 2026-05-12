// Phase 6AJ — on-slide citation marker with hover popover.
//
// Replaces the inline <sup title=…> tooltip used in earlier phases.
// Surfaces:
//   • marker number  [n]
//   • source title
//   • domain (parsed from source_url)
//   • basis chip (numeric_match / exact_phrase / keyword_overlap)
//   • supported / weak badge
//   • "Open source ↗" link when source_url is present
//
// Render contract:
//   • Returns null if there is no resolvable supported marker.
//   • Pure inline DOM; no portals, no global state.
//   • Degrades gracefully — works inside any slide layout, including the
//     ones that flatten to PNG/PPTX (the popover is JSX-only and is
//     stripped when the slide is captured as an image).
//   • Never throws on malformed citation entries.
//
// Architecturally: this is an *additive* visual layer on top of
// `slide.citations` produced by `backend/agent/citation_attach.py`.
// Renderers / exporters do not need to change.

import { useState } from "react";

function citationFor(slide, path) {
  if (!slide || !Array.isArray(slide.citations)) return null;
  for (const c of slide.citations) {
    if (c && c.path === path && Number.isFinite(c.marker) && c.marker > 0) {
      return c;
    }
  }
  return null;
}

function domainOf(url) {
  if (typeof url !== "string" || !url) return "";
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

const BASIS_LABEL = {
  numeric_match: "Number matched",
  exact_phrase: "Exact phrase",
  keyword_overlap: "Keyword overlap",
  no_match: "Unverified",
};

export default function CitationMark({ slide, path, p }) {
  const c = citationFor(slide, path);
  const [open, setOpen] = useState(false);
  if (!c) return null;

  const accent = (p && p.accent) || "#888";
  const text = (p && p.text) || "#111";
  const muted = (p && p.muted) || "#666";
  const surface = (p && p.surface) || "#fff";
  const domain = domainOf(c.source_url);
  const basisLabel = BASIS_LABEL[c.basis] || "Source match";

  const marker = (
    <sup
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      tabIndex={0}
      aria-label={`Citation ${c.marker}: ${c.source_title || "source"}`}
      className="ml-1 inline-block cursor-help select-none rounded-sm px-[5px] py-[1px] align-super text-[0.6em] font-semibold tabular-nums outline-none"
      style={{
        background: accent + "26",
        color: accent,
        lineHeight: 1,
      }}
    >
      {c.marker}
    </sup>
  );

  return (
    <span className="relative inline-block">
      {marker}
      {open && (
        <span
          role="tooltip"
          className="pointer-events-none absolute left-1/2 top-full z-50 mt-1 w-[min(20rem,80vw)] -translate-x-1/2 rounded-md border p-3 text-left shadow-xl"
          style={{
            background: surface,
            borderColor: accent + "33",
            color: text,
          }}
        >
          {/* header: marker + supported badge */}
          <span className="mb-1 flex items-center justify-between gap-2 text-[10px] font-semibold uppercase tracking-[0.18em]">
            <span style={{ color: accent }}>Source [{c.marker}]</span>
            <span
              className="rounded-sm px-1.5 py-[1px]"
              style={{
                background: c.supported ? accent + "1f" : "#9993",
                color: c.supported ? accent : muted,
              }}
            >
              {c.supported ? "Verified" : "Weak"}
            </span>
          </span>

          {/* title */}
          {c.source_title && (
            <span
              className="mb-1 block text-[13px] font-semibold leading-snug"
              style={{ color: text }}
            >
              {c.source_title}
            </span>
          )}

          {/* domain */}
          {domain && (
            <span
              className="mb-2 block text-[11px] font-medium tracking-wide"
              style={{ color: muted }}
            >
              {domain}
            </span>
          )}

          {/* basis chip */}
          <span
            className="mb-2 inline-block rounded-sm px-1.5 py-[1px] text-[10px] font-medium uppercase tracking-wide"
            style={{ background: muted + "22", color: muted }}
          >
            {basisLabel}
          </span>

          {/* claim quote */}
          {c.claim_text && (
            <span
              className="block border-l-2 pl-2 text-[11px] italic leading-snug"
              style={{
                borderColor: accent + "55",
                color: muted,
              }}
            >
              “{c.claim_text}”
            </span>
          )}

          {/* link */}
          {c.source_url && (
            <span className="mt-2 block text-right">
              <a
                href={c.source_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="pointer-events-auto text-[11px] font-semibold underline decoration-dotted underline-offset-2"
                style={{ color: accent }}
              >
                Open source ↗
              </a>
            </span>
          )}
        </span>
      )}
    </span>
  );
}
