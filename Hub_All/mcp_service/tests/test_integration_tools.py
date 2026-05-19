"""Test tích hợp Phase 8.2 — 3 tool MCP gọi API Service qua boundary HTTP.

Dùng respx mock httpx — KHÔNG cần API Service thật chạy. Verify request shape
+ envelope unwrap + map lỗi.

KHÁC `test_server.py` (Plan 03): test đó mock ở tầng `ApiClient` (`_get_client`).
Plan 05 mock ở tầng HTTP transport (`respx`) — verify cả `ApiClient` + tool cùng
nhau qua đúng boundary HTTP: tool gửi đúng request (path/body/header), unwrap
envelope `{success,data,error}`, map status 401/403/5xx sang `ToolError`.

9 behavior:
- Test 1 (list_hubs happy)        — GET /api/hubs → HubList; header X-API-Key đúng.
- Test 2 (search_wiki single-hub) — POST /api/search; body hub_ids=["h1"].
- Test 3 (search_wiki cross-hub)  — POST /api/search/cross-hub (hub_id None).
- Test 4 (ask_wiki single-hub)    — POST /api/ask; answer giữ marker [1].
- Test 5 (ask_wiki cross-hub)     — POST /api/search/answer (hub_id None).
- Test 6 (auth fail thiếu key)    — ToolError MCP_UNAUTHORIZED; KHÔNG request HTTP.
- Test 7 (API 401)                — ToolError MCP_UNAUTHORIZED.
- Test 8 (hub isolation 403)      — ToolError HUB_ACCESS_DENIED.
- Test 9 (API 5xx)                — ToolError message sạch (không stack trace).
"""
from __future__ import annotations

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from mcp_app.schemas import AskAnswer, HubList, SearchResult
from mcp_app.server import ask_wiki, list_hubs, search_wiki


def _envelope_ok(data: object) -> dict[str, object]:
    """Envelope thành công của API Service."""
    return {"success": True, "data": data, "error": None, "meta": None}


def _envelope_err(code: str, message: str) -> dict[str, object]:
    """Envelope lỗi của API Service."""
    return {
        "success": False,
        "data": None,
        "error": {"code": code, "message": message},
        "meta": None,
    }


# ---------------------------------------------------------------------------
# Test 1 — list_hubs happy path
# ---------------------------------------------------------------------------
@pytest.mark.critical
@respx.mock
async def test_list_hubs_happy(mock_ctx, api_base_url: str) -> None:
    """list_hubs gọi GET /api/hubs, unwrap data.items → HubList; header đúng."""
    route = respx.get(f"{api_base_url}/api/hubs").mock(
        return_value=httpx.Response(
            200,
            json=_envelope_ok(
                {
                    "items": [
                        {"id": "h1", "name": "Hub Y tế", "description": "mô tả 1"},
                        {"id": "h2", "name": "Hub Dược", "description": None},
                    ]
                }
            ),
        )
    )

    result = await list_hubs(mock_ctx(api_key="secret-123"))

    assert isinstance(result, HubList)
    assert len(result.hubs) == 2
    assert result.hubs[0].id == "h1"
    assert result.hubs[0].name == "Hub Y tế"
    # Request gửi đúng header X-API-Key
    assert route.called
    assert route.calls.last.request.headers["X-API-Key"] == "secret-123"


# ---------------------------------------------------------------------------
# Test 2 — search_wiki single-hub
# ---------------------------------------------------------------------------
@respx.mock
async def test_search_wiki_single_hub(mock_ctx, api_base_url: str) -> None:
    """search_wiki(hub_id) → POST /api/search; body chứa hub_ids=["h1"]."""
    route = respx.post(f"{api_base_url}/api/search").mock(
        return_value=httpx.Response(
            200,
            json=_envelope_ok(
                {
                    "results": [
                        {
                            "id": "c1",
                            "hub_id": "h1",
                            "hub_name": "Hub Y tế",
                            "title": "Tài liệu 1",
                            "snippet": "đoạn trích",
                            "content": "nội dung chunk",
                            "score": 0.91,
                        }
                    ]
                }
            ),
        )
    )

    result = await search_wiki(mock_ctx(), query="liều dùng", hub_id="h1", top_k=5)

    assert isinstance(result, SearchResult)
    assert result.total == 1
    assert result.results[0].chunk_id == "c1"
    assert result.results[0].hub_id == "h1"
    # Verify body request: hub_ids=["h1"]
    import json as _json

    sent_body = _json.loads(route.calls.last.request.content)
    assert sent_body["hub_ids"] == ["h1"]
    assert sent_body["query"] == "liều dùng"
    assert sent_body["top_k"] == 5


# ---------------------------------------------------------------------------
# Test 3 — search_wiki cross-hub
# ---------------------------------------------------------------------------
@respx.mock
async def test_search_wiki_cross_hub(mock_ctx, api_base_url: str) -> None:
    """search_wiki(hub_id=None) → POST /api/search/cross-hub; hub_ids=None."""
    route = respx.post(f"{api_base_url}/api/search/cross-hub").mock(
        return_value=httpx.Response(200, json=_envelope_ok({"results": []}))
    )

    result = await search_wiki(mock_ctx(), query="q")

    assert isinstance(result, SearchResult)
    assert result.total == 0
    # Verify gọi đúng path cross-hub
    assert route.called
    import json as _json

    sent_body = _json.loads(route.calls.last.request.content)
    assert sent_body["hub_ids"] is None


# ---------------------------------------------------------------------------
# Test 4 — ask_wiki single-hub
# ---------------------------------------------------------------------------
@respx.mock
async def test_ask_wiki_single_hub(mock_ctx, api_base_url: str) -> None:
    """ask_wiki(hub_id) → POST /api/ask; answer giữ marker [1], citations map đúng."""
    route = respx.post(f"{api_base_url}/api/ask").mock(
        return_value=httpx.Response(
            200,
            json=_envelope_ok(
                {
                    "answer": "Trả lời chi tiết [1]",
                    "citations": [
                        {
                            "chunk_id": "c7",
                            "document_name": "Phác đồ A",
                            "hub_name": "Hub Y tế",
                            "content_snippet": "đoạn trích nguồn",
                            "score": 0.82,
                        }
                    ],
                }
            ),
        )
    )

    result = await ask_wiki(mock_ctx(), query="phác đồ điều trị?", hub_id="h1")

    assert isinstance(result, AskAnswer)
    assert result.answer == "Trả lời chi tiết [1]"
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "c7"
    assert result.citations[0].snippet == "đoạn trích nguồn"
    # Verify gọi đúng path /api/ask (KHÔNG cross-hub)
    assert route.called
    import json as _json

    sent_body = _json.loads(route.calls.last.request.content)
    assert sent_body["hub_id"] == "h1"


# ---------------------------------------------------------------------------
# Test 5 — ask_wiki cross-hub
# ---------------------------------------------------------------------------
@respx.mock
async def test_ask_wiki_cross_hub(mock_ctx, api_base_url: str) -> None:
    """ask_wiki(hub_id=None) → POST /api/search/answer (KHÔNG /api/ask/cross-hub)."""
    route_answer = respx.post(f"{api_base_url}/api/search/answer").mock(
        return_value=httpx.Response(
            200,
            json=_envelope_ok(
                {
                    "answer": "Trả lời cross-hub",
                    "citations": [
                        {
                            "id": "c9",
                            "document_name": "Tài liệu 9",
                            "hub_name": "Hub Dược",
                            "snippet": "trích cross",
                            "score": 0.75,
                        }
                    ],
                }
            ),
        )
    )
    # Route /api/ask/cross-hub KHÔNG được gọi.
    route_wrong = respx.post(f"{api_base_url}/api/ask/cross-hub").mock(
        return_value=httpx.Response(200, json=_envelope_ok({"answer": "", "citations": []}))
    )

    result = await ask_wiki(mock_ctx(), query="q")

    assert isinstance(result, AskAnswer)
    assert result.answer == "Trả lời cross-hub"
    assert result.citations[0].chunk_id == "c9"
    assert result.citations[0].snippet == "trích cross"
    assert route_answer.called
    assert not route_wrong.called


# ---------------------------------------------------------------------------
# Test 6 — auth fail (thiếu key) → ToolError trước khi gọi HTTP
# ---------------------------------------------------------------------------
@pytest.mark.critical
@respx.mock(assert_all_called=False)
async def test_auth_fail_missing_key(mock_ctx, api_base_url: str) -> None:
    """ctx thiếu header x-api-key → ToolError MCP_UNAUTHORIZED; KHÔNG request HTTP."""
    route = respx.get(f"{api_base_url}/api/hubs").mock(
        return_value=httpx.Response(200, json=_envelope_ok({"items": []}))
    )

    with pytest.raises(ToolError, match="MCP_UNAUTHORIZED"):
        await list_hubs(mock_ctx(api_key=None))

    # Tool fail TRƯỚC khi gọi HTTP — respx KHÔNG nhận request nào.
    assert not route.called


# ---------------------------------------------------------------------------
# Test 7 — API trả 401 → ToolError MCP_UNAUTHORIZED
# ---------------------------------------------------------------------------
@pytest.mark.critical
@respx.mock
async def test_api_401_maps_unauthorized(mock_ctx, api_base_url: str) -> None:
    """API 401 INVALID_API_KEY → ToolError MCP_UNAUTHORIZED."""
    respx.get(f"{api_base_url}/api/hubs").mock(
        return_value=httpx.Response(
            401, json=_envelope_err("INVALID_API_KEY", "Key sai hoặc đã thu hồi")
        )
    )

    with pytest.raises(ToolError, match="MCP_UNAUTHORIZED"):
        await list_hubs(mock_ctx())


# ---------------------------------------------------------------------------
# Test 8 — hub isolation 403 → ToolError HUB_ACCESS_DENIED
# ---------------------------------------------------------------------------
@pytest.mark.critical
@respx.mock
async def test_hub_isolation_403(mock_ctx, api_base_url: str) -> None:
    """API 403 FORBIDDEN (hub isolation) → ToolError HUB_ACCESS_DENIED."""
    respx.post(f"{api_base_url}/api/search").mock(
        return_value=httpx.Response(
            403, json=_envelope_err("FORBIDDEN", "Không có quyền truy cập Hub này")
        )
    )

    with pytest.raises(ToolError, match="HUB_ACCESS_DENIED"):
        await search_wiki(mock_ctx(), query="q", hub_id="h-cấm")


# ---------------------------------------------------------------------------
# Test 9 — API 5xx → ToolError message sạch (không leak stack trace)
# ---------------------------------------------------------------------------
@respx.mock
async def test_api_5xx_clean_error(mock_ctx, api_base_url: str) -> None:
    """API 500 LLM_FAILED → ToolError; message KHÔNG chứa stack trace."""
    respx.post(f"{api_base_url}/api/ask").mock(
        return_value=httpx.Response(
            500, json=_envelope_err("LLM_FAILED", "Lỗi gọi LLM provider")
        )
    )

    with pytest.raises(ToolError) as exc_info:
        await ask_wiki(mock_ctx(), query="q", hub_id="h1")

    msg = str(exc_info.value)
    assert "API_ERROR" in msg
    # Message KHÔNG leak dấu vết stack trace nội bộ.
    assert "Traceback" not in msg
    assert 'File "' not in msg
