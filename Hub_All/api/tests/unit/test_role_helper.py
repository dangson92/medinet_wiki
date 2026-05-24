"""Unit test get_effective_role helper — Phase 1 Plan 01-02 (ROLE-04).

Pure Python test, KHÔNG cần Postgres/Redis runtime. Mock AsyncSession.execute
trả về MagicMock result với fetchone() side_effect — cover 4 case semantic +
1 defensive case.

Test cases (ROLE-04 acceptance):
1. super_admin: users.role='admin', user_hubs.role=NULL → return 'admin'.
2. hub_admin per-hub: users.role='editor', user_hubs.role='hub_admin' → return 'hub_admin'.
3. viewer per-hub override: users.role='admin', user_hubs.role='viewer' → return 'viewer'.
4. no membership fallback: users.role='admin', user_hubs row KHÔNG tồn tại → return 'admin'.
5. user_not_found defensive: users row KHÔNG tồn tại → raise UserNotFoundError.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.auth.role import UserNotFoundError, get_effective_role


def _make_session(*fetchone_returns: object) -> AsyncMock:
    """Build AsyncMock(AsyncSession) trả về sequence fetchone results.

    Args:
        *fetchone_returns: Tuple sequence — mỗi item là row return cho lần
            execute() tiếp theo. None = row không tồn tại; tuple = row tồn tại.

    Example:
        >>> session = _make_session(('hub_admin',))  # 1 query trả về row role='hub_admin'
        >>> session = _make_session(None, ('admin',))  # 2 queries: 1 None, 2 row
    """
    session = AsyncMock()
    result_mocks = []
    for fetchone_value in fetchone_returns:
        result = MagicMock()
        result.fetchone.return_value = fetchone_value
        result_mocks.append(result)
    session.execute = AsyncMock(side_effect=result_mocks)
    return session


@pytest.mark.asyncio
async def test_super_admin_no_user_hubs_row_returns_admin() -> None:
    """Case 4: users.role='admin', user_hubs row KHÔNG tồn tại (no membership)
    → return 'admin' (fallback global).

    STEP 1: user_hubs query trả None.
    STEP 2: users query trả ('admin',).
    """
    user_id = uuid4()
    hub_id = uuid4()
    session = _make_session(None, ('admin',))

    role = await get_effective_role(session, user_id, hub_id)

    assert role == 'admin'
    assert session.execute.call_count == 2


@pytest.mark.asyncio
async def test_super_admin_user_hubs_role_null_returns_admin() -> None:
    """Case 1: users.role='admin', user_hubs.role=NULL → return 'admin' (inherit).

    STEP 1: user_hubs query trả (None,) — row tồn tại NHƯNG role IS NULL.
    STEP 2: users query trả ('admin',).
    """
    user_id = uuid4()
    hub_id = uuid4()
    session = _make_session((None,), ('admin',))

    role = await get_effective_role(session, user_id, hub_id)

    assert role == 'admin'
    assert session.execute.call_count == 2


@pytest.mark.asyncio
async def test_hub_admin_per_hub_override_returns_hub_admin() -> None:
    """Case 2: users.role='editor', user_hubs.role='hub_admin' → return 'hub_admin'.

    Per-hub override path — STEP 1 đủ, KHÔNG cần STEP 2.
    """
    user_id = uuid4()
    hub_id = uuid4()
    session = _make_session(('hub_admin',))

    role = await get_effective_role(session, user_id, hub_id)

    assert role == 'hub_admin'
    assert session.execute.call_count == 1  # STEP 2 skip


@pytest.mark.asyncio
async def test_viewer_per_hub_override_returns_viewer() -> None:
    """Case 3: users.role='admin' (super), user_hubs.role='viewer' (demote per-hub)
    → return 'viewer' (override semantic — D-V3.1-02 LOCKED).

    Demonstration semantic: per-hub override CÓ THỂ demote super-admin xuống viewer
    cho hub cụ thể (forward compat case "super admin xem hub này dạng viewer").
    """
    user_id = uuid4()
    hub_id = uuid4()
    session = _make_session(('viewer',))

    role = await get_effective_role(session, user_id, hub_id)

    assert role == 'viewer'
    assert session.execute.call_count == 1


@pytest.mark.asyncio
async def test_user_not_found_raises_user_not_found_error() -> None:
    """Case 5: users row KHÔNG tồn tại → raise UserNotFoundError (defensive).

    STEP 1: user_hubs query trả None (no membership).
    STEP 2: users query trả None (user không tồn tại).
    → Raise UserNotFoundError với message mention user_id.
    """
    user_id = uuid4()
    hub_id = uuid4()
    session = _make_session(None, None)

    with pytest.raises(UserNotFoundError, match=str(user_id)):
        await get_effective_role(session, user_id, hub_id)

    assert session.execute.call_count == 2


@pytest.mark.asyncio
async def test_get_effective_role_accepts_str_uuid_args() -> None:
    """Defensive: helper chấp nhận user_id/hub_id dạng str (KHÔNG chỉ UUID object).

    Coverage carry forward Phase 3 SSO pattern — JWT claims.sub là str, KHÔNG UUID.
    """
    user_id_str = str(uuid4())
    hub_id_str = str(uuid4())
    session = _make_session(('admin',))

    role = await get_effective_role(session, user_id_str, hub_id_str)

    assert role == 'admin'
    # Verify session.execute() được gọi với param value là str (không phải UUID).
    call_kwargs = session.execute.call_args_list[0]
    # call_args_list[0] là tuple (args, kwargs); args[1] là dict params.
    assert isinstance(call_kwargs[0][1]['user_id'], str)
    assert isinstance(call_kwargs[0][1]['hub_id'], str)
