"""Integration test RBAC require_role — Plan 03-05 (AUTH-04 / ROADMAP AC3).

Dùng test-only route `/test/role-check` mount qua fixture spawn FastAPI app
riêng — KHÔNG sửa production router.

AC3 reformulation note: ROADMAP cite `PUT /api/hubs/:id` cho RBAC verify
(Phase 5 HUB-02 chưa tồn tại). Plan 03-05 verify `require_role()` dependency
contract qua test route. Full production endpoint test sẽ thêm Phase 5 HUB-02
reuse cùng require_role().

6 test:
1. test_anonymous_returns_401_missing_authorization
2. test_viewer_returns_403_forbidden (require_role 'admin')
3. test_editor_returns_403_forbidden (require_role 'admin')
4. test_admin_returns_200
5. test_multi_role_admin_passes (require_role 'admin', 'editor')
6. test_multi_role_viewer_rejected (require_role 'admin', 'editor')
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import APIRouter, Depends
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from app.auth import require_role
from app.models.auth import User


def _make_test_rbac_router(*roles: str) -> APIRouter:
    """Tạo router stub `/test/role-check` gate bằng require_role(*roles).

    Trả về dict `{role, user_id}` của user authenticated nếu pass.
    """
    r = APIRouter()

    @r.get("/test/role-check")
    async def role_check(
        user: User = Depends(require_role(*roles)),  # noqa: B008
    ) -> dict[str, str]:
        return {"role": user.role, "user_id": str(user.id)}

    return r


async def _spawn_rbac_app(
    *,
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    alembic_cfg: Config,
    monkeypatch: pytest.MonkeyPatch,
    roles: tuple[str, ...],
) -> AsyncIterator[httpx.AsyncClient]:
    """Spawn FastAPI app + test rbac route, return httpx AsyncClient."""
    # Override env vars CUỐI CÙNG (sau alembic_cfg).
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
    # DEF-05-01: cocoindex 1.0.3 `core.Environment` là process-global singleton —
    # KHÔNG re-open được. _spawn_rbac_app gọi nhiều lần trong cùng process (6 test)
    # → test thứ 2 crash `environment already open`. RBAC test KHÔNG cần cocoindex
    # → skip setup (mirror app_with_auth fixture conftest). Plan 05-06 DEF-05-01 fix.
    monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")

    from app.config import get_settings
    get_settings.cache_clear()

    # Migration upgrade.
    from alembic import command
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    # Truncate per-test isolation.
    import os
    sync_dsn = os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    sync_eng = create_engine(sync_dsn)
    with sync_eng.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE users, refresh_tokens, user_hubs "
                "RESTART IDENTITY CASCADE"
            )
        )
    sync_eng.dispose()

    # Reset engine state.
    from app.db.session import dispose_engine
    await dispose_engine()

    # DEF-05-01: reset audit queue (module-global asyncio.Queue) — _spawn_rbac_app
    # gọi nhiều lần, mỗi lần event loop riêng. Queue cũ bound vào loop trước →
    # audit_flush_loop shutdown await queue.get() treo vĩnh viễn (mirror
    # app_with_auth fixture conftest). Plan 05-06 DEF-05-01 fix.
    from app.services.audit_service import reset_queue
    reset_queue()

    # Create app + add test router.
    from app.main import create_app
    app = create_app()
    app.include_router(_make_test_rbac_router(*roles))

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


@pytest.fixture
async def rbac_client_admin_only(
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    alembic_cfg: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    """App + test route gate require_role('admin')."""
    async for c in _spawn_rbac_app(
        postgres_container=postgres_container,
        redis_container=redis_container,
        alembic_cfg=alembic_cfg,
        monkeypatch=monkeypatch,
        roles=("admin",),
    ):
        yield c


@pytest.fixture
async def rbac_client_admin_or_editor(
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    alembic_cfg: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    """App + test route gate require_role('admin', 'editor')."""
    async for c in _spawn_rbac_app(
        postgres_container=postgres_container,
        redis_container=redis_container,
        alembic_cfg=alembic_cfg,
        monkeypatch=monkeypatch,
        roles=("admin", "editor"),
    ):
        yield c


async def _insert_user_via_engine(
    *, email: str, role: str, full_name: str
) -> str:
    """INSERT 1 user — uses module conftest GO_SEED_HASH."""
    import uuid

    from app.db.session import get_engine
    from tests.integration.conftest import GO_SEED_HASH
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


async def _login(client: httpx.AsyncClient, email: str, password: str) -> str:
    """POST /api/auth/login → return access_token."""
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return str(r.json()["data"]["access_token"])


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_anonymous_returns_401_missing_authorization(
    rbac_client_admin_only: httpx.AsyncClient,
) -> None:
    """KHÔNG Bearer header → 401 MISSING_AUTHORIZATION."""
    r = await rbac_client_admin_only.get("/test/role-check")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "MISSING_AUTHORIZATION"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_viewer_returns_403_forbidden(
    rbac_client_admin_only: httpx.AsyncClient,
) -> None:
    """viewer token hit require_role('admin') → 403 FORBIDDEN."""
    await _insert_user_via_engine(
        email="viewer@medinet.vn", role="viewer", full_name="Viewer User"
    )
    token = await _login(
        rbac_client_admin_only, "viewer@medinet.vn", "Admin@123"
    )

    r = await rbac_client_admin_only.get(
        "/test/role-check", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["error"]["code"] == "FORBIDDEN"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_editor_returns_403_forbidden(
    rbac_client_admin_only: httpx.AsyncClient,
) -> None:
    """editor token hit require_role('admin') → 403 FORBIDDEN."""
    await _insert_user_via_engine(
        email="editor@medinet.vn", role="editor", full_name="Editor User"
    )
    token = await _login(
        rbac_client_admin_only, "editor@medinet.vn", "Admin@123"
    )

    r = await rbac_client_admin_only.get(
        "/test/role-check", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_returns_200(
    rbac_client_admin_only: httpx.AsyncClient,
) -> None:
    """admin token hit require_role('admin') → 200 + envelope success."""
    uid = await _insert_user_via_engine(
        email="admin@medinet.vn", role="admin", full_name="System Admin"
    )
    token = await _login(
        rbac_client_admin_only, "admin@medinet.vn", "Admin@123"
    )

    r = await rbac_client_admin_only.get(
        "/test/role-check", headers={"Authorization": f"Bearer {token}"}
    )
    # require_role return user → endpoint return dict {role, user_id} —
    # KHÔNG đi qua envelope helper (test stub trả raw dict). FastAPI auto
    # JSONResponse cho dict.
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "admin"
    assert body["user_id"] == uid


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_role_admin_passes(
    rbac_client_admin_or_editor: httpx.AsyncClient,
) -> None:
    """admin token hit require_role('admin', 'editor') → 200."""
    await _insert_user_via_engine(
        email="admin@medinet.vn", role="admin", full_name="System Admin"
    )
    token = await _login(
        rbac_client_admin_or_editor, "admin@medinet.vn", "Admin@123"
    )

    r = await rbac_client_admin_or_editor.get(
        "/test/role-check", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "admin"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_role_viewer_rejected(
    rbac_client_admin_or_editor: httpx.AsyncClient,
) -> None:
    """viewer token hit require_role('admin', 'editor') → 403 FORBIDDEN."""
    await _insert_user_via_engine(
        email="viewer@medinet.vn", role="viewer", full_name="Viewer User"
    )
    token = await _login(
        rbac_client_admin_or_editor, "viewer@medinet.vn", "Admin@123"
    )

    r = await rbac_client_admin_or_editor.get(
        "/test/role-check", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "FORBIDDEN"


# Verify type Any for asyncio.gather import-safety (silence ruff F401 if any).
_ = Any
