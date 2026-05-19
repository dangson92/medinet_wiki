"""Test cho server.py — 3 tool MCP gọi API Service qua HTTP.

Phủ 9 behavior gốc + 3 behavior OAuth resolve credential (Phase 8.3 Plan 03):
- Test 1 (list_hubs): unwrap data.items → HubList.
- Test 2 (search_wiki single-hub): post /api/search với hub_ids=[hub_id].
- Test 3 (search_wiki cross-hub): post /api/search/cross-hub với hub_ids=None.
- Test 4 (ask_wiki single-hub): post /api/ask → AskAnswer.
- Test 5 (ask_wiki cross-hub): post /api/search/answer → map citations field id/snippet.
- Test 6 (auth fail): require_api_key raise → ToolError MCP_UNAUTHORIZED.
- Test 7 (API 401): ApiUnauthorizedError → ToolError MCP_UNAUTHORIZED.
- Test 8 (API 403): ApiForbiddenError → ToolError HUB_ACCESS_DENIED.
- Test 9 (API 5xx): ApiServerError → ToolError không leak stack trace.
- Test 10 (resolve OAuth): ctx có Bearer token hợp lệ → tool chạy, forward JWT.
- Test 11 (OAuth token invalid): Bearer token không trong store → ToolError MCP_UNAUTHORIZED.
- Test 12 (no credential): không header → ToolError MCP_UNAUTHORIZED.

Mock ở tầng ApiClient (_get_client) — KHÔNG cần API Service thật, KHÔNG cần respx.
CHỈ import 3 tool + helper từ mcp_app.server (KHÔNG import build_asgi_app/main).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_app.api_client import (
    ApiForbiddenError,
    ApiServerError,
    ApiUnauthorizedError,
)
from mcp_app.server import ask_wiki, list_hubs, search_wiki


@pytest.fixture
def ctx() -> MagicMock:
    """ctx giả với header x-api-key hợp lệ."""
    c = MagicMock()
    c.request_context.request.headers = {"x-api-key": "test-key"}
    return c


def _patch_client(monkeypatch: pytest.MonkeyPatch, client: AsyncMock) -> None:
    """Thay _get_client() bằng client mock."""
    monkeypatch.setattr("mcp_app.server._get_client", lambda: client)


async def test_list_hubs_unwraps_items(
    ctx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 1: list_hubs map data.items → HubList."""
    client = AsyncMock()
    client.get.return_value = {
        "items": [{"id": "h1", "name": "Hub 1", "description": "d"}]
    }
    _patch_client(monkeypatch, client)

    result = await list_hubs(ctx)

    assert len(result.hubs) == 1
    assert result.hubs[0].id == "h1"
    assert result.hubs[0].name == "Hub 1"
    client.get.assert_awaited_once()
    assert client.get.call_args.args[0] == "/api/hubs"


async def test_search_wiki_single_hub(
    ctx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 2: search_wiki hub_id → post /api/search với hub_ids=[hub_id]."""
    client = AsyncMock()
    client.post.return_value = {
        "results": [
            {
                "id": "c1",
                "content": "noi dung",
                "score": 0.9,
                "title": "Doc 1",
                "hub_name": "Hub 1",
                "hub_id": "h1",
            }
        ]
    }
    _patch_client(monkeypatch, client)

    result = await search_wiki(ctx, query="q", hub_id="h1", top_k=5)

    assert result.total == 1
    assert result.results[0].chunk_id == "c1"
    assert client.post.call_args.args[0] == "/api/search"
    assert client.post.call_args.kwargs["json_body"]["hub_ids"] == ["h1"]


async def test_search_wiki_cross_hub(
    ctx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 3: search_wiki hub_id=None → post /api/search/cross-hub với hub_ids=None."""
    client = AsyncMock()
    client.post.return_value = {"results": []}
    _patch_client(monkeypatch, client)

    await search_wiki(ctx, query="q", hub_id=None)

    assert client.post.call_args.args[0] == "/api/search/cross-hub"
    assert client.post.call_args.kwargs["json_body"]["hub_ids"] is None


async def test_ask_wiki_single_hub(
    ctx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 4: ask_wiki hub_id → post /api/ask → AskAnswer."""
    client = AsyncMock()
    client.post.return_value = {
        "answer": "Trả lời [1]",
        "citations": [
            {
                "chunk_id": "c1",
                "document_name": "Doc 1",
                "hub_name": "Hub 1",
                "content_snippet": "trích",
                "score": 0.8,
            }
        ],
    }
    _patch_client(monkeypatch, client)

    result = await ask_wiki(ctx, query="q", hub_id="h1")

    assert result.answer == "Trả lời [1]"
    assert result.citations[0].chunk_id == "c1"
    assert result.citations[0].snippet == "trích"
    assert client.post.call_args.args[0] == "/api/ask"
    assert client.post.call_args.kwargs["json_body"]["hub_id"] == "h1"


async def test_ask_wiki_cross_hub(
    ctx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 5: ask_wiki hub_id=None → post /api/search/answer, map citation field id/snippet."""
    client = AsyncMock()
    client.post.return_value = {
        "answer": "Trả lời cross",
        "citations": [
            {
                "id": "c9",
                "document_name": "Doc 9",
                "hub_name": "Hub 9",
                "snippet": "trích cross",
                "score": 0.7,
            }
        ],
    }
    _patch_client(monkeypatch, client)

    result = await ask_wiki(ctx, query="q", hub_id=None)

    assert result.answer == "Trả lời cross"
    assert result.citations[0].chunk_id == "c9"
    assert result.citations[0].snippet == "trích cross"
    assert client.post.call_args.args[0] == "/api/search/answer"


async def test_auth_fail_raises_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 6: thiếu X-API-Key → ToolError MCP_UNAUTHORIZED."""
    bare_ctx = MagicMock()
    bare_ctx.request_context.request.headers = {}
    client = AsyncMock()
    _patch_client(monkeypatch, client)

    with pytest.raises(ToolError, match="MCP_UNAUTHORIZED"):
        await list_hubs(bare_ctx)


async def test_api_401_maps_to_unauthorized(
    ctx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 7: API 401 → ApiUnauthorizedError → ToolError MCP_UNAUTHORIZED."""
    client = AsyncMock()
    client.get.side_effect = ApiUnauthorizedError("key sai")
    _patch_client(monkeypatch, client)

    with pytest.raises(ToolError, match="MCP_UNAUTHORIZED"):
        await list_hubs(ctx)


async def test_api_403_maps_to_hub_access_denied(
    ctx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 8: API 403 hub isolation → ApiForbiddenError → ToolError HUB_ACCESS_DENIED."""
    client = AsyncMock()
    client.post.side_effect = ApiForbiddenError("không có quyền hub")
    _patch_client(monkeypatch, client)

    with pytest.raises(ToolError, match="HUB_ACCESS_DENIED"):
        await search_wiki(ctx, query="q", hub_id="h1")


async def test_api_5xx_no_stack_trace_leak(
    ctx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 9: API 5xx → ToolError message sạch, không leak stack trace nội bộ."""
    client = AsyncMock()
    client.post.side_effect = ApiServerError("LLM_FAILED: lỗi gọi LLM")
    _patch_client(monkeypatch, client)

    with pytest.raises(ToolError) as exc_info:
        await ask_wiki(ctx, query="q", hub_id="h1")

    msg = str(exc_info.value)
    assert "API_ERROR" in msg
    # Message KHÔNG chứa dấu vết stack trace nội bộ
    assert "Traceback" not in msg
    assert "File \"" not in msg


# ---------------------------------------------------------------------------
# Phase 8.3 Plan 03 — tool resolve OAuth token → forward downstream JWT
# ---------------------------------------------------------------------------


async def _seed_oauth_token(
    monkeypatch: pytest.MonkeyPatch,
    *,
    access_token: str,
    downstream_jwt: str,
    downstream_refresh: str = "ds-refresh",
) -> "object":
    """Tạo OAuthStore :memory:, seed 1 OAuth token, wire vào provider+store singleton.

    Trả store để test inspect sau (vd verify downstream JWT đã rotate).
    """
    import time

    from mcp_app.oauth.provider import MedinetOAuthProvider
    from mcp_app.oauth.store import OAuthStore

    store = OAuthStore(db_path=":memory:")
    await store.init_schema()
    await store.save_token(
        access_token=access_token,
        refresh_token="oauth-refresh",
        client_id="client-test",
        scopes=["wiki"],
        downstream_jwt=downstream_jwt,
        downstream_refresh_token=downstream_refresh,
        user_payload={"id": "u1", "email": "a@b.com", "role": "admin"},
        expires_at=int(time.time()) + 3600,
    )
    provider = MedinetOAuthProvider(
        store=store,
        api_client=None,
        issuer_url="https://mcp.example.com",
        access_token_ttl=3600,
        refresh_token_ttl=2592000,
    )
    monkeypatch.setattr("mcp_app.server._get_oauth_store", lambda: store)
    monkeypatch.setattr("mcp_app.server._get_oauth_provider", lambda: provider)
    return store


async def test_tool_resolves_oauth_token(
    mock_ctx_oauth, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 10: ctx có Bearer token hợp lệ → tool chạy, forward downstream JWT."""
    store = await _seed_oauth_token(
        monkeypatch, access_token="oauth-tok-1", downstream_jwt="jwt-downstream-1"
    )
    client = AsyncMock()
    client.get.return_value = {"items": [{"id": "h1", "name": "Hub 1"}]}
    _patch_client(monkeypatch, client)

    result = await list_hubs(mock_ctx_oauth(token="oauth-tok-1"))

    assert len(result.hubs) == 1
    # Tool forward downstream JWT (không X-API-Key)
    assert client.get.call_args.kwargs.get("jwt") == "jwt-downstream-1"
    assert client.get.call_args.kwargs.get("api_key") is None
    await store.aclose()


async def test_tool_oauth_token_invalid(
    mock_ctx_oauth, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 11: Bearer token không trong store → ToolError MCP_UNAUTHORIZED."""
    store = await _seed_oauth_token(
        monkeypatch, access_token="oauth-tok-1", downstream_jwt="jwt-1"
    )
    client = AsyncMock()
    _patch_client(monkeypatch, client)

    with pytest.raises(ToolError, match="MCP_UNAUTHORIZED"):
        await list_hubs(mock_ctx_oauth(token="token-khong-ton-tai"))
    await store.aclose()


async def test_tool_no_credential(
    mock_ctx_oauth, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 12: không header nào → ToolError MCP_UNAUTHORIZED."""
    store = await _seed_oauth_token(
        monkeypatch, access_token="oauth-tok-1", downstream_jwt="jwt-1"
    )
    client = AsyncMock()
    _patch_client(monkeypatch, client)

    with pytest.raises(ToolError, match="MCP_UNAUTHORIZED"):
        await list_hubs(mock_ctx_oauth(token=None))
    await store.aclose()
