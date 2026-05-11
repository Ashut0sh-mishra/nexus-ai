import { useCallback, useEffect, useRef, useState } from "react";
import { api, statusStreamUrl } from "../utils/api.js";

export function useGenerate() {
  const [loading, setLoading] = useState(false);

  const generate = useCallback(async (payload) => {
    setLoading(true);
    try {
      const { data } = await api.post("/generate", payload);
      return data;
    } finally {
      setLoading(false);
    }
  }, []);

  return { generate, loading };
}

/**
 * Subscribe to the SSE progress stream for a given task. Returns parsed events,
 * the latest status, and any terminal error message.
 *
 * Phase 6Q: ``restartKey`` is a numeric nonce; bumping it tears down the
 * current EventSource and opens a fresh one even when ``taskId`` is
 * unchanged. The lifecycle ``Retry`` / ``Resume`` buttons use this to
 * resubscribe after the backend re-enqueues the same task id.
 */
export function useTaskStream(taskId, restartKey = 0) {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState("pending");
  const [error, setError] = useState(null);
  const [liveSlides, setLiveSlides] = useState([]);
  const sourceRef = useRef(null);

  useEffect(() => {
    if (!taskId) return undefined;
    setEvents([]);
    setStatus("pending");
    setError(null);
    setLiveSlides([]);

    const es = new EventSource(statusStreamUrl(taskId));
    sourceRef.current = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setEvents((prev) => [...prev, data]);
        if (data.status) setStatus(data.status);
        if (data.error) setError(data.error);

        // Live per-slide stream. Phase 6R uses the canonical event name
        // ``slide_ready``; legacy ``slide`` is kept for back-compat.
        if (
          (data.event === "slide_ready" || data.event === "slide") &&
          data.slide &&
          typeof data.slide_index === "number"
        ) {
          setLiveSlides((prev) => {
            const next = [...prev];
            // Grow the array if a later slide arrives first.
            while (next.length <= data.slide_index) next.push(null);
            next[data.slide_index] = data.slide;
            return next;
          });
        }

        // Phase 6Q: cancelled is terminal alongside done/failed.
        // Phase 6R: terminal events also expose canonical event names.
        if (
          data.status === "done" ||
          data.status === "failed" ||
          data.status === "cancelled" ||
          data.event === "run_succeeded" ||
          data.event === "run_failed" ||
          data.event === "run_cancelled"
        ) {
          es.close();
        }
      } catch {
        /* ignore malformed frames */
      }
    };

    es.onerror = () => {
      // Browser will retry; if the server closed cleanly we end up here too.
      // Only flag as error if we never reached a terminal state.
      setStatus((s) => {
        if (s === "done" || s === "failed" || s === "cancelled") return s;
        setError((prev) => prev || "Connection lost. Retrying…");
        return s;
      });
    };

    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, [taskId, restartKey]);

  return { events, status, error, liveSlides };
}
