"""Phase 6U — SearchService.harvest min_sources tests.

Verifies that ``harvest`` keeps issuing follow-up queries until the
``target_min`` is met or all queries are exhausted. The 6T live
benchmark showed three prompts (mkt-001 3/4, evid-001 3/5, auto-001
0/4) where a single ``search`` call returned fewer sources than the
prompt's required minimum and the loop silently moved on.

These tests stub ``SearchService.search`` to deterministically return
small batches per query and confirm the harvest aggregates and
deduplicates across rider queries.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from services.search_service import SearchService  # noqa: E402


class _StubSearch(SearchService):
    """Test double whose ``search`` returns canned results per query."""

    def __init__(self, mapping: dict[str, list[dict]]):
        self._mapping = mapping
        self.calls: list[str] = []

    async def search(self, query: str, max_results: int = 5):
        self.calls.append(query)
        items = list(self._mapping.get(query, []))[:max_results]
        summary = f"summary-for:{query}" if items else ""
        return summary, items


def _src(url: str) -> dict:
    return {"title": url, "url": url, "snippet": ""}


@pytest.mark.asyncio
async def test_harvest_meets_target_via_followups() -> None:
    svc = _StubSearch(
        {
            "solar costs": [_src("https://a.test/1"), _src("https://a.test/2")],
            "solar costs 2024": [_src("https://b.test/1"), _src("https://b.test/2")],
            "solar costs overview": [_src("https://c.test/1")],
        }
    )
    summary, sources = await svc.harvest("solar costs", target_min=4, max_total=12)
    assert len(sources) >= 4
    urls = {s["url"] for s in sources}
    assert "https://a.test/1" in urls
    assert "https://b.test/1" in urls
    # First query is always issued; followups only because target unmet.
    assert svc.calls[0] == "solar costs"
    assert "solar costs 2024" in svc.calls


@pytest.mark.asyncio
async def test_harvest_deduplicates_by_url() -> None:
    dup = _src("https://dup.test/1")
    svc = _StubSearch(
        {
            "battery": [dup, _src("https://x.test/1")],
            "battery 2024": [dup, _src("https://y.test/1")],
            "battery overview": [_src("https://z.test/1")],
        }
    )
    _summary, sources = await svc.harvest("battery", target_min=4)
    urls = [s["url"] for s in sources]
    assert urls.count("https://dup.test/1") == 1


@pytest.mark.asyncio
async def test_harvest_returns_what_it_has_when_exhausted() -> None:
    # All queries return only one shared item; harvest must return that
    # single source rather than spinning forever or raising.
    svc = _StubSearch({"x": [_src("https://only.test/1")]})
    _summary, sources = await svc.harvest("x", target_min=5)
    assert len(sources) == 1


@pytest.mark.asyncio
async def test_harvest_skips_followups_when_target_met_immediately() -> None:
    items = [_src(f"https://a.test/{i}") for i in range(6)]
    svc = _StubSearch({"q": items})
    _summary, sources = await svc.harvest("q", target_min=4)
    assert len(sources) >= 4
    # Only the primary query should have been issued.
    assert svc.calls == ["q"]


@pytest.mark.asyncio
async def test_harvest_target_zero_keeps_legacy_behavior() -> None:
    svc = _StubSearch({"q": [_src("https://a.test/1")]})
    _summary, sources = await svc.harvest("q", target_min=0)
    # No followups; whatever the primary returned is fine.
    assert svc.calls == ["q"]
    assert len(sources) == 1
