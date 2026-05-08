import * as React from "react";
import { useNexusClient } from "./provider.js";
import type {
  GenerateOptions,
  Slide,
  SlideDeck,
  TaskProgressEvent,
  TaskStatus,
} from "../types.js";

export interface UseNexusGenerateState {
  taskId: string | null;
  status: TaskStatus | "idle";
  progress: number;
  step: string;
  error: string | null;
  events: TaskProgressEvent[];
  slides: Slide[];
  deck: SlideDeck | null;
}

const INITIAL: UseNexusGenerateState = {
  taskId: null,
  status: "idle",
  progress: 0,
  step: "",
  error: null,
  events: [],
  slides: [],
  deck: null,
};

/**
 * One-call hook that creates a generation task, subscribes to its SSE
 * progress stream, and resolves with the final deck. Returns the live state
 * plus a `generate(options)` action and a `reset()` helper.
 *
 * @example
 * const { generate, status, slides } = useNexusGenerate();
 * generate({ topic: "AI in healthcare", slide_count: 8 });
 */
export function useNexusGenerate() {
  const client = useNexusClient();
  const [state, setState] = React.useState<UseNexusGenerateState>(INITIAL);
  const closeRef = React.useRef<null | (() => void)>(null);

  const reset = React.useCallback(() => {
    closeRef.current?.();
    closeRef.current = null;
    setState(INITIAL);
  }, []);

  const generate = React.useCallback(
    async (opts: GenerateOptions): Promise<string> => {
      reset();
      setState((s) => ({ ...s, status: "pending", step: "queued" }));
      try {
        const { task_id } = await client.generate(opts);
        setState((s) => ({ ...s, taskId: task_id, status: "running" }));

        const tryStream = () => {
          try {
            closeRef.current = client.streamStatus(task_id, {
              onEvent: (ev) => {
                setState((s) => ({
                  ...s,
                  events: [...s.events, ev],
                  status: ev.status ?? s.status,
                  step: ev.step ?? s.step,
                  progress:
                    typeof ev.pct === "number" ? ev.pct : s.progress,
                  slides: Array.isArray(ev.slides) ? ev.slides : s.slides,
                }));
              },
              onError: (err) => {
                setState((s) => ({
                  ...s,
                  error:
                    err instanceof Error
                      ? err.message
                      : "Stream interrupted; polling instead.",
                }));
                // Fall back to polling.
                pollOnce();
              },
              onDone: async () => {
                try {
                  const deck = await client.getDeck(task_id);
                  setState((s) => ({
                    ...s,
                    status: "done",
                    deck,
                    slides: deck.slides ?? s.slides,
                  }));
                } catch (err) {
                  setState((s) => ({
                    ...s,
                    error:
                      err instanceof Error ? err.message : String(err),
                  }));
                }
              },
            });
          } catch {
            pollOnce();
          }
        };

        const pollOnce = async () => {
          try {
            const deck = await client.poll(task_id, {
              onTick: (d) =>
                setState((s) => ({
                  ...s,
                  slides: (d.slides as Slide[]) ?? s.slides,
                })),
            });
            setState((s) => ({
              ...s,
              status: "done",
              deck,
              slides: deck.slides ?? s.slides,
            }));
          } catch (err) {
            setState((s) => ({
              ...s,
              status: "failed",
              error: err instanceof Error ? err.message : String(err),
            }));
          }
        };

        tryStream();
        return task_id;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setState((s) => ({ ...s, status: "failed", error: msg }));
        throw err;
      }
    },
    [client, reset],
  );

  React.useEffect(() => () => closeRef.current?.(), []);

  return { ...state, generate, reset };
}

/**
 * Read-only deck loader. Fetches `/slides/:taskId` once and returns the deck.
 */
export function useNexusDeck(taskId: string | null | undefined) {
  const client = useNexusClient();
  const [deck, setDeck] = React.useState<SlideDeck | null>(null);
  const [loading, setLoading] = React.useState<boolean>(!!taskId);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!taskId) {
      setDeck(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    client
      .getDeck(taskId)
      .then((d) => {
        if (!cancelled) setDeck(d);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client, taskId]);

  return { deck, loading, error };
}
