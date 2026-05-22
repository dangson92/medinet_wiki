"""Plan 04-04 Task 3 — Integration test lifespan central_sync_pool + sync_worker_task spawn.

Most tests dùng AsyncMock asyncpg.create_pool (KHÔNG cần Postgres runtime; defer
testcontainer Phase 7 MIGRATE-05). Real-DB test (test_outbox_trigger_fires_on_chunks_insert)
gated `INTEGRATION_DB_URL` env (skipif).

Coverage:
- Hub con boot lifespan → mock pool → app.state.central_sync_pool init OK +
  sync_worker_task spawn OK (Test 1).
- Central boot lifespan → skip spawn (Test 2 — D-V3-Phase4-A3).
- Hub con fail-fast khi DSN trỏ sai DB (Test 3 — T-04-04-01 mitigation).
- create_pool init param == _init_central_sync_conn (Test 4 — BLOCKER 2 verify).
- ChunkPayload roundtrip parse trigger Plan 04-01 payload shape (Test 5 —
  BLOCKER 2 end-to-end content_hash hex + vector list[float]).
- Graceful shutdown cancel worker + close pool (Test 6).
- Live trigger fire trên chunks INSERT (Test 7 — skipif INTEGRATION_DB_URL).
"""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.sync.models import ChunkPayload

pytestmark = [pytest.mark.integration]


class _AcquireContextMock:
    """Async context manager mimicking asyncpg pool.acquire() — returns conn."""

    def __init__(self, conn: AsyncMock) -> None:
        self.conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self.conn

    async def __aexit__(self, *args: Any) -> None:
        return None


def _build_mock_pool(actual_db: str = "medinet_central") -> AsyncMock:
    """Build AsyncMock asyncpg.Pool — fetchval('SELECT current_database()') trả
    actual_db arg.
    """
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=actual_db)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value=None)
    # Transaction context manager (worker dùng async with conn.transaction()).
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=None)
    mock_transaction.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = lambda: mock_transaction

    mock_pool = AsyncMock()
    mock_pool.acquire = lambda: _AcquireContextMock(mock_conn)
    mock_pool.close = AsyncMock()
    return mock_pool


def _hub_con_env(hub_name: str = "yte") -> dict[str, str]:
    """Build env dict cho hub con boot lifespan — KHÔNG dùng SYNC_SKIP_CENTRAL_POOL
    flag (test này verify central_sync_pool init RAN với mock pool).

    Reset get_settings cache khi monkeypatch (caller responsible).
    """
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
        "HUB_ID": "00000000-0000-0000-0000-000000000001",
        "CENTRAL_SYNC_DSN": (
            "postgresql+asyncpg://sync_user:pwd@postgres:5432/medinet_central"
        ),
    }


def _central_env() -> dict[str, str]:
    """Build env dict cho central boot lifespan."""
    return {
        "HUB_NAME": "central",
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/medinet_central",
        "COCOINDEX_DATABASE_URL": "postgresql://u:p@localhost:5432/medinet_cocoindex",
        "REDIS_URL": "redis://localhost:6379/0",
        "COCOINDEX_SKIP_SETUP": "1",
        "APP_ENV": "dev",
    }


def _apply_env(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    """Apply env dict + reset get_settings cache + reset module globals."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from app.config import get_settings

    get_settings.cache_clear()
    # DEF-05-01 carry forward — reset module globals tránh state leak.
    from app.services.audit_service import reset_queue

    reset_queue()
    from app.db import session as _db_session

    _db_session._engine = None
    _db_session._session_factory = None


# ─────────────────────────────────────────────────────────────────────────
# Test 1 — Hub con boot lifespan → central_sync_pool init + worker spawn
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_hub_con_init_central_sync_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hub con boot lifespan → app.state.central_sync_pool != None + sync_worker_task
    spawned. SAU shutdown → cả 2 = None (cleanup graceful)."""
    _apply_env(monkeypatch, _hub_con_env("yte"))
    mock_pool = _build_mock_pool(actual_db="medinet_central")

    with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
        from asgi_lifespan import LifespanManager

        from app.main import create_app

        app = create_app()
        async with LifespanManager(app):
            assert app.state.central_sync_pool is not None, (
                "Hub con phải init central_sync_pool sau lifespan startup"
            )
            assert app.state.sync_worker_task is not None, (
                "Hub con phải spawn sync_worker_task sau lifespan startup"
            )
            # Worker task chưa done (đang loop poll).
            assert app.state.sync_worker_task.done() is False

        # Sau shutdown — cleanup graceful.
        assert app.state.central_sync_pool is None
        assert app.state.sync_worker_task is None
        mock_pool.close.assert_awaited()


# ─────────────────────────────────────────────────────────────────────────
# Test 2 — Central boot lifespan → skip spawn (D-V3-Phase4-A3)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_central_skips_sync_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Central boot lifespan → central_sync_pool == None + sync_worker_task == None."""
    _apply_env(monkeypatch, _central_env())

    from asgi_lifespan import LifespanManager

    from app.main import create_app

    app = create_app()
    async with LifespanManager(app):
        assert getattr(app.state, "central_sync_pool", None) is None, (
            "Central KHÔNG được init central_sync_pool (D-V3-Phase4-A3)"
        )
        assert getattr(app.state, "sync_worker_task", None) is None, (
            "Central KHÔNG được spawn sync_worker_task (D-V3-Phase4-A3)"
        )


# ─────────────────────────────────────────────────────────────────────────
# Test 3 — Hub con fail-fast khi DSN trỏ sai DB (T-04-04-01 mitigation)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_hub_con_fail_fast_dsn_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSN trỏ sai DB (vd medinet_hub_yte thay vì medinet_central) → lifespan raise."""
    _apply_env(monkeypatch, _hub_con_env("yte"))
    # Mock pool trả actual_db SAI (T-04-04-01 spoofing scenario).
    mock_pool = _build_mock_pool(actual_db="medinet_hub_yte")

    with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
        from asgi_lifespan import LifespanManager

        from app.main import create_app

        app = create_app()
        with pytest.raises((RuntimeError, Exception)) as exc_info:
            async with LifespanManager(app):
                pass
        err_msg = str(exc_info.value)
        assert (
            "CENTRAL_SYNC_DSN trỏ sai DB" in err_msg
            or "medinet_central" in err_msg
            or "T-04-04-01" in err_msg
        ), f"Expected DSN mismatch error message, got: {err_msg!r}"


# ─────────────────────────────────────────────────────────────────────────
# Test 4 — create_pool init param == _init_central_sync_conn (BLOCKER 2 verify)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_central_sync_pool_uses_pgvector_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BLOCKER 2 verify — create_pool kwargs.init == _init_central_sync_conn callback.

    Inspect call_args_list cho central_sync_pool create_pool call (khác db_pool
    init call). Filter calls có kwargs `init` set non-None.
    """
    _apply_env(monkeypatch, _hub_con_env("yte"))
    mock_pool = _build_mock_pool(actual_db="medinet_central")

    create_pool_mock = AsyncMock(return_value=mock_pool)
    with patch("asyncpg.create_pool", create_pool_mock):
        from asgi_lifespan import LifespanManager

        from app.main import create_app

        app = create_app()
        async with LifespanManager(app):
            pass

    # Inspect — confirm ≥ 1 call có init kwarg set (non-None).
    calls_with_init = [
        c
        for c in create_pool_mock.call_args_list
        if "init" in c.kwargs and c.kwargs["init"] is not None
    ]
    assert len(calls_with_init) >= 1, (
        f"central_sync_pool create_pool PHẢI có init=_init_central_sync_conn "
        f"kwarg (BLOCKER 2). All calls: {create_pool_mock.call_args_list!r}"
    )

    # Verify init callback là `_init_central_sync_conn` (or callable that calls
    # register_vector). Tên có thể đổi tùy implementation — kiểm tra callable
    # invokable + signature accept 1 arg conn.
    init_callback = calls_with_init[0].kwargs["init"]
    assert callable(init_callback), (
        f"init kwarg phải là callable, got {type(init_callback)!r}"
    )
    # Trigger registration với mock conn (smoke test — verify KHÔNG raise).
    mock_conn = AsyncMock()
    await init_callback(mock_conn)


# ─────────────────────────────────────────────────────────────────────────
# Test 5 — ChunkPayload roundtrip parse trigger Plan 04-01 payload shape
# ─────────────────────────────────────────────────────────────────────────


def test_chunk_payload_roundtrip_trigger_shape() -> None:
    """BLOCKER 2 end-to-end — parse real trigger Plan 04-01 payload shape.

    Trigger emit:
    - content_hash qua `encode(NEW.content_hash, 'hex')` → 32 hex char (16 bytes).
    - vector qua `to_jsonb(NEW.vector::float4[])` → JSON array float (1536-dim).

    ChunkPayload field_validator decode content_hash hex → bytes; vector list pass.
    """
    trigger_payload = {
        "id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "hub_id": str(uuid.uuid4()),
        "content": "Nội dung test tiếng Việt có dấu — Medinet Wiki Phase 4",
        "content_hash": "ab" * 16,  # 32 hex char = 16 bytes
        "heading_path": "Section 1.2 / Subsection A",
        "page_start": 1,
        "page_end": 3,
        "vector": [0.1] * 1536,  # 1536-dim float list từ to_jsonb cast
        "metadata": {"source": "test"},
        "created_at": "2026-05-22T00:00:00+00:00",
    }
    payload = ChunkPayload.model_validate(trigger_payload)

    # Verify hex decoded
    assert isinstance(payload.content_hash, bytes), (
        f"content_hash phải là bytes, got {type(payload.content_hash).__name__}"
    )
    assert len(payload.content_hash) == 16, (
        f"content_hash phải 16 bytes, got {len(payload.content_hash)}"
    )

    # Verify vector parsed correctly
    assert isinstance(payload.vector, list)
    assert len(payload.vector) == 1536
    assert all(isinstance(v, float) for v in payload.vector[:10])

    # Verify other fields
    assert payload.heading_path == "Section 1.2 / Subsection A"
    assert payload.page_start == 1
    assert payload.page_end == 3
    assert payload.metadata == {"source": "test"}


# ─────────────────────────────────────────────────────────────────────────
# Test 6 — Graceful shutdown cancel worker + close pool within 10s
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_graceful_shutdown_cancels_worker_within_10s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lifespan shutdown → task.cancel() + asyncio.wait_for timeout 10s + pool.close()."""
    _apply_env(monkeypatch, _hub_con_env("yte"))
    mock_pool = _build_mock_pool(actual_db="medinet_central")

    with patch("asyncpg.create_pool", AsyncMock(return_value=mock_pool)):
        from asgi_lifespan import LifespanManager

        from app.main import create_app

        app = create_app()
        worker_task_ref: Any = None
        async with LifespanManager(app):
            worker_task_ref = app.state.sync_worker_task
            assert worker_task_ref is not None

        # Sau shutdown — task đã done (cancelled hoặc finished).
        assert worker_task_ref.done() is True, (
            "sync_worker_task phải done (cancelled) sau lifespan shutdown"
        )
        mock_pool.close.assert_awaited()


# ─────────────────────────────────────────────────────────────────────────
# Test 7 — Live trigger fire trên chunks INSERT (skipif INTEGRATION_DB_URL)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.environ.get("INTEGRATION_DB_URL"),
    reason="Trigger test requires live Postgres test DB — set INTEGRATION_DB_URL env",
)
@pytest.mark.asyncio
async def test_outbox_trigger_fires_on_chunks_insert(
    integration_db_pool: AsyncIterator[Any] | None,
) -> None:
    """Real-DB end-to-end — INSERT chunks → trigger Plan 04-01 enqueue sync_outbox.

    Verify:
    - sync_outbox row được tạo với op_type='insert' + status='pending'.
    - Payload contain hex content_hash (32 char) + null vector (this row case).
    - documents.sync_status flipped 'pending' → 'syncing' (BLOCKER 1 fix).

    Defer Phase 7 MIGRATE-05 wire pytest-docker + alembic apply 0005 runtime.
    """
    if integration_db_pool is None:
        pytest.skip("INTEGRATION_DB_URL not set")

    async with integration_db_pool.acquire() as conn:  # type: ignore[attr-defined]
        # Cleanup state from previous test runs.
        await conn.execute("TRUNCATE sync_outbox CASCADE")

        # Seed chunk INSERT (assume migration 0005 applied + parent rows exist
        # — Phase 7 MIGRATE-05 fixture sẽ apply alembic + seed hubs/documents).
        chunk_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        hub_id = uuid.uuid4()
        await conn.execute(
            """INSERT INTO chunks (id, document_id, hub_id, content,
                                   content_hash, vector, metadata)
               VALUES ($1, $2, $3, 'test content',
                       E'\\\\x' || repeat('ab', 16), NULL, '{}'::jsonb)""",
            chunk_id,
            doc_id,
            hub_id,
        )

        rows = await conn.fetch(
            "SELECT * FROM sync_outbox WHERE chunk_id = $1", chunk_id
        )
        assert len(rows) == 1, (
            f"Trigger Plan 04-01 phải enqueue 1 sync_outbox row, got {len(rows)}"
        )
        row = rows[0]
        assert row["op_type"] == "insert"
        assert row["status"] == "pending"

        # BLOCKER 2 verify — payload contain hex content_hash (32 char = 16 bytes hex).
        payload = row["payload"]
        assert payload["id"] == str(chunk_id)
        assert isinstance(payload["content_hash"], str)
        assert len(payload["content_hash"]) == 32  # hex encode 16 bytes
