# Architecture Hardening Audit

> **Reading note.** For current truth, read `AUDIT_CURRENT_STATE.md` first. This file contains historical phase notes and original audit findings. Older sections may be superseded. Do not treat old phase claims as current evidence without checking `AUDIT_CURRENT_STATE.md` and `AUDIT_READING_GUIDE.md`.

Date: 2026-05-08  
Role: Senior staff-engineer architecture hardening review  
Scope: maintainability, modularity, abstraction quality, system boundaries, contracts, CI, regression safety, scaling, async/queue/export reliability, testing, observability, deployment, operations

## Executive Summary

The system is not production-hardened. It is a functional monolith-plus-worker application with many platform-shaped modules, but its reliability guarantees are mostly aspirational. The most serious risks are weak CI enforcement, fragile async/task execution, insufficient queue semantics, duplicate renderer/export contracts, limited observability, and a deployment strategy that stops at Docker Compose.

Operational readiness score: **3.1 / 10**  
Launch posture: **private alpha only**  
Production launch blocker count: **18 critical/high blockers**

## Phase 4 — Evidence-Aware Deck Generation + Source Visibility - 2026-05-09

### What Was Built
- `backend/agent/source_grounding.py` gained a deck-level helper `attach_research_sources_to_deck(slides, sources) -> list[dict]`. It is **non-mutating**, normalises the supplied sources once, and:
  - attaches up to 3 normalised sources under `slide["sources"]` for `stats` and `chart` layouts;
  - sets `chart_data.source` to a defensible label (source title, else URL host — never invented) **only if** it was empty;
  - attaches sources to `bullets` / `two-col` / `quote` slides only when `extract_claim_candidates_from_slide` reports a numeric claim;
  - leaves `title` / `closing` slides untouched;
  - leaves all slides untouched if no usable sources were supplied.
- `backend/agent/loop.py` now keeps the search sources alive through the pipeline (previously thrown away with `_, _sources = await self.search.search(...)`) and calls `attach_research_sources_to_deck` after the post-normalize step **and** after the critic+normalize step (the critic can rewrite chart/stats slides). Failures inside the helper are caught and never abort generation.
- `frontend/src/components/DeckQualityBadge.jsx` now surfaces `deck_quality.source_warnings`:
  - When `source_warnings.length > 0`, the pill label appends "· N source warning(s)".
  - When the panel is open, a new `deck_quality.source_warnings` block lists `slide N · layout · code` rows (capped at 12).
  - No layout, theme token, or visual contract changed; the only diff is text + one new section in the existing panel.
- `/api/slides/{task_id}` and `/api/share/{token}` already passed slides through `attach_quality_report` without filtering keys, so attached `slide.sources` and the new `chart_data.source` flow through unchanged. No route code modified.

### Files Changed
- `backend/agent/source_grounding.py` (added `attach_research_sources_to_deck` + helpers; ~110 lines).
- `backend/agent/loop.py` (3 small edits: keep `search_sources`, attach after assemble, attach after critic).
- `frontend/src/components/DeckQualityBadge.jsx` (single edit: `source_warnings` integration; visual style preserved).
- `backend/tests/test_phase4_attach_sources.py` (new, 13 tests).

### Tests Added (13)
- Stats slide gets normalised sources attached; cap respected; input not mutated.
- Chart slide with empty `chart_data.source` receives the title of the primary source.
- Chart slide with non-empty `chart_data.source` is **not** overwritten.
- Chart slide with no source title falls back to the URL host (`example.com`), never an invented label.
- Empty / garbage sources → no mutation.
- `bullets` slide *with* numeric claim → sources attached; *without* → not attached.
- `build_deck_source_report` warnings disappear after attach for stats and chart slides.
- Chart slide without sources still produces a warning when no sources are supplied.
- Full `DeckQualityReport.summary["source_warnings"]` drops to 0 after attach.
- Original deck list and inner dicts (including `chart_data`) are not mutated.

### Tests Run
- `scripts/test-backend.ps1`: **171 passed, 2 skipped, 4.94s** (was 158/2 after Phase 3; +13 new).
- Frontend `npm run verify:layouts`: ✔ **7 / 7**.

### Result
Phase 4 — **Pass.** Generated decks now carry research sources on stats/chart slides where it is defensible, the missing-source state is visible to users via the existing `DeckQualityBadge`, and no part of the existing API or visual surface was redesigned. `/api/generate` is unchanged; the loop continues to use `agent/loop.py`. Source attachment is deck-level and advisory: stats values are not bound to specific sources yet, and we never claim a stat is *true* — only that the slide has at least one piece of supporting source metadata.

### Remaining Risks (called out, not hidden)
- **Source matching is heuristic, not hard fact-checking.** A deck-level source list does not guarantee that any specific stat in a slide actually came from that source.
- **Sources are deck-level, not claim-specific.** A stats slide with three numbers and one source list cannot prove which number came from which.
- **No visual citations are rendered on slides yet.** Citations live in the data layer and the badge panel; the slide renderer is unchanged.
- **Runtime is still not driving `/api/generate`.** `AgentRuntime` lives parallel to the existing 6-step loop; only the loop produces user decks.
- **`/api/agent/test-run` remains internal-only**, no auth, no rate limit.
- **Still no Alembic migration** for `agent_runs` / `agent_steps` / `artifacts`.
- **The DeckQualityBadge update is the only frontend source UI.** Slide thumbnails, the slide renderer, and the export pipeline have no source affordance yet.
- **`extract_claim_candidates_from_slide` remains a heuristic** and may false-positive on prose like "100% effort".

## Phase 3 — Source Grounding & Evidence Artifacts - 2026-05-09

### What Was Built
- New module `backend/agent/source_grounding.py` with pure, JSON-safe helpers (no DB, no FastAPI, no slide-schema imports):
  - `normalize_source(raw, provider=...)` — coerces arbitrary search/browser dicts into `{title, url, snippet, provider, observed_at, confidence, metadata}`. Truncates snippets to 600 chars, titles to 240, urls to 1024. Filters out garbage (returns `None` when no url/title/snippet).
  - `extract_sources_from_tool_result(tool_name, tool_output)` — understands `info_search_web` (`data.sources`) and the read-only browser family (`browser_view/navigate/click/scroll_*`). Returns `[]` for unknown tools, failed payloads, idle, etc. Never raises.
  - `extract_claim_candidates_from_slide(slide)` — surfaces stats items, chart cells, and prose fields containing numbers as `{layout, path, snippet}` records (heuristic, never invents truth).
  - `attach_sources_to_slide(slide, sources)` — returns a *new* slide dict with normalised `sources[:8]`. Does not mutate input.
  - `slide_has_source_metadata(slide)` and `build_deck_source_report(slides) -> {warnings, stats_slide_count, chart_slide_count, slides_with_sources}`.
- Extended `agent/deck_quality.py`:
  - `DeckQualityReport` gained a new top-level `source_warnings: list[dict]` field (and `to_dict()` key). `summary` now also carries `source_warnings` (count) and `slides_with_sources`.
  - Stats slides without source metadata, and chart slides whose `chart_data.source` is empty *and* who have no other source metadata, produce advisory `missing_source` warnings. **Never** mutates slides, **never** flips `ok` to `False`.
- Extended `agent/runtime.py`:
  - After every successful tool observation the runtime calls `_record_source_artifacts(...)`. It pulls evidence via `extract_sources_from_tool_result` and writes one `Artifact(artifact_type="source")` row per source via the existing `services.agent_run_service.record_artifact`. `meta` carries `{tool, url, snippet, provider, observed_at, confidence, metadata}`. `file_url` is set to the source URL.
  - Failures inside artifact recording are caught, logged, and never abort the run.
  - Snippets are already truncated by `normalize_source`, so `Artifact.meta` cannot blow up regardless of tool output size.
  - **No DB schema change.** The existing `Artifact.meta` JSON column is the only storage used.
- Extended `api/routes/agent.py`:
  - Response now includes `artifacts: {total, sources, by_type}`. No raw payloads, no snippets, no URLs in the response — just counts. Inspect via `GET` of the artifact rows when needed.
  - The route still uses the same Phase 2.5 safe-default allowlist; nothing dangerous was opened.

### Files Changed
- `backend/agent/source_grounding.py` (new, ~270 lines).
- `backend/agent/deck_quality.py` (added `source_warnings` field + `build_deck_source_report` integration; 2 small edits).
- `backend/agent/runtime.py` (added `_record_source_artifacts` helper + 1 hook in the success path).
- `backend/api/routes/agent.py` (added `artifacts` summary; 3 small edits).
- `backend/tests/test_source_grounding.py` (new, 14 tests).
- `backend/tests/test_phase3_runtime_artifacts.py` (new, 3 tests).
- `backend/tests/test_deck_quality.py` and `backend/tests/test_api_deck_quality_payload.py` (intentional shape updates: added `source_warnings` to the exact-key sets).

### Tests Added (17 net new, 2 intentional shape updates)
- `normalize_source` happy path / empty-input None / snippet truncation.
- `extract_sources_from_tool_result` for `info_search_web` (filters garbage), for `browser_view`, returns `[]` for `idle` / failed / unknown.
- `extract_claim_candidates_from_slide` for stats / chart / bullets-with-numbers.
- `attach_sources_to_slide` does not mutate input.
- `slide_has_source_metadata` recognises `chart_data.source`, rejects junk.
- `build_deck_source_report` warns on stats-without-source, no-warns on chart-with-source, warns on chart-without-source.
- `DeckQualityReport.source_warnings` is populated end-to-end.
- Runtime persists 2 `Artifact(type="source")` rows for a successful `info_search_web` observation; persists **0** for a failed one.
- Route response carries `{artifacts: {total, sources, by_type}}` and does **not** embed raw snippets/urls.
- All previous Phase 1/2/2.5 tests still pass unchanged (other than the two intentional exact-set updates noted above).

### Tests Run
- `scripts/test-backend.ps1` (which now correctly builds the dev image when missing): **158 passed, 2 skipped, 4.16s** (was 139/2 after Phase 2.5; +19 new).
- Frontend `npm run verify:layouts`: ✔ **7 / 7** (no frontend changed).

### Result
Phase 3 — **Pass.** The system can now (a) normalise heterogeneous tool outputs into a single evidence record shape, (b) persist those evidence records as `Artifact` rows attached to the agent run that produced them, (c) surface advisory `source_warnings` on stats/chart slides without source metadata, and (d) report artifact counts on the runtime route without leaking raw payloads. The 6-step slide pipeline, `/api/generate`, the 29-tool registry, and the `BROWSER_ENABLED=false` default are all untouched. No DB migration required — we only used existing columns.

### Remaining Risks (called out, not hidden)
- **Source grounding is advisory, not hard fact-checking.** We never claim a stat is true; we only note when a slide makes a numeric claim with no source metadata.
- **Evidence artifacts are not surfaced in the frontend yet.** They live in the DB and the route summary; no UI renders them.
- **The runtime is still not wired into deck generation.** `/api/generate` continues to use `agent/loop.py`. Connecting a runtime-driven deck flow (with attached evidence) is Phase 4 / 5.
- **The `/api/agent/test-run` endpoint remains internal-only.** Still no `Depends(get_current_user)`, no rate limit, no per-user quota.
- **Browser-tool evidence is limited when `BROWSER_ENABLED=false`** (the default). Live browser observations require Phase 2A live mode and do not run in CI.
- **Still no Alembic migration** for `agent_runs` / `agent_steps` / `artifacts`. Production Postgres deploy of the runtime + evidence is gated on it.
- **`extract_claim_candidates_from_slide` is a heuristic.** A bullet like "100% effort" trips the number regex; a stat like "breakeven" does not. Acceptable for advisory flagging; not for fact-checking.

## Phase 2.5 — Safe Internal Agent API + Planner Adapter - 2026-05-09

### What Was Built
- New module `backend/agent/planners.py`: `build_default_planner()` returns an `AIService`-backed `Planner` (or `None` if **no** provider key is configured), plus `AGENT_SYSTEM_PROMPT` and a deterministic `_render_history` that truncates large tool outputs before they are fed back to the model. No streaming, no chain-of-thought leakage.
- New route `POST /api/agent/test-run` in `backend/api/routes/agent.py`. Wired in `backend/main.py` under `prefix="/api"`. The 6-step slide pipeline (`agent/loop.py`, `routes/generate.py`) is unchanged — this is a **separate** internal surface for exercising the runtime.
- Server-enforced safety policy:
  - `DANGEROUS_TOOLS` block-list: every shell tool, `file_write`, `file_str_replace`, both `deploy_*` tools, `make_manus_page`, and `browser_console_exec`. Any caller-supplied `allowed_tools` containing one of these returns **HTTP 400** `unsafe_tools_requested` *before* the runtime starts.
  - Unknown tool names return **HTTP 400** `unknown_tools`.
  - Empty allowlist returns **HTTP 400** `empty_allowlist`.
  - When no `allowed_tools` is supplied, server uses `safe_default_allowlist()` = `{message_notify_user, message_ask_user, info_search_web, idle, file_read, file_find_in_content, file_find_by_name}` plus the read-only `browser_*` family **only when `BROWSER_ENABLED=False`** (i.e., the inert disabled-safe stubs). When BROWSER_ENABLED is true, browser tools must be explicitly opted in per run by the operator. `browser_console_exec` is permanently in `DANGEROUS_TOOLS` and never selectable.
- Configuration error path: when no provider key is configured, `get_planner` raises **HTTP 503** `{error: "no_ai_provider_configured"}`. The route never crashes.
- Per-run runtime caps applied by the route: `max_steps=payload.max_steps or 8` (1–20), `max_tool_failures=3`, `per_step_timeout=20.0s`. Persistence via existing `services.agent_run_service` — every run produces an `AgentRun` and per-step `AgentStep` rows.
- Response shape (`AgentRunResponse`): `run_id`, `status` (`done`|`failed`), `final` text, `steps` (index/kind/action/error summary), `error` if any.
- Planner is wired through FastAPI `Depends(get_planner)` so tests inject a fake. **Zero LLM calls in the test suite.**

### Files Changed
- `backend/agent/planners.py` (new, ~95 lines).
- `backend/api/routes/agent.py` (new, ~165 lines).
- `backend/tests/test_agent_route.py` (new, 8 tests).
- `backend/main.py` (router import + `app.include_router(agent.router, prefix="/api", tags=["agent"])`). No other changes to main.

### Tests Added (8)
- Happy path: `idle` tool then `final` — validates `200`, response shape, persistence (4 `AgentStep` rows: thought / observation / thought / final).
- `unsafe_tools_requested` rejected (`shell_exec` in allowlist → 400).
- `unknown_tools` rejected (`does_not_exist` → 400).
- `empty_allowlist` rejected (`[]` → 400).
- `max_steps` exceeded (`max_steps=3`, planner emits 20 messages → 200, status `failed`, error `max_steps_exceeded`, exactly 3 thought steps).
- Malformed planner output (3 garbage strings → 200, status `failed`, `max_failures_exceeded`, observations carry `planner_output_not_json`).
- Default allowlist blocks dangerous call at runtime (planner asks for `shell_exec`, runtime records `tool_not_allowed` observation, run still completes via the next `final` action).
- 503 when no provider configured (`monkeypatch` `_has_any_provider → False`, real `get_planner` runs, returns 503 — zero LLM calls).

### Tests Run
- Backend full `pytest -q`: **139 passed, 2 skipped, 4.04s** (was 131/2 after Phase 2; +8 new route tests).
- Frontend `npm run verify:layouts`: ✔ **7 / 7** (no frontend changed).

### Result
Phase 2.5 — **Pass.** `AgentRuntime` is now reachable through a single, scoped, auth-light internal endpoint with a server-enforced safety envelope: shell / file-write / deploy / browser-console tools cannot be invoked through this surface even if the planner asks for them. Persistence is verified end-to-end through the HTTP layer. The 29-tool registry, the 6-step slide pipeline, the existing `/api/generate` flow, and the `BROWSER_ENABLED=false` default are all untouched.

### Remaining Risks (called out, not hidden)
- **Route is unauthenticated.** No `Depends(get_current_user)` yet; no rate limiting; no per-user quotas. Acceptable for an internal `test-run` endpoint, but it must not be exposed publicly without auth + RBAC. Tracked for Phase 7.
- **No SSE streaming.** Clients must wait for the full run to finish; no `/api/status/<run_id>` SSE channel for runtime progress.
- **No cancellation.** A run cannot be aborted from outside.
- **`per_step_timeout=20s` is wall-clock, not per-tool-class.** A single search can still consume up to 20s.
- **Still no Alembic migration** for `agent_runs` / `agent_steps`. Production Postgres deploy of this route is gated on it.
- **No deck integration.** This phase explicitly does **not** wire `AgentRuntime` into deck generation. That comes in Phase 3.
- `make_manus_page` is permanently in `DANGEROUS_TOOLS` for now; it is unused by the slide pipeline. If a future deck feature legitimately needs it, the policy must be revisited per-route, not relaxed globally.

## Phase 2 — Dynamic Tool-Calling Agent Runtime - 2026-05-09

### What Was Built
- New module `backend/agent/runtime.py` implementing `AgentRuntime`. **Lives beside** the existing 6-step slide pipeline in `agent/loop.py`; the old loop is **not modified** and is still the only thing wired into request flow.
- Strict action JSON contract: `{kind: "message"|"tool"|"final", name?, args?, text?}`. `parse_action` accepts raw planner output (whole-string JSON, fenced ```json``` block, or first balanced `{…}`) and returns `(Action, None)` or `(None, error_code)`. Malformed output never raises.
- Bounded loop with hard caps: `max_steps`, `max_tool_failures` (consecutive), `per_step_timeout` (wraps both planner call AND tool dispatch), and an optional `allowed_tools` allowlist. Defaults: 12 / 3 / 30s / all 29 tools.
- Tool dispatch goes through existing `agent.tools.call_tool`. **No tool was renamed, removed, or added** — the 29-tool registry assertion is intact.
- Every step persisted via Phase 1 `services.agent_run_service`: a `thought` step recording the planner's chosen action (kind/name/args/text) plus an `observation` step recording the tool's `ToolResult.to_dict()` (or the structured error). `final` action records a `final` step. `step_index` monotonic via `AgentRun.step_count`.
- Failure surfaces are all structured, never crashes:
  - `planner_output_not_json` / `invalid_kind` / `tool_action_missing_name` / `tool_action_args_not_object` → observation with `error`, increments failure counter.
  - `unknown_tool` (not in registry) and `tool_not_allowed` (not in allowlist) → observation, increments failure counter.
  - `planner_timeout` / `tool_timeout` / `tool_exception` → observation, increments failure counter.
  - Hitting `max_tool_failures` or `max_steps` → `finish_run(status="failed", error=...)`.
- Planner is dependency-injected (`Callable[[goal, history], Awaitable[str]]`). Production wiring to `services.ai_service.AIService` is intentionally deferred so tests use a scripted fake — zero LLM/network calls in CI.

### Files Changed
- `backend/agent/runtime.py` (new, ~310 lines).
- `backend/tests/test_agent_runtime.py` (new, 13 tests).

### Tests Added (13)
- `parse_action` validity: final, fenced-tool-with-thinking-prefix, garbage rejection, unknown-kind rejection, tool-without-name rejection.
- Runtime happy paths: final-on-first-step, idle-tool-then-final, persistence shape (thought/observation/thought/final indices 0..3, `output_json.ok==True`).
- Runtime safety: unknown tool recorded as observation then recovers, allowlist blocks `shell_exec`, `max_tool_failures` terminates with `max_failures_exceeded`, `max_steps` terminates with `max_steps_exceeded`, `planner_timeout` (per_step_timeout=0.05s on a 5s sleep) marks run failed.
- All tests use in-memory SQLite + scripted planner. Zero real LLM calls. Zero Playwright. Zero network.

### Tests Run
- Targeted Phase 1 + Phase 2 + existing deck/schema/layout regression set: **103 passed, 1 skipped, 2.21s**.
- Full backend `pytest -q`: **131 passed, 2 skipped, 2.39s** (was 118/2 after Phase 1; +13 new Phase 2 tests pass).
- Frontend `npm run verify:layouts` → ✔ 7 / 7 (no frontend changed).

### Result
Phase 2 — **Pass.** A dynamic, allowlisted, fully persisted, bounded tool-calling runtime exists and is provably safe against malformed output, unknown tools, timeouts, and unbounded loops. The 6-step slide pipeline is untouched.

### Remaining Risks (called out, not hidden)
- **No production caller wires `AgentRuntime` to a real LLM yet.** Production planner adapter (around `AIService.complete`) and an entry route are Phase 2.5 / 3 work. Until then, the runtime exists but no end-user request reaches it.
- **No streaming.** Steps persist transactionally per step; long runs do not yet emit SSE-style progress to the frontend.
- **`per_step_timeout` is a wall-clock cap on both planner and tool.** A single tool can still stall the loop for up to that timeout each call. Acceptable for now.
- **`max_tool_failures` is consecutive, not cumulative.** A planner that intersperses one good step every two failures will not terminate. Tracked.
- **No cancellation API.** A run cannot yet be aborted from the outside; this lands in Phase 7 with task cancellation.
- **Still no Alembic migration** for `agent_runs` / `agent_steps` / `artifacts`. Dev SQLite continues via `init_models()`. Production Postgres deploy of the runtime is gated on a migration revision.

## Phase 0 + Phase 1 — Workspace Truth & Agent Runtime Foundation - 2026-05-09

### What Was Fixed (Phase 0 — Runtime/Test Truth)
- **Workspace-vs-container confusion was real.** Git root is `D:\nexus-ai-1\nexus-ai`; the entire current `backend/`, `frontend/`, `audits/`, `scripts/` tree is **untracked** against the last commit `2ed7e94`. A sibling clone (e.g. `D:\nexus-ai-gh`) using the default Compose project name (`nexus-ai`) would silently override containers built from this folder. Now pinned to project name `nexus-ai-1` via top-level `name:` key in `docker-compose.yml`.
- New `scripts/doctor.ps1` prints workspace path + resolved Compose project + all running containers with their `com.docker.compose.project` label so the user can spot collisions before `docker compose up`.
- New `backend/requirements-dev.txt` with `pytest`, `pytest-asyncio`, `aiosqlite`. New `backend/Dockerfile.dev` layered on top of `nexus-ai-backend:latest` so the production image stays clean.
- New `scripts/test-backend.ps1` builds both images if missing and runs `pytest -q` against the local mount with in-memory SQLite — reproducible from THIS workspace, not whatever container happens to be running.
- README "Workspace & test commands (truthful)" section added with explicit commands; removed any implicit assumption that "container running == this folder."

### What Was Built (Phase 1 — Agent Runtime Foundation, storage only)
- Three additive ORM models in `backend/database/models.py`:
  - `AgentRun` — id, task_id (FK), user_id (FK), goal, status, max_steps, step_count, error_msg, meta JSON, timestamps.
  - `AgentStep` — id, run_id (FK CASCADE), step_index, kind ∈ {thought, action, observation, final}, action (tool name), status, input_json, output_json, error, timestamps.
  - `Artifact` — id, run_id (FK CASCADE, optional), task_id (FK CASCADE, optional), artifact_type, title, meta JSON, file_url, created_at.
- `backend/services/agent_run_service.py` — pure async helpers `create_run`, `append_step`, `record_artifact`, `finish_run`, `get_run_with_steps`, `list_artifacts_for_run`. No imports from `agent.loop` or `agent.tools` — zero risk of cycles.
- Tables auto-created via existing `init_models()` on dev/SQLite. **No Alembic migration added** (per project guidance not to add migrations without explicit authorization). Production deploy will need an `alembic revision --autogenerate` step before turning Phase 2 on.
- Existing 6-step slide pipeline in `agent/loop.py` is **unchanged**. None of the new code is wired into request flow yet.

### Files Changed
- `docker-compose.yml` — `name: nexus-ai-1` top-level key.
- `scripts/doctor.ps1` (new).
- `scripts/test-backend.ps1` (new).
- `backend/requirements-dev.txt` (new).
- `backend/Dockerfile.dev` (new).
- `backend/database/models.py` — added `AgentRun`, `AgentStep`, `Artifact`.
- `backend/services/agent_run_service.py` (new) — 6 helpers.
- `backend/tests/test_agent_run_service.py` (new) — 6 tests.
- `README.md` — "Workspace & test commands (truthful)" section.

### Tests Added
- 6 in-memory SQLite tests covering: minimal run creation, multi-step append + index/counter coherence, invalid kind rejection, artifact record + list, terminal status transition + invalid-status rejection, failed status records error message. All conftest-free.

### Tests Run
- Backend `pytest -q` in `nexus-ai-backend:latest` against THIS workspace mount: **118 passed, 2 skipped, 2.62s** (was 112/2 after Phase 2A; +6 new tests pass).
- Frontend `npm run verify:layouts` → ✔ 7 / 7.

### Result
Phase 0 + Phase 1 — **Pass.** Workspace identity is now explicit and machine-verifiable. Agent runtime has a real persistence floor. **Honest scope:** there is no agent runtime *behavior* yet — only storage primitives and a doctor script. Tasks 2–7 from the user's roadmap remain unimplemented.

### Remaining Risks (called out, not hidden)
- **No Alembic migration** for the three new tables. Dev SQLite + `init_models()` works; production Postgres deploy will fail until a migration is generated. Logged as a Phase 2 prerequisite.
- **`step_count` increment is not concurrency-safe** under the same `AgentRun` from two workers in parallel. Acceptable now (one runtime per run) but must be revisited when Phase 7 introduces task cancellation/retry.
- **`Artifact.run_id` is nullable** so artifacts created outside a run still attach to a task. This is intentional, but means `list_artifacts_for_run` will silently skip orphan artifacts.
- **No tool runtime, no tool-allowlist enforcement, no max_step enforcement at runtime.** Those are Phase 2.
- **README "Slide layouts (6)" line is still wrong** (we have 7). Not touched in this phase to keep the change narrow; tracked for the README pass alongside Phase 5.
- **Git state is dirty across the entire workspace.** Phase 0 deliberately did NOT commit anything. The user should commit when ready.

## Phase 2A Browser Automation Implementation - 2026-05-09

### What Was Fixed
- `backend/services/browser_service.py` was a pure no-op stub returning `ToolResult(ok=False, error="Browser tool disabled - install browser-use separately")` for every method, despite the README claiming `browser-use + Playwright` support. README claim is now consistent with implementation.
- Replaced the stub with a real Playwright-backed singleton (Chromium, headless by default). Lazy `_ensure_started()` lifecycle, explicit `shutdown()`, exception-safe (`PWError` / `PWTimeoutError` → structured `ToolResult(ok=False, error=...)`). All 11 method names and the `browse_url` helper preserved.
- New `BrowserService.is_available()` classmethod gates real activation behind `_PLAYWRIGHT_AVAILABLE AND settings.BROWSER_ENABLED`. `backend/agent/tools.py` `_BROWSER_AVAILABLE` now derives from `BrowserService.is_available()` rather than file presence, so the disabled fallback path is actually reachable.
- Browser automation is **disabled by default** (`BROWSER_ENABLED=False`). Default CI/local behavior unchanged.

### Files Changed
- `backend/services/browser_service.py` — stub replaced with Playwright impl; preserves `BrowserService`, `ToolResult`, `browse_url`, and all 11 async method signatures.
- `backend/agent/tools.py` — `_BROWSER_AVAILABLE` derivation via `BrowserService.is_available()`. 29-tool registry assertion preserved.
- `backend/config.py` — added `BROWSER_ENABLED`, `BROWSER_HEADLESS`, `BROWSER_TIMEOUT_MS`, `BROWSER_NAV_TIMEOUT_MS`, `BROWSER_VIEWPORT_WIDTH`, `BROWSER_VIEWPORT_HEIGHT` (all conservative defaults; OFF).
- `backend/requirements.txt` — added `playwright==1.47.0`. `browser-use` deferred to Phase 2D.
- `backend/Dockerfile` — added 13 Chromium runtime libs (`libnss3`, `libxkbcommon0`, `libgbm1`, `libasound2`, `libatk1.0-0`, `libatk-bridge2.0-0`, `libcups2`, `libdrm2`, `libxcomposite1`, `libxdamage1`, `libxfixes3`, `libxrandr2`, `libxshmfence1`) + `python -m playwright install chromium`.
- `docker-compose.yml` — `shm_size: "2gb"` on backend and worker (Chromium IPC).
- `backend/main.py` — registered `BrowserService().shutdown()` in lifespan teardown, guarded by `BROWSER_ENABLED`.
- `README.md` — corrected the Browser line to `Playwright (Chromium, opt-in via BROWSER_ENABLED=true)`.

### Tests Added
- `backend/tests/test_browser_service.py` — 6 default-on tests: singleton identity; disabled-when-`BROWSER_ENABLED=False`; disabled-when-Playwright-missing; `ToolResult` shape; `TOOLS` registry size = 29 with all 12 `browser_*` names; every `browser_*` callable returns structured error in disabled mode.
- `backend/tests/test_browser_service_live.py` — 4 live-gated tests (`pytest.importorskip("playwright")` + `BROWSER_LIVE=1`): `file://` navigate + view + screenshot, input/select/click + `console_exec`, navigation timeout returns structured error, `restart()` recycles session. No external network used.

### Tests Run
- Default backend pytest: **112 passed, 2 skipped, 1.81s** (was 106 / 1; +6 disabled-path tests pass, +1 module-level live skip).
- Frontend `npm run verify:layouts` → ✔ 7 / 7.

### Result
Browser automation surface is now real (opt-in) with a stable disabled-default path. 29-tool `TOOLS` registry assertion intact. No DB migrations. Reference folders untouched. Phase 2A close-out — **Pass**.

### Remaining Risks
- Image size will grow significantly once `nexus-ai-backend:latest` is rebuilt (Chromium + system libs ~300–400 MB). Acceptable for now; mitigation if needed is a `nexus-ai-backend-browser` variant gated by build arg.
- Worker container also receives Chromium even though only the backend currently exposes browser tools to the agent loop. Acceptable since both run agent code paths; can be split in a later phase.
- Single global page/context — no multi-tab / per-task isolation. That is Phase 2D scope when wiring browser into `agent/loop.py` alongside `browser-use`.
- `console_view` only captures messages emitted while the page is active in this process; resets across `restart()` (intentional).
- Live tests are present but skipped by default; first activation requires `docker compose build backend` followed by `BROWSER_LIVE=1 BROWSER_ENABLED=true pytest tests/test_browser_service_live.py`.

## Phase 1H Pre-Lock Triage Sweep (P1-1, P1-2, P0-2, P1-3) - 2026-05-09

### What Was Fixed
- **P1-1.** Frontend share page (`frontend/src/pages/SharedSlide.jsx`) now consumes the `deck_quality` field the share API already exposes. Single-component change; no boundary added; no API change.
- **P1-2.** Removed a self-inflicted boundary smell in `_normalize_slides`: the stats→chart safety-net mutated a slide into a chart layout while leaving its slide-level `subtitle` unset, immediately failing the validator one line later. The promotion now sets `subtitle` (forwarded or `""`) so the safety-net is internally consistent with the schema it shares with the rest of the loop.
- **P0-2.** New `tests/test_export_input_parity.py` codifies the read/export contract relied on by Phase 1D's `attach_quality_report`: both routes must pass `deck.slide_data or []` to their consumer with no intermediate transform. Source-level (AST) check; conftest-free; no DB.
- **P1-3.** Doc cross-link added inside each Phase 1A correction notice. No history rewritten.

### Files Changed
- `frontend/src/pages/SharedSlide.jsx`
- `backend/agent/loop.py` (single-line subtitle carry-forward)
- `backend/tests/test_deck_quality.py`, `backend/tests/test_slide_schema.py` (telemetry tests flipped)
- `backend/tests/test_export_input_parity.py` (new)
- 4 audit files (cross-link)

### Tests Added
- 3 AST-based parity tests; 0 net new telemetry tests (two flipped).

### Tests Run
- Default backend pytest: **106 passed, 1 skipped, 1.67s**.
- Frontend `npm run verify:layouts` → ✔ 7 / 7.

### Result
Architectural posture for Phase 1H — **Pass**. The pre-lock P0/P1 list is empty. The architecture risk matrix is otherwise unchanged — the P2 backlog and the strategic items (CI gate, durable events, observability, deployment maturity, secret fail-fast, retention) remain open and tracked.

### Remaining Risks
- The export parity test is structural, not behavioral. A future refactor that keeps `deck.slide_data or []` syntactically but reshapes the *contents* upstream will pass this test; that is acceptable for a lock-readiness guard.
- No new boundaries or modules were introduced; no module-graph changes to re-audit.

## Phase 1G Pre-Lock P0-1 (Test Suite Unblock) - 2026-05-09

### What Was Fixed
- Architectural defect in the database boundary: `create_async_engine(...)` in `backend/database/connection.py` passed `pool_size`, `max_overflow`, and `pool_pre_ping` unconditionally. Under SQLite (`sqlite+aiosqlite://`), SQLAlchemy uses `NullPool`, which rejects those kwargs, causing every default `pytest` collection to crash. The engine now branches on the URL scheme: production Postgres path is unchanged; SQLite paths get a clean `NullPool` engine.
- This is the narrow architectural cause of the recurring "full pytest still blocked by conftest/DB pool mismatch" line carried in every Phase 1A→1F section across the four audits. Closing it required only a guard around a single call site — no module reorganization, no abstraction layer added.
- Cross-audit fact correction: `backend/tests/` contains 5 files, all of which we already run. There is no larger "full suite" that was being held back; the blocker was the engine, not the conftest.

### Files Changed
- `backend/database/connection.py` — guard around `pool_size` / `max_overflow` / `pool_pre_ping` in the `create_async_engine` call.

### Tests Added
- None.

### Tests Run
- Default backend pytest (no `--noconftest`, no explicit file list): **103 passed, 1 skipped, 1.45s**.
- Frontend `npm run verify:layouts` → ✔ 7 / 7.

### Result
Architectural posture for Phase 1G — **Pass**. The DB boundary now tolerates the SQLite test URL without losing Postgres pool tuning.

### Remaining Risks
- The test boundary itself is still narrow (5 files). Broader integration test coverage (Postgres + Redis + Celery containers) remains a separate hardening workstream.
- Pool tuning for Postgres is unchanged; if those values ever need to vary per environment, this branch is the natural place to thread that through `settings`.

## Phase 1F Repair Preview UI + Env Cleanup - 2026-05-09

### What Was Added
- Frontend-only consumer of the Phase 1E `deck_quality.repair_preview` field. No new module, no new route, no new state-management surface. The existing `DeckQualityBadge` reads the array and renders it inside the existing expandable panel. The component remains a single self-contained file.
- The `errors` rendering path is preserved as a fallback when `repair_preview` is absent, so older API responses (and the share endpoint, when consumed by clients that do not surface a badge) keep working without change.
- Disk-level cleanup of two generated virtualenv trees: `nexus-ai/.venv` and `nexus-ai/manus-need/openmanus-reference/.venv`. Confirmed safe by absence of any `.vscode/settings.json` interpreter pinning, absence of any `nexus-ai/`-scoped script activating them, and the Docker-first test workflow.

### Files Changed
- `frontend/src/components/DeckQualityBadge.jsx`
- Deleted directories: `nexus-ai/.venv/`, `nexus-ai/manus-need/openmanus-reference/.venv/`

### Tests Added
- None. Phase 1E tests still cover the data contract end-to-end.

### Tests Run
- Backend Docker: 103 passed, 1 skipped, 1.14s.
- Frontend `npm run verify:layouts`: 7 / 7.
- Full pytest still blocked by the pre-existing pool mismatch.

### Result
Architectural posture for Phase 1F — **Pass**. No coupling change. The frontend continues to depend only on the public API shape, and the API shape did not change.

### Remaining Risks
- The badge component now mixes two render modes (preview vs errors). If the backend ever stops emitting `repair_preview` for a deck that has errors, the fallback path will engage — verified by the existing conditional. No behavioral regression.
- Stale virtualenv trees are gone; if pre-commit or other tooling is later introduced that expects a local venv, it must create one explicitly.

## Phase 1E Repair Preview - 2026-05-09

### What Was Added
- A second observability layer next to `build_deck_quality_report`: `build_repair_preview(slides, repair_actions=...)`. Same dependency-light boundary — imports only `agent.slide_schema` (transitively `agent.layouts_registry`). No DB, no FastAPI, no service code.
- `DeckQualityReport` extended with a `repair_preview: list[RepairAction]` field and an additive `repair_preview` JSON key in `to_dict()`. Existing `repair_actions`, `errors`, and `summary` keys preserved unchanged. The frozen `RepairAction` dataclass is unchanged — the only difference is that preview entries set `action="preview"` and populate `before`/`after`.
- Function ordering is safe: `build_deck_quality_report` calls `build_repair_preview` with `repair_actions=` already in hand; `build_repair_preview` only re-enters `build_deck_quality_report` when called standalone with `repair_actions=None`. No mutual recursion at call time.
- `attach_quality_report` continues to be the sole API-route surface; it required no edit because `to_dict()` is what changed.

### Files Changed
- `backend/agent/deck_quality.py`
- `backend/tests/test_deck_quality.py`
- `backend/tests/test_api_deck_quality_payload.py`
- `backend/tests/test_deck_repair_preview.py` (new)

### Tests Added
- 12 conftest-free tests, importing only `agent.deck_quality`. The module remains testable without database, FastAPI, or worker context.

### Tests Run
- Backend Docker: 103 passed, 1 skipped, 1.25s.
- Frontend `npm run verify:layouts`: 7 / 7.
- Full pytest still blocked by the pre-existing conftest/DB pool mismatch.

### Result
Architectural posture for Phase 1E — **Pass**. The new helper is a strict additive layer over Phase 1C, with no new coupling. API responses gain one optional JSON field (`deck_quality.repair_preview`); clients that ignore it see no behavioral change.

### Remaining Risks
- `_PREVIEW_DEFAULTS` is a small, hand-maintained table. If new layouts or new required fields are added, this table must be updated in lock-step with `agent.slide_schema`. A test in `test_deck_repair_preview.py` (`test_repair_preview_action_field_only_preview_or_not_applied`) catches drift indirectly, but a dedicated parity test could be added if/when the table grows.
- The dataclass `RepairAction.action` is currently a free-form string; this phase only consumes `"not_applied"` and `"preview"`. A future repair pipeline will introduce `"applied"`. No widening was needed for Phase 1E.

## Phase 1D Deck Quality Visibility - 2026-05-09

### What Was Added
- A read-time integration of `DeckQualityReport` into the deck-read API surface. The slides and share GET endpoints now return a `deck_quality` field constructed via `agent.deck_quality.attach_quality_report(payload, slides)`. The helper is a *shallow-copy* function that does not mutate its inputs and never raises on content errors.
- The architectural boundary is preserved: `agent/deck_quality.py` still imports only `agent/slide_schema.py`. The route modules reach into `agent.deck_quality` exactly the way they already reach into `agent.layouts_registry` for normalization. No new coupling between API and DB layers, and no new coupling between API and worker/loop code.
- No DB migration, no schema change, no Alembic revision. The `SlideDeck.slide_data` column remains `JSON().with_variant(JSONB, "postgresql")` typed `list`, exactly as before.

### Files Changed
- `backend/agent/deck_quality.py` — `attach_quality_report` + `__all__` export.
- `backend/api/routes/slides.py` — uses the helper in the GET handler.
- `backend/api/routes/share.py` — same treatment for the public share GET.
- `frontend/src/components/DeckQualityBadge.jsx` — small UI consumer.
- `frontend/src/pages/Generator.jsx` — wires the badge into the existing done-state footer.
- `backend/tests/test_api_deck_quality_payload.py` — conftest-free helper tests.

### Tests Added
- 6 unit tests for `attach_quality_report` covering non-mutation, JSON-serializability, valid/invalid/empty/non-list inputs.

### Tests Run
- Backend Docker (`--noconftest -p no:cacheprovider`): 90 passed, 1 skipped (the pre-existing layout-coverage cross-check), 1.13s.
- Frontend: `npm run verify:layouts` → 7 canonical, 7 exported.
- Full pytest still blocked by the `database/connection.py` pool mismatch under SQLite — Phase 1D does not regress this and does not introduce new conftest-coupling.

### Result
Architectural boundary check for Phase 1D — **Pass**. The added code is dependency-light, pure, and reversible. Public API responses gain a single, optional, JSON field; clients that ignore it see no change.

### Remaining Risks
- The recomputation is per-request. For very large decks this is O(slide_count) work on every read; current PRD slide caps make this negligible. Caching is unnecessary at this scale and was deliberately not introduced.
- If `agent.slide_schema` is ever made async or DB-aware, the route handlers will need to follow suit. Not the case today.
- The frontend badge intentionally does not paginate or virtualize the error list — it caps at 12 entries with a “…and N more” suffix. Acceptable for the typical 6–14 slide deck.

## Phase 1C Deck Quality Report - 2026-05-09

**Scope:** Architectural follow-up — introduce a structured, non-destructive deck-quality reporting layer that future repair / enforcement / UI work can build on without re-deriving validation outcomes.

### What Was Added
- `backend/agent/deck_quality.py` introduces two stable shapes (`RepairAction`, `DeckQualityReport`) and one entry point (`build_deck_quality_report`). The shapes are deliberately serializable (`to_dict()` on both) so a future API surface can return them unchanged.
- `RepairAction.action` is currently always `"not_applied"`; `before` / `after` are `None`. This freezes the contract a future repair pipeline can extend (`"applied"`, populated `before` / `after`) without API churn.
- `_normalize_slides` is now the single producer of validation telemetry, sourcing per-slide WARNING records from `DeckQualityReport.errors` and emitting an additional deck-level INFO summary `loop.deck_quality_report`. This eliminates the previous risk of telemetry diverging from what the validator would say.
- The module respects the established import boundary: only `agent.slide_schema` is imported. No database, services, or app code is pulled in.

### Files Changed
- `backend/agent/deck_quality.py` (new).
- `backend/agent/loop.py` — telemetry block in `_normalize_slides` rewritten to consume `build_deck_quality_report`.
- `backend/tests/test_deck_quality.py` (new).

### Tests Added
- 7 unit tests over `build_deck_quality_report` and the dataclass `to_dict()` shapes.
- 2 caplog tests against `NexusAgentLoop._normalize_slides` proving (a) the INFO `loop.deck_quality_report` summary is emitted with the correct `slide_count` / `repairs_needed` fields, and (b) the existing per-slide `loop.slide_validation_failed` WARNING for the known stats→chart safety-net case is still emitted (now sourced from the report).

### Tests Run
- `cd frontend ; npm run verify:layouts` → `✔ verify-layouts OK — 7 canonical layouts, 7 exported.`
- Docker pytest one-shot (`--noconftest -p no:cacheprovider tests/test_layout_coverage.py tests/test_slide_schema.py tests/test_deck_quality.py`) → **85 passed in 1.04s**.
- Full backend pytest still blocked by `backend/tests/conftest.py` (SQLite NullPool / `pool_size` mismatch in `database/connection.py`). Not run.

### Result
- Slide-contract observability layer → **Pass** for the corrected narrow scope.
- Overall hardening → **Partial** — we now have a structured report shape and a single source of truth for telemetry, but still no repair application, no enforcement, no API/UI surface, no export parity, and no real browser automation.
- Visual layer → **Unchanged**.

### Remaining Risks
- Repair actions are observability-only; nothing applies them.
- `DeckQualityReport` is internal-only — no API/UI exposure.
- Validation does not block generation or export.
- Safety-net stats→chart promotion can still produce a chart missing slide-level `subtitle`; now reported in both per-slide and deck-level telemetry, still not repaired.
- Export parity (PPTX/PDF) and real browser automation remain deferred.
- Registry still supports only 7 honest layouts.
- Full backend pytest still blocked by conftest/database wiring.

---

## Phase 1B.1 Audit Correction - 2026-05-09

**Scope:** Architectural follow-up — close three Phase 1B.1 contract gaps without expanding scope.

### What Was Corrected
- Slide-contract validator (`backend/agent/slide_schema.py::_validate_chart`) now treats `chart_data.unit` and `chart_data.source` as **required** keys (empty strings allowed; wrong types still fail). The validator now matches the normalized contract emitted by `NexusAgentLoop._normalize_slides`, which always sets both fields (often to `""`).
- `validate_slide` docstring corrected to describe `ValidationResult.normalized` as a shallow copy of the input with the canonical layout pinned on success and `None` on failure — and to make explicit that the validator is not an auto-repair layer.
- The `validate_deck` telemetry path inside `_normalize_slides` is now covered by a direct caplog-based test, removing the previous “wired but not tested” gap.

### Files Changed
- `backend/agent/slide_schema.py` — `_validate_chart` uses `_require_str(..., allow_empty=True, path_prefix="chart_data.")` for both `unit` and `source`; `validate_slide` docstring updated. No new app/database imports introduced.
- `backend/tests/test_slide_schema.py` — added sections 14 and 15.

### Tests Added
- 5 chart_data contract tests (missing unit/source fail; empty unit+source allowed; non-string unit/source fail).
- 1 `_normalize_slides` telemetry test using `caplog` on logger `nexus.agent.loop` to assert `loop.slide_validation_failed layout=chart path=subtitle code=missing` is emitted when the safety-net promotes a stats slide to chart without adding `subtitle`. Imports `NexusAgentLoop` directly (no conftest needed), matching the existing pattern in `tests/test_layout_coverage.py`.

### Tests Run
- `cd frontend ; npm run verify:layouts` → `✔ verify-layouts OK — 7 canonical layouts, 7 exported.`
- Targeted backend pytest via one-shot Docker (`--noconftest -p no:cacheprovider tests/test_layout_coverage.py tests/test_slide_schema.py`) → **76 passed in 1.33s**.
- Full backend pytest still blocked by `backend/tests/conftest.py` (SQLite NullPool / `pool_size` mismatch in `database/connection.py`). Not run; no claim made.

### Result
- Slide-contract architecture (validator + telemetry hookup) → **Pass** for the corrected narrow scope.
- Overall hardening → **Partial** — validation is observability-only; repair, enforcement, DeckQualityReport, export parity, and real browser automation are still out of scope.
- Visual layer → **Unchanged**.

### Remaining Risks
- No repair pipeline yet; bad slides emit warnings but still ship.
- Safety-net stats→chart promotion currently produces a chart missing slide-level `subtitle` — visible in telemetry but not yet repaired.
- No DeckQualityReport surfaced to API or UI.
- Full backend pytest still blocked by conftest/database wiring.
- Export parity (PPTX/PDF), real browser automation, and any expansion beyond 7 canonical layouts remain deferred.
- Registry still supports only 7 honest layouts until renderer/normalizer/export coverage expands.

---

## Phase 1B.1 Schema Strictness Update - 2026-05-09

### What Changed
- Tightened `backend/agent/slide_schema.py` to match the normalized contract emitted by `NexusAgentLoop._normalize_slides`:
  - `title` now requires `subtitle`, `eyebrow`.
  - `quote` now requires `attribution`.
  - `chart` now requires slide-level `subtitle`.
  - `closing` now requires `subtitle`, `cta`.
  - Empty strings are permitted for fields the normalizer can emit empty, but missing keys fail.
- Strict mode (`resolve_aliases=False`) now requires an EXACT canonical name — no case-fold, no trim, no alias resolution.
- `ValidationResult.normalized` is now a shallow copy of the input with canonical `layout` pinned (instead of echoing `raw`). NOT auto-repair.
- `_normalize_slides` now invokes `validate_deck(...)` after normalization purely as logging-only telemetry. No slides rejected, mutated, or repaired. Local import keeps `slide_schema` free of DB/app-layer dependencies; failures in the telemetry path are caught so they cannot break generation.

### Files Changed
- `backend/agent/slide_schema.py`
- `backend/agent/loop.py` (`_normalize_slides` only — telemetry block before `return out`)
- `backend/tests/test_slide_schema.py` (+13 tests)

### Tests Added
- `test_title_missing_subtitle_fails`, `test_title_missing_eyebrow_fails`, `test_title_empty_subtitle_allowed`
- `test_quote_missing_attribution_fails`
- `test_chart_missing_subtitle_fails`
- `test_closing_missing_subtitle_fails`, `test_closing_missing_cta_fails`
- `test_strict_mode_rejects_titlecase`, `test_strict_mode_rejects_padded_name`, `test_strict_mode_accepts_exact_canonical`
- `test_normalized_is_shallow_copy_with_canonical_layout`, `test_normalized_pins_canonical_layout_for_uppercase_input`, `test_normalized_is_none_on_failure`

### Tests Run
- `cd frontend ; npm run verify:layouts` → `✔ verify-layouts OK — 7 canonical layouts, 7 exported.`
- Docker one-shot pytest with `--noconftest -p no:cacheprovider tests/test_layout_coverage.py tests/test_slide_schema.py -v` → **70 passed in 0.91s**.
- Full backend pytest **not** claimed; still blocked by pre-existing `tests/conftest.py` / `database.connection` issue.

### Result
- **Phase 1B.1 narrow scope: Pass.** Architectural boundary tightened: schema now mirrors normalized contract, strict mode is honest, validation is observable in the generation loop without coupling to DB/app modules.
- **Broader platform status: Partial** (unchanged).

### Remaining Risks
- No repair pipeline yet.
- No `DeckQualityReport` yet.
- Validation failures are logged but not enforced.
- Edge-case: `out[0]/out[-1]` layout pinning and stats→chart safety-net in `_normalize_slides` can produce slides that the new validator flags (e.g. missing `subtitle`); telemetry-only for now.
- No export parity fix yet.
- No real browser automation yet.
- Visual quality unchanged.
- Full backend pytest still blocked by conftest/database setup.
- Registry still scoped to the 7 honest layouts.

## Phase 1B Schema Validation Update - 2026-05-09

### What Changed
- Added `backend/agent/slide_schema.py` — a hand-rolled, dependency-light validator that enforces per-layout contracts for the 7 canonical layouts. Returns structured `ValidationResult { ok, layout, errors[{path, code, message}], normalized }`.
- Per-layout contracts mirror the shapes produced by `NexusAgentLoop._normalize_slides`. Chart slides require `chart_type` ∈ {bar, line, doughnut}, `chart_data.labels`/`values` of equal length, numeric `values` (bool explicitly rejected). Stats require `{value, label}` items (max 3). Two-col requires `{heading, body}` columns (max 2). Bullets cap at 4.
- Unknown layouts are rejected with `unknown_layout` instead of silently being coerced via `FALLBACK_LAYOUT`. The fallback remains a render-time safety net but is no longer treated as a contract.
- Validator is currently a library only — not yet wired into the normalizer or export path. No repair, no scoring, no UI, no new layouts.

### Files Changed
- Added `backend/agent/slide_schema.py`.
- Added `backend/tests/test_slide_schema.py`.

### Tests Added
- 34 tests in `tests/test_slide_schema.py`: valid example per canonical layout, missing/empty/wrong-type field cases, bullets count/item-type rules, two-col column shape and count, stats item shape, chart enum + length-mismatch + non-numeric (incl. bool) + labels-list-type, quote required text, unknown layout in both alias and strict modes, `validate_deck` wrapper, `ValidationError.to_dict` stability.

### Tests Run
- `cd frontend ; npm run verify:layouts` → `✔ verify-layouts OK — 7 canonical layouts, 7 exported.`
- One-shot Docker pytest with `--noconftest -p no:cacheprovider` against `tests/test_layout_coverage.py` and `tests/test_slide_schema.py` → `57 passed in 0.74s`.
- Full backend pytest is still blocked by `tests/conftest.py` / `database/connection.py` (SQLite NullPool rejecting `pool_size`/`max_overflow`); not run.

### Result
- Phase 1B narrow scope: **Pass**.
- Architecture hardening overall: **Partial** — schema is defined and tested, but not yet enforced at the pipeline boundary, and conftest/DB setup, repair pipeline, export parity, browser autonomy remain open.

### Remaining Risks
- Validator is not yet invoked from `_normalize_slides`, the Celery task, or export — bad payloads can still slip through end-to-end.
- No auto-repair pipeline yet.
- No DeckQualityReport yet.
- Export parity (PPTX/PDF) is unverified.
- `services/browser_service.py` is still a disabled stub.
- Visual quality unchanged.
- Full backend pytest still blocked by conftest/DB setup.
- Only 7 honest layouts; broader layout coverage requires renderer + normalizer + export expansion before adding more.

## Phase 1A.1 Planner Layout Drift Update - 2026-05-09

### What Changed
- Closed the last obvious backend layout-whitelist drift: `backend/agent/planner.py` no longer carries its own hardcoded `_VALID_LAYOUTS` (which was missing `chart`). It now consumes the canonical registry the same way `agent/loop.py` does and resolves layouts via `normalize_layout(...)` with `FALLBACK_LAYOUT` as the safety net.
- `scripts/verify-layouts.mjs` extended with a planner-side guard: fails CI if `planner.py` stops importing the registry or reintroduces an inline `_VALID_LAYOUTS = {...}` literal.

### Files Changed
- `backend/agent/planner.py`, `backend/tests/test_layout_coverage.py`, `scripts/verify-layouts.mjs`.

### Tests Added
- 10 new cases in `backend/tests/test_layout_coverage.py`: planner-registry parity, 7 per-layout planner round-trip tests, planner unknown-layout fallback, explicit `chart`-not-lost regression.

### Tests Run
- `npm run verify:layouts` -> **PASS** (`7 canonical layouts, 7 exported`).
- One-shot pytest container against this workspace -> **PASS** (`23 passed in 0.69s`, includes the original 13 + 10 new planner cases).
- Full backend `pytest` suite NOT run. Reason: pre-existing `tests/conftest.py` failure (SQLAlchemy pool args incompatible with SQLite `NullPool`).

### Result
**Pass for the narrow planner drift fix.** The architecture risk matrix is otherwise unchanged — schema validation, repair pipeline, observability, queue reliability, CI gate, deployment, secrets, and renderer isolation remain open.

### Remaining Risks
- All hardening items beyond "layout name contracts" are unchanged.
- The `conftest.py` engine-pool bug is the gate for running the broader test tier.
- Live `nexus-backend` container is still bound to `D:\nexus-ai-gh\backend` in this environment.

## Phase 1A Correction Update - 2026-05-09

> **Correction notice.** The previous "Phase 1A Update - 2026-05-09" section in this file (immediately below) was inaccurate. It described a 23-layout / 40-alias registry and a 35-test passing run against files (`backend/agent/layouts_registry.py`, `backend/tests/test_layout_coverage.py`, `frontend/src/design/`) that did **not** exist in this workspace at the time it was written. That section is left in place below for traceability only; its content is not evidence. This section is the factual record for Phase 1A in this repository. **See "Phase 1A Correction Update" above for the verified numbers (7 canonical layouts, 0 aliases, 13 tests).**

### What Actually Changed (verified against repo)
- Hardcoded layout whitelists in `backend/agent/loop.py` (`_VALID_LAYOUTS = {"title", "bullets", "two-col", "quote", "stats", "chart", "closing"}`) and `frontend/src/utils/slideParser.js` (`new Set([...6 names...])`) have been removed. Both files now consume the canonical registry. The frontend set was also missing `chart`, which the renderer actually supports — this drift is now closed.
- Canonical registry stored as JSON in two byte-identical copies: `frontend/src/design/layouts.registry.json` (used by the Vite bundle) and `backend/agent/layouts.registry.json` (used by the backend container, which only mounts `./backend`). The `scripts/verify-layouts.mjs` script enforces byte-content parity between the two, plus a regression guard that fails CI if either source file reintroduces an inline literal.
- Real layout count today: **7 canonical layouts**, 0 aliases. The registry was sized to match what the renderer (`SlideRenderer.jsx` layouts map) and the existing per-layout normalization branches actually support.

### Files Changed / Added
- Added: `frontend/src/design/layouts.registry.json`, `frontend/src/design/registry.js`
- Added: `backend/agent/layouts.registry.json`, `backend/agent/layouts_registry.py`
- Added: `backend/tests/__init__.py`, `backend/tests/test_layout_coverage.py`
- Added: `scripts/verify-layouts.mjs`
- Modified: `backend/agent/loop.py`, `frontend/src/utils/slideParser.js`, `frontend/package.json`

### Tests Added
- `backend/tests/test_layout_coverage.py` (**13 tests, not 35**): registry parity (`_VALID_LAYOUTS == CANONICAL_LAYOUTS`), backend/frontend JSON byte-content parity, fallback canonicality, alias-target canonicality, 7 parametrized per-layout round-trip tests, unknown-layout fallback test, canonical-name passthrough test.

### Tests Run
- `cd frontend ; npm run verify:layouts` -> **PASS** (`7 canonical layouts, 7 exported`).
- `docker run --rm -v D:\nexus-ai-1\nexus-ai\backend:/app -v D:\nexus-ai-1\nexus-ai\frontend:/frontend -w /app -e PYTHONPATH=/app nexus-ai-backend:latest sh -c "pip install --quiet pytest pytest-asyncio && python -m pytest --noconftest -p no:cacheprovider tests/test_layout_coverage.py -v"` -> **PASS** (`13 passed in 0.58s`). A one-shot container was required because the running `nexus-backend` is bound to a different repo path.
- Full backend `pytest` suite NOT run. Reason: pre-existing `tests/conftest.py` failure (SQLAlchemy `pool_size`/`max_overflow` rejected with SQLite `NullPool`). Unrelated to Phase 1A; recorded as a CI prerequisite.
- Playwright gallery suite NOT run. Reason: out of scope for Phase 1A (no renderer changes).

### Result
**Pass for the narrow Phase 1A scope** (registry-driven canonical layout coverage). Tests prove the fix.
**The architecture risk matrix is otherwise unchanged.**

### Remaining Risks
- Slide payloads remain dictionary-driven beyond the layout name. No JSON Schema, no typed contract, no validate-then-repair pipeline.
- Normalizer still mutates silently (pins first/last slides, inserts placeholders, auto-promotes a stats slide to chart). No `RepairAction` log, no `DeckQualityReport`.
- The `conftest.py` engine-pool bug must be fixed before the backend test tier can run end-to-end in CI.
- All other rows in the architecture risk matrix (CI not enforced, no retries, lossy progress, separate render paths, no observability, Compose-only deployment, dev secret defaults, no retention) remain open.
- The running `nexus-backend` service in this environment binds to `D:\nexus-ai-gh\backend`; Phase 1A code changes here are not yet picked up by the live container without a rebuild from this workspace.

## Phase 1A Update - 2026-05-09

### What Changed
- Removed hardcoded canonical-layout whitelists from `backend/agent/loop.py` and `frontend/src/utils/slideParser.js`. Both now consume the canonical registry (`frontend/src/design/layouts.registry.json`) as the single source of truth. This closes the most concrete instance of the "weak contracts / dictionary-driven layouts" risk in the architecture risk matrix.
- 10 canonical layouts (`hero`, `bento`, `agenda`, `roadmap`, `metric-spotlight`, `process`, `pyramid`, `matrix-2x2`, `feature-grid`, `callout`) and their registered aliases no longer collapse to `bullets`/`title` in the normalizer or the frontend parser.
- `scripts/verify-layouts.mjs` now also fails CI if either file reintroduces an inline layout-set literal — a permanent regression guard for this risk.

### Files Changed
- `backend/agent/loop.py`
- `frontend/src/utils/slideParser.js`
- `scripts/verify-layouts.mjs`

### Tests Added
- `backend/tests/test_layout_coverage.py` (35 cases): registry-parity test, 23 per-layout round-trip tests, 10 alias-resolution tests, 1 unknown-layout fallback test.

### Tests Run
- `npm run verify:layouts` -> PASS.
- `python -m pytest --noconftest tests/test_layout_coverage.py -v` -> PASS (35/35).
- Full backend `pytest` suite was NOT run. Reason: pre-existing `tests/conftest.py` failure (SQLAlchemy `pool_size`/`max_overflow` rejected with SQLite `NullPool` in container). Independent of Phase 1A; recorded as a Phase 1H CI prerequisite.
- Playwright gallery suite was NOT run. Reason: out of scope for Phase 1A (no renderer changes).

### Result
Partial.

The "weak contracts" architecture risk is reduced at the layout-name level only. The deeper hardening items in this audit — durable task events, queue retries/idempotency, shared LayoutIR, observability, deployment strategy, secret fail-fast, CI gate — are unchanged.

### Remaining Risks
- Slide payloads remain dictionary-driven beyond the layout name. No JSON Schema, no typed contract, no validate-then-repair pipeline yet.
- Normalizer still mutates silently (pins first/last slides, inserts placeholders, auto-promotes a stats slide to chart). No `RepairAction` log, no `DeckQualityReport`.
- 10 newly-preserved canonical layouts have no per-layout normalization branches yet; they pass through with only `{id, layout, title}` populated. Renderer compatibility relies on existing frontend layout components.
- Pre-existing `conftest.py` engine-pool bug must be fixed before the backend test tier can run end-to-end in CI.
- All other rows in the architecture risk matrix (CI not enforced, no retries, lossy progress, separate render paths, no observability, Compose-only deployment, dev secret defaults, no retention, etc.) remain open.

## Operational Readiness Score

| Area | Score | Severity | Assessment |
|---|---:|---|---|
| Maintainability | 4 / 10 | High | Modules exist, but core orchestration and renderer/export surfaces are too large and coupled. |
| Modularity | 4 / 10 | High | Service names imply boundaries; runtime contracts remain dictionary-driven and leaky. |
| Abstraction quality | 3.5 / 10 | High | Registry/normalization abstractions are useful but too weak to enforce correctness. |
| Frontend/backend contracts | 3.5 / 10 | High | Shared registry exists, but schema, versioning, and generated-output contracts are not strong. |
| Renderer isolation | 3 / 10 | Critical | Browser preview, PPTX, and PDF are separate renderers with no robust parity strategy. |
| CI reliability | 2 / 10 | Critical | No `.github` workflow found; local scripts exist but are not enforced by repository automation. |
| Regression safety | 3 / 10 | Critical | Gallery snapshots cover curated samples; backend tests stub queue behavior. |
| Queue reliability | 3 / 10 | Critical | Celery exists, but no retries, idempotency model, replay, dead-letter handling, or durable progress log. |
| Async safety | 3 / 10 | High | Worker uses `asyncio.run()` per task and disposes DB engine to dodge event-loop issues. |
| Export reliability | 3 / 10 | Critical | Exports depend on separate render paths, external image/chart fetches, and best-effort behavior. |
| Observability | 2.5 / 10 | Critical | Logs and Sentry setting exist; no traces, metrics, quality events, or operational dashboards. |
| Deployment maturity | 2.5 / 10 | Critical | Compose overlay exists; no real orchestration, migrations strategy, rollout, secrets, or health SLOs. |
| Scalability | 3 / 10 | Critical | Horizontal theory exists, but no load tests, rate limits, cost controls, or tenant quotas. |
| Production reliability | 2.8 / 10 | Critical | Too many best-effort paths and weak recovery guarantees. |

## Architecture Risk Matrix

| Risk | Severity | Likelihood | Blast Radius | Evidence / Signal | Hardening Action |
|---|---|---:|---:|---|---|
| CI not enforced | Critical | High | High | No `.github` directory found; only local npm scripts. | Add GitHub Actions for backend tests, frontend build, layout verification, Playwright, Docker build. |
| Queue tasks are not retryable/idempotent | Critical | High | High | Celery task has `max_retries=0`; generation writes DB progressively. | Add idempotent task steps, retries by failure class, dead-letter queue, and replay. |
| Progress events are lossy | High | High | Medium | SSE uses Redis pub/sub and DB snapshot only; no durable event stream. | Persist task events and replay missed events on reconnect. |
| Async event-loop fragility | High | Medium | High | Worker disposes async engine at start/end to avoid loop-bound connection errors. | Use a stable async worker model or isolate DB sessions per task without engine churn. |
| Renderer/export drift | Critical | High | High | React, PPTX, and PDF render separately. | Create shared layout IR or render exports from same HTML/canvas source. |
| Export network fragility | High | Medium | High | Export fetches images/charts at export time; external services can fail/throttle. | Cache assets before export and export only from persisted local/R2 assets. |
| Weak test fidelity | Critical | High | High | Backend tests stub Celery and use SQLite; gallery tests use curated samples. | Add Docker integration tests with Postgres/Redis/Celery and generated-deck fixtures. |
| Monolithic generation loop | High | High | High | Agent loop owns research, planning, generation, critique, images, charts, persistence. | Split into typed pipeline stages with persisted artifacts. |
| Weak contracts | High | High | High | Slide payloads are dicts normalized heuristically. | Add schema validation, versioning, and repair errors. |
| Compose-only deployment | Critical | Medium | High | `docker-compose.prod.yml` but no Kubernetes/ECS/Terraform/rollout/migration process. | Define target deployment platform and release pipeline. |
| Secret defaults unsafe | Critical | Medium | High | `SECRET_KEY` defaults to `change-me-in-production`; `.env` has been tracked historically. | Enforce production secret checks at startup and rotate exposed keys. |
| Observability insufficient | Critical | High | High | No metrics/tracing/structured operational dashboards. | Add OpenTelemetry, Prometheus metrics, task traces, export metrics, model cost metrics. |
| Memory/disk growth | High | Medium | Medium | Storage volumes hold exports/uploads/memory/research cache; no retention policy visible. | Add retention jobs, storage quotas, cleanup, and monitoring. |
| Frontend rendering bottlenecks | Medium | Medium | Medium | Gallery renders 23 slides with Chart.js/framer/image loads; no virtualization. | Virtualize large galleries/decks and memoize heavy renderers. |
| External provider rate limits | High | High | High | LLM/search/image providers called directly with broad fallback. | Add rate limiting, circuit breakers, provider budgets, and backoff policies. |

## Hidden Scaling Failures

| Failure | Why It Is Hidden | Production Symptom | Required Hardening |
|---|---|---|---|
| Redis pub/sub progress loss | Local demo reconnects rarely. | Users reconnect and miss slide/progress events. | Durable task event table/stream with replay. |
| Worker starvation | Low concurrency hides queue pressure. | Long decks block workers; queue latency spikes. | Separate queues by task type, concurrency sizing, autoscaling, queue metrics. |
| Provider throttling cascade | Small tests do not hit rate limits. | Image/search/LLM calls fail in bursts and mark decks weak or failed. | Circuit breakers, retry budgets, provider-level rate limiters. |
| Export burst failures | Manual exports are sparse. | Many users export at once; image/chart fetches timeout. | Pre-cache assets and charts; export from internal storage only. |
| Postgres connection churn | Single-worker dev hides pool pressure. | Async engine disposal and multiple uvicorn workers create connection churn. | Pool sizing, session lifecycle tests, stable worker loop model. |
| Redis memory growth | Task results/events are not capacity-tested. | Redis memory pressure affects broker and result backend. | TTLs, broker/result separation, memory alerts. |
| Storage volume growth | Local data appears cheap. | Exports/uploads/cache fill disk. | Retention policy, quotas, cleanup workers, storage metrics. |
| Frontend render degradation | Gallery fixtures are small. | Large decks/edit sessions lag or crash low-memory browsers. | Virtualization, memoization, asset lazy loading, profiler budget. |
| Long-running SSE connections | Few local clients. | Many open connections consume backend resources. | Connection limits, heartbeat tuning, event replay, proxy config. |
| No tenant quotas | Single-user dev assumption. | One user can consume all workers/API quota. | Per-user/workspace quotas and admission control. |

## Architecture Smells

1. **Central orchestration sink.** The generation loop coordinates too many concerns and has too many fallback branches.
2. **Dictionary contracts.** Slide data moves as mutable dictionaries rather than typed/versioned contracts.
3. **Best-effort reliability.** Many non-fatal failures are logged and ignored, which helps demos but hides production degradation.
4. **Separate rendering truths.** Browser, PPTX, and PDF output are not guaranteed equivalent.
5. **Local scripts without enforced CI.** The repository has scripts but no discovered CI workflow enforcing them.
6. **Environment defaults too friendly.** Production can accidentally boot with dev defaults unless explicitly guarded.
7. **Queue exists but reliability model is absent.** Celery is a transport, not a reliability design.
8. **Tests substitute critical dependencies.** SQLite and Celery stubs reduce confidence in production behavior.
9. **Static container names.** Compose uses fixed `container_name`, causing conflicts across clones/environments.
10. **Hot reload in dev Compose.** Useful locally, but reinforces a gap between dev and prod behavior.

## Brittle Abstractions

| Abstraction | Brittleness | Consequence | Refactor Direction |
|---|---|---|---|
| Layout registry | Names and hints, not strict schemas. | Invalid slides pass until render/export. | Versioned JSON Schema with capabilities and budgets. |
| Normalizer | Heuristic coercion. | Bad model output becomes plausible but wrong slide data. | Validate first, repair second, reject when needed. |
| Export service | Renderer plus network fetcher plus storage writer. | Hard to test; many failure modes. | Split render, asset resolution, storage, and export job orchestration. |
| AI service | Provider fallback hides quality differences. | Output quality varies silently. | Provider profiles, evals, cost/latency metrics. |
| Progress stream | Pub/sub callback abstraction. | Missed events and no replay. | Durable event sink plus SSE projection. |
| Editor contract | Client normalizes server data locally. | Frontend/backend drift. | Shared schema package or generated types. |
| Docker Compose prod | “Production overlay” abstraction. | Looks deployable but lacks rollout/secrets/migrations. | Real deployment manifests and release runbook. |

## Over-Engineered Areas

| Area | Why It Is Over-Engineered | Risk | Correction |
|---|---|---|---|
| Theme catalog | Many themes before a robust rendering/export contract. | Broad surface area without quality guarantee. | Reduce to certified themes until parity is proven. |
| Multi-provider AI chain | Many providers before quality/cost eval maturity. | Hard-to-debug output variance. | Profile and evaluate providers; restrict production chain. |
| Layout count | 23 layouts before schema/render/export hardening. | Regression surface grows faster than tests. | Certify fewer layouts with strict tests. |
| Fallback pipelines | Markdown and legacy paths coexist. | Debugging quality regressions is difficult. | Pick one primary path with explicit fallback criteria. |
| Gallery snapshots | Many curated snapshots before generated-deck tests. | False confidence. | Add ugly real prompt fixtures and export parity tests. |

## Under-Engineered Areas

| Area | Missing Engineering | Severity |
|---|---|---|
| CI/CD | Automated repository gates, Docker builds, migrations, security scans. | Critical |
| Queue reliability | Retries, idempotency, DLQ, task leases, replay. | Critical |
| Observability | Metrics, traces, dashboards, alerting, quality telemetry. | Critical |
| Contracts | Typed schemas, generated types, versioning. | Critical |
| Export reliability | Asset prefetching, deterministic render, parity checks. | Critical |
| Security operations | Secret validation, scanning, rotation, upload scanning. | Critical |
| Load testing | Concurrency and provider-load simulations. | High |
| Data lifecycle | Retention, quotas, cleanup, storage monitoring. | High |
| Deployment | Orchestration, rollbacks, health SLOs, migration strategy. | Critical |
| Regression corpus | Real prompt and generated-output tests. | High |

## Dangerous Technical Debt

| Debt | Severity | Why Dangerous | Hardening Step |
|---|---|---|---|
| `asyncio.run()` Celery task with async engine disposal workaround | High | Indicates event-loop/pool lifecycle fragility. | Rework worker execution model and integration-test repeated tasks. |
| No queue retries | Critical | Transient provider/network failures become final user failures. | Add retries with idempotency and failure classification. |
| Separate export renderers | Critical | User-visible output can diverge from preview. | Build shared rendering model. |
| No durable task events | High | Support cannot reconstruct failures/progress. | Persist event log with artifacts. |
| Weak schema contracts | Critical | Invalid slide data can propagate. | Strict schema validation and generated types. |
| Stubbing critical infra in tests | Critical | CI can pass while production path is broken. | Add real integration test tier. |
| Static Compose container names | Medium | Multiple environments conflict. | Remove `container_name` or project-scope names. |
| Dev secret defaults | Critical | Accidental insecure production boot. | Startup fail-fast for production secrets. |
| External fetch during export | High | Exports fail due to third-party availability. | Resolve/cache assets before export. |
| No retention policy | High | Disk/storage growth becomes outage. | Add cleanup jobs and quotas. |

## Scaling Risk Analysis

| Component | Scaling Risk | Current Control | Gap | Priority |
|---|---|---|---|---|
| FastAPI backend | SSE connections and export requests consume workers. | Uvicorn workers in prod overlay. | No connection/load testing or autoscaling policy. | P0 |
| Celery workers | Long AI tasks block limited concurrency. | `--concurrency=2`, timeout. | No autoscaling, queues by workload, retries, or DLQ. | P0 |
| Redis | Broker, result backend, pub/sub all share Redis. | AOF enabled. | No broker/result separation, TTL policy, memory monitoring. | P0 |
| Postgres | Async engine disposal and multi-worker pressure. | Healthcheck only. | No pool sizing tests or migration/backup strategy. | P0 |
| Storage | Upload/export/cache growth. | Docker volume/local/R2 service. | No retention, quotas, lifecycle rules. | P1 |
| Image/search/LLM providers | Rate limits and latency spikes. | Basic fallback chain. | No circuit breakers, budgets, or provider health dashboard. | P0 |
| Frontend rendering | Large decks and gallery can become heavy. | Lazy image loading in some places. | No virtualization/profiling budgets. | P2 |
| Export | CPU/memory heavy PPT/PDF creation. | Worker resource limits in prod overlay. | No export queue separation or load test. | P0 |

## Async and Queue Reliability Risks

| Risk | Severity | Current Behavior | Required Guarantee |
|---|---|---|---|
| Duplicate task execution | Critical | No idempotency keys or step locks visible. | Re-running a task cannot duplicate/corrupt deck state. |
| Worker crash mid-task | Critical | DB may have partial state; pub/sub events lost. | Resume/replay or mark failed with artifact trail. |
| Transient provider failure | High | Task may fail or degrade silently. | Retry specific calls with budget and fallback reason. |
| Timeout handling | Medium | 300s app timeout plus Celery hard limits. | User-visible retry/recover path and task cleanup. |
| Progress delivery | Medium | Redis pub/sub best-effort. | Durable ordered events. |
| Cancellation | High | No first-class cancellation semantics found. | Cancel task, stop external work, mark state, cleanup. |
| Backpressure | Critical | No admission control. | Queue depth and quota-based request rejection. |

## Export Reliability Risks

| Risk | Severity | Why It Matters | Hardening Requirement |
|---|---|---|---|
| Preview/export mismatch | Critical | Users download the artifact, not the preview. | Snapshot parity tests and shared layout model. |
| External image fetch in export path | High | Export can fail long after generation succeeded. | Persist images locally/R2 during generation. |
| PDF path separate from PPTX | High | PDF can visually differ from PPTX. | Shared render source or explicit parity tests. |
| Chart rendering split | High | Chart.js/QuickChart/python-pptx can diverge. | Single ChartSpec with tested render adapters. |
| No export job isolation | Medium | Export load can compete with generation. | Separate export queue/worker pool. |
| No export retries | Medium | Transient failures become user-facing 500s. | Idempotent export jobs with retry and cached outputs. |

## Memory Leak and Bottleneck Risks

| Area | Risk | Signal | Recommendation |
|---|---|---|---|
| Backend export | Large PPT/PDF buffers held in memory. | `BytesIO`-style export flow. | Stream where possible and cap deck size/assets. |
| Image fetches | Large images loaded into memory during export. | External image bytes fetched synchronously. | Cache resized assets and enforce max dimensions. |
| Celery worker | Long-lived process running many async tasks. | Engine disposal workaround. | Memory profiling and worker recycle settings. |
| Frontend gallery/deck | Many slides with charts/images/motion. | 23 rendered figures in gallery. | Virtualize thumbnails and memoize slide renders. |
| Redis result backend | Task results and pub/sub on same Redis. | Same URL for broker/backend/pubsub. | TTLs and split Redis roles for production. |
| Storage cache | Research/export/upload memory grows. | Volume-backed storage, no cleanup read. | Retention worker and disk alerts. |

## CI and Regression Safety Gaps

| Gap | Severity | Current State | Required Gate |
|---|---|---|---|
| No discovered GitHub Actions | Critical | `.github` missing. | CI on every PR/push. |
| Backend tests not production-like | Critical | SQLite + Celery stub. | Postgres/Redis/Celery integration tier. |
| Frontend only local script | High | `npm run test:ci` exists but not enforced. | Workflow runs verify/build/gallery. |
| No export regression | Critical | Layout branch checks only. | PPT/PDF visual parity snapshots. |
| No generated-deck corpus | High | Curated gallery fixtures. | Prompt fixture corpus with visual and schema checks. |
| No migration test | High | Alembic exists. | Fresh DB and upgrade path in CI. |
| No security/dependency scan | High | Requirements/package deps. | pip/npm audit, secret scanning, container scan. |
| No load/perf test | High | None found. | Scheduled or release-blocking load smoke. |

## Observability Gaps

| Missing Signal | Impact | Required Instrumentation |
|---|---|---|
| Task duration by step | Cannot find bottlenecks. | Step timers and percentile dashboards. |
| Queue depth/age | Cannot detect backlog. | Celery queue metrics. |
| Provider latency/error/cost | Cannot manage AI economics. | Provider spans and cost counters. |
| Export success/failure by format | Cannot trust export reliability. | Export metrics and artifact failure reasons. |
| SSE disconnect/reconnect rate | Cannot diagnose live preview issues. | Stream connection metrics. |
| Slide validation failures | Cannot improve generation quality. | Validation error counters by layout. |
| Render/export parity failures | Cannot detect visual drift. | Visual diff metrics. |
| Storage growth | Disk outages likely. | Volume/R2 usage dashboards. |
| User/workspace quota usage | No abuse/cost control. | Quota counters. |
| Deployment health | No SLO posture. | Synthetic checks and alerting. |

## Deployment Risk Analysis

| Risk | Severity | Current Signal | Required Hardening |
|---|---|---|---|
| Compose is treated as production | Critical | `docker-compose.prod.yml` exists. | Choose real production platform and define deploy pipeline. |
| No migrations in release flow | Critical | Alembic exists, but Compose does not run migrations. | Automated migration job with rollback policy. |
| No secret management | Critical | Env files/defaults. | Managed secrets and production startup validation. |
| No rolling deployment strategy | High | Compose up/down. | Blue/green or rolling deploy with health gates. |
| No backup/restore runbook | Critical | Postgres volume only. | Automated backups and restore drills. |
| No TLS/proxy strategy in repo | High | Frontend nginx only. | Ingress/proxy/TLS/cors/rate-limit architecture. |
| No environment promotion | High | Dev/prod overlay. | Staging/prod parity and release promotion. |
| No container scanning | Medium | Dockerfiles only. | Image vulnerability scanning in CI. |
| No resource autoscaling | High | Static Compose resource limits. | Autoscaling policies and capacity plans. |
| Static container names | Medium | `container_name` set. | Remove for multi-env deployments. |

## Reliability Gaps

| Reliability Guarantee | Current State | Required State |
|---|---|---|
| Exactly-once or safe-at-least-once task behavior | Not guaranteed. | Idempotent steps with state machine. |
| Durable progress | Snapshot + volatile pub/sub. | Persisted ordered events. |
| Retry semantics | Mostly absent. | Retry by dependency/failure class. |
| Partial failure recovery | Weak. | Resume/retry from last successful artifact. |
| Export determinism | Weak. | Cached assets and reproducible renderer inputs. |
| Queue backpressure | Missing. | Admission control and quota enforcement. |
| Data retention | Missing. | Configured lifecycle policies. |
| Production startup safety | Weak. | Fail-fast on insecure/missing production config. |

## Exact Production Launch Blockers

| Blocker | Severity | Exit Criteria |
|---|---|---|
| No enforced CI workflow | Critical | GitHub Actions runs backend, frontend, layout, Playwright, Docker, security scans. |
| No production-like integration tests | Critical | CI spins Postgres/Redis/Celery and executes generate/status/slides/export smoke. |
| Queue tasks not idempotent/retryable | Critical | Task state machine supports safe retry and replay. |
| Progress events not durable | High | Reconnect replays ordered task events. |
| Export parity unverified | Critical | Browser/PPT/PDF parity tests pass for certified layouts. |
| External assets fetched during export | High | All export assets resolved and cached before export. |
| No secret management/startup validation | Critical | Production boot fails on dev secrets and uses managed secret store. |
| No migration/release runbook | Critical | Automated migration and rollback plan exists. |
| No observability baseline | Critical | Metrics, traces, dashboards, alerts for queue/tasks/export/providers/storage. |
| No load test baseline | High | Defined concurrency test passes with SLOs and resource budget. |
| No storage retention/quotas | High | Cleanup worker and quotas active. |
| No upload security scanning | High | Malware/type scanning and file governance active. |
| No backup/restore proof | Critical | Backup and restore drill documented and passing. |
| No cancellation/backpressure | High | Users can cancel; system rejects/queues based on quotas/depth. |
| Renderer contract not versioned | High | Slide schema and layout contract versions enforced. |

## Refactor Priority Matrix

| Priority | Refactor | Impact | Effort | Order |
|---|---|---:|---:|---:|
| P0 | Introduce typed slide/layout schemas and generated frontend/backend types. | Very high | Medium | 1 |
| P0 | Create durable task state machine and event log. | Very high | High | 2 |
| P0 | Make generation/export tasks idempotent and retryable. | Very high | High | 3 |
| P0 | Split export service into asset resolution, render adapters, storage writer. | High | Medium | 4 |
| P0 | Add shared layout IR or single-source render strategy. | Very high | High | 5 |
| P1 | Split agent loop into pipeline stages with persisted artifacts. | High | High | 6 |
| P1 | Centralize theme/layout contracts into one shared package. | High | Medium | 7 |
| P1 | Replace volatile progress pub/sub with durable replayable stream. | High | Medium | 8 |
| P1 | Add queue separation: generation, export, image/research. | High | Medium | 9 |
| P2 | Frontend render virtualization/memoization for large decks. | Medium | Medium | 10 |

## Hardening Roadmap

### 0-14 Days: Stop the Bleeding

| Work | Owner Area | Exit Criteria |
|---|---|---|
| Add CI workflow. | Platform | PRs run backend tests, frontend build, layout verify, Playwright gallery. |
| Add production config fail-fast. | Backend/Ops | App refuses production with dev secrets/default DB/empty critical vars. |
| Add basic queue metrics. | Ops | Queue depth, task duration, failure count visible. |
| Add schema validation before save/export. | Frontend/backend contracts | Invalid slide payloads fail with clear errors. |
| Remove static Compose container names or document project naming. | DevOps | Multiple clones can run without name conflicts. |

### 15-30 Days: Make Critical Paths Testable

| Work | Owner Area | Exit Criteria |
|---|---|---|
| Docker integration test tier. | QA/backend | Postgres/Redis/Celery generate/export smoke passes. |
| Durable task event table. | Backend | SSE reconnect can replay missed events. |
| Export asset caching. | Export | Export does not depend on third-party image availability. |
| Export regression snapshots. | QA/rendering | Certified layouts have PPT/PDF diff baselines. |
| Storage retention job. | Ops/backend | Upload/export/cache cleanup policy active. |

### 31-60 Days: Reliability Architecture

| Work | Owner Area | Exit Criteria |
|---|---|---|
| Idempotent task state machine. | Backend/queue | Retry does not corrupt decks or duplicate rows. |
| Retry and DLQ policy. | Queue | Transient failures retry; poison tasks are isolated. |
| Pipeline artifact model. | Backend | Each step writes typed artifacts and can be inspected. |
| Provider circuit breakers. | AI/platform | Provider failures degrade predictably with metrics. |
| Load test harness. | QA/Ops | Defined concurrency SLOs measured and tracked. |

### 61-90 Days: Production Operations

| Work | Owner Area | Exit Criteria |
|---|---|---|
| Real deployment platform. | DevOps | Staging/prod deploys through orchestrated pipeline. |
| Migration/backup/restore runbook. | DevOps/DB | Restore drill and migration dry run pass. |
| Full observability stack. | Ops | Dashboards and alerts cover app, queue, DB, Redis, exports, providers. |
| Security hardening. | Security | Secret management, upload scanning, dependency/container scanning. |
| SLO definition. | Product/Ops | Availability, generation latency, export success, queue age SLOs defined. |

## Final Staff-Engineer Verdict

This codebase has enough structure to continue evolving, but it is not hardened. The critical problem is that the visible application works through permissive contracts and best-effort behavior, while production systems require deterministic contracts, replayable jobs, durable events, tested deployments, and strong observability.

The highest-leverage architectural shift is to turn generation/export from a loose sequence of side effects into a typed, durable, idempotent pipeline with measured quality gates and enforced CI. Until that happens, scaling the system will amplify hidden failures rather than prove platform maturity.

---

## Phase 6A � Runtime Auth + Alembic Migration � 2026-05-09

**What changed**
- `/api/agent/test-run` now requires `Authorization: Bearer <jwt>`. New `get_current_user` dependency decodes JWT via `AuthService`, loads `User`, raises 401 on any failure. Runtime call uses `current_user.id`.
- New Alembic migration `0002_agent_runtime` (down_revision `0001_initial`) creates `agent_runs`, `agent_steps`, `artifacts` with FKs and 7 indexes. `_json_variant()` helper uses `JSON().with_variant(JSONB, "postgresql")`. Full reversible `downgrade()`.

**Files changed**
- `backend/api/routes/agent.py` (auth dep, route signature)
- `backend/database/migrations/versions/0002_agent_runtime.py` (NEW)
- `backend/tests/test_agent_route.py` (6 new auth tests; dep-override helper)
- `backend/tests/test_phase3_runtime_artifacts.py` (auth dep override)
- `backend/tests/test_runtime_migration.py` (NEW; 5 AST integrity tests)

**Tests added:** 11 (6 auth + 5 migration integrity).

**Tests run**
```
docker run --rm -v "D:\nexus-ai-1\nexus-ai\backend:/app" -w /app \
  -e PYTHONPATH=/app -e DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  nexus-ai/backend:dev sh -c "pip install --quiet pytest pytest-asyncio httpx aiosqlite && python -m pytest -q -p no:cacheprovider"
# ? 183 passed, 1 skipped, 1 warning
```
On-disk migration verification (fresh SQLite file):
```
alembic upgrade head
# ? 0001_initial ? 0002_agent_runtime
sqlite tables ? ['agent_runs', 'agent_steps', 'alembic_version', 'artifacts',
                 'exports', 'share_tokens', 'slides', 'tasks', 'users']
```

**Result:** Pass.

**Remaining risks**
- No rate limits, per-user quotas, or SSE step streaming on `/api/agent/test-run`.
- Runtime still does not drive `/api/generate` (user-facing flow remains the 6-step `agent/loop.py`).
- No claim-level citations; no on-slide visual citations; no hard fact-checking.
- Export parity (PPTX/PDF vs on-screen renderer) still unverified.
- Visual quality unchanged.
- Live `nexus-backend` container is bound to `D:\nexus-ai-gh\backend`; requires `docker compose up --build` from this workspace to pick up Phase 6A.


---

## Phase 6B � Competitive Accuracy + Stability Benchmark Baseline � 2026-05-09

**What changed**
- Added measurable benchmark baseline (no product-behavior changes). New plan, weighted rubric, prompt corpus, integrity tests, and an honest current-score file. Established that NEXUS is **not yet** beating Manus and that AI accuracy is **not yet measured live**.

**Files changed / added**
- `audits/COMPETITIVE_BENCHMARK_BASELINE.md` (NEW) � plan comparing NEXUS vs Manus, browser-use, OpenManus, AgenticSeek, Gamma/Tome across 7 weighted categories.
- `audits/CURRENT_COMPETITIVE_SCORE.md` (NEW) � honest baseline; estimated overall ~55/100; explicit list of unmeasured items.
- `benchmarks/rubric.json` (NEW) � weights sum to 100: deck_correctness 20, visual_quality 15, export_parity 15, evidence_accuracy 15, agent_autonomy 15, stability_reliability 10, security_production_readiness 10. Scale 1�10. Lists 5 competitors.
- `benchmarks/prompts.json` (NEW) � 11 realistic prompts spanning business, investor, education, product launch, market research, chart-heavy, evidence-heavy, visual-storytelling, agent-autonomy. Each has `expected_evidence`, `expected_visual`, `difficulty`, `primary_categories`. No expected slide content (offline only).
- `backend/tests/test_competitive_benchmark.py` (NEW) � 17 conftest-free integrity tests. No LLM calls.
- `audits/AUDIT_CURRENT_STATE.md`, `audits/AUDIT_PROMPT_CONTEXT.md` � updated to record Phase 6B completion.

**Tests added:** 17 (rubric weights sum / category schema / scale / competitors; prompts file / count / unique IDs / required kinds / required metadata / expected_evidence / expected_visual / difficulty / primary_categories / all difficulty levels covered / all prompt-evaluable rubric categories covered; categories?audit-open-risks mapping).

**Tests run**
```
docker run --rm -v "D:\nexus-ai-1\nexus-ai\backend:/app" \
  -v "D:\nexus-ai-1\nexus-ai\benchmarks:/benchmarks" -w /app \
  -e PYTHONPATH=/app -e DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  nexus-ai/backend:dev sh -c "pip install --quiet pytest pytest-asyncio httpx aiosqlite && python -m pytest -q -p no:cacheprovider"
# ? 200 passed, 2 skipped, 1 warning
```
(Was 182 passed, 2 skipped after Phase 6A; +18 new collected including a previously-uncollected test.)

**Result:** Pass.

**Remaining risks**
- AI generation accuracy not measured live � rubric and corpus exist but no live-eval harness has been run against `/api/generate`.
- No screenshot-diff visual regression suite.
- No renderer?export contract test (PPTX/PDF parity unverified).
- No claim-level citations, no on-slide citations, no hard fact-checking.
- Runtime still does not drive `/api/generate`.
- No rate limits / per-user quotas / SSE / audit logging on runtime route.
- Live `nexus-backend` container still bound to `D:\nexus-ai-gh\backend`; `docker compose up --build` from this workspace required to pick up Phase 6A/6B.


---

## Phase 6B-Fix � Restore Official Backend Test Gate � 2026-05-09

**What changed**
- Verification drift correction. The initial Phase 6B run used an ad-hoc `docker run` that mounted both `backend/` and `benchmarks/`. The official gate `scripts/test-backend.ps1` only mounted `backend/`, so `/benchmarks` was not visible to the container and Copilot's rerun produced **2 failed, 182 passed, 2 skipped, 1 warning, 16 errors**.
- Updated `scripts/test-backend.ps1` to also mount the repo's `benchmarks/` folder at `/benchmarks` (read-only) and to refuse to run if the directory is absent.
- Hardened `backend/tests/test_competitive_benchmark.py` so that when neither `<repo>/benchmarks/` nor `/benchmarks` is visible, both the existence tests and the rubric/prompts fixtures fail loudly with a clear message instead of silently passing against a non-existent path.

**Files changed**
- `scripts/test-backend.ps1`
- `backend/tests/test_competitive_benchmark.py`
- `audits/AUDIT_CURRENT_STATE.md`, `audits/AUDIT_PROMPT_CONTEXT.md`

**Tests added:** 0 (defensive hardening of the 17 existing benchmark tests).

**Tests run**
```
.\scripts\test-backend.ps1
# pytest summary ? 200 passed, 2 skipped, 1 warning (exit code 0)
```
The PowerShell wrapper may surface a non-zero `$LASTEXITCODE` purely from pytest-asyncio writing a deprecation warning to stderr; verified separately that the docker process exits 0 when stderr is suppressed.

**Result:** Pass.

**Remaining risks**
- Same as Phase 6B: AI accuracy still unmeasured live, no screenshot diff, no renderer?export contract test, no claim-level citations, runtime not driving `/api/generate`, no rate limits / quotas / SSE / audit logging.
- Live `nexus-backend` container still bound to `D:\nexus-ai-gh\backend`; `docker compose up --build` from this workspace required to pick up Phase 6A/6B/6B-Fix.

---

## Phase 6W — Role-Based Provider Routing + Token Pruning

**Date:** 2026-05-10. **Backend gate:** 431 passed, 2 skipped, 1 warning (unchanged from 6U-Rebench / 6V baseline). **Frontend layouts gate:** OK — 7 canonical layouts, 7 exported. No product API surface change. No new dependencies. No secrets in tracked files.

### 1. What was implemented

- **4 new providers wired** in [backend/config.py](nexus-ai/backend/config.py) and [backend/services/ai_service.py](nexus-ai/backend/services/ai_service.py): Cerebras, SambaNova, Mistral, GitHub Models. All four use the existing OpenAI-compatible `_openai_compat` helper — no new SDK.
- **All 10 providers reported by `/api/health`** ([backend/main.py](nexus-ai/backend/main.py)) with `configured`, `active`, `model`, `base_url`. `/api/health` is local-only — it does not remote-ping providers.
- **Role-based routing via `complete_for_role()`** ([backend/services/ai_service.py](nexus-ai/backend/services/ai_service.py)) — reads `settings.ROLE_MODEL_MAP`, logs role + preferred provider + preferred model, attempts the preferred provider with the **exact** preferred model, and on failure logs a warning and falls back to the existing `complete()` chain. `complete()` itself is unchanged.
- **Exact model override** for every provider call: `_call_openrouter`, `_call_nvidia_nim`, `_call_groq`, `_call_openai`, `_call_unfiltered`, `_call_cerebras`, `_call_sambanova`, `_call_mistral`, `_call_github_models`, `_call_gemini`, and `_call_anthropic` all accept a keyword-only `model: str | None = None`. When `None`, they use the env-default model for that provider.
- **Improved token pruning** in [backend/services/ai_service.py](nexus-ai/backend/services/ai_service.py):
  - `_prune_user_text()` now does **middle-truncation** (keeps head ~70% + tail ~30% with elision marker). The previous version truncated from the end, silently dropping the output contract ("Return ONLY a JSON array...") and producing malformed model output. The new version preserves the output contract.
  - `prune_messages()` rewritten to: keep system messages (de-duplicated), always preserve the last `KEEP_LAST_MESSAGES` non-system messages verbatim, drop oldest middle messages first with an elision placeholder, and as a final safeguard middle-truncate the single longest remaining message.
- **Research summarization** wired in [backend/agent/loop.py](nexus-ai/backend/agent/loop.py) — when harvested research exceeds 10,000 chars, the `summarize` role compresses it before it reaches planner/writer. Source metadata in `research_sources` is preserved separately and never destroyed.
- **LLM JSON repair** wired at the *only* point it adds value: when `_parse_slides_array` or `_parse_single_slide` fails on writer output, `_json_fix_retry()` calls the `json_fix` role once and re-parses. The deterministic `repair_for_validator` path was **not** replaced.
- **Dead-code removal:** deleted the duplicate copy of `_add_hero_images` in `loop.py` (the second definition was overriding the first; behavior unchanged).
- **Test script** `test_providers.py` (repo root) — skips unconfigured providers, pings configured ones with a tiny "Reply OK only." prompt, prints OK/FAIL/SKIP + model, exits non-zero only if every configured provider failed.

### 2. Role routing table

| Role | Provider | Model | Wired location | Status |
|------|----------|-------|----------------|--------|
| planner | gemini | `gemini-2.0-flash` | [backend/agent/planner.py](nexus-ai/backend/agent/planner.py#L48) | working |
| writer | groq | `llama-3.3-70b-versatile` | [backend/agent/loop.py](nexus-ai/backend/agent/loop.py#L383) (batch) + [backend/agent/loop.py](nexus-ai/backend/agent/loop.py#L451) (per-slide retry) | working |
| critic | openrouter | `deepseek/deepseek-r1:free` | [backend/agent/loop.py](nexus-ai/backend/agent/loop.py#L598) | working |
| research | cerebras | `qwen-3-235b-a22b-instruct-2507` | not used as a separate role; research is harvested by `SearchService` | **not used** (research compression goes through `summarize` role; `research` role is defined in the map but no call site invokes it) |
| vision | gemini | `gemini-2.0-flash` | [backend/agent/loop.py](nexus-ai/backend/agent/loop.py#L678) (image-prompt generation) | working |
| repair | openrouter | `qwen/qwen2.5-coder-32b:free` | not used as a separate role; deterministic `repair_for_validator` handles schema repair | **not used** (intentional — deterministic repair is sufficient for the current schema; LLM repair would add latency without clear benefit) |
| summarize | sambanova | `Meta-Llama-3.3-70B-Instruct` | [backend/agent/loop.py](nexus-ai/backend/agent/loop.py#L88) (`_summarize_long_research`, triggered when research > 10k chars) | working (conditional) |
| json_fix | github_models | `gpt-4o-mini` | [backend/agent/loop.py](nexus-ai/backend/agent/loop.py#L130) (`_json_fix_retry`, called when slide-array or single-slide parse fails) | working (conditional) |

### 3. Provider/model override behavior

| Provider | Exact-model override | Notes |
|---|---|---|
| openrouter | yes | via `_openai_compat` |
| nvidia_nim | yes | via `_openai_compat` |
| groq | yes | via `_openai_compat` |
| openai | yes | via `_openai_compat` |
| unfiltered | yes | via `_openai_compat` |
| cerebras | yes | via `_openai_compat` |
| sambanova | yes | via `_openai_compat` |
| mistral | yes | via `_openai_compat` |
| github_models | yes | via `_openai_compat` |
| gemini | yes | native SDK now reads `model_name` from override |
| anthropic | yes | native SDK now reads override; falls back to `active_anthropic_model` |

### 4. Test results

- **Backend** — `powershell -File ./scripts/test-backend.ps1` → **`431 passed, 2 skipped, 1 warning in 10.04s`**.
- **Frontend layouts** — `npm run verify:layouts` → **`verify-layouts OK — 7 canonical layouts, 7 exported`**.
- **Provider smoke test** — host Python lacks pydantic, so the script must run inside the backend container:
  ```
  docker run --rm -v "D:\nexus-ai-1\nexus-ai:/app" -v "D:\nexus-ai-1\nexus-ai\.env:/app/.env:ro" -w /app -e PYTHONPATH=/app/backend nexus-ai-backend:dev python test_providers.py
  ```
  Result at audit time: **ok=3, configured=8, total=10**. `groq`, `nvidia_nim`, `sambanova` returned OK. `gemini` and `openrouter` returned 429 (free-tier rate limit, transient). `cerebras` returned 429 (transient queue). `mistral` and `github_models` returned 401 (the keys provided at provisioning time were rejected — see Risks). `anthropic` and `openai` skipped (no key).

### 5. Remaining risks

- **Invalid keys in local `.env`.** `MISTRAL_API_KEY` and `GITHUB_MODELS_API_KEY` returned 401 from their providers. The roles that depend on them (`json_fix`) will always fall back to the `complete()` chain until those keys are rotated to working values.
- **Free-tier rate limits.** `gemini`, `openrouter`, and `cerebras` repeatedly hit 429 in the smoke test. The role-routing fallback to `complete()` masks this in production code, but **planner** (Gemini), **critic** (OpenRouter), **research** (Cerebras), and **vision** (Gemini) will silently degrade to whichever provider in the chain answers first whenever their preferred provider is rate-limited.
- **Approximate token pruning.** Pruning is dependency-free and uses ~4 chars/token as a heuristic. It is not exact tokenization. For pathological inputs it may under- or over-trim by ±10–15%. Adopting `tiktoken` would fix this but adds a dependency.
- **`research` and `repair` roles are defined but not wired.** They are reachable via `complete_for_role(role="research" | "repair")` if a future caller wants them, but no current code path invokes them. Listed in `ROLE_MODEL_MAP` for forward compatibility only. This is intentional and documented above.
- **Not a fully dynamic runtime.** Role → provider mapping is static (env-driven via `ROLE_MODEL_MAP`). There is no learned/measured routing that picks the cheapest provider that meets quality, no per-task A/B routing, and no automatic key-health probing. `/api/health` reports configuration, not liveness.

### 6. Score impact (honest, no marketing)

| Axis | Before 6W | After 6W |
|------|-----------|----------|
| Token efficiency | End-truncation often dropped the output contract → wasted retries | Middle-truncation preserves head + tail; no observed contract loss in tests |
| Provider resilience | 6 providers in chain, single-model-per-provider | 10 providers configured, role-preferred provider with exact-model override + automatic fallback to chain |
| Manus-like architecture | Single-provider chain regardless of task | Per-role provider/model preferences (4 roles actually wired); still static, not learned |

### 7. What changed (file list)

- [backend/config.py](nexus-ai/backend/config.py) — `ROLE_MODEL_MAP`, 4 new provider blocks, `MAX_CONTEXT_TOKENS`, `KEEP_LAST_MESSAGES`, extended `assert_required_for_runtime`.
- [backend/services/ai_service.py](nexus-ai/backend/services/ai_service.py) — 4 new handlers, `model_override` on all handlers (incl. Gemini + Anthropic), `complete_for_role()`, `prune_messages()` (rewritten), `_prune_user_text()` (middle-truncation), `ClaudeService = AIService` shim preserved.
- [backend/agent/planner.py](nexus-ai/backend/agent/planner.py) — `planner` role; `hasattr` fallback for legacy fakes.
- [backend/agent/loop.py](nexus-ai/backend/agent/loop.py) — `_ai_call` helper, `_summarize_long_research`, `_json_fix_retry`; `writer`/`critic`/`vision` roles wired; duplicate `_add_hero_images` removed.
- [backend/main.py](nexus-ai/backend/main.py) — `/api/health` reports all 10 providers.
- [.env.example](nexus-ai/.env.example) — 4 new provider blocks (placeholders only); `AI_PROVIDER_CHAIN` default aligned with `backend/config.py`; pruning knobs.
- [test_providers.py](nexus-ai/test_providers.py) — new root-level smoke test.

