"""Phase 6 Plan 06-03 Wave 3 Task 1 — Unit test require_api_key branch hub_name.

Per PLAN <behavior> 6 test:
1. settings.hub_name="central" + valid key → ApiKeyService.verify_key (M2 local).
2. settings.hub_name="yte" + valid key → request.app.state.api_key_verify_client.verify (proxy).
3. settings.hub_name="yte" + client=None → 503 APIKEY_VERIFY_CLIENT_UNAVAILABLE.
4. settings.hub_name="yte" + client.verify return None → 401 API_KEY_INVALID.
5. Missing X-API-Key → 401 API_KEY_MISSING (M2 regression — KHÔNG branch).
6. settings.hub_name="central" + verify_key return None → 401 API_KEY_INVALID.

Pattern: Mock get_settings + Request + ApiKeyService + ApiKeyVerifyClient.

Decision traceability:
- D-V3-Phase6-A LOCKED — Hub con branch HTTP proxy via app.state.api_key_verify_client.
- Plan 06-01 Wave 1 Settings.hub_name read.
- Plan 06-02 Wave 2 ApiKeyVerifyClient.verify() signature.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.auth.api_key import require_api_key


def _make_request(client: Any | None = ...) -> MagicMock:  # noqa: ANN401
    """Tạo Request mock với app.state.api_key_verify_client.

    Default: client = MagicMock với async verify method. Truyền `None` để
    test 503; truyền `...` (ellipsis sentinel) để bỏ qua attr (getattr return None).
    """
    request = MagicMock()
    if client is ...:
        client = MagicMock()
        client.verify = AsyncMock(return_value={"id": "key-1"})
    request.app.state.api_key_verify_client = client
    return request


def _make_settings(hub_name: str) -> SimpleNamespace:
    """Mock Settings với hub_name only — đủ cho require_api_key branch logic."""
    return SimpleNamespace(hub_name=hub_name, settings_proxy_secret="x" * 32)


# --------------------------------------------------------------------------
# Test 1: settings.hub_name="central" + valid key → ApiKeyService.verify_key
# --------------------------------------------------------------------------


async def test_central_valid_key_calls_local_apikey_service() -> None:
    """Test 1 — central hub: dùng ApiKeyService.verify_key (M2 local AES-GCM)."""
    request = _make_request()
    db = MagicMock()
    expected_principal = {"id": "key-1", "permissions": ["read"]}

    with (
        patch(
            "app.auth.api_key.get_settings",
            return_value=_make_settings("central"),
        ),
        patch("app.auth.api_key.ApiKeyService") as mock_service_cls,
    ):
        mock_service = MagicMock()
        mock_service.verify_key = AsyncMock(return_value=expected_principal)
        mock_service_cls.return_value = mock_service

        result = await require_api_key(
            request=request, x_api_key="mdk_valid", db=db
        )

    assert result == expected_principal
    mock_service.verify_key.assert_awaited_once_with("mdk_valid")
    # Hub con client KHÔNG được dùng ở central path
    request.app.state.api_key_verify_client.verify.assert_not_awaited()


# --------------------------------------------------------------------------
# Test 2: settings.hub_name="yte" + valid key → ApiKeyVerifyClient.verify
# --------------------------------------------------------------------------


async def test_hub_con_valid_key_calls_app_state_client() -> None:
    """Test 2 — hub con: dùng request.app.state.api_key_verify_client.verify."""
    expected_principal = {"id": "key-1", "permissions": ["read"]}
    client = MagicMock()
    client.verify = AsyncMock(return_value=expected_principal)
    request = _make_request(client=client)
    db = MagicMock()

    with (
        patch(
            "app.auth.api_key.get_settings",
            return_value=_make_settings("yte"),
        ),
        patch("app.auth.api_key.ApiKeyService") as mock_service_cls,
    ):
        result = await require_api_key(
            request=request, x_api_key="mdk_valid", db=db
        )

    assert result == expected_principal
    client.verify.assert_awaited_once_with("mdk_valid")
    # Central ApiKeyService KHÔNG được instantiate ở hub con path
    mock_service_cls.assert_not_called()


# --------------------------------------------------------------------------
# Test 3: settings.hub_name="yte" + client=None → 503 APIKEY_VERIFY_CLIENT_UNAVAILABLE
# --------------------------------------------------------------------------


async def test_hub_con_missing_client_raises_503() -> None:
    """Test 3 — hub con boot fail → app.state.api_key_verify_client=None → 503."""
    request = _make_request(client=None)
    db = MagicMock()

    with patch(
        "app.auth.api_key.get_settings",
        return_value=_make_settings("yte"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(
                request=request, x_api_key="mdk_any", db=db
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "APIKEY_VERIFY_CLIENT_UNAVAILABLE"


# --------------------------------------------------------------------------
# Test 4: settings.hub_name="yte" + client return None → 401 API_KEY_INVALID
# --------------------------------------------------------------------------


async def test_hub_con_invalid_key_raises_401_invalid() -> None:
    """Test 4 — hub con + client.verify return None → 401 API_KEY_INVALID."""
    client = MagicMock()
    client.verify = AsyncMock(return_value=None)
    request = _make_request(client=client)
    db = MagicMock()

    with patch(
        "app.auth.api_key.get_settings",
        return_value=_make_settings("yte"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(
                request=request, x_api_key="mdk_bad", db=db
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "API_KEY_INVALID"


# --------------------------------------------------------------------------
# Test 5: Missing X-API-Key → 401 API_KEY_MISSING (M2 regression)
# --------------------------------------------------------------------------


async def test_missing_header_raises_401_missing() -> None:
    """Test 5 — Missing X-API-Key (None) → 401 API_KEY_MISSING bất kể hub_name."""
    request = _make_request()
    db = MagicMock()

    # KHÔNG cần mock get_settings — early return trước branch
    with pytest.raises(HTTPException) as exc_info:
        await require_api_key(request=request, x_api_key=None, db=db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "API_KEY_MISSING"


# --------------------------------------------------------------------------
# Test 6: settings.hub_name="central" + verify_key return None → 401 API_KEY_INVALID
# --------------------------------------------------------------------------


async def test_central_invalid_key_raises_401_invalid() -> None:
    """Test 6 — central + ApiKeyService.verify_key None → 401 API_KEY_INVALID."""
    request = _make_request()
    db = MagicMock()

    with (
        patch(
            "app.auth.api_key.get_settings",
            return_value=_make_settings("central"),
        ),
        patch("app.auth.api_key.ApiKeyService") as mock_service_cls,
    ):
        mock_service = MagicMock()
        mock_service.verify_key = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(
                request=request, x_api_key="mdk_bad", db=db
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "API_KEY_INVALID"
