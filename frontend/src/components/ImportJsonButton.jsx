import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileJson, Loader2 } from "lucide-react";
import toast from "react-hot-toast";
import { api } from "../utils/api.js";

/**
 * Phase 6AN-JsonImport \u2014 Upload a JSON file and ground a deck on it.
 *
 * Two flavours of input are accepted:
 *
 * 1. ``{ "slides": [...] }`` \u2014 pre-built deck. Validated server-side
 *    and persisted directly; navigates to /deck/:taskId.
 * 2. Any other JSON \u2014 used as seed research. The server enqueues a
 *    normal generation task with ``search_web=false`` and the JSON
 *    written to the task memory dir; navigates to /generate?taskId=...
 *    so the live progress stream picks up.
 *
 * The user is prompted for a topic when the JSON has no ``topic`` field.
 */
export default function ImportJsonButton({ className = "" }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const onPick = () => {
    if (busy) return;
    inputRef.current?.click();
  };

  const onChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error("JSON file exceeds the 5 MB limit.");
      return;
    }

    setBusy(true);
    try {
      const text = await file.text();
      let parsed;
      try {
        parsed = JSON.parse(text);
      } catch (err) {
        toast.error("File is not valid JSON.");
        return;
      }

      const hasSlides = Array.isArray(parsed?.slides) && parsed.slides.length > 0;
      let topic =
        (typeof parsed?.topic === "string" && parsed.topic.trim()) ||
        (typeof parsed?.title === "string" && parsed.title.trim()) ||
        "";
      if (!topic) {
        // eslint-disable-next-line no-alert
        topic = window.prompt(
          "Enter a topic / title for this deck:",
          file.name.replace(/\.json$/i, ""),
        ) || "";
      }
      topic = topic.trim();
      if (topic.length < 4) {
        toast.error("Topic must be at least 4 characters.");
        return;
      }

      const body = hasSlides
        ? { topic, slides: parsed.slides, theme: parsed.theme || "Editorial" }
        : {
            topic,
            data: parsed,
            slide_count: Number.isInteger(parsed?.slide_count)
              ? Math.min(20, Math.max(4, parsed.slide_count))
              : 8,
            theme: parsed?.theme || "Editorial",
          };

      const { data } = await api.post("/import/json", body);
      const taskId = data?.task_id;
      if (!taskId) throw new Error("No task_id in response");

      if (data.mode === "direct") {
        toast.success(`Imported ${data.slide_count} slide(s).`);
        navigate(`/deck/${taskId}`);
      } else {
        toast.success("Generating deck from your JSON\u2026");
        // Generator page resumes from a running task when ``taskId`` is
        // supplied as a query param.
        navigate(`/generate?taskId=${encodeURIComponent(taskId)}`);
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const code =
        (detail && typeof detail === "object" && detail.error) ||
        (typeof detail === "string" && detail) ||
        err?.message ||
        "Import failed.";
      const messages = {
        missing_payload: "JSON must contain either 'slides' or 'data'.",
        empty_data: "JSON payload is empty.",
        empty: "No valid slides found in the JSON.",
        invalid_deck: "Slides failed schema validation.",
        seed_write_failed: "Could not save your JSON to the task workspace.",
      };
      toast.error(messages[code] || `Import failed: ${code}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={onPick}
        disabled={busy}
        className={`inline-flex items-center gap-1.5 rounded-full border border-nexus-border bg-nexus-surface px-3.5 py-1.5 text-xs text-nexus-muted transition hover:border-nexus-borderHi hover:bg-nexus-card hover:text-nexus-text disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <FileJson className="h-3.5 w-3.5" />
        )}
        {busy ? "Importing\u2026" : "Import JSON"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        onChange={onChange}
        hidden
      />
    </>
  );
}
