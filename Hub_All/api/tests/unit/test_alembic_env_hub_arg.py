"""Unit tests cho `parse_hub_x_arg` + `resolve_env_database_url` ở `migrations/env.py`.

Phase 1 Plan 01-03 (TOPO-02) — v3.0 Multi-Hub Split per-hub Alembic:
- `alembic -x hub=<name> upgrade head` → env.py đọc `-x hub` arg + override DSN runtime.
- `resolve_env_database_url(base_dsn, hub_arg, default_hub)` hỗ trợ cross-hub roundtrip
  (W8 fix: yte → duoc qua un-resolve về central rồi resolve sang target).

Threat model cover (xem 01-03-PLAN.md `<threat_model>`):
- T-01-03-01 Tampering: -x hub=<invalid> → ValueError ở parse_hub_x_arg.
- T-01-03-02 Tampering: DSN resolver bug → ValueError nếu base_dsn không trỏ
  medinet_central HOẶC medinet_hub_*.

NOTE: env.py KHÔNG phải module Python chuẩn (Alembic load qua exec_module). Test import
helpers qua sys.path inject — chỉ test 2 hàm pure (parse_hub_x_arg + resolve_env_database_url),
KHÔNG test side effect Alembic runtime (cần Postgres thật — defer integration test Plan 05).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# env.py không phải module Python chuẩn (alembic load via exec_module).
# Import qua sys.path inject để test 2 helper function pure.
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
if str(_MIGRATIONS_DIR) not in sys.path:
    sys.path.insert(0, str(_MIGRATIONS_DIR))

from env import parse_hub_x_arg, resolve_env_database_url  # noqa: E402

BASE_CENTRAL = "postgresql+asyncpg://u:p@h:5432/medinet_central"
BASE_YTE = "postgresql+asyncpg://u:p@h:5432/medinet_hub_yte"
BASE_INVALID = "postgresql+asyncpg://u:p@h:5432/some_random_db"


# === parse_hub_x_arg — 4 test ===


def test_parse_single_hub() -> None:
    """`-x hub=yte` → 'yte'."""
    assert parse_hub_x_arg(["hub=yte"]) == "yte"


def test_parse_with_other_args() -> None:
    """Nhiều -x argument, chọn đúng hub=duoc."""
    assert parse_hub_x_arg(["other=value", "hub=duoc"]) == "duoc"


def test_parse_empty() -> None:
    """KHÔNG -x hub argument → None (fallback Settings.hub_name)."""
    assert parse_hub_x_arg([]) is None


def test_parse_invalid_raises() -> None:
    """`-x hub=<invalid>` → ValueError (T-01-03-01 Tampering mitigation).

    FACTOR-04 dynamic validation: regex ``^[a-z][a-z0-9_]{0,15}$`` + RESERVED
    blacklist. Test 3 fail mode: uppercase (regex), reserved (blacklist),
    hyphen (regex). Hub mới hợp lệ (vd "dmd", "phap_che") PASS — KHÔNG hardcode
    whitelist 4 hub (`make hub-add` không phải sửa code).
    """
    with pytest.raises(ValueError, match="không hợp lệ"):
        parse_hub_x_arg(["hub=Invalid"])  # uppercase reject regex
    with pytest.raises(ValueError, match="không hợp lệ"):
        parse_hub_x_arg(["hub=postgres"])  # reserved blacklist
    with pytest.raises(ValueError, match="không hợp lệ"):
        parse_hub_x_arg(["hub=phap-che"])  # hyphen reject regex


def test_parse_dynamic_hub_accepted() -> None:
    """FACTOR-04 dynamic hub name (vd 'dmd') PASS validation.

    Gap fix 2026-05-23 — env.py trước hardcode 4 hub whitelist, block hub mới
    qua `make hub-add`. Sau refactor dùng ``is_valid_hub_name`` helper từ
    app.config (single source of truth FACTOR-04 Plan 02-05).
    """
    assert parse_hub_x_arg(["hub=dmd"]) == "dmd"
    assert parse_hub_x_arg(["hub=phap_che"]) == "phap_che"


# === resolve_env_database_url — 5 test (3 core + 2 W8) ===


def test_resolve_none_arg_central_default() -> None:
    """No -x arg + default_hub=central + base_dsn central → no-op."""
    assert (
        resolve_env_database_url(BASE_CENTRAL, None, default_hub="central")
        == BASE_CENTRAL
    )


def test_resolve_arg_overrides_default() -> None:
    """`-x hub=yte` ưu tiên hơn default_hub=central."""
    out = resolve_env_database_url(BASE_CENTRAL, "yte", default_hub="central")
    assert out.endswith("/medinet_hub_yte")


def test_resolve_fallback_to_default_hub() -> None:
    """No -x arg + default_hub=yte → fallback resolve sang yte."""
    out = resolve_env_database_url(BASE_CENTRAL, None, default_hub="yte")
    assert out.endswith("/medinet_hub_yte")


def test_resolve_unresolves_yte_base_when_arg_central() -> None:
    """Caller chạy alembic env với DATABASE_URL=...medinet_hub_yte (Settings.hub_name=yte)
    rồi pass -x hub=central → env phải un-resolve về central."""
    out = resolve_env_database_url(BASE_YTE, "central", default_hub="yte")
    assert out.endswith("/medinet_central")


def test_resolve_cross_hub_yte_to_duoc() -> None:
    """W8 cross-hub roundtrip: DATABASE_URL=...medinet_hub_yte (Settings.hub_name=yte)
    + -x hub=duoc → un-resolve yte về central rồi resolve sang duoc.
    Use case: dev pass `alembic -x hub=duoc` từ shell có HUB_NAME=yte set."""
    out = resolve_env_database_url(BASE_YTE, "duoc", default_hub="yte")
    assert out.endswith("/medinet_hub_duoc")


def test_resolve_invalid_base_dsn_raises() -> None:
    """W8: base_dsn không trỏ medinet_central HOẶC medinet_hub_* → caller dùng sai input.

    T-01-03-02 Tampering mitigation: DSN resolver bug catch ở input boundary.
    """
    with pytest.raises(ValueError, match="medinet_central hoặc medinet_hub_"):
        resolve_env_database_url(BASE_INVALID, "yte", default_hub="central")
