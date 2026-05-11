"""Phase 6R — structured run-event emitter.

Wraps the legacy ``on_progress(message, progress_pct, step, **extra)`` callback
and produces a richer SSE payload with a stable schema:

    {
        "task_id":      str,
        "event":        str,    # canonical event type (see EVENT_TYPES)
        "stage":        str,    # logical pipeline stage
        "message":      str,
        "progress_pct": float,
        "timestamp":    str,    # ISO-8601 UTC
        "sequence":     int,    # monotonic, per-task, 1-based
        # plus optional fields when relevant:
        "slide_index":  int,
        "slide_total":  int,
        "slide":        dict,
        "error":        str,
        "status":       str,    # back-compat alias used by status SSE consumers
        "step":         str,    # back-compat alias for ``stage``
    }

The emitter is intentionally lightweight and does NOT touch Redis or the DB
itself — it forwards each finished payload to a caller-supplied ``publish_raw``
async callable. The Celery worker provides a Redis-backed publisher; tests
provide an in-memory list. This keeps the unit tests Redis-free and makes
the event contract observable in isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

PublishRaw = Callable[[dict[str, Any]], Awaitable[None]]

# Canonical event types. The frontend timeline filters on these names; if a
# new one is added, the renderer should learn about it explicitly rather than
# silently rendering a generic row.
EVENT_TYPES: tuple[str, ...] = (
    "stage_started",
    "stage_completed",
    "slide_ready",
    "source_found",
    "citation_checked",
    "export_ready",
    "research_note",
    "outline_ready",
    "design_decision",
    "run_cancelled",
    "run_failed",
    "run_succeeded",
)

# Stages we consider "real work". Used so terminal status calls don't get a
# spurious ``stage_completed`` synthesised against a transient marker stage.
_REAL_STAGES = frozenset(
    {"analyze", "search", "strategy", "plan", "generate", "critique", "images", "assemble", "save"}
)

# When the legacy callback supplies one of these explicit ``event`` strings,
# we map it to a canonical event type. ``"slide"`` is the historical wire
# value emitted by the loop; we preserve it for back-compat.
_EXPLICIT_EVENT_MAP: dict[str, str] = {
    "slide": "slide_ready",
    "slide_ready": "slide_ready",
    "source_found": "source_found",
    "citation_checked": "citation_checked",
    "export_ready": "export_ready",
    "research_note": "research_note",
    "outline_ready": "outline_ready",
    "design_decision": "design_decision",
}

_TERMINAL_STATUS_MAP: dict[str, str] = {
    "done": "run_succeeded",
    "failed": "run_failed",
    "cancelled": "run_cancelled",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RunEventEmitter:
    """Adapter producing structured Phase 6R events from the legacy callback."""

    def __init__(self, task_id: str, publish_raw: PublishRaw) -> None:
        self.task_id = task_id
        self._publish_raw = publish_raw
        self._sequence = 0
        self._last_stage: str | None = None
        self._stages_started: set[str] = set()
        self._stages_completed: set[str] = set()
        self._terminal_seen = False

    # ── public API ────────────────────────────────────────────────────────
    async def emit(
        self,
        event_type: str,
        *,
        message: str,
        progress_pct: float,
        stage: str,
        status: str = "running",
        slide_index: int | None = None,
        slide_total: int | None = None,
        slide: dict[str, Any] | None = None,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Emit a single canonical event. Public for direct use by tests / future call sites."""
        if event_type not in EVENT_TYPES:
            # Defensive: unknown event types are still emitted but flagged so
            # the frontend can fall back to a generic row instead of crashing.
            event_type = event_type or "stage_started"
        self._sequence += 1
        payload: dict[str, Any] = {
            "task_id": self.task_id,
            "event": event_type,
            "stage": stage,
            "message": message,
            "progress_pct": float(progress_pct),
            "timestamp": _utcnow_iso(),
            "sequence": self._sequence,
            # Back-compat aliases — older SSE consumers (and the existing
            # Phase 6Q lifecycle/status tests) read these.
            "status": status,
            "step": stage,
        }
        if slide_index is not None:
            payload["slide_index"] = int(slide_index)
        if slide_total is not None:
            payload["slide_total"] = int(slide_total)
        if slide is not None:
            payload["slide"] = slide
        if error is not None:
            payload["error"] = error
        if extra:
            for k, v in extra.items():
                if k not in payload and v is not None:
                    payload[k] = v
        await self._publish_raw(payload)

    async def on_progress(
        self,
        message: str,
        progress_pct: float,
        step: str,
        **extra: Any,
    ) -> None:
        """Adapter that matches the legacy ``ProgressCallback`` signature.

        The agent loop calls this exactly the same way as before; the emitter
        figures out the canonical event type, synthesises ``stage_completed``
        events when the stage changes, and assigns sequence numbers.
        """
        status = str(extra.pop("status", "running"))
        explicit_event = extra.pop("event", None)
        slide = extra.pop("slide", None)
        slide_index = extra.pop("slide_index", None)
        slide_total = extra.pop("slide_total", None)
        error = extra.pop("error", None)

        # 1) Terminal status takes precedence.
        if status in _TERMINAL_STATUS_MAP:
            # Best-effort: close out the last running stage if we never saw a
            # transition past it (e.g. cancel mid-stage).
            if (
                not self._terminal_seen
                and self._last_stage is not None
                and self._last_stage in _REAL_STAGES
                and self._last_stage not in self._stages_completed
            ):
                await self.emit(
                    "stage_completed",
                    message=f"Stage {self._last_stage} finished.",
                    progress_pct=progress_pct,
                    stage=self._last_stage,
                    status="running",
                )
                self._stages_completed.add(self._last_stage)

            self._terminal_seen = True
            await self.emit(
                _TERMINAL_STATUS_MAP[status],
                message=message,
                progress_pct=progress_pct,
                stage=step,
                status=status,
                error=error,
                extra=extra or None,
            )
            return

        # 2) Explicit event types (slide_ready, source_found, …).
        if explicit_event:
            mapped = _EXPLICIT_EVENT_MAP.get(str(explicit_event), str(explicit_event))
            await self.emit(
                mapped,
                message=message,
                progress_pct=progress_pct,
                stage=step,
                status=status,
                slide_index=slide_index,
                slide_total=slide_total,
                slide=slide,
                error=error,
                extra=extra or None,
            )
            return

        # 3) Default: stage_started, with synthetic stage_completed on transition.
        if (
            self._last_stage is not None
            and self._last_stage != step
            and self._last_stage in _REAL_STAGES
            and self._last_stage not in self._stages_completed
        ):
            await self.emit(
                "stage_completed",
                message=f"Stage {self._last_stage} finished.",
                progress_pct=progress_pct,
                stage=self._last_stage,
                status="running",
            )
            self._stages_completed.add(self._last_stage)

        await self.emit(
            "stage_started",
            message=message,
            progress_pct=progress_pct,
            stage=step,
            status=status,
            slide_index=slide_index,
            slide_total=slide_total,
            slide=slide,
            error=error,
            extra=extra or None,
        )
        self._stages_started.add(step)
        self._last_stage = step


__all__ = ["EVENT_TYPES", "RunEventEmitter", "PublishRaw"]
