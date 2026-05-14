"""Shared fixtures cho integration tests Phase 2 (Plan 05).

Dinh nghia source-of-truth cho 2 fixture dung chung giua 3 file test:
- test_migration_upgrade_downgrade.py
- test_chunks_hnsw_cosine_ops.py
- test_alembic_ignores_cocoindex_schema.py

KHONG redeclare fixture trong test file — pytest auto-discover qua conftest.

Yeu cau prereq:
- Docker Desktop running (testcontainers tu pull image `pgvector/pgvector:pg16`).
- Image `pgvector/pgvector:pg16` la MANDATORY (P17 — KHONG postgres:16-alpine vi
  alpine khong co ext vector → CREATE EXTENSION fail).
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def postgres_container() -> Iterator[PostgresContainer]:
    """Postgres 16 + pgvector ext + pgcrypto ext (scope module — share giua test cung module).

    Image `pgvector/pgvector:pg16` MANDATORY:
    - postgres:16-alpine khong co binary pgvector → CREATE EXTENSION vector FAIL.
    - pgvector/pgvector:pg16 la official image, build voi ext vector san sang.

    `driver=None` ngam dinh `postgresql+psycopg2://` (sync driver — psycopg2-binary).
    Async migration test dung asyncpg qua DSN replace trong fixture `alembic_cfg`.
    """
    with PostgresContainer("pgvector/pgvector:pg16", driver=None) as pg:
        sync_url = pg.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql://"
        )
        eng = create_engine(sync_url)
        with eng.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        eng.dispose()
        yield pg


@pytest.fixture
def alembic_cfg(
    postgres_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> Config:
    """Alembic Config + inject env vars cho app.config.get_settings().

    Scope function (per-test) de:
    - monkeypatch.setenv cleanup tu dong sau moi test.
    - get_settings.cache_clear() refresh DSN giua test (vi @lru_cache).
    """
    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://")

    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("COCOINDEX_DATABASE_URL", sync_url)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("APP_ENV", "dev")

    from app.config import get_settings
    get_settings.cache_clear()

    cfg_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    return Config(str(cfg_path))
