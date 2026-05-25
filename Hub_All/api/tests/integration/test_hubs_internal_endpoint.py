"""Hot-fix 2026-05-25 — integration test endpoint GET /api/hubs/_internal.

Endpoint mới ship để fix Phase 6 HubRegistryClient boot fail-loud 401
(memory `project_phase6_internal_auth_gap` + `vps-upload-500-debug` bug 2).
Endpoint cũ `/api/hubs` yêu cầu JWT/X-API-Key → hub-con boot fetch_initial
KHÔNG có user JWT → 401 → uvicorn exit 1.

`/api/hubs/_internal` gate qua `require_internal_auth` (header X-Internal-Auth
constant-time compare với settings.settings_proxy_secret, Plan 06-03 pattern).
Trả raw list[dict] (KHÔNG envelope) cho HubRegistryClient parse trực tiếp.

3 test cover:
1. Header X-Internal-Auth ĐÚNG → 200 + list hub raw.
2. Header X-Internal-Auth SAI → 401 INTERNAL_AUTH_FAIL.
3. Thiếu header X-Internal-Auth → 401 INTERNAL_AUTH_FAIL.

Reuse fixture `seed_hubs_dmd_tdt` từ test_dep_hubs_scope.py (Phase 2 carry forward).
"""
from __future__ import annotations

import httpx
import pytest

from tests.integration.test_dep_hubs_scope import seed_hubs_dmd_tdt  # noqa: F401


_VALID_SECRET = "x" * 32  # match conftest.py:38 monkeypatch SETTINGS_PROXY_SECRET


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hubs_internal_valid_secret_returns_raw_list(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],  # noqa: F811
) -> None:
    """X-Internal-Auth ĐÚNG → 200 raw list (KHÔNG envelope) + cả 2 hub trả về."""
    dmd_id, tdt_id = seed_hubs_dmd_tdt

    r = await auth_client.get(
        "/api/hubs/_internal",
        headers={"X-Internal-Auth": _VALID_SECRET},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    # Raw list shape — KHÔNG envelope {success, data, meta}
    assert isinstance(body, list), f"Expected raw list, got {type(body).__name__}: {body!r}"
    hub_ids = {h["id"] for h in body}
    assert dmd_id in hub_ids, "Hub dmd phải có trong raw list internal"
    assert tdt_id in hub_ids, "Hub tdt phải có trong raw list internal"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hubs_internal_wrong_secret_returns_401(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],  # noqa: F811
) -> None:
    """X-Internal-Auth SAI → 401 INTERNAL_AUTH_FAIL envelope."""
    _ = seed_hubs_dmd_tdt  # trigger fixture (lifespan + truncate)

    r = await auth_client.get(
        "/api/hubs/_internal",
        headers={"X-Internal-Auth": "wrong-secret-" + "y" * 32},
    )

    assert r.status_code == 401, r.text
    body = r.json()
    # FastAPI HTTPException(detail={...}) wrap → {"detail": {"code": "...", "message": "..."}}
    # Envelope D6: app.exception_handler(HTTPException) wrap thành {success, error}
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_AUTH_FAIL"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hubs_internal_missing_header_returns_401(
    auth_client: httpx.AsyncClient,
    seed_hubs_dmd_tdt: tuple[str, str],  # noqa: F811
) -> None:
    """Thiếu header X-Internal-Auth → 401 INTERNAL_AUTH_FAIL (KHÔNG fallback JWT)."""
    _ = seed_hubs_dmd_tdt

    r = await auth_client.get("/api/hubs/_internal")

    assert r.status_code == 401, r.text
    body = r.json()
    # Envelope D6: app.exception_handler(HTTPException) wrap thành {success, error}
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_AUTH_FAIL"
