import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, Loader2 } from "lucide-react";
import toast from "react-hot-toast";
import { api } from "../utils/api.js";

/**
 * Phase 6S — Upload an existing .pptx and open it in the deck workspace.
 *
 * The button is intentionally lightweight: a hidden file input is triggered
 * on click; on success we navigate to ``/deck/:taskId`` so the imported deck
 * goes through the same edit / export / share surface as generated decks.
 *
 * Limits mirror the backend (100 MB, .pptx only). Errors surfaced via toast
 * use the ``detail.error`` code from the backend when present.
 */
export default function ImportPptxButton({ className = "" }) {
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
    if (!file.name.toLowerCase().endsWith(".pptx")) {
      toast.error("Only .pptx files are accepted.");
      return;
    }
    if (file.size > 100 * 1024 * 1024) {
      toast.error("File exceeds the 100 MB limit.");
      return;
    }

    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post("/import/pptx", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const taskId = data?.task_id;
      if (!taskId) throw new Error("No task_id in response");
      toast.success(`Imported ${data.slide_count} slide(s).`);
      navigate(`/deck/${taskId}`);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const code =
        (detail && typeof detail === "object" && detail.error) ||
        (typeof detail === "string" && detail) ||
        err?.message ||
        "Import failed.";
      const messages = {
        bad_extension: "Only .pptx files are accepted.",
        too_large: "File exceeds the 100 MB limit.",
        corrupt: "File is not a valid .pptx archive.",
        empty: "PPTX has no slides.",
        invalid_deck: "Imported deck failed validation.",
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
          <Upload className="h-3.5 w-3.5" />
        )}
        {busy ? "Importing…" : "Import .pptx"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
        onChange={onChange}
        hidden
      />
    </>
  );
}
