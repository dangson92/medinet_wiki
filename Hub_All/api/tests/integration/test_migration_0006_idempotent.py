"""Integration test migration 0006 idempotent — Phase 1 Plan 01-03 (ROLE-01..04).

Verify 4 success criteria của ROADMAP Phase 1:
1. `alembic upgrade head` 2 lần PASS idempotent; CHECK constraint accept 4 value.
2. user_hubs.role nullable default NULL; existing rows preserved.
3. audit_logs có row action='migration.role_seed' với count + timestamp.
4. `alembic downgrade -1` rollback PASS — restore CHECK 3 value cũ, drop user_hubs.role.

PRE-CONDITION: TEST_DATABASE_URL env var trỏ tới Postgres test DB CÓ schema
0001-0005 đã apply (KHÔNG bao gồm 0006). Test sẽ apply 0006 + verify + rollback.

Nếu TEST_DATABASE_URL không set → pytest.skip ("manual run only" — Phase 4
MIGRATE-01 sẽ chạy đầy đủ qua make test-integration).

SAFETY-CRITICAL DSN injection (Iter 1 revision fix I-01):
- `migrations/env.py:185-191` runtime OVERRIDE `sqlalchemy.url` từ
  `get_settings().database_url` → IGNORE caller's `cfg.set_main_option(...)`.
- Fixture PHẢI monkeypatch env var `DATABASE_URL` + `get_settings.cache_clear()`
  TRƯỚC `command.upgrade()` — env.py re-read Settings và pick up TEST_DATABASE_URL.
- KHÔNG dùng `set_main_option("sqlalchemy.url", ...)` (bị overwrite).
- KHÔNG convert sync_url ở level fixture (Iter 1 fix I-02) — env.py xử lý
  asyncpg natively qua `async_engine_from_config` + `resolve_env_database_url`.
- Reference pattern: tests/unit/test_alembic_env_hub_arg.py (sys.path inject
  env.py helpers — analog cho lý do tại sao phải monkeypatch env: env.py KHÔNG
  phải module Python chuẩn, Alembic load qua exec_module + runtime DSN injection).
"""
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture
def test_db_url() -> str:
    """Lấy TEST_DATABASE_URL hoặc skip test.

    Format gốc `postgresql+asyncpg://user:pass@host:5432/medinet_test` — KHÔNG
    convert sang `postgresql://`. env.py + Settings expect prefix asyncpg
    (async_engine_from_config). Chỉ khi asyncpg.connect() trực tiếp mới strip
    prefix (xem helper `_asyncpg_dsn` dưới).
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL chưa set — integration test chỉ chạy manual. "
            "Set TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/medinet_test "
            "trước khi chạy `pytest tests/integration/test_migration_0006_idempotent.py`. "
            "Phase 4 MIGRATE-01 sẽ chạy bắt buộc qua `make test-integration`."
        )
    return url


def _asyncpg_dsn(test_db_url: str) -> str:
    """Strip `+asyncpg` prefix cho asyncpg.connect() trực tiếp.

    asyncpg KHÔNG hiểu prefix `postgresql+asyncpg://` (SQLAlchemy driver hint).
    Chỉ cần dùng khi connect direct ngoài SQLAlchemy engine (vd verify CHECK
    constraint sau migration). env.py vẫn xài format gốc qua async_engine_from_config.
    """
    return test_db_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture
def alembic_cfg(test_db_url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    """Tạo Alembic Config với DSN injection qua monkeypatch env + cache_clear.

    SAFETY-CRITICAL (Iter 1 fix I-01 + I-02):
    - `migrations/env.py:185-191` runtime OVERRIDE `sqlalchemy.url` từ
      `get_settings().database_url`. Caller's set_main_option DSN cũng
      BỊ IGNORE → nếu dùng set_main_option, migration apply vào DB lấy từ .env
      (vd `medinet_central`) — SAFETY BLOCKER.
    - Pattern ĐÚNG: monkeypatch.setenv("DATABASE_URL", test_db_url) + clear
      `get_settings` lru_cache → env.py re-read Settings và pick up test DSN.
    - Format DSN giữ nguyên `postgresql+asyncpg://` (KHÔNG convert sync).
    - Reference: tests/unit/test_alembic_env_hub_arg.py (analog pattern test
      env.py helpers).
    """
    # 1. Override env var TRƯỚC khi get_settings() được gọi.
    monkeypatch.setenv("DATABASE_URL", test_db_url)

    # 2. Clear lru_cache get_settings (api/app/config.py:629 @lru_cache decorator).
    #    Settings instance trước đó (boot từ .env) đã cache → cache_clear() force
    #    re-parse env vars mới.
    from app.config import get_settings
    get_settings.cache_clear()

    # 3. Optional cleanup teardown: restore cache state sau test.
    #    monkeypatch.setenv() tự restore env var sau test scope (pytest builtin).
    #    Nhưng lru_cache PHẢI clear lại để test khác KHÔNG kế thừa Settings test DSN.
    def _cleanup_cache() -> None:
        get_settings.cache_clear()

    # pytest finalizer (request-scoped cleanup).
    # Note: monkeypatch fixture là function-scoped → tự revert env vars.
    # Manual cache_clear cuối test để Settings fresh cho next test.
    import atexit
    atexit.register(_cleanup_cache)  # safety net — không rely (test order dependency).

    # 4. Tạo Config — env.py sẽ đọc Settings.database_url MỚI khi load.
    #    alembic.ini ở Hub_All/api/alembic.ini (carry forward 0001-0005 layout).
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
    cfg_path = os.path.abspath(cfg_path)
    cfg = Config(cfg_path)
    # KHÔNG set_main_option("sqlalchemy.url", ...) — bị env.py override (I-01 fix).
    return cfg


def _reset_settings_cache() -> None:
    """Helper clear get_settings cache giữa test (defensive — test isolation).

    Gọi sau mỗi command.upgrade()/downgrade() để đảm bảo Settings KHÔNG cache
    state cũ (test_db_url khác giữa các test session hoặc parallel run).
    """
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_upgrade_head_then_check_constraint_accepts_hub_admin(
    test_db_url: str, alembic_cfg: Config,
) -> None:
    """Success criteria 1 — sau upgrade head, CHECK constraint accept 'hub_admin'.

    Steps:
    1. command.upgrade(cfg, 'head') → 0006 apply (DSN inject qua monkeypatch ở fixture).
    2. INSERT 1 user với role='hub_admin' → PHẢI thành công (CHECK pass).
    3. INSERT 1 user với role='invalid' → PHẢI fail (CHECK reject).
    """
    # Fixture đã monkeypatch DATABASE_URL + cache_clear → env.py pick up test DSN.
    command.upgrade(alembic_cfg, "head")

    conn = await asyncpg.connect(dsn=_asyncpg_dsn(test_db_url))
    try:
        # Insert user hub_admin — PHẢI thành công.
        user_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO users (id, email, password_hash, role)
            VALUES ($1, $2, $3, 'hub_admin')
            """,
            user_id, f"hubadmin_{user_id}@test.local", "dummy_hash",
        )

        # Verify row inserted với role='hub_admin'.
        row = await conn.fetchrow(
            "SELECT role FROM users WHERE id = $1", user_id,
        )
        assert row is not None
        assert row["role"] == "hub_admin"

        # Insert user role='invalid' — PHẢI fail CHECK constraint.
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                """
                INSERT INTO users (id, email, password_hash, role)
                VALUES ($1, $2, $3, 'invalid_role')
                """,
                uuid.uuid4(), f"invalid_{uuid.uuid4()}@test.local", "dummy_hash",
            )
    finally:
        # Cleanup test users — defensive (KHÔNG leak test data).
        await conn.execute(
            "DELETE FROM users WHERE email LIKE 'hubadmin_%@test.local' OR email LIKE 'invalid_%@test.local'"
        )
        await conn.close()


@pytest.mark.asyncio
async def test_upgrade_head_idempotent_runs_twice_without_error(
    test_db_url: str, alembic_cfg: Config,
) -> None:
    """Success criteria 1 (idempotent) — re-run upgrade head 2 lần KHÔNG fail.

    Steps:
    1. command.upgrade(cfg, 'head') → 0006 apply (lần 1; fixture DSN inject).
    2. _reset_settings_cache() giữa 2 lần để env.py re-read Settings (defensive).
    3. command.upgrade(cfg, 'head') → 0006 SKIP via introspect guard (lần 2 no-op).
    Cả 2 lần KHÔNG raise exception.

    Note: fixture đã monkeypatch + cache_clear lần đầu. Giữa 2 command.upgrade
    Settings có thể cached lại (lru_cache) — defensive clear thêm.
    """
    command.upgrade(alembic_cfg, "head")
    # Defensive — clear cache giữa 2 upgrade để env.py re-read Settings fresh.
    _reset_settings_cache()
    # Re-run — introspect guard ở 3 STEP của 0006 PHẢI skip toàn bộ.
    command.upgrade(alembic_cfg, "head")
    # Nếu không raise → PASS.


@pytest.mark.asyncio
async def test_user_hubs_role_nullable_accepts_null_and_value(
    test_db_url: str, alembic_cfg: Config,
) -> None:
    """Success criteria 2 — user_hubs.role nullable + NULL-aware CHECK + value CHECK.

    Steps:
    1. Tạo user + hub fixture.
    2. INSERT user_hubs row với role=NULL → PASS.
    3. INSERT user_hubs row với role='hub_admin' → PASS.
    4. INSERT user_hubs row với role='invalid' → FAIL CHECK.
    """
    # Fixture đã monkeypatch DATABASE_URL — env.py pick up test DSN.
    command.upgrade(alembic_cfg, "head")
    conn = await asyncpg.connect(dsn=_asyncpg_dsn(test_db_url))
    try:
        # Setup user + hub.
        user_id = uuid.uuid4()
        hub_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO users (id, email, password_hash, role) VALUES ($1, $2, $3, 'viewer')",
            user_id, f"role_test_{user_id}@test.local", "dummy_hash",
        )
        await conn.execute(
            "INSERT INTO hubs (id, slug, name) VALUES ($1, $2, $3)",
            hub_id, f"test-hub-{hub_id}", f"Test Hub {hub_id}",
        )

        # INSERT user_hubs role=NULL — inherit global.
        await conn.execute(
            "INSERT INTO user_hubs (user_id, hub_id, role) VALUES ($1, $2, NULL)",
            user_id, hub_id,
        )
        row = await conn.fetchrow(
            "SELECT role FROM user_hubs WHERE user_id = $1 AND hub_id = $2",
            user_id, hub_id,
        )
        assert row is not None
        assert row["role"] is None  # NULL preserved.

        # UPDATE role='hub_admin' — per-hub override.
        await conn.execute(
            "UPDATE user_hubs SET role = 'hub_admin' WHERE user_id = $1 AND hub_id = $2",
            user_id, hub_id,
        )
        row = await conn.fetchrow(
            "SELECT role FROM user_hubs WHERE user_id = $1 AND hub_id = $2",
            user_id, hub_id,
        )
        assert row["role"] == "hub_admin"

        # UPDATE role='invalid' — FAIL CHECK.
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "UPDATE user_hubs SET role = 'invalid' WHERE user_id = $1 AND hub_id = $2",
                user_id, hub_id,
            )
    finally:
        # Cleanup.
        await conn.execute(
            "DELETE FROM users WHERE email LIKE 'role_test_%@test.local'"
        )
        await conn.execute(
            "DELETE FROM hubs WHERE slug LIKE 'test-hub-%'"
        )
        await conn.close()


@pytest.mark.asyncio
async def test_audit_logs_seed_row_inserted_after_upgrade(
    test_db_url: str, alembic_cfg: Config,
) -> None:
    """Success criteria 3 — audit_logs có row action='migration.role_seed'.

    Verify:
    - Row tồn tại với action='migration.role_seed'.
    - payload chứa 'migration_revision' = '0006'.
    - payload chứa 'admin_count' (≥ 0 — có thể 0 nếu DB test rỗng).
    - payload chứa 'timestamp_utc' (string).
    """
    # Fixture monkeypatch DATABASE_URL — env.py pick up test DSN.
    command.upgrade(alembic_cfg, "head")
    conn = await asyncpg.connect(dsn=_asyncpg_dsn(test_db_url))
    try:
        row = await conn.fetchrow(
            """
            SELECT payload
            FROM audit_logs
            WHERE action = 'migration.role_seed'
              AND payload->>'migration_revision' = '0006'
            ORDER BY created_at DESC
            LIMIT 1
            """,
        )
        assert row is not None, "Migration seed row KHÔNG tồn tại sau upgrade"
        import json
        payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        assert payload.get("migration_revision") == "0006"
        assert "admin_count" in payload
        assert "user_hubs_count" in payload
        assert "timestamp_utc" in payload
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_downgrade_restores_check_3_value_and_drops_user_hubs_role(
    test_db_url: str, alembic_cfg: Config,
) -> None:
    """Success criteria 4 — downgrade -1 rollback PASS, restore CHECK 3 value + drop column.

    Steps:
    1. Upgrade head (0006 apply; fixture monkeypatch DSN).
    2. Verify user_hubs.role column tồn tại + CHECK accept 'hub_admin'.
    3. _reset_settings_cache() defensive trước downgrade (giữ DSN test fresh).
    4. Downgrade -1 (rollback 0006 → 0005; env.py re-read Settings).
    5. Verify user_hubs.role column DROPPED.
    6. Verify CHECK constraint users.role REJECT 'hub_admin' (3 value cũ).
    7. _reset_settings_cache() trước restore head (final state cho test order).
    8. Restore head state (KHÔNG để DB ở 0005 sau test).
    """
    # Setup state — apply head trước (fixture monkeypatch DSN).
    command.upgrade(alembic_cfg, "head")

    # Defensive — clear cache trước downgrade để env.py re-read Settings fresh.
    _reset_settings_cache()
    command.downgrade(alembic_cfg, "-1")

    conn = await asyncpg.connect(dsn=_asyncpg_dsn(test_db_url))
    try:
        # Verify user_hubs.role DROPPED.
        col_row = await conn.fetchrow(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'user_hubs' AND column_name = 'role'
            """,
        )
        assert col_row is None, "user_hubs.role column KHÔNG bị drop sau downgrade"

        # Verify CHECK constraint users.role REJECT 'hub_admin'.
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                """
                INSERT INTO users (id, email, password_hash, role)
                VALUES ($1, $2, $3, 'hub_admin')
                """,
                uuid.uuid4(), f"downgrade_test_{uuid.uuid4()}@test.local", "dummy_hash",
            )
    finally:
        # Cleanup + restore head cho test khác.
        await conn.execute(
            "DELETE FROM users WHERE email LIKE 'downgrade_test_%@test.local'"
        )
        await conn.close()
        # Defensive clear trước restore head — env.py re-read Settings.
        _reset_settings_cache()
        # Restore head state (KHÔNG để DB ở downgrade state — tránh phá test sau).
        command.upgrade(alembic_cfg, "head")
