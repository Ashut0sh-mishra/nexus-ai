"""Auth — JWT issuance/validation, password hashing, Google OIDC verification."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

logger = logging.getLogger("nexus.services.auth")

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd.verify(plain, hashed)
    except Exception:
        return False


class AuthService:
    @staticmethod
    def create_access_token(user_id: str, extra: dict[str, Any] | None = None) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
        }
        if extra:
            payload.update(extra)
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, settings.jwt_secret, algorithms=[settings.JWT_ALGORITHM])
        except JWTError as exc:
            raise ValueError(f"Invalid token: {exc}") from exc

    @staticmethod
    def verify_google_id_token(id_token_str: str) -> dict[str, Any]:
        """Verify a Google-issued ID token. Returns claims dict (sub, email, name, picture)."""
        if not settings.GOOGLE_CLIENT_ID:
            raise ValueError("GOOGLE_CLIENT_ID not configured")
        try:
            from google.auth.transport import requests as g_requests
            from google.oauth2 import id_token as g_id_token
        except ImportError as exc:
            raise RuntimeError(
                "google-auth is not installed. Run: pip install google-auth"
            ) from exc

        request = g_requests.Request()
        info = g_id_token.verify_oauth2_token(
            id_token_str, request, settings.GOOGLE_CLIENT_ID
        )
        if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise ValueError("Invalid token issuer")
        return {
            "sub": info["sub"],
            "email": info.get("email", ""),
            "name": info.get("name", ""),
            "picture": info.get("picture", ""),
            "email_verified": info.get("email_verified", False),
        }
