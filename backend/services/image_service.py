"""Image generation via Pollinations (free, no key) with Unsplash fallback.

Returns a public URL that works directly as an <img src> AND can be downloaded
by the PPTX export service.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

logger = logging.getLogger("nexus.services.image")

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


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
