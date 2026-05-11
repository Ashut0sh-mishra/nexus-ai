"""Phase 6D — Live-Eval Harness Foundation (offline-pure).

This module implements a deterministic, offline evaluator that takes a
*deck dict* and a *prompt spec* (from ``benchmarks/prompts.json``) and
returns a structured result record matching ``benchmarks/eval_schema.json``.

Design contract:

* No network calls. No LLM calls. No filesystem writes. Pure function.
* Per-category scores are filled only when measurable from a deck dict
  alone. Categories that require visual diff, runtime telemetry, or
  global gate measurement are set to ``None`` with an explanatory note.
* Safe to call from tests without any docker/db setup.

The harness CLI (``backend/scripts/run_live_eval.py``) is responsible for
fetching real decks (gated by ``NEXUS_RUN_LIVE_EVAL=true``) and feeding
them into :func:`evaluate_deck`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # deck_quality is dependency-light but optional for the evaluator
    from agent.deck_quality import build_deck_quality_report
except Exception:  # pragma: no cover - tested via fixture
    build_deck_quality_report = None  # type: ignore[assignment]


SCHEMA_VERSION = "1.0"


def _candidate_benchmarks_dirs() -> tuple[Path, ...]:
    here = Path(__file__).resolve()
    candidates: list[Path] = [Path("/benchmarks")]
    for depth in (2, 3):
        try:
            candidates.append(here.parents[depth] / "benchmarks")
        except IndexError:
            continue
    return tuple(candidates)


def _benchmarks_dir() -> Path:
    for candidate in _candidate_benchmarks_dirs():
        if candidate.is_dir() and (candidate / "prompts.json").is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate benchmarks/ directory. Looked in: "
        + ", ".join(str(c) for c in _candidate_benchmarks_dirs())
    )


def load_prompts(path: Path | None = None) -> list[dict[str, Any]]:
    """Load and return the prompt list from ``benchmarks/prompts.json``.

    Validates that every entry has the fields the evaluator depends on.
    Raises ``ValueError`` if the corpus is malformed or empty.
    """

    prompts_path = path or (_benchmarks_dir() / "prompts.json")
    with prompts_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    prompts = data.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        raise ValueError(f"prompts.json at {prompts_path} has no prompts list")
    seen_ids: set[str] = set()
    for entry in prompts:
        for required_field in ("id", "prompt", "expected_evidence", "expected_visual"):
            if required_field not in entry:
                raise ValueError(
                    f"prompts.json entry missing required field {required_field!r}: {entry}"
                )
        if entry["id"] in seen_ids:
            raise ValueError(f"prompts.json contains duplicate id {entry['id']!r}")
        seen_ids.add(entry["id"])
    return prompts


def get_prompt_spec(prompt_id: str, prompts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return the prompt spec for ``prompt_id`` or raise ``KeyError``."""

    corpus = prompts if prompts is not None else load_prompts()
    for entry in corpus:
        if entry["id"] == prompt_id:
            return entry
    raise KeyError(f"Unknown prompt_id: {prompt_id!r}")


def _collect_layouts(slides: list[dict[str, Any]]) -> list[str]:
    return [str(s.get("layout", "")).lower() for s in slides if isinstance(s, dict)]


def _count_sources(deck: dict[str, Any]) -> int:
    """Count unique sources across deck-level and per-slide.

    Sources are deduplicated by ``url`` if present, otherwise by their
    full repr.
    """

    seen: set[str] = set()

    def _add(item: Any) -> None:
        if isinstance(item, dict):
            key = item.get("url") or json.dumps(item, sort_keys=True, default=str)
        else:
            key = str(item)
        seen.add(key)

    for src in deck.get("sources", []) or []:
        _add(src)
    for slide in deck.get("slides", []) or []:
        if isinstance(slide, dict):
            for src in slide.get("sources", []) or []:
                _add(src)
    return len(seen)


def _score_deck_correctness(
    *,
    slide_count_in_window: bool,
    all_required_layouts_present: bool,
    chart_requirement_met: bool,
    deck_quality_ok: bool | None,
    deck_quality_invalid_count: int | None,
) -> int:
    """Offline-measurable 1-10 score for deck_correctness.

    Heuristic, deterministic. Not a measurement of LLM accuracy. Used to
    surface regressions in the schema/layout pipeline.
    """

    score = 4  # baseline if a deck exists at all
    if slide_count_in_window:
        score += 2
    if all_required_layouts_present:
        score += 2
    if chart_requirement_met:
        score += 1
    if deck_quality_ok is True:
        score += 1
    elif deck_quality_ok is False and (deck_quality_invalid_count or 0) > 0:
        score -= 1
    return max(1, min(10, score))


def _score_evidence_accuracy(
    *,
    needs_external_sources: bool,
    min_sources_required: int,
    source_count: int,
    claim_level_required: bool,
) -> int:
    """Partial offline score: deck-level source count only.

    Claim-level citation is not yet implemented in NEXUS, so prompts that
    require it cannot reach the top of the scale from offline data alone.
    """

    if not needs_external_sources:
        # Not penalized for missing sources when none are required.
        return 7
    if source_count <= 0:
        return 2
    if source_count < min_sources_required:
        return 4
    base = 7
    if source_count >= max(min_sources_required + 1, 3):
        base = 8
    if claim_level_required:
        # Capped because claim-level mapping does not exist.
        base = min(base, 6)
    return max(1, min(10, base))


def evaluate_deck(
    deck: dict[str, Any],
    prompt_spec: dict[str, Any],
    *,
    ran_live: bool = False,
    fixture_label: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate a deck against a prompt spec and return a result record.

    Pure / offline. Does not perform any network or filesystem operations.

    Args:
        deck: Normalized deck dict, expected to contain at minimum
            ``slides: list[dict]`` and optionally ``sources: list``.
        prompt_spec: An entry from ``benchmarks/prompts.json``.
        ran_live: Set to True only when this deck came from a real
            ``/api/generate`` run. The harness CLI flips this; tests
            keep it False.
        fixture_label: Identifier for the fixture deck when not live.
        now: Override timestamp for deterministic tests.

    Returns:
        A dict matching ``benchmarks/eval_schema.json``.
    """

    if not isinstance(deck, dict):
        raise TypeError("deck must be a dict")
    if not isinstance(prompt_spec, dict) or "id" not in prompt_spec:
        raise ValueError("prompt_spec must be a prompts.json entry with an 'id'")

    slides_raw = deck.get("slides") or []
    slides: list[dict[str, Any]] = [s for s in slides_raw if isinstance(s, dict)]
    layouts_present = _collect_layouts(slides)

    expected_visual = prompt_spec.get("expected_visual", {}) or {}
    expected_evidence = prompt_spec.get("expected_evidence", {}) or {}

    required_layouts = [str(l).lower() for l in expected_visual.get("required_layouts", []) or []]
    layouts_present_set = set(layouts_present)
    required_present = sorted(l for l in required_layouts if l in layouts_present_set)
    required_missing = sorted(l for l in required_layouts if l not in layouts_present_set)
    all_required_present = not required_missing

    slide_count = len(slides)
    min_slides = int(expected_visual.get("min_slides", 0) or 0)
    max_slides_val = expected_visual.get("max_slides")
    max_slides = int(max_slides_val) if isinstance(max_slides_val, int) else None
    slide_count_in_window = slide_count >= min_slides and (
        max_slides is None or slide_count <= max_slides
    )

    chart_required = bool(expected_visual.get("chart_required", False))
    chart_present = "chart" in layouts_present_set
    chart_requirement_met = (not chart_required) or chart_present

    needs_external = bool(expected_evidence.get("needs_external_sources", False))
    min_sources_required = int(expected_evidence.get("min_sources", 0) or 0)
    claim_level_required = bool(expected_evidence.get("claim_level_required", False))
    source_count = _count_sources(deck)
    if needs_external:
        external_met = source_count >= max(1, min_sources_required)
    else:
        external_met = True

    deck_quality_ok: bool | None = None
    deck_quality_invalid_count: int | None = None
    if build_deck_quality_report is not None and slides:
        try:
            report = build_deck_quality_report(slides)
            deck_quality_ok = bool(report.ok)
            deck_quality_invalid_count = int(report.invalid_count)
        except Exception:  # pragma: no cover - defensive
            deck_quality_ok = None
            deck_quality_invalid_count = None

    notes: list[str] = []
    if required_missing:
        notes.append(f"missing required layouts: {required_missing}")
    if chart_required and not chart_present:
        notes.append("chart_required=true but no 'chart' layout slide found")
    if needs_external and source_count < min_sources_required:
        notes.append(
            f"source_count {source_count} < min_sources {min_sources_required}"
        )
    if not slide_count_in_window:
        notes.append(
            f"slide_count {slide_count} outside window [{min_slides}, {max_slides}]"
        )
    notes.append("visual_quality: unmeasured offline (requires screenshot diff)")
    notes.append("export_parity: unmeasured per-prompt (covered by Phase 6C content tests)")
    notes.append("agent_autonomy: unmeasured offline (requires runtime telemetry)")
    notes.append("stability/security: measured at gate level, not per prompt")

    deck_correctness_score = _score_deck_correctness(
        slide_count_in_window=slide_count_in_window,
        all_required_layouts_present=all_required_present,
        chart_requirement_met=chart_requirement_met,
        deck_quality_ok=deck_quality_ok,
        deck_quality_invalid_count=deck_quality_invalid_count,
    )
    evidence_score = _score_evidence_accuracy(
        needs_external_sources=needs_external,
        min_sources_required=min_sources_required,
        source_count=source_count,
        claim_level_required=claim_level_required,
    )

    timestamp = (now or datetime.now(timezone.utc)).isoformat()

    return {
        "schema_version": SCHEMA_VERSION,
        "prompt_id": prompt_spec["id"],
        "prompt": prompt_spec.get("prompt", ""),
        "kind": prompt_spec.get("kind", ""),
        "difficulty": prompt_spec.get("difficulty", ""),
        "generated_slide_count": slide_count,
        "slide_count_in_window": slide_count_in_window,
        "required_layouts_present": required_present,
        "required_layouts_missing": required_missing,
        "all_required_layouts_present": all_required_present,
        "chart_required": chart_required,
        "chart_present": chart_present,
        "chart_requirement_met": chart_requirement_met,
        "source_count": source_count,
        "needs_external_sources": needs_external,
        "min_sources_required": min_sources_required,
        "external_source_expectation_met": external_met,
        "deck_quality_ok": deck_quality_ok,
        "deck_quality_invalid_count": deck_quality_invalid_count,
        "category_scores": {
            "deck_correctness": deck_correctness_score,
            "evidence_accuracy": evidence_score,
            "visual_quality": None,
            "export_parity": None,
            "agent_autonomy": None,
            "stability_reliability": None,
            "security_production_readiness": None,
        },
        "notes": notes,
        "ran_live": bool(ran_live),
        "fixture_label": fixture_label if not ran_live else None,
        "timestamp_utc": timestamp,
    }


# Stable list of top-level keys in a result record — referenced by tests.
RESULT_RECORD_KEYS: tuple[str, ...] = (
    "schema_version",
    "prompt_id",
    "prompt",
    "kind",
    "difficulty",
    "generated_slide_count",
    "slide_count_in_window",
    "required_layouts_present",
    "required_layouts_missing",
    "all_required_layouts_present",
    "chart_required",
    "chart_present",
    "chart_requirement_met",
    "source_count",
    "needs_external_sources",
    "min_sources_required",
    "external_source_expectation_met",
    "deck_quality_ok",
    "deck_quality_invalid_count",
    "category_scores",
    "notes",
    "ran_live",
    "fixture_label",
    "timestamp_utc",
)
