"""Phase 6U — slide-count hint extraction tests.

Verifies that ``agent.prompt_intent.extract_slide_count`` honours
explicit slide-count phrases in user prompts (e.g. "Produce a 12-slide
deck") and ignores ambiguous numbers. The 6T live benchmark showed
that 3/11 hard prompts failed the slide-count window because the
generator silently used the API field default of 8 instead of the
explicit count in the prompt text.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.prompt_intent import extract_slide_count  # noqa: E402


def test_extracts_hyphenated_slide_count() -> None:
    assert extract_slide_count("Produce a 12-slide market research report") == 12


def test_extracts_spaced_slide_count() -> None:
    assert extract_slide_count("Build a 10 slide deck on solar") == 10


def test_extracts_plural_slides() -> None:
    assert extract_slide_count("Create 14 slides covering battery markets") == 14


def test_extracts_with_keyword() -> None:
    assert extract_slide_count("generate 11 slide briefing") == 11


def test_returns_none_when_absent() -> None:
    assert extract_slide_count("Make a deck on autonomous vehicles") is None


def test_returns_none_for_empty_input() -> None:
    assert extract_slide_count("") is None
    assert extract_slide_count(None) is None  # type: ignore[arg-type]


def test_ignores_out_of_range_high() -> None:
    # 25 is above Pydantic's le=20; we deliberately do NOT clamp because
    # silently rewriting the user's request would mask the issue.
    assert extract_slide_count("Build a 25-slide marathon") is None


def test_ignores_out_of_range_low() -> None:
    # 2 is below Pydantic's ge=4.
    assert extract_slide_count("Just 2 slides please") is None


def test_does_not_match_unrelated_numbers() -> None:
    # "10x growth" must not be parsed as 10 slides.
    assert extract_slide_count("Pitch 10x growth strategy") is None


def test_returns_first_match_when_multiple() -> None:
    assert extract_slide_count("Produce 8 slides; 12 slides max") == 8
