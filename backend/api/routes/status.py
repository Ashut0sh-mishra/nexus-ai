"""GET /api/status/{task_id} — Server-Sent Events progress stream."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

import redis.asyncio as redis_async
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from config import settings
from database.connection import SessionLocal
from database.models import Task

logger = logging.getLogger("nexus.api.status")

router = APIRouter()

PROGRESS_CHANNEL_PREFIX = "nexus:task:progress:"
TERMINAL_STATES = {"done", "failed"}


def channel_for(task_id: str) -> str:
    return f"{PROGRESS_CHANNEL_PREFIX}{task_id}"


async def _load_task_snapshot(task_id: str) -> dict | None:
    async with SessionLocal() as session:
        res = await session.execute(select(Task).where(Task.id == task_id))
        task = res.scalar_one_or_none()
        if task is None:
            return None
        return {
            "task_id": task.id,
            "status": task.status,
            "progress_pct": float(task.progress_pct or 0.0),
            "step": task.current_step,
            "message": task.current_step or "Working…",
            "error": task.error_msg,
        }


async def _event_stream(task_id: str) -> AsyncIterator[dict]:
    snapshot = await _load_task_snapshot(task_id)
    if snapshot is None:
        yield {"event": "error", "data": json.dumps({"detail": "Task not found"})}
        return

    # Always emit a snapshot first so clients re-connecting still see state.
    yield {"data": json.dumps(snapshot)}
    if snapshot["status"] in TERMINAL_STATES:
        return

    client = redis_async.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(channel_for(task_id))
        last_heartbeat = asyncio.get_event_loop().time()
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
            now = asyncio.get_event_loop().time()
            if msg and msg.get("type") == "message":
                data = msg.get("data") or "{}"
                yield {"data": data}
                try:
                    parsed = json.loads(data)
                    if parsed.get("status") in TERMINAL_STATES:
                        return
                except json.JSONDecodeError:
                    pass
            elif now - last_heartbeat > 15:
                # Heartbeat to keep proxies from closing the connection.
                yield {"event": "ping", "data": "{}"}
                last_heartbeat = now
                # Re-poll DB in case the worker terminated without publishing.
                snap = await _load_task_snapshot(task_id)
                if snap and snap["status"] in TERMINAL_STATES:
                    yield {"data": json.dumps(snap)}
                    return
    except asyncio.CancelledError:  # pragma: no cover
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("status.stream_error", extra={"task_id": task_id})
        yield {"event": "error", "data": json.dumps({"detail": str(exc)})}
    finally:
        try:
            await pubsub.unsubscribe(channel_for(task_id))
            await pubsub.close()
        except Exception:
            pass
        await client.aclose()


@router.get(
    "/status/{task_id}",
    summary="Subscribe to a task's progress via Server-Sent Events.",
    description=(
        "Streams JSON progress events as the agent loop advances. Each event "
        "may carry `step`, `pct`, `message`, and a partial `slides` array. The "
        "stream closes once `status` becomes `done` or `failed`."
    ),
    responses={
        200: {
            "description": "SSE stream of progress events.",
            "content": {"text/event-stream": {}},
        },
        404: {"description": "Task not found."},
    },
)
async def task_status_stream(task_id: str):
    snap = await _load_task_snapshot(task_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return EventSourceResponse(_event_stream(task_id))
