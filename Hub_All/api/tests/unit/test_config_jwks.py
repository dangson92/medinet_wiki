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
    # Clear potential leftover CENTRAL_JWKS_URL from previous test/env.
    monkeypatch.delenv("CENTRAL_JWKS_URL", raising=False)
    monkeypatch.delenv("JWKS_REFRESH_INTERVAL", raising=False)
    monkeypatch.delenv("JWKS_MAX_STALE_SECONDS", raising=False)


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
    """Hub con + central_jwks_url set → OK."""
    _common_env(monkeypatch, hub_name)
    monkeypatch.setenv(
        "CENTRAL_JWKS_URL",
        "http://python-api-central:8080/.well-known/jwks.json",
    )
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
    monkeypatch.setenv("JWKS_REFRESH_INTERVAL", "60")
    monkeypatch.setenv("JWKS_MAX_STALE_SECONDS", "3600")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.jwks_refresh_interval == 60
    assert s.jwks_max_stale_seconds == 3600
