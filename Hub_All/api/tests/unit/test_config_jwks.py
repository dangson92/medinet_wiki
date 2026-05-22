"""Phase 3 SSO-01 — Unit test Settings JWKS cache lifecycle config (Plan 03-02 Task 1).

Verify:
- central_jwks_url default None (Plan 03-01 ship)
- jwks_refresh_interval default 3600 (1h)
- jwks_max_stale_seconds default 86400 (24h)
- Central hub_name=central + central_jwks_url=None OK
- Hub con + central_jwks_url=None raise ValidationError (T-03-02-01 mitigation)
- Hub con + central_jwks_url=set OK
- Override JWKS_REFRESH_INTERVAL / JWKS_MAX_STALE_SECONDS qua env

Decision traceability:
- D-V3-Phase3-B LOCKED — Boot fail-loud + runtime fail-quiet + 24h hard limit
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def _common_env(monkeypatch: pytest.MonkeyPatch, hub_name: str) -> None:
    db = "medinet_central" if hub_name == "central" else f"medinet_hub_{hub_name}"
    monkeypatch.setenv("HUB_NAME", hub_name)
    monkeypatch.setenv(
        "DATABASE_URL", f"postgresql+asyncpg://u:p@localhost:5432/{db}"
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    # Clear potential leftover CENTRAL_JWKS_URL + CENTRAL_URL from previous
    # test/env (test parametrize ngược thứ tự — chống pollution).
    monkeypatch.delenv("CENTRAL_JWKS_URL", raising=False)
    monkeypatch.delenv("CENTRAL_URL", raising=False)
    monkeypatch.delenv("JWKS_REFRESH_INTERVAL", raising=False)
    monkeypatch.delenv("JWKS_MAX_STALE_SECONDS", raising=False)
    # Plan 04-02 Task 1 — validator `_enforce_hub_id_for_hub_con` +
    # `_enforce_central_sync_dsn_for_hub` yêu cầu hub con set HUB_ID +
    # CENTRAL_SYNC_DSN. Auto-set cho hub con; clear cho central.
    if hub_name == "central":
        monkeypatch.delenv("HUB_ID", raising=False)
        monkeypatch.delenv("CENTRAL_SYNC_DSN", raising=False)
    else:
        monkeypatch.setenv("HUB_ID", "12345678-1234-1234-1234-123456789012")
        monkeypatch.setenv(
            "CENTRAL_SYNC_DSN",
            "postgresql+asyncpg://sync_user:pwd@postgres:5432/medinet_central",
        )


def test_jwks_defaults_match_d_v3_phase3_b(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default jwks_refresh_interval=3600, jwks_max_stale_seconds=86400."""
    _common_env(monkeypatch, "central")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.jwks_refresh_interval == 3600
    assert s.jwks_max_stale_seconds == 86400
    assert s.central_jwks_url is None  # central default None — Plan 03-01


def test_central_jwks_url_none_for_central_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Central + central_jwks_url=None OK (KHÔNG cần fetch — local pem)."""
    _common_env(monkeypatch, "central")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.hub_name == "central"
    assert s.central_jwks_url is None


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns", "phap_che"])
def test_hub_con_requires_central_jwks_url(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """Hub con + central_jwks_url=None → ValidationError (T-03-02-01 mitigation)."""
    _common_env(monkeypatch, hub_name)
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="CENTRAL_JWKS_URL"):
        Settings()


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns", "phap_che"])
def test_hub_con_with_central_jwks_url_ok(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """Hub con + central_jwks_url set → OK.

    Plan 03-04 Task 1: thêm CENTRAL_URL setenv để pass validator mới
    `_enforce_central_url_for_hub` (hub con required CENTRAL_URL).
    """
    _common_env(monkeypatch, hub_name)
    monkeypatch.setenv(
        "CENTRAL_JWKS_URL",
        "http://python-api-central:8080/.well-known/jwks.json",
    )
    # Plan 03-04 Rule 3 regression — validator mới yêu cầu hub con set CENTRAL_URL
    monkeypatch.setenv("CENTRAL_URL", "http://python-api-central:8080")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.hub_name == hub_name
    assert s.central_jwks_url == (
        "http://python-api-central:8080/.well-known/jwks.json"
    )


def test_jwks_refresh_interval_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override JWKS_REFRESH_INTERVAL qua env (test rotation nhanh)."""
    _common_env(monkeypatch, "yte")
    monkeypatch.setenv(
        "CENTRAL_JWKS_URL",
        "http://python-api-central:8080/.well-known/jwks.json",
    )
    # Plan 03-04 Rule 3 regression — validator mới yêu cầu hub con set CENTRAL_URL
    monkeypatch.setenv("CENTRAL_URL", "http://python-api-central:8080")
    monkeypatch.setenv("JWKS_REFRESH_INTERVAL", "60")
    monkeypatch.setenv("JWKS_MAX_STALE_SECONDS", "3600")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.jwks_refresh_interval == 60
    assert s.jwks_max_stale_seconds == 3600


# ────────────────────────────────────────────────────────────────────
# Plan 03-04 Task 1 — central_url field + validator (D-V3-Phase3-G)
# ────────────────────────────────────────────────────────────────────


def test_central_url_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """central_url default None ở central (KHÔNG cần redirect — local handle)."""
    _common_env(monkeypatch, "central")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.central_url is None


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns", "phap_che"])
def test_hub_con_requires_central_url(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """Hub con + central_url=None → ValidationError (T-03-04-01/04 mitigation).

    KHÔNG bù bằng central_jwks_url — 2 field tách biệt:
    - central_jwks_url: full URL endpoint /.well-known/jwks.json (Plan 03-01/02).
    - central_url: base URL build N endpoint khác login/refresh (Plan 03-04).
    """
    _common_env(monkeypatch, hub_name)
    monkeypatch.setenv(
        "CENTRAL_JWKS_URL",
        "http://python-api-central:8080/.well-known/jwks.json",
    )
    # KHÔNG set CENTRAL_URL — validator mới phải raise
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="CENTRAL_URL"):
        Settings()


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns", "phap_che"])
def test_hub_con_with_both_central_urls_ok(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """Hub con + cả CENTRAL_URL + CENTRAL_JWKS_URL set → OK (production wire)."""
    _common_env(monkeypatch, hub_name)
    monkeypatch.setenv(
        "CENTRAL_JWKS_URL",
        "http://python-api-central:8080/.well-known/jwks.json",
    )
    monkeypatch.setenv("CENTRAL_URL", "http://python-api-central:8080")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.hub_name == hub_name
    assert s.central_url == "http://python-api-central:8080"
    assert s.central_jwks_url == (
        "http://python-api-central:8080/.well-known/jwks.json"
    )
