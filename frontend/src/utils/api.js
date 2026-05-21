import axios from "axios";

const baseURL = import.meta.env.VITE_BACKEND_URL || "/api";
const normalizedBase =
  baseURL.endsWith("/api") || baseURL.endsWith("/api/")
    ? baseURL.replace(/\/$/, "")
    : `${baseURL.replace(/\/$/, "")}/api`;

// Phase 6AL — shared key baked at build time. The deployed backend's
// SecurityMiddleware rejects any request that does not carry this exact
// value in the X-Nexus-Key header. Empty in local dev = no header sent
// (backend's middleware is a no-op when NEXUS_API_KEY is empty there).
const NEXUS_KEY = import.meta.env.VITE_NEXUS_KEY || "";

export const api = axios.create({
  baseURL: normalizedBase,
  timeout: 60_000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("nexus_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (NEXUS_KEY) config.headers["X-Nexus-Key"] = NEXUS_KEY;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("nexus_token");
    }
    return Promise.reject(err);
  }
);

/** Returns the absolute URL for an SSE stream of task progress. */
export function statusStreamUrl(taskId) {
  return `${normalizedBase}/status/${encodeURIComponent(taskId)}`;
}

/**
 * Resolve a backend-relative path (e.g. an export `download_url` like
 * "/api/files/xyz.pptx") to an ABSOLUTE URL on the backend origin.
 *
 * Without this, a relative URL resolves against the *frontend* origin
 * (the Vercel app), whose SPA rewrite returns index.html for unknown
 * paths — so "Download PPTX" downloaded index.html instead of the file.
 * Already-absolute (http/https) URLs pass through unchanged.
 */
export function backendUrl(pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl;
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  // normalizedBase ends with "/api"; the backend origin is it minus "/api".
  const origin = normalizedBase.replace(/\/api$/, "");
  return `${origin}${pathOrUrl.startsWith("/") ? "" : "/"}${pathOrUrl}`;
}
