import { useEffect, useState } from "react";
import { useParams, useLocation, Link } from "react-router-dom";
import { Sparkles, User, Pencil, Play, X, RotateCw } from "lucide-react";
import toast from "react-hot-toast";
import { api } from "../utils/api.js";
import { useTaskStream } from "../hooks/useGenerate.js";
import { useJobLifecycle } from "../hooks/useJobLifecycle.js";
import { normalizeSlides } from "../utils/slideParser.js";
import ProgressStream from "../components/ProgressStream.jsx";
import SlideCarousel from "../components/SlideCarousel.jsx";
import ExportButtons from "../components/ExportButtons.jsx";
import DeckQualityBadge from "../components/DeckQualityBadge.jsx";
import SourceEvidencePanel from "../components/SourceEvidencePanel.jsx";
import StorylineRibbon from "../components/StorylineRibbon.jsx";
import AgentRunTimeline from "../components/AgentRunTimeline.jsx";

export default function Generator() {
  const { taskId } = useParams();
  const location = useLocation();
  const initialTopic = location.state?.topic || "";
  const initialTheme = location.state?.theme || "light-pro";
  const [restartKey, setRestartKey] = useState(0);
  const { events, status, error, liveSlides } = useTaskStream(taskId, restartKey);
  const [slides, setSlides] = useState([]);
  const [theme, setTheme] = useState(initialTheme);
  const [topic, setTopic] = useState(initialTopic);
  const [quality, setQuality] = useState(null);
  const { cancel, retry, resume, inFlight, lastError } = useJobLifecycle(taskId);

  // While generation runs, show whatever slides have streamed in so far
  // (browser-use-style live preview). On `done`, the GET /slides/:id swap
  // below replaces this with the final, normalized deck.
  const visibleSlides =
    slides.length > 0
      ? slides
      : normalizeSlides((liveSlides || []).filter(Boolean));
  const isStreamingPreview = slides.length === 0 && visibleSlides.length > 0;
  const isDone = status === "done";
  // Phase 6Q lifecycle classification (mirrors services/lifecycle_service.py).
  const isRunning = status === "pending" || status === "running";
  const isCancelling = status === "cancelling";
  const isCancelled = status === "cancelled";
  const isFailed = status === "failed";
  const canCancel = (isRunning || isCancelling) && inFlight !== "cancel";
  const canRetryOrResume = (isFailed || isCancelled) && !inFlight;

  const handleCancel = async () => {
    const r = await cancel();
    if (r) toast("Cancelling generation…", { icon: "⏹" });
  };
  const handleRetry = async () => {
    const r = await retry();
    if (r) {
      setSlides([]);
      setRestartKey((k) => k + 1);
      toast.success("Retrying from scratch…");
    }
  };
  const handleResume = async () => {
    const r = await resume();
    if (r) {
      setSlides([]);
      setRestartKey((k) => k + 1);
      toast(
        "Resuming… (no checkpoint persisted; runs from scratch)",
        { icon: "↻" },
      );
    }
  };

  useEffect(() => {
    if (status !== "done") return;
    let cancelled = false;
    api
      .get(`/slides/${taskId}`)
      .then((res) => {
        if (cancelled) return;
        setSlides(normalizeSlides(res.data?.slides || []));
        if (res.data?.theme) setTheme(res.data.theme);
        if (!topic && res.data?.topic) setTopic(res.data.topic);
        if (res.data?.deck_quality) setQuality(res.data.deck_quality);
      })
      .catch(() => {
        /* error surface handled by ProgressStream */
      });
    return () => {
      cancelled = true;
    };
  }, [status, taskId, topic]);

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-6xl flex-col px-6 py-8">
      {/* ChatGPT-style thread header */}
      <div className="mb-6 space-y-3">
        <div className="flex items-start gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-nexus-card border border-nexus-border">
            <User className="h-4 w-4 text-nexus-muted" />
          </div>
          <div className="flex-1 rounded-2xl rounded-tl-sm border border-nexus-border bg-nexus-surface px-4 py-3">
            <div className="text-[11px] uppercase tracking-widest text-nexus-dim">You</div>
            <p className="mt-1 text-sm text-nexus-text">
              {topic || (
                <span className="text-nexus-muted">
                  Generating presentation…
                </span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-nexus">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1 rounded-2xl rounded-tl-sm border border-nexus-border bg-nexus-surface px-4 py-3">
            <div className="text-[11px] uppercase tracking-widest text-nexus-dim">NEXUS</div>
            <p className="mt-1 text-sm text-nexus-muted">
              {isDone
                ? `Done. Generated ${slides.length} slides in the \u201C${theme}\u201D theme.`
                : isCancelling
                ? "Stopping after the current step…"
                : isCancelled
                ? "Generation cancelled. You can retry or resume."
                : isFailed
                ? "Generation failed. See log below."
                : "Researching, planning, writing, and assembling your deck…"}
            </p>
          </div>
        </div>
      </div>

      <div className="mb-3 flex items-center justify-between">
        <p className="font-mono text-[11px] text-nexus-dim">task: {taskId}</p>
        <Link to="/" className="text-xs text-nexus-muted hover:text-nexus-text transition">
          ← New deck
        </Link>
      </div>

      {/* Phase 6Q: lifecycle action bar. Visible whenever the run is
          not yet succeeded so the user can cancel a running job or
          retry / resume a failed / cancelled one. Buttons are disabled
          during in-flight requests to prevent double-submit. */}
      {!isDone && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-nexus-border bg-nexus-surface/70 px-4 py-3">
          <div className="text-xs text-nexus-muted">
            {isRunning && "Generation in progress."}
            {isCancelling && "Cancelling at the next safe checkpoint…"}
            {isCancelled && "Cancelled."}
            {isFailed && "Failed. You can retry or resume."}
            {lastError && (
              <span className="ml-2 text-red-400">({String(lastError)})</span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleCancel}
              disabled={!canCancel}
              className="btn-ghost"
              title="Stop generation at the next safe checkpoint"
            >
              <X className="h-4 w-4" />
              {inFlight === "cancel" ? "Cancelling…" : "Cancel"}
            </button>
            <button
              onClick={handleRetry}
              disabled={!canRetryOrResume}
              className="btn-ghost"
              title="Retry the run from scratch"
            >
              <RotateCw className="h-4 w-4" />
              {inFlight === "retry" ? "Retrying…" : "Retry"}
            </button>
            <button
              onClick={handleResume}
              disabled={!canRetryOrResume}
              className="btn-ghost"
              title="Resume (no persisted checkpoint; runs from scratch)"
            >
              <Play className="h-4 w-4" />
              {inFlight === "resume" ? "Resuming…" : "Resume"}
            </button>
          </div>
        </div>
      )}

      {/* Phase 6M: prominent app-workspace action bar. Surfaces every
          product action without forcing the user to scroll. Shown only
          once status === "done" so we never advertise actions for a deck
          that does not exist yet. */}
      {isDone && (
        <div className="mb-5 rounded-xl border border-nexus-border bg-nexus-surface/70 px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <DeckQualityBadge quality={quality} />
              <p className="text-xs text-nexus-muted">
                {slides.length} slides · theme: {theme}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                to={`/deck/${taskId}`}
                state={{ theme, topic }}
                className="btn-primary"
              >
                <Pencil className="h-4 w-4" /> Open editor
              </Link>
              <Link
                to={`/present/${taskId}`}
                state={{ theme, topic }}
                className="btn-ghost"
              >
                <Play className="h-4 w-4" /> Present
              </Link>
              <ExportButtons taskId={taskId} theme={theme} />
            </div>
          </div>
        </div>
      )}

      <div className="grid flex-1 gap-8 lg:grid-cols-[360px,1fr]">
        <div className="space-y-3">
          <ProgressStream events={events} status={status} error={error} />
          <AgentRunTimeline taskId={taskId} taskStatus={status} />
        </div>

        <div className="space-y-4">
          {visibleSlides.length > 0 ? (
            <>
              {isStreamingPreview && (
                <div className="inline-flex items-center gap-2 rounded-full border border-accent-purple/40 bg-accent-purple/10 px-3 py-1 text-xs text-accent-purple">
                  <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-accent-purple" />
                  Live preview · {visibleSlides.length} slide{visibleSlides.length === 1 ? "" : "s"} so far
                </div>
              )}
              <SlideCarousel
                slides={visibleSlides}
                initialTheme={theme}
                onThemeChange={setTheme}
              />
              {isDone && <StorylineRibbon slides={visibleSlides} />}
              {isDone && <SourceEvidencePanel slides={slides} />}
            </>
          ) : (
            <div className="card flex aspect-video items-center justify-center text-nexus-muted">
              {status === "failed"
                ? "Generation failed."
                : "Your deck will appear here as it’s written."}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
