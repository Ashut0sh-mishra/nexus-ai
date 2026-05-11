"""Phase 6U — extract user intent fields from the topic prompt.

Phase 6T benchmarking exposed that hard prompts like
"Produce a 12-slide market research report ..." were ignored: the
incoming ``slide_count`` field on ``/api/generate`` defaulted to 8 and
the planner happily honoured 8 instead of the explicit number in the
prompt text.

This module is a tiny, dependency-free helper that pulls a slide-count
hint out of the prompt. It is intentionally conservative: if the prompt
has no clear count, the function returns ``None`` and the caller keeps
its existing default.
"""

from __future__ import annotations

import re

# Match patterns we have seen in the live benchmark corpus and in real
# user prompts. The regex deliberately requires the digits to be
# followed by "slide" / "slides" within ~3 characters to avoid grabbing
# unrelated numbers like "Q1 2024" or "10x growth".
_SLIDE_COUNT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(\d{1,2})[\s\-]?slide(?:s)?\b", re.IGNORECASE),
    re.compile(r"\b(?:in|with|of|build|create|produce|generate|make)\s+(\d{1,2})\s+slide(?:s)?\b", re.IGNORECASE),
)

# Hard caps mirror the Pydantic constraint on /api/generate
# (slide_count: int = Field(8, ge=4, le=20)).
_MIN_SLIDES = 4
_MAX_SLIDES = 20


def extract_slide_count(topic: str | None) -> int | None:
    """Return an explicit slide count parsed from ``topic`` or ``None``.

    Behaviour:
    * Returns the first match in [4, 20]; values outside that range are
      ignored (returning ``None``) so the caller keeps its default.
    * Whitespace and punctuation around the number do not matter.
    * Returns ``None`` for empty / None input.
    """

    if not topic or not isinstance(topic, str):
        return None
    for pat in _SLIDE_COUNT_PATTERNS:
        m = pat.search(topic)
        if not m:
            continue
        try:
            n = int(m.group(1))
        except (TypeError, ValueError):
            continue
        if _MIN_SLIDES <= n <= _MAX_SLIDES:
            return n
        # Out-of-range numbers are intentionally ignored. Returning the
        # clamped value would silently rewrite the user's request.
        return None
    return None


__all__ = ["extract_slide_count"]
