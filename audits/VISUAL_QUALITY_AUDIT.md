# Visual Quality Audit: NEXUS AI Presentation Platform

> **Reading note.** For current truth, read `AUDIT_CURRENT_STATE.md` first. This file contains historical phase notes and original audit findings. Older sections may be superseded. Do not treat old phase claims as current evidence without checking `AUDIT_CURRENT_STATE.md` and `AUDIT_READING_GUIDE.md`.

Date: 2026-05-08  
Scope: visual rendering quality and presentation design quality only  
Excluded: backend architecture, API design, infrastructure, AI pipeline internals

## Executive Visual Verdict

The current visual system is competent but not premium. It looks like a well-built SaaS slide renderer, not like a top-tier presentation product. The strongest layouts show clean hierarchy and useful business structure. The weakest layouts look templated, card-heavy, overly icon-driven, and too close to dashboard UI patterns.

The biggest visual issue is not that individual slides are broken. The bigger issue is that the system lacks art direction: cinematic framing, editorial restraint, deck-level pacing, emotional progression, and the composed confidence seen in Manus, Gamma, Pitch, Tome, Canva premium templates, or McKinsey/BCG-style consulting decks.

Overall visual quality: **4.4 / 10**  
Premium presentation feel: **3.8 / 10**  
Consulting-style quality: **4.5 / 10**  
Cinematic quality: **2.8 / 10**  
Stage-readiness: **3.8 / 10**

## Phase 5 — Frontend Evidence Visibility (`SourceEvidencePanel`) - 2026-05-09

### What Changed (visual surface only)
- New component `frontend/src/components/SourceEvidencePanel.jsx`. Same visual language as the existing `DeckQualityBadge`: a small pill that toggles a single bordered panel of monospaced rows. Uses existing tokens (`nexus-border`, `nexus-card`, `nexus-muted`, `nexus-dim`, `accent-purple`). No new colours, no new typography, no new card geometry.
- Pill label: `Sources · N slides · M sources`. Renders nothing if no slide carries `sources`.
- Expanded panel groups by slide and shows `slide N · layout · title`, then per-source `title / host / snippet (truncated to 200 chars)`. Caps at 24 slides and 6 sources per slide; the rest are summarised as "… and N more".
- Mounted in two places only:
  - `Generator.jsx`: below the existing `DeckQualityBadge` / `ExportButtons` row, only after `status === "done"`.
  - `SharedSlide.jsx`: below the carousel.
- The slide renderer, the 7 layout components, the chart, the carousel, the exports, the thumbnails, and the deck header are unchanged.
- `slideParser.js` now passes through `slide.sources` (previously stripped). This is a data-shape pass-through only; renderer doesn't consume it.

### Files Changed
- `frontend/src/components/SourceEvidencePanel.jsx` (new).
- `frontend/src/pages/Generator.jsx` (one mount).
- `frontend/src/pages/SharedSlide.jsx` (one mount).
- `frontend/src/utils/slideParser.js` (preserve `sources`).

### Tests Run
- `npm run verify:layouts` → ✔ 7 / 7. No frontend test framework introduced.
- No backend code changed; backend gate not re-run for this phase.

### Result
**Narrow pass.** A second user-visible affordance for evidence is now in place. It is read-only, opt-in (collapsed by default), and styled to match the existing dark UI. **No on-slide visual citation rendering** — sources still live outside the slide canvas. Visual scores above are unchanged.

### Remaining Risks
- **No claim-specific citation mapping.** A stats slide with 3 numbers and a list of sources still cannot prove which number came from which source.
- **No on-slide visual citations.** Sources are visible only in the panel; the slide renderer has no badge, footnote, or source pill yet.
- **No hard fact-checking.** A source listed against a slide does not validate the slide’s numbers — it only shows what was retrieved.
- **The panel is the only way to inspect sources.** A user who never expands it sees only a count.
- **The slideParser change is structural** but minimal; it forwards `sources` verbatim, so any future schema tightening on sources must happen at the API or in `attach_research_sources_to_deck`.

## Phase 4 — DeckQualityBadge source-warning surface - 2026-05-09

### What Changed (visual surface only)
- `DeckQualityBadge` pill label now appends `· N source warning(s)` when `deck_quality.source_warnings.length > 0`. Same pill geometry, same tone tokens (amber/emerald), no new icon.
- Expanded panel now contains a third optional section, `deck_quality.source_warnings`, listing `slide N · layout · code` rows (same monospaced row style used by `errors` / `repair_preview`, capped at 12).
- No layout component, no theme token, no slide renderer, no chart, no thumbnail, no export visual changed.

### Files Changed
- `frontend/src/components/DeckQualityBadge.jsx` (single file).

### Tests Run
- `npm run verify:layouts` → ✔ 7 / 7 (unchanged).
- No frontend test framework was introduced for this phase; the component remains small enough to inspect manually.

### Result
**Narrow pass.** The badge gains a small, additive textual surface for source warnings without redesigning anything. Visual scores above are unchanged because no slide-rendering surface was touched.

### Remaining Risks
- The badge is currently the **only** visible surface for source data. Slides themselves still have no on-canvas citation affordance.
- Long source-warning lists are hard-capped at 12 rows; the user is told there are "…and N more" but cannot scroll the rest.
- The badge sits in the deck header area; a user who never opens the panel only sees the count, not which slides are affected.

## Phase 1H Pre-Lock Triage Sweep (P1-1, P1-2, P0-2, P1-3) - 2026-05-09

### What Was Added (Visually)
- **P1-1.** `DeckQualityBadge` now renders on the `SharedSlide` page next to the public-preview chip. Same component, same Tailwind utilities, same 12-row cap, same expand/collapse interaction — no design-token decisions, no new colors, no new typography. The visual surface area added is exactly one badge.
- **P1-2.** Backend-only fix; no visual change *per se*. The user-visible effect is that decks where the only validation issue was the self-inflicted stats→chart safety-net case now show a green badge instead of an amber one. The badge component itself is unchanged.
- **P0-2 / P1-3.** Test and documentation only; no visual impact.

### Files Changed (visual surface)
- `frontend/src/pages/SharedSlide.jsx` (badge mounted; no styling work).
- No other frontend file touched.

### Tests Added
- None on the frontend (no test framework introduced; layout parity gate continues to pass).

### Tests Run
- `npm run verify:layouts` → ✔ 7 / 7.
- Backend Docker (default pytest) → 106 passed, 1 skipped.

### Result
Visual posture for Phase 1H — **Pass (narrow)**. The visual scorecard does not move. Sharing a deck and viewing it as a public visitor now produces the same quality-signal affordance the authoring page provided since Phase 1D.

### Remaining Visual Risks
- All P2 polish items remain open: amber/emerald tokens vs `accent-*`, long-path truncation w/ tooltip, premium typography, cinematic art direction, brand-aware theming, share-page hero polish, chart styling parity. None are lock-blocking.
- No frontend test framework yet; visual regressions are still gated only by registry parity.

## Phase 1G Pre-Lock P0-1 (Test Suite Unblock) - 2026-05-09

### Visual Impact
None. Phase 1G is a backend-only fix to `backend/database/connection.py` that makes SQLite-targeted `pytest` runs work without the `--noconftest` workaround. No renderer, design token, layout component, typography, spacing, motion, or visual-test file was touched.

### Files Changed
- `backend/database/connection.py` (no frontend / renderer / CSS files).

### Tests Run
- Default backend pytest: **103 passed, 1 skipped**.
- `npm run verify:layouts` → ✔ 7 / 7 (registry parity gate, not a visual test).
- No visual / Playwright / Storybook suite run; none required.

### Result for this Audit
**Not applicable / Pass-through.** Visual scores do not move. All visual concerns documented elsewhere in this audit remain open and unaffected.

### Remaining Visual Risks
Unchanged from Phase 1F. The strategic visual backlog (cinematic art direction, premium typography, art-directed hero composition, share-page polish, chart styling parity, brand-aware theming) is untouched.

## Phase 1F Repair Preview UI + Env Cleanup - 2026-05-09

### What Was Added
- Minimal UI surface for `deck_quality.repair_preview` inside the existing `DeckQualityBadge`. The pill, color logic, expand/collapse animation, panel container, padding, typography, and 12-row cap are all unchanged. The only visual delta is the panel's content: when `repair_preview` is present, each row becomes `slide N · layout · path · action[ → after]` (monospace, same `text-[11px] text-nexus-muted`). When `repair_preview` is empty, the panel falls back to the original errors rendering. No new icons, colors, fonts, or design tokens.
- Disk cleanup of two unused `.venv` directories has no visual impact.

### Files Changed
- `frontend/src/components/DeckQualityBadge.jsx` (presentation only).

### Tests Added
- None on the frontend (no test framework introduced; `verify:layouts` parity gate continues to pass).

### Tests Run
- `npm run verify:layouts` → ✔ 7 canonical, 7 exported.
- Backend Docker tests (data feeding the UI): 103 passed, 1 skipped.

### Result
Visual posture for Phase 1F — **Pass (narrow)**. UI surface area is intentionally tiny; the design system is unchanged. Broader visual-quality posture remains **Partial** pending the still-out-of-scope visual passes.

### Remaining Risks
- The `formatPreviewValue` helper renders an empty string as `""`, which is the most informative compact representation. If future safe-defaults grow longer strings, the row could wrap; the 12-row cap and `max-w-md` container keep the panel bounded.
- The `SharedSlide` page still does not display the badge — unchanged from Phase 1D and deliberately out of Phase 1F scope.

## Phase 1E Repair Preview - 2026-05-09

### What Was Added
- No visible UI change in Phase 1E. The repair preview is a *backend-only* extension of the `deck_quality` payload. The existing `DeckQualityBadge` is unchanged and continues to summarize valid/invalid counts and repair-needed counts; it ignores the new `repair_preview` array until a deliberate UI follow-up surfaces it.
- Visual system, theme tokens, layouts, slide rendering, and export rendering are all untouched.

### Files Changed
- None on the frontend.
- Backend additions only: see the architecture / PRD / final-system audits for the file list.

### Tests Added
- None on the frontend.

### Tests Run
- `npm run verify:layouts` → ✔ 7 canonical layouts, 7 exported (unchanged).
- Backend tests relevant to UI-consumed data: 103 passed, 1 skipped.

### Result
Visual posture for Phase 1E — **Pass (no-op)**. The visual surface is intentionally unchanged; the new data is available to the UI when a future phase chooses to display it.

### Remaining Risks
- A small UI follow-up could expose `deck_quality.repair_preview[*]` inside the existing badge's expandable panel (e.g., showing `slide_index · layout · path · "→" · after`). Deliberately out of Phase 1E scope.
- Broader visual-quality posture remains **Partial** pending the still-out-of-scope passes (slide-master polish, chart styling parity, share-page typography, hero polish).

## Phase 1D Deck Quality Visibility - 2026-05-09

### What Was Added
- Minimal UI visibility: a new `DeckQualityBadge` component appears beside `ExportButtons` on the Generator page once the deck is `done`. It is a single pill (green when `deck_quality.ok && invalid_count === 0`, amber otherwise) showing `valid/total` slides and, when applicable, the number of `repairs` needed. Clicking it expands a small monospaced list of up to 12 errors keyed by `slide_index · layout · path · code`.
- The component is intentionally utilitarian: Tailwind utilities only, no new design tokens, no new icons, no new typography, no theme work. It reuses existing `nexus-*` and `accent-*` utility classes.
- Visual system otherwise unchanged. No layout edits. No card / typography / color-token changes. Slide rendering, theme system, and export rendering are untouched.

### Files Changed
- `frontend/src/components/DeckQualityBadge.jsx` — new file (~70 lines).
- `frontend/src/pages/Generator.jsx` — imports the badge, captures `deck_quality` from the slides response, and places the badge in the existing done-state footer (`<div className="flex items-center justify-between border-t border-nexus-border/60 pt-4">`). No structural rework.

### Tests Added
- No frontend test framework was introduced. The structural gate (`npm run verify:layouts`) still passes. Layout registry parity is unaffected.

### Tests Run
- `npm run verify:layouts` → ✔ 7 canonical layouts, 7 exported.
- Backend tests (relevant for the data the badge consumes): 90 passed, 1 skipped.

### Result
Visual posture for Phase 1D — **Pass (narrow)**. Minimal UI visibility added; visual system otherwise unchanged. Broader visual-quality posture remains **Partial** pending the still-out-of-scope visual passes (slide-master polish, chart styling parity with reference assets, share-page typography, hero polish).

### Remaining Risks
- The badge is currently rendered only on the Generator page. The `SharedSlide` page (which consumes `GET /api/share/{token}`) does not yet show it, although the API now returns `deck_quality` there too. Adding it to the share page is a small follow-up; deliberately out of Phase 1D scope.
- The amber pill uses Tailwind `amber-*` and `emerald-*` utilities directly rather than the `accent-*` token system. If the design system later formalizes a “warning” token, this should be migrated.

## Phase 1C Deck Quality Report - 2026-05-09

**Scope:** Backend telemetry layer only. **No visual changes.**

### What Was Added
- New backend-only module `backend/agent/deck_quality.py` (`RepairAction`, `DeckQualityReport`, `build_deck_quality_report`) wired into `NexusAgentLoop._normalize_slides` to emit structured per-slide WARNINGs and a deck-level INFO summary (`loop.deck_quality_report`).
- **No renderer, CSS, layout component, design token, typography, color, spacing, motion, or visual-test files were touched.**

### Files Changed
- `backend/agent/deck_quality.py` (new).
- `backend/agent/loop.py` (`_normalize_slides` telemetry only).
- `backend/tests/test_deck_quality.py` (new).
- (No `frontend/src/**` changes. No `tests/visual/*` changes.)

### Tests Added
- 9 backend tests covering the report shape, repair-action defaults, non-mutation guarantee, non-list handling, and live `_normalize_slides` telemetry (deck-level summary + per-slide failure).
- **No visual tests added or modified.**

### Tests Run
- `cd frontend ; npm run verify:layouts` → `✔ verify-layouts OK — 7 canonical layouts, 7 exported.` (registry parity only — not a visual test.)
- Backend Docker pytest one-shot → **85 passed in 1.04s**.
- No frontend visual / Storybook / Playwright suite was run as part of this phase.

### Result
- Visual quality → **Unchanged**. This phase is data-shape and observability only.
- Backend narrow scope → **Pass**.
- Visual fidelity vs PRD remains **Partial / not re-measured**.

### Remaining Risks
- All previously-recorded visual gaps remain open: chart polish, typography refinement, layout density, motion/transitions, branded theme depth, dark-mode parity, export rendering vs on-screen rendering.
- The safety-net stats→chart promotion still emits a chart slide without slide-level `subtitle`; this is now visible in both per-slide and deck-level telemetry, but the visual rendering of such a slide is unchanged and may still look incomplete until a repair phase lands.
- DeckQualityReport is not surfaced to the UI in this phase; users still see no quality cues.
- Full backend pytest still blocked by `conftest.py` / database setup.
- Registry still supports only 7 honest layouts.

---

## Phase 1B.1 Audit Correction - 2026-05-09

**Scope:** Backend slide-contract correction. **No visual changes.**

### What Was Corrected
- Backend slide-contract validator (`backend/agent/slide_schema.py`) now requires `chart_data.unit` and `chart_data.source`, and the `validate_slide` docstring accurately describes the non-repair shallow-copy semantics. A new caplog-based test exercises the `_normalize_slides` validation telemetry path.
- **No renderer, CSS, layout component, design token, typography, color, spacing, motion, or visual-test files were touched.**

### Files Changed
- `backend/agent/slide_schema.py`
- `backend/tests/test_slide_schema.py`
- (No `frontend/src/**` changes. No `tests/visual/*` changes.)

### Tests Added
- 5 backend chart_data contract tests.
- 1 backend telemetry caplog test on `_normalize_slides`.
- **No visual tests added or modified.**

### Tests Run
- `cd frontend ; npm run verify:layouts` → `✔ verify-layouts OK — 7 canonical layouts, 7 exported.` (registry parity only — not a visual test.)
- Backend Docker pytest one-shot → **76 passed in 1.33s**.
- No frontend visual / Storybook / Playwright suite was run as part of this correction.

### Result
- Visual quality → **Unchanged**. This correction is data-shape and observability only.
- Backend narrow scope → **Pass** (does not affect visual claims).
- Visual fidelity vs PRD remains **Partial / not re-measured** in this correction.

### Remaining Risks
- All previously-recorded visual gaps remain open: chart polish, typography refinement, layout density, motion/transitions, branded theme depth, dark-mode parity (where applicable), export rendering vs on-screen rendering.
- The safety-net stats→chart promotion still emits a chart slide without slide-level `subtitle`; this is now observable in logs but the visual rendering of such a slide is unchanged and may still look incomplete until a repair phase lands.
- Full backend pytest still blocked by `conftest.py` / database setup; full-suite green not claimed.
- Registry still supports only 7 honest layouts until renderer/normalizer/export coverage expands.

---

## Phase 1B.1 Schema Strictness Update - 2026-05-09

### What Changed
- Backend-only schema/telemetry hardening. **No renderer, slide-template, CSS, or visual-test changes.**
- `backend/agent/slide_schema.py` now requires `title.subtitle`, `title.eyebrow`, `quote.attribution`, `chart.subtitle`, `closing.subtitle`, `closing.cta` to be present (empty strings allowed where the normalizer emits them).
- `validate_slide(..., resolve_aliases=False)` now requires exact canonical names.
- `ValidationResult.normalized` is now a shallow copy with canonical `layout` pinned (no auto-repair).
- `NexusAgentLoop._normalize_slides` now emits structured validation telemetry post-normalization. Output shape unchanged; renderer input unchanged.

### Files Changed
- `backend/agent/slide_schema.py`
- `backend/agent/loop.py`
- `backend/tests/test_slide_schema.py`
- (No frontend, no renderer, no CSS, no visual-test files touched.)

### Tests Added
- 13 schema tests (see other audits for the full list). No visual tests added.

### Tests Run
- `cd frontend ; npm run verify:layouts` → OK (7/7).
- Docker one-shot pytest → **70 passed in 0.91s** for the targeted suites.
- No visual regression tests run — none exist in this phase.
- Full backend pytest **not** claimed; pre-existing conftest/database blocker remains.

### Result
- **Visual quality: Unchanged.** This phase did not touch any visual code or visual tests, so no visual claim is made or revised.
- **Phase 1B.1 narrow scope (schema strictness + telemetry): Pass.**
- **Broader platform status: Partial** (unchanged).

### Remaining Risks
- Visual fidelity (typography, spacing, charts, density, motion) remains unaddressed by this phase.
- No repair pipeline, no `DeckQualityReport`, no export parity fix, no real browser automation.
- Validation failures are logged, not enforced.
- Full backend pytest still blocked by conftest/database setup.
- Registry still supports only 7 honest layouts — visual coverage is bounded by that surface.

## Phase 1B Schema Validation Update - 2026-05-09

### What Changed
- Added `backend/agent/slide_schema.py`, a typed slide-contract validator covering the 7 canonical layouts. This is a *data* contract change, not a visual change.
- The validator surfaces structured errors (`path`, `code`, `message`) so future quality work (DeckQualityReport, repair pipeline) can act on specific failures rather than guessing.
- Unknown layouts are rejected with `unknown_layout` rather than silently coerced via `FALLBACK_LAYOUT`.
- No renderer changes. No typography changes. No spacing, color, or layout density changes. No export rendering changes. No new layouts.

### Files Changed
- Added `backend/agent/slide_schema.py`.
- Added `backend/tests/test_slide_schema.py`.

### Tests Added
- 34 tests in `tests/test_slide_schema.py` (valid examples per layout + failure paths for required fields, types, bullets cap, two-col shape, stats shape, chart enum + chart_data shape/length/numeric/bool, quote required text, unknown layouts, deck wrapper).

### Tests Run
- `cd frontend ; npm run verify:layouts` → `✔ verify-layouts OK — 7 canonical layouts, 7 exported.`
- One-shot Docker pytest (`--noconftest -p no:cacheprovider`) on `tests/test_layout_coverage.py` and `tests/test_slide_schema.py` → `57 passed in 0.74s`.
- No visual or screenshot tests were run. None exist for this scope.
- Full backend pytest still blocked by conftest/DB setup; not run.

### Result
- Phase 1B narrow scope (data-contract validation): **Pass**.
- Visual quality status: **Unchanged / Not addressed** — Phase 1B is a contract-layer change. Visual quality remains an open audit item and is NOT resolved by this phase.

### Remaining Risks
- Visual quality (typography, hierarchy, spacing, color, density, image use, chart aesthetics) is unchanged.
- Validator is not yet enforced in the rendering pipeline; bad payloads can still reach the renderer.
- No auto-repair pipeline yet.
- No DeckQualityReport yet.
- Export parity (PPTX/PDF) unverified — visual fidelity between web and export is not measured.
- No real browser automation (`services/browser_service.py` is disabled).
- Full backend pytest still blocked by conftest/DB setup.
- Only 7 honest layouts supported; broader visual-layout coverage (image, comparison, timeline, etc.) requires renderer + normalizer + export expansion first.

## Phase 1A.1 Planner Layout Drift Update - 2026-05-09

### Visual Impact
None. Phase 1A.1 only removed a hardcoded `_VALID_LAYOUTS` set from `backend/agent/planner.py` and routed it through the canonical registry. No styling, typography, spacing, palette, motion, layout component, or art-direction code was touched. The 7 canonical layouts and the renderer that draws them are unchanged.

### Tests Run
- `npm run verify:layouts` -> **PASS**.
- One-shot pytest container -> **PASS** (`23 passed in 0.69s`, includes the original 13 + 10 new planner cases).
- Visual / Playwright snapshot suites NOT run. Reason: this phase made no rendering changes.

### Result for this Audit
**Not applicable / Pass-through.** No visual scores move. The visual-quality scorecard, layout-by-layout findings, premium-feel critique, and recommendations all remain as written.

### Remaining Visual Risks
Unchanged. All visual concerns documented in this audit — mechanical rhythm, dashboard-y density, weak typography premium, missing cinematic framing, weak deck-level pacing, missing brand-aware theming, weak export-parity polish — are open and untouched by Phase 1A.1.

## Phase 1A Correction Update - 2026-05-09

> **Correction notice.** A previous Phase 1A audit pass intentionally did not update this file, with the rationale that "Phase 1A is a contract/coverage change, not a visual-rendering change." That rationale is still correct — Phase 1A makes no visual changes — but the prior Phase 1A claims about a 23-layout registry that appeared in other audit files were factually wrong, and silence here was being interpreted as endorsement. This section sets the visual-audit record straight. **See "Phase 1A Correction Update" above for the verified numbers (7 canonical layouts, 0 aliases, 13 tests).**

### Visual Impact of Phase 1A
None at the rendering level. Phase 1A only:
- Removed hardcoded layout whitelists from `backend/agent/loop.py` and `frontend/src/utils/slideParser.js` and sourced them from a canonical registry.
- Added `frontend/src/design/layouts.registry.json` (and a backend twin) listing the **7 canonical layouts the renderer already supports today** (`title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`). No new layouts were introduced; no styling, typography, spacing, palette, motion, or art-direction code was touched.
- Added a `case "chart"` branch in `frontend/src/utils/slideParser.js`. Before this phase, `chart` was missing from the frontend's valid-layout set (it was rendered correctly only because the renderer's own layout map covered it); the parser now passes through `chart_type` and `chart_data` fields explicitly. This is a contract fix, not a visual change \u2014 chart slides still render via the same `ChartSlide` component with the same styling.

### Tests Run
- `npm run verify:layouts` -> **PASS** (`7 canonical layouts, 7 exported`).
- `docker run --rm ... nexus-ai-backend:latest python -m pytest --noconftest tests/test_layout_coverage.py -v` -> **PASS** (`13 passed in 0.58s`).
- Visual / Playwright snapshot suites were NOT run. Reason: Phase 1A made no rendering or styling changes, so a snapshot run would only re-confirm the existing visual-quality baseline this audit already documents.

### Result for this Audit
**Not applicable / Pass-through.** Phase 1A neither improves nor regresses any of the visual dimensions scored in this document. The visual-quality scorecard, layout-by-layout findings, premium-feel critique, and recommendations below all remain as written. Any audit reader expecting Phase 1A to move visual scores should expect zero movement \u2014 that work is in later phases (typography refinement, art direction, layout expansion, premium feel).

### Remaining Visual Risks (unchanged by Phase 1A)
All visual concerns documented in this audit \u2014 mechanical rhythm, dashboard-y card density, weak typography premium, missing cinematic framing, weak deck-level pacing, missing brand-aware theming, weak export-parity polish \u2014 are unaffected by Phase 1A and remain open.

## Visual Score Summary

| Dimension | Score | Assessment |
|---|---:|---|
| Visual hierarchy | 5 / 10 | Basic hierarchy is clear, but not sophisticated or dynamic. |
| Whitespace rhythm | 4 / 10 | Padding is consistent, but rhythm is mechanical and often cramped in cards. |
| Typography quality | 4 / 10 | Functional type scale; not premium, editorial, or brand-sensitive enough. |
| Composition quality | 4 / 10 | Mostly grids, cards, and simple splits; limited dramatic composition. |
| Slide pacing | 3.5 / 10 | Layout variety exists, but deck-level emotional pacing is weak. |
| Grid consistency | 5.5 / 10 | Grids are predictable; some layouts feel more UI-like than presentation-like. |
| Spacing cadence | 4 / 10 | Repeated spacing tokens create consistency but not refinement. |
| Premium feel | 3.8 / 10 | Clean, but not expensive. Too much template energy. |
| Cinematic feel | 2.8 / 10 | Hero/image layouts lack camera-aware art direction and dramatic focal control. |
| Consulting quality | 4.5 / 10 | Some business structures exist; argument clarity and chart polish lag. |
| Presentation psychology | 3.5 / 10 | Slides organize content but rarely guide audience emotion or attention deeply. |
| Visual density | 4 / 10 | Often too card-dense or too text-card dependent. |
| Image composition | 3 / 10 | Images are backgrounds/fills, not intentionally composed scenes. |
| Card composition | 4 / 10 | Cards are clean but overused and often oversized/rounded. |
| Title/subtitle relationship | 4.5 / 10 | Clear but generic; subtitles often feel like filler text blocks. |
| Visual storytelling | 3 / 10 | Layouts show information, not narrative progression. |
| Readability | 5.5 / 10 | Generally readable, but long content and gallery framing expose fragility. |
| Presentation-stage quality | 3.8 / 10 | Acceptable in preview; not confident enough for a serious keynote or boardroom. |

## Competitive Visual Comparison

| Product / Standard | Visual Strength | NEXUS Relative Position | Gap |
|---|---|---|---|
| Manus | Cinematic task/progress storytelling, polished spatial rhythm, high perceived intelligence. | Significantly behind. | NEXUS feels more like a slide component library than an authored experience. |
| Gamma | Clean modern templates, polished card rhythm, strong publishing feel. | Behind. | NEXUS card layouts are less refined and less editorially paced. |
| Pitch | Crisp grid discipline, typography, collaboration-grade business polish. | Behind. | NEXUS lacks Pitch-level spacing precision and chart/table polish. |
| Tome | Narrative/media-led presentation flow, immersive visual storytelling. | Far behind. | NEXUS has weak cinematic/media direction. |
| Canva presentations | Huge template polish and accessible visual variety. | Behind. | NEXUS has fewer truly distinct art-directed compositions. |
| McKinsey/BCG decks | Argument hierarchy, chart discipline, restrained consulting clarity. | Behind. | NEXUS lacks decisive executive framing, chart rigor, and message architecture. |

## Manus / Gamma Comparison Matrix

| Visual Attribute | NEXUS | Manus | Gamma | Required Direction |
|---|---:|---:|---:|---|
| Premium first impression | 4 | 8 | 8 | Stronger first slide, less generic template structure. |
| Cinematic hero quality | 3 | 8 | 6 | Better image selection, focal cropping, darker/lighter region planning. |
| Layout sophistication | 4 | 7 | 8 | Fewer simple card grids, more editorial compositions. |
| Deck pacing | 3 | 7 | 7 | Alternate density, silence, data, hero, and argument slides intentionally. |
| Typography polish | 4 | 7 | 7 | Better font pairing, optical sizing, less generic Inter-only feel. |
| Consulting clarity | 4.5 | 6 | 6 | Add executive takeaway headlines and chart-first slides. |
| Emotional design | 3 | 8 | 6 | Introduce mood, tension, reveal, and visual payoff. |
| Readability | 5.5 | 7 | 8 | Improve text budget enforcement and stage-scale contrast. |
| Visual consistency | 5 | 7 | 8 | Better deck-level art direction and theme coherence. |
| Template originality | 3.5 | 7 | 6 | Reduce repeated card/icon/tint patterns. |

## Top Visual Weaknesses

1. **Too template-forward.** Many layouts look like rearranged card components rather than authored presentation slides.
2. **Weak cinematic art direction.** Images are mostly object-cover backgrounds with scrims; they lack focal composition, subject placement, and emotional staging.
3. **Overuse of cards.** Bento, feature-grid, KPI, process, callout, matrix, and agenda all lean on cards or card-like containers.
4. **Typography feels default.** The system is readable, but not editorial, premium, or brand-specific enough.
5. **Spacing is consistent but not nuanced.** Tokenized spacing creates order, but not the optical rhythm of premium slides.
6. **Weak slide pacing.** Decks risk feeling like a sequence of same-density panels.
7. **Limited presentation psychology.** Slides do not strongly control attention, reveal stakes, or create emotional progression.
8. **Charts are underdesigned.** Chart layouts look functional rather than consulting-grade.
9. **Gallery/stage framing is flawed.** Fixed app chrome can cover content, and clean layout captures show clipping/framing fragility.
10. **Rounded-card visual language is too dominant.** This makes the product feel like a SaaS dashboard rather than a premium presentation engine.

## Layouts That Feel Templated

| Layout | Why It Feels Templated | Severity |
|---|---|---|
| `bento` | Predictable big-card + small-card structure; colorful blocks feel generic. | High |
| `feature-grid` | Standard icon-card grid; common SaaS landing-page pattern. | High |
| `process` | Step cards plus arrows; functional but visually ordinary. | High |
| `agenda` | Numbered list with separators; clean but not premium. | Medium |
| `kpi` | Metric cards in row/grid; dashboard-like. | Medium |
| `matrix-2x2` | Consulting familiar, but card styling softens seriousness. | Medium |
| `callout` | Large colored card with icon; attractive but generic. | Medium |
| `bullets` | Conventional content layout; depends heavily on copy quality. | High |
| `comparison` | Side-by-side structure is expected; needs sharper contrast and argument. | Medium |
| `roadmap` | Timeline dots/cards feel common and lightweight. | Medium |

## Layouts That Feel More Premium

| Layout | Why It Works | Caveat |
|---|---|---|
| `hero` | Full-bleed image can create atmosphere. | Needs focal-point and contrast intelligence. |
| `title` | Multiple title variants create variety and some editorial moments. | Variants are inconsistent; some feel gimmicky. |
| `quote` | Low-density slide type can create breathing room. | Needs stronger typographic restraint and attribution styling. |
| `metric-spotlight` | Big-number hierarchy is presentation-friendly. | Needs better context framing and less generic supporting bullets. |
| `section` | Can give decks pacing if restrained. | Needs more dramatic section transitions. |
| `timeline` | Good narrative potential. | Current treatment needs more cinematic/consulting polish. |
| `image-focus` | Has premium potential when image quality is strong. | Requires real art direction and caption discipline. |

## Typography Scorecard

| Typography Area | Score | Critique | Required Fix |
|---|---:|---|---|
| Type scale | 5 | Functional clamp-based scale, but visually generic. | Add optical type scales per deck type: consulting, cinematic, editorial, startup pitch. |
| Font pairing | 3 | Defaults lean heavily on Inter/system; serif variants are inconsistent. | Define premium font pairs and enforce them deck-wide. |
| Title treatment | 4.5 | Titles are readable but often lack strong editorial tension. | Add message-headline patterns and optical line breaking. |
| Subtitle treatment | 4 | Subtitles often feel like generic explanatory text. | Use shorter, more intentional dek-style subtitles. |
| Eyebrow labels | 3.5 | Wide letter spacing is overused; can feel artificial. | Reduce tracking and vary label treatment by theme/layout. |
| Body readability | 5.5 | Generally readable. | Enforce max line length and fewer words per slide. |
| Numeric typography | 5 | Metrics are visually clear. | Improve labels, context, and comparison structure. |
| Stage readability | 4 | Preview-readable, but not reliably boardroom/keynote scale. | Test at projection scale and enforce minimum visual sizes. |

## Spacing Scorecard

| Spacing Area | Score | Critique | Required Fix |
|---|---:|---|---|
| Outer margins | 5 | Consistent but sometimes too uniform. | Use layout-specific optical margins. |
| Header-to-content gap | 4 | Often mechanical; cards begin too predictably below title. | Vary rhythm by slide type and density. |
| Card padding | 4 | Clean, but visually soft and samey. | Reduce card radius/padding for consulting themes; increase air for cinematic themes. |
| Grid gutters | 5 | Predictable and usable. | Add hierarchy-aware gutters, not equal spacing everywhere. |
| Vertical rhythm | 3.5 | Some layouts feel top-heavy or clipped in gallery. | Add content-fit measurement and rhythm presets. |
| Dense slide handling | 3 | Relies on truncation/ellipsis in some places. | Use density-aware layout switching. |
| Empty space usage | 3.5 | Empty space is often leftover, not intentionally dramatic. | Design “silence” slides and asymmetrical compositions. |

## Hierarchy Analysis

Current hierarchy is mostly achieved through size, color, and cards. That is the basic tier of presentation design. Premium decks use hierarchy through framing, contrast of density, visual sequencing, narrative emphasis, and intentional omission.

Problems:

- Too many slides begin with eyebrow -> title -> subtitle -> grid.
- Content blocks compete for equal attention.
- Icons are used as decoration rather than hierarchy anchors.
- Some layouts lack a single unmistakable message.
- Supporting text can dilute the main insight.

Required improvements:

- Every slide needs one dominant takeaway, visually encoded.
- Add “headline as argument” style for consulting decks.
- Add density classes: hero, argument, evidence, compare, detail, close.
- Add visual hierarchy validation: one primary, two secondary, rest tertiary.

## Composition Analysis

The system is grid-stable but compositionally conservative. It rarely uses scale, crop, negative space, diagonal tension, editorial layering, or cinematic subject placement.

Composition weaknesses:

- Repeated rectangular containers.
- Repeated icon-card structures.
- Few asymmetric compositions that feel intentional.
- Weak image/text integration.
- Little sense of foreground/midground/background.
- Chart slides lack executive takeaway framing.

Composition improvements:

- Add editorial layouts with extreme scale contrast.
- Add one-idea slides with large type and restrained detail.
- Add image-led layouts where text occupies a planned safe zone.
- Add consulting chart layouts: headline insight, chart, source, implication.
- Add visual rhythm rules across a deck: dense -> sparse -> evidence -> image -> close.

## Premium-Feel Assessment

| Premium Signal | Current State | Score |
|---|---|---:|
| Expensive typography | Mostly absent | 3 |
| Subtle spacing | Inconsistent | 4 |
| Editorial image use | Weak | 3 |
| Restrained color | Mixed; often too colorful | 4 |
| Brand confidence | Generic | 3 |
| Consulting clarity | Partial | 4.5 |
| Stage confidence | Weak | 3.8 |
| Template originality | Weak | 3.5 |
| Visual silence | Weak | 3 |
| Polished details | Partial | 4 |

Premium feel is limited by the system’s reliance on obvious visual building blocks: cards, icons, tints, grids, and wide-tracked labels. Premium decks usually feel less “assembled.”

## Emotional Design Weaknesses

- No strong mood progression across a deck.
- Images do not consistently create curiosity, tension, or aspiration.
- Title slides do not reliably create a memorable opening moment.
- Closing slides risk feeling generic.
- Data slides do not dramatize implications.
- Section slides do not create narrative resets.
- The design system organizes information but rarely creates desire.

## Cinematic Quality Gaps

| Cinematic Element | Current State | Gap |
|---|---|---|
| Focal point | Not controlled | Need subject detection and safe text zones. |
| Lighting mood | Depends on random image | Need style-directed image selection/generation. |
| Depth | Mostly flat | Add layered scrims, foreground text planes, parallax-like composition. |
| Framing | Center/object-cover | Add rule-of-thirds and crop-position logic. |
| Scale | Limited | Use extreme type/image scale in selected layouts. |
| Sequence | Weak | Plan visual arcs across deck, not slide-by-slide only. |
| Drama | Low | Add contrast, silence, reveal, and stronger opening/closing slides. |

## Per-Layout Visual Critique

| Layout | Visual Score | Critique | Redesign Priority |
|---|---:|---|---|
| `title` | 5 | Has variety, but variants are uneven. Some feel editorial; others feel gimmicky or brand-stamped. | High |
| `section` | 4.5 | Useful pacing slide, but lacks dramatic transition quality. | Medium |
| `bullets` | 3.5 | Functional, conventional, and too dependent on copy. Risks document-slide feel. | High |
| `two-col` | 4 | Clear but generic. Needs stronger contrast between columns and more visual argument. | Medium |
| `comparison` | 4 | Familiar consulting structure, but too soft and not decisive enough. | Medium |
| `kpi` | 4.5 | Readable metric structure; feels dashboard-like, not boardroom-premium. | Medium |
| `quote` | 5 | Has breathing-room potential. Needs more refined typography and less obvious quote styling. | Medium |
| `stats` | 4.5 | Clear numbers, but weak story. Needs context and implication. | Medium |
| `chart` | 3.5 | Underdesigned. Needs insight headline, cleaner axes, annotations, and source treatment. | Critical |
| `table` | 3 | Tables are rarely premium without strong formatting. Needs consulting-grade hierarchy. | High |
| `timeline` | 4.5 | Good narrative potential, currently too basic. | Medium |
| `image-focus` | 4 | Depends entirely on image quality. Needs focal crop and caption discipline. | High |
| `closing` | 4 | Likely generic. Needs memorable final note and visual restraint. | Medium |
| `hero` | 5 | Best cinematic potential, but current image handling is blunt. | High |
| `bento` | 4 | Modern but templated; feels like SaaS feature grid. | High |
| `agenda` | 3.5 | Clean list, low premium value. | Low |
| `roadmap` | 4 | Useful but common. Needs scale, milestones, and narrative emphasis. | Medium |
| `metric-spotlight` | 5 | Strong hierarchy potential. Needs better supporting context. | Medium |
| `process` | 3.5 | Step cards and arrows feel generic. | High |
| `pyramid` | 3.5 | Looks like a basic diagram. Needs stronger consulting polish. | High |
| `matrix-2x2` | 4 | Consulting familiar, but styling lacks executive sharpness. | Medium |
| `feature-grid` | 3.5 | Very templated. Icons/cards make it feel like a marketing webpage. | High |
| `callout` | 4.5 | Visually clear, but large colored card is predictable. | Medium |

## Layouts Needing Redesign First

| Priority | Layout | Why |
|---:|---|---|
| 1 | `chart` | Charts are central to business decks and currently lack consulting-grade polish. |
| 2 | `title` | First impression defines perceived intelligence and premium quality. |
| 3 | `hero` | Highest cinematic potential; current handling is too blunt. |
| 4 | `bullets` | Most likely to appear often; must stop feeling document-like. |
| 5 | `feature-grid` | Too generic and web-template-like. |
| 6 | `process` | Step-card pattern feels low originality. |
| 7 | `table` | Needs executive table design, not spreadsheet rendering. |
| 8 | `bento` | Useful, but must become more editorial and less SaaS-card. |
| 9 | `pyramid` | Needs sharper hierarchy and consulting polish. |
| 10 | `image-focus` | Needs image-aware crop and caption composition. |

## Exact Visual Improvements Required

### Typography

1. Add presentation-specific font systems: consulting, cinematic, editorial, startup, academic.
2. Add optical title breaking: avoid awkward line wraps and balance title lines by meaning.
3. Reduce overuse of wide-tracked eyebrows.
4. Add insight-headline style: full-sentence takeaway headlines for consulting decks.
5. Add stronger subtitle discipline: shorter, lower-contrast, less paragraph-like.

### Spacing

1. Replace one-size spacing with layout density presets.
2. Add optical margin tuning per layout.
3. Reduce equal-card rhythm in dense layouts.
4. Add more intentional negative space slides.
5. Add stage-scale spacing tests, not only preview-scale checks.

### Composition

1. Create asymmetric editorial layouts that are not card grids.
2. Add image-safe text zones based on image analysis.
3. Add chart-first consulting slide layouts.
4. Add sparse “one message” slides for pacing.
5. Add stronger section dividers with cinematic or editorial transitions.

### Cards

1. Reduce card radius for consulting/professional themes.
2. Use fewer cards per slide.
3. Replace some cards with ruled lines, tabs, bands, annotations, and panels.
4. Make icons optional and semantically meaningful.
5. Add card hierarchy: one dominant card, two supporting cards, not uniform grids.

### Images

1. Add focal-point crop logic.
2. Add contrast-aware text placement.
3. Add style consistency across deck images.
4. Prefer real subject images for product/place/person topics.
5. Avoid generic atmospheric images unless the slide is intentionally cinematic.

### Deck Pacing

1. Define rhythm patterns: opener, problem, evidence, insight, data, contrast, visual pause, close.
2. Limit consecutive card-grid slides.
3. Insert low-density visual pauses.
4. Alternate text-heavy and visual-heavy slides.
5. Add closing slides with a designed emotional endpoint.

## Redesign Priorities

| Priority | Work | Expected Visual Lift |
|---:|---|---|
| P0 | Redesign chart/table layouts into consulting-grade evidence slides. | Very high |
| P0 | Redesign title/hero/opening system for premium first impression. | Very high |
| P0 | Add layout density and overflow visual tests. | High |
| P1 | Add image focal-point, contrast, and safe-zone placement. | High |
| P1 | Reduce card dependence across bento/feature/process/callout. | High |
| P1 | Add deck-level pacing rules. | High |
| P1 | Add premium typography systems and better line-breaking. | Medium/high |
| P2 | Add theme-specific visual languages instead of palette swaps. | Medium/high |
| P2 | Add stage-readability checks. | Medium |
| P2 | Improve gallery framing so QA views are visually truthful. | Medium |

## Final Visual Assessment

NEXUS currently looks like a capable generated-slide UI, not a premium presentation design engine. It is clean enough for demos and internal drafts, but not strong enough for executive-stage, investor, consulting, or high-polish product storytelling without human redesign.

To compete visually, the product needs fewer generic cards, stronger typography, sharper consulting charts, more cinematic image composition, deck-level pacing, and a real sense of art direction. The fastest path upward is not adding more layouts; it is redesigning the most frequently used layouts until they feel authored rather than generated.

---

## Phase 6A — 2026-05-09 — No visual impact

Phase 6A added Bearer-JWT authentication to `/api/agent/test-run` and an Alembic migration for `agent_runs` / `agent_steps` / `artifacts`. **No frontend, renderer, layout, or visual code was touched.** Visual quality findings in this file remain current.


---

## Phase 6B — 2026-05-09 — Visual quality benchmark category defined

Phase 6B added a `visual_quality` rubric category (weight 15/100) in [benchmarks/rubric.json](nexus-ai/benchmarks/rubric.json) and a per-prompt `expected_visual` block in [benchmarks/prompts.json](nexus-ai/benchmarks/prompts.json). Current visual_quality score is **estimated at 5/10** (target 8/10). The estimate is recorded in [audits/CURRENT_COMPETITIVE_SCORE.md](nexus-ai/audits/CURRENT_COMPETITIVE_SCORE.md).

**No frontend, renderer, layout, or visual code was touched.** The pixel-level findings in this file remain current. A screenshot-diff suite is still missing and is the primary blocker for moving the visual_quality score from estimated to measured.


---

## Phase 6C — 2026-05-09 — Export content parity, not visual parity

Phase 6C added [backend/tests/test_export_parity.py](nexus-ai/backend/tests/test_export_parity.py) (15 tests) which prove that PPTX exports **preserve the textual content** of all 7 canonical layouts — titles, bullets, columns, quote text and attribution, stat values and labels, chart category labels and series values, captions, closing CTA. **This is content parity, not visual parity.**

Visual quality findings in this file remain current. Specifically still unmeasured: typography, spacing, exact positioning, font weight/family fidelity, chart visual styling, color reproduction, and pixel-level web?PPTX diff. PDF visual parity is also unclaimed — Phase 6C's PDF coverage is a smoke test only that **skips** if WeasyPrint is unavailable.

The fixture module [backend/tests/fixtures/canonical_slides.py](nexus-ai/backend/tests/fixtures/canonical_slides.py) is reusable by a future screenshot-diff phase.

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

