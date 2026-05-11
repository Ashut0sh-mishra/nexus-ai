# NEXUS AI — Competitive Benchmark Baseline

**Date:** 2026-05-09 (Phase 6B + 6B-Fix + 6C + 6D + 6E + 6F + 6G)
**Status:** Baseline + offline harness + wired adapter + runbook + Presenton reference benchmark. **No live LLM accuracy measurement has been run yet.** Phase 6G added Presenton ([manus-need/presenton](nexus-ai/manus-need/presenton/README.md)) as a presentation-product reference and recorded honest gaps; no NEXUS code changed and no scores moved up.
**Gate:** Verified via `.\scripts\test-backend.ps1` → 245 passed, 2 skipped, 1 warning. The script mounts `benchmarks/` at `/benchmarks` (read-only).
**Source of truth pointer:** `AUDIT_CURRENT_STATE.md` for what is currently verified by tests.
**Phase 6E adapter:** `backend/scripts/run_live_eval.py` now drives the real `/api/generate` → `/api/slides/{task_id}` round-trip (opt-in via `NEXUS_RUN_LIVE_EVAL=true`; not part of the test gate).

This document defines how NEXUS AI will be measured against Manus and the open-source agent references in `manus-need/` (browser-use, OpenManus, AgenticSeek), plus presentation-product references (Gamma, Tome, **Presenton**). It is paired with two machine-readable artifacts:

- [benchmarks/rubric.json](nexus-ai/benchmarks/rubric.json) — weighted scoring rubric (sums to 100).
- [benchmarks/prompts.json](nexus-ai/benchmarks/prompts.json) — 11 realistic deck prompts with expected evaluation criteria.

Integrity tests live at [backend/tests/test_competitive_benchmark.py](nexus-ai/backend/tests/test_competitive_benchmark.py). They verify the fixtures are well-formed and consistent with the audit's open-risk categories. They do **not** call any LLM and do **not** evaluate generation quality.

---

## Honest Disclaimer

NEXUS is **not yet benchmarked against Manus**. The "current NEXUS score" values below are best-guess estimates based on the existing offline test suite, audit history, and code review. They are **not** measured live-eval results. Once a live evaluation harness is built (out of scope for Phase 6B), those numbers must be replaced with measured values.

Do not cite these scores externally as proof of competitive parity.

---

## Competitor Set

| ID | Label | Kind | Why included |
| --- | --- | --- | --- |
| `manus` | Manus (target) | target | Primary competitive target — agent + deck quality. |
| `browser_use` | browser-use | open_source_reference | Browser-tool autonomy and DOM-action accuracy. |
| `openmanus` | OpenManus | open_source_reference | Tool-calling agent loop architecture. |
| `agenticseek` | AgenticSeek | open_source_reference | Retrieval / evidence-grounded reasoning. |
| `gamma_tome` | Gamma / Tome | presentation_tool_reference | Visual quality, layout breadth, export polish. |
| `presenton` | Presenton | presentation_tool_reference | Open-source (Apache 2.0) FastAPI + Next.js + Electron presentation generator. Reference for: BYOK provider breadth, async-with-status + SSE slide streaming, PPTX/PDF ingestion, MCP server, and backend test depth. |

---

## Phase 6G — Presenton Reference Comparison

**Phase 6G** adds [Presenton](nexus-ai/manus-need/presenton/README.md) as a *presentation-product* reference distinct from the agent references (browser-use / OpenManus / AgenticSeek) and from Gamma/Tome (closed-source SaaS). Presenton is open-source, locally-runnable, BYOK across multiple LLM providers, ships an Electron desktop binary, and exposes a far broader API than NEXUS today.

**This phase did not change any NEXUS code, did not run live eval, and did not move any score up.** Score remains an estimate at ~57/100.

All claims below are cited to files inside the in-repo Presenton snapshot at `manus-need/presenton/`.

### Per-category comparison: NEXUS today vs. Presenton today

| Area | NEXUS (this workspace) | Presenton (`manus-need/presenton/`) | Honest gap |
| --- | --- | --- | --- |
| **Generation API maturity** | Single async path: `POST /api/generate` + `GET /api/slides/{task_id}` polling. No SSE, no webhooks, no `derive`/`prepare`/`edit` endpoints. | Full surface: `create`, `prepare`, `generate` (sync), `generate/async` + `status/{id}`, **SSE `stream/{id}`** (slide-by-slide events), `edit`, `derive`, `update`, plus webhook callbacks. ([servers/fastapi/api/v1/ppt/endpoints/presentation.py](nexus-ai/manus-need/presenton/servers/fastapi/api/v1/ppt/endpoints/presentation.py)) | NEXUS is significantly thinner. No SSE, no webhooks, no derive/edit/prepare endpoints. |
| **Async status / progress** | Task status via DB polling on `/api/slides/{task_id}` (`pending` / `done` / `failed`). No structured progress messages. | Stage-by-stage progress: "Generating outlines" → "Selecting layout" → "Generating slides" → "Fetching assets" → "Exporting" → `completed`, plus `WebhookEvent`. | NEXUS does not expose stage progress to the client. |
| **Template / theme system** | 7 canonical layouts pinned in registry ([backend/agent/layouts.registry.json](nexus-ai/backend/agent/layouts.registry.json)); themes hardcoded in renderer. No template CRUD endpoints. No AI-from-PPTX template generation. | Template CRUD endpoints + job-based async **PPTX → React layout** generation ([servers/fastapi/templates/router.py](nexus-ai/manus-need/presenton/servers/fastapi/templates/router.py), [servers/fastapi/templates/slide_layout_jobs.py](nexus-ai/manus-need/presenton/servers/fastapi/templates/slide_layout_jobs.py)). 4 default templates (`general`, `modern`, `standard`, `swift`) plus user templates. | NEXUS has no template authoring/marketplace surface and no PPTX-driven template extraction. |
| **Export pipeline** | Server-side python-pptx renderer in [export_service.py](nexus-ai/backend/services/export_service.py); separate from web renderer. PPTX content parity tested for all 7 layouts (Phase 6C). PDF smoke only. | Single-source export: Puppeteer renders the same Next.js `/pdf-maker` preview to PDF/PPTX via the `presentation-export` package ([servers/fastapi/utils/export_utils.py](nexus-ai/manus-need/presenton/servers/fastapi/utils/export_utils.py)). Same source as preview. | Presenton's design avoids the dual-renderer drift NEXUS still has. NEXUS's content-parity tests mitigate but do not eliminate this risk. |
| **PPTX / PDF ingestion** | **None.** No upload, no parse, no import. | `POST /api/v1/ppt/pptx-slides/process` ([pptx_slides.py](nexus-ai/manus-need/presenton/servers/fastapi/api/v1/ppt/endpoints/pptx_slides.py)) extracts slides + fonts + screenshots; `POST /api/v1/ppt/pdf-slides/process` ([pdf_slides.py](nexus-ai/manus-need/presenton/servers/fastapi/api/v1/ppt/endpoints/pdf_slides.py)) converts PDF pages to PNG via ImageMagick. 100 MB caps. | **Hard NEXUS gap.** No PPTX or PDF ingestion exists at all. |
| **Provider support / BYOK / local models** | Configured via `.env`; default Groq (`llama-3.3-70b-versatile`); Anthropic and OpenAI used in code. No first-class Ollama path. No provider-switch UI. | First-class BYOK: OpenAI, Anthropic, Google Gemini, Vertex AI, Azure OpenAI, **Ollama (local)**, ChatGPT OAuth login, custom OpenAI-compatible providers. ([README.md](nexus-ai/manus-need/presenton/README.md)) | NEXUS does not offer Ollama / fully-offline operation, and provider support is narrower. |
| **MCP / API surface** | None. Internal `/api/agent/test-run` Bearer-JWT route is not MCP. | FastMCP-generated MCP server at `127.0.0.1:8001` ([servers/fastapi/mcp_server.py](nexus-ai/manus-need/presenton/servers/fastapi/mcp_server.py)) auto-derived from OpenAPI; exposes the full presentation/template/slide/image/font/upload surface as MCP tools. | NEXUS has no MCP integration surface. |
| **Test coverage** | **245 passed, 2 skipped, 1 warning** (Phase 6E gate). 17 benchmark integrity tests; 30 offline live-eval tests; 15 PPTX content-parity tests. **0 live-LLM tests executed.** | ~24 test files / ~100 test functions across `unit/`, `integration/`, `edge_cases/`, `regression/` with **schema-snapshot regression for HTML output and outline structure** ([servers/fastapi/tests/](nexus-ai/manus-need/presenton/servers/fastapi/tests/)). Cypress config present. | NEXUS test count is comparable; Presenton has snapshot regression NEXUS lacks; neither has pixel-diff visual regression. |
| **Visual quality posture** | No screenshot diff suite; renderer present for 7 layouts; `VISUAL_QUALITY_AUDIT.md` is honest about premium-feel gap. | No pixel-diff visual regression detected (searches for `playwright`, `screenshot`, `pixel` returned no visual-diff suite). Has Cypress config and HTML schema snapshots, but **schema** snapshots, not pixel snapshots. | **Both are equally short** on pixel-level visual regression. Neither system can claim measured visual parity to Gamma/Tome. |
| **Distribution** | Web app behind Docker Compose (FastAPI + Celery + Redis + Postgres + Vite SPA). | Web (Next.js + FastAPI in Docker) **plus Electron desktop binary** for Win/macOS/Linux ([electron/package.json](nexus-ai/manus-need/presenton/electron/package.json)) bundling Puppeteer + PyInstaller-packaged FastAPI. | NEXUS has no native desktop distribution path. |

### What this comparison does *not* prove

- It does **not** prove Presenton produces better decks than NEXUS. No live deck-quality measurement has been run on either side; this is a feature/surface comparison only.
- It does **not** prove NEXUS is worse end-to-end — NEXUS's authenticated `AgentRuntime` (Phase 6A), 7-layout schema validator, deck-quality report, repair preview, and source-grounding pipeline have no Presenton equivalent.
- It does **not** justify any score movement until live AI-accuracy or pixel-visual-parity measurements exist on both sides under the same prompts.

### How this changes the rubric

- The competitor list now includes `presenton` (added to `benchmarks/rubric.json`).
- The integrity test `test_rubric_lists_required_competitors` continues to pass (it asserts a *subset*, not equality).
- **No category weight changed. No NEXUS score changed.** Estimated weighted total remains **~57.5 / 100**.

### Honest verdict

Presenton is a *more mature presentation-product surface* than NEXUS today on import, async/SSE, MCP, BYOK breadth, and distribution. NEXUS has comparable backend-test depth and a stronger explicit story for deck-quality reporting and source grounding, but is narrower on user-facing surface area. **NEXUS does not beat Presenton, and NEXUS does not beat Manus.**


## Categories and Baseline

Scores are 1–10. Weighted total = sum(weight × score) / 10. Maximum weighted total = 100.

### 1. Deck generation correctness (weight 20)
- **Current NEXUS score (estimate):** **7**
- **Target score:** 9
- **Evidence we have:** `test_layout_coverage` 7/7, `test_slide_schema`, `test_deck_quality`, `test_api_deck_quality_payload`, `test_deck_repair_preview`, `test_phase4_attach_sources` all green; `npm run verify:layouts` 7/7.
- **Evidence missing:** No live-generation accuracy eval; layout breadth limited to 7 (Gamma/Tome use many more); no automated regression on real LLM outputs.
- **What test would prove improvement:** A live-eval harness that runs the 11 corpus prompts through `/api/generate`, checks `expected_visual.required_layouts ⊆ produced_layouts`, and asserts deck_quality score ≥ 0.8.

### 2. Visual quality (weight 15)
- **Current NEXUS score (estimate):** **5**
- **Target score:** 8
- **Evidence we have:** `VISUAL_QUALITY_AUDIT.md` review; renderer present for 7 layouts.
- **Evidence missing:** No screenshot diff suite; no Playwright-driven visual regression; typography/spacing not measured.
- **What test would prove improvement:** Pixel-diff snapshots per layout per breakpoint, with a tolerated delta budget; comparative side-by-side renders against Gamma/Tome on the same brief.

### 3. Export parity (weight 15)
- **Current NEXUS score (estimate):** **6** (raised from 4 by Phase 6C)
- **Target score:** 8
- **Evidence we have:** `test_export_input_parity` passes (input shape parity); **Phase 6C `test_export_parity` (15 tests) verifies PPTX textual content parity for all 7 canonical layouts** — title/body/bullets/columns/quote/attribution/stats-values-and-labels/chart-categories-and-series/closing-CTA all preserved on round-trip; deterministic; unknown-layout safe; empty-chart safe; on-disk reopen smoke; PDF export is smoke-tested only.
- **Evidence missing:** No pixel-level visual diff for PPTX; no renderer↔PDF contract; PDF visual parity unmeasured (skipped when WeasyPrint unavailable).
- **What test would prove improvement:** A pixel-diff snapshot test that renders each canonical layout in both the web renderer and PPTX/PDF and asserts a tolerated delta budget; or LibreOffice-headless PPTX→PNG capture compared against Playwright web screenshots.

### 4. Evidence / citation accuracy (weight 15)
- **Current NEXUS score (estimate):** **5**
- **Target score:** 9
- **Evidence we have:** `test_source_grounding`, `test_phase4_attach_sources` green; deck-level/slide-level sources persist; `SourceEvidencePanel` mounted.
- **Evidence missing:** Claim-level citation mapping; on-slide visual citations; hard fact-checking; live source-fact-check eval.
- **What test would prove improvement:** Claim→source mapping with a labeled gold corpus; precision/recall ≥ 0.85.

### 5. Agent / tool autonomy (weight 15)
- **Current NEXUS score (estimate):** **5**
- **Target score:** 8
- **Evidence we have:** `AgentRuntime` exists and is authenticated (Phase 6A); `test_agent_runtime`, `test_agent_route`, `test_browser_service`, `test_browser_service_live` green; runtime is opt-in.
- **Evidence missing:** Runtime does not drive `/api/generate`; no head-to-head browser-use comparison; no measured browse-task success rate; no SSE streaming.
- **What test would prove improvement:** Live runtime evaluation on the `agent_autonomy` and `evidence_heavy` prompts with a measured task-success rate ≥ 70%.

### 6. Stability / reliability (weight 10)
- **Current NEXUS score (estimate):** **7**
- **Target score:** 9
- **Evidence we have:** Backend pytest **182 passed, 2 skipped** (latest Copilot run after Phase 6A); migrations `0001_initial → 0002_agent_runtime` reversible; Alembic verified end-to-end on disk.
- **Evidence missing:** No 3-run flake check; no load test; no chaos test on browser/runtime path.
- **What test would prove improvement:** CI runs default pytest 3× consecutively with zero flakes; `alembic downgrade -1; alembic upgrade head` is part of CI.

### 7. Security / production readiness (weight 10)
- **Current NEXUS score (estimate):** **5**
- **Target score:** 8
- **Evidence we have:** Bearer JWT on `/api/agent/test-run` (Phase 6A); auth tests in `test_agent_route`.
- **Evidence missing:** No rate limits, no per-user quotas, no SSE step streaming, no audit logging on the runtime route, no secrets-rotation policy.
- **What test would prove improvement:** Rate-limit middleware + tests; per-user quota enforcement test; audit-log row-creation test on every runtime call.

---

## Estimated Weighted Baseline

| Category | Weight | Current (est.) | Weighted |
| --- | ---: | ---: | ---: |
| Deck correctness | 20 | 7 | 14.0 |
| Visual quality | 15 | 5 | 7.5 |
| Export parity | 15 | 6 | 9.0 |
| Evidence accuracy | 15 | 5 | 7.5 |
| Agent autonomy | 15 | 5 | 7.5 |
| Stability / reliability | 10 | 7 | 7.0 |
| Security / production readiness | 10 | 5 | 5.0 |
| **Total** | **100** | — | **57.5 / 100** |

This is an **estimate**, not a measurement. The real number can only be set by running the rubric against live outputs.

---

## How to use this baseline

1. When a phase closes a risk in one of these categories, update the score in [CURRENT_COMPETITIVE_SCORE.md](nexus-ai/audits/CURRENT_COMPETITIVE_SCORE.md) and re-run `pytest backend/tests/test_competitive_benchmark.py` to confirm fixtures still validate.
2. When a live-eval harness is added, replace the "estimate" column with a "measured" column.
3. Do not change category weights without a paired audit entry explaining why.

---

## Phase 6H - Reference Intelligence Blueprint - 2026-05-09

Phase 6H is audit/roadmap only. **No NEXUS code changed. No new measurement.** The full per-reference comparison, gap matrix, target architecture, and next-12-phase roadmap moved into [audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md](nexus-ai/audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md), which is now the master implementation roadmap.

- All references in this baseline file remain accurate; the 6H blueprint extends rather than replaces them.
- Competitive score remains an estimate at ~57/100 (~57.5 weighted). NEXUS does not beat Manus. Presenton still leads on user-facing presentation-product surface area.
- Phase 6J ran a **single-prompt** live-eval smoke for `biz-001` (result at [audits/LIVE_EVAL_RESULTS/biz-001-2026-05-09.json](nexus-ai/audits/LIVE_EVAL_RESULTS/biz-001-2026-05-09.json); offline-measurable scores: `deck_correctness=8`, `evidence_accuracy=7`; `deck_quality_ok=false`, `deck_quality_invalid_count=1`). One prompt is not a benchmark - the full 11-prompt run remains future Phase 6T. Headline score unchanged.
- Future score changes must cite a measurement file under `audits/LIVE_EVAL_RESULTS/`, a visual-diff result, a citation precision/recall report, or an export-parity test result. Surface-area parity alone does not move the score.

