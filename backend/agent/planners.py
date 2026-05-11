"""Phase 2.5 — LLM planner adapters for `AgentRuntime`.

The runtime accepts any ``Planner = Callable[[goal, history], Awaitable[str]]``.
Production wraps :class:`services.ai_service.AIService`. Tests inject fakes.

Configuration safety: ``build_default_planner`` returns ``None`` when **no**
provider key is configured. The HTTP layer turns that into a 503, never a
crash.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from agent.runtime import Planner, StepRecord
from config import settings

logger = logging.getLogger("nexus.agent.planners")


AGENT_SYSTEM_PROMPT = """You are NEXUS, a careful tool-using assistant.

You MUST reply with a single JSON object on each turn, no prose, no code fence,
shaped exactly like one of:

  {"kind": "message", "text": "<short status>"}
  {"kind": "tool", "name": "<tool_name>", "args": {"<k>": "<v>"}}
  {"kind": "final", "text": "<final answer to the user>"}

Rules:
- Only call tools that are listed in the allowlist for this run.
- Prefer "final" as soon as the goal is satisfied. Do NOT loop forever.
- Keep "args" small and JSON-serialisable. No code blocks. No markdown.
- If a tool returned an error, try a different approach or finalise with the
  best partial answer.
"""


def _render_history(goal: str, history: list[StepRecord]) -> str:
    """Compact, deterministic transcript fed back to the planner each turn."""
    lines = [f"GOAL: {goal}", ""]
    for rec in history:
        if rec.kind == "thought":
            lines.append(f"[{rec.index}] thought: {json.dumps(rec.input, ensure_ascii=False)[:600]}")
        elif rec.kind == "observation":
            payload: dict = {}
            if rec.action:
                payload["tool"] = rec.action
            if rec.error:
                payload["error"] = rec.error
            else:
                # Truncate large outputs.
                data = rec.output.get("data") if isinstance(rec.output, dict) else None
                payload["data"] = (str(data)[:400]) if data is not None else None
            lines.append(f"[{rec.index}] observation: {json.dumps(payload, ensure_ascii=False)}")
        elif rec.kind == "final":
            lines.append(f"[{rec.index}] final: {rec.input.get('text', '')[:400]}")
    lines.append("")
    lines.append("Reply with the next JSON action only.")
    return "\n".join(lines)


def _has_any_provider() -> bool:
    return any(
        [
            settings.OPENROUTER_API_KEY,
            settings.NVIDIA_NIM_API_KEY,
            settings.GEMINI_API_KEY,
            settings.GROQ_API_KEY,
            settings.ANTHROPIC_API_KEY,
            settings.OPENAI_API_KEY,
        ]
    )


def build_default_planner() -> Optional[Planner]:
    """Return an ``AIService``-backed planner, or ``None`` if unconfigured."""
    if not _has_any_provider():
        return None

    from services.ai_service import AIService

    ai = AIService()

    async def _plan(goal: str, history: list[StepRecord]) -> str:
        text, _tokens, _cost = await ai.complete(
            AGENT_SYSTEM_PROMPT,
            _render_history(goal, history),
            max_tokens=1024,
            temperature=0.2,
        )
        return text

    return _plan
