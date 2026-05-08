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

    # ── DEEP RESEARCH (multi-hop) ─────────────────────────────────────────
    # Fixes the "Sri Lanka deck about Caltech students" hallucination class:
    # we fetch the actual page text for the top results, extract concrete
    # entities (dates, numbers, proper nouns), then run a second focused
    # search using those entities. The combined corpus is what the LLM sees.
    async def deep_search(
        self,
        query: str,
        max_results: int = 6,
        *,
        fetch_pages: int = 3,
        do_second_hop: bool = True,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Multi-hop research. Always returns; never raises."""
        first_summary, first_sources = await self.search(query, max_results=max_results)

        # Fetch the top N pages and append extracted main text.
        page_texts: list[str] = []
        if fetch_pages > 0 and first_sources:
            page_texts = await self._fetch_pages(
                [s.get("url") for s in first_sources[:fetch_pages] if s.get("url")]
            )

        # Pull entities (4-digit years, $ amounts, percentages, capitalized
        # multi-word phrases) from the fetched text.
        entities = self._extract_entities(" \n".join(page_texts))

        second_summary, second_sources = "", []
        if do_second_hop and entities:
            follow_q = f"{query} {' '.join(entities[:5])}"[:300]
            try:
                second_summary, second_sources = await self.search(
                    follow_q, max_results=max(2, max_results // 2)
                )
            except Exception as exc:
                logger.warning("search.deep_second_hop_failed", extra={"err": str(exc)})

        # Build a single corpus the LLM can chew on.
        parts: list[str] = []
        if first_summary:
            parts.append("== Primary search ==\n" + first_summary)
        if page_texts:
            parts.append("== Source excerpts ==")
            for s, txt in zip(first_sources[:fetch_pages], page_texts):
                if not txt:
                    continue
                parts.append(f"[{s.get('title','')}] {txt[:1500]}")
        if entities:
            parts.append("== Key entities extracted ==\n" + ", ".join(entities[:25]))
        if second_summary:
            parts.append("== Follow-up search ==\n" + second_summary)

        all_sources = first_sources[:]
        seen = {s.get("url") for s in all_sources}
        for s in second_sources:
            if s.get("url") and s["url"] not in seen:
                all_sources.append(s)
                seen.add(s["url"])

        return ("\n\n".join(parts).strip(), all_sources)

    async def _fetch_pages(self, urls: list[str]) -> list[str]:
        """Fetch each URL and return cleaned main-text (best-effort, ~2KB each)."""
        async def _one(u: str) -> str:
            if not u:
                return ""
            try:
                async with httpx.AsyncClient(
                    timeout=12.0,
                    follow_redirects=True,
                    headers={"User-Agent": "NEXUS/1.0 research-bot"},
                ) as client:
                    r = await client.get(u)
                if r.status_code != 200 or "text/html" not in r.headers.get(
                    "content-type", ""
                ):
                    return ""
                return self._extract_main_text(r.text)
            except Exception as exc:
                logger.debug("search.fetch_page_failed", extra={"url": u[:80], "err": str(exc)})
                return ""

        return await asyncio.gather(*(_one(u) for u in urls))

    @staticmethod
    def _extract_main_text(html: str) -> str:
        """Strip scripts/styles/nav, return collapsed text body, capped at 2KB."""
        try:
            from bs4 import BeautifulSoup  # type: ignore
        except Exception:
            # Regex fallback if bs4 missing.
            text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            return re.sub(r"\s+", " ", text).strip()[:2000]

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
            tag.decompose()
        # Prefer <article> or <main> if present.
        root = soup.find("article") or soup.find("main") or soup.body or soup
        text = root.get_text(" ", strip=True) if root else ""
        return re.sub(r"\s+", " ", text)[:2000]

    @staticmethod
    def _extract_entities(text: str) -> list[str]:
        """Pull years, money, percents, and 2-3 word Capitalized phrases."""
        if not text:
            return []
        out: list[str] = []
        seen: set[str] = set()

        def add(x: str) -> None:
            x = x.strip()
            if x and x.lower() not in seen and len(x) <= 60:
                seen.add(x.lower())
                out.append(x)

        for m in re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", text):
            add(m)
        for m in re.findall(r"\$\s?\d[\d,\.]*\s?(?:million|billion|trillion|M|B|K)?", text):
            add(m)
        for m in re.findall(r"\b\d+(?:\.\d+)?\s?%", text):
            add(m)
        for m in re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", text):
            if not re.match(r"^(The|This|That|These|Those|These|And|But|For|From|With)\b", m):
                add(m)
            if len(out) > 40:
                break
        return out
