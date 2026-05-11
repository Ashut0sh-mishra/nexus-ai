"""Phase 1D — API payload integration tests for DeckQualityReport.

These tests target the small, dependency-light helper
``agent.deck_quality.attach_quality_report`` that the API routes
``GET /api/slides/{task_id}`` and ``GET /api/share/{token}`` use to attach
the report to their JSON responses without a DB migration.

They are intentionally conftest-free and import only ``agent.*`` modules
so they run cleanly under::

    python -m pytest --noconftest -p no:cacheprovider \\
        tests/test_api_deck_quality_payload.py -v
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

# Ensure ``backend/`` is on sys.path so the ``agent`` package resolves.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.deck_quality import attach_quality_report  # noqa: E402


VALID_DECK: list[dict] = [
    {
        "id": "slide-000",
        "layout": "title",
        "title": "Topic",
        "subtitle": "Sub",
        "eyebrow": "Presentation",
    },
    {
        "id": "slide-001",
        "layout": "bullets",
        "title": "Drivers",
        "bullets": ["a", "b", "c"],
    },
    {
        "id": "slide-002",
        "layout": "closing",
        "title": "Bye",
        "subtitle": "",
        "cta": "Q&A",
    },
]


def _payload_for(slides: list[dict]) -> dict:
    return {
        "task_id": "task-abc",
        "topic": "Renewables",
        "theme": "Editorial",
        "slide_count": len(slides),
        "slides": slides,
    }


# ── 1. Helper attaches deck_quality and preserves existing keys ────────────


def test_attach_quality_report_adds_deck_quality_key():
    payload = _payload_for(VALID_DECK)
    out = attach_quality_report(payload, VALID_DECK)

    # Existing keys unchanged.
    for k in ("task_id", "topic", "theme", "slide_count", "slides"):
        assert out[k] == payload[k]

    # New key is present and a dict.
    assert "deck_quality" in out
    quality = out["deck_quality"]
    assert isinstance(quality, dict)
    assert set(quality.keys()) == {
        "ok",
        "slide_count",
        "valid_count",
        "invalid_count",
        "errors",
        "repair_actions",
        "repair_preview",
        "summary",
        "source_warnings",
    }


def test_attach_quality_report_does_not_mutate_inputs():
    payload = _payload_for(VALID_DECK)
    payload_snapshot = copy.deepcopy(payload)
    slides_snapshot = copy.deepcopy(VALID_DECK)

    out = attach_quality_report(payload, VALID_DECK)

    assert payload == payload_snapshot, "payload must not be mutated"
    assert VALID_DECK == slides_snapshot, "slides must not be mutated"
    assert out is not payload, "must return a new dict"


def test_attach_quality_report_is_json_serializable():
    payload = _payload_for(VALID_DECK)
    out = attach_quality_report(payload, VALID_DECK)
    # Must round-trip through json.dumps without a custom encoder.
    encoded = json.dumps(out, default=str)
    decoded = json.loads(encoded)
    assert decoded["deck_quality"]["ok"] is True
    assert decoded["deck_quality"]["slide_count"] == len(VALID_DECK)


# ── 2. Invalid deck → quality flags surface in response ────────────────────


def test_attach_quality_report_flags_invalid_chart():
    bad = copy.deepcopy(VALID_DECK)
    # Insert a chart slide missing the required slide-level subtitle.
    bad.insert(
        2,
        {
            "id": "slide-002b",
            "layout": "chart",
            "title": "Capacity",
            "chart_type": "bar",
            "chart_data": {
                "labels": ["a", "b"],
                "values": [1.0, 2.0],
                "unit": "GW",
                "source": "IRENA",
            },
            # subtitle intentionally missing
        },
    )
    payload = _payload_for(bad)
    out = attach_quality_report(payload, bad)
    quality = out["deck_quality"]

    assert quality["ok"] is False
    assert quality["invalid_count"] >= 1
    assert any(
        e["path"] == "subtitle" and e["code"] == "missing" and e["layout"] == "chart"
        for e in quality["errors"]
    ), quality["errors"]
    assert quality["summary"]["repairs_needed"] >= 1


# ── 3. Empty / missing slides → safe response ──────────────────────────────


def test_attach_quality_report_handles_empty_slides():
    payload = _payload_for([])
    out = attach_quality_report(payload, [])
    quality = out["deck_quality"]
    assert quality["ok"] is True
    assert quality["slide_count"] == 0
    assert quality["valid_count"] == 0
    assert quality["invalid_count"] == 0
    assert quality["errors"] == []
    assert quality["repair_actions"] == []


def test_attach_quality_report_handles_non_list_slides():
    payload = {"slides": None}
    out = attach_quality_report(payload, None)
    quality = out["deck_quality"]
    assert quality["ok"] is False
    assert quality["summary"].get("deck_payload") == "invalid"
