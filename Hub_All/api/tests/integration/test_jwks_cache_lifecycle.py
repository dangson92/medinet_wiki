"""Phase 3 SSO-01 — Integration test JWKSCache lifecycle (Plan 03-02 Task 5).

Pragmatic scope:
- Spawn central app via TestClient → fetch /.well-known/jwks.json → original_jwks.
- Mock httpx.get cho JWKSCache (KHÔNG spawn 2 process subprocess) → assert
  cache fetch_initial OK + get_public_key OK.
- Simulate key rotation: swap mock httpx response → cache.refresh() → kid mới
  → get_public_key(old_kid) raise JWKSKidNotFoundError + new kid OK.

Full multi-process E2E rotate keypair runtime defer Plan 03-05 closeout smoke
(chạy thật 2 service compose central + yte với docker compose up).

Decision traceability:
- D-V3-Phase3-A — JWKS endpoint RFC 7517 (verify Plan 03-01 ship)
- D-V3-Phase3-B — Boot fail-loud + runtime fail-quiet + 24h hard limit
- D-V3-Phase3-D — In-process LRU cache hub con
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def public_key_path() -> Path:
    p = Path("keys/public.pem")
    if not p.exists():
        pytest.skip("api/keys/public.pem missing — run 'make keys'")
    return p


def _mock_httpx_for_response(jwks_response: dict) -> MagicMock:  # type: ignore[type-arg]
    """Helper build mock httpx async client trả JSON cố định cho JWKSCache."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=jwks_response)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)
    return mock_client


@pytest.mark.critical
@pytest.mark.integration
def test_central_jwks_endpoint_serves_real_keypair(
    monkeypatch: pytest.MonkeyPatch, public_key_path: Path
) -> None:
    """End-to-end: central app boot → GET /.well-known/jwks.json → JWK Set chứa
    đúng public key từ api/keys/public.pem (qua publish_jwks Plan 03-01)."""
    from app.auth.jwks import load_public_key_as_jwk

    expected_jwk = load_public_key_as_jwk(public_key_path)
    expected_kid = expected_jwk["kid"]

    # Boot central app
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
    monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    # KHÔNG dùng with TestClient(app) trigger lifespan — chỉ cần routing.
    client = TestClient(app)
    resp = client.get("/.well-known/jwks.json")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["keys"][0]["kid"] == expected_kid
    assert body["keys"][0]["n"] == expected_jwk["n"]
    assert body["keys"][0]["e"] == expected_jwk["e"]


@pytest.mark.critical
@pytest.mark.integration
async def test_jwks_cache_rotate_keypair_detects_new_kid(
    public_key_path: Path, tmp_path: Path
) -> None:
    """Simulate central rotate keypair → hub con refresh detect kid mới.

    Setup: JWKSCache fetch_initial với JWK A (kid_a) → get_public_key(kid_a) OK.
    Then: refresh() với JWK B (kid_b mới) → get_public_key(kid_a) raise
    JWKSKidNotFoundError + get_public_key(kid_b) OK.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.auth.jwks import (
        JWKSCache,
        JWKSKidNotFoundError,
        publish_jwks,
    )

    # Original JWK A (M2 public.pem)
    jwks_a = publish_jwks(public_key_path)
    kid_a = jwks_a["keys"][0]["kid"]

    # Sinh keypair mới ở tmp (B) — simulate central `make keys` rotate
    new_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    new_pub = new_priv.public_key()
    new_pub_pem = new_pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    new_pub_path = tmp_path / "public_b.pem"
    new_pub_path.write_bytes(new_pub_pem)
    jwks_b = publish_jwks(new_pub_path)
    kid_b = jwks_b["keys"][0]["kid"]
    assert kid_a != kid_b  # rotation phải đổi kid

    # JWKSCache fetch_initial với A
    cache = JWKSCache(jwks_url="http://central/.well-known/jwks.json")

    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_httpx_for_response(jwks_a)  # type: ignore[arg-type]
        await cache.fetch_initial()
    # get_public_key(kid_a) OK
    pub_a = cache.get_public_key(kid_a)
    assert pub_a is not None

    # Refresh với B (rotate)
    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_httpx_for_response(jwks_b)  # type: ignore[arg-type]
        await cache.refresh()

    # Sau refresh: kid_a KHÔNG còn, kid_b mới
    with pytest.raises(JWKSKidNotFoundError):
        cache.get_public_key(kid_a)
    pub_b = cache.get_public_key(kid_b)
    assert pub_b is not None


@pytest.mark.critical
@pytest.mark.integration
async def test_jwks_cache_background_refresh_task_lifecycle(
    public_key_path: Path,
) -> None:
    """start_refresh_task spawn asyncio task → stop_refresh_task cancel sạch."""
    from app.auth.jwks import JWKSCache, publish_jwks

    jwks = publish_jwks(public_key_path)
    cache = JWKSCache(
        jwks_url="http://central/.well-known/jwks.json",
        refresh_interval=60,
    )

    with patch("app.auth.jwks.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = _mock_httpx_for_response(jwks)  # type: ignore[arg-type]
        await cache.fetch_initial()
        cache.start_refresh_task()
        assert cache._refresh_task is not None
        assert not cache._refresh_task.done()

    await cache.stop_refresh_task()
    assert cache._refresh_task is None
