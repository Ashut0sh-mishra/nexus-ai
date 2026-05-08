import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { ArrowLeft, History, Image as ImageIcon, Loader2, Save } from "lucide-react";
import { api, slidesApi } from "../utils/api.js";
import { normalizeSlides, normalizeSlide } from "../utils/slideParser.js";
import SlideRenderer from "../components/SlideRenderer.jsx";
import EditorSidebar from "../components/EditorSidebar.jsx";
import EditorForm from "../components/EditorForm.jsx";
import QuickActionsBar from "../components/QuickActionsBar.jsx";
import ImageReplacer from "../components/ImageReplacer.jsx";
import VersionHistory from "../components/VersionHistory.jsx";

const THEMES = ["light-pro", "Editorial", "Pixel", "Vellum", "Dossier"];

/**
 * Slide editor: three-column layout (sidebar / preview / form). Wires the
 * Step 11 CRUD endpoints — PUT on save, DELETE / POST reorder /
 * POST regenerate via the sidebar and form actions.
 */
export default function Editor() {
  const { taskId } = useParams();
  const navigate = useNavigate();

  const [slides, setSlides] = useState([]); // server-truth
  const [draft, setDraft] = useState(null); // currently-edited slide copy
  const [activeIdx, setActiveIdx] = useState(0);
  const [theme, setTheme] = useState("light-pro");
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState("");
  const [showImageReplacer, setShowImageReplacer] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [autosaveStatus, setAutosaveStatus] = useState(""); // "", "saving", "saved"
  const autosaveTimer = useRef(null);

  // Initial load.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get(`/slides/${taskId}`)
      .then((res) => {
        if (cancelled) return;
        const list = normalizeSlides(res.data?.slides || []);
        setSlides(list);
        setTopic(res.data?.topic || "");
        if (res.data?.theme) setTheme(res.data.theme);
        if (list.length > 0) {
          setActiveIdx(0);
          setDraft({ ...list[0] });
        }
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || "Failed to load deck.");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  const active = slides[activeIdx];
  const slideId = active?.slide_id || active?.id;

  const isDirty = useMemo(() => {
    if (!draft || !active) return false;
    return JSON.stringify(draft) !== JSON.stringify(active);
  }, [draft, active]);

  // PRD §11 — debounced autosave via /api/slides/{taskId}/bulk.
  useEffect(() => {
    if (!isDirty || !draft || !slideId) return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(async () => {
      setAutosaveStatus("saving");
      try {
        await slidesApi.bulkUpdate(taskId, [draft]);
        const next = slides.slice();
        next[activeIdx] = { ...draft };
        setSlides(next);
        setAutosaveStatus("saved");
        setTimeout(() => setAutosaveStatus(""), 1500);
      } catch (err) {
        setAutosaveStatus("");
        // Don't surface — manual Save still works.
      }
    }, 1500);
    return () => clearTimeout(autosaveTimer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, slideId]);

  // Apply an updated slide returned from quick-actions / image replace.
  function replaceActiveSlide(updated) {
    const norm = normalizeSlide(updated, activeIdx);
    const next = slides.slice();
    next[activeIdx] = norm;
    setSlides(next);
    setDraft({ ...norm });
  }

  function selectSlide(i) {
    if (isDirty && !window.confirm("Discard unsaved changes?")) return;
    setActiveIdx(i);
    setDraft({ ...slides[i] });
    setError("");
  }

  async function save() {
    if (!draft || !slideId) return;
    setSaving(true);
    setError("");
    try {
      const { data } = await api.put(`/slides/${taskId}/${slideId}`, draft);
      const updated = normalizeSlide(data, activeIdx);
      const next = slides.slice();
      next[activeIdx] = updated;
      setSlides(next);
      setDraft({ ...updated });
    } catch (err) {
      setError(err?.response?.data?.detail || "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(i) {
    const id = slides[i]?.slide_id || slides[i]?.id;
    if (!id) return;
    if (!window.confirm(`Delete slide ${i + 1}?`)) return;
    try {
      const { data } = await api.delete(`/slides/${taskId}/${id}`);
      const list = normalizeSlides(data?.slides || []);
      setSlides(list);
      const newIdx = Math.max(0, Math.min(activeIdx, list.length - 1));
      setActiveIdx(newIdx);
      setDraft(list[newIdx] ? { ...list[newIdx] } : null);
    } catch (err) {
      setError(err?.response?.data?.detail || "Delete failed.");
    }
  }

  async function reorder(orderedIds) {
    try {
      const { data } = await api.post(`/slides/${taskId}/reorder`, {
        slide_ids: orderedIds,
      });
      const list = normalizeSlides(data?.slides || []);
      setSlides(list);
      // Keep the same active slide selected post-reorder.
      const newIdx = list.findIndex(
        (s) => (s.slide_id || s.id) === slideId
      );
      const safe = newIdx >= 0 ? newIdx : 0;
      setActiveIdx(safe);
      setDraft(list[safe] ? { ...list[safe] } : null);
    } catch (err) {
      setError(err?.response?.data?.detail || "Reorder failed.");
    }
  }

  async function regenerate(instruction = "") {
    if (!slideId) return;
    setRegenerating(true);
    setError("");
    try {
      const { data } = await api.post(
        `/slides/${taskId}/${slideId}/regenerate`,
        { instruction, keep_layout: true }
      );
      const updated = normalizeSlide(data?.slide || {}, activeIdx);
      const next = slides.slice();
      next[activeIdx] = updated;
      setSlides(next);
      setDraft({ ...updated });
    } catch (err) {
      setError(err?.response?.data?.detail || "Regeneration failed.");
    } finally {
      setRegenerating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center text-nexus-muted">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading deck…
      </div>
    );
  }

  if (error && slides.length === 0) {
    return (
      <div className="mx-auto mt-12 max-w-md rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-center text-sm text-red-300">
        {error}
        <div className="mt-4">
          <button onClick={() => navigate(-1)} className="btn-ghost">
            ← Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to={`/generate/${taskId}`}
            className="text-xs text-nexus-muted hover:text-nexus-text transition inline-flex items-center gap-1"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to deck
          </Link>
          <div className="text-xs text-nexus-dim">·</div>
          <div className="text-sm text-nexus-text">
            {topic || "Untitled deck"}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            className="rounded-md border border-nexus-border bg-nexus-card px-2 py-1 text-xs text-nexus-text"
          >
            {THEMES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <Link
            to={`/present/${taskId}`}
            className="btn-ghost !py-1.5 !text-xs"
          >
            Present
          </Link>
          <button
            onClick={() => setShowImageReplacer(true)}
            disabled={!slideId}
            className="btn-ghost !py-1.5 !text-xs inline-flex items-center gap-1.5 disabled:opacity-40"
          >
            <ImageIcon className="h-3.5 w-3.5" /> Image
          </button>
          <button
            onClick={() => setShowHistory(true)}
            className="btn-ghost !py-1.5 !text-xs inline-flex items-center gap-1.5"
          >
            <History className="h-3.5 w-3.5" /> History
          </button>
          {autosaveStatus && (
            <span className="text-[11px] text-nexus-muted">
              {autosaveStatus === "saving" ? "Autosaving…" : "Autosaved"}
            </span>
          )}
          <button
            onClick={save}
            disabled={!isDirty || saving}
            className="btn-primary inline-flex items-center gap-1.5 !py-1.5 !text-xs disabled:opacity-50"
          >
            {saving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            Save
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-3 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Three-pane layout */}
      <div className="grid gap-4 lg:grid-cols-[260px,1fr,360px]">
        <EditorSidebar
          slides={slides}
          activeIdx={activeIdx}
          onSelect={selectSlide}
          onDelete={remove}
          onReorder={reorder}
        />

        <div className="space-y-3">
          <QuickActionsBar
            taskId={taskId}
            slideId={slideId}
            onSlide={replaceActiveSlide}
          />
          {draft ? (
            <SlideRenderer slide={draft} theme={theme} deckSeed={taskId} />
          ) : (
            <div className="card flex aspect-video items-center justify-center text-nexus-muted">
              No slide selected.
            </div>
          )}
          {isDirty && (
            <div className="text-center text-[11px] uppercase tracking-widest text-accent-purple">
              Unsaved changes
            </div>
          )}
        </div>

        <EditorForm
          slide={draft}
          onChange={setDraft}
          onRegenerate={regenerate}
          regenerating={regenerating}
        />
      </div>

      {showImageReplacer && (
        <ImageReplacer
          taskId={taskId}
          slideId={slideId}
          onSlide={replaceActiveSlide}
          onClose={() => setShowImageReplacer(false)}
        />
      )}
      {showHistory && (
        <VersionHistory
          taskId={taskId}
          onClose={() => setShowHistory(false)}
          onRestored={async () => {
            setShowHistory(false);
            // Reload deck after restore.
            const res = await api.get(`/slides/${taskId}`);
            const list = normalizeSlides(res.data?.slides || []);
            setSlides(list);
            const safe = Math.min(activeIdx, list.length - 1);
            setActiveIdx(safe);
            setDraft(list[safe] ? { ...list[safe] } : null);
          }}
        />
      )}
    </div>
  );
}
