"""Auth endpoints — register, login (JWT), Google OAuth, /me."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.connection import get_db
from database.models import User
from services.auth_service import AuthService, hash_password, verify_password

logger = logging.getLogger("nexus.api.auth")

router = APIRouter()
auth_svc = AuthService()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str | None = Field(None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=20)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str | None = None
    plan: str
    credits_used: int


def _serialize(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "plan": u.plan,
        "credits_used": u.credits_used,
    }


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=payload.email.lower(),
        name=payload.name,
        api_key_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = auth_svc.create_access_token(user.id)
    logger.info("auth.register", extra={"user_id": user.id})
    return TokenResponse(access_token=token, user=_serialize(user))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    res = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = res.scalar_one_or_none()
    if user is None or not user.api_key_hash or not verify_password(
        payload.password, user.api_key_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = auth_svc.create_access_token(user.id)
    return TokenResponse(access_token=token, user=_serialize(user))


@router.post("/google", response_model=TokenResponse)
async def google_login(
    payload: GoogleLoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    if not settings.has_google_oauth:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured (set GOOGLE_CLIENT_ID).",
        )
    try:
        info = await auth_svc.verify_google_id_token(payload.id_token)
    except Exception as exc:
        logger.warning("auth.google_invalid_token", extra={"err": str(exc)})
        raise HTTPException(status_code=401, detail="Invalid Google token") from exc

    email = info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google token missing email")

    res = await db.execute(select(User).where(User.email == email.lower()))
    user = res.scalar_one_or_none()
    if user is None:
        user = User(
            email=email.lower(),
            name=info.get("name"),
            google_id=info.get("sub"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.google_id:
        user.google_id = info.get("sub")
        db.add(user)
        await db.commit()

    token = auth_svc.create_access_token(user.id)
    return TokenResponse(access_token=token, user=_serialize(user))


@router.get("/me", response_model=UserOut)
async def me(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        user_id = auth_svc.decode_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(**_serialize(user))
