import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Eye, X, Check } from "lucide-react";
import SlideRenderer from "./SlideRenderer.jsx";

// All 50 themes available in SlideRenderer. Used by the gallery modal.
const ALL_THEMES = [
  // Light vivid
  "Complete", "Golden", "Simplicity", "Marketing", "Proposal", "Strategy",
  "Launch", "Growth", "Plan", "Pitch", "Sales", "Plan2", "Multi",
  "Stunning", "Profile", "Annual", "Review", "Minimal", "Simple",
  "Elegant", "Modern", "Creative", "Clean", "light-pro",
  // Bold dark
  "Onyx", "Cobalt", "Emerald", "Plum", "Crimson", "Midnight", "Forest",
  "Rose", "Carbon", "Editorial",
  // Vibrant gradient
  "Sunrise", "Aurora", "Tropical", "Lagoon", "Coral", "Ice", "Peach",
  // Bright single-color
  "Sunset", "Ocean", "Mint", "Berry", "Slate", "Lemon", "Lavender",
  "Sand", "Linen", "Mist", "Cerulean", "Whiteboard", "Sketch",
  "Glamour", "Amber", "Arctic", "Neon", "Basalt", "Vellum", "Pixel",
  "Dossier",
];

// Cheap deterministic shuffle so the chip order varies per deck without
// looking random on every re-render. Seeded by the deck's task_id.
function seededShuffle(arr, seed) {
  const a = arr.slice();
  let h = 2166136261 >>> 0;
  const s = String(seed || "");
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  for (let i = a.length - 1; i > 0; i--) {
    h ^= h << 13; h ^= h >>> 17; h ^= h << 5; h >>>= 0;
    const j = h % (i + 1);
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export default function SlideCarousel({ slides = [], initialTheme = "Complete", deckSeed }) {
  const [idx, setIdx] = useState(0);
  const [theme, setTheme] = useState(initialTheme);
  const [galleryOpen, setGalleryOpen] = useState(false);

  // Keep the carousel in sync when the parent resolves auto → real theme.
  useEffect(() => {
    if (initialTheme && initialTheme !== theme) setTheme(initialTheme);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialTheme]);

  // Build picker list: auto-picked theme first, then a deterministically-
  // shuffled subset so the chip row varies per deck (no "hardcoded" feel).
  const pickerThemes = useMemo(() => {
    const shuffled = seededShuffle(ALL_THEMES, deckSeed || theme);
    return Array.from(new Set([theme, ...shuffled])).slice(0, 10);
  }, [deckSeed, theme]);

  useEffect(() => {
    const onKey = (e) => {
      if (galleryOpen && e.key === "Escape") return setGalleryOpen(false);
      if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slides.length, galleryOpen]);

  const total = slides.length;
  const safeIdx = Math.max(0, Math.min(idx, total - 1));
  const current = slides[safeIdx];
  const seed = deckSeed || slides[0]?.task_id || slides[0]?.deck_id;

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
      <div className="mb-3 flex items-center justify-between gap-2 text-xs text-nexus-muted">
        <div className="font-mono tabular-nums">
          {String(safeIdx + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
        </div>
        <div className="flex items-center gap-1.5">
          {pickerThemes.map((t) => (
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
          <button
            onClick={() => setGalleryOpen(true)}
            className="ml-1 inline-flex items-center gap-1 rounded-md border border-nexus-border bg-nexus-card px-2 py-1 text-xs text-nexus-text transition hover:border-nexus-borderHi"
            aria-label="Browse all themes"
            title="Preview all themes"
          >
            <Eye className="h-3.5 w-3.5" />
            <span>Browse all</span>
          </button>
        </div>
      </div>

      <SlideRenderer slide={current} theme={theme} deckSeed={seed} />

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

      {galleryOpen && (
        <ThemeGalleryModal
          slide={current}
          seed={seed}
          activeTheme={theme}
          onPick={(t) => { setTheme(t); setGalleryOpen(false); }}
          onClose={() => setGalleryOpen(false)}
        />
      )}
    </div>
  );
}

// ── Theme gallery modal — previews the current slide in every theme ─────────
function ThemeGalleryModal({ slide, seed, activeTheme, onPick, onClose }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] w-full max-w-6xl overflow-hidden rounded-2xl border border-nexus-border bg-nexus-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-nexus-border px-5 py-3">
          <div>
            <div className="text-sm font-semibold text-nexus-text">Choose a theme</div>
            <div className="text-xs text-nexus-muted">
              Live preview of slide {(slide?.title || "").slice(0, 60) || "—"} in all 50 themes
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-nexus-muted transition hover:bg-nexus-card hover:text-nexus-text"
            aria-label="Close gallery"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="grid max-h-[calc(90vh-60px)] grid-cols-2 gap-3 overflow-y-auto p-4 sm:grid-cols-3 lg:grid-cols-4">
          {ALL_THEMES.map((t) => {
            const isActive = t === activeTheme;
            return (
              <button
                key={t}
                onClick={() => onPick(t)}
                className={`group relative overflow-hidden rounded-lg border text-left transition ${
                  isActive
                    ? "border-nexus-accent ring-2 ring-nexus-accent"
                    : "border-nexus-border hover:border-nexus-borderHi"
                }`}
              >
                <div className="aspect-[16/9] w-full">
                  {/* Scaled-down live preview using CSS transform */}
                  <div
                    className="origin-top-left"
                    style={{ width: "1280px", height: "720px", transform: "scale(0.22)" }}
                  >
                    <SlideRenderer slide={slide} theme={t} deckSeed={seed} />
                  </div>
                </div>
                <div className="flex items-center justify-between border-t border-nexus-border bg-nexus-card px-3 py-2">
                  <span className="text-xs font-medium text-nexus-text">{t}</span>
                  {isActive && <Check className="h-3.5 w-3.5 text-nexus-accent" />}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
