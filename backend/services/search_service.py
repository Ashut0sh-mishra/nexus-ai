"""Web search abstraction — Tavily primary, Serper fallback, no-op last resort."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("nexus.services.search")


class SearchService:
    """Returns (summary_text, sources[]). Never raises — always degrades gracefully."""

    async def search(self, query: str, max_results: int = 5) -> tuple[str, list[dict[str, Any]]]:
        if not query or not query.strip():
            return "", []

        if settings.TAVILY_API_KEY:
            try:
                summary, sources = await self._tavily(query, max_results)
                logger.info("search.tavily_ok", extra={"sources": len(sources)})
                if summary or sources:
                    return summary, sources
            except Exception as exc:
                logger.warning("search.tavily_failed", extra={"err": str(exc)})

        if settings.SERPER_API_KEY:
            try:
                summary, sources = await self._serper(query, max_results)
                logger.info("search.serper_ok", extra={"sources": len(sources)})
                if summary or sources:
                    return summary, sources
            except Exception as exc:
                logger.warning("search.serper_failed", extra={"err": str(exc)})

        # FREE fallbacks — no API key required.
        try:
            summary, sources = await self._duckduckgo(query, max_results)
            if summary or sources:
                logger.info("search.duckduckgo_ok", extra={"sources": len(sources)})
                return summary, sources
        except Exception as exc:
            logger.warning("search.duckduckgo_failed", extra={"err": str(exc)})

        try:
            summary, sources = await self._wikipedia(query, max_results)
            if summary or sources:
                logger.info("search.wikipedia_ok", extra={"sources": len(sources)})
                return summary, sources
        except Exception as exc:
            logger.warning("search.wikipedia_failed", extra={"err": str(exc)})

        logger.info("search.no_results")
        return "", []

    # ── Phase 6U: multi-query harvest until min_sources reached ──────────

    async def harvest(
        self,
        query: str,
        *,
        target_min: int = 0,
        max_total: int = 12,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Harvest sources across follow-up queries until ``target_min`` is met.

        The first call uses the verbatim ``query``. If the harvest is
        still under ``target_min`` after that, follow-up queries derived
        from the topic ("<query> 2024", "<query> overview", etc.) are
        issued. Results are deduplicated by ``url``.

        Behaviour:
        * Always returns whatever it has, even if ``target_min`` is not
          met (callers must not assume ``min_sources`` is satisfied).
        * Each follow-up reuses the same backend chain as :meth:`search`.
        * Caps the number of follow-up queries at 3 to keep latency
          bounded; total result list capped at ``max_total``.

        The first non-empty summary text is preserved as the harvested
        ``research`` text so the planner gets reasonable context even
        when later follow-ups return only sources without prose.
        """

        if not query or not query.strip():
            return "", []

        target = max(0, int(target_min))
        cap = max(target, int(max_total))
        seen_urls: set[str] = set()
        sources_out: list[dict[str, Any]] = []
        summary_parts: list[str] = []

        async def _take(q: str, k: int) -> None:
            try:
                summary, items = await self.search(q, max_results=k)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("search.harvest_failed", extra={"q": q, "err": str(exc)})
                return
            if isinstance(summary, str) and summary.strip():
                summary_parts.append(summary.strip())
            for s in items or []:
                if not isinstance(s, dict):
                    continue
                url = str(s.get("url") or "").strip()
                key = url or str(s)
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                sources_out.append(s)
                if len(sources_out) >= cap:
                    return

        # Primary query first (always).
        await _take(query, max(target or 6, 6))

        # Follow-ups only if we are still under the target. Three small,
        # generic riders that don't depend on the topic kind.
        if target and len(sources_out) < target:
            riders = (
                f"{query} 2024",
                f"{query} overview",
                f"{query} statistics",
            )
            for rider in riders:
                if len(sources_out) >= target:
                    break
                await _take(rider, 5)

        merged_summary = "\n\n".join(summary_parts[:2]).strip()
        logger.info(
            "search.harvest_done",
            extra={
                "target_min": target,
                "found": len(sources_out),
                "queries": 1 + (3 if target and len(sources_out) < target else 0),
            },
        )
        return merged_summary, sources_out[:cap]

    # ── DuckDuckGo Instant Answer (no key) ───────────────────────────────
    async def _duckduckgo(
        self, query: str, max_results: int
    ) -> tuple[str, list[dict[str, Any]]]:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, params=params, headers={"User-Agent": "NEXUS/1.0"})
            r.raise_for_status()
            data = r.json()
        answer = (
            data.get("AbstractText")
            or data.get("Answer")
            or data.get("Definition")
            or ""
        )
        sources: list[dict[str, Any]] = []
        if data.get("AbstractURL"):
            sources.append(
                {
                    "title": data.get("Heading") or query,
                    "url": data.get("AbstractURL"),
                    "snippet": (data.get("AbstractText") or "")[:400],
                }
            )
        for topic in (data.get("RelatedTopics") or [])[: max_results * 2]:
            if not isinstance(topic, dict):
                continue
            text = topic.get("Text") or ""
            href = topic.get("FirstURL") or ""
            if not text or not href:
                continue
            sources.append(
                {
                    "title": text.split(" - ")[0][:120],
                    "url": href,
                    "snippet": text[:400],
                }
            )
            if len(sources) >= max_results:
                break
        summary = self._format_summary(answer, sources)
        return summary, sources

    # ── Wikipedia REST summary (no key) ──────────────────────────────────
    async def _wikipedia(
        self, query: str, max_results: int
    ) -> tuple[str, list[dict[str, Any]]]:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": max_results,
            "format": "json",
        }
        headers = {"User-Agent": "NEXUS/1.0 (research)"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(search_url, params=params, headers=headers)
            r.raise_for_status()
            hits = (r.json().get("query") or {}).get("search") or []

            sources: list[dict[str, Any]] = []
            answer = ""
            for i, hit in enumerate(hits[:max_results]):
                title = hit.get("title") or ""
                if not title:
                    continue
                # Pull the REST summary for the top hit only (keeps things fast).
                snippet = re.sub(r"<[^>]+>", "", hit.get("snippet") or "")[:400]
                page_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                if i == 0:
                    try:
                        sr = await client.get(
                            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}",
                            headers=headers,
                        )
                        if sr.status_code == 200:
                            extract = (sr.json() or {}).get("extract") or ""
                            if extract:
                                answer = extract[:800]
                                snippet = extract[:400]
                    except Exception:
                        pass
                sources.append({"title": title, "url": page_url, "snippet": snippet})
        summary = self._format_summary(answer, sources)
        return summary, sources

    # ── Tavily ────────────────────────────────────────────────────────────
    async def _tavily(self, query: str, max_results: int) -> tuple[str, list[dict[str, Any]]]:
        try:
            from tavily import TavilyClient
        except ImportError as exc:
            raise RuntimeError("tavily-python is not installed") from exc

        def _call() -> Any:
            client = TavilyClient(api_key=settings.TAVILY_API_KEY)
            return client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=True,
            )

        result = await asyncio.to_thread(_call)
        answer = (result or {}).get("answer") or ""
        results = (result or {}).get("results") or []
        sources = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("content") or "")[:400],
            }
            for r in results
        ]
        summary = self._format_summary(answer, sources)
        return summary, sources

    # ── Serper ────────────────────────────────────────────────────────────
    async def _serper(self, query: str, max_results: int) -> tuple[str, list[dict[str, Any]]]:
        url = "https://google.serper.dev/search"
        headers = {"X-API-KEY": settings.SERPER_API_KEY, "Content-Type": "application/json"}
        payload = {"q": query, "num": max_results}
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        organic = data.get("organic") or []
        sources = [
            {
                "title": o.get("title", ""),
                "url": o.get("link", ""),
                "snippet": (o.get("snippet") or "")[:400],
            }
            for o in organic[:max_results]
        ]
        answer = data.get("answerBox", {}).get("answer") or data.get("knowledgeGraph", {}).get(
            "description", ""
        )
        summary = self._format_summary(answer, sources)
        return summary, sources

    @staticmethod
    def _format_summary(answer: str, sources: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        if answer:
            lines.append(f"Direct answer: {answer.strip()}")
        if sources:
            lines.append("\nSources:")
            for i, s in enumerate(sources, 1):
                t = s.get("title") or s.get("url") or ""
                snip = s.get("snippet") or ""
                lines.append(f"{i}. {t} — {snip}")
        return "\n".join(lines).strip()
