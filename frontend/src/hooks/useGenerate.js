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
 */
export function useTaskStream(taskId) {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState("pending");
  const [error, setError] = useState(null);
  const [liveSlides, setLiveSlides] = useState([]);
  const [resolvedTheme, setResolvedTheme] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const sourceRef = useRef(null);

  useEffect(() => {
    if (!taskId) return undefined;
    setEvents([]);
    setStatus("pending");
    setError(null);
    setLiveSlides([]);
    setResolvedTheme(null);
    setAnalysis(null);

    const es = new EventSource(statusStreamUrl(taskId));
    sourceRef.current = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setEvents((prev) => [...prev, data]);
        if (data.status) setStatus(data.status);
        if (data.error) setError(data.error);

        // Live per-slide stream (browser-use-style step callback adapted to SSE).
        if (data.event === "slide" && data.slide && typeof data.slide_index === "number") {
          setLiveSlides((prev) => {
            const next = [...prev];
            // Grow the array if a later slide arrives first.
            while (next.length <= data.slide_index) next.push(null);
            next[data.slide_index] = data.slide;
            return next;
          });
        }

        // Auto-theme resolution event from the agent loop.
        if (data.event === "theme" && data.theme) {
          setResolvedTheme(data.theme);
        }

        // AI topic-analysis event (topic_type, tone, slide_count, etc.)
        if (data.event === "analysis" && data.analysis) {
          setAnalysis(data.analysis);
        }

        if (data.status === "done" || data.status === "failed") {
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
        if (s === "done" || s === "failed") return s;
        setError((prev) => prev || "Connection lost. Retrying…");
        return s;
      });
    };

    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, [taskId]);

  return { events, status, error, liveSlides, resolvedTheme, analysis };
}
