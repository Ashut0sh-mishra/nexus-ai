"""Pytest fixtures for the NEXUS backend integration tests.

Drives the FastAPI app through `httpx.ASGITransport` against a throw-away
SQLite database. The Celery `.delay()` call inside `POST /api/generate` is
stubbed out so no broker is required.
"""

from __future__ import annotations

import os
import sys
import tempfile
import types
from pathlib import Path

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Environment must be configured BEFORE importing `main` / `config`.
# ---------------------------------------------------------------------------
_TMP_DIR = Path(tempfile.mkdtemp(prefix="nexus-test-"))
TEST_DB_PATH = _TMP_DIR / "nexus_test.db"

os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "x" * 32
os.environ["GROQ_API_KEY"] = "test-dummy-key"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["LOG_LEVEL"] = "WARNING"


# ---------------------------------------------------------------------------
# Stub `workers.tasks` BEFORE the FastAPI app imports it.
# ---------------------------------------------------------------------------
_workers_pkg = types.ModuleType("workers")
_workers_pkg.__path__ = []
_workers_tasks = types.ModuleType("workers.tasks")


class _StubTask:
    name = "nexus.run_generation_task"

    def delay(self, *args, **kwargs):
        return types.SimpleNamespace(id="stub-task")

    def apply_async(self, *args, **kwargs):
        return types.SimpleNamespace(id="stub-task")


_workers_tasks.run_generation_task = _StubTask()
sys.modules["workers"] = _workers_pkg
sys.modules["workers.tasks"] = _workers_tasks


# ---------------------------------------------------------------------------
# Import after env + stubs are in place.
# ---------------------------------------------------------------------------
from httpx import ASGITransport, AsyncClient  # noqa: E402

from database.connection import SessionLocal, close_engine, engine  # noqa: E402
from database.models import Base  # noqa: E402
from main import app  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_database():
    """Create the schema once on the shared SessionLocal engine, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await close_engine()
    try:
        TEST_DB_PATH.unlink(missing_ok=True)
    except OSError:
        pass


@pytest_asyncio.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture()
async def db_session():
    async with SessionLocal() as session:
        yield session
