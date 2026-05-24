"""Smoke E2E test v3.1 RBAC hub_admin — 4 scenario.

Plan 04-02 v3.1 Phase 4 MIGRATE-02 — verify Phase 2 ship semantic E2E:
- (1) super admin: GET /api/hubs → ALL + POST user any hub → 201
- (2) hub_admin dmd: GET /api/hubs → CHỈ dmd + POST user dmd → 201 + POST user tdt → 403 HUB_ADMIN_REQUIRED
- (3) hub_admin tdt: mirror (2) với hub tdt
- (4) viewer: POST /api/users → 403 FORBIDDEN (cross-hub privilege denied)

Audit forensic chain (D-V3.1-Phase4-E LOCKED): scenario 1 + 2 + 3 verify
`payload->>'actor_role'` + `payload->>'actor_hub_id'` qua SQLAlchemy async engine query.

Pattern carry forward:
- `tests/integration/conftest.py` — app_with_auth + auth_client + admin_user + admin_token
  + _login_get_token + GO_SEED_HASH_PLAINTEXT + reset audit queue per-test isolation.
- `tests/integration/test_dep_hubs_scope.py` — _seed_hub_admin_user + seed_hubs_dmd_tdt
  fixture (reused inline).
- `tests/integration/test_audit_actor_metadata.py` — audit forensic JSONB query pattern.

D-V3.1-Phase4-C LOCKED: testcontainers in-process (postgres_container + redis_container
session-scoped — auto-spin pgvector/pgvector:pg16 + redis:7).

Note: scenario 4 chỉ verify POST /api/users → 403 (cross-hub privilege denied) — GET
documents path defer Phase 4 + ngoài MIGRATE-02 critical-path scope.
"""
from __future__ import annotations

import asyncio
import uuid as _uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import text


# ═════════════════════════════════════════════════════════════════════════
# Helpers — seed user pattern carry forward test_dep_hubs_scope.py
# ═════════════════════════════════════════════════════════════════════════


async def _seed_hub_admin_user(
    *, email: str, password_hash: str, hub_id: str
) -> str:
    """Seed user role='editor' global + user_hubs.role='hub_admin' per-hub.

    Pattern carry forward test_dep_hubs_scope.py:37-76 (Plan 02-02 ship).
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
                "name": "Hub Admin Smoke E2E",
            },
        )
        await conn.execute(
            text(
                "INSERT INTO user_hubs (user_id, hub_id, role, assigned_at) "
                "VALUES (:uid, :hid, 'hub_admin', NOW())"
            ),
            {"uid": user_id, "hid": hub_id},
        )
    return user_id


# ═════════════════════════════════════════════════════════════════════════
# Fixture — seed 2 hub thật (dmd + tdt) per memory project_real_hubs_deployment
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture
async def seed_hubs_dmd_tdt(app_with_auth: object) -> tuple[str, str]:
    """Tạo 2 hub dmd + tdt qua DB direct.

    Pattern carry forward test_dep_hubs_scope.py:79-125 (Plan 02-02 ship).
    app_with_auth fixture auto-truncate 8 bảng per-test isolation.
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


# ═════════════════════════════════════════════════════════════════════════
# Helpers — audit forensic query (D-V3.1-Phase4-E)
# ═════════════════════════════════════════════════════════════════════════


async def _assert_audit_actor_metadata(
    *,
    action: str,
    expected_role: str,
    expected_hub_id: str | None,
    timeout: float = 3.0,
) -> None:
    """Poll audit_logs WHERE action sau BackgroundTask emit + assert metadata.

    Pattern carry forward test_audit_actor_metadata.py (Plan 02-04 ship):
    - payload->>'actor_role' + payload->>'actor_hub_id' JSONB query.
    - Poll-based wait cho BackgroundTask fire-and-forget timing (memory
      project_fastapi_bgtask_commit).
    """
    from app.db.session import get_engine

    engine = get_engine()
    elapsed = 0.0
    row = None
    while elapsed < timeout:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    "SELECT payload->>'actor_role' AS actor_role, "
                    "       payload->>'actor_hub_id' AS actor_hub_id "
                    "FROM audit_logs WHERE action = :action "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"action": action},
            )
            row = result.first()
        if row is not None:
            break
        await asyncio.sleep(0.2)
        elapsed += 0.2

    assert row is not None, (
        f"Audit row not found: action={action} timeout={timeout}s"
    )
    actual_role, actual_hub_id = row[0], row[1]
    assert actual_role == expected_role, (
        f"Audit actor_role mismatch action={action}: "
        f"expected={expected_role} got={actual_role}"
    )
    assert actual_hub_id == expected_hub_id, (
        f"Audit actor_hub_id mismatch action={action}: "
        f"expected={expected_hub_id} got={actual_hub_id}"
    )


# ═════════════════════════════════════════════════════════════════════════
# Scenario 1 — super admin full access
# ═════════════════════════════════════════════════════════════════════════


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_1_super_admin_full_access(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Super admin GET /api/hubs → ALL + POST user dmd → 201 + audit actor_role='admin'."""
    dmd_id, tdt_id = seed_hubs_dmd_tdt
    headers = {"Authorization": f"Bearer {admin_token}"}

    # GET /api/hubs → trả cả dmd + tdt
    r = await auth_client.get("/api/hubs?per_page=100", headers=headers)
    assert r.status_code == 200, r.text
    hub_ids_returned = {h["id"] for h in r.json()["data"]}
    assert dmd_id in hub_ids_returned, "Super admin phải thấy dmd"
    assert tdt_id in hub_ids_returned, "Super admin phải thấy tdt"

    # POST /api/users hub_id=<dmd> → 201
    new_email = f"new-dmd-{_uuid.uuid4().hex[:8]}@test.vn"
    r = await auth_client.post(
        "/api/users",
        headers=headers,
        json={
            "email": new_email,
            "name": "New User DMD",
            "password": "Pass1234!",
            "hub_id": dmd_id,
            "role": "viewer",
        },
    )
    assert r.status_code == 201, (
        f"Super POST /api/users dmd fail: {r.status_code} {r.text}"
    )

    # Audit forensic verify — super admin → actor_role='admin' + actor_hub_id=NULL
    await _assert_audit_actor_metadata(
        action="user.create",
        expected_role="admin",
        expected_hub_id=None,
    )


# ═════════════════════════════════════════════════════════════════════════
# Scenario 2 — hub_admin dmd scoped
# ═════════════════════════════════════════════════════════════════════════


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_2_hub_admin_dmd_scoped(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Hub_admin dmd: GET /api/hubs → CHỈ dmd + POST user dmd → 201 + POST user tdt → 403."""
    dmd_id, tdt_id = seed_hubs_dmd_tdt
    from tests.integration.conftest import GO_SEED_HASH

    await _seed_hub_admin_user(
        email="hadmin.dmd.scen2@medinet.vn",
        password_hash=GO_SEED_HASH,
        hub_id=dmd_id,
    )

    login_r = await auth_client.post(
        "/api/auth/login",
        json={"email": "hadmin.dmd.scen2@medinet.vn", "password": "Admin@123"},
    )
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # GET /api/hubs → CHỈ dmd (filter central + tdt qua Plan 02-02 D-V3.1-Phase2-A)
    r = await auth_client.get("/api/hubs?per_page=100", headers=headers)
    assert r.status_code == 200, r.text
    hub_ids_returned = {h["id"] for h in r.json()["data"]}
    assert dmd_id in hub_ids_returned, "Hub_admin dmd PHẢI thấy dmd"
    assert tdt_id not in hub_ids_returned, (
        "Hub_admin dmd KHÔNG được thấy tdt (D-V3.1-Phase2-A filter authoritative)"
    )

    # POST /api/users hub_id=<dmd> → 201
    new_email_ok = f"scoped-dmd-{_uuid.uuid4().hex[:8]}@test.vn"
    r = await auth_client.post(
        "/api/users",
        headers=headers,
        json={
            "email": new_email_ok,
            "name": "Scoped User DMD",
            "password": "Pass1234!",
            "hub_id": dmd_id,
            "role": "viewer",
        },
    )
    assert r.status_code == 201, (
        f"Hub_admin dmd POST user dmd fail: {r.status_code} {r.text}"
    )

    # POST /api/users hub_id=<tdt> → 403 HUB_ADMIN_REQUIRED envelope
    new_email_reject = f"reject-tdt-{_uuid.uuid4().hex[:8]}@test.vn"
    r = await auth_client.post(
        "/api/users",
        headers=headers,
        json={
            "email": new_email_reject,
            "name": "Reject User TDT",
            "password": "Pass1234!",
            "hub_id": tdt_id,
            "role": "viewer",
        },
    )
    assert r.status_code == 403, (
        f"Hub_admin dmd POST user tdt should be 403: {r.status_code} {r.text}"
    )
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "HUB_ADMIN_REQUIRED", (
        f"Expected HUB_ADMIN_REQUIRED envelope, got: {body['error']}"
    )

    # Audit forensic verify — hub_admin dmd success path → actor_role='hub_admin' + actor_hub_id=dmd_id
    await _assert_audit_actor_metadata(
        action="user.create",
        expected_role="hub_admin",
        expected_hub_id=dmd_id,
    )


# ═════════════════════════════════════════════════════════════════════════
# Scenario 3 — hub_admin tdt mirror (cross-hub isolation symmetric)
# ═════════════════════════════════════════════════════════════════════════


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_3_hub_admin_tdt_scoped(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Hub_admin tdt mirror scenario 2 — verify cross-hub isolation symmetric."""
    dmd_id, tdt_id = seed_hubs_dmd_tdt
    from tests.integration.conftest import GO_SEED_HASH

    await _seed_hub_admin_user(
        email="hadmin.tdt.scen3@medinet.vn",
        password_hash=GO_SEED_HASH,
        hub_id=tdt_id,
    )

    login_r = await auth_client.post(
        "/api/auth/login",
        json={"email": "hadmin.tdt.scen3@medinet.vn", "password": "Admin@123"},
    )
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # GET /api/hubs → CHỈ tdt
    r = await auth_client.get("/api/hubs?per_page=100", headers=headers)
    assert r.status_code == 200, r.text
    hub_ids_returned = {h["id"] for h in r.json()["data"]}
    assert tdt_id in hub_ids_returned, "Hub_admin tdt PHẢI thấy tdt"
    assert dmd_id not in hub_ids_returned, (
        "Hub_admin tdt KHÔNG được thấy dmd (filter symmetric)"
    )

    # POST /api/users hub_id=<tdt> → 201
    new_email_ok = f"scoped-tdt-{_uuid.uuid4().hex[:8]}@test.vn"
    r = await auth_client.post(
        "/api/users",
        headers=headers,
        json={
            "email": new_email_ok,
            "name": "Scoped User TDT",
            "password": "Pass1234!",
            "hub_id": tdt_id,
            "role": "viewer",
        },
    )
    assert r.status_code == 201, (
        f"Hub_admin tdt POST user tdt fail: {r.status_code} {r.text}"
    )

    # POST /api/users hub_id=<dmd> → 403 HUB_ADMIN_REQUIRED
    new_email_reject = f"reject-dmd-{_uuid.uuid4().hex[:8]}@test.vn"
    r = await auth_client.post(
        "/api/users",
        headers=headers,
        json={
            "email": new_email_reject,
            "name": "Reject User DMD",
            "password": "Pass1234!",
            "hub_id": dmd_id,
            "role": "viewer",
        },
    )
    assert r.status_code == 403, (
        f"Hub_admin tdt POST user dmd should be 403: {r.status_code} {r.text}"
    )
    assert r.json()["error"]["code"] == "HUB_ADMIN_REQUIRED"

    # Audit forensic verify — hub_admin tdt success path → actor_role='hub_admin' + actor_hub_id=tdt_id
    await _assert_audit_actor_metadata(
        action="user.create",
        expected_role="hub_admin",
        expected_hub_id=tdt_id,
    )


# ═════════════════════════════════════════════════════════════════════════
# Scenario 4 — viewer privilege denied
# ═════════════════════════════════════════════════════════════════════════


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_scenario_4_viewer_post_user_forbidden(
    auth_client: httpx.AsyncClient,
    viewer_token: str,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Viewer POST /api/users → 403 FORBIDDEN (viewer KHÔNG có quyền tạo user).

    Viewer KHÔNG được phép POST /api/users (require_role hoặc require_hub_admin reject).
    Envelope code có thể là FORBIDDEN hoặc HUB_ADMIN_REQUIRED depending backend
    implementation ordering — accept cả 2 (Plan 02-03 + 02-01 hierarchy).
    """
    dmd_id, _ = seed_hubs_dmd_tdt
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # POST /api/users → 403 (viewer KHÔNG có quyền create)
    new_email = f"viewer-reject-{_uuid.uuid4().hex[:8]}@test.vn"
    r = await auth_client.post(
        "/api/users",
        headers=headers,
        json={
            "email": new_email,
            "name": "Viewer Reject",
            "password": "Pass1234!",
            "hub_id": dmd_id,
            "role": "viewer",
        },
    )
    assert r.status_code == 403, (
        f"Viewer POST /api/users should be 403: {r.status_code} {r.text}"
    )
    body = r.json()
    assert body["success"] is False
    # Accept FORBIDDEN (require_role) HOẶC HUB_ADMIN_REQUIRED (assert_hub_admin_for)
    # depending backend ordering Plan 02-03.
    assert body["error"]["code"] in ("FORBIDDEN", "HUB_ADMIN_REQUIRED"), (
        f"Viewer reject envelope code unexpected: {body['error']}"
    )
