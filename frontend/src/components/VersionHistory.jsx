import { useEffect, useState } from "react";
import { History, RotateCcw, Camera, Loader2, X } from "lucide-react";
import { versionsApi } from "../utils/api.js";

export default function VersionHistory({ taskId, onRestored, onClose }) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await versionsApi.list(taskId);
      setVersions(data || []);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    refresh();
  }, [taskId]);

  const snapshot = async () => {
    setBusy("snap");
    try {
      await versionsApi.snapshot(taskId, { label: "manual" });
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  const restore = async (v) => {
    if (!window.confirm(`Restore version ${v}? Current state will be saved first.`))
      return;
    setBusy(`r-${v}`);
    try {
      await versionsApi.restore(taskId, v);
      onRestored?.();
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-80 bg-nexus-surface border-l border-nexus-border shadow-2xl flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-nexus-border">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <History className="h-4 w-4" /> Version history
        </div>
        <button onClick={onClose} className="text-nexus-muted hover:text-nexus-text">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-3 border-b border-nexus-border">
        <button
          onClick={snapshot}
          disabled={!!busy}
          className="btn-ghost w-full !py-1.5 !text-xs inline-flex items-center justify-center gap-1.5"
        >
          {busy === "snap" ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Camera className="h-3 w-3" />
          )}
          Save snapshot
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {loading ? (
          <p className="text-xs text-nexus-muted p-2">Loading…</p>
        ) : versions.length === 0 ? (
          <p className="text-xs text-nexus-muted p-2">No versions yet.</p>
        ) : (
          versions.map((v) => (
            <div
              key={v.version}
              className="rounded-lg p-2.5 hover:bg-nexus-card group"
            >
              <div className="flex items-center justify-between">
                <div className="text-xs font-medium">v{v.version}</div>
                <button
                  onClick={() => restore(v.version)}
                  disabled={!!busy}
                  className="opacity-0 group-hover:opacity-100 text-xs text-nexus-accent inline-flex items-center gap-1 transition"
                >
                  {busy === `r-${v.version}` ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <RotateCcw className="h-3 w-3" />
                  )}
                  Restore
                </button>
              </div>
              <p className="text-[10px] text-nexus-muted mt-0.5">
                {v.label || "—"} · {new Date(v.created_at).toLocaleString()}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
