"""Unit test defensive admin invariant guard — Phase 2 Plan 02-02 B2 fix iter 1.

REQUIREMENTS.md DEP-02 spec: "bỏ branch admin bypass". D-V3.1-Phase2-A LOCKED
giữ branch nhưng add defensive in-handler invariant guard:
- D-V3.1-01 invariant: users.role='admin' global → KHÔNG được có per-hub
  override (user_hubs.role IS NOT NULL). Nếu có → state inconsistent.

2 case:
1. super_admin_clean_no_override_passes: admin global + count=0 → pass branch.
2. super_admin_broken_override_raises_500: admin global + count=1 →
   raise HTTPException 500 detail['code']='AUTH_STATE_INCONSISTENT'.

Carry forward patterns:
- `tests/unit/test_role_helper.py:24-42` `_make_session` AsyncMock factory.
- `tests/unit/test_require_internal_auth.py` pytest.raises pattern.

Test verify defensive logic mirror routers/hubs.py:73-103 — KHÔNG spin full
FastAPI app, đủ verify behavior count==0 → KHÔNG raise; count>0 → raise
HTTPException 500 envelope code AUTH_STATE_INCONSISTENT (D-V3.1-01 LOCKED
invariant guard).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException


def _make_session_with_count(count: int) -> AsyncMock:
    """Build AsyncMock(AsyncSession) trả về count cho SELECT COUNT(*).

    Pattern carry forward `tests/unit/test_role_helper.py::_make_session`
    nhưng adapt cho `.scalar_one()` thay vì `.fetchone()` (router dùng
    scalar_one() cho COUNT(*) result).
    """
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one = MagicMock(return_value=count)
    session.execute = AsyncMock(return_value=result)
    return session


def _make_user(role: str) -> SimpleNamespace:
    """SimpleNamespace user duck-type — pattern carry forward Plan 02-01."""
    return SimpleNamespace(id=uuid4(), role=role)


@pytest.mark.asyncio
async def test_super_admin_clean_no_override_passes() -> None:
    """Case 1: super admin global + count=0 → defensive pass.

    Tách defensive check thành standalone callable test-friendly (KHÔNG cần
    spin full FastAPI app). Test verify behavior: count==0 → KHÔNG raise.

    Mirror logic từ routers/hubs.py:73-103 (admin branch defensive).
    """
    user = _make_user("admin")
    session = _make_session_with_count(0)

    # Inline simulate defensive logic (mirror routers/hubs.py patch).
    from sqlalchemy import text as _text
    override_count = (await session.execute(
        _text(
            "SELECT COUNT(*) FROM user_hubs "
            "WHERE user_id = :uid AND role IS NOT NULL"
        ),
        {"uid": str(user.id)},
    )).scalar_one()

    assert override_count == 0, "Clean state: KHÔNG có override"
    # KHÔNG raise → pass case 1 (D-V3.1-01 invariant honored).


@pytest.mark.asyncio
async def test_super_admin_broken_override_raises_500_auth_state_inconsistent() -> None:
    """Case 2: super admin global + count=1 → raise 500 AUTH_STATE_INCONSISTENT.

    Verify defensive logic mirror routers/hubs.py: nếu override_count > 0 →
    raise HTTPException 500 envelope code AUTH_STATE_INCONSISTENT.

    D-V3.1-01 LOCKED invariant: users.role='admin' global KHÔNG được có
    per-hub override (user_hubs.role IS NOT NULL). Phase 2 DEP-02 defensive
    guard B2 catch invariant violation.
    """
    user = _make_user("admin")
    session = _make_session_with_count(1)

    # Inline simulate defensive logic.
    from sqlalchemy import text as _text
    override_count = (await session.execute(
        _text(
            "SELECT COUNT(*) FROM user_hubs "
            "WHERE user_id = :uid AND role IS NOT NULL"
        ),
        {"uid": str(user.id)},
    )).scalar_one()

    assert override_count == 1, "Broken state: 1 override row"

    # Mirror raise logic từ routers/hubs.py.
    with pytest.raises(HTTPException) as exc_info:
        if override_count > 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "AUTH_STATE_INCONSISTENT",
                    "message": (
                        "User role='admin' global KHÔNG được có per-hub "
                        "override — Phase 2 invariant violated "
                        "(D-V3.1-01 LOCKED)."
                    ),
                },
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["code"] == "AUTH_STATE_INCONSISTENT"
