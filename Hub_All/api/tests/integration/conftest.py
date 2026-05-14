"""Shared fixtures cho integration tests Phase 2 (Plan 05) + Phase 3 (Plan 05).

Phase 2 fixtures (source-of-truth cho 3 file test):
- test_migration_upgrade_downgrade.py
- test_chunks_hnsw_cosine_ops.py
- test_alembic_ignores_cocoindex_schema.py

Phase 3 Plan 05 fixtures (auth integration test):
- redis_container — RedisContainer 7-alpine cho blacklist + SETNX P16
- auth_env — env vars cho create_app() trỏ vào containers + keys
- app_with_auth — FastAPI app + alembic upgrade head + LifespanManager
- auth_client — httpx AsyncClient + ASGITransport cho hit /api/auth/*
- admin_user / editor_user / viewer_user — seed 3 user vào DB qua SQL
- admin_token / editor_token / viewer_token — POST /api/auth/login → access_token
- admin_token_pair — cả access_token + refresh_token cho test refresh race

KHONG redeclare fixture trong test file — pytest auto-discover qua conftest.

Yeu cau prereq:
- Docker Desktop running (testcontainers tu pull image `pgvector/pgvector:pg16`
  va `redis:7-alpine`).
- Image `pgvector/pgvector:pg16` la MANDATORY (P17 — KHONG postgres:16-alpine vi
  alpine khong co ext vector → CREATE EXTENSION fail).
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic.config import Config
from asgi_lifespan import LifespanManager
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


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


# ========================================================================
# === Phase 3 Plan 05 fixtures (auth integration test) ===================
# ========================================================================

# Go production seed hash từ backend/scripts/seed.sql line 13 — Argon2id
# params m=65536, t=3, p=4 (R6 cross-compat verified Plan 03-03).
# Tất cả test user dùng cùng plaintext "Admin@123" để convenience seed.
GO_SEED_HASH_PLAINTEXT = "Admin@123"
GO_SEED_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4"
    "$gpKFndFoG6bcXrx7R60sag"
    "$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c"
)


@pytest.fixture(scope="module")
def redis_container() -> Iterator[RedisContainer]:
    """Redis 7 testcontainer — share scope module (tránh pull image mỗi test)."""
    with RedisContainer("redis:7-alpine") as rc:
        yield rc


@pytest.fixture
def auth_env(
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Set env vars cho create_app() trỏ vào containers + key paths.

    KHÔNG dùng port 6379 default Redis local — testcontainers map random port.
    """
    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://")
    redis_host = redis_container.get_container_host_ip()
    redis_port = redis_container.get_exposed_port(6379)

    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("COCOINDEX_DATABASE_URL", sync_url)
    monkeypatch.setenv("REDIS_URL", f"redis://{redis_host}:{redis_port}/0")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", "keys/private.pem")
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", "keys/public.pem")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_TTL", "900")
    monkeypatch.setenv("JWT_REFRESH_TOKEN_TTL", "604800")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
async def app_with_auth(auth_env: None, alembic_cfg: Config) -> AsyncIterator[Any]:
    """FastAPI app + alembic upgrade head + lifespan ready.

    Migration chạy TRƯỚC lifespan vì lifespan chỉ verify connection, KHÔNG
    tạo schema. Tests sẽ INSERT vào users / refresh_tokens / user_hubs.
    """
    # Apply migration schema trước khi lifespan init.
    from alembic import command
    command.upgrade(alembic_cfg, "head")

    # Reset SQLAlchemy engine state cho test isolation (lifespan trước có thể
    # đã init engine với DSN cũ — phải dispose trước khi init lại).
    from app.db.session import dispose_engine
    await dispose_engine()

    from app.main import create_app
    app = create_app()
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def auth_client(app_with_auth: Any) -> AsyncIterator[httpx.AsyncClient]:
    """httpx AsyncClient + ASGITransport — in-process, KHÔNG cần boot server."""
    transport = httpx.ASGITransport(app=app_with_auth)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client


async def _insert_user(
    *, email: str, role: str, full_name: str
) -> str:
    """INSERT 1 user trực tiếp qua SQL, return UUID string.

    Dùng SQLAlchemy async engine (đã init bởi lifespan app_with_auth) thay
    vì asyncpg trực tiếp — tránh duplicate connection pool.
    """
    from app.db.session import get_engine
    engine = get_engine()
    user_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, role, "
                "is_active, created_at, updated_at) "
                "VALUES (:id, :email, :hash, :name, :role, TRUE, NOW(), NOW())"
            ),
            {
                "id": user_id,
                "email": email,
                "hash": GO_SEED_HASH,
                "name": full_name,
                "role": role,
            },
        )
    return user_id


@pytest.fixture
async def admin_user(app_with_auth: Any) -> dict[str, str]:
    """INSERT admin@medinet.vn / Admin@123 — role=admin."""
    _ = app_with_auth  # trigger lifespan + migration
    uid = await _insert_user(
        email="admin@medinet.vn", role="admin", full_name="System Admin"
    )
    return {
        "id": uid,
        "email": "admin@medinet.vn",
        "role": "admin",
        "password": GO_SEED_HASH_PLAINTEXT,
    }


@pytest.fixture
async def editor_user(app_with_auth: Any) -> dict[str, str]:
    """INSERT editor@medinet.vn / Admin@123 — role=editor."""
    _ = app_with_auth
    uid = await _insert_user(
        email="editor@medinet.vn", role="editor", full_name="Editor User"
    )
    return {
        "id": uid,
        "email": "editor@medinet.vn",
        "role": "editor",
        "password": GO_SEED_HASH_PLAINTEXT,
    }


@pytest.fixture
async def viewer_user(app_with_auth: Any) -> dict[str, str]:
    """INSERT viewer@medinet.vn / Admin@123 — role=viewer."""
    _ = app_with_auth
    uid = await _insert_user(
        email="viewer@medinet.vn", role="viewer", full_name="Viewer User"
    )
    return {
        "id": uid,
        "email": "viewer@medinet.vn",
        "role": "viewer",
        "password": GO_SEED_HASH_PLAINTEXT,
    }


async def _login_get_token(
    client: httpx.AsyncClient, user: dict[str, str]
) -> dict[str, Any]:
    """POST /api/auth/login, return data dict {access_token, refresh_token, ...}."""
    r = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True, body
    data: dict[str, Any] = body["data"]
    return data


@pytest.fixture
async def admin_token(
    auth_client: httpx.AsyncClient, admin_user: dict[str, str]
) -> str:
    """JWT access_token cho admin@medinet.vn."""
    data = await _login_get_token(auth_client, admin_user)
    return str(data["access_token"])


@pytest.fixture
async def editor_token(
    auth_client: httpx.AsyncClient, editor_user: dict[str, str]
) -> str:
    """JWT access_token cho editor@medinet.vn."""
    data = await _login_get_token(auth_client, editor_user)
    return str(data["access_token"])


@pytest.fixture
async def viewer_token(
    auth_client: httpx.AsyncClient, viewer_user: dict[str, str]
) -> str:
    """JWT access_token cho viewer@medinet.vn."""
    data = await _login_get_token(auth_client, viewer_user)
    return str(data["access_token"])


@pytest.fixture
async def admin_token_pair(
    auth_client: httpx.AsyncClient, admin_user: dict[str, str]
) -> dict[str, Any]:
    """Trả CẢ access_token + refresh_token cho test refresh race (AC5)."""
    return await _login_get_token(auth_client, admin_user)
