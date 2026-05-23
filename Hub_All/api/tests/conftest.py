"""Pytest fixtures cho api/tests.

Phase 1 chỉ unit test — chưa cần Postgres/Redis thực (defer testcontainers
sang Phase 2+). Fixture `_env` autouse set env vars tối thiểu để Settings
load được + clear `get_settings()` cache mỗi test cho independence.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set env vars tối thiểu cho `Settings` load được trong unit test.

    v3.0 Plan 01-02 — `Settings._enforce_hub_dsn_match` validator yêu cầu
    `DATABASE_URL` kết thúc bằng `/medinet_central` khi `HUB_NAME="central"`
    (default). Test stub DSN dùng `medinet_central` thay vì `test` để pass
    validator. Test cần stub `HUB_NAME="<hub>"` phải set rõ qua
    `monkeypatch.setenv("HUB_NAME", ...)` + `DATABASE_URL` khớp pattern.
    """
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/medinet_central",
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://test:test@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("APP_ENV", "dev")
    # Phase 6 Plan 06-01 SETTINGS-03 (D-V3-Phase6-D) — Validator
    # `_enforce_settings_proxy_secret` enforce length >= 32 char BOTH central
    # + hub con. Default test value 32 char dummy ("x" * 32) — cho phép mọi
    # unit test Phase 1..5 instantiate Settings KHÔNG break. Test riêng
    # `test_config_settings_proxy_secret.py` override env per scenario qua
    # `monkeypatch.setenv("SETTINGS_PROXY_SECRET", ...)` HOẶC `monkeypatch.delenv`.
    monkeypatch.setenv("SETTINGS_PROXY_SECRET", "x" * 32)

    # Reset lru_cache để mỗi test thấy env vars vừa set (không stale từ test trước).
    from app.config import get_settings

    get_settings.cache_clear()
