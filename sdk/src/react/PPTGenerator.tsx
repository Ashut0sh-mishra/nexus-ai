import * as React from "react";
import { NexusProvider } from "./provider.js";
import { useNexusGenerate } from "./hooks.js";
import { NexusDeck } from "./NexusDeck.js";
import type { GenerateOptions, Slide } from "../types.js";

export interface PPTGeneratorProps {
  /** Backend base URL, e.g. "https://api.example.com" or "/api". */
  baseUrl?: string;
  /** API key (sent as Authorization: Bearer …). */
  apiKey?: string;
  /** Optional workspace scoping. */
  workspaceId?: string;
  /** Whether to enable AI image generation server-side. */
  enableAIImages?: boolean;
  /** Initial topic; if provided, generation starts immediately. */
  topic?: string;
  /** Default generation options applied to every request. */
  defaults?: Partial<GenerateOptions>;
  /** CSS class for the outer wrapper. */
  className?: string;
  /** Render-prop access to the underlying deck state. */
  children?: (api: PPTGeneratorRenderApi) => React.ReactNode;
  /** Called whenever a deck finishes generation. */
  onComplete?: (slides: Slide[]) => void;
}

export interface PPTGeneratorRenderApi {
  generate: (opts: GenerateOptions) => Promise<string>;
  status: string;
  progress: number;
  step: string;
  slides: Slide[];
  error: string | null;
  reset: () => void;
}

/**
 * Drop-in “PPT generator in a box” — wraps {@link NexusProvider},
 * {@link useNexusGenerate} and {@link NexusDeck} into a single component.
 *
 * @example
 * <PPTGenerator
 *   apiKey={process.env.NEXUS_KEY}
 *   workspaceId="acme"
 *   enableAIImages
 *   topic="The future of energy"
 * />
 */
export function PPTGenerator(props: PPTGeneratorProps) {
  return (
    <NexusProvider baseUrl={props.baseUrl} token={props.apiKey}>
      <PPTGeneratorInner {...props} />
    </NexusProvider>
  );
}

function PPTGeneratorInner({
  workspaceId,
  enableAIImages,
  topic,
  defaults,
  className,
  children,
  onComplete,
}: PPTGeneratorProps) {
  const { generate, status, progress, step, slides, error, reset } =
    useNexusGenerate();
  const [input, setInput] = React.useState(topic ?? "");
  const startedRef = React.useRef(false);

  const launch = React.useCallback(
    async (overrides?: Partial<GenerateOptions>) => {
      const opts: GenerateOptions = {
        topic: input.trim(),
        ...defaults,
        ...overrides,
      };
      // Pass workspace + AI-images as extras (server reads them when present).
      if (workspaceId) (opts as any).workspace_id = workspaceId;
      if (enableAIImages !== undefined)
        (opts as any).enable_ai_images = enableAIImages;
      if (!opts.topic) return "";
      return generate(opts);
    },
    [generate, input, defaults, workspaceId, enableAIImages],
  );

  // Fire once if a topic prop was provided up-front.
  React.useEffect(() => {
    if (topic && !startedRef.current) {
      startedRef.current = true;
      launch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topic]);

  // Notify on completion.
  React.useEffect(() => {
    if (status === "done" && slides.length > 0) {
      onComplete?.(slides);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  if (children) {
    return (
      <div className={className}>
        {children({
          generate: launch,
          status,
          progress,
          step,
          slides,
          error,
          reset,
        })}
      </div>
    );
  }

  return (
    <div className={className} data-nexus-pptgen>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          launch();
        }}
        style={{
          display: "flex",
          gap: 8,
          marginBottom: 16,
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="What should the deck be about?"
          style={{
            flex: 1,
            padding: "10px 14px",
            borderRadius: 12,
            border: "1px solid #2a2a2a",
            background: "#111",
            color: "#fff",
            fontSize: 14,
          }}
        />
        <button
          type="submit"
          disabled={status === "running" || !input.trim()}
          style={{
            padding: "10px 18px",
            borderRadius: 12,
            border: "none",
            background: "#fff",
            color: "#000",
            fontSize: 14,
            fontWeight: 500,
            cursor: status === "running" ? "not-allowed" : "pointer",
            opacity: status === "running" ? 0.6 : 1,
          }}
        >
          {status === "running" ? `${Math.round(progress)}%` : "Generate"}
        </button>
      </form>

      {error && (
        <div
          style={{
            padding: 12,
            borderRadius: 8,
            background: "rgba(255,80,80,0.1)",
            color: "#ff8080",
            fontSize: 13,
            marginBottom: 12,
          }}
        >
          {error}
        </div>
      )}

      {status === "running" && (
        <div
          style={{
            fontSize: 12,
            color: "#888",
            marginBottom: 12,
          }}
        >
          {step || "Working…"} · {Math.round(progress)}%
        </div>
      )}

      {slides.length > 0 && <NexusDeck slides={slides} />}
    </div>
  );
}
