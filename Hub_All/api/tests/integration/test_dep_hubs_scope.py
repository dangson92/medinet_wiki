"""Integration test hubs.py scope — Phase 2 Plan 02-02 (DEP-02 + DEP-04).

3 scenario verify ROADMAP Phase 2 success criteria #1/3/4:
1. Super admin GET /api/hubs → trả ALL hubs.
2. Hub_admin (users.role='editor' + user_hubs.role='hub_admin' cho hub dmd)
   GET /api/hubs → CHỈ trả hub dmd (KHÔNG central, KHÔNG tdt).
3. Hub_admin POST /api/hubs (create hub mới) → 403 FORBIDDEN (require_role("admin")
   GIỮ NGUYÊN — DEP-04 LOCKED).

W1 isolation note: `app_with_auth` fixture (conftest.py:264-284) đã TRUNCATE 8 bảng
(users, refresh_tokens, user_hubs, hubs, audit_logs, api_keys, documents, chunks)
RESTART IDENTITY CASCADE per-test — fixture seed dưới KHÔNG cần truncate lại.

W2 schema note: hubs table có 10 cột (migration 0001 + 0003) — id, slug, name,
description, is_active, created_at, updated_at, code, subdomain, status. INSERT
9 cột (bỏ updated_at — server_default NOW()) là VALID.

Carry forward patterns:
- `tests/integration/test_rbac_dependency.py` _spawn_rbac_app + LifespanManager + _login.
- `tests/integration/conftest.py` fixture admin_user/editor_user + _insert_user_via_engine + _insert_hub.
- Plan 01-01 migration 0006 user_hubs.role TEXT NULL — INSERT trực tiếp seed hub_admin.

D-V3.1-Phase2-A LOCKED: routers/hubs.py:54-91 ĐÃ ĐÚNG theo thiết kế (hub_admin
users.role='editor' → rơi else branch → filter user_hubs). Test verify chứ
KHÔNG sửa router list/mutate handler signature (Task 2 chỉ thêm ≤ 15 dòng
defensive invariant guard cho admin branch — B2 iter 1).
"""
from __future__ import annotations

import uuid as _uuid

import httpx
import pytest
from sqlalchemy import text


async def _seed_hub_admin_user(
    *, email: str, password_hash: str, hub_id: str
) -> str:
    """Seed user role='editor' global + user_hubs.role='hub_admin' per-hub.

    Phase 2 fixture helper — Plan 01-01 migration 0006 đã ADD user_hubs.role
    TEXT NULL → INSERT user_hubs với role='hub_admin' để override global.

    Returns:
        user_id str (UUID).
    """
    from app.db.session import get_engine

    engine = get_engine()
    user_id = str(_uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, role, "
                "phone, department, status, is_active, created_at, updated_at) "
                "VALUES (:id, :email, :hash, :name, 'editor', NULL, NULL, "
                "'active', TRUE, NOW(), NOW())"
            ),
            {
                "id": user_id,
                "email": email,
                "hash": password_hash,
                "name": "Hub Admin Test",
            },
        )
        # Phase 1 Plan 01-01 migration 0006 — user_hubs.role NULL default,
        # explicit set 'hub_admin' để override.
        await conn.execute(
            text(
                "INSERT INTO user_hubs (user_id, hub_id, role, assigned_at) "
                "VALUES (:uid, :hid, 'hub_admin', NOW())"
            ),
            {"uid": user_id, "hid": hub_id},
        )
    return user_id


@pytest.fixture
async def seed_hubs_dmd_tdt(app_with_auth: object) -> tuple[str, str]:
    """Tạo 2 hub dmd + tdt qua DB direct (tránh require_role admin để tạo).

    W1: app_with_auth fixture (conftest.py:264-284) auto-truncate 8 bảng
    RESTART IDENTITY CASCADE per-test → fixture seed KHÔNG cần re-truncate.

    W2: hubs table có 10 cột (migration 0001 + 0003) — INSERT 9 cột (bỏ
    updated_at server_default NOW()) là VALID. Reference:
    - api/migrations/versions/0001_initial_schema.py:80-106 (7 cột base)
    - api/migrations/versions/0003_phase5_schema_reconcile.py:47-74 (3 cột thêm)

    Returns:
        (dmd_id, tdt_id) tuple.
    """
    _ = app_with_auth  # trigger lifespan + migration + truncate
    from app.db.session import get_engine

    engine = get_engine()
    dmd_id = str(_uuid.uuid4())
    tdt_id = str(_uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO hubs (id, slug, name, code, subdomain, status, "
                "is_active, created_at, updated_at) "
                "VALUES (:id, :slug, :name, :code, :subdomain, 'active', TRUE, "
                "NOW(), NOW())"
            ),
            {
                "id": dmd_id, "slug": "dmd", "name": "Đỗ Minh Đường",
                "code": "dmd", "subdomain": "dmd",
            },
        )
        await conn.execute(
            text(
                "INSERT INTO hubs (id, slug, name, code, subdomain, status, "
                "is_active, created_at, updated_at) "
                "VALUES (:id, :slug, :name, :code, :subdomain, 'active', TRUE, "
                "NOW(), NOW())"
            ),
            {
                "id": tdt_id, "slug": "tdt", "name": "Thuốc Dân Tộc",
                "code": "tdt", "subdomain": "tdt",
            },
        )
    return dmd_id, tdt_id


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_super_admin_get_hubs_returns_all(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 1 ROADMAP success criteria #1:
    Super admin GET /api/hubs → trả ALL hubs (cross-hub by design).

    Fixture `seed_hubs_dmd_tdt` tạo 2 hub (dmd + tdt) — verify cả 2 trong list.

    DEP-02 verify: admin branch routers/hubs.py:73 → service.list(...) trả ALL.
    """
    dmd_id, tdt_id = seed_hubs_dmd_tdt

    r = await auth_client.get(
        "/api/hubs?per_page=100",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    hub_ids_returned = {h["id"] for h in body["data"]}
    assert dmd_id in hub_ids_returned, "Super admin phải thấy hub dmd"
    assert tdt_id in hub_ids_returned, "Super admin phải thấy hub tdt"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_dmd_get_hubs_returns_only_dmd(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 2 ROADMAP success criteria #1:
    Hub_admin (users.role='editor' + user_hubs.role='hub_admin' dmd)
    GET /api/hubs → CHỈ trả hub dmd (KHÔNG central, KHÔNG tdt).

    D-V3.1-Phase2-A LOCKED: hub_admin có users.role='editor' (KHÔNG 'admin')
    → rơi else branch routers/hubs.py:78 → filter user_hubs.

    DEP-02 verify: else branch select(UserHub.hub_id) → list_for_hubs.

    KHÔNG dùng fixture editor_user (vì cần user_hubs.role='hub_admin' override).
    """
    dmd_id, tdt_id = seed_hubs_dmd_tdt
    from tests.integration.conftest import GO_SEED_HASH

    # Seed user hub_admin của dmd (KHÔNG có tdt assignment).
    await _seed_hub_admin_user(
        email="hub.admin.dmd@medinet.vn",
        password_hash=GO_SEED_HASH,
        hub_id=dmd_id,
    )

    # Login pattern carry forward conftest._login_get_token (plaintext Admin@123).
    login_r = await auth_client.post(
        "/api/auth/login",
        json={"email": "hub.admin.dmd@medinet.vn", "password": "Admin@123"},
    )
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["data"]["access_token"]

    r = await auth_client.get(
        "/api/hubs?per_page=100",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    hub_ids_returned = {h["id"] for h in body["data"]}
    assert dmd_id in hub_ids_returned, "Hub_admin dmd PHẢI thấy hub dmd"
    assert tdt_id not in hub_ids_returned, (
        "Hub_admin dmd KHÔNG được thấy hub tdt (filter user_hubs)"
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_post_hubs_returns_403_forbidden(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 3 ROADMAP success criteria #3:
    Hub_admin POST /api/hubs (create hub mới) → 403 FORBIDDEN.

    DEP-04 LOCKED: 5 endpoint mutate routers/hubs.py GIỮ require_role("admin")
    — hub_admin KHÔNG được tạo hub mới hoặc đổi metadata hub khác.
    Envelope code = 'FORBIDDEN' (từ require_role existing — KHÔNG đổi tên,
    KHÔNG dùng HUB_ADMIN_REQUIRED — đó là code cho assert_hub_admin_for
    Plan 02-01, dùng cho users.py CRUD scope ở Plan 02-03).
    """
    dmd_id, _ = seed_hubs_dmd_tdt
    from tests.integration.conftest import GO_SEED_HASH

    await _seed_hub_admin_user(
        email="hub.admin.dmd.create@medinet.vn",
        password_hash=GO_SEED_HASH,
        hub_id=dmd_id,
    )
    login_r = await auth_client.post(
        "/api/auth/login",
        json={
            "email": "hub.admin.dmd.create@medinet.vn",
            "password": "Admin@123",
        },
    )
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["data"]["access_token"]

    r = await auth_client.post(
        "/api/hubs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "New Hub Test",
            "code": "newhub",
            "subdomain": "newhub",
            "description": "Hub_admin KHÔNG được tạo",
        },
    )

    assert r.status_code == 403, r.text
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN", (
        "DEP-04 LOCKED: require_role envelope code GIỮ NGUYÊN 'FORBIDDEN' "
        "(KHÔNG dùng HUB_ADMIN_REQUIRED ở đây — đó là code mới cho "
        "assert_hub_admin_for Plan 02-01)."
    )
