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

    # Reset lru_cache để mỗi test thấy env vars vừa set (không stale từ test trước).
    from app.config import get_settings

    get_settings.cache_clear()
