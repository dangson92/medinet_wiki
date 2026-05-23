"""Unit test Phase 6 Plan 06-01 SETTINGS-03 (D-V3-Phase6-D LOCKED).

Settings 5 field mới + 1 model_validator `_enforce_settings_proxy_secret` —
length >= 32 char enforce BẤT KỂ central hay hub con (KHÁC pattern Phase 3+4
validator hub con only — shared secret cả 2 phía cần). Mitigate T-06-04-01
timing attack qua entropy 128-bit (32 char hex = 128 bit).

5 field mới:
- settings_proxy_secret: str = ""  — REQUIRED ca 2 side (validator enforce 32 char).
- settings_cache_ttl_rag_config: int = 60  (D-V3-Phase6-B).
- settings_cache_ttl_hub_registry: int = 300  (D-V3-Phase6-B).
- settings_cache_ttl_apikey: int = 60  (D-V3-Phase6-B).
- settings_subscriber_reconnect_seconds: int = 5  (Claude's Discretion).

Threat model cover:
- T-06-04-01 Tampering — secret entropy >= 128 bit (32 char hex).
- T-06-01-01 Spoofing — boot fail-loud nếu thiếu/short secret (deploy bug câm lặng).

NOTE: dùng `monkeypatch.setenv()` pattern theo conftest.py + test_config_phase4_fields.py.
conftest.py autouse `_env` đã set `SETTINGS_PROXY_SECRET="x"*32` default — test
override qua `monkeypatch.setenv` / `monkeypatch.delenv` per scenario.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def _central_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Helper set env tối thiểu cho central boot OK (Phase 1..5 carry forward).

    Conftest autouse đã set DATABASE_URL + COCOINDEX_DATABASE_URL + REDIS_URL +
    APP_ENV + SETTINGS_PROXY_SECRET=x*32 default. Helper set HUB_NAME explicit
    central + clear Phase 3/4 hub con fields (CENTRAL_JWKS_URL/CENTRAL_URL/HUB_ID/
    CENTRAL_SYNC_DSN) — central KHÔNG cần. Test caller override SETTINGS_PROXY_SECRET
    riêng để verify validator branches.
    """
    monkeypatch.setenv("HUB_NAME", "central")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
    )
    monkeypatch.delenv("CENTRAL_JWKS_URL", raising=False)
    monkeypatch.delenv("CENTRAL_URL", raising=False)
    monkeypatch.delenv("HUB_ID", raising=False)
    monkeypatch.delenv("CENTRAL_SYNC_DSN", raising=False)
    monkeypatch.delenv("CHECKSUM_HUB_DSNS_JSON", raising=False)


def _hub_con_env(monkeypatch: pytest.MonkeyPatch, hub_name: str = "yte") -> None:
    """Helper set env tối thiểu cho hub con boot OK Phase 1..5.

    Set HUB_NAME + DATABASE_URL + CENTRAL_JWKS_URL + CENTRAL_URL + HUB_ID +
    CENTRAL_SYNC_DSN — Phase 3+4 validator hub con required. Caller test
    override SETTINGS_PROXY_SECRET riêng.
    """
    db = f"medinet_hub_{hub_name}"
    monkeypatch.setenv("HUB_NAME", hub_name)
    monkeypatch.setenv(
        "DATABASE_URL",
        f"postgresql+asyncpg://u:p@localhost:5432/{db}",
    )
    monkeypatch.setenv(
        "CENTRAL_JWKS_URL",
        "http://python-api-central:8080/.well-known/jwks.json",
    )
    monkeypatch.setenv("CENTRAL_URL", "http://python-api-central:8080")
    monkeypatch.setenv("HUB_ID", "00000000-0000-4000-a000-000000000001")
    monkeypatch.setenv(
        "CENTRAL_SYNC_DSN",
        "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
    )


# ────────────────────────────────────────────────────────────────────────────
# Test 1: 32-char boundary OK
# ────────────────────────────────────────────────────────────────────────────
def test_settings_proxy_secret_exactly_32_char_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Settings(settings_proxy_secret="x"*32)` accept — boundary đúng 32 char OK."""
    _central_env(monkeypatch)
    monkeypatch.setenv("SETTINGS_PROXY_SECRET", "x" * 32)

    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.settings_proxy_secret == "x" * 32
    assert len(s.settings_proxy_secret) == 32


# ────────────────────────────────────────────────────────────────────────────
# Test 2: 31-char fail (below boundary)
# ────────────────────────────────────────────────────────────────────────────
def test_settings_proxy_secret_31_char_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """31 char (1 char below boundary) → ValidationError chứa "32 char"."""
    _central_env(monkeypatch)
    monkeypatch.setenv("SETTINGS_PROXY_SECRET", "x" * 31)

    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="32 char"):
        Settings()


# ────────────────────────────────────────────────────────────────────────────
# Test 3: Empty default fail (length 0)
# ────────────────────────────────────────────────────────────────────────────
def test_settings_proxy_secret_empty_default_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty string (default) → ValidationError chứa "32 char"."""
    _central_env(monkeypatch)
    monkeypatch.setenv("SETTINGS_PROXY_SECRET", "")

    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="32 char"):
        Settings()


# ────────────────────────────────────────────────────────────────────────────
# Test 4: Validator applied BOTH central + hub con (NOT branched on hub_name)
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("hub_name", ["central", "yte", "duoc", "hcns"])
def test_settings_proxy_secret_validator_both_sides(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """Validator áp dụng BẤT KỂ hub_name — central + hub con đều cần shared secret.

    KHÁC pattern Phase 3+4 `_enforce_central_jwks_url_for_hub` (hub con only)
    — shared secret D-V3-Phase6-D LOCKED: central verify header X-Internal-Auth,
    hub con gửi header → cả 2 phía đều cần secret.
    """
    if hub_name == "central":
        _central_env(monkeypatch)
    else:
        _hub_con_env(monkeypatch, hub_name)
    # Short secret → fail BẤT KỂ hub_name
    monkeypatch.setenv("SETTINGS_PROXY_SECRET", "short")

    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="32 char"):
        Settings()


# ────────────────────────────────────────────────────────────────────────────
# Test 5: TTL rag_config default 60s accept
# ────────────────────────────────────────────────────────────────────────────
def test_settings_cache_ttl_rag_config_default_60(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Settings(settings_cache_ttl_rag_config=60)` accept default 60 (D-V3-Phase6-B)."""
    _central_env(monkeypatch)
    # SETTINGS_PROXY_SECRET inherited từ conftest "x"*32 default
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.settings_cache_ttl_rag_config == 60


# ────────────────────────────────────────────────────────────────────────────
# Test 6: TTL hub_registry default 300s (5 phút rare-change)
# ────────────────────────────────────────────────────────────────────────────
def test_settings_cache_ttl_hub_registry_default_300(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Settings(settings_cache_ttl_hub_registry=300)` accept default 300 (D-V3-Phase6-B).

    5 phút rare-change — FACTOR-04 `make hub-add` KHÔNG thường xuyên + pub/sub
    invalidate primary mechanism khi đổi registry.
    """
    _central_env(monkeypatch)
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.settings_cache_ttl_hub_registry == 300


# ────────────────────────────────────────────────────────────────────────────
# Test 7: TTL apikey default 60s (AUX-02 hot revoke acceptable window)
# ────────────────────────────────────────────────────────────────────────────
def test_settings_cache_ttl_apikey_default_60(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Settings(settings_cache_ttl_apikey=60)` accept default 60 (D-V3-Phase6-B)."""
    _central_env(monkeypatch)
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.settings_cache_ttl_apikey == 60


# ────────────────────────────────────────────────────────────────────────────
# Test 8: Subscriber reconnect default 5s (Claude's Discretion fail-quiet retry)
# ────────────────────────────────────────────────────────────────────────────
def test_settings_subscriber_reconnect_seconds_default_5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Settings(settings_subscriber_reconnect_seconds=5)` accept default 5.

    Subscriber loop pubsub disconnect → sleep N seconds + retry connect.
    KHÔNG fail-loud (TTL natural fallback) — Claude's Discretion CONTEXT.md.
    """
    _central_env(monkeypatch)
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.settings_subscriber_reconnect_seconds == 5


# ────────────────────────────────────────────────────────────────────────────
# Test 9 (regression): Settings hợp lệ Phase 1..5 instantiate OK với 32-char secret
# ────────────────────────────────────────────────────────────────────────────
def test_full_settings_hub_con_with_all_phase_fields_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings hợp lệ Phase 1..5 + settings_proxy_secret 32 char → instantiate OK.

    Regression: Phase 1 (hub_dsn) + Phase 3 (jwks_url + central_url) + Phase 4
    (hub_id + central_sync_dsn) + Phase 6 (settings_proxy_secret) tất cả set
    → KHÔNG ValidationError. Đảm bảo Phase 6 KHÔNG break Phase 1..5 happy path.
    """
    _hub_con_env(monkeypatch, "yte")
    monkeypatch.setenv("SETTINGS_PROXY_SECRET", "x" * 32)
    # Đồng thời verify 5 TTL/subscriber field default OK khi load chung
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.hub_name == "yte"
    assert s.hub_id == "00000000-0000-4000-a000-000000000001"
    assert s.central_url == "http://python-api-central:8080"
    assert s.central_sync_dsn is not None
    assert s.settings_proxy_secret == "x" * 32
    assert s.settings_cache_ttl_rag_config == 60
    assert s.settings_cache_ttl_hub_registry == 300
    assert s.settings_cache_ttl_apikey == 60
    assert s.settings_subscriber_reconnect_seconds == 5
