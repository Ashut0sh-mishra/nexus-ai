"""Phase 6C — canonical export fixture slides.

Deterministic, image-free fixture slides covering all 7 canonical layouts.
Reused by:

* `backend/tests/test_export_parity.py` — PPTX text-extraction parity tests.
* Future phases that want screenshot or visual-diff comparisons.

No `image_url` is set on any slide so `ExportService._fetch_image` short-circuits
and no network call is made during tests.

Each slide contains stable, unique markers so text-extraction assertions can be
written without ambiguity.
"""
from __future__ import annotations

from typing import Any


def canonical_fixture_slides() -> list[dict[str, Any]]:
    return [
        {
            "layout": "title",
            "eyebrow": "Phase6C",
            "title": "Renderer Export Parity",
            "subtitle": "PARITYSUB-01 deterministic title slide",
        },
        {
            "layout": "bullets",
            "title": "PARITY-BULLETS-TITLE",
            "bullets": [
                "BULLET-ITEM-A first key point",
                "BULLET-ITEM-B second key point",
                "BULLET-ITEM-C third key point",
            ],
        },
        {
            "layout": "two-col",
            "title": "PARITY-TWOCOL-TITLE",
            "columns": [
                {"heading": "TWOCOL-LEFT-HEAD", "body": "TWOCOL-LEFT-BODY left column body."},
                {"heading": "TWOCOL-RIGHT-HEAD", "body": "TWOCOL-RIGHT-BODY right column body."},
            ],
        },
        {
            "layout": "quote",
            "title": "PARITY-QUOTE-TITLE",
            "quote": "PARITYQUOTE the medium is the message.",
            "attribution": "PARITYATTRIB McLuhan",
        },
        {
            "layout": "stats",
            "title": "PARITY-STATS-TITLE",
            "stats": [
                {"value": "STATVAL-42", "label": "STATLBL-Alpha"},
                {"value": "STATVAL-77", "label": "STATLBL-Bravo"},
                {"value": "STATVAL-93", "label": "STATLBL-Charlie"},
            ],
        },
        {
            "layout": "chart",
            "title": "PARITY-CHART-TITLE",
            "subtitle": "PARITY-CHART-SUB",
            "chart_type": "bar",
            "chart_data": {
                "labels": ["CHARTLBL-Q1", "CHARTLBL-Q2", "CHARTLBL-Q3"],
                "values": [10, 20, 30],
                "unit": "CHARTUNIT-USD",
                "source": "CHARTSRC-FY24",
            },
        },
        {
            "layout": "closing",
            "title": "PARITY-CLOSING-TITLE",
            "subtitle": "PARITY-CLOSING-SUB",
            "cta": "PARITY-CLOSING-CTA",
        },
    ]


CANONICAL_LAYOUTS = (
    "title", "bullets", "two-col", "quote", "stats", "chart", "closing",
)
