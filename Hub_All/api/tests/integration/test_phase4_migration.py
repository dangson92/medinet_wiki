"""Phase 4 Plan 04-01 — migration 0002 integration test.

Verify:
1. `alembic upgrade head` chạy thành công trên testcontainer Postgres trống.
2. Index `ix_documents_status_last_heartbeat` tồn tại sau khi apply.
3. Watchdog columns (last_heartbeat, attempts, error_message) có kiểu đúng.
4. `alembic check` không phát hiện drift sau khi apply head (P20 — Plan 02-03).

Test dùng testcontainers Postgres pgvector pg16 (image MANDATORY — alpine
KHÔNG có ext vector). Share container scope=module qua conftest.
"""
from __future__ import annotations

import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer


@pytest.mark.critical
@pytest.mark.integration
def test_phase4_migration_upgrade(
    postgres_container: PostgresContainer,
    alembic_cfg: Config,
) -> None:
    """Alembic upgrade head apply 0001 + 0002 — index ix_documents_status_last_heartbeat tồn tại."""
    # Apply migration head (chạy cả 0001 + 0002).
    asyncio.run(asyncio.to_thread(command.upgrade, alembic_cfg, "head"))

    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    eng = create_engine(sync_url)
    with eng.connect() as conn:
        # 1) Index composite tồn tại
        rows = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename='documents' "
                "ORDER BY indexname"
            )
        ).fetchall()
        index_names = {r[0] for r in rows}
        assert "ix_documents_status_last_heartbeat" in index_names, (
            f"Missing watchdog index — actual: {sorted(index_names)}"
        )

        # 2) Watchdog columns tồn tại đúng kiểu (Phase 2 baseline + Plan 04-01 verify).
        cols = conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name='documents' "
                "AND column_name IN ('last_heartbeat', 'attempts', 'error_message') "
                "ORDER BY column_name"
            )
        ).fetchall()
        col_map = {r[0]: (r[1], r[2]) for r in cols}
        assert "last_heartbeat" in col_map, f"Missing last_heartbeat: {col_map}"
        assert col_map["last_heartbeat"][0] == "timestamp with time zone"
        assert col_map["last_heartbeat"][1] == "YES"  # nullable
        assert "attempts" in col_map
        assert col_map["attempts"][0] == "integer"
        assert col_map["attempts"][1] == "NO"  # NOT NULL default 0
        assert "error_message" in col_map
        assert col_map["error_message"][0] == "text"

        # 3) Status enum CHECK constraint chứa 'failed_unsupported' (R4 Phase 2).
        # Dùng pg_get_constraintdef thay consrc (consrc deprecated pg12+).
        check_defs = conn.execute(
            text(
                "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname='documents' AND c.contype='c'"
            )
        ).fetchall()
        check_text = " ".join(str(d[0]) for d in check_defs)
        assert "failed_unsupported" in check_text, (
            f"Status enum thiếu failed_unsupported: {check_text}"
        )

    eng.dispose()


@pytest.mark.critical
@pytest.mark.integration
def test_phase4_migration_no_drift(
    postgres_container: PostgresContainer,
    alembic_cfg: Config,
) -> None:
    """`alembic check` sau khi upgrade head KHÔNG phát hiện drift (P20)."""
    asyncio.run(asyncio.to_thread(command.upgrade, alembic_cfg, "head"))
    # alembic check — raise CommandError nếu có drift; pass nếu schema match.
    asyncio.run(asyncio.to_thread(command.check, alembic_cfg))


@pytest.mark.critical
@pytest.mark.integration
def test_phase4_downgrade_drop_index(
    postgres_container: PostgresContainer,
    alembic_cfg: Config,
) -> None:
    """Downgrade 0002 → 0001 drop index, baseline còn lại."""
    asyncio.run(asyncio.to_thread(command.upgrade, alembic_cfg, "head"))
    asyncio.run(asyncio.to_thread(command.downgrade, alembic_cfg, "0001"))

    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    eng = create_engine(sync_url)
    with eng.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename='documents' AND indexname='ix_documents_status_last_heartbeat'"
            )
        ).fetchall()
        assert rows == [], "Index Phase 4 vẫn còn sau downgrade — Plan 04-01 downgrade() lỗi"

        # Index 0001 baseline còn lại
        rows2 = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename='documents' AND indexname='ix_documents_hub_id_status'"
            )
        ).fetchall()
        assert len(rows2) == 1, "Index baseline 0001 bị mất sau downgrade"
    eng.dispose()
