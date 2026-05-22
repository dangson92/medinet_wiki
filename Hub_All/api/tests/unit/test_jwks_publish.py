"""Phase 3 SSO-01 — Unit test JWKS publish layer (Plan 03-01 Task 1+2).

Verify (Task 1 — publish layer):
- load_public_key_as_jwk shape RFC 7517 với M2 keypair api/keys/public.pem.
- publish_jwks() trả {"keys": [<single JWK>]}.
- _derive_kid deterministic SHA-256 8-byte prefix base64url.
- _int_to_base64url match JWK spec (e=65537 → "AQAB").
- Defensive: non-RSA key reject + missing file raise OSError.

Verify (Task 2 — mount conditional):
- /.well-known/jwks.json mount khi HUB_NAME=central → 200 + JWK Set shape.
- /.well-known/jwks.json strip khi HUB_NAME=yte → 404 envelope D6 shape.
- Settings.central_jwks_url default None ở mọi hub (Plan 03-02 sẽ enforce hub con).

Decision traceability:
- D-V3-Phase3-A — JWKS endpoint RFC 7517 (KHÔNG shared keypair / cookie domain)
- D-V3-Phase3-D — JWKS cache in-process LRU hub con (KHÔNG Redis cho publish layer)
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

from app.auth.jwks import (
    JWKSet,
    _derive_kid,
    _int_to_base64url,
    load_public_key_as_jwk,
    publish_jwks,
)

# Resolve api/keys/public.pem relative tới repo root (cwd = api/ khi pytest run).
_PUBLIC_KEY_PATH = Path("keys/public.pem")


@pytest.fixture
def public_key_path() -> Path:
    """Path tới M2 public.pem (api/keys/public.pem)."""
    if not _PUBLIC_KEY_PATH.exists():
        pytest.skip(
            "api/keys/public.pem không tồn tại — chạy 'make keys' trước"
        )
    return _PUBLIC_KEY_PATH


# ────────────────────────────────────────────────────────────────────
# Task 1 — Publish layer (jwks.py module)
# ────────────────────────────────────────────────────────────────────


def test_load_public_key_as_jwk_shape_rsa_256(public_key_path: Path) -> None:
    """JWK trả về có đúng 6 key RFC 7517: kty/kid/use/alg/n/e + value cố định."""
    jwk = load_public_key_as_jwk(public_key_path, kid="test")
    assert set(jwk.keys()) == {"kty", "kid", "use", "alg", "n", "e"}
    assert jwk["kty"] == "RSA"
    assert jwk["kid"] == "test"
    assert jwk["use"] == "sig"
    assert jwk["alg"] == "RS256"
    # 2048-bit RSA modulus encode base64url ≥ 256 char (342 typical cho 2048-bit;
    # public.pem M2 dùng 4096-bit nên modulus n sẽ ≥ 683 char).
    assert len(jwk["n"]) >= 256
    # Exponent mặc định OpenSSL = 65537 → "AQAB" (3 byte base64url).
    assert jwk["e"] == "AQAB"


def test_load_public_key_as_jwk_auto_kid(public_key_path: Path) -> None:
    """Không truyền kid → auto-derive deterministic SHA-256 8-byte prefix."""
    jwk1 = load_public_key_as_jwk(public_key_path)
    jwk2 = load_public_key_as_jwk(public_key_path)
    assert jwk1["kid"] == jwk2["kid"]  # deterministic
    # base64url 8 byte unpadded = 11 char.
    assert len(jwk1["kid"]) == 11


def test_jwks_keys_shape_rfc_7517(public_key_path: Path) -> None:
    """publish_jwks() trả {"keys": [<single JWK>]} — RFC 7517 JWK Set."""
    jwks: JWKSet = publish_jwks(public_key_path)
    assert "keys" in jwks
    assert isinstance(jwks["keys"], list)
    assert len(jwks["keys"]) == 1  # single-key strategy v3.0-a
    jwk = jwks["keys"][0]
    assert jwk["kty"] == "RSA"
    assert jwk["alg"] == "RS256"


def test_derive_kid_deterministic_sha256_8byte() -> None:
    """Cùng PEM bytes → cùng kid; 2 PEM khác → kid khác."""
    pem_a = b"-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----\n"
    pem_b = b"-----BEGIN PUBLIC KEY-----\nBBBB\n-----END PUBLIC KEY-----\n"
    kid_a1 = _derive_kid(pem_a)
    kid_a2 = _derive_kid(pem_a)
    kid_b = _derive_kid(pem_b)
    assert kid_a1 == kid_a2
    assert kid_a1 != kid_b
    # Verify SHA-256 first 8 byte = kid pre-base64url.
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(pem_a).digest()[:8]
    ).rstrip(b"=").decode("ascii")
    assert kid_a1 == expected
    assert len(kid_a1) == 11


def test_int_to_base64url_no_padding() -> None:
    """RSA exponent 65537 → 'AQAB' (RFC 7518 Section 6.3.1 example)."""
    assert _int_to_base64url(65537) == "AQAB"
    # Verify 256 = 2 byte ([0x01,0x00]) → "AQA" (no padding).
    assert _int_to_base64url(256) == "AQA"


def test_load_public_key_rejects_non_rsa(tmp_path: Path) -> None:
    """EC public key PEM → ValueError 'không phải RSA'."""
    # Sinh EC key tạm (cryptography stdlib) để verify reject.
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric import ec

    ec_priv = ec.generate_private_key(ec.SECP256R1())
    ec_pub = ec_priv.public_key()
    ec_pem = ec_pub.public_bytes(
        encoding=ser.Encoding.PEM,
        format=ser.PublicFormat.SubjectPublicKeyInfo,
    )
    ec_path = tmp_path / "ec_pub.pem"
    ec_path.write_bytes(ec_pem)

    with pytest.raises(ValueError, match="không phải RSA"):
        load_public_key_as_jwk(ec_path)


def test_load_public_key_rejects_missing_file(tmp_path: Path) -> None:
    """File không tồn tại → OSError (caller log + return 503)."""
    missing = tmp_path / "nonexistent.pem"
    with pytest.raises(OSError):
        load_public_key_as_jwk(missing)


# ────────────────────────────────────────────────────────────────────
# Task 2 — Mount endpoint conditional central
# ────────────────────────────────────────────────────────────────────


def _setup_env(monkeypatch: pytest.MonkeyPatch, hub_name: str) -> None:
    """Boot env cho create_app() — pattern Phase 2 Plan 02-01.

    Plan 03-02 Task 1 thêm validator hub con required CENTRAL_JWKS_URL —
    auto-set cho hub con để boot Settings PASS (regression update).
    Plan 03-04 Task 1 thêm validator hub con required CENTRAL_URL — auto-set
    cùng pattern.
    """
    if hub_name == "central":
        db = "medinet_central"
    else:
        db = f"medinet_hub_{hub_name}"
    monkeypatch.setenv("HUB_NAME", hub_name)
    monkeypatch.setenv(
        "DATABASE_URL", f"postgresql+asyncpg://u:p@localhost:5432/{db}"
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")
    if hub_name != "central":
        monkeypatch.setenv(
            "CENTRAL_JWKS_URL",
            "http://python-api-central:8080/.well-known/jwks.json",
        )
        # Plan 03-04 — hub con required CENTRAL_URL
        monkeypatch.setenv("CENTRAL_URL", "http://python-api-central:8080")
        # Plan 04-02 — hub con required HUB_ID + CENTRAL_SYNC_DSN
        monkeypatch.setenv("HUB_ID", "12345678-1234-1234-1234-123456789012")
        monkeypatch.setenv(
            "CENTRAL_SYNC_DSN",
            "postgresql+asyncpg://sync_user:pwd@postgres:5432/medinet_central",
        )
    from app.config import get_settings

    get_settings.cache_clear()


def test_jwks_endpoint_mount_central_only(
    monkeypatch: pytest.MonkeyPatch, public_key_path: Path
) -> None:
    """HUB_NAME=central → /.well-known/jwks.json mount; hub con → strip 404."""
    # Đảm bảo cwd có keys/public.pem (CI ép pytest run từ api/).
    _ = public_key_path  # consume fixture skip guard

    from fastapi.testclient import TestClient

    # ── Central — endpoint mount, trả JWK Set ────────────────────────
    _setup_env(monkeypatch, "central")
    # Re-import create_app sau khi env set (module-level đã import 1 lần ở
    # top-of-file Phase 2 test, nhưng create_app() factory đọc settings runtime).
    from app.main import create_app

    app_central = create_app()
    # KHÔNG dùng `with TestClient(...)` — context manager trigger lifespan
    # startup (asyncpg pool + redis + cocoindex), test này chỉ cần routing.
    # Lifespan startup KHÔNG cần ở route registration check.
    client_central = TestClient(app_central)
    resp = client_central.get("/.well-known/jwks.json")
    assert resp.status_code == 200, (
        f"Central phải mount JWKS endpoint, got {resp.status_code}"
    )
    body = resp.json()
    assert "keys" in body
    assert len(body["keys"]) == 1
    assert body["keys"][0]["kty"] == "RSA"
    assert body["keys"][0]["alg"] == "RS256"
    assert body["keys"][0]["use"] == "sig"
    # Cache header verify
    assert "max-age=3600" in resp.headers.get("cache-control", "")

    # ── Hub yte — endpoint strip → 404 envelope ─────────────────────
    _setup_env(monkeypatch, "yte")
    app_yte = create_app()
    client_yte = TestClient(app_yte)
    resp = client_yte.get("/.well-known/jwks.json")
    assert resp.status_code == 404, (
        f"Hub con phải strip JWKS endpoint, got {resp.status_code}"
    )
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_settings_central_jwks_url_default_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings.central_jwks_url default None ở central (Plan 03-01 ship).

    Plan 03-02 đã thêm @model_validator enforce hub con required (fail-loud
    boot nếu thiếu) — test verify CENTRAL hub vẫn default None OK. Hub con
    case test riêng ở test_config_jwks.py::test_hub_con_requires_central_jwks_url.
    """
    _setup_env(monkeypatch, "central")
    from app.config import get_settings

    settings_central = get_settings()
    assert settings_central.central_jwks_url is None

    # Hub con được set CENTRAL_JWKS_URL ở _setup_env (Plan 03-02 regression update).
    _setup_env(monkeypatch, "yte")
    settings_yte = get_settings()
    assert settings_yte.central_jwks_url == (
        "http://python-api-central:8080/.well-known/jwks.json"
    )
