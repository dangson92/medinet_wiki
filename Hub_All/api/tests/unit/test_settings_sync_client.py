"""Phase 6 Plan 06-02 Wave 2 Task 1 — Unit test 3 HTTP client class.

Per PLAN <behavior> 10 test (4 RagConfigClient + 3 HubRegistryClient + 3 ApiKeyVerifyClient):

RagConfigClient:
- fetch_initial happy + httpx timeout → SettingsUnavailableError
- get() cache hit (Redis return bytes) skip httpx + emit HIT counter
- get() cache miss + central 500 + Redis empty → SettingsUnavailableError

HubRegistryClient:
- fetch_initial happy + 401 unauthorized → SettingsUnavailableError
- list_hubs() cache hit returns parsed list

ApiKeyVerifyClient:
- verify cache miss + 200 valid → setex + result=valid
- verify cache miss + 401 invalid → return None + result=invalid (KHÔNG setex)
- verify cache hit (Redis bytes) → skip httpx + result=cached

Pattern carry forward:
- `test_jwks_cache.py` (Plan 03-02) mock httpx fixture `_make_mock_httpx_get`.
- `AsyncMock` Redis fixture với .get() / .setex() async methods.

Decision traceability:
- D-V3-Phase6-A — HTTP pull + Redis cache TTL hybrid.
- D-V3-Phase6-B — TTL 60s / 300s / 60s per category.
- D-V3-Phase6-D — X-Internal-Auth shared secret 32 char min header.
- T-06-02-01..06 — STRIDE coverage (Info Disclosure + DoS + Tampering + Spoofing).
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def _make_mock_httpx_get(
    response_data: Any,
    status_code: int = 200,
) -> MagicMock:
    """Mock httpx async client GET trả JSON cố định.

    Pattern reuse từ `test_jwks_cache.py` (Plan 03-02).
    """
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json = MagicMock(return_value=response_data)
    if status_code >= 400:
        mock_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                f"mock {status_code}",
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


def _make_mock_httpx_post(
    response_data: Any,
    status_code: int = 200,
) -> MagicMock:
    """Mock httpx async client POST trả JSON cố định.

    KHÁC GET: ApiKeyVerifyClient KHÔNG `raise_for_status` (check 401/200 thủ công
    để decide cache positive vs return None).
    """
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json = MagicMock(return_value=response_data)
    mock_resp.raise_for_status = MagicMock()
    mock_post = AsyncMock(return_value=mock_resp)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = mock_post
    return mock_client


def _make_mock_redis(get_value: Any = None) -> MagicMock:
    """Mock Redis async — .get() return bytes/None + .setex() async no-op."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=get_value)
    redis.setex = AsyncMock(return_value=True)
    return redis


# ────────────────────────────────────────────────────────────────────
# RagConfigClient (4 test)
# ────────────────────────────────────────────────────────────────────


async def test_rag_config_client_fetch_initial_happy_path() -> None:
    """fetch_initial happy — mock httpx GET 200 + JSON → Redis setex called."""
    from app.settings_sync.client import RagConfigClient

    payload = {"provider": "openai", "model": "gpt-4", "dimensions": 1536}
    redis = _make_mock_redis()
    client = RagConfigClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
        ttl=60,
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_mock_httpx_get(payload)
        await client.fetch_initial()
    # Redis setex called với key + TTL + JSON
    redis.setex.assert_called_once()
    args = redis.setex.call_args.args
    assert args[0] == "settings:rag_config:yte"
    assert args[1] == 60
    assert json.loads(args[2]) == payload


async def test_rag_config_client_fetch_initial_timeout_raises_settings_unavailable() -> None:
    """fetch_initial httpx timeout → SettingsUnavailableError (boot fail-loud)."""
    from app.settings_sync.client import RagConfigClient, SettingsUnavailableError

    redis = _make_mock_redis()
    client = RagConfigClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        mock_inner = MagicMock()
        mock_inner.__aenter__ = AsyncMock(return_value=mock_inner)
        mock_inner.__aexit__ = AsyncMock(return_value=None)
        mock_inner.get = AsyncMock(
            side_effect=httpx.TimeoutException("mock timeout")
        )
        mock_cls.return_value = mock_inner
        with pytest.raises(SettingsUnavailableError):
            await client.fetch_initial()


async def test_rag_config_client_get_cache_hit_skips_httpx() -> None:
    """get() cache hit — Redis bytes return → KHÔNG httpx call + emit HIT counter."""
    from app.settings_sync.client import RagConfigClient

    cached_payload = {"provider": "openai", "model": "gpt-4"}
    redis = _make_mock_redis(
        get_value=json.dumps(cached_payload).encode("utf-8")
    )
    client = RagConfigClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        result = await client.get()
    # KHÔNG httpx call (mock_cls.return_value chưa từng dùng)
    mock_cls.assert_not_called()
    assert result == cached_payload
    redis.get.assert_called_once_with("settings:rag_config:yte")


async def test_rag_config_client_get_central_500_and_redis_empty_raises() -> None:
    """get() cache miss + central 500 + Redis empty → SettingsUnavailableError envelope."""
    from app.settings_sync.client import RagConfigClient, SettingsUnavailableError

    redis = _make_mock_redis(get_value=None)  # cache miss
    client = RagConfigClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_mock_httpx_get(
            {"detail": "internal error"}, status_code=500
        )
        with pytest.raises(SettingsUnavailableError):
            await client.get()


# ────────────────────────────────────────────────────────────────────
# HubRegistryClient (3 test)
# ────────────────────────────────────────────────────────────────────


async def test_hub_registry_client_fetch_initial_happy_singleton_key() -> None:
    """fetch_initial happy — Redis setex key="settings:hub_registry" singleton TTL 300s."""
    from app.settings_sync.client import HubRegistryClient

    hubs_list = [
        {"id": "uuid-1", "name": "yte", "active": True},
        {"id": "uuid-2", "name": "duoc", "active": True},
        {"id": "uuid-3", "name": "hcns", "active": True},
        {"id": "uuid-4", "name": "central", "active": True},
    ]
    redis = _make_mock_redis()
    client = HubRegistryClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
        internal_auth_secret="test-secret-32-char-min-padding-padding",
        ttl=300,
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_mock_httpx_get(hubs_list)
        await client.fetch_initial()
    redis.setex.assert_called_once()
    args = redis.setex.call_args.args
    assert args[0] == "settings:hub_registry"  # singleton, KHÔNG per-hub
    assert args[1] == 300
    assert json.loads(args[2]) == hubs_list


async def test_hub_registry_client_list_hubs_cache_hit_returns_parsed_list() -> None:
    """list_hubs() cache hit returns parsed list (Redis bytes → JSON decode)."""
    from app.settings_sync.client import HubRegistryClient

    cached_list = [{"id": "u-1", "name": "yte"}, {"id": "u-2", "name": "duoc"}]
    redis = _make_mock_redis(
        get_value=json.dumps(cached_list).encode("utf-8")
    )
    client = HubRegistryClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
        internal_auth_secret="test-secret-32-char-min-padding-padding",
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        result = await client.list_hubs()
    mock_cls.assert_not_called()
    assert result == cached_list


async def test_hub_registry_client_fetch_initial_401_raises_settings_unavailable() -> None:
    """fetch_initial 401 unauthorized → SettingsUnavailableError."""
    from app.settings_sync.client import HubRegistryClient, SettingsUnavailableError

    redis = _make_mock_redis()
    client = HubRegistryClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
        internal_auth_secret="test-secret-32-char-min-padding-padding",
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_mock_httpx_get(
            {"detail": "unauthorized"}, status_code=401
        )
        with pytest.raises(SettingsUnavailableError):
            await client.fetch_initial()


async def test_hub_registry_client_fetch_initial_sends_x_internal_auth_header() -> None:
    """Hot-fix 2026-05-25 — fetch_initial gửi X-Internal-Auth header + endpoint _internal."""
    from app.settings_sync.client import HubRegistryClient

    secret = "hot-fix-secret-2026-05-25-padding-padding"
    redis = _make_mock_redis()
    client = HubRegistryClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="dmd",
        internal_auth_secret=secret,
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        mock_client = _make_mock_httpx_get([])
        mock_cls.return_value = mock_client
        await client.fetch_initial()
    # Verify endpoint path là /api/hubs/_internal (KHÔNG /api/hubs cũ)
    call_args = mock_client.get.call_args
    url = call_args.args[0]
    assert url == "http://central:8080/api/hubs/_internal", (
        f"Hot-fix: endpoint phải là /api/hubs/_internal, got {url!r}"
    )
    # Verify X-Internal-Auth header gửi đúng secret
    headers = call_args.kwargs.get("headers", {})
    assert headers.get("X-Internal-Auth") == secret, (
        f"Hot-fix: header X-Internal-Auth phải = secret, got {headers!r}"
    )


async def test_hub_registry_client_unwraps_envelope_data_field() -> None:
    """Hot-fix 2026-05-25 — defensive unwrap envelope `{success, data: [...]}` shape."""
    from app.settings_sync.client import HubRegistryClient

    hubs_list = [{"id": "u-1", "name": "dmd"}, {"id": "u-2", "name": "tdt"}]
    envelope = {"success": True, "data": hubs_list, "meta": {"total": 2}}
    redis = _make_mock_redis()
    client = HubRegistryClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="dmd",
        internal_auth_secret="test-secret-32-char-min-padding-padding",
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_mock_httpx_get(envelope)
        await client.fetch_initial()
    # Cache phải lưu list (unwrap data field), KHÔNG nguyên envelope dict
    cached = json.loads(redis.setex.call_args.args[2])
    assert cached == hubs_list, (
        f"Hot-fix: phải unwrap envelope.data, got cached={cached!r}"
    )


# ────────────────────────────────────────────────────────────────────
# ApiKeyVerifyClient (3 test)
# ────────────────────────────────────────────────────────────────────


async def test_apikey_verify_client_cache_miss_200_valid_caches_principal() -> None:
    """verify cache miss + central 200 + valid:true → setex principal + return."""
    from app.settings_sync.client import ApiKeyVerifyClient
    from app.settings_sync.keys import make_apikey_cache_key

    principal = {
        "id": "key-uuid",
        "permissions": ["search"],
        "allowed_hub_ids": ["yte"],
    }
    central_response = {"valid": True, "principal": principal}
    redis = _make_mock_redis(get_value=None)  # cache miss
    secret = "x" * 32
    client = ApiKeyVerifyClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
        settings_proxy_secret=secret,
        ttl=60,
    )
    api_key = "mdk_abc123"
    expected_cache_key = make_apikey_cache_key(api_key)
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_mock_httpx_post(central_response, 200)
        result = await client.verify(api_key)
    assert result == principal
    # Setex positive only
    redis.setex.assert_called_once()
    args = redis.setex.call_args.args
    assert args[0] == expected_cache_key
    assert args[1] == 60
    assert json.loads(args[2]) == principal


async def test_apikey_verify_client_cache_miss_401_returns_none_no_cache() -> None:
    """verify cache miss + central 401 → None + KHÔNG setex (no negative cache)."""
    from app.settings_sync.client import ApiKeyVerifyClient

    redis = _make_mock_redis(get_value=None)
    client = ApiKeyVerifyClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
        settings_proxy_secret="x" * 32,
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value = _make_mock_httpx_post(
            {"detail": "invalid api key"}, status_code=401
        )
        result = await client.verify("bad_key")
    assert result is None
    redis.setex.assert_not_called()  # KHÔNG cache negative T-06-02-04


async def test_apikey_verify_client_cache_hit_skips_httpx() -> None:
    """verify cache hit (Redis bytes JSON) → KHÔNG httpx + return cached principal."""
    from app.settings_sync.client import ApiKeyVerifyClient

    cached_principal = {
        "id": "cached-uuid",
        "permissions": ["search", "ask"],
    }
    redis = _make_mock_redis(
        get_value=json.dumps(cached_principal).encode("utf-8")
    )
    client = ApiKeyVerifyClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
        settings_proxy_secret="x" * 32,
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        result = await client.verify("mdk_abc123")
    mock_cls.assert_not_called()  # cache hit skip HTTP
    assert result == cached_principal
    redis.setex.assert_not_called()  # KHÔNG re-cache


# ────────────────────────────────────────────────────────────────────
# Extra: verify X-Internal-Auth header sent (T-06-02-06 Spoofing mitigation)
# ────────────────────────────────────────────────────────────────────


async def test_apikey_verify_client_sends_internal_auth_header() -> None:
    """verify POST request gửi header X-Internal-Auth=<secret> (D-V3-Phase6-D)."""
    from app.settings_sync.client import ApiKeyVerifyClient

    redis = _make_mock_redis(get_value=None)
    secret = "x" * 32
    client = ApiKeyVerifyClient(
        central_url="http://central:8080",
        redis=redis,
        hub_name="yte",
        settings_proxy_secret=secret,
    )
    with patch("app.settings_sync.client.httpx.AsyncClient") as mock_cls:
        mock_inner = _make_mock_httpx_post(
            {"valid": True, "principal": {"id": "k"}},
            status_code=200,
        )
        mock_cls.return_value = mock_inner
        await client.verify("mdk_abc")
        # Inspect POST call kwargs
        call = mock_inner.post.call_args
        headers = call.kwargs.get("headers", {})
        assert headers.get("X-Internal-Auth") == secret
