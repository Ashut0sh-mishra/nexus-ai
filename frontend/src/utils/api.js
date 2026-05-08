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

// ─── PRD §10/§16/§17 helpers ─────────────────────────────────────────────

export const brandKitsApi = {
  list: () => api.get("/brand-kits").then((r) => r.data),
  create: (payload) => api.post("/brand-kits", payload).then((r) => r.data),
  get: (id) => api.get(`/brand-kits/${id}`).then((r) => r.data),
  update: (id, payload) => api.put(`/brand-kits/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/brand-kits/${id}`).then((r) => r.data),
};

export const assetsApi = {
  list: (params = {}) => api.get("/assets", { params }).then((r) => r.data),
  upload: (file, extra = {}) => {
    const fd = new FormData();
    fd.append("file", file);
    Object.entries(extra).forEach(([k, v]) => v != null && fd.append(k, v));
    return api
      .post("/assets", fd, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },
  update: (id, payload) => api.put(`/assets/${id}`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/assets/${id}`).then((r) => r.data),
};

export const apiKeysApi = {
  list: () => api.get("/api-keys").then((r) => r.data),
  create: (payload) => api.post("/api-keys", payload).then((r) => r.data),
  rotate: (id) => api.post(`/api-keys/${id}/rotate`).then((r) => r.data),
  revoke: (id) => api.delete(`/api-keys/${id}`).then((r) => r.data),
};

export const webhooksApi = {
  list: () => api.get("/webhooks").then((r) => r.data),
  create: (payload) => api.post("/webhooks", payload).then((r) => r.data),
  test: (id) => api.post(`/webhooks/${id}/test`).then((r) => r.data),
  remove: (id) => api.delete(`/webhooks/${id}`).then((r) => r.data),
};

export const versionsApi = {
  list: (taskId) => api.get(`/decks/${taskId}/versions`).then((r) => r.data),
  snapshot: (taskId, payload = {}) =>
    api.post(`/decks/${taskId}/versions`, payload).then((r) => r.data),
  get: (taskId, version) =>
    api.get(`/decks/${taskId}/versions/${version}`).then((r) => r.data),
  restore: (taskId, version) =>
    api.post(`/decks/${taskId}/versions/${version}/restore`).then((r) => r.data),
};

export const slidesApi = {
  duplicate: (taskId, slideId) =>
    api.post(`/slides/${taskId}/${slideId}/duplicate`).then((r) => r.data),
  replaceImage: (taskId, slideId, payload) =>
    api.post(`/slides/${taskId}/${slideId}/image`, payload).then((r) => r.data),
  quickAction: (taskId, slideId, payload) =>
    api.post(`/slides/${taskId}/${slideId}/quick-action`, payload).then((r) => r.data),
  bulkUpdate: (taskId, slides) =>
    api.post(`/slides/${taskId}/bulk`, { slides }).then((r) => r.data),
};

export const workspacesApi = {
  list: () => api.get("/workspaces").then((r) => r.data),
  create: (payload) => api.post("/workspaces", payload).then((r) => r.data),
  get: (id) => api.get(`/workspaces/${id}`).then((r) => r.data),
  remove: (id) => api.delete(`/workspaces/${id}`).then((r) => r.data),
  members: (id) => api.get(`/workspaces/${id}/members`).then((r) => r.data),
  addMember: (id, payload) =>
    api.post(`/workspaces/${id}/members`, payload).then((r) => r.data),
};

export const auditLogsApi = {
  list: (params = {}) => api.get("/audit-logs", { params }).then((r) => r.data),
};

