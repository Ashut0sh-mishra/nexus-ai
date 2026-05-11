import { useState } from "react";

/**
 * Phase 1D — minimal, unobtrusive indicator for backend-computed
 * `deck_quality` (a serialized `DeckQualityReport`).
 *
 * Color rules:
 *   - ok=true                                  → neutral / green pill
 *   - invalid_count > 0 OR repairs_needed > 0  → amber pill
 *
 * Renders nothing if `quality` is missing.
 */
export default function DeckQualityBadge({ quality }) {
  const [open, setOpen] = useState(false);

  if (!quality || typeof quality !== "object") return null;

  const slideCount = Number(quality.slide_count ?? 0);
  const validCount = Number(quality.valid_count ?? 0);
  const invalidCount = Number(quality.invalid_count ?? 0);
  const repairs = Array.isArray(quality.repair_actions)
    ? quality.repair_actions.length
    : 0;
  const sourceWarnings = Array.isArray(quality.source_warnings)
    ? quality.source_warnings
    : [];
  const sourceWarningCount = sourceWarnings.length;
  const ok = quality.ok === true && invalidCount === 0;

  const tone = ok
    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
    : "border-amber-500/40 bg-amber-500/10 text-amber-300";

  const baseLabel = ok
    ? `Quality OK · ${validCount}/${slideCount} valid`
    : `Quality issues · ${validCount}/${slideCount} valid · ${repairs} repair${
        repairs === 1 ? "" : "s"
      } needed`;
  const label =
    sourceWarningCount > 0
      ? `${baseLabel} · ${sourceWarningCount} source warning${
          sourceWarningCount === 1 ? "" : "s"
        }`
      : baseLabel;

  const errors = Array.isArray(quality.errors) ? quality.errors : [];
  const preview = Array.isArray(quality.repair_preview)
    ? quality.repair_preview
    : [];

  return (
    <div className="flex flex-col items-end gap-2 normal-case tracking-normal">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs transition ${tone}`}
        aria-expanded={open}
        aria-label="Toggle deck quality details"
      >
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            ok ? "bg-emerald-400" : "bg-amber-400"
          }`}
        />
        {label}
      </button>

      {open && (preview.length > 0 || errors.length > 0 || sourceWarningCount > 0) && (
        <div className="w-full max-w-md rounded-lg border border-nexus-border bg-nexus-card/60 p-3 text-[11px] text-nexus-muted">
          {preview.length > 0 ? (
            <>
              <div className="mb-2 font-mono text-nexus-dim">
                deck_quality.repair_preview
              </div>
              <ul className="space-y-1">
                {preview.slice(0, 12).map((p, i) => (
                  <li key={i} className="font-mono">
                    slide {p.slide_index} · {p.layout || "?"} · {p.path} ·{" "}
                    {p.action}
                    {p.action === "preview" && (
                      <>
                        {" → "}
                        {formatPreviewValue(p.after)}
                      </>
                    )}
                  </li>
                ))}
                {preview.length > 12 && (
                  <li className="text-nexus-dim">
                    …and {preview.length - 12} more
                  </li>
                )}
              </ul>
            </>
          ) : errors.length > 0 ? (
            <>
              <div className="mb-2 font-mono text-nexus-dim">
                deck_quality.errors
              </div>
              <ul className="space-y-1">
                {errors.slice(0, 12).map((e, i) => (
                  <li key={i} className="font-mono">
                    slide {e.slide_index} · {e.layout || "?"} · {e.path} ·{" "}
                    {e.code}
                  </li>
                ))}
                {errors.length > 12 && (
                  <li className="text-nexus-dim">
                    …and {errors.length - 12} more
                  </li>
                )}
              </ul>
            </>
          ) : null}

          {sourceWarningCount > 0 && (
            <div className={preview.length > 0 || errors.length > 0 ? "mt-3" : ""}>
              <div className="mb-2 font-mono text-nexus-dim">
                deck_quality.source_warnings
              </div>
              <ul className="space-y-1">
                {sourceWarnings.slice(0, 12).map((w, i) => (
                  <li key={i} className="font-mono break-words">
                    slide {w.slide_index} · {w.layout || "?"} · {w.code}
                  </li>
                ))}
                {sourceWarnings.length > 12 && (
                  <li className="text-nexus-dim">
                    …and {sourceWarnings.length - 12} more
                  </li>
                )}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatPreviewValue(value) {
  if (value === "" || value === null || value === undefined) return '""';
  if (typeof value === "string") return JSON.stringify(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
