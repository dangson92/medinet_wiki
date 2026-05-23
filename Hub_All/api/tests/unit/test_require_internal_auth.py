"""Phase 6 Plan 06-03 Wave 3 Task 1 — Unit test require_internal_auth dependency.

Per PLAN <behavior> 6 test:
1. Correct secret header → no raise (return None).
2. Wrong secret → 401 INTERNAL_AUTH_FAIL.
3. Missing header → 401 INTERNAL_AUTH_FAIL.
4. Empty header value → 401 INTERNAL_AUTH_FAIL.
5. hmac.compare_digest called (constant-time mitigation T-06-04-01) — spy verify.
6. Dependency read settings.settings_proxy_secret (not hardcoded).

Decision traceability:
- D-V3-Phase6-D LOCKED — Shared secret X-Internal-Auth header.
- T-06-03-01 mitigation — hmac.compare_digest constant-time compare.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.auth.dependencies import require_internal_auth

SECRET = "x" * 32  # 32 char min — D-V3-Phase6-D validator Plan 06-01


def _make_settings(secret: str = SECRET) -> SimpleNamespace:
    """Mock Settings với settings_proxy_secret only."""
    return SimpleNamespace(settings_proxy_secret=secret)


# --------------------------------------------------------------------------
# Test 1: Correct secret header → no raise
# --------------------------------------------------------------------------


async def test_correct_secret_no_raise() -> None:
    """Test 1 — Header X-Internal-Auth match settings → no raise (return None)."""
    with patch(
        "app.config.get_settings",
        return_value=_make_settings(),
    ):
        # KHÔNG raise → test pass
        result = await require_internal_auth(x_internal_auth=SECRET)
        assert result is None


# --------------------------------------------------------------------------
# Test 2: Wrong secret → 401 INTERNAL_AUTH_FAIL
# --------------------------------------------------------------------------


async def test_wrong_secret_raises_401() -> None:
    """Test 2 — Header value != settings.settings_proxy_secret → 401."""
    with patch(
        "app.config.get_settings",
        return_value=_make_settings(),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await require_internal_auth(x_internal_auth="wrong-secret-xxxxxxxxxxxxxxxxxxxxx")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "INTERNAL_AUTH_FAIL"


# --------------------------------------------------------------------------
# Test 3: Missing header → 401 INTERNAL_AUTH_FAIL
# --------------------------------------------------------------------------


async def test_missing_header_raises_401() -> None:
    """Test 3 — None header (FastAPI Header default) → 401 INTERNAL_AUTH_FAIL."""
    with patch(
        "app.config.get_settings",
        return_value=_make_settings(),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await require_internal_auth(x_internal_auth=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "INTERNAL_AUTH_FAIL"


# --------------------------------------------------------------------------
# Test 4: Empty header value "" → 401
# --------------------------------------------------------------------------


async def test_empty_header_raises_401() -> None:
    """Test 4 — Empty string header (truthy=False) → 401 INTERNAL_AUTH_FAIL."""
    with patch(
        "app.config.get_settings",
        return_value=_make_settings(),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await require_internal_auth(x_internal_auth="")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "INTERNAL_AUTH_FAIL"


# --------------------------------------------------------------------------
# Test 5: hmac.compare_digest called (constant-time mitigation)
# --------------------------------------------------------------------------


async def test_uses_hmac_compare_digest_constant_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 5 — Verify hmac.compare_digest invoked (T-06-04-01 timing attack mitigation).

    Spy via monkeypatch hmac.compare_digest module-level. KHÔNG mock false (
    để function vẫn pass với correct secret).
    """
    import hmac

    spy_called = {"count": 0}
    real_compare = hmac.compare_digest

    def _spy_compare_digest(a: object, b: object) -> bool:
        spy_called["count"] += 1
        return real_compare(a, b)  # type: ignore[arg-type]

    monkeypatch.setattr(hmac, "compare_digest", _spy_compare_digest)

    with patch(
        "app.config.get_settings",
        return_value=_make_settings(),
    ):
        await require_internal_auth(x_internal_auth=SECRET)

    assert spy_called["count"] >= 1, "hmac.compare_digest phải được gọi"


# --------------------------------------------------------------------------
# Test 6: Settings env loaded — read settings_proxy_secret
# --------------------------------------------------------------------------


async def test_reads_settings_proxy_secret_not_hardcoded() -> None:
    """Test 6 — Verify dependency reads settings.settings_proxy_secret dynamic.

    Mock Settings với secret KHÁC default xxxx → verify function dùng giá trị này.
    """
    custom_secret = "y" * 32
    with patch(
        "app.config.get_settings",
        return_value=_make_settings(secret=custom_secret),
    ):
        # Header value custom_secret → match → no raise
        result = await require_internal_auth(x_internal_auth=custom_secret)
        assert result is None

        # Header value default "x"*32 (KHÁC custom) → 401
        with pytest.raises(HTTPException) as exc_info:
            await require_internal_auth(x_internal_auth=SECRET)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "INTERNAL_AUTH_FAIL"
