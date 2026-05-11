"""Phase 1C — Deck quality report and repair-action telemetry.

This module wraps :func:`agent.slide_schema.validate_deck` to produce a
*structured*, serializable view of how well a normalized deck satisfies
the slide contract. It is intentionally **observability-only**:

* It does NOT mutate the input slides.
* It does NOT auto-repair anything.
* Each schema failure is surfaced as a :class:`RepairAction` with
  ``action="not_applied"`` so a future repair pipeline can act on the
  same data shape.

The module is dependency-light by design: it imports only
``agent.slide_schema`` (which itself only imports the JSON-backed
``agent.layouts_registry``). It must not import database, services, or
FastAPI app code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.slide_schema import ValidationError, validate_deck
from agent.source_grounding import build_deck_source_report


# ── Public result types ────────────────────────────────────────────────────


@dataclass(frozen=True)
class RepairAction:
    """A single, structured repair recommendation for an invalid slide field.

    Phase 1C is *report-only*: ``action`` will always be ``"not_applied"``.
    A future repair pipeline can populate ``before`` / ``after`` and flip
    ``action`` to ``"applied"`` without changing the public shape.
    """

    slide_index: int
    layout: str | None
    path: str
    code: str
    message: str
    action: str = "not_applied"
    before: Any = None
    after: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_index": self.slide_index,
            "layout": self.layout,
            "path": self.path,
            "code": self.code,
            "message": self.message,
            "action": self.action,
            "before": self.before,
            "after": self.after,
        }


@dataclass
class DeckQualityReport:
    """Structured, serializable summary of deck-level validation outcomes."""

    ok: bool
    slide_count: int
    valid_count: int
    invalid_count: int
    errors: list[dict[str, Any]] = field(default_factory=list)
    repair_actions: list[RepairAction] = field(default_factory=list)
    repair_preview: list[RepairAction] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    source_warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "slide_count": self.slide_count,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "errors": list(self.errors),
            "repair_actions": [r.to_dict() for r in self.repair_actions],
            "repair_preview": [r.to_dict() for r in self.repair_preview],
            "summary": dict(self.summary),
            "source_warnings": list(self.source_warnings),
        }


# ── Public API ─────────────────────────────────────────────────────────────


def build_deck_quality_report(slides: Any) -> DeckQualityReport:
    """Build a non-destructive deck quality report.

    The function never mutates ``slides`` and never repairs anything. It
    delegates schema checking to
    :func:`agent.slide_schema.validate_deck` and aggregates the per-slide
    outcomes into structured ``errors`` and ``repair_actions``.

    Parameters
    ----------
    slides:
        Whatever ``validate_deck`` accepts — typically a ``list[dict]``.
        Non-list inputs are surfaced as a single deck-level error.

    Returns
    -------
    DeckQualityReport
        Always returns a report; never raises for content errors.
    """

    results = validate_deck(slides)

    # ``validate_deck`` collapses a non-list input into one synthetic
    # invalid_payload result. Treat that case as a deck-level error
    # rather than pretending we have one slide.
    if not isinstance(slides, list):
        single = results[0] if results else None
        deck_errors: list[dict[str, Any]] = []
        repairs: list[RepairAction] = []
        if single is not None:
            for err in single.errors:
                deck_errors.append(_error_record(-1, None, err))
                repairs.append(_repair_from_error(-1, None, err))
        preview = build_repair_preview(slides, repair_actions=repairs)
        return DeckQualityReport(
            ok=False,
            slide_count=0,
            valid_count=0,
            invalid_count=0,
            errors=deck_errors,
            repair_actions=repairs,
            repair_preview=preview,
            summary={
                "deck_payload": "invalid",
                "repairs_needed": len(repairs),
                "repairs_previewable": sum(
                    1 for p in preview if p.action == "preview"
                ),
                "source_warnings": 0,
            },
            source_warnings=[],
        )

    slide_count = len(results)
    valid_count = sum(1 for r in results if r.ok)
    invalid_count = slide_count - valid_count

    errors: list[dict[str, Any]] = []
    repairs: list[RepairAction] = []
    layouts_seen: dict[str, int] = {}

    for idx, vr in enumerate(results):
        if vr.layout is not None:
            layouts_seen[vr.layout] = layouts_seen.get(vr.layout, 0) + 1
        if vr.ok:
            continue
        for err in vr.errors:
            errors.append(_error_record(idx, vr.layout, err))
            repairs.append(_repair_from_error(idx, vr.layout, err))

    preview = build_repair_preview(slides, repair_actions=repairs)
    source_report = build_deck_source_report(slides)
    summary = {
        "layouts": layouts_seen,
        "repairs_needed": len(repairs),
        "repairs_previewable": sum(1 for p in preview if p.action == "preview"),
        "source_warnings": len(source_report["warnings"]),
        "slides_with_sources": source_report["slides_with_sources"],
    }

    return DeckQualityReport(
        ok=invalid_count == 0,
        slide_count=slide_count,
        valid_count=valid_count,
        invalid_count=invalid_count,
        errors=errors,
        repair_actions=repairs,
        repair_preview=preview,
        summary=summary,
        source_warnings=list(source_report["warnings"]),
    )


# ── Internal helpers ───────────────────────────────────────────────────────


def _error_record(
    slide_index: int, layout: str | None, err: ValidationError
) -> dict[str, Any]:
    return {
        "slide_index": slide_index,
        "layout": layout,
        "path": err.path,
        "code": err.code,
        "message": err.message,
    }


def _repair_from_error(
    slide_index: int, layout: str | None, err: ValidationError
) -> RepairAction:
    return RepairAction(
        slide_index=slide_index,
        layout=layout,
        path=err.path,
        code=err.code,
        message=err.message,
        action="not_applied",
    )


# ── Phase 1E: repair preview ───────────────────────────────────────────────

# Map of (layout, dotted-path, error-code) -> safe default value.
#
# Only entries with an *obvious, local* default belong here. Anything that
# requires guessing semantic content (bullets, columns, stats items, chart
# data) is intentionally absent so the preview never invents content.
_PREVIEW_DEFAULTS: dict[tuple[str, str, str], Any] = {
    ("title", "subtitle", "missing"): "",
    ("title", "eyebrow", "missing"): "Presentation",
    ("chart", "subtitle", "missing"): "",
    ("closing", "subtitle", "missing"): "",
    ("closing", "cta", "missing"): "Next steps",
}


def build_repair_preview(
    slides: Any,
    *,
    repair_actions: list[RepairAction] | None = None,
) -> list[RepairAction]:
    """Return preview-only repair suggestions for an invalid deck.

    Phase 1E is *preview-only*: every returned :class:`RepairAction` keeps
    ``action="preview"`` (when a safe default exists) or
    ``action="not_applied"`` (when the field has no obvious local default,
    so the preview refuses to invent content). Nothing is mutated.

    Parameters
    ----------
    slides:
        The same input shape accepted by
        :func:`build_deck_quality_report`. Used only to read ``before``
        values; never mutated.
    repair_actions:
        Optional pre-computed repair actions from
        :func:`build_deck_quality_report`. When omitted, the function
        derives them by running ``build_deck_quality_report`` itself.

    Returns
    -------
    list[RepairAction]
        One entry per underlying validation failure. Order matches the
        underlying ``repair_actions`` order. Length is always equal to
        ``len(repair_actions)`` so callers can pair them by index.
    """

    if repair_actions is None:
        repair_actions = build_deck_quality_report(slides).repair_actions

    preview: list[RepairAction] = []
    is_list = isinstance(slides, list)
    for action in repair_actions:
        layout = action.layout or ""
        key = (layout, action.path, action.code)
        before: Any = None
        if is_list and 0 <= action.slide_index < len(slides):
            slide = slides[action.slide_index]
            if isinstance(slide, dict):
                before = slide.get(action.path)
        if key in _PREVIEW_DEFAULTS:
            preview.append(
                RepairAction(
                    slide_index=action.slide_index,
                    layout=action.layout,
                    path=action.path,
                    code=action.code,
                    message=action.message,
                    action="preview",
                    before=before,
                    after=_PREVIEW_DEFAULTS[key],
                )
            )
        else:
            # No safe default — surface the issue but do not invent content.
            preview.append(
                RepairAction(
                    slide_index=action.slide_index,
                    layout=action.layout,
                    path=action.path,
                    code=action.code,
                    message=action.message,
                    action="not_applied",
                    before=before,
                    after=None,
                )
            )
    return preview


def attach_quality_report(payload: dict[str, Any], slides: Any) -> dict[str, Any]:
    """Return a *shallow copy* of ``payload`` with a ``deck_quality`` key.

    Phase 1D helper for API routes that already shape an outgoing response
    dict (e.g. ``GET /api/slides/{task_id}``, ``GET /api/share/{token}``).
    The function is intentionally tiny:

    * It does not mutate ``payload``.
    * It does not mutate ``slides``.
    * It does not repair slides.
    * It does not raise; ``build_deck_quality_report`` always returns a
      ``DeckQualityReport`` even for malformed inputs.
    * The added value is the JSON-serializable ``DeckQualityReport.to_dict()``,
      so downstream JSON encoders need no special handling.

    Backward compatibility: existing clients that ignore unknown keys see
    no behavioral change. ``payload["slides"]`` (and any other field) is
    preserved as-is.
    """

    out = dict(payload)
    out["deck_quality"] = build_deck_quality_report(slides).to_dict()
    return out


__all__ = [
    "RepairAction",
    "DeckQualityReport",
    "build_deck_quality_report",
    "build_repair_preview",
    "attach_quality_report",
]
