# @nexus-ai/react-sdk

Embeddable React SDK + headless TypeScript client for the **NEXUS AI** presentation generator.

```bash
npm install @nexus-ai/react-sdk
```

## Quick start (React)

```tsx
import {
  NexusProvider,
  useNexusGenerate,
  NexusDeck,
} from "@nexus-ai/react-sdk/react";

function App() {
  return (
    <NexusProvider baseUrl="https://api.your-nexus-host.com">
      <Demo />
    </NexusProvider>
  );
}

function Demo() {
  const { generate, status, progress, slides, deck, error } = useNexusGenerate();

  return (
    <>
      <button
        onClick={() => generate({ topic: "The future of AI", slide_count: 8 })}
        disabled={status === "running" || status === "pending"}
      >
        Generate deck
      </button>

      {status === "running" && <p>Working… {Math.round(progress)}%</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}

      <NexusDeck slides={slides} />
      {deck && <a href={`/export/${deck.task_id}/pptx`}>Download .pptx</a>}
    </>
  );
}
```

## Headless client (no React)

```ts
import { NexusClient } from "@nexus-ai/react-sdk";

const nexus = new NexusClient({ baseUrl: "https://api.example.com", token: "…" });

const { task_id } = await nexus.generate({ topic: "Go-to-market plan" });
const deck = await nexus.poll(task_id);

console.log(`Got ${deck.slides.length} slides`);
const { download_url } = await nexus.export(task_id, "pptx");
console.log(download_url);
```

## Exports

- `@nexus-ai/react-sdk` — types + `NexusClient`, `NexusError`
- `@nexus-ai/react-sdk/react` — `NexusProvider`, `useNexusGenerate`, `useNexusDeck`, `NexusSlide`, `NexusDeck`
- `@nexus-ai/react-sdk/client` — same as the root entry; useful when tree-shaking React out

## API surface

`NexusClient` mirrors the backend 1:1:

| Method | Endpoint |
| --- | --- |
| `generate(opts)` | `POST /api/generate` |
| `getDeck(taskId)` | `GET /api/slides/:taskId` |
| `getSlide(taskId, slideId)` | `GET /api/slides/:taskId/:slideId` |
| `updateSlide(taskId, slideId, patch)` | `PUT /api/slides/:taskId/:slideId` |
| `deleteSlide(taskId, slideId)` | `DELETE /api/slides/:taskId/:slideId` |
| `reorderSlides(taskId, ids)` | `POST /api/slides/:taskId/reorder` |
| `regenerateSlide(taskId, slideId, instr?)` | `POST /api/slides/:taskId/:slideId/regenerate` |
| `upload(file)` | `POST /api/upload` |
| `streamStatus(taskId, handlers)` | `GET /api/status/:taskId` (SSE) |
| `poll(taskId)` | polling fallback for non-browser runtimes |
| `export(taskId, format, theme?)` | `POST /api/export/{pptx\|pdf}` — returns `{ download_url, format, file_size }` |

## License

MIT
