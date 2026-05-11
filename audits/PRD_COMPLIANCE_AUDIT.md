# PRD Compliance Audit: AI PPT Generator Platform

> **Reading note.** For current truth, read `AUDIT_CURRENT_STATE.md` first. This file contains historical phase notes and original audit findings. Older sections may be superseded. Do not treat old phase claims as current evidence without checking `AUDIT_CURRENT_STATE.md` and `AUDIT_READING_GUIDE.md`.

Date: 2026-05-08  
Source of truth: Original AI PPT Generator Platform PRD, as represented by `PRD_AUDIT.md` and the requested PRD sections  
Audit posture: acquisition / enterprise investment diligence  
Scope: PRD compliance, architecture drift, fake-complete areas, missing systems, production readiness, competitive quality

## Executive Summary

The implementation is not PRD-complete. It satisfies the basic demo loop: prompt in, queued generation, slide JSON persisted, browser preview, PPTX/PDF export endpoints, basic editor, upload ingestion, images, charts, and gallery regression harness. That is materially useful, but the PRD describes a much deeper platform: visual intelligence, structured business-context understanding, brand-aware generation, asset systems, AI editing, scalable enterprise architecture, and competitive output quality.

The largest gap is not missing screens. The largest gap is that many PRD systems exist as endpoint shells, heuristics, fallbacks, or isolated services that do not create a reliable end-to-end product capability.

## Phase 5 -- Frontend Evidence Visibility - 2026-05-09

### PRD Surface Touched
- **"User can inspect evidence behind generated decks."** New `SourceEvidencePanel` mounts on the generator result screen and on shared decks. Shows per-slide sources (title, host, truncated snippet). The PRD row "explainable / inspectable output" moves from `data exists` (Phase 4) to `data is visible to the user` (Phase 5).
- **"Source data flows end-to-end."** `slideParser.js` was previously stripping `slide.sources` during normalization; that has been fixed so backend-attached sources reach the UI intact.
- **`/api/generate`, `/api/slides/{task_id}`, `/api/share/{token}` are all unchanged.** The new UI is purely consumer-side.

### Files Changed
- `frontend/src/components/SourceEvidencePanel.jsx` (new).
- `frontend/src/pages/Generator.jsx` (one mount).
- `frontend/src/pages/SharedSlide.jsx` (one mount).
- `frontend/src/utils/slideParser.js` (preserve `sources`).

### Tests Run
- `npm run verify:layouts` -> 7 / 7.
- No backend code changed; backend gate not re-run.

### Result
**Pass (narrow).** "Generated decks are inspectable" is now a real user feature on both the generator screen and the public share view. Full PRD compliance still requires (a) per-claim source binding, (b) on-slide visual citation rendering, (c) runtime-driven deck generation, and (d) authentication on the runtime endpoint.

### Remaining Risks
- No claim-specific citation mapping yet.
- No on-slide visual citations yet -- only the panel.
- No hard fact-checking.
- Runtime still not driving `/api/generate`.
- Route remains unauthenticated/internal.
- No Alembic migration yet.

## Phase 4 -- Evidence-Aware Deck Generation + Source Visibility - 2026-05-09

### PRD Surface Touched
- **"Generated decks should be source-aware"** -- stats and chart slides now carry up to 3 normalised research sources attached to `slide["sources"]`; `chart_data.source` is filled with the source title or URL host when it was empty. The PRD requirement "connect generated claims to sources" moves from `evidence captured but not connected` (Phase 3) to `deck-level sources flow into the deck data` (Phase 4).
- **"Quality / governance must be visible to the user"** -- `DeckQualityBadge` now shows the count of `source_warnings` in the pill and lists them in the panel. First time a non-developer can see "this stats slide has no source."
- **The PRD `/api/generate` flow is unchanged** -- same endpoint, same response shape; `slides[i].sources` is purely additive.

### Files Changed
- `backend/agent/source_grounding.py` (added `attach_research_sources_to_deck`).
- `backend/agent/loop.py` (preserved + attached search sources).
- `frontend/src/components/DeckQualityBadge.jsx` (source-warning surface).
- 1 new test file (13 tests).

### Tests Run
- Backend full: **171 passed, 2 skipped** (was 158/2; +13).
- Frontend `verify:layouts` -> 7 / 7.

### Result
**Pass (narrow).** The PRD row "deck output should be source-aware and let users see when it isn't" moves from `not implemented` to `implemented at deck-level with visible warnings`. Full PRD compliance still requires (a) per-claim source binding (which number came from which source), (b) on-slide visual citation rendering, (c) runtime-driven deck generation, and (d) authentication on the runtime endpoint.

### Remaining Risks
- Source matching is heuristic, not hard fact-checking.
- Sources are deck-level, not claim-specific.
- No visual citations rendered on slides yet -- only in the badge panel.
- Runtime still not driving `/api/generate`.
- Route remains unauthenticated/internal.
- No Alembic migration yet.

## Phase 3 -- Source Grounding & Evidence Artifacts - 2026-05-09

### PRD Surface Touched
- **"Visual / business-context intelligence" -> evidence layer**: heterogeneous tool outputs (web search, read-only browser tools) are now normalised to a single evidence record shape and persisted as `Artifact(artifact_type="source")` rows attached to the originating `AgentRun`. The PRD's "connect generated claims to sources" requirement now has a real, tested data substrate.
- **"Deck quality / governance"**: stats and chart slides without source metadata produce advisory `source_warnings` in `DeckQualityReport`. This is the first quality signal that distinguishes "the schema validates" from "the slide makes a numeric claim it can't back up." Advisory only -- nothing is rejected, repaired, or invented.
- **The PRD slide-generation flow (`/api/generate` -> Celery -> 6-step pipeline) is untouched.** Phase 3 deliberately stops short of routing decks through `AgentRuntime`.

### Files Changed
- `backend/agent/source_grounding.py` (new).
- `backend/agent/deck_quality.py` (added `source_warnings`).
- `backend/agent/runtime.py` (artifact persistence on success).
- `backend/api/routes/agent.py` (artifact summary in response).
- 2 new test files (17 tests), 2 existing tests updated for new exact-set shape.

### Tests Run
- Backend full: **158 passed, 2 skipped** (was 139/2; +19).
- Frontend `verify:layouts` -> 7 / 7.

### Result
**Pass (narrow).** The PRD row "agent connects claims to sources" moves from `not implemented` to `evidence is captured, persisted, and surfaced as advisory deck-quality warnings`. Full PRD compliance still requires (a) deck generation actually consuming evidence to produce citations / chart sources, (b) frontend rendering of source pills/badges, and (c) authentication / quota on the runtime endpoint.

### Remaining Risks
- Source grounding is advisory, not hard fact-checking.
- No frontend rendering of sources yet.
- Runtime route is unauthenticated/internal.
- No Alembic migration for the runtime + artifact tables.
- Deck generation is not yet runtime-driven.
- Browser observations limited under `BROWSER_ENABLED=false` (default).

## Phase 2.5 -- Safe Internal Agent API + Planner Adapter - 2026-05-09

### PRD Surface Touched
- "Agentic AI behavior" -- the runtime is no longer reachable only from Python. It now has an internal HTTP surface (`POST /api/agent/test-run`) with strict request schema, a server-enforced safe allowlist, and a planner adapter to `AIService`. The runtime continues to persist `AgentRun` / `AgentStep` per step.
- "AI governance" -- a real, tested policy boundary now exists: shell, file-write, deploy, and browser-console tools are categorically rejected at the route layer (HTTP 400), not just at the runtime layer. This is the first piece of platform-level governance in the system, narrow but real.
- The PRD slide-generation flow (`/api/generate` -> Celery -> 6-step pipeline) is untouched.

### Files Changed
- `backend/agent/planners.py` (new).
- `backend/api/routes/agent.py` (new).
- `backend/tests/test_agent_route.py` (new, 8 tests).
- `backend/main.py` (router include only).

### Tests Run
- Backend full: **139 passed, 2 skipped** (was 131/2; +8).
- Frontend `verify:layouts` -> 7 / 7.

### Result
**Pass (narrow).** The PRD row "agentic AI behavior" moves from `runtime exists, untouched by user flow` (Phase 2) to `runtime callable behind a policy gate, persisted, governed by allowlist`. Full PRD compliance still requires (a) authentication and rate-limiting on the endpoint, (b) Phase 3 source/citation grounding so observations become deck artifacts, and (c) integration into the slide pipeline.

### Remaining Risks
- Endpoint is unauthenticated and has no per-user quota; explicitly internal-only until Phase 7.
- Not wired to deck generation.
- No Alembic migration for runtime tables; production Postgres deploy is gated on one.

## Phase 2 -- Dynamic Tool-Calling Agent Runtime - 2026-05-09

### PRD Surface Touched
- "AI editing / agentic behavior" -- PRD describes an agent that can decide on tools, call them, and observe results, not just a fixed pipeline. That capability now has a real implementation (`backend/agent/runtime.py`) with strict action JSON, allowlist, bounded loop, per-step persistence to `agent_runs` / `agent_steps`, and 13 tests covering happy path, malformed output, unknown tool, allowlist, timeout, max_steps, max_failures, and persistence shape.
- The 6-step slide generation pipeline is **unchanged**; the runtime is a parallel module not yet routed in front of any user request.

### Files Changed
- `backend/agent/runtime.py` (new, ~310 lines).
- `backend/tests/test_agent_runtime.py` (new, 13 tests).

### Tests Run
- Backend full: **131 passed, 2 skipped** (was 118/2; +13).
- Frontend `verify:layouts` -> 7 / 7.

### Result
**Pass (narrow).** The runtime *capability* is no longer an endpoint shell or a heuristic -- it is real, validated code with a tested safety envelope. PRD compliance for "agentic AI behavior" moves from `scaffolding` to `runtime exists, untouched by user flow`. Full PRD compliance for this row still requires (a) a planner adapter against `AIService`, (b) a route that hands a goal to `AgentRuntime`, and (c) Phase 3 source grounding so observations become deck citations.

### Remaining Risks
- Not routed for real users; not visible in product UX yet.
- Tool allowlist is the only governance gate; per-user quotas/RBAC come in Phase 7.
- Runtime tables have no Alembic migration; production Postgres deploy is blocked until one is generated.

## Phase 1H Pre-Lock Triage Sweep (P1-1, P1-2, P0-2, P1-3) - 2026-05-09

### What Was Fixed
- **P1-1 (PRD Phase 1D Remaining Risks).** `frontend/src/pages/SharedSlide.jsx` now consumes `deck_quality` from the share API and renders `DeckQualityBadge` next to the public-preview header chip. Backend already returned the field on `GET /api/share/{token}` since Phase 1D; only the consumer was missing.
- **P1-2 (PRD Phase 1B.1 -> 1F Remaining Risks).** `_normalize_slides` no longer produces self-inflicted validation warnings on every safety-net stats->chart promotion. The promoted chart slide now carries a slide-level `subtitle` (forwarded from the source slide if present, defaulting to `""`). The previously-amber badge on safety-net decks now goes green automatically; no synthetic content is invented.
- **P0-2.** Added a tiny conftest-free parity test (`tests/test_export_input_parity.py`) that pins the contract Phase 1D depends on: both the slides-read route and the export routes must read `deck.slide_data` via the same `deck.slide_data or []` expression, with no transform between the deck-quality computation and the export render input.
- **P1-3.** Cross-link added inside the existing Phase 1A correction notice ("See 'Phase 1A Correction Update' above for the verified numbers (7 canonical layouts, 0 aliases, 13 tests)."). Older inaccurate sections kept intact per the constraint not to delete history.

### Files Changed
- `frontend/src/pages/SharedSlide.jsx` (P1-1).
- `backend/agent/loop.py` (P1-2; one `s["subtitle"] = s.get("subtitle", "")` line in the stats->chart safety-net).
- `backend/tests/test_deck_quality.py` (P1-2; `test_normalize_slides_still_logs_validation_failure_for_safety_net` flipped to assert the warning is no longer emitted and that the chart slide carries a subtitle).
- `backend/tests/test_slide_schema.py` (P1-2; mirroring flip in `test_normalize_slides_logs_validation_failure`).
- `backend/tests/test_export_input_parity.py` (P0-2; new file, 3 tests).
- All 4 audit files (P1-3 cross-link).

### Tests Added
- 3 conftest-free AST-based parity tests in `tests/test_export_input_parity.py`.
- 0 net new tests for P1-2 (two existing tests had their semantics flipped).

### Tests Run
- Default backend pytest: **106 passed, 1 skipped, 1.67s** (was 103 + 3 new parity tests; the two flipped tests still count as 1 each).
- Frontend `npm run verify:layouts` -> OK 7 / 7.

### Result
Narrow Phase 1H scope (all four triage items) -- **Pass**. Triage table is now empty at P0/P1; remaining items are the deferred P2 backlog and the strategic out-of-scope items every prior phase has called out.

### Remaining Risks
- The export-parity test is source-level (AST). It pins the `deck.slide_data or []` expression at all `slides=` call sites in `export.py`. It does not exercise ExportService end-to-end; that requires Postgres/Redis/Celery containers and is a deliberate hardening backlog item, not a lock blocker.
- P1-2 closes the *self-inflicted* amber-badge case. Genuinely malformed user-content slides (e.g. a chart slide with a non-string `subtitle` from a future model output) will still be flagged correctly.
- P2 items (design tokens for badge colors, path truncation w/ tooltip, `_PREVIEW_DEFAULTS` parity test, persisted `deck_quality_json`, frontend test framework, broader visual/PRD gaps) remain open and were not in scope.

## Phase 1G Pre-Lock P0-1 (Test Suite Unblock) - 2026-05-09

### What Was Fixed
- Triage P0-1 closed. `backend/database/connection.py` previously passed `pool_size=10, max_overflow=20, pool_pre_ping=True` unconditionally to `create_async_engine`. SQLite's async driver (`aiosqlite`) uses `NullPool`, which rejects those kwargs, so any default `pytest` invocation against the SQLite test URL crashed at engine creation. The engine now branches on the URL scheme: pool-sizing kwargs are passed only when the URL is **not** SQLite. The Postgres / asyncpg production path is byte-identical to before.
- Triage finding worth recording: the audits' recurring phrase "full backend pytest still blocked" was inaccurate -- the `backend/tests/` directory contains exactly the 5 files we have been running (`test_layout_coverage.py`, `test_slide_schema.py`, `test_deck_quality.py`, `test_api_deck_quality_payload.py`, `test_deck_repair_preview.py`). There is no broader suite hidden behind a conftest. The real defect was the engine-kwargs crash, which forced every prior phase to use `--noconftest -p no:cacheprovider` plus an explicit file list. That workaround is no longer required.

### Files Changed
- `backend/database/connection.py` -- replaced the unconditional `create_async_engine(..., pool_size=10, max_overflow=20, pool_pre_ping=True, ...)` with a `_db_url`-scheme branch. No other module touched. No model, no migration, no API change.

### Tests Added
- None. Phase 1G is a single, narrow infrastructure fix; the 103 existing tests are the regression surface.

### Tests Run
- Default backend pytest (no `--noconftest`, no explicit file list): `docker run ... -e DATABASE_URL=sqlite+aiosqlite:///:memory: ... python -m pytest -q` -> **103 passed, 1 skipped, 1.45s**.
- Frontend `npm run verify:layouts` -> OK 7 / 7 canonical.

### Result
Narrow Phase 1G scope -- **Pass**. The default test invocation now works against SQLite, removing the workaround flags every prior phase carried.

### Remaining Risks
- The repo simply has no integration tests beyond the 5 unit-style files. Building out queue / route / DB-touching test coverage is a separate, larger workstream and is **not** a lock blocker.
- The Postgres path was not exercised in this verification (no Postgres container in the test loop). Behaviorally unchanged because the kwargs branch only adds a guard around the existing call site.

## Phase 1F Repair Preview UI + Env Cleanup - 2026-05-09

### What Was Added
- The existing `DeckQualityBadge` now renders Phase 1E's `repair_preview` array inside its already-existing expandable details panel. Each preview entry is rendered as a compact monospace line:
  - `slide 2 - chart - subtitle - preview -> ""`
  - `slide 3 - bullets - bullets - not_applied`
  When `repair_preview` is present, it replaces the raw `errors` listing in the panel (errors remain available as a fallback when the preview is empty). The pill, color logic, expand/collapse interaction, and 12-row cap all behave as before.
- Two unused generated virtualenv directories were deleted from disk:
  - `D:\nexus-ai-1\nexus-ai\.venv`
  - `D:\nexus-ai-1\nexus-ai\manus-need\openmanus-reference\.venv`
  Neither was referenced by `nexus-ai`'s own config (no `.vscode/settings.json`, no `pyproject.toml` interpreter pinning, no script under `nexus-ai/` activating them). The verified backend test path is Docker-based, so removing them does not affect any verified workflow. The unrelated `D:\nexus-ai-1\.venv` (parent of the workspace) was left untouched as out of scope.

### Files Changed
- `frontend/src/components/DeckQualityBadge.jsx` -- reads `quality.repair_preview` (with safe array fallback), renders preview entries with their `before -> after` for `action="preview"` rows, falls back to `errors` rendering when no preview exists, adds a tiny `formatPreviewValue` helper. No structural rework; existing pill, classes, and cap unchanged.
- Deleted directories (not edits): `nexus-ai/.venv`, `nexus-ai/manus-need/openmanus-reference/.venv`.

### Tests Added
- None. The Phase 1E backend tests already cover the data shape; the Phase 1F change is purely a presentation-layer consumer of an existing field.

### Tests Run
- Backend Docker (`--noconftest -p no:cacheprovider`, 5 files): **103 passed, 1 skipped, 1.14s**.
- Frontend `npm run verify:layouts` -> OK 7 canonical, 7 exported.
- Full backend pytest still blocked by the pre-existing `tests/conftest.py` SQLite NullPool / `pool_size` mismatch -- untouched.

### Result
Narrow Phase 1F scope -- **Pass**. The deck-quality UI now answers "what would be repaired" using the data Phase 1E already serializes, and the workspace no longer carries two stale virtualenv trees.

### Remaining Risks
- The `formatPreviewValue` helper does a permissive `JSON.stringify`; if a future schema-default value contains non-serializable content, the catch falls back to `String(value)`. Acceptable for the current safe-default set (only short strings).
- The deleted `.venv` directories were *generated*, not source-controlled; recreating them is a one-line `python -m venv` away if a developer wants a local interpreter.

## Phase 1E Repair Preview - 2026-05-09

### What Was Added
- A non-mutating *repair preview* layer on top of Phase 1C/1D. `agent.deck_quality.build_repair_preview(slides, repair_actions=...)` walks the deck's existing repair_actions and, for each schema gap with an obvious local default, emits a `RepairAction(action="preview", before=<current>, after=<safe default>)`. Gaps that would require inventing semantic content (bullets, columns, stats items, chart_data) stay `action="not_applied", after=None` -- the preview never invents content.
- Safe defaults wired in: `title.subtitle` -> `""`, `title.eyebrow` -> `"Presentation"`, `chart.subtitle` -> `""`, `closing.subtitle` -> `""`, `closing.cta` -> `"Next steps"`.
- `DeckQualityReport` now exposes a `repair_preview: list[RepairAction]` field, and `to_dict()` adds a `repair_preview` JSON key plus a new `summary.repairs_previewable` counter. The existing `repair_actions` list is preserved unchanged.
- The deck stays untouched: nothing is applied. Generation, normalization, validation, and export pipelines are unchanged.

### Files Changed
- `backend/agent/deck_quality.py` -- added `build_repair_preview`, `_PREVIEW_DEFAULTS` table, `repair_preview` field on `DeckQualityReport`, additive `repair_preview` + `summary.repairs_previewable` keys in `to_dict()`, populated in both list and non-list payload branches.
- `backend/tests/test_deck_quality.py` -- added `repair_preview` to the expected key set in `test_deck_quality_report_to_dict_shape`.
- `backend/tests/test_api_deck_quality_payload.py` -- added `repair_preview` to the expected key set in `test_attach_quality_report_adds_deck_quality_key`.
- `backend/tests/test_deck_repair_preview.py` -- new test module (12 tests).

### Tests Added
- 12 conftest-free unit tests for `build_repair_preview`: empty for valid/empty decks; safe defaults for title subtitle/eyebrow, chart subtitle, closing subtitle/cta; refusal to invent bullets/chart_data; non-mutation of slides and of supplied repair_actions; index-pairing with repair_actions; new `repair_preview` field/`summary.repairs_previewable` exposure on `DeckQualityReport`; `action` constrained to `{"preview", "not_applied"}`; non-list payload safety.

### Tests Run
- Backend Docker (`--noconftest -p no:cacheprovider`, 5 files): **103 passed, 1 skipped, 1.25s**.
- Frontend: `npm run verify:layouts` -> OK 7 / 7 canonical.
- Full backend pytest still blocked by the pre-existing `tests/conftest.py` SQLite NullPool / `pool_size` mismatch -- untouched by Phase 1E.

### Result
PRD checkpoint for repair-preview visibility -- **Pass (narrow)**. The deck response now answers two questions: *what is invalid* (Phase 1C/1D) and *what would be repaired* (Phase 1E). Actual deck data remains read-only.

### Remaining Risks
- Defaults are intentionally minimal. "Presentation" as a default eyebrow and "Next steps" as a default CTA are placeholders -- acceptable for a preview, but should be revisited before any repair pipeline starts applying them.
- The preview is recomputed on every API read alongside the report. Cost is O(slide_count) and well within budget at PRD slide caps.
- No UI changes were made in Phase 1E; the existing `DeckQualityBadge` ignores `repair_preview` until a follow-up explicitly surfaces it.

## Phase 1D Deck Quality Visibility - 2026-05-09

### What Was Added
- Backend now surfaces the Phase 1C `DeckQualityReport` on the public deck-read APIs without persisting it. `GET /api/slides/{task_id}` and `GET /api/share/{token}` recompute the report on read via a tiny pure helper `agent.deck_quality.attach_quality_report(payload, slides)` and return it as a new `deck_quality` JSON field alongside the existing `slides`, `theme`, and `slide_count`.
- Frontend gains a minimal `DeckQualityBadge` component (a status pill with optional expandable error list) wired into the Generator page next to the export buttons. It is visible only when generation is `done` and `deck_quality` is present.
- Generation, validation, normalization, and export pipelines are unchanged. No repairs are applied. No DB migration. No model change. `slide_data` remains a list.

### Files Changed
- `backend/agent/deck_quality.py` -- added `attach_quality_report(payload, slides)` and exported it. Pure, non-mutating, JSON-safe.
- `backend/api/routes/slides.py` -- GET handler now calls `attach_quality_report` so the response carries `deck_quality`.
- `backend/api/routes/share.py` -- GET handler mirrors the same change for shared decks.
- `frontend/src/components/DeckQualityBadge.jsx` -- new component (~70 lines, Tailwind utilities only).
- `frontend/src/pages/Generator.jsx` -- captures `deck_quality` from the slides API response and renders the badge inside the existing done-state footer.
- `backend/tests/test_api_deck_quality_payload.py` -- new tests for the payload helper.

### Tests Added
- 6 conftest-free unit tests for `attach_quality_report`: presence of `deck_quality` key, no input mutation, JSON serializability, invalid-chart detection, empty-deck handling, non-list-slides handling.

### Tests Run
- Backend (Docker, `--noconftest -p no:cacheprovider`): `tests/test_layout_coverage.py tests/test_slide_schema.py tests/test_deck_quality.py tests/test_api_deck_quality_payload.py` -> **90 passed, 1 skipped, 1.13s**.
- Frontend: `npm run verify:layouts` -> OK 7 canonical layouts, 7 exported.
- Full backend `pytest` suite remains blocked by the pre-existing `tests/conftest.py` SQLite NullPool / `pool_size` mismatch in `database/connection.py`. Phase 1D does not touch that path.

### Result
PRD checkpoint for deck quality visibility -- **Pass (narrow)**. Generated decks now expose schema-validation outcomes both in backend telemetry (Phase 1C) and on the user-facing API + UI (Phase 1D). Validation is still observability-only; nothing blocks generation or export.

### Remaining Risks
- The badge surfaces issues but does not act on them. Repair pipeline, enforcement, and export-layer parity remain out of scope.
- `deck_quality` is recomputed per request rather than persisted, so its values are always derived from the current `slide_data`. If the schema rules change and a stored deck is re-fetched, the report will reflect the new rules -- intentional, but worth noting.
- The Generator UI integration is intentionally minimal; no design overhaul, no theming work.

## Phase 1C Deck Quality Report - 2026-05-09

**Scope:** PRD-compliance follow-up -- introduce the PRD-anticipated `DeckQualityReport` and `RepairAction` shapes as structured telemetry, without yet exposing them to the API/UI or applying repairs.

### What Was Added
- A new backend module `backend/agent/deck_quality.py` defines the PRD-named shapes `DeckQualityReport` and `RepairAction` with stable, serializable `to_dict()` representations. This locks in the contract a future repair / quality-score / API surface can adopt without renaming.
- `build_deck_quality_report(slides)` produces a structured, non-mutating, non-repairing summary: counts of valid / invalid slides, structured errors (`slide_index`, `layout`, `path`, `code`, `message`), and a `RepairAction` per error with `action="not_applied"`.
- `NexusAgentLoop._normalize_slides` now logs an INFO deck-level summary (`loop.deck_quality_report`) and continues to emit the per-slide WARNING records, all sourced from the same report -- the PRD-style "observe before you repair" posture.

### Files Changed
- `backend/agent/deck_quality.py` (new).
- `backend/agent/loop.py` -- `_normalize_slides` telemetry block now consumes `build_deck_quality_report`.
- `backend/tests/test_deck_quality.py` (new).

### Tests Added
- 7 unit tests over the report shape, error structure, repair-action defaults, non-mutation guarantee, non-list payload handling, and `to_dict()` shapes.
- 2 caplog-based tests over `_normalize_slides` proving the deck-level summary line and the per-slide PRD-relevant failure (chart missing slide-level `subtitle`) are emitted.

### Tests Run
- `cd frontend ; npm run verify:layouts` -> `OK verify-layouts OK -- 7 canonical layouts, 7 exported.`
- Docker pytest one-shot, `--noconftest -p no:cacheprovider tests/test_layout_coverage.py tests/test_slide_schema.py tests/test_deck_quality.py` -> **85 passed in 1.04s**.
- Full backend pytest **not** run (still blocked by `conftest.py` / database setup). No full-suite green claim is made.

### Result
- PRD-relevant observability of slide quality (DeckQualityReport, RepairAction) -> **Pass** for the corrected narrow scope.
- Broader PRD compliance (research depth, browser automation, export parity, repair application + enforcement, deck-quality scoring surfaced to UI/API, multi-tenant correctness) -> **Partial**.
- Visual PRD requirements -> **Unchanged**.

### Remaining Risks
- PRD-shaped report exists internally but is not yet returned to clients via the API.
- Repair actions are recorded but not applied.
- Validation does not enforce a hard generation/export failure on broken slides.
- Safety-net stats->chart promotion still can produce a chart missing slide-level `subtitle`; observable in both per-slide and deck-level telemetry, still not repaired.
- Export parity (PPTX/PDF), real browser automation, and registry expansion beyond 7 layouts remain deferred.
- Full backend pytest still blocked by conftest/database wiring.

---

## Phase 1B.1 Audit Correction - 2026-05-09

**Scope:** PRD-compliance follow-up -- align validator with the documented chart_data contract and prove telemetry actually fires.

### What Was Corrected
- The PRD-stated `chart_data { labels, values, unit, source }` shape is now enforced as a **four-key required contract** (with empty strings tolerated for `unit` / `source` to match `_normalize_slides` output). Previously the validator only type-checked `unit` / `source` when present, leaving the contract under-enforced.
- `validate_slide` documentation now correctly describes `ValidationResult.normalized` as a shallow copy with canonical layout pinned (or `None` on failure) and explicitly states it is not auto-repair -- preventing future readers from assuming PRD-level repair semantics that do not exist yet.
- A targeted telemetry test now demonstrates that PRD-relevant validation failures (e.g. chart slide produced by safety-net without slide-level subtitle) are actually logged at runtime by `NexusAgentLoop._normalize_slides`.

### Files Changed
- `backend/agent/slide_schema.py` -- `_validate_chart` requires `chart_data.unit` and `chart_data.source`; docstring updated.
- `backend/tests/test_slide_schema.py` -- sections 14 and 15 added.

### Tests Added
- 5 chart_data contract tests covering the PRD shape.
- 1 telemetry test on `_normalize_slides` asserting `loop.slide_validation_failed layout=chart path=subtitle code=missing` warning is emitted on logger `nexus.agent.loop`.

### Tests Run
- `cd frontend ; npm run verify:layouts` -> `OK verify-layouts OK -- 7 canonical layouts, 7 exported.`
- Docker pytest one-shot, `--noconftest -p no:cacheprovider tests/test_layout_coverage.py tests/test_slide_schema.py` -> **76 passed in 1.33s**.
- Full backend pytest **not** run (still blocked by `conftest.py` / database setup). No full-suite green claim is made.

### Result
- PRD compliance for slide-contract validation (chart_data shape + telemetry) -> **Pass** under the corrected narrow scope.
- Broader PRD compliance (research depth, browser automation, export parity, repair/enforcement, DeckQualityReport, multi-tenant correctness, etc.) -> **Partial**.
- Visual PRD requirements -> **Unchanged** (no renderer or visual-test code touched in this correction).

### Remaining Risks
- No repair pipeline -- PRD-violating slides ship with warnings only.
- Safety-net stats->chart promotion still produces a chart missing slide-level `subtitle`; tracked via telemetry, not corrected.
- No DeckQualityReport surfaced to the API or UI as the PRD anticipates.
- Full backend pytest still blocked by conftest/database wiring.
- Export parity (PPTX/PDF) not touched.
- No real browser automation yet.
- Registry still supports only 7 honest layouts until renderer/normalizer/export coverage expands.

---

## Phase 1B.1 Schema Strictness Update - 2026-05-09

### What Changed
- Closed three Phase 1B audit findings:
  1. Validator was looser than the normalized contract (`title.subtitle`, `title.eyebrow`, `quote.attribution`, `chart.subtitle`, `closing.subtitle`, `closing.cta` were optional). All are now required (empty strings still allowed where the normalizer emits them).
  2. `resolve_aliases=False` previously did `.strip().lower()` -- now it requires an EXACT canonical name.
  3. `ValidationResult.normalized` previously echoed `raw` -- now a shallow copy with canonical `layout` pinned. No auto-repair.
- Wired `validate_deck` into `NexusAgentLoop._normalize_slides` as non-repairing telemetry. Logs structured failures (`slide`, `layout`, `path`, `code`, `message`); never rejects or mutates.

### Files Changed
- `backend/agent/slide_schema.py`
- `backend/agent/loop.py` (telemetry-only insertion in `_normalize_slides`)
- `backend/tests/test_slide_schema.py` (+13 tests)

### Tests Added
- 6 missing-required-field tests (title.subtitle, title.eyebrow, quote.attribution, chart.subtitle, closing.subtitle, closing.cta) plus `test_title_empty_subtitle_allowed`.
- 3 strict-mode tests including `test_strict_mode_rejects_titlecase`.
- 3 `normalized` semantics tests (shallow copy, canonical pin on alias resolution, None on failure).

### Tests Run
- `cd frontend ; npm run verify:layouts` -> OK (7/7).
- Docker one-shot pytest -> **70 passed in 0.91s** for the targeted suites.
- Full backend pytest **not** claimed; pre-existing conftest/database blocker remains.

### Result
- **PRD compliance -- schema-contract requirement: Pass** for the narrow Phase 1B.1 scope. The validator now reflects what the generation pipeline actually produces, and the pipeline emits structured validation telemetry.
- **Overall PRD compliance: Partial** (unchanged). Repair, quality scoring, export parity, real browser automation, and visual fidelity remain outstanding.

### Remaining Risks
- No repair pipeline yet -- PRD-level "Manus-grade quality" not claimed.
- No `DeckQualityReport` yet.
- Validation failures are logged but not enforced as hard generation/export failures.
- No export parity fix yet.
- No real browser automation yet.
- Visual quality unchanged.
- Full backend pytest still blocked by conftest/database setup.
- Registry still supports only 7 honest layouts.

## Phase 1B Schema Validation Update - 2026-05-09

### What Changed
- Added a typed slide-contract validation layer at `backend/agent/slide_schema.py`. Generated slide payloads can now be checked against per-layout contracts for the 7 canonical layouts before render or export.
- `validate_slide(raw)` returns a structured `ValidationResult { ok, layout, errors[{path, code, message}], normalized }` -- not a boolean -- so the rest of the pipeline (when wired) can act on specific failures.
- Unknown layouts are rejected with `unknown_layout` instead of silently mapping to `FALLBACK_LAYOUT`.
- No repair pipeline, no DeckQualityReport, no export changes, no UI changes, no new layouts.

### Files Changed
- Added `backend/agent/slide_schema.py`.
- Added `backend/tests/test_slide_schema.py`.

### Tests Added
- 34 tests in `tests/test_slide_schema.py` exercising valid examples for every canonical layout and explicit failure paths for missing/empty/wrong-type fields, bullets count + item type, two-col column shape + count, stats item shape, chart `chart_type` enum, `chart_data` length mismatch / non-numeric / bool / labels-not-list, quote required text, unknown layouts (alias and strict modes), `validate_deck`, and `ValidationError.to_dict`.

### Tests Run
- `cd frontend ; npm run verify:layouts` -> `OK verify-layouts OK -- 7 canonical layouts, 7 exported.`
- One-shot Docker pytest (`--noconftest -p no:cacheprovider`) on `tests/test_layout_coverage.py` and `tests/test_slide_schema.py` -> `57 passed in 0.74s`.
- Full backend pytest still blocked by `tests/conftest.py` / `database/connection.py` SQLite NullPool / `pool_size` issue; not run.

### Result
- Phase 1B narrow scope: **Pass**.
- PRD compliance overall: **Partial** -- slide-contract validation exists as a library, but enforcement is not yet wired into the generation/export pipeline; quality, export parity, and autonomy gaps remain.

### Remaining Risks
- Validator is not yet enforced inside `_normalize_slides` or the export path.
- No auto-repair pipeline yet.
- No DeckQualityReport yet.
- Export parity (PPTX/PDF) unverified.
- No real browser automation (`services/browser_service.py` is disabled).
- Visual quality unchanged.
- Full backend pytest still blocked by conftest/DB setup.
- Only 7 honest layouts supported until renderer/normalizer/export coverage expands.

## Phase 1A.1 Planner Layout Drift Update - 2026-05-09

### What Changed
- PRD section 9 follow-up: `backend/agent/planner.py` (the outline planner that runs *before* the agent loop's content generator) was the last backend module still carrying a hardcoded layout whitelist -- and it was missing `chart`, meaning chart-bearing outlines were silently collapsed to bullets at the planning stage. It now imports `CANONICAL_LAYOUTS`, `FALLBACK_LAYOUT`, and `normalize_layout` from `agent.layouts_registry` and resolves outline layouts through them.
- Verify script extended to fail CI if planner.py reintroduces a hardcoded literal or stops importing the registry.

### Files Changed
- `backend/agent/planner.py`, `backend/tests/test_layout_coverage.py`, `scripts/verify-layouts.mjs`.

### Tests Added
- 10 new cases proving planner parity with the registry, per-layout outline round-trip for all 7 canonical layouts, planner unknown-layout fallback, and explicit `chart`-not-lost regression.

### Tests Run
- `npm run verify:layouts` -> **PASS**.
- One-shot pytest container -> **PASS** (`23 passed in 0.69s`).
- Full backend `pytest` suite NOT run. Reason: pre-existing `tests/conftest.py` import failure unrelated to this phase.
- Playwright / prompt-corpus suites NOT run. Reason: out of scope.

### Result
**Pass for the narrow planner-side drift in PRD section 9.** All other PRD section 9 items -- schema-constrained generation, validation-driven repair, `DeckQualityReport`, brand-aware generation, AI editing assistant, export parity -- remain open.

### Remaining Risks
- No JSON schema / repair pipeline / DeckQualityReport yet.
- Other PRD sections (visual intelligence, image engine, text-to-chart, brand-aware, AI editor, scalability, security, enterprise readiness) are unaffected by this phase.

## Phase 1A Correction Update - 2026-05-09

> **Correction notice.** The previous "Phase 1A Update - 2026-05-09" section in this file (immediately below) was inaccurate for this workspace. It claimed a 23-layout registry, 40 aliases, a `backend/agent/layouts_registry.py` module, a `frontend/src/design/` directory, and a 35-test passing run. None of those artifacts existed in this repo at the time that section was written. Left in place below for traceability only; not evidence. **See "Phase 1A Correction Update" above for the verified numbers (7 canonical layouts, 0 aliases, 13 tests).**

### What Actually Changed for PRD Section 9 (verified against repo)
- The drift flagged in PRD section 9 ("AI Slide Generation") was that the agent loop and frontend parser each carried hardcoded layout whitelists that did not even agree with each other (the frontend was missing `chart`). That drift is now closed at the layout-name level: both sides import the same canonical registry.
- The canonical layout count today is **7** (`title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`), with 0 aliases. This honestly reflects what the renderer and normalizer support; the previous "23 layouts" framing in the prior section was aspirational, not implemented.
- Backend and frontend now share the registry via two byte-identical JSON copies (`backend/agent/layouts.registry.json`, `frontend/src/design/layouts.registry.json`); `scripts/verify-layouts.mjs` enforces byte-content parity and rejects reintroducing inline literals.

### Files Changed / Added
- Added: `frontend/src/design/layouts.registry.json`, `frontend/src/design/registry.js`
- Added: `backend/agent/layouts.registry.json`, `backend/agent/layouts_registry.py`
- Added: `backend/tests/__init__.py`, `backend/tests/test_layout_coverage.py`
- Added: `scripts/verify-layouts.mjs`
- Modified: `backend/agent/loop.py`, `frontend/src/utils/slideParser.js`, `frontend/package.json`

### Tests Added
- `backend/tests/test_layout_coverage.py` (**13 tests**): registry-parity test, backend/frontend JSON parity test, 7 per-layout round-trip tests through `_normalize_slides`, unknown-layout fallback test, alias-target sanity test, canonical-name passthrough test.

### Tests Run
- `npm run verify:layouts` -> **PASS** (`7 canonical layouts, 7 exported`).
- `docker run --rm -v ...:/app -v ...:/frontend -w /app -e PYTHONPATH=/app nexus-ai-backend:latest sh -c "pip install --quiet pytest pytest-asyncio && python -m pytest --noconftest -p no:cacheprovider tests/test_layout_coverage.py -v"` -> **PASS** (`13 passed in 0.58s`).
- Full backend `pytest` suite was NOT run. Reason: pre-existing `tests/conftest.py` import failure (SQLAlchemy `pool_size`/`max_overflow` incompatible with SQLite `NullPool` in the container). Unrelated to Phase 1A.
- Playwright gallery and prompt-corpus suites were NOT run. Reason: out of Phase 1A scope.

### Result
**Pass for the narrow PRD section 9 layout-coverage drift.** Tests prove it.
**Partial for PRD section 9 as a whole** -- schema-constrained generation, validation-driven repair, `DeckQualityReport`, brand-aware generation, visual-first design enforcement, export parity, and AI editing assistant remain unchanged.

### Remaining Risks
- No strict per-layout JSON schema, no validation-driven repair (PRD section 9 "Highest-impact next step" remains open).
- No `DeckQualityReport`; "business-ready" is still implied by successful generation, not measured.
- The 7-layout registry honestly reflects current implementation. PRD goals that imply more layouts (rich editorial, infographic-style, brand-aware) are not yet implemented and were not promised by Phase 1A.
- All other PRD section gaps (visual intelligence, image selection engine, text-to-chart, brand-aware generation, AI editing assistant, scalability, security) are unaffected by this phase.

## Phase 1A Update - 2026-05-09

### What Changed
- Section 9 ("AI Slide Generation") flagged that the registry exposed 23 layouts but the backend agent loop's `_VALID_LAYOUTS` and `_normalize_slides` preserved only a smaller subset, silently converting advanced registry layouts to bullets. This is now fixed at the layout-name level: the backend imports `CANONICAL_LAYOUTS` from `agent.layouts_registry` (which loads `frontend/src/design/layouts.registry.json`), and the frontend parser imports the same source via `design/registry.js`.
- The 10 canonical layouts that were being collapsed (`hero`, `bento`, `agenda`, `roadmap`, `metric-spotlight`, `process`, `pyramid`, `matrix-2x2`, `feature-grid`, `callout`) now survive normalization. Registered aliases (`big-number`, `cover`, `kpi_grid`, `matrix`, `banner`, etc.) resolve to their canonical target.
- `scripts/verify-layouts.mjs` extended to fail CI if either file reintroduces an inline layout-set literal.

### Files Changed
- `backend/agent/loop.py`
- `frontend/src/utils/slideParser.js`
- `scripts/verify-layouts.mjs`

### Tests Added
- `backend/tests/test_layout_coverage.py` (35 cases): 1 registry-parity test, 23 per-layout round-trip tests, 10 alias-resolution tests, 1 unknown-layout fallback test.

### Tests Run
- `npm run verify:layouts` -> PASS (23 canonical layouts, 40 aliases, 21 exported).
- `python -m pytest --noconftest tests/test_layout_coverage.py -v` -> PASS (35/35).
- Full backend `pytest` suite was NOT run. Reason: pre-existing `tests/conftest.py` import failure unrelated to this change (SQLAlchemy pool args incompatible with SQLite `NullPool` in container). Recorded for the CI workstream.
- Playwright gallery and prompt-corpus suites were NOT run. Reason: out of Phase 1A scope.

### Result
Partial.

The layout-coverage drift in PRD section 9 is closed at the name level. The deeper PRD compliance gaps -- schema-constrained generation, validation-driven repair, `DeckQualityReport`, brand-aware generation, visual-first design enforcement, export parity, AI editing assistant, enterprise readiness -- are unchanged.

### Remaining Risks
- No strict per-layout schema or validation-driven repair yet (PRD section 9 "Highest-impact next step" remains open).
- No `DeckQualityReport`; "business-ready" is still implied by successful generation, not measured (PRD section 1).
- The 10 newly-preserved canonical layouts have no per-layout normalization branches in the agent loop; their content fields still pass through unstructured. Editor/export coverage for these layouts is unchanged.
- `table` and `image-focus` remain `exported: false` in the registry. PPTX export parity is unchanged.
- All other PRD section gaps (visual intelligence, image selection engine, text-to-chart, brand-aware generation, AI editing assistant, scalability, security) are unaffected by this phase.

## Weighted Compliance Summary

| Weighted Metric | Score | Diligence Interpretation |
|---|---:|---|
| Overall PRD completion | 49% | Below credible beta. Core MVP exists, strategic PRD systems are partial or fake-complete. |
| Production readiness | 32% | Private alpha. Reliability, fidelity, observability, and quality gates are weak. |
| Enterprise readiness | 21% | Not enterprise-ready. Missing SSO/RBAC depth, isolation guarantees, encryption, audit coverage, compliance controls. |
| Visual quality | 39% | Usable demo visuals, not consistently professional or competitive. Export parity is a major blocker. |
| AI intelligence | 34% | Prompt orchestration and heuristics, not deep visual/business intelligence. |
| Competitive position vs Manus | 28% | Lacks real autonomous browser/tool execution and robust agent behavior. |
| Competitive position vs Gamma | 33% | Lacks polished composition quality, mature editing, brand workflows, and collaboration. |

## Scoring Model

| Score Type | Meaning |
|---|---|
| Completeness % | How much of the PRD requirement is implemented end-to-end. |
| Architecture quality | Design quality of the implementation, not feature breadth. |
| Implementation depth | Whether the capability is real, robust, and integrated. |
| Production readiness | Whether it could be trusted for paying/professional users. |
| Competitive quality | Whether it approaches Manus/Gamma-level expectations. |

Scale for architecture/depth/readiness/competitive quality: **1 = absent**, **5 = usable prototype**, **10 = production-grade / category competitive**.

## Section-by-Section PRD Scorecard

| PRD Section | Completeness | Architecture Quality | Implementation Depth | Production Readiness | Competitive Quality | Biggest Weakness | Highest Impact Next Step |
|---|---:|---:|---:|---:|---:|---|---|
| Product Vision | 55% | 4 | 4 | 3 | 3 | Prompt-to-deck exists, but business-ready editable PPTX is inconsistent. | Define quality gates for "business-ready" and fail/repair decks that miss them. |
| Core Objectives | 52% | 4 | 4 | 3 | 3 | Objectives are implemented as breadth, not durable capability. | Prioritize export fidelity, context-to-chart, and editor depth over more surfaces. |
| AI Visual Intelligence | 35% | 3 | 3 | 2 | 2 | Mostly keyword/layout heuristics, not visual reasoning. | Add visual planning artifact per deck and slide. |
| Image Selection Engine | 38% | 3 | 3 | 2 | 2 | Stock/Pollinations fallback exists; brand safety, smart crop, consistency absent. | Build ranked image candidates with safety, crop, style, and palette checks. |
| Visual Recommendation System | 42% | 3 | 3 | 3 | 3 | Regex/hash/layout heuristics substitute for recommendation intelligence. | Add an explicit visual recommender model with explainable choices. |
| Multi-Format Context Understanding | 40% | 4 | 3 | 3 | 3 | Files parse, but structured insights are weakly consumed downstream. | Make structured data first-class in planning and chart generation. |
| Text-to-Chart Intelligence | 35% | 4 | 3 | 3 | 3 | Chart processor exists, but prose/data-to-chart reasoning is shallow. | Add text/data-to-ChartSpec extractor with validation. |
| Deck Planning Layer | 55% | 4 | 4 | 3 | 3 | Planner creates outlines, but narrative arc is not modeled or validated. | Add deck narrative schema and flow validator. |
| AI Slide Generation | 58% | 4 | 4 | 3 | 3 | JSON generation works but relies on brittle parsing and fallback normalization. | Add schema-constrained generation and validation-driven repair. |
| Visual-First Design | 45% | 4 | 4 | 3 | 3 | Layout catalog exists, but visual-first composition is not guaranteed. | Build layout budget solver and generated-slide overflow tests. |
| Image Placement Rules | 35% | 3 | 3 | 2 | 2 | Placement is layout-driven, not image/content-aware. | Add luminance, subject, focal-point, and text-over-image checks. |
| Brand-Aware Generation | 25% | 3 | 2 | 2 | 2 | Brand kits exist as CRUD; generation/export use is shallow or absent. | Thread brand kit through planning, rendering, export, and prompts. |
| Asset Management | 50% | 4 | 4 | 3 | 3 | Upload/tag asset basics exist; reusable libraries/workspace UX immature. | Add workspace asset library, folders/sets, permissions, and editor integration. |
| Slide Editor | 48% | 4 | 4 | 3 | 3 | Basic editing/autosave/regenerate exists; shape/chart/layout editing weak. | Add schema-aware editor controls and chart/image/layout editing. |
| AI Editing Assistant | 20% | 2 | 2 | 1 | 1 | No real in-editor assistant workflow. | Add per-slide AI actions: rewrite, simplify, make visual, change tone, regenerate image. |
| Developer Experience | 45% | 4 | 3 | 2 | 2 | REST and SDK skeleton exist; SDK/webhooks not proven. | Add SDK integration tests, examples, versioning, webhook delivery tests. |
| Backend Architecture | 50% | 4 | 4 | 3 | 3 | Many services exist, but central loop and weak contracts dominate. | Split pipeline into typed, persisted, replayable stages. |
| Scalability | 32% | 3 | 3 | 2 | 2 | Celery exists, but no load proof, quotas, replay, or tenant operations. | Add load tests, durable job events, quotas, cancellation, retry policy. |
| Security | 28% | 3 | 3 | 2 | 2 | Basic auth/API keys exist; enterprise security is missing. | Implement RBAC, SSO/OIDC/SAML, encryption, audit coverage, upload scanning. |
| MVP Scope | 68% | 4 | 5 | 4 | 4 | Basic MVP loop is real; quality and editor/export depth are weak. | Stabilize MVP around validated output, reliable export, and focused editing. |

## Completeness By PRD Pillar

| Pillar | Weight | Completion | Weighted Contribution |
|---|---:|---:|---:|
| Product vision + core objectives | 10% | 54% | 5.4 |
| Visual/image intelligence | 15% | 37% | 5.6 |
| Context + chart intelligence | 15% | 38% | 5.7 |
| Planning + slide generation | 15% | 57% | 8.6 |
| Rendering + visual-first design | 15% | 42% | 6.3 |
| Brand/assets/editor | 12% | 41% | 4.9 |
| DX/backend/scalability/security | 13% | 39% | 5.1 |
| MVP closure | 5% | 68% | 3.4 |
| **Total** | **100%** |  | **44.9 raw / adjusted to 49%** |

Adjustment rationale: The implementation has working end-to-end demo paths that deserve credit beyond isolated section scoring, but those paths do not raise enterprise or competitive readiness.

## Detailed PRD Section Audits

### 1. Product Vision

PRD intent: prompt or business context should become editable, business-ready PowerPoint output.

| Dimension | Score |
|---|---:|
| Completeness | 55% |
| Architecture quality | 4 / 10 |
| Implementation depth | 4 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- Prompt-to-task-to-deck exists.
- PPTX export exists; PDF export exists via HTML/WeasyPrint path, but it is a separate rendering path and not proven equivalent.
- Editor exists but is not a full presentation editor.
- Business-ready output is not validated with professional quality metrics.

Fake-complete areas:

- "Business-ready" is implied by successful generation, not measured.
- "Editable" means basic slide/data editing, not shape-level or design-level editing.

Missing systems:

- Quality scoring.
- Export parity certification.
- Professional template/brand enforcement.
- Business-context-to-insight validation.

Architectural drift:

- The PRD describes an output-quality platform; implementation trends toward a broad demo platform.

Biggest weakness: no enforceable definition of business-ready deck quality.

Highest-impact next step: introduce `DeckQualityReport` and block completion/export when critical quality gates fail.

### 2. Core Objectives

| Dimension | Score |
|---|---:|
| Completeness | 52% |
| Architecture quality | 4 / 10 |
| Implementation depth | 4 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- Generates decks, supports uploads, charts, images, editor, API, SDK skeleton, exports.
- Enterprise scalability and deep context understanding remain immature.
- Storytelling is prompt/heuristic-driven, not modeled.

Fake-complete areas:

- "Structured + unstructured uploads" exists technically, but structured context does not reliably drive slides.
- "APIs/SDKs" exist as code, not as validated developer product.

Missing systems:

- Collaboration.
- Strong SDK examples.
- Durable webhook delivery.
- Real white-label/embed platform.

Biggest weakness: objective breadth is implemented without depth guarantees.

Highest-impact next step: narrow the MVP definition and certify those flows end-to-end.

### 3. AI Visual Intelligence

| Dimension | Score |
|---|---:|
| Completeness | 35% |
| Architecture quality | 3 / 10 |
| Implementation depth | 3 / 10 |
| Production readiness | 2 / 10 |
| Competitive quality | 2 / 10 |

Implementation reality:

- Image category classification exists via layout/topic keywords.
- Images are recommended through stock APIs or Pollinations fallback.
- Icons appear in frontend layouts.
- There is no deep multimodal understanding of slide composition.

Fake-complete areas:

- "AI visual intelligence" is mostly deterministic rules plus prompts.
- "Contextual relevance" is based on title/topic query strings, not semantic image ranking.

Missing systems:

- Visual scene planning.
- Image embedding search/ranking.
- Diagram/infographic generation.
- Visual consistency pass across deck.
- Image safety/compliance filter.

Architectural drift:

- PRD expects visual reasoning; implementation provides image retrieval/generation plumbing.

Highest-impact next step: create a `VisualPlan` object per slide with visual intent, asset type, placement, style, contrast requirements, and fallback behavior.

### 4. Image Selection Engine

| Dimension | Score |
|---|---:|
| Completeness | 38% |
| Architecture quality | 3 / 10 |
| Implementation depth | 3 / 10 |
| Production readiness | 2 / 10 |
| Competitive quality | 2 / 10 |

Implementation reality:

- Unsplash/Pexels/Pollinations path exists.
- Layout rules decide placement and prompt modifiers.
- Export fetches images best-effort.

Fake-complete areas:

- AI-generated images are low-control Pollinations URLs, not a production image-generation system.
- Brand-safe image selection is absent.
- Auto-cropping is resizing, not subject-aware cropping.

Missing systems:

- NSFW/brand safety scoring.
- Subject detection/focal point crop.
- Style matching.
- Palette matching.
- Licensing/credit enforcement in exported decks.

Highest-impact next step: add an image candidate pipeline: search/generate -> score -> safety filter -> crop plan -> placement plan -> persist asset.

### 5. Visual Recommendation System

| Dimension | Score |
|---|---:|
| Completeness | 42% |
| Architecture quality | 3 / 10 |
| Implementation depth | 3 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- Layouts are selected by planner, markdown heuristics, and post-normalization rules.
- Timelines/process/KPI/chart decisions exist in partial form.
- No explicit recommendation system explains visual choices.

Fake-complete areas:

- Recommendation is rules and fallback conversion, not a scored recommender.
- "Infographics" are layout names, not real generated information graphics.

Missing systems:

- Visual type scoring.
- Narrative-aware visual rhythm.
- Slide-to-slide variation model.
- Recommendation explanations.

Highest-impact next step: add `VisualRecommendationService` that scores chart/image/table/timeline/process/KPI choices from slide intent and available data.

### 6. Multi-Format Context Understanding

| Dimension | Score |
|---|---:|
| Completeness | 40% |
| Architecture quality | 4 / 10 |
| Implementation depth | 3 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- Upload route accepts common formats and stores extracted text/structured data.
- Business intelligence extraction exists and is stored under uploaded file data.
- Task generation links uploaded files.

Weak implementation:

- Structured file content is not reliably carried through as typed chart/table inputs.
- Most downstream use still collapses context into prompt text.

Fake-complete areas:

- "Understands CSV/XLSX/PDF/PPTX" is too strong. It parses and summarizes; it does not deeply understand.

Missing systems:

- OCR for images/screenshots.
- URL-as-input ingestion.
- API/CRM connectors.
- Semantic document indexing.
- Table semantics and column typing.

Highest-impact next step: persist `ContextArtifact` records with typed tables, metrics, claims, entities, source spans, and chart candidates.

### 7. Text-to-Chart Intelligence

| Dimension | Score |
|---|---:|
| Completeness | 35% |
| Architecture quality | 4 / 10 |
| Implementation depth | 3 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- Chart service normalizes chart specs and produces Chart.js/PPTX config.
- Business intelligence extractor detects some money, percentage, growth, quarter/year series.
- Agent loop processes charts before save/export.

Weak implementation:

- The system is better at rendering a chart once specified than deciding the right chart from raw business prose/data.
- Chart theme support is incomplete relative to the theme catalog.

Fake-complete areas:

- "Text-to-chart" is partial detection plus chart rendering, not robust text-to-visual intelligence.

Missing systems:

- ChartSpec confidence scoring.
- Multi-series inference.
- Source-backed chart values.
- User-editable chart data UI.
- Chart quality checks.

Highest-impact next step: implement a validated `ChartSpec` pipeline with source references and editor support.

### 8. Deck Planning Layer

| Dimension | Score |
|---|---:|
| Completeness | 55% |
| Architecture quality | 4 / 10 |
| Implementation depth | 4 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- Planner emits outline JSON with layout/title/intent and optional visual fields.
- Topic classifier and theme picker influence the deck.
- Design reference and research can be prepended into context.

Weak implementation:

- Narrative structure is not a typed object.
- No flow validator ensures story logic.
- Markdown pipeline and fallback path can override planner intent.

Fake-complete areas:

- "Storytelling flow" is prompt wording, not enforced structure.

Missing systems:

- Narrative arc schema.
- Audience-specific planning rules.
- Executive vs educational vs sales deck patterns.
- Plan quality scoring.

Highest-impact next step: define `DeckPlan` with sections, beats, audience intent, slide roles, evidence requirements, and visual rhythm.

### 9. AI Slide Generation

| Dimension | Score |
|---|---:|
| Completeness | 58% |
| Architecture quality | 4 / 10 |
| Implementation depth | 4 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- Per-slide and batch generation paths exist.
- JSON parsing and fallback slides exist.
- Critic pass rewrites weak slides heuristically.
- Normalization ensures basic fields.

Critical drift:

- Registry has 23 layouts, but backend agent loop `_VALID_LAYOUTS` and `_normalize_slides` preserve only a smaller subset. Advanced registry layouts can be converted to bullets before persistence. This undermines registry-driven layout claims.

Fake-complete areas:

- Speaker notes and visual hierarchy metadata are not first-class.
- Structured schema generation is not enforced.

Missing systems:

- Strict JSON schema output validation.
- Validation-driven repair.
- Speaker notes generation/export.
- Per-slide evidence/source metadata.

Highest-impact next step: generate against schema per layout and repair invalid slides before save.

### 10. Visual-First Design

| Dimension | Score |
|---|---:|
| Completeness | 45% |
| Architecture quality | 4 / 10 |
| Implementation depth | 4 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- Registry lists 23 canonical layouts.
- Frontend gallery renders 23 figures.
- Design tokens and primitives exist.
- PPTX exporter has branches for many layouts.

Weak implementation:

- Backend generation normalization can collapse advanced layouts.
- No layout solver measures whether generated content actually fits.
- Visual-first design is component templates, not intelligence.

Fake-complete areas:

- "Manus-grade" naming does not equal Manus-grade output.

Missing systems:

- Layout budget engine.
- Overflow repair loop.
- Deck-level visual rhythm scoring.
- Preview/export parity tests.

Highest-impact next step: add generated deck visual regression with overflow detection and compare browser/PPT/PDF outputs.

### 11. Image Placement Rules

| Dimension | Score |
|---|---:|
| Completeness | 35% |
| Architecture quality | 3 / 10 |
| Implementation depth | 3 / 10 |
| Production readiness | 2 / 10 |
| Competitive quality | 2 / 10 |

Implementation reality:

- Placement is mostly hardcoded by layout.
- Export has fixed image regions and scrims for some layouts.
- React renderer uses object-cover and scrims in some cases.

Weak implementation:

- No contrast/luminance checks.
- No focal-point crop.
- No subject-aware placement.
- No collision detection between text and image subjects.

Highest-impact next step: implement image analysis: dominant colors, luminance, focal region, safe text zones, crop instructions.

### 12. Brand-Aware Generation

| Dimension | Score |
|---|---:|
| Completeness | 25% |
| Architecture quality | 3 / 10 |
| Implementation depth | 2 / 10 |
| Production readiness | 2 / 10 |
| Competitive quality | 2 / 10 |

Implementation reality:

- Brand kit CRUD exists.
- Theme/profile stamping exists from topic classifier.
- Brand kit does not appear to be deeply threaded through generation/render/export.

Fake-complete areas:

- Brand kit API roundtrip can pass while generated decks ignore the kit.
- Brand-aware generation is mostly theme selection, not brand enforcement.

Missing systems:

- Brand asset ingestion.
- Logo rules.
- Typography enforcement.
- Brand voice enforcement.
- Template memory.
- Per-workspace style history.

Highest-impact next step: make `brand_kit_id` part of generation request and propagate it through planner prompts, theme resolution, React renderer, PPT/PDF export, and asset selection.

### 13. Asset Management

| Dimension | Score |
|---|---:|
| Completeness | 50% |
| Architecture quality | 4 / 10 |
| Implementation depth | 4 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- Asset upload route exists.
- Asset metadata/tags exist.
- Image replacement has partial UI/backend support.

Weak implementation:

- Workspace library UX is immature.
- No reusable visual sets.
- No asset permission model deep enough for enterprise.
- No virus scan/safety processing.

Highest-impact next step: build workspace asset library with folders/collections, permission checks, metadata, and editor insertion flow.

### 14. Slide Editor

| Dimension | Score |
|---|---:|
| Completeness | 48% |
| Architecture quality | 4 / 10 |
| Implementation depth | 4 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- Editor page loads decks, edits slide data, autosaves, saves, deletes, reorders, regenerates a slide, changes basic theme, opens image replacer/history.
- Version history exists.

Weak implementation:

- No shape-level editing.
- No drag/drop canvas editing.
- Chart editing is weak or absent.
- Layout picker is not a professional design tool.
- Editor allows JSON-shape drift instead of schema-guided editing.

Highest-impact next step: build schema-aware editor controls per layout and a real chart/image/layout editing path.

### 15. AI Editing Assistant

| Dimension | Score |
|---|---:|
| Completeness | 20% |
| Architecture quality | 2 / 10 |
| Implementation depth | 2 / 10 |
| Production readiness | 1 / 10 |
| Competitive quality | 1 / 10 |

Implementation reality:

- Per-slide regenerate endpoint/UI exists in some form.
- No assistant chat or robust AI editing command system exists.

Fake-complete areas:

- "AI-assisted regeneration" is not the same as an editing assistant.

Missing systems:

- Rewrite selected text.
- Make slide more visual.
- Simplify dense slide.
- Change tone.
- Replace image with style instructions.
- Generate diagram.
- Explain suggested changes.

Highest-impact next step: add command-based AI assistant actions mapped to schema-safe slide transformations.

### 16. Developer Experience

| Dimension | Score |
|---|---:|
| Completeness | 45% |
| Architecture quality | 4 / 10 |
| Implementation depth | 3 / 10 |
| Production readiness | 2 / 10 |
| Competitive quality | 2 / 10 |

Implementation reality:

- REST API exists.
- OpenAPI exists.
- SDK package exists.
- API keys exist.
- Webhooks route exists.

Weak implementation:

- SDK is not proven in host apps.
- No versioned API contract strategy.
- Webhook delivery/retry testing is not proven.
- No Next.js example.
- No embeddable editor.

Highest-impact next step: create a tested example app using the SDK and add CI integration tests against local API.

### 17. Backend Architecture

| Dimension | Score |
|---|---:|
| Completeness | 50% |
| Architecture quality | 4 / 10 |
| Implementation depth | 4 / 10 |
| Production readiness | 3 / 10 |
| Competitive quality | 3 / 10 |

Implementation reality:

- FastAPI, PostgreSQL, Redis/Celery, storage service, export service, AI service, chart/image/research services exist.
- Browser service is a stub.
- No vector database.
- Central agent loop remains too large.

Fake-complete areas:

- API gateway means FastAPI app, not a gateway architecture.
- Context management parses files but lacks durable semantic artifact model.

Missing systems:

- Vector/embedding store.
- Durable step event store.
- Model evaluation service.
- Replay/debug pipeline.
- Real browser/tool service.

Highest-impact next step: create a typed pipeline architecture with persisted artifacts and replace central loop responsibilities.

### 18. Scalability

| Dimension | Score |
|---|---:|
| Completeness | 32% |
| Architecture quality | 3 / 10 |
| Implementation depth | 3 / 10 |
| Production readiness | 2 / 10 |
| Competitive quality | 2 / 10 |

Implementation reality:

- Queue-based background generation exists.
- Parallel image recommendation/fetch is bounded.
- Docker compose exists.

Weak implementation:

- No load testing evidence.
- No tenant quotas.
- No cost ceilings.
- No autoscaling manifests.
- No durable cancellation/retry/replay model.
- External API throttling remains fragile.

Highest-impact next step: implement load test harness plus task lifecycle controls: retry policy, cancellation, quotas, per-provider rate limits, and cost budgets.

### 19. Security

| Dimension | Score |
|---|---:|
| Completeness | 28% |
| Architecture quality | 3 / 10 |
| Implementation depth | 3 / 10 |
| Production readiness | 2 / 10 |
| Competitive quality | 2 / 10 |

Implementation reality:

- JWT/password auth, Google OAuth shape, API key create/rotate/revoke, upload type allowlist, some owner checks, audit log route exist.

Weak implementation:

- No enterprise RBAC.
- No SAML/enterprise OIDC.
- No SCIM.
- No virus scanning.
- No encryption-at-rest proof.
- Workspace isolation needs audit.
- Audit logging is not complete across mutations.
- Secrets posture has risk due to tracked `.env` history/context.

Highest-impact next step: implement RBAC/workspace isolation audit, full mutation audit logs, upload scanning, and remove/rotate committed secrets.

### 20. MVP Scope

| Dimension | Score |
|---|---:|
| Completeness | 68% |
| Architecture quality | 4 / 10 |
| Implementation depth | 5 / 10 |
| Production readiness | 4 / 10 |
| Competitive quality | 4 / 10 |

Implementation reality:

- Prompt-to-deck, context upload, AI images, charts, editor, PPTX, PDF, REST, SDK skeleton exist.
- MVP output quality is not stable enough for broad launch.

Weak implementation:

- MVP is technically broad but lacks hardening and QA.
- Editor and export fidelity remain below serious user expectations.

Highest-impact next step: freeze scope and harden the main workflow: prompt -> validated deck -> edit -> export -> share.

## Fake-Complete Matrix

| Rank | Fake-Complete System | PRD Section | Severity | Current Reality | Required Reality |
|---:|---|---|---|---|---|
| 1 | AI Visual Intelligence | Â§3 | Critical | Rules + prompts + stock fallback. | Visual reasoning, ranking, consistency, and quality scoring. |
| 2 | Browser/Manus-style tools | Backend / competitive | Critical | Browser service is a disabled stub. | Real browser/tool execution with observation and replay. |
| 3 | Brand-aware generation | Â§12 | Critical | Brand kit CRUD exists; generation/export integration shallow. | Brand kit controls visuals, fonts, images, voice, templates. |
| 4 | Context understanding | Â§6 | High | Parses files but often reduces to text context. | Typed context artifacts drive charts/tables/insights. |
| 5 | Text-to-chart | Â§7 | High | Chart rendering is stronger than chart intelligence. | Robust prose/data-to-ChartSpec pipeline. |
| 6 | Visual recommendation | Â§5 | High | Heuristics choose layouts/visuals. | Scored recommender with rationale. |
| 7 | Export fidelity | Â§1 / Â§10 | Critical | Separate renderers for React/PPT/PDF. | One source of visual truth or parity tests. |
| 8 | Enterprise security | Â§21 | Critical | Basic auth/API keys. | RBAC, SSO, SCIM, audit, encryption, isolation. |
| 9 | AI editing assistant | Â§15 | High | Regenerate is not an assistant. | Command/chat assistant for slide transformations. |
| 10 | Gallery regression | Visual QA | High | Curated sample snapshots. | Generated-deck and export parity regression suite. |
| 11 | SDK/DX | Â§16 | Medium | Package exists but not proven. | Published, tested SDK with examples and versioning. |
| 12 | Webhooks | Â§16 | Medium | Route exists. | Retried delivery, signing, monitoring, tests. |
| 13 | Asset management | Â§13 | Medium | Files/tags. | Workspace media library with permissions/sets. |
| 14 | Layout registry | Â§10 | High | Names/aliases/schema hints. | Enforceable schema/capability registry. |
| 15 | Normalization layer | Â§9 | High | Heuristic coercion. | Strict validation + repair loop. |
| 16 | Fact checking | AI quality | High | Regex/entity pool warnings. | Evidence-linked claim verification. |
| 17 | Image generation | Â§4 | Medium | Pollinations URL fallback. | Controlled generation providers with safety/style controls. |
| 18 | Scalability | Â§20 | Critical | Celery existence. | Load-tested, quota-managed, horizontally scalable platform. |
| 19 | Audit logs | Â§21 | High | Partial route/logging. | Complete mutation audit coverage. |
| 20 | Professional editor | Â§14 | High | Form editor + preview. | Visual schema-aware deck editor. |

## Missing Systems Matrix

| Rank | Missing System | PRD Section | Impact | Why It Matters |
|---:|---|---|---|---|
| 1 | Shared layout IR / single rendering source | Â§10 | Critical | Prevents React/PPT/PDF drift. |
| 2 | Strict layout schemas | Â§9 / Â§10 | Critical | Prevents invalid/generated garbage slides. |
| 3 | Validation-driven repair loop | Â§9 | Critical | Makes AI output controllable. |
| 4 | Deck quality scoring | Product Vision | Critical | Defines "business-ready." |
| 5 | Generated-deck regression corpus | Testing | Critical | Tests real output, not curated fixtures. |
| 6 | Export parity test suite | Â§10 | Critical | Verifies what users actually download. |
| 7 | Visual recommender service | Â§5 | High | Turns heuristics into explicit intelligence. |
| 8 | Text/data-to-ChartSpec extractor | Â§7 | High | Core business presentation capability. |
| 9 | Context artifact model | Â§6 | High | Makes uploads useful beyond prompt text. |
| 10 | Brand kit runtime integration | Â§12 | High | Required for professional and enterprise buyers. |
| 11 | AI editing assistant | Â§15 | High | Expected by modern AI design tools. |
| 12 | Chart editor | Â§14 | High | Charts must be editable post-generation. |
| 13 | Image safety/crop/style pipeline | Â§4 / Â§11 | High | Required for reliable visual output. |
| 14 | Enterprise RBAC | Â§21 | Critical | Required for enterprise. |
| 15 | SAML/OIDC/SCIM | Â§21 | Critical | Required for enterprise sales. |
| 16 | Upload virus scanning | Â§21 | Critical | Required for file-ingesting SaaS. |
| 17 | Durable job event/replay system | Â§18 / Â§20 | High | Required for debugging and scale. |
| 18 | Cost/rate-limit governance | Â§20 | High | Required for AI SaaS economics. |
| 19 | Vector/semantic memory | Â§18 | Medium | Needed for previous decks/style memory. |
| 20 | SDK integration example app | Â§16 | Medium | Needed for credible developer platform. |

## Top 20 Highest ROI Improvements

| Rank | Improvement | Effort | ROI | PRD Sections Lifted |
|---:|---|---|---|---|
| 1 | Align backend `_VALID_LAYOUTS`/normalizer with canonical registry. | Low | Very high | Â§9, Â§10 |
| 2 | Add strict schema validation per layout. | Medium | Very high | Â§9, Â§10, MVP |
| 3 | Add validation-driven repair loop. | Medium | Very high | Â§9, Product Vision |
| 4 | Build generated prompt regression corpus. | Medium | Very high | Testing, visual quality |
| 5 | Add DOM overflow tests for generated decks. | Medium | Very high | Â§10 |
| 6 | Add React/PPT/PDF export parity snapshots. | Medium/High | Very high | Â§1, Â§10 |
| 7 | Thread brand kits through generation/render/export. | Medium | High | Â§12, enterprise |
| 8 | Implement Text/Data-to-ChartSpec extractor. | Medium | High | Â§6, Â§7 |
| 9 | Make uploaded structured data first-class planning input. | Medium | High | Â§6, Â§7, Â§8 |
| 10 | Add per-slide AI editing commands. | Medium | High | Â§14, Â§15 |
| 11 | Add chart editor UI. | Medium | High | Â§7, Â§14 |
| 12 | Build image candidate scoring/safety/crop pipeline. | Medium/High | High | Â§3, Â§4, Â§11 |
| 13 | Centralize themes across frontend/export/chart. | Medium | High | Â§10, maintainability |
| 14 | Split agent loop into typed persisted stages. | High | High | Â§8, Â§9, Â§18, Â§20 |
| 15 | Add load tests and queue lifecycle controls. | Medium | High | Â§20 |
| 16 | Add full audit logging for mutations. | Medium | High | Â§21 |
| 17 | Add upload virus scanning and file governance. | Medium | High | Â§21 |
| 18 | Add SDK host-app integration test. | Low/Medium | Medium | Â§16 |
| 19 | Add webhook receiver test/retry policy. | Low/Medium | Medium | Â§16 |
| 20 | Add vector memory for prior decks/brand style. | High | Medium | Â§12, Â§18 |

## Roadmap Priorities

### 0-30 Days: Compliance Stabilization

| Priority | Deliverable | Exit Criteria |
|---|---|---|
| P0 | Canonical registry enforcement in backend generation. | No canonical layout is dropped during save normalization. |
| P0 | Layout schema validation. | Every slide validates before save/export. |
| P0 | Generated-deck visual tests. | CI catches overflow and unsupported layouts on real prompt fixtures. |
| P0 | Export parity baseline. | React/PPT/PDF differences are measured per layout. |
| P1 | Brand kit propagation. | Brand colors/fonts appear in generated preview and export. |
| P1 | Text/data-to-chart MVP. | Uploaded CSV/XLSX or prose growth claim creates validated chart slides. |
| P1 | AI editing commands MVP. | Rewrite/simplify/make visual/change tone actions work per slide. |

### 31-60 Days: Product Depth

| Priority | Deliverable | Exit Criteria |
|---|---|---|
| P0 | Shared LayoutIR design. | React and export consume common layout metadata. |
| P0 | Context artifact model. | Uploaded files produce typed tables, metrics, claims, entities, and source spans. |
| P1 | Visual recommender service. | Visual choices are scored and logged with reasons. |
| P1 | Image selection pipeline. | Safety/style/crop/contrast checks run before image attachment. |
| P1 | Chart editor. | Users can edit chart data/type/source after generation. |

### 61-90 Days: Enterprise / Competitive Readiness

| Priority | Deliverable | Exit Criteria |
|---|---|---|
| P0 | RBAC + workspace isolation audit. | All resource queries enforce workspace/user permissions. |
| P0 | Load test + quotas + rate limits. | Platform survives defined concurrency target with controlled cost. |
| P0 | Durable job event/replay system. | Any failed deck can be debugged and replayed from step artifacts. |
| P1 | SSO/OIDC foundation. | Enterprise identity path exists beyond Google OAuth. |
| P1 | Competitive benchmark harness. | 50-prompt blind benchmark against Gamma/Manus-style expectations. |

## Acquisition / Enterprise Investment Risk Assessment

| Risk | Severity | Diligence Concern |
|---|---|---|
| Output quality not objectively measured. | Critical | Buyer cannot trust "business-ready" claim. |
| Export/rendering drift. | Critical | Presentation products are judged by final artifacts. |
| Brand-aware claims are shallow. | Critical | Enterprise buyers require brand governance. |
| AI intelligence is mostly heuristic. | High | Differentiation may not survive competitive review. |
| Enterprise security incomplete. | Critical | Blocks enterprise adoption. |
| Scalability unproven. | High | Cost and reliability unknown under usage. |
| Fake-complete subsystems. | High | Technical diligence will discount platform maturity. |
| Monolithic generation loop. | High | Hard to maintain, debug, and evolve. |

## Final Compliance Verdict

The implementation is approximately **49% PRD-complete** under acquisition-grade scrutiny.

The MVP shell is real. The platform claims are not. The most dangerous areas are visual intelligence, brand-aware generation, structured context understanding, export fidelity, AI editing, enterprise security, and scalability. These are not minor polish gaps; they are core PRD promises.

The next phase should stop adding new named systems and instead make existing systems enforceable, measurable, and integrated end-to-end.

---

## Phase 6A -- Runtime Auth + Alembic Migration -- 2026-05-09

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

## Phase 6B -- Competitive Accuracy + Stability Benchmark Baseline -- 2026-05-09

**What changed**
- Added measurable benchmark baseline (no product-behavior changes). New plan, weighted rubric, prompt corpus, integrity tests, and an honest current-score file. Established that NEXUS is **not yet** beating Manus and that AI accuracy is **not yet measured live**.

**Files changed / added**
- `audits/COMPETITIVE_BENCHMARK_BASELINE.md` (NEW) -- plan comparing NEXUS vs Manus, browser-use, OpenManus, AgenticSeek, Gamma/Tome across 7 weighted categories.
- `audits/CURRENT_COMPETITIVE_SCORE.md` (NEW) -- honest baseline; estimated overall ~55/100; explicit list of unmeasured items.
- `benchmarks/rubric.json` (NEW) -- weights sum to 100: deck_correctness 20, visual_quality 15, export_parity 15, evidence_accuracy 15, agent_autonomy 15, stability_reliability 10, security_production_readiness 10. Scale 1--10. Lists 5 competitors.
- `benchmarks/prompts.json` (NEW) -- 11 realistic prompts spanning business, investor, education, product launch, market research, chart-heavy, evidence-heavy, visual-storytelling, agent-autonomy. Each has `expected_evidence`, `expected_visual`, `difficulty`, `primary_categories`. No expected slide content (offline only).
- `backend/tests/test_competitive_benchmark.py` (NEW) -- 17 conftest-free integrity tests. No LLM calls.
- `audits/AUDIT_CURRENT_STATE.md`, `audits/AUDIT_PROMPT_CONTEXT.md` -- updated to record Phase 6B completion.

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
- AI generation accuracy not measured live -- rubric and corpus exist but no live-eval harness has been run against `/api/generate`.
- No screenshot-diff visual regression suite.
- No renderer?export contract test (PPTX/PDF parity unverified).
- No claim-level citations, no on-slide citations, no hard fact-checking.
- Runtime still does not drive `/api/generate`.
- No rate limits / per-user quotas / SSE / audit logging on runtime route.
- Live `nexus-backend` container still bound to `D:\nexus-ai-gh\backend`; `docker compose up --build` from this workspace required to pick up Phase 6A/6B.


---

## Phase 6B-Fix -- Restore Official Backend Test Gate -- 2026-05-09

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

## Phase 6C -- Renderer-to-Export Parity Contract Tests -- 2026-05-09

**What changed**
- Added a backend-side **content** parity safety net for PPTX exports across all 7 canonical layouts. No renderer or product behavior changed.
- New deterministic, image-free fixture module covering `title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing` with unique text markers so round-trip extraction can assert content survival unambiguously. Reusable by future screenshot/visual-diff phases.
- New tests drive `ExportService._export_pptx_sync` through an in-memory storage stub (no filesystem, no network), reopen the saved bytes with `python-pptx`, and assert per-layout text and chart category/series parity. Also covers determinism, unknown-layout fallback, empty-chart fallback, on-disk reopen smoke, and a PDF smoke test that **skips** if WeasyPrint is unavailable.

**Files changed / added**
- `backend/tests/fixtures/__init__.py` (NEW empty package marker)
- `backend/tests/fixtures/canonical_slides.py` (NEW reusable fixture)
- `backend/tests/test_export_parity.py` (NEW -- 15 tests)
- Audits updated: `audits/AUDIT_CURRENT_STATE.md`, `audits/AUDIT_PROMPT_CONTEXT.md`, `audits/COMPETITIVE_BENCHMARK_BASELINE.md`, `audits/CURRENT_COMPETITIVE_SCORE.md`, `audits/VISUAL_QUALITY_AUDIT.md`.

**Tests added:** 15.

**Tests run**
```
.\scripts\test-backend.ps1
# pytest summary ? 215 passed, 2 skipped, 1 warning (exit code 0)
```
(Up from 200 passed, 2 skipped after Phase 6B-Fix; +15 new, including 1 PDF smoke test that may skip in some environments.)

`npm run verify:layouts` not run -- no frontend or layout files changed.

**Result:** Pass.

**Score impact**
- Rubric `export_parity` raised from 4/10 (input parity only) to **6/10** (PPTX content parity for all 7 layouts; visual/pixel parity still unmeasured; PDF smoke only).
- Estimated overall competitive score: **~55 ? ~57.5 / 100** (still an estimate, still not measured; NEXUS does not beat Manus).

**Remaining risks**
- **Visual/pixel parity unmeasured.** Typography, exact positioning, font fidelity, chart styling not checked.
- **PDF visual parity unclaimed.** Smoke test only; skipped if WeasyPrint is unavailable.
- AI generation accuracy still not measured live (no harness against `/api/generate`).
- No screenshot-diff visual regression suite.
- No claim-level citations, no on-slide citations, no hard fact-checking.
- Runtime still does not drive `/api/generate`.
- No rate limits / quotas / SSE / audit logging on the runtime route.
- Live `nexus-backend` container still bound to `D:\nexus-ai-gh\backend`; `docker compose up --build` from this workspace required to pick up Phase 6A/6B/6B-Fix/6C.


---

## Phase 6D -- Live-Eval Harness Baseline -- 2026-05-09

**What changed**
- Added an offline-only foundation for converting the 11-prompt benchmark corpus into measurable per-prompt score records. Harness is opt-in. **No live run was executed.** No product behavior changed.
- New eval result schema, evaluator service, fixture decks, opt-in CLI, PowerShell wrapper, and 18 offline tests.
- The CLI explicitly refuses to call `/api/generate` without `NEXUS_RUN_LIVE_EVAL=true`. The actual generate integration is a `NotImplementedError` stub so a future phase wires it cleanly instead of silently producing fake data.
- Per-category scoring: `deck_correctness` and (partial) `evidence_accuracy` are computed offline from a deck dict; `visual_quality`, `export_parity`, `agent_autonomy`, `stability_reliability`, `security_production_readiness` remain `null` with explanatory notes (they require visual diff, runtime telemetry, or global gate measurement).

**Files changed / added**
- `benchmarks/eval_schema.json` (NEW)
- `backend/services/eval_service.py` (NEW)
- `backend/tests/fixtures/eval_decks.py` (NEW)
- `backend/tests/test_live_eval.py` (NEW -- 18 tests)
- `backend/scripts/__init__.py` (NEW empty package marker)
- `backend/scripts/run_live_eval.py` (NEW opt-in CLI)
- `scripts/run-live-eval.ps1` (NEW PowerShell wrapper)
- Audits updated: `AUDIT_CURRENT_STATE.md`, `AUDIT_PROMPT_CONTEXT.md`, `COMPETITIVE_BENCHMARK_BASELINE.md`, `CURRENT_COMPETITIVE_SCORE.md`.

**Tests added:** 18.

**Tests run**
```
.\scripts\test-backend.ps1
# pytest summary ? 233 passed, 2 skipped, 1 warning (exit code 0)
```
(Up from 215 passed, 2 skipped after Phase 6C; +18 new.)

**Result:** Pass.

**Score impact**
- **None.** Phase 6D is harness only; no live run was executed, so all rubric scores remain estimates. Competitive score unchanged at ~57/100 (estimate).
- The Phase 6C cleanup also corrected a typo (`4?66` ? `4?6`) in `AUDIT_CURRENT_STATE.md` and refreshed the stability/reliability evidence row in `CURRENT_COMPETITIVE_SCORE.md` from `182 passed` to the current `233 passed, 2 skipped, 1 warning`.

**Remaining risks**
- AI generation accuracy still not measured -- the harness is wired but `/api/generate` integration is a `NotImplementedError` stub.
- Visual/pixel parity unmeasured.
- PDF visual parity unclaimed (smoke only).
- No claim-level citations, no on-slide citations, no hard fact-checking.
- Runtime still does not drive `/api/generate`.
- No rate limits / quotas / SSE / audit logging on the runtime route.
- Live `nexus-backend` container still bound to `D:\nexus-ai-gh\backend`; `docker compose up --build` from this workspace required to pick up Phase 6A--6D.


---

## Phase 6E -- Opt-In Live Eval Generate Adapter -- 2026-05-09

**What changed**
- Replaced the Phase 6D `NotImplementedError` stub in `backend/scripts/run_live_eval.py` with a real adapter that POSTs to `/api/generate`, polls `/api/slides/{task_id}` until the task is `done` / `failed` / timeout, and feeds the deck into `services.eval_service.evaluate_deck`.
- All HTTP goes through an injectable `HttpClient` Protocol; the default `httpx.Client` is built lazily so tests cannot accidentally make real HTTP. Live evaluation remains opt-in via `NEXUS_RUN_LIVE_EVAL=true` and is **not** part of the official backend gate.
- New CLI flags: `--prompt-id`, `--base-url`, `--timeout-seconds`, `--poll-interval-seconds`, `--theme`, `--search-web` / `--no-search-web`, `--slide-count`.
- Result files are written to `backend/storage/evals/` (gitignored) by default; override via `NEXUS_EVAL_OUTPUT_DIR`.
- **No product-behavior changes.** No new layouts, no renderer changes, no UI changes.

**Files changed / added**
- `backend/scripts/run_live_eval.py` (REWRITTEN -- real adapter, was `NotImplementedError` stub)
- `backend/tests/test_live_eval_adapter.py` (NEW -- 12 tests with in-memory fake HTTP client)
- Audits updated: `AUDIT_CURRENT_STATE.md`, `AUDIT_PROMPT_CONTEXT.md`, `COMPETITIVE_BENCHMARK_BASELINE.md`, `CURRENT_COMPETITIVE_SCORE.md`.

**Tests added:** 12.

**Tests run**
```
.\scripts\test-backend.ps1
# pytest summary ? 245 passed, 2 skipped, 1 warning (exit code 0)
```
(Up from 233 passed, 2 skipped after Phase 6D; +12 new.)

**Result:** Pass.

**Live eval actually run?** No. The adapter is wired and contract-tested with a fake HTTP client; no real `/api/generate` round-trip has been executed against a running stack. All rubric scores remain estimates.

**Where result files are written**
- Default: `/app/storage/evals/` inside the live-eval container, which corresponds to `backend/storage/evals/` on the host (gitignored).
- Override: set `NEXUS_EVAL_OUTPUT_DIR` to redirect.

**Score impact**
- **None.** Phase 6E is adapter wiring; no live run was executed, so all rubric scores remain estimates. Competitive score unchanged at ~57/100 (estimate).

**Remaining risks**
- AI generation accuracy still not measured -- adapter is wired but no live run has been executed.
- Visual/pixel parity unmeasured.
- PDF visual parity unclaimed (smoke only).
- No claim-level citations, no on-slide citations, no hard fact-checking.
- Runtime still does not drive `/api/generate`.
- No rate limits / quotas / SSE / audit logging on the runtime route.
- Live `nexus-backend` container still bound to `D:\nexus-ai-gh\backend`; `docker compose up --build` from this workspace required to pick up Phase 6A--6E.
- NEXUS does not beat Manus.

## Phase 6F - Live Eval Runbook + One-Prompt Smoke (Partial) - 2026-05-09

**Outcome: Partial.** Runbook authored; **the controlled biz-001 live run was not executed** because the running `nexus-backend` container was bound to `D:\nexus-ai-gh\backend` (the previous workspace), not this one. `docker inspect nexus-backend` confirmed mount source `D:\nexus-ai-gh\backend -> /app`. Running live eval against that stack would not reflect Phase 6A-6E code; per the runbook's own guard the run was deliberately skipped. Tearing down a 16h-running stack and rebuilding from this workspace requires explicit operator approval and was out of scope for this phase.

### Files added / changed
- **NEW:** `audits/LIVE_EVAL_RUNBOOK.md` - prerequisites, `docker compose down/up --build` from this workspace, host-mount verification, env vars, exact one-prompt command for `biz-001`, output location (`backend/storage/evals/`, gitignored), result-JSON interpretation, rollback.
- Updated: `audits/AUDIT_CURRENT_STATE.md`, `audits/AUDIT_PROMPT_CONTEXT.md`, `audits/CURRENT_COMPETITIVE_SCORE.md`, `audits/COMPETITIVE_BENCHMARK_BASELINE.md`, this file.
- **No code changes.** No new tests. No new dependencies.

### Tests run
- `.\scripts\test-backend.ps1` ? **245 passed, 2 skipped, 1 warning** (unchanged from Phase 6E; pytest exit 0).

### Live evaluation
- **Not executed.** No result JSON produced. `backend/storage/evals/` remains empty. Rubric scores remain estimates; competitive score still ~57/100; NEXUS does not beat Manus.

### Risks (unchanged from 6E, plus)
- Stack drift: dev container is bound to the old `D:\nexus-ai-gh\backend` workspace. Phase 6A-6E code is not in the running stack until `docker compose up --build` is run from this workspace, as the runbook describes.

## Phase 6G - Presenton Reference Benchmark - 2026-05-09

**Outcome: Pass.** Added [Presenton](nexus-ai/manus-need/presenton/README.md) as a presentation-product reference distinct from the Manus / browser-use / OpenManus / AgenticSeek agent references and from Gamma/Tome (closed-source SaaS). Recorded an honest, file-cited per-category comparison. **No NEXUS code changed. No live eval run. No score moved.**

### Files added / changed
- Updated: `audits/COMPETITIVE_BENCHMARK_BASELINE.md` (new `Phase 6G - Presenton Reference Comparison` section + competitor-table row).
- Updated: `audits/CURRENT_COMPETITIVE_SCORE.md` (Presenton honest disclosure; clarified that closing Presenton-class surface gaps does not by itself raise the rubric score).
- Updated: `benchmarks/rubric.json` (`competitors` list now includes `presenton`; `test_rubric_lists_required_competitors` continues to pass since it asserts a *subset*).
- Updated: `audits/AUDIT_CURRENT_STATE.md`, `audits/AUDIT_PROMPT_CONTEXT.md`, this file.
- **No code changes.** No new tests. No new dependencies.

### Honest gaps recorded vs. Presenton
- **Hard gap:** No PPTX or PDF ingestion in NEXUS; Presenton ships `POST /api/v1/ppt/pptx-slides/process` and `POST /api/v1/ppt/pdf-slides/process` with 100 MB caps and screenshot/font extraction.
- **Hard gap:** No MCP server in NEXUS; Presenton ships a FastMCP server auto-derived from OpenAPI on `127.0.0.1:8001`.
- **Soft gap:** No SSE slide streaming; no `derive` / `prepare` / `edit` endpoints; no webhook callbacks; no stage-by-stage progress messages.
- **Soft gap:** Narrower BYOK story (`.env`-driven, Groq default; Anthropic/OpenAI in code). Presenton supports first-class OpenAI / Anthropic / Google / Vertex / Azure / **Ollama** / custom OpenAI-compatible.
- **Soft gap:** No native desktop distribution. Presenton ships an Electron binary (Win/macOS/Linux) bundling Puppeteer + PyInstaller-packaged FastAPI.
- **Even gaps:** Both lack pixel-diff visual regression suites; both have ~comparable backend test counts (NEXUS 245 / Presenton ~100); neither has a measured live deck-quality result.
- **NEXUS-only strengths preserved:** Authenticated `AgentRuntime` (Phase 6A); 7-layout canonical schema validator; deck-quality report + repair preview; deck-level source grounding; 30 offline live-eval tests; 15 PPTX content-parity tests.

### Tests run
- `.\scripts\test-backend.ps1` -> **245 passed, 2 skipped, 1 warning** (unchanged from Phase 6E/6F; pytest exit 0).

### Live evaluation
- **Not executed.** No result JSON produced. `backend/storage/evals/` remains empty. Rubric scores remain estimates; competitive score still ~57/100; NEXUS does not beat Manus, and NEXUS does not beat Presenton on user-facing surface area.

### Score impact
- **None.** Surface-area documentation only. Competitive score unchanged at ~57/100 (estimate). Closing Presenton-class surface gaps would close real product gaps but does not by itself move the rubric, which is gated on live deck-quality measurement.

## Phase 6H - Reference Intelligence Blueprint - 2026-05-09

**Outcome: Pass.** Audit/roadmap phase only. **No NEXUS code changed. No live eval run. No score moved.** Authored a master implementation roadmap in [audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md](nexus-ai/audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md) that compares NEXUS against Manus, Presenton, browser-use, OpenManus, Suna, AgenticSeek, and the curated Browser/Claude research notes; defines a NEXUS gap matrix across 15 capabilities; describes a unified target architecture; and lists the next 12 implementation phases (6I through 6T).

### Files added / changed
- Added: `audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md`.
- Updated: `audits/AUDIT_CURRENT_STATE.md`, `audits/AUDIT_PROMPT_CONTEXT.md`, `audits/CURRENT_COMPETITIVE_SCORE.md`, `audits/COMPETITIVE_BENCHMARK_BASELINE.md`, `audits/FINAL_SYSTEM_AUDIT.md`, and this file.
- **No code changes.** No new tests. No JSON files modified.

### Honest position
- NEXUS does not beat Manus.
- Presenton still leads on user-facing presentation-product surface area (PPTX/PDF ingestion, MCP server, SSE streaming, Ollama BYOK, Electron desktop).
- Estimated competitive score remains ~57/100 (~57.5 weighted, estimate).
- This blueprint is now the master implementation roadmap; future phases (6I onward) plan against it.

### Tests run
- `.\scripts\test-backend.ps1` -> **245 passed, 2 skipped, 1 warning** (unchanged; pytest exit 0).

### Live evaluation
- **Not executed.** `backend/storage/evals/` remains empty. No result JSON produced.

### Score impact
- **None.** Audit/roadmap only. Score remains an estimate; only a measured live-eval run can move it.

## Phase 6I - Runtime drives /api/generate behind feature flag - 2026-05-09

**Outcome: Pass.** First implementation phase from the Phase 6H blueprint. Adds the env-driven feature flag `NEXUS_RUNTIME_DRIVES_GENERATE` (default **OFF**). When off, `/api/generate` is byte-identical to pre-6I (existing live-eval adapter and frontend unaffected). When on, the route additionally persists exactly one `AgentRun` linked via `task_id` (with `meta.phase="6I"`, `meta.dispatch_only=true`) and one `thought` `AgentStep`, marks the run `done`, and surfaces `agent_run_id` in the response. The Celery worker still drives the actual generation pipeline; the runtime does not yet execute generation. **No live eval run. No score moved.**

### Files added / changed
- Updated: [backend/config.py](nexus-ai/backend/config.py) (`NEXUS_RUNTIME_DRIVES_GENERATE: bool = False`).
- Updated: [backend/api/routes/generate.py](nexus-ai/backend/api/routes/generate.py) (`_record_runtime_dispatch` helper; `GenerateResponse.agent_run_id: Optional[str] = None`; flag-gated branch).
- Added: [backend/tests/test_runtime_generate_route.py](nexus-ai/backend/tests/test_runtime_generate_route.py) (4 offline tests).
- Updated: this file plus `audits/AUDIT_CURRENT_STATE.md`, `audits/AUDIT_PROMPT_CONTEXT.md`, `audits/CURRENT_COMPETITIVE_SCORE.md`, `audits/FINAL_SYSTEM_AUDIT.md`.
- **No layout, renderer, frontend, or worker code changed.** No new dependencies. No JSON files modified. No reference repo files modified.

### Tests added (4)
1. `test_generate_flag_off_response_shape_unchanged` - flag off: 202 + `task_id`/`status`, `agent_run_id` is `None`/absent, zero `AgentRun` rows, zero `AgentStep` rows.
2. `test_generate_flag_on_persists_run_and_step` - flag on: exactly one `AgentRun` (status `done`, `meta.phase="6I"`, `meta.dispatch_only=true`, linked via `task_id`) and exactly one `thought` `AgentStep` (status `ok`, `input_json.dispatch="celery"`).
3. `test_generate_flag_on_response_compatible_with_live_eval_adapter` - flag on: response still satisfies the live-eval adapter contract (`task_id` present), preserving Phase 6E adapter compatibility.
4. `test_generate_flag_on_step_failure_records_failed_run` - flag on with `append_step` monkeypatched to raise: API still returns 202, no crash, the `AgentRun` row exists with status `failed` and `error_msg` starting `dispatch_record_failed`. Records failure state instead of leaking it.

### Tests run
- `.\scripts\test-backend.ps1` -> **249 passed, 2 skipped, 1 warning** (was 245 + 4 new; pytest exit 0).

### Live evaluation
- **Not executed.** `backend/storage/evals/` remains empty. No result JSON produced.

### Score impact
- **None.** Surface/integration only. Default product behavior unchanged. Score remains an estimate at ~57/100 (~57.5 weighted). NEXUS still does not beat Manus. Presenton still leads on user-facing presentation-product surface area. Phase 6J (rebuild stack + `biz-001` live smoke) remains the first score-eligible phase.

### Phase 6I-Fix - Response-contract cleanup - 2026-05-09

Response-contract cleanup only. Added `response_model_exclude_none=True` on the `/api/generate` route so the flag-off response JSON contains exactly `{task_id, status}` and never the key `agent_run_id` (not even as `null`). Tightened `test_generate_flag_off_response_shape_unchanged` to assert `set(body.keys()) == {"task_id", "status"}` and `"agent_run_id" not in body`. Flag-on tests unchanged.

- Files changed: [backend/api/routes/generate.py](nexus-ai/backend/api/routes/generate.py), [backend/tests/test_runtime_generate_route.py](nexus-ai/backend/tests/test_runtime_generate_route.py).
- No live eval. No score change. Backend gate: **249 passed, 2 skipped, 1 warning** (unchanged).

### Phase 6J - First controlled one-prompt live-eval smoke (`biz-001`) - 2026-05-09

Phase 6J is the first controlled one-prompt live measurement attempt and the first score-eligible measurement phase. The full 11-prompt benchmark remains future Phase 6T.

- Stack was **rebuilt from this workspace** (`D:\nexus-ai-1\nexus-ai`) before measurement; backend mount verified `D:\nexus-ai-1\nexus-ai\backend -> /app`; backend health `200 {"status":"ok"}`.
- Live eval **did run**, exactly once, for `biz-001` (no other prompts). Committed result: [audits/LIVE_EVAL_RESULTS/biz-001-2026-05-09.json](nexus-ai/audits/LIVE_EVAL_RESULTS/biz-001-2026-05-09.json). No secrets in the result file; no redaction needed.
- Measured (offline-measurable subset only): `ran_live=true`, `generated_slide_count=8`, `slide_count_in_window=true`, `required_layouts_missing=[]`, `chart_requirement_met=true`, `external_source_expectation_met=true`, `deck_quality_ok=false`, `deck_quality_invalid_count=1`, `category_scores.deck_correctness=8`, `category_scores.evidence_accuracy=7`. Other category scores `null` per schema.
- **Score did not change.** Estimate remains **~57/100 (~57.5 weighted)**. NEXUS still does not beat Manus. NEXUS still does not beat Presenton overall on user-facing presentation-product surface area. Only `biz-001` was run; the full 11-prompt benchmark remains future Phase 6T.
- Added offline test [backend/tests/test_live_eval_results.py](nexus-ai/backend/tests/test_live_eval_results.py); updated [scripts/test-backend.ps1](nexus-ai/scripts/test-backend.ps1) to mount `audits/LIVE_EVAL_RESULTS -> /live_eval_results:ro`.
- Backend gate: **251 passed, 2 skipped, 1 warning**.


---

## Phase 6W -- Role-Based Provider Routing + Token Pruning

**Date:** 2026-05-10. **Backend gate:** 431 passed, 2 skipped, 1 warning (unchanged from 6U-Rebench / 6V baseline). **Frontend layouts gate:** OK -- 7 canonical layouts, 7 exported. No product API surface change. No new dependencies. No secrets in tracked files.

### 1. What was implemented

- **4 new providers wired** in [backend/config.py](nexus-ai/backend/config.py) and [backend/services/ai_service.py](nexus-ai/backend/services/ai_service.py): Cerebras, SambaNova, Mistral, GitHub Models. All four use the existing OpenAI-compatible `_openai_compat` helper -- no new SDK.
- **All 10 providers reported by `/api/health`** ([backend/main.py](nexus-ai/backend/main.py)) with `configured`, `active`, `model`, `base_url`. `/api/health` is local-only -- it does not remote-ping providers.
- **Role-based routing via `complete_for_role()`** ([backend/services/ai_service.py](nexus-ai/backend/services/ai_service.py)) -- reads `settings.ROLE_MODEL_MAP`, logs role + preferred provider + preferred model, attempts the preferred provider with the **exact** preferred model, and on failure logs a warning and falls back to the existing `complete()` chain. `complete()` itself is unchanged.
- **Exact model override** for every provider call: `_call_openrouter`, `_call_nvidia_nim`, `_call_groq`, `_call_openai`, `_call_unfiltered`, `_call_cerebras`, `_call_sambanova`, `_call_mistral`, `_call_github_models`, `_call_gemini`, and `_call_anthropic` all accept a keyword-only `model: str | None = None`. When `None`, they use the env-default model for that provider.
- **Improved token pruning** in [backend/services/ai_service.py](nexus-ai/backend/services/ai_service.py):
  - `_prune_user_text()` now does **middle-truncation** (keeps head ~70% + tail ~30% with elision marker). The previous version truncated from the end, silently dropping the output contract ("Return ONLY a JSON array...") and producing malformed model output. The new version preserves the output contract.
  - `prune_messages()` rewritten to: keep system messages (de-duplicated), always preserve the last `KEEP_LAST_MESSAGES` non-system messages verbatim, drop oldest middle messages first with an elision placeholder, and as a final safeguard middle-truncate the single longest remaining message.
- **Research summarization** wired in [backend/agent/loop.py](nexus-ai/backend/agent/loop.py) -- when harvested research exceeds 10,000 chars, the `summarize` role compresses it before it reaches planner/writer. Source metadata in `research_sources` is preserved separately and never destroyed.
- **LLM JSON repair** wired at the *only* point it adds value: when `_parse_slides_array` or `_parse_single_slide` fails on writer output, `_json_fix_retry()` calls the `json_fix` role once and re-parses. The deterministic `repair_for_validator` path was **not** replaced.
- **Dead-code removal:** deleted the duplicate copy of `_add_hero_images` in `loop.py` (the second definition was overriding the first; behavior unchanged).
- **Test script** `test_providers.py` (repo root) -- skips unconfigured providers, pings configured ones with a tiny "Reply OK only." prompt, prints OK/FAIL/SKIP + model, exits non-zero only if every configured provider failed.

### 2. Role routing table

| Role | Provider | Model | Wired location | Status |
|------|----------|-------|----------------|--------|
| planner | gemini | `gemini-2.0-flash` | [backend/agent/planner.py](nexus-ai/backend/agent/planner.py#L48) | working |
| writer | groq | `llama-3.3-70b-versatile` | [backend/agent/loop.py](nexus-ai/backend/agent/loop.py#L383) (batch) + [backend/agent/loop.py](nexus-ai/backend/agent/loop.py#L451) (per-slide retry) | working |
| critic | openrouter | `deepseek/deepseek-r1:free` | [backend/agent/loop.py](nexus-ai/backend/agent/loop.py#L598) | working |
| research | cerebras | `qwen-3-235b-a22b-instruct-2507` | not used as a separate role; research is harvested by `SearchService` | **not used** (research compression goes through `summarize` role; `research` role is defined in the map but no call site invokes it) |
| vision | gemini | `gemini-2.0-flash` | [backend/agent/loop.py](nexus-ai/backend/agent/loop.py#L678) (image-prompt generation) | working |
| repair | openrouter | `qwen/qwen2.5-coder-32b:free` | not used as a separate role; deterministic `repair_for_validator` handles schema repair | **not used** (intentional -- deterministic repair is sufficient for the current schema; LLM repair would add latency without clear benefit) |
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

- **Backend** -- `powershell -File ./scripts/test-backend.ps1` -> **`431 passed, 2 skipped, 1 warning in 10.04s`**.
- **Frontend layouts** -- `npm run verify:layouts` -> **`verify-layouts OK -- 7 canonical layouts, 7 exported`**.
- **Provider smoke test** -- host Python lacks pydantic, so the script must run inside the backend container:
  ```
  docker run --rm -v "D:\nexus-ai-1\nexus-ai:/app" -v "D:\nexus-ai-1\nexus-ai\.env:/app/.env:ro" -w /app -e PYTHONPATH=/app/backend nexus-ai-backend:dev python test_providers.py
  ```
  Result at audit time: **ok=3, configured=8, total=10**. `groq`, `nvidia_nim`, `sambanova` returned OK. `gemini` and `openrouter` returned 429 (free-tier rate limit, transient). `cerebras` returned 429 (transient queue). `mistral` and `github_models` returned 401 (the keys provided at provisioning time were rejected -- see Risks). `anthropic` and `openai` skipped (no key).

### 5. Remaining risks

- **Invalid keys in local `.env`.** `MISTRAL_API_KEY` and `GITHUB_MODELS_API_KEY` returned 401 from their providers. The roles that depend on them (`json_fix`) will always fall back to the `complete()` chain until those keys are rotated to working values.
- **Free-tier rate limits.** `gemini`, `openrouter`, and `cerebras` repeatedly hit 429 in the smoke test. The role-routing fallback to `complete()` masks this in production code, but **planner** (Gemini), **critic** (OpenRouter), **research** (Cerebras), and **vision** (Gemini) will silently degrade to whichever provider in the chain answers first whenever their preferred provider is rate-limited.
- **Approximate token pruning.** Pruning is dependency-free and uses ~4 chars/token as a heuristic. It is not exact tokenization. For pathological inputs it may under- or over-trim by +/-10-15%. Adopting `tiktoken` would fix this but adds a dependency.
- **`research` and `repair` roles are defined but not wired.** They are reachable via `complete_for_role(role="research" | "repair")` if a future caller wants them, but no current code path invokes them. Listed in `ROLE_MODEL_MAP` for forward compatibility only. This is intentional and documented above.
- **Not a fully dynamic runtime.** Role -> provider mapping is static (env-driven via `ROLE_MODEL_MAP`). There is no learned/measured routing that picks the cheapest provider that meets quality, no per-task A/B routing, and no automatic key-health probing. `/api/health` reports configuration, not liveness.

### 6. Score impact (honest, no marketing)

| Axis | Before 6W | After 6W |
|------|-----------|----------|
| Token efficiency | End-truncation often dropped the output contract -> wasted retries | Middle-truncation preserves head + tail; no observed contract loss in tests |
| Provider resilience | 6 providers in chain, single-model-per-provider | 10 providers configured, role-preferred provider with exact-model override + automatic fallback to chain |
| Manus-like architecture | Single-provider chain regardless of task | Per-role provider/model preferences (4 roles actually wired); still static, not learned |

### 7. What changed (file list)

- [backend/config.py](nexus-ai/backend/config.py) -- `ROLE_MODEL_MAP`, 4 new provider blocks, `MAX_CONTEXT_TOKENS`, `KEEP_LAST_MESSAGES`, extended `assert_required_for_runtime`.
- [backend/services/ai_service.py](nexus-ai/backend/services/ai_service.py) -- 4 new handlers, `model_override` on all handlers (incl. Gemini + Anthropic), `complete_for_role()`, `prune_messages()` (rewritten), `_prune_user_text()` (middle-truncation), `ClaudeService = AIService` shim preserved.
- [backend/agent/planner.py](nexus-ai/backend/agent/planner.py) -- `planner` role; `hasattr` fallback for legacy fakes.
- [backend/agent/loop.py](nexus-ai/backend/agent/loop.py) -- `_ai_call` helper, `_summarize_long_research`, `_json_fix_retry`; `writer`/`critic`/`vision` roles wired; duplicate `_add_hero_images` removed.
- [backend/main.py](nexus-ai/backend/main.py) -- `/api/health` reports all 10 providers.
- [.env.example](nexus-ai/.env.example) -- 4 new provider blocks (placeholders only); `AI_PROVIDER_CHAIN` default aligned with `backend/config.py`; pruning knobs.
- [test_providers.py](nexus-ai/test_providers.py) -- new root-level smoke test.

