"""Webhook subscriptions and dispatch (PRD §16).

Events emitted by the agent loop:

- ``deck.created``    — task was created
- ``deck.completed``  — generation finished successfully
- ``deck.failed``     — generation failed
- ``slide.updated``   — a slide was edited or regenerated

Use ``dispatch_event(db, event, payload, user_id=..., workspace_id=...)`` from
elsewhere in the codebase to fan out to every subscribed webhook.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from database.connection import SessionLocal, get_db
from database.models import User, Webhook

logger = logging.getLogger("nexus.api.webhooks")
router = APIRouter()


VALID_EVENTS = {"deck.created", "deck.completed", "deck.failed", "slide.updated"}


def _serialize(w: Webhook) -> dict[str, Any]:
    return {
        "id": w.id,
        "url": w.url,
        "events": w.events_json or [],
        "active": w.active,
        "workspace_id": w.workspace_id,
        "secret_preview": (w.secret[:6] + "…") if w.secret else None,
        "last_delivery_at": w.last_delivery_at.isoformat() if w.last_delivery_at else None,
        "last_status": w.last_status,
        "failure_count": w.failure_count,
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


class WebhookCreate(BaseModel):
    url: str = Field(..., max_length=2048)
    events: list[str] = Field(default_factory=lambda: ["deck.completed", "deck.failed"])
    workspace_id: Optional[str] = None
    active: bool = True


@router.get("/webhooks", summary="List the user's webhook subscriptions.")
async def list_webhooks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(select(Webhook).where(Webhook.user_id == user.id))
    ).scalars().all()
    return [_serialize(w) for w in rows]


@router.post("/webhooks", summary="Create a webhook subscription. Secret is returned once.")
async def create_webhook(
    payload: WebhookCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    bad = [e for e in payload.events if e not in VALID_EVENTS]
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown events: {bad}. Allowed: {sorted(VALID_EVENTS)}",
        )
    if not (payload.url.startswith("http://") or payload.url.startswith("https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)://")
    secret = secrets.token_urlsafe(24)
    w = Webhook(
        user_id=user.id,
        workspace_id=payload.workspace_id,
        url=payload.url,
        secret=secret,
        events_json=payload.events,
        active=payload.active,
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    out = _serialize(w)
    out["secret"] = secret
    return out


@router.delete("/webhooks/{webhook_id}", summary="Delete a webhook subscription.")
async def delete_webhook(
    webhook_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    w = (await db.execute(select(Webhook).where(Webhook.id == webhook_id))).scalar_one_or_none()
    if w is None or w.user_id != user.id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(w)
    await db.commit()
    return {"deleted": webhook_id}


@router.post("/webhooks/{webhook_id}/test", summary="Send a test payload to a webhook URL.")
async def test_webhook(
    webhook_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    w = (await db.execute(select(Webhook).where(Webhook.id == webhook_id))).scalar_one_or_none()
    if w is None or w.user_id != user.id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    status_code = await _deliver(w, "webhook.test", {"message": "hello from NEXUS"})
    return {"status": status_code}


# --------------------------------------------------------------------------- #
# Outbound dispatcher — call from anywhere
# --------------------------------------------------------------------------- #
async def _deliver(w: Webhook, event: str, payload: dict[str, Any]) -> int:
    """Send a single signed POST. Returns HTTP status code (or 0 on error)."""
    body = json.dumps(
        {"event": event, "data": payload, "timestamp": int(time.time())},
        separators=(",", ":"),
    ).encode()
    sig = ""
    if w.secret:
        sig = hmac.new(w.secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "NEXUS-Webhook/1.0",
        "X-Nexus-Event": event,
        "X-Nexus-Signature": f"sha256={sig}",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(w.url, content=body, headers=headers)
            return resp.status_code
    except Exception as exc:
        logger.warning("webhook.delivery_failed", extra={"id": w.id, "err": str(exc)})
        return 0


async def dispatch_event(
    event: str,
    payload: dict[str, Any],
    *,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> None:
    """Fire-and-forget: deliver ``event`` to every matching active webhook.

    Safe to call from any async context. Opens its own DB session so callers
    don't have to thread one through.
    """
    if event not in VALID_EVENTS:
        return
    try:
        async with SessionLocal() as db:
            q = select(Webhook).where(Webhook.active == True)  # noqa: E712
            if user_id:
                q = q.where(Webhook.user_id == user_id)
            if workspace_id:
                q = q.where(Webhook.workspace_id == workspace_id)
            hooks = (await db.execute(q)).scalars().all()
            tasks: list[asyncio.Task] = []
            for w in hooks:
                if w.events_json and event not in w.events_json:
                    continue
                tasks.append(asyncio.create_task(_deliver_and_record(w.id, event, payload)))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as exc:  # pragma: no cover
        logger.warning("webhook.dispatch_failed", extra={"event": event, "err": str(exc)})


async def _deliver_and_record(webhook_id: str, event: str, payload: dict[str, Any]) -> None:
    async with SessionLocal() as db:
        w = (await db.execute(select(Webhook).where(Webhook.id == webhook_id))).scalar_one_or_none()
        if w is None:
            return
        status = await _deliver(w, event, payload)
        w.last_delivery_at = datetime.utcnow()
        w.last_status = status
        if status == 0 or status >= 400:
            w.failure_count = (w.failure_count or 0) + 1
        else:
            w.failure_count = 0
        db.add(w)
        await db.commit()
