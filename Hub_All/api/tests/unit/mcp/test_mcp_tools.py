"""Unit test MCP tool behavior + hub isolation — Phase 8.1 Plan 03 Task 2.

Pure-Python: mock authenticate_mcp_request + service layer, KHÔNG cần Postgres/Redis.

Deviation từ PLAN.md:
- PLAN gọi list_hubs() không tham số → thực tế signature list_hubs(ctx: Context).
  Test truyền MagicMock() làm ctx (tool không cần ctx sau khi authenticate đã mock).
- PLAN dùng patch("app.mcp.server.SearchService") → SearchService import LOCAL trong
  search_wiki body → không patch được qua module mcp.server. Phải patch
  "app.services.search_service.SearchService" (module gốc).
- AskService import tại MODULE LEVEL trong server.py → patch "app.mcp.server.AskService" đúng.
- _get_pool() fixture setup: pool.acquire() cần setup __aenter__/__aexit__ đúng cách
  để `async with pool.acquire() as conn:` hoạt động.

Threat coverage:
- T-08.1-02-E  — Elevation: hub ngoài phạm vi → HubIsolationError → ToolError HUB_ACCESS_DENIED.
- D-13 (CONTEXT.md) — hub_id filter, KHÔNG escalation.
- D-14 (CONTEXT.md) — ask_wiki log usage_events non-blocking (asyncio.create_task).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from app.auth.dependencies import UserWithHubs
from app.mcp import server as mcp_server_module
from app.mcp.schemas import AskAnswer, HubList
from app.repositories.hub_isolation import HubIsolationError


def _make_user(role: str = "viewer", hub_ids: list[str] | None = None) -> UserWithHubs:
    """Helper tạo UserWithHubs giả cho test."""
    user = MagicMock()
    user.id = "user-uuid-test"
    user.role = role
    return UserWithHubs(user=user, hub_ids=hub_ids or ["hub-1"])


def _make_mock_pool(fetch_rows: list[dict] | None = None) -> MagicMock:
    """Dựng mock asyncpg.Pool với async context manager acquire() + fetch().

    Tái hiện `async with pool.acquire() as conn: rows = await conn.fetch(...)`.
    """
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    # async with pool.acquire() as conn → conn = mock_conn
    mock_ctx_mgr = MagicMock()
    mock_ctx_mgr.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire = MagicMock(return_value=mock_ctx_mgr)
    # Default fetch trả rỗng; test override khi cần
    mock_conn.fetch = AsyncMock(return_value=fetch_rows or [])
    return mock_pool


@pytest.fixture(autouse=True)
def _inject_mock_pool() -> None:
    """Inject mock pool vào singleton trước mỗi test — KHÔNG cần Postgres."""
    mock_pool = _make_mock_pool()
    mcp_server_module.set_pool(mock_pool)


@pytest.mark.asyncio
async def test_list_hubs_viewer_returns_assigned_hubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """list_hubs viewer: trả chỉ hub được assign (query user_hubs JOIN).

    T-08.1-02-E2: non-admin KHÔNG nhận all hubs → chỉ hub_ids của user.
    """
    user = _make_user(role="viewer", hub_ids=["hub-1"])
    monkeypatch.setattr(
        "app.mcp.server.authenticate_mcp_request",
        AsyncMock(return_value=user),
    )
    # Setup mock pool với fetch trả 1 row
    mock_rows = [{"id": "hub-1", "name": "Hub Y Tế", "description": "Tổng hợp"}]
    mock_pool = _make_mock_pool(fetch_rows=mock_rows)
    mcp_server_module.set_pool(mock_pool)

    ctx = MagicMock()
    result = await mcp_server_module.list_hubs(ctx)

    assert isinstance(result, HubList)
    assert len(result.hubs) == 1
    assert result.hubs[0].id == "hub-1"
    assert result.hubs[0].name == "Hub Y Tế"


@pytest.mark.asyncio
async def test_list_hubs_admin_returns_all_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """list_hubs admin: trả TẤT CẢ hub active (query hubs WHERE status='active').

    T-08.1-02-E2: admin query riêng — KHÔNG bị filter theo user_hubs.
    """
    user = _make_user(role="admin", hub_ids=[])
    monkeypatch.setattr(
        "app.mcp.server.authenticate_mcp_request",
        AsyncMock(return_value=user),
    )
    mock_rows = [
        {"id": "hub-1", "name": "Hub A", "description": None},
        {"id": "hub-2", "name": "Hub B", "description": "Mô tả"},
    ]
    mock_pool = _make_mock_pool(fetch_rows=mock_rows)
    mcp_server_module.set_pool(mock_pool)

    ctx = MagicMock()
    result = await mcp_server_module.list_hubs(ctx)

    assert isinstance(result, HubList)
    assert len(result.hubs) == 2
    assert {h.id for h in result.hubs} == {"hub-1", "hub-2"}


@pytest.mark.asyncio
async def test_search_wiki_hub_isolation_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-13: hub_id ngoài phạm vi user → HubIsolationError → ToolError HUB_ACCESS_DENIED.

    T-08.1-02-E: Elevation of Privilege qua param hub_id — SearchService phải reject.
    Deviation: SearchService import LOCAL trong search_wiki → patch module gốc
    app.services.search_service.SearchService (không phải app.mcp.server.SearchService).
    """
    user = _make_user(role="viewer", hub_ids=["hub-a"])
    monkeypatch.setattr(
        "app.mcp.server.authenticate_mcp_request",
        AsyncMock(return_value=user),
    )
    mock_svc = MagicMock()
    mock_svc.search = AsyncMock(side_effect=HubIsolationError("hub-b ngoài phạm vi"))
    with patch("app.services.search_service.SearchService", return_value=mock_svc):
        ctx = MagicMock()
        with pytest.raises(ToolError) as exc_info:
            await mcp_server_module.search_wiki(ctx, query="test", hub_id="hub-b")
    assert "HUB_ACCESS_DENIED" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ask_wiki_returns_answer_with_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    """ask_wiki trả AskAnswer với answer text + citations list (D-11).

    Xác nhận server.py mapping CitationItem đúng field từ AskResponse.Citation.
    """
    user = _make_user(role="viewer", hub_ids=["hub-1"])
    monkeypatch.setattr(
        "app.mcp.server.authenticate_mcp_request",
        AsyncMock(return_value=user),
    )

    # Dựng mock AskOutcome khớp structure thật
    # outcome.response.answer, outcome.response.citations[i].chunk_id/content_snippet/...
    mock_citation = MagicMock()
    mock_citation.chunk_id = "chunk-uuid-1"
    mock_citation.document_name = "Quy trình khám bệnh.docx"
    mock_citation.hub_name = "Hub Y Tế"
    mock_citation.content_snippet = "Bước 1: đăng ký..."
    mock_citation.score = 0.87

    mock_response = MagicMock()
    mock_response.answer = "Quy trình gồm 3 bước [1]."
    mock_response.citations = [mock_citation]

    mock_usage = MagicMock()
    mock_usage.model = "gpt-4o"
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.total_tokens = 150
    mock_usage.cost_usd = 0.001

    mock_outcome = MagicMock()
    mock_outcome.response = mock_response
    mock_outcome.usage = mock_usage

    mock_svc = MagicMock()
    mock_svc.ask = AsyncMock(return_value=mock_outcome)

    # AskService import MODULE LEVEL → patch tại app.mcp.server.AskService
    def _safe_create_task(coro: object, **kwargs: object) -> MagicMock:
        # Đóng coroutine ngay để tránh RuntimeWarning "coroutine was never awaited"
        if hasattr(coro, "close"):
            coro.close()  # type: ignore[union-attr]
        return MagicMock()

    with patch("app.mcp.server.AskService", return_value=mock_svc):
        # mock asyncio.create_task để D-14 không tạo coroutine thật
        with patch("app.mcp.server.asyncio") as mock_asyncio:
            mock_asyncio.create_task = _safe_create_task
            ctx = MagicMock()
            result = await mcp_server_module.ask_wiki(ctx, query="Quy trình khám bệnh?", hub_id="hub-1")

    assert isinstance(result, AskAnswer)
    assert result.answer == "Quy trình gồm 3 bước [1]."
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "chunk-uuid-1"
    assert result.citations[0].score == pytest.approx(0.87)


@pytest.mark.asyncio
async def test_ask_wiki_logs_usage_nonblocking(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-14: ask_wiki gọi asyncio.create_task(log_usage_event(...)) — non-blocking.

    Xác nhận create_task được gọi 1 lần sau AskService.ask() trả kết quả.
    Patch app.mcp.server.asyncio để intercept create_task trong module scope.
    """
    user = _make_user(role="viewer", hub_ids=["hub-1"])
    monkeypatch.setattr(
        "app.mcp.server.authenticate_mcp_request",
        AsyncMock(return_value=user),
    )

    mock_citation = MagicMock()
    mock_citation.chunk_id = "c1"
    mock_citation.document_name = "doc"
    mock_citation.hub_name = "hub"
    mock_citation.content_snippet = "..."
    mock_citation.score = 0.9

    mock_response = MagicMock()
    mock_response.answer = "Trả lời [1]."
    mock_response.citations = [mock_citation]

    mock_usage = MagicMock()
    mock_usage.model = "gpt-4o"
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 5
    mock_usage.total_tokens = 15
    mock_usage.cost_usd = 0.0001

    mock_outcome = MagicMock()
    mock_outcome.response = mock_response
    mock_outcome.usage = mock_usage

    mock_svc = MagicMock()
    mock_svc.ask = AsyncMock(return_value=mock_outcome)

    create_task_calls: list[object] = []

    def mock_create_task(coro: object, **kwargs: object) -> MagicMock:
        create_task_calls.append(coro)
        # Huỷ coroutine để tránh RuntimeWarning "coroutine was never awaited"
        if hasattr(coro, "close"):
            coro.close()  # type: ignore[union-attr]
        return MagicMock()

    with patch("app.mcp.server.AskService", return_value=mock_svc):
        with patch("app.mcp.server.asyncio") as mock_asyncio:
            mock_asyncio.create_task = mock_create_task
            ctx = MagicMock()
            await mcp_server_module.ask_wiki(ctx, query="test", hub_id="hub-1")

    assert len(create_task_calls) == 1, "asyncio.create_task phải được gọi 1 lần cho D-14"
