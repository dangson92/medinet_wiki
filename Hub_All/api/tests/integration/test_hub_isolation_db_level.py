"""E-V3-3 enforce — DB-level hub isolation critical test (Phase 1 v3.0 TOPO-04).

EXIT criteria E-V3-3 (PROJECT.md): Hub isolation bug DB-level KHÔNG fixable trong
7 ngày = ship-blocker. v3.0 reinforce E4 từ logical (WHERE hub_id) sang physical
(DB riêng cùng instance). Process HUB_NAME=yte KHÔNG được kết nối medinet_hub_duoc.

Test này KHÔNG thay test_hub_isolation.py (E4 v2.0 logical) — chạy song song.
v2.0 test = repository layer WHERE hub_id; v3.0 test = process-config + DB conn.

MỌI test marker @pytest.mark.critical (HARD-03 CI gate) + @pytest.mark.integration.

Reuse fixture pattern conftest.py: PostgresContainer pgvector/pgvector:pg16 module-scope.
W6 fix: fixture pg_container_4dbs dùng `with closing(psycopg2.connect(...))` + `with conn.cursor()`
context manager cho lifecycle gọn — loại bỏ pattern manual close + no-op .replace() M2 cũ.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing
from typing import Any

import asyncpg
import psycopg2  # testcontainers-postgres dep
import pytest
from pydantic import ValidationError
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def pg_container_4dbs() -> Iterator[PostgresContainer]:
    """Postgres container với 4 DB medinet (central + yte + duoc + hcns) pre-created.

    W6 refactor: dùng context manager `with closing(psycopg2.connect(...)) as conn:`
    cho lifecycle gọn — autocommit set qua `conn.autocommit = True` ngay sau enter
    (psycopg2 connection context manager commit/rollback transaction, KHÔNG close
    connection theo PEP-249 spec → phải close thủ công ngoài with block hoặc
    dùng `contextlib.closing`).
    """
    with PostgresContainer("pgvector/pgvector:pg16", driver=None) as pg:
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)

        # Step 1: connect superuser default DB (postgres) → CREATE 4 DB nghiệp vụ
        with closing(psycopg2.connect(
            host=host, port=port, user=pg.username, password=pg.password, dbname="postgres",
        )) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                for db in [
                    "medinet_central",
                    "medinet_hub_yte",
                    "medinet_hub_duoc",
                    "medinet_hub_hcns",
                ]:
                    # Idempotent: check pg_database trước CREATE (testcontainer fresh,
                    # nhưng safety cho re-run module-scope)
                    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db,))
                    if cur.fetchone() is None:
                        cur.execute(f"CREATE DATABASE {db}")

        # Step 2: CREATE EXTENSION vector trên mỗi DB
        for db in [
            "medinet_central",
            "medinet_hub_yte",
            "medinet_hub_duoc",
            "medinet_hub_hcns",
        ]:
            with closing(psycopg2.connect(
                host=host, port=port, user=pg.username, password=pg.password, dbname=db,
            )) as db_conn:
                db_conn.autocommit = True
                with db_conn.cursor() as db_cur:
                    db_cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

        yield pg


def _build_dsn(pg: PostgresContainer, db_name: str) -> str:
    """Build SQLAlchemy async DSN cho DB hub cụ thể."""
    host = pg.get_container_host_ip()
    port = pg.get_exposed_port(5432)
    return f"postgresql+asyncpg://{pg.username}:{pg.password}@{host}:{port}/{db_name}"


def _build_asyncpg_dsn(pg: PostgresContainer, db_name: str) -> str:
    """Build asyncpg raw DSN cho DB hub cụ thể."""
    host = pg.get_container_host_ip()
    port = pg.get_exposed_port(5432)
    return f"postgresql://{pg.username}:{pg.password}@{host}:{port}/{db_name}"


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    """Reset lru_cache Settings sau mỗi test để re-load env mới."""
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.critical
@pytest.mark.integration
def test_settings_yte_with_central_dsn_raises(
    pg_container_4dbs: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HUB_NAME=yte + DATABASE_URL trỏ medinet_central → ValidationError fail-fast."""
    monkeypatch.setenv("HUB_NAME", "yte")
    monkeypatch.setenv("DATABASE_URL", _build_dsn(pg_container_4dbs, "medinet_central"))
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        _build_asyncpg_dsn(pg_container_4dbs, "medinet_central"),
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    from app.config import Settings
    with pytest.raises(ValidationError, match="DSN mismatch hub_name"):
        Settings()


@pytest.mark.critical
@pytest.mark.integration
def test_settings_yte_with_duoc_dsn_raises(
    pg_container_4dbs: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HUB_NAME=yte + DATABASE_URL trỏ medinet_hub_duoc (cross-hub typo) → ValidationError."""
    monkeypatch.setenv("HUB_NAME", "yte")
    monkeypatch.setenv("DATABASE_URL", _build_dsn(pg_container_4dbs, "medinet_hub_duoc"))
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        _build_asyncpg_dsn(pg_container_4dbs, "medinet_central"),
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    from app.config import Settings
    with pytest.raises(ValidationError, match="DSN mismatch hub_name"):
        Settings()


@pytest.mark.critical
@pytest.mark.integration
def test_settings_yte_with_yte_dsn_succeeds(
    pg_container_4dbs: PostgresContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HUB_NAME=yte + DATABASE_URL trỏ medinet_hub_yte → instantiate OK."""
    monkeypatch.setenv("HUB_NAME", "yte")
    monkeypatch.setenv("DATABASE_URL", _build_dsn(pg_container_4dbs, "medinet_hub_yte"))
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        _build_asyncpg_dsn(pg_container_4dbs, "medinet_central"),
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    from app.config import Settings
    s = Settings()
    assert s.hub_name == "yte"
    assert s.database_url.endswith("/medinet_hub_yte")


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_db_connection_yte_cannot_reach_duoc(
    pg_container_4dbs: PostgresContainer,
) -> None:
    """Asyncpg connection bound 1 DB — process kết nối medinet_hub_yte
    KHÔNG có cách query data medinet_hub_duoc qua cùng connection.

    Postgres asyncpg connection = 1 connection = 1 database. Đổi DB phải reconnect
    với DSN khác. Process layer (Phase 2 FACTOR-01) sẽ enforce qua Settings validator
    + init_engine 1 lần lifespan startup.
    """
    yte_dsn = _build_asyncpg_dsn(pg_container_4dbs, "medinet_hub_yte")
    conn = await asyncpg.connect(yte_dsn)
    try:
        current = await conn.fetchval("SELECT current_database()")
        assert current == "medinet_hub_yte"

        # Tạo 1 bảng test trong yte
        await conn.execute("DROP TABLE IF EXISTS _iso_test")
        await conn.execute("CREATE TABLE _iso_test (id int, hub text)")
        await conn.execute("INSERT INTO _iso_test VALUES (1, 'yte_marker')")

        # Verify yte data
        rows = await conn.fetch("SELECT * FROM _iso_test")
        assert len(rows) == 1 and rows[0]["hub"] == "yte_marker"

        await conn.execute("DROP TABLE _iso_test")
    finally:
        await conn.close()


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_4_dbs_independent_data(
    pg_container_4dbs: PostgresContainer,
) -> None:
    """Seed bảng test ở mỗi DB hub khác nhau → verify cross-DB không thấy data.

    Verify physical isolation: DB yte INSERT data → DB duoc query KHÔNG thấy.
    """
    # Seed mỗi DB
    for hub, marker in [("yte", "alpha"), ("duoc", "beta"), ("hcns", "gamma")]:
        dsn = _build_asyncpg_dsn(pg_container_4dbs, f"medinet_hub_{hub}")
        conn: Any = await asyncpg.connect(dsn)
        try:
            await conn.execute("DROP TABLE IF EXISTS _iso_marker")
            await conn.execute("CREATE TABLE _iso_marker (m text)")
            await conn.execute("INSERT INTO _iso_marker VALUES ($1)", marker)
        finally:
            await conn.close()

    # Verify mỗi DB chỉ thấy marker của chính nó
    for hub, expected in [("yte", "alpha"), ("duoc", "beta"), ("hcns", "gamma")]:
        dsn = _build_asyncpg_dsn(pg_container_4dbs, f"medinet_hub_{hub}")
        conn = await asyncpg.connect(dsn)
        try:
            result = await conn.fetchval("SELECT m FROM _iso_marker")
            assert result == expected, (
                f"Cross-DB leak detected: medinet_hub_{hub} thấy marker {result!r} "
                f"thay vì {expected!r} — E-V3-3 fail."
            )
        finally:
            await conn.close()

    # Cleanup
    for hub in ["yte", "duoc", "hcns"]:
        dsn = _build_asyncpg_dsn(pg_container_4dbs, f"medinet_hub_{hub}")
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute("DROP TABLE IF EXISTS _iso_marker")
        finally:
            await conn.close()
