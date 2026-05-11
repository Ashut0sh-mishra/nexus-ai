"""Phase 1G P0-2: cheapest possible export-parity guarantee.

The Phase 1D ``attach_quality_report`` helper computes ``deck_quality`` on
the deck-read API path by reading ``deck.slide_data``. Export routes must
hand the *same* slide list to ``ExportService`` so that the green
``deck_quality`` badge a user sees on the deck-read page reflects the
exact slide payload that gets rendered to PPTX / PDF.

This test does not exercise the full ExportService machinery (renderer,
network, file IO). It is a strict source-level parity check: both the
slides route and the export routes read ``deck.slide_data`` via the same
``deck.slide_data or []`` expression and pass it directly to their
downstream consumer. That contract is what the Phase 1D guarantee rests
on; if a future refactor reshapes the slide payload before passing it to
ExportService, this test will fail and force the change to be made
explicit (and re-validated against ``deck_quality``).

Conftest-free, dependency-light. Imports nothing from the database, the
worker, or FastAPI test clients.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _slide_kwarg_expr(call: ast.Call) -> str | None:
    """Return the source expression for the ``slides=`` kwarg, or None."""
    for kw in call.keywords:
        if kw.arg == "slides":
            return ast.unparse(kw.value)
    return None


def _all_slide_kwarg_exprs(module_path: Path) -> list[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    exprs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            expr = _slide_kwarg_expr(node)
            if expr is not None:
                exprs.append(expr)
    return exprs


def test_export_routes_pass_deck_slide_data_unchanged():
    """Every ``slides=`` call site in export.py must pass ``deck.slide_data``
    (with the same ``or []`` safety) - never a transformed copy."""
    export_path = _BACKEND_ROOT / "api" / "routes" / "export.py"
    exprs = _all_slide_kwarg_exprs(export_path)
    assert exprs, "expected at least one slides= kwarg in export.py"
    expected = "deck.slide_data or []"
    for expr in exprs:
        assert expr == expected, (
            f"export.py passes slides={expr!r}; expected {expected!r}. "
            "If this changed intentionally, update the deck_quality "
            "contract in attach_quality_report or this parity test."
        )


def test_slides_route_reads_deck_slide_data_with_same_safety():
    """The slides GET route must read ``deck.slide_data`` with the same
    ``or []`` safety so the ``deck_quality`` report reflects the exact
    list export will receive."""
    slides_path = _BACKEND_ROOT / "api" / "routes" / "slides.py"
    src = slides_path.read_text(encoding="utf-8")
    assert "deck.slide_data or []" in src, (
        "slides.py must read deck.slide_data with `or []` fallback; "
        "see test_export_routes_pass_deck_slide_data_unchanged for why."
    )


def test_export_module_imports_export_service():
    """Sanity check: parity test points at the right module."""
    export_path = _BACKEND_ROOT / "api" / "routes" / "export.py"
    src = export_path.read_text(encoding="utf-8")
    assert "from services.export_service import ExportService" in src
