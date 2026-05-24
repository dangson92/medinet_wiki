"""Integration test audit_logs payload actor metadata — Phase 2 Plan 02-04 DEP-05.

2 scenario verify ROADMAP success criteria #4:
1. Hub_admin dmd POST /api/users → audit_logs row action='user.create' payload chứa
   actor_role='hub_admin' + actor_hub_id='<dmd-uuid>'.
2. Super admin POST /api/users → audit_logs row payload chứa actor_role='admin'
   + actor_hub_id IS NULL.

W1 isolation note: `app_with_auth` fixture (conftest.py:264-284) đã TRUNCATE 8 bảng
per-test RESTART IDENTITY CASCADE — fixture seed dưới KHÔNG cần re-truncate.

W2 schema note: hubs table 10 cột (migration 0001:80-106 + 0003:47-74) — INSERT 9 cột
(bỏ updated_at server_default NOW()) là VALID.

Carry forward patterns:
- `_seed_hub_admin_user` + `seed_hubs_dmd_tdt` từ Plan 02-02 + 02-03 (duplicate
  inline để Plan 02-04 self-contained — Plan 02-05 closeout sẽ consolidate).
- `_wait_audit_row` poll-based wait pattern conftest.py:778-806 (audit_flush_loop
  background task — KHÔNG sync, phải poll).
- asyncpg direct connect cho query JSONB payload->>'actor_role'.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid as _uuid

import httpx
import pytest
from sqlalchemy import text


# Reuse helpers từ Plan 02-03 — duplicate inline để Plan 02-04 self-contained.
async def _seed_hub_admin_user(*, email: str, hub_id: str) -> str:
    """W1: app_with_auth TRUNCATE per-test → KHÔNG cần re-truncate."""
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
            {"id": user_id, "email": email, "hash": GO_SEED_HASH,
             "name": "Hub Admin Audit Test"},
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
async def seed_hubs_dmd_tdt() -> tuple[str, str]:
    """W1: TRUNCATE auto. W2: hubs 10 cột — INSERT 9 cột valid (bỏ updated_at
    server_default NOW() — migration 0001:80-106 + 0003:47-74).
    """
    from app.db.session import get_engine

    engine = get_engine()
    dmd_id = str(_uuid.uuid4())
    tdt_id = str(_uuid.uuid4())
    async with engine.begin() as conn:
        for hub_id, slug, name, code in [
            (dmd_id, "dmd", "Đỗ Minh Đường", "dmd"),
            (tdt_id, "tdt", "Thuốc Dân Tộc", "tdt"),
        ]:
            await conn.execute(
                text(
                    "INSERT INTO hubs (id, slug, name, code, subdomain, status, "
                    "is_active, created_at, updated_at) "
                    "VALUES (:id, :slug, :name, :code, :sub, 'active', TRUE, "
                    "NOW(), NOW())"
                ),
                {"id": hub_id, "slug": slug, "name": name,
                 "code": code, "sub": slug},
            )
    return dmd_id, tdt_id


async def _wait_audit_row(
    target_email: str, *, action: str = "user.create", timeout_s: float = 3.0
) -> dict[str, object]:
    """Poll audit_logs cho row có payload->>'email' == target_email.

    audit_flush_loop background task batch flush (KHÔNG sync) — poll-based wait
    tránh flaky sleep (carry forward conftest.py:778-806 pattern).

    Returns:
        dict payload đã parse JSON.

    Raises:
        AssertionError nếu timeout.
    """
    from app.db.session import get_engine

    engine = get_engine()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    "SELECT payload FROM audit_logs "
                    "WHERE action = :action AND payload->>'email' = :email "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"action": action, "email": target_email},
            )
            row = result.fetchone()
            if row is not None:
                payload = row[0]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                return payload
        await asyncio.sleep(0.05)
    raise AssertionError(
        f"audit_logs row action={action} email={target_email} KHÔNG xuất hiện "
        f"trong {timeout_s}s — audit_flush_loop có thể chưa flush"
    )


async def _login(client: httpx.AsyncClient, email: str, password: str) -> str:
    r = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_user_create_audit_payload_nested_correctly(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 1 ROADMAP success criteria #4:
    Hub_admin dmd POST /api/users → audit_logs payload nest
    actor_role='hub_admin' + actor_hub_id=<dmd-uuid>.
    """
    dmd_id, _ = seed_hubs_dmd_tdt
    await _seed_hub_admin_user(email="hub.admin.audit@dmd.vn", hub_id=dmd_id)
    token = await _login(auth_client, "hub.admin.audit@dmd.vn", "Admin@123")

    target_email = f"audit.target.dmd.{_uuid.uuid4()}@dmd.vn"
    r = await auth_client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": target_email,
            "name": "Audit Target DMD",
            "password": "Pass1234",
            "hub_id": dmd_id,
            "role": "viewer",
        },
    )
    assert r.status_code == 201, r.text

    # Poll audit_logs cho row vừa INSERT (audit_flush_loop background batch).
    payload = await _wait_audit_row(target_email=target_email)

    assert payload.get("actor_role") == "hub_admin", (
        f"DEP-05: payload.actor_role phải = 'hub_admin', got {payload.get('actor_role')!r}"
    )
    assert payload.get("actor_hub_id") == dmd_id, (
        f"DEP-05: payload.actor_hub_id phải = '{dmd_id}', "
        f"got {payload.get('actor_hub_id')!r}"
    )
    assert payload.get("email") == target_email, "extra fields phải preserve"
    assert payload.get("role") == "viewer", "extra fields phải preserve"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_super_admin_user_create_audit_payload_actor_admin_null_hub(
    auth_client: httpx.AsyncClient,
    admin_token: str,
    seed_hubs_dmd_tdt: tuple[str, str],
) -> None:
    """Scenario 2 ROADMAP success criteria #4:
    Super admin POST /api/users → audit_logs payload nest
    actor_role='admin' + actor_hub_id IS NULL.
    """
    dmd_id, _ = seed_hubs_dmd_tdt

    target_email = f"audit.target.super.{_uuid.uuid4()}@dmd.vn"
    r = await auth_client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": target_email,
            "name": "Audit Target Super",
            "password": "Pass1234",
            "hub_id": dmd_id,
            "role": "viewer",
        },
    )
    assert r.status_code == 201, r.text

    payload = await _wait_audit_row(target_email=target_email)

    assert payload.get("actor_role") == "admin", (
        f"DEP-05: super admin payload.actor_role phải = 'admin', "
        f"got {payload.get('actor_role')!r}"
    )
    assert payload.get("actor_hub_id") is None, (
        f"DEP-05: super admin payload.actor_hub_id phải IS NULL, "
        f"got {payload.get('actor_hub_id')!r}"
    )
