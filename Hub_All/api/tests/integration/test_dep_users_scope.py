"""Integration test users.py CRUD scope — Phase 2 Plan 02-03 (DEP-03 + D-V3.1-Phase2-E + B1 iter 1).

7 scenario verify ROADMAP Phase 2 success criteria #2 (5 cũ + 2 mới B1 iter 1):
1. Super admin POST /api/users any hub → 201.
2. Hub_admin dmd POST /api/users (hub_id=dmd) → 201.
3. Hub_admin dmd POST /api/users (hub_id=tdt) → 403 HUB_ADMIN_REQUIRED.
4. Hub_admin dmd PATCH /api/users/:id/role escalation role='admin' → 403 (T-02-02-E).
5. Hub_admin dmd DELETE user-thuộc-CHỈ-dmd → 200 (B1 iter 1 single-hub pass).
6. Hub_admin dmd DELETE user-thuộc-dmd+tdt → 403 CROSS_HUB_USER_DELETE_DENIED (B1 iter 1 cross-hub mới).
7. Hub_admin dmd DELETE user-thuộc-CHỈ-tdt → 403 HUB_ADMIN_REQUIRED (B1 iter 1 other-hub deny).

W1 isolation note: `app_with_auth` fixture (conftest.py:264-284) đã TRUNCATE 8 bảng
per-test RESTART IDENTITY CASCADE — fixture seed dưới KHÔNG cần re-truncate.

W2 schema note: hubs table 10 cột (migration 0001:80-106 + 0003:47-74) — INSERT 9 cột
(bỏ updated_at server_default NOW()) là VALID.

W4 coverage note: chạy với --cov-fail-under=80 ở acceptance criteria.

W5 FE breakage note: Phase 2 ship trước Phase 3 FE-04 → hub_admin gọi GET /api/users
qua FE cũ (chưa pass hub_id query) sẽ thấy 400 HUB_ID_REQUIRED. Acceptable theo
Phase 2 → Phase 3 sequential dep; Plan 02-05 closeout sẽ note operator broadcast.

Carry forward patterns:
- `tests/integration/test_dep_hubs_scope.py` (Plan 02-02) — `_seed_hub_admin_user` +
  `seed_hubs_dmd_tdt` fixture DRY duplicate inline cho Plan 02-03 self-contained.
- `tests/integration/conftest.py` — auth_client + admin_token + GO_SEED_HASH fixture.
- Plan 02-01 `assert_hub_admin_for` validator function (BLOCKING dep — Wave 1).
"""
from __future__ import annotations

import uuid as _uuid

import httpx
import pytest
from sqlalchemy import text


async def _seed_user_in_hubs(
    *, email: str, hub_ids: list[str], role: str = "viewer"
) -> str:
    """Seed user qua DB direct + assignment user_hubs cho 1+ hub.

    B1 iter 1: hỗ trợ multi-hub user (test #6 cross-hub denied case).

    Args:
        email: user email.
        hub_ids: list hub UUID str (≥ 1; 2+ cho cross-hub test).
        role: users.role global (default 'viewer').

    Returns:
        user_id str.
    """
    from app.db.session import get_engine

    from tests.integration.conftest import GO_SEED_HASH

    engine = get_engine()
    user_id = str(_uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, role, "
                "phone, department, status, is_active, created_at, updated_at) "
                "VALUES (:id, :email, :hash, :name, :role, NULL, NULL, "
                "'active', TRUE, NOW(), NOW())"
            ),
            {
                "id": user_id, "email": email, "hash": GO_SEED_HASH,
                "name": f"Test {email}", "role": role,
            },
        )
        for hub_id in hub_ids:
            await conn.execute(
                text(
                    "INSERT INTO user_hubs (user_id, hub_id, assigned_at) "
                    "VALUES (:uid, :hid, NOW())"
                ),
                {"uid": user_id, "hid": hub_id},
            )
    return user_id


async def _seed_user_in_hub(*, email: str, hub_id: str, role: str = "viewer") -> str:
    """Shortcut single-hub variant (carry forward Plan 02-02 pattern)."""
    return await _seed_user_in_hubs(email=email, hub_ids=[hub_id], role=role)


async def _seed_hub_admin_user(*, email: str, hub_id: str) -> str:
    """Seed hub_admin user (users.role='editor' global + user_hubs.role='hub_admin').

    Carry forward Plan 02-02 helper — duplicate inline để Plan 02-03 self-contained.
    W1: app_with_auth TRUNCATE per-test → KHÔNG cần re-truncate.
    """
    from app.db.session import get_engine

    from tests.integration.conftest import GO_SEED_HASH

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
                "id": user_id, "email": email, "hash": GO_SEED_HASH,
                "name": "Hub Admin Test",
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


@pytest.fixture
async def seed_hubs_dmd_tdt(app_with_auth: object) -> tuple[str, str]:
    """Tạo 2 hub dmd + tdt qua DB direct (carry forward Plan 02-02).

    W1: app_with_auth TRUNCATE per-test → KHÔNG cần re-truncate.
    W2: hubs 10 cột — INSERT 9 cột valid (bỏ updated_at).
    """
    _ = app_with_auth  # ensure lifespan + engine init
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
            {"id": dmd_id, "slug": "dmd", "name": "Đỗ Minh Đường",
             "code": "dmd", "subdomain": "dmd"},
        )
        await conn.execute(
            text(
                "INSERT INTO hubs (id, slug, name, code, subdomain, status, "
                "is_active, created_at, updated_at) "
                "VALUES (:id, :slug, :name, :code, :subdomain, 'active', TRUE, "
                "NOW(), NOW())"
            ),
            {"id": tdt_id, "slug": "tdt", "name": "Thuốc Dân Tộc",
             "code": "tdt", "subdomain": "tdt"},
        )
    return dmd_id, tdt_id


async def _login(client: httpx.AsyncClient, email: str, password: str) -> str:
    """Login + return access_token (carry forward conftest pattern)."""
    r = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_super_admin_create_user_any_hub_returns_201(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 1 ROADMAP success criteria #2:
    Super admin POST /api/users any hub → 201 (bypass assert_hub_admin_for)."""
    dmd_id, _ = seed_hubs_dmd_tdt

    r = await auth_client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": f"super.created.{_uuid.uuid4()}@dmd.vn",
            "name": "User by super admin",
            "password": "Pass1234",
            "hub_id": dmd_id,
            "role": "viewer",
        },
    )

    assert r.status_code == 201, r.text


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_create_user_in_own_hub_returns_201(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 2: Hub_admin dmd POST /api/users (hub_id=dmd) → 201."""
    dmd_id, _ = seed_hubs_dmd_tdt
    await _seed_hub_admin_user(email="hub.admin.create.own@dmd.vn", hub_id=dmd_id)
    token = await _login(auth_client, "hub.admin.create.own@dmd.vn", "Admin@123")

    r = await auth_client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": f"viewer.dmd.{_uuid.uuid4()}@dmd.vn",
            "name": "Viewer DMD",
            "password": "Pass1234",
            "hub_id": dmd_id,
            "role": "viewer",
        },
    )

    assert r.status_code == 201, r.text


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_create_user_in_other_hub_returns_403_hub_admin_required(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 3: Hub_admin dmd POST /api/users (hub_id=tdt) → 403 HUB_ADMIN_REQUIRED."""
    dmd_id, tdt_id = seed_hubs_dmd_tdt
    await _seed_hub_admin_user(email="hub.admin.create.other@dmd.vn", hub_id=dmd_id)
    token = await _login(auth_client, "hub.admin.create.other@dmd.vn", "Admin@123")

    r = await auth_client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": f"viewer.tdt.{_uuid.uuid4()}@tdt.vn",
            "name": "Viewer TDT",
            "password": "Pass1234",
            "hub_id": tdt_id,
            "role": "viewer",
        },
    )

    assert r.status_code == 403, r.text
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "HUB_ADMIN_REQUIRED"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_patch_role_admin_escalation_blocked_403(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 4 T-02-02-E mitigation:
    Hub_admin dmd PATCH /api/users/:id/role body{role='admin', hub_id=dmd} → 403."""
    dmd_id, _ = seed_hubs_dmd_tdt
    await _seed_hub_admin_user(email="hub.admin.escalate@dmd.vn", hub_id=dmd_id)
    target_user_id = await _seed_user_in_hub(
        email=f"target.escalate.{_uuid.uuid4()}@dmd.vn",
        hub_id=dmd_id,
        role="viewer",
    )
    token = await _login(auth_client, "hub.admin.escalate@dmd.vn", "Admin@123")

    r = await auth_client.patch(
        f"/api/users/{target_user_id}/role",
        headers={"Authorization": f"Bearer {token}"},
        json={"hub_id": dmd_id, "role": "admin"},  # escalation attempt
    )

    assert r.status_code == 403, r.text
    body = r.json()
    assert body["error"]["code"] == "HUB_ADMIN_REQUIRED", (
        f"T-02-02-E mitigation: escalation phải reject với HUB_ADMIN_REQUIRED, "
        f"got {body['error'].get('code')!r}"
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_delete_single_hub_user_of_own_hub_passes_200(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 5 B1 iter 1 DEP-03 spec compliance:
    Hub_admin dmd DELETE user-thuộc-CHỈ-dmd → 200.

    DEP-03 line 24 spec literal include DELETE trong hub_admin scope.
    D-V3.1-Phase2-E narrowed: hub_admin xoá user thuộc CHỈ hub mình → OK.
    """
    dmd_id, _ = seed_hubs_dmd_tdt
    await _seed_hub_admin_user(email="hub.admin.del.own@dmd.vn", hub_id=dmd_id)
    target_user_id = await _seed_user_in_hub(
        email=f"target.del.own.{_uuid.uuid4()}@dmd.vn",
        hub_id=dmd_id,
        role="viewer",
    )
    token = await _login(auth_client, "hub.admin.del.own@dmd.vn", "Admin@123")

    r = await auth_client.delete(
        f"/api/users/{target_user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200, r.text


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_delete_cross_hub_user_returns_403_cross_hub_denied(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 6 B1 iter 1 mới:
    Hub_admin dmd DELETE user-thuộc-dmd+tdt → 403 CROSS_HUB_USER_DELETE_DENIED.

    D-V3.1-Phase2-E: user thuộc nhiều hub → cross-hub op → super admin only.
    Envelope code MỚI để phân biệt với HUB_ADMIN_REQUIRED (scope violation).
    """
    dmd_id, tdt_id = seed_hubs_dmd_tdt
    await _seed_hub_admin_user(email="hub.admin.del.cross@dmd.vn", hub_id=dmd_id)
    target_user_id = await _seed_user_in_hubs(
        email=f"target.cross.{_uuid.uuid4()}@cross.vn",
        hub_ids=[dmd_id, tdt_id],  # multi-hub user
        role="viewer",
    )
    token = await _login(auth_client, "hub.admin.del.cross@dmd.vn", "Admin@123")

    r = await auth_client.delete(
        f"/api/users/{target_user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 403, r.text
    body = r.json()
    assert body["error"]["code"] == "CROSS_HUB_USER_DELETE_DENIED", (
        f"B1 iter 1: cross-hub DELETE phải reject với CROSS_HUB_USER_DELETE_DENIED, "
        f"got {body['error'].get('code')!r}"
    )


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_delete_user_in_other_hub_returns_403_hub_admin_required(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 7 B1 iter 1:
    Hub_admin dmd DELETE user-thuộc-CHỈ-tdt → 403 HUB_ADMIN_REQUIRED.

    Target user single-hub nhưng hub đó ≠ caller's scope → assert_hub_admin_for
    raise HUB_ADMIN_REQUIRED (KHÔNG CROSS_HUB_USER_DELETE_DENIED).
    """
    dmd_id, tdt_id = seed_hubs_dmd_tdt
    await _seed_hub_admin_user(email="hub.admin.del.other@dmd.vn", hub_id=dmd_id)
    target_user_id = await _seed_user_in_hub(
        email=f"target.other.{_uuid.uuid4()}@tdt.vn",
        hub_id=tdt_id,  # user single-hub nhưng hub khác caller
        role="viewer",
    )
    token = await _login(auth_client, "hub.admin.del.other@dmd.vn", "Admin@123")

    r = await auth_client.delete(
        f"/api/users/{target_user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 403, r.text
    body = r.json()
    assert body["error"]["code"] == "HUB_ADMIN_REQUIRED", (
        f"B1 iter 1: other-hub single-user DELETE phải reject với HUB_ADMIN_REQUIRED "
        f"(qua assert_hub_admin_for), got {body['error'].get('code')!r}"
    )
