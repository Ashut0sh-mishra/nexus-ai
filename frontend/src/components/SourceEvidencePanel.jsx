import { useMemo, useState } from "react";

/**
 * Phase 5 — compact, read-only evidence viewer.
 *
 * Reads ``slide.sources`` (populated by Phase 4's
 * ``attach_research_sources_to_deck``) and groups them by slide.
 *
 * Renders nothing if no slide has any sources. Designed to sit beside
 * ``DeckQualityBadge`` / ``ExportButtons`` — no large card-in-card,
 * no design overhaul.
 */
export default function SourceEvidencePanel({ slides, defaultOpen = false }) {
  const [open, setOpen] = useState(Boolean(defaultOpen));

  const groups = useMemo(() => collectSourceGroups(slides), [slides]);
  const totalSources = useMemo(
    () => groups.reduce((acc, g) => acc + g.sources.length, 0),
    [groups]
  );

  if (groups.length === 0 || totalSources === 0) return null;

  const label = `Sources · ${groups.length} slide${
    groups.length === 1 ? "" : "s"
  } · ${totalSources} source${totalSources === 1 ? "" : "s"}`;

  return (
    <div className="flex w-full flex-col gap-2 normal-case tracking-normal">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex w-fit items-center gap-2 rounded-full border border-nexus-border bg-nexus-surface px-3 py-1 text-xs text-nexus-muted transition hover:text-nexus-text"
        aria-expanded={open}
        aria-label="Toggle source evidence panel"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-accent-purple" />
        {label}
      </button>

      {open && (
        <div className="w-full max-w-2xl rounded-lg border border-nexus-border bg-nexus-card/60 p-3 text-[11px] text-nexus-muted">
          <div className="mb-2 font-mono text-nexus-dim">deck.sources</div>
          <ul className="space-y-3">
            {groups.slice(0, 24).map((g) => (
              <li key={`g-${g.slideIndex}`} className="space-y-1">
                <div className="font-mono text-nexus-dim">
                  slide {g.slideIndex + 1} · {g.layout || "?"}
                  {g.title ? ` · ${truncate(g.title, 80)}` : ""}
                </div>
                <ul className="space-y-1 pl-3">
                  {g.sources.slice(0, 6).map((s, i) => (
                    <li key={`g-${g.slideIndex}-s-${i}`} className="space-y-0.5">
                      <div className="text-nexus-text break-words">
                        {s.title || s.host || s.url || "Untitled source"}
                      </div>
                      {(s.url || s.host) && (
                        <div className="font-mono text-[10px] text-nexus-dim break-all">
                          {s.host || hostFromUrl(s.url) || s.url}
                        </div>
                      )}
                      {s.snippet && (
                        <div className="text-[11px] text-nexus-muted break-words">
                          {truncate(s.snippet, 200)}
                        </div>
                      )}
                    </li>
                  ))}
                  {g.sources.length > 6 && (
                    <li className="text-nexus-dim">
                      …and {g.sources.length - 6} more
                    </li>
                  )}
                </ul>
              </li>
            ))}
            {groups.length > 24 && (
              <li className="text-nexus-dim">
                …and {groups.length - 24} more slide{groups.length - 24 === 1 ? "" : "s"}
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function collectSourceGroups(slides) {
  if (!Array.isArray(slides)) return [];
  const out = [];
  slides.forEach((slide, idx) => {
    if (!slide || typeof slide !== "object") return;
    const raw = Array.isArray(slide.sources) ? slide.sources : [];
    if (raw.length === 0) return;
    const sources = raw
      .filter((s) => s && typeof s === "object")
      .map((s) => ({
        title: typeof s.title === "string" ? s.title : "",
        url: typeof s.url === "string" ? s.url : "",
        host: hostFromUrl(typeof s.url === "string" ? s.url : ""),
        snippet: typeof s.snippet === "string" ? s.snippet : "",
      }));
    if (sources.length === 0) return;
    out.push({
      slideIndex: idx,
      layout: typeof slide.layout === "string" ? slide.layout : "",
      title: typeof slide.title === "string" ? slide.title : "",
      sources,
    });
  });
  return out;
}

function hostFromUrl(url) {
  if (typeof url !== "string" || !url.includes("://")) return "";
  const rest = url.split("://", 2)[1];
  const host = rest.split("/", 1)[0] || "";
  return host.replace(/^www\./, "");
}

function truncate(text, max) {
  if (typeof text !== "string") return "";
  return text.length <= max ? text : text.slice(0, max - 1) + "…";
}
