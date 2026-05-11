import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import SlideRenderer from "./SlideRenderer.jsx";

const THEMES = ["light-pro", "Editorial", "Pixel", "Vellum", "Dossier"];

export default function SlideCarousel({ slides = [], initialTheme = "light-pro" }) {
  const [idx, setIdx] = useState(0);
  const [theme, setTheme] = useState(initialTheme);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slides.length]);

  const total = slides.length;
  const safeIdx = Math.max(0, Math.min(idx, total - 1));
  const current = slides[safeIdx];

  const next = () => setIdx((i) => Math.min(i + 1, total - 1));
  const prev = () => setIdx((i) => Math.max(i - 1, 0));

  if (!total) {
    return (
      <div className="card flex aspect-video items-center justify-center text-nexus-muted">
        No slides yet.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between text-xs text-nexus-muted">
        <div className="font-mono tabular-nums">
          {String(safeIdx + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
        </div>
        <div className="flex items-center gap-1.5">
          {THEMES.map((t) => (
            <button
              key={t}
              onClick={() => setTheme(t)}
              className={`rounded-md px-2 py-1 text-xs transition ${
                theme === t
                  ? "bg-nexus-card text-nexus-text border border-nexus-borderHi"
                  : "text-nexus-muted hover:text-nexus-text"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <SlideRenderer slide={current} theme={theme} />

      <div className="mt-4 flex items-center justify-center gap-3">
        <button
          onClick={prev}
          disabled={safeIdx === 0}
          className="btn-ghost !px-3 !py-2"
          aria-label="Previous slide"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-1.5">
          {slides.map((_, i) => (
            <button
              key={i}
              onClick={() => setIdx(i)}
              aria-label={`Go to slide ${i + 1}`}
              className={`h-1.5 rounded-full transition-all ${
                i === safeIdx
                  ? "w-6 bg-gradient-nexus"
                  : "w-1.5 bg-nexus-borderHi hover:bg-nexus-muted"
              }`}
            />
          ))}
        </div>
        <button
          onClick={next}
          disabled={safeIdx === total - 1}
          className="btn-ghost !px-3 !py-2"
          aria-label="Next slide"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
