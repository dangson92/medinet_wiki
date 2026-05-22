"""Plan 04-05 (SYNC-03 / D-V3-Phase4-D1) — Unit test refactor cross-hub search.

Verify `SearchService._search_cross_hub_impl` đã refactor từ fan-out parallel
`_search_one(hub_id)` per hub bằng 1 SQL aggregated `WHERE hub_id = ANY` qua
single `_run_vector_query` call với hub_ids=list[str] (NOT single hub_id).

Public API `SearchService.search_cross_hub()` signature giữ NGUYÊN — backward
compat M2 contract (ask_service.py consumer + frontend client).

8 test:
1. test_search_cross_hub_signature_unchanged — public API kwargs unchanged.
2. test_search_cross_hub_empty_hub_ids_returns_empty — non-admin no hubs → empty.
3. test_search_cross_hub_admin_no_filter_queries_all_active — admin → all active hubs.
4. test_search_cross_hub_intersects_jwt_and_body — SSO-03 intersect logic carry forward.
5. test_search_cross_hub_uses_single_sql_no_fanout — _run_vector_query called 1 lần
   với hub_ids list (NOT N lần với single hub_id).
6. test_search_cross_hub_redis_cache_get_set_unchanged — cache D-11 carry forward.
7. test_search_cross_hub_response_shape_results_list — envelope SearchResponse shape.
8. test_search_cross_hub_no_asyncio_gather — inspect.getsource() KHÔNG chứa
   asyncio.gather( trong _search_cross_hub_impl (guarantee refactor xoá fan-out).
"""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.search import SearchRequest
from app.services.search_service import SearchService


def _make_user(role: str = "viewer", hub_ids: list[str] | None = None) -> SimpleNamespace:
    """Tạo UserWithHubs-like giả — chỉ cần `.user.role` và `.hub_ids`."""
    user = SimpleNamespace(id="user-1", role=role)
    return SimpleNamespace(user=user, hub_ids=hub_ids or [])


def _make_pool_with_active_hubs(active_hub_ids: list[str]) -> MagicMock:
    """Mock asyncpg.Pool — query `SELECT id FROM hubs WHERE is_active = TRUE`
    trả rows = [{"id": <uuid>}, ...] cho branch admin-all.
    """
    pool = MagicMock()
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[{"id": h} for h in active_hub_ids])
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


def _make_row(score: float = 0.9, hub_id: str = "hub-a") -> dict[str, Any]:
    """Mock 1 asyncpg Record dict cho `_row_to_item` consume."""
    from datetime import datetime, timezone
    return {
        "id": "chunk-1",
        "document_id": "doc-1",
        "hub_id": hub_id,
        "content": "test content " * 30,
        "heading_path": "Section/Sub",
        "metadata": {},
        "filename": "doc.pdf",
        "updated_at": datetime(2026, 5, 22, 0, 0, 0, tzinfo=timezone.utc),
        "hub_name": "yte",
        "score": score,
    }


# ════════════════════════════════════════════════════════════════════════════
# Test 1 — Public API signature unchanged (backward compat M2 contract)
# ════════════════════════════════════════════════════════════════════════════


def test_search_cross_hub_signature_unchanged() -> None:
    """Public API SearchService.search_cross_hub(body, user) kwargs unchanged.

    M2 ask_service.py + frontend api.ts call `service.search_cross_hub(body=..., user=...)`.
    Plan 04-05 refactor IN-PLACE — KHÔNG đổi parameter name/order/return type.
    """
    sig = inspect.signature(SearchService.search_cross_hub)
    params = sig.parameters
    # `self` + `body` + `user` — exactly 3 params (self counted).
    assert "body" in params, f"PHẢI có kwarg `body`; signature: {sig}"
    assert "user" in params, f"PHẢI có kwarg `user`; signature: {sig}"
    # Return annotation = dict[str, Any] hoặc tương đương (router wrap envelope).
    assert sig.return_annotation is not inspect.Signature.empty, (
        "PHẢI có return annotation rõ ràng — backward compat M2"
    )


# ════════════════════════════════════════════════════════════════════════════
# Test 2 — Non-admin no hubs intersect rỗng → empty envelope
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_search_cross_hub_empty_hub_ids_returns_empty() -> None:
    """Non-admin user với user.hub_ids=[] → return SearchResponse empty envelope.

    intersect_hubs(body.hub_ids=None, user.hub_ids=[], role="viewer") → [] →
    early-return empty.
    """
    pool = _make_pool_with_active_hubs([])  # branch admin-all KHÔNG trigger
    service = SearchService(pool=pool, redis=None)
    body = SearchRequest(query="test query", hub_ids=None, top_k=10)
    user = _make_user(role="viewer", hub_ids=[])

    result = await service.search_cross_hub(body=body, user=user)

    assert isinstance(result, dict)
    assert result["results"] == []
    assert result["total_hubs_searched"] == 0
    assert result["cache_hit"] is False


# ════════════════════════════════════════════════════════════════════════════
# Test 3 — Admin no filter → query all active hubs
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_search_cross_hub_admin_no_filter_queries_all_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admin user + body.hub_ids=None → SELECT id FROM hubs WHERE is_active = TRUE.

    Plan 04-05 carry forward admin-all branch (predicate NHẤT QUÁN với
    `_run_vector_query` all_hubs=True branch).
    """
    active_hubs = ["hub-yte", "hub-duoc", "hub-hcns"]
    pool = _make_pool_with_active_hubs(active_hubs)
    service = SearchService(pool=pool, redis=None)

    # Mock embed_text + _run_vector_query — focus chỉ verify admin-all branch query
    monkeypatch.setattr(
        "app.services.search_service.embed_text",
        AsyncMock(return_value=[0.1] * 1536),
    )
    mock_run_query = AsyncMock(return_value=([], 3))
    monkeypatch.setattr(service, "_run_vector_query", mock_run_query)

    body = SearchRequest(query="test query", hub_ids=None, top_k=10)
    user = _make_user(role="admin", hub_ids=[])

    result = await service.search_cross_hub(body=body, user=user)

    # Verify SELECT id FROM hubs WHERE is_active = TRUE đã query
    pool.acquire.assert_called()
    # Verify _run_vector_query called với 3 hub_ids (admin-all đã resolve)
    mock_run_query.assert_called_once()
    call_kwargs = mock_run_query.call_args.kwargs
    assert call_kwargs["hub_ids"] == active_hubs, (
        f"admin-all phải pass full active hubs list, got {call_kwargs['hub_ids']}"
    )
    # total_hubs_searched = số hub đã query
    assert result["total_hubs_searched"] == 3


# ════════════════════════════════════════════════════════════════════════════
# Test 4 — JWT hub_ids ∩ body.hub_ids intersect (SSO-03 carry forward)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_search_cross_hub_intersects_jwt_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """user.hub_ids=[yte,duoc] + body.hub_ids=[yte,hcns] → intersect=[yte] (defense in depth D-07).

    SSO-03 carry forward: hub user KHÔNG có quyền bị silent-drop (KHÔNG raise).
    """
    pool = _make_pool_with_active_hubs([])
    service = SearchService(pool=pool, redis=None)

    monkeypatch.setattr(
        "app.services.search_service.embed_text",
        AsyncMock(return_value=[0.1] * 1536),
    )
    mock_run_query = AsyncMock(return_value=([], 1))
    monkeypatch.setattr(service, "_run_vector_query", mock_run_query)

    body = SearchRequest(query="test query", hub_ids=["hub-yte", "hub-hcns"], top_k=10)
    user = _make_user(role="viewer", hub_ids=["hub-yte", "hub-duoc"])

    await service.search_cross_hub(body=body, user=user)

    mock_run_query.assert_called_once()
    call_kwargs = mock_run_query.call_args.kwargs
    # intersect = ["hub-yte"] (sorted)
    assert call_kwargs["hub_ids"] == ["hub-yte"], (
        f"intersect SSO-03 fail — expected [hub-yte], got {call_kwargs['hub_ids']}"
    )


# ════════════════════════════════════════════════════════════════════════════
# Test 5 — KEY ASSERTION: 1 SQL aggregated, NOT fan-out N task
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_search_cross_hub_uses_single_sql_no_fanout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KEY refactor verify — `_run_vector_query` called EXACTLY 1 lần với hub_ids
    là FULL list (NOT N lần per-hub).

    Plan 04-05 D-V3-Phase4-D1 LOCKED: thay fan-out parallel _search_one(hub_id)
    qua N asyncio task bằng 1 SQL `WHERE hub_id = ANY($1::uuid[])` aggregated.
    """
    pool = _make_pool_with_active_hubs([])
    service = SearchService(pool=pool, redis=None)

    monkeypatch.setattr(
        "app.services.search_service.embed_text",
        AsyncMock(return_value=[0.1] * 1536),
    )
    mock_run_query = AsyncMock(return_value=([], 3))
    monkeypatch.setattr(service, "_run_vector_query", mock_run_query)

    body = SearchRequest(
        query="test query", hub_ids=["hub-a", "hub-b", "hub-c"], top_k=10
    )
    user = _make_user(
        role="viewer", hub_ids=["hub-a", "hub-b", "hub-c"]
    )

    await service.search_cross_hub(body=body, user=user)

    # KEY ASSERTION: _run_vector_query called EXACTLY 1 lần (NOT 3 lần fan-out)
    assert mock_run_query.call_count == 1, (
        f"Plan 04-05 refactor — _run_vector_query phải call 1 lần (aggregated SQL), "
        f"call_count actual={mock_run_query.call_count} (fan-out chưa xoá)"
    )
    # Hub_ids passed phải là FULL list (NOT single)
    call_kwargs = mock_run_query.call_args.kwargs
    assert len(call_kwargs["hub_ids"]) == 3, (
        f"hub_ids passed phải = full list (3 hubs), got len={len(call_kwargs['hub_ids'])}"
    )
    assert call_kwargs["all_hubs"] is False, (
        "Cross-hub multi-hub_ids → all_hubs=False (chỉ admin-all branch dùng all_hubs=True)"
    )


# ════════════════════════════════════════════════════════════════════════════
# Test 6 — Redis cache D-11 carry forward
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_search_cross_hub_redis_cache_get_set_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis cache get/set behavior unchanged — D-11 carry forward.

    Cache hit → trả cached JSON + cache_hit=True. Cache miss → execute query +
    cache.set với TTL.
    """
    pool = _make_pool_with_active_hubs([])
    redis_mock = MagicMock()
    cached_response = {
        "results": [],
        "total_hubs_searched": 2,
        "query_time_ms": 5,
        "cache_hit": False,  # service sẽ flip True khi return
    }
    redis_mock.get = AsyncMock(return_value=json.dumps(cached_response))
    redis_mock.set = AsyncMock(return_value=None)
    service = SearchService(pool=pool, redis=redis_mock)

    monkeypatch.setattr(
        "app.services.search_service.embed_text",
        AsyncMock(return_value=[0.1] * 1536),
    )
    mock_run_query = AsyncMock(return_value=([], 2))
    monkeypatch.setattr(service, "_run_vector_query", mock_run_query)

    body = SearchRequest(query="test", hub_ids=["hub-a", "hub-b"], top_k=10)
    user = _make_user(role="viewer", hub_ids=["hub-a", "hub-b"])

    result = await service.search_cross_hub(body=body, user=user)

    # Cache hit path — redis.get đã call, _run_vector_query KHÔNG call
    redis_mock.get.assert_called_once()
    assert result["cache_hit"] is True, "Cache hit phải set cache_hit=True"
    # Cache hit → KHÔNG re-query DB
    mock_run_query.assert_not_called()


# ════════════════════════════════════════════════════════════════════════════
# Test 7 — Response shape SearchResponse envelope
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_search_cross_hub_response_shape_results_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Response dict chứa `results` (list), `total_hubs_searched` (int),
    `query_time_ms` (int), `cache_hit` (bool) — SearchResponse envelope shape.
    """
    pool = _make_pool_with_active_hubs([])
    service = SearchService(pool=pool, redis=None)

    monkeypatch.setattr(
        "app.services.search_service.embed_text",
        AsyncMock(return_value=[0.1] * 1536),
    )
    # Trả 2 row mock
    mock_run_query = AsyncMock(
        return_value=([_make_row(score=0.9), _make_row(score=0.8)], 2)
    )
    monkeypatch.setattr(service, "_run_vector_query", mock_run_query)

    body = SearchRequest(query="test", hub_ids=["hub-a", "hub-b"], top_k=10)
    user = _make_user(role="viewer", hub_ids=["hub-a", "hub-b"])

    result = await service.search_cross_hub(body=body, user=user)

    assert "results" in result
    assert isinstance(result["results"], list)
    assert len(result["results"]) == 2
    assert "total_hubs_searched" in result
    assert isinstance(result["total_hubs_searched"], int)
    assert result["total_hubs_searched"] == 2  # 2 hubs queried
    assert "query_time_ms" in result
    assert isinstance(result["query_time_ms"], int)
    assert "cache_hit" in result
    assert result["cache_hit"] is False


# ════════════════════════════════════════════════════════════════════════════
# Test 8 — KEY ASSERTION: KHÔNG còn asyncio.gather trong _search_cross_hub_impl
# ════════════════════════════════════════════════════════════════════════════


def test_search_cross_hub_no_asyncio_gather() -> None:
    """`_search_cross_hub_impl` source KHÔNG chứa `asyncio.gather(` — guarantee
    refactor xoá fan-out pattern.

    Plan 04-05 D-V3-Phase4-D1: thay fan-out asyncio.gather(*[_search_one(h) for h in hub_ids])
    bằng 1 SQL aggregated → asyncio.gather KHÔNG còn cần trong _search_cross_hub_impl.
    """
    source = inspect.getsource(SearchService._search_cross_hub_impl)
    assert "asyncio.gather" not in source, (
        f"Plan 04-05 refactor incomplete — `_search_cross_hub_impl` vẫn chứa "
        f"asyncio.gather (fan-out pattern chưa xoá). Source snippet: ...\n"
        f"{source[:500]}"
    )
    # Inner function _search_one cũng phải bị xoá (chỉ còn _run_vector_query call)
    assert "async def _search_one" not in source, (
        f"Plan 04-05 refactor incomplete — `_search_cross_hub_impl` vẫn chứa "
        f"inner function `async def _search_one` (fan-out helper chưa xoá)."
    )
