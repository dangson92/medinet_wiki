"""Test cho auth.py — trích X-API-Key + OAuth Bearer token từ HTTP header MCP.

Phủ 4 behavior X-API-Key (Phase 8.2) + 3 behavior OAuth token (Phase 8.3):
- Test 1: header có `x-api-key` → extract_api_key trả đúng giá trị.
- Test 2: không có header `x-api-key` → extract_api_key trả None.
- Test 3: ctx thiếu request_context (AttributeError) → extract_api_key trả None.
- Test 4: require_api_key — có key trả key; thiếu key raise ToolError MCP_UNAUTHORIZED.
- Test 5: header `Authorization: Bearer abc` → extract_oauth_token trả "abc".
- Test 6: không có header authorization → extract_oauth_token trả None.
- Test 7: header sai format ("Basic ..." / thiếu token) → extract_oauth_token trả None.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_app.auth import extract_api_key, extract_oauth_token, require_api_key


def _make_ctx(headers: dict[str, str] | None) -> MagicMock:
    """Dựng ctx giả với ctx.request_context.request.headers là dict thật."""
    ctx = MagicMock()
    if headers is None:
        ctx.request_context.request = None
    else:
        ctx.request_context.request.headers = headers
    return ctx


def test_extract_api_key_present() -> None:
    """Test 1: header chứa x-api-key → trả đúng giá trị."""
    ctx = _make_ctx({"x-api-key": "abc123"})
    assert extract_api_key(ctx) == "abc123"


def test_extract_api_key_missing_header() -> None:
    """Test 2: không có header x-api-key → trả None."""
    ctx = _make_ctx({"content-type": "application/json"})
    assert extract_api_key(ctx) is None


def test_extract_api_key_no_request_context() -> None:
    """Test 3: ctx thiếu request_context → trả None (không raise)."""

    # Object thật không có thuộc tính request_context → truy cập raise AttributeError
    class _BareCtx:
        pass

    ctx = _BareCtx()
    assert extract_api_key(ctx) is None


def test_require_api_key_present_returns_key() -> None:
    """Test 4a: header có key → require_api_key trả key."""
    ctx = _make_ctx({"x-api-key": "secret-key"})
    assert require_api_key(ctx) == "secret-key"


def test_require_api_key_missing_raises_tool_error() -> None:
    """Test 4b: thiếu key → raise ToolError chứa MCP_UNAUTHORIZED."""
    ctx = _make_ctx({})
    with pytest.raises(ToolError, match="MCP_UNAUTHORIZED"):
        require_api_key(ctx)


# ---------------------------------------------------------------------------
# Phase 8.3 — extract_oauth_token đọc Authorization: Bearer <token>
# ---------------------------------------------------------------------------


def test_extract_oauth_token_present() -> None:
    """Test 5: header Authorization Bearer → trả đúng token."""
    ctx = _make_ctx({"authorization": "Bearer abc-oauth-token"})
    assert extract_oauth_token(ctx) == "abc-oauth-token"


def test_extract_oauth_token_missing() -> None:
    """Test 6: không có header authorization → trả None (không raise)."""
    ctx = _make_ctx({"content-type": "application/json"})
    assert extract_oauth_token(ctx) is None


def test_extract_oauth_token_malformed() -> None:
    """Test 7: header sai format ("Basic ..." / chỉ "Bearer") → trả None."""
    assert extract_oauth_token(_make_ctx({"authorization": "Basic xyz"})) is None
    assert extract_oauth_token(_make_ctx({"authorization": "Bearer"})) is None
    assert extract_oauth_token(_make_ctx({"authorization": "Bearer "})) is None


def test_extract_oauth_token_no_request_context() -> None:
    """Test 7b: ctx thiếu request_context → trả None (không raise)."""

    class _BareCtx:
        pass

    assert extract_oauth_token(_BareCtx()) is None
