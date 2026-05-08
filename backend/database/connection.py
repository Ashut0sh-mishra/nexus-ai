"""Async SQLAlchemy engine + session factory."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings

logger = logging.getLogger("nexus.db")

engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_models() -> None:
    """Create tables on startup if they don't exist (dev convenience).

    Production deployments should use Alembic migrations exclusively.
    """
    from database.models import Base  # local import to avoid circulars

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database.init_ok")
    except Exception as exc:  # pragma: no cover
        logger.warning("database.init_failed", extra={"err": str(exc)})


async def close_engine() -> None:
    await engine.dispose()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an AsyncSession with automatic cleanup."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
