/**
 * Local persistence for in-progress deck edits in the workspace.
 *
 * Stored under localStorage key `nexus.deck.<taskId>` as JSON
 * `{ slides, theme, savedAt }`. We deliberately keep this client-side only;
 * the backend `/api/generate` and export pipeline are unchanged.
 */

const KEY_PREFIX = "nexus.deck.";

export function loadDeck(taskId) {
  if (!taskId || typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY_PREFIX + taskId);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.slides)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveDeck(taskId, { slides, theme }) {
  if (!taskId || typeof window === "undefined") return false;
  try {
    const payload = JSON.stringify({
      slides,
      theme,
      savedAt: new Date().toISOString(),
    });
    window.localStorage.setItem(KEY_PREFIX + taskId, payload);
    return true;
  } catch {
    return false;
  }
}

export function clearDeck(taskId) {
  if (!taskId || typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(KEY_PREFIX + taskId);
  } catch {
    /* ignore */
  }
}
