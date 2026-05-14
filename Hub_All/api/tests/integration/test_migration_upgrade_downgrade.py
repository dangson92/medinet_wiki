"""Integration tests: Alembic migration upgrade/downgrade tren Postgres thuc.

Su dung testcontainers pgvector/pgvector:pg16 — KHONG mock asyncpg.
Verify ROADMAP Phase 2 success criteria #1 + #3.

Fixture `postgres_container` + `alembic_cfg` lay tu tests/integration/conftest.py
qua dependency injection — KHONG redeclare trong file nay (tranh shadow scope).
"""
from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer


@pytest.mark.critical
@pytest.mark.integration
def test_upgrade_creates_10_tables(
    postgres_container: PostgresContainer,
    alembic_cfg: Config,
) -> None:
    """upgrade head -> public schema co dung 10 bang app + alembic_version.

    Verify ROADMAP Phase 2 success criteria #1 (10 bang baseline tao OK).
    """
    command.upgrade(alembic_cfg, "head")

    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    eng = create_engine(sync_url)
    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE' "
            "ORDER BY table_name"
        )).all()
    eng.dispose()

    table_names = sorted(r[0] for r in rows)
    expected = sorted([
        "alembic_version",
        "api_keys",
        "audit_logs",
        "chunks",
        "documents",
        "hubs",
        "refresh_tokens",
        "settings",
        "usage_events",
        "user_hubs",
        "users",
    ])
    assert table_names == expected, f"Schema mismatch. Got: {table_names}"


@pytest.mark.critical
@pytest.mark.integration
def test_downgrade_drops_all_clean(
    postgres_container: PostgresContainer,
    alembic_cfg: Config,
) -> None:
    """downgrade base sau upgrade head -> public schema rong (alembic_version cung drop).

    Verify ROADMAP Phase 2 success criteria #3 (clean rollback).
    """
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")

    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    eng = create_engine(sync_url)
    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE'"
        )).all()
    eng.dispose()

    assert len(rows) == 0, f"Downgrade khong clean. Con lai: {[r[0] for r in rows]}"
