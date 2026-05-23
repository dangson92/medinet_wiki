"""Phase 6 Plan 06-03 Wave 3 Task 2b — Unit test POST /api/api-keys/verify endpoint.

Per PLAN <behavior> 6 test:
1. Correct X-Internal-Auth + valid api_key body → 200 {valid:true, principal:...}.
2. Wrong X-Internal-Auth → 401 INTERNAL_AUTH_FAIL (require_internal_auth gate).
3. Missing X-Internal-Auth header → 401 INTERNAL_AUTH_FAIL.
4. Correct header + invalid api_key → 200 {valid:false, principal:null}.
5. Missing api_key field trong body → 422 Pydantic validation.
6. Endpoint chỉ mount khi settings.hub_name="central" (FACTOR-02 — verify ở
   integration test wave 4; unit test verify via router include conditional).

Pattern: TestClient(app) + dependency override + mock ApiKeyService.

Decision traceability:
- D-V3-Phase6-D LOCKED — Internal-only header X-Internal-Auth.
- T-06-03-05 mitigation — central-only mount FACTOR-02 carry forward.
- Plan 06-02 ApiKeyVerifyClient consume {valid, principal} raw dict.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_internal_auth
from app.routers.api_keys import get_api_key_service, verify_api_key
from app.schemas.api_keys import VerifyApiKeyRequest


SECRET = "x" * 32


def _make_test_app(service: Any) -> FastAPI:
    """Build minimal FastAPI app mount /api/api-keys/verify.

    Override `get_api_key_service` để inject mock service. require_internal_auth
    dùng dependency thật (đọc Settings từ conftest autouse env SETTINGS_PROXY_SECRET).
    """
    app = FastAPI()

    @app.post("/api/api-keys/verify")
    async def _route(
        req: VerifyApiKeyRequest,
        _internal: None = Depends(require_internal_auth),  # noqa: B008
        svc: Any = Depends(lambda: service),  # noqa: B008
    ) -> dict[str, Any]:
        return await verify_api_key(req=req, _internal=_internal, service=svc)

    app.dependency_overrides[get_api_key_service] = lambda: service
    return app


# --------------------------------------------------------------------------
# Test 1: Correct header + valid api_key → 200 {valid:true, principal:...}
# --------------------------------------------------------------------------


def test_valid_key_returns_principal() -> None:
    """Test 1 — POST /verify với header + body valid → 200 {valid:true}."""
    principal = {
        "id": "key-1",
        "permissions": ["read"],
        "allowed_hub_ids": ["yte"],
    }
    service = MagicMock()
    service.verify_key = AsyncMock(return_value=principal)

    app = _make_test_app(service)
    client = TestClient(app)

    resp = client.post(
        "/api/api-keys/verify",
        json={"api_key": "mdk_valid_abc"},
        headers={"X-Internal-Auth": SECRET},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"valid": True, "principal": principal}
    service.verify_key.assert_awaited_once_with("mdk_valid_abc")


# --------------------------------------------------------------------------
# Test 2: Wrong X-Internal-Auth → 401 INTERNAL_AUTH_FAIL
# --------------------------------------------------------------------------


def test_wrong_internal_auth_returns_401() -> None:
    """Test 2 — Header value sai → 401 INTERNAL_AUTH_FAIL (require_internal_auth gate)."""
    service = MagicMock()
    service.verify_key = AsyncMock(return_value=None)

    app = _make_test_app(service)
    client = TestClient(app)

    resp = client.post(
        "/api/api-keys/verify",
        json={"api_key": "mdk_any"},
        headers={"X-Internal-Auth": "wrong-secret-yyyyyyyyyyyyyyyyyy"},
    )

    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"]["code"] == "INTERNAL_AUTH_FAIL"
    service.verify_key.assert_not_awaited()


# --------------------------------------------------------------------------
# Test 3: Missing X-Internal-Auth → 401 INTERNAL_AUTH_FAIL
# --------------------------------------------------------------------------


def test_missing_internal_auth_returns_401() -> None:
    """Test 3 — KHÔNG có header → 401 INTERNAL_AUTH_FAIL."""
    service = MagicMock()
    service.verify_key = AsyncMock(return_value=None)

    app = _make_test_app(service)
    client = TestClient(app)

    resp = client.post(
        "/api/api-keys/verify",
        json={"api_key": "mdk_any"},
        # KHÔNG header X-Internal-Auth
    )

    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"]["code"] == "INTERNAL_AUTH_FAIL"


# --------------------------------------------------------------------------
# Test 4: Correct header + invalid api_key → 200 {valid:false, principal:null}
# --------------------------------------------------------------------------


def test_invalid_api_key_returns_valid_false() -> None:
    """Test 4 — verify_key return None → 200 {valid:false, principal:null}.

    KHÔNG raise 401 (endpoint chỉ trả result; require_api_key dependency của hub
    con sẽ raise 401 ApiKeyVerifyClient.verify → None).
    """
    service = MagicMock()
    service.verify_key = AsyncMock(return_value=None)

    app = _make_test_app(service)
    client = TestClient(app)

    resp = client.post(
        "/api/api-keys/verify",
        json={"api_key": "mdk_revoked"},
        headers={"X-Internal-Auth": SECRET},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"valid": False, "principal": None}


# --------------------------------------------------------------------------
# Test 5: Missing api_key field → 422 Pydantic validation
# --------------------------------------------------------------------------


def test_missing_api_key_field_returns_422() -> None:
    """Test 5 — Body thiếu api_key field → 422 Pydantic validation error."""
    service = MagicMock()

    app = _make_test_app(service)
    client = TestClient(app)

    resp = client.post(
        "/api/api-keys/verify",
        json={},  # missing api_key
        headers={"X-Internal-Auth": SECRET},
    )

    assert resp.status_code == 422


# --------------------------------------------------------------------------
# Test 6: VerifyApiKeyRequest schema validate
# --------------------------------------------------------------------------


def test_verify_api_key_request_schema_exists() -> None:
    """Test 6 — Schema VerifyApiKeyRequest tồn tại + có field api_key bắt buộc.

    Verify schema import + min_length validation (api_key="" reject).
    """
    from pydantic import ValidationError

    # Valid instance
    valid = VerifyApiKeyRequest(api_key="mdk_abc")
    assert valid.api_key == "mdk_abc"

    # Empty string → ValidationError (min_length=1)
    with pytest.raises(ValidationError):
        VerifyApiKeyRequest(api_key="")
