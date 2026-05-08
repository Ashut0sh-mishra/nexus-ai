import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  X,
  Maximize2,
  Minimize2,
  StickyNote,
  Loader2,
} from "lucide-react";
import { api } from "../utils/api.js";
import { normalizeSlides } from "../utils/slideParser.js";
import SlideRenderer from "../components/SlideRenderer.jsx";

/**
 * Full-screen presentation mode. Keyboard:
 *   ←/PgUp      previous
 *   →/PgDn/Spc  next
 *   Home/End    first/last
 *   F           toggle browser fullscreen
 *   N           toggle speaker notes
 *   Esc         exit (back to editor / generator)
 *   1–9         jump to slide N
 */
export default function Presenter() {
  const { taskId } = useParams();
  const navigate = useNavigate();

  const [slides, setSlides] = useState([]);
  const [theme, setTheme] = useState("light-pro");
  const [idx, setIdx] = useState(0);
  const [showNotes, setShowNotes] = useState(false);
  const [isFs, setIsFs] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [chrome, setChrome] = useState(true); // auto-hide controls
  const stageRef = useRef(null);
  const hideTimer = useRef(null);

  // ── Load deck ─────────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    api
      .get(`/slides/${taskId}`)
      .then((res) => {
        if (cancelled) return;
        setSlides(normalizeSlides(res.data?.slides || []));
        if (res.data?.theme) setTheme(res.data.theme);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.detail || "Failed to load deck.");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  const total = slides.length;
  const safeIdx = Math.min(Math.max(0, idx), Math.max(0, total - 1));
  const current = slides[safeIdx];

  const next = useCallback(() => setIdx((i) => Math.min(i + 1, total - 1)), [total]);
  const prev = useCallback(() => setIdx((i) => Math.max(i - 1, 0)), []);
  const exit = useCallback(() => {
    if (document.fullscreenElement) document.exitFullscreen?.();
    navigate(`/generate/${taskId}`);
  }, [navigate, taskId]);

  // ── Fullscreen handling ────────────────────────────────────────────────────
  const toggleFs = useCallback(async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await stageRef.current?.requestFullscreen?.();
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const onFs = () => setIsFs(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  // ── Keyboard nav ──────────────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e) => {
      // Ignore when typing in an input.
      const tag = (e.target?.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || e.target?.isContentEditable) return;

      switch (e.key) {
        case "ArrowRight":
        case "PageDown":
        case " ":
          e.preventDefault();
          next();
          break;
        case "ArrowLeft":
        case "PageUp":
          e.preventDefault();
          prev();
          break;
        case "Home":
          e.preventDefault();
          setIdx(0);
          break;
        case "End":
          e.preventDefault();
          setIdx(Math.max(0, total - 1));
          break;
        case "Escape":
          if (!document.fullscreenElement) {
            e.preventDefault();
            exit();
          }
          break;
        case "f":
        case "F":
          e.preventDefault();
          toggleFs();
          break;
        case "n":
        case "N":
          e.preventDefault();
          setShowNotes((v) => !v);
          break;
        default:
          if (/^[1-9]$/.test(e.key)) {
            const n = Number(e.key) - 1;
            if (n < total) setIdx(n);
          }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, exit, toggleFs, total]);

  // ── Auto-hide chrome on idle ──────────────────────────────────────────────
  useEffect(() => {
    function bump() {
      setChrome(true);
      if (hideTimer.current) clearTimeout(hideTimer.current);
      hideTimer.current = setTimeout(() => setChrome(false), 2500);
    }
    bump();
    window.addEventListener("mousemove", bump);
    window.addEventListener("keydown", bump);
    return () => {
      window.removeEventListener("mousemove", bump);
      window.removeEventListener("keydown", bump);
      if (hideTimer.current) clearTimeout(hideTimer.current);
    };
  }, []);

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black text-nexus-muted">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading deck…
      </div>
    );
  }

  if (error || total === 0) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-3 bg-black text-nexus-muted">
        <div>{error || "No slides to present."}</div>
        <button onClick={exit} className="btn-ghost">
          ← Back
        </button>
      </div>
    );
  }

  return (
    <div
      ref={stageRef}
      className="fixed inset-0 z-50 flex flex-col bg-black"
      style={{ cursor: chrome ? "default" : "none" }}
    >
      {/* Top chrome */}
      <div
        className={`absolute left-0 right-0 top-0 z-10 flex items-center justify-between px-4 py-3 transition-opacity ${
          chrome ? "opacity-100" : "opacity-0"
        }`}
      >
        <div className="font-mono text-[11px] tabular-nums text-white/60">
          {String(safeIdx + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setShowNotes((v) => !v)}
            title="Toggle speaker notes (N)"
            className={`rounded-md border px-2 py-1 text-xs transition ${
              showNotes
                ? "border-accent-purple/60 bg-accent-purple/20 text-accent-purple"
                : "border-white/10 bg-white/5 text-white/70 hover:text-white"
            }`}
          >
            <StickyNote className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={toggleFs}
            title="Toggle fullscreen (F)"
            className="rounded-md border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70 transition hover:text-white"
          >
            {isFs ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
          </button>
          <button
            onClick={exit}
            title="Exit (Esc)"
            className="rounded-md border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70 transition hover:text-white"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Stage */}
      <div className="flex flex-1 items-center justify-center px-6 py-6">
        <div className="w-full max-w-[min(96vw,calc(96vh*16/9))]">
          <SlideRenderer slide={current} theme={theme} deckSeed={taskId} />
        </div>
      </div>

      {/* Speaker notes panel */}
      {showNotes && (
        <div className="border-t border-white/10 bg-black/80 px-6 py-3 text-sm text-white/80 backdrop-blur">
          <div className="mb-1 text-[10px] uppercase tracking-widest text-white/40">
            Speaker notes
          </div>
          <div className="max-h-32 overflow-y-auto whitespace-pre-wrap">
            {current?.speaker_notes || (
              <span className="text-white/40">No notes for this slide.</span>
            )}
          </div>
        </div>
      )}

      {/* Side click zones for prev/next */}
      <button
        type="button"
        onClick={prev}
        aria-label="Previous slide"
        className={`absolute left-0 top-0 bottom-0 z-10 flex w-16 items-center justify-start pl-3 transition-opacity ${
          chrome && safeIdx > 0 ? "opacity-100" : "opacity-0"
        }`}
        disabled={safeIdx === 0}
      >
        <ChevronLeft className="h-6 w-6 text-white/50 hover:text-white" />
      </button>
      <button
        type="button"
        onClick={next}
        aria-label="Next slide"
        className={`absolute right-0 top-0 bottom-0 z-10 flex w-16 items-center justify-end pr-3 transition-opacity ${
          chrome && safeIdx < total - 1 ? "opacity-100" : "opacity-0"
        }`}
        disabled={safeIdx >= total - 1}
      >
        <ChevronRight className="h-6 w-6 text-white/50 hover:text-white" />
      </button>

      {/* Progress bar */}
      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-white/5">
        <div
          className="h-full bg-gradient-nexus transition-all"
          style={{ width: `${total ? ((safeIdx + 1) / total) * 100 : 0}%` }}
        />
      </div>

      {/* Help hint (only when chrome is hidden — never shown) */}
      <div
        className={`pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-white/10 bg-black/60 px-3 py-1 text-[10px] uppercase tracking-widest text-white/50 transition-opacity ${
          chrome ? "opacity-100" : "opacity-0"
        }`}
      >
        ← → navigate · F fullscreen · N notes · Esc exit
      </div>
    </div>
  );
}
