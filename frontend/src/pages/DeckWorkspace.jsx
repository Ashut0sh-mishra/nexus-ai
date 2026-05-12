import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useLocation } from "react-router-dom";
import {
  Sparkles,
  Save,
  RotateCcw,
  Play,
  Plus,
  Copy,
  Trash2,
  ArrowUp,
  ArrowDown,
  Undo2,
  Redo2,
} from "lucide-react";
import toast from "react-hot-toast";

import { api } from "../utils/api.js";
import { normalizeSlide, normalizeSlides } from "../utils/slideParser.js";
import { loadDeck, saveDeck, clearDeck } from "../utils/deckStorage.js";
import {
  makeBlankSlide,
  convertSlideLayout,
  SUPPORTED_LAYOUTS,
} from "../utils/slideFactory.js";
import { useUndoRedo } from "../hooks/useUndoRedo.js";
import SlideRenderer from "../components/SlideRenderer.jsx";
import SlideEditor from "../components/SlideEditor.jsx";
import ExportButtons from "../components/ExportButtons.jsx";
import DeckQualityBadge from "../components/DeckQualityBadge.jsx";
import SourceEvidencePanel from "../components/SourceEvidencePanel.jsx";
import CitationsPanel from "../components/CitationsPanel.jsx";
import StorylineRibbon from "../components/StorylineRibbon.jsx";
import LayoutRationaleChip from "../components/LayoutRationaleChip.jsx";
import SlideReasoningDrawer from "../components/SlideReasoningDrawer.jsx";

const THEMES = ["light-pro", "Editorial", "Pixel", "Vellum", "Dossier"];

/**
 * DeckWorkspace — editable post-generation workspace at /deck/:taskId.
 *
 * Phase 6P adds slide-level structural editing on top of the field-level
 * editor: add / duplicate / delete / move-up / move-down / change layout,
 * plus undo/redo for all local changes (field edits, structural changes,
 * theme picks). Save still uses `PUT /api/slides/{task_id}` (Phase 6L-UX-Fix);
 * Reset still reverts to the server deck; export and share still render
 * the saved server deck.
 */
export default function DeckWorkspace() {
  const { taskId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const [serverDeck, setServerDeck] = useState(null);
  // Phase 6P-Fix: single combined workspace history so undo/redo is
  // chronological across slide edits, structural ops, layout changes,
  // and theme picks. Each entry is a fresh `{ slides, theme }` snapshot.
  const workspaceHist = useUndoRedo({
    slides: [],
    theme: location.state?.theme || "light-pro",
  });
  const slides = workspaceHist.value.slides;
  const theme = workspaceHist.value.theme;

  const [topic, setTopic] = useState(location.state?.topic || "");
  const [quality, setQuality] = useState(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [loadError, setLoadError] = useState(null);

  // Initial load: prefer server deck, then merge in any locally-saved edits.
  useEffect(() => {
    let cancelled = false;
    api
      .get(`/slides/${taskId}`)
      .then((res) => {
        if (cancelled) return;
        const norm = normalizeSlides(res.data?.slides || []);
        const serverTheme = res.data?.theme || "light-pro";
        setServerDeck({
          slides: norm,
          theme: serverTheme,
          topic: res.data?.topic || "",
          quality: res.data?.deck_quality || null,
        });
        if (res.data?.topic) setTopic(res.data.topic);
        if (res.data?.deck_quality) setQuality(res.data.deck_quality);

        const saved = loadDeck(taskId);
        if (saved && Array.isArray(saved.slides) && saved.slides.length > 0) {
          workspaceHist.reset({
            slides: normalizeSlides(saved.slides),
            theme: saved.theme || serverTheme,
          });
          setDirty(true);
        } else {
          workspaceHist.reset({ slides: norm, theme: serverTheme });
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(
          err?.response?.data?.detail ||
            "Could not load this deck. It may still be generating."
        );
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  const total = slides.length;
  const safeIdx = Math.max(0, Math.min(activeIdx, Math.max(total - 1, 0)));
  const active = slides[safeIdx];

  const commitSlides = (next) => {
    workspaceHist.set({ slides: next, theme });
    setDirty(true);
  };

  const handleSlideChange = (next) => {
    if (!active) return;
    const norm = normalizeSlide({ ...active, ...next }, safeIdx);
    const arr = [...slides];
    arr[safeIdx] = norm;
    commitSlides(arr);
  };

  const handleThemePick = (t) => {
    workspaceHist.set({ slides, theme: t });
    setDirty(true);
  };

  // ── Structural ops ────────────────────────────────────────────────────
  const handleAddSlide = () => {
    const blank = normalizeSlide(makeBlankSlide("bullets"), total);
    const insertAt = Math.min(safeIdx + 1, total);
    const arr = [...slides.slice(0, insertAt), blank, ...slides.slice(insertAt)];
    commitSlides(arr);
    setActiveIdx(insertAt);
  };

  const handleDuplicateSlide = () => {
    if (!active) return;
    const dup = normalizeSlide(
      { ...active, id: `${active.id || "slide"}-copy-${Date.now().toString(36)}` },
      safeIdx + 1,
    );
    const arr = [
      ...slides.slice(0, safeIdx + 1),
      dup,
      ...slides.slice(safeIdx + 1),
    ];
    commitSlides(arr);
    setActiveIdx(safeIdx + 1);
  };

  const handleDeleteSlide = () => {
    if (total <= 1) {
      toast.error("Deck must keep at least one slide.");
      return;
    }
    const arr = [...slides.slice(0, safeIdx), ...slides.slice(safeIdx + 1)];
    commitSlides(arr);
    setActiveIdx(Math.max(0, Math.min(safeIdx, arr.length - 1)));
  };

  const moveSlide = (delta) => {
    const j = safeIdx + delta;
    if (j < 0 || j >= total) return;
    const arr = [...slides];
    [arr[safeIdx], arr[j]] = [arr[j], arr[safeIdx]];
    commitSlides(arr);
    setActiveIdx(j);
  };

  const handleLayoutChange = (nextLayout) => {
    if (!active || nextLayout === active.layout) return;
    const converted = normalizeSlide(
      convertSlideLayout(active, nextLayout),
      safeIdx,
    );
    const arr = [...slides];
    arr[safeIdx] = converted;
    commitSlides(arr);
  };

  const handleUndo = () => {
    workspaceHist.undo();
    setDirty(true);
  };
  const handleRedo = () => {
    workspaceHist.redo();
    setDirty(true);
  };

  // ── Persistence ───────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!taskId) return;
    try {
      const res = await api.put(`/slides/${taskId}`, { slides, theme });
      const data = res.data || {};
      const norm = normalizeSlides(data.slides || slides);
      const savedTheme = data.theme || theme;
      workspaceHist.reset({ slides: norm, theme: savedTheme });
      if (data.deck_quality) setQuality(data.deck_quality);
      clearDeck(taskId);
      setServerDeck({
        slides: norm,
        theme: savedTheme,
        topic: data.topic || topic,
        quality: data.deck_quality || null,
      });
      setDirty(false);
      toast.success("Saved to server. Exports & share now use these edits.");
    } catch (err) {
      const detail = err?.response?.data?.detail;
      let message = "Save to server failed.";
      if (detail && typeof detail === "object" && detail.error === "invalid_deck") {
        const n = (detail.invalid_slides || []).length;
        message = `${n} slide${n === 1 ? "" : "s"} failed validation; not saved.`;
      } else if (typeof detail === "string") {
        message = detail;
      }
      const ok = saveDeck(taskId, { slides, theme });
      if (ok) {
        toast.error(`${message} Kept a local draft in this browser.`);
      } else {
        toast.error(message);
      }
    }
  };

  const handleReset = () => {
    if (!serverDeck) return;
    workspaceHist.reset({
      slides: serverDeck.slides,
      theme: serverDeck.theme || "light-pro",
    });
    clearDeck(taskId);
    setActiveIdx(0);
    setDirty(false);
    toast.success("Reverted to server deck.");
  };

  const handlePresent = () => {
    saveDeck(taskId, { slides, theme });
    navigate(`/present/${taskId}`, { state: { theme, topic } });
  };

  if (loadError) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12 text-center">
        <p className="text-nexus-muted">{loadError}</p>
        <Link to="/" className="mt-4 inline-block text-sm text-accent-purple">
          ← New deck
        </Link>
      </div>
    );
  }

  if (!total) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-12 text-center text-nexus-muted">
        Loading deck…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-6">
      {/* Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-nexus">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-nexus-text">
              {topic || "Untitled deck"}
            </h1>
            <p className="font-mono text-[11px] text-nexus-dim">
              task: {taskId} · {total} slides · theme: {theme}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <DeckQualityBadge quality={quality} />
          <button
            onClick={handleUndo}
            disabled={!workspaceHist.canUndo}
            className="btn-ghost"
            title="Undo (local)"
            aria-label="Undo last edit"
          >
            <Undo2 className="h-4 w-4" />
          </button>
          <button
            onClick={handleRedo}
            disabled={!workspaceHist.canRedo}
            className="btn-ghost"
            title="Redo (local)"
            aria-label="Redo edit"
          >
            <Redo2 className="h-4 w-4" />
          </button>
          <button
            onClick={handleReset}
            disabled={!dirty}
            className="btn-ghost"
            title="Discard local edits"
          >
            <RotateCcw className="h-4 w-4" /> Reset
          </button>
          <button
            onClick={handleSave}
            disabled={!dirty}
            className="btn-ghost"
          >
            <Save className="h-4 w-4" /> {dirty ? "Save edits" : "Saved"}
          </button>
          <button onClick={handlePresent} className="btn-primary">
            <Play className="h-4 w-4" /> Present
          </button>
          <ExportButtons taskId={taskId} theme={theme} />
        </div>
      </div>

      {dirty && (
        <div className="mb-3 rounded-md border border-accent-purple/40 bg-accent-purple/10 px-3 py-2 text-xs text-accent-purple">
          You have unsaved edits. Click <strong>Save edits</strong> to persist
          them on the server — exports (PPTX/PDF) and the share link will
          then use the edited deck. Until you save, those still render the
          previously-saved version.
        </div>
      )}

      {/* 3-column workspace */}
      <div className="grid gap-4 lg:grid-cols-[220px,minmax(0,1fr),360px]">
        {/* Sidebar navigator + slide-level actions */}
        <aside className="card max-h-[80vh] overflow-y-auto p-2">
          <div className="mb-2 flex flex-wrap items-center gap-1 px-1">
            <button
              onClick={handleAddSlide}
              className="btn-ghost !px-2 !py-1 text-xs"
              title="Add slide after current"
              aria-label="Add slide"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={handleDuplicateSlide}
              className="btn-ghost !px-2 !py-1 text-xs"
              title="Duplicate current slide"
              aria-label="Duplicate slide"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => moveSlide(-1)}
              disabled={safeIdx === 0}
              className="btn-ghost !px-2 !py-1 text-xs"
              title="Move up"
              aria-label="Move slide up"
            >
              <ArrowUp className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => moveSlide(1)}
              disabled={safeIdx >= total - 1}
              className="btn-ghost !px-2 !py-1 text-xs"
              title="Move down"
              aria-label="Move slide down"
            >
              <ArrowDown className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={handleDeleteSlide}
              disabled={total <= 1}
              className="btn-ghost !px-2 !py-1 text-xs"
              title="Delete current slide"
              aria-label="Delete slide"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
          <ul className="space-y-1">
            {slides.map((s, i) => (
              <li key={s.id || i}>
                <button
                  onClick={() => setActiveIdx(i)}
                  className={`w-full rounded-md px-2 py-2 text-left text-xs transition ${
                    i === safeIdx
                      ? "bg-nexus-card text-nexus-text border border-nexus-borderHi"
                      : "text-nexus-muted hover:text-nexus-text"
                  }`}
                >
                  <div className="font-mono text-[10px] text-nexus-dim">
                    {String(i + 1).padStart(2, "0")} · {s.layout}
                  </div>
                  <div className="mt-1 line-clamp-2 text-sm">
                    {s.title || s.quote || "Untitled"}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* Live preview */}
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <div className="font-mono text-xs text-nexus-dim">
                {String(safeIdx + 1).padStart(2, "0")} /{" "}
                {String(total).padStart(2, "0")}
              </div>
              <LayoutRationaleChip slide={active} />
            </div>
            <div className="flex items-center gap-1.5">
              {THEMES.map((t) => (
                <button
                  key={t}
                  onClick={() => handleThemePick(t)}
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
          <SlideRenderer slide={active} theme={theme} />
          <SlideReasoningDrawer slide={active} slideIndex={safeIdx} />
        </section>

        {/* Editor pane */}
        <aside className="card max-h-[80vh] overflow-y-auto p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-nexus-text">
              Edit slide
            </h3>
            <label className="flex items-center gap-1 text-[11px] uppercase tracking-widest text-nexus-dim">
              Layout
              <select
                value={active?.layout || "bullets"}
                onChange={(e) => handleLayoutChange(e.target.value)}
                className="rounded-md border border-nexus-border bg-nexus-card px-2 py-1 text-xs text-nexus-text focus:border-accent-purple focus:outline-none"
                aria-label="Change slide layout"
              >
                {SUPPORTED_LAYOUTS.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <SlideEditor slide={active} onChange={handleSlideChange} />
        </aside>
      </div>

      <div className="mt-6 space-y-3">
        <StorylineRibbon slides={slides} currentIndex={safeIdx} />
        <CitationsPanel taskId={taskId} />
        <SourceEvidencePanel slides={slides} />
      </div>
    </div>
  );
}
