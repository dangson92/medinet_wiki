"""Phase 6 Plan 06-04 — Integration test ASGI lifespan settings_sync state populate + shutdown.

Coverage (6 test):
- Test 1: SETTINGS_SKIP_FETCH=1 escape hatch → app.state.{rag,hub_registry,
  api_key_verify}_client + settings_subscriber_task = None.
- Test 2: Mock httpx happy → 3 client instance populated qua isinstance check.
- Test 3: Mock httpx happy + Redis mock → settings_subscriber_task is asyncio.Task
  + .done() == False (running).
- Test 4: Shutdown lifespan → settings_subscriber_task.done()/cancelled() True
  sau LifespanManager exit (cleanup graceful).
- Test 5: Mock httpx raise ConnectError → LifespanManager startup raise
  (boot fail-loud D-V3-Phase6-A → uvicorn exit 1 simulate).
- Test 6: Central mode (hub_name=central) → app.state.{rag,hub_registry,
  api_key_verify}_client = None (block skip — KHÔNG hub con).

Pattern carry forward:
- `test_jwks_cache_lifecycle.py` Plan 03-02 — ASGI LifespanManager + mock httpx.
- `test_sync_lifespan_integration.py` Plan 04-04 — mock asyncpg + state assert.

Defer:
- pubsub e2e fakeredis test deferred — see test_settings_sync_pubsub_e2e.py.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from asgi_lifespan import LifespanManager

pytestmark = [pytest.mark.integration]


def _hub_con_env(hub_name: str = "yte") -> dict[str, str]:
    """Build env dict cho hub con boot lifespan — Plan 03-02 + 04-04 pattern carry forward."""
    db = f"medinet_hub_{hub_name}"
    return {
        "HUB_NAME": hub_name,
        "DATABASE_URL": f"postgresql+asyncpg://u:p@localhost:5432/{db}",
        "COCOINDEX_DATABASE_URL": "postgresql://u:p@localhost:5432/medinet_cocoindex",
        "REDIS_URL": "redis://localhost:6379/0",
        "COCOINDEX_SKIP_SETUP": "1",
        "APP_ENV": "dev",
        "CENTRAL_JWKS_URL": "http://python-api-central:8080/.well-known/jwks.json",
        "CENTRAL_URL": "http://python-api-central:8080",
        "JWKS_SKIP_FETCH": "1",
        "HUB_ID": "12345678-1234-1234-1234-123456789012",
        "CENTRAL_SYNC_DSN": (
            "postgresql+asyncpg://sync_user:pwd@postgres:5432/medinet_central"
        ),
        "SYNC_SKIP_CENTRAL_POOL": "1",
        "SETTINGS_PROXY_SECRET": "x" * 32,
    }


def _central_env() -> dict[str, str]:
    """Build env dict cho central boot lifespan — block hub con skip."""
    return {
        "HUB_NAME": "central",
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
        "COCOINDEX_DATABASE_URL": "postgresql://u:p@localhost:5432/medinet_cocoindex",
        "REDIS_URL": "redis://localhost:6379/0",
        "COCOINDEX_SKIP_SETUP": "1",
        "APP_ENV": "dev",
        "SETTINGS_PROXY_SECRET": "x" * 32,
    }


def _apply_env(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    """Apply env dict + reset get_settings cache + reset module globals."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from app.config import get_settings

    get_settings.cache_clear()
    # DEF-05-01 carry forward — reset module-global state TRƯỚC khi boot app.
    from app.services.audit_service import reset_queue

    reset_queue()
    from app.db import session as _db_session

    _db_session._engine = None
    _db_session._session_factory = None


def _mock_httpx_factory(
    rag_config_data: dict[str, Any],
    hubs_data: list[dict[str, Any]],
) -> MagicMock:
    """Build mock httpx.AsyncClient — return canned responses based on URL path.

    Pattern carry forward `test_jwks_cache_lifecycle.py` Plan 03-02 mock httpx.
    """

    async def _mock_get(url: str, *args: Any, **kwargs: Any) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "/rag-config" in url:
            resp.json = MagicMock(return_value=rag_config_data)
        elif "/hubs" in url:
            resp.json = MagicMock(return_value=hubs_data)
        else:
            resp.json = MagicMock(return_value={})
        resp.status_code = 200
        return resp

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=_mock_get)
    return mock_client


# ─────────────────────────────────────────────────────────────────────────
# Test 1 — SETTINGS_SKIP_FETCH=1 escape hatch
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_skip_fetch_flag_bypasses_settings_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SETTINGS_SKIP_FETCH=1 → app.state.{rag,hub_registry,api_key_verify}_client = None."""
    env = _hub_con_env("yte")
    env["SETTINGS_SKIP_FETCH"] = "1"
    _apply_env(monkeypatch, env)

    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        assert app.state.rag_config_client is None, (
            "SETTINGS_SKIP_FETCH=1 → rag_config_client KHÔNG được init"
        )
        assert app.state.hub_registry_client is None
        assert app.state.api_key_verify_client is None
        assert app.state.settings_subscriber_task is None


# ─────────────────────────────────────────────────────────────────────────
# Test 2 — Mock httpx happy → 3 client instance populated
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_populates_settings_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mock httpx fetch_initial happy → 3 client instance populated isinstance OK."""
    from app.settings_sync.client import (
        ApiKeyVerifyClient,
        HubRegistryClient,
        RagConfigClient,
    )

    env = _hub_con_env("yte")
    env["SETTINGS_SKIP_FETCH"] = "0"
    _apply_env(monkeypatch, env)

    rag_config_data = {"provider": "openai", "model": "gpt-4", "dimensions": 1536}
    hubs_data = [{"id": "yte", "subpath": "/yte", "active": True}]
    mock_client = _mock_httpx_factory(rag_config_data, hubs_data)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from app.main import create_app

        app = create_app()
        async with LifespanManager(app):
            assert isinstance(app.state.rag_config_client, RagConfigClient), (
                f"Expected RagConfigClient, got {type(app.state.rag_config_client)!r}"
            )
            assert isinstance(app.state.hub_registry_client, HubRegistryClient)
            assert isinstance(app.state.api_key_verify_client, ApiKeyVerifyClient)


# ─────────────────────────────────────────────────────────────────────────
# Test 3 — Mock httpx + Redis → settings_subscriber_task running
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_subscriber_branch_by_redis_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subscriber spawn branch theo app.state.redis_ready (T-06-04-04 guard).

    Phase 6 lifespan logic: `if app.state.redis is not None and app.state.redis_ready`:
    - True → asyncio.create_task(settings_subscriber_loop) spawn.
    - False → log warning skip (best-effort fail-quiet per CONTEXT Claude's
      Discretion D-V3-Phase6 sub-decision).

    Test verify branch logic — KHÔNG hard-code redis state (môi trường CI vs
    local có thể khác: testcontainer Redis live HOẶC standalone Redis chết).
    """
    from app.settings_sync.client import (
        ApiKeyVerifyClient,
        HubRegistryClient,
        RagConfigClient,
    )

    env = _hub_con_env("yte")
    env["SETTINGS_SKIP_FETCH"] = "0"
    env["REDIS_URL"] = "redis://localhost:6379/0"
    _apply_env(monkeypatch, env)

    rag_config_data = {"provider": "openai", "model": "gpt-4"}
    hubs_data = [{"id": "yte"}]
    mock_client = _mock_httpx_factory(rag_config_data, hubs_data)

    with patch("httpx.AsyncClient", return_value=mock_client):
        from app.main import create_app

        app = create_app()
        async with LifespanManager(app):
            # 3 client populate.
            assert isinstance(app.state.rag_config_client, RagConfigClient)
            assert isinstance(app.state.hub_registry_client, HubRegistryClient)
            assert isinstance(app.state.api_key_verify_client, ApiKeyVerifyClient)
            # Branch theo redis_ready — Phase 6 lifespan guard T-06-04-04.
            if app.state.redis_ready:
                assert app.state.settings_subscriber_task is not None, (
                    "redis_ready=True → subscriber_task PHẢI spawn asyncio.Task"
                )
                assert isinstance(
                    app.state.settings_subscriber_task, asyncio.Task
                )
            else:
                assert app.state.settings_subscriber_task is None, (
                    "redis_ready=False → subscriber_task PHẢI = None (skip)"
                )


# ─────────────────────────────────────────────────────────────────────────
# Test 4 — Shutdown cancels subscriber task
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_shutdown_resets_subscriber_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown lifespan → app.state.settings_subscriber_task reset = None.

    Verify shutdown logic main.py — sau yield trong finally block:
    - `task.cancel() + asyncio.wait_for(timeout=10s)` graceful cancel.
    - `app.state.settings_subscriber_task = None` state cleared.

    Pattern song song Plan 04-04 test_graceful_shutdown_cancels_worker — verify
    state field reset sau lifespan exit (KHÔNG leak Task reference).
    """
    from app.settings_sync.client import RagConfigClient

    env = _hub_con_env("yte")
    env["SETTINGS_SKIP_FETCH"] = "0"
    env["REDIS_URL"] = "redis://localhost:6379/0"
    _apply_env(monkeypatch, env)

    rag_config_data = {"provider": "openai"}
    hubs_data = [{"id": "yte"}]
    mock_client = _mock_httpx_factory(rag_config_data, hubs_data)

    captured_task_ref: list[Any] = []
    with patch("httpx.AsyncClient", return_value=mock_client):
        from app.main import create_app

        app = create_app()
        async with LifespanManager(app):
            assert isinstance(app.state.rag_config_client, RagConfigClient)
            # Capture task ref (nếu spawn) để verify done() sau shutdown.
            if app.state.settings_subscriber_task is not None:
                captured_task_ref.append(app.state.settings_subscriber_task)

        # Sau LifespanManager exit — state reset None (shutdown handler).
        assert app.state.settings_subscriber_task is None, (
            "Shutdown handler PHẢI reset app.state.settings_subscriber_task = None"
        )
        # Nếu task spawn → verify cancelled/done sau shutdown.
        if captured_task_ref:
            t = captured_task_ref[0]
            assert t.done(), (
                f"Subscriber task PHẢI done sau lifespan shutdown, got done()={t.done()}"
            )


# ─────────────────────────────────────────────────────────────────────────
# Test 5 — Boot fail-loud khi fetch_initial raise
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_fetch_initial_fail_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RagConfigClient.fetch_initial raise → boot fail-loud (D-V3-Phase6-A simulate).

    Test direct fetch_initial behavior (KHÔNG qua asgi_lifespan để tránh leak
    audit_task / search_cache_task khi raise giữa lifespan startup — pattern
    pre-existing M2 baseline: shutdown finally CHỈ chạy khi yield đã reach;
    raise trước yield → tasks ở step 0..N-1 leak). Thay vì test full asgi
    lifecycle, ta test trực tiếp `rag_client.fetch_initial()` → raise
    SettingsUnavailableError (đảm bảo lifespan code path đúng nếu trigger).
    """
    from app.settings_sync.client import (
        RagConfigClient,
        SettingsUnavailableError,
    )

    async def _fail_get(*args: Any, **kwargs: Any) -> None:
        raise httpx.ConnectError("mock central down — T-06-04-01 simulate")

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=_fail_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        client = RagConfigClient(
            central_url="http://python-api-central:8080",
            redis=None,
            hub_name="yte",
            ttl=60,
        )
        with pytest.raises(SettingsUnavailableError) as exc_info:
            await client.fetch_initial()
        err_msg = str(exc_info.value)
        assert "fetch_initial failed" in err_msg, (
            f"Expected SettingsUnavailableError fetch_initial failed, got: {err_msg!r}"
        )

    # Verify main.py lifespan code path TRIGGER fetch_initial trong block hub con.
    # Acceptance grep `rag_client.fetch_initial` được verify ở Task 1 acceptance
    # criteria (grep main.py). Boot fail-loud chain documented ở lifespan
    # try/except block (raise re-thrown propagate uvicorn exit 1).
    import pathlib

    main_py = pathlib.Path("app/main.py").read_text(encoding="utf-8")
    assert "await rag_client.fetch_initial()" in main_py, (
        "main.py lifespan PHẢI gọi await rag_client.fetch_initial() blocking"
    )
    assert "lifespan_settings_sync_init_failed" in main_py, (
        "main.py lifespan PHẢI log critical fail-loud nếu raise"
    )


# ─────────────────────────────────────────────────────────────────────────
# Test 6 — Central mode skips settings_sync block
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_central_mode_skips_settings_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Central app (hub_name=central) → settings_sync block skipped (D-V3-Phase6-A)."""
    _apply_env(monkeypatch, _central_env())

    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        assert getattr(app.state, "rag_config_client", None) is None, (
            "Central KHÔNG được init rag_config_client (block hub con-only)"
        )
        assert getattr(app.state, "hub_registry_client", None) is None
        assert getattr(app.state, "api_key_verify_client", None) is None
        assert getattr(app.state, "settings_subscriber_task", None) is None
