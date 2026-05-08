import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, Loader2, Sparkles, Brain } from "lucide-react";

export default function ProgressStream({ events, status, error, analysis }) {
  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-medium tracking-wide text-nexus-muted uppercase">
          Generation progress
        </h3>
        <span
          className={`text-xs ${
            status === "done"
              ? "text-accent-teal"
              : status === "failed"
                ? "text-red-400"
                : "text-nexus-muted"
          }`}
        >
          {status === "done"
            ? "Complete"
            : status === "failed"
              ? "Failed"
              : "Running…"}
        </span>
      </div>

      {analysis && (
        <div className="mb-4 rounded-xl border border-accent-purple/30 bg-accent-purple/5 p-3">
          <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-widest text-accent-purple">
            <Brain className="h-3.5 w-3.5" />
            NEXUS thinking
          </div>
          <div className="flex flex-wrap gap-1.5">
            {analysis.topic_type && (
              <span className="rounded-full border border-nexus-border bg-nexus-card px-2 py-0.5 text-[11px] text-nexus-text">
                {String(analysis.topic_type)} topic
              </span>
            )}
            {analysis.tone && (
              <span className="rounded-full border border-nexus-border bg-nexus-card px-2 py-0.5 text-[11px] text-nexus-text">
                {String(analysis.tone)} tone
              </span>
            )}
            {analysis.ideal_slide_count && (
              <span className="rounded-full border border-nexus-border bg-nexus-card px-2 py-0.5 text-[11px] text-nexus-text">
                {analysis.ideal_slide_count} slides
              </span>
            )}
            {analysis.best_theme && (
              <span className="rounded-full border border-nexus-border bg-nexus-card px-2 py-0.5 text-[11px] text-nexus-text">
                theme: {String(analysis.best_theme)}
              </span>
            )}
            {analysis.data_heavy && (
              <span className="rounded-full border border-accent-teal/40 bg-accent-teal/10 px-2 py-0.5 text-[11px] text-accent-teal">
                data-heavy
              </span>
            )}
            {analysis.has_timeline && (
              <span className="rounded-full border border-accent-teal/40 bg-accent-teal/10 px-2 py-0.5 text-[11px] text-accent-teal">
                timeline
              </span>
            )}
            {analysis.needs_comparison && (
              <span className="rounded-full border border-accent-teal/40 bg-accent-teal/10 px-2 py-0.5 text-[11px] text-accent-teal">
                comparison
              </span>
            )}
          </div>
          {Array.isArray(analysis.key_aspects) && analysis.key_aspects.length > 0 && (
            <p className="mt-2 text-xs text-nexus-muted">
              Covering: {analysis.key_aspects.slice(0, 4).join(" · ")}
            </p>
          )}
        </div>
      )}

      <ol className="space-y-3">
        <AnimatePresence initial={false}>
          {events.map((evt, i) => {
            const isLast = i === events.length - 1;
            const completed = !isLast || status === "done";
            return (
              <motion.li
                key={`${evt.step}-${i}`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="flex items-start gap-3"
              >
                <div className="mt-0.5">
                  {completed ? (
                    <CheckCircle2 className="h-4 w-4 text-accent-teal" />
                  ) : status === "failed" && isLast ? (
                    <span className="block h-4 w-4 rounded-full bg-red-500/30 ring-2 ring-red-500" />
                  ) : (
                    <Loader2 className="h-4 w-4 animate-spin text-accent-purple" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm text-nexus-text">{evt.message}</p>
                  {typeof evt.progress_pct === "number" && (
                    <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-nexus-card">
                      <div
                        className="h-full rounded-full bg-gradient-nexus transition-all duration-500"
                        style={{ width: `${Math.min(100, evt.progress_pct)}%` }}
                      />
                    </div>
                  )}
                </div>
              </motion.li>
            );
          })}
        </AnimatePresence>
        {events.length === 0 && (
          <li className="flex items-center gap-3 text-sm text-nexus-muted">
            <Sparkles className="h-4 w-4 text-accent-purple animate-pulse-soft" />
            Connecting to NEXUS…
          </li>
        )}
      </ol>

      {error && (
        <div className="mt-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}
    </div>
  );
}
