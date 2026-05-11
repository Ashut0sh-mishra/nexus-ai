"""Phase 6B — benchmark data integrity tests.

Conftest-free, dependency-free. Validates the static JSON benchmark assets:

* `benchmarks/rubric.json` — weighted scoring rubric.
* `benchmarks/prompts.json` — realistic prompt corpus.

These tests do **not** call any LLM and do **not** evaluate generation quality.
They only verify that the benchmark fixtures are well-formed and internally
consistent with the audit's open-risk categories.

Run::

    python -m pytest --noconftest -p no:cacheprovider \
        backend/tests/test_competitive_benchmark.py -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _find_benchmarks_dir() -> Path | None:
    """Locate the benchmarks/ folder, or return None if it is not visible.

    Works whether tests run from the repo root (`nexus-ai/benchmarks/`)
    or inside the docker image where `backend/` is mounted at `/app/`
    and the benchmarks folder is mounted at `/benchmarks/`. Returns None
    if no valid candidate exists so the integrity tests can fail loudly
    instead of silently passing against a non-existent path.
    """
    here = Path(__file__).resolve()
    parents = list(here.parents)
    candidates = [
        parents[2] / "benchmarks" if len(parents) > 2 else None,  # nexus-ai/benchmarks
        Path("/benchmarks"),                                       # docker mount
        parents[3] / "benchmarks" if len(parents) > 3 else None,   # repo root one level up
    ]
    for c in candidates:
        if c is not None and c.is_dir():
            return c
    return None


_BENCH_DIR = _find_benchmarks_dir()
_RUBRIC_PATH = (_BENCH_DIR / "rubric.json") if _BENCH_DIR else None
_PROMPTS_PATH = (_BENCH_DIR / "prompts.json") if _BENCH_DIR else None


_MISSING_MOUNT_MSG = (
    "benchmarks/ directory not found. Phase 6B integrity tests require either "
    "<repo>/benchmarks/ on disk or a /benchmarks mount inside the container. "
    "Update scripts/test-backend.ps1 to mount the repo's benchmarks/ folder "
    "to /benchmarks (read-only)."
)

# Categories that must map to the audit's currently-tracked open risks.
EXPECTED_CATEGORIES = {
    "deck_correctness",
    "visual_quality",
    "export_parity",
    "evidence_accuracy",
    "agent_autonomy",
    "stability_reliability",
    "security_production_readiness",
}

EXPECTED_DIFFICULTIES = {"easy", "medium", "hard"}

CANONICAL_LAYOUTS = {
    "title", "bullets", "two-col", "quote", "stats", "chart", "closing",
}


@pytest.fixture(scope="module")
def rubric() -> dict:
    if _RUBRIC_PATH is None:
        pytest.fail(_MISSING_MOUNT_MSG)
    return json.loads(_RUBRIC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def prompts_doc() -> dict:
    if _PROMPTS_PATH is None:
        pytest.fail(_MISSING_MOUNT_MSG)
    return json.loads(_PROMPTS_PATH.read_text(encoding="utf-8"))


# ── rubric integrity ─────────────────────────────────────────────────────────


def test_rubric_file_exists() -> None:
    assert _RUBRIC_PATH is not None, _MISSING_MOUNT_MSG
    assert _RUBRIC_PATH.is_file(), f"rubric file missing at {_RUBRIC_PATH}"


def test_rubric_weights_sum_to_100(rubric: dict) -> None:
    weights = rubric["weights"]
    assert sum(weights.values()) == 100, weights


def test_rubric_weight_keys_match_categories(rubric: dict) -> None:
    assert set(rubric["weights"].keys()) == EXPECTED_CATEGORIES


def test_rubric_categories_block_matches_weights(rubric: dict) -> None:
    cat_ids = {c["id"] for c in rubric["categories"]}
    assert cat_ids == EXPECTED_CATEGORIES
    for cat in rubric["categories"]:
        assert cat["weight"] == rubric["weights"][cat["id"]], cat["id"]
        assert cat.get("description"), cat["id"]
        assert cat.get("audit_open_risk"), cat["id"]
        assert isinstance(cat.get("evidence_required"), list) and cat["evidence_required"], cat["id"]


def test_rubric_scale_is_1_to_10(rubric: dict) -> None:
    scale = rubric["scale"]
    assert scale["min"] == 1
    assert scale["max"] == 10
    assert 1 <= scale["passing"] <= scale["max"]
    assert 1 <= scale["target"] <= scale["max"]


def test_rubric_lists_required_competitors(rubric: dict) -> None:
    ids = {c["id"] for c in rubric["competitors"]}
    # Per Phase 6B prompt: must compare against these references.
    required = {"manus", "browser_use", "openmanus", "agenticseek", "gamma_tome"}
    assert required.issubset(ids), ids


# ── prompt corpus integrity ──────────────────────────────────────────────────


def test_prompts_file_exists() -> None:
    assert _PROMPTS_PATH is not None, _MISSING_MOUNT_MSG
    assert _PROMPTS_PATH.is_file(), f"prompts file missing at {_PROMPTS_PATH}"


def test_prompts_minimum_count(prompts_doc: dict) -> None:
    assert len(prompts_doc["prompts"]) >= 10


def test_prompt_ids_unique(prompts_doc: dict) -> None:
    ids = [p["id"] for p in prompts_doc["prompts"]]
    assert len(ids) == len(set(ids)), ids


def test_prompts_cover_required_kinds(prompts_doc: dict) -> None:
    kinds = {p["kind"] for p in prompts_doc["prompts"]}
    required = {
        "business",
        "investor",
        "education",
        "product_launch",
        "market_research",
        "chart_heavy",
        "evidence_heavy",
        "visual_storytelling",
    }
    missing = required - kinds
    assert not missing, f"prompt kinds missing: {missing}"


def test_every_prompt_has_required_metadata(prompts_doc: dict) -> None:
    required_top = {"id", "kind", "difficulty", "prompt", "expected_evidence", "expected_visual", "primary_categories"}
    for p in prompts_doc["prompts"]:
        missing = required_top - set(p.keys())
        assert not missing, f"prompt {p.get('id')!r} missing keys: {missing}"
        assert isinstance(p["prompt"], str) and len(p["prompt"]) >= 20, p["id"]


def test_every_prompt_declares_expected_evidence(prompts_doc: dict) -> None:
    required = {"needs_external_sources", "min_sources", "claim_level_required", "notes"}
    for p in prompts_doc["prompts"]:
        ev = p["expected_evidence"]
        assert required.issubset(ev.keys()), p["id"]
        assert isinstance(ev["needs_external_sources"], bool), p["id"]
        assert isinstance(ev["min_sources"], int) and ev["min_sources"] >= 0, p["id"]
        assert isinstance(ev["claim_level_required"], bool), p["id"]
        if ev["needs_external_sources"]:
            assert ev["min_sources"] >= 1, p["id"]


def test_every_prompt_declares_expected_visual(prompts_doc: dict) -> None:
    required = {"required_layouts", "min_slides", "max_slides", "chart_required"}
    for p in prompts_doc["prompts"]:
        vis = p["expected_visual"]
        assert required.issubset(vis.keys()), p["id"]
        assert isinstance(vis["required_layouts"], list) and vis["required_layouts"], p["id"]
        unknown = set(vis["required_layouts"]) - CANONICAL_LAYOUTS
        assert not unknown, f"prompt {p['id']} references non-canonical layouts: {unknown}"
        assert 1 <= vis["min_slides"] <= vis["max_slides"], p["id"]
        if vis["chart_required"]:
            assert "chart" in vis["required_layouts"] or any(
                lay in vis["required_layouts"] for lay in ("chart", "stats")
            ), p["id"]


def test_every_prompt_has_difficulty(prompts_doc: dict) -> None:
    for p in prompts_doc["prompts"]:
        assert p["difficulty"] in EXPECTED_DIFFICULTIES, p["id"]


def test_every_prompt_primary_categories_valid(prompts_doc: dict) -> None:
    for p in prompts_doc["prompts"]:
        cats = p["primary_categories"]
        assert isinstance(cats, list) and cats, p["id"]
        unknown = set(cats) - EXPECTED_CATEGORIES
        assert not unknown, f"prompt {p['id']} has unknown categories: {unknown}"


def test_corpus_covers_all_difficulty_levels(prompts_doc: dict) -> None:
    seen = {p["difficulty"] for p in prompts_doc["prompts"]}
    assert seen == EXPECTED_DIFFICULTIES, seen


def test_corpus_covers_all_rubric_categories(prompts_doc: dict) -> None:
    """Every rubric category must be exercised by at least one prompt."""
    seen: set[str] = set()
    for p in prompts_doc["prompts"]:
        seen.update(p["primary_categories"])
    # `stability_reliability` and `security_production_readiness` are platform
    # properties, not per-prompt evaluation targets, so they are exempt.
    prompt_evaluable = EXPECTED_CATEGORIES - {
        "stability_reliability",
        "security_production_readiness",
    }
    missing = prompt_evaluable - seen
    assert not missing, f"rubric categories not covered by any prompt: {missing}"


# ── audit cross-reference ────────────────────────────────────────────────────


def test_categories_map_to_audit_open_risks(rubric: dict) -> None:
    """Each rubric category must declare which audit open risk it tracks."""
    open_risks = {c["audit_open_risk"] for c in rubric["categories"]}
    # Must mention at least these tracked open risks from AUDIT_CURRENT_STATE.md.
    expected_risk_phrases = {
        "schema/layout correctness",
        "visual quality",
        "export parity",
        "evidence/citation accuracy",
        "browser/tool autonomy",
        "runtime reliability",
        "security/production readiness",
    }
    assert expected_risk_phrases.issubset(open_risks), open_risks
