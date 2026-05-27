"""Phase 6AX — Content quality validation.

Validates slide content against research to catch hallucinated data,
generic filler, and low-quality slides BEFORE they're saved.

This is a pre-save quality gate that complements deck_repair.py:
- deck_repair.py fixes schema/contract violations (missing fields, wrong types)
- content_validator.py detects content quality issues (fake data, filler, repetition)
"""

from __future__ import annotations

from typing import Any
import re


def has_hallucinated_chart(slide: dict[str, Any], research: str) -> bool:
    """Check if chart contains numbers not found in research."""
    if slide.get("layout") != "chart":
        return False

    chart_data = slide.get("chart_data")
    if not isinstance(chart_data, dict):
        return False

    values = chart_data.get("values", [])
    if not values:
        return False

    # Extract all numbers from research (with some context)
    research_numbers = set()
    # Match numbers with optional units/context: "42%", "$1.2B", "1,234", etc.
    for match in re.finditer(r'\$?\d+(?:,\d{3})*(?:\.\d+)?[KMB%]?', research):
        num_str = match.group(0)
        # Normalize: remove $, commas
        normalized = num_str.replace('$', '').replace(',', '')
        research_numbers.add(normalized)

    # Check if chart values appear in research
    suspicious_count = 0
    for val in values:
        val_str = str(val).replace(',', '')
        # Check if this exact value or close match exists in research
        found = False
        for research_num in research_numbers:
            if val_str in research_num or research_num in val_str:
                found = True
                break
        if not found:
            suspicious_count += 1

    # If more than half the values aren't in research, likely hallucinated
    return suspicious_count > len(values) / 2


def is_generic_filler(slide: dict[str, Any]) -> bool:
    """Detect generic filler slides with no specific content."""
    title = slide.get("title", "").lower()

    # Generic titles that signal filler content
    generic_phrases = [
        "market overview", "key benefits", "why this matters",
        "growing trend", "innovative solution", "our approach",
        "next steps", "the opportunity", "looking ahead",
        "in conclusion", "to summarize", "key takeaways",
    ]

    for phrase in generic_phrases:
        if phrase in title:
            return True

    # Check bullets for generic content
    bullets = slide.get("bullets", [])
    if bullets:
        generic_bullet_words = ["various", "several", "many", "numerous", "growing", "increasing"]
        generic_count = 0
        for bullet in bullets:
            bullet_lower = str(bullet).lower()
            if any(word in bullet_lower for word in generic_bullet_words):
                generic_count += 1
        # If most bullets are generic, it's filler
        if generic_count > len(bullets) / 2:
            return True

    return False


def validate_slide_content(slide: dict[str, Any], research: str = "") -> dict[str, Any]:
    """Validate slide content quality.

    Returns dict with:
        - valid: bool (True if slide passes quality checks)
        - reason: str (explanation if invalid)
        - fix: str (suggested fix: "convert_to_bullets", "remove", etc.)
    """
    layout = slide.get("layout", "")

    # Check for hallucinated chart data
    if has_hallucinated_chart(slide, research):
        return {
            "valid": False,
            "reason": "Chart contains numbers not found in research (likely hallucinated)",
            "fix": "convert_to_bullets",
        }

    # Check for generic filler
    if is_generic_filler(slide):
        return {
            "valid": False,
            "reason": "Slide contains generic filler content without specific facts",
            "fix": "remove",
        }

    # Passed all checks
    return {"valid": True, "reason": "", "fix": ""}


def clean_slides_for_quality(slides: list[dict[str, Any]], research: str = "") -> list[dict[str, Any]]:
    """Remove or convert low-quality slides.

    Phase 6AX: This runs AFTER repair_for_validator but BEFORE editorial passes.
    It's the last chance to catch content quality issues before save.
    """
    if not isinstance(slides, list):
        return slides

    out = []
    removed_count = 0
    converted_count = 0

    for slide in slides:
        if not isinstance(slide, dict):
            out.append(slide)
            continue

        validation = validate_slide_content(slide, research)

        if validation["valid"]:
            out.append(slide)
        elif validation["fix"] == "convert_to_bullets":
            # Convert bad chart to bullets
            converted_count += 1
            slide["layout"] = "bullets"
            # Use subtitle or generic message
            subtitle = slide.get("subtitle", "Key insights")
            slide["bullets"] = [subtitle, f"Data from {slide.get('chart_data', {}).get('source', 'research')}"]
            slide.pop("chart_data", None)
            slide.pop("chart_type", None)
            out.append(slide)
        elif validation["fix"] == "remove":
            # Skip this slide entirely
            removed_count += 1
        else:
            # Unknown fix, keep the slide
            out.append(slide)

    # Log quality issues (would need logger import)
    # logger.info(f"Quality validation: removed={removed_count}, converted={converted_count}")

    return out


__all__ = ["clean_slides_for_quality", "validate_slide_content"]
