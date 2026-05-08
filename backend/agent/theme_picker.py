"""Theme auto-selection.

Picks the most fitting NEXUS template for a given topic when the user chooses
"Auto" (or the request comes in with theme empty / "auto"). The mapping is
deterministic and keyword-based so the same topic always yields the same look,
but a small hash-based tiebreaker spreads neutral topics across the library.
"""

from __future__ import annotations

import hashlib
import re

# Curated, themed buckets. Order matters: the FIRST bucket whose pattern
# matches the topic wins. Each value is a list of theme names; we pick the
# one whose hash-of-topic falls on it, so two related decks don't always
# come out in the exact same skin.
_BUCKETS: list[tuple[str, list[str]]] = [
    # Finance / business / pitch / corporate
    (
        r"\b(pitch|investor|series\s?[abc]|venture|vc|finance|financial|earnings|revenue|"
        r"profit|market|saas|b2b|enterprise|business|corporate|strategy|consulting|kpi|"
        r"roadmap)\b",
        ["Complete", "Pitch", "Sales", "Cobalt", "Profile", "Plan", "Strategy",
         "Simplicity", "Modern", "Annual", "light-pro"],
    ),
    # Geopolitics / war / news / journalism / policy
    (
        r"\b(war|conflict|geopolitic|geopolitical|military|nato|nuclear|sanction|policy|"
        r"government|election|diplomac|treaty|crisis|terror|refugee|invasion|"
        r"intelligence|espionage)\b",
        ["Dossier", "Crimson", "Onyx", "Midnight", "Carbon", "Basalt", "Editorial"],
    ),
    # Science / research / academia / medicine
    (
        r"\b(research|study|paper|science|scientific|biology|chemistry|physics|"
        r"medicine|medical|clinical|disease|virus|genom|neuroscience|psychology|"
        r"academic|thesis|fellowship)\b",
        ["Vellum", "Editorial", "Mist", "Linen", "Ice", "Arctic", "Profile"],
    ),
    # Climate / nature / sustainability / energy (non-tech)
    (
        r"\b(climate|sustainab|environment|carbon|renewable|solar|wind|fusion|"
        r"forest|ocean|biodivers|ecosystem|conservation|green|esg)\b",
        ["Emerald", "Forest", "Mint", "Lagoon", "Growth", "Sand", "Vellum"],
    ),
    # Technology / AI / software / startups
    (
        r"\b(ai|artificial\s?intelligence|llm|machine\s?learning|deep\s?learning|"
        r"neural|gpt|transformer|robot|software|developer|engineer|api|cloud|"
        r"kubernetes|devops|cyber|security|blockchain|crypto|web3|quantum|"
        r"compute|chip|gpu|cpu|semiconductor|startup|product\s?launch)\b",
        ["Pixel", "Neon", "Cobalt", "Cerulean", "Midnight", "Carbon", "Aurora",
         "Plum", "Modern", "Launch"],
    ),
    # Education / training / lesson
    (
        r"\b(lesson|teach|course|class|curriculum|student|education|tutorial|"
        r"primer|workshop|training)\b",
        ["Whiteboard", "Sketch", "Mist", "Simple", "Clean", "Lemon", "Aurora"],
    ),
    # Design / brand / creative / fashion / lifestyle
    (
        r"\b(brand|design|creative|fashion|luxury|lifestyle|interior|architect|"
        r"art|gallery|museum|portfolio|aesthetic|typography)\b",
        ["Glamour", "Creative", "Stunning", "Editorial", "Plum", "Berry",
         "Coral", "Tropical", "Elegant"],
    ),
    # Food / restaurant / hospitality / travel
    (
        r"\b(food|recipe|restaurant|cafe|coffee|menu|culinary|chef|hotel|hospitality|"
        r"travel|tourism|destination|cuisine)\b",
        ["Sand", "Vellum", "Amber", "Peach", "Sunset", "Coral", "Sunrise", "Linen"],
    ),
    # Sports / gaming / entertainment
    (
        r"\b(sport|football|soccer|cricket|basketball|olympic|game|gaming|esport|"
        r"movie|film|music|concert|festival|entertainment)\b",
        ["Neon", "Glamour", "Tropical", "Sunrise", "Coral", "Plum", "Cerulean"],
    ),
    # Health / wellness / fitness
    (
        r"\b(health|wellness|fitness|nutrition|diet|mental|therapy|mindful|yoga)\b",
        ["Arctic", "Mint", "Mist", "Linen", "Ice", "Lagoon", "Aurora"],
    ),
]

# Generic fallback bucket if no keyword hits — lots of vivid options.
_FALLBACK_THEMES = [
    "Complete", "Pitch", "Modern", "Sunset", "Ocean", "Mint", "Berry",
    "Aurora", "Tropical", "Coral", "Lavender", "Sunrise", "Cerulean",
    "Plum", "Cobalt", "Emerald", "Crimson", "Glamour", "Stunning",
    "Creative", "Elegant", "Strategy", "Launch", "Growth", "Plan",
    "Editorial", "Pixel", "Vellum", "Dossier", "light-pro",
]

# Theme names actually known to the renderer (frontend + python-pptx).
# Must stay in sync with frontend/src/components/SlideRenderer.jsx themePalettes.
_KNOWN_THEMES = {
    # Existing five
    "light-pro", "Editorial", "Pixel", "Vellum", "Dossier",
    # Light vivid
    "Complete", "Golden", "Simplicity", "Marketing", "Proposal", "Strategy",
    "Launch", "Growth", "Plan", "Pitch", "Sales", "Plan2", "Multi",
    "Stunning", "Profile", "Annual", "Review", "Minimal", "Simple",
    "Elegant", "Modern", "Creative", "Clean",
    # Bold dark
    "Onyx", "Cobalt", "Emerald", "Plum", "Crimson", "Midnight", "Forest",
    "Rose", "Carbon",
    # Vibrant gradient
    "Sunrise", "Aurora", "Tropical", "Lagoon", "Coral", "Ice", "Peach",
    # Bright single-color
    "Sunset", "Ocean", "Mint", "Berry", "Slate", "Lemon", "Lavender",
    "Sand", "Linen", "Mist", "Cerulean", "Whiteboard", "Sketch",
    "Glamour", "Amber", "Arctic", "Neon", "Basalt",
}


def _stable_pick(options: list[str], topic: str, seed: str = "") -> str:
    if not options:
        return "Editorial"
    # Keep only options the renderer actually knows about, preserving order.
    options = [o for o in options if o in _KNOWN_THEMES] or list(_KNOWN_THEMES)
    key = (topic.lower().strip() + "|" + (seed or "")).encode("utf-8")
    h = int(hashlib.sha1(key).hexdigest(), 16)
    return options[h % len(options)]


def is_auto(theme: str | None) -> bool:
    if not theme:
        return True
    t = theme.strip().lower()
    return t in {"", "auto", "auto-pick", "default"}


def auto_select_theme(topic: str, seed: str = "") -> str:
    """Pick the theme that best fits a topic.

    Deterministic for the same (topic, seed) pair. Pass a per-deck `seed`
    (e.g. task_id) so two decks on the same topic still get different looks.
    """
    text = (topic or "").lower()
    for pattern, options in _BUCKETS:
        if re.search(pattern, text):
            return _stable_pick(options, text, seed)
    return _stable_pick(_FALLBACK_THEMES, text, seed)


def resolve_theme(theme: str | None, topic: str, seed: str = "") -> str:
    """Resolve a (possibly 'auto') theme into a concrete theme name."""
    if is_auto(theme):
        return auto_select_theme(topic, seed)
    if theme in _KNOWN_THEMES:
        return theme
    # Unknown theme name: fall back to auto rather than crashing the renderer.
    return auto_select_theme(topic, seed)
