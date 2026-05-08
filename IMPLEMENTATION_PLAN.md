# NEXUS AI — Implementation Plan (Adapt-in-Place)

**Approach.** Keep the existing flat-package backend (`backend/api`, `backend/agent`,
`backend/services`, `backend/database`, `backend/workers`), the existing
Vite + React 18 + JSX frontend, the existing python-pptx exporter, the
existing 6-step Manus-style agent loop in [backend/agent/loop.py](backend/agent/loop.py),
and the existing multi-provider AI chain in [backend/services/ai_service.py](backend/services/ai_service.py).
All new functionality is layered on top. No model is renamed, no route is
removed, no working code is rewritten just to match the PRD's example
folder names.

**Deviations from the generic 23-step prompt list, locked in here:**

| Generic plan said | We will do |
|---|---|
| `backend/app/...` package | Use existing `backend/` flat package |
| Routes under `/api/v1/...` | Keep existing `/api/...` (no version bump). Add new routes under `/api/...` too. |
| New `Deck`, `Slide`, `UploadedFile`, `ExportJob` models | Extend existing `Task` (deck-level fields), add `Slide` row table, add `UploadedFile`. Reuse existing `Export` table (already has format/url/size/status-equivalent). |
| Next.js + TypeScript frontend | Keep Vite + React 18 + JSX |
| Node `pptxgenjs` worker | Keep python-pptx; add native chart rendering inside it |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Keep 6-provider chain (`AI_PROVIDER_CHAIN`) |

---

## Status legend
- ✅ already exists and is good enough
- 🟡 exists but needs extension
- ❌ to be built

---

## 1. Prompt-to-PPT generation
**Status: 🟡** — works end-to-end today via [backend/api/routes/generate.py](backend/api/routes/generate.py) → Celery task `run_generation_task` → [backend/agent/loop.py](backend/agent/loop.py) (analyze → search → plan → generate → critic → images → save). Returns `{task_id, status: "pending"}`, SSE progress on `/api/status/{id}`.

**Modify:**
- [backend/api/routes/generate.py](backend/api/routes/generate.py) — extend `GenerateRequest` with `file_ids: list[str] | None`, `audience`, `tone`, `industry`, plus existing `theme`/`slide_count`. Persist into the new `Task` columns from §3.
- [backend/agent/loop.py](backend/agent/loop.py) — pass uploaded-file context + audience/tone/industry into planner and slide prompts (see §6, §7).

**Create:** nothing new for this feature alone.

**Deps:** none.

---

## 2. File upload + multi-format context extraction
**Status: ❌** — no upload endpoint or parsers exist today.

**Create:**
- [backend/api/routes/upload.py](backend/api/routes/upload.py) — `POST /api/upload` (multipart), `GET /api/upload/{file_id}`, `DELETE /api/upload/{file_id}`. Saves to `backend/storage/uploads/`.
- [backend/services/context_extractor.py](backend/services/context_extractor.py) — dispatcher + per-format parsers:
  - CSV/XLSX → pandas + openpyxl (headers, row count, sample, numeric cols)
  - JSON → flatten + array detection
  - PDF → pdfplumber (text + tables)
  - DOCX → python-docx (text with heading structure)
  - PPTX → python-pptx (already installed)
  - TXT/MD → raw read
- [backend/utils/file_parser.py](backend/utils/file_parser.py) — extension/mimetype detection, size limits, sanitisation.

**Modify:**
- [backend/main.py](backend/main.py) — `app.include_router(upload.router, prefix="/api", tags=["upload"])`.
- [backend/requirements.txt](backend/requirements.txt) — add `pdfplumber`, `python-docx`, `pandas`, `openpyxl`.
- [.env.example](.env.example) — add `MAX_UPLOAD_SIZE_MB=25`, `UPLOAD_DIR=storage/uploads`.

**Deps:** `pdfplumber`, `python-docx`, `pandas`, `openpyxl`.

---

## 3. Database model extensions
**Status: 🟡** — current models in [backend/database/models.py](backend/database/models.py): `User`, `Task`, `SlideDeck`, `Export`, `ShareToken`. None will be deleted.

**Modify [backend/database/models.py](backend/database/models.py):**

`Task` (deck-level metadata) — add columns:
- `prompt: Text` (mirrors `topic` for clarity; nullable, populated alongside)
- `context_sources: JSON | None` — list of file_id refs
- `deck_plan_json: JSON | None`
- `audience: String | None`
- `tone: String | None`
- `industry: String | None`
- `theme_settings: JSON | None`
- `updated_at: DateTime` (server_default + onupdate)

`Slide` (new) — per-slide row table:
- `id: UUID PK`
- `task_id: FK → tasks.id, ON DELETE CASCADE` (we keep `Task` as the deck record; the existing `SlideDeck` JSON-blob row stays for back-compat)
- `slide_number: int`
- `slide_type: String` (title / content / chart / image / kpi / comparison / timeline / section / closing)
- `title: String`
- `subtitle: String | None`
- `content_json: JSON` (bullets, body, kpi_cards, table_data)
- `chart_data_json: JSON | None`
- `image_data_json: JSON | None`
- `speaker_notes: Text | None`
- `layout_metadata: JSON | None`
- `design_tokens: JSON | None`
- `created_at`, `updated_at`
- unique constraint on `(task_id, slide_number)`

`UploadedFile` (new):
- `id: UUID PK`
- `task_id: FK → tasks.id, nullable` (uploaded before deck creation)
- `user_id: FK → users.id, nullable`
- `filename: String`
- `file_type: String` (csv/xlsx/json/pdf/docx/pptx/txt/md)
- `file_path: String`
- `file_size: int`
- `extracted_text: Text | None`
- `extracted_data_json: JSON | None` (BI output from §5)
- `created_at`

`Export` — already exists. Add `status: String` (pending/processing/completed/failed) and `output_path: String` to support background export tracking (currently `Export` is only written after success). No deletion.

**Migration:** `cd backend && alembic revision --autogenerate -m "add_slide_uploadedfile_and_extend_task"` → `alembic upgrade head`.

---

## 4. Business intelligence extraction
**Status: ❌**

**Create:**
- [backend/services/intelligence_service.py](backend/services/intelligence_service.py) — `extract_business_intelligence(text, structured_data) -> { chart_opportunities, kpi_candidates, insights, data_tables }`. Regex for `$X / $XM / $XB`, `X%`, "grew from … to …", "Q1: …", "X vs Y", time-series detection, numeric-column stats from structured data.

**Modify:**
- [backend/api/routes/upload.py](backend/api/routes/upload.py) (from §2) — call `extract_business_intelligence` after parsing and persist to `UploadedFile.extracted_data_json`.

**Deps:** none (stdlib `re`, pandas already added in §2).

---

## 5. Enhanced deck planning
**Status: 🟡** — planner today returns `{layout, title, intent}` per slide with layouts limited to `title/bullets/two-col/quote/stats/closing` ([backend/agent/planner.py](backend/agent/planner.py)).

**Modify:**
- [backend/agent/planner.py](backend/agent/planner.py) — extend `_VALID_LAYOUTS` with `chart_focus, image_text, kpi_grid, bullet_list, timeline, comparison, section`. Extend each plan item with `purpose`, `content_brief`, `chart_type`, `chart_data_source`, `image_prompt`, `visual_elements[]`, `text_density`. Accept `file_context` (extracted text + BI from `UploadedFile`s) and `audience/tone/industry` and inject into the prompt.
- [backend/agent/prompts.py](backend/agent/prompts.py) — rewrite `PLANNER_SYSTEM_PROMPT` and `planner_user_message` to enforce consulting narrative arc (situation → complication → data → insight → recommendation → CTA), and to auto-allocate slides to detected `chart_opportunities` / `kpi_candidates` / `data_tables`.
- Persist plan to `Task.deck_plan_json` from the loop.

---

## 6. Structured slide-JSON generation + per-slide rows
**Status: 🟡** — slides today are produced into `SlideDeck.slide_data` (JSON list) by `_generate_all_at_once` / `_generate_per_slide` in [backend/agent/loop.py](backend/agent/loop.py).

**Modify:**
- [backend/agent/prompts.py](backend/agent/prompts.py) — extend the slide schema produced by the LLM so each slide has `slide_type`, `content {bullets, body_text, kpi_cards, table_data}`, `chart {type, title, data}`, `image {prompt, placement, style}`, `speaker_notes`, `layout_metadata`, `design_tokens`.
- [backend/agent/loop.py](backend/agent/loop.py) — after `_normalize_slides`, write each slide as a `Slide` row in addition to the existing `SlideDeck.slide_data` blob. Keep the blob for back-compat with the current frontend `SlideRenderer` and `SlideCarousel`.

---

## 7. Chart data processing
**Status: ❌** for app-level service; the existing `_quickchart_url` in [backend/services/export_service.py](backend/services/export_service.py) only builds an image URL.

**Create:**
- [backend/services/chart_service.py](backend/services/chart_service.py) — `process_chart_data(spec) -> {type, title, chartjs_config, pptx_config}`, `auto_detect_chart_type(data)`. Number formatting ($, %, K/M/B), theme-aware palette, axis range calculation. Supports bar, line, pie, donut, area, scatter.

**Modify:**
- [backend/agent/loop.py](backend/agent/loop.py) — for each slide with chart data, call `process_chart_data` before persisting `Slide.chart_data_json`.
- [backend/services/export_service.py](backend/services/export_service.py) — `_render_chart` reads `pptx_config` for native python-pptx charts (not QuickChart PNG fallback) when present.

---

## 8. Image recommendation
**Status: 🟡** — [backend/services/image_service.py](backend/services/image_service.py) only builds Pollinations URLs; no stock-API search, no per-slide rules.

**Modify:**
- [backend/services/image_service.py](backend/services/image_service.py) — add `search_stock_images(query, count)` (Unsplash + Pexels) gated on env keys, `recommend_images(slide)` with per-slide-type rules (title=hero/background, content=icon/illustration, chart=skip, kpi=minimal, section=atmospheric, comparison=icon-per-item). Fallback path returns a detailed prompt for AI generation.
- [.env.example](.env.example) — add `UNSPLASH_ACCESS_KEY=`, `PEXELS_API_KEY=`.
- [backend/agent/loop.py](backend/agent/loop.py) — replace `_add_hero_images` (or wrap it) so each slide's `image_data_json` includes URL + alt + placement + dims.

**Deps:** none (httpx already used).

---

## 9. PPTX export with native charts + new layouts
**Status: 🟡** — [backend/services/export_service.py](backend/services/export_service.py) already renders `title / bullets / two-col / quote / stats / chart / closing`. Missing: `kpi`, `comparison`, `timeline`, `section`, plus native charts driven by `pptx_config` from §7.

**Modify:**
- [backend/services/export_service.py](backend/services/export_service.py) — add `_render_kpi`, `_render_comparison`, `_render_timeline`, `_render_section`. Rewrite `_render_chart` to consume `pptx_config` (CategoryChartData → `add_chart(XL_CHART_TYPE...)`), keeping the QuickChart PNG path only as fallback. Read input from new `Slide` rows when present, falling back to `SlideDeck.slide_data`.

**Deps:** none.

---

## 10. PDF export
**Status: ✅** — `ExportService.export_pdf` exists; weasyprint is in requirements. Will revisit only if tests fail.

**Modify (optional):** wrap export in a Celery task for true background processing and update an `Export` row with status. No new files.

---

## 11. Slide CRUD / regenerate API
**Status: 🟡** — [backend/api/routes/slides.py](backend/api/routes/slides.py) only has `GET /api/slides/{task_id}` (whole-deck blob).

**Modify [backend/api/routes/slides.py](backend/api/routes/slides.py)** — add:
- `GET  /api/slides/{deck_id}/all` — list of `Slide` rows ordered by `slide_number`
- `PUT  /api/slides/{deck_id}/{slide_id}` — partial update
- `POST /api/slides/{deck_id}/{slide_id}/regenerate` — `{instruction}` → LLM rewrite
- `DELETE /api/slides/{deck_id}/{slide_id}` — delete + renumber
- `POST /api/slides/{deck_id}/reorder` — `{slide_order: [id, ...]}`
- `POST /api/slides/{deck_id}/duplicate/{slide_id}`

---

## 12. Frontend — file upload in generator
**Status: ❌**

**Modify:**
- [frontend/src/pages/Home.jsx](frontend/src/pages/Home.jsx) and/or [frontend/src/components/PromptInput.jsx](frontend/src/components/PromptInput.jsx) — add drag-and-drop zone, accept CSV/XLSX/JSON/PDF/DOCX/PPTX/TXT/MD, POST each to `/api/upload`, show chips, send `file_ids` + settings to `/api/generate`.
- Add a settings collapsible (theme / audience / tone / industry / slide count).

---

## 13. Frontend — slide editor page
**Status: ❌** — no per-slide editor today. `Generator.jsx` shows the carousel and progress only.

**Create:**
- [frontend/src/pages/DeckEditor.jsx](frontend/src/pages/DeckEditor.jsx) — three-pane layout: thumbnail rail (left), slide preview with inline-editable text (center), inspector (right) with layout dropdown, AI actions (rewrite / make-visual / simplify / custom), speaker notes. Top bar: editable title, Download PPTX, Download PDF, Present.
- API client helper [frontend/src/utils/api.js](frontend/src/utils/api.js) — `getSlides`, `updateSlide`, `regenerateSlide`, `reorderSlides`, `deleteSlide`, `duplicateSlide`.

**Modify:**
- [frontend/src/App.jsx](frontend/src/App.jsx) — add routes `/deck/:id` and `/deck/:id/present`.

---

## 14. Frontend — chart rendering + chart editor
**Status: 🟡** — `chart.js` and `react-chartjs-2` are already in [frontend/package.json](frontend/package.json).

**Create:**
- [frontend/src/components/SlideChart.jsx](frontend/src/components/SlideChart.jsx) — chooses `Bar / Line / Pie / Doughnut` based on `chart_data_json.type`, theme-aware colors.
- [frontend/src/components/ChartEditor.jsx](frontend/src/components/ChartEditor.jsx) — editable label/value table + chart-type switcher inside the editor's right inspector.

**Modify:** [frontend/src/components/SlideRenderer.jsx](frontend/src/components/SlideRenderer.jsx) — branch to `SlideChart` when `chart_data_json` exists.

---

## 15. Frontend — presentation mode
**Status: ❌**

**Create:**
- [frontend/src/pages/Presentation.jsx](frontend/src/pages/Presentation.jsx) — fullscreen 16:9, keyboard nav (←/→/Space/Esc), framer-motion `AnimatePresence`, slide counter, scaled-up renderer (title 48, body 22).

**Modify:** [frontend/src/App.jsx](frontend/src/App.jsx) — route `/deck/:id/present`.

---

## 16. React SDK
**Status: ❌**

**Create (new top-level folder `sdk/`):**
- [sdk/package.json](sdk/package.json) — `@nexus-ai/react-sdk`
- [sdk/tsconfig.json](sdk/tsconfig.json)
- [sdk/src/index.ts](sdk/src/index.ts)
- [sdk/src/PPTGenerator.tsx](sdk/src/PPTGenerator.tsx) — props: `apiKey`, `baseUrl`, `theme?`, `enableAIImages?`, `onComplete`, `onError`
- [sdk/src/hooks/useNexusAI.ts](sdk/src/hooks/useNexusAI.ts) — `{ generate, upload, getDeck, getSlides, exportDeck, updateSlide, regenerateSlide }`
- [sdk/src/types/index.ts](sdk/src/types/index.ts)
- [sdk/README.md](sdk/README.md)

**Deps (sdk only):** `react`, `axios`, `typescript`, `tsup` (build).

---

## 17. OpenAPI documentation
**Status: 🟡** — FastAPI metadata is set in [backend/main.py](backend/main.py); some routes lack tags / descriptions.

**Modify:** every route module under [backend/api/routes/](backend/api/routes) — add per-endpoint docstrings, Pydantic `Field(description=...)`, consistent `tags=[...]`, response models. Confirm `/docs` and `/redoc` render.

---

## 18. Docker compose
**Status: 🟡** — current [docker-compose.yml](docker-compose.yml) has `postgres / redis / backend / worker / frontend` already. Postgres pinned at 15-alpine.

**Modify:**
- Bump `postgres:15-alpine` → `postgres:16-alpine` only if migrations are clean (or keep 15 — no requirement to change).
- Confirm health checks are present (they are, for postgres + redis).
- [.env.example](.env.example) — add the new keys: `UNSPLASH_ACCESS_KEY`, `PEXELS_API_KEY`, `MAX_UPLOAD_SIZE_MB`, `UPLOAD_DIR`, plus document existing `DATABASE_URL`, `REDIS_URL`, `AI_PROVIDER_CHAIN`, `JWT_SECRET`.

---

## 19. End-to-end test
**Status: ❌**

**Create:** [test_e2e.py](test_e2e.py) — sample CSV → `/api/upload` → `/api/generate` (with `file_ids`) → poll `/api/slides/{id}/all` → assert ≥5 slides, ≥1 chart, ≥1 KPI → `/api/export/pptx` → poll + download → assert size > 0. Prints PASS/FAIL per step.

---

## Cross-cutting risks
1. **Two slide stores.** `SlideDeck.slide_data` (blob) and new `Slide` rows must stay in sync. Strategy: agent loop writes both; reads prefer rows when present.
2. **Celery task contract.** `run_generation_task` currently takes only `task_id`; settings live on the `Task` row, so no signature change needed when we add `file_ids`/`audience`/`tone`/`industry`.
3. **Heavy parser deps.** `pdfplumber` pulls Pillow/cryptography; verify Docker image still builds.
4. **Provider chain.** All new LLM calls must go through [backend/services/ai_service.py](backend/services/ai_service.py) (or `ClaudeService` which already wraps it), never hit `anthropic`/`openai` SDKs directly — so the existing 6-provider fallback keeps working.
5. **Frontend stays JSX.** SDK is the only TypeScript surface; the app remains Vite + JSX to avoid a migration.

---

## Ordered execution (matches the 23-step prompt list, but mapped to this repo)

| Step | Scope | Files touched |
|---|---|---|
| 3 | DB models + migration | [backend/database/models.py](backend/database/models.py), `backend/database/migrations/versions/*.py` |
| 4 | Upload route + parsers | [backend/api/routes/upload.py](backend/api/routes/upload.py), [backend/services/context_extractor.py](backend/services/context_extractor.py), [backend/utils/file_parser.py](backend/utils/file_parser.py), [backend/main.py](backend/main.py), [backend/requirements.txt](backend/requirements.txt) |
| 5 | BI extraction | [backend/services/intelligence_service.py](backend/services/intelligence_service.py), upload route wiring |
| 6 | Enhanced planner | [backend/agent/planner.py](backend/agent/planner.py), [backend/agent/prompts.py](backend/agent/prompts.py) |
| 7 | Per-slide rows + structured JSON | [backend/agent/loop.py](backend/agent/loop.py), [backend/agent/prompts.py](backend/agent/prompts.py) |
| 8 | Chart service | [backend/services/chart_service.py](backend/services/chart_service.py), loop wiring, export wiring |
| 9 | Image recs | [backend/services/image_service.py](backend/services/image_service.py), [.env.example](.env.example), loop wiring |
| 10 | Slide CRUD | [backend/api/routes/slides.py](backend/api/routes/slides.py) |
| 11 | PPTX layouts + native charts | [backend/services/export_service.py](backend/services/export_service.py) |
| 12 | PDF (revisit only if needed) | [backend/services/export_service.py](backend/services/export_service.py) |
| 13 | Editor page | [frontend/src/pages/DeckEditor.jsx](frontend/src/pages/DeckEditor.jsx), [frontend/src/utils/api.js](frontend/src/utils/api.js), [frontend/src/App.jsx](frontend/src/App.jsx) |
| 14 | Chart components | [frontend/src/components/SlideChart.jsx](frontend/src/components/SlideChart.jsx), [frontend/src/components/ChartEditor.jsx](frontend/src/components/ChartEditor.jsx), [frontend/src/components/SlideRenderer.jsx](frontend/src/components/SlideRenderer.jsx) |
| 15 | Upload UI | [frontend/src/pages/Home.jsx](frontend/src/pages/Home.jsx), [frontend/src/components/PromptInput.jsx](frontend/src/components/PromptInput.jsx) |
| 16 | Presentation mode | [frontend/src/pages/Presentation.jsx](frontend/src/pages/Presentation.jsx), [frontend/src/App.jsx](frontend/src/App.jsx) |
| 17 | Pipeline wiring + generate-route extension | [backend/api/routes/generate.py](backend/api/routes/generate.py), [backend/agent/loop.py](backend/agent/loop.py), [backend/workers/tasks.py](backend/workers/tasks.py) |
| 18 | React SDK | `sdk/` |
| 19 | OpenAPI polish | all `backend/api/routes/*.py` |
| 20 | Docker + env | [docker-compose.yml](docker-compose.yml), [.env.example](.env.example) |
| 21 | E2E test | [test_e2e.py](test_e2e.py) |
| 22 | Fix-everything pass | as needed |
| 23 | Final verification | TODO.md if anything remains |

No code is modified by this step. The plan above is the contract for steps 3–23.
