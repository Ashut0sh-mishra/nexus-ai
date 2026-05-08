"""Image recommendation: stock-API search (Unsplash + Pexels) with
Pollinations AI fallback.

The agent loop calls ``recommend_images(slide, *, topic)`` for each slide that
benefits from a visual. The result is a dict the slide-row mapper feeds into
``image_data_json``::

    {
        "url":       "https://...",
        "alt":       "Brief alt text",
        "source":    "unsplash" | "pexels" | "pollinations" | "ai",
        "credit":    {"author": "Jane Doe", "url": "https://..."}  # stock only
        "placement": "background" | "side" | "icon" | "atmospheric",
        "width":     1280,
        "height":    720,
        "prompt":    "<the descriptive prompt used>",
    }

Stock-API calls are gated on env keys; if neither is set, the loop falls
back to Pollinations using the recommended prompt.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from config import settings

logger = logging.getLogger("nexus.services.image")

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
UNSPLASH_API = "https://api.unsplash.com/search/photos"
PEXELS_API = "https://api.pexels.com/v1/search"


# Per-slide-layout rules: which placement, what prompt style.
_LAYOUT_RULES: dict[str, dict[str, Any]] = {
    "title": {
        "placement": "background",
        "modifier": "cinematic hero shot, soft gradient, no text, editorial",
        "width": 1920,
        "height": 1080,
    },
    "section": {
        "placement": "atmospheric",
        "modifier": "abstract atmospheric scene, soft tones, no text",
        "width": 1920,
        "height": 1080,
    },
    "bullets": {
        "placement": "side",
        "modifier": "minimalist editorial illustration, no text, soft palette",
        "width": 800,
        "height": 600,
    },
    "two-col": {
        "placement": "icon",
        "modifier": "two complementary illustrations side by side, no text",
        "width": 800,
        "height": 600,
    },
    "image-focus": {
        "placement": "background",
        "modifier": "stunning editorial photograph, no text, magazine quality",
        "width": 1600,
        "height": 900,
    },
    "closing": {
        "placement": "background",
        "modifier": "warm closing scene, soft gradient, no text",
        "width": 1920,
        "height": 1080,
    },
    "timeline": {
        "placement": "atmospheric",
        "modifier": "panoramic timeline backdrop, no text, abstract",
        "width": 1600,
        "height": 600,
    },
}

# Layouts that are already centerpiece compositions — skip visuals.
_SKIP_LAYOUTS = {"chart", "stats", "kpi", "kpi_grid", "table", "quote"}


# PRD §3 — image category classification. Each category has a prompt-style
# modifier and a recommended placement that the renderer can honor.
_CATEGORY_MODIFIERS: dict[str, str] = {
    "hero":         "cinematic editorial photograph, dramatic lighting, no text",
    "industry":     "industry-specific business scene, professional photograph, no text",
    "mockup":       "clean product mockup on neutral background, no text",
    "illustration": "minimalist editorial illustration, soft palette, no text",
    "icon":         "simple flat vector icon, single concept, no text",
    "background":   "abstract atmospheric background, soft gradient, no text",
    "conceptual":   "conceptual visual metaphor, editorial style, no text",
    "infographic":  "clean infographic-style diagram, minimal labels",
    "team":         "diverse team portrait illustration, warm palette, no text",
    "map":          "stylized world map illustration, muted tones, no text",
    "diagram":      "simple architectural diagram, line art, no text",
}

# Keyword → category. First hit wins.
_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("map",          ["map", "geography", "global", "country", "region", "continent"]),
    ("team",         ["team", "people", "employee", "staff", "founder", "leadership", "diversity"]),
    ("mockup",       ["product", "mockup", "device", "screen", "interface", "ui", "ux", "app", "dashboard"]),
    ("infographic",  ["infographic", "process", "workflow", "pipeline", "framework", "stages"]),
    ("diagram",      ["architecture", "system", "diagram", "flow", "schematic"]),
    ("industry",     ["finance", "fintech", "healthcare", "manufacturing", "retail", "logistics", "energy", "agriculture"]),
    ("conceptual",   ["strategy", "vision", "concept", "future", "growth", "innovation"]),
    ("illustration", ["story", "journey", "narrative", "approach"]),
]


def classify_image_category(slide: dict[str, Any], topic: str | None = None) -> str:
    """PRD §3 — decide what KIND of image best fits this slide.

    Returns one of ``_CATEGORY_MODIFIERS`` keys. Uses the slide layout as a
    primary signal, then keyword-matches title + bullets.
    """
    layout = str(slide.get("layout") or "").strip().lower()
    if layout == "title":
        return "hero"
    if layout == "section":
        return "background"
    if layout == "image-focus":
        return "hero"
    if layout == "closing":
        return "background"
    if layout == "timeline":
        return "infographic"
    if layout == "comparison":
        return "conceptual"

    haystack = " ".join(
        [
            str(slide.get("title") or ""),
            str(slide.get("subtitle") or ""),
            " ".join(str(b) for b in (slide.get("bullets") or [])),
            str(topic or ""),
        ]
    ).lower()

    for category, words in _CATEGORY_KEYWORDS:
        if any(w in haystack for w in words):
            return category

    # Default for content-heavy slides.
    return "illustration"


# ── public ──────────────────────────────────────────────────────────────────
def _slugify_prompt(prompt: str) -> str:
    cleaned = re.sub(r"\s+", " ", prompt or "").strip()
    return cleaned[:200] if cleaned else "abstract gradient background"


def pollinations_url(
    prompt: str,
    *,
    width: int = 1280,
    height: int = 720,
    seed: int | None = None,
) -> str:
    """Return a Pollinations image URL. Stable for a given (prompt, seed)."""
    encoded = quote(_slugify_prompt(prompt), safe="")
    qs = [f"width={width}", f"height={height}", "nologo=true", "model=flux"]
    if seed is not None:
        qs.append(f"seed={seed}")
    return f"{POLLINATIONS_BASE}/{encoded}?{'&'.join(qs)}"


def should_have_image(layout: str | None) -> bool:
    """Return True when a slide of this layout benefits from a visual."""
    return bool(layout) and layout not in _SKIP_LAYOUTS


def should_have_image_for_profile(
    layout: str | None,
    profile: dict[str, Any] | None = None,
) -> bool:
    """Layout filter + topic-category gate.

    Mirrors Manus's behavior observed in the analyzed decks:
    history / research decks ship with ZERO photographic heroes; tutorials
    prefer diagrams; data decks rely on chart canvases only; pitch / brand
    decks lean on cinematic heroes.
    """
    if not should_have_image(layout):
        return False
    if not profile:
        return True
    strategy = str(profile.get("image_strategy") or "hero").lower()
    if strategy == "none":
        return False
    if strategy == "chart-only":
        # Data decks: only allow images on title / closing / image-focus.
        return str(layout).lower() in {"title", "closing", "image-focus"}
    if strategy == "optional":
        # Sparing imagery for research/history: hero positions only.
        return str(layout).lower() in {"title", "closing", "image-focus", "hero", "section"}
    return True


def build_prompt(slide: dict[str, Any], topic: str | None = None) -> str:
    """Compose a visual prompt from a slide payload.

    Honors any explicit ``slide["image_prompt"]`` first, then falls back to
    ``title`` + the category-specific modifier (PRD §3 image classification).
    """
    explicit = str(slide.get("image_prompt") or "").strip()
    category = classify_image_category(slide, topic)
    cat_modifier = _CATEGORY_MODIFIERS.get(category, "")
    layout = str(slide.get("layout") or "").strip().lower()
    rules = _LAYOUT_RULES.get(layout, _LAYOUT_RULES["bullets"])
    layout_modifier = rules["modifier"]
    # Prefer the more specific category modifier; fall back to layout.
    modifier = cat_modifier or layout_modifier
    if explicit:
        return f"{explicit}, {modifier}"
    title = str(slide.get("title") or topic or "").strip() or "abstract concept"
    return f"{title}, {modifier}"


async def search_stock_images(
    query: str,
    *,
    count: int = 1,
    orientation: str = "landscape",
) -> list[dict[str, Any]]:
    """Search Unsplash first, fall back to Pexels. Returns up to ``count`` hits.

    Each hit::

        {"url", "thumb", "alt", "source", "width", "height",
         "credit": {"author", "author_url", "page_url"}}

    Returns ``[]`` when neither key is set or both providers fail.
    """
    if not query:
        return []
    results: list[dict[str, Any]] = []
    if settings.UNSPLASH_ACCESS_KEY:
        try:
            results = await _search_unsplash(query, count, orientation)
        except Exception as exc:
            logger.warning("image.unsplash_failed", extra={"err": str(exc)})
    if not results and settings.PEXELS_API_KEY:
        try:
            results = await _search_pexels(query, count, orientation)
        except Exception as exc:
            logger.warning("image.pexels_failed", extra={"err": str(exc)})
    return results[:count]


async def recommend_images(
    slide: dict[str, Any],
    *,
    topic: str | None = None,
    seed: int | None = None,
    images_context: list[str] | None = None,
) -> dict[str, Any] | None:
    """Pick one image for the slide following layout-specific rules.

    Order of preference:
    1. Stock-API hit (Unsplash → Pexels) when either key is configured.
    2. Pollinations AI image with a layout-tuned prompt.

    ``images_context`` is an optional list of research-derived hints
    (people, capitals, related topics) that get folded into the search
    query so we hit specific real subjects instead of generic stock.

    Returns ``None`` when the layout shouldn't carry a visual.
    """
    layout = str(slide.get("layout") or "").strip().lower()
    if not should_have_image(layout):
        return None

    rules = _LAYOUT_RULES.get(layout, _LAYOUT_RULES["bullets"])
    width = int(rules.get("width") or 1280)
    height = int(rules.get("height") or 720)
    placement = str(rules.get("placement") or "background")
    prompt = build_prompt(slide, topic)
    # Fold first research hint into the prompt for higher-relevance image hits.
    if images_context:
        title = (slide.get("title") or "").lower()
        # Pick the hint most likely to match this slide.
        hint = next(
            (h for h in images_context if h and h.lower() not in title and len(h) > 2),
            None,
        )
        if hint:
            prompt = f"{hint}, {prompt}" if prompt else hint
    category = classify_image_category(slide, topic)
    query = str(slide.get("title") or topic or "abstract").strip() or "abstract"

    # 1. Stock APIs (only if a key is present).
    if settings.UNSPLASH_ACCESS_KEY or settings.PEXELS_API_KEY:
        hits = await search_stock_images(query, count=1, orientation="landscape")
        if hits:
            h = hits[0]
            return {
                "url": h["url"],
                "alt": h.get("alt") or query,
                "source": h.get("source") or "stock",
                "credit": h.get("credit"),
                "placement": placement,
                "category": category,
                "width": h.get("width") or width,
                "height": h.get("height") or height,
                "prompt": prompt,
            }

    # 2. Pollinations fallback.
    return {
        "url": pollinations_url(prompt, width=width, height=height, seed=seed),
        "alt": str(slide.get("title") or topic or "Slide visual"),
        "source": "pollinations",
        "credit": None,
        "placement": placement,
        "category": category,
        "width": width,
        "height": height,
        "prompt": prompt,
    }


# ── internals ───────────────────────────────────────────────────────────────
async def _search_unsplash(
    query: str, count: int, orientation: str
) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Client-ID {settings.UNSPLASH_ACCESS_KEY}"}
    params = {
        "query": query,
        "per_page": max(1, min(count, 5)),
        "orientation": orientation,
        "content_filter": "high",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(UNSPLASH_API, params=params, headers=headers)
        r.raise_for_status()
        payload = r.json()
    out: list[dict[str, Any]] = []
    for item in payload.get("results") or []:
        urls = item.get("urls") or {}
        user = item.get("user") or {}
        out.append(
            {
                "url": urls.get("regular") or urls.get("full") or urls.get("small"),
                "thumb": urls.get("thumb"),
                "alt": item.get("alt_description") or item.get("description") or query,
                "source": "unsplash",
                "width": item.get("width"),
                "height": item.get("height"),
                "credit": {
                    "author": user.get("name") or user.get("username"),
                    "author_url": (user.get("links") or {}).get("html"),
                    "page_url": (item.get("links") or {}).get("html"),
                },
            }
        )
    return out


async def _search_pexels(
    query: str, count: int, orientation: str
) -> list[dict[str, Any]]:
    headers = {"Authorization": settings.PEXELS_API_KEY}
    params = {
        "query": query,
        "per_page": max(1, min(count, 5)),
        "orientation": orientation,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(PEXELS_API, params=params, headers=headers)
        r.raise_for_status()
        payload = r.json()
    out: list[dict[str, Any]] = []
    for item in payload.get("photos") or []:
        sizes = item.get("src") or {}
        out.append(
            {
                "url": sizes.get("large") or sizes.get("original") or sizes.get("medium"),
                "thumb": sizes.get("small") or sizes.get("tiny"),
                "alt": item.get("alt") or query,
                "source": "pexels",
                "width": item.get("width"),
                "height": item.get("height"),
                "credit": {
                    "author": item.get("photographer"),
                    "author_url": item.get("photographer_url"),
                    "page_url": item.get("url"),
                },
            }
        )
    return out
