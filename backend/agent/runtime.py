"""Phase 2 — Dynamic tool-calling agent runtime.

Bounded loop:
    receive goal -> ask planner for next action (strict JSON) -> validate
    -> dispatch tool from agent.tools.TOOLS -> record observation
    -> repeat until ``final`` action or a safety limit fires.

This runtime is **independent** of the existing 6-step slide pipeline in
``agent/loop.py``. Nothing in this file is wired into request flow yet.

Safety:
- ``max_steps`` hard cap on planning rounds.
- ``max_tool_failures`` hard cap on consecutive tool failures.
- ``per_step_timeout`` per-tool-call wall clock.
- ``allowed_tools`` allowlist (defaults to all 29 tools).
- Every step is persisted via ``services.agent_run_service``.
- Malformed planner output, unknown tools, and disallowed tools each produce
  a structured ``observation`` step rather than crashing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from agent.tools import TOOLS, call_tool
from services.agent_run_service import (
    append_step,
    create_run,
    finish_run,
    record_artifact,
)

logger = logging.getLogger("nexus.agent.runtime")


# ── Planner protocol ────────────────────────────────────────────────────────
# A planner is an async callable that takes (goal, history) and returns the
# raw model text (expected to contain a JSON action). Real implementations
# wrap ``services.ai_service.AIService``; tests inject a fake.

Planner = Callable[[str, list["StepRecord"]], Awaitable[str]]


# ── Action schema ──────────────────────────────────────────────────────────
_ALLOWED_KINDS = {"message", "tool", "final"}


@dataclass
class Action:
    kind: str  # "message" | "tool" | "final"
    name: Optional[str] = None
    args: dict[str, Any] = field(default_factory=dict)
    text: Optional[str] = None  # for "message" / "final"


def _extract_json_block(text: str) -> Optional[dict[str, Any]]:
    """Return the first valid JSON object in *text* or None."""
    if not text:
        return None
    text = text.strip()
    # Fast path: whole string is JSON.
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    # Fenced ```json ... ``` block.
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(1))
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass
    # First top-level {...} via brace matching.
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        return obj if isinstance(obj, dict) else None
                    except Exception:
                        break
        start = text.find("{", start + 1)
    return None


def parse_action(raw: str) -> tuple[Optional[Action], Optional[str]]:
    """Return (Action, None) on success, (None, error_message) on failure."""
    obj = _extract_json_block(raw)
    if obj is None:
        return None, "planner_output_not_json"
    kind = obj.get("kind")
    if kind not in _ALLOWED_KINDS:
        return None, f"invalid_kind: {kind!r}"
    if kind == "tool":
        name = obj.get("name")
        if not isinstance(name, str) or not name:
            return None, "tool_action_missing_name"
        args = obj.get("args") or {}
        if not isinstance(args, dict):
            return None, "tool_action_args_not_object"
        return Action(kind="tool", name=name, args=args), None
    if kind == "final":
        return Action(kind="final", text=str(obj.get("text") or "")), None
    # message
    return Action(kind="message", text=str(obj.get("text") or "")), None


# ── Runtime config + result ────────────────────────────────────────────────
@dataclass
class RuntimeConfig:
    max_steps: int = 12
    max_tool_failures: int = 3
    per_step_timeout: float = 30.0
    allowed_tools: Optional[set[str]] = None  # None == all registered tools

    def is_tool_allowed(self, name: str) -> bool:
        if name not in TOOLS:
            return False
        if self.allowed_tools is None:
            return True
        return name in self.allowed_tools


@dataclass
class StepRecord:
    """In-memory mirror of an AgentStep, passed to the planner as history."""

    index: int
    kind: str
    action: Optional[str] = None
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class RuntimeResult:
    run_id: str
    status: str  # "done" | "failed" | "cancelled"
    final_text: Optional[str]
    steps: list[StepRecord]
    error: Optional[str] = None


# ── The runtime ────────────────────────────────────────────────────────────
class AgentRuntime:
    def __init__(self, planner: Planner, config: Optional[RuntimeConfig] = None) -> None:
        self.planner = planner
        self.config = config or RuntimeConfig()

    async def run(
        self,
        session: AsyncSession,
        *,
        goal: str,
        task_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> RuntimeResult:
        run = await create_run(
            session,
            goal=goal,
            task_id=task_id,
            user_id=user_id,
            max_steps=self.config.max_steps,
            meta={"allowed_tools": sorted(self.config.allowed_tools) if self.config.allowed_tools else None},
        )
        await session.commit()

        history: list[StepRecord] = []
        consecutive_failures = 0
        final_text: Optional[str] = None
        terminal_status = "failed"
        terminal_error: Optional[str] = None

        for step_no in range(self.config.max_steps):
            # 1. Ask planner for the next action.
            try:
                raw = await asyncio.wait_for(
                    self.planner(goal, history), timeout=self.config.per_step_timeout
                )
            except asyncio.TimeoutError:
                rec = await self._record(
                    session, run.id, history,
                    kind="observation", status="error",
                    output={"error": "planner_timeout"},
                    error="planner_timeout",
                )
                terminal_error = "planner_timeout"
                break
            except Exception as exc:
                logger.exception("runtime.planner_failed")
                await self._record(
                    session, run.id, history,
                    kind="observation", status="error",
                    output={"error": "planner_exception"},
                    error=str(exc),
                )
                terminal_error = f"planner_exception: {exc}"
                break

            action, parse_err = parse_action(raw)
            if action is None:
                await self._record(
                    session, run.id, history,
                    kind="observation", status="error",
                    input={"raw": raw[:500]},
                    output={"error": parse_err},
                    error=parse_err,
                )
                consecutive_failures += 1
                if consecutive_failures >= self.config.max_tool_failures:
                    terminal_error = f"max_failures_exceeded: {parse_err}"
                    break
                continue

            # 2. Record the planner's chosen action as a "thought" step.
            await self._record(
                session, run.id, history,
                kind="thought",
                action=action.name if action.kind == "tool" else None,
                input={"kind": action.kind, "name": action.name, "args": action.args, "text": action.text},
            )

            # 3. Terminal action.
            if action.kind == "final":
                final_text = action.text
                terminal_status = "done"
                await self._record(
                    session, run.id, history,
                    kind="final", input={"text": final_text or ""},
                )
                break

            # 4. Plain message (no tool dispatch); reset failure counter.
            if action.kind == "message":
                consecutive_failures = 0
                continue

            # 5. Tool action.
            assert action.kind == "tool" and action.name is not None
            if not self.config.is_tool_allowed(action.name):
                err = "unknown_tool" if action.name not in TOOLS else "tool_not_allowed"
                await self._record(
                    session, run.id, history,
                    kind="observation", status="error",
                    action=action.name, input=action.args,
                    output={"error": err}, error=err,
                )
                consecutive_failures += 1
                if consecutive_failures >= self.config.max_tool_failures:
                    terminal_error = f"max_failures_exceeded: {err}"
                    break
                continue

            try:
                result = await asyncio.wait_for(
                    call_tool(action.name, **action.args),
                    timeout=self.config.per_step_timeout,
                )
            except asyncio.TimeoutError:
                await self._record(
                    session, run.id, history,
                    kind="observation", status="error",
                    action=action.name, input=action.args,
                    output={"error": "tool_timeout"}, error="tool_timeout",
                )
                consecutive_failures += 1
                if consecutive_failures >= self.config.max_tool_failures:
                    terminal_error = "max_failures_exceeded: tool_timeout"
                    break
                continue
            except Exception as exc:
                logger.exception("runtime.tool_unhandled")
                await self._record(
                    session, run.id, history,
                    kind="observation", status="error",
                    action=action.name, input=action.args,
                    output={"error": "tool_exception"}, error=str(exc),
                )
                consecutive_failures += 1
                if consecutive_failures >= self.config.max_tool_failures:
                    terminal_error = f"max_failures_exceeded: tool_exception: {exc}"
                    break
                continue

            obs_status = "ok" if result.ok else "error"
            await self._record(
                session, run.id, history,
                kind="observation", status=obs_status,
                action=action.name, input=action.args,
                output=result.to_dict(), error=result.error,
            )
            if result.ok:
                consecutive_failures = 0
                # Phase 3: persist evidence artifacts for successful
                # source-bearing tool observations. Failures here must not
                # abort the run.
                try:
                    await self._record_source_artifacts(
                        session, run.id, action.name, result.to_dict()
                    )
                except Exception:  # pragma: no cover - defensive
                    logger.exception("runtime.artifact_record_failed")
            else:
                consecutive_failures += 1
                if consecutive_failures >= self.config.max_tool_failures:
                    terminal_error = f"max_failures_exceeded: {result.error}"
                    break
        else:
            # Loop exited without break -> hit max_steps.
            terminal_error = "max_steps_exceeded"

        await finish_run(
            session, run_id=run.id, status=terminal_status, error=terminal_error
        )
        await session.commit()

        return RuntimeResult(
            run_id=run.id,
            status=terminal_status,
            final_text=final_text,
            steps=history,
            error=terminal_error,
        )

    # ── helpers ──────────────────────────────────────────────────────────
    async def _record(
        self,
        session: AsyncSession,
        run_id: str,
        history: list[StepRecord],
        *,
        kind: str,
        action: Optional[str] = None,
        status: str = "ok",
        input: Optional[dict[str, Any]] = None,
        output: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> StepRecord:
        step = await append_step(
            session, run_id=run_id, kind=kind, action=action,
            input_json=input or {}, output_json=output or {},
            status=status, error=error,
        )
        await session.commit()
        rec = StepRecord(
            index=step.step_index, kind=kind, action=action,
            input=dict(input or {}), output=dict(output or {}), error=error,
        )
        history.append(rec)
        return rec

    async def _record_source_artifacts(
        self,
        session: AsyncSession,
        run_id: str,
        tool_name: str,
        tool_output: dict[str, Any],
    ) -> int:
        """Persist evidence artifacts extracted from a successful observation.

        Returns the number of artifact rows written. ``0`` is a perfectly
        valid result (e.g. an ``idle`` observation with no sources).
        """
        # Local import keeps the runtime importable in test contexts that
        # don't need source grounding.
        from agent.source_grounding import extract_sources_from_tool_result

        sources = extract_sources_from_tool_result(tool_name, tool_output)
        if not sources:
            return 0

        for src in sources:
            await record_artifact(
                session,
                run_id=run_id,
                artifact_type="source",
                title=(src.get("title") or src.get("url") or tool_name)[:240],
                meta={
                    "tool": tool_name,
                    "url": src.get("url"),
                    "snippet": src.get("snippet"),
                    "provider": src.get("provider"),
                    "observed_at": src.get("observed_at"),
                    "confidence": src.get("confidence"),
                    "metadata": src.get("metadata") or {},
                },
                file_url=src.get("url"),
            )
        await session.commit()
        return len(sources)
