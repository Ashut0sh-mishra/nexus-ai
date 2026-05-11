import axios from "axios";

const baseURL = import.meta.env.VITE_BACKEND_URL || "/api";
const normalizedBase =
  baseURL.endsWith("/api") || baseURL.endsWith("/api/")
    ? baseURL.replace(/\/$/, "")
    : `${baseURL.replace(/\/$/, "")}/api`;

export const api = axios.create({
  baseURL: normalizedBase,
  timeout: 60_000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("nexus_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
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
