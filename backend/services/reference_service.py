"""Presentation-design reference service.

Two complementary inspiration sources:

1. **Local reference index** \u2014 reads the `*.analysis.json` files produced
   by `tools/analyze_manus_decks.py` against the Manus sample decks under
   `manus-reference/sample-decks/`. Provides per-category recommended
   layouts, palettes, font pairs, words/slide and image frequency.

2. **SlideShare scraper** (best-effort, no API key) \u2014 searches public
   SlideShare cards by topic and returns lightweight metadata
   (`title, author, url, slide_count, thumbnail`). Each scraped deck can
   be drilled-down for its slide thumbnails / titles. Cached on disk for
   24 h. Fails silently to an empty list \u2014 the planner keeps working.

Hard rule: **layout/structure inspiration only**. We extract the *shape*
of professional decks (slide-type sequence, slide count, words/slide,
image cadence) and bias the planner with it. We never copy the textual
content of any scraped deck.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from config import PROJECT_ROOT, settings


logger = logging.getLogger("nexus.reference_service")


# ---------------------------------------------------------------------------
# Local reference loading
# ---------------------------------------------------------------------------

_LOCAL_DIR = PROJECT_ROOT / "manus-reference" / "sample-decks"
_CACHE_DIR: Path = settings.STORAGE_DIR / "research_cache"
_CACHE_TTL_S = 24 * 3600

# In-memory index: filename \u2192 analysis dict (loaded once at startup).
_LOCAL_INDEX: dict[str, dict[str, Any]] = {}
# Filename \u2192 inferred category (history/data/tutorial/pitch/explainer/research/brand).
_FILE_CATEGORY: dict[str, str] = {}


# Mapping rules from filename keywords to category. Kept here so the loader
# does not depend on `topic_classifier` at import time.
_FILENAME_CATEGORY_HINTS: list[tuple[str, str]] = [
    ("rome", "history"),
    ("history", "history"),
    ("empire", "history"),
    ("srilanka", "history"),
    ("data-q", "data"),
    ("quarterly", "data"),
    ("kpi", "data"),
    ("django", "tutorial"),
    ("howto", "tutorial"),
    ("tutorial", "tutorial"),
    ("pulsefit", "pitch"),
    ("pitch", "pitch"),
    ("photosynthesis", "explainer"),
    ("explainer", "explainer"),
    ("comparison", "explainer"),
    ("brand", "brand"),
    ("research", "research"),
]


def _infer_category(filename: str) -> str:
    name = filename.lower()
    for hint, cat in _FILENAME_CATEGORY_HINTS:
        if hint in name:
            return cat
    return "explainer"


def load_local_references() -> int:
    """Load every `*.analysis.json` under `manus-reference/sample-decks/`.

    Returns the number of decks indexed. Safe to call multiple times \u2014
    re-loads from disk so admins can drop in new analyses without a
    backend restart.
    """
    _LOCAL_INDEX.clear()
    _FILE_CATEGORY.clear()

    if not _LOCAL_DIR.exists():
        logger.warning("reference.local_dir_missing", extra={"path": str(_LOCAL_DIR)})
        return 0

    count = 0
    for path in _LOCAL_DIR.rglob("*.analysis.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "reference.load_failed",
                extra={"file": path.name, "err": str(exc)},
            )
            continue
        _LOCAL_INDEX[path.name] = data
        _FILE_CATEGORY[path.name] = _infer_category(path.name)
        count += 1

    logger.info("reference.local_loaded", extra={"count": count})
    return count


# ---------------------------------------------------------------------------
# Layout-pattern extraction
# ---------------------------------------------------------------------------

def extract_layout_patterns(analysis: dict[str, Any]) -> list[str]:
    """Return the ordered layout sequence inferred from one analysis dict.

    The analyzer emits per-slide records under the key `slides` with a
    `layout` field. Falls back to inspecting `layouts` (a Counter dict)
    when no per-slide info exists.
    """
    slides = analysis.get("slides")
    if isinstance(slides, list):
        return [
            str(s.get("layout") or "bullets").strip().lower()
            for s in slides
            if isinstance(s, dict)
        ]
    layouts = analysis.get("layouts") or {}
    if isinstance(layouts, dict):
        # Best-effort: flatten Counter-shaped dict back into a sequence.
        return [k for k, n in layouts.items() for _ in range(int(n))]
    return []


def get_reference_for_topic(category: str) -> dict[str, Any]:
    """Aggregate local references for a category into planner-ready hints.

    Returns a dict with:
      - `recommended_layouts`: ordered layout sequence (median deck length)
      - `palette`: top 3 hex colors across decks
      - `font_pairs`: top heading/body font pairs across decks
      - `words_per_slide`: average across decks
      - `image_freq`: 0\u20131.0 fraction of slides with an image
      - `slide_type_distribution`: counter of layouts
      - `sample_count`: how many decks contributed
    """
    matches = [
        analysis
        for fname, analysis in _LOCAL_INDEX.items()
        if _FILE_CATEGORY.get(fname) == category
    ] or list(_LOCAL_INDEX.values())  # fall back to ALL decks if none match

    if not matches:
        return {
            "recommended_layouts": [],
            "palette": [],
            "font_pairs": [],
            "words_per_slide": 0.0,
            "image_freq": 0.0,
            "slide_type_distribution": {},
            "sample_count": 0,
        }

    # Layouts
    layout_seqs = [extract_layout_patterns(a) for a in matches]
    flat_layouts = [layout for seq in layout_seqs for layout in seq]
    layout_counter: Counter[str] = Counter(flat_layouts)

    # Pick the median-length sequence as a representative ordering.
    layout_seqs_sorted = sorted(layout_seqs, key=len)
    recommended = layout_seqs_sorted[len(layout_seqs_sorted) // 2] if layout_seqs_sorted else []

    # Palette
    color_counter: Counter[str] = Counter()
    for a in matches:
        for hex_color, n in (a.get("top_colors") or [])[:5]:
            color_counter[str(hex_color).upper()] += int(n)
    palette = [c for c, _ in color_counter.most_common(3)]

    # Fonts
    font_counter: Counter[str] = Counter()
    for a in matches:
        for font, n in (a.get("top_fonts") or [])[:5]:
            font_counter[str(font)] += int(n)
    font_pairs = [f for f, _ in font_counter.most_common(2)]

    # Words / images
    words_avg = sum(float(a.get("avg_words") or 0) for a in matches) / len(matches)
    image_freq = 0.0
    for a in matches:
        slides = a.get("slides")
        if isinstance(slides, list) and slides:
            with_img = sum(1 for s in slides if isinstance(s, dict) and s.get("has_image"))
            image_freq += with_img / len(slides)
    image_freq = image_freq / len(matches) if matches else 0.0

    return {
        "recommended_layouts": recommended,
        "palette": palette,
        "font_pairs": font_pairs,
        "words_per_slide": round(words_avg, 1),
        "image_freq": round(image_freq, 2),
        "slide_type_distribution": dict(layout_counter.most_common(10)),
        "sample_count": len(matches),
    }


# ---------------------------------------------------------------------------
# SlideShare scraper (best-effort, public HTML, no API key)
# ---------------------------------------------------------------------------

_SLIDESHARE_BASE = "https://www.slideshare.net"
_SS_SEARCH = _SLIDESHARE_BASE + "/search?q={q}"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _cache_path(key: str) -> Path:
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return _CACHE_DIR / f"slideshare_{h}.json"


def _cache_get(key: str) -> dict | list | None:
    try:
        p = _cache_path(key)
        if not p.exists():
            return None
        if (time.time() - p.stat().st_mtime) > _CACHE_TTL_S:
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.debug("reference.cache_read_failed", extra={"err": str(exc)})
        return None


def _cache_put(key: str, data: dict | list) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(key).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("reference.cache_write_failed", extra={"err": str(exc)})


_INT_RE = re.compile(r"\d+")


async def search_slideshare(topic: str, limit: int = 3) -> list[dict[str, Any]]:
    """Search SlideShare for decks matching `topic`. Returns up to `limit`
    cards. Cached for 24 h. Returns `[]` on any failure.
    """
    topic = (topic or "").strip()
    if not topic:
        return []
    cache_key = f"search::{topic.lower()}::{limit}"
    cached = _cache_get(cache_key)
    if isinstance(cached, list):
        return cached

    url = _SS_SEARCH.format(q=quote_plus(topic))
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.8"},
            follow_redirects=True,
        ) as client:
            r = await client.get(url)
            if r.status_code != 200:
                logger.info(
                    "reference.slideshare_search_status",
                    extra={"status": r.status_code, "topic": topic},
                )
                return []
            html = r.text
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "reference.slideshare_search_failed",
            extra={"err": str(exc), "topic": topic},
        )
        return []

    cards = _parse_slideshare_search(html, limit=limit)
    _cache_put(cache_key, cards)
    return cards


def _parse_slideshare_search(html: str, *, limit: int) -> list[dict[str, Any]]:
    """Pull deck cards out of a SlideShare search page. SlideShare's
    markup changes; we look for anchors whose href matches the slideshow
    URL pattern (`/slideshow/<slug>/<id>`) and gather adjacent text.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    cards: list[dict[str, Any]] = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/slideshow/" not in href:
            continue
        full = href if href.startswith("http") else _SLIDESHARE_BASE + href
        if full in seen:
            continue
        title = (a.get_text() or "").strip()
        # Many cards render the title as an aria-label on the link.
        if not title:
            title = (a.get("aria-label") or a.get("title") or "").strip()
        if not title or len(title) < 6:
            continue
        seen.add(full)

        # Try to find a thumbnail and slide count near the anchor.
        thumb = ""
        img = a.find("img")
        if img and img.get("src"):
            thumb = img["src"]

        slide_count = 0
        # SlideShare often shows "32 slides" near the card.
        nearby = a.find_parent()
        if nearby is not None:
            text = nearby.get_text(" ", strip=True).lower()
            m = re.search(r"(\d{1,3})\s+slides", text)
            if m:
                slide_count = int(m.group(1))

        cards.append(
            {
                "title": title[:160],
                "url": full,
                "thumbnail": thumb,
                "slide_count": slide_count,
                "author": "",  # SlideShare requires a follow-up fetch
            }
        )
        if len(cards) >= limit:
            break

    return cards


async def scrape_slideshare_deck(deck_url: str) -> dict[str, Any]:
    """Fetch a single SlideShare deck page and extract slide thumbnails +
    titles. Returns ``{}`` on failure. Cached for 24 h.
    """
    deck_url = (deck_url or "").strip()
    if not deck_url:
        return {}

    cache_key = f"deck::{deck_url}"
    cached = _cache_get(cache_key)
    if isinstance(cached, dict):
        return cached

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.8"},
            follow_redirects=True,
        ) as client:
            r = await client.get(deck_url)
            if r.status_code != 200:
                return {}
            html = r.text
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "reference.slideshare_deck_failed",
            extra={"err": str(exc), "url": deck_url},
        )
        return {}

    soup = BeautifulSoup(html, "html.parser")
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    author = ""
    author_link = soup.find("a", attrs={"data-cy": "user-name"}) or soup.find("a", class_=re.compile("author"))
    if author_link:
        author = author_link.get_text(strip=True)

    slides: list[dict[str, str]] = []
    for img in soup.find_all("img"):
        src = img.get("data-full") or img.get("data-src") or img.get("src") or ""
        if not src:
            continue
        if "slidesharecdn" not in src:
            continue
        slides.append({"thumbnail": src, "alt": (img.get("alt") or "").strip()})
        if len(slides) >= 60:
            break

    payload = {
        "url": deck_url,
        "title": title[:200],
        "author": author[:100],
        "slide_count": len(slides),
        "slides": slides,
    }
    _cache_put(cache_key, payload)
    return payload


# ---------------------------------------------------------------------------
# Combined design inspiration (planner-facing API)
# ---------------------------------------------------------------------------

async def get_design_inspiration(topic: str, category: str) -> dict[str, Any]:
    """Return both local reference patterns and (best-effort) SlideShare
    examples for `topic`. The planner consumes this to bias layout choice
    and slide count \u2014 not text content.
    """
    local = get_reference_for_topic(category)

    try:
        slideshare = await asyncio.wait_for(search_slideshare(topic, limit=3), timeout=18.0)
    except asyncio.TimeoutError:
        slideshare = []
    except Exception as exc:  # noqa: BLE001
        logger.info("reference.slideshare_inspiration_failed", extra={"err": str(exc)})
        slideshare = []

    # Recommended slide count: blend local median with scraped average.
    local_count = len(local.get("recommended_layouts") or [])
    scraped_counts = [int(s.get("slide_count") or 0) for s in slideshare if int(s.get("slide_count") or 0) > 4]
    scraped_avg = sum(scraped_counts) / len(scraped_counts) if scraped_counts else 0
    recommended_slide_count = (
        round((local_count + scraped_avg) / 2) if local_count and scraped_avg else (local_count or 8)
    )

    notes: list[str] = []
    if local.get("recommended_layouts"):
        seq = " \u2192 ".join(local["recommended_layouts"][:8])
        notes.append(f"Manus-style {category} decks usually flow: {seq}")
    if local.get("words_per_slide"):
        notes.append(f"Target ~{local['words_per_slide']:.0f} words per slide.")
    if local.get("image_freq"):
        pct = int(local["image_freq"] * 100)
        notes.append(f"~{pct}% of slides carry an image.")
    if slideshare:
        notes.append(
            f"{len(slideshare)} comparable public deck(s) found on SlideShare; use only their structure, never their text."
        )

    return {
        "local_reference": local,
        "slideshare_examples": slideshare,
        "recommended_layouts": local.get("recommended_layouts") or [],
        "recommended_slide_count": recommended_slide_count,
        "design_notes": notes,
    }


def format_design_reference_for_prompt(design_ref: dict[str, Any]) -> str:
    """Render the design reference as a planner-ready text block.

    The block intentionally avoids any *content* from external decks \u2014
    only structural hints: layout sequence, words/slide, image cadence,
    palette, font pairs.
    """
    if not design_ref:
        return ""
    local = design_ref.get("local_reference") or {}
    notes = design_ref.get("design_notes") or []
    layouts = design_ref.get("recommended_layouts") or []
    slide_count = design_ref.get("recommended_slide_count")
    palette = local.get("palette") or []
    fonts = local.get("font_pairs") or []
    examples = design_ref.get("slideshare_examples") or []

    lines: list[str] = ["=== DESIGN REFERENCE (structure only \u2014 NEVER copy text) ==="]
    if layouts:
        lines.append("Recommended layout sequence: " + " \u2192 ".join(layouts[:12]))
    if slide_count:
        lines.append(f"Target slide count: ~{slide_count}")
    if local.get("words_per_slide"):
        lines.append(f"Words per slide target: ~{local['words_per_slide']:.0f}")
    if local.get("image_freq") is not None:
        lines.append(f"Image cadence: ~{int(local['image_freq'] * 100)}% of slides")
    if palette:
        lines.append("Reference palette (hex): " + ", ".join("#" + c for c in palette))
    if fonts:
        lines.append("Reference fonts: " + ", ".join(fonts))
    for note in notes:
        lines.append(f"- {note}")
    if examples:
        lines.append("Public structural references:")
        for ex in examples[:3]:
            sc = ex.get("slide_count") or "?"
            lines.append(f"  * {ex.get('title','')[:90]} ({sc} slides)")
    lines.append("Use this reference to bias layout choice, slide count, image cadence, and visual rhythm. Do NOT reuse any text or imagery from external decks.")
    lines.append("=== END DESIGN REFERENCE ===")
    return "\n".join(lines)
