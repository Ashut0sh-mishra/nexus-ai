"""Business intelligence extraction for uploaded files.

Takes raw extracted text plus structured data (from
:mod:`services.context_extractor`) and surfaces:

- ``chart_opportunities`` — data series the deck planner can turn into charts
- ``kpi_candidates``      — headline numbers worth a KPI card
- ``insights``            — short prose summaries
- ``data_tables``         — table-shaped data ready for slide rendering

The output is intentionally LLM-free (regex + numeric-column stats) so it
runs synchronously inside the upload route. The agent loop later feeds these
keys into the planner prompt so the deck plan auto-allocates slides to
detected opportunities.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("nexus.services.intelligence")


# --------------------------------------------------------------------------- #
# Regex patterns
# --------------------------------------------------------------------------- #
# Money: $1.2M, $5,000, USD 250k, $250.5 billion, etc.
_MONEY = re.compile(
    r"""
    (?P<currency>[$€£¥]|USD|EUR|GBP|JPY)?\s*
    (?P<amount>\d{1,3}(?:[,_]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    \s*
    (?P<scale>k|thousand|m|mn|million|b|bn|billion|t|tn|trillion)?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PERCENT = re.compile(r"(?P<sign>[+\-])?\s*(?P<value>\d+(?:\.\d+)?)\s*%")

# "Revenue grew from $2M to $5M", "increased from 100 to 250"
# Allows up to ~6 intervening words between the amounts (e.g. "$2M in 2022 to $5M").
_GROWTH_FROM_TO = re.compile(
    r"""
    (?P<metric>[A-Za-z][A-Za-z\s/&-]{2,40})
    \s+(?:grew|increased|rose|jumped|expanded|climbed|went)\s+
    from\s+(?P<from>[$€£]?\d[\d.,]*\s*(?:k|m|mn|million|b|bn|billion)?)
    (?:\s+\w+){0,6}\s+
    to\s+(?P<to>[$€£]?\d[\d.,]*\s*(?:k|m|mn|million|b|bn|billion)?)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# "X reduced by 35%", "CAC dropped 12%", "decreased by 8%"
_DECREASE_BY = re.compile(
    r"""
    (?P<metric>[A-Za-z][A-Za-z\s/&-]{2,40})
    \s+(?:reduced|dropped|decreased|fell|declined|shrunk|cut)\s+
    (?:by\s+)?
    (?P<value>\d+(?:\.\d+)?)\s*%
    """,
    re.IGNORECASE | re.VERBOSE,
)

# "X increased by 35%", "Revenue grew 12%"
_INCREASE_BY = re.compile(
    r"""
    (?P<metric>[A-Za-z][A-Za-z\s/&-]{2,40})
    \s+(?:grew|increased|rose|jumped|expanded|climbed|gained|up)\s+
    (?:by\s+)?
    (?P<value>\d+(?:\.\d+)?)\s*%
    """,
    re.IGNORECASE | re.VERBOSE,
)

# "Q1: $1M, Q2: $1.5M, Q3: $2.2M, Q4: $3M"
_QUARTER_SERIES = re.compile(
    r"Q[1-4]\s*[:=]\s*[$€£]?\d[\d.,]*\s*(?:k|m|mn|million|b|bn|billion)?",
    re.IGNORECASE,
)

# "2022: $2M, 2023: $3M, 2024: $5M"
_YEAR_SERIES = re.compile(
    r"(19|20)\d{2}\s*[:=]\s*[$€£]?\d[\d.,]*\s*(?:k|m|mn|million|b|bn|billion)?",
    re.IGNORECASE,
)


_SCALES: dict[str, float] = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "mn": 1e6, "million": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9,
    "t": 1e12, "tn": 1e12, "trillion": 1e12,
}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def extract_business_intelligence(
    text: str | None,
    structured_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run BI extraction over text + structured data."""
    text = text or ""
    structured_data = structured_data or {}

    chart_opps: list[dict[str, Any]] = []
    kpi_cands: list[dict[str, Any]] = []
    insights: list[str] = []
    data_tables: list[dict[str, Any]] = []

    # --- Text-driven detections --------------------------------------------
    chart_opps.extend(_detect_quarter_series(text))
    chart_opps.extend(_detect_year_series(text))

    growth_kpis, growth_insights, growth_charts = _detect_growth_phrases(text)
    kpi_cands.extend(growth_kpis)
    insights.extend(growth_insights)
    chart_opps.extend(growth_charts)

    kpi_cands.extend(_detect_standalone_money(text, limit=8))
    kpi_cands.extend(_detect_standalone_percentages(text, limit=8))

    # --- Structured-data-driven detections ---------------------------------
    if structured_data:
        st_charts, st_kpis, st_tables, st_insights = _from_structured(structured_data)
        chart_opps.extend(st_charts)
        kpi_cands.extend(st_kpis)
        data_tables.extend(st_tables)
        insights.extend(st_insights)

    return {
        "chart_opportunities": _dedupe(chart_opps, key="metric"),
        "kpi_candidates": _dedupe(kpi_cands, key="label")[:12],
        "insights": list(dict.fromkeys(insights))[:10],
        "data_tables": data_tables[:6],
    }


# --------------------------------------------------------------------------- #
# Text detectors
# --------------------------------------------------------------------------- #
def _parse_money(token: str) -> float | None:
    m = _MONEY.match(token.strip())
    if not m:
        return None
    raw = m.group("amount").replace(",", "").replace("_", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    scale = (m.group("scale") or "").lower()
    return value * _SCALES.get(scale, 1.0)


def _detect_growth_phrases(text: str) -> tuple[list[dict], list[str], list[dict]]:
    kpis: list[dict[str, Any]] = []
    insights: list[str] = []
    charts: list[dict[str, Any]] = []

    for m in _GROWTH_FROM_TO.finditer(text):
        metric = m.group("metric").strip().title()
        v_from = _parse_money(m.group("from"))
        v_to = _parse_money(m.group("to"))
        if v_from is None or v_to is None or v_from <= 0:
            continue
        change_pct = ((v_to - v_from) / v_from) * 100
        kpis.append(
            {
                "label": metric,
                "value": _fmt_money(v_to),
                "raw_value": v_to,
                "change": f"{change_pct:+.0f}%",
                "trend": "up" if change_pct >= 0 else "down",
            }
        )
        insights.append(
            f"{metric} grew from {_fmt_money(v_from)} to {_fmt_money(v_to)} ({change_pct:+.0f}%)."
        )
        charts.append(
            {
                "metric": metric,
                "chart_type": "bar",
                "data_points": [
                    {"label": "Start", "value": v_from},
                    {"label": "End", "value": v_to},
                ],
                "source": "text:growth_from_to",
            }
        )

    for m in _INCREASE_BY.finditer(text):
        metric = m.group("metric").strip().title()
        try:
            pct = float(m.group("value"))
        except ValueError:
            continue
        kpis.append(
            {
                "label": metric,
                "value": f"+{pct:g}%",
                "raw_value": pct,
                "change": f"+{pct:g}%",
                "trend": "up",
            }
        )
        insights.append(f"{metric} increased by {pct:g}%.")

    for m in _DECREASE_BY.finditer(text):
        metric = m.group("metric").strip().title()
        try:
            pct = float(m.group("value"))
        except ValueError:
            continue
        kpis.append(
            {
                "label": metric,
                "value": f"-{pct:g}%",
                "raw_value": pct,
                "change": f"-{pct:g}%",
                "trend": "down",
            }
        )
        insights.append(f"{metric} reduced by {pct:g}%.")

    return kpis, insights, charts


def _detect_quarter_series(text: str) -> list[dict[str, Any]]:
    matches = _QUARTER_SERIES.findall(text)
    if len(matches) < 2:
        return []
    points: list[dict[str, Any]] = []
    for token in re.finditer(
        r"(?P<label>Q[1-4])\s*[:=]\s*(?P<val>[$€£]?\d[\d.,]*\s*(?:k|m|mn|million|b|bn|billion)?)",
        text,
        re.IGNORECASE,
    ):
        v = _parse_money(token.group("val"))
        if v is None:
            continue
        points.append({"label": token.group("label").upper(), "value": v})
    if len(points) < 2:
        return []
    return [
        {
            "metric": "Quarterly trend",
            "chart_type": "line",
            "data_points": points[:8],
            "source": "text:quarter_series",
        }
    ]


def _detect_year_series(text: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for token in re.finditer(
        r"(?P<label>(?:19|20)\d{2})\s*[:=]\s*(?P<val>[$€£]?\d[\d.,]*\s*(?:k|m|mn|million|b|bn|billion)?)",
        text,
        re.IGNORECASE,
    ):
        v = _parse_money(token.group("val"))
        if v is None:
            continue
        points.append({"label": token.group("label"), "value": v})
    if len(points) < 2:
        return []
    return [
        {
            "metric": "Yearly trend",
            "chart_type": "line",
            "data_points": points[:10],
            "source": "text:year_series",
        }
    ]


def _detect_standalone_money(text: str, *, limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[float] = set()
    for m in _MONEY.finditer(text):
        # Require an explicit currency symbol/word — a bare number with a
        # scale letter like "t" can collide with "to" / "the" in prose.
        if not m.group("currency"):
            continue
        v = _parse_money(m.group(0))
        if v is None or v in seen or v < 100:
            continue
        seen.add(v)
        # Try to grab a 1-3 word label preceding the amount.
        start = max(0, m.start() - 40)
        prefix = text[start : m.start()].rstrip(" :=")
        label_match = re.search(r"([A-Za-z][A-Za-z &/-]{2,40})$", prefix)
        label = label_match.group(1).strip().title() if label_match else "Amount"
        out.append(
            {
                "label": label,
                "value": _fmt_money(v),
                "raw_value": v,
                "change": None,
                "trend": None,
            }
        )
        if len(out) >= limit:
            break
    return out


def _detect_standalone_percentages(text: str, *, limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in _PERCENT.finditer(text):
        try:
            v = float(m.group("value"))
        except ValueError:
            continue
        sign = m.group("sign") or ""
        start = max(0, m.start() - 40)
        prefix = text[start : m.start()].rstrip(" :=")
        label_match = re.search(r"([A-Za-z][A-Za-z &/-]{2,40})$", prefix)
        label = label_match.group(1).strip().title() if label_match else "Metric"
        out.append(
            {
                "label": label,
                "value": f"{sign}{v:g}%",
                "raw_value": v,
                "change": f"{sign}{v:g}%" if sign else None,
                "trend": "up" if sign == "+" else "down" if sign == "-" else None,
            }
        )
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------- #
# Structured-data detectors (CSV/XLSX/JSON/PDF tables)
# --------------------------------------------------------------------------- #
def _from_structured(
    data: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    fmt = data.get("format")
    if fmt == "table":
        return _from_table(data)
    if fmt == "xlsx":
        out_charts: list[dict] = []
        out_kpis: list[dict] = []
        out_tables: list[dict] = []
        out_insights: list[str] = []
        for sheet in data.get("sheets", [])[:5]:
            ch, kp, tb, ins = _from_table(sheet)
            for c in ch:
                c["source"] = f"sheet:{sheet.get('sheet')}"
            out_charts.extend(ch)
            out_kpis.extend(kp)
            out_tables.extend(tb)
            out_insights.extend(ins)
        return out_charts, out_kpis, out_tables, out_insights
    if fmt == "pdf":
        out_tables = []
        for t in data.get("tables", [])[:5]:
            out_tables.append(
                {
                    "headers": t.get("headers") or [],
                    "rows": t.get("rows") or [],
                    "source": f"pdf:p{t.get('page')}",
                }
            )
        return [], [], out_tables, []
    return [], [], [], []


def _from_table(
    table: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    headers = table.get("headers") or []
    rows = table.get("sample_rows") or []
    numeric = table.get("numeric_columns") or []

    charts: list[dict[str, Any]] = []
    kpis: list[dict[str, Any]] = []
    insights: list[str] = []

    if headers and rows:
        # First non-numeric column is treated as the label axis.
        label_idx = 0
        numeric_names = {c["name"] for c in numeric}
        for i, h in enumerate(headers):
            if h not in numeric_names:
                label_idx = i
                break

        for col in numeric[:4]:
            try:
                col_idx = headers.index(col["name"])
            except ValueError:
                continue
            data_points = []
            for row in rows:
                if len(row) <= max(col_idx, label_idx):
                    continue
                try:
                    val = float(str(row[col_idx]).replace(",", ""))
                except (TypeError, ValueError):
                    continue
                data_points.append(
                    {"label": str(row[label_idx]), "value": val}
                )
            if len(data_points) >= 2:
                charts.append(
                    {
                        "metric": col["name"],
                        "chart_type": _suggest_chart_type(data_points),
                        "data_points": data_points,
                        "source": "structured:numeric_column",
                    }
                )

    for col in numeric[:6]:
        kpis.append(
            {
                "label": f"{col['name']} (sum)",
                "value": _fmt_number(col["sum"]),
                "raw_value": col["sum"],
                "change": None,
                "trend": None,
            }
        )
        insights.append(
            f"{col['name']}: avg {_fmt_number(col['avg'])}, "
            f"min {_fmt_number(col['min'])}, max {_fmt_number(col['max'])}."
        )

    table_payload = (
        [
            {
                "headers": headers,
                "rows": rows,
                "source": "structured:sample_rows",
            }
        ]
        if headers and rows
        else []
    )

    return charts, kpis, table_payload, insights


def _suggest_chart_type(points: list[dict[str, Any]]) -> str:
    labels = [str(p.get("label", "")) for p in points]
    # Year-like or quarter-like labels => line
    if all(re.fullmatch(r"(19|20)\d{2}", lbl or "") for lbl in labels if lbl):
        return "line"
    if all(re.fullmatch(r"Q[1-4](?:\s*\d{2,4})?", lbl or "", re.IGNORECASE) for lbl in labels if lbl):
        return "line"
    if 2 <= len(points) <= 6:
        return "bar"
    return "line"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _fmt_money(v: float) -> str:
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e12:
        return f"{sign}${a / 1e12:.1f}T"
    if a >= 1e9:
        return f"{sign}${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}${a / 1e3:.1f}K"
    return f"{sign}${a:,.0f}"


def _fmt_number(v: float) -> str:
    a = abs(v)
    sign = "-" if v < 0 else ""
    if a >= 1e9:
        return f"{sign}{a / 1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}{a / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}{a / 1e3:.1f}K"
    if a == int(a):
        return f"{sign}{int(a):,}"
    return f"{sign}{a:,.2f}"


def _dedupe(items: list[dict[str, Any]], *, key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        k = str(item.get(key, "")).strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out
