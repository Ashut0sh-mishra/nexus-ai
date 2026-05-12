/**
 * Phase 6AH-A2 — Layout rationale chip.
 *
 * A compact pill that explains *why* the active slide ended up with the
 * layout it did. The rationale is derived from data the pipeline already
 * persists per slide:
 *   - `layout`               (planner + agent/layout_recommender.py)
 *   - `intent.narrative_role` (agent/slide_intent.py)
 *   - `intent.density`
 *   - `intent.communication_goal`
 *
 * No new field is required on the slide payload. The chip is read-only
 * chrome; it does not mutate slides, the renderer, or the exporter.
 */

const LAYOUT_RATIONALE = {
  bigstat: "One number deserved the full slide.",
  section_divider: "A breath between acts.",
  quote: "The strongest voice was a direct quote.",
  comparison: "Two-side framing made the contrast cleaner.",
  timeline: "Dated events benefit from a timeline.",
  chart: "The numbers carry this part.",
  stats: "A small set of numbers carry the point.",
  bullets: "Structured points fit a list.",
  "two-col": "Two related dimensions side by side.",
  title: "Setting the frame.",
  closing: "Landing the call to action.",
};

function prettyRole(role) {
  if (!role) return "";
  return String(role).replace(/_/g, " ");
}

export default function LayoutRationaleChip({ slide }) {
  if (!slide || typeof slide !== "object") return null;
  const layout = slide.layout || "";
  if (!layout) return null;
  const role = slide?.intent?.narrative_role || "";
  const density = slide?.intent?.density || "";
  const goal = slide?.intent?.communication_goal || "";
  const base = LAYOUT_RATIONALE[layout] || `Layout chosen: ${layout}.`;
  const detail = [
    role ? `role: ${prettyRole(role)}` : "",
    density ? `density: ${density}` : "",
    goal ? `goal: ${goal}` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      className="inline-flex max-w-full items-start gap-2 rounded-full border border-nexus-border bg-nexus-card/60 px-3 py-1 text-[11px] text-nexus-muted"
      title={detail || undefined}
    >
      <span className="font-mono uppercase tracking-widest text-nexus-dim">
        {layout}
      </span>
      <span className="truncate text-nexus-muted">{base}</span>
    </div>
  );
}
