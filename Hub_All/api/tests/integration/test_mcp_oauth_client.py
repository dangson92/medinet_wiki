"""Integration tests cho MCP OAuth client endpoints (Phase 8.3 add-on per-user).

Coverage:
- User-facing GET /api/mcp/my-oauth-client:
    + lazy-create cặp lần đầu, idempotent lần sau.
    + KHÔNG token → 401 (kế thừa get_current_user).
    + 2 user khác → 2 cặp khác (isolation per-user).
- User-facing POST /api/mcp/my-oauth-client/rotate:
    + đổi client_secret, GIỮ client_id, set rotated_at.
    + lazy-create nếu user chưa có cặp.
- Internal GET /api/internal/mcp/clients/{client_id}:
    + env MCP_INTERNAL_TOKEN rỗng → 503 (fail-closed).
    + thiếu Authorization → 401.
    + sai token → 401.
    + đúng token + client tồn tại → 200 với owner_user_id khớp.
    + đúng token + client không tồn tại → 404.

Fixtures kế thừa conftest: `auth_client`, `admin_user`/`editor_user` (dict
{id,email,role,password}), `admin_token`/`editor_token` (JWT string).
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest


# ─── User-facing endpoints ─────────────────────────────────────────────────


async def test_get_my_oauth_client_lazy_create(
    auth_client: httpx.AsyncClient, admin_token: str
) -> None:
    """GET lần đầu lazy-create cặp + trả full client_secret plaintext."""
    r = await auth_client.get(
        "/api/mcp/my-oauth-client",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["client_id"].startswith("mcpu_")
    assert len(data["client_id"]) >= 5 + 20  # prefix + 22-char hậu tố
    assert len(data["client_secret"]) >= 32
    assert isinstance(data["redirect_uris"], list)
    assert len(data["redirect_uris"]) >= 1
    assert "claude.ai" in data["redirect_uris"][0]
    assert data["rotated_at"] is None  # chưa rotate
    assert data["created_at"] is not None


async def test_get_my_oauth_client_idempotent(
    auth_client: httpx.AsyncClient, admin_token: str
) -> None:
    """GET 2 lần liên tiếp trả cùng cặp (KHÔNG sinh cặp mới mỗi GET)."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    r1 = await auth_client.get("/api/mcp/my-oauth-client", headers=headers)
    r2 = await auth_client.get("/api/mcp/my-oauth-client", headers=headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["data"]["client_id"] == r2.json()["data"]["client_id"]
    assert (
        r1.json()["data"]["client_secret"] == r2.json()["data"]["client_secret"]
    )


async def test_get_my_oauth_client_isolation_per_user(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    editor_token: str,
) -> None:
    """Mỗi user nhận cặp riêng — client_id KHÔNG trùng nhau."""
    r_admin = await auth_client.get(
        "/api/mcp/my-oauth-client",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r_editor = await auth_client.get(
        "/api/mcp/my-oauth-client",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert r_admin.status_code == 200 and r_editor.status_code == 200
    assert (
        r_admin.json()["data"]["client_id"]
        != r_editor.json()["data"]["client_id"]
    )
    assert (
        r_admin.json()["data"]["client_secret"]
        != r_editor.json()["data"]["client_secret"]
    )


async def test_get_my_oauth_client_unauthenticated_returns_401(
    auth_client: httpx.AsyncClient,
) -> None:
    """KHÔNG Bearer → 401 (kế thừa từ get_current_user dependency)."""
    r = await auth_client.get("/api/mcp/my-oauth-client")
    assert r.status_code == 401


async def test_rotate_changes_secret_keeps_id(
    auth_client: httpx.AsyncClient, admin_token: str
) -> None:
    """POST /rotate đổi client_secret, giữ client_id, set rotated_at."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    initial = (
        await auth_client.get("/api/mcp/my-oauth-client", headers=headers)
    ).json()["data"]
    rotated = (
        await auth_client.post("/api/mcp/my-oauth-client/rotate", headers=headers)
    ).json()["data"]
    assert rotated["client_id"] == initial["client_id"]
    assert rotated["client_secret"] != initial["client_secret"]
    assert rotated["rotated_at"] is not None


async def test_rotate_lazy_creates_when_no_existing(
    auth_client: httpx.AsyncClient, editor_token: str
) -> None:
    """POST /rotate lần đầu trên user chưa có cặp → tạo mới (KHÔNG 404)."""
    headers = {"Authorization": f"Bearer {editor_token}"}
    r = await auth_client.post("/api/mcp/my-oauth-client/rotate", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["client_id"].startswith("mcpu_")
    assert len(data["client_secret"]) >= 32


# ─── Internal endpoint ─────────────────────────────────────────────────────


async def test_internal_lookup_no_config_returns_503(
    auth_client: httpx.AsyncClient,
    admin_user: dict[str, str],
    admin_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Env MCP_INTERNAL_TOKEN rỗng → 503 fail-closed (KHÔNG silent allow)."""
    monkeypatch.setenv("MCP_INTERNAL_TOKEN", "")
    from app.config import get_settings

    get_settings.cache_clear()

    # Lazy-create để có client_id thật — không ảnh hưởng kết quả 503.
    _ = admin_user
    create = await auth_client.get(
        "/api/mcp/my-oauth-client",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client_id = create.json()["data"]["client_id"]

    r = await auth_client.get(
        f"/api/internal/mcp/clients/{client_id}",
        headers={"Authorization": "Bearer anything"},
    )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "INTERNAL_AUTH_NOT_CONFIGURED"


async def test_internal_lookup_missing_authorization_returns_401(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Có env nhưng thiếu Authorization header → 401."""
    monkeypatch.setenv("MCP_INTERNAL_TOKEN", "test-shared-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    r = await auth_client.get("/api/internal/mcp/clients/whatever-id")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "MISSING_AUTHORIZATION"


async def test_internal_lookup_wrong_token_returns_401(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bearer token không khớp env → 401."""
    monkeypatch.setenv("MCP_INTERNAL_TOKEN", "test-shared-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    r = await auth_client.get(
        "/api/internal/mcp/clients/whatever-id",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_INTERNAL_TOKEN"


async def test_internal_lookup_returns_owner(
    auth_client: httpx.AsyncClient,
    admin_user: dict[str, str],
    admin_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Đúng token + client tồn tại → 200 với owner_user_id + email khớp user."""
    monkeypatch.setenv("MCP_INTERNAL_TOKEN", "test-shared-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    # Sinh cặp cho admin_user.
    create = await auth_client.get(
        "/api/mcp/my-oauth-client",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    created_data = create.json()["data"]
    client_id = created_data["client_id"]

    # Lookup qua internal endpoint.
    r = await auth_client.get(
        f"/api/internal/mcp/clients/{client_id}",
        headers={"Authorization": "Bearer test-shared-secret"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["client_id"] == client_id
    assert data["client_secret"] == created_data["client_secret"]
    assert data["owner_user_id"] == admin_user["id"]
    assert data["owner_email"] == admin_user["email"]
    assert isinstance(data["redirect_uris"], list)


async def test_internal_lookup_unknown_client_returns_404(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Đúng token + client_id chưa tồn tại → 404 NOT_FOUND."""
    monkeypatch.setenv("MCP_INTERNAL_TOKEN", "test-shared-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    r = await auth_client.get(
        "/api/internal/mcp/clients/mcpu_never-existed-id",
        headers={"Authorization": "Bearer test-shared-secret"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ─── Service-level (thuần persistence) ──────────────────────────────────────


async def test_service_get_or_create_idempotent(app_with_auth: Any) -> None:
    """`get_or_create` 2 lần liên tiếp cho cùng user → đúng 1 row trong DB."""
    import uuid

    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.session import get_engine
    from app.services.mcp_oauth_service import MCPOAuthClientService

    _ = app_with_auth  # trigger lifespan + engine init

    engine = get_engine()
    user_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            sa_text(
                "INSERT INTO users (id, email, password_hash, role) "
                "VALUES (:id, :email, 'x', 'admin')"
            ),
            {"id": user_id, "email": f"svc-{user_id[:8]}@test.vn"},
        )

    async with AsyncSession(engine) as session:
        service = MCPOAuthClientService(db=session)
        first = await service.get_or_create(uuid.UUID(user_id))
        second = await service.get_or_create(uuid.UUID(user_id))
        assert first.client_id == second.client_id
        assert first.client_secret == second.client_secret
        count = (
            await session.execute(
                sa_text(
                    "SELECT COUNT(*) FROM mcp_oauth_clients WHERE user_id = :u"
                ),
                {"u": user_id},
            )
        ).scalar()
        assert count == 1
