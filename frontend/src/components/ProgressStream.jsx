import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  CheckCircle2,
  Loader2,
  Sparkles,
  XCircle,
  Ban,
  FileText,
  Globe,
  Quote as QuoteIcon,
  Download,
  ChevronDown,
  ChevronRight,
  BookOpen,
  ListOrdered,
  Brain,
} from "lucide-react";

const STAGE_LABELS = {
  analyze: "Analyze",
  search: "Research",
  plan: "Plan",
  generate: "Generate",
  critique: "Refine",
  images: "Imagery",
  assemble: "Assemble",
  save: "Save",
  done: "Done",
  failed: "Failed",
  cancelled: "Cancelled",
};

const ARTIFACT_ICON = {
  slide_ready: FileText,
  source_found: Globe,
  citation_checked: QuoteIcon,
  export_ready: Download,
};

function _stageLabel(stage) {
  if (!stage) return "";
  return STAGE_LABELS[stage] || stage.charAt(0).toUpperCase() + stage.slice(1);
}

function buildTimeline(events) {
  const rows = [];
  const stageRowByStage = new Map();
  const intel = { sources: [], research: null, outline: null, decisions: [] };

  for (const evt of events) {
    const ev = evt.event;
    const stage = evt.stage || evt.step;

    if (ev === "design_decision") {
      intel.decisions.push({
        decision: evt.decision,
        value: evt.value,
        rationale: evt.rationale,
        category: evt.category,
        sequence: evt.sequence,
      });
      continue;
    }

    // Intel events — extract and skip from timeline
    if (ev === "source_found") {
      intel.sources.push({ title: evt.message, url: evt.url || "" });
      // Still show as artifact under search stage
      const row = stageRowByStage.get(stage || "search");
      if (row) {
        row.artifacts.push({
          event: ev,
          message: evt.message,
          url: evt.url,
          sequence: evt.sequence,
        });
      }
      continue;
    }
    if (ev === "research_note") {
      intel.research = evt.message;
      continue;
    }
    if (ev === "outline_ready") {
      intel.outline = evt.outline || null;
      continue;
    }

    if (ev === "stage_started" || (!ev && stage)) {
      let row = stageRowByStage.get(stage);
      if (!row) {
        row = {
          kind: "stage",
          stage,
          message: evt.message,
          progress_pct: evt.progress_pct,
          state: "running",
          artifacts: [],
          sequence: evt.sequence ?? rows.length,
        };
        stageRowByStage.set(stage, row);
        rows.push(row);
      } else {
        row.message = evt.message;
        if (typeof evt.progress_pct === "number") row.progress_pct = evt.progress_pct;
      }
      continue;
    }

    if (ev === "stage_completed") {
      const row = stageRowByStage.get(stage);
      if (row) {
        row.state = "completed";
        if (typeof evt.progress_pct === "number") row.progress_pct = evt.progress_pct;
      }
      continue;
    }

    if (ev === "slide_ready" || ev === "citation_checked" || ev === "export_ready") {
      const row = stageRowByStage.get(stage);
      const artifact = { event: ev, message: evt.message, slide_index: evt.slide_index, sequence: evt.sequence };
      if (row) row.artifacts.push(artifact);
      else rows.push({ kind: "artifact", ...artifact, stage });
      continue;
    }

    if (ev === "run_succeeded" || ev === "run_failed" || ev === "run_cancelled") {
      for (const row of stageRowByStage.values()) {
        if (row.state === "running") {
          row.state = ev === "run_succeeded" ? "completed" : "stopped";
        }
      }
      rows.push({
        kind: "terminal",
        event: ev,
        message: evt.message,
        error: evt.error,
        sequence: evt.sequence ?? rows.length,
      });
      continue;
    }

    rows.push({
      kind: "artifact",
      event: ev || "step",
      message: evt.message,
      stage,
      sequence: evt.sequence ?? rows.length,
    });
  }

  return { rows, intel };
}

function StatusPill({ status }) {
  const cls =
    status === "done"
      ? "text-accent-teal"
      : status === "failed"
        ? "text-red-400"
        : status === "cancelled"
          ? "text-amber-400"
          : "text-nexus-muted";
  const label =
    status === "done" ? "Complete" : status === "failed" ? "Failed" : status === "cancelled" ? "Cancelled" : "Running…";
  return <span className={`text-xs ${cls}`}>{label}</span>;
}

function StageRow({ row }) {
  const Icon = row.state === "completed" ? CheckCircle2 : row.state === "stopped" ? Ban : Loader2;
  const iconCls =
    row.state === "completed"
      ? "h-4 w-4 text-accent-teal"
      : row.state === "stopped"
        ? "h-4 w-4 text-amber-400"
        : "h-4 w-4 animate-spin text-accent-purple";
  return (
    <li className="flex items-start gap-3">
      <div className="mt-0.5">
        <Icon className={iconCls} />
      </div>
      <div className="flex-1">
        <p className="text-sm text-nexus-text">
          <span className="font-medium">{_stageLabel(row.stage)}</span>
          {row.message ? <span className="text-nexus-muted"> · {row.message}</span> : null}
        </p>
        {typeof row.progress_pct === "number" && (
          <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-nexus-card">
            <div
              className="h-full rounded-full bg-gradient-nexus transition-all duration-500"
              style={{ width: `${Math.min(100, row.progress_pct)}%` }}
            />
          </div>
        )}
        {row.artifacts && row.artifacts.length > 0 && (
          <ul className="mt-2 space-y-1.5">
            {row.artifacts.map((a, idx) => {
              const Icon2 = ARTIFACT_ICON[a.event] || FileText;
              return (
                <li key={`${a.sequence ?? idx}-${a.event}`} className="flex items-center gap-2 text-xs text-nexus-muted">
                  <Icon2 className="h-3.5 w-3.5 text-accent-teal shrink-0" />
                  {a.url ? (
                    <a href={a.url} target="_blank" rel="noopener noreferrer" className="truncate hover:text-nexus-text transition-colors">
                      {a.message}
                    </a>
                  ) : (
                    <span className="truncate">{a.message}</span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </li>
  );
}

function ArtifactRow({ row }) {
  const Icon = ARTIFACT_ICON[row.event] || FileText;
  return (
    <li className="flex items-start gap-3">
      <div className="mt-0.5">
        <Icon className="h-4 w-4 text-accent-teal" />
      </div>
      <p className="flex-1 text-sm text-nexus-text">{row.message}</p>
    </li>
  );
}

function TerminalRow({ row }) {
  const Icon = row.event === "run_succeeded" ? CheckCircle2 : row.event === "run_cancelled" ? Ban : XCircle;
  const cls =
    row.event === "run_succeeded" ? "text-accent-teal" : row.event === "run_cancelled" ? "text-amber-400" : "text-red-400";
  return (
    <li className="flex items-start gap-3">
      <div className="mt-0.5">
        <Icon className={`h-4 w-4 ${cls}`} />
      </div>
      <div className="flex-1">
        <p className={`text-sm ${cls}`}>{row.message}</p>
        {row.error && <p className="mt-0.5 text-xs text-red-300/80">{row.error}</p>}
      </div>
    </li>
  );
}

function Collapsible({ icon: Icon, title, count, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-t border-nexus-border">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-5 py-3 text-left hover:bg-nexus-card/50 transition-colors"
      >
        <Icon className="h-3.5 w-3.5 text-accent-purple shrink-0" />
        <span className="flex-1 text-xs font-medium uppercase tracking-wide text-nexus-muted">{title}</span>
        {count != null && (
          <span className="rounded-full bg-nexus-card px-1.5 py-0.5 text-[10px] text-nexus-dim">{count}</span>
        )}
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 text-nexus-dim" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-nexus-dim" />
        )}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-4">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const DECISION_LABEL = {
  deck_type: "Deck type",
  mood: "Visual mood",
  story_arc: "Story arc",
  layout_recipe: "Layout recipe",
  intent_rhythm: "Narrative pacing",
  layout_upgrade: "Layout upgrade",
  narrative_beats: "Story beats",
};

const BEAT_COLOR = {
  setup: "bg-blue-400/60",
  escalation: "bg-amber-400/70",
  turning_point: "bg-rose-500/80",
  consequence: "bg-emerald-400/60",
  aftermath: "bg-accent-purple/60",
  support: "bg-nexus-card",
};

const BEAT_LABEL = {
  setup: "Setup",
  escalation: "Escalation",
  turning_point: "Turning point",
  consequence: "Consequence",
  aftermath: "Aftermath",
  support: "Support",
};

function isBeatSequence(value) {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((v) => typeof v === "string") &&
    value.some((v) => v in BEAT_COLOR)
  );
}

function BeatStrip({ beats }) {
  if (!Array.isArray(beats) || beats.length === 0) return null;
  const seen = new Set();
  return (
    <div className="mt-1.5">
      <div className="flex h-4 gap-0.5 overflow-hidden rounded">
        {beats.map((b, i) => (
          <div
            key={i}
            title={`${i + 1}. ${BEAT_LABEL[b] || b}`}
            className={`flex-1 ${BEAT_COLOR[b] || "bg-nexus-card"}`}
          />
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
        {beats.filter((b) => {
          if (seen.has(b)) return false;
          seen.add(b);
          return true;
        }).map((b) => (
          <span key={b} className="flex items-center gap-1 text-[10px] text-nexus-dim">
            <span className={`h-1.5 w-1.5 rounded-sm ${BEAT_COLOR[b] || "bg-nexus-card"}`} />
            {BEAT_LABEL[b] || b}
          </span>
        ))}
      </div>
    </div>
  );
}

function isLayoutUpgrade(value) {
  return (
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    "slide_index" in value &&
    "from" in value &&
    "to" in value
  );
}

function LayoutUpgradeBadge({ upgrade }) {
  return (
    <span className="mt-0.5 inline-flex items-center gap-1.5 rounded-md border border-accent-purple/30 bg-accent-purple/10 px-2 py-0.5 font-mono text-[11px] text-nexus-text">
      <span className="text-nexus-dim">slide {upgrade.slide_index}</span>
      <span className="text-nexus-muted line-through">{upgrade.from}</span>
      <span className="text-accent-purple">→</span>
      <span className="font-medium text-accent-teal">{upgrade.to}</span>
    </span>
  );
}

const ROLE_COLOR = {
  opening: "bg-accent-purple/70",
  context: "bg-blue-400/60",
  evidence: "bg-accent-teal/70",
  turning_point: "bg-amber-400/70",
  synthesis: "bg-emerald-400/60",
  closing: "bg-rose-400/60",
  divider: "bg-nexus-muted/40",
  support: "bg-slate-400/50",
};

const DENSITY_HEIGHT = { low: "h-2", medium: "h-3.5", high: "h-5" };

function RhythmStrip({ rhythm }) {
  if (!Array.isArray(rhythm) || rhythm.length === 0) return null;
  return (
    <div className="mt-1.5">
      <div className="flex items-end gap-0.5">
        {rhythm.map((r) => (
          <div
            key={r.i}
            title={`${r.i}. ${r.role || "?"} · ${r.density || "?"}`}
            className={`flex-1 rounded-sm ${ROLE_COLOR[r.role] || "bg-nexus-card"} ${DENSITY_HEIGHT[r.density] || "h-3"}`}
          />
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
        {Array.from(new Set(rhythm.map((r) => r.role).filter(Boolean))).map((role) => (
          <span key={role} className="flex items-center gap-1 text-[10px] text-nexus-dim">
            <span className={`h-1.5 w-1.5 rounded-sm ${ROLE_COLOR[role] || "bg-nexus-card"}`} />
            {role}
          </span>
        ))}
      </div>
    </div>
  );
}

function isRhythm(value) {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    typeof value[0] === "object" &&
    value[0] !== null &&
    "role" in value[0]
  );
}

function formatDecisionValue(value) {
  if (Array.isArray(value)) {
    if (isRhythm(value)) return null; // RhythmStrip handles render
    if (isBeatSequence(value)) return null; // BeatStrip handles render
    return value.join(" → ");
  }
  if (isLayoutUpgrade(value)) return null; // LayoutUpgradeBadge handles render
  if (value == null) return "";
  return String(value);
}

function IntelPanel({ intel }) {
  const hasSources = intel.sources.length > 0;
  const hasResearch = !!intel.research;
  const hasOutline = Array.isArray(intel.outline) && intel.outline.length > 0;
  const hasDecisions = Array.isArray(intel.decisions) && intel.decisions.length > 0;

  if (!hasSources && !hasResearch && !hasOutline && !hasDecisions) return null;

  return (
    <>
      {hasDecisions && (
        <Collapsible icon={Brain} title="AI reasoning" count={intel.decisions.length} defaultOpen>
          <ul className="space-y-2.5">
            {intel.decisions.map((d, i) => {
              const rhythm = isRhythm(d.value) ? d.value : null;
              const beats = isBeatSequence(d.value) ? d.value : null;
              const upgrade = isLayoutUpgrade(d.value) ? d.value : null;
              const formatted = formatDecisionValue(d.value);
              return (
                <li key={i} className="border-l-2 border-accent-purple/40 pl-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-wider text-nexus-dim">
                      {DECISION_LABEL[d.decision] || d.decision}
                    </span>
                    {formatted && (
                      <span className="text-xs font-medium text-nexus-text">{formatted}</span>
                    )}
                  </div>
                  {rhythm && <RhythmStrip rhythm={rhythm} />}
                  {beats && <BeatStrip beats={beats} />}
                  {upgrade && <LayoutUpgradeBadge upgrade={upgrade} />}
                  {d.rationale && (
                    <p className="mt-0.5 text-xs leading-snug text-nexus-muted">{d.rationale}</p>
                  )}
                </li>
              );
            })}
          </ul>
        </Collapsible>
      )}

      {hasSources && (
        <Collapsible icon={Globe} title="Sources" count={intel.sources.length} defaultOpen={hasSources}>
          <ul className="space-y-2">
            {intel.sources.map((s, i) => (
              <li key={i} className="flex items-start gap-2">
                <Globe className="mt-0.5 h-3 w-3 shrink-0 text-accent-teal" />
                {s.url ? (
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-nexus-muted hover:text-nexus-text transition-colors leading-snug"
                  >
                    {s.title}
                  </a>
                ) : (
                  <span className="text-xs text-nexus-muted leading-snug">{s.title}</span>
                )}
              </li>
            ))}
          </ul>
        </Collapsible>
      )}

      {hasResearch && (
        <Collapsible icon={BookOpen} title="Research notes">
          <p className="text-xs text-nexus-muted leading-relaxed whitespace-pre-wrap">{intel.research}</p>
        </Collapsible>
      )}

      {hasOutline && (
        <Collapsible icon={ListOrdered} title="Slide plan" count={intel.outline.length} defaultOpen>
          <ol className="space-y-1.5">
            {intel.outline.map((s) => (
              <li key={s.i} className="flex items-start gap-2">
                <span className="mt-0.5 min-w-[1.25rem] text-right text-[10px] font-mono text-nexus-dim">{s.i}.</span>
                <div className="flex-1">
                  <span className="text-xs text-nexus-text">{s.title}</span>
                  {s.layout && (
                    <span className="ml-1.5 rounded bg-nexus-card px-1 py-px text-[9px] uppercase tracking-wider text-nexus-dim">
                      {s.layout}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </Collapsible>
      )}
    </>
  );
}

export default function ProgressStream({ events, status, error }) {
  const { rows, intel } = buildTimeline(events || []);

  return (
    <div className="card overflow-hidden p-0">
      <div className="flex items-center justify-between px-5 py-4">
        <h3 className="text-sm font-medium uppercase tracking-wide text-nexus-muted">Generation progress</h3>
        <StatusPill status={status} />
      </div>

      <div className="px-5 pb-4">
        <ol className="space-y-3">
          <AnimatePresence initial={false}>
            {rows.map((row, i) => (
              <motion.div
                key={`${row.kind}-${row.sequence ?? i}-${row.stage ?? row.event ?? i}`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
              >
                {row.kind === "stage" && <StageRow row={row} />}
                {row.kind === "artifact" && <ArtifactRow row={row} />}
                {row.kind === "terminal" && <TerminalRow row={row} />}
              </motion.div>
            ))}
          </AnimatePresence>
          {rows.length === 0 && (
            <li className="flex items-center gap-3 text-sm text-nexus-muted">
              <Sparkles className="h-4 w-4 animate-pulse-soft text-accent-purple" />
              Connecting to NEXUS…
            </li>
          )}
        </ol>
      </div>

      {error && (
        <div className="mx-5 mb-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <IntelPanel intel={intel} />
    </div>
  );
}
