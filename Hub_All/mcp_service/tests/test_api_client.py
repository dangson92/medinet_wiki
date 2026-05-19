"""Test cho api_client.py (ApiClient) — dùng respx mock httpx.

Phủ 6 behavior gốc + 3 behavior login() (Phase 8.3 — OAuth flow):
- Test 1: 200 envelope success → trả data đã unwrap.
- Test 2: 401 INVALID_API_KEY → raise ApiUnauthorizedError.
- Test 3: 403 FORBIDDEN → raise ApiForbiddenError.
- Test 4: 400 INVALID_QUERY → raise ApiBadRequestError mang message.
- Test 5: 500 LLM_FAILED → raise ApiServerError.
- Test 6: header X-API-Key gửi đúng giá trị truyền vào.
- Test 7 (login_success): 200 envelope login → trả dict JWT pair đủ field.
- Test 8 (login_wrong_credential): 401 → trả None (KHÔNG raise).
- Test 9 (login_server_error): 500 → raise ApiServerError.
"""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from mcp_app.api_client import (
    ApiBadRequestError,
    ApiClient,
    ApiForbiddenError,
    ApiServerError,
    ApiUnauthorizedError,
)

BASE_URL = "http://localhost:8180"


@respx.mock
async def test_post_unwraps_envelope_data() -> None:
    """Test 1: 200 envelope success → trả thẳng data."""
    respx.post(f"{BASE_URL}/api/search").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "data": {"results": []}, "error": None, "meta": None},
        )
    )
    async with ApiClient(BASE_URL) as client:
        data = await client.post("/api/search", api_key="k", json_body={"query": "x"})
    assert data == {"results": []}


@respx.mock
async def test_401_raises_unauthorized() -> None:
    """Test 2: 401 INVALID_API_KEY → ApiUnauthorizedError."""
    respx.post(f"{BASE_URL}/api/search").mock(
        return_value=httpx.Response(
            401,
            json={
                "success": False,
                "data": None,
                "error": {"code": "INVALID_API_KEY", "message": "Key sai"},
                "meta": None,
            },
        )
    )
    async with ApiClient(BASE_URL) as client:
        with pytest.raises(ApiUnauthorizedError):
            await client.post("/api/search", api_key="bad", json_body={})


@respx.mock
async def test_403_raises_forbidden() -> None:
    """Test 3: 403 FORBIDDEN → ApiForbiddenError."""
    respx.post(f"{BASE_URL}/api/search").mock(
        return_value=httpx.Response(
            403,
            json={
                "success": False,
                "data": None,
                "error": {"code": "FORBIDDEN", "message": "Không có quyền hub"},
                "meta": None,
            },
        )
    )
    async with ApiClient(BASE_URL) as client:
        with pytest.raises(ApiForbiddenError):
            await client.post("/api/search", api_key="k", json_body={})


@respx.mock
async def test_400_raises_bad_request_with_message() -> None:
    """Test 4: 400 INVALID_QUERY → ApiBadRequestError mang message."""
    respx.post(f"{BASE_URL}/api/ask").mock(
        return_value=httpx.Response(
            400,
            json={
                "success": False,
                "data": None,
                "error": {"code": "INVALID_QUERY", "message": "Query rỗng"},
                "meta": None,
            },
        )
    )
    async with ApiClient(BASE_URL) as client:
        with pytest.raises(ApiBadRequestError, match="Query rỗng"):
            await client.post("/api/ask", api_key="k", json_body={})


@respx.mock
async def test_500_raises_server_error() -> None:
    """Test 5: 500 LLM_FAILED → ApiServerError."""
    respx.post(f"{BASE_URL}/api/ask").mock(
        return_value=httpx.Response(
            500,
            json={
                "success": False,
                "data": None,
                "error": {"code": "LLM_FAILED", "message": "LLM lỗi"},
                "meta": None,
            },
        )
    )
    async with ApiClient(BASE_URL) as client:
        with pytest.raises(ApiServerError):
            await client.post("/api/ask", api_key="k", json_body={})


@respx.mock
async def test_x_api_key_header_forwarded() -> None:
    """Test 6: header X-API-Key gửi đúng giá trị truyền vào."""
    route = respx.get(f"{BASE_URL}/api/hubs").mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "data": {"hubs": []}, "error": None, "meta": None},
        )
    )
    async with ApiClient(BASE_URL) as client:
        await client.get("/api/hubs", api_key="secret-key-123")

    assert route.called
    sent_request = route.calls.last.request
    assert sent_request.headers["X-API-Key"] == "secret-key-123"


# ---------------------------------------------------------------------------
# Phase 8.3 — ApiClient.login() gọi POST /api/auth/login (D-02)
# ---------------------------------------------------------------------------


@pytest.mark.critical
@respx.mock
async def test_login_success() -> None:
    """Test 7: 200 envelope login → trả dict JWT pair đủ field + body đúng."""
    route = respx.post(f"{BASE_URL}/api/auth/login").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "access_token": "jwt-access",
                    "refresh_token": "jwt-refresh",
                    "expires_at": 1234567890,
                    "user": {"id": "u1", "email": "a@b.com", "role": "admin"},
                },
                "error": None,
                "meta": None,
            },
        )
    )
    async with ApiClient(BASE_URL) as client:
        data = await client.login("a@b.com", "pwd")

    assert data is not None
    assert data["access_token"] == "jwt-access"
    assert data["refresh_token"] == "jwt-refresh"
    assert data["expires_at"] == 1234567890
    assert data["user"]["email"] == "a@b.com"
    # Body request đúng {email, password}.
    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body == {"email": "a@b.com", "password": "pwd"}


@pytest.mark.critical
@respx.mock
async def test_login_wrong_credential() -> None:
    """Test 8: 401 → login() trả None (KHÔNG raise — credential sai là kết quả hợp lệ)."""
    respx.post(f"{BASE_URL}/api/auth/login").mock(
        return_value=httpx.Response(
            401,
            json={
                "success": False,
                "data": None,
                "error": {"code": "INVALID_CREDENTIALS", "message": "Sai"},
                "meta": None,
            },
        )
    )
    async with ApiClient(BASE_URL) as client:
        data = await client.login("a@b.com", "sai")

    assert data is None


@respx.mock
async def test_login_server_error() -> None:
    """Test 9: 500 → login() raise ApiServerError (lỗi hạ tầng, khác credential sai)."""
    respx.post(f"{BASE_URL}/api/auth/login").mock(
        return_value=httpx.Response(
            500,
            json={
                "success": False,
                "data": None,
                "error": {"code": "INTERNAL", "message": "Lỗi server"},
                "meta": None,
            },
        )
    )
    async with ApiClient(BASE_URL) as client:
        with pytest.raises(ApiServerError):
            await client.login("a@b.com", "pwd")
