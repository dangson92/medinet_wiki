"""Unit test Phase 8.2 — GET /api/hubs chấp nhận X-API-Key + scope theo role.

Pure-Python, mock `HubService` + auth, KHÔNG cần Postgres.

Phủ:
- admin → `HubService.list()` (mọi hub), KHÔNG gọi `list_for_hubs`.
- non-admin có hub_ids → `HubService.list_for_hubs` được gọi với đúng hub_ids.
- non-admin hub_ids rỗng → trả danh sách rỗng, total 0.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.routers.hubs import list_hubs


def _make_user(role: str) -> SimpleNamespace:
    """User ORM giả tối thiểu — chỉ cần `.id` và `.role`."""
    return SimpleNamespace(id="user-1", role=role)


def _make_db(hub_ids: list[str], override_count: int = 0) -> MagicMock:
    """Mock AsyncSession.execute — multi-call:

    - Admin branch (Plan 02-02 B2 defensive): SELECT COUNT(*) → `scalar_one()`
      returns `override_count` (default 0 = clean state).
    - Non-admin else branch (M2 baseline): SELECT UserHub.hub_id →
      `scalars().all()` returns `hub_ids`.

    Cùng MagicMock result hỗ trợ cả 2 path (scalar_one + scalars().all)
    — caller chỉ dùng 1 path, path còn lại idle.
    """
    db = MagicMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = hub_ids
    result.scalars.return_value = scalars
    # Plan 02-02 B2 defensive: admin branch dùng scalar_one() cho COUNT(*).
    result.scalar_one = MagicMock(return_value=override_count)
    db.execute = AsyncMock(return_value=result)
    return db


def _make_hub(hub_id: str, name: str) -> object:
    """HubResponse giả — chỉ cần `.model_dump(mode="json")`."""
    hub = MagicMock()
    hub.model_dump.return_value = {"id": hub_id, "name": name}
    return hub


def _decode(response: object) -> dict:
    """Giải JSON body từ JSONResponse trả về."""
    return json.loads(response.body)


async def test_admin_lists_all_hubs() -> None:
    """Test 1 — admin → HubService.list() (mọi hub), KHÔNG gọi list_for_hubs."""
    user = _make_user(role="admin")
    db = _make_db(hub_ids=[])
    service = MagicMock()
    service.list = AsyncMock(
        return_value=([_make_hub("h1", "Hub Y tế")], 1)
    )
    service.list_for_hubs = AsyncMock()

    response = await list_hubs(
        page=1, per_page=20, user=user, service=service, db=db
    )

    service.list.assert_awaited_once()
    service.list_for_hubs.assert_not_awaited()
    body = _decode(response)
    assert body["success"] is True
    assert body["meta"]["total"] == 1


async def test_viewer_lists_only_assigned_hubs() -> None:
    """Test 2 — viewer có hub_ids → list_for_hubs được gọi với đúng hub_ids."""
    user = _make_user(role="viewer")
    db = _make_db(hub_ids=["hub-a"])
    service = MagicMock()
    service.list = AsyncMock()
    service.list_for_hubs = AsyncMock(
        return_value=([_make_hub("hub-a", "Hub A")], 1)
    )

    response = await list_hubs(
        page=1, per_page=20, user=user, service=service, db=db
    )

    service.list.assert_not_awaited()
    service.list_for_hubs.assert_awaited_once()
    _, kwargs = service.list_for_hubs.await_args
    assert kwargs["hub_ids"] == ["hub-a"]
    body = _decode(response)
    assert body["meta"]["total"] == 1
    assert body["data"][0]["id"] == "hub-a"


async def test_viewer_no_hubs_returns_empty() -> None:
    """Test 3 — viewer hub_ids rỗng → list_for_hubs trả ([], 0)."""
    user = _make_user(role="viewer")
    db = _make_db(hub_ids=[])
    service = MagicMock()
    service.list = AsyncMock()
    service.list_for_hubs = AsyncMock(return_value=([], 0))

    response = await list_hubs(
        page=1, per_page=20, user=user, service=service, db=db
    )

    service.list.assert_not_awaited()
    service.list_for_hubs.assert_awaited_once()
    _, kwargs = service.list_for_hubs.await_args
    assert kwargs["hub_ids"] == []
    body = _decode(response)
    assert body["data"] == []
    assert body["meta"]["total"] == 0
