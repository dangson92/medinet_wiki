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
    """downgrade base sau upgrade head -> 10 bang app bi drop (chi con alembic_version).

    Verify ROADMAP Phase 2 success criteria #3 (clean rollback).

    NOTE (deviation Rule 1): Alembic LEAVES `alembic_version` table sau khi
    downgrade base (behavior chuan — version tracking table CANNOT tu drop
    chinh no). Test verify chi 10 bang app bi xoa sach, alembic_version van
    ton tai (rong, 0 row). De clean tuyet doi can DROP TABLE alembic_version
    explicit — KHONG phai trach nhiem cua downgrade base.
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
            "WHERE table_schema='public' AND table_type='BASE TABLE' "
            "ORDER BY table_name"
        )).all()

        # alembic_version sau downgrade base PHAI rong (0 revision tracked)
        version_count = conn.execute(text(
            "SELECT count(*) FROM alembic_version"
        )).scalar()
    eng.dispose()

    table_names = sorted(r[0] for r in rows)
    # Chap nhan alembic_version van ton tai (behavior chuan Alembic).
    # 10 bang app PHAI bi xoa sach.
    assert table_names == ["alembic_version"], (
        f"Downgrade khong clean. Bang app con sot lai: {table_names}"
    )
    assert version_count == 0, (
        f"alembic_version PHAI rong sau downgrade base, co {version_count} row"
    )
