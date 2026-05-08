import { useState } from "react";
import {
  Sparkles,
  Wand2,
  Minimize2,
  Maximize2,
  Image as ImageIcon,
  MessageSquare,
  Loader2,
} from "lucide-react";
import { slidesApi } from "../utils/api.js";

const ACTIONS = [
  { id: "rewrite", label: "Rewrite", icon: Wand2 },
  { id: "simplify", label: "Simplify", icon: Sparkles },
  { id: "shorten", label: "Shorter", icon: Minimize2 },
  { id: "expand", label: "Expand", icon: Maximize2 },
  { id: "visualize", label: "Visualize", icon: ImageIcon },
];

const TONES = ["professional", "friendly", "bold", "casual", "academic"];

/**
 * Floating quick-action toolbar that lives above the slide preview.
 * Hits POST /api/slides/{taskId}/{slideId}/quick-action.
 */
export default function QuickActionsBar({ taskId, slideId, onSlide }) {
  const [busy, setBusy] = useState(null);
  const [tone, setTone] = useState(false);
  const disabled = !slideId;

  async function run(action, extra = {}) {
    if (!slideId) return;
    setBusy(action);
    try {
      const res = await slidesApi.quickAction(taskId, slideId, {
        action,
        ...extra,
      });
      if (res?.slide) onSlide?.(res.slide);
    } catch (err) {
      console.error("quick-action", err);
      alert(err?.response?.data?.detail || "Quick action failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card flex flex-wrap items-center gap-1.5 !p-2">
      {ACTIONS.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => run(id)}
          disabled={disabled || busy}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-nexus-muted hover:text-nexus-text hover:bg-nexus-card transition disabled:opacity-40"
        >
          {busy === id ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Icon className="h-3.5 w-3.5" />
          )}
          {label}
        </button>
      ))}
      <div className="relative">
        <button
          onClick={() => setTone((v) => !v)}
          disabled={disabled}
          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-nexus-muted hover:text-nexus-text hover:bg-nexus-card transition disabled:opacity-40"
        >
          <MessageSquare className="h-3.5 w-3.5" /> Tone…
        </button>
        {tone && (
          <div className="absolute top-full mt-1 right-0 z-20 card !p-1 min-w-[140px]">
            {TONES.map((t) => (
              <button
                key={t}
                onClick={() => {
                  setTone(false);
                  run("tone", { tone: t });
                }}
                className="block w-full text-left px-3 py-1.5 text-xs text-nexus-muted hover:text-nexus-text hover:bg-nexus-card rounded"
              >
                {t}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
