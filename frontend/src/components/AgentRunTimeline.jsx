/**
 * Phase 6AH-A4 — AgentRun timeline panel.
 *
 * Calls the new read-only GET /api/runs/by-task/{taskId} endpoint and
 * renders the ordered AgentStep rows as a "watch it think" feed. While
 * the run is still active (status in {pending, running, cancelling}),
 * the panel polls every 3 seconds; on terminal status it stops.
 *
 * The panel renders nothing (returns null) when the backend has no
 * AgentRun for the task — that's the normal flag-off path.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../utils/api.js";

const ACTIVE_STATUSES = new Set(["pending", "running", "cancelling"]);

function prettyAction(step) {
  if (!step) return "step";
  if (step.action) return step.action;
  const stage = step?.input?.stage || step?.output?.stage;
  if (stage) return stage;
  return step.kind || "step";
}

function statusTone(status) {
  switch (status) {
    case "ok":
      return "text-emerald-400 border-emerald-400/30";
    case "failed":
    case "error":
      return "text-red-400 border-red-400/30";
    case "running":
      return "text-accent-purple border-accent-purple/30";
    default:
      return "text-nexus-muted border-nexus-border";
  }
}

function formatDuration(startedAt, completedAt) {
  if (!startedAt) return "";
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  if (!Number.isFinite(start) || !Number.isFinite(end)) return "";
  const ms = Math.max(0, end - start);
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function AgentRunTimeline({ taskId, taskStatus }) {
  const [run, setRun] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const stopRef = useRef(false);

  const refresh = useCallback(async () => {
    if (!taskId) return;
    try {
      const res = await api.get(`/runs/by-task/${taskId}`);
      setRun(res.data || null);
      setError(null);
    } catch (e) {
      // 404 is the normal flag-off path; treat as "no run" silently.
      if (e?.response?.status === 404) {
        setRun(null);
        setError(null);
      } else {
        setError(String(e?.message || e));
      }
    } finally {
      setLoaded(true);
    }
  }, [taskId]);

  useEffect(() => {
    stopRef.current = false;
    refresh();
    return () => {
      stopRef.current = true;
    };
  }, [refresh]);

  useEffect(() => {
    if (!run) return undefined;
    const runActive = ACTIVE_STATUSES.has(String(run.status || ""));
    const taskActive =
      taskStatus &&
      ACTIVE_STATUSES.has(String(taskStatus).toLowerCase());
    if (!runActive && !taskActive) return undefined;
    const t = setInterval(() => {
      if (stopRef.current) return;
      refresh();
    }, 3000);
    return () => clearInterval(t);
  }, [run, taskStatus, refresh]);

  if (!loaded) return null;
  if (!run) return null;

  const steps = Array.isArray(run.steps) ? run.steps : [];
  const phase = run?.meta?.phase ? ` · ${run.meta.phase}` : "";
  const mode = run?.meta?.mode ? ` · ${run.meta.mode}` : "";

  return (
    <div className="rounded-xl border border-nexus-border bg-nexus-surface/70">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-[11px] uppercase tracking-widest text-nexus-dim">
            Agent run
          </span>
          <span
            className={[
              "rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-widest",
              statusTone(run.status),
            ].join(" ")}
          >
            {run.status}
          </span>
          <span className="text-[11px] text-nexus-muted">
            {steps.length} step{steps.length === 1 ? "" : "s"}
            {phase}
            {mode}
          </span>
        </div>
        <span className="text-[11px] text-nexus-dim">
          {expanded ? "Hide" : "Show"}
        </span>
      </button>
      {expanded && (
        <ol className="border-t border-nexus-border px-4 py-2">
          {steps.length === 0 && (
            <li className="py-2 text-[12px] text-nexus-muted">
              Waiting for the first step…
            </li>
          )}
          {steps.map((step) => {
            const note =
              step?.output?.note ||
              step?.output?.event ||
              step?.input?.event ||
              "";
            return (
              <li
                key={`s-${step.step_index}`}
                className="grid grid-cols-[2.5rem,1fr,auto] items-baseline gap-3 border-b border-nexus-border/40 py-2 last:border-b-0"
              >
                <span className="font-mono text-[11px] tabular-nums text-nexus-dim">
                  {String(step.step_index).padStart(2, "0")}
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[12px] text-nexus-text">
                      {prettyAction(step)}
                    </span>
                    {step.status && step.status !== "ok" && (
                      <span
                        className={[
                          "rounded-full border px-1.5 py-0 text-[10px] uppercase tracking-widest",
                          statusTone(step.status),
                        ].join(" ")}
                      >
                        {step.status}
                      </span>
                    )}
                  </div>
                  {note && (
                    <div className="mt-0.5 truncate text-[11px] text-nexus-muted">
                      {String(note)}
                    </div>
                  )}
                  {step.error && (
                    <div className="mt-0.5 truncate text-[11px] text-red-400">
                      {String(step.error)}
                    </div>
                  )}
                </div>
                <span className="font-mono text-[11px] tabular-nums text-nexus-dim">
                  {formatDuration(step.started_at, step.completed_at)}
                </span>
              </li>
            );
          })}
        </ol>
      )}
      {error && (
        <div className="border-t border-nexus-border px-4 py-2 text-[11px] text-red-400">
          {error}
        </div>
      )}
    </div>
  );
}
