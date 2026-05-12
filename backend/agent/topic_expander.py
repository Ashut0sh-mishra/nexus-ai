"""Phase 6AM-Grounding: topic expansion.

Short / vague user prompts ("ai", "create ppt on ai") cause the web
search step to return disambiguation noise: Wikipedia stubs about
unrelated subjects, no real grounding. With no real research the LLM
writer hallucinates confidently ("72% of PDF software allows
annotations", "AI is the new electricity \u2014 Einstein"), and the deck
ends up presenting fiction beautifully.

This module turns the user's raw topic into a small set of specific
search queries that the existing :class:`SearchService` can actually
ground a deck on. It is:

* **Additive.** The kill switch ``NEXUS_DISABLE_TOPIC_EXPANSION=true``
  returns ``[topic]`` unchanged so the legacy pipeline is one env var
  away. Any LLM/parse failure also degrades to ``[topic]``.
* **Cheap.** One LLM call (cap ~120 tokens out) per deck.
* **Deterministic at the edges.** A regex layer strips meta-verbs
  ("create ppt on", "make a presentation about") before the LLM sees
  the topic, so even when the LLM is unavailable the search query is
  cleaner than the raw user input.

Public surface:

    canonicalize_topic(raw: str) -> str
        Pure-Python cleanup; safe to call in tests with no LLM.

    async expand_topic(topic, ai_call=None, *, max_queries=5)
        -> tuple[list[str], int, float]
        Returns ``(queries, tokens, cost)``. ``queries[0]`` is always
        the canonicalized topic; the rest are LLM-proposed specific
        angles. Order matters: the planner / writer see the union of
        results in the order they were harvested.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


# ── Canonicalization ─────────────────────────────────────────────────────
#
# A small allow-list of meta-verbs that users tend to prefix on top of the
# actual topic. We strip these so "create ppt on ai" reaches the web
# search layer as "ai". The list is intentionally short and case-
# insensitive; we'd rather leave a substring in than corrupt a topic.
_META_PREFIXES = (
    "create a ppt on",
    "create a ppt about",
    "create ppt on",
    "create ppt about",
    "create a presentation on",
    "create a presentation about",
    "create presentation on",
    "create presentation about",
    "make a ppt on",
    "make a ppt about",
    "make a presentation on",
    "make a presentation about",
    "make ppt on",
    "make ppt about",
    "build a deck on",
    "build a deck about",
    "build deck on",
    "build deck about",
    "generate a ppt on",
    "generate a ppt about",
    "generate ppt on",
    "generate ppt about",
    "generate a presentation on",
    "generate a presentation about",
    "give me a ppt on",
    "give me a presentation on",
    "i want a ppt on",
    "i want a presentation on",
    "i need a ppt on",
    "i need a presentation on",
    "ppt on",
    "ppt about",
    "presentation on",
    "presentation about",
    "deck on",
    "deck about",
    "slides on",
    "slides about",
    "slides for",
)


def canonicalize_topic(raw: str) -> str:
    """Strip meta-verbs and surrounding whitespace.

    Examples
    --------
    >>> canonicalize_topic("create ppt on ai")
    'ai'
    >>> canonicalize_topic("Make a presentation about renewable energy in india")
    'renewable energy in india'
    >>> canonicalize_topic("AI safety")  # already clean
    'AI safety'
    """
    if not isinstance(raw, str):
        return ""
    text = raw.strip()
    if not text:
        return ""
    lowered = text.lower()
    for prefix in _META_PREFIXES:
        if lowered.startswith(prefix + " "):
            text = text[len(prefix):].lstrip(" :-\u2014\u2013")
            lowered = text.lower()
    # Collapse internal whitespace and trim trailing punctuation that came
    # from chat input.
    text = re.sub(r"\s+", " ", text).strip(" .;:-\u2014\u2013")
    return text


# ── Public expander ──────────────────────────────────────────────────────

_KILL_SWITCH_ENV = "NEXUS_DISABLE_TOPIC_EXPANSION"

# Topics this length or longer are assumed specific enough; we skip the
# LLM call and only return the canonicalized topic plus light riders.
# 60 chars is roughly "AI agents in enterprise customer support 2026" \u2014
# long enough that "broaden it" is more likely to hurt than help.
_SPECIFICITY_CHAR_THRESHOLD = 60


AiCall = Callable[..., Awaitable[tuple[str, int, float]]]


async def expand_topic(
    topic: str,
    ai_call: AiCall | None = None,
    *,
    max_queries: int = 5,
) -> tuple[list[str], int, float]:
    """Expand ``topic`` into up to ``max_queries`` search queries.

    ``queries[0]`` is always the canonicalized topic; downstream
    harvesters may rely on that invariant.

    Parameters
    ----------
    topic:
        Raw user input. Will be canonicalized before any LLM call.
    ai_call:
        An async callable matching ``AgentLoop._ai_call``'s signature.
        When ``None`` (e.g. in unit tests) the function returns the
        canonicalized topic only. ``(queries, 0, 0.0)``.
    max_queries:
        Hard cap on returned list length. ``<= 1`` returns the
        canonicalized topic only.

    Returns
    -------
    ``(queries, tokens, cost)``.
    """
    base = canonicalize_topic(topic)
    if not base:
        return [], 0, 0.0
    if max_queries <= 1:
        return [base], 0, 0.0

    # Kill switch: ops can disable expansion without redeploying.
    if os.environ.get(_KILL_SWITCH_ENV, "").lower() in ("1", "true", "yes"):
        return [base], 0, 0.0

    # Long, already-specific topics: skip the LLM. The harvest stage's
    # built-in riders will handle volume; spending a call on expansion
    # would just paraphrase.
    if len(base) >= _SPECIFICITY_CHAR_THRESHOLD:
        return [base], 0, 0.0

    if ai_call is None:
        return [base], 0, 0.0

    # One cheap LLM call. We ask for SPECIFIC angles only, with explicit
    # examples so the model doesn't return "AI overview", "AI summary"
    # \u2014 the kind of paraphrase that gets us the same Wikipedia noise.
    system = (
        "You convert a vague presentation topic into specific web search "
        "queries. You return ONLY a JSON array of strings."
    )
    want = max(2, min(max_queries - 1, 6))
    user = (
        f'Topic: "{base}"\n\n'
        f"Write {want} SPECIFIC web search queries that would surface "
        f"substantive 2025\u20132026 sources for a presentation on this "
        f"topic. Each query must be 4\u201310 words.\n\n"
        f"REQUIRED:\n"
        f"- Cover different angles: market size, key players, recent "
        f"events, statistics, expert commentary.\n"
        f"- Bias toward current/recent (use a recent year if relevant).\n"
        f"- Use proper-noun anchors when the topic has well-known "
        f"organizations, people, or reports.\n\n"
        f"FORBIDDEN:\n"
        f'- "{base} overview", "{base} summary", "{base} introduction", '
        f'"what is {base}". Paraphrases of the topic are useless.\n'
        f"- Generic riders like \"news\", \"information\", \"facts\".\n\n"
        f"Return ONLY a JSON array of strings. No prose, no preamble."
    )

    tokens = 0
    cost = 0.0
    proposals: list[str] = []
    try:
        text, tokens, cost = await ai_call(
            role="analyze",
            system=system,
            user=user,
            max_tokens=300,
            temperature=0.3,
        )
        cleaned = _strip_fences(text or "")
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if match:
            cleaned = match.group(0)
        data = json.loads(cleaned)
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, str):
                    q = re.sub(r"\s+", " ", entry).strip(' "\'\u201c\u201d')
                    if q:
                        proposals.append(q)
    except Exception as exc:
        logger.warning(
            "topic_expander.failed",
            extra={"topic": base[:80], "err": str(exc)},
        )
        proposals = []

    # De-dup, filter near-paraphrases of the base topic, cap length.
    base_lower = base.lower()
    out: list[str] = [base]
    seen: set[str] = {base_lower}
    for q in proposals:
        ql = q.lower()
        if ql in seen:
            continue
        # Pure paraphrase guard: skip queries that are just the topic
        # with a generic suffix like "overview" or "summary".
        if ql.startswith(base_lower) and len(ql) - len(base_lower) <= 12:
            tail = ql[len(base_lower):].strip()
            if tail in {"", "overview", "summary", "introduction", "intro", "info", "news"}:
                continue
        seen.add(ql)
        out.append(q)
        if len(out) >= max_queries:
            break

    logger.info(
        "topic_expander.done",
        extra={
            "topic": base[:80],
            "queries": len(out),
            "tokens": tokens,
        },
    )
    return out, tokens, cost


def _strip_fences(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned
