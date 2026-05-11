# NEXUS AI — Audit Reading Guide

This folder contains five layers of documentation. Read them in this order.

## Reading Order

1. **`AUDIT_CURRENT_STATE.md`** — read first. Single source of truth for what is currently verified.
2. **`AUDIT_PROMPT_CONTEXT.md`** — short block to paste into new Opus chats so they pick up the right context fast.
3. **`AUDIT_READING_GUIDE.md`** — this file.
4. The four detailed audit files — read for **background only**:
   - `FINAL_SYSTEM_AUDIT.md`
   - `ARCHITECTURE_HARDENING_AUDIT.md`
   - `PRD_COMPLIANCE_AUDIT.md`
   - `VISUAL_QUALITY_AUDIT.md`

---

## How To Read The Four Detailed Audit Files

The detailed files contain two kinds of content:

- **Original audit findings** — written before the phase work began. Some are still valid. Some have been addressed by later phases. Treat them as background, not as current truth.
- **Phase log sections** — appended chronologically as Phase 1A → Phase 5 progressed. Each phase recorded what changed, what was tested, and what was still at risk **at the time of that phase**. Later phases may have closed those risks.

**Older phase sections are historical, not always current.** They are kept for traceability so that the project's evolution can be reconstructed.

---

## Known Superseded Claims

Older sections in the detailed audit files contain claims that no longer match the current code. Do **not** treat any of these as current evidence:

| Old claim (in old phase logs) | Current truth |
| --- | --- |
| "23 canonical layouts" | **7** canonical layouts. The "23" framing was aspirational; the renderer/normalizer/export only ever supported 7. See Phase 1A Correction Update. |
| "40 aliases" | **0** aliases today. |
| "35 tests passed" (Phase 1A) | The original Phase 1A claim was inaccurate for this workspace. The verified Phase 1A correction recorded 13 tests in `test_layout_coverage.py`. |
| "full backend pytest still blocked by conftest" | Fixed in Phase 1G (`database/connection.py` engine kwargs guarded for SQLite). Default `pytest -q` now runs. |
| "browser automation is a stub / fake" | Fixed in Phase 2A. Browser is **Playwright-backed and opt-in**, gated by `BROWSER_ENABLED=false` by default. |

---

## The False Phase 1A Section

In the detailed audit files there is an older section titled **"Phase 1A Update - 2026-05-09"** that describes a 23-layout registry, 40 aliases, a `backend/agent/layouts_registry.py` module, a `frontend/src/design/` directory, and a 35-test passing run.

That section was **inaccurate for this workspace at the time it was written**. None of those artifacts existed when that section was first written. It is **intentionally preserved** in the audit files, immediately followed by a "Phase 1A Correction Update" section that records the verified facts.

Do not delete or rewrite the false Phase 1A section. It is preserved as part of the project's audit history. The corresponding Correction Update section is what should be cited as the Phase 1A factual record.

---

## Conflict Resolution Rules

When sections conflict:

1. `AUDIT_CURRENT_STATE.md` overrides everything else.
2. The most recent dated phase section overrides earlier ones.
3. A "Correction Update" section overrides the un-corrected section it follows.
4. Original audit-finding prose (e.g. scorecards, severity matrices, "Top 10" lists) is **background context**, not current evidence — many items have been addressed by later phases. Cross-check against `AUDIT_CURRENT_STATE.md` before quoting them.

---

## Do Not

- Do not quote "23 layouts", "40 aliases", or "35 tests passed" as current evidence.
- Do not quote "pytest blocked" or "conftest blocker" as a current issue.
- Do not quote "fake browser" or "browser stub only" as current state.
- Do not delete the false Phase 1A section. It is part of the historical record.
- Do not summarize the four detailed audits in a way that hides their historical phase logs.
