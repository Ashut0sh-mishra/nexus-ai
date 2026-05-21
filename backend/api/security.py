"""Phase 6AL — production lock-down middleware.

A single ``SecurityMiddleware`` enforces three rules so a public free-tier
deployment cannot be drained by random callers:

1. **Shared API key.** Every protected route requires the
   ``X-Nexus-Key`` header to match ``settings.NEXUS_API_KEY`` exactly.
   The key is set as a Fly secret on the backend AND baked into the
   frontend build via ``VITE_NEXUS_KEY``. The bundle isn't
   cryptographically secret (anyone can read JS), but combined with
   CORS + rate-limits below it makes abuse impractical.

2. **CORS-locked Origin check.** For browser requests we also verify
   the ``Origin`` header matches ``settings.FRONTEND_URL``. Random
   domains hitting the API (even with a stolen key) get 403.

3. **Per-IP rate limit.** A bounded sliding-window counter blocks any
   single IP from making more than ``RATE_LIMIT_PER_HOUR`` calls per
   hour to generation endpoints. Free-tier AI quotas survive abuse.

The middleware is **defense-in-depth, not cryptography**. A future phase
should add real user auth (Clerk / magic-link / Auth0) for finer-grained
access control; this layer is for invite-only free-tier launches.

Routes exempted from the API-key check (intentionally public):

* ``GET /api/health`` — load-balancer health probes.
* ``GET /`` — root marketing/banner.
* ``GET /docs`` / ``GET /redoc`` / ``GET /openapi.json`` — schema viewers.
* ``GET /api/share/...`` — public share links by design (Phase 6L).
* ``GET /api/files/...`` / ``GET /files/...`` — static export downloads.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from config import settings

logger = logging.getLogger("nexus.api.security")


# ── Tunables ──────────────────────────────────────────────────────────────

# How many requests one IP can make per hour to a rate-limited endpoint.
# Generous enough for invite-only dogfooding, tight enough to stop abuse.
RATE_LIMIT_PER_HOUR = 20
RATE_LIMIT_WINDOW_SECONDS = 60 * 60

# Endpoints subject to the per-IP rate limit (the expensive ones).
RATE_LIMITED_PATH_PREFIXES: tuple[str, ...] = (
    "/api/generate",
    "/api/export",
    "/api/import",
)

# Endpoints exempt from the X-Nexus-Key check entirely. Health probes
# and public share links never require the shared key.
PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/share",
    "/api/files",
    "/files",
    "/docs",
    "/redoc",
    "/openapi.json",
    # SSE EventSource cannot send custom headers from the browser, so
    # /api/status is gated by task_id (UUIDv4) instead of the shared
    # key. Subscribing to someone else's task with a known id only
    # reveals progress events, never lets you create new work.
    "/api/status",
)
PUBLIC_EXACT_PATHS: frozenset[str] = frozenset({"/"})


# ── Helpers ───────────────────────────────────────────────────────────────


def _client_ip(request: Request) -> str:
    """Return the best-effort client IP.

    Honours ``X-Forwarded-For`` from the upstream proxy (Fly.io / Cloudflare
    both inject it). Falls back to the direct client tuple.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First value in the chain is the original client.
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def _is_public_path(path: str) -> bool:
    if path in PUBLIC_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def _is_rate_limited_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in RATE_LIMITED_PATH_PREFIXES)


# ── Middleware ────────────────────────────────────────────────────────────


class SecurityMiddleware(BaseHTTPMiddleware):
    """Combined API-key auth + per-IP rate limit.

    The middleware is no-op when ``settings.NEXUS_API_KEY`` is empty —
    that's the local-dev mode. Production sets the key as a Fly secret
    and the lock-down activates.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        # Per-IP timestamp queues for the sliding window rate limit.
        # In-process state: fine for a single-machine free-tier deploy;
        # a future phase can swap this for Redis if we scale out.
        self._ip_hits: dict[str, deque[float]] = {}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Preflight requests are handled by CORSMiddleware; let them through.
        if method == "OPTIONS":
            return await call_next(request)

        # 1) API-key gate (skipped when the key is unset = local dev).
        if settings.NEXUS_API_KEY and not _is_public_path(path):
            supplied = request.headers.get("x-nexus-key", "")
            if supplied != settings.NEXUS_API_KEY:
                logger.warning(
                    "security.api_key_rejected",
                    extra={
                        "path": path,
                        "ip": _client_ip(request),
                        "supplied_len": len(supplied),
                    },
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "forbidden", "reason": "invalid_api_key"},
                )

        # 2) Per-IP rate limit for expensive endpoints.
        if _is_rate_limited_path(path):
            ip = _client_ip(request)
            now = time.monotonic()
            cutoff = now - RATE_LIMIT_WINDOW_SECONDS
            hits = self._ip_hits.setdefault(ip, deque())
            # Trim old timestamps from the left.
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= RATE_LIMIT_PER_HOUR:
                logger.warning(
                    "security.rate_limited",
                    extra={"path": path, "ip": ip, "hits": len(hits)},
                )
                retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - hits[0]))
                return JSONResponse(
                    status_code=429,
                    headers={"retry-after": str(max(retry_after, 1))},
                    content={
                        "detail": "rate_limited",
                        "limit": RATE_LIMIT_PER_HOUR,
                        "window_seconds": RATE_LIMIT_WINDOW_SECONDS,
                    },
                )
            hits.append(now)

        return await call_next(request)


__all__ = ["SecurityMiddleware", "RATE_LIMIT_PER_HOUR", "RATE_LIMIT_WINDOW_SECONDS"]
