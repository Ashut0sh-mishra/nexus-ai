import { useState } from "react";
import { Image as ImageIcon, Loader2, Wand2, Upload, X } from "lucide-react";
import { slidesApi, assetsApi } from "../utils/api.js";

/**
 * Replace the slide image: paste a URL, upload a file (becomes an asset), or
 * generate a new one from a text prompt (Pollinations server-side).
 */
export default function ImageReplacer({ taskId, slideId, onSlide, onClose }) {
  const [tab, setTab] = useState("url");
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState("");
  const [prompt, setPrompt] = useState("");

  async function applyUrl() {
    if (!url.trim() || !slideId) return;
    setBusy(true);
    try {
      const res = await slidesApi.replaceImage(taskId, slideId, {
        image_url: url.trim(),
      });
      if (res?.slide) onSlide?.(res.slide);
      onClose?.();
    } catch (err) {
      alert(err?.response?.data?.detail || "Image update failed");
    } finally {
      setBusy(false);
    }
  }

  async function applyFile(file) {
    if (!file || !slideId) return;
    setBusy(true);
    try {
      const asset = await assetsApi.upload(file);
      const res = await slidesApi.replaceImage(taskId, slideId, {
        asset_id: asset.id,
        image_url: asset.file_url,
      });
      if (res?.slide) onSlide?.(res.slide);
      onClose?.();
    } catch (err) {
      alert(err?.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function applyPrompt() {
    if (!prompt.trim() || !slideId) return;
    setBusy(true);
    try {
      const res = await slidesApi.replaceImage(taskId, slideId, {
        prompt: prompt.trim(),
      });
      if (res?.slide) onSlide?.(res.slide);
      onClose?.();
    } catch (err) {
      alert(err?.response?.data?.detail || "Image generation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="card w-full max-w-md p-5 space-y-4 relative">
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-nexus-muted hover:text-nexus-text"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <ImageIcon className="h-4 w-4" /> Replace image
        </h3>

        <div className="flex gap-1 border-b border-nexus-border">
          {[
            { id: "url", label: "URL" },
            { id: "file", label: "Upload" },
            { id: "ai", label: "AI" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 py-1.5 text-xs border-b-2 transition ${
                tab === t.id
                  ? "border-nexus-accent text-nexus-text"
                  : "border-transparent text-nexus-muted"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "url" && (
          <div className="space-y-2">
            <input
              className="input"
              type="url"
              placeholder="https://images.example.com/foo.jpg"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <button
              onClick={applyUrl}
              disabled={busy || !url.trim()}
              className="btn-primary w-full"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Apply URL"}
            </button>
          </div>
        )}

        {tab === "file" && (
          <label className="block border-dashed border-2 border-nexus-border rounded-xl p-6 text-center cursor-pointer hover:border-nexus-borderHi">
            <Upload className="h-5 w-5 mx-auto mb-2 text-nexus-muted" />
            <p className="text-sm text-nexus-muted">
              {busy ? "Uploading…" : "Choose image to upload"}
            </p>
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => applyFile(e.target.files?.[0])}
            />
          </label>
        )}

        {tab === "ai" && (
          <div className="space-y-2">
            <textarea
              className="input"
              rows={3}
              placeholder="A serene mountain landscape at sunrise, editorial style"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <button
              onClick={applyPrompt}
              disabled={busy || !prompt.trim()}
              className="btn-primary w-full inline-flex items-center justify-center gap-2"
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Wand2 className="h-4 w-4" />
              )}
              Generate
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
