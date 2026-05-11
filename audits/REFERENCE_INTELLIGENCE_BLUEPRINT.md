# NEXUS AI - Reference Intelligence Blueprint

**Date:** 2026-05-09 (Phase 6H - audit/roadmap only)
**Scope:** Audit and blueprint. No product implementation. No code changes. No live eval.
**Status of NEXUS:** Estimated competitive score ~57/100 (~57.5 weighted, estimate). NEXUS does not beat Manus. NEXUS does not beat Presenton on user-facing presentation-product surface area.
**This file is the master implementation roadmap going forward.** All future implementation phases (6I onward) should be planned against the gap matrix and the 12-phase roadmap below. When this file conflicts with older audit text, prefer this file plus `AUDIT_CURRENT_STATE.md`.

References cited below were inspected read-only inside this workspace at `manus-reference/` and `manus-need/`. No file under `manus-need/` or `manus-reference/` has been modified by this phase.

---

## 1. Executive Verdict

### Where NEXUS stands today
- Backend gate is green: `.\scripts\test-backend.ps1` -> 245 passed, 2 skipped, 1 warning.
- Authenticated `AgentRuntime` exists (`backend/agent/runtime.py`) and is reachable via `/api/agent/test-run` behind a Bearer JWT, but it does not drive the user-facing `/api/generate` flow.
- 7 canonical layouts (`title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`) with a frontend gate and a backend schema validator.
- Deck-level source grounding, deck-quality report, and a preview-only repair pipeline.
- 30 offline live-eval tests and 15 PPTX content-parity tests; live eval has never been executed; `backend/storage/evals/` is empty.
- Competitive scoring is an estimate, not a measurement.

### Why NEXUS does not beat Manus yet
- The runtime does not drive generation end-to-end; the user flow is still the `agent/loop.py` 6-step pipeline.
- No measured browser task success, no measured deck quality, no measured citation accuracy.
- Offline deterministic claim-level citation mapper exists (Phase 6K, `backend/services/claim_citation_service.py`), but no on-slide citation marks in the rendered deck and no live integration into `/api/generate` or `evaluate_deck`. No hard fact-checking.
- No rate limits, per-user quotas, SSE step streaming, or audit logging on the runtime route.
- No production multi-tenant isolation, no per-task sandbox, no verified live LLM/search stack.

### Why NEXUS does not beat Presenton on presentation-product surface area
- No PPTX or PDF ingestion (Presenton has both with 100 MB caps).
- No MCP server (Presenton ships FastMCP from OpenAPI on `127.0.0.1:8001`).
- No SSE slide streaming, no `derive`/`prepare`/`edit` endpoints, no webhook callbacks, no stage-by-stage progress.
- Narrower BYOK story; no first-class Ollama; no `.env`-driven multi-provider matrix.
- No Electron desktop binary.

### What NEXUS already does well
- Authenticated runtime route (Phase 6A) with Alembic-tracked persistence tables.
- Schema-validated 7-layout deck pipeline; deterministic textual export parity test for every layout.
- Deck-quality report + repair preview is a stronger explicit story than any reference.
- Deck-level source grounding and per-slide source attachment for source-bearing slides.
- Strong test discipline: 245 backend tests; all offline; all reproducible from `.\scripts\test-backend.ps1`.
- Competitive rubric (`benchmarks/rubric.json`, weights sum=100) and 11-prompt corpus (`benchmarks/prompts.json`) are honest, machine-readable, and integrity-tested.
- Phase 6C/6D/6E/6F/6G discipline: zero false claims of measurement; estimates clearly labelled.

### What must become true before NEXUS is honestly near Manus
1. Runtime drives `/api/generate` behind a feature flag, with the same 7-layout schema gate.
2. The `biz-001` live eval has been executed at least once and a result JSON is committed to the audit history.
3. Claim-level citation mapping with at least one labeled gold slide.
4. SSE/progress lifecycle on the generation route with cancel and replay.
5. Visual pixel-diff suite for all 7 canonical layouts.
6. Provider abstraction supporting Ollama in addition to current providers.
7. MCP / OpenAPI tool surface so external agents can call NEXUS.
8. Rate limits, quotas, audit logging on the runtime route.
9. PPTX/PDF ingestion endpoint with content-parity tests.
10. Live evaluation across the full 11-prompt corpus, with measured (not estimated) per-category scores.

Until all 10 are true, the public claim must remain: "NEXUS does not beat Manus."

---

## 2. Reference Comparison

### 2.1 Manus (`manus-reference/`)
- **Inspected:** `manus-reference/manus.im/`, `manus-reference/api.manus.im/`, `manus-reference/events.manus.im/`, `manus-reference/help.manus.im/`, `manus-reference/trust.manus.im/`, `manus-reference/index.html`, `manus-reference/cookies.txt`, `manus-reference/hts-log.txt`. This is a captured site mirror, not source code.
- **Best at:** End-to-end autonomous task execution as a product (browser, file, terminal, multi-tool reasoning), commercial polish, public benchmark messaging.
- **NEXUS lesson:** The product surface (task list, step trace, evidence, replay) is the autonomy UX bar. The "show every tool call" pattern is what NEXUS step persistence should ultimately surface to users.
- **NEXUS already has:** `AgentRuntime` with persisted `agent_runs`/`agent_steps`/`artifacts` rows; an internal test route to drive it.
- **NEXUS missing:** Public step-streamed UX, replay, cross-task memory, live tool fleet.
- **What not to copy:** No code in `manus-reference/` is source code; nothing to copy. Do not reproduce branding, copy, or proprietary terminology.
- **License/risk:** Site capture only. Treat as competitive intelligence; do not redistribute.

### 2.2 Presenton (`manus-need/presenton/`)
- **Inspected:** `manus-need/presenton/servers/fastapi/` (FastAPI app with `/api/v1/ppt/*`), `manus-need/presenton/servers/nextjs/` (UI), `manus-need/presenton/electron/` (desktop wrapper), `manus-need/presenton/presentation-export/`, `manus-need/presenton/scripts/`, `manus-need/presenton/README.md`, `manus-need/presenton/LICENSE` (Apache-2.0).
- **Best at:** Presentation product surface area: full generation API, async with stage progress, SSE slide streaming, PPTX/PDF ingestion, BYOK breadth (OpenAI/Anthropic/Google/Vertex/Azure/Ollama/custom), FastMCP server, Electron desktop binary, ~24 test files.
- **NEXUS lesson:** Async-with-stage-progress, SSE slide streaming, derive/prepare/edit decomposition, PPTX/PDF ingestion, MCP-from-OpenAPI, env-var-only BYOK pattern, single-admin-with-rotation auth.
- **NEXUS already has:** Schema-validated 7-layout pipeline with stronger explicit deck-quality report and repair-preview semantics; deeper backend test count (245); deck-level source grounding.
- **NEXUS missing:** PPTX/PDF ingestion (hard), MCP server (hard), SSE streaming + derive/prepare/edit + webhooks (soft), Ollama BYOK (soft), Electron desktop (soft).
- **What not to copy:** Do not copy templates, themes, or generation prompts verbatim. Do not reuse Presenton's HTML/Tailwind template files.
- **License/risk:** Apache-2.0. Patterns safe to study; attribution required if any code derived.

### 2.3 browser-use (`manus-need/browser-use-reference/`)
- **Inspected:** `manus-need/browser-use-reference/browser_use/` (core package), `manus-need/browser-use-reference/examples/`, `manus-need/browser-use-reference/skills/`, `manus-need/browser-use-reference/docker/`, `manus-need/browser-use-reference/README.md`.
- **Best at:** Browser automation via accessibility tree (no vision required), structured action schemas (click/type/navigate), action history, Playwright integration.
- **NEXUS lesson:** Accessibility-tree page representation is more token-efficient than screenshots. Action schema with strict JSON validation maps directly to NEXUS's tool registry.
- **NEXUS already has:** Playwright-backed `BrowserService` (opt-in, `BROWSER_ENABLED=false` by default); browser tests at `backend/tests/test_browser_service*.py`.
- **NEXUS missing:** Accessibility-tree action loop, browser action trace capture, deterministic replay of recorded browser sessions.
- **What not to copy:** Do not reuse vendored prompts or specific action prompts. Build NEXUS-native versions.
- **License/risk:** MIT. Pattern-safe.

### 2.4 OpenManus (`manus-need/openmanus-reference/`)
- **Inspected:** `manus-need/openmanus-reference/app/` (agents, flow, tools, prompts), `manus-need/openmanus-reference/config/`, `manus-need/openmanus-reference/examples/`, `manus-need/openmanus-reference/run_flow.py`, `manus-need/openmanus-reference/run_mcp.py`.
- **Best at:** Planner / executor / monitor agent hierarchy with strict tool registry; ReAct loop with `max_steps`; MCP integration via `run_mcp.py`.
- **NEXUS lesson:** Clean separation of planner, executor, monitor, and tool registry with JSON schemas. Use MCP from `run_mcp.py` as a study reference for connecting NEXUS to external MCP servers.
- **NEXUS already has:** `backend/agent/planner.py`, `backend/agent/loop.py`, `backend/agent/tools.py`, `backend/agent/runtime.py` with persisted steps.
- **NEXUS missing:** Strict planner/executor split, configurable `max_steps`, monitor sub-agent, tool-registry JSON-schema validation at registration time.
- **What not to copy:** Do not lift prompt templates verbatim. Re-author NEXUS-native equivalents.
- **License/risk:** MIT. Most permissive of the agent references.

### 2.5 Suna (`manus-need/suna-reference/`)
- **Inspected:** `manus-need/suna-reference/apps/` (frontend), `manus-need/suna-reference/core/` (backend agent + tools), `manus-need/suna-reference/packages/`, `manus-need/suna-reference/docs/`.
- **Best at:** Production agent runtime: thread/conversation model, real-time streaming, per-task Linux sandbox, LiteLLM provider abstraction, "agent as markdown" pattern, skills/knowledge packs, persistent memory.
- **NEXUS lesson:** Thread model (create thread -> run agent -> stream updates -> complete) is the async job lifecycle target. LiteLLM is the right provider abstraction. Skills system is a good pattern for presentation-domain expertise.
- **NEXUS already has:** Celery worker scaffold (`backend/workers/`), step persistence, `agent_runs`/`agent_steps`/`artifacts` tables, deck-quality and repair-preview "skills"-like services.
- **NEXUS missing:** Thread/SSE streaming, per-task sandbox isolation, skills registry, persistent cross-run memory.
- **What not to copy:** Do not copy Supabase or Daytona-specific code. Abstract behind a NEXUS-native interface.
- **License/risk:** Apache-2.0. Heavy infra dependencies; cherry-pick patterns only.

### 2.6 AgenticSeek (`manus-need/agenticseek-reference/`)
- **Inspected:** `manus-need/agenticseek-reference/sources/agents/`, `manus-need/agenticseek-reference/sources/llm_provider.py`, `manus-need/agenticseek-reference/llm_router/`, `manus-need/agenticseek-reference/llm_server/`, `manus-need/agenticseek-reference/frontend/`.
- **Best at:** Local-first agent routing (BART zero-shot + adaptive LLM voting), specialist agents (casual/browser/coder/file/planner/MCP), session recovery (`recover_last_session`/`save_session`), local provider matrix (Ollama, LM Studio, llama.cpp, OpenAI, Google, DeepSeek).
- **NEXUS lesson:** The router pattern (classifier + LLM voting) maps cleanly onto deciding which NEXUS specialist (deck planner, source grounder, repair previewer, browser agent) to dispatch. Session recovery is a production must-have.
- **NEXUS already has:** Single agent path; no router; session recovery is implicit (DB-backed run rows but no resume API).
- **NEXUS missing:** Specialist routing, session recovery API, local-provider matrix.
- **What not to copy:** **GPL-3.0. Do not copy any code.** Patterns only. NEXUS commercial posture is incompatible with GPL derivative work.
- **License/risk:** GPL-3.0. Reference only.

### 2.7 Browser/Claude research notes (`manus-need/refence serche .txt`)
- **Inspected:** the file in this workspace.
- **Best at:** Curated landscape: also names Playwright MCP (Apache-2.0), HyperAgent (action caching for replay), PPT Master (SVG -> native PPTX, OOXML template extraction), SlideDeck AI (minimal pipeline baseline), AgentBench (LLM-as-agent benchmark harness).
- **NEXUS lesson:** Action caching (HyperAgent) directly solves NEXUS's eval reproducibility gap. PPT Master's SVG -> native PPTX is the path to editable, premium-feel exports. Playwright MCP is the canonical reference for exposing tools via MCP. AgentBench is the discipline reference for separating offline vs live evaluation.
- **NEXUS already has:** None of these patterns yet.
- **NEXUS missing:** Action cache + replay, SVG -> native-shape PPTX, MCP server, LLM-as-judge harness.
- **What not to copy:** Verify each repo's license before any pattern adaptation; AgenticSeek is GPL-3.0 (already excluded), HyperAgent license must be re-verified before adapting code-shape rather than concept.
- **License/risk:** Mixed; Playwright MCP and Presenton are Apache-2.0; PPT Master and HyperAgent need explicit license verification at adapt time. The notes file itself contains Mojibake (`--`) consistent with `cp1252`-decoded UTF-8; quote sparingly and re-encode if cited.

---

## 3. NEXUS Gap Matrix

Severity legend: Hard = NEXUS lacks the capability entirely; Soft = NEXUS has a partial or weaker version; Even = NEXUS and the best reference are roughly tied.

| Capability | NEXUS today | Best reference | Severity | First NEXUS-native fix | Test needed | Rubric category |
|---|---|---|---|---|---|---|
| Runtime-driven generation | Runtime exists; not driving `/api/generate` | OpenManus / Suna | Hard | Feature-flag `runtime_drives_generate=true` route variant; identical 7-layout schema gate | Offline test asserting flagged route returns the same schema-validated deck shape | agent_autonomy, deck_correctness |
| Browser/tool autonomy | `BrowserService` opt-in; no action loop or trace | browser-use | Hard | Action-trace capture (URL, action, AX-tree hash) persisted as `Artifact("browser_trace")` | Offline replay test: feed recorded trace, assert deterministic outcome | agent_autonomy |
| Research and source grounding | Deck-level + slide-level sources | Suna + browser-use | Soft | Add per-bullet candidate-source list during planner phase; persist as `Artifact("source_candidate")` | Test that every claim-bearing bullet has >=1 candidate source row | evidence_accuracy |
| Claim-level citations | Not present | Presenton (partial) / Manus | Hard | Mapper: bullet text -> source URL, with offline gold corpus of 5 labeled slides | New test `test_claim_citation_mapper.py` over the gold corpus | evidence_accuracy |
| Presentation templates / themes | 7 canonical layouts only | Presenton / PPT Master | Hard | Theme registry: name -> color/font/spacing tokens applied at render | Test that two themes produce different `theme_id` in deck JSON without changing schema | visual_quality |
| Visual quality | Renderer present; no pixel diff | Presenton / PPT Master | Soft | Playwright snapshot per layout into `backend/tests/snapshots/`; threshold-based diff | New `test_visual_diff.py` using saved baselines | visual_quality |
| PPTX/PDF export parity | PPTX content parity only; PDF smoke | Presenton / PPT Master | Soft | Reopen-and-assert pixel-or-shape parity on PPTX; WeasyPrint-based PDF parity smoke gated by env | Extend `test_export_parity.py` with shape-count parity + PDF page-count assertions | export_parity |
| PPTX/PDF ingestion | Not present | Presenton | Hard | `POST /api/import/pptx` returning normalized deck JSON; reject >100 MB | New `test_pptx_import.py` with a fixture deck round-trip | deck_correctness, export_parity |
| Async job progress / SSE | Sync-only generation | Presenton / Suna | Hard | SSE channel emitting `stage`/`slide_ready` events; cancel by token | Test with a fake clock that all expected SSE events fire in order | stability_reliability |
| Retry / cancel / resume / replay | None | HyperAgent / Suna | Hard | Resume by `agent_run_id`; replay by `Artifact("browser_trace")`; cancel by token | Test that resumed run reuses prior step rows; cancel sets `status="cancelled"` | stability_reliability |
| Provider / BYOK / Ollama | Groq default; Anthropic/OpenAI in code | Presenton / Suna (LiteLLM) | Soft | Single `LLMProvider` interface with `groq`/`openai`/`anthropic`/`ollama` adapters; env-var only | New `test_provider_registry.py` covering each adapter with fakes | security_production_readiness, agent_autonomy |
| MCP / OpenAPI tool surface | Not present | Presenton (FastMCP) / Playwright MCP | Hard | Generate MCP server from FastAPI OpenAPI for read-only tools first | Test that the MCP descriptor exposes the documented tools and schemas | agent_autonomy |
| Quotas / rate limits / audit logs | None on runtime route | Suna | Hard | Per-user token bucket + per-user run quota + structured audit log row per runtime call | Test rate-limit returns 429; quota exhausted returns 403; audit row count increments | security_production_readiness |
| Live eval / benchmark measurement | 30 offline tests; live never run | AgentBench / HyperAgent | Hard | Execute `biz-001` smoke from `audits/LIVE_EVAL_RUNBOOK.md`; commit redacted result JSON | Existing `backend/tests/test_live_eval_adapter.py`; new "smoke result exists" test gated by env | deck_correctness, evidence_accuracy |
| Security / production readiness | Bearer JWT on runtime; no quotas/SSE/audit | Suna | Hard | Combine BYOK abstraction + quotas + audit log + SSE step streaming in one runtime hardening phase | Tests above; plus offline test that audit log captures auth principal | security_production_readiness |

---

## 4. Unified Target Architecture

Future NEXUS architecture, expressed as layered responsibilities. None of this is implemented yet; this is the target.

```
+-------------------------------------------------------------+
|  Public API (FastAPI)                                       |
|   /api/generate (sync + SSE), /api/import/{pptx,pdf},       |
|   /api/agent/run, /api/mcp (FastMCP from OpenAPI)           |
|   Quotas + rate limits + audit log middleware               |
+-------------------------------------------------------------+
|  Runtime (drives /api/generate behind feature flag)         |
|   Coordinator -> Planner -> Executor -> Monitor             |
|   Strict tool registry with JSON schemas                    |
|   Step persistence (agent_runs/agent_steps/artifacts)       |
|   Resume / cancel / replay by run_id                        |
+-------------------------------------------------------------+
|  Specialist agents (router-dispatched)                      |
|   DeckPlanner, SourceGrounder, RepairPreviewer,             |
|   BrowserAgent (browser-use-style accessibility tree),      |
|   ImporterAgent (PPTX/PDF -> deck JSON)                     |
+-------------------------------------------------------------+
|  Provider abstraction                                       |
|   LLMProvider: groq | openai | anthropic | ollama | custom  |
|   SearchProvider: tavily | bing | offline                   |
|   ImageProvider: stable-baseline | pexels | offline         |
+-------------------------------------------------------------+
|  Presentation engine                                        |
|   7+ canonical layouts; theme registry; renderer;           |
|   PPTX content + shape parity; PDF parity (WeasyPrint);     |
|   Visual snapshot suite                                     |
+-------------------------------------------------------------+
|  Eval and benchmark                                         |
|   Offline evaluator + live adapter (opt-in)                 |
|   Action cache + deterministic replay                       |
|   Per-prompt result JSON in backend/storage/evals/          |
+-------------------------------------------------------------+
|  Storage                                                    |
|   Postgres (runs/steps/artifacts/decks/users/quotas/audit)  |
|   Redis (job state, SSE channel, rate-limit buckets)        |
|   Object storage abstraction for artifacts and exports      |
+-------------------------------------------------------------+
```

Mapped to references:
- Manus-like autonomy: Coordinator / Planner / Executor / Monitor + step trace.
- Presenton-level presentation engine: theme registry + ingestion + SSE + MCP + BYOK + PDF parity.
- browser-use-level browser operation: accessibility-tree action loop + action trace capture.
- OpenManus / Suna runtime discipline: strict tool registry + thread lifecycle + per-task isolation.
- AgenticSeek-style local/search/routing inspiration: router + Ollama + session recovery (NEXUS-native; no GPL code).
- NEXUS-native benchmark proof: 11-prompt corpus run live, measured per category, results committed.

---

## 5. Roadmap to Beat Manus (next 12 phases)

Each phase is small, testable, and auditable. Phases that move only product surface are flagged "surface only"; phases that can move the rubric score are flagged "score-eligible". A phase is score-eligible only if it produces a measurement.

### Phase 6I - Runtime drives /api/generate behind feature flag
- Goal: Add `NEXUS_RUNTIME_DRIVES_GENERATE` flag; when true, `/api/generate` dispatches through `AgentRuntime`; output schema is identical.
- Likely files: `backend/api/routes/generate.py` (or equivalent), `backend/agent/runtime.py`, `backend/config.py`, `backend/tests/test_runtime_generate_route.py`.
- Tests required: schema parity test (flag on vs off) on a fixture prompt; smoke test asserting `agent_run_id` is returned.
- Acceptance: gate green; flag off is the default; both branches produce schema-valid decks.
- Score category: agent_autonomy, deck_correctness.
- Score-eligible: surface only (no measurement).

### Phase 6J - Rebuild stack and run biz-001 live eval smoke
- Goal: `docker compose up --build` from this workspace; execute `biz-001` per `audits/LIVE_EVAL_RUNBOOK.md`; commit the redacted result JSON.
- Likely files: `audits/LIVE_EVAL_RUNBOOK.md` (no code changes); new `audits/LIVE_EVAL_RESULTS/biz-001-YYYY-MM-DD.json` (redacted).
- Tests required: offline test that asserts the committed result JSON parses against `benchmarks/eval_schema.json`.
- Acceptance: result JSON exists and parses; per-category measured fields filled; backend gate green.
- Score category: deck_correctness, evidence_accuracy.
- Score-eligible: yes (first real measurement).

### Phase 6K - Claim-level citation mapper (offline + gold corpus)
- Goal: New `backend/services/claim_citation_service.py` mapping bullet text -> source URL; ship a 5-slide gold corpus.
- Likely files: `backend/services/claim_citation_service.py`, `backend/tests/fixtures/citation_gold.py`, `backend/tests/test_claim_citation_mapper.py`.
- Tests required: precision/recall floor on gold corpus.
- Acceptance: precision >= 0.8 on the 5-slide gold corpus; gate green.
- Score category: evidence_accuracy.
- Score-eligible: yes (measured precision/recall).

**Status (2026-05-09): Implemented and accepted as Pass.** Shipped [backend/services/claim_citation_service.py](nexus-ai/backend/services/claim_citation_service.py), gold corpus [backend/tests/fixtures/citation_gold.py](nexus-ai/backend/tests/fixtures/citation_gold.py) (5 cases), and tests [backend/tests/test_claim_citation_service.py](nexus-ai/backend/tests/test_claim_citation_service.py) (18 tests; final filename diverges from the placeholder above). Mapping bases: `exact_phrase`, `numeric_match` (unit-aware: `42M`/`42 million` -> `42m`; `93%`/`93 percent` -> `93%`), `keyword_overlap` (Jaccard >= 0.34), or explicit `no_match`. Aggregate precision/recall proxy on the corpus is **>= 0.9** (test `test_corpus_aggregate_precision_proxy`). **No integration into `/api/generate` or `evaluate_deck`**, so live-eval behaviour and `benchmarks/eval_schema.json` are unchanged. Gate: 269 passed, 2 skipped, 1 warning. Headline competitive score unchanged - this phase is offline infrastructure only and does not move the score on its own; subsequent phases that wire citation mapping into the live eval and re-measure the corpus will be score-eligible.

### Phase 6L - Theme registry
- Goal: `backend/agent/themes_registry.py` mapping `theme_id` -> color/font/spacing tokens; renderer reads tokens.
- Likely files: themes_registry, renderer, layouts_registry, tests under `backend/tests/test_themes_registry.py`.
- Tests required: same deck rendered under two themes differs only in token-derived properties.
- Acceptance: gate green; two themes produce different `theme_id` without schema drift.
- Score category: visual_quality.
- Score-eligible: surface only.

**Status (2026-05-09): Implemented and accepted as Pass.** Shipped [backend/agent/themes_registry.py](nexus-ai/backend/agent/themes_registry.py) with `Theme` dataclass, two built-in themes (`nexus-default`, `nexus-light`), legacy aliases (`editorial`, `vellum`), and helpers `list_theme_ids` / `get_theme` / `resolve_theme` / `apply_theme`. Tests in [backend/tests/test_themes_registry.py](nexus-ai/backend/tests/test_themes_registry.py) (26 tests) prove that switching themes on the same deck only mutates `theme_id` + `theme_tokens` (slides byte-identical), that unknown ids fall back deterministically to default (or raise under `strict=True`), and that the canonical 7-layout schema still validates after `apply_theme`. **Renderer/exporter wiring is intentionally out of scope for this phase**: the legacy `services.export_service.THEMES` palette is untouched and the frontend renderer is unchanged, so visual quality has not changed yet. Headline competitive score unchanged. Gate: 295 passed, 2 skipped, 1 warning.

### Phase 6M - SSE / progress job lifecycle
- Goal: SSE endpoint emitting `stage` and `slide_ready` events; cancel by token.
- Likely files: `backend/api/routes/generate.py` (SSE), `backend/services/agent_run_service.py`, `backend/tests/test_generate_sse.py`.
- Tests required: fake-clock test asserting event order; cancel test sets `status="cancelled"`.
- Acceptance: event ordering deterministic; cancel returns 200; gate green.
- Score category: stability_reliability.
- Score-eligible: surface only.

### Phase 6N - Browser action trace capture + replay
- Goal: Persist browser actions as `Artifact("browser_trace")`; deterministic offline replay.
- Likely files: `backend/services/browser_service.py`, `backend/agent/runtime.py`, `backend/tests/test_browser_trace_replay.py`.
- Tests required: replay-from-trace yields identical output without LLM/network.
- Acceptance: replay test passes offline; gate green.
- Score category: agent_autonomy, stability_reliability.
- Score-eligible: yes (replay determinism is a measurement).

### Phase 6O - Visual pixel-diff suite
- Goal: Playwright snapshot per layout; threshold diff stored under `backend/tests/snapshots/`.
- Likely files: `backend/tests/test_visual_diff.py`, snapshot files, optional `scripts/refresh-snapshots.ps1`.
- Tests required: per-layout diff under fixed threshold.
- Acceptance: 7/7 layouts pass; gate green when snapshots exist; missing snapshots produce a clear failure, not a silent pass.
- Score category: visual_quality.
- Score-eligible: yes (measured pixel diff).

### Phase 6P - PPTX ingestion endpoint
- Goal: `POST /api/import/pptx` -> normalized deck JSON; 100 MB cap; reject password-protected files.
- Likely files: `backend/api/routes/import.py`, `backend/services/import_service.py`, `backend/tests/test_pptx_import.py`, fixtures.
- Tests required: round-trip a fixture pptx; reject oversize and corrupt input.
- Acceptance: round-trip preserves slide count and per-slide title text; gate green.
- Score category: deck_correctness, export_parity.
- Score-eligible: surface only (parity is structural, not visual).

### Phase 6Q - PDF ingestion endpoint
- Goal: `POST /api/import/pdf` -> normalized deck JSON via WeasyPrint or `pypdf`-based extraction.
- Likely files: `backend/api/routes/import.py`, `backend/services/import_service.py`, `backend/tests/test_pdf_import.py`.
- Tests required: page-count parity; per-page text presence sniff.
- Acceptance: gate green; PDF over 100 MB rejected.
- Score category: deck_correctness.
- Score-eligible: surface only.

### Phase 6R - Provider / BYOK abstraction including Ollama
- Goal: Single `LLMProvider` interface; adapters for groq/openai/anthropic/ollama/custom; env-var only.
- Likely files: `backend/services/ai_service.py` (refactor behind interface), `backend/services/providers/` (new), `backend/tests/test_provider_registry.py`.
- Tests required: each adapter exercised with a fake; selection by env var; missing key returns clear error.
- Acceptance: gate green; default behavior unchanged when env vars are unset.
- Score category: agent_autonomy, security_production_readiness.
- Score-eligible: surface only.

### Phase 6S - MCP / OpenAPI tool surface
- Goal: Generate FastMCP server from FastAPI OpenAPI for read-only endpoints first; serve on a separate port.
- Likely files: new `backend/mcp_server.py`, `backend/tests/test_mcp_descriptor.py`, docs in `audits/`.
- Tests required: descriptor lists documented tools and schemas; integration smoke against an in-memory client.
- Acceptance: descriptor stable; gate green.
- Score category: agent_autonomy.
- Score-eligible: surface only.

### Phase 6T - Quota / rate-limit / audit-log hardening + full 11-prompt live benchmark
- Goal (part 1): Per-user token bucket, per-user run quota, structured audit log row per runtime call.
- Goal (part 2): Execute the full 11-prompt corpus through the live eval adapter (opt-in); commit redacted per-prompt result JSONs; recompute the headline score from measurements.
- Likely files: `backend/api/middleware.py`, `backend/database/models.py` (audit_log), `backend/tests/test_runtime_quota.py`, `backend/tests/test_runtime_audit_log.py`, `audits/LIVE_EVAL_RESULTS/*.json`, `audits/CURRENT_COMPETITIVE_SCORE.md` (recomputed from measurement).
- Tests required: 429 on rate limit; 403 on quota exhausted; audit row count increments; per-prompt eval JSONs parse against `benchmarks/eval_schema.json`.
- Acceptance: gate green; per-category scores in `CURRENT_COMPETITIVE_SCORE.md` are now measurements, not estimates.
- Score category: security_production_readiness, deck_correctness, evidence_accuracy, visual_quality, export_parity, agent_autonomy, stability_reliability.
- Score-eligible: yes - this is the first phase that may honestly raise the headline score above estimate.

---

## 6. Measurement Plan

Honest improvement requires measurement. The discipline below is mandatory.

- **Backend tests:** `.\scripts\test-backend.ps1` must remain green every phase. Today: 245 passed, 2 skipped, 1 warning.
- **Offline eval:** `backend/services/eval_service.py` against fixture decks; runs in CI; never moves the headline.
- **Live eval (opt-in):** `backend/scripts/run_live_eval.py` with `NEXUS_RUN_LIVE_EVAL=true`; produces per-prompt JSON under `backend/storage/evals/` (gitignored); committed copies of *redacted* results live under `audits/LIVE_EVAL_RESULTS/`.
- **Visual screenshot diff:** Playwright snapshots per layout under `backend/tests/snapshots/`; per-layout threshold; missing snapshot = test fail.
- **Export parity:** PPTX content parity already covered (Phase 6C). Extend to shape-count parity and PDF page-count parity (Phase 6O / 6P / 6Q).
- **Citation accuracy:** Precision/recall on a labeled gold corpus (Phase 6K).
- **Browser task success rate:** Replay-from-trace determinism (Phase 6N); separately, manual scored runs against a fixed task list once `BROWSER_ENABLED=true`.
- **Reliability / flake checks:** Each test must be reproducible; flaky tests are quarantined to `pytest.mark.flaky` and tracked in `AUDIT_CURRENT_STATE.md` until fixed.
- **Security gates:** Audit log must capture auth principal, route, and outcome; rate-limit and quota tests must run offline.

A score in `CURRENT_COMPETITIVE_SCORE.md` may be edited only when at least one of: a new measurement file under `audits/LIVE_EVAL_RESULTS/`, a new visual diff suite result, a new citation precision/recall report, or a new export-parity test result, supports the change. Surface-area work alone never moves the score.

---

## 7. Non-Goals

- **No cloning Manus.** Do not reproduce branding, copy, or any proprietary string from `manus-reference/`.
- **No copying reference code.** Patterns only. AgenticSeek (GPL-3.0) is reference-only; no code adaptation. PPT Master and HyperAgent require explicit per-file license verification before any code-shape adaptation.
- **No score increase without measurement.** Surface-area parity with Presenton or Manus does not raise the rubric score; only a committed live-eval result, visual diff result, or labelled-corpus precision/recall result does.
- **No broad rewrite.** Each phase modifies the smallest file set required, with tests, and updates the relevant audit files.
- **No live provider calls without opt-in.** `NEXUS_RUN_LIVE_EVAL=true` and the documented runbook are required. The default backend gate must never call paid providers.
- **No modifying reference repos.** `manus-need/` and `manus-reference/` remain read-only inputs.

---

## 8. Source of truth

- This file is the master implementation roadmap.
- `AUDIT_CURRENT_STATE.md` remains the per-phase truth ledger.
- `AUDIT_PROMPT_CONTEXT.md` is the short context block for new chats.
- `CURRENT_COMPETITIVE_SCORE.md` records the headline score; it cannot move without a measurement.
- `COMPETITIVE_BENCHMARK_BASELINE.md` records per-competitor reference comparisons; it can grow with new sections but never overwrites prior entries.
- `FINAL_SYSTEM_AUDIT.md` and `PRD_COMPLIANCE_AUDIT.md` continue to receive a dated phase block per phase.
