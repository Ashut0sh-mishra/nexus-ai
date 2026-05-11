import { useCallback, useState } from "react";
import { api } from "../utils/api.js";

/**
 * Phase 6Q — control hook for `/api/lifecycle/{task_id}` actions.
 *
 * Exposes ``cancel`` / ``retry`` / ``resume`` plus an ``inFlight`` flag
 * so the UI can disable buttons during the round-trip and avoid the
 * double-submit / duplicate-action problem the prompt calls out.
 *
 * The hook stays purposefully thin: it does not own status state. The
 * generation screen still subscribes to ``useTaskStream`` for live
 * progress; this hook only owns the request lifecycle for the three
 * control endpoints.
 */
export function useJobLifecycle(taskId) {
  const [inFlight, setInFlight] = useState(null); // "cancel" | "retry" | "resume" | null
  const [lastError, setLastError] = useState(null);

  const _call = useCallback(
    async (action, path) => {
      if (!taskId || inFlight) return null;
      setInFlight(action);
      setLastError(null);
      try {
        const { data } = await api.post(`/lifecycle/${taskId}/${path}`);
        return data;
      } catch (err) {
        const detail = err?.response?.data?.detail;
        const msg =
          (typeof detail === "string" && detail) ||
          (detail && typeof detail === "object" && detail.error) ||
          err?.message ||
          "Action failed";
        setLastError(msg);
        return null;
      } finally {
        setInFlight(null);
      }
    },
    [taskId, inFlight],
  );

  const cancel = useCallback(() => _call("cancel", "cancel"), [_call]);
  const retry = useCallback(() => _call("retry", "retry"), [_call]);
  const resume = useCallback(() => _call("resume", "resume"), [_call]);

  return { cancel, retry, resume, inFlight, lastError };
}
