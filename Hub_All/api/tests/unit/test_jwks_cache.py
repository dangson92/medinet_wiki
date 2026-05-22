"""Phase 3 SSO-01 — Unit test JWKSCache lifecycle (Plan 03-02 Task 2).

Verify:
- fetch_initial success + timeout/500/invalid shape raise (boot fail-loud D-V3-Phase3-B)
- get_public_key + kid not found + 24h hard limit stale (R-V3-5)
- refresh fail-quiet (giữ cached — runtime D-V3-Phase3-B)
- jwk_to_public_key roundtrip với publish_jwks (sign/verify property qua JWT)
- _base64url_to_int inverse property (RFC 7518)

Decision traceability:
- D-V3-Phase3-B — boot fail-loud + runtime fail-quiet + 24h hard limit
- D-V3-Phase3-D — in-process LRU cache (KHÔNG Redis)
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.auth.jwks import (
    JWKSCache,
    JWKSKidNotFoundError,
    JWKSStaleError,
    _base64url_to_int,
    _int_to_base64url,
    jwk_to_public_key,
    publish_jwks,
)


@pytest.fixture
def public_key_path() -> Path:
    p = Path("keys/public.pem")
    if not p.exists():
        pytest.skip("api/keys/public.pem missing — run 'make keys'")
    return p


@pytest.fixture
def valid_jwks_response(public_key_path: Path) -> dict:  # type: ignore[type-arg]
    """Build JWKS response từ M2 public.pem để mock httpx trả về."""
    return publish_jwks(public_key_path)  # type: ignore[return-value]


def _make_mock_httpx_get(
    response_data: dict,  # type: ignore[type-arg]
    status_code: int = 200,
) -> MagicMock:
    """Helper build mock httpx async client trả JSON cố định."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json = MagicMock(return_value=response_data)
    if status_code >= 400:
        mock_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "mock 500",
                request=MagicMock(),
                response=mock_resp,
            )
        )
    else:
        mock_resp.raise_for_status = MagicMock()
    mock_get = AsyncMock(return_value=mock_resp)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = mock_get
    return mock_client


async def test_jwks_cache_fetch_initial_success(
    valid_jwks_response: dict,  # type: ignore[type-arg]
) -> None:
    """Happy path — fetch_initial populate cache + get_public_key trả RSAPublicKey."""
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

    cache = JWKSCache(jwks_url="http://test/jwks.json")
    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _make_mock_httpx_get(valid_jwks_response)
        await cache.fetch_initial()
    kid = valid_jwks_response["keys"][0]["kid"]
    public_key = cache.get_public_key(kid)
    assert isinstance(public_key, RSAPublicKey)


async def test_jwks_cache_fetch_initial_timeout_raises() -> None:
    """httpx.TimeoutException → fetch_initial raise → boot fail-loud."""
    cache = JWKSCache(jwks_url="http://test/jwks.json", timeout=0.1)
    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("mock timeout")
        )
        mock_client_cls.return_value = mock_client
        with pytest.raises(httpx.TimeoutException):
            await cache.fetch_initial()


async def test_jwks_cache_fetch_initial_500_raises(
    valid_jwks_response: dict,  # type: ignore[type-arg]
) -> None:
    """httpx 500 → raise_for_status raise → fail-loud."""
    cache = JWKSCache(jwks_url="http://test/jwks.json")
    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _make_mock_httpx_get(
            valid_jwks_response, status_code=500
        )
        with pytest.raises(httpx.HTTPStatusError):
            await cache.fetch_initial()


async def test_jwks_cache_fetch_initial_invalid_shape_raises() -> None:
    """JWKS response {\"invalid\": \"shape\"} → ValueError."""
    cache = JWKSCache(jwks_url="http://test/jwks.json")
    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _make_mock_httpx_get({"invalid": "shape"})
        with pytest.raises(ValueError, match="'keys' list"):
            await cache.fetch_initial()


async def test_jwks_cache_get_public_key_kid_not_found(
    valid_jwks_response: dict,  # type: ignore[type-arg]
) -> None:
    """kid không trong cache → JWKSKidNotFoundError."""
    cache = JWKSCache(jwks_url="http://test/jwks.json")
    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _make_mock_httpx_get(valid_jwks_response)
        await cache.fetch_initial()
    with pytest.raises(JWKSKidNotFoundError, match="không trong JWKS cache"):
        cache.get_public_key("nonexistent_kid_xyz")


async def test_jwks_cache_24h_hard_limit_raises_stale(
    valid_jwks_response: dict,  # type: ignore[type-arg]
) -> None:
    """Cache > max_stale_seconds → JWKSStaleError ở get_public_key (R-V3-5)."""
    cache = JWKSCache(
        jwks_url="http://test/jwks.json",
        max_stale_seconds=1,  # 1s cho test nhanh
    )
    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _make_mock_httpx_get(valid_jwks_response)
        await cache.fetch_initial()
    kid = valid_jwks_response["keys"][0]["kid"]
    # Manual rewind last_refresh_ts để mô phỏng stale
    cache._last_refresh_ts = time.time() - 2
    assert cache.is_stale()
    with pytest.raises(JWKSStaleError, match="quá hạn"):
        cache.get_public_key(kid)


async def test_jwks_cache_refresh_fail_quiet_keeps_old_value(
    valid_jwks_response: dict,  # type: ignore[type-arg]
) -> None:
    """refresh() fail → log warning + giữ cached + KHÔNG raise (runtime fail-quiet)."""
    cache = JWKSCache(jwks_url="http://test/jwks.json")
    # fetch_initial OK
    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _make_mock_httpx_get(valid_jwks_response)
        await cache.fetch_initial()
    kid = valid_jwks_response["keys"][0]["kid"]
    cached_key = cache.get_public_key(kid)

    # refresh fail
    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("mock timeout refresh")
        )
        mock_client_cls.return_value = mock_client
        await cache.refresh()  # KHÔNG raise — fail-quiet

    # Cached value vẫn còn
    cached_key_after = cache.get_public_key(kid)
    assert cached_key is cached_key_after


def test_jwk_to_public_key_roundtrip(public_key_path: Path) -> None:
    """publish_jwks → jwk_to_public_key roundtrip + sign/verify property qua JWT."""
    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

    jwks = publish_jwks(public_key_path)
    jwk = jwks["keys"][0]
    pub_key = jwk_to_public_key(jwk)
    assert isinstance(pub_key, RSAPublicKey)

    # Sign JWT bằng private key + verify bằng public_key reconstruct
    private_pem = Path("keys/private.pem").read_bytes()
    token = pyjwt.encode(
        {"sub": "test", "iss": "medinet-wiki"},
        private_pem,
        algorithm="RS256",
    )
    decoded = pyjwt.decode(
        token,
        pub_key,
        algorithms=["RS256"],
        issuer="medinet-wiki",
    )
    assert decoded["sub"] == "test"


def test_base64url_to_int_roundtrip() -> None:
    """_int_to_base64url ↔ _base64url_to_int inverse property."""
    assert _base64url_to_int("AQAB") == 65537
    assert _base64url_to_int(_int_to_base64url(65537)) == 65537
    # Test large modulus 2048-bit
    assert _base64url_to_int(_int_to_base64url(2**2048 - 1)) == 2**2048 - 1
    # Inverse direction
    assert _int_to_base64url(_base64url_to_int("AQA")) == "AQA"
