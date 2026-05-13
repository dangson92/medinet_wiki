"""SQLAlchemy 2.0 async engine + session factory + FastAPI dependency.

Vòng đời:
  - FastAPI lifespan startup → init_engine(settings)
  - Mỗi request → Depends(get_session) inject AsyncSession
  - FastAPI lifespan shutdown → dispose_engine()

Phase 2 (Plan 01) chỉ define API; Phase 3 (Auth) sẽ wire init_engine vào lifespan.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> AsyncEngine:
    """Khởi tạo async engine + session factory (gọi 1 lần ở lifespan startup).

    DSN `postgresql+asyncpg://...` (SQLAlchemy parse, async driver asyncpg).
    Pool: min 2, max 10 (đủ cho M2 < 100 concurrent). `pool_pre_ping=True` để
    tránh stale connection sau Postgres restart.
    """
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    _engine = create_async_engine(
        settings.database_url,
        pool_size=10,
        max_overflow=5,
        pool_pre_ping=True,
        echo=False,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return _engine


async def dispose_engine() -> None:
    """Đóng pool (gọi ở lifespan shutdown)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_engine() -> AsyncEngine:
    """Truy cập engine sau khi đã init (raise nếu chưa init)."""
    if _engine is None:
        raise RuntimeError(
            "DB engine chưa init. Gọi init_engine(settings) trong lifespan startup."
        )
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yield AsyncSession scope per-request.

    Auto-commit nếu handler không raise, rollback nếu có exception.
    """
    if _session_factory is None:
        raise RuntimeError(
            "DB session factory chưa init. Gọi init_engine(settings) trong lifespan."
        )
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
