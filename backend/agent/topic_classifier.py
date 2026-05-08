"""Topic → editorial profile classifier.

Reverse-engineered from analysis of seven Manus-generated decks
(see ``manus-reference/sample-decks/ANALYSIS.md``).

Given a raw user prompt, returns an editorial profile that drives:
  - word target per slide (history needs ~100 words; pitch ~60)
  - font pair (heading + body) — Manus picks fonts by topic, not from a fixed list
  - single accent color (Manus uses exactly 3 colors per deck: ink + body + 1 accent)
  - image strategy (history/research = no images; pitch/brand = heroes)
  - preferred theme name

Rule-based first (keyword scoring) so it is cheap, deterministic, and never
fails. The shape of the returned dict is stable so downstream code can rely on
it without optional handling.
"""

from __future__ import annotations

import re
from typing import Any

# Categories — anchored to ANALYSIS.md findings.
Category = str  # one of: history|research|tutorial|pitch|data|brand|explainer

# Per-category editorial defaults.
# word_target = AVERAGE words per slide we want the LLM to write.
# image_strategy: "none" | "hero" | "diagram" | "chart-only" | "optional"
#   - "optional" = sparingly: title + closing + 1–2 hero slides
# theme = matches frontend SlideRenderer.jsx themePalettes keys.
_PROFILES: dict[str, dict[str, Any]] = {
    "history": {
        "mood": "serious, archival, editorial",
        "accent_color": "#8B0000",          # crimson
        "ink_color": "#2C3539",
        "body_color": "#444444",
        "font_pair": ("Cinzel", "Inter"),
        "heading_weight": "700",
        "body_weight": "300",
        "word_target": 100,
        "image_strategy": "optional",
        "theme": "Editorial",
    },
    "research": {
        "mood": "academic, restrained, evidentiary",
        "accent_color": "#8B0000",
        "ink_color": "#333333",
        "body_color": "#555555",
        "font_pair": ("Playfair Display", "Roboto"),
        "heading_weight": "700",
        "body_weight": "400",
        "word_target": 100,
        "image_strategy": "optional",
        "theme": "Vellum",
    },
    "tutorial": {
        "mood": "didactic, clean, code-friendly",
        "accent_color": "#E6DB74",          # Monokai yellow
        "ink_color": "#222222",
        "body_color": "#3A3A3A",
        "font_pair": ("Poppins", "Inter"),
        "heading_weight": "600",
        "body_weight": "300",
        "word_target": 70,
        "image_strategy": "diagram",
        "theme": "Pixel",
        "code_font": "Fira Code",
    },
    "pitch": {
        "mood": "bold, confident, brand-forward",
        "accent_color": "#00D084",          # mint
        "ink_color": "#0A2540",
        "body_color": "#3F4D5E",
        "font_pair": ("Montserrat", "Open Sans"),
        "heading_weight": "700",
        "body_weight": "400",
        "word_target": 60,
        "image_strategy": "hero",
        "theme": "Pitch",
    },
    "data": {
        "mood": "punchy, futuristic, numbers-first",
        "accent_color": "#F472B6",          # hot pink
        "ink_color": "#000000",
        "body_color": "#1A1A1A",
        "font_pair": ("Orbitron", "Rajdhani"),
        "heading_weight": "900",
        "body_weight": "700",
        "word_target": 55,
        "image_strategy": "chart-only",
        "theme": "Onyx",
    },
    "brand": {
        "mood": "luxe, editorial, design-forward",
        "accent_color": "#B91C1C",
        "ink_color": "#111111",
        "body_color": "#3A3A3A",
        "font_pair": ("Playfair Display", "Inter"),
        "heading_weight": "700",
        "body_weight": "300",
        "word_target": 40,
        "image_strategy": "hero",
        "theme": "Glamour",
    },
    "explainer": {
        "mood": "friendly, illustrative, instructional",
        "accent_color": "#2563EB",
        "ink_color": "#1F2937",
        "body_color": "#4B5563",
        "font_pair": ("Inter", "Inter"),
        "heading_weight": "700",
        "body_weight": "400",
        "word_target": 70,
        "image_strategy": "diagram",
        "theme": "light-pro",
    },
}

# Keyword → category. First match wins per category, then we pick the highest
# scoring category. Patterns kept liberal so partial matches still work.
_KEYWORDS: list[tuple[str, str]] = [
    # history
    ("history", r"\b(history|historical|empire|civil\s?war|ancient|medieval|"
        r"world\s?war|ww[12]|holocaust|colonial|revolution|dynasty|civilization|"
        r"renaissance|cold\s?war|caesar|napoleon|roman|byzantine|ottoman|mughal|"
        r"freedom\s?movement|independence|partition)\b"),
    # research
    ("research", r"\b(research|study|paper|thesis|literature\s?review|hypothesis|"
        r"clinical|peer[-\s]?review|methodology|findings|systematic\s?review|"
        r"meta[-\s]?analysis|citation|bibliography|abstract|whitepaper)\b"),
    # tutorial
    ("tutorial", r"\b(tutorial|how\s?to|guide|walkthrough|primer|crash\s?course|"
        r"getting\s?started|introduction\s?to|build(ing)?\s+a|step[-\s]?by[-\s]?step|"
        r"django|flask|react|vue|node|python\s+(101|basics|fundamentals)|"
        r"learn|teach|lesson|workshop|tutorial|coding|programming)\b"),
    # pitch
    ("pitch", r"\b(pitch|investor|fundrais|seed|series\s?[abcd]|venture|vc|"
        r"product\s?launch|go[-\s]?to[-\s]?market|gtm|business\s?plan|"
        r"startup|founders?|cap\s?table|valuation|moat|tam|sam|som|"
        r"acquisition|merger|board\s?meeting|sales\s?deck)\b"),
    # data
    ("data", r"\b(q[1-4]|quarterly|earnings|sales\s?report|revenue|kpi|metrics|"
        r"dashboard|analytics|performance\s?review|monthly\s?report|"
        r"forecast|p&l|ebitda|arr|mrr|conversion|funnel|cohort|retention)\b"),
    # brand
    ("brand", r"\b(brand|branding|rebrand|identity|style\s?guide|fashion|"
        r"luxury|lifestyle|interior|architecture|art|gallery|museum|portfolio|"
        r"aesthetic|typography|logo|visual\s?identity|campaign)\b"),
    # explainer
    ("explainer", r"\b(explain|explainer|overview|introduction|what\s?is|"
        r"understanding|simple|beginner|fundamentals|concepts|basics|"
        r"primer\s+on)\b"),
]

_DEFAULT_CATEGORY = "explainer"


def classify_topic(prompt: str) -> dict[str, Any]:
    """Return the editorial profile for a prompt. Never raises."""
    text = (prompt or "").lower().strip()
    if not text:
        return _profile(_DEFAULT_CATEGORY)

    scores: dict[str, int] = {}
    for category, pattern in _KEYWORDS:
        hits = len(re.findall(pattern, text))
        if hits:
            scores[category] = scores.get(category, 0) + hits

    if not scores:
        return _profile(_DEFAULT_CATEGORY)

    # Highest-scoring category wins. Ties broken by _KEYWORDS declaration order.
    order = [c for c, _ in _KEYWORDS]
    best = max(scores.items(), key=lambda kv: (kv[1], -order.index(kv[0])))[0]
    return _profile(best)


def _profile(category: str) -> dict[str, Any]:
    base = _PROFILES.get(category) or _PROFILES[_DEFAULT_CATEGORY]
    out = dict(base)
    out["category"] = category
    return out


def style_guidance_block(profile: dict[str, Any]) -> str:
    """Inject category-specific writing guidance into the slide prompt."""
    cat = profile.get("category", _DEFAULT_CATEGORY)
    target = int(profile.get("word_target", 70))
    mood = profile.get("mood", "")
    floor = max(40, target - 15)
    ceiling = target + 25
    return (
        f"\n\nEDITORIAL PROFILE (category={cat}, mood={mood}):\n"
        f"- Aim for ~{target} words PER SLIDE of body content "
        f"(soft floor {floor}, soft ceiling {ceiling}).\n"
        f"- Bullets for this category: 3-5 items, each a full sentence "
        f"({_bullet_word_hint(cat)} words per bullet).\n"
        f"- Be specific. Use real names, dates, numbers, quotes from research.\n"
        f"- Never pad with marketing fluff to hit the word count — cut the slide "
        f"into two slides instead if you have more to say.\n"
    )


def _bullet_word_hint(category: str) -> str:
    return {
        "history": "18-25",
        "research": "18-25",
        "tutorial": "12-18",
        "pitch": "10-14",
        "data": "8-12",
        "brand": "6-10",
        "explainer": "12-18",
    }.get(category, "12-18")
