# PRD vs Reality — Brutally Honest Audit

_Last updated: 2026-05-08 — written from the agent's POV after this session's three visual fixes (card-height, duplicate eyebrow, AI/tech images) but BEFORE the SlideShare scraper lands._

This document maps **every section of `AI PPT Generator Platform — Complete PRD`** (24 sections) onto the current `nexus-ai` codebase. Each item is rated:

| Status | Meaning |
|--------|---------|
| ✅ **Shipped** | End-to-end, validated in a generated deck or by direct test. |
| 🟡 **Partial** | Code exists and compiles; one or more downstream consumers don't actually use it, or it's a stub. |
| 🟥 **Missing** | No code path. Pure todo. |
| ⚠️ **Risk** | Shipped but fragile / not load-tested / not isolated. |

**Reading rule:** if a row says 🟡 or 🟥, do not believe a marketing screenshot.

---

## §1. Product Vision — "prompt → editable, business-ready PPTX"

| Capability | Status | Evidence | Gap |
|---|---|---|---|
| Prompt → PPTX | ✅ | `backend/api/routes/generate.py` → `agent/loop.py` → `services/export_service.py` | — |
| Editable web editor | 🟡 | `frontend/src/pages/Editor.jsx` exists (text edit, reorder, version sidebar) | No drag-and-drop layout edit, no chart re-edit UI, no per-shape selection. |
| Document/dataset → PPTX | 🟡 | `routes/upload.py` + `services/context_extractor.py` parse csv/xlsx/json/pdf/docx/pptx/md | Parsed payload is appended as text context — never structurally fed into chart/table generators. |

---

## §2. Core Objectives

| Objective | Status | Notes |
|---|---|---|
| Generate professional PPT decks | ✅ | Markdown pipeline (`agent/markdown_pipeline.py`) is the live path. |
| Structured + unstructured uploads | 🟡 | Upload endpoint accepts them; CSV/XLSX never reaches the chart generator. |
| Charts/graphs/visuals/storytelling slides | 🟡 | Chart shapes render via `chart_service.py`. Storytelling is keyword-driven, no narrative arc model. |
| Auto images/icons/illustrations | ✅ (this session) | `image_service.py` (Unsplash → Pexels → Pollinations). Icons via `lucide-react` in frontend, not in PPTX. |
| Web slide editor | 🟡 | See §1; ~basic. |
| Export PPTX/PDF/PNG/share | 🟡 | PPTX ✅, share-link ✅, PDF/PNG **not implemented** in `export_service.py`. |
| APIs/SDKs/React/embed | 🟡 | REST ✅, `sdk/` package exists with `<PPTGenerator/>` but **never published, never tested in a host app**. |
| Enterprise scalability | 🟥 | Single-process FastAPI + Celery worker on Redis; no horizontal proof, no autoscaling, no rate-limit ceilings tested. |

---

## §3. AI Visual & Image Intelligence

| Image type PRD wants | Status | Where |
|---|---|---|
| Hero images | ✅ | `image_service.classify_image_category` returns `"hero"`; `loop._add_hero_images` selects per layout. |
| Industry-related visuals | 🟡 | We pass topic title as the search query — relevance depends entirely on Unsplash/Pexels query quality. No industry taxonomy. |
| Product mockups | 🟥 | Not implemented. |
| Business illustrations | 🟥 | Stock photos only; no illustration source (undraw, blush). |
| Icons & diagrams | 🟡 | Frontend `SlideRenderer` injects lucide icons. **PPTX export does not embed icons.** |
| Background visuals | 🟡 | Theme bg color only. No background-photo overlay path. |
| Conceptual imagery | 🟡 | Pollinations AI fallback (text-to-image), low quality. |
| Infographics | 🟥 | Not implemented. |
| Team/avatar illustrations | 🟥 | Not implemented. |
| Maps/geographic visuals | 🟥 | Not implemented. |
| Contextually relevant + narrative-aligned | 🟡 | Slide-level prompt = title + topic; no narrative-arc awareness. |

**This session's fix:** research/history decks no longer hard-block hero imagery — `image_strategy="optional"` allows hero on title/closing/image-focus only. AI/tech topics now get heroes.

---

## §4. Intelligent Image Selection Engine

| PRD requirement | Status |
|---|---|
| AI-generated images | 🟡 — Pollinations only (no DALL·E/Flux/Stability key wiring beyond config stubs). |
| Stock retrieval | ✅ — Unsplash + Pexels with API-key fallback. |
| Brand-safe selection | 🟥 — No NSFW filter, no brand-kit allowlist. |
| Context-aware recommendation | 🟡 — Layout-type + category modifiers in `image_service.build_prompt`; no embedding-based ranking. |
| Auto-cropping/resizing | 🟡 — `python-pptx` resizes to placeholder; **no smart crop** (face/subject detect). |
| Background removal | 🟥 — Not implemented. |
| Style matching | 🟥 — No style classifier. |
| Theme-aware placement | 🟡 — Layout decides position; theme palette decides overlay color. No explicit theme→image-style map. |
| Industry-specific imagery | 🟥 — No taxonomy. |
| Visual consistency across deck | 🟡 — All images come from same sources; **no palette-coherence pass**, no recurring-subject lock. |

---

## §5. Automatic Visual Recommendation System

| Visual type | Decided by | Status |
|---|---|---|
| Charts | `agent/markdown_pipeline._build_visual_slide` numeric-density rule | 🟡 — fires on slides with ≥3 numeric tokens; no series-shape inference. |
| Graphs | Same as charts | 🟡 |
| Images | `should_have_image_for_profile` (this session adds `optional`) | ✅ |
| Icons | Frontend renderer only | 🟡 |
| Timelines | Layout `timeline` chosen when bullets contain dates | ✅ |
| Process diagrams | Layout `roadmap`/`process` when bullets contain `STEP/PHASE/STAGE` | ✅ (this session's pipeline) |
| KPI cards | Layout `metric-spotlight` for dominant percent number | ✅ |
| Tables | Layout `table` when planner emits `table` | 🟡 — planner rarely picks it. |
| Comparison layouts | Layout `comparison`/`two-col` chosen by hash rotation | ✅ |
| Infographics | 🟥 — **not implemented.** |

**Honest gap:** no LLM-driven visual recommender — all decisions are regex/heuristic. Works for English, breaks on other languages.

---

## §6. Multi-Format Context Understanding

| Input | Parser status | Used downstream? |
|---|---|---|
| CSV / XLSX / JSON | ✅ parsed (`pandas`, `openpyxl`) | ❌ payload only fed as text context, never to chart_service. **Big gap.** |
| PDF / DOCX | ✅ parsed (`pypdf`, `python-docx`) | ❌ extracted as raw text only. |
| PPTX | ✅ parsed | ❌ used for analysis tooling, not as user input. |
| Plain text / Markdown | ✅ | ✅ |
| Research reports | 🟡 — same as PDF | partial |
| Meeting notes | 🟡 — text path | partial |
| Screenshots / images | 🟥 — no OCR. |
| URLs | 🟡 — `search_service` fetches some; **no URL-as-input endpoint.** |
| APIs | 🟥 |
| CRM exports | 🟥 |
| Analytics reports | 🟥 |
| KPI/metric/trend extraction | 🟥 — no structured insight extractor over the parsed text. |

**Brutal:** §6 is the single biggest "looks done, isn't" area. Files arrive, get parsed, and the parsed structure dies in a `context_summary` string.

---

## §7. Text-to-Chart / Text-to-Visual Intelligence

| Sub-capability | Status |
|---|---|
| Detect numeric claims in prose | 🟡 — `markdown_pipeline._NUMBER_RE` finds them but only triggers `metric-spotlight`. |
| Auto-generate revenue/KPI charts from sentences | 🟥 — no NLP→ChartSpec extractor. |
| Auto-generate KPI cards | 🟡 — only when LLM emits them in markdown. |
| Executive summary insights | 🟥 |
| Supporting business imagery | 🟡 — generic hero only. |

**Estimate:** PRD example "Revenue grew $2M→$5M while CAC −35%" → today produces a bullets slide, not a chart. Real gap.

---

## §8. Deck Planning Layer

| PRD field | Where today |
|---|---|
| Narrative structure | 🟡 — `agent/planner.py` produces an outline JSON, but no explicit narrative-arc model (problem→solution→ask). |
| Slide purpose | ✅ — outline `intent` field. |
| Recommended layouts | 🟡 — planner suggests, but the markdown pipeline frequently overrides via `_build_visual_slide`. |
| Suggested charts/images/diagrams | 🟡 — chart suggestions yes, image prompts yes, diagrams no. |
| Storytelling flow | 🟥 — no flow validator. |
| Audience targeting | 🟡 — `audience` field threaded into prompts; planner doesn't pivot layout choice on it. |
| Context sources | ✅ — `research_data.sources_used`. |

---

## §9. AI Slide Generation (structured JSON)

| PRD field | Status |
|---|---|
| Title / subtitle | ✅ |
| Bullet content | ✅ |
| Speaker notes | 🟥 — **not generated** anywhere. PRD calls it out; we ignore it. |
| Charts / graphs | 🟡 — when planner picks chart layout. |
| Tables / KPI cards | 🟡 — KPI yes; tables rare. |
| Image prompts | ✅ — `slide.image_prompt`. |
| Layout metadata | ✅ — `slide.layout`. |
| Visual hierarchy metadata | 🟥 — no z-index, no emphasis ranks. |
| Design tokens | 🟡 — per-slide `_accent_override` / `_font_heading` / `_font_body` (added this session) but no token namespace. |

---

## §10. Visual-First Design (Manus parity)

| PRD principle | Reality |
|---|---|
| Avoid documentation-style slides | 🟡 — bulleted slides still dominate; this session diversified via hash-rotated layouts but caps remain. |
| Consulting-style layouts | 🟡 — `bento`, `matrix-2x2`, `pyramid` exist on backend; **frontend `SlideRenderer.layouts` dict only registers 10** (title/bullets/two-col/quote/stats/chart/table/timeline/image-focus/closing). Backend emits bento/feature-grid/callout/agenda/roadmap/process/metric-spotlight/hero — frontend silently falls back to TitleSlide. **This is a real bug.** |
| Strong visual hierarchy | 🟡 — manual font sizes; no automated hierarchy pass. |
| Minimal text density | 🟡 — `word_target` per category enforces it in prompts; LLM still overflows. Critic re-passes only when enabled. |
| Modern business design | ✅ — 69 themes wired in PPTX exporter (was 5 in HONEST_STATUS — now real). |
| Storytelling-driven layouts | 🟥 — no narrative-arc engine. |
| Responsive spacing | 🟡 — frontend Tailwind; PPTX export uses fixed EMU coords. |
| Consistent branding | 🟡 — accent color stamped per slide; brand-kit not yet consumed. |

---

## §11. Image Placement & Layout Rules

| Decision | Status |
|---|---|
| Image position | 🟡 — layout-driven, not content-driven. |
| Image size | ✅ — placeholder sizing. |
| Overlay text placement | 🟡 — fixed per layout. |
| Contrast optimization | 🟥 — no overlay luminance check; dark text can land on dark photo. |
| Cropping focus area | 🟥 — center crop only. |
| White space usage | 🟡 — Tailwind padding, hand-tuned. |
| Background blur | 🟥 |
| Layout balance text/visuals | 🟡 — fixed per layout, not measured. |

---

## §12. Brand-Aware Visual Generation

| Brand input | Status |
|---|---|
| Brand colors | 🟥 — Brand-kit DB rows exist (`models.BrandKit`) and CRUD endpoints work, but `export_service.py` does **not** read brand-kit colors. Stub. |
| Typography | 🟥 — same: brand-kit fonts not consumed by exporter. |
| Industry type | 🟥 — no industry classifier. |
| Audience type | 🟡 — passed into prompts. |
| Presentation tone | 🟡 — passed into prompts. |
| Existing templates | 🟥 — no template reuse. |
| Previous decks | 🟥 — no per-user style memory. |

**Honest:** §12 is the single most over-claimed area in HONEST_STATUS. Code looks like it works because the API roundtrip succeeds; the exporter ignores it.

---

## §13. Image & Asset Management

| Capability | Status |
|---|---|
| Upload custom images | ✅ — `routes/assets.py` POST. |
| Replace AI-generated images in editor | 🟡 — endpoint exists; UI hookup partial. |
| Maintain asset libraries | ✅ — `Asset` model with tags. |
| Save reusable visual sets | 🟥 — no "set" abstraction. |
| Organize icons/graphics | 🟡 — tags only, no folders. |
| Workspace-level media collections | 🟡 — `workspace_id` FK on assets, but no scoping UI. |

---

## §14. Web-Based Slide Editor

| Feature | Status |
|---|---|
| Drag-and-drop editing | 🟥 — no shape-level drag. |
| Image replacement | 🟡 — backend ready; UI flow incomplete. |
| Layout editing | 🟡 — can change `layout` value via dropdown; no visual layout picker. |
| Chart editing | 🟥 — chart re-edit not implemented. |
| Text editing | ✅ — inline title/bullet edit. |
| AI-assisted regeneration | 🟡 — regenerate-deck only; no per-slide regenerate UI. |
| Slide duplication | ✅ |
| Theme switching | ✅ |
| Version history | ✅ — `routes/versions.py` + sidebar. |
| Auto-save | 🟡 — debounced PUT on edit, not battle-tested. |

---

## §15. AI Editing Assistant

| Capability | Status |
|---|---|
| Rewriting content | 🟥 |
| Make slides more visual | 🟥 |
| Replacing images | 🟡 (manual) |
| Generating diagrams | 🟥 |
| Improving storytelling | 🟥 |
| Simplifying dense content | 🟥 |
| Tone changes | 🟥 |

**Brutal:** §15 is **not built**. There is no in-editor AI assistant chat. Only full-deck regenerate.

---

## §16. Developer Experience

| Surface | Status |
|---|---|
| REST APIs | ✅ — 21+ endpoints. |
| TypeScript SDK | 🟡 — `sdk/src/client.ts` exists, npm package not published, no integration tests. |
| React SDK | 🟡 — `<PPTGenerator/>`, `<NexusDeck/>` components in `sdk/src/react/`. **Never tested in a host app.** |
| Next.js integration | 🟥 — no app-router example. |
| White-label mode | 🟥 — no theming-of-editor knob. |
| Webhooks | ⚠️ — `routes/webhooks.py` exists, HMAC code present, **never delivered to a real endpoint and verified.** |
| OpenAPI docs | ✅ — FastAPI auto. |
| Embeddable editor components | 🟥 — only generator widget; no embeddable editor. |

---

## §17. React SDK example

The PRD's exact snippet (`<PPTGenerator apiKey workspaceId enableAIImages />`) — we have the component but `enableAIImages` is not a prop today. Easy fix.

---

## §18. Backend Architecture

| PRD service | Have | Notes |
|---|---|---|
| API Gateway | 🟡 | Just FastAPI; no Kong/nginx in front. |
| Auth Service | ✅ | JWT + Google OAuth in `services/auth_service.py`. |
| Deck Generation Service | ✅ | `agent/loop.py`. |
| Context Management Service | 🟡 | `services/context_extractor.py` parses; doesn't store structured. |
| Image Recommendation Service | ✅ | `services/image_service.py`. |
| Image Generation Service | 🟡 | Pollinations only. |
| File Processing Service | 🟡 | Synchronous, in-process. |
| Vector Database | 🟥 | **Not present.** No embeddings, no semantic search. |
| Chart Generation Service | ✅ | `services/chart_service.py`. |
| Export Service | 🟡 | PPTX yes; PDF/PNG no. |
| Queue Workers | ✅ | Celery + Redis. |

---

## §19. Recommended Tech Stack

| PRD | We have |
|---|---|
| React + Next.js + TS | React + Vite + JSX (no Next.js, no TS in app code; SDK is TS) |
| Node/Nest/FastAPI | FastAPI ✅ |
| PostgreSQL | ✅ |
| Pinecone / pgvector | 🟥 |
| BullMQ / Temporal | Celery (close enough) |
| S3 / R2 | ✅ via boto3, local fallback |
| OpenAI / Gemini / Claude | Groq llama-3.3-70b primary; NIM/OpenRouter fallback. **No Claude/GPT-4 in production.** |
| OpenAI Images / Flux / Stability | 🟥 (Pollinations only) |
| Recharts / ECharts | Recharts in editor ✅ |
| pptxgenjs | We use **python-pptx**, not pptxgenjs. Equivalent capability, different stack. |

---

## §20. Scalability Requirements

| Requirement | Status |
|---|---|
| Thousands of concurrent users | 🟥 — never load-tested. |
| Queue-based generation | ✅ |
| Background rendering | ✅ |
| Parallel image processing | ✅ — `asyncio.Semaphore(4)` |
| Horizontal worker scaling | 🟡 — Celery supports it, no orchestration manifest. |
| CDN asset delivery | 🟥 — local FS / R2 direct only. |

---

## §21. Security Requirements

| Requirement | Status |
|---|---|
| RBAC | 🟡 — owner-only checks per resource; no roles table. |
| Secure uploads | 🟡 — file-type allowlist, no virus scan. |
| Encrypted storage | 🟥 — files at rest in plaintext. |
| API key rotation | ✅ — `routes/api_keys.py POST /rotate`. |
| Workspace isolation | 🟡 — `workspace_id` FK present; not all queries filter by it. **Audit needed.** |
| Audit logs | 🟡 — endpoint reads logs; not every mutation writes one. |
| SSO support | 🟡 — Google OAuth only; no SAML/OIDC enterprise SSO. |

---

## §22. MVP Scope

| MVP item | Status |
|---|---|
| Prompt-to-PPT | ✅ |
| Context uploads | 🟡 (parsed, not deeply used) |
| AI image support | ✅ |
| Charts and graphs | ✅ |
| Basic editor | ✅ |
| PPTX export | ✅ |
| PDF export | 🟥 |
| REST API | ✅ |
| React SDK | 🟡 |

**MVP completion: ~75%.** PDF export is the only hard MVP miss.

---

## §23. Future Enhancements (intentionally out)

All 🟥 — collab, Google Slides, Figma, video, animation, marketplace, voice. Not promised, not built.

---

## §24. Product Positioning

We're at **~55%** of the positioning statement. The platform converts prompts into editable PPTX; "structured + unstructured business context into industry-grade presentations with charts, images, insights, storytelling, and visual design" overstates today's reality.

---

## TL;DR Scorecard

| Pillar | % shipped | Single biggest gap |
|---|---|---|
| §1–2 Vision/Objectives | 70% | PDF/PNG export missing; uploads parsed but not structurally used. |
| §3–4 Image intelligence | 60% | No background-removal, no face-aware crop, no industry taxonomy. |
| §5 Visual recommender | 55% | All heuristic; no LLM-driven recommender; no infographics. |
| §6 Multi-format ingest | 30% | Files parsed → text only. KPI extraction never reaches charts. |
| §7 Text→chart | 20% | Numeric NLP→ChartSpec missing. |
| §8 Planning | 65% | No narrative-arc model; planner overridden by markdown pipeline. |
| §9 Slide JSON | 75% | **Speaker notes never generated.** Visual-hierarchy metadata absent. |
| §10 Visual-first design | 60% | Frontend `SlideRenderer.layouts` dict registers only 10 of ~18 backend layouts → silent fallback to TitleSlide. **Real bug.** |
| §11 Image placement | 35% | No contrast/blur/face-aware logic. |
| §12 Brand-aware | 15% | Brand-kit data never reaches exporter. **Most over-claimed area.** |
| §13 Asset mgmt | 70% | No "visual sets", no folders. |
| §14 Editor | 45% | No drag-drop, no chart editor. |
| §15 AI editing assistant | 5% | Not built. |
| §16 DX (SDK/webhooks) | 50% | SDK never published; webhooks never delivered. |
| §17 React example | 40% | `enableAIImages` prop missing. |
| §18 Architecture | 70% | No vector DB. |
| §19 Tech stack | 65% | No Claude/GPT-4 (Groq only); no Flux/Stability; React not Next.js. |
| §20 Scalability | 40% | Never load-tested. |
| §21 Security | 50% | No encryption-at-rest, audit-log coverage incomplete. |
| §22 MVP | 75% | PDF export. |

**Weighted average: ~52% PRD-complete.**

---

## What needs to ship next, ranked by impact-per-hour

### Tier 1 — Visible quality wins (small effort)

1. **Register backend-only layouts in frontend `SlideRenderer.layouts`** — bento, feature-grid, callout, agenda, roadmap, process, metric-spotlight, hero, pyramid, matrix-2x2. Without this, half of every deck silently renders as TitleSlide. _Impact: huge. Effort: ~4 h._
2. **Wire brand-kit colors + fonts into `export_service.py`** — replace hardcoded fallbacks with `brand_kit.primary_color` / `body_font` per task. _Impact: enterprise-grade. Effort: ~2 h._
3. **Add PDF export** via LibreOffice headless (`unoconv`/`libreoffice --headless --convert-to pdf`) or via PPTX → PNG rasterizer. _Impact: closes MVP. Effort: ~3 h._
4. **Generate speaker notes** in markdown pipeline — append `_NOTES_:` section per slide; write into `slide.notesSlide` in `python-pptx`. _Impact: PRD §9 compliance. Effort: ~2 h._
5. **Build `services/reference_service.py`** (in-progress this session) — local PPTX analysis index + SlideShare scraper to bias planner toward proven layout sequences. _Impact: directly attacks "look like Manus." Effort: ~6 h._

### Tier 2 — Structural intelligence (medium effort)

6. **Text→Chart extractor** — regex/LLM hybrid that pulls `(metric, value, year)` triples from prose and emits ChartSpec. Targets PRD §7. _Effort: ~1 day._
7. **Structured ingest** — when an XLSX is uploaded, surface the columns to the planner as candidate chart inputs, not just text. PRD §6. _Effort: ~1 day._
8. **In-editor AI assistant** — single-slide regenerate / rewrite / "make more visual" buttons calling existing per-slide endpoints. PRD §15. _Effort: ~2 days._
9. **Contrast-aware image overlay** — compute mean luminance of selected stock photo, flip overlay text color. PRD §11. _Effort: ~2 h._

### Tier 3 — Platform credibility (larger)

10. **Vector DB for "previous decks" memory** — pgvector + per-workspace deck embedding index. PRD §12, §18. _Effort: ~2 days._
11. **HTML→PNG slide renderer** — Playwright + Tailwind templates per layout, used as one of the export formats. The single biggest item to close the Manus visual gap. _Effort: ~1 week._
12. **Webhook end-to-end test** — real receiver, signature verification, retry policy. PRD §16. _Effort: ~half day._
13. **Load test harness** — Locust against `/api/generate` with N concurrent tasks. PRD §20. _Effort: ~1 day._

### Tier 4 — Enterprise grade

14. SSO (SAML/OIDC), encryption at rest, virus-scan uploads, audit-log coverage to 100% mutations. PRD §21.
15. White-label mode, embeddable editor, Next.js example app. PRD §16.

---

## Self-criticism

- HONEST_STATUS.md said "5 themes wired" — actually now 69. Drift between docs and code. **Fix:** generate this audit programmatically next time.
- HONEST_STATUS.md said `run.font.name = "Inter"` is hardcoded — actually now `font_name` variable (see `export_service.py:448`). Fixed since that doc.
- I keep shipping plumbing without an end-to-end check. The frontend layouts dict missing 8 backend layouts is the perfect example: backend "ships" the layout, exporter renders it correctly in PPTX, frontend silently degrades. Nobody sees it because most users only download the PPTX.
- I have **zero** automated tests for the agent pipeline. Every "verified" claim in this doc was eyeballed.

---

## Bottom line

Across 24 PRD sections, ~**52% PRD-complete**. The core (prompt → PPTX with images, charts, themes, hero shots, layout diversity) **works and looks decent**. The enterprise / brand / asset / collaboration / multi-format-context layers are mostly **stubs that compile**.

Highest-leverage next session: **Tier 1 items 1–5 in order**. They cost ~17 hours total and would lift the visible quality more than any LLM upgrade.
