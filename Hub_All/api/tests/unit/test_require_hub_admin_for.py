"""Unit test assert_hub_admin_for validator — Phase 2 Plan 02-01 DEP-01.

Pure Python test, KHÔNG cần Postgres/Redis runtime. Mock AsyncSession.execute
trả về MagicMock result với fetchone() side_effect — cover 5 case D-V3.1-Phase2-D
LOCKED.

Test cases (DEP-01 acceptance — 5 case D-V3.1-Phase2-D):
1. super_admin_bypass: user.role='admin' → pass (KHÔNG call get_effective_role).
2. hub_admin_correct_hub: user.role='editor' + get_effective_role='hub_admin' → pass.
3. hub_admin_wrong_hub: user.role='editor' + get_effective_role='viewer' (no override) → 403.
4. viewer_not_hub_admin: user.role='viewer' + get_effective_role='viewer' → 403.
5. user_not_found_defensive: patch get_effective_role raise UserNotFoundError → 403 (KHÔNG 404).

Carry forward patterns:
- `_make_session` AsyncMock factory — pattern `tests/unit/test_role_helper.py:24-42`.
- `pytest.raises(HTTPException)` + `assert exc_info.value.detail["code"]` — pattern
  `tests/unit/test_require_internal_auth.py` carry forward Phase 6 Plan 06-03.
- `SimpleNamespace` user fixture — pattern Plan 01-02 + nhẹ hơn full User ORM mock.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.auth.dependencies import assert_hub_admin_for
from app.auth.role import UserNotFoundError


def _make_session(*fetchone_returns: object) -> AsyncMock:
    """Build AsyncMock(AsyncSession) trả về sequence fetchone results.

    Carry forward pattern `tests/unit/test_role_helper.py:24-42`.

    Args:
        *fetchone_returns: Tuple sequence — mỗi item là row return cho lần
            execute() tiếp theo. None = row không tồn tại; tuple = row tồn tại.

    Example:
        >>> session = _make_session(('hub_admin',))  # 1 query trả row role='hub_admin'
        >>> session = _make_session(None, ('viewer',))  # 2 queries: 1 None, 2 row
    """
    session = AsyncMock()
    result_mocks = []
    for fetchone_value in fetchone_returns:
        result = MagicMock()
        result.fetchone.return_value = fetchone_value
        result_mocks.append(result)
    session.execute = AsyncMock(side_effect=result_mocks)
    return session


def _make_user(role: str, user_id: object = None) -> SimpleNamespace:
    """SimpleNamespace user fixture — KHÔNG cần full User ORM.

    Carry forward pattern `tests/unit/test_require_internal_auth.py` —
    SimpleNamespace duck-type đủ cho assert_hub_admin_for đọc `user.role` + `user.id`.
    """
    return SimpleNamespace(id=user_id or uuid4(), role=role)


@pytest.mark.asyncio
async def test_super_admin_bypass_returns_none_without_db_call() -> None:
    """Case 1 D-V3.1-Phase2-D: user.role='admin' → bypass, KHÔNG call get_effective_role.

    Verify session.execute KHÔNG được gọi (bypass trước query — performance
    + security guarantee).
    """
    user = _make_user("admin")
    session = AsyncMock()  # KHÔNG cần _make_session vì sẽ KHÔNG gọi execute.
    hub_id = str(uuid4())

    # Không raise → pass case 1.
    result = await assert_hub_admin_for(user=user, db=session, target_hub_id=hub_id)

    assert result is None, "assert_hub_admin_for phải return None khi pass"
    assert session.execute.call_count == 0, (
        "Super admin bypass: get_effective_role KHÔNG được gọi"
    )


@pytest.mark.asyncio
async def test_hub_admin_correct_hub_returns_none() -> None:
    """Case 2 D-V3.1-Phase2-D: user.role='editor' global + hub_admin per-hub → pass.

    STEP 1 (user_hubs.role override): query trả ('hub_admin',) → get_effective_role
    return 'hub_admin' → assert_hub_admin_for pass.
    """
    user = _make_user("editor")
    hub_id = str(uuid4())
    # Mock 1 query: user_hubs.role='hub_admin' → fetchone trả ('hub_admin',).
    session = _make_session(('hub_admin',))

    result = await assert_hub_admin_for(user=user, db=session, target_hub_id=hub_id)

    assert result is None, "assert_hub_admin_for phải return None khi hub_admin đúng"


@pytest.mark.asyncio
async def test_hub_admin_wrong_hub_raises_403_hub_admin_required() -> None:
    """Case 3 D-V3.1-Phase2-D: user.role='editor' + hub khác (no override) → 403.

    STEP 1: user_hubs.role NULL cho hub này → fallthrough STEP 2.
    STEP 2: users.role='editor' (KHÔNG hub_admin) → get_effective_role return 'editor'.
    → assert_hub_admin_for raise 403 HUB_ADMIN_REQUIRED.
    """
    user = _make_user("editor")
    hub_id = str(uuid4())
    # Mock 2 query: user_hubs row None (no override), users.role='editor'.
    session = _make_session(None, ('editor',))

    with pytest.raises(HTTPException) as exc_info:
        await assert_hub_admin_for(user=user, db=session, target_hub_id=hub_id)

    assert exc_info.value.status_code == 403, "Phải raise 403 (KHÔNG 401/404)"
    assert isinstance(exc_info.value.detail, dict), "detail phải là dict envelope"
    assert exc_info.value.detail["code"] == "HUB_ADMIN_REQUIRED", (
        f"Envelope code phải 'HUB_ADMIN_REQUIRED', got {exc_info.value.detail.get('code')!r}"
    )


@pytest.mark.asyncio
async def test_viewer_not_hub_admin_raises_403_hub_admin_required() -> None:
    """Case 4 D-V3.1-Phase2-D: user.role='viewer' global + no override → 403.

    STEP 1: user_hubs row None.
    STEP 2: users.role='viewer' → get_effective_role return 'viewer'.
    → assert_hub_admin_for raise 403 HUB_ADMIN_REQUIRED.
    """
    user = _make_user("viewer")
    hub_id = str(uuid4())
    session = _make_session(None, ('viewer',))

    with pytest.raises(HTTPException) as exc_info:
        await assert_hub_admin_for(user=user, db=session, target_hub_id=hub_id)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "HUB_ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_user_not_found_raises_403_not_404_defensive() -> None:
    """Case 5 D-V3.1-Phase2-D: get_effective_role raise UserNotFoundError → catch + 403.

    Defensive: stale JWT user_id (user vừa bị xoá nhưng JWT còn valid signature)
    → assert_hub_admin_for catch UserNotFoundError + raise 403 HUB_ADMIN_REQUIRED.
    KHÔNG raise 404 (leak user_id existence) hoặc 500 (internal error).

    Pattern dùng patch để force get_effective_role raise — KHÔNG mock session
    (vì sẽ KHÔNG được dùng — patch ở module level).
    """
    user = _make_user("editor")
    hub_id = str(uuid4())
    session = AsyncMock()  # KHÔNG quan trọng vì get_effective_role bị patch.

    with patch(
        "app.auth.dependencies.get_effective_role",
        new=AsyncMock(side_effect=UserNotFoundError(f"User {user.id!r} not found")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await assert_hub_admin_for(user=user, db=session, target_hub_id=hub_id)

    assert exc_info.value.status_code == 403, (
        "Defensive guard: KHÔNG raise 404 leak existence"
    )
    assert exc_info.value.detail["code"] == "HUB_ADMIN_REQUIRED"
    # Verify UserNotFoundError được chain (`raise ... from e`) — exception traceback preserve.
    assert isinstance(exc_info.value.__cause__, UserNotFoundError), (
        "Exception chain phải preserve UserNotFoundError cho debug traceback"
    )
