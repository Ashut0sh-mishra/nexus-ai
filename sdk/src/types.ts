/**
 * Slide / deck data model — mirrors what the NEXUS backend produces.
 * Keep these intentionally permissive: the renderer should degrade gracefully
 * when fields are missing.
 */

export type SlideLayout =
  | "title"
  | "section"
  | "bullets"
  | "two-col"
  | "comparison"
  | "kpi"
  | "quote"
  | "stats"
  | "chart"
  | "table"
  | "timeline"
  | "image-focus"
  | "closing";

export interface SlideColumn {
  heading?: string;
  body?: string;
}

export interface SlideStat {
  value: string | number;
  label?: string;
  trend?: string;
}

export interface SlideKpi {
  value: string | number;
  label?: string;
  sublabel?: string;
  delta?: string;
  direction?: "up" | "down" | "" | string;
}

export interface SlideComparisonItem {
  heading?: string;
  subtitle?: string;
  points?: string[];
  body?: string;
}

export interface SlideTimelineEvent {
  year?: string | number;
  title?: string;
  desc?: string;
}

export interface ChartData {
  labels?: string[];
  values?: number[];
  unit?: string;
  source?: string;
}

export interface ImageEnvelope {
  url?: string;
  alt?: string;
  source?: string;
  credit?: string;
  placement?: string;
  width?: number;
  height?: number;
  prompt?: string;
}

export interface Slide {
  id?: string;
  slide_id?: string;
  slide_number?: number;
  layout: SlideLayout | string;
  title?: string;
  subtitle?: string;
  eyebrow?: string;
  tagline?: string;
  section_number?: string;

  // Layout-specific
  bullets?: string[];
  columns?: SlideColumn[];
  items?: SlideComparisonItem[];
  kpis?: SlideKpi[];
  quote?: string;
  attribution?: string;
  stats?: SlideStat[];
  chart_type?: "bar" | "line" | "doughnut" | string;
  chart_data?: ChartData;
  headers?: string[];
  rows?: string[][];
  events?: SlideTimelineEvent[];
  caption?: string;
  message?: string;
  cta?: string;

  // Media
  image_url?: string;
  image_prompt?: string;
  image?: ImageEnvelope;

  speaker_notes?: string;
}

export interface SlideDeck {
  task_id: string;
  topic?: string;
  theme?: string;
  slide_count?: number;
  slides: Slide[];
}

export interface GenerateOptions {
  topic: string;
  slide_count?: number;
  theme?: string;
  search_web?: boolean;
  user_id?: string;
  file_ids?: string[];
  audience?: string;
  tone?: string;
  industry?: string;
}

export interface GenerateResponse {
  task_id: string;
  status: string;
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  extracted_preview: string;
  has_structured_data: boolean;
  error?: string | null;
}

export type TaskStatus =
  | "pending"
  | "running"
  | "done"
  | "failed"
  | string;

export interface TaskProgressEvent {
  step?: string;
  pct?: number;
  message?: string;
  status?: TaskStatus;
  slides?: Slide[];
  // Anything else the backend streams.
  [key: string]: any;
}

export interface NexusClientOptions {
  /** Base URL to the NEXUS backend, e.g. "https://api.example.com" or "/api". */
  baseUrl?: string;
  /** Bearer token for authenticated calls. */
  token?: string;
  /** Custom fetch (defaults to global fetch). */
  fetch?: typeof fetch;
  /** Default request timeout in ms (default: 60_000). */
  timeoutMs?: number;
}
