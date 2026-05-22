"""Alembic environment runtime — Medinet Wiki API.

Đặc trưng:
- Async runtime (asyncio + async_engine_from_config) — match stack SQLAlchemy 2 + asyncpg.
- DSN inject từ app.config.get_settings() + override qua `-x hub=<name>` argument
  (Phase 1 v3.0 TOPO-02 — per-hub Alembic). KHÔNG hardcode trong alembic.ini.
- target_metadata = Base.metadata (import từ app.db.base + app.models.*).
- include_object filter: exclude schema 'cocoindex' (Pitfall #P7 — KHÔNG touch internal state).
- compare_type=True + compare_server_default=True (Pitfall #P20 — drift detection chính xác).

Per-hub mode (Phase 1 v3.0 TOPO-02):
1. `alembic upgrade head`               → dùng Settings.database_url (M2 backward-compat).
2. `alembic -x hub=<name> upgrade head` → override DSN per-hub (Plan 03 + Makefile callers).

Cross-hub roundtrip support (W8): caller có thể chạy với DATABASE_URL=...medinet_hub_yte
(Settings.hub_name=yte) + pass -x hub=duoc → env un-resolve về central rồi resolve sang duoc.
Use case: dev test cross-hub migration KHÔNG cần restart server với env khác.

Helper functions (parse_hub_x_arg + resolve_env_database_url) là pure — unit testable
qua sys.path inject (xem tests/unit/test_alembic_env_hub_arg.py). Guard
`hasattr(context, "config")` cho phép import từ pytest mà KHÔNG trigger alembic runtime.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import models để Base.metadata pick up đủ 10 table TRƯỚC khi autogenerate run.
from app.config import get_settings, resolve_database_url
from app.db.base import Base
from app.models import *  # noqa: F401, F403 — register tất cả model vào metadata

# === Pure helpers — unit testable (KHÔNG access alembic.context) ===

# 4 hub hợp lệ — khớp Settings.hub_name Literal (Plan 02). Hub mới phải update
# cả 2 nơi (Plan 05 hub-init.sh dynamic add sẽ centralize source of truth).
_VALID_HUBS = {"central", "yte", "duoc", "hcns"}

# Plan 04-01 SYNC-05 — Per-hub-only migration registry (D-V3-Phase4-A2).
# Revision được xác định "per-hub-only" → SKIP no-op khi apply trên DB central.
# Runtime guard concret nằm trong từng migration upgrade() qua current_database()
# check (vd 0005_sync_outbox_per_hub.py). Helper pure này phục vụ unit test +
# tài liệu hóa intent (KHÔNG được dùng bởi alembic runtime trực tiếp — runtime
# check nằm trong migration module để chống bug "operator forget set -x hub").
_HUB_ONLY_REVS: frozenset[str] = frozenset({"0005"})


def is_sync_outbox_rev_applicable(rev_id: str, hub_name: str) -> bool:
    """Skip guard pure helper cho per-hub-only revision (Plan 04-01 D-V3-Phase4-A2).

    Args:
        rev_id: Alembic revision identifier (vd "0005").
        hub_name: Target hub name (central / yte / duoc / hcns / dynamic FACTOR-04).

    Returns:
        True nếu migration nên apply, False nếu skip no-op.

    Semantics:
        - rev KHÔNG nằm trong ``_HUB_ONLY_REVS`` → True (mọi rev khác apply mọi DB).
        - rev nằm trong ``_HUB_ONLY_REVS`` + ``hub_name == "central"`` → False (skip).
        - rev nằm trong ``_HUB_ONLY_REVS`` + ``hub_name != "central"`` → True
          (apply mọi hub con, kể cả dynamic FACTOR-04 vd `phap_che`).

    NOTE: Helper này pure-function unit testable; runtime enforcement nằm trong
    từng migration module qua `op.get_bind().execute("SELECT current_database()")`
    check để chống bug "operator quên `-x hub=<name>`" → apply nhầm trên central.
    """
    if rev_id not in _HUB_ONLY_REVS:
        return True
    return hub_name != "central"


def parse_hub_x_arg(x_args: list[str]) -> str | None:
    """Parse `-x hub=<name>` từ list x_arguments — trả hub name hoặc None.

    ``context.get_x_argument(as_dictionary=False)`` trả list ``["key=value", ...]``.

    Args:
        x_args: List chuỗi dạng ``"key=value"`` từ alembic CLI ``-x`` flag.

    Returns:
        Hub name nếu tìm thấy ``hub=<name>``, None nếu KHÔNG có (fallback
        Settings.hub_name khi caller dùng `resolve_env_database_url`).

    Raises:
        ValueError: nếu ``hub=<name>`` không thuộc 4 hub hợp lệ
            (T-01-03-01 Tampering mitigation — chống typo / malicious input).
    """
    for arg in x_args:
        if not arg.startswith("hub="):
            continue
        hub = arg.split("=", 1)[1].strip()
        if hub not in _VALID_HUBS:
            raise ValueError(
                f"alembic -x hub=<name>: {hub!r} không hợp lệ. "
                f"Hợp lệ: {sorted(_VALID_HUBS)}."
            )
        return hub
    return None


def resolve_env_database_url(
    base_dsn: str, hub_arg: str | None, default_hub: str
) -> str:
    """Resolve DSN runtime — ưu tiên ``hub_arg``, fallback ``default_hub``.

    Args:
        base_dsn: ``Settings.database_url`` (đã validated khớp ``default_hub`` qua
            ``_enforce_hub_dsn_match`` validator của Plan 02).
        hub_arg: Từ ``alembic -x hub=<name>`` hoặc None nếu CLI KHÔNG truyền.
        default_hub: ``Settings.hub_name`` fallback khi ``hub_arg is None``.

    Returns:
        DSN đã resolve cho target hub.

    Supported scenarios:
        - target=central + base_dsn trỏ central: return base_dsn (no rewriting).
        - target=<hub> + base_dsn trỏ central: ``resolve_database_url(base_dsn, hub)``.
        - target=<hub> + base_dsn trỏ medinet_hub_<other>: un-resolve về central
          trước, rồi resolve sang target (W8 — cross-hub yte→duoc roundtrip).
        - target=central + base_dsn trỏ medinet_hub_<other>: un-resolve về central.

    Raises:
        ValueError: ``base_dsn`` không trỏ ``medinet_central`` HOẶC
            ``medinet_hub_*`` (T-01-03-02 Tampering — input boundary check).
    """
    target_hub = hub_arg if hub_arg is not None else default_hub

    # Tách query string giữ nguyên (sslmode=require, application_name=..., ...).
    if "?" in base_dsn:
        path_part, query_part = base_dsn.split("?", 1)
        query_suffix = f"?{query_part}"
    else:
        path_part, query_suffix = base_dsn, ""
    path_part = path_part.rstrip("/")
    last_seg = path_part.rsplit("/", 1)[-1]

    # Validate base_dsn segment hợp lệ (central HOẶC medinet_hub_*).
    is_central_base = last_seg == "medinet_central"
    is_hub_base = last_seg.startswith("medinet_hub_")
    if not (is_central_base or is_hub_base):
        raise ValueError(
            f"base_dsn phải trỏ medinet_central hoặc medinet_hub_*: "
            f"{base_dsn!r}"
        )

    # Un-resolve base_dsn về central nếu đang ở hub khác (W8 cross-hub support).
    if is_hub_base:
        central_path = path_part[: -len(last_seg)] + "medinet_central"
        base_dsn_central = central_path + query_suffix
    else:
        base_dsn_central = base_dsn

    # target=central → trả base_dsn_central (có thể un-resolved hoặc nguyên).
    if target_hub == "central":
        return base_dsn_central

    # target=<hub> → resolve_database_url từ central base (Plan 02 helper).
    return resolve_database_url(base_dsn_central, target_hub)


# === Alembic runtime — KHÔNG chạy khi pytest import helpers ===
# Guard `hasattr(context, "config")` — `alembic.context.config` CHỈ available
# khi env.py được Alembic load qua exec_module. Pytest import "from env import X"
# sẽ skip block này → KHÔNG fail với AttributeError.

if hasattr(context, "config"):
    # Alembic Config object — read alembic.ini
    config = context.config

    # Setup logging từ alembic.ini
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)

    # === DSN injection runtime — support -x hub=<name> override ===
    _settings = get_settings()
    _x_args = context.get_x_argument(as_dictionary=False)
    _hub_arg = parse_hub_x_arg(list(_x_args))
    _resolved_dsn = resolve_env_database_url(
        _settings.database_url, _hub_arg, default_hub=_settings.hub_name
    )
    config.set_main_option("sqlalchemy.url", _resolved_dsn)

    # Target metadata cho autogenerate
    target_metadata = Base.metadata


def include_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Filter autogenerate diff — exclude schema 'cocoindex' (Pitfall #P7).

    CocoIndex tự quản schema `cocoindex` (auto-create internal state tables ở
    Phase 4). Alembic KHÔNG được drop/alter/touch các bảng đó — nếu không,
    `alembic upgrade head` có thể xóa state cocoindex → re-index toàn bộ corpus.
    """
    if hasattr(object_, "schema") and object_.schema == "cocoindex":
        return False
    return True


def run_migrations_offline() -> None:
    """Offline mode — sinh SQL string KHÔNG cần connect DB (vd để review)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Cấu hình context cho 1 transaction migration (sync wrapper)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Online async — tạo async engine + run migrations qua run_sync."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Online mode entry — chạy async migration qua asyncio.run."""
    asyncio.run(run_async_migrations())


# Guard alembic-only entrypoint — bypass khi unit test import từ pytest.
if hasattr(context, "config"):
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
