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

NOTE: conftest.py autouse `_env` fixture đã set `COCOINDEX_DATABASE_URL`,
`REDIS_URL`, `APP_ENV`, `DATABASE_URL` mặc định. Test instantiate Settings
trực tiếp với kwargs sẽ override env. Để bảo đảm `hub_name` đọc từ env
HUB_NAME (Test 6), dùng `monkeypatch.setenv("HUB_NAME", ...)`.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, resolve_database_url

# Stub các required field khác (cocoindex_database_url, redis_url) để Settings init OK
# trong test instantiate trực tiếp. conftest._env autouse cũng set sẵn nhưng đây
# explicit kwargs để test scenario rõ ràng (DSN cocoindex/redis không phải focus).
VALID_BASE: dict[str, str] = {
    "cocoindex_database_url": "postgresql://u:p@h:5432/medinet_cocoindex",
    "redis_url": "redis://localhost:6379/0",
}


# === Test 1: central default DSN khớp medinet_central ===
def test_central_matches_central_dsn_ok() -> None:
    """Settings(hub_name='central', DSN /medinet_central) — instantiate OK."""
    s = Settings(
        hub_name="central",
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_central",
        **VALID_BASE,
    )
    assert s.hub_name == "central"
    assert s.database_url.endswith("/medinet_central")


# === Test 2: hub yte với DSN medinet_hub_yte ===
def test_yte_matches_yte_dsn_ok() -> None:
    """Settings(hub_name='yte', DSN /medinet_hub_yte) — instantiate OK."""
    s = Settings(
        hub_name="yte",
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_hub_yte",
        **VALID_BASE,
    )
    assert s.hub_name == "yte"
    assert s.database_url.endswith("/medinet_hub_yte")


# === Test 3: hub yte trỏ medinet_central → ValidationError (E-V3-3) ===
def test_yte_mismatch_central_raises() -> None:
    """T-01-02-01 Spoofing — HUB_NAME=yte + DSN central → fail-fast.

    Lỗi nguy hiểm nhất: hub con vô tình truy cập aggregated data central.
    Validator phải raise startup, KHÔNG defer runtime.
    """
    with pytest.raises(ValidationError, match="DSN mismatch hub_name"):
        Settings(
            hub_name="yte",
            database_url="postgresql+asyncpg://u:p@h:5432/medinet_central",
            **VALID_BASE,
        )


# === Test 4: hub duoc trỏ medinet_hub_yte → ValidationError (cross-hub) ===
def test_duoc_mismatch_yte_dsn_raises() -> None:
    """T-01-02-02 Information Disclosure — cross-hub DSN typo bị reject startup."""
    with pytest.raises(ValidationError, match="DSN mismatch hub_name"):
        Settings(
            hub_name="duoc",
            database_url="postgresql+asyncpg://u:p@h:5432/medinet_hub_yte",
            **VALID_BASE,
        )


# === Test 5: hub_name không thuộc Literal → ValidationError ===
def test_invalid_hub_name_raises() -> None:
    """Literal restrict 4 giá trị — bất kỳ value khác (typo, hub mới chưa register)
    → ValidationError. Bảo vệ chống Plan 04 hub-init forget update Literal.
    """
    with pytest.raises(ValidationError):
        Settings(
            hub_name="invalid_hub",  # type: ignore[arg-type]
            database_url="postgresql+asyncpg://u:p@h:5432/medinet_central",
            **VALID_BASE,
        )


# === Test 6: Default hub_name = 'central' nếu env HUB_NAME không set ===
def test_default_hub_name_is_central(monkeypatch: pytest.MonkeyPatch) -> None:
    """M2 backward-compat — Settings() không truyền hub_name → default 'central'.

    Phải đảm bảo env HUB_NAME không có (conftest._env không set HUB_NAME, nhưng
    người chạy local có thể có HUB_NAME export sẵn). Explicit `delenv` để chắc.
    """
    monkeypatch.delenv("HUB_NAME", raising=False)
    s = Settings(
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_central",
        **VALID_BASE,
    )
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
    """T-01-02-04 Tampering — base_dsn không kết thúc /medinet_central → caller
    misuse, raise ValueError với message rõ.
    """
    bad_base = "postgresql+asyncpg://u:p@h:5432/medinet_hub_yte"
    with pytest.raises(ValueError, match="medinet_central"):
        resolve_database_url(bad_base, "duoc")


# === Bonus coverage: DSN có query string vẫn validate đúng ===
def test_dsn_with_query_string_validates() -> None:
    """Validator strip `?option=value` trước khi check suffix — DSN production
    thường có `?sslmode=require` hoặc tương tự.
    """
    s = Settings(
        hub_name="yte",
        database_url=(
            "postgresql+asyncpg://u:p@h:5432/medinet_hub_yte?sslmode=require"
        ),
        **VALID_BASE,
    )
    assert s.hub_name == "yte"


# === Bonus coverage: resolve_database_url giữ query string ===
def test_resolve_database_url_preserves_query() -> None:
    """Helper preserve query string khi đổi segment database name."""
    base = "postgresql+asyncpg://u:p@h:5432/medinet_central?sslmode=require"
    result = resolve_database_url(base, "duoc")
    assert result == "postgresql+asyncpg://u:p@h:5432/medinet_hub_duoc?sslmode=require"
