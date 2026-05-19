"""Fixture chung cho test MCP Service — Phase 8.2 Plan 05.

Cung cấp:
- `mock_ctx`     — factory tạo `ctx` MCP giả với (hoặc không có) header X-API-Key.
- `reset_api_client` — autouse, reset singleton `_api_client` của server trước/sau
  mỗi test để base_url không leak giữa các test.
- `api_base_url` — base URL dùng cho respx mock + override config qua env MCP_API_BASE_URL.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# Base URL giả dùng xuyên suốt test tích hợp — respx route khớp theo URL này.
_API_BASE_URL = "http://testserver-api"


@pytest.fixture
def mock_ctx():
    """Factory tạo `ctx` MCP giả.

    Trả về hàm `_make(api_key=...)`:
    - `api_key` là chuỗi → `ctx.request_context.request.headers` là dict thật
      `{"x-api-key": api_key}` → `extract_api_key` đọc được key.
    - `api_key is None` → headers là dict rỗng `{}` → `extract_api_key` trả `None`
      → tool raise ToolError MCP_UNAUTHORIZED.

    Dùng dict thật (không MagicMock) cho `headers` để `.get("x-api-key")` trả
    đúng giá trị/None — MagicMock sẽ trả Mock object cho mọi `.get(...)`.
    """

    def _make(api_key: str | None = "test-key-123") -> MagicMock:
        ctx = MagicMock()
        headers: dict[str, str] = {"x-api-key": api_key} if api_key is not None else {}
        ctx.request_context.request.headers = headers
        return ctx

    return _make


@pytest.fixture(autouse=True)
def reset_api_client():
    """Reset singleton ApiClient của server trước + sau mỗi test.

    `mcp_app.server._api_client` là singleton lazy-init. Nếu không reset, base_url
    của test trước leak sang test sau (respx route không khớp). Đặt `None` để
    `_get_client()` tạo ApiClient mới từ config (đã bị override bởi `api_base_url`).
    """
    import mcp_app.server as server

    server._api_client = None
    yield
    server._api_client = None


@pytest.fixture
def api_base_url(monkeypatch: pytest.MonkeyPatch) -> str:
    """Base URL API Service giả + override config để ApiClient dùng đúng URL.

    Set env `MCP_API_BASE_URL` và xoá cache `get_settings` (lru_cache) để
    `_get_client()` khởi tạo ApiClient với base_url khớp respx mock.
    """
    from mcp_app.config import get_settings

    monkeypatch.setenv("MCP_API_BASE_URL", _API_BASE_URL)
    get_settings.cache_clear()
    yield _API_BASE_URL
    get_settings.cache_clear()
