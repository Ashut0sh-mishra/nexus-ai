import type {
  GenerateOptions,
  GenerateResponse,
  NexusClientOptions,
  Slide,
  SlideDeck,
  TaskProgressEvent,
  UploadResponse,
} from "./types.js";

const DEFAULT_BASE = "/api";

function joinUrl(base: string, path: string): string {
  const b = base.replace(/\/+$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${b}${p}`;
}

export class NexusError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "NexusError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Headless client for the NEXUS backend. Framework-agnostic — usable in
 * any JS environment with `fetch` (browsers, Node 18+, Deno, edge runtimes).
 */
export class NexusClient {
  private baseUrl: string;
  private token?: string;
  private _fetch: typeof fetch;
  private timeoutMs: number;

  constructor(options: NexusClientOptions = {}) {
    let base = options.baseUrl ?? DEFAULT_BASE;
    // Allow callers to pass an origin like "https://api.foo.com" — auto-append /api.
    if (!/\/api\/?$/.test(base) && !base.endsWith("/api")) {
      base = `${base.replace(/\/+$/, "")}/api`;
    }
    this.baseUrl = base.replace(/\/+$/, "");
    this.token = options.token;
    this._fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.timeoutMs = options.timeoutMs ?? 60_000;
  }

  setToken(token: string | undefined) {
    this.token = token;
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  private headers(extra?: Record<string, string>): Record<string, string> {
    const h: Record<string, string> = { Accept: "application/json", ...extra };
    if (this.token) h.Authorization = `Bearer ${this.token}`;
    return h;
  }

  private async request<T>(
    path: string,
    init: RequestInit = {},
    timeoutMs?: number,
  ): Promise<T> {
    const url = joinUrl(this.baseUrl, path);
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs ?? this.timeoutMs);
    try {
      const res = await this._fetch(url, {
        ...init,
        signal: init.signal ?? ctrl.signal,
        headers: { ...this.headers(), ...(init.headers as Record<string, string> | undefined) },
      });
      const ct = res.headers.get("content-type") || "";
      const body = ct.includes("application/json") ? await res.json() : await res.text();
      if (!res.ok) {
        const detail =
          (body && typeof body === "object" && "detail" in body && (body as any).detail) ||
          body;
        throw new NexusError(
          typeof detail === "string" ? detail : `Request failed: ${res.status}`,
          res.status,
          detail,
        );
      }
      return body as T;
    } finally {
      clearTimeout(t);
    }
  }

  // ── Health ────────────────────────────────────────────────────────────────
  health() {
    return this.request<{ status: string; provider: string; model: string }>("/health");
  }

  // ── Generate ──────────────────────────────────────────────────────────────
  generate(opts: GenerateOptions): Promise<GenerateResponse> {
    return this.request<GenerateResponse>("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    });
  }

  // ── Slides ────────────────────────────────────────────────────────────────
  getDeck(taskId: string): Promise<SlideDeck> {
    return this.request<SlideDeck>(`/slides/${encodeURIComponent(taskId)}`);
  }

  getSlide(taskId: string, slideId: string): Promise<Slide> {
    return this.request<Slide>(
      `/slides/${encodeURIComponent(taskId)}/${encodeURIComponent(slideId)}`,
    );
  }

  updateSlide(
    taskId: string,
    slideId: string,
    patch: Partial<Slide>,
  ): Promise<Slide> {
    return this.request<Slide>(
      `/slides/${encodeURIComponent(taskId)}/${encodeURIComponent(slideId)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      },
    );
  }

  deleteSlide(taskId: string, slideId: string): Promise<SlideDeck> {
    return this.request<SlideDeck>(
      `/slides/${encodeURIComponent(taskId)}/${encodeURIComponent(slideId)}`,
      { method: "DELETE" },
    );
  }

  reorderSlides(taskId: string, slideIds: string[]): Promise<SlideDeck> {
    return this.request<SlideDeck>(
      `/slides/${encodeURIComponent(taskId)}/reorder`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slide_ids: slideIds }),
      },
    );
  }

  regenerateSlide(
    taskId: string,
    slideId: string,
    instruction = "",
    keepLayout = true,
  ): Promise<{ slide: Slide; tokens?: number; cost_usd?: number }> {
    return this.request(
      `/slides/${encodeURIComponent(taskId)}/${encodeURIComponent(slideId)}/regenerate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction, keep_layout: keepLayout }),
      },
    );
  }

  // ── Upload ────────────────────────────────────────────────────────────────
  async upload(file: Blob | File, filename?: string): Promise<UploadResponse> {
    const fd = new FormData();
    fd.append(
      "file",
      file,
      filename ?? (file instanceof File ? file.name : "upload.bin"),
    );
    const url = joinUrl(this.baseUrl, "/upload");
    const res = await this._fetch(url, {
      method: "POST",
      body: fd,
      headers: this.headers(), // no Content-Type — let the browser set the multipart boundary.
    });
    const ct = res.headers.get("content-type") || "";
    const body = ct.includes("application/json") ? await res.json() : await res.text();
    if (!res.ok) {
      const detail =
        (body && typeof body === "object" && "detail" in body && (body as any).detail) ||
        body;
      throw new NexusError(
        typeof detail === "string" ? detail : `Upload failed: ${res.status}`,
        res.status,
        detail,
      );
    }
    return body as UploadResponse;
  }

  // ── Export ────────────────────────────────────────────────────────────────
  /**
   * Trigger an export and return the download URL. Backend supports `pptx`
   * and `pdf` today; `html` and `json` are accepted for forward-compat and
   * fall back to a `pdf` request if the server rejects them.
   */
  async export(
    taskId: string,
    format: "pptx" | "pdf" | "html" | "json" = "pptx",
    theme?: string,
  ): Promise<{ download_url: string; format: string; file_size: number }> {
    const path = format === "pdf" ? "/export/pdf" : "/export/pptx";
    return this.request(path, {
      method: "POST",
      body: JSON.stringify({ task_id: taskId, theme, format }),
    });
  }

  // ── Status streaming (SSE) ────────────────────────────────────────────────
  /**
   * Subscribe to the task's SSE progress stream. Returns a function that
   * closes the connection.
   */
  streamStatus(
    taskId: string,
    handlers: {
      onEvent?: (ev: TaskProgressEvent) => void;
      onError?: (err: unknown) => void;
      onDone?: (final: TaskProgressEvent | null) => void;
    } = {},
  ): () => void {
    if (typeof EventSource === "undefined") {
      throw new Error(
        "EventSource is not available in this runtime. Use poll() instead.",
      );
    }
    const url = joinUrl(this.baseUrl, `/status/${encodeURIComponent(taskId)}`);
    const es = new EventSource(url, { withCredentials: false });
    let last: TaskProgressEvent | null = null;
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as TaskProgressEvent;
        last = data;
        handlers.onEvent?.(data);
        if (data.status === "done" || data.status === "failed") {
          es.close();
          handlers.onDone?.(data);
        }
      } catch (err) {
        handlers.onError?.(err);
      }
    };
    es.onerror = (err) => {
      handlers.onError?.(err);
      es.close();
      handlers.onDone?.(last);
    };
    return () => es.close();
  }

  /**
   * Poll the deck endpoint until the status reaches a terminal state.
   * Useful in environments without EventSource (e.g. Node).
   */
  async poll(
    taskId: string,
    {
      intervalMs = 2_000,
      timeoutMs = 5 * 60_000,
      onTick,
    }: {
      intervalMs?: number;
      timeoutMs?: number;
      onTick?: (deck: Partial<SlideDeck>) => void;
    } = {},
  ): Promise<SlideDeck> {
    const started = Date.now();
    while (true) {
      try {
        const deck = await this.getDeck(taskId);
        onTick?.(deck);
        if ((deck as any).status === "failed") {
          throw new NexusError("Generation failed", 500, deck);
        }
        if (Array.isArray(deck.slides) && deck.slides.length > 0) {
          return deck;
        }
      } catch (err) {
        if (err instanceof NexusError && err.status !== 404) throw err;
      }
      if (Date.now() - started > timeoutMs) {
        throw new NexusError("Polling timed out", 504);
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  }
}

export type { GenerateOptions, GenerateResponse, Slide, SlideDeck, UploadResponse, TaskProgressEvent } from "./types.js";
