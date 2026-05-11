import { useEffect, useMemo, useState } from "react";

import { api } from "../utils/api.js";

/**
 * Phase 6N — claim-level citations panel.
 *
 * Fetches ``GET /api/slides/:taskId/citations`` (deterministic report
 * produced by ``services.claim_citation_service.map_deck_citations``)
 * and renders it grouped by slide.
 *
 * Failure modes are non-blocking: a 404 / 409 / network error renders a
 * compact informational pill. The deck workspace still loads and edits.
 */
export default function CitationsPanel({ taskId, defaultOpen = false }) {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!taskId) return undefined;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .get(`/slides/${taskId}/citations`)
      .then((res) => {
        if (cancelled) return;
        setReport(res.data || null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err?.response?.data?.detail ||
            err?.message ||
            "Could not load citations."
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  const groups = useMemo(() => groupClaimsBySlide(report?.claims), [report]);
  const summary = report?.summary || null;

  if (loading) {
    return (
      <div className="inline-flex items-center gap-2 rounded-full border border-nexus-border bg-nexus-surface px-3 py-1 text-xs text-nexus-muted">
        <span className="h-1.5 w-1.5 rounded-full bg-nexus-dim" />
        Loading citations…
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="inline-flex items-center gap-2 rounded-full border border-nexus-border bg-nexus-surface px-3 py-1 text-xs text-nexus-muted"
        title={error}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-nexus-dim" />
        Citations unavailable
      </div>
    );
  }

  if (!summary || summary.total_claims === 0) {
    return (
      <div className="inline-flex items-center gap-2 rounded-full border border-nexus-border bg-nexus-surface px-3 py-1 text-xs text-nexus-muted">
        <span className="h-1.5 w-1.5 rounded-full bg-nexus-dim" />
        No claims detected for citation
      </div>
    );
  }

  const { total_claims, supported, unsupported } = summary;
  const dotColor =
    unsupported === 0
      ? "bg-emerald-400"
      : supported === 0
        ? "bg-rose-400"
        : "bg-amber-400";
  const label = `Citations · ${supported}/${total_claims} supported · ${unsupported} weak/unsupported`;

  return (
    <div className="flex w-full flex-col gap-2 normal-case tracking-normal">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex w-fit items-center gap-2 rounded-full border border-nexus-border bg-nexus-surface px-3 py-1 text-xs text-nexus-muted transition hover:text-nexus-text"
        aria-expanded={open}
        aria-label="Toggle citation evidence panel"
      >
        <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
        {label}
      </button>

      {open && (
        <div className="w-full max-w-2xl rounded-lg border border-nexus-border bg-nexus-card/60 p-3 text-[11px] text-nexus-muted">
          <div className="mb-2 font-mono text-nexus-dim">
            deck.citations · support_rate{" "}
            {Math.round((summary.support_rate || 0) * 100)}%
          </div>
          <ul className="space-y-3">
            {groups.slice(0, 24).map((g) => (
              <li key={`g-${g.slideIndex}`} className="space-y-1">
                <div className="font-mono text-nexus-dim">
                  slide {g.slideIndex + 1}
                  {g.layout ? ` · ${g.layout}` : ""}
                </div>
                <ul className="space-y-1.5 pl-3">
                  {g.claims.slice(0, 8).map((c, i) => (
                    <ClaimRow key={`g-${g.slideIndex}-c-${i}`} c={c} />
                  ))}
                  {g.claims.length > 8 && (
                    <li className="text-nexus-dim">
                      …and {g.claims.length - 8} more claims
                    </li>
                  )}
                </ul>
              </li>
            ))}
            {groups.length > 24 && (
              <li className="text-nexus-dim">
                …and {groups.length - 24} more slides
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function ClaimRow({ c }) {
  const supported = Boolean(c?.supported);
  const basis = c?.basis || "no_match";
  const weak = supported && typeof c?.score === "number" && c.score < 0.5;
  const tag = !supported
    ? { text: "unsupported", cls: "text-rose-300 border-rose-400/40 bg-rose-500/10" }
    : weak
      ? { text: `weak · ${basis}`, cls: "text-amber-300 border-amber-400/40 bg-amber-500/10" }
      : { text: basis, cls: "text-emerald-300 border-emerald-400/40 bg-emerald-500/10" };

  return (
    <li className="space-y-0.5">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center rounded-full border px-2 py-[1px] text-[10px] font-mono ${tag.cls}`}
        >
          {tag.text}
        </span>
        {typeof c?.score === "number" && supported && (
          <span className="font-mono text-[10px] text-nexus-dim">
            score {c.score.toFixed(2)}
          </span>
        )}
      </div>
      <div className="text-nexus-text break-words">
        {truncate(c?.claim_text || "", 220)}
      </div>
      {supported && (c?.source_title || c?.source_url) && (
        <div className="font-mono text-[10px] text-nexus-dim break-all">
          {c.source_url ? (
            <a
              href={c.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-dotted hover:text-nexus-muted"
            >
              {c.source_title || c.source_url}
            </a>
          ) : (
            c.source_title
          )}
        </div>
      )}
    </li>
  );
}

function groupClaimsBySlide(claims) {
  if (!Array.isArray(claims)) return [];
  const map = new Map();
  for (const c of claims) {
    if (!c || typeof c !== "object") continue;
    const idx = Number.isInteger(c.slide_index) ? c.slide_index : 0;
    if (!map.has(idx)) {
      map.set(idx, {
        slideIndex: idx,
        layout: typeof c.layout === "string" ? c.layout : "",
        claims: [],
      });
    }
    map.get(idx).claims.push(c);
  }
  return Array.from(map.values()).sort((a, b) => a.slideIndex - b.slideIndex);
}

function truncate(s, n) {
  if (typeof s !== "string") return "";
  if (s.length <= n) return s;
  return `${s.slice(0, n - 1)}…`;
}
