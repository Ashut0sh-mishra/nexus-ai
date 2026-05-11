# NEXUS Project Handoff

This document is for the next developer taking over `D:\nexus-ai-1\nexus-ai`.

NEXUS is an AI slide-generation app. The user enters a topic, the backend researches and generates a deck, and the frontend streams progress, previews slides, allows editing, and exports/shares the final presentation.

## Current Product State

- The product is a working AI slide generator with a Manus-style direction, not a full Manus replacement yet.
- Main generation still uses the classic slide pipeline in `backend/agent/loop.py`. Pipeline shape (post-Phase 6AD): `topic → search → strategy → narrative beats → planner → slides → intent → recommender → critic → images → save`.
- A newer dynamic agent runtime exists in parallel, but it does not fully drive `/api/generate` yet.
- Evidence/source grounding has been added: sources can be attached to generated slides and displayed in the frontend.
- Frontend includes generation, live progress (with Intel Panel + AI Reasoning panel surfacing sources, research notes, slide plan, design decisions, narrative beats, layout upgrades), deck editing, presenter mode, share pages, exports, deck-quality warnings, and source evidence panels.
- **Layout count: 11 canonical, 11 exported** — `title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`, `bigstat`, `section_divider`, `timeline`, `comparison`. The four most-recent layouts (Phase 6AA + 6AC) are deterministic recommender upgrades, never replacing planner output blindly.
- **Per-slide intent metadata** (`narrative_role`, `tone`, `density`, `communication_goal`, optional `beat`) attached additively after normalization (Phase 6AB + 6AD). Validator does not require it; renderer ignores it; old saved decks are unaffected.
- **Narrative beat layer** (Phase 6AD): six canonical beats (`setup` / `escalation` / `turning_point` / `consequence` / `aftermath` / `support`) derived deterministically from `DeckStrategy.story_arc` plus optional research-side promotion, persisted as `narrative_beats.json` artifact.

## High-Level Architecture

```text
React/Vite frontend
  -> POST /api/generate
FastAPI backend
  -> creates Task row
  -> enqueues Celery job
Celery worker
  -> runs NexusAgentLoop
  -> publishes progress events to Redis
Frontend EventSource
  -> GET /api/status/{task_id}
  -> live progress and live slide preview
Backend saves final deck
  -> GET /api/slides/{task_id}
  -> export/share/edit flows
```

Core stack:

- Frontend: React 18, Vite, Tailwind, Framer Motion, lucide-react, axios.
- Backend: FastAPI, SQLAlchemy async, Celery, Redis, PostgreSQL, Pydantic settings.
- AI: multi-provider `AIService` with free-first fallback.
- Search: Tavily, Serper, DuckDuckGo, Wikipedia depending on configured keys/service code.
- Browser: Playwright service, disabled by default via `BROWSER_ENABLED=false`.
- Export: backend PPTX/PDF export service plus local/R2 storage fallback.

## Important Folders

```text
backend/
  main.py                    FastAPI app, routers, health check, startup
  config.py                  all env vars and provider/model config
  api/routes/                HTTP APIs
  agent/                     generation loop, prompts, tools, runtime, source grounding
  services/                  AI/search/browser/export/storage/auth/lifecycle services
  database/                  SQLAlchemy models and connection
  workers/                   Celery app and generation task
  tests/                     backend tests

frontend/
  src/App.jsx                routes
  src/pages/                 Home, Generator, DeckWorkspace, Presenter, SharedSlide
  src/components/            slide renderer/editor/export/progress/source panels
  src/hooks/                 generation stream, lifecycle, export helpers
  src/utils/                 API client, slide normalization, local deck storage

scripts/
  test-backend.ps1           reproducible backend test runner
  doctor.ps1                 checks correct workspace/docker project
  verify-layouts.mjs         frontend/backend layout parity check

audits/
  existing audit trail and phase notes

manus-need/
  open-source reference projects only; not production code

manus-reference/
  scraped public Manus website/reference pages; not real Manus source code
```

## Backend Request Flow

The main endpoint is `POST /api/generate` in `backend/api/routes/generate.py`.

Request body:

```json
{
  "topic": "AI trends in healthcare",
  "slide_count": 8,
  "theme": "Editorial",
  "search_web": true,
  "user_id": null,
  "min_sources": 0
}
```

What happens:

1. The route validates the payload.
2. It infers an effective art direction/theme.
3. It creates a `Task` row with status `pending`.
4. If `NEXUS_RUNTIME_DRIVES_GENERATE=true`, it records an `AgentRun` dispatch trail only. This is feature-flagged and default off.
5. It enqueues `run_generation_task.delay(task.id, payload.min_sources)`.
6. The response is `202` with `{ task_id, status }`.

The worker entry point is `backend/workers/tasks.py`.

The worker:

- loads the `Task`,
- creates a Redis progress publisher,
- runs `NexusAgentLoop.run(...)`,
- enforces a 300 second timeout,
- emits status/progress events,
- marks cancelled/failed/done states.

## Generation Pipeline

The main generation class is `NexusAgentLoop` in `backend/agent/loop.py`.

Pipeline:

1. Analyze topic.
2. Search web if enabled.
3. Build deck strategy and art direction.
4. Plan slide outline.
5. Generate all slides in one batch when possible.
6. Fall back to per-slide generation if batch generation fails.
7. Normalize slides to canonical layouts.
8. Attach source metadata to source-bearing slides.
9. Run critic/rewrite pass.
10. Re-normalize and re-attach sources.
11. Add hero images when possible.
12. Repair deck for validator compatibility.
13. Save final `SlideDeck` and update `Task`.

Key supporting files:

- `backend/agent/prompts.py`: system/user prompts for generation and critique.
- `backend/agent/planner.py`: outline planning.
- `backend/agent/deck_strategy.py`: strategy artifact.
- `backend/agent/art_direction.py`: topic-aware visual direction.
- `backend/agent/layouts_registry.py` and `layouts.registry.json`: canonical layouts.
- `backend/agent/deck_quality.py`: quality report and source warnings.
- `backend/agent/source_grounding.py`: source extraction/normalization/attachment.
- `backend/agent/deck_repair.py`: validator repair before save.

## AI / Model Setup

All model settings are centralized in `backend/config.py`. Do not read `os.environ` directly from random modules.

The current provider chain defaults to the **stable runtime profile** -- only providers with verified-working credentials:

```text
groq, nvidia_nim, sambanova
```

All 10 providers below remain SUPPORTED in code and visible in `/api/health`. Disabled providers are operationally disabled, not removed -- re-enable any of them by editing `AI_PROVIDER_CHAIN` and / or `ROLE_MODEL_MAP` once their credentials work.

- Excluded due to free-tier 429 risk: `gemini`, `openrouter`, `cerebras`.
- Excluded until valid inference credentials exist: `mistral`, `github_models`.
- No key configured: `anthropic`, `openai`, `unfiltered` (still selectable via env).

Supported provider env vars (10 providers total):

- `GROQ_API_KEY`, model default `llama-3.3-70b-versatile`
- `GEMINI_API_KEY`, model default `gemini-2.0-flash`
- `OPENROUTER_API_KEY`, model default `meta-llama/llama-3.3-70b-instruct:free`
- `NVIDIA_NIM_API_KEY`, model default `meta/llama-3.3-70b-instruct`
- `ANTHROPIC_API_KEY`, dev model `claude-opus-4-7`, prod model `claude-sonnet-4-6`
- `OPENAI_API_KEY`, fallback model `gpt-4.1`
- `UNFILTERED_API_KEY`, optional community OpenAI-compatible endpoint
- `CEREBRAS_API_KEY`, model default `qwen-3-235b-a22b-instruct-2507` (Phase 6W)
- `SAMBANOVA_API_KEY`, model default `Meta-Llama-3.3-70B-Instruct` (Phase 6W)
- `MISTRAL_API_KEY`, model default `mistral-small-latest` (Phase 6W)
- `GITHUB_MODELS_API_KEY`, model default `gpt-4o-mini` (Phase 6W)

Important behavior:

- `AIService.complete(system, user, max_tokens, temperature)` tries each configured provider in `AI_PROVIDER_CHAIN` until one succeeds. Signature unchanged.
- `AIService.complete_for_role(role, system, user, ...)` (Phase 6W) routes by **role**: it consults `settings.ROLE_MODEL_MAP`, calls the preferred provider with the **exact** preferred model, and on any failure logs `ai.role_failed_falling_back` and falls back to the regular `complete()` chain. Returns the same `(text, tokens, cost)` tuple.
- All provider handlers (`_call_openrouter`, `_call_nvidia_nim`, `_call_groq`, `_call_openai`, `_call_unfiltered`, `_call_cerebras`, `_call_sambanova`, `_call_mistral`, `_call_github_models`, `_call_gemini`, `_call_anthropic`) accept a keyword-only `model: str | None = None`. When `None` they use the env-default model.
- If a valid Anthropic key starts with `sk-ant-`, Anthropic is automatically promoted to the front of the chain.
- `ClaudeService` is a compatibility shim (`ClaudeService = AIService`); old code still works.
- `/api/health` reports **all 10 providers** with `configured`, `active`, `model`, `base_url`. It does not remote-ping providers.
- Token pruning helpers `prune_messages()` and `_prune_user_text()` (Phase 6W) do middle-truncation that preserves the head + tail (so the output contract at the end of prompts is never dropped). Approximate, dependency-free, ~4 chars/token. Tunables: `MAX_CONTEXT_TOKENS` (default 6000), `KEEP_LAST_MESSAGES` (default 5).

Role routing (`settings.ROLE_MODEL_MAP`, Phase 6W -- stable profile):

| Role | Provider | Model | Wired in code? |
|------|----------|-------|----------------|
| `planner` | sambanova | `Meta-Llama-3.3-70B-Instruct` | yes -- `backend/agent/planner.py` |
| `writer` | groq | `llama-3.3-70b-versatile` | yes -- `backend/agent/loop.py` (batch + per-slide) |
| `critic` | nvidia_nim | `meta/llama-3.3-70b-instruct` | yes -- `backend/agent/loop.py` (rewrite weak slides) |
| `research` | sambanova | `Meta-Llama-3.3-70B-Instruct` | defined; not currently wired (research is harvested by `SearchService`; compression flows through `summarize`) |
| `vision` | groq | `llama-3.3-70b-versatile` | yes -- `backend/agent/loop.py` (hero-image prompts) |
| `repair` | nvidia_nim | `meta/llama-3.3-70b-instruct` | defined; not currently wired (deterministic `repair_for_validator` is sufficient for the current schema) |
| `summarize` | sambanova | `Meta-Llama-3.3-70B-Instruct` | yes (conditional) -- `_summarize_long_research` triggers when research > 10k chars |
| `json_fix` | groq | `llama-3.3-70b-versatile` | yes (conditional) -- `_json_fix_retry` runs on slide-array / single-slide parse failure |

Every role is pinned to a verified-working provider; on failure `complete_for_role()` still falls back through `AI_PROVIDER_CHAIN`.

Smoke test: `test_providers.py` (repo root). Skips unconfigured providers, pings configured ones with a tiny "Reply OK only." prompt, prints OK/FAIL/SKIP + model, exits non-zero only if every configured provider failed. Host Python typically lacks `pydantic`, so run inside the backend container:

```powershell
docker run --rm `
  -v "D:\nexus-ai-1\nexus-ai:/app" `
  -v "D:\nexus-ai-1\nexus-ai\.env:/app/.env:ro" `
  -w /app -e PYTHONPATH=/app/backend `
  nexus-ai-backend:dev python test_providers.py
```

Remaining risks:

- **Active role routing uses only `groq`, `nvidia_nim`, `sambanova`.** Every role in `ROLE_MODEL_MAP` is pinned to one of these three; the default `AI_PROVIDER_CHAIN` is the same set. The other 7 providers (`gemini`, `openrouter`, `cerebras`, `mistral`, `github_models`, `anthropic`, `openai`, plus optional `unfiltered`) remain supported in code and visible in `/api/health` but are NOT routed to by default. Re-enable any of them later by editing `AI_PROVIDER_CHAIN` and / or `ROLE_MODEL_MAP` -- no code change required.
- **Free-tier limits on the three active providers.** Groq, NVIDIA NIM, and SambaNova all have free / low-cost tiers that can rate-limit under sustained load. There is currently no paid tier configured. If all three throttle simultaneously, `complete_for_role()` and `complete()` both return errors -- there is no fallback to a non-active provider unless the chain is widened.
- **Static routing.** `ROLE_MODEL_MAP` and `AI_PROVIDER_CHAIN` are env-driven; no learned / measured routing, no per-task A/B, no automatic key-health probing. `/api/health` reports configuration, not liveness.
- **Approximate token pruning.** `prune_messages()` and `_prune_user_text()` use a ~4 chars/token heuristic (no `tiktoken` dependency). For pathological inputs it may under- or over-trim by a few percent.
- **Future key rotation.** If the disabled providers are re-enabled later, their keys will need to be valid at that time -- the current Mistral / GitHub Models keys return 401 and the Gemini / OpenRouter / Cerebras keys hit free-tier 429s, so simply un-commenting them without rotating / upgrading first will reintroduce the failures the stable profile was designed to avoid.

## Database Models

Defined in `backend/database/models.py`.

Main product tables:

- `User`: account/auth data.
- `Task`: one generation job, status/progress/cost/model metadata.
- `SlideDeck`: final saved slide JSON and theme.
- `Export`: generated PPTX/PDF file URLs.
- `ShareToken`: public share links.

Agent-runtime tables:

- `AgentRun`: dynamic-agent run metadata.
- `AgentStep`: thought/action/observation/final records.
- `Artifact`: evidence/source/file artifacts.

Warning: the agent-runtime models exist, but production Alembic migration coverage should be checked before deploying fresh production databases.

## API Routes

Registered in `backend/main.py` under `/api`:

- `POST /api/generate`: enqueue deck generation.
- `GET /api/status/{task_id}`: SSE progress stream.
- `GET /api/lifecycle/{task_id}`: lifecycle status.
- `POST /api/lifecycle/{task_id}/cancel`: request cancellation.
- `POST /api/lifecycle/{task_id}/retry`: rerun from scratch.
- `POST /api/lifecycle/{task_id}/resume`: currently reruns from scratch; no checkpoint resume yet.
- `GET /api/slides/{task_id}`: fetch final deck.
- `PUT /api/slides/{task_id}`: save edited deck.
- `POST /api/export/pptx`: export PPTX.
- `POST /api/export/pdf`: export PDF.
- `POST /api/share`: create share token.
- `GET /api/share/{token}`: public deck view.
- `/api/auth/*`: auth routes.
- `POST /api/agent/test-run`: internal safe agent-runtime test route.
- `GET /api/health`: backend/provider health.

## Frontend Flow

Routes are in `frontend/src/App.jsx`:

- `/`: Home/prompt entry.
- `/generate/:taskId`: generation progress and live preview.
- `/deck/:taskId`: editable deck workspace.
- `/present/:taskId`: fullscreen presenter.
- `/share/:token`: public shared deck.

Important frontend files:

- `frontend/src/utils/api.js`: axios client. Uses `VITE_BACKEND_URL` or `/api` by default.
- `frontend/src/hooks/useGenerate.js`: starts generation and opens the SSE stream.
- `frontend/src/hooks/useJobLifecycle.js`: cancel/retry/resume controls.
- `frontend/src/pages/Generator.jsx`: progress UI, live slide preview, done actions.
- `frontend/src/pages/DeckWorkspace.jsx`: edit slides, reorder, duplicate, delete, change layout, save.
- `frontend/src/components/SlideRenderer.jsx`: canonical frontend slide rendering.
- `frontend/src/components/SlideEditor.jsx`: field-level slide editor.
- `frontend/src/components/DeckQualityBadge.jsx`: validation/source warning panel.
- `frontend/src/components/SourceEvidencePanel.jsx`: source/evidence panel.
- `frontend/src/utils/slideParser.js`: normalizes backend slide JSON for frontend use.

Frontend generation flow:

1. Home posts to `/api/generate`.
2. App navigates to `/generate/{taskId}`.
3. `useTaskStream` opens `EventSource` to `/api/status/{taskId}`.
4. Live `slide_ready` frames populate preview as slides arrive.
5. When status is `done`, frontend fetches `/api/slides/{taskId}`.
6. User can export, present, share, or open editor.

## Slide Layouts And Data Shape

Canonical layouts are controlled by the backend registry and verified by `scripts/verify-layouts.mjs`.

Canonical layouts (11 total, all exported, as of Phase 6AC):

- `title`
- `bullets`
- `two-col`
- `quote`
- `stats`
- `chart`
- `closing`
- `bigstat` — single dominant metric (Phase 6AA). Exporter degrades to `stats`.
- `section_divider` — typography pause between deck sections (Phase 6AA). Exporter degrades to `title`.
- `timeline` — horizontal chronology of dated events (Phase 6AC). Exporter degrades to `bullets`.
- `comparison` — side-by-side with explicit `vs` framing (Phase 6AC). Exporter degrades to `two-col`.

The four post-Phase-6V layouts are populated by `agent/layout_recommender.py` (Phase 6AA + 6AC), a deterministic post-planner upgrader that never replaces planner output blindly. It only fires when the upgrade is unambiguously better and refuses to upgrade if the new layout would silently drop content.

Always check `backend/agent/layouts.registry.json`, `frontend/src/design/layouts.registry.json`, `backend/agent/layouts_registry.py`, and `frontend/src/utils/slideFactory.js` before adding/removing layouts. Both registry JSON files must stay byte-identical (verified by `scripts/verify-layouts.mjs`).

Do not add a backend layout unless the frontend renderer (`SlideRenderer.jsx`) and export service (`backend/services/export_service.py` PPTX dispatch + HTML block) also support it. The exporter must always degrade gracefully to a pre-existing layout if the new layout cannot be rendered natively.

## Source Evidence / Grounding

Source-related functionality is implemented but still advisory.

Current behavior:

- Search results can be carried through generation.
- `source_grounding.py` normalizes sources.
- Source metadata can be attached to slides.
- `deck_quality.py` reports source warnings.
- Frontend shows evidence in `SourceEvidencePanel`.

Limitations:

- It is not full claim-level citation verification.
- It does not guarantee every factual claim has a source.
- On-slide citations are not fully implemented yet.

## Dynamic Agent Runtime

The newer runtime is separate from the main deck pipeline.

Key files:

- `backend/agent/runtime.py`: tool-calling loop with JSON actions.
- `backend/agent/tools.py`: tool registry.
- `backend/agent/planners.py`: planner adapter around `AIService`.
- `backend/api/routes/agent.py`: safe internal `/api/agent/test-run` route.
- `backend/services/agent_run_service.py`: persistence helpers.
- `AgentRun`, `AgentStep`, `Artifact` tables in `models.py`.

Status:

- Runtime exists and is tested.
- It can record steps/artifacts.
- It is not the main production `/api/generate` engine yet.
- `NEXUS_RUNTIME_DRIVES_GENERATE=true` only records a dispatch trail; it does not fully execute deck generation through the runtime.

## Local Development

Use this exact workspace:

```powershell
cd D:\nexus-ai-1\nexus-ai
```

There was previously confusion with another clone such as `D:\nexus-ai-gh`. Use `scripts/doctor.ps1` to verify Docker/container context.

Backend with Docker/test script:

```powershell
pwsh ./scripts/test-backend.ps1
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Frontend layout verification:

```powershell
cd frontend
npm run verify:layouts
```

Frontend production build:

```powershell
cd frontend
npm run build
```

Manual backend dev:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Worker in separate terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
celery -A workers.celery_app.celery worker --loglevel=info
```

Docker boot:

```powershell
.\start.bat
```

## Required / Useful Environment Variables

Minimum useful local setup:

```env
SECRET_KEY=change-this
DATABASE_URL=postgresql://postgres:password@localhost:5432/nexus
REDIS_URL=redis://localhost:6379
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000

# Set at least one AI key:
GROQ_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
NVIDIA_NIM_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Optional research:
TAVILY_API_KEY=
SERPER_API_KEY=

# Optional browser automation:
BROWSER_ENABLED=false

# Optional storage:
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=nexus-exports
R2_ENDPOINT=
R2_PUBLIC_URL=
```

Backend startup fails if no AI provider key is configured.

## Verification Status From Recent Work

Recent verified gates in this workspace:

- Backend reached **`521 passed, 2 skipped, 1 warning`** after Phase 6X–6AE-Acceptance (was 431/2/1 at Phase 6V).
- Frontend layout verification passed: **`11 canonical layouts, 11 exported`** (was 7/7 pre-Phase 6AA).
- Frontend production build: **`built in ~5s`** with chunk-size warning at the existing pre-6AE baseline (~210 kB gzipped JS).
- Diagnostics were clean after Phase 6X–6AE-Acceptance.

If taking over, rerun these before making large changes:

```powershell
pwsh ./scripts/test-backend.ps1
cd frontend
npm run verify:layouts
npm run build
```

## Known Gaps / Next Work

Highest-impact next tasks:

1. ~~Add role-based model routing and token budgets.~~ **Done in Phase 6W.**
2. ~~Add prompt/session pruning so old tool results do not waste tokens.~~ **Done in Phase 6W.**
3. Move `/api/generate` closer to the dynamic runtime instead of only the old loop. (Phase 6I shipped feature flag `NEXUS_RUNTIME_DRIVES_GENERATE`; only dispatch trail is recorded today.)
4. Add production Alembic migrations for newer runtime/evidence tables if missing.
5. Add claim-level citation mapping and optional on-slide citations. (Mapper exists in `backend/services/claim_citation_service.py` from Phase 6K; not yet wired into `/api/generate` or rendered on slides.)
6. Add Playwright/visual regression tests for frontend and export fidelity. (Pre-condition for any `visual_quality` rubric score increase.)
7. Harden `/api/agent/test-run` with auth/rate limits before any public exposure.
8. Implement true checkpoint resume; current resume starts from scratch.
9. Improve export parity between React renderer and backend PPTX/PDF renderer. (Phases 6AA + 6AC ship structural exporter degradation for the 4 new layouts; visual parity still unmeasured.)
10. Add quotas/credit accounting around AI usage.
11. ~~**(Phase 6X–6AE acceptance)** Commit unit tests for the in-flight phases and re-run the backend gate.~~ **Done.** Backend gate is now **521 passed / 2 skipped / 1 warning** (was 431/2/1 at Phase 6V; +90 new tests). Phases 6X / 6Y / 6AB / 6AA / 6AC / 6AD / 6AE are all promoted from Acceptance Pending to **Pass**. See the Phase 6X–6AE-Acceptance entry in `audits/AUDIT_CURRENT_STATE.md` for full details.
12. **(Score-eligible) Live re-benchmark** after Phase 6X–6AE acceptance. Score is held at ~62/100 Partial until a logged `LIVE_EVAL_RESULTS/` JSON measures the impact of the new visible-cognition surface, 4 new layouts, intent metadata, and narrative beats.

## Reference Folder Findings

`manus-reference` is scraped public Manus website content. It does not reveal Manus' private model stack.

`manus-need` contains open-source references:

- OpenManus defaults to Claude 3.7 Sonnet and supports Anthropic, Gemini, Azure OpenAI, Ollama/local, Bedrock, and compatible APIs.
- Browser Use supports Browser Use Cloud, OpenAI, Anthropic, Azure OpenAI, Gemini, DeepSeek, Grok/xAI, Novita, and Bedrock. It recommends a specialized browser model for browser automation.
- AgenticSeek defaults to local Ollama with `deepseek-r1:14b`, with API fallbacks like OpenAI, DeepSeek, OpenRouter, Together, Google, Anthropic, MiniMax, and LM Studio.
- Suna/Kortix uses router-style cloud LLM routing with OpenRouter primary and Anthropic/OpenAI/xAI/Gemini/Groq/Bedrock optional. It also has useful session-pruning settings.

Best thing to copy from references: not more providers, but smarter routing by task type plus token/context pruning. **Phase 6W status:** role-based routing (`complete_for_role`), exact-model override on every provider handler, and middle-truncation prompt pruning are now implemented. See the Phase 6W section in `audits/FINAL_SYSTEM_AUDIT.md`. Possible future work: exact `tiktoken` pruning, learned/measured routing, automatic key-health probing, and dynamic chain reordering by latency.

## Takeover Advice

- Do not rewrite everything. The current app works; improve it in narrow phases.
- Keep frontend/backend layout registry in sync.
- Keep source metadata alive through parsing, editing, export, and share flows.
- Treat the dynamic runtime as the future path, but do not break the stable slide loop until parity is proven.
- Always run backend tests and `npm run verify:layouts` before claiming a phase is done.
- Be careful with Docker: verify this workspace is the mounted source before trusting container results.