"""JWKS publish layer — Plan 03-01 (SSO-01 part 1, D-V3-Phase3-A).

Module expose `publish_jwks()` cho central JWKS endpoint RFC 7517:
    GET /.well-known/jwks.json -> {"keys": [{"kty":"RSA","kid":"...",...}]}

Stack: `cryptography` (M2 baseline qua PyJWT[crypto]) — KHÔNG thêm dep mới
(KHÔNG dùng `jwcrypto` — analysis cho thấy 10 LOC manual đủ; xem 03-CONTEXT.md
Claude's Discretion + Plan 03-01 notes).

Plan 03-02 sẽ thêm `JWKSCache` class cùng module này — publish + cache cùng
concern JWKS lifecycle. Phase 7 MCP service tái sử dụng cache layer.

Locked decisions:
    D-V3-Phase3-A — JWKS endpoint (KHÔNG shared keypair / cookie domain)
    D-V3-Phase3-D — In-process cache hub con (KHÔNG Redis)

REQ traceability: SSO-01 (Plan 03-01)
Risk mitigation: R-V3-5 (HA — central rotate key -> hub con auto-detect ở
next TTL refresh thông qua kid mismatch — Plan 03-02 ship cache layer).
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import TypedDict

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPublicKey,
    RSAPublicNumbers,
)

# kid (Key ID) length sau base64url 8-byte SHA-256 prefix = 11 char unpadded.
# Cố định tránh nhầm kid với UUID/jti (32+ char).
_KID_BYTE_LENGTH = 8


class JWK(TypedDict):
    """RFC 7517 JWK shape cho RS256 sig key."""

    kty: str   # "RSA"
    kid: str   # base64url SHA-256 8-byte prefix
    use: str   # "sig"
    alg: str   # "RS256"
    n: str     # modulus base64url unpadded
    e: str     # exponent base64url unpadded (65537 = "AQAB")


class JWKSet(TypedDict):
    """RFC 7517 JWK Set shape."""

    keys: list[JWK]


def _int_to_base64url(n: int) -> str:
    """Big-int -> base64url unpadded ASCII (RFC 7518 Section 6.3.1).

    JWK n/e fields dùng base64url-encoded big-endian unsigned int bytes.
    `n` (modulus 2048-bit) = 256 byte -> 342 char base64url unpadded.
    `e` (exponent 65537) = 3 byte -> "AQAB" (4 char unpadded).

    Edge case n=0: bit_length=0 -> byte_length=0 -> b"" -> "" (acceptable —
    KHÔNG dùng cho RSA params thực).
    """
    byte_length = (n.bit_length() + 7) // 8
    data = n.to_bytes(byte_length, byteorder="big")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _derive_kid(pem_bytes: bytes) -> str:
    """kid = base64url của 8 byte đầu SHA-256 PEM (deterministic).

    Rotation: PEM mới -> kid mới tự nhiên. Hub con cache phát hiện kid
    mismatch khi verify JWT -> trigger re-fetch JWKS (Plan 03-02).
    """
    digest = hashlib.sha256(pem_bytes).digest()
    prefix = digest[:_KID_BYTE_LENGTH]
    return base64.urlsafe_b64encode(prefix).rstrip(b"=").decode("ascii")


def load_public_key_as_jwk(pem_path: Path, kid: str | None = None) -> JWK:
    """Đọc PEM public key -> JWK dict RFC 7517.

    Args:
        pem_path: đường dẫn tới file PEM (`-----BEGIN PUBLIC KEY-----`).
        kid: nếu None, auto-derive từ SHA-256 PEM bytes (deterministic).

    Raises:
        OSError: file không tồn tại / không đọc được.
        ValueError: PEM parse fail HOẶC key không phải RSA.
    """
    pem_bytes = pem_path.read_bytes()
    pub_key = serialization.load_pem_public_key(pem_bytes)
    if not isinstance(pub_key, RSAPublicKey):
        raise ValueError(
            f"Public key tại {pem_path!s} không phải RSA "
            f"(type={type(pub_key).__name__}). JWKS endpoint yêu cầu RS256 — "
            f"chạy 'make keys' để sinh lại RSA keypair PKCS#8."
        )
    numbers: RSAPublicNumbers = pub_key.public_numbers()
    if kid is None:
        kid = _derive_kid(pem_bytes)
    return JWK(
        kty="RSA",
        kid=kid,
        use="sig",
        alg="RS256",
        n=_int_to_base64url(numbers.n),
        e=_int_to_base64url(numbers.e),
    )


def publish_jwks(public_key_path: Path) -> JWKSet:
    """Build JWK Set RFC 7517 từ central public key.

    Single-key strategy ở v3.0-a (1 active key + manual rotation — `make keys`
    overwrite -> restart central). Multi-key rotation (overlap window) defer
    Phase 7 MCP service.

    Args:
        public_key_path: settings.jwt_public_key_path (Path).

    Returns:
        {"keys": [<single JWK>]} — JSON-serializable dict.

    Raises:
        OSError / ValueError: nếu PEM thiếu hoặc không phải RSA — central
        không thể boot mà thiếu keypair (M2 carry forward — `make keys` step
        bắt buộc Phase 1).
    """
    jwk = load_public_key_as_jwk(public_key_path)
    return JWKSet(keys=[jwk])


__all__ = ["JWK", "JWKSet", "load_public_key_as_jwk", "publish_jwks"]
