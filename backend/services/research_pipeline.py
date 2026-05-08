"""Multi-source research pipeline (Manus-style fact-first).

Gathers verified facts from many free APIs IN PARALLEL before any LLM
generates content. The point is to give the writing model real numbers,
dates, names, and quotes so it cannot hallucinate them.

All sources are FREE and most need no API key. Failures degrade silently;
we always return a structured dict, never raise.

Public API:
    research_topic(topic, category, depth="deep") -> dict
    select_sources(topic, category) -> list[str]
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("nexus.services.research_pipeline")

_UA = {"User-Agent": "NexusAI/1.0 (research) httpx"}
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# ── cache ────────────────────────────────────────────────────────────────
_CACHE_DIR: Path = settings.STORAGE_DIR / "research_cache"
_CACHE_TTL_S = 24 * 3600


def _cache_key(topic: str, category: str) -> Path:
    h = hashlib.sha256(f"{category}::{topic.lower().strip()}".encode()).hexdigest()[:32]
    return _CACHE_DIR / f"{h}.json"


def _cache_get(topic: str, category: str) -> dict | None:
    try:
        p = _cache_key(topic, category)
        if not p.exists():
            return None
        if (time.time() - p.stat().st_mtime) > _CACHE_TTL_S:
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("research.cache_read_failed", extra={"err": str(exc)})
        return None


def _cache_put(topic: str, category: str, data: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_key(topic, category).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.debug("research.cache_write_failed", extra={"err": str(exc)})


# ── source selector (deterministic, keyword-based) ───────────────────────
_PERSON_RE = re.compile(
    r"^[A-Z][a-z]+ [A-Z][a-z]+(?: [A-Z][a-z]+)?$"
)  # "First Last" or "First Middle Last"
_COUNTRY_NAMES = {
    # Quick subset; missing ones fall through to wikipedia/wikidata anyway.
    "japan", "india", "china", "usa", "united states", "uk", "united kingdom",
    "france", "germany", "italy", "spain", "russia", "brazil", "canada",
    "australia", "mexico", "south africa", "egypt", "turkey", "argentina",
    "indonesia", "pakistan", "nigeria", "bangladesh", "vietnam", "thailand",
    "philippines", "iran", "iraq", "saudi arabia", "south korea", "north korea",
    "ukraine", "poland", "sri lanka", "nepal", "myanmar", "kenya", "ethiopia",
}
_TECH_KW = re.compile(
    r"\b(ai|artificial intelligence|machine learning|llm|gpt|blockchain|crypto|"
    r"software|cloud|kubernetes|devops|cyber|quantum|api|saas|web3|robotics|"
    r"react|vue|django|python|javascript|typescript|database|sql)\b",
    re.I,
)
_BUSINESS_KW = re.compile(
    r"\b(revenue|profit|earnings|q[1-4]\s?\d{2,4}|kpi|sales|pitch|investor|"
    r"startup|company|corporate|tesla|apple|google|microsoft|amazon|meta|"
    r"nvidia|openai|anthropic)\b",
    re.I,
)
_CURRENT_KW = re.compile(
    r"\b(202[4-9]|election|breaking|latest|news|recent|today|this year)\b", re.I
)
_BOOK_KW = re.compile(r"\b(book|novel|author|literature|poetry|memoir)\b", re.I)


def select_sources(topic: str, category: str) -> list[str]:
    """Return ordered list of source IDs that make sense for this topic."""
    t = (topic or "").strip().lower()
    cat = (category or "explainer").lower()
    sources: list[str] = []

    def add(*names: str) -> None:
        for n in names:
            if n not in sources:
                sources.append(n)

    # Always-good baseline.
    add("duckduckgo", "wikipedia")

    is_country = t in _COUNTRY_NAMES or any(c in t for c in _COUNTRY_NAMES)
    is_person = bool(_PERSON_RE.match(topic.strip())) and cat in (
        "history", "explainer", "research", "brand"
    )
    is_tech = bool(_TECH_KW.search(t))
    is_business = cat in ("pitch", "data", "brand") or bool(_BUSINESS_KW.search(t))
    is_current = bool(_CURRENT_KW.search(t))
    is_book = bool(_BOOK_KW.search(t))

    # Wikidata is cheap and useful for almost any noun-phrase topic.
    add("wikidata")
    if is_country:
        add("rest_countries", "open_meteo")
    if is_person:
        add("quotable")
    # Web-search + scraper for ANY non-trivial research category. Tavily
    # quietly falls back to DDG-HTML when no API key is configured, so we
    # always get *something* even on free tier.
    if cat in ("research", "explainer", "history", "data", "pitch", "brand", "tutorial") \
            or is_tech or is_business or is_current:
        add("tavily", "webpage_scraper")
    if is_book or cat == "research":
        add("openlibrary")

    return sources


# ── individual source fetchers ───────────────────────────────────────────
# Splits a multi-keyword prompt into candidate single-topic queries.
_TOPIC_SPLIT_RE = re.compile(r"\s*[\u00b7\u2022,;|/\u2013\u2014]+\s*|\s+(?:and|vs|versus)\s+", re.I)


def _split_topic(topic: str, *, max_parts: int = 4) -> list[str]:
    parts = [p.strip() for p in _TOPIC_SPLIT_RE.split(topic or "") if p.strip()]
    # De-dup, keep order, cap.
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        k = p.lower()
        if k not in seen and len(p) >= 3:
            seen.add(k)
            out.append(p)
        if len(out) >= max_parts:
            break
    return out


async def _wikipedia(client: httpx.AsyncClient, topic: str) -> dict:
    """Fetch Wikipedia data. If the full topic returns nothing useful,
    fan out across keyword splits (e.g. "AI · Brain · Neural networks") and
    aggregate the per-keyword summaries — this fixes empty-result cases for
    multi-topic prompts."""
    primary = await _wikipedia_one(client, topic)
    if primary.get("summary"):
        return primary

    parts = _split_topic(topic)
    if len(parts) <= 1:
        return primary

    sub_results = await asyncio.gather(
        *(_wikipedia_one(client, p) for p in parts), return_exceptions=True
    )
    summaries: list[str] = []
    sections: list[str] = []
    sub_pages: list[dict] = []
    for p, r in zip(parts, sub_results):
        if isinstance(r, Exception) or not r:
            continue
        if r.get("summary"):
            summaries.append(f"**{r.get('title') or p}**: {r['summary']}")
            sub_pages.append({
                "topic": p,
                "title": r.get("title") or p,
                "url": r.get("url") or "",
                "summary": r.get("summary") or "",
            })
        if r.get("sections"):
            sections.extend(r["sections"][:3])
    if not summaries:
        return primary
    return {
        "title": topic,
        "summary": "\n\n".join(summaries)[:4000],
        "sections": sections[:12],
        "url": "",
        "thumbnail": "",
        "description": "",
        "subtopics": sub_pages,
        "full_text": "\n\n".join(summaries)[:6000],
    }


async def _wikipedia_one(client: httpx.AsyncClient, topic: str) -> dict:
    title = topic.strip().replace(" ", "_")
    out: dict[str, Any] = {}
    try:
        r = await client.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
            headers=_UA,
        )
        if r.status_code == 200:
            j = r.json() or {}
            out.update({
                "summary": j.get("extract") or "",
                "title": j.get("title") or topic,
                "url": (j.get("content_urls") or {}).get("desktop", {}).get("page", ""),
                "thumbnail": (j.get("thumbnail") or {}).get("source", ""),
                "description": j.get("description") or "",
            })
    except Exception as exc:
        logger.debug("research.wikipedia_summary_failed", extra={"err": str(exc)})

    # Mobile-sections gives us section titles + lead text for richer context.
    try:
        r2 = await client.get(
            f"https://en.wikipedia.org/api/rest_v1/page/mobile-sections/{title}",
            headers=_UA,
        )
        if r2.status_code == 200:
            j2 = r2.json() or {}
            sections = []
            for s in (j2.get("remaining", {}).get("sections") or [])[:12]:
                line = (s.get("line") or "").strip()
                if line:
                    sections.append(line)
            lead_text = (j2.get("lead", {}).get("sections") or [{}])[0].get("text", "")
            # Strip HTML tags from lead text quickly.
            lead_clean = re.sub(r"<[^>]+>", " ", lead_text or "")
            lead_clean = re.sub(r"\s+", " ", lead_clean).strip()[:2000]
            if sections:
                out["sections"] = sections
            if lead_clean and not out.get("summary"):
                out["summary"] = lead_clean
            if lead_clean:
                out["full_text"] = lead_clean
    except Exception as exc:
        logger.debug("research.wikipedia_sections_failed", extra={"err": str(exc)})
    return out


async def _wikidata(client: httpx.AsyncClient, topic: str) -> dict:
    try:
        r = await client.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": topic,
                "language": "en",
                "format": "json",
                "limit": 1,
            },
            headers=_UA,
        )
        hits = (r.json() or {}).get("search") or []
        if not hits:
            return {}
        eid = hits[0].get("id")
        label = hits[0].get("label") or topic
        desc = hits[0].get("description") or ""
        if not eid:
            return {}
        # Pull entity claims (lightweight: labels + simple values).
        r2 = await client.get(
            "https://www.wikidata.org/w/api.php",
            params={"action": "wbgetentities", "ids": eid, "format": "json", "props": "claims"},
            headers=_UA,
        )
        ent = (r2.json() or {}).get("entities", {}).get(eid, {})
        claims = ent.get("claims") or {}
        # Map a few well-known property IDs to friendly names.
        prop_map = {
            "P569": "birth_date", "P570": "death_date",
            "P571": "founded", "P576": "dissolved",
            "P1082": "population", "P2046": "area_km2",
            "P36": "capital", "P38": "currency", "P37": "official_language",
            "P17": "country", "P625": "coordinates",
        }
        facts: dict[str, Any] = {}
        for pid, name in prop_map.items():
            if pid in claims and claims[pid]:
                try:
                    val = claims[pid][0]["mainsnak"]["datavalue"]["value"]
                    if isinstance(val, dict):
                        val = val.get("time") or val.get("amount") or val.get("id") or val
                    facts[name] = str(val).lstrip("+")[:80]
                except (KeyError, TypeError, IndexError):
                    pass
        return {"id": eid, "label": label, "description": desc, "facts": facts}
    except Exception as exc:
        logger.debug("research.wikidata_failed", extra={"err": str(exc)})
        return {}


async def _duckduckgo(client: httpx.AsyncClient, topic: str) -> dict:
    try:
        r = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": topic, "format": "json", "no_html": "1", "skip_disambig": "1"},
            headers=_UA,
        )
        j = r.json() or {}
        related = []
        for it in (j.get("RelatedTopics") or [])[:8]:
            if isinstance(it, dict) and it.get("Text"):
                related.append(it["Text"][:200])
        return {
            "abstract": j.get("AbstractText") or "",
            "abstract_url": j.get("AbstractURL") or "",
            "answer": j.get("Answer") or "",
            "definition": j.get("Definition") or "",
            "related": related,
        }
    except Exception as exc:
        logger.debug("research.duckduckgo_failed", extra={"err": str(exc)})
        return {}


async def _rest_countries(client: httpx.AsyncClient, topic: str) -> dict:
    try:
        r = await client.get(
            f"https://restcountries.com/v3.1/name/{topic}",
            headers=_UA,
        )
        if r.status_code != 200:
            return {}
        arr = r.json() or []
        if not arr:
            return {}
        c = arr[0]
        return {
            "name": (c.get("name") or {}).get("common", topic),
            "official": (c.get("name") or {}).get("official", ""),
            "capital": (c.get("capital") or [""])[0],
            "region": c.get("region") or "",
            "subregion": c.get("subregion") or "",
            "population": c.get("population") or 0,
            "area_km2": c.get("area") or 0,
            "languages": list((c.get("languages") or {}).values()),
            "currencies": list((c.get("currencies") or {}).keys()),
            "flag": (c.get("flags") or {}).get("png", ""),
            "lat_lng": c.get("latlng") or [],
            "borders": c.get("borders") or [],
            "timezones": (c.get("timezones") or [])[:5],
        }
    except Exception as exc:
        logger.debug("research.rest_countries_failed", extra={"err": str(exc)})
        return {}


async def _open_meteo(client: httpx.AsyncClient, topic: str) -> dict:
    try:
        r = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": topic, "count": 1, "language": "en", "format": "json"},
            headers=_UA,
        )
        results = (r.json() or {}).get("results") or []
        if not results:
            return {}
        loc = results[0]
        out = {
            "name": loc.get("name"),
            "country": loc.get("country"),
            "lat": loc.get("latitude"),
            "lon": loc.get("longitude"),
            "elevation_m": loc.get("elevation"),
            "timezone": loc.get("timezone"),
            "population": loc.get("population"),
        }
        # Also fetch current weather (lightweight, useful for context).
        try:
            r2 = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude"),
                    "current_weather": "true",
                },
                headers=_UA,
            )
            cw = (r2.json() or {}).get("current_weather") or {}
            if cw:
                out["weather"] = {
                    "temperature_c": cw.get("temperature"),
                    "windspeed_kmh": cw.get("windspeed"),
                    "time": cw.get("time"),
                }
        except Exception:
            pass
        return out
    except Exception as exc:
        logger.debug("research.open_meteo_failed", extra={"err": str(exc)})
        return {}


async def _quotable(client: httpx.AsyncClient, topic: str) -> dict:
    try:
        r = await client.get(
            "https://api.quotable.io/search/quotes",
            params={"query": topic, "limit": 5},
            headers=_UA,
        )
        j = r.json() or {}
        return {
            "quotes": [
                {"content": q.get("content", ""), "author": q.get("author", "")}
                for q in (j.get("results") or [])
                if q.get("content")
            ]
        }
    except Exception as exc:
        logger.debug("research.quotable_failed", extra={"err": str(exc)})
        return {}


async def _openlibrary(client: httpx.AsyncClient, topic: str) -> dict:
    try:
        r = await client.get(
            "https://openlibrary.org/search.json",
            params={"q": topic, "limit": 5},
            headers=_UA,
        )
        docs = (r.json() or {}).get("docs") or []
        return {
            "books": [
                {
                    "title": d.get("title", ""),
                    "author": (d.get("author_name") or [""])[0],
                    "year": d.get("first_publish_year"),
                    "cover_id": d.get("cover_i"),
                    "cover_url": (
                        f"https://covers.openlibrary.org/b/id/{d['cover_i']}-M.jpg"
                        if d.get("cover_i") else ""
                    ),
                }
                for d in docs[:5]
            ]
        }
    except Exception as exc:
        logger.debug("research.openlibrary_failed", extra={"err": str(exc)})
        return {}


async def _tavily_search(topic: str) -> dict:
    """Use existing SearchService when keys are present; else DDG-HTML fallback."""
    try:
        from services.search_service import SearchService
        svc = SearchService()
        summary, sources = await svc.search(topic, max_results=5)
        if sources:
            return {
                "summary": summary,
                "sources": sources,
                "search_urls": [s.get("url") for s in sources if s.get("url")],
            }
    except Exception as exc:
        logger.debug("research.tavily_failed", extra={"err": str(exc)})

    # Fallback: scrape DuckDuckGo HTML when no upstream keys/results.
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": topic},
                headers={**_UA, "Accept-Language": "en-US,en;q=0.9"},
            )
        if r.status_code != 200:
            return {}
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "lxml")
            results = []
            for res in soup.select(".result")[:10]:
                a = res.select_one("a.result__a")
                snippet_el = res.select_one(".result__snippet")
                if not a:
                    continue
                results.append({
                    "title": a.get_text(strip=True)[:200],
                    "url": a.get("href") or "",
                    "snippet": snippet_el.get_text(" ", strip=True)[:300] if snippet_el else "",
                })
            return {
                "summary": "",
                "sources": results,
                "search_urls": [r["url"] for r in results if r.get("url")],
            }
        except Exception:
            return {}
    except Exception as exc:
        logger.debug("research.ddg_html_failed", extra={"err": str(exc)})
        return {}


async def _webpage_scraper(client: httpx.AsyncClient, urls: list[str]) -> list[dict]:
    """Fetch top URLs and extract clean main text (~3KB each)."""
    if not urls:
        return []

    async def _one(u: str) -> dict:
        try:
            r = await client.get(u, headers=_UA, follow_redirects=True)
            if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
                return {}
            return {"url": u, "title": _extract_title(r.text), "text": _clean_html(r.text)}
        except Exception as exc:
            logger.debug("research.scrape_failed", extra={"url": u[:80], "err": str(exc)})
            return {}

    out = await asyncio.gather(*(_one(u) for u in urls[:3]))
    return [p for p in out if p]


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    return (m.group(1).strip()[:200]) if m else ""


def _clean_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for t in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
            t.decompose()
        root = soup.find("article") or soup.find("main") or soup.body or soup
        text = root.get_text(" ", strip=True) if root else ""
    except Exception:
        text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:3000]


# ── orchestrator ──────────────────────────────────────────────────────────
async def research_topic(
    topic: str,
    category: str,
    depth: str = "deep",
) -> dict:
    """Run the full multi-source research pipeline. Returns structured dict."""
    topic = (topic or "").strip()
    if not topic:
        return _empty_result(topic, category)

    # Cache check.
    cached = _cache_get(topic, category)
    if cached:
        cached["_from_cache"] = True
        return cached

    sources_to_use = select_sources(topic, category)
    logger.info(
        "research.start",
        extra={"topic": topic[:80], "category": category, "sources": sources_to_use},
    )

    sources_used: list[str] = []
    payload: dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        coro_map: dict[str, Any] = {}
        if "wikipedia" in sources_to_use:
            coro_map["wikipedia"] = _wikipedia(client, topic)
        if "wikidata" in sources_to_use:
            coro_map["wikidata"] = _wikidata(client, topic)
        if "duckduckgo" in sources_to_use:
            coro_map["duckduckgo"] = _duckduckgo(client, topic)
        if "rest_countries" in sources_to_use:
            coro_map["rest_countries"] = _rest_countries(client, topic)
        if "open_meteo" in sources_to_use:
            coro_map["open_meteo"] = _open_meteo(client, topic)
        if "quotable" in sources_to_use:
            coro_map["quotable"] = _quotable(client, topic)
        if "openlibrary" in sources_to_use:
            coro_map["openlibrary"] = _openlibrary(client, topic)
        if "tavily" in sources_to_use:
            coro_map["tavily"] = _tavily_search(topic)

        if coro_map:
            results = await asyncio.gather(*coro_map.values(), return_exceptions=True)
            for name, res in zip(coro_map.keys(), results):
                if isinstance(res, Exception) or not res:
                    continue
                payload[name] = res
                sources_used.append(name)

        # Webpage scraper runs after tavily so it can use those URLs.
        if "webpage_scraper" in sources_to_use and depth == "deep":
            urls: list[str] = []
            tav_payload = payload.get("tavily") or {}
            for u in (tav_payload.get("search_urls") or []):
                if u and u not in urls:
                    urls.append(u)
            for s in tav_payload.get("sources", []):
                u = s.get("url") if isinstance(s, dict) else None
                if u and u not in urls:
                    urls.append(u)
            wiki_url = (payload.get("wikipedia") or {}).get("url")
            if wiki_url and wiki_url not in urls:
                urls.append(wiki_url)
            scraped = await _webpage_scraper(client, urls)
            if scraped:
                payload["webpage_scraper"] = scraped
                sources_used.append("webpage_scraper")

    result = _normalize_research(topic, category, payload, sources_used)
    _cache_put(topic, category, result)
    return result


def _empty_result(topic: str, category: str) -> dict:
    return {
        "topic": topic, "category": category, "sources_used": [],
        "summary": "", "key_facts": [], "timeline": [], "statistics": {},
        "key_people": [], "key_quotes": [], "related_topics": [],
        "web_content": [], "images_context": [], "raw": {},
    }


def _normalize_research(
    topic: str, category: str, payload: dict, sources_used: list[str]
) -> dict:
    """Combine raw source dicts into the unified schema."""
    res = _empty_result(topic, category)
    res["sources_used"] = sources_used
    res["raw"] = payload

    # Summary: prefer wikipedia, then duckduckgo abstract, then tavily summary.
    wiki = payload.get("wikipedia") or {}
    ddg = payload.get("duckduckgo") or {}
    tav = payload.get("tavily") or {}
    res["summary"] = (
        wiki.get("summary")
        or ddg.get("abstract")
        or ddg.get("definition")
        or tav.get("summary")
        or ""
    )[:2000]

    # Key facts from wikidata + structured sources.
    facts: list[dict] = []
    wd_facts = (payload.get("wikidata") or {}).get("facts") or {}
    for k, v in wd_facts.items():
        facts.append({"fact": f"{k.replace('_',' ').title()}: {v}",
                      "source": "wikidata", "type": k})
    rc = payload.get("rest_countries") or {}
    if rc:
        if rc.get("population"):
            facts.append({"fact": f"Population: {rc['population']:,}",
                          "source": "rest_countries", "type": "population"})
        if rc.get("area_km2"):
            facts.append({"fact": f"Area: {rc['area_km2']:,} km²",
                          "source": "rest_countries", "type": "area"})
        if rc.get("capital"):
            facts.append({"fact": f"Capital: {rc['capital']}",
                          "source": "rest_countries", "type": "capital"})
        if rc.get("languages"):
            facts.append({"fact": f"Languages: {', '.join(rc['languages'][:3])}",
                          "source": "rest_countries", "type": "language"})
    om = payload.get("open_meteo") or {}
    if om and om.get("population"):
        facts.append({"fact": f"City population: {om['population']:,}",
                      "source": "open_meteo", "type": "population"})
    res["key_facts"] = facts

    # Statistics dict (machine-readable).
    stats: dict[str, Any] = {}
    if rc.get("population"):
        stats["population"] = rc["population"]
    if rc.get("area_km2"):
        stats["area_km2"] = rc["area_km2"]
    for k in ("birth_date", "death_date", "founded", "dissolved"):
        if wd_facts.get(k):
            stats[k] = wd_facts[k]
    res["statistics"] = stats

    # Timeline: pull dates from wikidata + scraped text.
    timeline: list[dict] = []
    for k in ("founded", "birth_date", "dissolved", "death_date"):
        v = wd_facts.get(k)
        if v:
            timeline.append({"date": v[:10], "event": k.replace("_", " ").title()})
    # Heuristic: pull "year — phrase" lines from scraped text.
    for page in (payload.get("webpage_scraper") or [])[:3]:
        for m in re.finditer(r"\b(1[5-9]\d{2}|20\d{2})\b([^.]{5,120})\.", page.get("text", "")):
            timeline.append({"date": m.group(1), "event": m.group(2).strip(" -—–:")[:120]})
            if len(timeline) >= 12:
                break
        if len(timeline) >= 12:
            break
    res["timeline"] = timeline[:12]

    # Key people: capitalized 2-word phrases in summary + scraped text.
    people: list[str] = []
    seen_p: set[str] = set()
    text_blob = res["summary"] + " " + " ".join(
        p.get("text", "") for p in (payload.get("webpage_scraper") or [])
    )
    for m in re.findall(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text_blob):
        if m.lower() in seen_p:
            continue
        if any(w in m for w in ("The", "And", "From", "With", "This", "That", "These")):
            continue
        seen_p.add(m.lower())
        people.append(m)
        if len(people) >= 10:
            break
    res["key_people"] = people

    # Quotes.
    res["key_quotes"] = (payload.get("quotable") or {}).get("quotes", [])[:5]

    # Related topics.
    res["related_topics"] = (ddg.get("related") or [])[:6]

    # Web content (scraped pages).
    res["web_content"] = [
        {"url": p.get("url", ""), "title": p.get("title", ""),
         "text": (p.get("text") or "")[:3000]}
        for p in (payload.get("webpage_scraper") or [])
    ]

    # Image search hints.
    img_hints: list[str] = []
    if wiki.get("title"):
        img_hints.append(wiki["title"])
    img_hints.extend(people[:3])
    img_hints.extend(res["related_topics"][:3])
    if rc.get("capital"):
        img_hints.append(rc["capital"])
    res["images_context"] = list(dict.fromkeys(img_hints))[:8]

    return res


# ── LLM-friendly context formatter ────────────────────────────────────────
def format_research_for_prompt(research: dict) -> str:
    """Produce a markdown context block to feed into an LLM prompt."""
    if not research or not research.get("sources_used"):
        return ""
    out: list[str] = []
    out.append(f"# VERIFIED RESEARCH for: {research.get('topic','')}")
    out.append(f"_Sources used: {', '.join(research.get('sources_used', []))}_")
    out.append("")
    if research.get("summary"):
        out.append("## Summary")
        out.append(research["summary"])
        out.append("")
    if research.get("key_facts"):
        out.append("## Verified Facts (use exactly, do not invent)")
        for f in research["key_facts"][:20]:
            out.append(f"- {f['fact']}  _[{f['source']}]_")
        out.append("")
    if research.get("timeline"):
        out.append("## Timeline (verified dates)")
        for t in research["timeline"][:12]:
            out.append(f"- **{t['date']}** — {t['event']}")
        out.append("")
    if research.get("key_people"):
        out.append("## Key People")
        out.append(", ".join(research["key_people"][:10]))
        out.append("")
    if research.get("key_quotes"):
        out.append("## Quotes")
        for q in research["key_quotes"][:3]:
            out.append(f'> "{q.get("content","")}" — {q.get("author","")}')
        out.append("")
    if research.get("related_topics"):
        out.append("## Related")
        out.append("; ".join(research["related_topics"][:5]))
        out.append("")
    if research.get("web_content"):
        out.append("## Article excerpts")
        for w in research["web_content"][:3]:
            out.append(f"### {w.get('title','')}")
            out.append((w.get("text") or "")[:1500])
            out.append("")
    out.append("**Strict rule:** Use ONLY the facts above. Do not invent dates, "
               "numbers, names, or quotes that are not in this research block.")
    return "\n".join(out)
