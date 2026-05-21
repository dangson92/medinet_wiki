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

import asyncio
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

    v3.0 Plan 01-02 — `Settings._enforce_hub_dsn_match` validator yeu cau
    DATABASE_URL ket thuc `/medinet_central` khi HUB_NAME=central (default test).
    Container auto-create DB `test` (POSTGRES_DB default); ta tao them
    `medinet_central` voi cung extension de test fixture co the doi DSN
    sang `/medinet_central` ma khong rebuild image.
    """
    with PostgresContainer("pgvector/pgvector:pg16", driver=None) as pg:
        sync_url = pg.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql://"
        )
        # Enable ext tren DB `test` (default container) — backward compat
        # cho test cu chua migrate sang DSN medinet_central.
        eng = create_engine(sync_url)
        with eng.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        eng.dispose()
        # Tao them DB `medinet_central` + enable ext — Plan 01-02 validator
        # yeu cau DSN suffix khop hub_name. CREATE DATABASE phai chay
        # AUTOCOMMIT ngoai transaction.
        admin_eng = create_engine(sync_url, isolation_level="AUTOCOMMIT")
        with admin_eng.connect() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname='medinet_central'")
            ).scalar()
            if not existing:
                conn.execute(text("CREATE DATABASE medinet_central"))
        admin_eng.dispose()
        central_url = sync_url.rsplit("/", 1)[0] + "/medinet_central"
        central_eng = create_engine(central_url)
        with central_eng.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        central_eng.dispose()
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
    # v3.0 Plan 01-02 — Swap DB segment cuoi sang /medinet_central de pass
    # Settings._enforce_hub_dsn_match (HUB_NAME default "central"). DB
    # medinet_central da duoc tao trong postgres_container fixture.
    central_sync_url = sync_url.rsplit("/", 1)[0] + "/medinet_central"
    async_url = central_sync_url.replace(
        "postgresql://", "postgresql+asyncpg://"
    )

    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("COCOINDEX_DATABASE_URL", central_sync_url)
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
# Reference Go source: git tag `m1-go-archived` (xoá khỏi tree 2026-05-14 TEARDOWN-01 pull-in).
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

    v3.0 Plan 01-02 — DSN swap sang /medinet_central de pass validator
    (xem `postgres_container` fixture pre-create DB).
    """
    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    central_sync_url = sync_url.rsplit("/", 1)[0] + "/medinet_central"
    async_url = central_sync_url.replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    redis_host = redis_container.get_container_host_ip()
    redis_port = redis_container.get_exposed_port(6379)

    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("COCOINDEX_DATABASE_URL", central_sync_url)
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
async def app_with_auth(
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    alembic_cfg: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Any]:
    """FastAPI app + alembic upgrade head + lifespan ready.

    Migration chạy TRƯỚC lifespan vì lifespan chỉ verify connection, KHÔNG
    tạo schema. Tests sẽ INSERT vào users / refresh_tokens / user_hubs.

    CRITICAL — set env vars CUỐI CÙNG TRONG fixture này (sau alembic_cfg):
    alembic_cfg setEnv REDIS_URL=localhost:6379 (placeholder Phase 2 — không
    dùng redis cho migration). Plan 03-05 cần REDIS_URL trỏ vào testcontainer
    port — phải override SAU alembic_cfg, rồi clear cache, rồi gọi create_app.
    Cùng lý do với DATABASE_URL/JWT_*_PATH.
    """
    # CRITICAL: alembic_cfg đã setEnv (Phase 2 style — localhost:6379 cho Redis,
    # không cần redis cho migration). Plan 03-05 cần override REDIS_URL +
    # JWT keys + CORS để create_app dùng testcontainer Redis. Set TẠI ĐÂY
    # đảm bảo override xảy ra SAU alembic_cfg.
    # v3.0 Plan 01-02 — DSN swap sang /medinet_central de pass validator.
    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    central_sync_url = sync_url.rsplit("/", 1)[0] + "/medinet_central"
    async_url = central_sync_url.replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    redis_host = redis_container.get_container_host_ip()
    redis_port = redis_container.get_exposed_port(6379)

    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("COCOINDEX_DATABASE_URL", central_sync_url)
    monkeypatch.setenv("REDIS_URL", f"redis://{redis_host}:{redis_port}/0")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_PRIVATE_KEY_PATH", "keys/private.pem")
    monkeypatch.setenv("JWT_PUBLIC_KEY_PATH", "keys/public.pem")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_TTL", "900")
    monkeypatch.setenv("JWT_REFRESH_TOKEN_TTL", "604800")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    # Plan 05-06: deterministic test AES_KEY (32-byte base64url) cho AES-GCM
    # round-trip reproducible — API key encrypt/decrypt (Plan 05-05 crypto).
    monkeypatch.setenv(
        "AES_KEY", "bWVkaW5ldC10ZXN0LWFlcy1rZXktMzJieXRlcyEhMDA="
    )

    # DEF-05-01: cocoindex 1.0.3 `core.Environment` là process-global singleton —
    # KHÔNG re-open được sau open + close. Fixture này dùng cho >1 test cùng
    # process (CRUD test hub/user/apikey + test_documents_list_delete) sẽ FAIL
    # từ test thứ 2 với `environment already open`. CRUD test KHÔNG cần cocoindex
    # ingestion flow — set COCOINDEX_SKIP_SETUP=1 để lifespan bỏ qua
    # setup_cocoindex(). Test cần cocoindex_app (A4 BackgroundTask) cấp mock vào
    # app.state.cocoindex_app SAU lifespan (xem mock_cocoindex_app fixture).
    monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")

    from app.config import get_settings
    get_settings.cache_clear()

    # Apply migration schema trước khi lifespan init.
    # alembic env.py dùng `asyncio.run(run_async_migrations())` — call từ
    # trong async fixture sẽ raise "asyncio.run() cannot be called from a
    # running event loop". Wrap qua to_thread() → thread mới có event loop riêng.
    from alembic import command
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    # Reset SQLAlchemy engine state cho test isolation (lifespan trước có thể
    # đã init engine với DSN cũ — phải dispose trước khi init lại).
    from app.db.session import dispose_engine
    await dispose_engine()

    # DEF-05-01: reset audit queue (module-global asyncio.Queue trong
    # audit_service). Mỗi test dùng event loop riêng — `asyncio.Queue` cũ giữ
    # internal futures bound vào loop của test trước → `audit_flush_loop` test
    # sau `await queue.get()` treo vĩnh viễn. reset_queue() force re-init queue
    # trên event loop hiện tại (helper có sẵn cho mục đích test isolation này).
    from app.services.audit_service import reset_queue
    reset_queue()

    # TRUNCATE per-test isolation — postgres_container scope=module nên data
    # giữa các test trong cùng module sẽ leak. Phase 3 Plan 05 cần fresh state
    # mỗi test (admin_user fixture INSERT cùng email → unique violation lần 2).
    # Dùng raw sync engine TRƯỚC khi lifespan init (init_engine chưa chạy).
    import os
    sync_dsn = os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    sync_eng = create_engine(sync_dsn)
    with sync_eng.begin() as conn:
        # CASCADE truncate — refresh_tokens.user_id + user_hubs.user_id FK reference users.
        # Plan 05-06: thêm bảng Phase 5 (hubs/audit_logs/api_keys/documents/chunks)
        # để CRUD + hub-isolation integration test có fresh state mỗi test.
        conn.execute(
            text(
                "TRUNCATE TABLE users, refresh_tokens, user_hubs, hubs, "
                "audit_logs, api_keys, documents, chunks "
                "RESTART IDENTITY CASCADE"
            )
        )
    sync_eng.dispose()

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


async def _insert_hub(*, name: str, code: str, subdomain: str) -> str:
    """INSERT 1 hub row trực tiếp qua SQL, return hub_id string.

    Cột theo migration 0003 (Plan 05-01): hubs có cả `slug` (legacy NOT NULL
    mirror) + `code` (contract frontend) + `subdomain` + `status`. `slug=code`.
    Dùng cho Plan 05-06 hub-isolation integration test (test_hub_isolation.py).
    """
    from app.db.session import get_engine
    engine = get_engine()
    hub_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO hubs "
                "(id, slug, code, name, subdomain, description, status, "
                "is_active, created_at, updated_at) "
                "VALUES (:id, :slug, :code, :name, :subdomain, NULL, 'active', "
                "TRUE, NOW(), NOW())"
            ),
            {
                "id": hub_id,
                "slug": code,
                "code": code,
                "name": name,
                "subdomain": subdomain,
            },
        )
    return hub_id


async def _assign_user_hub(*, user_id: str, hub_id: str) -> None:
    """INSERT 1 row user_hubs — gán user vào hub (HUB-02 isolation source)."""
    from app.db.session import get_engine
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO user_hubs (user_id, hub_id, assigned_at) "
                "VALUES (:uid, :hid, NOW())"
            ),
            {"uid": user_id, "hid": hub_id},
        )


async def _insert_document(
    *, hub_id: str, filename: str, uploaded_by: str | None = None
) -> str:
    """INSERT 1 document row, return document_id. Dùng cho search test.

    Cột theo migration 0001 (documents): seed document `status='completed'`
    để search test (Plan 06-04) có document JOIN-able cho chunks. Bypass upload
    flow — search isolation test cần data ở nhiều hub (T-06-04-02 accept).
    """
    from app.db.session import get_engine
    engine = get_engine()
    doc_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO documents "
                "(id, hub_id, uploaded_by, filename, file_path, mime_type, "
                "file_size_bytes, status, chunk_count, attempts, "
                "created_at, updated_at, last_heartbeat) "
                "VALUES (:id, :hub, :uploader, :name, :path, "
                "'application/octet-stream', 100, 'completed', 1, 0, "
                "NOW(), NOW(), NOW())"
            ),
            {
                "id": doc_id,
                "hub": hub_id,
                "uploader": uploaded_by,
                "name": filename,
                "path": f"/tmp/{doc_id}",
            },
        )
    return doc_id


async def _insert_chunk(
    *, document_id: str, hub_id: str, content: str, vector: list[float]
) -> str:
    """INSERT 1 chunk row với vector. Dùng cho search test (chunks table rỗng M2).

    `content_hash` BYTEA NOT NULL → seed 4 byte placeholder. `vector` Vector(1536)
    → caller PHẢI truyền list đúng 1536 phần tử; literal `'[...]'` cast `::vector`.
    """
    from app.db.session import get_engine
    engine = get_engine()
    chunk_id = str(uuid.uuid4())
    vec_literal = "[" + ",".join(repr(float(x)) for x in vector) + "]"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO chunks "
                "(id, document_id, hub_id, content, content_hash, "
                "heading_path, page_start, page_end, vector, metadata, created_at) "
                "VALUES (:id, :doc, :hub, :content, :hash, "
                "'', 1, 1, CAST(:vec AS vector), '{}'::jsonb, NOW())"
            ),
            {
                "id": chunk_id,
                "doc": document_id,
                "hub": hub_id,
                "content": content,
                "hash": b"\x00" * 4,
                "vec": vec_literal,
            },
        )
    return chunk_id


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


# ========================================================================
# === Phase 7 Plan 07-05 fixtures (Ask API integration test) =============
# ========================================================================
#
# Plan 07-05 — integration test suite critical-path Phase 7 (ASK-01..05).
# LLM call MOCK (D-07-05-A): OPENAI_API_KEY ở M2 dev là placeholder
# `sk-replace-me` → KHÔNG gọi provider thật. Mock `litellm.acompletion` +
# `litellm.completion_cost` qua `mock_llm` fixture — vừa tránh gọi key giả vừa
# KIỂM SOÁT answer (vd "Trả lời [1] và [2]." → verify citation mapping
# deterministic).
#
# DEF-05-01: file test boot app qua `app_with_auth` PHẢI chạy PER-FILE
# (cocoindex 1.0.3 `core.Environment` là process-global singleton — không
# re-open). Mỗi file test = 1 pytest invocation riêng.


def make_fake_completion(
    content: str,
    *,
    prompt_tokens: int = 120,
    completion_tokens: int = 40,
) -> Any:
    """Object giả mô phỏng LiteLLM `ModelResponse` cho test mock.

    `AskService._call_llm` đọc `resp.choices[0].message.content`;
    `AskService._extract_usage` đọc `resp.usage.prompt_tokens` /
    `.completion_tokens` / `.total_tokens`. `SimpleNamespace` lồng nhau cấp
    đủ các attribute đó — KHÔNG cần import litellm type thật.
    """
    from types import SimpleNamespace

    msg = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    return SimpleNamespace(choices=[choice], usage=usage)


@pytest.fixture
def mock_llm(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Monkeypatch `litellm.acompletion` + `litellm.completion_cost` (D-07-05-A).

    Trả `state` dict — test set `state["answer"]` TRƯỚC khi gọi `/api/ask` để
    kiểm soát câu trả lời LLM (verify citation mapping deterministic). Sau
    response, test đọc:
    - `state["captured_messages"]` — list message đã gửi cho LLM (verify
      anti-injection prompt được chèn vào `messages[0]`).
    - `state["captured_model"]` — model LiteLLM nhận (verify hot-swap ASK-04).

    `completion_cost` mock trả float cố định 0.0012 — key placeholder M2 dev
    không có bảng giá thật.
    """
    state: dict[str, Any] = {
        "answer": "Trả lời mặc định [1].",
        "captured_messages": None,
        "captured_model": None,
    }

    async def _fake_acompletion(
        *, model: str, messages: list[dict[str, str]], **kw: Any
    ) -> Any:
        _ = kw
        state["captured_messages"] = messages
        state["captured_model"] = model
        return make_fake_completion(state["answer"])

    def _fake_cost(*a: Any, **kw: Any) -> float:
        _ = (a, kw)
        return 0.0012

    monkeypatch.setattr("litellm.acompletion", _fake_acompletion)
    monkeypatch.setattr("litellm.completion_cost", _fake_cost)
    return state


async def _wait_usage_count(
    conn: Any,
    expected: int,
    *,
    timeout_s: float = 2.0,
    interval_s: float = 0.05,
) -> int:
    """Poll `count(*)` usage_events tới khi == `expected` hoặc timeout (D-07-05-B).

    `usage_events` ghi qua FastAPI `BackgroundTasks` — với httpx `ASGITransport`,
    background task chạy SAU response nhưng timing không xác định. Thay vì
    `asyncio.sleep` cố định (flaky), POLL có giới hạn: lặp query count mỗi
    `interval_s` cho tới khi đạt `expected` RỒI mới return → deterministic.

    Raise `AssertionError` nếu sau `timeout_s` vẫn chưa đạt `expected`.
    """
    import asyncio
    import time

    deadline = time.monotonic() + timeout_s
    last = -1
    while time.monotonic() < deadline:
        last = await conn.fetchval("SELECT count(*) FROM usage_events")
        if last == expected:
            return int(last)
        await asyncio.sleep(interval_s)
    raise AssertionError(
        f"usage_events count={last}, kỳ vọng {expected} sau {timeout_s}s"
    )


def _make_vec(seed: float) -> list[float]:
    """Vector deterministic 1536-dim — mọi phần tử = `seed`.

    Dùng cho `_insert_chunk` + monkeypatch query embedding (cùng vector → cosine
    distance xác định). Tương đương `_fixed_vector` trong test_search_hub_isolation
    — helper chung đặt ở conftest cho test Phase 7 tái dùng.
    """
    return [seed] * 1536
