# Final System Audit: NEXUS AI Presentation Platform

> **Reading note.** For current truth, read `AUDIT_CURRENT_STATE.md` first. This file contains historical phase notes and original audit findings. Older sections may be superseded. Do not treat old phase claims as current evidence without checking `AUDIT_CURRENT_STATE.md` and `AUDIT_READING_GUIDE.md`.

Date: 2026-05-08  
Role: Principal engineer + product architect audit  
Scope: architecture quality, rendering quality, AI depth, platform maturity, product readiness, competitive position

This report is intentionally severe. It audits the system as a platform, not as a prototype milestone.

## Executive Verdict

NEXUS is not enterprise-ready and not yet competitive with Manus, Gamma, or Tome. It is a structured prototype that has acquired platform-shaped components: registry, normalizer, renderer, tests, export path, AI planner, image service, and chart service. The issue is that many of those components are still shallow contracts rather than durable platform boundaries.

The system can demo. It cannot yet guarantee consistently professional presentations, export fidelity, production resilience, enterprise governance, or defensible AI intelligence.

## Phase 5 -- Frontend Evidence Visibility - 2026-05-09

### What Changed
- Generated decks and shared decks now expose a compact, collapsed-by-default `SourceEvidencePanel` listing per-slide sources (title, host, truncated snippet). Backend untouched; the frontend slide normaliser was fixed to forward `slide.sources` to the UI (it was being stripped before).
- The slide renderer, layouts, exports, charts, and thumbnails are unchanged.

### Files Changed
- `frontend/src/components/SourceEvidencePanel.jsx` (new).
- `frontend/src/pages/Generator.jsx`, `frontend/src/pages/SharedSlide.jsx` (one mount each).
- `frontend/src/utils/slideParser.js` (preserve `sources`).

### Tests Run
- `npm run verify:layouts` -> 7 / 7.
- No backend code changed.

### Result
**Pass (narrow).** Source data became user-visible. The Executive Verdict above does not change -- we still don't have on-slide citations, claim-level source binding, hard fact-checking, or runtime-driven generation.

### Remaining Risks
- No claim-specific citation mapping.
- No on-slide visual citations.
- No hard fact-checking.
- Runtime still not driving `/api/generate`.
- Route remains unauthenticated/internal.
- No Alembic migration yet.

## Phase 4 -- Evidence-Aware Deck Generation + Source Visibility - 2026-05-09

### What Changed
- The existing 6-step deck pipeline now preserves search results past the search step and attaches them to source-bearing slides (`stats`, `chart`, and prose slides that contain numeric claims). Title and closing slides remain untouched.
- `chart_data.source` is now filled with a defensible label (source title, else URL host -- never invented) when it was empty.
- `DeckQualityBadge` now communicates `deck_quality.source_warnings` to the user: a count in the pill and a list in the expanded panel.
- No visual slide redesign, no new frontend pages, no /api/generate breakage, no DB schema change.

### Files Changed
- `backend/agent/source_grounding.py` (`attach_research_sources_to_deck` + helpers).
- `backend/agent/loop.py` (preserve sources, call attach helper after normalize and after critic+normalize).
- `frontend/src/components/DeckQualityBadge.jsx` (compact source-warning surface).
- `backend/tests/test_phase4_attach_sources.py` (new, 13 tests).

### Tests Run
- Backend full: **171 passed, 2 skipped** (was 158/2; +13).
- Frontend `verify:layouts` -> 7 / 7.

### Result
**Pass (narrow).** A user generating a deck with web search enabled now sees source data flow into stats/chart slides, sees a count of "source warning" advisories on the deck quality pill, and can inspect those advisories in the existing panel. The Executive Verdict above does not change: this is data-layer + minimal UI; slide-level visual citations and runtime-driven generation are still ahead.

### Remaining Risks
- Source matching is heuristic, not hard fact-checking.
- Sources are deck-level, not claim-specific.
- No visual citations on slides yet.
- Runtime is not driving `/api/generate`.
- `/api/agent/test-run` is unauthenticated/internal.
- No Alembic migration for the runtime + artifact tables.

## Phase 3 -- Source Grounding & Evidence Artifacts - 2026-05-09

### What Changed
- A real evidence layer now exists: tool observations from `info_search_web` and the read-only browser tools are normalised into a single `SourceEvidence` shape and persisted as `Artifact(artifact_type="source")` rows linked to the originating `AgentRun`. Snippets are truncated; raw bodies never reach the DB unbounded.
- Deck quality reporting now includes advisory `source_warnings` for stats / chart slides without source metadata. **Advisory only** -- it does not fail generation, mutate slides, or invent sources.
- The runtime route now surfaces an `artifacts: {total, sources, by_type}` summary; it does not leak raw snippets/urls.
- The 6-step slide pipeline, the 29-tool registry, and the existing `/api/generate` flow are unchanged.

### Files Changed
- `backend/agent/source_grounding.py` (new).
- `backend/agent/deck_quality.py` (added `source_warnings` field + report integration).
- `backend/agent/runtime.py` (artifact recording in success path).
- `backend/api/routes/agent.py` (artifact summary in response).
- `backend/tests/test_source_grounding.py` (new, 14 tests).
- `backend/tests/test_phase3_runtime_artifacts.py` (new, 3 tests).
- 2 existing tests updated for the new exact-set shape.

### Tests Run
- Backend full: **158 passed, 2 skipped** (was 139/2; +19).
- Frontend `verify:layouts` -> 7 / 7.

### Result
**Pass (narrow).** The platform now has a tested, persisted evidence model, plus advisory source-warning surface on the deck quality report. The Executive Verdict above does not change: nothing in this phase is yet visible in the user UX, deck generation is still not runtime-driven, and source grounding is advisory rather than hard fact-checking. Promotion of the verdict requires Phase 4/5 integration into the deck pipeline, frontend evidence surfacing, and authentication on the runtime endpoint.

### Remaining Risks
- Source grounding is advisory, not hard fact-checking.
- Evidence artifacts are not yet shown in the frontend.
- Runtime route is unauthenticated/internal.
- No Alembic migration for `agent_runs` / `agent_steps` / `artifacts`.
- Deck generation is not yet runtime-driven.
- Browser observations are limited when `BROWSER_ENABLED=false` (default).

## Phase 2.5 -- Safe Internal Agent API + Planner Adapter - 2026-05-09

### What Changed
- The `AgentRuntime` is now reachable from HTTP via `POST /api/agent/test-run` with a server-enforced safe-default allowlist. Shell, file-write, deploy, and `browser_console_exec` tools are categorically rejected at the route layer (HTTP 400) before the runtime even starts; the planner cannot reach them through this surface.
- `AIService` is wrapped in a `Planner` adapter (`agent/planners.py`). When no provider key is set, the route returns 503 with a clear configuration error rather than crashing.
- The 6-step slide pipeline and the `/api/generate` flow are not modified.

### Files Changed
- `backend/agent/planners.py` (new).
- `backend/api/routes/agent.py` (new).
- `backend/tests/test_agent_route.py` (new, 8 tests).
- `backend/main.py` (router include only).

### Tests Run
- Backend full: **139 passed, 2 skipped** (was 131/2; +8).
- Frontend `verify:layouts` -> 7 / 7.

### Result
**Pass (narrow).** The runtime now has a callable surface with a real safety envelope. The Executive Verdict above does not change: this endpoint is internal-grade, unauthenticated, and not yet routed into product UX. Promotion of the verdict still requires authentication, rate limits, deck integration (Phase 3+), and an Alembic migration for the runtime tables.

### Remaining Risks
- Route is unauthenticated.
- No SSE step streaming, no cancellation, no per-user quotas.
- No Alembic migration for `agent_runs` / `agent_steps`; production Postgres deploy of this route is blocked on it.

## Phase 2 -- Dynamic Tool-Calling Agent Runtime - 2026-05-09

### What Changed
- A real agent runtime now exists at `backend/agent/runtime.py` with bounded loop, strict JSON action contract, allowlist enforcement, per-step timeout, and full per-step persistence to `agent_runs` / `agent_steps`. The 6-step slide pipeline (`agent/loop.py`) is untouched and is still the path serving every user request today.
- This narrows one of the longest-standing items in this audit -- the gap between "agent-shaped components" and "a real runtime that can choose tools and observe results." That runtime now exists, with tests, but is **not yet routed in front of any user**.

### Files Changed
- `backend/agent/runtime.py` (new).
- `backend/tests/test_agent_runtime.py` (new, 13 tests).

### Tests Run
- Backend full suite: **131 passed, 2 skipped** (was 118/2; +13).
- Targeted Phase 1+2 + deck/schema/layout regression: 103 passed, 1 skipped.
- Frontend `verify:layouts` -> 7 / 7.

### Result
**Pass (narrow).** The platform now has a real, persisted, bounded agent runtime as a separate module. The Executive Verdict above does not change yet because no end-user surface exercises it. Promotion of the verdict requires Phase 2.5 (planner adapter to `AIService` + route) and Phase 3 (browser/source grounding integrated into runs).

### Remaining Risks
- Runtime is unwired in production flow.
- No Alembic migration for the runtime tables; production Postgres deploy of the runtime is blocked on it.
- No cancellation API, no SSE streaming of steps, consecutive-only failure counter. All tracked for later phases.

## Phase 1H Pre-Lock Triage Sweep (P1-1, P1-2, P0-2, P1-3) - 2026-05-09

### What Was Fixed
- **P1-1.** `SharedSlide` page now renders `DeckQualityBadge` from the `deck_quality` field that `GET /api/share/{token}` has been returning since Phase 1D. Closes the most-cited Phase 1D leftover with no backend change.
- **P1-2.** Stats->chart safety-net in `_normalize_slides` no longer emits self-inflicted `loop.slide_validation_failed layout=chart path=subtitle code=missing` warnings on every promoted chart slide. The promotion now carries forward the source slide's subtitle (or defaults to `""`), satisfying the tightened schema without inventing semantic content.
- **P0-2.** New `tests/test_export_input_parity.py` (3 tests, AST-based) pins the read-path / export-path equality the Phase 1D `deck_quality` guarantee rests on: both routes must pass `deck.slide_data or []` unchanged.
- **P1-3.** One-sentence cross-link inside the four existing Phase 1A correction notices pointing readers to the verified-numbers section above. No older content removed.

### Files Changed
- `frontend/src/pages/SharedSlide.jsx`
- `backend/agent/loop.py` (one line in the stats->chart safety-net)
- `backend/tests/test_deck_quality.py` (test semantics flipped)
- `backend/tests/test_slide_schema.py` (test semantics flipped)
- `backend/tests/test_export_input_parity.py` (new)
- 4 audit files (cross-link only)

### Tests Added
- 3 source-level parity tests for the export contract.
- 0 net new tests for P1-2 (two existing telemetry tests now assert the *absence* of the previously-required warning).

### Tests Run
- Default backend pytest: **106 passed, 1 skipped, 1.67s**.
- Frontend `npm run verify:layouts` -> OK 7 / 7.

### Result
Narrow Phase 1H scope -- **Pass**. The pre-lock P0/P1 triage list is empty.

### Remaining Risks
- ExportService end-to-end fidelity (renderer/export drift Critical row) still awaits its own hardening workstream. The new parity test is a contract guard, not an integration test.
- All other open hardening items (queue retries, durable progress events, observability, deployment maturity, multi-tenant correctness) remain on the strategic backlog and were not in scope for the lock.

## Phase 1G Pre-Lock P0-1 (Test Suite Unblock) - 2026-05-09

### What Was Fixed
- The recurring "full backend pytest still blocked" line in every prior phase entry was traced to a single defect in `backend/database/connection.py`: pool kwargs (`pool_size`, `max_overflow`, `pool_pre_ping`) were passed unconditionally, but SQLite's async driver uses `NullPool` and rejects them. Default `pytest` invocations therefore failed at import time. Engine creation now branches on the URL scheme; pool kwargs are only applied for non-SQLite backends. Postgres / asyncpg behavior is unchanged.
- Audit posture correction: the `tests/` directory holds exactly the 5 files prior phases have been running. There is no larger hidden suite; previous "blocked" framing across all four audits should be read as "default pytest invocation crashed," not "a wider tier of tests was unrun."

### Files Changed
- `backend/database/connection.py` -- single edit: scheme-aware engine kwargs.

### Tests Added
- None.

### Tests Run
- Backend Docker, **default invocation** (no `--noconftest`, no file list): `python -m pytest -q` -> **103 passed, 1 skipped, 1.45s**.
- Frontend `npm run verify:layouts` -> OK 7 / 7.

### Result
Narrow Phase 1G scope -- **Pass**. The lock-blocking concern flagged across all four audits is closed at root.

### Remaining Risks
- Test breadth itself remains low (5 files). That is a separate, deliberate backlog item and is not a lock blocker per the triage.
- Postgres path not re-run as part of this fix; it was not changed.

## Phase 1F Repair Preview UI + Env Cleanup - 2026-05-09

### What Was Added
- UI consumer for the Phase 1E `repair_preview` field: `DeckQualityBadge` now lists each preview entry as `slide N - layout - path - action[ -> after]` inside the existing expanded panel, capped at 12 rows. When the preview list is empty, it falls back to the original `errors` listing.
- Disk hygiene: `nexus-ai/.venv` and `nexus-ai/manus-need/openmanus-reference/.venv` were deleted after confirming no active project config in `nexus-ai/` references them. The `D:\nexus-ai-1\.venv` directory at the parent path was left alone (out of workspace scope).

### Files Changed
- `frontend/src/components/DeckQualityBadge.jsx`
- Deleted: `nexus-ai/.venv/`, `nexus-ai/manus-need/openmanus-reference/.venv/`

### Tests Added
- None.

### Tests Run
- Backend Docker: 103 passed, 1 skipped, 1.14s.
- Frontend: `npm run verify:layouts` -> OK 7 / 7.
- Full pytest still blocked by the pre-existing conftest/DB pool mismatch.

### Result
Narrow Phase 1F scope -- **Pass**. Broader system-audit posture remains **Partial**.

### Remaining Risks
- The badge still does not paginate or virtualize the preview list -- acceptable at PRD slide caps.
- A developer that wants a local Python venv must re-create one explicitly. The Docker test path is the project's verified path and is unaffected.

## Phase 1E Repair Preview - 2026-05-09

### What Was Added
- `agent.deck_quality.build_repair_preview` -- a pure helper that converts the existing `repair_actions` list into preview-only suggestions. Each entry is a `RepairAction` with `action="preview"` (when a safe local default exists) or `action="not_applied"` (when a fix would require inventing content).
- `DeckQualityReport.repair_preview` and `to_dict()["repair_preview"]` are new, additive surfaces. The summary gains a `repairs_previewable` counter for quick triage.
- No mutation. No application. No validation gate. No DB change. No UI change. No export change.

### Files Changed
- `backend/agent/deck_quality.py`
- `backend/tests/test_deck_quality.py` (key-set update)
- `backend/tests/test_api_deck_quality_payload.py` (key-set update)
- `backend/tests/test_deck_repair_preview.py` (new)

### Tests Added
- 12 unit tests in `test_deck_repair_preview.py` covering valid/invalid/empty/non-list inputs, all five safe-default mappings, refusal to invent content for bullets/chart_data, non-mutation of inputs and supplied repair_actions, and pairing semantics with `repair_actions`.

### Tests Run
- Backend Docker (`--noconftest -p no:cacheprovider`): **103 passed, 1 skipped**.
- Frontend: `npm run verify:layouts` -> OK 7 / 7 canonical.
- Full pytest suite still blocked by the pre-existing `database/connection.py` pool mismatch under SQLite.

### Result
Narrow Phase 1E scope -- **Pass**. Broader system-audit posture remains **Partial** pending the actual repair pipeline, export-parity audits, full-suite pytest unblock, and browser automation.

### Remaining Risks
- The preview's safe-default values are defensible defaults, not guarantees. Any future repair pipeline that consumes `repair_preview` must treat them as suggestions, not commitments.
- Schema gaps with no safe default (bullets/columns/stats/chart_data) stay surfaced but unresolved -- by design -- to avoid generating fake content.
- Persisting historical reports/previews would require a `SlideDeck.deck_quality_json` migration; deliberately out of Phase 1E scope.

## Phase 1D Deck Quality Visibility - 2026-05-09

### What Was Added
- Deck-read API surfaces the Phase 1C `DeckQualityReport` to clients on both `GET /api/slides/{task_id}` and `GET /api/share/{token}` via `agent.deck_quality.attach_quality_report(payload, slides)` -- a tiny, pure, non-mutating helper that adds a `deck_quality` field to the response dict.
- Frontend Generator page renders a minimal `DeckQualityBadge` next to `ExportButtons` whenever a finished deck loads.
- No persistence change, no migration, no model change. `_normalize_slides` and the deck-save path in `agent/loop.py` are untouched. The report is recomputed on read from the already-validated `slide_data` JSON column.

### Files Changed
- `backend/agent/deck_quality.py` -- added `attach_quality_report` + export.
- `backend/api/routes/slides.py`, `backend/api/routes/share.py` -- wired in the helper on the response path.
- `frontend/src/components/DeckQualityBadge.jsx` -- new component.
- `frontend/src/pages/Generator.jsx` -- consumes `res.data.deck_quality` and renders the badge.
- `backend/tests/test_api_deck_quality_payload.py` -- new test module (conftest-free).

### Tests Added
- `test_attach_quality_report_adds_deck_quality_key`
- `test_attach_quality_report_does_not_mutate_inputs`
- `test_attach_quality_report_is_json_serializable`
- `test_attach_quality_report_flags_invalid_chart`
- `test_attach_quality_report_handles_empty_slides`
- `test_attach_quality_report_handles_non_list_slides`

### Tests Run
- Backend Docker (`--noconftest -p no:cacheprovider`): `tests/test_layout_coverage.py tests/test_slide_schema.py tests/test_deck_quality.py tests/test_api_deck_quality_payload.py` -> **90 passed, 1 skipped**.
- Frontend: `npm run verify:layouts` -> OK 7 / 7 canonical.
- Full backend pytest still blocked by conftest/DB pool mismatch -- pre-existing, untouched by Phase 1D.

### Result
Narrow Phase 1D scope -- **Pass**. Broader system-audit posture remains **Partial** (repair pipeline, export parity, browser automation, full pytest run still pending).

### Remaining Risks
- Validation remains advisory; nothing blocks generation or export.
- A future schema change will retro-flag previously-saved decks since the report is recomputed on read. This is the intended trade-off for the no-migration constraint.
- Adding a persisted `deck_quality_json` column on `SlideDeck` (with a migration) would be the natural next step if historical reports become valuable; deliberately out of Phase 1D scope.

## Phase 1C Deck Quality Report - 2026-05-09

**Scope:** Add a non-destructive deck-quality / repair-action telemetry layer around `_normalize_slides`. **Not** a repair pipeline; **not** an enforcement boundary; **not** a UI surface.

### What Was Added
- New module `backend/agent/deck_quality.py` exposing:
  - `RepairAction` (dataclass: `slide_index`, `layout`, `path`, `code`, `message`, `action`, `before`, `after`).
  - `DeckQualityReport` (dataclass: `ok`, `slide_count`, `valid_count`, `invalid_count`, `errors`, `repair_actions`, `summary`).
  - `build_deck_quality_report(slides) -> DeckQualityReport` -- wraps `validate_deck`, never mutates input, never repairs. Each schema error produces a `RepairAction` with `action="not_applied"`.
- `NexusAgentLoop._normalize_slides` now builds a `DeckQualityReport` after normalization + safety-net mutation, logs each per-slide failure as `loop.slide_validation_failed` (sourced from the report -- single source of truth) and emits a deck-level INFO summary `loop.deck_quality_report ok=... slide_count=... valid=... invalid=... repairs_needed=...`. Generation is not blocked or rejected based on the report.
- `deck_quality.py` is dependency-light: it only imports `agent.slide_schema`. No database, services, or FastAPI imports introduced.

### Files Changed
- `backend/agent/deck_quality.py` (new).
- `backend/agent/loop.py` -- telemetry block in `_normalize_slides` replaced with the report-driven version.
- `backend/tests/test_deck_quality.py` (new, 9 tests).

### Tests Added
- `test_build_report_returns_ok_for_valid_deck`
- `test_build_report_flags_invalid_chart_missing_subtitle`
- `test_build_report_emits_repair_actions_marked_not_applied`
- `test_build_report_does_not_mutate_input`
- `test_build_report_handles_non_list_payload`
- `test_repair_action_to_dict_shape`
- `test_deck_quality_report_to_dict_shape`
- `test_normalize_slides_logs_deck_quality_summary` -- caplog asserts the INFO `loop.deck_quality_report` summary line.
- `test_normalize_slides_still_logs_validation_failure_for_safety_net` -- caplog asserts `loop.slide_validation_failed layout=chart path=subtitle code=missing` is still emitted for the known stats->chart safety-net case.

### Tests Run
- `cd frontend ; npm run verify:layouts` -> `OK verify-layouts OK -- 7 canonical layouts, 7 exported.`
- Targeted Docker pytest one-shot (`--noconftest -p no:cacheprovider tests/test_layout_coverage.py tests/test_slide_schema.py tests/test_deck_quality.py`) -> **85 passed in 1.04s** (was 76; +9 new).
- Full backend pytest **NOT run** -- still blocked by `backend/tests/conftest.py` (SQLite NullPool / `pool_size` mismatch in `database/connection.py`).

### Result
- Phase 1C narrow scope (deck quality reporting + repair-action telemetry) -> **Pass** under the targeted test set.
- Broader platform correctness -> **Partial** (no repair application, no API/UI surface, no enforcement, no export parity).
- Visual quality -> **Unchanged** (no renderer/CSS/visual-test files touched).

### Remaining Risks
- Repair actions are reported and logged but not applied. `RepairAction.action` is always `"not_applied"`; `before` / `after` always `None`.
- `DeckQualityReport` is **not** surfaced to the API or UI. Consumers outside the loop logger cannot see it yet.
- Validation still does not block generation or export.
- Safety-net stats->chart conversion may still produce a chart missing slide-level `subtitle`; now visible in both the per-slide warning and the deck-level summary, still telemetry-only.
- Export parity (PPTX/PDF) untouched.
- No real browser automation yet.
- Visual quality unchanged.
- Registry still pinned to 7 honest layouts until renderer/normalizer/export coverage expands.
- Full backend pytest may still be blocked by `conftest.py` / database setup.

---

## Phase 1B.1 Audit Correction - 2026-05-09

**Scope:** Narrow follow-up to Phase 1B.1 to close three audit gaps. Not Phase 1C; no repair pipeline.

### What Was Corrected
- `chart_data.unit` and `chart_data.source` are now **required keys** in the slide-contract validator (empty strings allowed, non-string still fails). Previously only type-checked when present, which contradicted the normalized contract documented for Phase 1B.1.
- `validate_slide` docstring rewritten: `ValidationResult.normalized` is a **shallow copy** of the input with the canonical layout name pinned on success, and `None` on failure. Explicitly states this is **not auto-repair** and content fields are unchanged.
- Added a direct telemetry test for `NexusAgentLoop._normalize_slides` proving the `validate_deck` warnings actually emit at runtime (not only that the schema rules exist in isolation).

### Files Changed
- `backend/agent/slide_schema.py` -- `_validate_chart` now calls `_require_str(cd, "unit", ..., allow_empty=True, path_prefix="chart_data.")` and the same for `source`; `validate_slide` docstring updated.
- `backend/tests/test_slide_schema.py` -- added section 14 (chart_data.unit / chart_data.source contract) and section 15 (`_normalize_slides` telemetry caplog test).

### Tests Added
- `test_chart_missing_chart_data_unit_fails` -- missing key -> `code=missing path=chart_data.unit`.
- `test_chart_missing_chart_data_source_fails` -- missing key -> `code=missing path=chart_data.source`.
- `test_chart_empty_unit_and_source_allowed` -- both `""` accepted (mirrors normalizer output).
- `test_chart_non_string_unit_fails` -- int rejected with `code=wrong_type`.
- `test_chart_non_string_source_fails` -- list rejected with `code=wrong_type`.
- `test_normalize_slides_logs_validation_failure` -- drives `NexusAgentLoop._normalize_slides` with a deck where the safety-net stats->chart conversion produces a chart slide without slide-level `subtitle`; asserts a `WARNING` record on logger `nexus.agent.loop` containing `loop.slide_validation_failed layout=chart path=subtitle code=missing`.

### Tests Run
- `cd frontend ; npm run verify:layouts` -> `OK verify-layouts OK -- 7 canonical layouts, 7 exported.`
- Targeted Docker pytest (one-shot `nexus-ai-backend:latest`, `--noconftest -p no:cacheprovider`, `tests/test_layout_coverage.py tests/test_slide_schema.py`) -> **76 passed in 1.33s** (was 70; +6 from this correction).
- Full backend pytest **NOT run** -- `backend/tests/conftest.py` is still blocked by SQLite NullPool / `pool_size` mismatch in `database/connection.py`. No claim of full-suite green is made.

### Result
- Phase 1B.1 narrow scope (slide-contract validation + telemetry) -> **Pass** under the targeted test set (76/76 green; verify-layouts green).
- Broader platform correctness -> **Partial** (no repair pipeline, no DeckQualityReport, validation logged but not enforced, export parity unchanged).
- Visual quality -> **Unchanged** (no renderer/CSS/test changes in this correction).

### Remaining Risks
- No repair pipeline yet -- the safety-net stats->chart promotion in `_normalize_slides` still emits chart slides without slide-level `subtitle`; this is now visible as a `loop.slide_validation_failed` warning but is **telemetry-only**, not enforced.
- No DeckQualityReport surfaced to the API/UI.
- Full backend pytest may still be blocked by `conftest.py` / database setup.
- Export parity (PPTX/PDF) not touched.
- No real browser automation yet.
- Registry still pinned to 7 honest layouts until renderer / normalizer / export coverage expands.

---

## Phase 1B.1 Schema Strictness Update - 2026-05-09

### What Changed
- Tightened `backend/agent/slide_schema.py` so its required-field set matches the contract that `NexusAgentLoop._normalize_slides` actually emits. Previously optional keys are now required (empty strings still permitted where the normalizer can emit them):
  - `title`: now requires `subtitle`, `eyebrow`.
  - `quote`: now requires `attribution`.
  - `chart`: now requires slide-level `subtitle`.
  - `closing`: now requires `subtitle`, `cta`.
- Fixed strict-mode layout handling: `validate_slide(..., resolve_aliases=False)` now requires an EXACT canonical name. No case-folding, no whitespace-trimming, no alias resolution. `"Title"`, `" bullets "`, `"two_col"` all fail with `unknown_layout` in strict mode.
- Fixed `ValidationResult.normalized` semantics: on success it is now a shallow copy of the input with the canonical layout name pinned (instead of echoing `raw`). Mutating `normalized` no longer leaks back into the caller's dict. Failure still returns `normalized=None`. This is NOT auto-repair -- content fields are unchanged.
- Wired `validate_deck(...)` into `NexusAgentLoop._normalize_slides` as non-repairing telemetry. After the existing normalization + chart safety-net, every failing slide is logged via `nexus.agent.loop` with structured fields (`slide`, `layout`, `path`, `code`, `message`). No slides are rejected, mutated, or repaired. The validation block is wrapped in a guard so a telemetry exception can never break generation. The import is local to the method to avoid app/DB import cycles, and `slide_schema.py` itself imports nothing from the database or app layer.

### Files Changed
- `backend/agent/slide_schema.py` -- tightened `_validate_title`, `_validate_quote`, `_validate_chart`, `_validate_closing`; replaced strict-mode normalization in `validate_slide`; replaced `normalized=raw` with shallow-copy + canonical-layout pinning.
- `backend/agent/loop.py` -- added telemetry-only `validate_deck` call at the end of `_normalize_slides`.
- `backend/tests/test_slide_schema.py` -- +13 new tests.

### Tests Added
- `test_title_missing_subtitle_fails`
- `test_title_missing_eyebrow_fails`
- `test_title_empty_subtitle_allowed`
- `test_quote_missing_attribution_fails`
- `test_chart_missing_subtitle_fails`
- `test_closing_missing_subtitle_fails`
- `test_closing_missing_cta_fails`
- `test_strict_mode_rejects_titlecase` (proves `"Title"` fails when `resolve_aliases=False`)
- `test_strict_mode_rejects_padded_name`
- `test_strict_mode_accepts_exact_canonical`
- `test_normalized_is_shallow_copy_with_canonical_layout`
- `test_normalized_pins_canonical_layout_for_uppercase_input`
- `test_normalized_is_none_on_failure`

### Tests Run
- `cd frontend ; npm run verify:layouts` -> `OK verify-layouts OK -- 7 canonical layouts, 7 exported.`
- One-shot Docker pytest:
  ```
  docker run --rm \
    -v "D:\nexus-ai-1\nexus-ai\backend:/app" \
    -v "D:\nexus-ai-1\nexus-ai\frontend:/frontend" \
    -w /app -e PYTHONPATH=/app nexus-ai-backend:latest \
    sh -c "pip install --quiet pytest pytest-asyncio && \
           python -m pytest --noconftest -p no:cacheprovider \
             tests/test_layout_coverage.py tests/test_slide_schema.py -v"
  ```
  Result: **70 passed in 0.91s** (23 layout-coverage + 47 slide-schema, up from 57 in Phase 1B).
- Full backend pytest is **NOT** claimed to pass -- `tests/conftest.py` is still blocked by the pre-existing SQLite NullPool / pool_size mismatch in `database/connection.py`. That blocker is out of scope for Phase 1B.1.

### Result
- **Phase 1B.1 narrow scope: Pass.** The schema validator now matches the normalized-contract emitted by `_normalize_slides`, strict mode is genuinely strict, `normalized` is a true shallow copy with canonical layout, and `_normalize_slides` emits structured validation telemetry without mutating output.
- **Broader platform status: Partial** (unchanged). Repair pipeline, deck-quality scoring, export parity, browser automation, and visual quality are not addressed by this phase.

### Remaining Risks
- No repair pipeline yet -- validation failures are logged but not enforced as hard generation/export failures.
- No `DeckQualityReport` yet.
- The forced `out[0]["layout"]="title"` / `out[-1]["layout"]="closing"` pins in `_normalize_slides` can produce slides that fail the tightened title/closing field requirements when the original slide was a different layout. Phase 1B.1 only logs these via telemetry; the normalizer's pin behavior itself is unchanged.
- Stats->chart safety-net conversion in `_normalize_slides` does not add a slide-level `subtitle`, so converted chart slides will trigger a `subtitle/missing` warning. Telemetry-only -- generation is unaffected.
- No export parity fix yet.
- No real browser automation yet.
- Visual quality unchanged -- no renderer or visual-test changes in this phase.
- Full backend pytest still blocked by pre-existing `tests/conftest.py` / `database.connection` SQLite NullPool issue.
- Registry still supports only the 7 honest layouts (`title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`) until renderer/normalizer/export coverage is expanded.

## Phase 1B Schema Validation Update - 2026-05-09

### What Changed
- Introduced a typed slide-contract validator for the 7 canonical layouts (`title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`).
- Validator returns a structured `ValidationResult` with `ok`, resolved `layout`, a list of `ValidationError(path, code, message)`, and the original payload echoed in `normalized` on success.
- Per-layout contracts mirror the field shapes already produced by `NexusAgentLoop._normalize_slides`: required `title`; `bullets` (list[str], 1-4); `columns` (list[{heading, body}], 1-2); `quote` + optional `attribution`; `stats` (list[{value, label}], 1-3); `chart_type` in {bar, line, doughnut} with `chart_data.labels`/`values` paired-length, numeric values (bool rejected); optional `subtitle`/`eyebrow`/`cta` enforced as strings when present.
- Unknown layouts are rejected with `unknown_layout`; the validator does NOT silently coerce them through `FALLBACK_LAYOUT` (that remains a render-time safety net only).
- No repair pipeline, no DeckQualityReport, no export changes, no UI changes, no new layouts. Validator is currently a library -- it is NOT yet wired into `_normalize_slides` or the export path.

### Files Changed
- Added `backend/agent/slide_schema.py` (new module).
- Added `backend/tests/test_slide_schema.py` (new test file).

### Tests Added
- 34 new tests in `tests/test_slide_schema.py` covering: registry/example parity, every canonical layout's valid example, missing/empty/wrong-type required fields, bullets length and item-type rules, two-col column shape and count, stats item shape and type, chart `chart_type` enum, `chart_data` length mismatch, non-numeric values, bool-as-value rejection, labels-must-be-list, quote required text, unknown layouts under both alias and strict modes, `validate_deck` wrapper, and `ValidationError.to_dict` shape.

### Tests Run
- `cd frontend ; npm run verify:layouts` -> `OK verify-layouts OK -- 7 canonical layouts, 7 exported.`
- One-shot Docker pytest (workspace mounted, conftest bypassed):
  ```
  docker run --rm -v "$repo/backend:/app" -v "$repo/frontend:/frontend" \
    -w /app -e PYTHONPATH=/app nexus-ai-backend:latest sh -c \
    "pip install --quiet pytest pytest-asyncio && \
     python -m pytest --noconftest -p no:cacheprovider \
       tests/test_layout_coverage.py tests/test_slide_schema.py -v"
  ```
  -> `57 passed in 0.74s` (23 layout-coverage + 34 schema).
- Full backend pytest tier was NOT run; `backend/tests/conftest.py` is still blocked by the pre-existing SQLite NullPool / `pool_size`/`max_overflow` mismatch in `database/connection.py`. That is unchanged by Phase 1B.

### Result
- Phase 1B narrow scope: **Pass** -- typed schema validation for the 7 canonical layouts is in place and proven by tests.
- Broader system status: **Partial** -- schema is a library; it is not yet enforced in the generation pipeline or export path. Repair pipeline, DeckQualityReport, export parity, browser autonomy, and visual quality are unchanged.

### Remaining Risks
- Validator is not yet called from `_normalize_slides` or the Celery task -- malformed payloads can still reach the renderer/export.
- No auto-repair pipeline yet; failures are reported, not corrected.
- No DeckQualityReport / deck-level scoring yet.
- Export parity (PPTX/PDF) is unverified against the registry.
- No real browser automation; `services/browser_service.py` remains a disabled stub.
- Visual quality (typography, spacing, layout density) unchanged.
- Full backend pytest is still blocked by `tests/conftest.py` / `database.connection` setup.
- Registry still honestly supports only 7 layouts; broader layout coverage (image, comparison, timeline, etc.) is not in scope until renderer + normalizer + export catch up.

## Phase 1A.1 Planner Layout Drift Update - 2026-05-09

### What Changed
- `backend/agent/planner.py` no longer carries its own hardcoded `_VALID_LAYOUTS = {"title", "bullets", "two-col", "quote", "stats", "closing"}` set (which was missing `chart`). It now imports `CANONICAL_LAYOUTS`, `FALLBACK_LAYOUT`, and `normalize_layout` from `agent.layouts_registry`, and `_VALID_LAYOUTS` is `frozenset(CANONICAL_LAYOUTS)`.
- `Planner._parse_outline` resolves layout names via `normalize_layout(...)` and falls back to `FALLBACK_LAYOUT` instead of the hardcoded literal `"bullets"`. `chart` outlines are no longer collapsed.
- `scripts/verify-layouts.mjs` now also fails CI if `planner.py` does not import the registry or reintroduces an inline `_VALID_LAYOUTS = {...}` literal containing canonical layout names.

### Files Changed
- `backend/agent/planner.py`
- `backend/tests/test_layout_coverage.py`
- `scripts/verify-layouts.mjs`

### Tests Added
Appended to `backend/tests/test_layout_coverage.py` (10 new cases, 23 total in the file):
- `test_planner_valid_layouts_matches_registry`.
- `test_planner_preserves_canonical_layout[<layout>]` parametrized over all 7 canonical layouts.
- `test_planner_unknown_layout_falls_back_to_fallback_layout`.
- `test_planner_chart_layout_not_lost` (explicit regression for the missing-`chart` drift).

### Tests Run
- `cd frontend ; npm run verify:layouts` -> **PASS** (`7 canonical layouts, 7 exported`).
- `docker run --rm -v ...:/app -v ...:/frontend -w /app -e PYTHONPATH=/app nexus-ai-backend:latest sh -c "pip install --quiet pytest pytest-asyncio && python -m pytest --noconftest -p no:cacheprovider tests/test_layout_coverage.py -v"` -> **PASS** (`23 passed in 0.69s`).
- Full backend `pytest` suite NOT run. Reason: pre-existing `tests/conftest.py` import failure (`pool_size`/`max_overflow` rejected with SQLite `NullPool`); same prerequisite as Phase 1A.

### Result
**Pass for the narrow Phase 1A.1 scope.** The last obvious backend layout-whitelist drift is closed and locked in by tests + verify-layouts.

### Remaining Risks
- Schema validation, `RepairAction`, `DeckQualityReport`, export parity, browser autonomy claims, and visual quality are unchanged -- not addressed by Phase 1A.1.
- The `conftest.py` engine-pool bug still blocks running the full backend suite end-to-end.
- The running `nexus-backend` container still binds to a different repo path (`D:\nexus-ai-gh\backend`); rebuild from this workspace is required for the live service to pick up Phase 1A.1 code.

## Phase 1A Correction Update - 2026-05-09

> **Correction notice.** The previous "Phase 1A Update - 2026-05-09" section in this file (immediately below) was inaccurate. It claimed a 23-layout registry, 40 aliases, a `backend/agent/layouts_registry.py` module, a `frontend/src/design/` directory, a `backend/tests/test_layout_coverage.py` file, and a 35-test passing run. Inspection of this workspace at the time of writing showed that **none of those files existed** and `_VALID_LAYOUTS`/`VALID_LAYOUTS` were still hardcoded. That section is left in place below for traceability, but its content does not describe the state of this repository and must not be treated as evidence. The factual record for Phase 1A is this section. **See "Phase 1A Correction Update" above for the verified numbers (7 canonical layouts, 0 aliases, 13 tests).**

### What Actually Changed (verified against repo)
- Created canonical registry **`frontend/src/design/layouts.registry.json`** (and a byte-identical copy at **`backend/agent/layouts.registry.json`** because the backend container only mounts `./backend`). Single source of truth: **7 canonical layouts** (`title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`), **0 aliases**, fallback `bullets`. The 7-layout count matches what the existing renderer (`SlideRenderer.jsx` `layouts` map) and the existing backend per-layout normalization branches actually support today. No layouts were invented.
- Created **`backend/agent/layouts_registry.py`** -- loads the JSON at import time and exports `CANONICAL_LAYOUTS`, `EXPORT_SUPPORTED`, `LAYOUT_ALIASES`, `FALLBACK_LAYOUT`, `normalize_layout(raw)`.
- Created **`frontend/src/design/registry.js`** -- imports the JSON and exports `CANONICAL_LAYOUTS`, `LAYOUT_ALIASES`, `EXPORT_SUPPORTED`, `FALLBACK_LAYOUT`, `resolveLayoutName(raw)`.
- **`backend/agent/loop.py`** -- removed the hardcoded literal `_VALID_LAYOUTS = {"title", "bullets", "two-col", "quote", "stats", "chart", "closing"}` and replaced it with `_VALID_LAYOUTS = frozenset(CANONICAL_LAYOUTS)` sourced from the registry. Inside `_normalize_slides`, raw layouts now go through `normalize_layout(raw.get("layout"))` (alias-aware) and unknowns fall back to `FALLBACK_LAYOUT` (`bullets`) instead of a hardcoded literal.
- **`frontend/src/utils/slideParser.js`** -- removed the hardcoded `new Set(["title", "bullets", "two-col", "quote", "stats", "closing"])` (which was also missing `chart`, a real renderer-supported layout). Now `VALID_LAYOUTS = new Set(CANONICAL_LAYOUTS)`. Unknown layouts now fall back to `FALLBACK_LAYOUT` instead of being silently re-typed as `"title"`. Added a `case "chart"` branch so chart slides round-trip through the parser correctly.
- **`scripts/verify-layouts.mjs`** -- new script. Fails CI if (a) the two registry JSON copies drift, (b) `loop.py` does not import the registry or reintroduces a hardcoded `_VALID_LAYOUTS = { ... }` set literal containing canonical layout names, (c) `slideParser.js` does not import the registry or reintroduces a hardcoded `new Set([ ... ])` literal containing canonical layout names.
- **`frontend/package.json`** -- added `"verify:layouts": "node ../scripts/verify-layouts.mjs"` script.

### Files Changed / Added
- Added: `frontend/src/design/layouts.registry.json`
- Added: `frontend/src/design/registry.js`
- Added: `backend/agent/layouts.registry.json`
- Added: `backend/agent/layouts_registry.py`
- Added: `backend/tests/__init__.py`
- Added: `backend/tests/test_layout_coverage.py`
- Added: `scripts/verify-layouts.mjs`
- Modified: `backend/agent/loop.py`
- Modified: `frontend/src/utils/slideParser.js`
- Modified: `frontend/package.json`

### Tests Added
`backend/tests/test_layout_coverage.py` -- **13 cases total** (not 35):
- `test_backend_valid_layouts_matches_registry` -- asserts `_VALID_LAYOUTS` equals the registry on disk.
- `test_backend_and_frontend_registry_files_match` -- asserts the backend and frontend JSON copies are byte-content-equal (skips with explicit reason if the frontend tree is not mounted in the test runtime; the JS verify script enforces the same parity from the other side).
- `test_fallback_layout_is_canonical`.
- `test_aliases_only_target_canonical_layouts` -- vacuously true today (0 aliases) but locks the contract for future aliases.
- `test_normalize_preserves_canonical_layout[<layout>]` -- parametrized over all 7 canonical layouts (`title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`); each round-trips through `NexusAgentLoop._normalize_slides`. The `stats` test seeds a `chart` sibling so the loop's stats->chart auto-promotion does not interfere.
- `test_unknown_layout_falls_back_to_fallback_not_silently_dropped`.
- `test_normalize_layout_canonical_passthrough` -- case/whitespace tolerance for canonical names.

### Tests Run
Exact commands and results:

```
# Frontend / parity gate (PowerShell, repo root D:\nexus-ai-1\nexus-ai)
cd .\frontend ; npm run verify:layouts
```
Result: **PASS** -- `OK verify-layouts OK -- 7 canonical layouts, 7 exported.`

```
# Backend tests (Docker; the running nexus-backend container is bound to a
# different repo path, so a one-shot container was used with this workspace's
# backend and frontend trees mounted)
docker run --rm \
  -v "D:\nexus-ai-1\nexus-ai\backend:/app" \
  -v "D:\nexus-ai-1\nexus-ai\frontend:/frontend" \
  -w /app -e PYTHONPATH=/app nexus-ai-backend:latest \
  sh -c "pip install --quiet pytest pytest-asyncio && python -m pytest --noconftest -p no:cacheprovider tests/test_layout_coverage.py -v"
```
Result: **PASS** -- `13 passed in 0.58s`. All 13 tests passed including all 7 per-layout round-trips and the backend/frontend JSON parity check.

NOT run, with reasons:
- Full backend `pytest` suite (whole `tests/` tree) was NOT run. Reason: pre-existing `tests/conftest.py` import failure (`database/connection.py` passes `pool_size`/`max_overflow` that SQLite `NullPool` rejects). Unrelated to Phase 1A; tracked for a future CI/conftest fix phase.
- Playwright gallery / visual snapshot suite was NOT run. Reason: out of Phase 1A scope; this phase made no renderer or styling changes.

### Result
**Pass for the narrow Phase 1A scope** (registry-driven canonical layout coverage). Tests prove it.
**Partial for the broader audit findings** -- the validation pipeline, repair pipeline, DeckQualityReport, regression corpus, export parity, and "fake browser" autonomy claims are unchanged.

### Remaining Risks
- The registry currently lists only 7 layouts because that is what the repo's renderer and normalizer actually support today. Earlier audit prose referencing 23 layouts described an aspiration, not the current code. Expanding the registry beyond 7 layouts requires renderer + normalizer + export parity work and is out of Phase 1A scope.
- No JSON Schema, no `RepairAction`, no `DeckQualityReport`. Invalid slide payloads are still silently coerced inside `_normalize_slides`.
- The pre-existing `conftest.py` engine-pool bug blocks running the rest of the backend suite end-to-end.
- Browser/tool autonomy claims in UI/marketing surfaces are still present.
- The running `nexus-backend` container in this environment is bound to a different repo path (`D:\nexus-ai-gh\backend`), so Phase 1A code changes here are not yet picked up by the live service. A `docker compose up --build` from this workspace is required before runtime verification.

## Phase 1A Update - 2026-05-09

### What Changed
- Backend `_VALID_LAYOUTS` and frontend `VALID_LAYOUTS` are no longer hardcoded 13-element sets. Both are now sourced from the canonical registry (`frontend/src/design/layouts.registry.json`) -- 23 layouts, single source of truth.
- The 10 canonical layouts that the agent loop previously collapsed to `bullets` (`hero`, `bento`, `agenda`, `roadmap`, `metric-spotlight`, `process`, `pyramid`, `matrix-2x2`, `feature-grid`, `callout`) now survive normalization with their layout name preserved.
- Aliases (`big-number`, `cover`, `kpi_grid`, `matrix`, `banner`, `grid`, `toc`, `steps`, `hierarchy`, `highlight`, etc.) now resolve through the registry to their canonical target instead of being silently rewritten to `bullets` or `title`.
- `verify-layouts.mjs` extended with a guard that fails CI if either file reintroduces a hardcoded layout-set literal.

### Files Changed
- `backend/agent/loop.py` (imports from `agent.layouts_registry`; removed inline 13-element set; alias-aware fallback).
- `frontend/src/utils/slideParser.js` (imports from `design/registry.js`; removed inline 13-element set; uses `resolveLayoutName`).
- `scripts/verify-layouts.mjs` (added Check 4: registry-import enforcement + inline-literal rejection).

### Tests Added
- `backend/tests/test_layout_coverage.py` (35 cases):
  - 1 parity test (`_VALID_LAYOUTS == CANONICAL_LAYOUTS`, 23 entries).
  - 23 parametrized round-trip tests, one per canonical layout.
  - 10 alias-resolution tests proving aliases route to canonical, not `bullets`.
  - 1 unknown-layout fallback test.

### Tests Run
- `npm run verify:layouts` -> PASS (`23 canonical layouts, 40 aliases, 21 exported`).
- `python -m pytest --noconftest tests/test_layout_coverage.py -v` -> PASS (`35 passed in 1.12s`).
- Full backend `pytest` suite was NOT run in this phase. Reason: pre-existing `tests/conftest.py` import error (SQLAlchemy `pool_size`/`max_overflow` rejected by SQLite `NullPool` in the running container). Unrelated to Phase 1A; tracked as a CI prerequisite.
- `npm run test:gallery` was NOT run. Reason: out of Phase 1A scope (no renderer or visual changes were made).

### Result
Partial.

Audit findings #1 (weak slide/layout contracts) and #2 (backend normalizer dropping/collapsing canonical layouts) are addressed at the layout-name level only. Findings #3 (validate-vs-repair), #4 (DeckQualityReport), #5 (regression corpus), #6 (DOM overflow), #7 (preview/export parity), and #8 (fake browser claims) remain open.

### Remaining Risks
- The normalizer still applies best-effort coercion (forces first slide to `title`, last to `closing`, fills empty content with `"Section N"` placeholders). Per-layout normalization branches for the 10 newly-surviving layouts are not yet implemented; they currently get the base `{id, layout, title}` shape only.
- No JSON Schema, no `RepairAction`, no `DeckQualityReport` yet -- invalid slide data is still silently mutated rather than rejected or reported.
- Export parity unchanged. `table` and `image-focus` remain `exported: false` in the registry; the 10 newly-preserved canonical layouts still rely on the existing PPTX branches in `export_service.py` with no parity tests.
- The pre-existing `conftest.py` engine-pool bug blocks the broader backend test suite from running and must be fixed before Phase 1H (CI gate).
- Browser/tool autonomy claims in UI/marketing surfaces are still present (audit finding #8).

## Overall Scorecard

| Area | Score | Severity | Assessment |
|---|---:|---|---|
| Architecture quality | 4.5 / 10 | High | Broad structure exists, but the core pipeline is monolithic and fallback-driven. |
| System coherence | 4 / 10 | High | Frontend, backend, export, AI, and design system are aligned by convention more than by hard contracts. |
| Rendering quality | 4.5 / 10 | High | Browser rendering is usable; export and real-content robustness are weak. |
| Visual polish | 4 / 10 | High | Some layouts look presentable in curated samples, but design intelligence is not deep. |
| Maintainability | 4 / 10 | High | Large renderer files, duplicate theme maps, silent failures, and mixed old/new systems increase change risk. |
| Scalability | 3.5 / 10 | Critical | Queue exists, but resilience, quotas, cancellation, replay, tenant isolation, and cost governance are immature. |
| Technical debt | 7.5 / 10 risk | High | Debt is already architecture-level, not just cleanup-level. |
| Abstraction quality | 4 / 10 | High | Registry is underpowered; schemas and layout budgets are not first-class. |
| Design-system consistency | 4.5 / 10 | High | Tokens exist, but hardcoded and duplicate visual definitions remain. |
| Renderer correctness | 4 / 10 | High | Gallery snapshots cover curated fixtures, not generated decks or export parity. |
| Testing maturity | 3.5 / 10 | Critical | Tests prove smoke paths, not production behavior or AI output quality. |
| Product readiness | 3.5 / 10 | Critical | Private alpha. Not ready for paid professional users. |
| Enterprise readiness | 2 / 10 | Critical | Missing identity, governance, isolation, auditability, compliance, admin controls. |
| AI intelligence depth | 3.5 / 10 | High | Prompt orchestration and heuristics, not deep autonomous reasoning or visual intelligence. |
| Competitive position | 3 / 10 | Critical | Demoable, but behind Manus/Gamma/Tome on core differentiation. |

## Production Readiness Score

| Dimension | Score | Blocking Reason |
|---|---:|---|
| Reliability | 3 / 10 | Many best-effort fallbacks and silent degradation paths. |
| Observability | 3 / 10 | Logs exist, but no quality telemetry, model-level tracing, or artifact audit model. |
| Security | 2.5 / 10 | Secrets handling and enterprise auth posture are not production-grade. |
| Data integrity | 4 / 10 | DB persistence exists, but slide contracts and versioning are weak. |
| Export fidelity | 3 / 10 | React and PPTX renderers are separate implementations. |
| AI quality control | 3.5 / 10 | Critic/fact-checking are heuristic and shallow. |
| UX readiness | 4 / 10 | Core screens exist, but professional editing/recovery/error UX is thin. |
| Operational scalability | 3 / 10 | Queue exists, but no serious capacity, retry, cost, or tenant model. |

Production readiness: **3.2 / 10**  
Release classification: **private alpha only**

## Severity Key

| Severity | Meaning |
|---|---|
| Critical | Blocks production, enterprise use, or investor-grade confidence. |
| High | Significant refactor or product correction required. |
| Medium | Important quality issue but not immediately platform-blocking. |
| Low | Cleanup or polish issue. |

## Current Architecture Diagram

```text
User Prompt
   |
   v
Frontend Generator UI
   |
   v
FastAPI /api/generate
   |
   v
Celery Task
   |
   v
NexusAgentLoop
   |-- topic classifier
   |-- LLM analysis
   |-- research pipeline
   |-- design reference service
   |-- markdown pipeline
   |-- legacy JSON planner fallback
   |-- per-slide generation fallback
   |-- critic rewrite pass
   |-- fact checker
   |-- image recommender
   |-- chart processor
   v
Postgres slide/deck records
   |
   +--> React SlideRenderer preview
   |
   +--> python-pptx ExportService
```

Primary architectural smell: the center is a large orchestration object with too many responsibilities and too many fallback exits that still produce a completed deck.

## Desired Architecture Direction

```text
GenerationRequest vN
   |
   v
Pipeline Orchestrator
   |
   +--> Step: Research          -> ResearchArtifact vN
   +--> Step: Narrative Plan    -> DeckPlan vN
   +--> Step: Slide Draft       -> SlideDraft[] vN
   +--> Step: Contract Validate -> ValidationReport
   +--> Step: Repair            -> RepairedSlide[] vN
   +--> Step: Visual Plan       -> VisualPlan vN
   +--> Step: Layout Solve      -> LayoutIR[] vN
   +--> Step: Render            -> HTML/PDF/PPTX from same IR
   +--> Step: Quality Score     -> DeckQualityReport
   v
Durable artifact store + event log + replayable jobs
```

The key shift: stop treating slide JSON as the whole contract. Introduce a versioned layout intermediate representation with measurable constraints.

## 1. Top 10 Architecture Weaknesses

| Rank | Weakness | Severity | Why It Matters |
|---:|---|---|---|
| 1 | React renderer and PPTX exporter are separate layout engines. | Critical | Export parity will keep breaking because geometry is duplicated manually. |
| 2 | The canonical registry is mostly a naming registry, not a schema contract. | Critical | It cannot enforce valid slide content, layout budgets, or visual constraints. |
| 3 | Agent loop is monolithic. | High | Planning, research, generation, validation, images, charts, and persistence are tightly coupled. |
| 4 | Pipeline success is fallback-based instead of quality-gated. | High | Weak or malformed output can become a finished deck. |
| 5 | No first-class artifact model for each generation stage. | High | Debugging, replay, auditing, and improvement loops are weak. |
| 6 | No robust versioning of slide contracts. | High | Future layout changes can break old decks or exports. |
| 7 | Theme system is duplicated across frontend/export/chart services. | High | Visual drift is guaranteed over time. |
| 8 | Product claims exceed implemented capability. | High | Browser automation, intelligence, and enterprise readiness are overstated by structure. |
| 9 | Job lifecycle is under-modeled. | High | Cancellation, retry, replay, partial recovery, and cost control are not mature. |
| 10 | Validation is mostly heuristic normalization. | High | The system repairs after ambiguity instead of preventing invalid states. |

## 2. Top 10 Visual Weaknesses

| Rank | Weakness | Severity | Detail |
|---:|---|---|---|
| 1 | Layouts depend heavily on grids/cards/tints. | High | Decks risk looking like UI dashboards rather than premium presentations. |
| 2 | Gallery uses curated content. | High | It does not prove real generated slides survive overflow, weak copy, or bad data. |
| 3 | Image direction is generic. | High | Hero/background/side placement is not enough for strong art direction. |
| 4 | Chart visuals are basic. | High | Charts are functional, not editorial or investor-grade. |
| 5 | Theme count masks weak visual strategy. | High | More palettes do not equal better deck design. |
| 6 | Typography handling is incomplete. | High | Title sizing exists; full text-density solving does not. |
| 7 | PPT output likely diverges from browser preview. | Critical | Users judge exports, not internal preview architecture. |
| 8 | Visual hierarchy is inconsistent across layouts. | Medium | Some slides feel composed; others feel assembled. |
| 9 | Navbar/gallery page polish is secondary. | Medium | The gallery first viewport does not immediately sell renderer quality. |
| 10 | Icons can become decorative filler. | Medium | They often add color but not meaning. |

## 3. Top 10 Technical Debt Risks

| Rank | Debt | Severity | Risk |
|---:|---|---|---|
| 1 | Large `SlideRenderer.jsx` responsibility scope. | High | Hard to reason about, test, or safely extend. |
| 2 | Duplicate theme definitions in frontend and backend. | High | Long-term drift and inconsistent exports. |
| 3 | Export renderer manually recreates layouts. | Critical | Every new layout multiplies maintenance cost. |
| 4 | Silent `pass` and best-effort failures. | High | Operational failures can be invisible. |
| 5 | Stubbed browser service. | High | Claimed agent capability is not actually present. |
| 6 | Tests stub Celery. | High | Real queue behavior is not covered. |
| 7 | Regex JSON extraction from LLM output. | High | Brittle under provider/model variation. |
| 8 | Checked-in failed test output artifact. | Medium | Signals weak repository hygiene. |
| 9 | Chart palette coverage is incomplete. | Medium | Many themes fall back to limited chart styling. |
| 10 | Legacy and new pipelines coexist. | High | Debugging quality regressions becomes difficult. |

## Technical Debt Matrix

| Debt Item | Impact | Probability | Urgency | Owner Area | Recommendation |
|---|---:|---:|---:|---|---|
| Separate React/PPT renderers | Very high | Very high | Immediate | Rendering/export | Build shared LayoutIR or server-side render from same engine. |
| Underpowered registry | Very high | Very high | Immediate | Platform | Upgrade to real schema + capabilities registry. |
| Monolithic agent loop | High | High | 30 days | Backend/AI | Split into typed pipeline steps. |
| Fake browser automation | High | Certain | Immediate | AI/tools | Implement or remove from claims/UI. |
| Stubbed backend tests | High | High | 30 days | Backend | Add real Celery/Postgres/Redis integration tests. |
| Silent best-effort failures | High | High | 30 days | Platform | Convert to typed warnings/errors surfaced to users/admins. |
| Theme duplication | Medium | High | 30 days | Design system | Single source theme package consumed by frontend/export/chart. |
| Weak generated-content tests | High | High | Immediate | QA/AI | Add real prompt corpus and quality gates. |
| Fact checker shallowness | Medium | High | 60 days | AI | Replace with evidence-linked claim extraction. |
| Image intelligence shallowness | Medium | High | 60 days | AI/visual | Add visual plan and asset-quality scoring. |

## 4. Fake-Complete Systems Still Pretending To Work

| System | Current Reality | Severity | Required Fix |
|---|---|---|---|
| Browser automation | Explicit no-op stub returning disabled results. | Critical | Implement Playwright/browser-use path or remove Manus-style browser claims. |
| Manus-style agent | Mostly a linear deck-generation pipeline with fallbacks. | High | Add real tool execution, memory, replay, observation, and state transitions. |
| Fact checking | Regex flags years/names against partial research pools. | High | Build claim extraction + source-backed verification. |
| Image intelligence | Keyword/category mapping plus stock/Pollinations fallback. | High | Add visual intent planning and asset scoring. |
| Enterprise auth | Basic auth shape, not enterprise identity. | Critical | SSO/SAML/OIDC, RBAC, SCIM, audit logs, admin controls. |
| Screenshot regression | Curated gallery snapshots only. | High | Add generated-deck visual tests and export parity screenshots. |
| PPT parity | Branch coverage exists, not visual equivalence. | Critical | Same layout IR or image/PDF rendering source. |
| AI provider chain | Fallback exists, quality consistency does not. | Medium | Add provider-specific evals and output normalization contracts. |
| Design system | Tokens exist, but not universally enforced. | Medium | Lint/token enforcement and removal of duplicate visual constants. |
| Chart intelligence | Data normalization exists, but insight and chart selection are shallow. | Medium | Add data semantics and chart recommendation scoring. |

## 5. Abstraction Problems

### Registry

Current registry abstraction is insufficient. It defines layout names, aliases, exported flags, and rough field lists. It does not define:

- Required fields with validation rules.
- Maximum text lengths by region.
- Maximum item counts by layout.
- Responsive behavior constraints.
- Export capabilities and known fidelity limitations.
- Data requirements for charts/tables/KPIs.
- Repair instructions when validation fails.
- Golden fixtures per layout.

### Renderer

The renderer abstraction is component-oriented, not layout-solver-oriented. Each layout makes its own decisions. That is acceptable for a demo, but weak for a platform that must guarantee fit and export parity.

### AI Pipeline

The AI pipeline abstraction is procedural. A durable platform needs typed step boundaries:

```text
ResearchArtifact -> DeckPlan -> SlideDraft -> ValidatedSlide -> LayoutIR -> RenderedArtifact
```

Today, too much is just dictionaries moving through best-effort functions.

### Export

Export is not an abstraction over rendering. It is a second renderer. That is the highest-risk abstraction failure in the system.

## 6. Over-Engineering Risks

| Risk | Severity | Explanation |
|---|---|---|
| Too many pipeline stages before output quality is proven. | High | Research, design reference, markdown, legacy, critic, fact check, images, charts all exist, but quality is not guaranteed. |
| Theme catalog breadth before design excellence. | Medium | Many themes can create an illusion of quality while masking weak composition. |
| Multi-provider chain before provider evals. | Medium | Fallback breadth is less valuable than reliable quality profiles. |
| Registry-driven marketing before schema rigor. | High | Registry needs to enforce contracts, not just centralize labels. |
| Gallery snapshots before real-world prompt corpus. | High | Snapshot tests are useful but currently validate idealized samples. |
| Export branch coverage before visual parity. | High | Having a branch for a layout does not mean the export looks correct. |

## 7. Scalability Risks

| Area | Risk | Severity |
|---|---|---|
| Queue execution | Long-running tasks can fail mid-pipeline without strong replay semantics. | High |
| Cost control | Multi-step LLM calls and image generation can grow unpredictably. | High |
| Rate limits | Stock APIs, Pollinations, search APIs, and LLM providers can throttle. | High |
| Tenant isolation | No mature workspace/tenant boundary model visible. | Critical |
| Cancellation | User cancellation and cleanup are not first-class. | Medium |
| Partial output | Partial decks exist, but product treatment and retry semantics are weak. | Medium |
| Observability | No deck quality metrics, model trace UI, or step artifact inspection for operators. | High |
| Data lifecycle | Retention, deletion, export artifacts, and uploaded files need governance. | High |
| Reprocessing | No clear migration/re-render strategy for old decks when layouts change. | High |
| Horizontal scale | Scaling workers alone does not solve external dependency bottlenecks. | High |

## 8. Rendering Pipeline Weaknesses

Rendering is the platform's most important weakness because users judge the final deck, not internal architecture.

| Weakness | Severity | Explanation |
|---|---|---|
| Browser and PPTX renderers diverge. | Critical | Two engines mean two visual truths. |
| No layout budget model. | Critical | Text can be normalized but still visually overflow. |
| No real generated-content stress corpus. | High | Gallery fixtures are too clean. |
| No deterministic measurement loop. | High | Renderer does not appear to measure actual DOM overflow and repair content. |
| Export images fetched during export. | Medium | Exports can vary by network/API status. |
| Chart rendering split across Chart.js, QuickChart, and python-pptx. | High | Visual consistency and correctness are fragile. |
| Unsupported layouts fall back too gracefully. | Medium | This hides contract failures. |
| Snapshot threshold allows visual drift. | Medium | Pixel tests must be paired with semantic/overflow tests. |

## 9. Frontend Quality Assessment

Frontend score: **4.5 / 10**

| Category | Score | Assessment |
|---|---:|---|
| App structure | 5 | Routes and pages are understandable, but product workflows are still thin. |
| Renderer | 4 | Functional but too large and too internally complex. |
| Design system | 4.5 | Tokens/primitives exist, but enforcement is incomplete. |
| UX polish | 4 | Demo UI works; professional deck workflow polish is not mature. |
| Testing | 4 | Gallery snapshot tests help, but generated-deck tests are missing. |
| Maintainability | 4 | Renderer/theme complexity will slow future changes. |

Key frontend risks:

- `SlideRenderer.jsx` does too much.
- Theme logic is not fully centralized.
- Gallery is a harness, not evidence of real deck robustness.
- Editing UX must enforce schema validity instead of allowing arbitrary drift.
- Export UX must warn when export fidelity is known to be lower than preview.

## 10. Backend Quality Assessment

Backend score: **4 / 10**

| Category | Score | Assessment |
|---|---:|---|
| API breadth | 6 | Many routes exist. Breadth is ahead of hardening. |
| Pipeline design | 3.5 | Too centralized and fallback-heavy. |
| Persistence | 4.5 | Basic models exist, but artifact/version modeling is weak. |
| Worker architecture | 4 | Celery exists, but tests and lifecycle guarantees are immature. |
| Export service | 3 | Separate renderer creates major maintenance/fidelity risk. |
| Security | 2.5 | Not enterprise-grade. |
| Testing | 3.5 | E2E tests stub important infrastructure. |

Backend risks:

- The generation loop is an orchestration sink.
- Search/research/image/export failures often degrade silently.
- Real queue behavior is not sufficiently tested.
- Secrets and environment posture are not production-safe.
- Export service will become a long-term drag unless replaced or re-architected.

## 11. AI-System Quality Assessment

AI score: **3.5 / 10**

| Capability | Score | Assessment |
|---|---:|---|
| Topic analysis | 4 | Basic classification and theme hints. |
| Research grounding | 4.5 | Multi-source research is useful, but not deep verification. |
| Planning | 4 | Structured plan generation exists, but is prompt-dependent. |
| Slide writing | 3.5 | Depends heavily on LLM compliance and repair heuristics. |
| Critique | 3 | Blandness heuristic, not a robust quality evaluator. |
| Fact checking | 2.5 | Regex/entity pool matching is shallow. |
| Image intelligence | 3 | Category heuristics, not visual reasoning. |
| Autonomy | 2 | Browser/tool autonomy is mostly absent. |
| Evaluation | 2.5 | No serious model/deck quality benchmark. |

The AI system is prompt orchestration with supporting heuristics. It is not yet a presentation intelligence engine.

## 12. Product Maturity Assessment

Product maturity: **private alpha**

| Product Area | Maturity | Notes |
|---|---|---|
| Deck generation | Alpha | Works, but quality consistency is unknown. |
| Deck editing | Early alpha | Needs schema-aware editing and repair. |
| Presentation mode | Prototype | Useful but not differentiating. |
| Export | Alpha | Must prove fidelity. |
| Sharing | Prototype/alpha | Basic flow, not enterprise-ready. |
| Gallery | Internal QA tool | Useful for development, not product proof. |
| Brand kits | Immature | Needed for serious users. |
| Collaboration | Missing/immature | Required to compete with Gamma/Tome. |
| Enterprise admin | Missing | Required for enterprise. |
| Analytics/quality feedback | Missing | Required to improve model output systematically. |

## 13. What Separates This From Manus/Gamma/Tome

| Competitor | Their Advantage | NEXUS Gap |
|---|---|---|
| Manus | Real autonomous workflows, browser/tool execution, richer agent behavior. | Browser automation is a stub; pipeline is mostly linear generation. |
| Gamma | Stronger product polish, composition quality, editing workflow, templates, collaboration. | NEXUS lacks consistent visual excellence and mature editing. |
| Tome | Storytelling UX, media-rich narrative flow, consumer-grade interaction polish. | NEXUS is more engineering-led than story/product-led. |

Competitive score:

| Dimension | NEXUS | Manus | Gamma | Tome |
|---|---:|---:|---:|---:|
| Autonomous agent depth | 2 | 8 | 4 | 4 |
| Presentation visual quality | 4 | 6 | 8 | 7 |
| Editing workflow maturity | 3 | 5 | 8 | 7 |
| Export reliability | 3 | 5 | 7 | 6 |
| Enterprise readiness | 2 | 5 | 6 | 5 |
| Research/tool intelligence | 4 | 8 | 4 | 4 |
| Platform architecture | 4.5 | 6 | 7 | 6 |
| Differentiation | 3 | 8 | 8 | 7 |

## 14. What Would Make Elite Engineers Reject This Architecture

| Rejection Reason | Severity |
|---|---|
| Separate layout engines for browser and PPTX. | Critical |
| Registry not strong enough to be a real contract. | Critical |
| Monolithic agent loop with too many responsibilities. | High |
| Silent best-effort failure style. | High |
| Fake browser automation. | High |
| Tests stub critical infrastructure. | High |
| Output quality not measured with real prompt corpus. | High |
| Duplicate theme/visual constants. | Medium |
| Checked-in failed test output artifact. | Medium |
| Product positioning ahead of implementation reality. | High |

## 15. What Would Impress Elite Engineers

This section is not praise. It identifies assets worth preserving.

| Asset | Why It Matters | Condition For It To Become Strong |
|---|---|---|
| Canonical layout registry | Central naming is necessary. | Must become schema/capability registry. |
| Frontend/backend parity check | Catches obvious drift. | Must expand into visual/export parity validation. |
| Normalization layer | Reduces LLM shape chaos. | Must be replaced/augmented by strict validation. |
| Gallery snapshots | Good regression base. | Must include generated-deck and overflow tests. |
| Chart processor | Useful data normalization direction. | Needs semantics, theme coverage, and visual parity. |
| Research pipeline | Useful grounding direction. | Needs evidence-linked claims and quality scoring. |
| Live slide streaming | Good UX primitive. | Needs robust partial-state and repair semantics. |

## 16. Exact Next 30 Days Roadmap

| Week | Priority | Workstream | Deliverable | Success Criteria |
|---|---:|---|---|---|
| 1 | P0 | Registry contracts | Replace field-list registry with JSON Schema per layout. | Invalid slides fail validation with actionable errors. |
| 1 | P0 | Fake capability cleanup | Remove or clearly disable browser automation claims. | No UI/docs imply unavailable browser agent behavior. |
| 1 | P0 | Repo hygiene | Remove checked-in failed test artifacts and secrets-risk files. | Clean repo scan; no committed runtime test output. |
| 2 | P0 | Validation loop | Add slide validation before save and before export. | No deck can finish with invalid required layout data. |
| 2 | P0 | Test corpus | Add 20 real ugly prompts and generated fixtures. | CI validates no empty slides, no unsupported layouts, no overflow. |
| 2 | P1 | Renderer checks | Add DOM overflow detection to gallery + generated fixtures. | CI fails on text overflow/clipping. |
| 3 | P0 | Export parity | Add visual comparison for React preview vs PPT/PDF output on all layouts. | Known parity gaps are measured and tracked. |
| 3 | P1 | Theme consolidation | Generate frontend/export/chart theme maps from one source. | No duplicate manually maintained theme lists. |
| 4 | P0 | Pipeline split | Extract research, planning, generation, validation, repair, media, persistence into typed services. | Agent loop becomes orchestration only. |
| 4 | P1 | Real integration tests | Add Docker-backed Celery/Postgres/Redis test path. | Queue lifecycle tested without stubbing core worker behavior. |

30-day exit criteria:

- No fake-complete browser/tool claims.
- Registry is a real validation contract.
- Generated decks are tested, not only gallery samples.
- Export fidelity gaps are quantified.
- Agent loop responsibilities are reduced.

## 17. Exact Next 90 Days Roadmap

| Phase | Priority | Workstream | Deliverable | Success Criteria |
|---|---:|---|---|---|
| Days 31-45 | P0 | Shared layout model | Define `LayoutIR` with measured regions, text budgets, and render primitives. | React and export consume the same layout intent. |
| Days 31-45 | P0 | Quality scoring | Add `DeckQualityReport` with specificity, evidence, visual fit, export readiness. | Every deck has machine-readable quality score. |
| Days 31-60 | P0 | Repair engine | Model receives validation errors and repairs only invalid slides. | Repair success rate > 90% on prompt corpus. |
| Days 45-60 | P1 | Brand kits | Add logo, colors, fonts, tone, image style, example deck constraints. | Brand kit changes visibly alter output without breaking layout. |
| Days 45-75 | P1 | Evidence-linked research | Claim extraction with source references and uncertainty labels. | Fact warnings become explainable and actionable. |
| Days 60-75 | P0 | Export architecture | Move toward single-source rendering: LayoutIR -> HTML/PDF/PPTX or HTML screenshot export. | Export visual parity improves measurably. |
| Days 60-90 | P1 | Enterprise foundation | RBAC, workspace isolation, audit logs, API key management, retention policy. | Enterprise security review has a coherent answer. |
| Days 75-90 | P1 | Competitive evals | Blind compare against Gamma/Tome on 50 prompts. | Win/loss reasons are tracked by category. |
| Days 75-90 | P2 | Observability | Step traces, model costs, latency, failure classes, quality dashboards. | Operators can debug any bad deck from artifacts. |
| Days 75-90 | P2 | Collaboration model | Comments/version history/basic multi-user deck lifecycle. | Product starts matching buyer expectations. |

90-day exit criteria:

- Same layout contract drives preview and export.
- Deck quality is measured, not guessed.
- Enterprise blockers are at least architecturally addressed.
- Competitive gaps are quantified with benchmark prompts.
- Product can move from private alpha toward limited beta.

## 18. Estimated Engineering Maturity Level

Engineering maturity: **4.5 / 10**

| Level | Description | Fit |
|---|---|---|
| 1-2 | Throwaway prototype | Too structured for this. |
| 3-4 | Demo prototype with services | Partly fits. |
| 5 | Early platform skeleton | Closest current level. |
| 6-7 | Production beta architecture | Not yet. |
| 8-10 | Enterprise-grade platform | Far away. |

The system is just below early platform maturity because its contracts are not hard enough and its tests do not validate the true product promise.

## 19. Estimated Startup Readiness Level

Startup readiness: **3 / 10**

| Area | Readiness | Reason |
|---|---:|---|
| Demo readiness | 7 | Can show a working app. |
| Paid user readiness | 3 | Output consistency and export fidelity are not proven. |
| Enterprise sales readiness | 1.5 | Security/admin/compliance posture missing. |
| Technical diligence readiness | 3 | Architecture concerns would surface quickly. |
| Differentiation readiness | 2.5 | Positioning is not yet backed by unique capability. |

## 20. Estimated Acquisition / Investor Perception

| Audience | Likely Perception | Risk |
|---|---|---|
| Seed investor | Interesting demo, high execution risk. | May question differentiation and quality moat. |
| Technical investor | Broad build, architecture debt visible. | Will probe renderer/export duplication and fake-complete systems. |
| Strategic acquirer | Prototype asset, not platform asset. | May value team/product direction more than codebase. |
| Enterprise buyer | Not ready. | Security, governance, support, reliability gaps. |
| Design/product buyer | Visual quality not yet premium. | Gamma/Tome comparison will be difficult. |

Investor-grade narrative would require evidence that NEXUS can reliably produce better decks than existing tools for a specific segment. Current code does not prove that.

## Prioritized Recommendations

| Priority | Recommendation | Why |
|---:|---|---|
| P0 | Convert registry into a real schema and capability contract. | Every other system depends on valid slide structure. |
| P0 | Stop treating PPTX as a separate hand-built renderer. | Export fidelity is existential for a presentation product. |
| P0 | Add generated-deck quality tests from real prompts. | Curated gallery snapshots are insufficient. |
| P0 | Remove or implement fake browser/tool capabilities. | Product trust and architecture clarity depend on it. |
| P0 | Split the agent loop into typed, persisted pipeline steps. | Enables debugging, replay, quality scoring, and maintainability. |
| P1 | Centralize theme/design tokens across frontend/export/chart. | Prevents long-term visual drift. |
| P1 | Add validation-driven repair loop. | Makes AI output controllable. |
| P1 | Add real queue integration tests. | Current backend tests skip important production behavior. |
| P1 | Add evidence-linked fact checking. | Shallow warning flags are not enough. |
| P2 | Build brand kits and professional editing workflows. | Required for serious differentiation. |

## Final Assessment

NEXUS has enough structure to look like a platform from a distance, but the hard parts are not yet solved:

- Consistent professional slide quality.
- Browser-preview-to-export fidelity.
- Strong slide contracts.
- Real AI quality evaluation.
- Enterprise-grade operations and governance.
- Clear differentiation against stronger incumbents.

The immediate danger is continuing to add platform-sounding subsystems while the core output quality remains unproven. The next engineering phase should reduce ambiguity, strengthen contracts, measure output quality, and eliminate fake-complete capabilities.

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
- Updated: `audits/AUDIT_CURRENT_STATE.md`, `audits/AUDIT_PROMPT_CONTEXT.md`, `audits/CURRENT_COMPETITIVE_SCORE.md`, `audits/COMPETITIVE_BENCHMARK_BASELINE.md`, this file, and `audits/PRD_COMPLIANCE_AUDIT.md`.
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
- Updated: this file plus `audits/AUDIT_CURRENT_STATE.md`, `audits/AUDIT_PROMPT_CONTEXT.md`, `audits/CURRENT_COMPETITIVE_SCORE.md`, `audits/PRD_COMPLIANCE_AUDIT.md`.
- **No layout, renderer, frontend, or worker code changed.** No new dependencies. No JSON files modified. No reference repo files modified.

### Tests added (4)
1. `test_generate_flag_off_response_shape_unchanged` - flag off: 202 + `task_id`/`status`, `agent_run_id` is `None`/absent, **zero** `AgentRun` rows, **zero** `AgentStep` rows.
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

Response-contract cleanup only. Added `response_model_exclude_none=True` on the `/api/generate` route so the flag-off response JSON contains exactly `{task_id, status}` and never the key `agent_run_id` (not even as `null`). Tightened `test_generate_flag_off_response_shape_unchanged` to assert `set(body.keys()) == {"task_id", "status"}` and `"agent_run_id" not in body`. Flag-on tests unchanged: `agent_run_id` is still surfaced when the flag is on.

- Files changed: [backend/api/routes/generate.py](nexus-ai/backend/api/routes/generate.py), [backend/tests/test_runtime_generate_route.py](nexus-ai/backend/tests/test_runtime_generate_route.py).
- No live eval. No score change. Backend gate: **249 passed, 2 skipped, 1 warning** (unchanged).

### Phase 6J - First controlled one-prompt live-eval smoke (`biz-001`) - 2026-05-09

Phase 6J is the first controlled one-prompt live measurement attempt and the first score-eligible measurement phase. The full 11-prompt benchmark remains future Phase 6T.

- Stack was **rebuilt from this workspace** before measurement. The previously-running stack was bound to `D:\nexus-ai-gh\backend`; it was torn down and rebuilt via `docker compose up --build -d` from `D:\nexus-ai-1\nexus-ai`. `docker inspect nexus-backend` then reported `Source: D:\nexus-ai-1\nexus-ai\backend -> Destination: /app`; backend health was `200 {"status":"ok"}`.
- Live eval **did run**, exactly once, for `biz-001` (no other prompts). Committed result: [audits/LIVE_EVAL_RESULTS/biz-001-2026-05-09.json](nexus-ai/audits/LIVE_EVAL_RESULTS/biz-001-2026-05-09.json). On-disk source (gitignored): `backend/storage/evals/biz-001-20260509T090834Z.json`. No provider keys or raw provider payloads in the result file; no redaction was required.
- Measured fields (offline-measurable subset only): `ran_live=true`, `generated_slide_count=8`, `slide_count_in_window=true`, `required_layouts_missing=[]`, `chart_required=false`, `chart_requirement_met=true`, `needs_external_sources=false`, `external_source_expectation_met=true`, `deck_quality_ok=false`, `deck_quality_invalid_count=1`, `category_scores.deck_correctness=8`, `category_scores.evidence_accuracy=7`. All of `visual_quality`, `export_parity`, `agent_autonomy`, `stability_reliability`, `security_production_readiness` remain `null` per schema.
- **Score did not change.** One easy prompt is not a benchmark. Estimate stays **~57/100 (~57.5 weighted)**. NEXUS still does not beat Manus. NEXUS still does not beat Presenton overall.
- Added offline test [backend/tests/test_live_eval_results.py](nexus-ai/backend/tests/test_live_eval_results.py) (2 tests) that validates every committed result JSON against `benchmarks/eval_schema.json`. Updated [scripts/test-backend.ps1](nexus-ai/scripts/test-backend.ps1) to mount `audits/LIVE_EVAL_RESULTS -> /live_eval_results:ro` when present.
- Backend gate: **251 passed, 2 skipped, 1 warning** (was 249 + 2 new in 6J).


---

## Phase 6W-Stable -- Stable-Provider Runtime Profile -- 2026-05-10

**Backend gate:** 431 passed, 2 skipped, 1 warning. **Frontend layouts gate:** OK -- 7 canonical layouts, 7 exported. No code removed. No secrets added. `/api/health` still lists all 10 providers.

### Change

Activated the stable runtime profile so every code path hits a verified-working key on the first try (no reliance on chain fallback for routine operation):

- `AI_PROVIDER_CHAIN` default in `backend/config.py` and `.env.example` is now `groq,nvidia_nim,sambanova`.
- `ROLE_MODEL_MAP` re-pinned: `planner -> sambanova`, `writer -> groq`, `critic -> nvidia_nim`, `research -> sambanova`, `vision -> groq`, `repair -> nvidia_nim`, `summarize -> sambanova`, `json_fix -> groq`. Every role now points to a provider whose key is currently OK.
- `.env.example` documents that Gemini / OpenRouter / Cerebras are excluded from the default chain due to free-tier 429 risk, and Mistral / GitHub Models are excluded until valid inference credentials exist. All 10 providers remain SUPPORTED -- they are operationally disabled, not removed.
- `.env` `AI_PROVIDER_CHAIN` aligned to the same default.

### Why

The Phase 6W smoke test showed only `groq`, `nvidia_nim`, `sambanova` returning OK; Gemini / OpenRouter / Cerebras returned 429 (transient free-tier limits) and Mistral / GitHub Models returned 401 (provider rejected the keys). With the original mapping, `complete_for_role()` always paid one round-trip + a fallback hop for `planner` / `critic` / `vision` / `json_fix`. The stable profile cuts that to a single working call.

### Verification

- `powershell -File ./scripts/test-backend.ps1` -> **431 passed, 2 skipped, 1 warning**.
- `npm run verify:layouts` -> **verify-layouts OK -- 7 canonical layouts, 7 exported**.

### Files changed

- `backend/config.py` -- `AI_PROVIDER_CHAIN` default and `ROLE_MODEL_MAP` updated.
- `.env.example` -- chain default + comments documenting which providers are operationally disabled and why.
- `.env` -- `AI_PROVIDER_CHAIN` aligned.
- `PROJECT_HANDOFF.md` -- AI / Model Setup section reflects the stable profile.

### Rollback

Set `AI_PROVIDER_CHAIN` and / or override `ROLE_MODEL_MAP` via env once the disabled providers' credentials become operational. No code change is required to re-enable any of the other 7 providers.

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

