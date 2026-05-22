"""Unit tests cho `Settings.hub_name` field + `resolve_database_url` helper.

Phase 1 Plan 01-02 (TOPO-04) — v3.0 Multi-Hub Split foundation:
- `Settings.hub_name: Literal["central","yte","duoc","hcns"]` đọc từ env `HUB_NAME`
- `model_validator(mode="after")` enforce DSN suffix khớp `hub_name`
  (E-V3-3: hub yte KHÔNG được trỏ medinet_central / medinet_hub_duoc).
- `resolve_database_url(base_dsn, hub_name)` helper deterministic.

Threat model cover (xem 01-02-PLAN.md `<threat_model>`):
- T-01-02-01 Spoofing: HUB_NAME=yte nhưng DATABASE_URL trỏ central → ValidationError
- T-01-02-02 Information Disclosure: cross-hub DSN typo → ValidationError
- T-01-02-03 Elevation of Privilege: hub con cố ý trỏ central → ValidationError
- T-01-02-04 Tampering: resolve_database_url với base_dsn sai → ValueError

NOTE: dùng `monkeypatch.setenv()` để control env vars (consistent với mọi test
khác trong api/tests/). conftest.py autouse `_env` fixture set sẵn baseline,
override qua monkeypatch theo từng test scenario. KHÔNG instantiate Settings
trực tiếp với kwargs (mypy strict không reconcile được với pydantic-settings
internal `__init__` union types — 64 errors).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings, resolve_database_url


def _set_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    hub_name: str | None = None,
    database_url: str | None = None,
) -> None:
    """Helper set env vars rồi clear cache get_settings — để Settings load tươi.

    None → giữ giá trị conftest set sẵn (hub_name → KHÔNG set env → default;
    database_url → conftest default). Truyền giá trị explicit để override.
    """
    if hub_name is not None:
        monkeypatch.setenv("HUB_NAME", hub_name)
    if database_url is not None:
        monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()


# === Test 1: central default DSN khớp medinet_central ===
def test_central_matches_central_dsn_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HUB_NAME=central + DSN /medinet_central — instantiate OK."""
    _set_env(
        monkeypatch,
        hub_name="central",
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_central",
    )
    s = Settings()
    assert s.hub_name == "central"
    assert s.database_url.endswith("/medinet_central")


# === Test 2: hub yte với DSN medinet_hub_yte ===
def test_yte_matches_yte_dsn_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """HUB_NAME=yte + DSN /medinet_hub_yte — instantiate OK.

    Plan 03-02 SSO-01 (Task 1) thêm validator `_enforce_central_jwks_url_for_hub`
    → hub con phải có CENTRAL_JWKS_URL. Set env để pass validator (regression
    update — KHÔNG đụng semantic test DSN match).
    """
    monkeypatch.setenv(
        "CENTRAL_JWKS_URL",
        "http://python-api-central:8080/.well-known/jwks.json",
    )
    _set_env(
        monkeypatch,
        hub_name="yte",
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_hub_yte",
    )
    s = Settings()
    assert s.hub_name == "yte"
    assert s.database_url.endswith("/medinet_hub_yte")


# === Test 3: hub yte trỏ medinet_central → ValidationError (E-V3-3) ===
def test_yte_mismatch_central_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-01-02-01 Spoofing — HUB_NAME=yte + DSN central → fail-fast.

    Lỗi nguy hiểm nhất: hub con vô tình truy cập aggregated data central.
    Validator phải raise startup, KHÔNG defer runtime.
    """
    _set_env(
        monkeypatch,
        hub_name="yte",
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_central",
    )
    with pytest.raises(ValidationError, match="DSN mismatch hub_name"):
        Settings()


# === Test 4: hub duoc trỏ medinet_hub_yte → ValidationError (cross-hub) ===
def test_duoc_mismatch_yte_dsn_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-01-02-02 Information Disclosure — cross-hub DSN typo bị reject startup."""
    _set_env(
        monkeypatch,
        hub_name="duoc",
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_hub_yte",
    )
    with pytest.raises(ValidationError, match="DSN mismatch hub_name"):
        Settings()


# === Test 5: hub_name vi phạm regex format → ValidationError ===
def test_invalid_hub_name_pattern_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plan 02-05 FACTOR-04 — Regex validator reject hub_name uppercase /
    hyphen / starting digit. Plan 01-02 ship Literal[4 hub] đã đổi sang str
    + regex (Plan 02-05). Test này verify regex enforce KHÔNG bị bypass.

    "invalid_hub" (snake_case 11 char) sau Plan 02-05 sẽ PASS regex — KHÔNG
    còn reject (Literal removed). Đổi input thành "Invalid_Hub" (uppercase →
    regex reject) để test giữ semantic "invalid hub name fail-fast".
    """
    _set_env(
        monkeypatch,
        hub_name="Invalid_Hub",  # uppercase → regex reject
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_central",
    )
    with pytest.raises(ValidationError, match="hub_name invalid format"):
        Settings()


# === Test 6: Default hub_name = 'central' nếu env HUB_NAME không set ===
def test_default_hub_name_is_central(monkeypatch: pytest.MonkeyPatch) -> None:
    """M2 backward-compat — Settings() không có HUB_NAME env → default 'central'.

    conftest._env không set HUB_NAME (chỉ DATABASE_URL/REDIS_URL/...). Explicit
    `delenv` đảm bảo người chạy local đã export HUB_NAME cũng bị clear.
    """
    monkeypatch.delenv("HUB_NAME", raising=False)
    _set_env(
        monkeypatch,
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_central",
    )
    s = Settings()
    assert s.hub_name == "central"


# === Test 7: resolve_database_url(central → yte) đổi đúng segment ===
def test_resolve_database_url_yte() -> None:
    """Helper resolve DSN deterministic — central → medinet_hub_<name>."""
    base = "postgresql+asyncpg://u:p@h:5432/medinet_central"
    result = resolve_database_url(base, "yte")
    assert result == "postgresql+asyncpg://u:p@h:5432/medinet_hub_yte"


# === Test 8: resolve_database_url(central → central) trả nguyên DSN gốc ===
def test_resolve_database_url_central_passthrough() -> None:
    """hub_name='central' → trả nguyên DSN, KHÔNG biến đổi (no-op)."""
    base = "postgresql+asyncpg://u:p@h:5432/medinet_central"
    result = resolve_database_url(base, "central")
    assert result == base


# === Bonus coverage: resolve_database_url với base_dsn sai → ValueError ===
def test_resolve_database_url_invalid_base_raises() -> None:
    """T-01-02-04 Tampering — base_dsn không kết thúc /medinet_central →
    caller misuse, raise ValueError với message rõ.
    """
    bad_base = "postgresql+asyncpg://u:p@h:5432/medinet_hub_yte"
    with pytest.raises(ValueError, match="medinet_central"):
        resolve_database_url(bad_base, "duoc")


# === Bonus coverage: DSN có query string vẫn validate đúng ===
def test_dsn_with_query_string_validates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validator strip `?option=value` trước khi check suffix — DSN production
    thường có `?sslmode=require` hoặc tương tự.

    Plan 03-02 Task 1 thêm CENTRAL_JWKS_URL required cho hub con.
    """
    monkeypatch.setenv(
        "CENTRAL_JWKS_URL",
        "http://python-api-central:8080/.well-known/jwks.json",
    )
    _set_env(
        monkeypatch,
        hub_name="yte",
        database_url=(
            "postgresql+asyncpg://u:p@h:5432/medinet_hub_yte?sslmode=require"
        ),
    )
    s = Settings()
    assert s.hub_name == "yte"


# === Bonus coverage: resolve_database_url giữ query string ===
def test_resolve_database_url_preserves_query() -> None:
    """Helper preserve query string khi đổi segment database name."""
    base = "postgresql+asyncpg://u:p@h:5432/medinet_central?sslmode=require"
    result = resolve_database_url(base, "duoc")
    assert result == (
        "postgresql+asyncpg://u:p@h:5432/medinet_hub_duoc?sslmode=require"
    )
