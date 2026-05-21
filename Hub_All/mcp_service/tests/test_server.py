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
from mcp_app.server import ask_wiki, list_hubs, register_tools, search_wiki


@pytest.fixture
def ctx() -> MagicMock:
    """ctx giả với header x-api-key hợp lệ."""
    c = MagicMock()
    c.request_context.request.headers = {"x-api-key": "test-key"}
    return c


def _patch_client(monkeypatch: pytest.MonkeyPatch, client: AsyncMock) -> None:
    """Thay _get_client() bằng client mock."""
    monkeypatch.setattr("mcp_app.server._get_client", lambda: client)


async def test_registered_tools_include_read_only_annotations() -> None:
    """Claude/MCP clients need safety annotations to bypass read-only approval gates."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("test")
    register_tools(mcp)

    tools = {tool.name: tool for tool in await mcp.list_tools()}
    expected_titles = {
        "list_hubs": "List hubs",
        "search_wiki": "Search wiki",
        "ask_wiki": "Ask wiki",
    }
    assert set(expected_titles).issubset(tools)
    for name, title in expected_titles.items():
        tool = tools[name]
        assert tool.title == title
        assert tool.annotations is not None
        assert tool.annotations.title == title
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.openWorldHint is False


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
) -> object:
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


# ---------------------------------------------------------------------------
# Phase 8.3 Plan 09 — gap closure wave 9 (HIGH-05 envelope + HIGH-03 concurrency)
# ---------------------------------------------------------------------------


async def test_list_hubs_envelope_data_list_branch(mock_ctx) -> None:
    """list_hubs unwrap envelope `data:[list]` (HIGH-05, regression commit 3dbb378).

    API service `/api/hubs` (resp.paginated) trả envelope `{data:[...], meta:{...}}`
    → `data` đã unwrap là LIST hub. Test verify nhánh `isinstance(data, list)`
    của server.py (dòng 368) — KHÔNG dùng fallback `dict.get("items")`.
    """
    from unittest.mock import AsyncMock, patch

    from mcp_app.auth import Credential
    from mcp_app.server import list_hubs

    # Mock ApiClient — get trả LIST trực tiếp (sau khi envelope `data:[...]` unwrap).
    list_data = [
        {"id": "hub-1", "name": "Hub Một", "description": "Mô tả 1"},
        {"id": "hub-2", "name": "Hub Hai", "description": None},
    ]
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=list_data)

    # Credential signature confirmed (Warning #9): kind, value, oauth_token.
    fake_cred = Credential(kind="api_key", value="test-key", oauth_token=None)

    with (
        patch("mcp_app.server._resolve_credential", AsyncMock(return_value=fake_cred)),
        patch("mcp_app.server._get_client", return_value=fake_client),
    ):
        result = await list_hubs(mock_ctx())

    assert len(result.hubs) == 2
    assert result.hubs[0].id == "hub-1"
    assert result.hubs[0].name == "Hub Một"
    assert result.hubs[1].description is None


async def test_list_hubs_envelope_legacy_items_dict_branch(mock_ctx) -> None:
    """list_hubs unwrap fallback `{items: [...]}` legacy format (HIGH-05 fallback path).

    Fallback `dict.get("items", [])` cho format cũ phòng khi API đổi shape ngược.
    Test chứng minh fallback path đang hoạt động (BOND legacy compat).
    """
    from unittest.mock import AsyncMock, patch

    from mcp_app.auth import Credential
    from mcp_app.server import list_hubs

    legacy_data = {"items": [{"id": "hub-x", "name": "Hub X"}]}
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=legacy_data)
    fake_cred = Credential(kind="api_key", value="k", oauth_token=None)

    with (
        patch("mcp_app.server._resolve_credential", AsyncMock(return_value=fake_cred)),
        patch("mcp_app.server._get_client", return_value=fake_client),
    ):
        result = await list_hubs(mock_ctx())

    assert len(result.hubs) == 1
    assert result.hubs[0].id == "hub-x"


async def test_refresh_jwt_concurrency_single_flight(oauth_store) -> None:
    """2 task song song _call_api gặp 401 → refresh_jwt gọi ĐÚNG 1 LẦN (HIGH-03).

    Audit 2026-05-21 HIGH-03 + Warning #8 (audit checker): assertion nghiêm —
    refresh_mock.call_count == 1 (single-flight), call_state["get_calls"] in
    (3, 4) tùy race ordering.

    Race ordering:
    - 4 calls = 2 task gọi với JWT-OLD song song (cả 2 raise 401) +
      2 task retry với JWT-NEW (cả 2 OK).
    - 3 calls = task 2 vào lock SAU task 1 refresh xong, đọc record thấy JWT
      đã update → skip refresh, retry với JWT-NEW ngay (chỉ 1 lần gọi).
      Trường hợp này task 1 gọi 2 lần (OLD + NEW) + task 2 gọi 1 lần (NEW) = 3.
    """
    import asyncio
    import time
    from unittest.mock import AsyncMock, patch

    from mcp_app.api_client import ApiClient, ApiUnauthorizedError
    from mcp_app.auth import Credential
    from mcp_app.server import _call_api, _refresh_locks

    # Setup oauth_store với 1 token có downstream JWT cũ.
    await oauth_store.save_token(
        access_token="oauth-T",
        refresh_token="oauth-R",
        client_id="client-test",
        scopes=["wiki"],
        downstream_jwt="JWT-OLD",
        downstream_refresh_token="REFRESH-OLD",
        user_payload={"id": 1},
        expires_at=int(time.time()) + 3600,
    )

    # Reset lock pool cho test isolation.
    _refresh_locks.clear()

    # Mock ApiClient:
    # - get(): lần đầu raise ApiUnauthorizedError (401); lần sau trả {"ok": True}.
    # - refresh_jwt(): trả pair JWT mới.
    call_state = {"get_calls": 0}

    async def _fake_get(path, *, jwt=None, api_key=None, params=None):  # type: ignore[no-untyped-def]
        call_state["get_calls"] += 1
        # 401 nếu JWT vẫn là JWT-OLD; OK nếu JWT mới.
        if jwt == "JWT-OLD":
            raise ApiUnauthorizedError("401 mock")
        return {"ok": True, "jwt_used": jwt}

    refresh_mock = AsyncMock(
        return_value={"access_token": "JWT-NEW", "refresh_token": "REFRESH-NEW"}
    )
    fake_client = AsyncMock(spec=ApiClient)
    fake_client.get = _fake_get
    fake_client.refresh_jwt = refresh_mock

    # Credential signature confirmed (Warning #9): kind, value, oauth_token.
    cred = Credential(kind="jwt", value="JWT-OLD", oauth_token="oauth-T")

    with (
        patch("mcp_app.server._get_client", return_value=fake_client),
        patch("mcp_app.server._get_oauth_store", return_value=oauth_store),
    ):
        # asyncio.gather 2 task song song.
        results = await asyncio.gather(
            _call_api(cred, "GET", "/api/test"),
            _call_api(cred, "GET", "/api/test"),
        )

    # HIGH-03 assertion nghiêm (Warning #8): refresh_jwt gọi ĐÚNG 1 lần (single-flight).
    assert refresh_mock.call_count == 1, (
        f"HIGH-03: refresh_jwt phải gọi ĐÚNG 1 lần, nhận {refresh_mock.call_count}"
    )
    # Cả 2 task succeed.
    assert len(results) == 2
    for r in results:
        assert r["ok"] is True
    # Tổng get calls (Warning #8 — siết từ >=3 sang in (3, 4)):
    # Bất kỳ giá trị NGOÀI {3, 4} → behavior sai (vd 5 = double refresh).
    assert call_state["get_calls"] in (3, 4), (
        f"HIGH-03: Expect get_calls ∈ (3, 4) tùy race ordering, "
        f"got {call_state['get_calls']}"
    )

    # Cleanup lock pool.
    _refresh_locks.clear()
