"""POST /api/share — create a public share token. GET /api/share/{token} — view."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.connection import get_db
from database.models import ShareToken, SlideDeck, Task

logger = logging.getLogger("nexus.api.share")

router = APIRouter()

DEFAULT_TTL_DAYS = 30


class ShareCreateRequest(BaseModel):
    task_id: str = Field(..., min_length=4)
    ttl_days: int = Field(DEFAULT_TTL_DAYS, ge=1, le=365)


class ShareCreateResponse(BaseModel):
    token: str
    share_url: str
    expires_at: datetime


@router.post("/share", response_model=ShareCreateResponse, status_code=201)
async def create_share(
    payload: ShareCreateRequest, db: AsyncSession = Depends(get_db)
) -> ShareCreateResponse:
    task_res = await db.execute(select(Task).where(Task.id == payload.task_id))
    task = task_res.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "done":
        raise HTTPException(status_code=409, detail="Task not complete yet")

    token = secrets.token_urlsafe(16)
    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.ttl_days)
    share = ShareToken(token=token, task_id=task.id, expires_at=expires_at)
    db.add(share)
    await db.commit()

    share_url = f"{settings.FRONTEND_URL.rstrip('/')}/share/{token}"
    logger.info("share.created", extra={"task_id": task.id, "token": token})
    return ShareCreateResponse(token=token, share_url=share_url, expires_at=expires_at)


@router.get("/share/{token}")
async def view_share(token: str, db: AsyncSession = Depends(get_db)) -> dict:
    res = await db.execute(select(ShareToken).where(ShareToken.token == token))
    share = res.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="Share link not found")
    # SQLite returns naive datetimes; treat them as UTC for comparison.
    expires = share.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires is not None and expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Share link expired")

    deck_res = await db.execute(select(SlideDeck).where(SlideDeck.task_id == share.task_id))
    deck = deck_res.scalar_one_or_none()
    task_res = await db.execute(select(Task).where(Task.id == share.task_id))
    task = task_res.scalar_one_or_none()
    if deck is None or task is None:
        raise HTTPException(status_code=404, detail="Slides no longer available")

    share.views = (share.views or 0) + 1
    db.add(share)
    await db.commit()

    return {
        "topic": task.topic,
        "theme": deck.theme,
        "slide_count": deck.slide_count,
        "slides": deck.slide_data or [],
        "created_at": deck.created_at,
        "views": share.views,
    }
