"""Test cho api_client.py (ApiClient) — dùng respx mock httpx.

Phủ 6 behavior:
- Test 1: 200 envelope success → trả data đã unwrap.
- Test 2: 401 INVALID_API_KEY → raise ApiUnauthorizedError.
- Test 3: 403 FORBIDDEN → raise ApiForbiddenError.
- Test 4: 400 INVALID_QUERY → raise ApiBadRequestError mang message.
- Test 5: 500 LLM_FAILED → raise ApiServerError.
- Test 6: header X-API-Key gửi đúng giá trị truyền vào.
"""
from __future__ import annotations

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
