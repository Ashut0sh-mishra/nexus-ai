"""Phase 1B — typed slide-contract validation tests.

These tests are intentionally self-contained: they import only
``agent.slide_schema`` (which transitively imports ``agent.layouts_registry``
— a JSON-file loader with no DB / app dependencies). They run cleanly
under::

    python -m pytest --noconftest -p no:cacheprovider \\
        tests/test_layout_coverage.py tests/test_slide_schema.py -v

and do NOT rely on ``backend/tests/conftest.py`` (which is currently
broken by a SQLite NullPool / pool_size mismatch in ``database.connection``).
"""

from __future__ import annotations

import pytest

from agent.layouts_registry import CANONICAL_LAYOUTS
from agent.slide_schema import (
    ValidationError,
    ValidationResult,
    validate_deck,
    validate_slide,
)

# ── Valid example slides for each canonical layout ─────────────────────────

VALID_EXAMPLES: dict[str, dict] = {
    "title": {
        "id": "slide-000",
        "layout": "title",
        "title": "The Future of Renewable Energy",
        "subtitle": "A 2026 Outlook",
        "eyebrow": "Presentation",
    },
    "bullets": {
        "id": "slide-001",
        "layout": "bullets",
        "title": "Key Drivers",
        "bullets": [
            "Falling solar costs",
            "Battery breakthroughs",
            "Policy tailwinds",
        ],
    },
    "two-col": {
        "id": "slide-002",
        "layout": "two-col",
        "title": "Pros vs Cons",
        "columns": [
            {"heading": "Pros", "body": "Lower marginal cost over time."},
            {"heading": "Cons", "body": "Upfront capital intensity."},
        ],
    },
    "quote": {
        "id": "slide-003",
        "layout": "quote",
        "title": "Industry Voice",
        "quote": "The cheapest electricity in history is now solar.",
        "attribution": "IEA, 2020",
    },
    "stats": {
        "id": "slide-004",
        "layout": "stats",
        "title": "By the Numbers",
        "stats": [
            {"value": "30%", "label": "Global share by 2030"},
            {"value": "$1.7T", "label": "Annual investment"},
            {"value": "12M", "label": "Jobs created"},
        ],
    },
    "chart": {
        "id": "slide-005",
        "layout": "chart",
        "title": "Capacity Growth",
        "chart_type": "bar",
        "chart_data": {
            "labels": ["2022", "2023", "2024", "2025"],
            "values": [100.0, 145.0, 210.0, 295.0],
            "unit": "GW",
            "source": "IRENA",
        },
        "subtitle": "Global installed solar capacity",
    },
    "closing": {
        "id": "slide-006",
        "layout": "closing",
        "title": "Thank You",
        "subtitle": "Questions welcome",
        "cta": "Let's discuss",
    },
    # Phase 6AA — single dominant metric.
    "bigstat": {
        "id": "slide-007",
        "layout": "bigstat",
        "title": "Headline Number",
        "value": "93%",
        "label": "Adoption rate",
        "subtitle": "Across the surveyed cohort",
    },
    # Phase 6AA — typography-only narrative pause.
    "section_divider": {
        "id": "slide-008",
        "layout": "section_divider",
        "title": "Part Two",
        "eyebrow": "Continued",
        "subtitle": "Implications for the next decade",
    },
    # Phase 6AC — chronology of dated events.
    "timeline": {
        "id": "slide-009",
        "layout": "timeline",
        "title": "Major Milestones",
        "subtitle": "",
        "events": [
            {"date": "2018", "label": "Initial breakthrough"},
            {"date": "2021", "label": "Commercial pilot launched"},
            {"date": "2024", "label": "Mass-market rollout"},
        ],
    },
    # Phase 6AC — explicit left/right contrast.
    "comparison": {
        "id": "slide-010",
        "layout": "comparison",
        "title": "Before vs After",
        "subtitle": "",
        "left": {"heading": "Legacy", "body": "Manual workflows; 3-day cycle time."},
        "right": {"heading": "Modern", "body": "Automated pipeline; 4-hour cycle time."},
    },
}


# ── 1. Every canonical layout has a passing valid example ──────────────────


def test_all_canonical_layouts_have_examples():
    """Guard: if a canonical layout is added without a test example, fail."""
    assert set(VALID_EXAMPLES.keys()) == set(CANONICAL_LAYOUTS), (
        f"VALID_EXAMPLES keys {sorted(VALID_EXAMPLES)} must match "
        f"CANONICAL_LAYOUTS {sorted(CANONICAL_LAYOUTS)}"
    )


@pytest.mark.parametrize("layout", sorted(CANONICAL_LAYOUTS))
def test_valid_example_passes(layout: str):
    result = validate_slide(VALID_EXAMPLES[layout])
    assert isinstance(result, ValidationResult)
    assert result.ok, f"{layout} valid example failed: {[e.to_dict() for e in result.errors]}"
    assert result.layout == layout
    assert result.errors == []
    assert result.normalized is not None


# ── 2. Structured result shape ─────────────────────────────────────────────


def test_to_dict_shape():
    result = validate_slide({"layout": "bullets"})
    d = result.to_dict()
    assert set(d.keys()) == {"ok", "layout", "errors", "normalized"}
    assert d["ok"] is False
    for err in d["errors"]:
        assert set(err.keys()) == {"path", "code", "message"}


# ── 3. Missing / empty / wrong-type required fields ────────────────────────


def test_missing_layout_fails():
    result = validate_slide({"title": "X"})
    assert not result.ok
    assert any(e.code == "missing" and e.path == "layout" for e in result.errors)


def test_layout_wrong_type_fails():
    result = validate_slide({"layout": 123, "title": "X"})
    assert not result.ok
    assert any(e.code == "wrong_type" and e.path == "layout" for e in result.errors)


def test_non_dict_payload_fails():
    result = validate_slide(["not", "a", "slide"])
    assert not result.ok
    assert any(e.code == "invalid_payload" for e in result.errors)


def test_missing_required_title_fails():
    payload = dict(VALID_EXAMPLES["bullets"])
    del payload["title"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "missing" and e.path == "title" for e in result.errors)


def test_empty_title_fails():
    payload = dict(VALID_EXAMPLES["bullets"])
    payload["title"] = "   "
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "empty" and e.path == "title" for e in result.errors)


def test_wrong_type_bullets_fails():
    payload = dict(VALID_EXAMPLES["bullets"])
    payload["bullets"] = "not a list"
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "wrong_type" and e.path == "bullets" for e in result.errors)


def test_too_many_bullets_fails():
    payload = dict(VALID_EXAMPLES["bullets"])
    payload["bullets"] = ["a", "b", "c", "d", "e"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "too_many" and e.path == "bullets" for e in result.errors)


def test_bullet_item_wrong_type_fails():
    payload = dict(VALID_EXAMPLES["bullets"])
    payload["bullets"] = ["ok", 42, "ok2"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "wrong_type" and e.path == "bullets[1]" for e in result.errors)


# ── 4. two-col / columns ───────────────────────────────────────────────────


def test_columns_must_be_list_of_dicts():
    payload = dict(VALID_EXAMPLES["two-col"])
    payload["columns"] = ["not", "dicts"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "wrong_type" and e.path.startswith("columns[") for e in result.errors)


def test_column_missing_heading_fails():
    payload = {
        "layout": "two-col",
        "title": "X",
        "columns": [{"body": "no heading here"}],
    }
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "missing" and e.path == "columns[0].heading" for e in result.errors
    )


def test_too_many_columns_fails():
    payload = dict(VALID_EXAMPLES["two-col"])
    payload["columns"] = payload["columns"] + [{"heading": "extra", "body": "extra"}]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "too_many" and e.path == "columns" for e in result.errors)


# ── 5. stats item shape ────────────────────────────────────────────────────


def test_stats_item_missing_label_fails():
    payload = {
        "layout": "stats",
        "title": "X",
        "stats": [{"value": "10%"}],
    }
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "missing" and e.path == "stats[0].label" for e in result.errors
    )


def test_stats_item_wrong_type_fails():
    payload = {
        "layout": "stats",
        "title": "X",
        "stats": ["not a dict"],
    }
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "wrong_type" and e.path == "stats[0]" for e in result.errors)


# ── 6. chart_data shape ────────────────────────────────────────────────────


def test_chart_missing_chart_data_fails():
    payload = dict(VALID_EXAMPLES["chart"])
    del payload["chart_data"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "missing" and e.path == "chart_data" for e in result.errors)


def test_chart_invalid_chart_type_fails():
    payload = dict(VALID_EXAMPLES["chart"])
    payload["chart_type"] = "pie"  # not in {bar, line, doughnut}
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "invalid_value" and e.path == "chart_type" for e in result.errors
    )


def test_chart_data_length_mismatch_fails():
    payload = dict(VALID_EXAMPLES["chart"])
    payload["chart_data"] = {
        "labels": ["a", "b", "c"],
        "values": [1.0, 2.0],
        "unit": "",
        "source": "",
    }
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "length_mismatch" and e.path == "chart_data" for e in result.errors
    )


def test_chart_data_non_numeric_value_fails():
    payload = dict(VALID_EXAMPLES["chart"])
    payload["chart_data"] = {
        "labels": ["a", "b"],
        "values": [1.0, "two"],
        "unit": "",
        "source": "",
    }
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "wrong_type" and e.path == "chart_data.values[1]"
        for e in result.errors
    )


def test_chart_data_bool_rejected_as_value():
    """bool is a subclass of int in Python; the schema must reject it."""
    payload = dict(VALID_EXAMPLES["chart"])
    payload["chart_data"] = {
        "labels": ["a", "b"],
        "values": [1.0, True],
        "unit": "",
        "source": "",
    }
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "wrong_type" and e.path == "chart_data.values[1]"
        for e in result.errors
    )


def test_chart_data_labels_must_be_list():
    payload = dict(VALID_EXAMPLES["chart"])
    payload["chart_data"] = {
        "labels": "not a list",
        "values": [1.0],
        "unit": "",
        "source": "",
    }
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "wrong_type" and e.path == "chart_data.labels"
        for e in result.errors
    )


# ── 7. quote layout ────────────────────────────────────────────────────────


def test_quote_missing_quote_text_fails():
    payload = {"layout": "quote", "title": "X"}
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "missing" and e.path == "quote" for e in result.errors)


# ── 8. Unknown layouts MUST NOT silently pass ──────────────────────────────


def test_unknown_layout_fails():
    result = validate_slide({"layout": "spaceship", "title": "X"})
    assert not result.ok
    assert any(e.code == "unknown_layout" and e.path == "layout" for e in result.errors)
    # Even though the runtime fallback resolves to FALLBACK_LAYOUT for safety,
    # the validator must NOT silently coerce — layout stays None on failure.
    assert result.layout is None


def test_unknown_layout_strict_mode_fails():
    """resolve_aliases=False must also reject unknown names."""
    result = validate_slide({"layout": "wizard", "title": "X"}, resolve_aliases=False)
    assert not result.ok
    assert any(e.code == "unknown_layout" for e in result.errors)


# ── 9. validate_deck convenience wrapper ───────────────────────────────────


def test_validate_deck_returns_one_result_per_slide():
    deck = [VALID_EXAMPLES["title"], VALID_EXAMPLES["bullets"], {"layout": "nope"}]
    results = validate_deck(deck)
    assert len(results) == 3
    assert results[0].ok
    assert results[1].ok
    assert not results[2].ok


def test_validate_deck_non_list_fails():
    results = validate_deck("not a list")
    assert len(results) == 1
    assert not results[0].ok
    assert results[0].errors[0].code == "invalid_payload"


# ── 10. ValidationError is structurally stable ─────────────────────────────


def test_validation_error_to_dict():
    err = ValidationError(path="x.y", code="missing", message="m")
    assert err.to_dict() == {"path": "x.y", "code": "missing", "message": "m"}


# ── 11. Phase 1B.1 — Tightened required fields ─────────────────────────────
#
# These tests pin the normalized-contract fields that the validator must
# now require. The keys must be present even when their values are empty
# strings (mirroring what ``NexusAgentLoop._normalize_slides`` emits).


def test_title_missing_subtitle_fails():
    payload = dict(VALID_EXAMPLES["title"])
    del payload["subtitle"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "missing" and e.path == "subtitle" for e in result.errors)


def test_title_missing_eyebrow_fails():
    payload = dict(VALID_EXAMPLES["title"])
    del payload["eyebrow"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "missing" and e.path == "eyebrow" for e in result.errors)


def test_title_empty_subtitle_allowed():
    """Phase 1B.1: empty subtitle is allowed (normalizer can emit "")."""
    payload = dict(VALID_EXAMPLES["title"])
    payload["subtitle"] = ""
    result = validate_slide(payload)
    assert result.ok, [e.to_dict() for e in result.errors]


def test_quote_missing_attribution_fails():
    payload = dict(VALID_EXAMPLES["quote"])
    del payload["attribution"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "missing" and e.path == "attribution" for e in result.errors)


def test_chart_missing_subtitle_fails():
    payload = dict(VALID_EXAMPLES["chart"])
    del payload["subtitle"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "missing" and e.path == "subtitle" for e in result.errors)


def test_closing_missing_subtitle_fails():
    payload = dict(VALID_EXAMPLES["closing"])
    del payload["subtitle"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "missing" and e.path == "subtitle" for e in result.errors)


def test_closing_missing_cta_fails():
    payload = dict(VALID_EXAMPLES["closing"])
    del payload["cta"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(e.code == "missing" and e.path == "cta" for e in result.errors)


# ── 12. Phase 1B.1 — Strict-mode layout key handling ───────────────────────


def test_strict_mode_rejects_titlecase():
    """resolve_aliases=False must require an EXACT canonical name.

    ``"Title"`` differs from canonical ``"title"`` only in case, but
    strict mode does not case-fold or trim. It must fail.
    """
    payload = dict(VALID_EXAMPLES["title"])
    payload["layout"] = "Title"
    result = validate_slide(payload, resolve_aliases=False)
    assert not result.ok
    assert any(
        e.code == "unknown_layout" and e.path == "layout" for e in result.errors
    )
    assert result.layout is None


def test_strict_mode_rejects_padded_name():
    payload = dict(VALID_EXAMPLES["bullets"])
    payload["layout"] = " bullets "
    result = validate_slide(payload, resolve_aliases=False)
    assert not result.ok
    assert any(e.code == "unknown_layout" for e in result.errors)


def test_strict_mode_accepts_exact_canonical():
    """Sanity check: exact canonical names still pass in strict mode."""
    for layout, payload in VALID_EXAMPLES.items():
        result = validate_slide(payload, resolve_aliases=False)
        assert result.ok, (
            f"strict-mode rejected canonical {layout!r}: "
            f"{[e.to_dict() for e in result.errors]}"
        )
        assert result.layout == layout


# ── 13. Phase 1B.1 — ``normalized`` is a shallow copy with canonical layout


def test_normalized_is_shallow_copy_with_canonical_layout():
    """``normalized`` must be a NEW dict, not the input, and carry the
    resolved canonical layout name. Mutating it must not affect the
    caller's input."""
    payload = dict(VALID_EXAMPLES["bullets"])
    result = validate_slide(payload)
    assert result.ok
    assert result.normalized is not None
    assert result.normalized is not payload, (
        "normalized must be a copy, not the input dict"
    )
    assert result.normalized["layout"] == "bullets"
    # Mutating normalized must not leak back into the input.
    result.normalized["title"] = "MUTATED"
    assert payload["title"] != "MUTATED"


def test_normalized_pins_canonical_layout_for_uppercase_input():
    """When alias-resolution is on, an upper-case layout still resolves
    to its canonical form and ``normalized.layout`` reflects that."""
    payload = dict(VALID_EXAMPLES["bullets"])
    payload["layout"] = "BULLETS"
    result = validate_slide(payload, resolve_aliases=True)
    assert result.ok, [e.to_dict() for e in result.errors]
    assert result.layout == "bullets"
    assert result.normalized is not None
    assert result.normalized["layout"] == "bullets"


def test_normalized_is_none_on_failure():
    payload = dict(VALID_EXAMPLES["title"])
    del payload["subtitle"]
    result = validate_slide(payload)
    assert not result.ok
    assert result.normalized is None


# -- 14. Phase 1B.1 Audit Correction � chart_data.unit / chart_data.source --


def test_chart_missing_chart_data_unit_fails():
    payload = dict(VALID_EXAMPLES["chart"])
    payload["chart_data"] = dict(payload["chart_data"])
    del payload["chart_data"]["unit"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "missing" and e.path == "chart_data.unit" for e in result.errors
    ), [e.to_dict() for e in result.errors]


def test_chart_missing_chart_data_source_fails():
    payload = dict(VALID_EXAMPLES["chart"])
    payload["chart_data"] = dict(payload["chart_data"])
    del payload["chart_data"]["source"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "missing" and e.path == "chart_data.source" for e in result.errors
    ), [e.to_dict() for e in result.errors]


def test_chart_empty_unit_and_source_allowed():
    """Mirrors what NexusAgentLoop._normalize_slides emits when source/unit
    are absent: empty strings are accepted as valid."""
    payload = dict(VALID_EXAMPLES["chart"])
    payload["chart_data"] = dict(payload["chart_data"])
    payload["chart_data"]["unit"] = ""
    payload["chart_data"]["source"] = ""
    result = validate_slide(payload)
    assert result.ok, [e.to_dict() for e in result.errors]


def test_chart_non_string_unit_fails():
    payload = dict(VALID_EXAMPLES["chart"])
    payload["chart_data"] = dict(payload["chart_data"])
    payload["chart_data"]["unit"] = 123
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "wrong_type" and e.path == "chart_data.unit" for e in result.errors
    )


def test_chart_non_string_source_fails():
    payload = dict(VALID_EXAMPLES["chart"])
    payload["chart_data"] = dict(payload["chart_data"])
    payload["chart_data"]["source"] = ["IRENA"]
    result = validate_slide(payload)
    assert not result.ok
    assert any(
        e.code == "wrong_type" and e.path == "chart_data.source" for e in result.errors
    )


# -- 15. Phase 1B.1 Audit Correction � _normalize_slides telemetry ----------
#
# Direct test of the validate_deck telemetry wired into
# NexusAgentLoop._normalize_slides. We import NexusAgentLoop the same way
# tests/test_layout_coverage.py does (no conftest required).
#
# P1-2 update: the stats?chart safety-net now sets a slide-level
# ``subtitle`` (carried forward from source, defaulting to ""), so the
# previously-emitted ``loop.slide_validation_failed`` warning with
# path=subtitle code=missing must NOT appear for this self-inflicted case.


def test_normalize_slides_logs_validation_failure(caplog):
    import logging
    import sys
    from pathlib import Path as _Path

    _BACKEND_ROOT = _Path(__file__).resolve().parent.parent
    if str(_BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(_BACKEND_ROOT))
    from agent.loop import NexusAgentLoop  # noqa: E402

    caplog.set_level(logging.WARNING, logger="nexus.agent.loop")

    slides = [
        {"layout": "title", "title": "T", "subtitle": "S", "eyebrow": "E"},
        {
            "layout": "stats",
            "title": "Numbers",
            "stats": [
                {"value": "10", "label": "alpha"},
                {"value": "20", "label": "beta"},
            ],
        },
        {"layout": "closing", "title": "Bye", "subtitle": "", "cta": "Thanks"},
    ]
    out = NexusAgentLoop._normalize_slides(slides, len(slides), "topic")

    # Safety-net must have promoted the stats slide to a chart…
    assert any(s["layout"] == "chart" for s in out), [s["layout"] for s in out]
    # …and that chart slide now carries a (possibly empty) subtitle.
    chart_slide = next(s for s in out if s["layout"] == "chart")
    assert "subtitle" in chart_slide
    assert isinstance(chart_slide["subtitle"], str)

    msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert not any(
        "loop.slide_validation_failed" in m
        and "layout=chart" in m
        and "path=subtitle" in m
        and "code=missing" in m
        for m in msgs
    ), msgs