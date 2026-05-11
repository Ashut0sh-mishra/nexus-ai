# NEXUS Live-Eval Runbook (Phase 6F)

**Date:** 2026-05-09
**Phase context:** Phase 6E wired the opt-in adapter at `backend/scripts/run_live_eval.py`. This runbook is the manual procedure to execute the **first** controlled live evaluation.

> **WARNING — paid providers.** Running live eval invokes the real `/api/generate` flow. Depending on configuration this may call paid LLM providers (Groq / OpenAI / Anthropic) and/or paid web-search providers (Tavily). Cost is the operator's responsibility. **Do not run this in CI.**

> **WARNING — not a measurement of the current workspace by default.** As of 2026-05-09 the running `nexus-backend` container in dev was observed bound to `D:\nexus-ai-gh\backend`, not this workspace. A live-eval run against that stack would NOT reflect Phase 6A–6E code. Always confirm the host mount before running.

---

## 1. Prerequisites

- Docker Desktop running.
- This workspace at `D:\nexus-ai-1\nexus-ai`.
- `.env` populated with at least:
  - `LLM_API_KEY` (Groq is the default per `docker-compose.yml`).
  - Database / Redis defaults are fine.
  - Optional: `SERPAPI_API_KEY` / `TAVILY_API_KEY` if `--search-web` is used.
- The local image `nexus-ai-backend:dev` exists (built by `scripts/test-backend.ps1` on first run).

---

## 2. Bring up the stack from THIS workspace

```powershell
cd D:\nexus-ai-1\nexus-ai
docker compose down
docker compose up --build -d
```

`down` stops the previous stack (including any container bound to a different workspace); `up --build` rebuilds against this workspace's `backend/` and mounts `./backend:/app`.

---

## 3. Confirm the backend is THIS workspace, not an old bound path

```powershell
# Mount source must point at THIS workspace's backend folder.
docker inspect nexus-backend |
    Select-String -Pattern '"Source"|"Destination"' |
    Select-Object -First 8
```

Expected:

```
"Source": "D:\\nexus-ai-1\\nexus-ai\\backend",
"Destination": "/app",
```

If `"Source"` reads anything else (e.g. `D:\nexus-ai-gh\backend`), **stop**. Run `docker compose down -v` from this workspace and `docker compose up --build -d` again.

Health check (host port 8080 → container 8000 per `docker-compose.yml`):

```powershell
Invoke-WebRequest -Uri http://localhost:8080/api/health -UseBasicParsing | Select-Object StatusCode,Content
```

Expected: `200` with a JSON body containing `"status":"ok"`.

---

## 4. Required environment variables

Set in the **PowerShell session that will launch the harness**:

```powershell
$env:NEXUS_RUN_LIVE_EVAL = "true"   # required; CLI refuses without this
# Optional override (defaults to backend/storage/evals/ inside the container):
# $env:NEXUS_EVAL_OUTPUT_DIR = "/app/storage/evals"
```

The CLI exits non-zero if `NEXUS_RUN_LIVE_EVAL` is not exactly `"true"`.

---

## 5. Run exactly one prompt: `biz-001`

`biz-001` is the lowest-risk corpus entry (internal Q1 sales update; `needs_external_sources=false`; no chart required; 5–8 slides). Run it first to validate the harness end-to-end:

```powershell
$env:NEXUS_RUN_LIVE_EVAL = "true"
.\scripts\run-live-eval.ps1 -PromptId biz-001 -BaseUrl http://localhost:8080
```

Notes:
- `scripts/run-live-eval.ps1` already wires the `benchmarks/` mount and forwards `NEXUS_RUN_LIVE_EVAL` into the container.
- Default timeout: 600s. Default poll interval: 3.0s. Override with `-PromptId biz-001` plus the args supported by `python -m scripts.run_live_eval --help`.
- **Do not run all prompts** at this stage. Validate one first.

---

## 6. Output location

Inside the container the harness writes one record per prompt to:

```
/app/storage/evals/<prompt_id>-<UTC-timestamp>.json
```

Because `./backend:/app` is bind-mounted, the file appears on the host at:

```
D:\nexus-ai-1\nexus-ai\backend\storage\evals\<prompt_id>-<UTC-timestamp>.json
```

This path is **gitignored** (via `backend/storage/` in `.gitignore`). Do not commit live result files.

---

## 7. How to interpret the result JSON

The shape is documented in `benchmarks/eval_schema.json`. Key fields to inspect after a `biz-001` run:

| Field | Expectation for biz-001 |
| --- | --- |
| `ran_live` | `true` |
| `fixture_label` | `null` |
| `generated_slide_count` | 5–8 |
| `slide_count_in_window` | `true` |
| `required_layouts_missing` | `[]` (i.e. title, bullets, stats, closing all present) |
| `chart_required` | `false` |
| `chart_requirement_met` | `true` |
| `needs_external_sources` | `false` |
| `external_source_expectation_met` | `true` |
| `deck_quality_ok` | `true` (if the schema validator was happy) |
| `category_scores.deck_correctness` | 1–10 (offline-measurable) |
| `category_scores.evidence_accuracy` | 1–10 |
| `category_scores.visual_quality` | `null` (requires screenshot diff) |
| `category_scores.export_parity` | `null` (per-prompt; covered globally by Phase 6C) |
| `category_scores.agent_autonomy` | `null` (requires runtime telemetry) |
| `notes` | human-readable; should mention any missing layouts and which categories are unmeasured |

Anything below 7 in `deck_correctness` for an easy prompt like `biz-001` is a regression signal.

---

## 8. Rollback / cleanup

```powershell
# Remove generated result files for the current run (host side):
Remove-Item D:\nexus-ai-1\nexus-ai\backend\storage\evals\*.json -Force

# Stop the stack:
docker compose down

# Optional: drop the eval-output volume (none is configured today; storage
# is bind-mounted) — nothing to remove beyond the files above.
```

The CLI itself writes nothing to the database and does not mutate user-facing state. The only persistent side-effect is the generated `Task` row produced by `/api/generate`, plus its `SlideDeck` row, which live in the dev Postgres instance and are routinely truncated by `docker compose down -v`.

---

## 9. After a successful single-prompt run

1. Inspect the JSON at `backend/storage/evals/<prompt_id>-<ts>.json`.
2. Append the file path and the offline-measurable scores (`deck_correctness`, `evidence_accuracy`) to `audits/CURRENT_COMPETITIVE_SCORE.md` under a new "Measured single-prompt run" section.
3. **Do not generalize** to all 11 prompts from one run. The competitive headline score remains an estimate until a full 11-prompt run is recorded.
4. **Do not claim NEXUS beats Manus.** A single passing offline-measurable prompt does not refute the existing honest gap.

---

## 10. Test gate is unaffected

The official backend gate (`.\scripts\test-backend.ps1`) does **not** run live eval. The CLI explicitly refuses without `NEXUS_RUN_LIVE_EVAL=true`, and the test gate does not set that variable. Live eval is opt-in operator-only.
