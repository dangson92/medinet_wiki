"""Unit test Phase 8.2 — auth X-API-Key trên dependency + endpoint search/ask.

Pure-Python, KHÔNG cần Postgres/Redis. Mock `db.execute`, `SearchService`,
`AskService`, `BackgroundTasks`.

Bố cục:
- Phần 1 (Task 1) — `get_api_key_or_jwt_with_hubs`: verify X-API-Key HOặC JWT
  rồi load `hub_ids` từ `user_hubs`, trả `UserWithHubs`. 4 test.
- Phần 2 (Task 3) — endpoint search/ask chạy được qua X-API-Key path; SC4
  usage_events vẫn ghi; regression JWT thuần. 3 test.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.auth.dependencies import (
    UserWithHubs,
    get_api_key_or_jwt_with_hubs,
)


def _make_user(role: str = "viewer") -> SimpleNamespace:
    """Tạo User ORM giả tối thiểu — chỉ cần `.id` và `.role`."""
    return SimpleNamespace(id="user-1", role=role)


def _make_db(hub_ids: list[str]) -> MagicMock:
    """Mock AsyncSession.execute — trả scalar list `hub_ids` cho query user_hubs."""
    db = MagicMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = hub_ids
    result.scalars.return_value = scalars
    db.execute = AsyncMock(return_value=result)
    return db


# --------------------------------------------------------------------------
# Phần 1 — Task 1: test dependency get_api_key_or_jwt_with_hubs
# --------------------------------------------------------------------------


async def test_apikey_non_admin_loads_hub_ids_from_user_hubs() -> None:
    """Test 1 — X-API-Key user non-admin có 2 hub → hub_ids đúng 2 hub từ DB."""
    user = _make_user(role="viewer")
    db = _make_db(hub_ids=["hub-a", "hub-b"])

    result = await get_api_key_or_jwt_with_hubs(user=user, db=db)

    assert isinstance(result, UserWithHubs)
    assert result.user is user
    assert result.hub_ids == ["hub-a", "hub-b"]


async def test_jwt_path_loads_hub_ids_from_user_hubs() -> None:
    """Test 2 — không X-API-Key, user từ JWT → hub_ids vẫn load từ user_hubs."""
    user = _make_user(role="editor")
    db = _make_db(hub_ids=["hub-x"])

    result = await get_api_key_or_jwt_with_hubs(user=user, db=db)

    assert result.hub_ids == ["hub-x"]
    assert result.user.role == "editor"


async def test_missing_auth_propagates_401() -> None:
    """Test 3 — không X-API-Key lẫn JWT → 401 MISSING_AUTHORIZATION propagate.

    `get_api_key_or_jwt_with_hubs` nhận `user` qua `Depends(get_api_key_or_jwt)`;
    khi auth fail, `get_api_key_or_jwt` raise 401 TRƯỚC khi dependency mới chạy.
    Verify trực tiếp `get_api_key_or_jwt` raise — dependency mới KHÔNG nuốt lỗi.
    """
    from fastapi import HTTPException
    from starlette.requests import Request

    from app.auth.dependencies import get_api_key_or_jwt

    scope = {"type": "http", "headers": []}
    request = Request(scope)

    jwt_mgr = MagicMock()
    db = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_api_key_or_jwt(
            request=request,
            x_api_key=None,
            token=None,
            jwt_mgr=jwt_mgr,
            redis=None,
            db=db,
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "MISSING_AUTHORIZATION"


async def test_admin_still_returns_real_hub_ids() -> None:
    """Test 4 — user admin (X-API-Key) → hub_ids vẫn là list thực tế từ DB.

    Bypass filter cho admin xảy ra ở service layer, KHÔNG ở dependency này —
    đồng nhất với `get_current_user_with_hubs`.
    """
    user = _make_user(role="admin")
    db = _make_db(hub_ids=["hub-a"])

    result = await get_api_key_or_jwt_with_hubs(user=user, db=db)

    assert result.user.role == "admin"
    assert result.hub_ids == ["hub-a"]


# --------------------------------------------------------------------------
# Phần 2 — Task 3: endpoint search/ask qua X-API-Key path
# --------------------------------------------------------------------------


def _make_request(*, db_pool: object | None = None) -> object:
    """Tạo starlette Request thật tối thiểu — slowapi `@limiter.limit` đòi
    `request` đúng kiểu `starlette.requests.Request`.

    `app` giả gắn vào scope để `request.app.state.db_pool` đọc được (ask
    endpoint cần pool cho BackgroundTasks). `state` rỗng cho `request_id`.
    """
    from starlette.requests import Request

    app = SimpleNamespace(state=SimpleNamespace(db_pool=db_pool))
    return Request(
        {
            "type": "http",
            "headers": [],
            "method": "POST",
            "app": app,
            "state": {},
        }
    )


def _undecorated(func: object) -> object:
    """Lấy hàm endpoint gốc (bỏ wrapper slowapi `@limiter.limit`).

    slowapi wrap qua `functools.wraps` → `__wrapped__` trỏ về hàm gốc; gọi
    trực tiếp hàm gốc bỏ qua rate-limit (không cần Redis/state trong unit test).
    """
    return getattr(func, "__wrapped__", func)


async def test_search_endpoint_runs_with_apikey_user() -> None:
    """Test 5 — search_endpoint chạy với UserWithHubs từ X-API-Key non-admin.

    Verify endpoint KHÔNG raise 401 và `SearchService.search` nhận đúng
    `user.hub_ids` (non-admin chỉ hub được assign).
    """
    from app.routers.search import search_endpoint

    user = UserWithHubs(user=_make_user(role="viewer"), hub_ids=["hub-a"])
    service = MagicMock()
    service.search = AsyncMock(return_value={"results": []})
    body = MagicMock()
    request = _make_request()

    fn = _undecorated(search_endpoint)
    resp = await fn(request=request, body=body, user=user, service=service)

    service.search.assert_awaited_once()
    # user truyền xuống service phải giữ nguyên hub_ids scope.
    _, kwargs = service.search.await_args
    assert kwargs["user"].hub_ids == ["hub-a"]
    assert resp is not None


async def test_ask_endpoint_schedules_usage_log_via_apikey() -> None:
    """Test 6 — /api/ask qua X-API-Key path: background_tasks.add_task được gọi
    với `log_usage_event` (SC4 — usage_events vẫn ghi, không phụ thuộc auth).
    """
    from app.routers.ask import ask_endpoint
    from app.services.usage_service import log_usage_event

    user = UserWithHubs(user=_make_user(role="viewer"), hub_ids=["hub-a"])

    usage = SimpleNamespace(
        user_id="user-1",
        hub_id="hub-a",
        model="gpt-4o-mini",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost_usd=0.001,
        request_id=None,
    )
    response_obj = MagicMock()
    response_obj.model_dump.return_value = {"answer": "x"}
    outcome = SimpleNamespace(usage=usage, response=response_obj)

    service = MagicMock()
    service.ask = AsyncMock(return_value=outcome)

    body = SimpleNamespace(hub_id="hub-a", hub_ids=None, query="câu hỏi")
    background_tasks = MagicMock()
    request = _make_request(db_pool=MagicMock())
    request.state.request_id = "req-1"

    fn = _undecorated(ask_endpoint)
    await fn(
        request=request,
        body=body,
        background_tasks=background_tasks,
        user=user,
        service=service,
    )

    background_tasks.add_task.assert_called_once()
    args, _ = background_tasks.add_task.call_args
    assert args[0] is log_usage_event


async def test_search_endpoint_regression_jwt_path() -> None:
    """Test 7 — regression: search vẫn chạy với UserWithHubs (JWT thuần).

    `get_api_key_or_jwt_with_hubs` fallback JWT khi không có X-API-Key —
    endpoint hành vi không đổi, service nhận đúng user.
    """
    from app.routers.search import search_endpoint

    user = UserWithHubs(user=_make_user(role="editor"), hub_ids=["hub-x"])
    service = MagicMock()
    service.search = AsyncMock(return_value={"results": [1]})
    body = MagicMock()
    request = _make_request()

    fn = _undecorated(search_endpoint)
    resp = await fn(request=request, body=body, user=user, service=service)

    service.search.assert_awaited_once()
    assert resp is not None
