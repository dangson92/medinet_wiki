"""JWKS publish + cache layer — Plan 03-01 (publish) + Plan 03-02 (cache).

Plan 03-01 (SSO-01 part 1, D-V3-Phase3-A) expose `publish_jwks()` cho central
JWKS endpoint RFC 7517:
    GET /.well-known/jwks.json -> {"keys": [{"kty":"RSA","kid":"...",...}]}

Plan 03-02 (SSO-01 part 2, D-V3-Phase3-B/D) thêm `JWKSCache` class cho hub con
verify JWT: in-process LRU + asyncio refresh task TTL 1h + 24h hard limit
(503 JWKS_STALE envelope nếu cache > limit — R-V3-5 fail-loud delayed).

Stack: `cryptography` + `httpx` (M2 baseline) — KHÔNG dep mới `jwcrypto`.

Locked decisions:
    D-V3-Phase3-A — JWKS endpoint (KHÔNG shared keypair / cookie domain)
    D-V3-Phase3-B — Boot fail-loud + runtime fail-quiet + 24h hard limit
    D-V3-Phase3-D — In-process cache hub con (KHÔNG Redis)

REQ traceability: SSO-01 (Plan 03-01 publish + Plan 03-02 cache)
Risk mitigation: R-V3-5 (HA — central rotate key -> hub con auto-detect ở
next TTL refresh thông qua kid mismatch).
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


# ────────────────────────────────────────────────────────────────────────────
# Plan 03-02 — JWKSCache class + lifecycle (SSO-01 part 2, D-V3-Phase3-B/D)
# ────────────────────────────────────────────────────────────────────────────

import asyncio  # noqa: E402 — module-level import sau Plan 03-01 publish layer
import logging  # noqa: E402
import time  # noqa: E402

import httpx  # noqa: E402

logger = logging.getLogger(__name__)


class JWKSStaleError(Exception):
    """Raise khi cache > max_stale_seconds — caller render 503 JWKS_STALE envelope.

    R-V3-5 fail-loud delayed mitigation: cache local 1h TTL + background refresh
    fail-quiet, NHƯNG nếu sau 24h KHÔNG refresh thành công → mọi JWT verify trả
    503 (KHÔNG accept stale key vĩnh viễn).
    """


class JWKSKidNotFoundError(Exception):
    """Raise khi JWT header kid không match key nào trong cache.

    Cause: (a) central rotate keypair (Plan 03-01 _derive_kid SHA-256 PEM đổi
    kid tự nhiên) + hub con chưa refresh (defer 1h TTL); (b) attacker forge
    JWT với kid bịa; (c) JWT M2 cũ phát hành trước Plan 03-02 KHÔNG có kid.
    """


def _base64url_to_int(data: str) -> int:
    """Inverse `_int_to_base64url` — JWK n/e base64url → big-int (RFC 7518 §6.3.1).

    base64.urlsafe_b64decode yêu cầu padding %4 — pad lại để decode OK.
    """
    pad = "=" * (-len(data) % 4)
    raw = base64.urlsafe_b64decode(data + pad)
    return int.from_bytes(raw, byteorder="big")


def jwk_to_public_key(jwk: JWK) -> RSAPublicKey:
    """JWK dict RFC 7517 → cryptography RSAPublicKey object cho pyjwt.decode().

    Reverse `load_public_key_as_jwk` — verify roundtrip property qua test
    (sign JWT bằng private.pem → verify bằng pub key reconstruct từ JWK).
    """
    if jwk["kty"] != "RSA":
        raise ValueError(f"JWK kty={jwk['kty']!r}, chỉ support RSA (RS256).")
    n = _base64url_to_int(jwk["n"])
    e = _base64url_to_int(jwk["e"])
    return RSAPublicNumbers(e=e, n=n).public_key()


class JWKSCache:
    """In-process LRU JWKS cache cho hub con verify JWT (D-V3-Phase3-D).

    Lifecycle:
        1. `fetch_initial()` — blocking httpx.get timeout 5s → exception →
           boot fail-loud (lifespan startup raise → process exit 1).
        2. `start_refresh_task()` — spawn asyncio task chạy `_refresh_loop()`
           mỗi `refresh_interval` sec, fail-quiet (log warning + giữ cached).
        3. `get_public_key(kid)` — verify hot path; raise `JWKSStaleError`
           nếu cache > `max_stale_seconds` (R-V3-5 fail-loud delayed).
        4. `stop_refresh_task()` — graceful shutdown (cancel asyncio task).

    Threat model:
        - T-03-02-02 (DoS) — httpx timeout 5s chống stuck lifespan
        - T-03-02-03 (Tampering) — kid mismatch khi key rotation → caller
          chọn re-fetch hoặc reject; cache TTL hard limit minimize fake window
        - T-03-02-08 (DoS) — refresh loop wrap try/except global tránh task
          die câm + 24h hard limit guarantee fail-loud delayed nếu task chết

    Decision traceability: D-V3-Phase3-B (lifecycle) + D-V3-Phase3-D (storage).
    """

    def __init__(
        self,
        jwks_url: str,
        *,
        refresh_interval: int = 3600,
        max_stale_seconds: int = 86400,
        timeout: float = 5.0,
    ) -> None:
        self._jwks_url = jwks_url
        self._refresh_interval = refresh_interval
        self._max_stale_seconds = max_stale_seconds
        self._timeout = timeout
        self._keys_by_kid: dict[str, RSAPublicKey] = {}
        self._last_refresh_ts: float = 0.0
        self._refresh_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def fetch_initial(self) -> None:
        """Blocking fetch — raise nếu fail (boot fail-loud D-V3-Phase3-B)."""
        try:
            await self._fetch_and_cache()
        except Exception as e:
            logger.critical(
                "jwks_fetch_initial_failed: url=%s error=%s — boot abort",
                self._jwks_url,
                e,
            )
            raise

    async def refresh(self) -> None:
        """Internal refresh — fail-quiet (log warning + giữ cached value).

        D-V3-Phase3-B runtime fail-quiet: central JWKS endpoint blip 5 phút
        KHÔNG nên kill hub con request. Cache cũ vẫn pass JWT verify cho tới
        khi 24h hard limit (`max_stale_seconds`) → JWKSStaleError 503.
        """
        try:
            await self._fetch_and_cache()
        except Exception as e:
            logger.warning(
                "jwks_refresh_failed: url=%s error=%s — giữ cached value",
                self._jwks_url,
                e,
            )
            # KHÔNG raise — fail-quiet runtime D-V3-Phase3-B

    async def _fetch_and_cache(self) -> None:
        """Fetch JWKS từ URL + populate cache. Internal — caller wrap try/except."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(self._jwks_url)
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, dict) or "keys" not in data:
            raise ValueError(
                f"JWKS response thiếu 'keys' list (got: {type(data).__name__})"
            )
        keys = data["keys"]
        if not isinstance(keys, list) or not keys:
            raise ValueError(
                f"JWKS response 'keys' phải là non-empty list (got: {keys!r})"
            )
        new_keys: dict[str, RSAPublicKey] = {}
        for jwk_dict in keys:
            if not isinstance(jwk_dict, dict) or "kid" not in jwk_dict:
                logger.warning("jwks_skip_invalid_jwk: %r", jwk_dict)
                continue
            try:
                pub_key = jwk_to_public_key(jwk_dict)  # type: ignore[arg-type]
            except (ValueError, KeyError) as e:
                logger.warning(
                    "jwks_skip_unparseable_key: kid=%s error=%s",
                    jwk_dict.get("kid"),
                    e,
                )
                continue
            new_keys[jwk_dict["kid"]] = pub_key
        if not new_keys:
            raise ValueError("JWKS response không có key hợp lệ sau parse")
        async with self._lock:
            self._keys_by_kid = new_keys
            self._last_refresh_ts = time.time()
        logger.info(
            "jwks_cache_updated: kids=%s last_refresh_ts=%.0f",
            sorted(new_keys.keys()),
            self._last_refresh_ts,
        )

    def is_stale(self) -> bool:
        """True nếu cache > max_stale_seconds — caller raise 503 JWKS_STALE."""
        if self._last_refresh_ts == 0.0:
            return True  # chưa fetch_initial → stale by definition
        return (time.time() - self._last_refresh_ts) > self._max_stale_seconds

    def get_public_key(self, kid: str) -> RSAPublicKey:
        """Verify hot path — raise JWKSStaleError nếu cache quá hạn 24h.

        Caller (get_current_user dependency Task 4) catch:
        - JWKSStaleError → 503 JWKS_STALE envelope
        - JWKSKidNotFoundError → 401 INVALID_TOKEN (kid mismatch — operator
          rotate key + hub con chưa refresh, hoặc attacker forge kid bịa)
        """
        if self.is_stale():
            raise JWKSStaleError(
                f"JWKS cache quá hạn {self._max_stale_seconds}s "
                f"({time.time() - self._last_refresh_ts:.0f}s since last refresh)"
            )
        if kid not in self._keys_by_kid:
            raise JWKSKidNotFoundError(
                f"kid={kid!r} không trong JWKS cache "
                f"(available: {sorted(self._keys_by_kid.keys())})"
            )
        return self._keys_by_kid[kid]

    def start_refresh_task(self) -> None:
        """Spawn asyncio background task refresh mỗi refresh_interval sec."""
        if self._refresh_task is not None and not self._refresh_task.done():
            logger.warning("jwks_refresh_task_already_running — skip")
            return
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info(
            "jwks_refresh_task_started: interval=%ds", self._refresh_interval
        )

    async def _refresh_loop(self) -> None:
        """Asyncio task — sleep refresh_interval + refresh, lặp vô tận.

        Defensive bao try/except global ngăn task chết câm khi exception
        ngoài _fetch_and_cache (đã log). 24h hard limit guarantee fail-loud
        delayed nếu task chết (T-03-02-08 mitigation).
        """
        while True:
            try:
                await asyncio.sleep(self._refresh_interval)
                await self.refresh()
            except asyncio.CancelledError:
                logger.info("jwks_refresh_loop_cancelled")
                raise
            except Exception as e:  # noqa: BLE001 — defensive task survival
                logger.error("jwks_refresh_loop_unexpected: %s", e)

    async def stop_refresh_task(self) -> None:
        """Graceful shutdown (cancel asyncio task)."""
        if self._refresh_task is None:
            return
        self._refresh_task.cancel()
        try:
            await self._refresh_task
        except asyncio.CancelledError:
            pass
        self._refresh_task = None
        logger.info("jwks_refresh_task_stopped")


__all__ = [
    "JWK",
    "JWKSCache",
    "JWKSKidNotFoundError",
    "JWKSStaleError",
    "JWKSet",
    "jwk_to_public_key",
    "load_public_key_as_jwk",
    "publish_jwks",
]
