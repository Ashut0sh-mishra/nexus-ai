"""Phase 1B — typed slide-contract validation for the 7 canonical layouts.

This module is the single source of truth for what a *valid* slide payload
looks like for each canonical layout (``title``, ``bullets``, ``two-col``,
``quote``, ``stats``, ``chart``, ``closing``). It mirrors the field shapes
that ``backend/agent/loop.py::NexusAgentLoop._normalize_slides`` produces.

Goals (intentionally narrow — Phase 1B):
* Validate required fields per layout.
* Validate field types.
* Validate ``chart_data`` shape for chart slides.
* Validate ``stats`` item shape for stats slides.
* Validate ``columns`` shape for two-col slides.
* Return *structured* validation results, not just True/False.
* Be usable before *or* after ``_normalize_slides``.

Out of scope (do NOT add here):
* Auto-repair of malformed slides.
* Deck-level quality scoring.
* Export rendering coverage.
* New layouts.

The validator is hand-rolled (no third-party JSON-schema dep) so the
backend keeps a single non-Pydantic-dependent path that is trivial to
unit-test without a database or app context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.layouts_registry import (
    CANONICAL_LAYOUTS,
    FALLBACK_LAYOUT,
    LAYOUT_ALIASES,
    normalize_layout,
)

# ── Public result types ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ValidationError:
    """A single, structured validation failure.

    ``path`` is a dotted JSON-pointer-ish path into the slide payload, e.g.
    ``"chart_data.values[1]"`` or ``"columns[0].heading"``.
    ``code`` is a stable machine token (e.g. ``missing``, ``wrong_type``).
    ``message`` is a short human-readable explanation.
    """

    path: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}


@dataclass
class ValidationResult:
    """Outcome of validating a single slide payload."""

    ok: bool
    layout: str | None
    errors: list[ValidationError] = field(default_factory=list)
    normalized: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "layout": self.layout,
            "errors": [e.to_dict() for e in self.errors],
            "normalized": self.normalized,
        }


# ── Constants mirrored from the normalizer ─────────────────────────────────

_VALID_LAYOUTS = frozenset(CANONICAL_LAYOUTS)
_VALID_CHART_TYPES = frozenset({"bar", "line", "doughnut"})
_MAX_BULLETS = 4
_MAX_COLUMNS = 2
_MAX_STATS = 3


# ── Field-level helpers ────────────────────────────────────────────────────


def _require_str(
    raw: dict[str, Any],
    key: str,
    errors: list[ValidationError],
    *,
    allow_empty: bool = False,
    path_prefix: str = "",
) -> None:
    path = f"{path_prefix}{key}"
    if key not in raw:
        errors.append(ValidationError(path, "missing", f"required field '{key}' is missing"))
        return
    val = raw[key]
    if not isinstance(val, str):
        errors.append(
            ValidationError(path, "wrong_type", f"'{key}' must be a string, got {type(val).__name__}")
        )
        return
    if not allow_empty and not val.strip():
        errors.append(ValidationError(path, "empty", f"'{key}' must be a non-empty string"))


def _require_list(
    raw: dict[str, Any],
    key: str,
    errors: list[ValidationError],
) -> list[Any] | None:
    if key not in raw:
        errors.append(ValidationError(key, "missing", f"required field '{key}' is missing"))
        return None
    val = raw[key]
    if not isinstance(val, list):
        errors.append(
            ValidationError(key, "wrong_type", f"'{key}' must be a list, got {type(val).__name__}")
        )
        return None
    return val


# ── Per-layout validators ──────────────────────────────────────────────────


def _validate_title(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    _require_str(raw, "title", errors)
    # Phase 1B.1: ``subtitle`` and ``eyebrow`` are part of the normalized
    # title-slide contract emitted by ``_normalize_slides``. They may be
    # empty strings (the normalizer can emit ``""`` for ``subtitle``),
    # but the keys must be present.
    _require_str(raw, "subtitle", errors, allow_empty=True)
    _require_str(raw, "eyebrow", errors, allow_empty=True)


def _validate_bullets(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    _require_str(raw, "title", errors)
    bullets = _require_list(raw, "bullets", errors)
    if bullets is None:
        return
    if not bullets:
        errors.append(ValidationError("bullets", "empty", "'bullets' must contain at least 1 item"))
    if len(bullets) > _MAX_BULLETS:
        errors.append(
            ValidationError(
                "bullets", "too_many", f"'bullets' has {len(bullets)} items (max {_MAX_BULLETS})"
            )
        )
    for i, b in enumerate(bullets):
        if not isinstance(b, str):
            errors.append(
                ValidationError(
                    f"bullets[{i}]",
                    "wrong_type",
                    f"bullet {i} must be a string, got {type(b).__name__}",
                )
            )
        elif not b.strip():
            errors.append(ValidationError(f"bullets[{i}]", "empty", f"bullet {i} is empty"))


def _validate_two_col(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    _require_str(raw, "title", errors)
    cols = _require_list(raw, "columns", errors)
    if cols is None:
        return
    if not cols:
        errors.append(ValidationError("columns", "empty", "'columns' must contain at least 1 item"))
    if len(cols) > _MAX_COLUMNS:
        errors.append(
            ValidationError(
                "columns", "too_many", f"'columns' has {len(cols)} items (max {_MAX_COLUMNS})"
            )
        )
    for i, c in enumerate(cols):
        if not isinstance(c, dict):
            errors.append(
                ValidationError(
                    f"columns[{i}]",
                    "wrong_type",
                    f"column {i} must be an object, got {type(c).__name__}",
                )
            )
            continue
        _require_str(c, "heading", errors, path_prefix=f"columns[{i}].")
        _require_str(c, "body", errors, path_prefix=f"columns[{i}].")


def _validate_quote(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    _require_str(raw, "title", errors)
    _require_str(raw, "quote", errors)
    # Phase 1B.1: ``attribution`` is part of the normalized quote-slide
    # contract. Empty strings are permitted (the normalizer emits ``""``
    # when no attribution is provided), but the key must be present.
    _require_str(raw, "attribution", errors, allow_empty=True)


def _validate_stats(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    _require_str(raw, "title", errors)
    stats = _require_list(raw, "stats", errors)
    if stats is None:
        return
    if not stats:
        errors.append(ValidationError("stats", "empty", "'stats' must contain at least 1 item"))
    if len(stats) > _MAX_STATS:
        errors.append(
            ValidationError(
                "stats", "too_many", f"'stats' has {len(stats)} items (max {_MAX_STATS})"
            )
        )
    for i, s in enumerate(stats):
        if not isinstance(s, dict):
            errors.append(
                ValidationError(
                    f"stats[{i}]",
                    "wrong_type",
                    f"stat {i} must be an object, got {type(s).__name__}",
                )
            )
            continue
        _require_str(s, "value", errors, path_prefix=f"stats[{i}].")
        _require_str(s, "label", errors, path_prefix=f"stats[{i}].")


def _validate_chart(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    _require_str(raw, "title", errors)

    ctype = raw.get("chart_type")
    if "chart_type" not in raw:
        errors.append(ValidationError("chart_type", "missing", "'chart_type' is required"))
    elif not isinstance(ctype, str):
        errors.append(ValidationError("chart_type", "wrong_type", "'chart_type' must be a string"))
    elif ctype.strip().lower() not in _VALID_CHART_TYPES:
        errors.append(
            ValidationError(
                "chart_type",
                "invalid_value",
                f"'chart_type' must be one of {sorted(_VALID_CHART_TYPES)}, got {ctype!r}",
            )
        )

    if "chart_data" not in raw:
        errors.append(ValidationError("chart_data", "missing", "'chart_data' is required"))
        return
    cd = raw["chart_data"]
    if not isinstance(cd, dict):
        errors.append(
            ValidationError(
                "chart_data",
                "wrong_type",
                f"'chart_data' must be an object, got {type(cd).__name__}",
            )
        )
        return

    labels = cd.get("labels")
    values = cd.get("values")

    if "labels" not in cd:
        errors.append(ValidationError("chart_data.labels", "missing", "'labels' is required"))
        labels = None
    elif not isinstance(labels, list):
        errors.append(
            ValidationError("chart_data.labels", "wrong_type", "'labels' must be a list")
        )
        labels = None
    else:
        for i, l in enumerate(labels):
            if not isinstance(l, str):
                errors.append(
                    ValidationError(
                        f"chart_data.labels[{i}]",
                        "wrong_type",
                        f"label {i} must be a string",
                    )
                )

    if "values" not in cd:
        errors.append(ValidationError("chart_data.values", "missing", "'values' is required"))
        values = None
    elif not isinstance(values, list):
        errors.append(
            ValidationError("chart_data.values", "wrong_type", "'values' must be a list")
        )
        values = None
    else:
        for i, v in enumerate(values):
            # bool is a subclass of int — explicitly reject it as a number.
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                errors.append(
                    ValidationError(
                        f"chart_data.values[{i}]",
                        "wrong_type",
                        f"value {i} must be a number, got {type(v).__name__}",
                    )
                )

    if isinstance(labels, list) and isinstance(values, list) and len(labels) != len(values):
        errors.append(
            ValidationError(
                "chart_data",
                "length_mismatch",
                f"'labels' ({len(labels)}) and 'values' ({len(values)}) must have equal length",
            )
        )

    if isinstance(labels, list) and not labels:
        errors.append(ValidationError("chart_data.labels", "empty", "'labels' must not be empty"))

    # Phase 1B.1 Audit Correction: ``unit`` and ``source`` are part of the
    # normalized chart_data contract. Keys must be present; empty strings
    # are permitted (the normalizer emits ``""`` when absent). Non-string
    # values still fail.
    _require_str(cd, "unit", errors, allow_empty=True, path_prefix="chart_data.")
    _require_str(cd, "source", errors, allow_empty=True, path_prefix="chart_data.")

    # Phase 1B.1: chart slides carry a slide-level ``subtitle`` in the
    # normalized contract. Empty strings allowed; missing key is not.
    _require_str(raw, "subtitle", errors, allow_empty=True)


def _validate_closing(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    _require_str(raw, "title", errors)
    # Phase 1B.1: ``subtitle`` and ``cta`` are part of the normalized
    # closing-slide contract. Both keys must be present; empty strings
    # are permitted (the normalizer can emit ``""`` for ``subtitle``).
    _require_str(raw, "subtitle", errors, allow_empty=True)
    _require_str(raw, "cta", errors, allow_empty=True)


def _validate_bigstat(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    """Phase 6AA — single dominant metric.

    Required: ``title``, ``value``. Optional but key-must-exist:
    ``label`` (the unit / context line) and ``subtitle`` (one-line
    framing). Empty strings are permitted on the optional keys so the
    deck-repair pass can seed defaults the same way it does for title /
    closing slides.
    """
    _require_str(raw, "title", errors)
    _require_str(raw, "value", errors)
    _require_str(raw, "label", errors, allow_empty=True)
    _require_str(raw, "subtitle", errors, allow_empty=True)


def _validate_section_divider(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    """Phase 6AA — typography pause between deck sections.

    Required: ``title``. Optional but key-must-exist: ``eyebrow`` and
    ``subtitle`` (both empty-string-permitted so the deck-repair pass
    can seed defaults if missing).
    """
    _require_str(raw, "title", errors)
    _require_str(raw, "eyebrow", errors, allow_empty=True)
    _require_str(raw, "subtitle", errors, allow_empty=True)


_MAX_TIMELINE_EVENTS = 6


def _validate_timeline(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    """Phase 6AC — chronological events.

    Required: ``title``, ``events`` (list of {date, label}). Optional but
    key-must-exist: ``subtitle``. Each event requires both a string
    ``date`` and a string ``label``; both must be non-empty so the
    timeline does not render visual gaps.
    """
    _require_str(raw, "title", errors)
    _require_str(raw, "subtitle", errors, allow_empty=True)
    events = _require_list(raw, "events", errors)
    if events is None:
        return
    if not events:
        errors.append(ValidationError("events", "empty", "'events' must contain at least 1 item"))
    if len(events) > _MAX_TIMELINE_EVENTS:
        errors.append(
            ValidationError(
                "events",
                "too_many",
                f"'events' has {len(events)} items (max {_MAX_TIMELINE_EVENTS})",
            )
        )
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            errors.append(
                ValidationError(
                    f"events[{i}]",
                    "wrong_type",
                    f"event {i} must be an object, got {type(e).__name__}",
                )
            )
            continue
        _require_str(e, "date", errors, path_prefix=f"events[{i}].")
        _require_str(e, "label", errors, path_prefix=f"events[{i}].")


def _validate_comparison(raw: dict[str, Any], errors: list[ValidationError]) -> None:
    """Phase 6AC — side-by-side comparison.

    Required: ``title``, ``left`` (object {heading, body}), ``right``
    (object {heading, body}). Optional but key-must-exist: ``subtitle``.
    Both sides require non-empty heading + body; an empty side defeats
    the layout's purpose.
    """
    _require_str(raw, "title", errors)
    _require_str(raw, "subtitle", errors, allow_empty=True)
    for side in ("left", "right"):
        if side not in raw:
            errors.append(ValidationError(side, "missing", f"required field '{side}' is missing"))
            continue
        block = raw[side]
        if not isinstance(block, dict):
            errors.append(
                ValidationError(
                    side, "wrong_type", f"'{side}' must be an object, got {type(block).__name__}"
                )
            )
            continue
        _require_str(block, "heading", errors, path_prefix=f"{side}.")
        _require_str(block, "body", errors, path_prefix=f"{side}.")


_VALIDATORS: dict[str, Any] = {
    "title": _validate_title,
    "bullets": _validate_bullets,
    "two-col": _validate_two_col,
    "quote": _validate_quote,
    "stats": _validate_stats,
    "chart": _validate_chart,
    "closing": _validate_closing,
    "bigstat": _validate_bigstat,
    "section_divider": _validate_section_divider,
    "timeline": _validate_timeline,
    "comparison": _validate_comparison,
}


# ── Public API ─────────────────────────────────────────────────────────────


def validate_slide(
    raw: Any,
    *,
    resolve_aliases: bool = True,
) -> ValidationResult:
    """Validate a single slide payload.

    Parameters
    ----------
    raw:
        The slide dict to validate. Anything that is not a ``dict`` is
        rejected with an ``invalid_payload`` error.
    resolve_aliases:
        When True (default), pass the raw layout through
        :func:`agent.layouts_registry.normalize_layout` first. When False,
        only exact canonical names are accepted.

    Returns
    -------
    ValidationResult
        Structured outcome with ``ok``, resolved ``layout``, and
        ``errors``. On success, ``normalized`` is a *shallow copy* of the
        input ``raw`` dict with the canonical layout name pinned
        (``{**raw, "layout": resolved}``); content fields are unchanged.
        On failure, ``normalized`` is ``None``. This validator does
        *not* repair malformed payloads — it is not auto-repair.
    """

    if not isinstance(raw, dict):
        return ValidationResult(
            ok=False,
            layout=None,
            errors=[
                ValidationError(
                    "", "invalid_payload", f"slide must be an object, got {type(raw).__name__}"
                )
            ],
        )

    raw_layout = raw.get("layout")
    if raw_layout is None:
        return ValidationResult(
            ok=False,
            layout=None,
            errors=[ValidationError("layout", "missing", "'layout' is required")],
        )
    if not isinstance(raw_layout, str):
        return ValidationResult(
            ok=False,
            layout=None,
            errors=[
                ValidationError(
                    "layout",
                    "wrong_type",
                    f"'layout' must be a string, got {type(raw_layout).__name__}",
                )
            ],
        )

    if resolve_aliases:
        resolved = normalize_layout(raw_layout)
        # ``normalize_layout`` returns FALLBACK_LAYOUT for *any* unknown value
        # — that is a render-time safety net, not a contract. The validator
        # must NOT silently accept that fallback. Only treat the resolved
        # value as canonical if the input was itself canonical or a known
        # alias.
        key = raw_layout.strip().lower()
        is_known = key in _VALID_LAYOUTS or key in LAYOUT_ALIASES
        if not is_known:
            return ValidationResult(
                ok=False,
                layout=None,
                errors=[
                    ValidationError(
                        "layout",
                        "unknown_layout",
                        f"layout {raw_layout!r} is not one of {sorted(_VALID_LAYOUTS)}",
                    )
                ],
            )
    else:
        # Phase 1B.1: strict mode requires an EXACT canonical name. No
        # case-folding, no whitespace-trimming, no alias resolution. This
        # makes ``resolve_aliases=False`` a true contract gate that fails
        # for inputs like ``"Title"``, ``" title "``, or ``"two_col"``.
        resolved = raw_layout
        if resolved not in _VALID_LAYOUTS:
            return ValidationResult(
                ok=False,
                layout=None,
                errors=[
                    ValidationError(
                        "layout",
                        "unknown_layout",
                        f"layout {raw_layout!r} is not one of {sorted(_VALID_LAYOUTS)} (strict mode)",
                    )
                ],
            )

    if resolved not in _VALID_LAYOUTS:
        # Unknown layouts MUST NOT silently pass. They are surfaced as
        # errors even though ``normalize_layout`` returns the FALLBACK_LAYOUT
        # at runtime — that is a render-time safety net, not a contract.
        return ValidationResult(
            ok=False,
            layout=None,
            errors=[
                ValidationError(
                    "layout",
                    "unknown_layout",
                    f"layout {raw_layout!r} is not one of {sorted(_VALID_LAYOUTS)}",
                )
            ],
        )

    errors: list[ValidationError] = []
    _VALIDATORS[resolved](raw, errors)

    # Phase 1B.1: ``normalized`` is a *shallow copy* of the input with the
    # canonical layout name pinned. It is NOT an auto-repair of the
    # payload — content fields are unchanged. Mutating ``normalized``
    # therefore does not mutate the caller's input dict.
    normalized: dict[str, Any] | None
    if errors:
        normalized = None
    else:
        normalized = dict(raw)
        normalized["layout"] = resolved

    return ValidationResult(
        ok=not errors,
        layout=resolved,
        errors=errors,
        normalized=normalized,
    )


def validate_deck(slides: Any) -> list[ValidationResult]:
    """Validate a list of slides; returns one ``ValidationResult`` per slide."""

    if not isinstance(slides, list):
        return [
            ValidationResult(
                ok=False,
                layout=None,
                errors=[
                    ValidationError(
                        "",
                        "invalid_payload",
                        f"deck must be a list, got {type(slides).__name__}",
                    )
                ],
            )
        ]
    return [validate_slide(s) for s in slides]


__all__ = [
    "ValidationError",
    "ValidationResult",
    "validate_slide",
    "validate_deck",
    "FALLBACK_LAYOUT",
]
