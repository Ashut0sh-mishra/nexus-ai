"""Chart data processor.

Given a raw chart spec from the LLM (or auto-allocated from uploaded data),
produces a clean envelope::

    {
        "type":           "bar|line|pie|doughnut|area|scatter",
        "title":          str,
        "subtitle":       str | None,
        "unit":           str | None,
        "source":         str | None,
        "labels":         [str, ...],
        "values":         [float, ...],   # primary series values (for back-compat)
        "datasets":       [{label, data, backgroundColor, borderColor, ...}, ...],
        "chartjs_config": {type, data, options},   # consumable by Chart.js / QuickChart
        "pptx_config":    {xl_chart_type, categories, series, axis_format, ...},
        "axis":           {y_min, y_max, format},
        "palette":        [str, ...],
    }

Used by the agent loop (so each slide carries a renderer-ready chart) and by
the PPTX exporter (which prefers ``pptx_config`` over building one from raw
labels/values).
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Iterable

logger = logging.getLogger("nexus.services.chart")

_VALID_TYPES = {"bar", "line", "pie", "doughnut", "area", "scatter"}

# Theme palettes — keep in sync with ``services.export_service.THEMES`` so the
# PPTX and Chart.js renders share colors. Falls back to "Editorial".
_THEME_ACCENTS: dict[str, str] = {
    "light-pro": "#F59E0B",
    "Editorial": "#A78BFA",
    "Pixel": "#34D399",
    "Vellum": "#A0522D",
    "Dossier": "#60A5FA",
}

# Multi-series palette (used for pie/doughnut and >1 dataset).
_PALETTE_BY_THEME: dict[str, list[str]] = {
    "light-pro": ["#F59E0B", "#10B981", "#3B82F6", "#EC4899", "#8B5CF6", "#F472B6"],
    "Editorial": ["#A78BFA", "#34D399", "#60A5FA", "#F472B6", "#FBBF24", "#22D3EE"],
    "Pixel":     ["#34D399", "#60A5FA", "#F472B6", "#FBBF24", "#A78BFA", "#22D3EE"],
    "Vellum":    ["#A0522D", "#C19A6B", "#6B5E4A", "#8C7853", "#D4A373", "#A98467"],
    "Dossier":   ["#60A5FA", "#34D399", "#F472B6", "#FBBF24", "#A78BFA", "#22D3EE"],
}

_DEFAULT_PALETTE = _PALETTE_BY_THEME["Editorial"]
_DEFAULT_ACCENT = _THEME_ACCENTS["Editorial"]


# ── public API ──────────────────────────────────────────────────────────────
def auto_detect_chart_type(spec: dict[str, Any]) -> str:
    """Heuristically pick a chart type from a raw spec.

    Rules (in order):
    - Honor ``spec["chart_type"]`` when valid.
    - Time-like labels (years, quarters, dates, ordered numbers) -> "line".
    - 2-6 labels with non-cumulative values that sum to a "whole" -> "pie".
    - Otherwise -> "bar".
    """
    explicit = str(spec.get("chart_type") or spec.get("type") or "").strip().lower()
    if explicit in _VALID_TYPES:
        return explicit

    labels = [str(x) for x in (spec.get("labels") or [])]
    values = [_safe_float(v) for v in (spec.get("values") or [])]
    if not labels or not values:
        return "bar"

    if _looks_time_series(labels):
        return "line"

    # Share-of-whole: 2-6 categories, all positive, no obvious time order.
    if 2 <= len(labels) <= 6 and all(v > 0 for v in values):
        total = sum(values)
        if total > 0:
            ratios = [v / total for v in values]
            # If max share < 0.85 (i.e. it's actually a distribution, not just
            # one category), prefer pie.
            if max(ratios) < 0.85:
                return "pie"

    return "bar"


def process_chart_data(
    spec: dict[str, Any] | None,
    *,
    theme: str | None = None,
    title: str | None = None,
) -> dict[str, Any] | None:
    """Normalize a raw chart spec into a renderer-ready envelope.

    Accepts either:
    - the legacy slide shape: ``{chart_type, chart_data: {labels, values, unit, source}, title, subtitle}``
    - the flattened shape:    ``{chart_type, labels, values, unit, source, title, ...}``
    - or a multi-series shape: ``{chart_type, labels, datasets: [{label, data}, ...], ...}``

    Returns ``None`` when no usable data is present.
    """
    if not spec:
        return None

    # Pull labels/values from either flat or nested shape.
    cd = spec.get("chart_data") if isinstance(spec.get("chart_data"), dict) else {}
    labels_src = spec.get("labels") if "labels" in spec else cd.get("labels")
    values_src = spec.get("values") if "values" in spec else cd.get("values")
    datasets_src = spec.get("datasets") if "datasets" in spec else cd.get("datasets")
    unit = (spec.get("unit") or cd.get("unit") or "").strip() or None
    source = (spec.get("source") or cd.get("source") or "").strip() or None
    chart_title = (
        title
        or str(spec.get("title") or cd.get("title") or "").strip()
        or "Chart"
    )
    subtitle = str(spec.get("subtitle") or "").strip() or None

    labels: list[str] = [str(x) for x in (labels_src or []) if str(x).strip()]

    # Normalize datasets.
    datasets: list[dict[str, Any]] = []
    primary_values: list[float] = []
    if isinstance(datasets_src, list) and datasets_src:
        for ds in datasets_src:
            if not isinstance(ds, dict):
                continue
            data = [_safe_float(v) for v in (ds.get("data") or [])]
            if not data:
                continue
            datasets.append(
                {
                    "label": str(ds.get("label") or "Series"),
                    "data": data,
                }
            )
            if not primary_values:
                primary_values = data
    elif values_src:
        primary_values = [_safe_float(v) for v in values_src]
        datasets.append(
            {
                "label": f"Value ({unit})" if unit else "Value",
                "data": primary_values,
            }
        )

    if not labels or not primary_values:
        return None

    # Trim ragged series to the shorter of labels/data.
    n = min(len(labels), max(len(d["data"]) for d in datasets))
    labels = labels[:n]
    for d in datasets:
        d["data"] = d["data"][:n]
    primary_values = datasets[0]["data"]

    chart_type = auto_detect_chart_type({**spec, "labels": labels, "values": primary_values})

    palette = _PALETTE_BY_THEME.get(theme or "", _DEFAULT_PALETTE)
    accent = _THEME_ACCENTS.get(theme or "", _DEFAULT_ACCENT)

    axis = _compute_axis(primary_values, unit) if chart_type in {"bar", "line", "area", "scatter"} else None

    chartjs_config = _build_chartjs_config(
        chart_type=chart_type,
        labels=labels,
        datasets=datasets,
        unit=unit,
        title=chart_title,
        accent=accent,
        palette=palette,
        axis=axis,
    )
    pptx_config = _build_pptx_config(
        chart_type=chart_type,
        labels=labels,
        datasets=datasets,
        unit=unit,
        accent=accent,
        palette=palette,
        axis=axis,
    )

    out: dict[str, Any] = {
        "type": chart_type,
        "title": chart_title,
        "subtitle": subtitle,
        "unit": unit,
        "source": source,
        "labels": labels,
        "values": primary_values,
        "datasets": datasets,
        "chartjs_config": chartjs_config,
        "pptx_config": pptx_config,
        "palette": palette,
        "accent": accent,
    }
    if axis:
        out["axis"] = axis
    return out


# ── helpers ─────────────────────────────────────────────────────────────────
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _safe_float(v: Any) -> float:
    if isinstance(v, (int, float)) and not _is_nan(v):
        return float(v)
    if isinstance(v, str):
        m = _NUM.search(v.replace(",", ""))
        if m:
            try:
                return float(m.group(0))
            except ValueError:
                return 0.0
    return 0.0


def _is_nan(v: float) -> bool:
    try:
        return math.isnan(float(v))
    except Exception:
        return False


_TIME_RE = re.compile(r"^(?:Q[1-4](?:[\s-]?\d{2,4})?|FY\d{2,4}|\d{4}(?:-\d{2}){0,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)$", re.I)
_MONTHS = {
    "jan", "feb", "mar", "apr", "may", "jun", "jul",
    "aug", "sep", "sept", "oct", "nov", "dec",
    "january", "february", "march", "april", "june",
    "july", "august", "september", "october", "november", "december",
}


def _looks_time_series(labels: Iterable[str]) -> bool:
    labels = list(labels)
    if len(labels) < 2:
        return False
    hits = 0
    for raw in labels:
        s = str(raw).strip()
        if _TIME_RE.match(s):
            hits += 1
            continue
        low = s.lower()
        if low in _MONTHS:
            hits += 1
            continue
        if low.startswith(tuple(_MONTHS)):
            hits += 1
            continue
        if s.isdigit() and 1900 <= int(s) <= 2100:
            hits += 1
    return hits >= max(2, int(0.6 * len(labels)))


def _compute_axis(values: list[float], unit: str | None) -> dict[str, Any]:
    lo = min(values)
    hi = max(values)
    span = hi - lo if hi != lo else max(abs(hi), 1.0)
    pad = span * 0.1
    y_min = 0.0 if lo >= 0 else lo - pad
    y_max = hi + pad
    return {
        "y_min": y_min,
        "y_max": y_max,
        "format": _detect_format(unit, hi),
    }


def _detect_format(unit: str | None, hi: float) -> str:
    """Return one of ``"currency" | "percent" | "compact" | "plain"``."""
    u = (unit or "").lower().strip()
    if any(s in u for s in ("$", "usd", "eur", "£", "€", "¥")):
        return "currency"
    if "%" in u or "percent" in u:
        return "percent"
    if hi >= 1000:
        return "compact"
    return "plain"


def format_number(value: float, fmt: str = "compact") -> str:
    if value is None:
        return ""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if fmt == "percent":
        return f"{sign}{a:.1f}%"
    if fmt == "currency":
        return f"{sign}${_compact(a)}"
    if fmt == "compact":
        return f"{sign}{_compact(a)}"
    if a == int(a):
        return f"{sign}{int(a)}"
    return f"{sign}{a:.2f}"


def _compact(a: float) -> str:
    if a >= 1_000_000_000_000:
        return f"{a / 1_000_000_000_000:.1f}T"
    if a >= 1_000_000_000:
        return f"{a / 1_000_000_000:.1f}B"
    if a >= 1_000_000:
        return f"{a / 1_000_000:.1f}M"
    if a >= 1_000:
        return f"{a / 1_000:.1f}K"
    if a == int(a):
        return f"{int(a)}"
    return f"{a:.2f}"


def _build_chartjs_config(
    *,
    chart_type: str,
    labels: list[str],
    datasets: list[dict[str, Any]],
    unit: str | None,
    title: str,
    accent: str,
    palette: list[str],
    axis: dict[str, Any] | None,
) -> dict[str, Any]:
    is_share = chart_type in {"pie", "doughnut"}
    js_type = chart_type if chart_type != "area" else "line"

    js_datasets: list[dict[str, Any]] = []
    for i, ds in enumerate(datasets):
        color = palette[i % len(palette)]
        if is_share:
            js_datasets.append(
                {
                    "data": ds["data"],
                    "backgroundColor": [palette[k % len(palette)] for k in range(len(labels))],
                    "borderWidth": 0,
                }
            )
        elif chart_type == "line":
            js_datasets.append(
                {
                    "label": ds["label"],
                    "data": ds["data"],
                    "borderColor": color,
                    "backgroundColor": color + "33",
                    "borderWidth": 2,
                    "tension": 0.35,
                    "fill": False,
                    "pointRadius": 3,
                    "pointHoverRadius": 5,
                }
            )
        elif chart_type == "area":
            js_datasets.append(
                {
                    "label": ds["label"],
                    "data": ds["data"],
                    "borderColor": color,
                    "backgroundColor": color + "55",
                    "borderWidth": 2,
                    "tension": 0.35,
                    "fill": True,
                }
            )
        elif chart_type == "scatter":
            js_datasets.append(
                {
                    "label": ds["label"],
                    "data": [{"x": i, "y": v} for i, v in enumerate(ds["data"])],
                    "backgroundColor": color,
                    "borderColor": color,
                }
            )
        else:  # bar
            js_datasets.append(
                {
                    "label": ds["label"],
                    "data": ds["data"],
                    "backgroundColor": color + "CC",
                    "borderColor": color,
                    "borderWidth": 2,
                    "borderRadius": 4,
                }
            )

    options: dict[str, Any] = {
        "responsive": True,
        "maintainAspectRatio": False,
        "plugins": {
            "title": {"display": bool(title), "text": title},
            "legend": {"display": is_share or len(datasets) > 1},
        },
    }
    if not is_share:
        scales: dict[str, Any] = {
            "x": {"grid": {"display": False}},
            "y": {"grid": {"color": "rgba(127,127,127,0.12)"}},
        }
        if axis:
            scales["y"]["min"] = axis["y_min"]
            scales["y"]["max"] = axis["y_max"]
        options["scales"] = scales

    return {
        "type": js_type,
        "data": {"labels": labels, "datasets": js_datasets},
        "options": options,
    }


def _build_pptx_config(
    *,
    chart_type: str,
    labels: list[str],
    datasets: list[dict[str, Any]],
    unit: str | None,
    accent: str,
    palette: list[str],
    axis: dict[str, Any] | None,
) -> dict[str, Any]:
    """Renderer-agnostic spec the PPTX exporter consumes.

    We don't import ``pptx`` here (keep this module light); the exporter
    maps ``xl_chart_type`` strings onto python-pptx enum values.
    """
    xl_map = {
        "bar": "COLUMN_CLUSTERED",
        "line": "LINE",
        "pie": "PIE",
        "doughnut": "DOUGHNUT",
        "area": "AREA",
        "scatter": "XY_SCATTER",
    }
    return {
        "xl_chart_type": xl_map.get(chart_type, "COLUMN_CLUSTERED"),
        "categories": labels,
        "series": [
            {
                "label": ds["label"],
                "values": ds["data"],
                "color": palette[i % len(palette)],
            }
            for i, ds in enumerate(datasets)
        ],
        "accent": accent,
        "palette": palette,
        "unit": unit,
        "axis": axis,
        "value_format": (axis or {}).get("format", "plain"),
        "show_legend": chart_type in {"pie", "doughnut"} or len(datasets) > 1,
    }
