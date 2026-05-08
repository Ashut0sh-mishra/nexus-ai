"""Brand kit CRUD (PRD §12)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from database.connection import get_db
from database.models import BrandKit, User

logger = logging.getLogger("nexus.api.brand_kits")
router = APIRouter()


class BrandKitIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    workspace_id: str | None = None
    is_default: bool = False
    primary_color: str | None = None
    secondary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    text_color: str | None = None
    palette: list[str] | None = None
    heading_font: str | None = None
    body_font: str | None = None
    logo_url: str | None = None
    industry: str | None = None
    audience: str | None = None
    tone: str | None = None
    voice_guidelines: str | None = None


def _serialize(b: BrandKit) -> dict[str, Any]:
    return {
        "id": b.id,
        "workspace_id": b.workspace_id,
        "user_id": b.user_id,
        "name": b.name,
        "is_default": b.is_default,
        "primary_color": b.primary_color,
        "secondary_color": b.secondary_color,
        "accent_color": b.accent_color,
        "background_color": b.background_color,
        "text_color": b.text_color,
        "palette": b.palette_json or [],
        "heading_font": b.heading_font,
        "body_font": b.body_font,
        "logo_url": b.logo_url,
        "industry": b.industry,
        "audience": b.audience,
        "tone": b.tone,
        "voice_guidelines": b.voice_guidelines,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


@router.get("/brand-kits", summary="List brand kits owned by the current user.")
async def list_brand_kits(
    workspace_id: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    q = select(BrandKit).where(BrandKit.user_id == user.id)
    if workspace_id:
        q = q.where(BrandKit.workspace_id == workspace_id)
    rows = (await db.execute(q.order_by(BrandKit.created_at.desc()))).scalars().all()
    return [_serialize(b) for b in rows]


@router.post("/brand-kits", summary="Create a new brand kit.")
async def create_brand_kit(
    payload: BrandKitIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    palette = data.pop("palette", None)
    b = BrandKit(user_id=user.id, palette_json=palette, **data)
    db.add(b)
    await db.flush()
    if b.is_default:
        # Unset default on siblings.
        await db.execute(
            update(BrandKit)
            .where(BrandKit.user_id == user.id, BrandKit.id != b.id)
            .values(is_default=False)
        )
    await db.commit()
    await db.refresh(b)
    logger.info("brand_kits.create", extra={"id": b.id, "user_id": user.id})
    return _serialize(b)


@router.get("/brand-kits/{kit_id}", summary="Get one brand kit.")
async def get_brand_kit(
    kit_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    b = (await db.execute(select(BrandKit).where(BrandKit.id == kit_id))).scalar_one_or_none()
    if b is None or b.user_id != user.id:
        raise HTTPException(status_code=404, detail="Brand kit not found")
    return _serialize(b)


@router.put("/brand-kits/{kit_id}", summary="Update a brand kit (partial).")
async def update_brand_kit(
    kit_id: str,
    payload: BrandKitIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    b = (await db.execute(select(BrandKit).where(BrandKit.id == kit_id))).scalar_one_or_none()
    if b is None or b.user_id != user.id:
        raise HTTPException(status_code=404, detail="Brand kit not found")
    data = payload.model_dump(exclude_none=True)
    palette = data.pop("palette", None)
    if palette is not None:
        b.palette_json = palette
    for k, v in data.items():
        setattr(b, k, v)
    db.add(b)
    if b.is_default:
        await db.execute(
            update(BrandKit)
            .where(BrandKit.user_id == user.id, BrandKit.id != b.id)
            .values(is_default=False)
        )
    await db.commit()
    await db.refresh(b)
    return _serialize(b)


@router.delete("/brand-kits/{kit_id}", summary="Delete a brand kit.")
async def delete_brand_kit(
    kit_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    b = (await db.execute(select(BrandKit).where(BrandKit.id == kit_id))).scalar_one_or_none()
    if b is None or b.user_id != user.id:
        raise HTTPException(status_code=404, detail="Brand kit not found")
    await db.delete(b)
    await db.commit()
    return {"deleted": kit_id}
