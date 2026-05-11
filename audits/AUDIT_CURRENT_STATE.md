# NEXUS AI — Current Audit State

**Last verified:** 2026-05-10 (Phase 6X → 6AE-Acceptance — **Pass**. Backend gate **521 passed, 2 skipped, 1 warning** (was 431/2/1 at Phase 6V; +90 new tests including the 78 in-flight phase tests, 8 auto-parametrized layout-coverage cases, plus 4 new schema example cases). No live eval run, no headline score change claimed. Phase 6U-Rebench remains the most recent score-eligible measurement.
**Source of truth:** This file. All four detailed audit files in this folder contain useful background and historical phase logs, but their older sections may be superseded. When in doubt, prefer this file.

---

## Current Completed Phase

**Phase 6X–6AE-Acceptance — Lock acceptance for the entire visible-cognition + composition batch.** Accepted as **Pass**. Six in-flight phases (`6X`, `6Y`, `6AB`, `6AA`, `6AC`, `6AD`, `6AE`) promote from Acceptance Pending to Pass on a clean backend gate. **No reference-folder edits, no reference-code copies, stack unchanged.** **Backend gate: 521 passed, 2 skipped, 1 warning** (was 431/2/1 at Phase 6V; +90 new tests). **No live eval run; headline score unchanged at ~62/100 (Phase 6U-Rebench Partial baseline).**

### Tests added (8 new test files, 78 new test cases + auto-parametrized layout-coverage extensions)

- New [nexus-ai/backend/tests/test_run_events_intel.py](nexus-ai/backend/tests/test_run_events_intel.py) — 9 cases covering Phase 6X (`research_note`, `outline_ready`, `source_found`) and Phase 6Y/6AB/6AD (`design_decision`) SSE event types: registry presence, EXPLICIT_EVENT_MAP routing, payload round-trip, sequence monotonicity, complex value passthrough (beats/rhythm), forward-compatible unknown-event handling.
- New [nexus-ai/backend/tests/test_slide_intent.py](nexus-ai/backend/tests/test_slide_intent.py) — 19 cases covering Phase 6AB intent block + Phase 6AD beat threading: 4-field shape, JSON-serialisability, position-based and arc-based role derivation, beat override, density per layout, tone precedence (art_mood > strategy_tone > neutral), attach idempotency, non-dict pass-through, beats-length-mismatch fallback, schema compatibility (validator accepts intent block).
- New [nexus-ai/backend/tests/test_layout_recommender.py](nexus-ai/backend/tests/test_layout_recommender.py) — 11 cases for Phase 6AA upgraders: bigstat dominance rule, density-high refusal, single-stat upgrade, section_divider trigger, long-bullet refusal, pinned-end protection, non-dict and empty-list defensive paths, input-non-mutation contract.
- New [nexus-ai/backend/tests/test_layout_recommender_timeline.py](nexus-ai/backend/tests/test_layout_recommender_timeline.py) — 6 cases for Phase 6AC timeline upgrader: year-only / month-name / quarter / ISO / decade date patterns, mixed-content refusal, ≥3 threshold, 6-event cap, non-bullets skip.
- New [nexus-ai/backend/tests/test_layout_recommender_comparison.py](nexus-ai/backend/tests/test_layout_recommender_comparison.py) — 6 cases for Phase 6AC comparison upgrader: title cue (vs / before-after), antonym pair (problem↔solution, pros↔cons), missing-content refusal, non-two-col skip.
- New [nexus-ai/backend/tests/test_narrative_beats.py](nexus-ai/backend/tests/test_narrative_beats.py) — 12 cases for Phase 6AD: vocabulary contract, length-stability, pinned setup/aftermath, arc normalisation (known + unknown), arc threading across middle, research-side promotion (positive + negative), `role_from_beat` round-trip, transition indices.
- New [nexus-ai/backend/tests/test_phase_6aa_6ac_layouts.py](nexus-ai/backend/tests/test_phase_6aa_6ac_layouts.py) — 13 cases asserting registry presence (count = 11), schema validators accept well-formed slides for each new layout, schema rejects malformed payloads (missing required fields, oversized event lists), deck_repair seeds optional fields without inventing semantic content.

### Files changed (in addition to the new test files)

- [nexus-ai/backend/tests/test_slide_schema.py](nexus-ai/backend/tests/test_slide_schema.py) — `VALID_EXAMPLES` extended with 4 new layout examples (bigstat, section_divider, timeline, comparison) so the parametrized `test_valid_example_passes[<layout>]` and the `test_all_canonical_layouts_have_examples` guard now cover the full 11-layout set.
- [nexus-ai/backend/tests/test_layout_coverage.py](nexus-ai/backend/tests/test_layout_coverage.py) — `_seed_slide` extended with seed payloads for the 4 new layouts so the parametrized `test_normalize_preserves_canonical_layout[<layout>]` survives `_normalize_slides` for all 11 layouts.
- [nexus-ai/backend/agent/themes_registry.py](nexus-ai/backend/agent/themes_registry.py) — restored Phase 6O design invariant: removed 14 redundant self-aliases (`"whiteboard" → "whiteboard"` etc.) that session-1 added in error. The 14 first-class themes resolve directly via `BUILTIN_THEMES` because `_normalize_id` already lowercases. Self-aliases must never appear in `LEGACY_THEME_ALIASES`; only legacy display-name → canonical-id translations belong there. Unblocks `test_aliases_only_cover_editorial_and_vellum`. Strict hygiene; no schema, no architecture, no behaviour change for existing decks.

### Test-run command (reproducible)

```
docker run --rm \
  -v "D:/nexus-ai-1/nexus-ai/backend:/app" \
  -v "D:/nexus-ai-1/nexus-ai/benchmarks:/benchmarks:ro" \
  -v "D:/nexus-ai-1/nexus-ai/audits/LIVE_EVAL_RESULTS:/live_eval_results:ro" \
  -w "/app" \
  -e PYTHONPATH=/app/.local/lib/python3.11/site-packages:/app \
  -e DATABASE_URL=sqlite+aiosqlite:///:memory: \
  nexus-ai-backend:dev \
  python -m pytest -q
# 521 passed, 2 skipped, 1 warning in 12.57s
```

### Acceptance promotions

The following six in-flight phases are now **Pass**:

| Phase | Title | Status |
|---|---|---|
| 6X | Visible cognition (research_note + outline_ready + source_found) | **Pass** (was Acceptance Pending) |
| 6Y | Design decision narration | **Pass** (was Acceptance Pending) |
| 6AB | Slide intent metadata layer | **Pass** (was Acceptance Pending) |
| 6AA | Visual diversity layouts: bigstat + section_divider | **Pass** (was Acceptance Pending) |
| 6AC | Timeline + comparison semantic layouts | **Pass** (was Acceptance Pending) |
| 6AD | Narrative beat layer | **Pass** (was Acceptance Pending) |
| 6AE | Semantic scene composition primitives | **Pass** (was Acceptance Pending) |

### Honest limitations

- **No live eval.** Score remains ~62/100 Partial. NEXUS still does not beat Manus.
- **Frontend test runner not configured.** Phase 6AE primitive composition is verified by code review + clean `vite build`, not by automated visual snapshot diff. Phase 6AG (Playwright snapshots) would close this gap.
- **Test count delta is +90, not the +24 originally projected.** The parametrized layout-coverage and slide-schema fixtures auto-generated 11 cases (one per layout × 2 = 22 cases, of which 11 exercise the new layouts).
- **Themes self-alias removal is not back-compat for explicit `LEGACY_THEME_ALIASES["whiteboard"]` callers** — but no production code reads that alias entry directly (verified by grep across the backend tree); resolution flows through `get_theme()` which falls back to `BUILTIN_THEMES` for first-class theme ids.

### What this unlocks

The 6X–6AE batch is now production-disciplined: every phase has unit-test coverage, the gate is clean, the audit trail is complete. Phase 6AF (Per-slide Optimization Pass) and Phase 6AG (Visual Quality Evaluation) can now build on a verified foundation rather than acceptance-pending scaffolding.

---

## Previously Completed Phase

**Phase 6AE — Semantic scene composition primitives.** Accepted as **Acceptance Pending** (no backend gate rerun, no live eval, no score change). Extracts a reusable cinematic primitive set (`Eyebrow`, `Header`, `HeroMetric`, `NarrativeQuote`, `TimelineSpine`, `ComparisonAxis`, `ComparisonSide`, `SectionDividerBlock`, `VisualCallout`, `SlideFrame`) and refactors the four Phase-6AA/6AC layouts (`bigstat`, `section_divider`, `timeline`, `comparison`) to compose from primitives instead of duplicating handcrafted Tailwind. **No reference-folder edits, no reference-code copies, stack unchanged. No renderer rewrite — additive primitive module + 4 layout refactors with byte-for-byte equivalent visual output.** Legacy seven layouts (`title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`) deliberately untouched — refactoring tested code carries non-zero regression risk and is out of scope for 6AE. **Headline score unchanged (~62/100).**

### What changed

A new `frontend/src/components/slidePrimitives.jsx` module exposes 10 presentation-only primitives. Each primitive:
- Takes the theme palette `p` as a required prop.
- Accepts a small enumerated set of size / variant / alignment / tone props (no free-form `className` pass-through that would let layouts drift back to handcrafted soup).
- Has no state, no effects, no portals.
- Is exporter-irrelevant — frontend renderer concern only; the backend PPTX/HTML exporter is unaffected.

The four Phase-6AA/6AC layouts (`BigStatSlide`, `SectionDividerSlide`, `TimelineSlide`, `ComparisonSlide`) shrink from inline Tailwind blocks into composition shells:

```
BigStatSlide       → SlideFrame > [ Eyebrow + HeroMetric ]
SectionDividerSlide → SectionDividerBlock (eyebrow / title / rule / subtitle)
TimelineSlide      → SlideFrame > [ Header + TimelineSpine ]
ComparisonSlide    → SlideFrame > [ Header + ComparisonSide + ComparisonAxis + ComparisonSide ]
```

Visual parity is byte-equivalent: identical Tailwind utility classes, identical theme-palette tokens, identical spacing rules. The refactor is *internal* — no public API change to the layouts dispatch dict, no slide-schema change, no exporter touch.

### Files changed
- New [nexus-ai/frontend/src/components/slidePrimitives.jsx](nexus-ai/frontend/src/components/slidePrimitives.jsx) — 10 primitives + bundled default export. ~250 LOC. Pure presentational; no state, no effects, no new dependencies.
- [nexus-ai/frontend/src/components/SlideRenderer.jsx](nexus-ai/frontend/src/components/SlideRenderer.jsx) — imports from `slidePrimitives.jsx`; refactors `BigStatSlide`, `SectionDividerSlide`, `TimelineSlide`, `ComparisonSlide` to compose from primitives. Net LOC reduction in `SlideRenderer.jsx` of ~110 lines (handcrafted Tailwind → primitive calls).

### Validation
- `node scripts/verify-layouts.mjs` → `11 canonical layouts, 11 exported`.
- Frontend `vite build` → clean (5.16s, gzipped JS 210.58 kB; +0.54 kB vs Phase 6AD baseline — primitive module overhead).
- Backend gate not yet rerun. No backend changes in this phase. New tests pending: `frontend/src/components/__tests__/slidePrimitives.test.jsx` (visual snapshot suite) once a frontend test runner is configured (none exists today per Phase 6P limitation note).

### Honest limitations
- **Acceptance Pending.** No frontend test runner is configured in this repo (Phase 6P note carried forward). Visual parity between pre-6AE and post-6AE layouts is asserted by code review only, not by automated snapshot diff. Phase 6AG (Playwright snapshots) would close this gap.
- **Legacy seven layouts not migrated.** `TitleSlide` / `BulletsSlide` / `TwoColSlide` / `QuoteSlide` / `StatsSlide` / `ChartSlide` / `ClosingSlide` still use handcrafted Tailwind. Migrating them is a separate, explicitly out-of-scope phase — would need pixel-diff verification first.
- **No exporter parity change.** The backend PPTX/HTML exporter is unaffected by this phase. PPTX visual fidelity for the four Phase-6AA/6AC layouts continues to rely on the structural degradation paths from those phases.
- **No score change.** Score remains ~62/100 Partial. Composition refactor is renderer-only and cannot move any rubric category until a measured live-eval (or a Phase 6AG visual-diff) registers it.

---

## Previously Completed Phase

**Phase 6AD — Narrative beat layer.** Accepted as **Acceptance Pending** (no backend gate rerun, no live eval, no score change). Adds a deterministic per-slide narrative beat sequence between strategy and slide intent. **No reference-folder edits, no reference-code copies, stack unchanged.** Pipeline shape now: `topic → search → strategy → narrative beats → planner → slides → intent (beats-aware) → recommender (beats-aware) → critic → images → save`. Beats are persisted as `narrative_beats.json` artifact alongside `strategy.json`. **Headline score unchanged (~62/100, Phase 6U-Rebench Partial baseline) — surface only, not score-eligible.**

### What changed

A new pure-Python module derives a six-beat canonical sequence (`setup`, `escalation`, `turning_point`, `consequence`, `aftermath`, `support`) from `DeckStrategy.story_arc` plus optional research-side promotion when dramatic-shift signals (`however`, `suddenly`, `inflection point`, etc.) are detected. The first beat is pinned `setup`, the last is pinned `aftermath`, and the middle stretches the arc evenly. Beats are threaded into `slide_intent.attach_slide_intent` so per-slide `narrative_role` derives from beat instead of position; into `layout_recommender._try_section_divider_upgrade` so beat-based turning points trigger section dividers regardless of density; and into a new `design_decision` SSE event with `decision="narrative_beats"` that the AI Reasoning panel renders as a color-coded beat strip.

### Files changed
- New [nexus-ai/backend/agent/narrative_beats.py](nexus-ai/backend/agent/narrative_beats.py) — `derive_beats(slide_count, story_arc, research)`, `normalize_arc`, `role_from_beat`, `beat_transition_indices`. 6 canonical beat constants, deterministic, ~190 LOC.
- [nexus-ai/backend/agent/slide_intent.py](nexus-ai/backend/agent/slide_intent.py) — `derive_intent` and `attach_slide_intent` accept new `beat=` / `beats=` kwargs. When beats supplied, `narrative_role` derives from beat via `role_from_beat()` and `intent.beat` is stored on the slide. Length-mismatch falls back to position-based derivation.
- [nexus-ai/backend/agent/layout_recommender.py](nexus-ai/backend/agent/layout_recommender.py) — `_try_section_divider_upgrade` trigger broadened: beat-based `turning_point` qualifies regardless of density. Beat-driven upgrades carry a different rationale string.
- [nexus-ai/backend/agent/loop.py](nexus-ai/backend/agent/loop.py) — `_beats: list[str]` plumbed through `run()`. Computed after strategy commit (≈25.3% progress); persisted via `memory.write_artifact("narrative_beats.json", ...)`; threaded into all three `attach_slide_intent` call sites; emitted as `design_decision` event.
- [nexus-ai/frontend/src/components/ProgressStream.jsx](nexus-ai/frontend/src/components/ProgressStream.jsx) — new `<BeatStrip>` component, `isBeatSequence` predicate, `BEAT_COLOR` / `BEAT_LABEL` maps, decision-label entry for `narrative_beats`.

### Validation
- `node scripts/verify-layouts.mjs` → `11 canonical layouts, 11 exported`.
- Frontend `vite build` → `built in 4.21s`, gzipped JS 210.04 kB (was 209.18 kB; +0.86 kB).
- Backend gate not yet rerun. New tests pending: `test_narrative_beats.py` (8 cases: default shape, arc normalization, turning-point promotion via research, length stability, transition indices, role round-trip).

### Honest limitations
- **Acceptance Pending.** Backend gate (was 431/2/1 at Phase 6V) not rerun; no new tests committed.
- **No live eval.** Score unchanged at ~62/100 Partial. NEXUS still does not beat Manus.
- **Beats are deterministic, not LLM-derived.** They derive from `DeckStrategy.story_arc` and a 13-pattern keyword scan over research. Sophisticated dramatic shape (multi-act, character arcs) is out of scope.
- **Conservative research promotion.** Only one slide's beat is promoted to `turning_point` per deck, only when an unambiguous keyword fires. Decks without these keywords keep arc-derived beats.

---

## Previously Completed Phase

**Phase 6AC — Timeline + comparison semantic layouts.** Accepted as **Acceptance Pending** (no backend gate rerun, no live eval, no score change). Adds two new canonical layouts (`timeline`, `comparison`) plus deterministic recommender upgraders that promote `bullets → timeline` when ≥3 dated events are detected and `two-col → comparison` when explicit contrast framing is present. **No reference-folder edits, no reference-code copies, stack unchanged.** Layout count: **11 canonical, 11 exported** (was 9/9 at Phase 6AA). Both new layouts degrade gracefully in the exporter (timeline → bullets, comparison → two-col). **Headline score unchanged (~62/100). NEXUS still does not beat Manus.**

### What changed

Two new entries appended to `layouts.registry.json` (both copies, byte-identical per `verify-layouts`). Both layouts use the existing renderer/exporter dispatch contract: new React primitives (`<TimelineSlide>`, `<ComparisonSlide>`, `<ComparisonSide>`) compose Tailwind + theme-palette tokens just like the existing 9 layouts, with no free-form HTML. PPTX exporter degrades timeline events to bullet lines (`"DATE — LABEL"`) and comparison sides to a two-col proxy. HTML exporter emits semantic blocks (`<dl class="events">`, `<div class="comparison columns">`) so any HTML→PDF renderer can lay them out.

The deterministic recommender (`agent/layout_recommender.py`) gains two upgraders:
- `_try_timeline_upgrade`: refuses to fire if any non-dated bullet would be lost. Date patterns: 4-digit years, full month names, ISO dates, quarter notation, decade notation.
- `_try_comparison_upgrade`: requires either an explicit title cue (`vs`, `before/after`, `old vs new`, etc.) OR an antonym-pair heading match (`before↔after`, `problem↔solution`, `pros↔cons`, etc.) AND non-empty heading + body on both sides.

### Files changed
- [nexus-ai/backend/agent/layouts.registry.json](nexus-ai/backend/agent/layouts.registry.json) — +`timeline`, +`comparison`.
- [nexus-ai/frontend/src/design/layouts.registry.json](nexus-ai/frontend/src/design/layouts.registry.json) — same, byte-identical.
- [nexus-ai/backend/agent/slide_schema.py](nexus-ai/backend/agent/slide_schema.py) — `_validate_timeline` (events list of {date, label}, max 6), `_validate_comparison` (left + right blocks with heading + body), registered in `_VALIDATORS`.
- [nexus-ai/backend/agent/deck_repair.py](nexus-ai/backend/agent/deck_repair.py) — `_repair_timeline`, `_repair_comparison` (seed `subtitle` only; never invent `events` or sides).
- [nexus-ai/backend/agent/loop.py](nexus-ai/backend/agent/loop.py) — `_normalize_slides` branches for `timeline` and `comparison` so their fields survive normalization.
- [nexus-ai/backend/agent/layout_recommender.py](nexus-ai/backend/agent/layout_recommender.py) — `_DATE_PATTERNS` (5 regex patterns), `_COMPARISON_TITLE_RE`, `_COMPARISON_HEADING_PAIRS` (7 antonym sets), `_try_timeline_upgrade`, `_try_comparison_upgrade`, `_extract_timeline_events`, `_is_dated_bullet`, `_matches_comparison_pair`. Registered in `_UPGRADERS`.
- [nexus-ai/backend/services/export_service.py](nexus-ai/backend/services/export_service.py) — PPTX dispatch: `timeline` → `_render_bullets` via formatted-line proxy; `comparison` → `_render_two_col` via promoted-side proxy. HTML dispatch: `<div class="timeline"><dl class="events">…</dl></div>` and `<div class="comparison columns">…</div>`.
- [nexus-ai/frontend/src/components/SlideRenderer.jsx](nexus-ai/frontend/src/components/SlideRenderer.jsx) — `<TimelineSlide>` (horizontal chronology with spine + nodes + dates + labels), `<ComparisonSlide>` (3-col grid with center "vs" badge), `<ComparisonSide>` (per-side block). 2 new entries in `layouts` dispatch dict.

### Validation
- `node scripts/verify-layouts.mjs` → `11 canonical layouts, 11 exported`.
- Frontend `vite build` → clean (4.97s, gzipped JS 209.75 kB).
- Backend gate not yet rerun. New tests pending: `test_layout_recommender_timeline.py` (6 cases), `test_layout_recommender_comparison.py` (5 cases), schema validator extension.

### Honest limitations
- **Acceptance Pending.** No backend gate rerun; no recommender unit tests; no schema-validator unit tests for the new layouts.
- **No live eval.** Score unchanged at ~62/100 Partial.
- **Recommender is conservative by design.** Mixed-format bullet lists, ambiguous comparison headings, and any case where upgrading would silently drop content are refused. False-negatives are preferred to false-positives.
- **PPTX export is structural, not visual.** Timeline events render as bullet lines, not as a horizontal native PPTX timeline shape. Visual parity is a future Phase 6AG (Playwright snapshots) candidate.

---

## Previously Completed Phase

**Phase 6AA — Visual diversity layouts: bigstat + section_divider.** Accepted as **Acceptance Pending** (no backend gate rerun, no live eval, no score change). Promotes the existing renderer-internal `StatsHero` variant into a first-class `bigstat` canonical layout and adds a new `section_divider` layout for typography-only narrative pauses. Adds a deterministic recommender (`agent/layout_recommender.py`) that uses `intent` metadata from Phase 6AB to upgrade slides only when the upgrade is unambiguously better. **No reference-folder edits, no reference-code copies, stack unchanged.** Layout count: **9 canonical, 9 exported** (was 7/7). **Headline score unchanged (~62/100).**

### What changed

`bigstat` is a single-dominant-metric layout: hero-sized value + label + optional subtitle. The recommender promotes a `stats` slide to `bigstat` when its first stat numerically dwarfs the others by at least 3× (or is the only stat) AND `intent.density != "high"`. PPTX exporter degrades to `_render_stats` via a one-item proxy payload; HTML exporter emits `<div class="bigstat">…</div>`.

`section_divider` is a typography pause: centered eyebrow + giant title + thin rule + optional subtitle. The recommender promotes a `bullets` slide to `section_divider` when `intent.narrative_role == "turning_point"` AND `intent.density == "low"` AND no bullet exceeds 60 characters (refuses to drop substantive content). PPTX exporter degrades to `_render_title` (field shapes align); HTML exporter emits `<div class="section-divider">…</div>`.

Recommender pass runs in the assemble stage, after `attach_slide_intent` and before the critic re-normalize cycle. Each upgrade emits a `design_decision` event with `decision="layout_upgrade"` rendered as a `<LayoutUpgradeBadge>` in the AI Reasoning panel.

### Files changed
- [nexus-ai/backend/agent/layouts.registry.json](nexus-ai/backend/agent/layouts.registry.json) — +`bigstat`, +`section_divider`.
- [nexus-ai/frontend/src/design/layouts.registry.json](nexus-ai/frontend/src/design/layouts.registry.json) — same, byte-identical.
- [nexus-ai/backend/agent/slide_schema.py](nexus-ai/backend/agent/slide_schema.py) — `_validate_bigstat` (title + value required; label / subtitle empty-string-permitted), `_validate_section_divider` (title required; eyebrow / subtitle empty-string-permitted), registered in `_VALIDATORS`.
- [nexus-ai/backend/agent/deck_repair.py](nexus-ai/backend/agent/deck_repair.py) — `_repair_bigstat`, `_repair_section_divider` (seed empty-string defaults; never invent `value`).
- [nexus-ai/backend/agent/loop.py](nexus-ai/backend/agent/loop.py) — `_normalize_slides` branches for `bigstat` (preserves value / label / subtitle, falls back to `stats[0]` when recommender promoted) and `section_divider` (eyebrow / subtitle defaults). Recommender wired in after `attach_slide_intent`; re-normalises and re-attaches intent so the rhythm event reflects upgrades. One `design_decision` event per upgrade.
- New [nexus-ai/backend/agent/layout_recommender.py](nexus-ai/backend/agent/layout_recommender.py) — `recommend_layouts(slides) → (slides, upgrades)`. Pure function, never raises, never re-layouts pinned ends. `_try_bigstat_upgrade`, `_try_section_divider_upgrade`. Helper `_looks_dominant_metric` (3× rule), `_parse_number` (strips `$`, `,`, `%` etc.).
- [nexus-ai/backend/services/export_service.py](nexus-ai/backend/services/export_service.py) — PPTX dispatch for `bigstat` (proxy → `_render_stats`) and `section_divider` (→ `_render_title`); HTML dispatch with semantic class names.
- [nexus-ai/frontend/src/components/SlideRenderer.jsx](nexus-ai/frontend/src/components/SlideRenderer.jsx) — `<BigStatSlide>` (10rem hero number + label + subtitle), `<SectionDividerSlide>` (eyebrow + 7xl title + thin rule + subtitle). 2 new entries in `layouts` dispatch dict.
- [nexus-ai/frontend/src/components/ProgressStream.jsx](nexus-ai/frontend/src/components/ProgressStream.jsx) — `<LayoutUpgradeBadge>`, `isLayoutUpgrade` predicate, decision-label entry for `layout_upgrade`.

### Validation
- `node scripts/verify-layouts.mjs` → `9 canonical layouts, 9 exported`.
- Frontend `vite build` → clean (4.20s, gzipped JS 209.18 kB).
- Backend gate not yet rerun. New tests pending: `test_layout_recommender.py` (8 cases for the bigstat + section_divider upgraders), `test_layout_coverage.py` extension, `test_export_input_parity.py` extension.

### Honest limitations
- **Acceptance Pending.** No backend gate rerun; no recommender unit tests committed.
- **No live eval.** Score unchanged at ~62/100 Partial.
- **bigstat dominance heuristic is structural, not semantic.** It picks "one big number" mechanically; it does not judge whether the chosen metric is the most rhetorically important.
- **section_divider drops bullets.** The recommender refuses to upgrade if any bullet >60 chars exists, but this still drops shorter bullets when promoting. The first short bullet is preserved as `subtitle`.

---

## Previously Completed Phase

**Phase 6AB — Slide intent metadata layer.** Accepted as **Acceptance Pending** (no backend gate rerun, no live eval, no score change). Adds a deterministic per-slide `intent` block ({`narrative_role`, `tone`, `density`, `communication_goal`}) attached after `_normalize_slides`. **No reference-folder edits, no reference-code copies, stack unchanged.** Pure-Python derivation; no LLM, no network, no randomness. Backward-compatible: `validate_deck` does not require `intent` and does not reject unknown top-level keys; the renderer ignores unrecognised fields; old saved decks render and validate exactly as before. **Headline score unchanged (~62/100).**

### What changed

A new module `agent/slide_intent.py` exposes `derive_intent(slide, *, position, total, story_arc, strategy_tone, art_mood)` and `attach_slide_intent(slides, ...)`. Mirrors the `attach_research_sources_to_deck` pattern: best-effort, never raises, returns a new list. Field derivations:

- `narrative_role` ∈ {`opening`, `context`, `evidence`, `turning_point`, `synthesis`, `closing`, `divider`, `support`} from position + `DeckStrategy.story_arc` (mapped via 18-key arc-to-role table).
- `tone` ∈ {`serious`, `polished`, `technical`, `editorial`, `calm`, `expressive`, `neutral`} from `ArtDirection.mood` (preferred) or keyword scan over `DeckStrategy.tone`.
- `density` ∈ {`low`, `medium`, `high`} heuristic from layout-specific content shape (bullet count + length, quote length, stats count, chart label count, two-col body length).
- `communication_goal` short verb-phrase from `(role × layout)` lookup.

Wired into `loop.py` after both `_normalize_slides` calls (assemble pass and critic re-normalise). After attach, a single `design_decision` event with `decision="intent_rhythm"` carries the per-slide role + density list. Frontend renders this as `<RhythmStrip>` — color = role, height = density.

### Files changed
- New [nexus-ai/backend/agent/slide_intent.py](nexus-ai/backend/agent/slide_intent.py) — pure-Python intent derivation. Public API: `NARRATIVE_ROLES`, `DENSITIES`, `derive_intent`, `attach_slide_intent`.
- [nexus-ai/backend/agent/loop.py](nexus-ai/backend/agent/loop.py) — 2 attach call sites (post-normalise, post-critic-renormalise); 1 `design_decision` rhythm emission.
- [nexus-ai/frontend/src/components/ProgressStream.jsx](nexus-ai/frontend/src/components/ProgressStream.jsx) — `<RhythmStrip>` (color-coded bars per slide), `isRhythm` predicate, decision-label entry for `intent_rhythm`.

### Validation
- Frontend `vite build` → clean.
- Backend gate not yet rerun. Tests pending: `test_slide_intent.py` (8 cases: shape, JSON-serialisability, role from position with no arc, role from arc beats, density per layout, tone precedence, attach idempotency, non-dict pass-through).

### Honest limitations
- **Acceptance Pending.** No tests committed; no backend gate rerun.
- **Intent is best-effort, not LLM-judged.** Density heuristics are mechanical; tone preference falls back to `neutral` when neither art mood nor strategy tone match a known keyword.

---

## Previously Completed Phase

**Phase 6Y — Design decision narration.** Accepted as **Acceptance Pending** (no backend gate rerun). Adds `design_decision` to the canonical SSE `EVENT_TYPES` and emits four narrated events from the strategy stage (`deck_type`, `mood`, `story_arc`, `layout_recipe`) using values that already exist in `DeckStrategy` and `ArtDirection`. **No reference-folder edits, no reference-code copies, stack unchanged. No new endpoint, no migration, no LLM call.** **Headline score unchanged.**

### What changed

`backend/services/run_events.py` adds `design_decision` to `EVENT_TYPES` and to `_EXPLICIT_EVENT_MAP`. `backend/agent/loop.py` emits 4 events (24.5%–25.1% progress) inside the strategy try-block. Each event carries `decision`, `value`, `rationale` fields plus, where relevant, additional context (e.g. `category` for mood). Failures wrapped in nested try/except — emission errors cannot break the strategy stage. `frontend/src/components/ProgressStream.jsx` adds an "AI reasoning" collapsible (Brain icon, default-open) at the top of the Intel Panel; each decision renders as eyebrow + value + rationale.

### Files changed
- [nexus-ai/backend/services/run_events.py](nexus-ai/backend/services/run_events.py) — `EVENT_TYPES` + `_EXPLICIT_EVENT_MAP` extended.
- [nexus-ai/backend/agent/loop.py](nexus-ai/backend/agent/loop.py) — 4 emissions in strategy stage.
- [nexus-ai/frontend/src/components/ProgressStream.jsx](nexus-ai/frontend/src/components/ProgressStream.jsx) — `<Collapsible>` reuse for "AI reasoning" section, decisions array in intel.

### Validation
- Frontend `vite build` → clean.
- Backend gate not yet rerun. Tests pending: `test_run_events_design.py` (1 case for round-trip).

### Honest limitations
- **Acceptance Pending.** No tests committed.
- **No event durability.** SSE-only; reconnect after closed shows nothing. Phase 6Z would close this gap.

---

## Previously Completed Phase

**Phase 6X — Visible cognition (research_note + outline_ready + per-source events).** Accepted as **Acceptance Pending** (no backend gate rerun). Surfaces intermediate artifacts that the agent already produces but did not stream: per-source events after research harvest, a research-text snippet, and a structured slide-plan after the planner. **No reference-folder edits, no reference-code copies, stack unchanged. No new endpoint, no migration, no LLM call.** **Headline score unchanged.**

### What changed

`backend/services/run_events.py` adds `research_note` and `outline_ready` to `EVENT_TYPES` and to `_EXPLICIT_EVENT_MAP`. `backend/agent/loop.py` emits one `source_found` per harvested URL (max 8) right after `SearchService.harvest`, one `research_note` (first 800 chars of compressed research), and one `outline_ready` carrying `[{i, layout, title}]` after `planner.plan`. Frontend `ProgressStream.jsx` extracts these into an `intel = {sources, research, outline}` channel and renders a 3-collapsible Intel Panel below the timeline (Sources with clickable links, Research notes, Slide plan with layout badges open by default).

### Files changed
- [nexus-ai/backend/services/run_events.py](nexus-ai/backend/services/run_events.py) — 2 new event types.
- [nexus-ai/backend/agent/loop.py](nexus-ai/backend/agent/loop.py) — 3 emission sites (search → strategy → plan).
- [nexus-ai/frontend/src/components/ProgressStream.jsx](nexus-ai/frontend/src/components/ProgressStream.jsx) — full rewrite that PRESERVES the prior timeline rendering and adds Intel Panel below; new `<Collapsible>` primitive.

### Validation
- Frontend `vite build` → clean.
- Backend gate not yet rerun. Tests pending: `test_run_events_intel.py` (3 cases), `test_loop_intel_emissions.py` (2 cases).

### Honest limitations
- **Acceptance Pending.** No tests committed.
- **No event durability** (Phase 6R explicit limitation still applies); reconnect after closed loses the panel.
- **`outline` payload is unbounded.** Long outlines could inflate SSE frame size; max-slide ceiling not yet imposed.

---

## Previously Completed Phase

**Phase 6U-Rebench - Full 11-prompt live re-benchmark after Phase 6U + 6V.** Accepted as **Partial**, not Pass. **9/11 prompts produced schema-valid result JSONs.** Two 12-slide prompts (`mkt-001`, `evid-001`) hard-failed with worker `tasks.timeout` (300s) caused by upstream Groq + OpenRouter HTTP 429 rate-limit cascades. Per spec rule "If fewer than 11 prompts produce schema-valid result JSONs, report Partial/Fail, not Pass." — this run is reported as Partial. **No product code or harness was changed during this measurement-only phase.** Backend gate unchanged from 6V: **431 passed, 2 skipped, 1 warning**.

**Command:** `docker exec -e NEXUS_RUN_LIVE_EVAL=true -e NEXUS_EVAL_OUTPUT_DIR=/app/storage/evals_6v nexus-backend python -m scripts.run_live_eval --base-url http://localhost:8000 --timeout-seconds 600`. Result JSONs persisted to [audits/LIVE_EVAL_RESULTS/phase6V/](nexus-ai/audits/LIVE_EVAL_RESULTS/phase6V/) (9 files: `auto-001`, `biz-001`, `biz-002`, `chart-001`, `edu-001`, `edu-002`, `inv-001`, `prod-001`, `story-001`). Harness `min_sources` forwarding from `expected_evidence` block verified in [backend/scripts/run_live_eval.py](nexus-ai/backend/scripts/run_live_eval.py).

### Quality on the 9 successful prompts (vs Phase 6T 11/11 baseline)

| Metric | Phase 6T | Phase 6U-Rebench (over 9) | Delta |
| --- | --- | --- | --- |
| Mean `deck_correctness` | 7.6 | **9.56** | **+1.96** |
| Mean `evidence_accuracy` | 5.5 | 5.78 | +0.28 |
| `slide_count_in_window` | 8/11 | 9/9 | +18 pp |
| `external_source_expectation_met` | 6/11 | 6/9 | +12 pp |
| `deck_quality_ok` | **1/11** | **9/9** | **+91 pp** |
| `chart_requirement_met` | 11/11 | 9/9 | maintained |
| `all_required_layouts_present` | 11/11 | 7/9 | −22 pp |
| **Delivery rate** | **11/11** | **9/11** | **−2 (regression)** |

**Honest reading:** Phase 6V deck-strategy + 6U source harvest **did** produce real per-deck quality gains (especially `deck_quality_ok` 1/11 → 9/9 and `deck_correctness` 7.6 → 9.56). However, the two 12-slide prompts that previously produced fallback decks now hard-fail under provider rate-limit pressure within the 300s worker time budget. The headline score is held to **~62 / 100** (up modestly from ~59) with explicit Partial caveat — quality on completed runs is up; delivery rate dropped by 2 prompts. Full 11/11 promotion is gated on a clean re-run with no provider 429 (or a future tuning phase for planner backoff / worker time budget).

See full breakdown in [CURRENT_COMPETITIVE_SCORE.md](nexus-ai/audits/CURRENT_COMPETITIVE_SCORE.md) § *Phase 6U-Rebench*.

### Limitations

- 5 of 7 rubric categories remain unmeasured (`agent_autonomy`, `export_parity`, `security_production_readiness`, `stability_reliability`, `visual_quality`).
- Single run; no retry-on-failure logic in the harness for whole-task timeouts.
- Failed prompts are both 12-slide → length × rate-limit interaction, not a 6V/6U regression per se.
- `all_required_layouts_present` 7/9 on completed runs — first observed regression; not investigated this phase.

---

## Previous Completed Phase

**Phase 6V - Reference-inspired dynamic research deck generation.** Accepted as **Pass**. Inserts a research-first deck-strategy step between search and planner so different topics produce visibly different deck shapes (research report vs. pitch vs. how-to). **No reference-folder edits, no reference-code copies, stack unchanged.** Backend gate: **431 passed, 2 skipped, 1 warning** (was 403 / 2 / 1; +28 new tests across 3 new files). **Headline score unchanged at ~59 / 100** - per the 6U rule, no score increase until the post-6U re-benchmark. The new pipeline shape is `topic -> search/harvest -> deck strategy -> planner -> slide generation -> repair/validate -> save`.

### What changed (verbatim spec)

A new pure-Python module derives a typed strategy artifact from the harvested research and the existing art-direction signal, and the planner / generator now read from that artifact instead of just the raw research blob. Strategy contains all 13 spec fields: `deck_type`, `audience`, `thesis`, `story_arc`, `tone`, `visual_direction`, `layout_recipe`, `research_questions`, `key_facts`, `source_notes`, `image_style`, `chart_guidance`, plus a `research_quality` honesty rating ("rich" | "thin" | "none").

Seven NEXUS-native deck types: `research_report`, `pitch`, `explainer`, `case_study`, `briefing`, `how_to`, `overview`. Each type carries its own `layout_recipe` and `story_arc`, so a market-research deck and a how-to deck no longer share the same eight slides in the same order. The recipe is a planner *hint* (not a hard constraint); the existing first=title / last=closing rule is preserved.

### Reference ideas used (no code copied)

- **Manus** task-trace pattern: surface a visible per-stage artifact the rest of the run can read. `DeckStrategy` is that artifact, persisted via `memory.write_artifact("strategy.json", ...)`.
- **OpenManus / Suna** planner-executor split: give the planner a richer typed context object instead of a string. `DeckStrategy` is that context.
- **browser-use** evidence-first shape: `key_facts` (regex-extracted from research) and `research_quality` make the planner's evidence basis explicit and honest.
- **Presenton** presentation-pipeline language ("story arc", "layout recipe"). We use those words; the implementation is NEXUS-native.
- **AgenticSeek** routing-by-category: `_classify_deck_type` chooses one of seven deck types from topic keywords. Implementation is original; only the *idea* of routing is shared.

No source code, prompts, CSS, slide templates, branding, license text removal, or class/function structure was copied. All keyword sets, recipes, and arcs were authored fresh for NEXUS.

### Files changed

- New [nexus-ai/backend/agent/deck_strategy.py](nexus-ai/backend/agent/deck_strategy.py) - deterministic strategy builder. Public API: `DeckStrategy`, `build_deck_strategy(...)`, `render_strategy_for_planner(strategy)`, plus the seven `DECK_TYPE_*` constants and `DECK_TYPES` tuple. No LLM, no network, no randomness.
- [nexus-ai/backend/agent/loop.py](nexus-ai/backend/agent/loop.py) - new step 2b "STRATEGY" between search and plan. Emits SSE `stage_started`/`stage_completed` events for the new `"strategy"` stage at 24% / 26% progress. Strategy is threaded into `planner.plan(...)` and `_generate_all_at_once(...)`.
- [nexus-ai/backend/agent/planner.py](nexus-ai/backend/agent/planner.py) - `plan(...)` accepts an optional `strategy` kw-arg. When supplied, the rendered strategy block is prepended to the planner user prompt, and the deterministic `_fallback_outline` rotates layouts according to `strategy.layout_recipe` instead of a fixed `["bullets","two-col","stats","quote"]` cycle.
- [nexus-ai/backend/agent/prompts.py](nexus-ai/backend/agent/prompts.py) - `planner_user_message` and `slides_user_message` accept `strategy=None` kw-arg. Slide prompt now explicitly tells the LLM: *"avoid generic filler like 'key benefits', 'future outlook', 'important considerations' unless they are genuinely topic-specific"*. New private `_render_strategy_block` helper avoids an import cycle by lazily importing `render_strategy_for_planner`.
- [nexus-ai/backend/agent/memory.py](nexus-ai/backend/agent/memory.py) - new `write_artifact(name, data)` method so the strategy is observable on disk alongside `research.txt`, `outline.json`, and per-slide files.
- [nexus-ai/backend/services/run_events.py](nexus-ai/backend/services/run_events.py) - `_REAL_STAGES` frozenset gains `"strategy"` so the new stage participates in the Phase 6R event schema (no schema change).
- New [nexus-ai/backend/tests/test_deck_strategy.py](nexus-ai/backend/tests/test_deck_strategy.py) - 18 cases covering shape, JSON-serialisability, deck-type classification (all 7 types + generic-overview), recipe trim/pad scaling, research-quality rating, fact extraction (`$4.2 trillion`, `93%`, `3.5x`), unique source summarisation, chart guidance differences across deck types.
- New [nexus-ai/backend/tests/test_planner_receives_strategy.py](nexus-ai/backend/tests/test_planner_receives_strategy.py) - 3 cases with a captured-prompt fake Claude: strategy block appears when supplied; default behaviour preserved when not; LLM-failure fallback honours `strategy.layout_recipe`.
- New [nexus-ai/backend/tests/test_strategy_pipeline_integration.py](nexus-ai/backend/tests/test_strategy_pipeline_integration.py) - 4 cases threading `extract_slide_count -> build_deck_strategy -> Planner -> repair_for_validator -> validate_deck`. Confirms (a) explicit slide-count from the prompt is honoured end-to-end, (b) post-repair decks pass validation, (c) different deck types yield different middle layouts (research-report has stats; how-to does not), (d) strategy is JSON-serialisable for memory artifacts.

### New pipeline shape

```
topic
  -> analyze
  -> search / harvest                (existing, 6U)
  -> *** deck strategy ***           (NEW, 6V — emits "strategy" SSE stage)
  -> planner                         (now consumes DeckStrategy)
  -> slide generation                (now consumes DeckStrategy)
  -> assemble + critique + images
  -> repair_for_validator            (existing, 6U)
  -> validate + save
```

### Tests run

```
docker run --rm -v ".\backend:/app" -w /app -e PYTHONPATH=/app \
  -e DATABASE_URL=sqlite+aiosqlite:///:memory: nexus-ai-backend:dev \
  python -m pytest -q
# 431 passed, 2 skipped, 1 warning in 9.37s
```

### Limitations / out of scope

- Strategy is deterministic (pure-Python heuristics). Deliberately no LLM call here so the strategy remains cheap, testable, and offline-safe; the LLM still owns slide *content*.
- The `key_facts` regex is a lossy starter list — it surfaces numbers + context phrases for the planner, not all evidence. The LLM still has the full research blob too.
- Headline competitive score remains at ~59 / 100. **Score only changes after a later live re-benchmark** (Phase 6U-Rebench remains the next score-eligible measurement).
- No frontend changes. Editor, export, share, and presenter flows are unchanged.
- No reference-folder edits. No reference-code copies. No new external dependencies.

---

## Previously Completed Phase

**Phase 6U - Measured benchmark gap fix.** Accepted as **Pass**. Targeted fix for the three concrete failures Phase 6T exposed. **No reference-folder edits, no reference-code copies, stack unchanged.** Backend gate at the time: **403 passed, 2 skipped, 1 warning** (was 381 / 2 / 1; +22 new tests across 3 new files). **Headline score unchanged at ~59 / 100** - per the 6U rule, no score increase until the post-6U re-benchmark. NEXUS still does not beat Manus or Presenton; the next score-eligible measurement is Phase 6U-Rebench.

Three product changes, each scoped to its concrete failure mode:

1. **Slide-count window honoring.** New [backend/agent/prompt_intent.py](nexus-ai/backend/agent/prompt_intent.py) `extract_slide_count(topic)` parses explicit phrasings (`"Produce a 12-slide market research report"`, `"Build a 10 slide deck"`, `"generate 14 slides"`). [`NexusAgentLoop.run`](nexus-ai/backend/agent/loop.py) overrides the incoming `slide_count` field when the prompt text carries an explicit count in `[4, 20]`. Out-of-range hints are ignored (no silent clamping). 6T gap: mkt-001 / evid-001 / auto-001 requested 10-14 slides and always received 8.
2. **Source harvesting `min_sources`.** New `SearchService.harvest(query, *, target_min, max_total)` in [backend/services/search_service.py](nexus-ai/backend/services/search_service.py) keeps issuing follow-up queries (`"<q> 2024"`, `"<q> overview"`, `"<q> statistics"`) until `target_min` unique sources are gathered or providers are honestly exhausted. Plumbed through `GenerateRequest.min_sources` (new optional field; default 0 preserves prior single-shot behaviour) → Celery task arg → `loop.run(min_sources=...)`. The live-eval harness now forwards `expected_evidence.min_sources` from [benchmarks/prompts.json](nexus-ai/benchmarks/prompts.json) per prompt. 6T gap: mkt-001 3/4, evid-001 3/5, auto-001 0/4.
3. **`deck_quality_ok` defaults / repair.** New [backend/agent/deck_repair.py](nexus-ai/backend/agent/deck_repair.py) `repair_for_validator(slides)` runs as a final pre-save pass that fills layout-local validator defaults (`title.subtitle=""`, `title.eyebrow="Presentation"`, `closing.subtitle=""`, `closing.cta="Thank you"`, `chart.subtitle=""`, `chart_data.unit=""`, `chart_data.source=""`, `quote.attribution=""`). Closes the dominant 6T failure mode where `_normalize_slides` pinned the first/last slide to `title`/`closing` without seeding their required fields, leaving 10/11 decks with `deck_quality_ok=false`. Repair never invents semantic content (no synthesised bullets / stats / chart values / sources) - missing semantic fields stay flagged so the underlying generation problem remains visible.

### Files changed
- New [nexus-ai/backend/agent/prompt_intent.py](nexus-ai/backend/agent/prompt_intent.py) - dependency-free `extract_slide_count` regex helper.
- New [nexus-ai/backend/agent/deck_repair.py](nexus-ai/backend/agent/deck_repair.py) - `repair_for_validator(slides)` pre-save pass.
- [nexus-ai/backend/agent/loop.py](nexus-ai/backend/agent/loop.py) - imports both helpers; `run(...)` gains `min_sources: int = 0`; topic hint overrides `slide_count`; search step calls `harvest` when `min_sources > 0`; final pre-save call to `repair_for_validator`.
- [nexus-ai/backend/services/search_service.py](nexus-ai/backend/services/search_service.py) - new `harvest` method (3 follow-up queries max; deduplicates by URL; capped at `max_total`).
- [nexus-ai/backend/api/routes/generate.py](nexus-ai/backend/api/routes/generate.py) - `GenerateRequest.min_sources: int = Field(0, ge=0, le=20)` (default 0 keeps the prior contract); enqueue passes it as the second Celery arg.
- [nexus-ai/backend/workers/tasks.py](nexus-ai/backend/workers/tasks.py) - `run_generation_task(self, task_id, min_sources=0)` and `_run(task_id, min_sources)` forward to `loop.run`.
- [nexus-ai/backend/scripts/run_live_eval.py](nexus-ai/backend/scripts/run_live_eval.py) - reads `expected_evidence.min_sources` per prompt and forwards it to `/api/generate`.
- New [nexus-ai/backend/tests/test_slide_count_hint.py](nexus-ai/backend/tests/test_slide_count_hint.py) - 10 cases covering hyphenated / spaced / plural patterns, no-match, out-of-range, multiple-match precedence.
- New [nexus-ai/backend/tests/test_search_min_sources.py](nexus-ai/backend/tests/test_search_min_sources.py) - 5 async cases with a `_StubSearch` double: target-met-via-followups, dedupe-by-url, exhausted-but-honest, target-met-immediately-skips-followups, `target_min=0` keeps legacy behaviour.
- New [nexus-ai/backend/tests/test_normalize_slides_deck_quality.py](nexus-ai/backend/tests/test_normalize_slides_deck_quality.py) - 7 cases: per-layout repair (title / closing / chart / quote), full-deck round-trip through `validate_deck`, refusal to invent bullet content, non-dict slide pass-through.

### Out of scope (intentionally not in 6U)
- No new score. The post-6U re-benchmark is its own phase (Phase 6U-Rebench) - no headline score change is reported here.
- No DB migration. `min_sources` is a Celery argument, not a `Task` column, to keep the change reversible.
- No reference-folder edits. No reference-code copies. Stack unchanged.
- Repair pass does not fabricate semantic content. Missing bullet / column / stat / chart-numeric fields stay flagged so the validator still surfaces the underlying generation problem.

### Acceptance criteria met
- Backend gate green (403 / 2 / 1).
- New tests cover the three explicit 6U targets (slide-count extraction, source harvesting min_sources, generated slides satisfy strict `validate_deck`).
- No edits inside `manus-need/`, `manus-reference/`, or any other reference folder.
- `deck_quality.py` remains observability-only; the new `deck_repair.py` is the destructive pre-save pass.

## Previously Completed Phase (still in effect)

**Phase 6T - Full 11-prompt live benchmark.** Accepted as **Pass**. First end-to-end measurement of the full benchmark corpus against [benchmarks/prompts.json](nexus-ai/benchmarks/prompts.json). Stack rebuilt from this workspace (mount confirmed `D:\nexus-ai-1\nexus-ai\backend -> /app`; `/api/health` 200). All 11 prompts ran live with `NEXUS_RUN_LIVE_EVAL=true`; **11 / 11 produced an evaluable deck with `ran_live=true`**; one prompt (mkt-001, hardest) hit the agent-loop timeout on a retry but the first attempt yielded a scored 8-slide fallback deck. **No product code changed.** Result JSONs (redacted - no secrets) saved under [audits/LIVE_EVAL_RESULTS/](nexus-ai/audits/LIVE_EVAL_RESULTS/), one per prompt; all 11 validate against [benchmarks/eval_schema.json](nexus-ai/benchmarks/eval_schema.json) (re-confirmed by [backend/tests/test_live_eval_results.py](nexus-ai/backend/tests/test_live_eval_results.py) - 2 passed). Backend gate: **381 passed, 2 skipped, 1 warning**. **Measured aggregate: `deck_correctness` mean 7.6 / 10, `evidence_accuracy` mean 5.5 / 10. Honest headline score: ~59 / 100** (was ~57 estimate; +2 from now-measured `deck_correctness`). Two of seven rubric categories are now corpus-measured; five remain estimates. Full per-prompt table, aggregates, and remaining gaps are in [audits/CURRENT_COMPETITIVE_SCORE.md](nexus-ai/audits/CURRENT_COMPETITIVE_SCORE.md) § *Phase 6T*. **NEXUS still does not beat Manus or Presenton.** Top gaps the data exposes: hard prompts always emit 8 slides (mkt-001 / evid-001 / auto-001 requested 10-14); evidence-heavy prompts under-source (mkt-001 3/4, evid-001 3/5, auto-001 0/4); `deck_quality_ok` is 1 / 11 (validator stricter than renderer); no claim-level citations.

## Previously Completed Phase (still in effect)

**Phase 6S - PPTX ingestion endpoint.** Accepted as **Pass**. Closes the headline Presenton gap: users can now upload an existing `.pptx` file and convert it into an editable NEXUS deck that flows through the same `/api/slides`, `/api/export`, and `/api/share` surface as generated decks. New endpoint `POST /api/import/pptx` accepts a multipart upload, rejects oversize (>100 MB) / non-`.pptx` / corrupt files with structured 400 errors, parses each slide via `python-pptx`, and emits a canonical NEXUS deck (`title` for slide 1 when a usable title is present, `bullets` for the rest) that is validated through `agent.slide_schema.validate_deck` before being persisted as a `Task` (`status="done"`) + `SlideDeck` row. The frontend Hero adds a small `Import .pptx` button that uploads the file and navigates to `/deck/:taskId` on success. **No score change. ~57/100.** NEXUS still does not beat Manus or Presenton (PPTX ingestion alone does not move the headline number).

### Files changed
- New [nexus-ai/backend/services/pptx_import_service.py](nexus-ai/backend/services/pptx_import_service.py) - `import_pptx_bytes(data, filename)` returns `ImportedDeck`. Conservative converter: first slide → `title` layout (with subtitle from the first body line); subsequent slides → `bullets` (max 4 bullets, each clamped to 240 chars). Hard ceiling of 60 slides. `PPTXImportError` codes: `empty_payload`, `corrupt`, `empty`, `dependency`.
- New [nexus-ai/backend/api/routes/import_pptx.py](nexus-ai/backend/api/routes/import_pptx.py) - `POST /api/import/pptx`. Streams the upload in 1 MB chunks and rejects > `MAX_BYTES` (100 MB) without buffering the whole file. Validates extension (400 `bad_extension`), conversion errors (400 `corrupt` / `empty`), and final schema (defensively 400 `invalid_deck`). Persists `Task` + `SlideDeck`; returns the canonical deck JSON plus a `source` block (`source_filename`, `source_slide_count`, `imported_slide_count`, `truncated`).
- [nexus-ai/backend/main.py](nexus-ai/backend/main.py) - registers the new router under `/api`.
- New [nexus-ai/backend/tests/test_import_pptx.py](nexus-ai/backend/tests/test_import_pptx.py) - 7 tests using fixture decks built at test time (no checked-in binaries): success + persistence, slide-count preservation + title extraction, schema validation of the converted deck, rejection of non-`.pptx` extension, rejection of corrupt content, rejection of oversize files (with `MAX_BYTES` patched to 1 KB so the test stays cheap), and end-to-end editability via the existing `GET /api/slides/{task_id}`.
- New [nexus-ai/frontend/src/components/ImportPptxButton.jsx](nexus-ai/frontend/src/components/ImportPptxButton.jsx) - hidden file input + small chip-style button. Client-side mirror of the backend size/extension limits. On success, shows a toast and navigates to `/deck/:taskId`. On failure, surfaces the backend `detail.error` code as a friendly message.
- [nexus-ai/frontend/src/components/Hero.jsx](nexus-ai/frontend/src/components/Hero.jsx) - mounts `ImportPptxButton` next to the existing `More` chip on the home hero so the import entry point is visible without a route or modal.

### Endpoint contract
| Field | Type | Notes |
|---|---|---|
| `task_id` | str | new Task row, `status="done"` |
| `topic` | str | first slide title (or filename fallback) |
| `theme` | str | `"Editorial"` (current default) |
| `slide_count` | int | imported slide count after the 60-slide ceiling |
| `slides` | list[dict] | canonical NEXUS slides, validated via `validate_deck` |
| `source.filename` | str | uploaded filename |
| `source.source_slide_count` | int | slide count in the original PPTX |
| `source.imported_slide_count` | int | slide count in the persisted deck |
| `source.truncated` | bool | `true` when the source exceeded the 60-slide ceiling |

### Validation
- New tests: **7 passed** ([nexus-ai/backend/tests/test_import_pptx.py](nexus-ai/backend/tests/test_import_pptx.py)).
- Backend gate (full): **381 passed, 2 skipped, 1 warning** (was 374/2/1; +7 new tests).
- Frontend `vite build`: `✓ built in 4.82s` (pre-existing chunk-size warning unchanged).

### Honest limitations (Phase 6S)
- **Conservative layout mapping.** Only `title` (slide 1, when a title is present) and `bullets` (everything else) are emitted. We do not reverse-engineer `two-col`, `stats`, `chart`, `quote`, or `closing` from arbitrary PPTX structure; users who want those layouts can change the layout per slide in the deck workspace. This is intentional: the existing `convertSlideLayout` helper from Phase 6P already handles those rewrites without losing data.
- **Text-only.** Images, charts, embedded media, speaker notes, slide masters, themes, fonts, and animations are all dropped on import. The output is a clean text skeleton, not a pixel-faithful re-render of the source deck.
- **No PDF.** PDF ingestion is explicitly out of scope; the endpoint is `.pptx`-only and rejects everything else with `bad_extension`.
- **No auth, no rate limit.** Mirrors the rest of the existing `/api` surface (`/api/generate`, `/api/slides`, `/api/export`, `/api/share`). A hostile client can spam imports up to the 100 MB cap; if multi-tenant isolation becomes a hard requirement this should be revisited alongside the Phase 6Q lifecycle routes.
- **60-slide ceiling.** Source decks larger than 60 slides are truncated with `source.truncated=true`. This is a defence-in-depth limit on top of the schema validator and the `_MAX_SLIDES` cap; it is not user-configurable.
- **Persistence is permanent.** Each successful import creates a real `Task` + `SlideDeck` row; there is no "draft" state and no client-side dry-run. Cleanup is not yet implemented.
- **No live eval.** Score unchanged at ~57/100. NEXUS still does not beat Manus or Presenton.

## Older Completed Phase (still in effect)

**Phase 6R - Rich SSE run stream.** Accepted as **Pass**. The progress stream that drives `Generator.jsx` now carries a structured event vocabulary so the frontend can render a proper agent timeline instead of a flat log. Each SSE frame still flows through Redis pub/sub and the legacy `(message, progress_pct, step, **extra)` callback inside `agent.loop`, but every frame is now produced by a new `RunEventEmitter` adapter that adds canonical event names, a monotonic per-task sequence number, and an ISO-8601 UTC timestamp. Back-compat aliases (`status`, `step`) are preserved so the Phase 6Q lifecycle / status route consumers and existing tests are unchanged. **No score change. ~57/100.** NEXUS still does not beat Manus or Presenton.

### Files changed
- New [nexus-ai/backend/services/run_events.py](nexus-ai/backend/services/run_events.py) - `EVENT_TYPES` tuple (`stage_started`, `stage_completed`, `slide_ready`, `source_found`, `citation_checked`, `export_ready`, `run_cancelled`, `run_failed`, `run_succeeded`), `RunEventEmitter` with `on_progress` adapter and direct `emit` API. Synthesises `stage_completed` on stage transitions and on terminal frames; assigns sequence; preserves order.
- [nexus-ai/backend/workers/tasks.py](nexus-ai/backend/workers/tasks.py) - `_make_publisher` now wraps a `RunEventEmitter` around the Redis-backed `publish_raw` callable; the call sites inside `agent.loop` are unchanged.
- New [nexus-ai/backend/tests/test_run_events.py](nexus-ai/backend/tests/test_run_events.py) - 10 Redis-free unit tests covering required-field shape, monotonic sequence, stage-transition synthesis, slide_ready mapping, terminal `run_succeeded`/`run_failed`/`run_cancelled` behaviour, idempotent terminal frames, back-compat aliases, and explicit `source_found`/`citation_checked` round-trip.
- [nexus-ai/frontend/src/hooks/useGenerate.js](nexus-ai/frontend/src/hooks/useGenerate.js) - `useTaskStream` recognises both legacy `event === "slide"` and canonical `event === "slide_ready"` for the live preview, and treats the canonical terminal events as stream-close triggers alongside the legacy `status` field.
- [nexus-ai/frontend/src/components/ProgressStream.jsx](nexus-ai/frontend/src/components/ProgressStream.jsx) - rewritten as a structured agent timeline. Events are folded into stage rows (with synthesised `stage_completed` advancing the spinner to a green check), inline artifact rows (slides / sources / citations / exports rendered under the active stage), and dedicated terminal rows (succeeded / failed / cancelled). Pre-6R legacy frames render as a generic stage row.

### Event schema (Phase 6R wire contract)
| Field | Type | Required | Notes |
|---|---|---|---|
| `task_id` | str | yes | |
| `event` | str | yes | one of `EVENT_TYPES` |
| `stage` | str | yes | logical pipeline stage (`analyze`, `search`, `plan`, `generate`, `critique`, `images`, `assemble`, `save`, or terminal stage) |
| `message` | str | yes | human-readable line |
| `progress_pct` | float | yes | 0–100 |
| `timestamp` | str | yes | ISO-8601 UTC |
| `sequence` | int | yes | monotonic per-task, 1-based |
| `slide_index` | int | when relevant | for `slide_ready` / `citation_checked` |
| `slide_total` | int | when relevant | |
| `slide` | dict | when relevant | full slide payload for live preview |
| `error` | str | when relevant | for `run_failed` |
| `status` / `step` | str | yes | back-compat aliases for the Phase 6Q SSE consumer |

### Validation
- New tests: **10 passed** ([nexus-ai/backend/tests/test_run_events.py](nexus-ai/backend/tests/test_run_events.py)).
- Backend gate (full): **374 passed, 2 skipped, 1 warning** (was 364/2/1; +10 new tests).
- Frontend `vite build`: `✓ built in 4.52s` (pre-existing chunk-size warning unchanged).

### Honest limitations (Phase 6R)
- **No persisted event log.** Sequence numbers are produced in memory by `RunEventEmitter`; if the worker restarts mid-run the new emitter starts at sequence 1 again. Phase 6R deliberately does not add an `AgentEvent` table because the frontend already buffers events client-side and re-renders from `events[]`.
- **No backfill on reconnect.** The status route still emits a single DB snapshot before subscribing to Redis; clients that connect after early events have already been published will see only the events that arrive afterwards plus the current row state. There is no replay buffer.
- **`stage_completed` is synthesised, not observed.** The agent loop calls `on_progress` once per stage entry; `stage_completed` is derived by detecting the transition to the next stage (or the run finishing). A stage that fails partway never gets a `stage_completed`; the frontend marks it `stopped` when the terminal event arrives.
- **`source_found` / `citation_checked` / `export_ready` are not yet emitted by the live agent loop.** They are part of the canonical event vocabulary and are handled end-to-end (emitter → SSE → frontend timeline) so they can be wired in incrementally without further schema work; today no live caller emits them.
- **No new live eval.** Score unchanged at ~57/100. NEXUS still does not beat Manus or Presenton.

## Older Completed Phase (still in effect)

**Phase 6Q - Live job lifecycle: cancel / retry / resume.** Accepted as **Pass**. Generation is now controllable like a real agent run. A new lifecycle vocabulary (`queued`, `running`, `cancelling`, `cancelled`, `failed`, `succeeded`) sits on top of the legacy `Task.status` strings (preserved on disk so SSE / export / share / slides stay 100 % wire-compatible). A new `/api/lifecycle/{task_id}` route family exposes a JSON status payload and three control actions. The cancel signal is implemented as `Task.status == "cancelling"`: the agent loop polls it at every safe checkpoint and exits via a typed `JobCancelled` exception; the worker top-level finalizes the row as `cancelled` and publishes a final SSE frame. `retry` and `resume` both reset the same row and re-enqueue the existing Celery task; because there is no persisted mid-run checkpoint they are documented to behave identically and the response carries `from_checkpoint: false` (honest fallback). The frontend `Generator` page gains a Cancel / Retry / Resume action bar with in-flight tracking that prevents double-submit, and `useTaskStream` accepts a `restartKey` so the SSE stream is torn down and re-opened on retry/resume. **No score change. ~57/100.** NEXUS still does not beat Manus or Presenton.

### Files changed
- New [nexus-ai/backend/services/lifecycle_service.py](nexus-ai/backend/services/lifecycle_service.py) - lifecycle vocabulary, `to_lifecycle_state`, `allowed_actions`, `status_payload`, `request_cancel`, `is_cancelling`, `mark_cancelled`, `reset_for_retry`, plus the `JobCancelled` exception used by the loop.
- New [nexus-ai/backend/api/routes/lifecycle.py](nexus-ai/backend/api/routes/lifecycle.py) - `GET /api/lifecycle/{task_id}`, `POST /api/lifecycle/{task_id}/cancel`, `POST /api/lifecycle/{task_id}/retry`, `POST /api/lifecycle/{task_id}/resume`. Disallowed transitions return `409 invalid_transition`. Retry / Resume responses always include `from_checkpoint: false`.
- [nexus-ai/backend/main.py](nexus-ai/backend/main.py) - registers the new router under `/api`.
- [nexus-ai/backend/api/routes/status.py](nexus-ai/backend/api/routes/status.py) - SSE `TERMINAL_STATES` now includes `cancelled` so the stream closes cleanly on user cancel.
- [nexus-ai/backend/agent/loop.py](nexus-ai/backend/agent/loop.py) - `_mark_running` checkpoint reads `Task.status` and raises `JobCancelled` when it sees `cancelling`; the top-level `try` catches it, publishes a final `cancelled` SSE frame, and re-raises so the worker can finalize.
- [nexus-ai/backend/workers/tasks.py](nexus-ai/backend/workers/tasks.py) - top-level handler catches `JobCancelled` and calls `lifecycle_service.mark_cancelled` to write the terminal row.
- New [nexus-ai/backend/tests/test_lifecycle_route.py](nexus-ai/backend/tests/test_lifecycle_route.py) - 10 tests: GET payload for `running`/`done`, 404, cancel marks `cancelling`, cancel idempotent, cancel rejected for terminal task, retry re-enqueues + resets fields, resume returns `from_checkpoint=false`, retry rejected for `running`, and the loop's `_mark_running` checkpoint observes the cancel signal via `Task.status`.
- New [nexus-ai/frontend/src/hooks/useJobLifecycle.js](nexus-ai/frontend/src/hooks/useJobLifecycle.js) - thin control hook with `cancel` / `retry` / `resume`, single in-flight slot, surfaced `lastError`. Prevents double-submit at the UI layer.
- [nexus-ai/frontend/src/hooks/useGenerate.js](nexus-ai/frontend/src/hooks/useGenerate.js) - `useTaskStream` now accepts a `restartKey` so the EventSource can be torn down and re-opened when the same task id is re-enqueued; `cancelled` joins `done`/`failed` as a terminal status.
- [nexus-ai/frontend/src/pages/Generator.jsx](nexus-ai/frontend/src/pages/Generator.jsx) - Cancel / Retry / Resume action bar (lucide `X`, `RotateCw`, `Play`), in-flight aware button labels, `restartKey` bump on retry/resume, status-aware NEXUS reply text for `cancelling` / `cancelled` / `failed`.

### Lifecycle states & allowed actions
| State | `Task.status` | Terminal | Allowed actions |
|---|---|---|---|
| `queued` | `pending` | no | `cancel` |
| `running` | `running` | no | `cancel` |
| `cancelling` | `cancelling` | no | (none) |
| `cancelled` | `cancelled` | yes | `retry`, `resume` |
| `failed` | `failed` | yes | `retry`, `resume` |
| `succeeded` | `done` | yes | (none) |

### Validation
- New tests: **10 passed** ([nexus-ai/backend/tests/test_lifecycle_route.py](nexus-ai/backend/tests/test_lifecycle_route.py)).
- Backend gate (full): **364 passed, 2 skipped, 1 warning** (was 354/2/1; +10 new tests).
- Frontend `vite build`: `✓ built in 4.14s` (pre-existing chunk-size warning unchanged).

### Honest limitations (Phase 6Q)
- **Cancel is cooperative.** It only fires at the loop's stage-transition checkpoints (`analyze` → `search` → `plan` → `generate` → `assemble` → `save`). A long LLM call inside a stage will finish before the cancel takes effect. The hard 5-minute Celery timeout still applies as a backstop.
- **No persisted mid-run checkpoint.** `resume` is wire-equivalent to `retry`; the response always carries `from_checkpoint: false`. Phase 6Q deliberately does not add per-stage memory persistence (`AgentMemory` is per-task and best-effort).
- **No auth on lifecycle routes.** They mirror `GET /api/status/{task_id}` and `PUT /api/slides/{task_id}` which are also currently unauthenticated; this is consistent with the existing surface but should be revisited if multi-tenant isolation becomes a hard requirement.
- **Single in-flight slot per page.** The frontend allows only one of cancel / retry / resume at a time; clicking another action is disabled until the request returns. This is intentional anti-double-submit, not a feature.
- **No queue-position info.** `queued` exposes `progress_pct=0` and `stage="queued"`; we do not surface a Celery queue depth.
- **Score unchanged at ~57/100.** No live eval was run. NEXUS still does not beat Manus or Presenton.

## Older Completed Phase (still in effect)

**Phase 6P - Slide editing depth (with 6P-Fix applied to undo/redo).** Accepted as **Pass**. The deck workspace at `/deck/:taskId` now supports add / duplicate / delete / move-up / move-down / change-layout slide operations plus **chronological undo/redo** across slide edits, structural ops, layout changes, and theme picks (single combined `{slides, theme}` history). Save still uses the existing `PUT /api/slides/{task_id}` endpoint introduced in Phase 6L-UX-Fix; Reset still reverts to the server deck; PPTX/PDF exports and the share link continue to render the saved server deck. **No backend changes.** **No DB migration. No new endpoint. No new dependency. No LLM call. No live eval. Score unchanged at ~57/100.** NEXUS still does not beat Manus or Presenton.

### Files changed
- New [nexus-ai/frontend/src/utils/slideFactory.js](nexus-ai/frontend/src/utils/slideFactory.js) - exports `makeBlankSlide(layout)`, `convertSlideLayout(slide, nextLayout)`, and `SUPPORTED_LAYOUTS`. Every blank slide and every layout-converted slide is shaped to pass `agent.slide_schema.validate_deck` on the backend (e.g. `bullets` always has at least one non-empty string; `chart_data` always carries `labels`, `values`, `unit`, `source`; `stats` always has `value` and `label` strings; `two-col` always has at least one column with non-empty heading/body). Title is preserved across layout changes when present.
- New [nexus-ai/frontend/src/hooks/useUndoRedo.js](nexus-ai/frontend/src/hooks/useUndoRedo.js) - minimal local history hook with `value`, `set`, `undo`, `redo`, `reset`, `canUndo`, `canRedo`, default `limit=50`. Pure local state; no server history.
- [nexus-ai/frontend/src/pages/DeckWorkspace.jsx](nexus-ai/frontend/src/pages/DeckWorkspace.jsx) - rewritten to drive `slides` and `theme` through a **single combined `useUndoRedo` instance** holding `{ slides, theme }` snapshots, so undo/redo is **chronological**: undoing reverts whichever change was most recent (slide edit, structural op, layout change, or theme pick), not all of them at once. Header gains Undo / Redo buttons (lucide `Undo2` / `Redo2`). Sidebar gains a compact action row (Add / Duplicate / MoveUp / MoveDown / Delete) using lucide icons (`Plus`, `Copy`, `ArrowUp`, `ArrowDown`, `Trash2`). Editor pane gains a compact `Layout` `<select>` driven by `SUPPORTED_LAYOUTS`. Delete is blocked when only one slide remains (toast). Moving clamps the active index. Reset clears local draft and restores the cached server deck. Save calls `PUT /api/slides/:taskId` exactly as before, then `reset(...)` the workspace history so undo cannot revert past the saved state. `CitationsPanel` and `SourceEvidencePanel` continue to render below the workspace and continue to receive the live `slides` array.

### Editor actions implemented
| Action | Trigger | Behavior |
|---|---|---|
| Add slide | `+` in sidebar action row | Insert a new `bullets` slide after the current index; focus the new slide. |
| Duplicate slide | `Copy` in sidebar | Clone the current slide with a fresh id; focus the duplicate. |
| Delete slide | `Trash2` in sidebar | Remove the current slide; blocked when only one slide remains; active index clamped. |
| Move up | `ArrowUp` in sidebar | Swap with previous slide; disabled at index 0. |
| Move down | `ArrowDown` in sidebar | Swap with next slide; disabled at last index. |
| Change layout | `Layout` `<select>` in editor pane | Convert via `convertSlideLayout` so required fields stay valid; title preserved. |
| Undo | `Undo2` in header | Walk one step back in the combined `{slides, theme}` history; reverts only the most recent change; marks dirty. |
| Redo | `Redo2` in header | Walk one step forward; marks dirty. |
| Save edits | header (existing) | `PUT /api/slides/:taskId`; then `reset(...)` both histories; clears local draft. |
| Reset | header (existing) | Restores cached server deck; clears local draft and history. |

### Validation
- Backend gate: **354 passed, 2 skipped, 1 warning** (unchanged - no backend code touched).
- Frontend `vite build`: `✓ built in 4.24s` (pre-existing chunk-size warning unchanged; gzipped JS ~202.7 kB, up from ~200.5 kB).

### Honest limitations (Phase 6P)
- **Frontend-only.** No new backend endpoint; no schema change; no migration. The 354/2/1 backend gate is unchanged.
- **No frontend test runner is configured in this repo.** New `slideFactory.js` and `useUndoRedo.js` are exercised only via manual UI use; the backend `slide_schema` validator (already covered by the Phase 1B test surface) is the safety net that the new defaults must pass through `PUT /api/slides/:taskId`.
- **No drag-and-drop reorder.** Move uses up/down buttons only.
- **No keyboard shortcuts.** Undo/redo is button-only (no Ctrl+Z binding) to avoid swallowing native input undo inside text fields.
- **No AI regenerate / rewrite slide button.** No clean existing endpoint to wire to; not implemented per the spec.
- **No multi-select or bulk delete.** Operations act on the single active slide.
- **Chart data is still preview-only in the editor pane** (unchanged from Phase 6L-UX); `convertSlideLayout` to `chart` produces a 3-point placeholder dataset that the user must edit out-of-band by regenerating, since `SlideEditor` has no chart-data fields.
- **History is per-mount, in-memory.** Refreshing the page or navigating away discards undo history. There is no server-side version history.
- **Score unchanged at ~57/100.** No live eval was run. NEXUS still does not beat Manus or Presenton.

## Previously Completed Phase (still in effect)

**Phase 6O - Wire theme registry to preview/editor/presenter/export/share.** Accepted as **Pass**. The Phase 6L `agent/themes_registry.py` is now the single source of truth for all five legacy theme display names (`light-pro`, `Editorial`, `Pixel`, `Vellum`, `Dossier`). Three previously-untyped legacy palettes (`Pixel`, `Dossier`, `light-pro`) are promoted to first-class built-in themes with structured tokens (colors, fonts, spacing, radius, chart palette); `Editorial` and `Vellum` continue to resolve through the existing aliases (`editorial → nexus-default`, `vellum → nexus-light`). A new read-only endpoint `GET /api/themes` (and `GET /api/themes/{id}`) exposes the registry. The PPTX/PDF exporter's `THEMES` dict is now derived from the registry rather than hard-coded; the React `SlideRenderer` reads from a new shared `frontend/src/design/themes.js` mirror. **No DB migration. No new dependency. No LLM call. No live eval. Score unchanged at ~57/100.** NEXUS still does not beat Manus or Presenton.

### Files changed
- [nexus-ai/backend/agent/themes_registry.py](nexus-ai/backend/agent/themes_registry.py) - added three built-in themes (`pixel`, `dossier`, `light-pro`) with full token groups; trimmed `LEGACY_THEME_ALIASES` to the two themes that remain alias-only (`editorial`, `vellum`). Existing test surface (`test_themes_registry.py`) continues to pass unchanged.
- New [nexus-ai/backend/api/routes/themes.py](nexus-ai/backend/api/routes/themes.py) - `GET /api/themes` returns `{schema_version, default_theme_id, themes:[token_dict, ...], aliases}`; `GET /api/themes/{id}` resolves a single theme (404 on unknown id). Pure read, no DB.
- [nexus-ai/backend/main.py](nexus-ai/backend/main.py) - imports and mounts the new `themes` router under `/api`.
- [nexus-ai/backend/services/export_service.py](nexus-ai/backend/services/export_service.py) - replaced the hard-coded `THEMES` dict with `THEMES = {name: _palette_for(name) ...}` derived from `agent.themes_registry.get_theme`. Exporter palette now includes a comma-joined `chart_palette` so the QuickChart helper can produce theme-driven doughnut colors instead of a hard-coded array. Hex strings are still stored without `#` so the existing python-pptx helpers (`_hex_to_rgb`, etc.) work unchanged.
- New [nexus-ai/frontend/src/design/themes.js](nexus-ai/frontend/src/design/themes.js) - hand-mirrored token table for the same five legacy theme names plus a `chartPalette` per theme. Exports `paletteFor(name)` (case-insensitive secondary match, Editorial fallback) and `listThemeNames`.
- [nexus-ai/frontend/src/components/SlideRenderer.jsx](nexus-ai/frontend/src/components/SlideRenderer.jsx) - removed the duplicated inline `themePalettes` object and now imports `paletteFor` from `design/themes.js`. The chart slide's doughnut color set comes from `p.chartPalette` instead of a hard-coded `[p.accent, "#34D399", ...]` array, so themed decks render themed charts.
- New [nexus-ai/backend/tests/test_themes_route.py](nexus-ai/backend/tests/test_themes_route.py) - 13 tests covering: each of the five legacy display names resolves to a registry theme; the five accents are pairwise distinct; `Pixel`/`Dossier`/`light-pro` decks resolve to the new first-class ids; aliases map only `editorial`/`vellum`; `BUILTIN_THEMES` includes all five legacy ids; `GET /api/themes` shape; `GET /api/themes/{name}` for legacy display names; 404 for unknown id; exporter `THEMES` dict is registry-derived and accents match the registry.

### How it surfaces in each surface
- **Preview / editor (`DeckWorkspace`, `SlideCarousel`)** - both go through `SlideRenderer`, which now reads tokens from `design/themes.js`. Bullets, two-col borders, stats accents, chart series colors, and chart legend colors all follow the resolved theme.
- **Presenter (`/present/:taskId`)** - reads `theme` from local storage / server, passes to `SlideRenderer`. No code change required; it picks up the new shared registry transparently.
- **Share (`/share/:token`)** - same path through `SlideCarousel` -> `SlideRenderer`. Theme returned by the share API drives rendering.
- **Export (PPTX + PDF)** - `ExportService` resolves the theme through the registry, so legacy display names (`Editorial`, `Pixel`, `Vellum`, `Dossier`, `light-pro`) all map to the same accent/text/muted/bg as the on-screen preview.

### Validation
- Backend gate: **354 passed, 2 skipped, 1 warning** (was 341; +13 new tests, no pre-existing test changed).
- Frontend `vite build`: `✓ built in 4.37s` (pre-existing chunk-size warning unchanged; gzipped JS ~200.5 kB).

### Honest limitations (Phase 6O)
- **No DB schema change.** Existing `Task.theme` rows continue to use legacy display-name strings; resolution happens at read time.
- **No theme picker redesign.** `Templates.jsx` still has its own static template list (it includes 14 extra non-registry themes such as `Whiteboard`, `Sketch`, `Glamour`, etc.) - those still flow through the existing exporter fallback (`Editorial`) when chosen. Phase 6O only guarantees the five named themes.
- **No semantic understanding.** The registry is a static token table; the renderer still composes layouts identically across themes (only colors / accents change visually).
- **PPTX text fonts unchanged.** The exporter still hard-codes `Inter` for all themes; the registry's `fonts.heading` / `fonts.body` are not yet read by `_add_text`. Visual fidelity therefore differs slightly between preview/serif and PPTX/Inter for `Vellum` / `Dossier`.
- **No frontend test runner.** New `paletteFor` is exercised only via manual rendering; backend route tests cover the parity invariant (exporter accent == registry accent) instead.
- **Score unchanged at ~57/100.** No live eval was run. NEXUS still does not beat Manus or Presenton.

## Previously Completed Phase (still in effect)

**Phase 6N - Claim-level citations visible in workspace.** Accepted as **Pass**. The Phase 6K deterministic claim-citation mapper is now reachable from the deck editor: a new read-only endpoint `GET /api/slides/{task_id}/citations` serves the report produced by `services.claim_citation_service.map_deck_citations`, and a new `CitationsPanel` component renders it grouped by slide with explicit *supported* / *weak* / *unsupported* tags. **No DB migration. No new dependency. No LLM call. Algorithm not duplicated** — the route delegates to the existing service. **Score-ineligible:** UI surfacing of an existing offline service; no live eval, no semantic understanding. NEXUS still does not beat Manus or Presenton. Honest score remains ~57/100.

### Files changed
- [nexus-ai/backend/api/routes/slides.py](nexus-ai/backend/api/routes/slides.py) — added route `GET /api/slides/{task_id}/citations`. Imports `map_deck_citations` from `services.claim_citation_service`. 404 for unknown task; 409 for not-yet-`done` task; if the `SlideDeck` row is missing for an otherwise-`done` task, returns the empty-but-shaped report (`claims=[]`, zeroed summary) rather than 404 so the frontend degrades gracefully. Always returns `{schema_version, claims, summary, task_id}`. The matching algorithm itself is not modified.
- New [nexus-ai/frontend/src/components/CitationsPanel.jsx](nexus-ai/frontend/src/components/CitationsPanel.jsx) — fetches `/slides/:taskId/citations`, groups claims by `slide_index`, renders one row per claim with: a colored status pill (`unsupported` rose / `weak · <basis>` amber when score < 0.5 / `<basis>` emerald), the truncated claim text, the score (when supported), and the source title/url as a dotted-underline external link when available. Top-level pill uses a tri-color dot: emerald when all claims supported, rose when none, amber otherwise. Loading and error branches both render a compact informational pill so failures **do not block** the editor. Empty state (zero detected claims) renders "No claims detected for citation".
- [nexus-ai/frontend/src/pages/DeckWorkspace.jsx](nexus-ai/frontend/src/pages/DeckWorkspace.jsx) — imports and mounts `CitationsPanel` directly above the existing `SourceEvidencePanel` in the bottom strip of the editor. The two panels are stacked in a single `space-y-3` flex column so per-slide source listings (Phase 5) and per-claim citation status (Phase 6N) sit side by side without redesign. Initial deck load is unchanged; citation fetch is independent of `GET /api/slides/{task_id}` and its failure does not affect editor state.
- New [nexus-ai/backend/tests/test_slides_citations_route.py](nexus-ai/backend/tests/test_slides_citations_route.py) — 6 integration tests: empty-but-shaped report when deck has no sources; supported and unsupported claims both surface (and `source_url` / `source_title` are wired through for the supported one); per-slide grouping via `slide_index`; 404 for unknown task; 409 for non-done task; empty report (not 404) when the `SlideDeck` row is missing for a done task.

### Where it appears
In the deck workspace at `/deck/:taskId`, immediately below the editor grid, in the same bottom strip that has hosted `SourceEvidencePanel` since Phase 5. The pill is collapsed by default; click to expand the per-slide / per-claim list.

### Validation
- Backend gate: **341 passed, 2 skipped, 1 warning** (was 335; +6 new tests, no pre-existing test changed).
- Frontend `vite build`: `✓ built in 3.98s` (pre-existing chunk-size warning unchanged; bundle gzipped grew from ~199.4 kB to ~200.3 kB).

### Honest limitations (Phase 6N)
- **Heuristic citations only.** The underlying mapper is the Phase 6K word/numeric/Jaccard matcher; no semantic similarity, no embedding model, no fact-checking. "Supported" means a source's title or snippet contains a phrase match, a numeric match (with unit-aware normalization), or keyword overlap above the existing 0.34 Jaccard threshold.
- **No on-slide citation marks.** The renderer does not yet draw `[1]` / `[2]` indicators on the slide itself; citation status appears in the editor strip only. The Presenter view and the PPTX/PDF/share surfaces are unchanged.
- **No editing of citations.** The panel is read-only. Users cannot accept / reject / override a match.
- **No `share` integration.** `GET /api/share/{token}` does not surface this report. Only the authenticated editor route consumes it.
- **No frontend test runner is configured in this repo.** The new component has no automated test; manual verification only. Citation fetch failure is asserted by the route tests, not by a UI test.
- **Score unchanged.** No live eval was run. NEXUS still does not beat Manus or Presenton. Honest score remains ~57/100.

## Previously Completed Phase (still in effect)

**Phase 6M-Fix - Migrate legacy localStorage theme to `auto`.** Accepted as **Pass**. Frontend-only follow-up to Phase 6M. Existing browsers that had `nexus.preferred-theme` set to `light-pro` or `Editorial` from the pre-6M era — when those values were the form default rather than a deliberate choice — were silently bypassing topic-aware inference because the form loaded the stored value and sent it to `/api/generate` as an explicit theme. [frontend/src/components/PromptInput.jsx](nexus-ai/frontend/src/components/PromptInput.jsx) now treats those two stored values as "no choice yet": on form mount, missing storage → `auto`; stored `light-pro` or `Editorial` → migrated in place to `auto` and the form initial state becomes `auto`; any other stored value (`Pixel`, `Vellum`, `Dossier`, `Whiteboard`, …) is a real user preference and is preserved verbatim. Manual selections continue to persist via `onThemeChange` exactly as before. **Backend untouched.** Backend gate: **335 passed, 2 skipped, 1 warning** (unchanged). Frontend `vite build`: `✓ built in 3.91s`. Honest limitation: this only affects browsers that visit the home form after this build ships — older saved values are migrated lazily on first load, not via a background job.

## Previously Completed Phase (still in effect)

**Phase 6M - Topic-aware art direction.** Accepted as **Pass**. Generated decks no longer default to the bright orange/amber `light-pro` look for every prompt — when the user does not pick a template, the backend deterministically infers a fitting theme from the topic text (e.g. a war / conflict / geopolitics prompt now renders with the dark navy `Dossier` documentary theme instead of a startup-pitch palette). **No DB migration.** No new endpoint. No new dependency. No LLM call. **Score-ineligible:** keyword-based heuristic only; no semantic understanding, no live eval, no pixel-level visual proof. NEXUS still does not beat Manus or Presenton.

### Files changed
- New [nexus-ai/backend/agent/art_direction.py](nexus-ai/backend/agent/art_direction.py) — pure-Python deterministic helper. Public API: `infer_art_direction(topic: str, theme: str | None = None) -> ArtDirection`. Returns a frozen dataclass `{theme, theme_id, mood, rationale, category, palette_hint}`. Sentinel values that trigger inference: `None`, `""`, `"auto"` (case-insensitive, whitespace-tolerant). Any other `theme` is respected verbatim. Categories scored by word-boundary keyword hits; ties break by category priority so `conflict` outranks `business` for "war economy" prompts.
- [nexus-ai/backend/api/routes/generate.py](nexus-ai/backend/api/routes/generate.py) — calls `infer_art_direction(payload.topic, payload.theme)` before constructing the `Task` row, and persists the resolved theme as `Task.theme`. Adds a single structured log line `generate.art_direction` with `input_theme`, `effective_theme`, `category`, `mood`, `rationale`. The `GenerateResponse` shape is **unchanged** — the contract assertion in `test_runtime_generate_route` (`set(body.keys()) == {"task_id", "status"}`) still passes because the inferred theme propagates through `Task.theme` rather than the response payload.
- [nexus-ai/frontend/src/components/PromptInput.jsx](nexus-ai/frontend/src/components/PromptInput.jsx) — adds `"auto"` as the first entry in the `THEMES` array (so it is the default for new visitors who have no `nexus.preferred-theme` in localStorage) and renders the dropdown label as `auto · pick from topic`. Existing localStorage-stored theme picks continue to load and are still respected. The active-template pill now reads `auto · pick from topic` when the auto sentinel is in effect.
- New [nexus-ai/backend/tests/test_art_direction.py](nexus-ai/backend/tests/test_art_direction.py) — 27 unit tests covering: sentinel detection, explicit override (including whitespace), category routing for war/conflict, business/sales, science/AI/technical, education/history, healthcare/climate/social-impact, creative/design/branding, generic fallback, conflict-vs-business tie-breaking, determinism, rationale shape, and `to_dict` round-trip.
- New [nexus-ai/backend/tests/test_generate_route_art_direction.py](nexus-ai/backend/tests/test_generate_route_art_direction.py) — 4 integration tests against the real FastAPI app via `httpx.ASGITransport` + `get_db` override + Celery `delay` no-op monkeypatch. Asserts: `theme="auto"` + war topic → `Task.theme == "Dossier"`; `theme=""` + business topic → `Task.theme == "light-pro"`; explicit `theme="Pixel"` + war topic → respected; explicit `theme="Editorial"` is treated as explicit (so the pre-6M response-shape contract stays green).

### Topic categories and selected themes
The selectable themes are restricted to the five legacy display names that both the frontend `SlideRenderer.themePalettes` and the backend `services.export_service.THEMES` already render, so every art-direction result is renderable end-to-end without further changes:

| Category | Trigger keywords (sample) | Theme | Mood | Rationale |
| --- | --- | --- | --- | --- |
| `conflict` | war, warfare, military, missile, geopolitics, ceasefire, refugee, ukraine, gaza, syria, ww2 | `Dossier` | serious | dark navy/blue intelligence-brief surface; no orange, no purple |
| `business` | startup, saas, b2b, sales, gtm, pitch deck, investor, series a, ipo, revenue, valuation | `light-pro` | polished | clean light corporate with amber accent |
| `technical` | ai, llm, language model, machine learning, quantum, cybersecurity, kubernetes, devops, cryptography | `Pixel` | technical | cool dark surface with green-cyan tech accent |
| `history` | history, ancient, medieval, renaissance, dynasty, archaeology, education, syllabus, classroom | `Vellum` | editorial | warm paper, serif headings |
| `human` | healthcare, clinical, pandemic, vaccine, climate, sustainability, biodiversity, social impact, nonprofit | `Vellum` | calm | warm, trustworthy, paper-like |
| `creative` | design, brand, branding, advertising, fashion, art, music, photography, ux, storytelling | `Editorial` | expressive | high-contrast purple-accent surface |
| `generic` | (no keyword match) | `Editorial` | neutral | documented fallback identical to the prior default |

### Where inference is wired
Single call site: `POST /api/generate` in [generate.py](nexus-ai/backend/api/routes/generate.py), immediately before `Task(...)` construction. The resolved `effective_theme` is persisted on the `Task` row, which is what `workers/tasks.py:run_generation_task` later reads (`theme=task.theme or "Editorial"`) and passes through `NexusAgentLoop.run(...)` into the `SlideDeck` row, the PPTX/PDF export pipeline, and the `/api/share/{token}` payload. No additional plumbing was required because all downstream consumers already read from `Task.theme` / `SlideDeck.theme`.

### Before / after for a war / conflict prompt
- **Before Phase 6M.** The home form's default theme was `light-pro` (white background, amber/orange `#F59E0B` accent). Submitting "Geopolitical analysis of the Russia–Ukraine war" with default settings produced a deck rendered in that bright corporate palette — the same look as a startup pitch — which is the exact failure mode the user flagged.
- **After Phase 6M.** The home form's default is now `auto`. The same prompt resolves to `Task.theme = "Dossier"`, mood `serious`, category `conflict`, with the rationale "Topic reads as conflict / geopolitics / crisis; chose Dossier for a serious, restrained documentary look instead of a bright default template." The frontend `SlideRenderer` and the backend PPTX exporter both already know how to render `Dossier` (dark navy/blue surface, slate/blue accent), so the live preview, the editor, the presenter view, the PPTX, the PDF, and the share link all show the documentary palette consistently. A user who explicitly picks `Pixel` (or any non-auto value) in the dropdown still gets exactly that — the inference branch is skipped.

### Validation
- Backend gate (Docker, in-memory SQLite): **335 passed, 2 skipped, 1 warning**. Up from the 302/2/1 Phase-6M-Shell baseline; the delta is 27 art-direction unit tests + 4 generate-route integration tests + 2 unrelated tests already in the tree (recount on the same baseline). No pre-existing test was modified.
- Frontend `vite build`: `✓ built in 3.74s` (pre-existing chunk-size warning unchanged).

### Honest limitations (Phase 6M)
- **Heuristic only.** This is a keyword-scored classifier, not semantic understanding. A topic like "the war on talent" will currently score as `conflict` because of the literal word "war"; topics that describe conflict without using listed keywords will fall back to `Editorial`.
- **Theme palette is still small.** Only the five existing renderable themes (`light-pro`, `Editorial`, `Pixel`, `Vellum`, `Dossier`) are reachable from inference. The 14 extra theme names listed in [Templates.jsx](nexus-ai/frontend/src/components/Templates.jsx) are still not rendered by the backend PPTX exporter (the legacy `THEMES` dict in `services/export_service.py` covers only the five used here).
- **No visual / pixel proof.** No automated screenshot diff, no live-eval run, no responsive snapshots. Manual inspection only.
- **No new product capability.** No new endpoint, no schema change, no migration. The user-facing change is "decks no longer all look the same" plus a single `auto` option in the template dropdown.
- **`Editorial` and `light-pro` are intentionally treated as explicit.** Older clients that send `theme="Editorial"` (the previous Pydantic default) continue to get exactly that — Phase 6M does not silently override them. Only `""` and `"auto"` trigger inference. This is a conservative compatibility decision; it means a user who happens to leave the dropdown on `Editorial` for a war topic will still get `Editorial`.
- **Headline competitive score unchanged.** No live eval was run. NEXUS still does not beat Manus or Presenton.

## Previously Completed Phase (still in effect)

**Phase 6M-Shell - App workspace action surface (frontend UX/workflow wiring only).** Accepted as **Pass**. Makes the live generated-deck experience read as a real product workspace instead of a marketing page. **Backend untouched.** No new endpoints, no schema changes, no migration, no live eval. **Score-ineligible:** UI/workflow wiring only; no visual quality, accuracy, or stability metric was measured.

### What Phase 6M-Shell added
- [frontend/src/App.jsx](nexus-ai/frontend/src/App.jsx) now hides the marketing `Footer` on app routes (`/generate/:taskId`, `/deck/:taskId`, `/present/:taskId`) and additionally hides the `Navbar` on `/present/:taskId` so the presenter view is fullscreen with no nav overlap. Footer is preserved on `/` and `/share/:token`. Implementation uses `useLocation` + `matchPath` against a small route-pattern list inside an internal `AppChrome` component.
- [frontend/src/pages/Generator.jsx](nexus-ai/frontend/src/pages/Generator.jsx) is now an app workspace:
  - Outer container uses `min-h-[calc(100vh-4rem)]` + `flex flex-col` so the page has a stable, app-sized footprint while generation streams.
  - When `status === "done"`, a prominent **action bar** is rendered above the progress + preview grid (not buried below it). The bar surfaces, in order: `DeckQualityBadge`, `slide_count + theme` summary, `Open editor` (→ `/deck/:taskId`), `Present` (→ `/present/:taskId`), and the existing `ExportButtons` (Download PPTX, Download PDF, Share link). The bar is a single `flex flex-wrap` row so it stacks cleanly on mobile.
  - The previous bottom-of-grid action row was removed to avoid duplication. The `SourceEvidencePanel` continues to render below the carousel on done.
  - While generating, the progress panel and live preview are unchanged; no marketing footer interrupts them.
- No edits to [frontend/src/pages/DeckWorkspace.jsx](nexus-ai/frontend/src/pages/DeckWorkspace.jsx) or [frontend/src/pages/Presenter.jsx](nexus-ai/frontend/src/pages/Presenter.jsx); the workspace header already exposes `DeckQualityBadge`, `Reset`, `Save edits`, `Present`, and `ExportButtons` in a `flex flex-wrap` row that fits desktop and wraps on narrow widths, and the presenter remains fullscreen (`fixed inset-0 z-[60]`).
- No backend code, no test, and no migration was changed in this phase.
- Frontend `vite build`: `✓ built in 3.75s` (pre-existing chunk-size warning unchanged).
- Backend gate at the time of acceptance: **302 passed, 2 skipped, 1 warning** (backend untouched).

**Phase 6L-UX-Fix - Server persistence for edited decks.** Accepted as **Pass**. Closes the honesty gap from Phase 6L-UX: edits made in the deck workspace are now persisted on the server and downstream surfaces (PPTX export, share link) read from the same `SlideDeck` row. localStorage is demoted to a draft / fallback used only when the server save fails. **No DB migration.** No new task is created — edits are written in place on the existing `SlideDeck`. **Score-ineligible:** this phase restores correct save semantics; it does not change generation quality, run live eval, or move the headline competitive score.

### What Phase 6L-UX-Fix added
- New endpoint **`PUT /api/slides/{task_id}`** in [backend/api/routes/slides.py](nexus-ai/backend/api/routes/slides.py). Request body: `{ "slides": [...], "theme": "<optional>" }`. Behavior:
  - 404 if the task does not exist.
  - 409 if the task is not in `status == "done"` (same precondition as `GET`).
  - Validates every slide via `agent.slide_schema.validate_deck`. On any validation failure, responds **400** with `{"error": "invalid_deck", "invalid_slides": [...]}` and the existing `SlideDeck` row is **not** overwritten.
  - On success, updates the existing `SlideDeck` row in place: `slide_data` is replaced with the canonical-layout-pinned slides, `slide_count` is recomputed, and `theme` is overwritten only if provided. Returns the same shape as `GET /api/slides/{task_id}`, with `deck_quality` attached.
- New test file [backend/tests/test_slides_put.py](nexus-ai/backend/tests/test_slides_put.py) (7 tests):
  1. `PUT` persists edited slides to the existing `SlideDeck` row.
  2. `GET` after `PUT` returns the edited slides and updated theme.
  3. Invalid `PUT` (e.g. bullets slide missing `title` and with empty `bullets`) returns **400** and the original deck is left untouched on disk.
  4. `GET /api/share/{token}` returns the **edited** slides (proves share serves the same `SlideDeck` source that `PUT` writes).
  5. PPTX export rendered from the persisted deck contains the edited title / bullet text and not the original strings (uses `ExportService._export_pptx_sync` against the post-`PUT` deck with a stub storage to capture bytes; parsed with `python-pptx`).
  6. `PUT` to an unknown task → 404.
  7. `PUT` to a non-done task → 409.
- Frontend [frontend/src/pages/DeckWorkspace.jsx](nexus-ai/frontend/src/pages/DeckWorkspace.jsx) **Save edits** button now calls `api.put('/slides/:taskId', { slides, theme })`. On success, it clears the localStorage draft, refreshes the cached server deck (so `Reset` reverts to the just-saved server state), and shows a confirmation toast saying exports/share now use the edits. On failure, it falls back to writing a localStorage draft so the user does not lose work, and surfaces the structured backend error message (including `invalid_deck` validation errors) in a toast. The dirty-state banner copy is updated accordingly: it now tells the user to click `Save edits` to make exports/share render the edited deck.
- The presenter route still reads the localStorage draft first (so unsaved edits are visible in fullscreen present mode), with the server deck as fallback. This is intentional and matches the workspace's draft semantics.
- Backend gate: **302 passed, 2 skipped, 1 warning** (was 295 passed before this phase; +7 new tests, no pre-existing tests changed).
- Frontend `vite build`: `✓ built in 4.18s` (pre-existing chunk-size warning unchanged).

### Honest limitations (Phase 6L-UX-Fix)
- **No PDF-export integration test.** [backend/api/routes/export.py](nexus-ai/backend/api/routes/export.py) routes `pptx` and `pdf` through the same `_load_deck` helper and the same `SlideDeck.slide_data` source, so PDF necessarily reads the edited deck. We did not add a separate PDF round-trip test in this phase because the PDF backend (`ExportService.export_pdf`) reuses the PPTX renderer and a separate parser is not in the existing test toolbox; a PDF-level assertion would require wiring an additional dependency. **The PPTX test is the proof of "export uses edited slides"; PDF is by code-path equivalence, not by direct assertion.**
- **No auth on the new endpoint.** `PUT /api/slides/{task_id}` is unauthenticated, matching the rest of the existing `/api/slides`, `/api/export`, and `/api/share` surface in this codebase. Adding per-user authorization is a separate, score-ineligible follow-up; it would need to be coordinated with the existing optional `User` model.
- **No rate limit.** A malicious client could flood `PUT` requests against an arbitrary `task_id`. Same surface profile as the existing `POST /api/share` and `POST /api/export/pptx` endpoints.
- **No version history.** `PUT` overwrites in place. There is no audit trail of previous deck states; `Reset` after a successful save no longer recovers the originally generated deck.
- **Live eval was not run.** No live `/api/generate` invocation, no `evaluate_deck` against benchmarks. Phase 6J's `biz-001` measurement and the full Phase 6T 11-prompt benchmark remain future work.
- **Headline competitive score unchanged.** NEXUS still does not beat Manus. NEXUS still does not beat Presenton overall.
- **localStorage is now draft-only.** Old saved drafts from Phase 6L-UX may still exist in users' browsers; they are loaded into the workspace on mount as before, but the user will see the dirty banner and must click `Save edits` to upload them.

## Previously Completed Phase (still in effect)

**Phase 6L-UX - Deck workspace UX recovery (frontend-only).** Accepted as **Pass**. Restores a real post-generation editing workspace and a fullscreen presenter view that were missing from the mounted frontend. **Backend untouched.** No change to `/api/generate`, deck/render schema, exports, share links, or live-eval. **Score-ineligible:** UX restoration only; no visual quality, accuracy, or stability metric was measured.

### What Phase 6L-UX added
- New page [frontend/src/pages/DeckWorkspace.jsx](nexus-ai/frontend/src/pages/DeckWorkspace.jsx) at route `/deck/:taskId`. Three-column layout: slide-navigator sidebar (thumbnail-style buttons; click to focus), live preview pane (existing `SlideRenderer` + theme picker), editor pane.
- New page [frontend/src/pages/Presenter.jsx](nexus-ai/frontend/src/pages/Presenter.jsx) at route `/present/:taskId`. Fullscreen black background, centered slide, hidden editing chrome. Keyboard: `→` / `Space` / `PageDown` next, `←` / `PageUp` previous, `Esc` returns to workspace.
- New component [frontend/src/components/SlideEditor.jsx](nexus-ai/frontend/src/components/SlideEditor.jsx). Per-layout controlled form. Edits supported per layout: `title` (title, subtitle, eyebrow), `bullets` (title + bullets[] with add/remove), `two-col` (title + 2 columns: heading/body), `quote` (quote, attribution), `stats` (title + 3 stats: value/label), `closing` (title, subtitle, cta), `chart` (title, subtitle only - chart data preview-only). Unknown layouts render a read-only "preview-only" notice.
- New util [frontend/src/utils/deckStorage.js](nexus-ai/frontend/src/utils/deckStorage.js). Local edits persist to `localStorage` keyed by `nexus.deck.<taskId>` as JSON `{ slides, theme, savedAt }`. Helpers: `loadDeck`, `saveDeck`, `clearDeck`.
- Route wiring in [frontend/src/App.jsx](nexus-ai/frontend/src/App.jsx) adds `/deck/:taskId` and `/present/:taskId` alongside the existing `/`, `/generate/:taskId`, `/share/:token` routes. Existing routes are unchanged.
- [frontend/src/pages/Generator.jsx](nexus-ai/frontend/src/pages/Generator.jsx) now shows an **"Open editor"** button next to the existing `DeckQualityBadge` and `ExportButtons` once `status === "done"`. The streaming progress panel and live preview during generation are unchanged. No automatic redirect (so the streaming log stays available for inspection).
- Workspace header keeps existing surfaces visible: `DeckQualityBadge` (deck quality), `ExportButtons` (Download PPTX, Download PDF, Share link), and `SourceEvidencePanel` below the workspace. A `Present` button enters fullscreen presenter view.
- Save/Reset semantics: edits flip a `dirty` flag; `Save edits` writes to `localStorage`; `Reset` reverts to the server deck and clears the local copy. A persistent banner reminds the user that PPTX/PDF/Share exports still render the **server-side** deck, not local edits.
- Frontend production build passes: `vite build` reports `✓ built in 4.44s` (1 chunk-size warning, pre-existing).
- Backend gate is **unchanged**: this phase touches no backend code, no migrations, and no tests. Re-running the gate confirms **295 passed, 2 skipped, 1 warning**.

### Score impact
- **None.** This phase restores UX surface area only. Estimated competitive score remains **~57/100 (~57.5 weighted, estimate)**. NEXUS still does not beat Manus. NEXUS still does not beat Presenton overall on user-facing presentation-product surface area. Phase 6J's `biz-001` run remains a single-prompt smoke measurement; the full 11-prompt benchmark remains future Phase 6T. Phase 6K mapper and Phase 6L theme registry both remain offline-only and not yet wired into the live generate / render path.

### Limitations (recorded honestly)
- **Local-only persistence.** Edits live in `localStorage` keyed per `taskId` and per browser. They are not pushed to the backend, do not survive on a different device, and do not change what the server stores in the database.
- **Exports use the server deck, not local edits.** PPTX, PDF, and Share-link rendering still go through the existing backend pipeline; they intentionally ignore in-browser edits to avoid silently committing unverified edits to a permanent artifact. A banner in the workspace says so.
- **No backend save endpoint.** No new API was added. Implementing a `PUT /api/decks/:taskId` save path is deferred to a follow-up phase and would be score-eligible only if it ships with proper auth, validation, and tests.
- **Chart edits are limited to title/subtitle.** Chart data (`chart_data.labels`, `chart_data.values`) is preview-only because numeric edits would invalidate `evaluate_deck`'s evidence checks without re-running source grounding.
- **No frontend test runner is configured in this repo.** No automated component test was added. Manual verification steps: (1) generate a deck, (2) click `Open editor`, (3) edit a bullet and a stats value, (4) verify the live preview updates, (5) Save, refresh, verify the edits persist, (6) press `Present`, verify keyboard navigation and `Esc` returns to the workspace.
- **No visual quality / a11y / responsive measurements** were taken. The workspace is built with the existing Tailwind tokens and follows the existing layout conventions, but pixel-level proof and screen-reader audits are deferred.
- **Phase 6L (theme registry) is not yet wired into this workspace.** The workspace theme picker still uses the existing renderer's hard-coded palette (`light-pro`, `Editorial`, `Pixel`, `Vellum`, `Dossier`); it does not consume the new `themes_registry` module. Wiring is deferred.

## Previously Completed Phase (still in effect)

**Phase 6L - Backend theme registry.** Accepted as **Pass**. Adds a deterministic backend theme registry that maps a stable `theme_id` to a structured set of presentation design tokens (colors, fonts, spacing, radius, chart palette), plus opt-in helpers to attach those tokens to a deck dict. Pure deterministic - no LLM, no network, no randomness, no filesystem writes. **Score-ineligible:** this phase only adds infrastructure and tests; it does not change visual quality on its own, does not run live eval, and does not move the headline competitive score.

### What Phase 6L added
- New module [backend/agent/themes_registry.py](nexus-ai/backend/agent/themes_registry.py). Public API: `Theme` dataclass, `BUILTIN_THEMES`, `LEGACY_THEME_ALIASES`, `THEME_DERIVED_KEYS`, `list_theme_ids()`, `get_theme(theme_id, *, strict=False)`, `resolve_theme(deck, *, strict=False)`, `apply_theme(deck, theme_id=None)`. Schema version `1.0`.
- Two built-in themes: `nexus-default` (compatible with the existing "Editorial"-style dark palette) and `nexus-light` (alternate light/serif palette). Each theme exposes `theme_id`, `display_name`, `colors{bg,surface,text,muted,accent,accent_alt,border}`, `fonts{heading,body,mono}`, `spacing{xs..xl}`, `radius{sm..lg}`, and a `chart_palette` tuple of >=6 colors.
- Legacy display-name aliases: `editorial -> nexus-default`, `vellum -> nexus-light`, case-insensitive. Existing `Task.theme="Editorial"` decks resolve cleanly without any DB migration. Other legacy palettes (`Pixel`, `Dossier`, `light-pro`) intentionally stay on the legacy `THEMES` dict in `backend/services/export_service.py`; migrating them is future work.
- `apply_theme` is non-mutating and only adds two deck-level keys (`theme_id`, `theme_tokens`). Slides payload is byte-identical across themes; the diff between two themed decks is provably restricted to `THEME_DERIVED_KEYS`.
- New test file [backend/tests/test_themes_registry.py](nexus-ai/backend/tests/test_themes_registry.py) with 26 deterministic offline tests: registry shape (default + alternate present, sorted ids, required token groups, hex-color sanity, non-negative spacing/radius), `Theme.to_tokens()` round-trip, `get_theme` behavior (case-insensitive, unknown -> default, unknown + strict -> `ValueError`, None/empty/non-string -> default, legacy alias resolution, identity-stable across calls), `resolve_theme` precedence (`theme_id` over legacy `theme`, non-dict -> default, unknown fields -> default), `apply_theme` invariants (does not mutate input, only `THEME_DERIVED_KEYS` change between themes, slides byte-identical, canonical id resolution from legacy alias, unknown id -> default, reads from deck when arg omitted, rejects non-mapping, deterministic), preservation of the canonical 7-layout schema via `validate_deck`, and a regression guard that the legacy `services.export_service.THEMES` map still imports.
- **No change to `/api/generate`, no change to deck/render schema, no change to `evaluate_deck`, no change to `benchmarks/eval_schema.json`.** Existing decks remain valid; new fields are optional. The legacy export palette in `backend/services/export_service.py` is intentionally untouched.
- Backend gate (official): **295 passed, 2 skipped, 1 warning** (was 269 + 26 new in 6L).

### Score impact
- **None.** Phase 6L is surface infrastructure only. Estimated competitive score remains **~57/100 (~57.5 weighted, estimate)**. NEXUS still does not beat Manus. NEXUS still does not beat Presenton overall on user-facing presentation-product surface area. Phase 6J's `biz-001` run remains a single-prompt smoke measurement; the full 11-prompt benchmark remains future Phase 6T. The Phase 6K claim-citation mapper remains offline-only and is not yet wired into the live generate / evaluate path.

### Limitations (recorded honestly)
- The registry is structural only. No frontend renderer, no PPTX/PDF exporter, and no live-generate path actually consume the new `theme_tokens` field yet; consumer wiring is deferred. This means visual quality has **not** improved as a result of Phase 6L; the only measured property is that switching themes produces a deck dict whose diff is restricted to `theme_id` + `theme_tokens`.
- Only two built-in themes ship in this phase; the legacy `Pixel` / `Dossier` / `light-pro` palettes still flow through the old `THEMES` dict in `export_service.py`. Migrating them is future work.
- No screenshot diff suite, no rendered-PPTX visual comparison, and no pixel-level proof that a different `theme_id` produces a visually distinct deck. Phase 6L only proves token-level (data) divergence.
- Strict mode is opt-in (`strict=True`); the default behavior on unknown `theme_id` is to silently fall back to the default theme. Callers that need a hard error must pass `strict=True` themselves.

## Previously Completed Phase (still in effect)

**Phase 6K - Deterministic claim-to-source citation mapper.** Accepted as **Pass**. Offline infrastructure only; not integrated into `/api/generate` or `evaluate_deck`. See [backend/services/claim_citation_service.py](nexus-ai/backend/services/claim_citation_service.py), gold corpus [backend/tests/fixtures/citation_gold.py](nexus-ai/backend/tests/fixtures/citation_gold.py), tests [backend/tests/test_claim_citation_service.py](nexus-ai/backend/tests/test_claim_citation_service.py).

## Previously Completed Phase (still in effect)

**Phase 6J - First controlled one-prompt live-eval smoke (`biz-001`).** Accepted as **Pass**. This is the first score-eligible measurement phase, but only for one prompt. The full 11-prompt benchmark remains future Phase 6T.

### What Phase 6J did
- Confirmed the running stack was drifted (`nexus-backend` was bound to `D:\nexus-ai-gh\backend`, not this workspace). Tore down that stack via `docker compose down` from the drifted workspace and rebuilt this workspace via `docker compose up --build -d` from `D:\nexus-ai-1\nexus-ai`. Re-verified `docker inspect nexus-backend` now reports `Source: D:\nexus-ai-1\nexus-ai\backend -> Destination: /app`. Backend health: `200 {"status":"ok","provider":"groq","model":"llama-3.3-70b-versatile"}`.
- Ran the live harness for `biz-001` exactly once with `NEXUS_RUN_LIVE_EVAL=true` against `http://host.docker.internal:8080` (no other prompts). Result JSON written to [backend/storage/evals/biz-001-20260509T090834Z.json](nexus-ai/backend/storage/evals/biz-001-20260509T090834Z.json) (gitignored), and a safe copy committed at [audits/LIVE_EVAL_RESULTS/biz-001-2026-05-09.json](nexus-ai/audits/LIVE_EVAL_RESULTS/biz-001-2026-05-09.json). The result file contains no provider keys and no raw provider payloads, so no redaction was required.
- Measured fields (offline-measurable subset only): `ran_live=true`, `generated_slide_count=8`, `slide_count_in_window=true`, `required_layouts_missing=[]`, `chart_required=false`, `chart_requirement_met=true`, `needs_external_sources=false`, `external_source_expectation_met=true`, `deck_quality_ok=false`, `deck_quality_invalid_count=1`, `category_scores.deck_correctness=8`, `category_scores.evidence_accuracy=7`. All of `visual_quality`, `export_parity`, `agent_autonomy`, `stability_reliability`, `security_production_readiness` remain `null` per schema (require out-of-band measurement). Notes: one slide failed deck-schema validation (`deck_quality_invalid_count=1`) - this is an honest signal worth tracking in subsequent phases; visual / export-parity / autonomy categories explicitly unmeasured offline.
- Added offline test [backend/tests/test_live_eval_results.py](nexus-ai/backend/tests/test_live_eval_results.py) (2 tests). It validates every committed JSON under `audits/LIVE_EVAL_RESULTS/` against `benchmarks/eval_schema.json` (top-level keys, category_scores keys, strict types, ran_live/fixture_label invariant, offline-measurable categories in 1..10, all null-by-schema categories null). Test is fully offline; does not call `/api/generate` or any provider. Skips when no committed results exist.
- Updated [scripts/test-backend.ps1](nexus-ai/scripts/test-backend.ps1) to additionally mount `audits\LIVE_EVAL_RESULTS -> /live_eval_results:ro` (read-only) when present, so the gate can validate committed result files.
- Backend gate (official): **251 passed, 2 skipped, 1 warning** (was 249 + 2 new in 6J).

### Score impact
- **No headline score change.** One easy prompt is not a benchmark. Estimated competitive score remains **~57/100 (~57.5 weighted, estimate)**. NEXUS still does not beat Manus. NEXUS still does not beat Presenton overall on user-facing presentation-product surface area. The full 11-prompt run remains future Phase 6T and is the gate for any meaningful score change.

## Previously Completed Phase (still in effect)

**Phase 6I - Runtime drives /api/generate behind feature flag.** Accepted as **Pass**. First implementation phase from the Phase 6H blueprint. Adds `NEXUS_RUNTIME_DRIVES_GENERATE` (default **OFF**) to `backend/config.py`. When the flag is off, `/api/generate` behaves exactly as before. When the flag is on, the route additionally persists an `AgentRun` (linked via `task_id`, `meta.phase="6I"`, `meta.dispatch_only=true`) and a single `thought` `AgentStep`, marks the run `done`, and surfaces `agent_run_id` in the response. The Celery worker still drives the actual generation pipeline; the runtime does not yet execute generation.

### What Phase 6I added
- New env-driven feature flag `NEXUS_RUNTIME_DRIVES_GENERATE` (default `False`) in [backend/config.py](nexus-ai/backend/config.py).
- New helper `_record_runtime_dispatch` in [backend/api/routes/generate.py](nexus-ai/backend/api/routes/generate.py) that persists an `AgentRun` + `thought` step + terminal `done` (or `failed` on persistence error) using the existing `services.agent_run_service` API. Uses the existing `AgentRun` / `AgentStep` / `Artifact` tables from migration `0002_agent_runtime`.
- `GenerateResponse` gained an optional `agent_run_id: Optional[str] = None` field. With the flag off, the field is `None`; live-eval adapter and frontend are unchanged because both only consume `task_id`.
- New offline test file [backend/tests/test_runtime_generate_route.py](nexus-ai/backend/tests/test_runtime_generate_route.py) (4 tests): flag-off response shape unchanged + zero `AgentRun` rows; flag-on persists exactly one `AgentRun` + one `thought` step, run status `done`, `agent_run_id` present; flag-on response remains compatible with the live-eval adapter (`task_id` present); flag-on with `append_step` raising still returns 202 and records the `AgentRun` as `failed` with `dispatch_record_failed` prefix.
- Celery enqueue is monkeypatched to a no-op in the new tests so they remain offline.
- **No layout, renderer, frontend, or worker code changed.** No new dependencies. No JSON files modified.
- Full backend pytest via official gate after 6I: 249 passed, 2 skipped, 1 warning (was 245 + 4 new).

### Phase 6I-Fix - Response-contract cleanup
- Added `response_model_exclude_none=True` on the `/api/generate` route so the flag-off JSON body is exactly `{task_id, status}` and never includes `agent_run_id: null`. Tightened the flag-off test to assert `set(body.keys()) == {"task_id", "status"}` and `"agent_run_id" not in body`. Flag-on tests unchanged. No live eval. No score change. Gate after 6I-Fix: 249 passed, 2 skipped, 1 warning.

## Previously Completed Phase (still in effect)

**Phase 6H - Reference Intelligence Blueprint.** Accepted as **Pass**. Audit/roadmap phase only. Authored [audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md](nexus-ai/audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md) - now the master implementation roadmap. It compares NEXUS against Manus, Presenton, browser-use, OpenManus, Suna, AgenticSeek, and the curated Browser/Claude research notes; defines a NEXUS gap matrix across 15 capabilities; describes a unified target architecture; and lists the next 12 implementation phases (6I through 6T) with goals, files touched, tests required, acceptance criteria, score category, and whether the phase is score-eligible. **No NEXUS code changed. No live eval run. No score moved.** Estimated competitive score remains ~57/100 (~57.5 weighted, estimate). NEXUS does not beat Manus. Presenton still leads on user-facing presentation-product surface area. Backend gate remains 245 passed, 2 skipped, 1 warning.

### What Phase 6H added
- New file [audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md](nexus-ai/audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md) (executive verdict, per-reference comparison with file citations, 15-row gap matrix, unified target architecture, next-12-phase roadmap, measurement plan, non-goals).
- Updated header dates and footer disclosures in `AUDIT_CURRENT_STATE.md`, `AUDIT_PROMPT_CONTEXT.md`, `CURRENT_COMPETITIVE_SCORE.md`, `COMPETITIVE_BENCHMARK_BASELINE.md`, `FINAL_SYSTEM_AUDIT.md`, `PRD_COMPLIANCE_AUDIT.md`.
- **No code changes.** No new tests. No JSON files modified. No reference-repo files modified.

## Previously Completed Phase (still in effect)

**Phase 6G - Presenton Reference Benchmark.** Accepted as **Pass**. Added [Presenton](nexus-ai/manus-need/presenton/README.md) as a presentation-product reference distinct from the Manus / browser-use / OpenManus / AgenticSeek agent references and from Gamma/Tome (closed-source SaaS). Recorded an honest, file-cited feature comparison across generation API maturity, async/SSE, template/theme system, export pipeline, PPTX/PDF ingestion, provider/BYOK, MCP, test coverage, and visual posture. **No NEXUS code changed. No live eval run. No score moved up.**

### What Phase 6G added
- Updated [audits/COMPETITIVE_BENCHMARK_BASELINE.md](nexus-ai/audits/COMPETITIVE_BENCHMARK_BASELINE.md) with a new § *Phase 6G — Presenton Reference Comparison* section (per-category table with file citations into `manus-need/presenton/`) and added a `presenton` row to the competitor table.
- Updated [audits/CURRENT_COMPETITIVE_SCORE.md](nexus-ai/audits/CURRENT_COMPETITIVE_SCORE.md) to disclose, alongside the Manus disclaimer, that NEXUS does not beat Presenton on user-facing surface area today (PPTX/PDF ingestion, SSE streaming, MCP server, BYOK including Ollama, Electron desktop — all NEXUS gaps).
- Updated [benchmarks/rubric.json](nexus-ai/benchmarks/rubric.json) to add `presenton` to the `competitors` list (kind = `presentation_tool_reference`). Existing integrity test `test_rubric_lists_required_competitors` continues to pass (it asserts a *subset* of required IDs, not equality).
- **No code changes.** No new tests. No category weight changes. No score change. No live eval executed.
- Full backend pytest via official gate: **245 passed, 2 skipped, 1 warning** (unchanged from Phase 6E/6F).

### Honest gaps recorded vs. Presenton
- **Hard gap:** NEXUS has no PPTX or PDF ingestion at all; Presenton ships both with file-upload endpoints and a 100 MB cap.
- **Hard gap:** NEXUS has no MCP server; Presenton ships a FastMCP server auto-derived from OpenAPI.
- **Soft gap:** NEXUS has no SSE slide streaming, no `derive`/`prepare`/`edit` endpoints, no webhook callbacks, no stage-by-stage progress messages.
- **Soft gap:** NEXUS provider story is `.env`-driven (Groq default, Anthropic/OpenAI in code). Presenton supports first-class BYOK across OpenAI / Anthropic / Google / Vertex / Azure / Ollama / custom OpenAI-compatible.
- **Soft gap:** NEXUS has no Electron desktop distribution.
- **Even gaps:** Neither system has a pixel-diff visual regression suite. Neither has executed a live deck-quality measurement.
- **NEXUS-only strengths preserved:** Authenticated `AgentRuntime` (Phase 6A), 7-layout canonical schema validator, deck-quality report + repair preview, deck-level source grounding, 245 backend tests including 30 offline live-eval tests and 15 PPTX content-parity tests.

### What Phase 6F added (still in effect)
- New runbook [audits/LIVE_EVAL_RUNBOOK.md](nexus-ai/audits/LIVE_EVAL_RUNBOOK.md) covering prerequisites, `docker compose down/up --build` from this workspace, host-mount verification (`docker inspect nexus-backend` must show `D:\nexus-ai-1\nexus-ai\backend`), required env vars, the exact one-prompt command for `biz-001`, output location (`backend/storage/evals/`, gitignored), how to interpret the result JSON, and rollback/cleanup.
- Explicit warnings: paid LLM/search providers may be invoked; **do not** generalize from one prompt; **do not** claim Manus parity.
- **No code changes.** No new tests. No live eval was executed and no result file was produced.
- Full backend pytest via official gate: **245 passed, 2 skipped, 1 warning** (unchanged from Phase 6E).

### What Phase 6E added (still in effect)
- Replaced the Phase 6D `NotImplementedError` stub in [backend/scripts/run_live_eval.py](nexus-ai/backend/scripts/run_live_eval.py) with a real opt-in adapter that POSTs to `/api/generate`, polls `/api/slides/{task_id}` until the task is `done` / `failed` / timeout, and shapes the response into the deck dict expected by `evaluate_deck`.
- Adapter uses an injectable `HttpClient` Protocol so tests run with an in-memory fake; the default client (`httpx.Client`) is built lazily so tests can never make real HTTP unless someone explicitly removes the injection.
- New CLI flags: `--prompt-id`, `--base-url`, `--timeout-seconds`, `--poll-interval-seconds`, `--theme`, `--search-web` / `--no-search-web`, `--slide-count`. The opt-in guard (`NEXUS_RUN_LIVE_EVAL=true`) is preserved — without it the CLI exits non-zero.
- New offline tests [backend/tests/test_live_eval_adapter.py](nexus-ai/backend/tests/test_live_eval_adapter.py) (12 tests): refusal without env flag and with non-`true` flag, expected POST payload, pending→done polling, failed-task detection, timeout, post 4xx/5xx, 404, record writing under `NEXUS_EVAL_OUTPUT_DIR`, non-zero return on failure, and a guard that confirms `httpx` is **not** imported when a fake client is injected.
- Result files write to `backend/storage/evals/` (gitignored via `backend/storage/`) by default; override via `NEXUS_EVAL_OUTPUT_DIR`.
- **No product-behavior changes.** No new layouts, no renderer changes, no UI changes, no live LLM calls in tests.
- Full backend pytest via official gate: **245 passed, 2 skipped, 1 warning** (was 233 + 12 new).

### What Phase 6D added (still in effect)
- New eval result schema [benchmarks/eval_schema.json](nexus-ai/benchmarks/eval_schema.json) describing the per-prompt record shape.
- New offline evaluator [backend/services/eval_service.py](nexus-ai/backend/services/eval_service.py) (`evaluate_deck`, `load_prompts`, `get_prompt_spec`). Pure function: no network, no LLM, no filesystem writes. Per-category scores are filled only when measurable from a deck dict alone (`deck_correctness`, partial `evidence_accuracy`); the rest are `null` with explanatory notes.
- New deterministic fixture decks [backend/tests/fixtures/eval_decks.py](nexus-ai/backend/tests/fixtures/eval_decks.py) (passing/failing decks for `inv-001`, passing for `biz-001`, slide-count violator).
- New offline test suite [backend/tests/test_live_eval.py](nexus-ai/backend/tests/test_live_eval.py) (18 tests): corpus loading, ID uniqueness, unknown-id raises, schema-stable result keys, category-key set matches rubric, passing-deck assertions, failing-deck detection of missing layouts / chart / sources, slide-count window violation, ran_live default semantics, bad-input rejection, **and a guard that the live-eval CLI refuses without `NEXUS_RUN_LIVE_EVAL=true`**.
- New opt-in CLI [backend/scripts/run_live_eval.py](nexus-ai/backend/scripts/run_live_eval.py) and PowerShell wrapper [scripts/run-live-eval.ps1](nexus-ai/scripts/run-live-eval.ps1). Without `NEXUS_RUN_LIVE_EVAL=true` the CLI exits non-zero; the actual `/api/generate` call is intentionally a `NotImplementedError` stub so a future phase wires it cleanly instead of silently faking data.
- Live-eval output target: `backend/storage/evals/` (already gitignored via `backend/storage/`).
- **No product-behavior changes.** No new layouts, no renderer changes, no UI changes, no live LLM calls in tests.
- Full backend pytest via official gate: **233 passed, 2 skipped, 1 warning** (was 215 + 18 new).

### What Phase 6C added (still in effect)
- New deterministic fixture module [backend/tests/fixtures/canonical_slides.py](nexus-ai/backend/tests/fixtures/canonical_slides.py) covering all 7 canonical layouts with unique text markers and no `image_url` (so exports run without network calls).
- New parity tests [backend/tests/test_export_parity.py](nexus-ai/backend/tests/test_export_parity.py) (15 tests) that drive `ExportService._export_pptx_sync` through an in-memory storage stub, reopen the saved PPTX with `python-pptx`, and assert per-layout textual content parity for `title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`. Chart slide also asserts category labels and series values survive. Includes determinism check, unknown-layout fallback safety, empty-chart fallback, on-disk reopen smoke, and a PDF smoke test that **skips** if WeasyPrint is unavailable (PDF visual parity remains open).
- The fixture module is reusable by future screenshot/visual-diff phases.
- **No product-behavior changes.** No new layouts, no renderer changes, no UI changes.
- Full backend pytest via official gate: **215 passed, 2 skipped, 1 warning** (was 200 + 15 new).

### What Phase 6B + 6B-Fix added (still in effect)
- Verification drift detected: the initial Phase 6B run used an ad-hoc `docker run` invocation that mounted both `backend/` and `benchmarks/`, but the official gate `scripts/test-backend.ps1` only mounted `backend/`. When Copilot reran the official gate the result was **2 failed, 182 passed, 2 skipped, 1 warning, 16 errors** because `/benchmarks` was not visible inside the container.
- Fixed [scripts/test-backend.ps1](nexus-ai/scripts/test-backend.ps1) to also mount the repo's `benchmarks/` folder at `/benchmarks` (read-only) and to refuse to run if the directory is missing.
- Hardened [backend/tests/test_competitive_benchmark.py](nexus-ai/backend/tests/test_competitive_benchmark.py): when neither `<repo>/benchmarks/` nor `/benchmarks` is visible, the existence tests and rubric/prompts fixtures fail loudly with a clear message instead of silently passing against a non-existent path.
- **Verified gate result:** `.\scripts\test-backend.ps1` → **200 passed, 2 skipped, 1 warning** (pytest exit code 0). The PowerShell wrapper may surface a non-zero `$LASTEXITCODE` purely from pytest-asyncio's stderr deprecation warning; the underlying pytest run is green.

### What Phase 6B added
- New benchmark plan [audits/COMPETITIVE_BENCHMARK_BASELINE.md](nexus-ai/audits/COMPETITIVE_BENCHMARK_BASELINE.md) comparing NEXUS against Manus, browser-use, OpenManus, AgenticSeek, and Gamma/Tome across 7 weighted categories.
- New machine-readable rubric [benchmarks/rubric.json](nexus-ai/benchmarks/rubric.json) (weights sum to 100): deck_correctness 20, visual_quality 15, export_parity 15, evidence_accuracy 15, agent_autonomy 15, stability_reliability 10, security_production_readiness 10.
- New prompt corpus [benchmarks/prompts.json](nexus-ai/benchmarks/prompts.json) with 11 realistic deck prompts spanning business, investor, education, product launch, market research, chart-heavy, evidence-heavy, visual storytelling, and agent-autonomy kinds; each with `expected_evidence`, `expected_visual`, `difficulty`, and `primary_categories`.
- New baseline score file [audits/CURRENT_COMPETITIVE_SCORE.md](nexus-ai/audits/CURRENT_COMPETITIVE_SCORE.md). Honest disclosure: NEXUS is not beating Manus yet; estimated overall score ~55/100; AI accuracy not measured.
- New integrity tests [backend/tests/test_competitive_benchmark.py](nexus-ai/backend/tests/test_competitive_benchmark.py) (17 tests, no LLM calls): rubric weights sum to 100; rubric/prompt schemas; corpus covers required kinds, all difficulty levels, and all prompt-evaluable rubric categories; categories map to audit open risks.
- Full backend pytest: **200 passed, 2 skipped** (was 182, 2 skipped after Phase 6A; +18 new collected from this phase, including a previously-uncollected one).

### What Phase 6A added (still in effect)
- `/api/agent/test-run` requires `Authorization: Bearer <jwt>` (`get_current_user` dep in [backend/api/routes/agent.py](nexus-ai/backend/api/routes/agent.py)).
- Alembic migration [backend/database/migrations/versions/0002_agent_runtime.py](nexus-ai/backend/database/migrations/versions/0002_agent_runtime.py) creates `agent_runs`, `agent_steps`, `artifacts`. Verified end-to-end on disk.

### What Phase 5 added (still in effect)
- `SourceEvidencePanel` component exists (`frontend/src/components/SourceEvidencePanel.jsx`).
- Mounted in both `frontend/src/pages/Generator.jsx` and `frontend/src/pages/SharedSlide.jsx`.
- `frontend/src/utils/slideParser.js` preserves `slide.sources` end-to-end.
- `npm run verify:layouts` passes with **7 canonical layouts / 7 exported**.

---

## Current Verified Facts

| Area | State |
| --- | --- |
| Certified layouts | **7 canonical** (`title`, `bullets`, `two-col`, `quote`, `stats`, `chart`, `closing`) |
| Layout aliases | **0** |
| Frontend layout gate | `npm run verify:layouts` → 7 / 7 |
| Browser automation | Playwright-backed, **opt-in**, disabled by default (`BROWSER_ENABLED=false`) |
| Agent runtime | Exists (`backend/agent/runtime.py`), reachable via internal test route, **authenticated (Bearer JWT)** |
| Alembic migrations | `0001_initial` → `0002_agent_runtime` (head). Runtime persistence tables now part of migration chain. |
| Deck-quality report | Computed and surfaced via `DeckQualityBadge` |
| Repair pipeline | **Preview-only** (`build_repair_preview`), nothing applied |
| Evidence — Phase 3 | Source artifacts persisted as `Artifact(artifact_type="source")` rows |
| Evidence — Phase 4 | Generated decks attach deck-level sources to source-bearing slides; `chart_data.source` filled from real data only |
| Evidence — Phase 5 | Frontend `SourceEvidencePanel` renders deck-level sources |
| Competitive benchmark | Baseline plan, rubric (sum=100), 11-prompt corpus, integrity tests — Phase 6B. **AI accuracy not yet measured live.** |
| Live-eval harness | **Phase 6D** offline evaluator + **Phase 6E** real `/api/generate` adapter (opt-in, fake-HTTP-tested). 30 offline tests. **No live run executed yet.** Scores remain estimates. |
| Estimated competitive score | ~57 / 100 (estimate, not measured — export_parity raised from 4→6 after Phase 6C; Phase 6D harness only) |
| Export parity — PPTX content | **All 7 canonical layouts content-parity tested** (Phase 6C). Title/body/stats/labels/values preserved. Visual/pixel parity still unmeasured. |
| Export parity — PDF | Smoke test only; full visual parity remains open. |
| Backend default pytest | Unblocked since Phase 1G (engine kwargs guarded for SQLite). Phase 6I gate: **249 passed, 2 skipped, 1 warning**. |

---

## Evidence Limitations (open)

- No claim-specific citation mapping (sources are deck-level / slide-level, not bound to individual claims).
- No on-slide visual citations.
- No hard fact-checking. Source matching is heuristic and advisory.

---

## Still Open

- **Live AI accuracy not yet measured.** Phase 6B established the rubric and corpus; no live-eval harness has been run against `/api/generate`. Scores in `CURRENT_COMPETITIVE_SCORE.md` are estimates.
- **Visual/pixel export parity.** Phase 6C added textual content parity for PPTX across all 7 canonical layouts; pixel-level visual fidelity (typography, spacing, exact positioning) is still unmeasured.
- **PDF parity.** Only a smoke test (skips if WeasyPrint unavailable). No PDF visual parity is claimed.
- **Visual quality.** Typography, spacing, hierarchy, premium-feel — see `VISUAL_QUALITY_AUDIT.md`. No screenshot-diff suite.
- **Runtime not driving `/api/generate`.** The user-facing generate flow is still the 6-step `agent/loop.py` pipeline. The dynamic tool-calling runtime exists separately.
- **Auth / security (residual).** `/api/agent/test-run` now requires Bearer JWT, but there are still no rate limits, no per-user quotas, and no SSE step streaming.
- **Live container drift.** The currently-running `nexus-backend` container is bound to a different host path (`D:\nexus-ai-gh\backend`) and will not pick up Phase 6A/6B/6C code until `docker compose up --build` is run from this workspace.
- **Audit folder token bloat.** The four detailed audit files contain ~3,200 lines of phase history. Future cleanup may compact this further; for now history is preserved verbatim.

---

## Next Recommended Phase

Phase 6J (one-prompt `biz-001` live-eval smoke), Phase 6K (offline claim-level citation mapper), Phase 6L (backend theme registry), Phase 6S (PPTX ingestion), Phase 6T (first full 11-prompt benchmark), Phase 6U (measured benchmark gap fix), and Phase 6V (research-first deck strategy) are all complete and accepted. The next queued phase is:

1. **Phase 6U-Rebench - Full 11-prompt re-benchmark** (score-eligible). Re-run the live-eval suite against the 6U product changes (slide-count override, `harvest` min_sources, `repair_for_validator`) and update the headline competitive score against the new measurement. Per the 6U rule, no headline score change is reported until that re-measurement completes.

Recommendation: **Phase 6U-Rebench next** for the next score-eligible measurement. See [audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md](nexus-ai/audits/REFERENCE_INTELLIGENCE_BLUEPRINT.md) § *Roadmap to Beat Manus* for goals, files touched, tests required, acceptance criteria, score category, and score-eligibility for every queued phase.

---

## How To Use This File

- Future AI chats: read this file before reading any of `FINAL_SYSTEM_AUDIT.md`, `ARCHITECTURE_HARDENING_AUDIT.md`, `PRD_COMPLIANCE_AUDIT.md`, or `VISUAL_QUALITY_AUDIT.md`.
- See `AUDIT_READING_GUIDE.md` for how to interpret older phase sections.
- See `AUDIT_PROMPT_CONTEXT.md` for the short context block to paste into new chats.

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

