/**
 * Phase 6AH-A3 — Per-slide reasoning drawer.
 *
 * Collapsible side-panel that exposes everything the pipeline already
 * knows about the active slide: intent block, layout rationale, claim
 * citations (Phase 6AF), and attached sources (Phase 5).
 *
 * Read-only chrome. No mutation. No renderer change. No exporter change.
 * If the slide carries no intent / citations / sources, the drawer
 * renders nothing (returns null).
 */

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import LayoutRationaleChip from "./LayoutRationaleChip.jsx";

function prettyKey(k) {
  return String(k).replace(/_/g, " ");
}

function IntentBlock({ intent }) {
  if (!intent) return null;
  const keys = ["narrative_role", "tone", "density", "communication_goal"];
  const rows = keys
    .map((k) => [k, intent[k]])
    .filter(([, v]) => v && String(v).trim().length > 0);
  if (rows.length === 0) return null;
  return (
    <dl className="grid grid-cols-[7rem,1fr] gap-x-3 gap-y-1 text-[12px]">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="font-mono uppercase tracking-widest text-nexus-dim">
            {prettyKey(k)}
          </dt>
          <dd className="text-nexus-text">{String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function CitationsBlock({ citations }) {
  if (!Array.isArray(citations) || citations.length === 0) return null;
  return (
    <ul className="space-y-1.5">
      {citations.slice(0, 6).map((c, i) => (
        <li
          key={`cit-${i}`}
          className="rounded-md border border-nexus-border/60 bg-nexus-card/40 px-2 py-1.5 text-[11px]"
        >
          <div className="flex items-center gap-2">
            {c.marker && (
              <span className="font-mono text-[10px] text-accent-purple">
                [{c.marker}]
              </span>
            )}
            <span className="truncate text-nexus-text">
              {c.source_title || c.source_url || "Source"}
            </span>
            {c.supported === false && (
              <span className="ml-auto rounded-full border border-amber-400/40 px-1.5 py-0 text-[10px] text-amber-300">
                weak
              </span>
            )}
          </div>
          {c.claim_text && (
            <div className="mt-0.5 line-clamp-2 text-nexus-muted">
              “{String(c.claim_text)}”
            </div>
          )}
        </li>
      ))}
      {citations.length > 6 && (
        <li className="text-[10px] text-nexus-dim">
          … and {citations.length - 6} more
        </li>
      )}
    </ul>
  );
}

function SourcesBlock({ sources }) {
  if (!Array.isArray(sources) || sources.length === 0) return null;
  return (
    <ul className="space-y-1">
      {sources.slice(0, 5).map((s, i) => (
        <li key={`src-${i}`} className="text-[11px]">
          <div className="truncate text-nexus-text">
            {s.title || s.url || "Source"}
          </div>
          {s.host && (
            <div className="font-mono text-[10px] text-nexus-dim">{s.host}</div>
          )}
        </li>
      ))}
      {sources.length > 5 && (
        <li className="text-[10px] text-nexus-dim">
          … and {sources.length - 5} more
        </li>
      )}
    </ul>
  );
}

export default function SlideReasoningDrawer({ slide, slideIndex = 0 }) {
  const [open, setOpen] = useState(false);
  if (!slide) return null;
  const hasIntent =
    slide.intent &&
    ["narrative_role", "tone", "density", "communication_goal"].some(
      (k) => slide.intent[k],
    );
  const hasCitations =
    Array.isArray(slide.citations) && slide.citations.length > 0;
  const hasSources = Array.isArray(slide.sources) && slide.sources.length > 0;
  const transition =
    typeof slide.transition === "string" && slide.transition.trim().length > 0
      ? slide.transition.trim()
      : "";
  if (!hasIntent && !hasCitations && !hasSources && !transition) return null;

  return (
    <div className="rounded-xl border border-nexus-border bg-nexus-surface/70">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-4 py-2 text-left"
        aria-expanded={open}
      >
        <div className="flex items-center gap-2 truncate">
          <span className="text-[11px] uppercase tracking-widest text-nexus-dim">
            Slide reasoning
          </span>
          <span className="font-mono text-[11px] tabular-nums text-nexus-dim">
            #{String(slideIndex + 1).padStart(2, "0")}
          </span>
          <LayoutRationaleChip slide={slide} />
          {transition && (
            <span
              className="ml-1 truncate rounded-full border border-accent-purple/40 bg-accent-purple/10 px-2 py-[1px] text-[10px] italic text-accent-purple"
              title={`Transition from previous slide: ${transition}`}
            >
              ↪ {transition}
            </span>
          )}
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-nexus-muted" />
        ) : (
          <ChevronDown className="h-4 w-4 text-nexus-muted" />
        )}
      </button>
      {open && (
        <div className="border-t border-nexus-border px-4 py-3">
          <div className="grid gap-4 md:grid-cols-3">
            {hasIntent && (
              <section>
                <h4 className="mb-1.5 text-[11px] uppercase tracking-widest text-nexus-dim">
                  Intent
                </h4>
                <IntentBlock intent={slide.intent} />
              </section>
            )}
            {hasCitations && (
              <section>
                <h4 className="mb-1.5 text-[11px] uppercase tracking-widest text-nexus-dim">
                  Citations
                </h4>
                <CitationsBlock citations={slide.citations} />
              </section>
            )}
            {hasSources && (
              <section>
                <h4 className="mb-1.5 text-[11px] uppercase tracking-widest text-nexus-dim">
                  Sources
                </h4>
                <SourcesBlock sources={slide.sources} />
              </section>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
