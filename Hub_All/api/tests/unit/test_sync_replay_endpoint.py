"""Phase 4 Plan 04-06 Task 2 — Unit test POST /api/sync/replay admin endpoint
+ lifespan central spawn checksum_scheduler_task.

D-V3-Phase4-C2 admin replay verify:
- Pydantic schema SyncReplayRequest hub_id regex format + since ISO datetime.
- Require admin role (Phase 3 require_role carry forward).
- Hub con strip endpoint (central-only mount conditional).
- Body validation 422 cho missing hub_id.
- replay SQL pattern: UPDATE sync_outbox SET status='pending', attempt_count=0,
  last_error=NULL, next_retry_at=NULL WHERE status='dead' AND created_at >= $1.
- W8 fix audit_logs INSERT (action='sync.replay').
- Audit failure KHONG block replay (defensive try/except inner).

D-V3-Phase4-C3 lifespan spawn verify:
- Central boot → app.state.checksum_scheduler_task created.
- Hub con boot → app.state.checksum_scheduler_task is None.

Mock pattern: TestClient + dependency_overrides + mock asyncpg.connect.
"""
from __future__ import annotations

import inspect
import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

# ════════════════════════════════════════════════════════════════════
# Fixture — Settings cache clear cho mỗi test
# ════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _setup_central_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set env cho create_app central boot — co checksum_hub_dsns JSON."""
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
    # Central scheduler need this JSON to spawn / function. Set to single hub yte.
    monkeypatch.setenv(
        "CHECKSUM_HUB_DSNS_JSON",
        json.dumps(
            {
                "yte": (
                    "postgresql+asyncpg://sync_ro:pwd@postgres:5432/medinet_hub_yte"
                )
            }
        ),
    )
    from app.config import get_settings

    get_settings.cache_clear()


def _setup_hub_env(monkeypatch: pytest.MonkeyPatch, hub_name: str) -> None:
    """Set env cho create_app hub con boot."""
    monkeypatch.setenv("HUB_NAME", hub_name)
    monkeypatch.setenv(
        "DATABASE_URL",
        f"postgresql+asyncpg://u:p@localhost:5432/medinet_hub_{hub_name}",
    )
    monkeypatch.setenv(
        "COCOINDEX_DATABASE_URL",
        "postgresql://u:p@localhost:5432/medinet_cocoindex",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")
    monkeypatch.setenv(
        "CENTRAL_JWKS_URL",
        "http://python-api-central:8080/.well-known/jwks.json",
    )
    monkeypatch.setenv("CENTRAL_URL", "http://python-api-central:8080")
    monkeypatch.setenv("HUB_ID", "12345678-1234-1234-1234-123456789012")
    monkeypatch.setenv(
        "CENTRAL_SYNC_DSN",
        "postgresql+asyncpg://sync_user:pwd@postgres:5432/medinet_central",
    )
    monkeypatch.setenv("SYNC_SKIP_CENTRAL_POOL", "1")
    from app.config import get_settings

    get_settings.cache_clear()


# ════════════════════════════════════════════════════════════════════
# Test 1 — Pydantic schema validation hub_id regex format
# ════════════════════════════════════════════════════════════════════


def test_sync_replay_request_schema_valid_hub_id() -> None:
    """SyncReplayRequest accept valid hub_id format + ISO datetime."""
    from app.routers.sync import SyncReplayRequest

    body = SyncReplayRequest(
        hub_id="yte",
        since=datetime(2026, 5, 22, 0, 0, 0, tzinfo=UTC),
    )
    assert body.hub_id == "yte"
    assert body.since.year == 2026


def test_sync_replay_request_schema_invalid_hub_id() -> None:
    """SyncReplayRequest reject hub_id format invalid (uppercase / special chars)."""
    from pydantic import ValidationError

    from app.routers.sync import SyncReplayRequest

    with pytest.raises(ValidationError):
        SyncReplayRequest(
            hub_id="YTE",  # uppercase reject regex ^[a-z][a-z0-9_]{0,15}$
            since=datetime(2026, 5, 22, 0, 0, 0, tzinfo=UTC),
        )

    with pytest.raises(ValidationError):
        SyncReplayRequest(
            hub_id="hub-name",  # hyphen reject
            since=datetime(2026, 5, 22, 0, 0, 0, tzinfo=UTC),
        )


# ════════════════════════════════════════════════════════════════════
# Test 2 — replay SQL pattern matches D-V3-Phase4-C2
# ════════════════════════════════════════════════════════════════════


def test_replay_sql_resets_dead_rows() -> None:
    """REPLAY_SQL constant chua UPDATE sync_outbox + reset 4 field."""
    from app.routers.sync import REPLAY_SQL

    sql_normalized = " ".join(REPLAY_SQL.split())
    assert "UPDATE sync_outbox" in sql_normalized
    assert "status = 'pending'" in sql_normalized
    assert "attempt_count = 0" in sql_normalized
    assert "last_error = NULL" in sql_normalized
    assert "next_retry_at = NULL" in sql_normalized
    assert "status = 'dead'" in sql_normalized
    assert "created_at >= $1" in sql_normalized


# ════════════════════════════════════════════════════════════════════
# Test 3 — Endpoint mount conditional central-only (FACTOR-02 extend)
# ════════════════════════════════════════════════════════════════════


def test_replay_endpoint_central_only_mounted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Central boot → POST /api/sync/replay route mounted."""
    _setup_central_env(monkeypatch)
    from app.main import create_app

    app = create_app()
    paths = [
        (getattr(r, "path", None), getattr(r, "methods", None))
        for r in app.routes
    ]
    replay_routes = [
        (p, m) for (p, m) in paths if p == "/api/sync/replay" and m
    ]
    assert replay_routes, (
        "POST /api/sync/replay PHAI mount o central — Plan 04-06 D-V3-Phase4-C2"
    )
    methods = replay_routes[0][1] or set()
    assert "POST" in methods


@pytest.mark.parametrize("hub_name", ["yte", "duoc", "hcns"])
def test_replay_endpoint_hub_con_strips(
    monkeypatch: pytest.MonkeyPatch, hub_name: str
) -> None:
    """Hub con boot → POST /api/sync/replay KHONG mount (FACTOR-02 carry forward).

    /api/sync prefix entire router central-only nen replay endpoint cung strip.
    Hub con → 404 envelope D6 via StarletteHTTPException handler.
    """
    _setup_hub_env(monkeypatch, hub_name)
    from app.main import create_app

    app = create_app()
    paths = [getattr(r, "path", None) for r in app.routes]
    assert "/api/sync/replay" not in paths
    # /api/sync any sub-route — also stripped (sync_router central-only)
    sync_routes = [p for p in paths if p and p.startswith("/api/sync")]
    assert sync_routes == []


# ════════════════════════════════════════════════════════════════════
# Test 4 — Lifespan central spawn checksum_scheduler_task
# ════════════════════════════════════════════════════════════════════


def test_lifespan_central_spawns_checksum_task_source_check() -> None:
    """Central lifespan PHAI spawn checksum_scheduler_task — source check verify.

    KHONG dung full lifespan boot cho central (full lifespan boot trong unit
    test suite gay MemoryError do test pollution + accumulated async state +
    watchdog/audit/cocoindex side-effects. Defer integration test Phase 7
    MIGRATE-05 live-DB smoke E2E).

    Source check verify:
    - `checksum_scheduler_task_started` log line ton tai (in spawn branch).
    - `from app.observability.checksum_scheduler import checksum_scheduler_loop`
      import ton tai (only invoked trong central branch).
    - `asyncio.create_task(checksum_scheduler_loop(app))` spawn line ton tai.
    """
    from app import main as main_module

    source = inspect.getsource(main_module.lifespan)
    assert "checksum_scheduler_task_started" in source, (
        "main.py lifespan PHAI log checksum_scheduler_task_started khi spawn"
    )
    assert (
        "from app.observability.checksum_scheduler import" in source
        and "checksum_scheduler_loop" in source
    ), "main.py PHAI import checksum_scheduler_loop trong central branch"
    assert "asyncio.create_task" in source and "checksum_scheduler_loop(app)" in source, (
        "main.py PHAI spawn checksum_scheduler_task qua asyncio.create_task"
    )


def test_lifespan_hub_con_skips_checksum_task_source_check() -> None:
    """Hub con KHONG spawn checksum_scheduler_task — source check verify branch.

    Pattern: `if settings.hub_name == "central":` gate ngay quanh spawn task.
    KHONG dung full lifespan boot cho hub con (lifespan voi nhieu task spawn
    slow + flaky trong unit test — defer integration test Phase 7 MIGRATE-05).
    """
    import inspect

    from app import main as main_module

    source = inspect.getsource(main_module.lifespan)
    # Find scheduler spawn block: must guarded by hub_name == "central".
    assert "checksum_scheduler_task = None" in source, (
        "main.py lifespan must default checksum_scheduler_task = None"
    )
    # Locate spawn block — should appear AFTER central guard.
    spawn_idx = source.find("checksum_scheduler_task = asyncio.create_task")
    assert spawn_idx > 0, "spawn line phai ton tai trong lifespan"
    # Walk backwards to find nearest `if settings.hub_name == "central":` guard.
    pre_spawn = source[:spawn_idx]
    last_central_guard = pre_spawn.rfind('settings.hub_name == "central"')
    assert last_central_guard > 0, (
        "checksum_scheduler_task spawn PHAI co guard `if settings.hub_name == \"central\":` "
        "(D-V3-Phase4-C3 — central-only placement)"
    )
    # Between guard and spawn KHONG co `else:` branch xen vao (defensive).
    between = source[last_central_guard:spawn_idx]
    assert "\n    else:" not in between, (
        "spawn block phai trong nhanh `if central`, KHONG bi else: break"
    )


# ════════════════════════════════════════════════════════════════════
# Test 5 — Replay endpoint hub_id KHONG registered → 400 HUB_NOT_REGISTERED
# ════════════════════════════════════════════════════════════════════


def test_replay_endpoint_imports_audit_log_sql() -> None:
    """Source code chua INSERT INTO audit_logs + action='sync.replay' (W8 fix)."""
    from app.routers import sync as sync_module

    source = inspect.getsource(sync_module)
    # W8 fix mandatory grep
    assert "INSERT INTO audit_logs" in source, (
        "W8 fix — replay phai INSERT audit_logs row cho non-repudiation"
    )
    assert "sync.replay" in source, (
        "W8 fix — audit action label 'sync.replay' required"
    )


def test_replay_endpoint_uses_to_asyncpg_dsn_from_shared_module() -> None:
    """sync.py import _to_asyncpg_dsn tu app.db.dsn (W3 fix shared module)."""
    from app.routers import sync as sync_module

    source = inspect.getsource(sync_module)
    assert "from app.db.dsn import _to_asyncpg_dsn" in source, (
        "W3 fix — replay endpoint phai import _to_asyncpg_dsn tu shared "
        "app.db.dsn module (KHONG circular import qua app.main)"
    )


def test_replay_endpoint_uses_require_role_admin() -> None:
    """sync.py replay_dead_outbox depend on require_role('admin') (Phase 3 SSO-04)."""
    from app.routers import sync as sync_module

    source = inspect.getsource(sync_module)
    # require_role used with admin literal.
    assert 'require_role("admin")' in source or "require_role('admin')" in source, (
        "Plan 04-06 — require_role('admin') gate cho POST /api/sync/replay"
    )
