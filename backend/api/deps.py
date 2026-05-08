"""Shared FastAPI dependencies for authenticated routes (PRD §21)."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import ApiKey, User
from services.auth_service import AuthService

_auth = AuthService()


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the calling user from a bearer token *or* an API key.

    Bearer auth is used by the web UI; API key auth is used by the SDK.
    Returns 401 if neither is present or valid.
    """
    # 1) JWT bearer
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            user_id = _auth.decode_token(token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid bearer token") from exc
        res = await db.execute(select(User).where(User.id == user_id))
        user = res.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    # 2) API key (X-API-Key: nxs_<prefix>_<secret>)
    if x_api_key:
        # Find by prefix to avoid scanning the whole table.
        prefix = x_api_key[:12]
        res = await db.execute(select(ApiKey).where(ApiKey.key_prefix == prefix))
        candidates = list(res.scalars().all())
        from services.auth_service import _pwd
        for k in candidates:
            if k.revoked_at is not None:
                continue
            try:
                if _pwd.verify(x_api_key, k.key_hash):
                    user = (
                        await db.execute(select(User).where(User.id == k.user_id))
                    ).scalar_one_or_none()
                    if user is None:
                        raise HTTPException(status_code=401, detail="User not found")
                    return user
            except Exception:
                continue

    raise HTTPException(status_code=401, detail="Authentication required")


async def get_optional_user(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Same as ``get_current_user`` but returns ``None`` instead of 401."""
    if not authorization and not x_api_key:
        return None
    try:
        return await get_current_user(authorization, x_api_key, db)  # type: ignore[arg-type]
    except HTTPException:
        return None
