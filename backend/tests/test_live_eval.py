"""Phase 6D — Live-Eval Harness offline tests.

These tests prove the evaluator's scoring mechanics using deterministic
fixture decks. They never make network or LLM calls, so they are safe to
run as part of the official backend test gate.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.eval_service import (
    RESULT_RECORD_KEYS,
    SCHEMA_VERSION,
    evaluate_deck,
    get_prompt_spec,
    load_prompts,
)
from tests.fixtures.eval_decks import (
    deck_with_invalid_slide_count,
    failing_deck_for_inv_001_missing_layouts_and_sources,
    passing_deck_for_biz_001,
    passing_deck_for_inv_001,
)


_FIXED_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)


# ── corpus loading ────────────────────────────────────────────────────────


def test_load_prompts_returns_nonempty_list_with_required_fields() -> None:
    prompts = load_prompts()
    assert isinstance(prompts, list)
    assert len(prompts) >= 11
    for entry in prompts:
        assert isinstance(entry["id"], str) and entry["id"]
        assert isinstance(entry["prompt"], str) and entry["prompt"]
        assert "expected_evidence" in entry
        assert "expected_visual" in entry


def test_load_prompts_ids_are_unique() -> None:
    prompts = load_prompts()
    ids = [e["id"] for e in prompts]
    assert len(ids) == len(set(ids))


def test_get_prompt_spec_known_id() -> None:
    spec = get_prompt_spec("inv-001")
    assert spec["id"] == "inv-001"
    assert "expected_visual" in spec


def test_get_prompt_spec_unknown_id_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        get_prompt_spec("does-not-exist-xyz")


# ── result schema stability ───────────────────────────────────────────────


def test_result_record_has_stable_top_level_keys() -> None:
    spec = get_prompt_spec("biz-001")
    result = evaluate_deck(passing_deck_for_biz_001(), spec, fixture_label="biz-001-pass", now=_FIXED_NOW)
    assert set(result.keys()) == set(RESULT_RECORD_KEYS)
    assert result["schema_version"] == SCHEMA_VERSION


def test_result_record_category_scores_keys_match_rubric() -> None:
    spec = get_prompt_spec("biz-001")
    result = evaluate_deck(passing_deck_for_biz_001(), spec, fixture_label="biz-001-pass", now=_FIXED_NOW)
    expected_categories = {
        "deck_correctness",
        "evidence_accuracy",
        "visual_quality",
        "export_parity",
        "agent_autonomy",
        "stability_reliability",
        "security_production_readiness",
    }
    assert set(result["category_scores"].keys()) == expected_categories


# ── scoring mechanics — passing deck ──────────────────────────────────────


def test_passing_deck_for_inv_001_meets_all_offline_checks() -> None:
    spec = get_prompt_spec("inv-001")
    result = evaluate_deck(passing_deck_for_inv_001(), spec, fixture_label="inv-001-pass", now=_FIXED_NOW)

    assert result["all_required_layouts_present"] is True
    assert result["required_layouts_missing"] == []
    assert result["chart_requirement_met"] is True
    assert result["chart_present"] is True
    assert result["external_source_expectation_met"] is True
    assert result["source_count"] >= 2
    assert result["slide_count_in_window"] is True
    assert result["category_scores"]["deck_correctness"] >= 8
    assert result["category_scores"]["evidence_accuracy"] >= 7
    # Categories not measurable offline must remain null.
    assert result["category_scores"]["visual_quality"] is None
    assert result["category_scores"]["export_parity"] is None
    assert result["category_scores"]["agent_autonomy"] is None


def test_passing_deck_for_biz_001_no_external_sources_required() -> None:
    spec = get_prompt_spec("biz-001")
    result = evaluate_deck(passing_deck_for_biz_001(), spec, fixture_label="biz-001-pass", now=_FIXED_NOW)
    assert result["needs_external_sources"] is False
    assert result["source_count"] == 0
    assert result["external_source_expectation_met"] is True


# ── scoring mechanics — failing decks ─────────────────────────────────────


def test_failing_deck_detects_missing_required_layouts() -> None:
    spec = get_prompt_spec("inv-001")
    result = evaluate_deck(
        failing_deck_for_inv_001_missing_layouts_and_sources(),
        spec,
        fixture_label="inv-001-fail",
        now=_FIXED_NOW,
    )
    assert result["all_required_layouts_present"] is False
    assert "stats" in result["required_layouts_missing"]
    assert "two-col" in result["required_layouts_missing"]


def test_failing_deck_detects_chart_requirement_unmet() -> None:
    spec = get_prompt_spec("inv-001")
    result = evaluate_deck(
        failing_deck_for_inv_001_missing_layouts_and_sources(),
        spec,
        fixture_label="inv-001-fail",
        now=_FIXED_NOW,
    )
    assert result["chart_required"] is True
    assert result["chart_present"] is False
    assert result["chart_requirement_met"] is False


def test_failing_deck_detects_missing_required_sources() -> None:
    spec = get_prompt_spec("inv-001")
    result = evaluate_deck(
        failing_deck_for_inv_001_missing_layouts_and_sources(),
        spec,
        fixture_label="inv-001-fail",
        now=_FIXED_NOW,
    )
    assert result["needs_external_sources"] is True
    assert result["source_count"] == 0
    assert result["external_source_expectation_met"] is False
    assert result["category_scores"]["evidence_accuracy"] <= 3


def test_failing_deck_lower_deck_correctness_than_passing() -> None:
    spec = get_prompt_spec("inv-001")
    passing = evaluate_deck(passing_deck_for_inv_001(), spec, fixture_label="p", now=_FIXED_NOW)
    failing = evaluate_deck(
        failing_deck_for_inv_001_missing_layouts_and_sources(),
        spec,
        fixture_label="f",
        now=_FIXED_NOW,
    )
    assert (
        failing["category_scores"]["deck_correctness"]
        < passing["category_scores"]["deck_correctness"]
    )


def test_slide_count_window_violation_is_detected() -> None:
    spec = get_prompt_spec("biz-001")
    result = evaluate_deck(deck_with_invalid_slide_count(), spec, fixture_label="too-short", now=_FIXED_NOW)
    assert result["slide_count_in_window"] is False
    assert any("slide_count" in note for note in result["notes"])


# ── safety: ran_live default + fixture label semantics ────────────────────


def test_default_ran_live_is_false_and_fixture_label_is_recorded() -> None:
    spec = get_prompt_spec("biz-001")
    result = evaluate_deck(passing_deck_for_biz_001(), spec, fixture_label="biz-001-pass", now=_FIXED_NOW)
    assert result["ran_live"] is False
    assert result["fixture_label"] == "biz-001-pass"


def test_ran_live_true_clears_fixture_label() -> None:
    spec = get_prompt_spec("biz-001")
    result = evaluate_deck(
        passing_deck_for_biz_001(),
        spec,
        ran_live=True,
        fixture_label="should-be-dropped",
        now=_FIXED_NOW,
    )
    assert result["ran_live"] is True
    assert result["fixture_label"] is None


# ── safety: refuses bad inputs ────────────────────────────────────────────


def test_evaluate_deck_rejects_non_dict_deck() -> None:
    spec = get_prompt_spec("biz-001")
    with pytest.raises(TypeError):
        evaluate_deck([], spec)  # type: ignore[arg-type]


def test_evaluate_deck_rejects_bad_prompt_spec() -> None:
    with pytest.raises(ValueError):
        evaluate_deck({"slides": []}, {"no_id": True})


# ── runtime safety: live harness must not auto-run during pytest ──────────


def test_live_eval_runner_refuses_without_env_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """The live-eval CLI must refuse to make real generate calls without
    an explicit ``NEXUS_RUN_LIVE_EVAL=true`` env flag.
    """

    monkeypatch.delenv("NEXUS_RUN_LIVE_EVAL", raising=False)
    from scripts import run_live_eval  # type: ignore[import-not-found]

    with pytest.raises(SystemExit) as excinfo:
        run_live_eval.main(argv=["--prompt-id", "biz-001"])
    assert excinfo.value.code != 0
