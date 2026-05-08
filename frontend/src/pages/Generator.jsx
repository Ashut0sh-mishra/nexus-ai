import { useEffect, useState } from "react";
import { useParams, useLocation, Link } from "react-router-dom";
import { Sparkles, User } from "lucide-react";
import { api } from "../utils/api.js";
import { useTaskStream } from "../hooks/useGenerate.js";
import { normalizeSlides } from "../utils/slideParser.js";
import ProgressStream from "../components/ProgressStream.jsx";
import SlideCarousel from "../components/SlideCarousel.jsx";
import ExportButtons from "../components/ExportButtons.jsx";

export default function Generator() {
  const { taskId } = useParams();
  const location = useLocation();
  const initialTopic = location.state?.topic || "";
  const initialTheme = location.state?.theme || "auto";
  const { events, status, error, liveSlides, resolvedTheme, analysis } = useTaskStream(taskId);
  const [slides, setSlides] = useState([]);
  const [theme, setTheme] = useState(initialTheme);
  const [topic, setTopic] = useState(initialTopic);

  // If the backend resolved "auto" to a real theme, reflect it immediately.
  useEffect(() => {
    if (resolvedTheme && resolvedTheme !== theme) setTheme(resolvedTheme);
  }, [resolvedTheme]); // eslint-disable-line react-hooks/exhaustive-deps

  const wasAutoPicked =
    initialTheme === "auto" && resolvedTheme && resolvedTheme === theme;

  // While generation runs, show whatever slides have streamed in so far
  // (browser-use-style live preview). On `done`, the GET /slides/:id swap
  // below replaces this with the final, normalized deck.
  const visibleSlides =
    slides.length > 0
      ? slides
      : normalizeSlides((liveSlides || []).filter(Boolean));
  const isStreamingPreview = slides.length === 0 && visibleSlides.length > 0;

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
      })
      .catch(() => {
        /* error surface handled by ProgressStream */
      });
    return () => {
      cancelled = true;
    };
  }, [status, taskId, topic]);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
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
              {status === "done"
                ? `Done. Generated ${slides.length} slides in the \u201C${theme}\u201D theme.`
                : status === "failed"
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

      <div className="grid gap-8 lg:grid-cols-[360px,1fr]">
        <ProgressStream events={events} status={status} error={error} analysis={analysis} />

        <div className="space-y-4">
          {visibleSlides.length > 0 ? (
            <>
              {isStreamingPreview && (
                <div className="inline-flex items-center gap-2 rounded-full border border-accent-purple/40 bg-accent-purple/10 px-3 py-1 text-xs text-accent-purple">
                  <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-accent-purple" />
                  Live preview · {visibleSlides.length} slide{visibleSlides.length === 1 ? "" : "s"} so far
                </div>
              )}
              <SlideCarousel slides={visibleSlides} initialTheme={theme} deckSeed={taskId} />
              {status === "done" && (
                <div className="flex items-center justify-between border-t border-nexus-border/60 pt-4">
                  <p className="text-xs text-nexus-muted">
                    {visibleSlides.length} slides · theme:{" "}
                    <span className="text-nexus-text font-medium">{theme}</span>
                    {wasAutoPicked && (
                      <span className="ml-1 text-accent-purple">
                        (NEXUS auto-picked)
                      </span>
                    )}
                  </p>
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/present/${taskId}`}
                      className="btn-ghost !py-1.5 !text-xs"
                    >
                      Present
                    </Link>
                    <Link
                      to={`/editor/${taskId}`}
                      className="btn-ghost !py-1.5 !text-xs"
                    >
                      Edit deck
                    </Link>
                    <ExportButtons taskId={taskId} theme={theme} />
                  </div>
                </div>
              )}
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
