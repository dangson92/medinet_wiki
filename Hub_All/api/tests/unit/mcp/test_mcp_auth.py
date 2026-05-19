"""Unit test MCP auth — Phase 8.1 Plan 03 Task 1.

Pure-Python logic test — KHÔNG cần Postgres/Redis. Phủ auth gate qua monkeypatch mock:
- Thiếu X-API-Key header → ToolError MCP_UNAUTHORIZED.
- API key không hợp lệ / đã thu hồi → ToolError MCP_UNAUTHORIZED.

Deviation từ PLAN.md (viết theo API mcp==1.9.4):
- PLAN ghi monkeypatch "app.mcp.auth.get_http_headers" → nhưng get_http_headers KHÔNG
  tồn tại trong mcp==1.27.1. Thay vào đó:
  * Tạo mock ctx với ctx.request_context.request.headers.get() trả value tương ứng.
  * Monkeypatch "app.mcp.server.authenticate_mcp_request" trực tiếp để kiểm soát
    output (cho test key sai: mock trả ValueError MCP_UNAUTHORIZED).
- PLAN gọi list_hubs() không có tham số → thực tế signature list_hubs(ctx: Context).
  Test phải truyền mock ctx.

Threat coverage:
- T-08.1-01-S  — Spoofing: thiếu header → gate reject.
- T-08.1-01-S2 — Spoofing: key đã thu hồi → gate reject.
- D-06 (CONTEXT.md) — key sai → KHÔNG để tool chạy.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from app.mcp import server as mcp_server_module


def _make_ctx(api_key: str | None = None) -> MagicMock:
    """Dựng mock MCP Context với HTTP headers giả lập.

    ctx.request_context.request.headers.get("x-api-key") → api_key (hoặc None).
    Tái hiện cách _get_api_key_from_ctx() trong auth.py đọc header Starlette Request.
    """
    ctx = MagicMock()
    headers = MagicMock()
    if api_key is not None:
        headers.get = MagicMock(return_value=api_key)
    else:
        headers.get = MagicMock(return_value=None)
    ctx.request_context.request.headers = headers
    return ctx


@pytest.fixture(autouse=True)
def _inject_mock_pool() -> None:
    """Inject mock pool vào singleton trước mỗi test — KHÔNG cần Postgres."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire = MagicMock(return_value=mock_conn)
    mcp_server_module.set_pool(mock_pool)


@pytest.mark.asyncio
async def test_missing_api_key_raises_tool_error() -> None:
    """Thiếu X-API-Key header → authenticate_mcp_request raise ValueError → list_hubs raise ToolError.

    D-06: key thiếu → MCP error ngay transport level, KHÔNG để tool chạy.
    """
    ctx = _make_ctx(api_key=None)  # không có x-api-key
    with pytest.raises(ToolError) as exc_info:
        await mcp_server_module.list_hubs(ctx)
    assert "MCP_UNAUTHORIZED" in str(exc_info.value)


@pytest.mark.asyncio
async def test_invalid_api_key_raises_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """API key không hợp lệ / đã thu hồi → authenticate_mcp_request raise ValueError → ToolError.

    T-08.1-01-S2: ApiKeyService.verify_key check is_active=TRUE trong DB.
    Dùng monkeypatch authenticate_mcp_request ở server module để tránh cần DB thật.
    """
    # Monkeypatch authenticate_mcp_request để simulate key thu hồi
    async def _fake_auth(ctx: object, pool: object) -> None:
        raise ValueError("MCP_UNAUTHORIZED: API key không hợp lệ hoặc đã thu hồi")

    monkeypatch.setattr(
        "app.mcp.server.authenticate_mcp_request",
        _fake_auth,
    )

    ctx = _make_ctx(api_key="invalid-key-revoked")
    with pytest.raises(ToolError) as exc_info:
        await mcp_server_module.list_hubs(ctx)
    assert "MCP_UNAUTHORIZED" in str(exc_info.value)


@pytest.mark.asyncio
async def test_search_wiki_auth_gate() -> None:
    """search_wiki thiếu key → ToolError MCP_UNAUTHORIZED (D-06).

    Xác nhận auth gate áp dụng cho TẤT CẢ tool, không chỉ list_hubs.
    """
    ctx = _make_ctx(api_key=None)  # không có x-api-key
    with pytest.raises(ToolError) as exc_info:
        await mcp_server_module.search_wiki(ctx, query="test query")
    assert "MCP_UNAUTHORIZED" in str(exc_info.value)
