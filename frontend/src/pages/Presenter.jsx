import { useEffect, useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { X, ChevronLeft, ChevronRight } from "lucide-react";

import { api } from "../utils/api.js";
import { normalizeSlides } from "../utils/slideParser.js";
import { loadDeck } from "../utils/deckStorage.js";
import SlideRenderer from "../components/SlideRenderer.jsx";

/**
 * Presenter — minimal fullscreen presentation view at /present/:taskId.
 *
 * Hides the navbar/footer chrome by absolutely-positioning a black
 * fullscreen layer; the surrounding `App.jsx` chrome is rendered behind
 * it. Reads slides from localStorage first (so local edits are honored)
 * and falls back to the server deck.
 *
 * Keyboard:
 *   ArrowRight / Space / PageDown — next
 *   ArrowLeft / PageUp            — previous
 *   Escape                        — back to workspace
 */
export default function Presenter() {
  const { taskId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [slides, setSlides] = useState([]);
  const [theme, setTheme] = useState(location.state?.theme || "light-pro");
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const saved = loadDeck(taskId);
    if (saved && Array.isArray(saved.slides) && saved.slides.length > 0) {
      setSlides(normalizeSlides(saved.slides));
      if (saved.theme) setTheme(saved.theme);
      return;
    }
    let cancelled = false;
    api
      .get(`/slides/${taskId}`)
      .then((res) => {
        if (cancelled) return;
        setSlides(normalizeSlides(res.data?.slides || []));
        if (res.data?.theme) setTheme(res.data.theme);
      })
      .catch(() => {
        /* leave empty; UI shows fallback */
      });
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  const total = slides.length;
  const safeIdx = Math.max(0, Math.min(idx, total - 1));

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") {
        e.preventDefault();
        setIdx((i) => Math.min(i + 1, Math.max(total - 1, 0)));
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        setIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === "Escape") {
        navigate(`/deck/${taskId}`);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [total, navigate, taskId]);

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-black">
      <button
        onClick={() => navigate(`/deck/${taskId}`)}
        aria-label="Exit presentation"
        className="absolute right-4 top-4 z-10 rounded-md bg-white/10 p-2 text-white/80 backdrop-blur hover:bg-white/20"
      >
        <X className="h-4 w-4" />
      </button>

      <div className="flex flex-1 items-center justify-center px-6">
        {total > 0 ? (
          <div className="w-full max-w-[min(95vw,calc(95vh*16/9))]">
            <SlideRenderer slide={slides[safeIdx]} theme={theme} />
          </div>
        ) : (
          <p className="text-white/70">No slides to present.</p>
        )}
      </div>

      {total > 0 && (
        <div className="flex items-center justify-center gap-6 px-6 py-4 text-white/70">
          <button
            onClick={() => setIdx((i) => Math.max(i - 1, 0))}
            disabled={safeIdx === 0}
            aria-label="Previous slide"
            className="rounded-full bg-white/10 p-2 hover:bg-white/20 disabled:opacity-30"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <div className="font-mono text-xs tabular-nums">
            {String(safeIdx + 1).padStart(2, "0")} /{" "}
            {String(total).padStart(2, "0")}
          </div>
          <button
            onClick={() =>
              setIdx((i) => Math.min(i + 1, Math.max(total - 1, 0)))
            }
            disabled={safeIdx === total - 1}
            aria-label="Next slide"
            className="rounded-full bg-white/10 p-2 hover:bg-white/20 disabled:opacity-30"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>
      )}
    </div>
  );
}
