"""Phase 6J - Offline validator for committed live-eval result JSON files.

Live evaluation is gated behind ``NEXUS_RUN_LIVE_EVAL=true`` and is not
part of the backend test gate. Once a live run produces a per-prompt
record and a redacted/safe copy is committed under
``audits/LIVE_EVAL_RESULTS/``, this test guarantees the committed copy
still conforms to the contract described by ``benchmarks/eval_schema.json``.

The test:
  * is fully offline,
  * does not call ``/api/generate`` or any LLM/search provider,
  * does not create or mutate any files,
  * skips cleanly when no committed results exist yet.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# benchmarks/ is mounted at /benchmarks inside the official test gate,
# but the repo layout also has benchmarks/ at the repo root so local
# pytest invocations work too.
_REPO_ROOT_CANDIDATES = (
    Path("/benchmarks"),
    Path(__file__).resolve().parents[2] / "benchmarks",
)


def _find_schema() -> Path:
    for cand in _REPO_ROOT_CANDIDATES:
        schema = (cand / "eval_schema.json") if cand.name == "benchmarks" else (cand / "eval_schema.json")
        if schema.exists():
            return schema
    pytest.skip("benchmarks/eval_schema.json not found in expected locations")


def _find_results_dir() -> Path | None:
    candidates = (
        Path("/live_eval_results"),
        Path(__file__).resolve().parents[2] / "audits" / "LIVE_EVAL_RESULTS",
    )
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return None


def _expected_top_level_keys(schema: dict) -> set[str]:
    return set(schema["result_record"].keys())


def _expected_category_keys(schema: dict) -> set[str]:
    return set(schema["result_record"]["category_scores"].keys())


def _committed_result_files() -> list[Path]:
    rdir = _find_results_dir()
    if rdir is None:
        return []
    return sorted(p for p in rdir.glob("*.json") if p.is_file())


def test_committed_live_eval_results_match_schema_keys() -> None:
    """Every committed result must have exactly the schema's top-level keys."""

    schema_path = _find_schema()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    expected_top = _expected_top_level_keys(schema)
    expected_cats = _expected_category_keys(schema)

    files = _committed_result_files()
    if not files:
        pytest.skip("no committed live-eval results under audits/LIVE_EVAL_RESULTS/")

    for fpath in files:
        record = json.loads(fpath.read_text(encoding="utf-8"))

        assert isinstance(record, dict), f"{fpath.name}: top-level must be an object"
        actual_top = set(record.keys())
        assert actual_top == expected_top, (
            f"{fpath.name}: top-level keys mismatch.\n"
            f"  missing: {sorted(expected_top - actual_top)}\n"
            f"  extra:   {sorted(actual_top - expected_top)}"
        )

        cats = record["category_scores"]
        assert isinstance(cats, dict), f"{fpath.name}: category_scores must be an object"
        assert set(cats.keys()) == expected_cats, (
            f"{fpath.name}: category_scores keys mismatch.\n"
            f"  missing: {sorted(expected_cats - set(cats.keys()))}\n"
            f"  extra:   {sorted(set(cats.keys()) - expected_cats)}"
        )


def test_committed_live_eval_results_field_types() -> None:
    """Strict type spot-checks for the offline-measurable fields."""

    files = _committed_result_files()
    if not files:
        pytest.skip("no committed live-eval results under audits/LIVE_EVAL_RESULTS/")

    bool_fields = (
        "slide_count_in_window",
        "all_required_layouts_present",
        "chart_required",
        "chart_present",
        "chart_requirement_met",
        "needs_external_sources",
        "external_source_expectation_met",
        "ran_live",
    )
    int_fields = (
        "generated_slide_count",
        "source_count",
        "min_sources_required",
    )
    list_fields = (
        "required_layouts_present",
        "required_layouts_missing",
        "notes",
    )
    str_fields = (
        "schema_version",
        "prompt_id",
        "prompt",
        "kind",
        "difficulty",
        "timestamp_utc",
    )

    for fpath in files:
        rec = json.loads(fpath.read_text(encoding="utf-8"))

        for k in bool_fields:
            assert isinstance(rec[k], bool), f"{fpath.name}: {k} must be bool"
        for k in int_fields:
            assert isinstance(rec[k], int) and not isinstance(rec[k], bool), (
                f"{fpath.name}: {k} must be int"
            )
        for k in list_fields:
            assert isinstance(rec[k], list), f"{fpath.name}: {k} must be list"
        for k in str_fields:
            assert isinstance(rec[k], str) and rec[k], f"{fpath.name}: {k} must be non-empty str"

        # deck_quality fields may be null OR int/bool.
        dqo = rec["deck_quality_ok"]
        assert dqo is None or isinstance(dqo, bool), (
            f"{fpath.name}: deck_quality_ok must be bool|null"
        )
        dqi = rec["deck_quality_invalid_count"]
        assert dqi is None or (isinstance(dqi, int) and not isinstance(dqi, bool)), (
            f"{fpath.name}: deck_quality_invalid_count must be int|null"
        )

        # fixture_label must be null when ran_live, else a non-empty string.
        if rec["ran_live"]:
            assert rec["fixture_label"] is None, (
                f"{fpath.name}: ran_live=true requires fixture_label=null"
            )
        else:
            assert isinstance(rec["fixture_label"], str) and rec["fixture_label"], (
                f"{fpath.name}: ran_live=false requires non-empty fixture_label"
            )

        # category_scores: offline-measurable categories must be 1-10 int;
        # the rest must be null.
        cats = rec["category_scores"]
        for k in ("deck_correctness", "evidence_accuracy"):
            v = cats[k]
            assert isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 10, (
                f"{fpath.name}: category_scores.{k} must be int 1..10, got {v!r}"
            )
        for k in (
            "visual_quality",
            "export_parity",
            "agent_autonomy",
            "stability_reliability",
            "security_production_readiness",
        ):
            assert cats[k] is None, (
                f"{fpath.name}: category_scores.{k} must be null per schema, got {cats[k]!r}"
            )
