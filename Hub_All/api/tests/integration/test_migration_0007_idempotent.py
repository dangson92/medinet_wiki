"""Integration test 0007_document_versions migration — Plan 05-01 VER-01.

5 test cover ROADMAP Phase 5 success criterion #1:
1. upgrade_creates_table_with_15_columns: alembic upgrade head + verify 15 cột exact.
2. upgrade_idempotent_re_run: alembic upgrade head × 2 lần PASS (introspect skip).
3. downgrade_drops_table: alembic downgrade -1 PASS + table + index bị DROP.
4. unique_constraint_enforces_doc_ver: INSERT duplicate (doc_id, ver_num) → fail.
5. check_constraint_rejects_invalid_change_type: INSERT change_type invalid → fail.

SAFETY-CRITICAL DSN injection pattern (Plan 01-03 v3.1 Iter 1 fix I-01 + I-02 carry forward):
- monkeypatch env DATABASE_URL + get_settings.cache_clear() — KHÔNG dùng
  Config.set_main_option("sqlalchemy.url", ...) vì env.py:185-191 runtime OVERRIDE
  → caller's set_main_option BỊ IGNORE → test apply migration vào DB .env vd
  medinet_central, SAFETY BLOCKER (data loss risk).

Reuse:
- postgres_container fixture (conftest.py:42-186 session-scoped).
- testcontainers.postgres + asyncpg (Plan 04-02 v3.1 carry forward).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from testcontainers.postgres import PostgresContainer


# === SAFETY DSN injection fixture (Plan 01-03 v3.1 Iter 1 fix carry forward) ===

@pytest.fixture
def alembic_isolated_dsn(
    postgres_container: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    """SAFETY-CRITICAL: monkeypatch env DATABASE_URL + clear get_settings cache.

    KHÔNG dùng Config.set_main_option("sqlalchemy.url", ...) — env.py:185-191
    runtime OVERRIDE từ get_settings().database_url → caller's set_main_option
    BỊ IGNORE → test apply migration vào DB .env vd medinet_central, SAFETY
    BLOCKER (Plan 01-03 v3.1 Iter 1 fix I-01 + I-02).

    Returns:
        DSN postgresql:// (async-driver-compatible).
    """
    dsn = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    # env.py xử lý async natively — giữ postgresql:// prefix (KHÔNG cần asyncpg suffix).
    # Settings validator v3.0 Plan 01-02 _enforce_hub_dsn_match check segment cuối
    # endswith /medinet_central khi HUB_NAME=central (default). postgres_container
    # fixture đã pre-create DB medinet_central với pgvector + pgcrypto ext.
    central_dsn = dsn.rsplit("/", 1)[0] + "/medinet_central"
    async_dsn = central_dsn.replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    monkeypatch.setenv("DATABASE_URL", async_dsn)
    monkeypatch.setenv("APP_ENV", "dev")

    # Clear get_settings cache — force re-read DATABASE_URL từ env mới patch.
    from app.config import get_settings
    get_settings.cache_clear()

    yield central_dsn

    # Cleanup: clear cache lại để test sau KHÔNG bị stale.
    get_settings.cache_clear()


@pytest.fixture
def alembic_cfg_for_test(alembic_isolated_dsn: str) -> Config:
    """Alembic Config trỏ tới alembic.ini repo + DSN injection qua env.

    KHÔNG dùng `alembic_cfg` từ conftest.py vì conftest scope module-fixed
    apply head 1 lần; test idempotent + downgrade cần fresh Config per-test.
    """
    _ = alembic_isolated_dsn  # trigger fixture monkeypatch env
    repo_root = Path(__file__).resolve().parents[2]  # tests/integration/ → api/
    alembic_ini = repo_root / "alembic.ini"
    assert alembic_ini.exists(), f"alembic.ini not found at {alembic_ini}"
    cfg = Config(str(alembic_ini))
    # KHÔNG set sqlalchemy.url ở đây — env.py:185-191 sẽ override từ env DATABASE_URL.
    return cfg


# === Helper: reset DB to base state trước mỗi test ===

async def _reset_db_to_base(dsn: str) -> None:
    """Drop alembic_version + tất cả schema table — fresh state cho test isolation."""
    conn = await asyncpg.connect(dsn)
    try:
        # Drop schema public CASCADE — fresh state (testcontainer dùng được vì DB ephemeral).
        await conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        await conn.execute("CREATE SCHEMA public")
        await conn.execute("GRANT ALL ON SCHEMA public TO public")
        # Re-enable extensions (postgres_container fixture đã enable nhưng schema public
        # vừa CASCADE drop → extension cũng bị drop nếu được create trong public).
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    finally:
        await conn.close()


# === Test 1: upgrade creates table với 15 cột exact ===

@pytest.mark.critical
@pytest.mark.integration
def test_upgrade_creates_table_with_15_columns(
    alembic_isolated_dsn: str,
    alembic_cfg_for_test: Config,
) -> None:
    """VER-01: alembic upgrade head → document_versions table tồn tại + 15 cột exact."""
    asyncio.run(_reset_db_to_base(alembic_isolated_dsn))

    # Apply migration head (sequential 0001 → 0007).
    command.upgrade(alembic_cfg_for_test, "head")

    # Verify table + 15 cột exact (async asyncpg query).
    async def _verify() -> None:
        conn = await asyncpg.connect(alembic_isolated_dsn)
        try:
            # Check table exists
            row = await conn.fetchrow(
                "SELECT to_regclass('document_versions') AS oid"
            )
            assert row["oid"] is not None, "document_versions table missing after upgrade"

            # Check 15 cột exact (information_schema query)
            cols = await conn.fetch(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'document_versions' "
                "ORDER BY ordinal_position"
            )
            col_names = [c["column_name"] for c in cols]
            expected = {
                "id", "document_id", "version_number", "is_original",
                "name", "file_type", "file_size", "file_path",
                "file_hash", "extractor_used", "chunk_count",
                "change_type", "change_note", "created_by", "created_at",
            }
            actual = set(col_names)
            missing = expected - actual
            assert not missing, f"document_versions missing columns: {missing}"
            assert len(col_names) == 15, (
                f"document_versions should have 15 explicit columns (DocumentVersionAPI interface), got {len(col_names)}: {col_names}"
            )

            # Check UNIQUE constraint exists
            uniq = await conn.fetchrow(
                "SELECT conname FROM pg_constraint "
                "WHERE conname = 'uq_document_versions_doc_ver'"
            )
            assert uniq is not None, "UNIQUE constraint uq_document_versions_doc_ver missing"

            # Check INDEX exists
            idx = await conn.fetchrow(
                "SELECT indexname FROM pg_indexes "
                "WHERE indexname = 'ix_document_versions_document_id'"
            )
            assert idx is not None, "INDEX ix_document_versions_document_id missing"

            # Check CHECK constraint exists.
            # Naming convention từ app/db/base.py NAMING_CONVENTION:
            #   "ck": "ck_%(table_name)s_%(constraint_name)s"
            # → SQLAlchemy auto-prefix `ck_{table}_` vào tham số `name=` của
            # CheckConstraint. Migration source dùng name="ck_document_versions_change_type"
            # nên runtime conname là `ck_document_versions_ck_document_versions_change_type`
            # (double prefix). Pattern này giống Plan 01-01 0006 log show
            # `ck_users_ck_users_role_enum` (introspect runtime). LIKE match cả 2
            # form để test resilient nếu naming convention thay đổi tương lai.
            chk = await conn.fetchrow(
                "SELECT conname FROM pg_constraint "
                "WHERE conname LIKE '%ck_document_versions_change_type'"
            )
            assert chk is not None, (
                "CHECK constraint matching '%ck_document_versions_change_type' missing"
            )
        finally:
            await conn.close()

    asyncio.run(_verify())


# === Test 2: upgrade idempotent — re-run 2 lần PASS ===

@pytest.mark.critical
@pytest.mark.integration
def test_upgrade_idempotent_re_run(
    alembic_isolated_dsn: str,
    alembic_cfg_for_test: Config,
) -> None:
    """VER-01: alembic upgrade head × 2 lần → lần 2 PASS (introspect skip-guard)."""
    asyncio.run(_reset_db_to_base(alembic_isolated_dsn))

    # Run 1 — apply migrations 0001 → 0007
    command.upgrade(alembic_cfg_for_test, "head")

    # Run 2 — re-run head; KHÔNG fail (Alembic detect already at head + 0007 introspect skip).
    command.upgrade(alembic_cfg_for_test, "head")

    # Verify table vẫn tồn tại
    async def _verify() -> None:
        conn = await asyncpg.connect(alembic_isolated_dsn)
        try:
            row = await conn.fetchrow(
                "SELECT to_regclass('document_versions') AS oid"
            )
            assert row["oid"] is not None, "document_versions table missing after re-run"
        finally:
            await conn.close()

    asyncio.run(_verify())


# === Test 3: downgrade drops table ===

@pytest.mark.critical
@pytest.mark.integration
def test_downgrade_drops_table(
    alembic_isolated_dsn: str,
    alembic_cfg_for_test: Config,
) -> None:
    """VER-01: alembic upgrade head + downgrade -1 → document_versions bị DROP + index DROP."""
    asyncio.run(_reset_db_to_base(alembic_isolated_dsn))

    # Apply migrations + verify table tồn tại
    command.upgrade(alembic_cfg_for_test, "head")

    # Downgrade -1 → revert 0007 → 0006
    command.downgrade(alembic_cfg_for_test, "-1")

    # Verify table + index bị DROP
    async def _verify() -> None:
        conn = await asyncpg.connect(alembic_isolated_dsn)
        try:
            row = await conn.fetchrow(
                "SELECT to_regclass('document_versions') AS oid"
            )
            assert row["oid"] is None, (
                "document_versions table should be DROPPED after downgrade -1"
            )

            idx = await conn.fetchrow(
                "SELECT indexname FROM pg_indexes "
                "WHERE indexname = 'ix_document_versions_document_id'"
            )
            assert idx is None, "INDEX should be DROPPED after downgrade -1"
        finally:
            await conn.close()

    asyncio.run(_verify())


# === Test 4: UNIQUE constraint enforces (document_id, version_number) ===

@pytest.mark.critical
@pytest.mark.integration
def test_unique_constraint_enforces_doc_ver(
    alembic_isolated_dsn: str,
    alembic_cfg_for_test: Config,
) -> None:
    """VER-01: UNIQUE (document_id, version_number) — INSERT duplicate → fail."""
    asyncio.run(_reset_db_to_base(alembic_isolated_dsn))
    command.upgrade(alembic_cfg_for_test, "head")

    async def _verify() -> None:
        conn = await asyncpg.connect(alembic_isolated_dsn)
        try:
            # Seed 1 hub + 1 document để FK satisfy
            hub_id = "00000000-0000-0000-0000-000000000001"
            doc_id = "00000000-0000-0000-0000-000000000002"
            # INSERT hubs: NOT NULL phải gồm id + slug + name + code + subdomain
            # (per migrations 0001 baseline + 0003 reconcile — subdomain server_default
            # dropped sau backfill row mới phải truyền tường minh).
            await conn.execute(
                "INSERT INTO hubs (id, slug, code, name, subdomain, status, is_active, created_at) "
                "VALUES ($1::uuid, 'test', 'test', 'Test Hub', 'test', 'active', TRUE, NOW()) "
                "ON CONFLICT DO NOTHING",
                hub_id,
            )
            await conn.execute(
                "INSERT INTO documents (id, hub_id, filename, file_path, file_size_bytes, "
                "mime_type, status, created_at, updated_at) "
                "VALUES ($1::uuid, $2::uuid, 'test.docx', '/tmp/test.docx', 1024, "
                "'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'pending', NOW(), NOW()) "
                "ON CONFLICT DO NOTHING",
                doc_id, hub_id,
            )

            # INSERT version 1 — OK
            await conn.execute(
                "INSERT INTO document_versions "
                "(document_id, version_number, is_original, name, file_type, file_size, file_path, change_type) "
                "VALUES ($1::uuid, 1, true, 'test.docx', 'docx', 1024, '/tmp/test.docx', 'reupload')",
                doc_id,
            )

            # INSERT version 1 lần 2 (cùng doc_id, version_number) → UniqueViolationError
            with pytest.raises(asyncpg.exceptions.UniqueViolationError):
                await conn.execute(
                    "INSERT INTO document_versions "
                    "(document_id, version_number, is_original, name, file_type, file_size, file_path, change_type) "
                    "VALUES ($1::uuid, 1, true, 'test.docx', 'docx', 1024, '/tmp/test.docx', 'reupload')",
                    doc_id,
                )
        finally:
            await conn.close()

    asyncio.run(_verify())


# === Test 5: CHECK constraint rejects invalid change_type ===

@pytest.mark.critical
@pytest.mark.integration
def test_check_constraint_rejects_invalid_change_type(
    alembic_isolated_dsn: str,
    alembic_cfg_for_test: Config,
) -> None:
    """VER-01: CHECK change_type IN 4 value — INSERT invalid → fail."""
    asyncio.run(_reset_db_to_base(alembic_isolated_dsn))
    command.upgrade(alembic_cfg_for_test, "head")

    async def _verify() -> None:
        conn = await asyncpg.connect(alembic_isolated_dsn)
        try:
            hub_id = "00000000-0000-0000-0000-000000000003"
            doc_id = "00000000-0000-0000-0000-000000000004"
            # INSERT hubs: cùng schema bắt buộc id + slug + code + name + subdomain (0001 + 0003).
            await conn.execute(
                "INSERT INTO hubs (id, slug, code, name, subdomain, status, is_active, created_at) "
                "VALUES ($1::uuid, 'test2', 'test2', 'Test Hub 2', 'test2', 'active', TRUE, NOW()) "
                "ON CONFLICT DO NOTHING",
                hub_id,
            )
            await conn.execute(
                "INSERT INTO documents (id, hub_id, filename, file_path, file_size_bytes, "
                "mime_type, status, created_at, updated_at) "
                "VALUES ($1::uuid, $2::uuid, 'test.docx', '/tmp/test.docx', 1024, "
                "'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'pending', NOW(), NOW()) "
                "ON CONFLICT DO NOTHING",
                doc_id, hub_id,
            )

            # INSERT với change_type='invalid_value' → CheckViolationError
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await conn.execute(
                    "INSERT INTO document_versions "
                    "(document_id, version_number, is_original, name, file_type, file_size, file_path, change_type) "
                    "VALUES ($1::uuid, 1, true, 'test.docx', 'docx', 1024, '/tmp/test.docx', 'invalid_value')",
                    doc_id,
                )
        finally:
            await conn.close()

    asyncio.run(_verify())
