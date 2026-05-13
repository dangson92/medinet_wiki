"""Alembic environment runtime — Medinet Wiki API M2.

Đặc trưng:
- Async runtime (asyncio + async_engine_from_config) — match stack SQLAlchemy 2 + asyncpg.
- DSN inject từ app.config.get_settings() — alembic.ini KHÔNG hardcode (mỗi env dùng DSN riêng).
- target_metadata = Base.metadata (import từ app.db.base + app.models.*).
- include_object filter: exclude schema 'cocoindex' (Pitfall #P7 — KHÔNG touch internal state).
- compare_type=True + compare_server_default=True (Pitfall #P20 — drift detection chính xác).
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import models để Base.metadata pick up đủ 10 table TRƯỚC khi autogenerate run.
from app.config import get_settings
from app.db.base import Base
from app.models import *  # noqa: F401, F403 — register tất cả model vào metadata

# Alembic Config object — read alembic.ini
config = context.config

# Setup logging từ alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject DSN runtime — KHÔNG hardcode trong alembic.ini.
_settings = get_settings()
config.set_main_option("sqlalchemy.url", _settings.database_url)

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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
