import { useCallback, useRef, useState } from "react";

/**
 * Phase 6P — minimal undo/redo history hook.
 *
 * Local-only history of slide-array snapshots (or any JSON-serializable
 * state). Operates by reference comparison: callers should always pass a
 * **new** array/object reference when state changes. The committed value
 * is held in React state so the component re-renders.
 *
 *   const { value, set, undo, redo, reset, canUndo, canRedo } =
 *       useUndoRedo(initialSlides, { limit: 50 });
 *
 * `set(next)` pushes a new entry on top of the history. Calling `undo()`
 * moves one step back; `redo()` moves forward (if no `set` happened in
 * between). `reset(next)` replaces the entire history with a single
 * entry — useful after a Save (server is now source of truth) or a
 * Reset-to-server.
 */
export function useUndoRedo(initial, { limit = 50 } = {}) {
  const [value, setValue] = useState(initial);
  const past = useRef([]);
  const future = useRef([]);

  const set = useCallback(
    (next) => {
      setValue((current) => {
        if (next === current) return current;
        past.current.push(current);
        if (past.current.length > limit) past.current.shift();
        future.current = [];
        return next;
      });
    },
    [limit],
  );

  const undo = useCallback(() => {
    setValue((current) => {
      if (past.current.length === 0) return current;
      const prev = past.current.pop();
      future.current.push(current);
      return prev;
    });
  }, []);

  const redo = useCallback(() => {
    setValue((current) => {
      if (future.current.length === 0) return current;
      const next = future.current.pop();
      past.current.push(current);
      return next;
    });
  }, []);

  const reset = useCallback((next) => {
    past.current = [];
    future.current = [];
    setValue(next);
  }, []);

  return {
    value,
    set,
    undo,
    redo,
    reset,
    canUndo: past.current.length > 0,
    canRedo: future.current.length > 0,
  };
}
