import { Copy, X, Check } from "lucide-react";
import { useState, useEffect } from "react";
import toast from "react-hot-toast";

export default function ShareModal({ open, onClose, url }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) setCopied(false);
  }, [open]);

  if (!open) return null;

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(url || "");
      setCopied(true);
      toast.success("Link copied.");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Could not copy.");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="card w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">Share this deck</h3>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-nexus-muted hover:bg-nexus-card hover:text-nexus-text"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="mb-3 text-sm text-nexus-muted">
          Anyone with this link can view a read-only version of the
          presentation.
        </p>

        <div className="flex gap-2">
          <input readOnly value={url || ""} className="input font-mono text-xs" />
          <button onClick={onCopy} className="btn-primary !px-3">
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </button>
        </div>

        {url && (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="mt-4 block truncate text-center text-xs text-accent-purple hover:underline"
          >
            Open in new tab →
          </a>
        )}
      </div>
    </div>
  );
}
