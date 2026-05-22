"""Unit tests cho `Settings.hub_name` str validator (FACTOR-04 Plan 02-05).

Plan 02-05 đổi field `hub_name` từ Literal[4 hub] → str + regex + blacklist.
Test này verify validator chấp nhận hub mới (dynamic registration) đồng thời
reject 10 invalid pattern + 6 reserved name + edge case empty/single-char.

Threat model cover:
- T-02-05-01 Tampering: hub_name attacker-controlled env injection special char
  → regex reject pre-DB-create
- T-02-05-02 Privilege confuse: hub_name=medinet / postgres collision Postgres
  role/system DB → blacklist reject startup
- T-02-05-03 DoS: hub_name = 100-char string blow up DB identifier limit →
  regex max 16 char reject

Pattern theo test_config_hub_name.py (Phase 1 Plan 01-02) — monkeypatch.setenv +
get_settings.cache_clear → Settings() fresh instantiate.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import RESERVED_HUB_NAMES, Settings, get_settings


def _set_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    hub_name: str | None = None,
    database_url: str | None = None,
) -> None:
    if hub_name is not None:
        monkeypatch.setenv("HUB_NAME", hub_name)
    if database_url is not None:
        monkeypatch.setenv("DATABASE_URL", database_url)
    # Plan 03-02 Task 1 — validator `_enforce_central_jwks_url_for_hub` yêu cầu
    # hub con set CENTRAL_JWKS_URL. Auto-set cho mọi hub_name != "central" để
    # test cũ Plan 02-05 (regression FACTOR-04) KHÔNG fail. Test REJECT pattern
    # vẫn raise sớm ở hub_name regex validator (before model_validator), nên
    # CENTRAL_JWKS_URL không ảnh hưởng đó.
    if hub_name is not None and hub_name != "central":
        monkeypatch.setenv(
            "CENTRAL_JWKS_URL",
            "http://python-api-central:8080/.well-known/jwks.json",
        )
    get_settings.cache_clear()


# ═══════════════════════════════════════════════════════════════════════════
# ACCEPT scenarios — 4 hub gốc (regression) + 3 hub mới (dynamic)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("hub", ["central", "yte", "duoc", "hcns"])
def test_accept_4_original_hubs_regression(
    monkeypatch: pytest.MonkeyPatch, hub: str
) -> None:
    """Regression — 4 hub gốc PHẢI accept sau khi đổi Literal → str + regex."""
    dsn_target = (
        "medinet_central" if hub == "central" else f"medinet_hub_{hub}"
    )
    _set_env(
        monkeypatch,
        hub_name=hub,
        database_url=f"postgresql+asyncpg://u:p@h:5432/{dsn_target}",
    )
    s = Settings()
    assert s.hub_name == hub


@pytest.mark.parametrize("hub", ["phap_che", "marketing", "dev_test"])
def test_accept_dynamic_hub_names(
    monkeypatch: pytest.MonkeyPatch, hub: str
) -> None:
    """Hub mới (vd phap_che, marketing) match regex → accept (FACTOR-04 enable)."""
    _set_env(
        monkeypatch,
        hub_name=hub,
        database_url=f"postgresql+asyncpg://u:p@h:5432/medinet_hub_{hub}",
    )
    s = Settings()
    assert s.hub_name == hub


def test_accept_single_char_hub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Edge case — 1-char hub name (vd 'a') OK qua regex `{0,15}` (min total 1)."""
    _set_env(
        monkeypatch,
        hub_name="a",
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_hub_a",
    )
    s = Settings()
    assert s.hub_name == "a"


def test_accept_max_length_16_char(monkeypatch: pytest.MonkeyPatch) -> None:
    """Edge case — 16-char hub name OK (boundary inclusive)."""
    hub_16 = "a" + "b" * 15  # 16 char total
    assert len(hub_16) == 16
    _set_env(
        monkeypatch,
        hub_name=hub_16,
        database_url=f"postgresql+asyncpg://u:p@h:5432/medinet_hub_{hub_16}",
    )
    s = Settings()
    assert s.hub_name == hub_16


# ═══════════════════════════════════════════════════════════════════════════
# REJECT pattern — uppercase / hyphen / starting-digit / starting-underscore /
# too-long / empty / special-char
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "hub,reason",
    [
        ("Yte", "uppercase"),
        ("YTE", "all-uppercase"),
        ("phap-che", "hyphen-disallowed"),
        ("1hub", "starting-digit"),
        ("_underscore", "starting-underscore"),
        ("17chars_name_long", "exceeds-16-char-max"),  # 17 char
        ("", "empty-string"),
        ("hub.dot", "dot-disallowed"),
        ("hub space", "whitespace-disallowed"),
        ("hub$dollar", "special-char-disallowed"),
    ],
)
def test_reject_invalid_pattern(
    monkeypatch: pytest.MonkeyPatch, hub: str, reason: str
) -> None:
    """T-02-05-01 / T-02-05-03 — Regex validator reject 10 invalid pattern."""
    _set_env(
        monkeypatch,
        hub_name=hub,
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_central",
    )
    with pytest.raises(ValidationError, match="hub_name invalid format"):
        Settings()


# ═══════════════════════════════════════════════════════════════════════════
# REJECT reserved blacklist — 6 name collide Postgres system DB / role
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("hub", sorted(RESERVED_HUB_NAMES))
def test_reject_reserved_hub_names(
    monkeypatch: pytest.MonkeyPatch, hub: str
) -> None:
    """T-02-05-02 — 6 reserved name (postgres/cocoindex/template0/template1/
    public/medinet) reject để tránh collision Postgres system / role medinet.
    """
    _set_env(
        monkeypatch,
        hub_name=hub,
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_central",
    )
    with pytest.raises(ValidationError, match="hub_name reserved"):
        Settings()


def test_central_not_in_reserved_blacklist() -> None:
    """'central' KHÔNG trong blacklist — aggregator special-case (medinet_central
    DB mapping, KHÔNG prefix medinet_hub_).
    """
    assert "central" not in RESERVED_HUB_NAMES


def test_reserved_blacklist_size_is_6() -> None:
    """Lock blacklist size — thêm reserved name mới phải update test này +
    docstring RESERVED_HUB_NAMES.
    """
    assert len(RESERVED_HUB_NAMES) == 6


# ═══════════════════════════════════════════════════════════════════════════
# DSN match validator regression — Phase 1 _enforce_hub_dsn_match dùng
# self.hub_name dynamic, accept str từ trước → Plan 02-05 KHÔNG break.
# ═══════════════════════════════════════════════════════════════════════════


def test_dynamic_hub_dsn_match_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hub mới phap_che + DSN /medinet_hub_phap_che → _enforce_hub_dsn_match
    pass (Phase 1 validator dùng self.hub_name dynamic, KHÔNG hardcode 4 hub).
    """
    _set_env(
        monkeypatch,
        hub_name="phap_che",
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_hub_phap_che",
    )
    s = Settings()
    assert s.hub_name == "phap_che"
    assert s.database_url.endswith("/medinet_hub_phap_che")


def test_dynamic_hub_dsn_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hub mới phap_che nhưng DSN /medinet_hub_marketing → fail-fast (E-V3-3
    enforce hub con KHÔNG truy cập data hub khác).
    """
    _set_env(
        monkeypatch,
        hub_name="phap_che",
        database_url="postgresql+asyncpg://u:p@h:5432/medinet_hub_marketing",
    )
    with pytest.raises(ValidationError, match="DSN mismatch hub_name"):
        Settings()
