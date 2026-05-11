"""Phase 1E — repair preview unit tests.

These tests exercise ``agent.deck_quality.build_repair_preview`` in
isolation: it must produce ``preview`` actions with safe before/after
values where the schema gap has an obvious local default, and must keep
``not_applied`` for fields that would require inventing semantic content
(bullets, columns, stats items, chart_data).

Run conftest-free::

    python -m pytest --noconftest -p no:cacheprovider \\
        tests/test_deck_repair_preview.py -v
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.deck_quality import (  # noqa: E402
    RepairAction,
    build_deck_quality_report,
    build_repair_preview,
)


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


# ── 1. Valid deck → empty preview ─────────────────────────────────────────


def test_build_repair_preview_empty_for_valid_deck():
    preview = build_repair_preview(VALID_DECK)
    assert preview == []


def test_build_repair_preview_empty_for_empty_deck():
    assert build_repair_preview([]) == []


# ── 2. Title slide missing subtitle + eyebrow → safe defaults ─────────────


def test_preview_fills_title_subtitle_and_eyebrow():
    deck = [
        {"id": "s0", "layout": "title", "title": "Hello"},
    ]
    preview = build_repair_preview(deck)
    by_path = {p.path: p for p in preview}

    assert "subtitle" in by_path
    assert by_path["subtitle"].action == "preview"
    assert by_path["subtitle"].after == ""
    assert by_path["subtitle"].layout == "title"

    assert "eyebrow" in by_path
    assert by_path["eyebrow"].action == "preview"
    assert by_path["eyebrow"].after == "Presentation"


# ── 3. Chart slide missing subtitle → preview after="" ────────────────────


def test_preview_fills_chart_subtitle():
    deck = [
        {
            "id": "s0",
            "layout": "chart",
            "title": "Capacity",
            "chart_type": "bar",
            "chart_data": {
                "labels": ["a", "b"],
                "values": [1.0, 2.0],
                "unit": "GW",
                "source": "IRENA",
            },
        }
    ]
    preview = build_repair_preview(deck)
    subtitle_actions = [p for p in preview if p.path == "subtitle"]
    assert len(subtitle_actions) == 1
    assert subtitle_actions[0].action == "preview"
    assert subtitle_actions[0].after == ""
    assert subtitle_actions[0].layout == "chart"


# ── 4. Closing slide missing subtitle + cta → safe defaults ───────────────


def test_preview_fills_closing_subtitle_and_cta():
    deck = [{"id": "s0", "layout": "closing", "title": "End"}]
    preview = build_repair_preview(deck)
    by_path = {p.path: p for p in preview}

    assert by_path["subtitle"].action == "preview"
    assert by_path["subtitle"].after == ""

    assert by_path["cta"].action == "preview"
    assert by_path["cta"].after == "Next steps"


# ── 5. Fields without a safe default stay not_applied ─────────────────────


def test_preview_does_not_invent_bullets():
    deck = [{"id": "s0", "layout": "bullets", "title": "Drivers"}]
    preview = build_repair_preview(deck)
    bullet_actions = [p for p in preview if p.path == "bullets"]
    assert bullet_actions, "bullets gap should still be surfaced"
    for action in bullet_actions:
        assert action.action == "not_applied"
        assert action.after is None


def test_preview_does_not_invent_chart_data():
    deck = [{"id": "s0", "layout": "chart", "title": "Capacity"}]
    preview = build_repair_preview(deck)
    chart_actions = [p for p in preview if p.path.startswith("chart_data")]
    assert chart_actions, "chart_data gap should still be surfaced"
    for action in chart_actions:
        assert action.action == "not_applied"
        assert action.after is None


# ── 6. Non-mutation guarantees ────────────────────────────────────────────


def test_preview_does_not_mutate_input_slides():
    deck = [{"id": "s0", "layout": "title", "title": "Hello"}]
    snapshot = copy.deepcopy(deck)
    build_repair_preview(deck)
    assert deck == snapshot


def test_preview_does_not_alter_passed_repair_actions():
    deck = [{"id": "s0", "layout": "title", "title": "Hello"}]
    report = build_deck_quality_report(deck)
    repairs_snapshot = [r.to_dict() for r in report.repair_actions]
    build_repair_preview(deck, repair_actions=report.repair_actions)
    assert [r.to_dict() for r in report.repair_actions] == repairs_snapshot


# ── 7. Pairing: preview length matches repair_actions length ──────────────


def test_preview_pairs_with_repair_actions_by_index():
    deck = [
        {"id": "s0", "layout": "title", "title": "Hello"},
        {"id": "s1", "layout": "closing", "title": "End"},
    ]
    report = build_deck_quality_report(deck)
    preview = build_repair_preview(deck, repair_actions=report.repair_actions)
    assert len(preview) == len(report.repair_actions)
    for src, prev in zip(report.repair_actions, preview):
        assert prev.slide_index == src.slide_index
        assert prev.layout == src.layout
        assert prev.path == src.path
        assert prev.code == src.code


# ── 8. DeckQualityReport now exposes repair_preview directly ──────────────


def test_deck_quality_report_includes_repair_preview_field():
    deck = [{"id": "s0", "layout": "title", "title": "Hello"}]
    report = build_deck_quality_report(deck)
    assert isinstance(report.repair_preview, list)
    assert all(isinstance(p, RepairAction) for p in report.repair_preview)

    d = report.to_dict()
    assert "repair_preview" in d
    assert isinstance(d["repair_preview"], list)
    assert d["summary"]["repairs_previewable"] == sum(
        1 for p in d["repair_preview"] if p["action"] == "preview"
    )


def test_repair_preview_action_field_only_preview_or_not_applied():
    deck = [
        {"id": "s0", "layout": "title", "title": "Hello"},
        {"id": "s1", "layout": "bullets", "title": "Drivers"},
    ]
    preview = build_repair_preview(deck)
    assert preview, "expected at least one preview entry"
    for action in preview:
        assert action.action in {"preview", "not_applied"}


# ── 9. Non-list payloads still produce a safe (empty/typed) preview ───────


def test_preview_handles_non_list_input():
    preview = build_repair_preview(None)
    # validate_deck collapses None to a single deck-level error; the
    # preview still returns a list (possibly with not_applied entries)
    # and never raises.
    assert isinstance(preview, list)
    for action in preview:
        assert action.action in {"preview", "not_applied"}
