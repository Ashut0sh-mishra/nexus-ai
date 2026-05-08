"""API key management for SDK / external integrations (PRD §16, §21)."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from database.connection import get_db
from database.models import ApiKey, User
from services.auth_service import _pwd

logger = logging.getLogger("nexus.api.api_keys")
router = APIRouter()


def _serialize(k: ApiKey, *, secret: str | None = None) -> dict[str, Any]:
    out = {
        "id": k.id,
        "name": k.name,
        "key_prefix": k.key_prefix,
        "scopes": k.scopes_json or [],
        "workspace_id": k.workspace_id,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "revoked_at": k.revoked_at.isoformat() if k.revoked_at else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }
    if secret is not None:
        out["secret"] = secret  # returned ONCE on creation
    return out


class ApiKeyCreate(BaseModel):
    name: str = Field(default="default", max_length=128)
    workspace_id: Optional[str] = None
    scopes: list[str] | None = None
    expires_at: Optional[datetime] = None


@router.get("/api-keys", summary="List the current user's API keys.")
async def list_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
        )
    ).scalars().all()
    return [_serialize(k) for k in rows]


@router.post("/api-keys", summary="Create a new API key. Secret is returned once.")
async def create_key(
    payload: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    # Format: nxs_<8 url-safe chars>_<32 url-safe chars>
    prefix_part = secrets.token_urlsafe(6)[:8]
    secret_part = secrets.token_urlsafe(24)[:32]
    secret = f"nxs_{prefix_part}_{secret_part}"
    prefix = secret[:12]  # "nxs_" + 8 chars
    k = ApiKey(
        user_id=user.id,
        workspace_id=payload.workspace_id,
        name=payload.name,
        key_prefix=prefix,
        key_hash=_pwd.hash(secret),
        scopes_json=payload.scopes or [],
        expires_at=payload.expires_at,
    )
    db.add(k)
    await db.commit()
    await db.refresh(k)
    logger.info("api_keys.create", extra={"id": k.id, "user_id": user.id})
    return _serialize(k, secret=secret)


@router.post("/api-keys/{key_id}/rotate", summary="Rotate an API key (returns a new secret).")
async def rotate_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    k = (await db.execute(select(ApiKey).where(ApiKey.id == key_id))).scalar_one_or_none()
    if k is None or k.user_id != user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    prefix_part = secrets.token_urlsafe(6)[:8]
    secret_part = secrets.token_urlsafe(24)[:32]
    secret = f"nxs_{prefix_part}_{secret_part}"
    k.key_prefix = secret[:12]
    k.key_hash = _pwd.hash(secret)
    db.add(k)
    await db.commit()
    await db.refresh(k)
    logger.info("api_keys.rotate", extra={"id": k.id})
    return _serialize(k, secret=secret)


@router.delete("/api-keys/{key_id}", summary="Revoke (and soft-delete) an API key.")
async def revoke_key(
    key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    k = (await db.execute(select(ApiKey).where(ApiKey.id == key_id))).scalar_one_or_none()
    if k is None or k.user_id != user.id:
        raise HTTPException(status_code=404, detail="API key not found")
    k.revoked_at = datetime.utcnow()
    db.add(k)
    await db.commit()
    return {"revoked": key_id}
