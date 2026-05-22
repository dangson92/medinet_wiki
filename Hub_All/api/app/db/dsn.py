"""Phase 4 Plan 04-04 (W3 fix) — Shared DSN conversion helpers.

Tách helper `_to_asyncpg_dsn` khỏi `app/main.py` sang module trung lập để Plan
04-06 (`checksum_scheduler.py` + `routers/sync.py` admin replay) + Plan 04-04
(lifespan central_sync_pool) import từ shared module — tránh circular import
qua `app.main` → routers chain.

Lý do W3 fix:
- `app/main.py::create_app` import từ `app/routers/sync.py` (M2 sync stub).
- Nếu Plan 04-06 thêm `sync.py` router import `_to_asyncpg_dsn` từ
  `app.main` → vòng tròn `routers.sync` → `app.main` → `routers.sync` lại.
- Tách sang `app/db/dsn.py` (module trung lập, KHÔNG import gì từ routers/
  hoặc main) → mọi consumer import an toàn.

Idempotent — chuyển đổi prefix `postgresql+asyncpg://` thành `postgresql://`
nếu phát hiện, ngược lại pass-through nguyên (KHÔNG raise) cho legacy DSN +
test fixture truyền DSN đã chuyển sẵn.
"""
from __future__ import annotations


def _to_asyncpg_dsn(sqlalchemy_dsn: str) -> str:
    """Convert SQLAlchemy DSN (`postgresql+asyncpg://...`) → asyncpg DSN
    (`postgresql://...`).

    SQLAlchemy + Alembic dùng prefix `postgresql+asyncpg://` để chỉ driver
    asyncpg cho async engine. `asyncpg.create_pool()` cần raw `postgresql://`
    KHÔNG có driver prefix. Strip prefix idempotent (no-op nếu đã raw).

    Args:
        sqlalchemy_dsn: DSN dạng SQLAlchemy hoặc raw asyncpg.

    Returns:
        DSN sạch cho `asyncpg.create_pool()` consume.
    """
    return sqlalchemy_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


__all__ = ["_to_asyncpg_dsn"]
