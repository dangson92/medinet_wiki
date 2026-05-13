---
phase: 2
plan: 01
subsystem: app/db
tags: [sqlalchemy, async, pgvector, mixin, alembic-friendly]
dependency_graph:
  requires: []
  provides:
    - app.db.Base (DeclarativeBase với naming convention deterministic)
    - app.db.get_session (FastAPI dependency AsyncSession scope per-request)
    - app.db.init_engine / dispose_engine (lifespan hooks Phase 3)
    - app.db.UUIDMixin / TimestampMixin (tái dùng cho 7/8 model M2)
    - app.db.Vector (shim từ pgvector.sqlalchemy)
  affects:
    - Plan 02-02 (10 SQLAlchemy models inherit Base + mixins)
    - Plan 02-03 (Alembic env.py: target_metadata = Base.metadata)
    - Phase 3 Auth (lifespan wires init_engine; routers Depends(get_session))
tech_stack:
  added:
    - sqlalchemy 2.0.36+ (async API + DeclarativeBase + mapped_column)
    - pgvector.sqlalchemy.Vector (column type cho embedding)
  patterns:
    - MetaData naming convention dict (P20 mitigation Alembic drift)
    - Lazy singleton engine + sessionmaker (init lifespan startup, dispose shutdown)
    - server_default cho UUID id (`gen_random_uuid()` ext pgcrypto)
    - DateTime(timezone=True) bake TIMESTAMPTZ (kháng naive datetime trap)
key_files:
  created:
    - Hub_All/api/app/db/__init__.py
    - Hub_All/api/app/db/base.py
    - Hub_All/api/app/db/session.py
    - Hub_All/api/app/db/mixins.py
    - Hub_All/api/app/db/types.py
  modified: []
decisions:
  - D-02-01-01: server_default `gen_random_uuid()` thay vì Python `uuid4()` để concurrent INSERT không phụ thuộc Python (cần ext pgcrypto, Plan 04 migration bake)
  - D-02-01-02: `expire_on_commit=False` cho async_sessionmaker — tránh DetachedInstanceError khi access attribute sau commit (pattern async chuẩn)
  - D-02-01-03: DSN giữ prefix `postgresql+asyncpg://` cho create_async_engine (KHÔNG strip như asyncpg pool ở Plan 03 Phase 1 — SQLAlchemy hiểu prefix)
  - D-02-01-04: Vector shim `app/db/types.py` re-export thay vì import trực tiếp — tách logic versioning lib cho swap tương lai
  - D-02-01-05: `pool_size=10, max_overflow=5` đủ cho M2 <100 concurrent (PRD v1.3 target); revisit ở Phase 10 hardening nếu observ thấy pool exhaustion
metrics:
  duration_minutes: 12
  tasks_completed: 4
  files_created: 5
  files_modified: 0
  commits: 4
  completed_date: 2026-05-13
requirements_covered:
  - CORE-02 (partial — base infra; Plan 02-02 hoàn thiện model layer)
---

# Phase 2 Plan 01: SQLAlchemy declarative base + async engine + session factory + mixins — Summary

## One-liner

Dựng `app/db/` foundation cho toàn bộ Phase 2-7 — SQLAlchemy 2.0 async `Base` với MetaData naming convention (Alembic-friendly), lazy singleton async engine + sessionmaker, FastAPI dependency `get_session()` auto commit/rollback, 2 mixin tái dùng (`UUIDMixin` server-default gen_random_uuid + `TimestampMixin` TIMESTAMPTZ NOW), và `Vector` shim cho consistent import path.

## What was built

5 file mới trong `Hub_All/api/app/db/`:

| File | Mục đích | Symbol public |
|---|---|---|
| `base.py` | DeclarativeBase + NAMING_CONVENTION dict | `Base`, `NAMING_CONVENTION` |
| `session.py` | Async engine + sessionmaker + FastAPI dependency | `init_engine`, `dispose_engine`, `get_engine`, `get_session` |
| `mixins.py` | Mixin tái dùng cho mọi ORM model | `UUIDMixin`, `TimestampMixin` |
| `types.py` | Shim re-export pgvector Vector | `Vector` |
| `__init__.py` | Public API convenience re-export | (8 symbol tổng) |

**Naming convention bake vào `Base.metadata`:**

```python
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

**Engine pool config:** `pool_size=10, max_overflow=5, pool_pre_ping=True, echo=False`.

**Session config:** `expire_on_commit=False` (pattern async chuẩn — kháng DetachedInstanceError sau commit khi access attribute).

**`get_session()` lifecycle:** yield session → handler chạy → auto commit nếu không raise, rollback nếu có exception.

## Tasks executed

| # | Task | Commit | Files |
|---|---|---|---|
| 01 | `base.py` — `Base = DeclarativeBase` + NAMING_CONVENTION | `c21f0dd` | `app/db/base.py` |
| 02 | `session.py` — `init_engine` + `async_sessionmaker` + `get_session` | `7b396f8` | `app/db/session.py` |
| 03 | `mixins.py` — `UUIDMixin` + `TimestampMixin` | `7db8df1` | `app/db/mixins.py` |
| 04 | `types.py` + `__init__.py` — Vector shim + public API | `4785076` | `app/db/types.py`, `app/db/__init__.py`, `app/db/session.py` (fix) |

Tổng cộng **4 commit** atomic.

## Verification

Tất cả command verification cuối plan đã pass:

```bash
$ cd Hub_All/api && uv run python -c "from app.db import Base, get_session, UUIDMixin, TimestampMixin, Vector; print('OK')"
OK

$ cd Hub_All/api && uv run python -c "from app.db.base import Base; assert 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s' == Base.metadata.naming_convention['fk']"
(exit 0)

$ cd Hub_All/api && uv run python -c "from app.db import Base, UUIDMixin, TimestampMixin, Vector, get_session, init_engine; print(Base.__name__)"
Base

$ cd Hub_All/api && uv run ruff check app/db
All checks passed!

$ cd Hub_All/api && uv run mypy app/db
Success: no issues found in 5 source files

$ ls Hub_All/api/app/db/
__init__.py  base.py  mixins.py  session.py  types.py
```

5 file đầy đủ, ruff sạch, mypy strict pass.

## Truths achieved (Must-Haves)

- ✓ **Truth 1:** Phase 3 (Auth) có thể `from app.db.session import get_session` để inject AsyncSession vào FastAPI router — verified `get_session` import OK.
- ✓ **Truth 2:** Plan 02-02 có thể `from app.db.base import Base` + `from app.db.mixins import UUIDMixin, TimestampMixin` để định nghĩa 9 model class consistent — verified imports.
- ✓ **Truth 3:** Plan 02-03 (Alembic) có thể `from app.db.base import Base` rồi `target_metadata = Base.metadata` để autogenerate detect mọi model — verified `Base.metadata` accessible, naming convention bake đúng.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `from typing import AsyncGenerator` deprecated trong Python 3.12**

- **Found during:** Task 04 verification (chạy `uv run ruff check app/db/`)
- **Issue:** Ruff rule UP035 báo `from typing import AsyncGenerator` deprecated từ Python 3.9+; modern path là `from collections.abc import AsyncGenerator`. Plan 02-01 task 02 paste-ready dùng `typing.AsyncGenerator` (out-of-date).
- **Fix:** Edit `app/db/session.py` thay `from typing import AsyncGenerator` → `from collections.abc import AsyncGenerator`. Không thay đổi behavior, chỉ là import path modern.
- **Files modified:** `Hub_All/api/app/db/session.py`
- **Commit:** `4785076` (gộp với Task 04 vì cùng lúc phát hiện qua ruff check chạy ở task 04 acceptance criteria)

Không có Rule 2/3/4 deviation.

## Threat Model Bake

Plan 02-01 không trực tiếp implement T-02-01..05 (đó là constraint cấp model/migration — Plan 02-02 + 02-04). Tuy nhiên foundation này hỗ trợ mitigation:

- **R1 (pgvector 2000-dim limit)** — `Vector` shim trong `types.py` sẵn sàng cho Plan 02-02 model `chunks.embedding: Mapped[list[float]] = mapped_column(Vector(1536))`. Dim 1536 sẽ pin ở Plan 02-02 (KHÔNG ở plan này).
- **P20 (Alembic drift sai)** — NAMING_CONVENTION bake trong `Base.metadata` đảm bảo Plan 02-04 migration có constraint name deterministic (`fk_documents_hub_id_hubs` thay vì `documents_hub_id_fkey1`).
- **P11 (FastAPI middleware order)** — `init_engine`/`dispose_engine` định sẵn API để Plan 03-01 wire vào lifespan startup/shutdown đúng order.

T-02-01..05 (hub isolation, document cascade, refresh_tokens hash, api_keys hash, audit log accept) sẽ mitigate ở Plan 02-02 (model FK NOT NULL + UNIQUE columns) và Plan 02-04 (migration apply constraint).

## Key Decisions Made

1. **D-02-01-01 server_default uuid:** chọn `gen_random_uuid()` (Postgres-side, qua ext pgcrypto) thay vì Python `uuid4()`. Lý do: concurrent INSERT không phụ thuộc Python tốc độ, ID generation atomic ở DB. Trade-off: Plan 02-04 migration phải `CREATE EXTENSION IF NOT EXISTS pgcrypto` đầu file. Trade-off chấp nhận.
2. **D-02-01-02 expire_on_commit=False:** pattern async chuẩn để tránh `DetachedInstanceError` khi access attribute sau `session.commit()`. Với sync SQLAlchemy mặc định là `True`, nhưng async pattern khuyến nghị `False`.
3. **D-02-01-03 DSN prefix giữ nguyên:** `create_async_engine("postgresql+asyncpg://...")` HIỂU prefix; KHÔNG strip như cách Plan 03 Phase 1 phải làm cho `asyncpg.create_pool()` thuần.
4. **D-02-01-04 Vector shim:** re-export `pgvector.sqlalchemy.Vector` qua `app/db/types.py` — tách logic versioning. Lợi ích: nếu Phase 7+ cần swap pgvector→pgvecto-rs hoặc bump major version có breaking API, chỉ sửa 1 file.
5. **D-02-01-05 pool sizing:** `pool_size=10, max_overflow=5` — đủ cho M2 target <100 concurrent (PRD v1.3). Revisit ở Phase 10 hardening nếu observ thấy pool exhaustion (structlog warning `QueuePool limit ... reached`).

## Requirements Coverage

- **CORE-02 (Database foundation):** Partial — base infra (Base + session + mixins + Vector shim) sẵn sàng. Plan 02-02 (10 model class) + Plan 02-04 (migration) sẽ complete CORE-02.

## Notes for Next Plans

- **Plan 02-02 (models)** PHẢI:
  - `from app.db import Base, UUIDMixin, TimestampMixin, Vector` cho mọi model.
  - Áp dụng `UUIDMixin` + `TimestampMixin` cho 7/8 table có data row (users/hubs/documents/chunks/audit_logs/usage_events/refresh_tokens/api_keys). Bảng `alembic_version` quản bởi Alembic, KHÔNG inherit.
  - Pin `Vector(1536)` cho `chunks.embedding` (R1 mitigation).
- **Plan 02-03 (Alembic env.py)** PHẢI:
  - `from app.db.base import Base` → `target_metadata = Base.metadata` (autogenerate detect).
  - Honor naming convention đã bake (KHÔNG override `MetaData` ở `env.py`).
  - `include_object` filter ignore CocoIndex schema (`cocoindex.*`) — R5 mitigation.
- **Phase 3 Auth (lifespan)** PHẢI:
  - Lifespan startup: `init_engine(get_settings())`.
  - Lifespan shutdown: `await dispose_engine()`.
  - Router: `db: AsyncSession = Depends(get_session)`.

## Self-Check: PASSED

**Files verified exist:**
- ✓ `Hub_All/api/app/db/__init__.py`
- ✓ `Hub_All/api/app/db/base.py`
- ✓ `Hub_All/api/app/db/session.py`
- ✓ `Hub_All/api/app/db/mixins.py`
- ✓ `Hub_All/api/app/db/types.py`

**Commits verified in git log:**
- ✓ `c21f0dd` — feat(phase-02): db(base)
- ✓ `7b396f8` — feat(phase-02): db(session)
- ✓ `7db8df1` — feat(phase-02): db(mixins)
- ✓ `4785076` — feat(phase-02): db(types+init)

**Verification commands all exit 0:** ruff ✓, mypy ✓, import smoke ✓, naming convention assert ✓.
