"""Unit tests cho Settings 5 field mới Phase 4 Plan 04-02 + 3 model_validator
+ 1 length validator + 1 helper property.

Plan 04-02 SYNC-01/03/04 (D-V3-Phase4-A5/C3/D2):
- hub_id: str | None = None — UUID4 string từ env HUB_ID (hub con required boot fail-loud)
- central_sync_dsn: str | None = None — asyncpg DSN trỏ medinet_central (hub con required)
- checksum_hub_dsns_json: str | None = None — JSON dict {hub_name: dsn} central scheduler
- sync_batch_size: int = 100 — worker batch query SELECT FOR UPDATE SKIP LOCKED
- sync_poll_interval: float = 5.0 — worker idle poll sleep seconds
- sync_max_attempts: int = 5 — exp backoff max retry trước mark dead
- sync_backoff_seconds: list[int] = [1, 5, 30, 120] — CSV parse mode="before"

3 model_validator boot fail-fast:
- _enforce_hub_id_for_hub_con — hub_name != "central" → hub_id required
- _enforce_central_sync_dsn_for_hub — hub_name != "central" → central_sync_dsn required
- _enforce_checksum_hub_dsns_for_central — central + checksum_hub_dsns_json set → JSON parseable
  + dict[str,str] type check (None OK cho deploy lần đầu)

1 length validator:
- _validate_backoff_length — len(backoff) == max_attempts - 1

1 helper property:
- checksum_hub_dsns -> dict[str, str] — parse JSON (empty dict nếu None)

Threat model cover (PLAN 04-02 STRIDE register):
- T-04-02-01 Tampering — env thiếu HUB_ID → fail-fast validator
- T-04-02-02 DoS — env thiếu CENTRAL_SYNC_DSN → fail-fast validator
- T-04-02-03 Tampering — CHECKSUM_HUB_DSNS_JSON malformed → JSON parse error
- T-04-02-05 DoS — backoff length mismatch → IndexError runtime mitigation

NOTE: dùng `monkeypatch.setenv()` pattern theo conftest.py + test_config_hub_name.py.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def _hub_con_env(
    monkeypatch: pytest.MonkeyPatch,
    hub_name: str,
) -> None:
    """Helper set env tối thiểu cho hub con boot OK (skip Phase 4 fields).

    Set HUB_NAME + DATABASE_URL + CENTRAL_JWKS_URL + CENTRAL_URL (Phase 3
    regression carry forward — validator Phase 1/3 vẫn enforce). Phase 4 fields
    (HUB_ID + CENTRAL_SYNC_DSN) caller test set qua monkeypatch riêng theo
    scenario.
    """
    db = f"medinet_hub_{hub_name}"
    monkeypatch.setenv("HUB_NAME", hub_name)
    monkeypatch.setenv(
        "DATABASE_URL",
        f"postgresql+asyncpg://u:p@localhost:5432/{db}",
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv(
        "CENTRAL_JWKS_URL",
        "http://python-api-central:8080/.well-known/jwks.json",
    )
    monkeypatch.setenv("CENTRAL_URL", "http://python-api-central:8080")
    # Phase 4 fields explicit clear — test set lại theo scenario
    monkeypatch.delenv("HUB_ID", raising=False)
    monkeypatch.delenv("CENTRAL_SYNC_DSN", raising=False)
    monkeypatch.delenv("CHECKSUM_HUB_DSNS_JSON", raising=False)
    monkeypatch.delenv("SYNC_BATCH_SIZE", raising=False)
    monkeypatch.delenv("SYNC_POLL_INTERVAL", raising=False)
    monkeypatch.delenv("SYNC_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("SYNC_BACKOFF_SECONDS", raising=False)


def _central_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Helper set env tối thiểu cho central boot OK."""
    monkeypatch.setenv("HUB_NAME", "central")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("CENTRAL_JWKS_URL", raising=False)
    monkeypatch.delenv("CENTRAL_URL", raising=False)
    monkeypatch.delenv("HUB_ID", raising=False)
    monkeypatch.delenv("CENTRAL_SYNC_DSN", raising=False)
    monkeypatch.delenv("CHECKSUM_HUB_DSNS_JSON", raising=False)
    monkeypatch.delenv("SYNC_BATCH_SIZE", raising=False)
    monkeypatch.delenv("SYNC_POLL_INTERVAL", raising=False)
    monkeypatch.delenv("SYNC_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("SYNC_BACKOFF_SECONDS", raising=False)


# ────────────────────────────────────────────────────────────────────────────
# Test 1: Central boot OK — KHÔNG required hub_id / central_sync_dsn
# ────────────────────────────────────────────────────────────────────────────
def test_central_boot_ok_without_phase4_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Central aggregator KHÔNG own data → hub_id / central_sync_dsn None OK.

    D-V3-Phase4-D2: Central aggregator KHÔNG cần hub_id (KHÔNG INSERT chunks).
    D-V3-Phase4-A1: Central KHÔNG self-push outbox → KHÔNG cần central_sync_dsn.
    """
    _central_env(monkeypatch)
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.hub_name == "central"
    assert s.hub_id is None
    assert s.central_sync_dsn is None
    assert s.checksum_hub_dsns_json is None


# ────────────────────────────────────────────────────────────────────────────
# Test 2: Hub con missing HUB_ID → ValidationError (T-04-02-01)
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns", "phap_che"])
def test_hub_con_requires_hub_id(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """Hub con + HUB_ID=None → ValidationError (D-V3-Phase4-D2 fail-fast)."""
    _hub_con_env(monkeypatch, hub_name)
    # KHÔNG set HUB_ID — validator phải raise
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="HUB_ID"):
        Settings()


# ────────────────────────────────────────────────────────────────────────────
# Test 3: Hub con với HUB_ID không phải UUID → ValidationError (T-04-02-03)
# ────────────────────────────────────────────────────────────────────────────
def test_hub_con_hub_id_invalid_uuid_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hub_id='not-a-uuid' → ValidationError (field_validator _validate_hub_id_uuid)."""
    _hub_con_env(monkeypatch, "yte")
    monkeypatch.setenv("HUB_ID", "not-a-uuid")
    monkeypatch.setenv(
        "CENTRAL_SYNC_DSN",
        "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
    )
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="hub_id invalid UUID"):
        Settings()


# ────────────────────────────────────────────────────────────────────────────
# Test 4: Hub con có HUB_ID nhưng missing CENTRAL_SYNC_DSN → ValidationError
# ────────────────────────────────────────────────────────────────────────────
def test_hub_con_requires_central_sync_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hub con + HUB_ID set + CENTRAL_SYNC_DSN=None → ValidationError (T-04-02-02)."""
    _hub_con_env(monkeypatch, "yte")
    monkeypatch.setenv("HUB_ID", "12345678-1234-1234-1234-123456789012")
    # KHÔNG set CENTRAL_SYNC_DSN — validator phải raise
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="CENTRAL_SYNC_DSN"):
        Settings()


# ────────────────────────────────────────────────────────────────────────────
# Test 5: Hub con với cả 2 field set → boot OK
# ────────────────────────────────────────────────────────────────────────────
def test_hub_con_with_all_required_fields_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hub con + HUB_ID UUID4 + CENTRAL_SYNC_DSN set → boot OK."""
    _hub_con_env(monkeypatch, "yte")
    monkeypatch.setenv("HUB_ID", "12345678-1234-1234-1234-123456789012")
    monkeypatch.setenv(
        "CENTRAL_SYNC_DSN",
        "postgresql+asyncpg://sync_user:pwd@postgres:5432/medinet_central",
    )
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.hub_name == "yte"
    assert s.hub_id == "12345678-1234-1234-1234-123456789012"
    assert s.central_sync_dsn is not None
    assert "medinet_central" in s.central_sync_dsn


# ────────────────────────────────────────────────────────────────────────────
# Test 6: Central + checksum_hub_dsns_json=None → boot OK (deploy lần đầu)
# ────────────────────────────────────────────────────────────────────────────
def test_central_without_checksum_hub_dsns_json_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Central deploy lần đầu CHƯA register hub con → checksum_hub_dsns_json
    optional default None (D-V3-Phase4-C3 — scheduler tick no-op empty dict).
    """
    _central_env(monkeypatch)
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.hub_name == "central"
    assert s.checksum_hub_dsns_json is None
    assert s.checksum_hub_dsns == {}  # property empty dict


# ────────────────────────────────────────────────────────────────────────────
# Test 7: Central với CHECKSUM_HUB_DSNS_JSON valid → property parse dict
# ────────────────────────────────────────────────────────────────────────────
def test_central_checksum_hub_dsns_property_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """checksum_hub_dsns property parse JSON → dict[str, str] (D-V3-Phase4-C3)."""
    _central_env(monkeypatch)
    monkeypatch.setenv(
        "CHECKSUM_HUB_DSNS_JSON",
        '{"yte": "postgresql://u:p@h:5432/medinet_hub_yte",'
        ' "duoc": "postgresql://u:p@h:5432/medinet_hub_duoc"}',
    )
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.checksum_hub_dsns == {
        "yte": "postgresql://u:p@h:5432/medinet_hub_yte",
        "duoc": "postgresql://u:p@h:5432/medinet_hub_duoc",
    }


# ────────────────────────────────────────────────────────────────────────────
# Test 8: Central với CHECKSUM_HUB_DSNS_JSON invalid JSON → ValidationError
# ────────────────────────────────────────────────────────────────────────────
def test_central_checksum_hub_dsns_invalid_json_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CHECKSUM_HUB_DSNS_JSON='not-json' → ValidationError (T-04-02-03)."""
    _central_env(monkeypatch)
    monkeypatch.setenv("CHECKSUM_HUB_DSNS_JSON", "not-json")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="CHECKSUM_HUB_DSNS_JSON invalid JSON"):
        Settings()


# ────────────────────────────────────────────────────────────────────────────
# Test 9: Central với CHECKSUM_HUB_DSNS_JSON là list thay vì dict → ValidationError
# ────────────────────────────────────────────────────────────────────────────
def test_central_checksum_hub_dsns_not_dict_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON parseable nhưng KHÔNG phải dict → ValidationError."""
    _central_env(monkeypatch)
    monkeypatch.setenv("CHECKSUM_HUB_DSNS_JSON", '["list", "not", "dict"]')
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="dict"):
        Settings()


# ────────────────────────────────────────────────────────────────────────────
# Test 10: Defaults D-V3-Phase4-A5 — sync_batch/poll/max/backoff
# ────────────────────────────────────────────────────────────────────────────
def test_sync_defaults_match_d_v3_phase4_a5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-V3-Phase4-A5 LOCKED defaults: batch=100 + poll=5.0 + max=5 + backoff=[1,5,30,120]."""
    _central_env(monkeypatch)
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.sync_batch_size == 100
    assert s.sync_poll_interval == 5.0
    assert s.sync_max_attempts == 5
    assert s.sync_backoff_seconds == [1, 5, 30, 120]


# ────────────────────────────────────────────────────────────────────────────
# Test 11: SYNC_BACKOFF_SECONDS CSV parse mode="before"
# ────────────────────────────────────────────────────────────────────────────
def test_sync_backoff_seconds_csv_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SYNC_BACKOFF_SECONDS env CSV '2,10,60,300' → [2, 10, 60, 300]."""
    _central_env(monkeypatch)
    monkeypatch.setenv("SYNC_BACKOFF_SECONDS", "2,10,60,300")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.sync_backoff_seconds == [2, 10, 60, 300]


# ────────────────────────────────────────────────────────────────────────────
# Test 12: backoff length mismatch max_attempts → ValidationError (T-04-02-05)
# ────────────────────────────────────────────────────────────────────────────
def test_backoff_length_mismatch_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """max_attempts=3 yêu cầu backoff length=2 — set length=4 → ValidationError.

    D-V3-Phase4-A5: attempt 1 KHÔNG backoff, attempts 2..N dùng backoff[0..N-2].
    """
    _central_env(monkeypatch)
    monkeypatch.setenv("SYNC_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("SYNC_BACKOFF_SECONDS", "1,5,30,120")  # 4 elements vs 2 expected
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="length mismatch"):
        Settings()


# ────────────────────────────────────────────────────────────────────────────
# Test 13 (Bonus): backoff length custom match max_attempts → OK
# ────────────────────────────────────────────────────────────────────────────
def test_backoff_length_match_custom_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operator override max_attempts=3 + backoff '1,5' (length 2) → boot OK."""
    _central_env(monkeypatch)
    monkeypatch.setenv("SYNC_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("SYNC_BACKOFF_SECONDS", "1,5")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.sync_max_attempts == 3
    assert s.sync_backoff_seconds == [1, 5]


# ────────────────────────────────────────────────────────────────────────────
# Test 14 (Bonus): Override SYNC_BATCH_SIZE + SYNC_POLL_INTERVAL qua env
# ────────────────────────────────────────────────────────────────────────────
def test_sync_batch_and_poll_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operator tune SYNC_BATCH_SIZE=50 + SYNC_POLL_INTERVAL=2.5 → Settings load đúng."""
    _central_env(monkeypatch)
    monkeypatch.setenv("SYNC_BATCH_SIZE", "50")
    monkeypatch.setenv("SYNC_POLL_INTERVAL", "2.5")
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert s.sync_batch_size == 50
    assert s.sync_poll_interval == 2.5
