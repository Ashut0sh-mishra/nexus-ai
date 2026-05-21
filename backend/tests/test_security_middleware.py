"""Phase 6AL — SecurityMiddleware tests.

Covers the production lock-down behaviour:
* API-key gate rejects mismatched / missing X-Nexus-Key on protected routes,
* public paths (health, share, status, docs) bypass the key check,
* the gate is a no-op when NEXUS_API_KEY is empty (local dev),
* per-IP rate limit returns 429 after the window cap.

These tests build a tiny throwaway FastAPI app wired with the real
middleware so we exercise the actual dispatch logic, not a mock.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from config import settings  # noqa: E402
import api.security as security  # noqa: E402
from api.security import SecurityMiddleware  # noqa: E402


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityMiddleware)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/generate")
    async def generate():
        return {"task_id": "t-1", "status": "pending"}

    @app.get("/api/status/{task_id}")
    async def status_(task_id: str):
        return {"task_id": task_id}

    @app.get("/api/slides/{task_id}")
    async def slides(task_id: str):
        return {"task_id": task_id}

    return app


@pytest.fixture
def restore_key():
    """Snapshot + restore the global NEXUS_API_KEY around each test."""
    original = settings.NEXUS_API_KEY
    yield
    settings.NEXUS_API_KEY = original


# ── No-op mode (local dev): empty key → everything passes ──────────────────


def test_gate_is_noop_when_key_empty(restore_key):
    settings.NEXUS_API_KEY = ""
    client = TestClient(_build_app())
    assert client.post("/api/generate").status_code == 200
    assert client.get("/api/slides/abc").status_code == 200


# ── Active mode: protected routes require the exact key ────────────────────


def test_protected_route_rejects_missing_key(restore_key):
    settings.NEXUS_API_KEY = "secret-key-value"
    client = _client_no_raise(_build_app())
    r = client.post("/api/generate")
    assert r.status_code == 403
    assert r.json()["reason"] == "invalid_api_key"


def test_protected_route_rejects_wrong_key(restore_key):
    settings.NEXUS_API_KEY = "secret-key-value"
    client = _client_no_raise(_build_app())
    r = client.post("/api/generate", headers={"X-Nexus-Key": "wrong"})
    assert r.status_code == 403


def test_protected_route_accepts_correct_key(restore_key):
    settings.NEXUS_API_KEY = "secret-key-value"
    client = _client_no_raise(_build_app())
    r = client.post("/api/generate", headers={"X-Nexus-Key": "secret-key-value"})
    assert r.status_code == 200


# ── Public paths bypass the key check even when the gate is active ─────────


def test_health_is_public_when_gate_active(restore_key):
    settings.NEXUS_API_KEY = "secret-key-value"
    client = _client_no_raise(_build_app())
    assert client.get("/api/health").status_code == 200


def test_status_sse_is_public_when_gate_active(restore_key):
    """SSE EventSource cannot send headers, so /api/status is gated by
    task_id (UUID) instead of the shared key."""
    settings.NEXUS_API_KEY = "secret-key-value"
    client = _client_no_raise(_build_app())
    assert client.get("/api/status/some-task-id").status_code == 200


# ── Per-IP rate limit ──────────────────────────────────────────────────────


def test_rate_limit_returns_429_after_cap(restore_key, monkeypatch):
    # The whole lock-down only activates when the key is set; supply the
    # correct key header so requests pass the gate and reach the limiter.
    settings.NEXUS_API_KEY = "secret-key-value"
    monkeypatch.setattr(security, "RATE_LIMIT_PER_HOUR", 3)
    client = _client_no_raise(_build_app())

    headers = {"X-Forwarded-For": "203.0.113.7", "X-Nexus-Key": "secret-key-value"}
    codes = [client.post("/api/generate", headers=headers).status_code for _ in range(4)]
    # First 3 allowed, 4th blocked.
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429


def test_rate_limit_is_per_ip(restore_key, monkeypatch):
    settings.NEXUS_API_KEY = "secret-key-value"
    monkeypatch.setattr(security, "RATE_LIMIT_PER_HOUR", 2)
    client = _client_no_raise(_build_app())

    a = {"X-Forwarded-For": "198.51.100.1", "X-Nexus-Key": "secret-key-value"}
    b = {"X-Forwarded-For": "198.51.100.2", "X-Nexus-Key": "secret-key-value"}
    assert client.post("/api/generate", headers=a).status_code == 200
    assert client.post("/api/generate", headers=a).status_code == 200
    assert client.post("/api/generate", headers=a).status_code == 429
    # Different IP has its own budget.
    assert client.post("/api/generate", headers=b).status_code == 200


def _client_no_raise(app: FastAPI) -> TestClient:
    """TestClient that returns error responses instead of raising."""
    return TestClient(app, raise_server_exceptions=False)
