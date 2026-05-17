"""Rate-limit + X-API-Key auth integration test — Plan 05-06 (AUX-02 / AUX-03).

Phase 5 endpoint production decorate @limiter.limit = GET /api/audit-logs
(Plan 05-05). Test verify CƠ CHẾ rate-limit qua test-only route mount lên app
`app_with_auth` — KHÔNG sửa production main.py. Limit nhỏ (3/minute) cho
deterministic. slowapi `app.state.limiter` đã wire qua create_app (Plan 05-06 Task 1).

4 test:
1. test_rate_limit_returns_429_envelope — request thứ 4 → 429 envelope shape.
2. test_under_limit_passes — 2 request dưới ngưỡng → 200.
3. test_x_api_key_invalid_rejected (@critical) — X-API-Key sai/thiếu → 401.
4. test_auth_me_not_rate_limited — spam GET /api/auth/me → KHÔNG 429.
"""
from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from fastapi import APIRouter, Depends, Request

from app.auth.api_key import require_api_key
from app.middleware import limiter


def _mount_limited_route(app: Any) -> str:
    """Mount test-only route rate-limited 3/minute với key UNIQUE → return path.

    slowapi limiter counter lưu Redis — share giữa test trong cùng module. slowapi
    key = key_func(request) + scope (tên function decorated) — KHÔNG gồm path nên
    path unique KHÔNG đủ. Override `key_func` của decorator trả giá trị unique
    per-mount → counter cô lập per-test (test_rate_limit_returns_429 KHÔNG leak
    counter sang test_under_limit). KHÔNG sửa production main.py.
    """
    token = uuid.uuid4().hex
    path = f"/test/limited-{token[:8]}"
    r = APIRouter()
    # slowapi gọi per-route key_func KHÔNG đối số (extension.py:499 `lim.key_func()`)
    # — khác key_func module-level (nhận request). Lambda 0-arg trả token unique.
    unique_key = f"ratelimit-test:{token}"

    @r.get(path)
    @limiter.limit("3/minute", key_func=lambda: unique_key)
    async def limited(request: Request) -> dict[str, str]:
        _ = request  # slowapi đọc request để rate-limit key.
        return {"status": "ok"}

    app.include_router(r)
    return path


def _mount_apikey_route(app: Any) -> str:
    """Mount test-only route gate Depends(require_api_key) → return path."""
    path = f"/test/apikey-{uuid.uuid4().hex[:8]}"
    r = APIRouter()

    @r.get(path)
    async def apikey_protected(
        principal: dict[str, Any] = Depends(require_api_key),  # noqa: B008
    ) -> dict[str, Any]:
        return {"principal_id": principal["id"]}

    app.include_router(r)
    return path


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rate_limit_returns_429_envelope(
    app_with_auth: Any,
) -> None:
    """Gọi route rate-limited 4 lần → request thứ 4 trả 429 envelope shape đầy đủ."""
    path = _mount_limited_route(app_with_auth)
    transport = httpx.ASGITransport(app=app_with_auth)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        statuses = []
        last_body: dict[str, Any] = {}
        for _i in range(4):
            resp = await client.get(path)
            statuses.append(resp.status_code)
            last_body = resp.json()

    assert statuses[:3] == [200, 200, 200], statuses
    assert statuses[3] == 429, statuses
    assert set(last_body.keys()) == {"success", "data", "error", "meta"}
    assert last_body["success"] is False
    assert last_body["data"] is None
    assert last_body["meta"] is None
    assert last_body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_under_limit_passes(
    app_with_auth: Any,
) -> None:
    """Gọi route rate-limited 2 lần (dưới ngưỡng 3) → cả 2 trả 200."""
    path = _mount_limited_route(app_with_auth)
    transport = httpx.ASGITransport(app=app_with_auth)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        r1 = await client.get(path)
        r2 = await client.get(path)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_x_api_key_invalid_rejected(
    app_with_auth: Any,
) -> None:
    """X-API-Key sai → 401 API_KEY_INVALID; thiếu header → 401 API_KEY_MISSING.

    Verify require_api_key (Plan 05-06 Task 1) gọi đúng `ApiKeyService.verify_key`
    (BLOCKER 1 — method tên sai → AttributeError → test fail).
    """
    path = _mount_apikey_route(app_with_auth)
    transport = httpx.ASGITransport(app=app_with_auth)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # Key sai (không có row api_keys match) → 401 API_KEY_INVALID.
        r_bad = await client.get(
            path, headers={"X-API-Key": "mdk_bad-key-xxxxx"}
        )
        assert r_bad.status_code == 401, r_bad.text
        body_bad = r_bad.json()
        assert set(body_bad.keys()) == {"success", "data", "error", "meta"}
        assert body_bad["error"]["code"] == "API_KEY_INVALID"

        # Thiếu header → 401 API_KEY_MISSING.
        r_missing = await client.get(path)
        assert r_missing.status_code == 401, r_missing.text
        assert r_missing.json()["error"]["code"] == "API_KEY_MISSING"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_me_not_rate_limited(
    auth_client: httpx.AsyncClient,
    admin_token: str,
) -> None:
    """Spam GET /api/auth/me nhiều lần → KHÔNG 429 (auth/me KHÔNG decorate limiter)."""
    for _i in range(8):
        r = await auth_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code != 429, (
            f"auth/me KHÔNG được rate-limit (AUX-03), got {r.status_code}"
        )
        assert r.status_code == 200, r.text
