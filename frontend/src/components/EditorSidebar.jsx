import { useState } from "react";
import { GripVertical, Trash2 } from "lucide-react";

/**
 * Left rail: slide thumbnails. Reorder via native HTML5 drag-and-drop.
 * Calls `onReorder(orderedIds)` once after a successful drop.
 */
export default function EditorSidebar({
  slides = [],
  activeIdx = 0,
  onSelect,
  onDelete,
  onReorder,
}) {
  const [dragIdx, setDragIdx] = useState(null);
  const [overIdx, setOverIdx] = useState(null);

  function onDragStart(e, i) {
    setDragIdx(i);
    e.dataTransfer.effectAllowed = "move";
    // Some browsers require setData to fire dragend reliably.
    try {
      e.dataTransfer.setData("text/plain", String(i));
    } catch {
      /* ignore */
    }
  }

  function onDragOver(e, i) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (overIdx !== i) setOverIdx(i);
  }

  function onDrop(e, target) {
    e.preventDefault();
    const src = dragIdx;
    setDragIdx(null);
    setOverIdx(null);
    if (src == null || src === target) return;
    const reordered = slides.slice();
    const [moved] = reordered.splice(src, 1);
    reordered.splice(target, 0, moved);
    const orderedIds = reordered.map((s) => s.slide_id || s.id).filter(Boolean);
    if (orderedIds.length === slides.length) {
      onReorder?.(orderedIds);
    }
  }

  return (
    <aside className="card max-h-[calc(100vh-9rem)] overflow-y-auto !p-2">
      <div className="px-2 py-1.5 text-[10px] uppercase tracking-widest text-nexus-dim">
        Slides ({slides.length})
      </div>
      <ul className="space-y-1">
        {slides.map((s, i) => {
          const isActive = i === activeIdx;
          const isOver = i === overIdx && dragIdx !== null && dragIdx !== i;
          return (
            <li
              key={s.slide_id || s.id || i}
              draggable
              onDragStart={(e) => onDragStart(e, i)}
              onDragOver={(e) => onDragOver(e, i)}
              onDrop={(e) => onDrop(e, i)}
              onDragEnd={() => {
                setDragIdx(null);
                setOverIdx(null);
              }}
              className={`group flex cursor-pointer items-start gap-2 rounded-lg border px-2 py-2 transition ${
                isActive
                  ? "border-accent-purple/60 bg-accent-purple/10"
                  : "border-nexus-border bg-nexus-card hover:border-nexus-borderHi"
              } ${isOver ? "ring-2 ring-accent-purple/50" : ""}`}
              onClick={() => onSelect?.(i)}
            >
              <GripVertical className="mt-0.5 h-3.5 w-3.5 shrink-0 text-nexus-dim opacity-50 group-hover:opacity-100" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-nexus-dim">
                  <span className="font-mono tabular-nums">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>·</span>
                  <span>{s.layout || "title"}</span>
                </div>
                <div className="mt-0.5 truncate text-xs text-nexus-text">
                  {s.title || <span className="text-nexus-muted">Untitled</span>}
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete?.(i);
                }}
                className="opacity-0 transition group-hover:opacity-100"
                aria-label="Delete slide"
              >
                <Trash2 className="h-3.5 w-3.5 text-nexus-muted hover:text-red-400" />
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
