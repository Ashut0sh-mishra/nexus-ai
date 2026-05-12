/**
 * Phase 6AH-A1 + A5 — Storyline ribbon + narrative arc map.
 *
 * Surfaces intelligence the pipeline already produces:
 *   - per-slide `intent.narrative_role` (agent/slide_intent.py)
 *   - per-slide `intent.density`
 *   - per-slide `layout`
 *
 * This is a pure presentational chrome component. It does not mutate
 * slides, does not call the renderer, and does not touch the exporter.
 * If `intent` is absent on every slide, the component renders nothing.
 */

import { useMemo } from "react";

// Canonical narrative roles emitted by agent/slide_intent.py. The order
// roughly matches the natural deck flow; the ribbon uses this order only
// for the legend dot color, never to reorder slides.
const ROLE_COLOR = {
  opening: "bg-accent-purple",
  hook: "bg-accent-purple",
  context: "bg-sky-500",
  setup: "bg-sky-500",
  problem: "bg-rose-500",
  insight: "bg-amber-400",
  evidence: "bg-emerald-500",
  proof: "bg-emerald-500",
  comparison: "bg-indigo-400",
  recommendation: "bg-fuchsia-500",
  call_to_action: "bg-fuchsia-500",
  closing: "bg-nexus-muted",
  conclusion: "bg-nexus-muted",
  divider: "bg-nexus-dim",
  pause: "bg-nexus-dim",
};

const DENSITY_HEIGHT = {
  high: "h-4",
  medium: "h-3",
  low: "h-2",
};

function roleColor(role) {
  if (!role) return "bg-nexus-border";
  const key = String(role).toLowerCase().replace(/\s+/g, "_");
  return ROLE_COLOR[key] || "bg-nexus-muted";
}

function densityHeight(density) {
  if (!density) return "h-3";
  return DENSITY_HEIGHT[String(density).toLowerCase()] || "h-3";
}

function prettyRole(role) {
  if (!role) return "—";
  return String(role).replace(/_/g, " ");
}

function deriveArcLabels(slides) {
  // Collapse consecutive identical roles into the deck-level arc summary.
  // E.g. [hook, context, context, evidence, evidence, closing] →
  // [hook, context, evidence, closing].
  const arc = [];
  for (const s of slides) {
    const role = (s?.intent?.narrative_role || "").toLowerCase();
    if (!role) continue;
    if (arc.length === 0 || arc[arc.length - 1] !== role) {
      arc.push(role);
    }
  }
  return arc;
}

export default function StorylineRibbon({ slides, currentIndex = 0 }) {
  const list = Array.isArray(slides) ? slides : [];
  const hasIntent = useMemo(
    () => list.some((s) => s?.intent?.narrative_role),
    [list],
  );
  const arc = useMemo(() => deriveArcLabels(list), [list]);

  if (list.length === 0 || !hasIntent) return null;

  return (
    <div className="rounded-xl border border-nexus-border bg-nexus-surface/70 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-[11px] uppercase tracking-widest text-nexus-dim">
            Storyline
          </span>
          {arc.length > 0 && (
            <span className="text-[11px] text-nexus-muted">
              {arc.map((a) => prettyRole(a)).join(" → ")}
            </span>
          )}
        </div>
        <span className="text-[11px] text-nexus-dim">
          slide {Math.min(currentIndex + 1, list.length)} / {list.length}
        </span>
      </div>
      <div
        className="mt-2 flex items-end gap-1.5 overflow-x-auto"
        role="list"
        aria-label="Slide storyline"
      >
        {list.map((slide, idx) => {
          const role = slide?.intent?.narrative_role || "";
          const density = slide?.intent?.density || "";
          const layout = slide?.layout || "";
          const isCurrent = idx === currentIndex;
          const tip = [
            `Slide ${idx + 1}`,
            slide?.title ? `· ${slide.title}` : "",
            role ? `\nrole: ${prettyRole(role)}` : "",
            density ? `\ndensity: ${density}` : "",
            layout ? `\nlayout: ${layout}` : "",
          ].join("");
          return (
            <div
              key={slide?.id || `r-${idx}`}
              role="listitem"
              title={tip.trim()}
              className={[
                "flex shrink-0 flex-col items-center gap-1",
                isCurrent ? "opacity-100" : "opacity-70",
              ].join(" ")}
            >
              <div
                className={[
                  "w-3 rounded-sm transition-all",
                  densityHeight(density),
                  roleColor(role),
                  isCurrent ? "ring-2 ring-accent-purple/70 ring-offset-1 ring-offset-nexus-surface" : "",
                ].join(" ")}
                aria-current={isCurrent ? "true" : undefined}
              />
              <span className="text-[10px] tabular-nums text-nexus-dim">
                {idx + 1}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
