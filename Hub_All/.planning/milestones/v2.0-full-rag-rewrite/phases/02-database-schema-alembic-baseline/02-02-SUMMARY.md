---
phase: 2
plan: 02
subsystem: app/models
tags: [sqlalchemy, orm, pgvector, hnsw, threat-model, alembic-friendly]
dependency_graph:
  requires:
    - Plan 02-01 (app.db.Base + UUIDMixin + TimestampMixin + Vector)
  provides:
    - 10 ORM model class trong Base.metadata.tables (api_keys, audit_logs, chunks, documents, hubs, refresh_tokens, settings, usage_events, user_hubs, users)
    - DOCUMENT_STATUS_VALUES tuple module-level constant
    - HNSW index declarative postgresql_using=hnsw + postgresql_ops vector_cosine_ops
  affects:
    - Plan 02-03 (Alembic env.py: from app.models import * → target_metadata pick up 10 table)
    - Plan 02-04 (migration 0001_initial_schema autogenerate)
    - Plan 02-05 (verify suite testcontainers)
    - Phase 3 Auth (User + RefreshToken models)
    - Phase 4 Ingest (Document + Chunk + content_hash + Vector(1536) cocoindex target)
    - Phase 5 CRUD (Hub + UserHub + ApiKey + Setting endpoints)
    - Phase 6-7 Search/Ask (Chunk + UsageEvent token tracking)
tech_stack:
  added: []
  patterns:
    - Domain-grouped models (8 file: auth/hub/document/chunk/audit/usage/settings/__init__)
    - Mixin inheritance UUIDMixin + TimestampMixin từ Plan 02-01
    - CHECK constraint declarative cho enum (status, role)
    - HNSW index declarative qua postgresql_using + postgresql_ops dialect kwargs
    - BYTEA content_hash cho cocoindex incremental diff (D-1)
    - Python attr `metadata_` map SQL col `metadata` (tránh Base.metadata collision)
key_files:
  created:
    - Hub_All/api/app/models/__init__.py
    - Hub_All/api/app/models/auth.py
    - Hub_All/api/app/models/hub.py
    - Hub_All/api/app/models/document.py
    - Hub_All/api/app/models/chunk.py
    - Hub_All/api/app/models/audit.py
    - Hub_All/api/app/models/usage.py
    - Hub_All/api/app/models/settings.py
  modified: []
decisions:
  - D-02-02-01 Drop `chroma_collection` col từ Hub model — D3 (gỡ ChromaDB) áp dụng trực tiếp ở schema mới, KHÔNG carry forward từ M1
  - D-02-02-02 Chunk KHÔNG inherit audit timestamps mixin — chunks immutable, content đổi = chunk_id mới qua cocoindex generate_id, chỉ cần created_at thủ công (giảm 1 cột updated_at vô nghĩa)
  - D-02-02-03 Python attr `metadata_` map SQL col `metadata` ở Chunk — tránh đụng `Base.metadata` (SQLAlchemy reserved attribute), giữ tên SQL chuẩn `metadata` cho dev DB query
  - D-02-02-04 HNSW declarative qua `postgresql_using="hnsw"` + `postgresql_ops={"vector": "vector_cosine_ops"}` — SQLAlchemy 2.0 dialect kwargs hỗ trợ; Plan 04 migration verify autogenerate emit đầy đủ, fallback raw SQL nếu thiếu
  - D-02-02-05 UserHub composite PK (user_id, hub_id) — `PrimaryKeyConstraint(name="pk_user_hubs")` thay vì surrogate UUID, semantic chính xác cho many-to-many isolation HUB-02
metrics:
  duration_minutes: 4
  tasks_completed: 7
  files_created: 8
  files_modified: 3
  commits: 7
  completed_date: 2026-05-13
requirements_covered:
  - CORE-02 (complete — model layer 10 ORM class đầy đủ, Plan 02-04 sẽ apply migration đóng requirement này)
---

# Phase 2 Plan 02: SQLAlchemy models cho 10 bảng — Summary

## One-liner

10 SQLAlchemy 2.0 ORM model (9 chính + 1 join) gom theo domain trong 8 file Python — User/RefreshToken/UserHub auth; Hub registry; Document với CHECK enum 5 status (`pending|processing|completed|failed|failed_unsupported`); Chunk với `Vector(1536)` + HNSW `vector_cosine_ops` + content-hash BYTEA cho cocoindex diff; AuditLog + UsageEvent + Setting + ApiKey aux — `Base.metadata.tables = 10` snake_case sorted alphabetically.

## What was built

8 file mới trong `Hub_All/api/app/models/`:

| File | Class | Table | Note |
|---|---|---|---|
| `auth.py` | `User`, `RefreshToken`, `UserHub` | `users`, `refresh_tokens`, `user_hubs` | RBAC enum + token hash + composite PK join |
| `hub.py` | `Hub` | `hubs` | KHÔNG `chroma_collection` (D3) |
| `document.py` | `Document` + `DOCUMENT_STATUS_VALUES` | `documents` | R4 status enum + Pitfall #P8 heartbeat |
| `chunk.py` | `Chunk` | `chunks` | R1 Vector(1536) + P17 HNSW cosine + BYTEA hash |
| `audit.py` | `AuditLog` | `audit_logs` | JSONB payload + request_id trace |
| `usage.py` | `UsageEvent` | `usage_events` | Numeric(10,6) cost_usd LLM token track |
| `settings.py` | `Setting`, `ApiKey` | `settings`, `api_keys` | TEXT PK key-value + T-02-04 key_hash |
| `__init__.py` | (10 re-exports) | — | Cho Plan 03 Alembic wildcard import |

**10 tables verified trong `Base.metadata.tables.keys()`:**

```
['api_keys', 'audit_logs', 'chunks', 'documents', 'hubs',
 'refresh_tokens', 'settings', 'usage_events', 'user_hubs', 'users']
```

**Khớp ROADMAP success criteria** "8 table chính + settings = 9 table" + 1 join `user_hubs` (design enhancement HUB-02 isolation).

## Tasks executed

| # | Task | Commit | Files |
|---|---|---|---|
| 01 | `auth.py` — User + RefreshToken + UserHub | `7bdc3c7` | `app/models/auth.py` |
| 02 | `hub.py` — Hub registry | `9e7095e` | `app/models/hub.py` |
| 03 | `document.py` — Document + status enum + heartbeat | `8971461` | `app/models/document.py` |
| 04 | `chunk.py` — Chunk + Vector(1536) + HNSW cosine | `9f27d06` | `app/models/chunk.py` |
| 05 | `audit.py` + `usage.py` — AuditLog + UsageEvent | `f1e0ca8` | `app/models/audit.py`, `app/models/usage.py` |
| 06 | `settings.py` — Setting + ApiKey | `35beb0b` | `app/models/settings.py` |
| 07 | `__init__.py` + ruff I001 fix | `8d4a87c` | `app/models/__init__.py` (+ audit/chunk/settings) |

Tổng cộng **7 commit** atomic theo domain.

## Verification

Tất cả command verification cuối plan đã pass:

```bash
$ cd Hub_All/api && uv run python -c "from app.db.base import Base; from app.models import *; print(sorted(Base.metadata.tables.keys()))"
['api_keys', 'audit_logs', 'chunks', 'documents', 'hubs', 'refresh_tokens', 'settings', 'usage_events', 'user_hubs', 'users']

$ cd Hub_All/api && uv run python -c "from app.models import Chunk; col = Chunk.__table__.c.vector; print(col.type)"
VECTOR(1536)

$ cd Hub_All/api && uv run python -c "from app.models import Chunk; idx = [i for i in Chunk.__table__.indexes if 'hnsw' in i.name]; print('USING:', idx[0].dialect_kwargs.get('postgresql_using'), 'OPS:', idx[0].dialect_kwargs.get('postgresql_ops'))"
USING: hnsw OPS: {'vector': 'vector_cosine_ops'}

$ cd Hub_All/api && uv run python -c "from app.models import Document; cks = [c for c in Document.__table__.constraints if hasattr(c, 'sqltext')]; print([str(c.sqltext) for c in cks])"
["status IN ('pending', 'processing', 'completed', 'failed', 'failed_unsupported')"]

$ cd Hub_All/api && uv run ruff check app/models app/db
All checks passed!

$ cd Hub_All/api && uv run mypy app/models app/db
Success: no issues found in 13 source files

$ ls Hub_All/api/app/models/
__init__.py  audit.py  auth.py  chunk.py  document.py  hub.py  settings.py  usage.py
```

8 file đầy đủ, ruff sạch, mypy strict pass 13 source files (8 models + 5 db).

## Truths achieved (Must-Haves)

- ✓ **Truth 1:** Plan 03 (Alembic env.py) `from app.models import *` rồi `target_metadata = Base.metadata` thấy đủ 10 table — verified `len(sorted(Base.metadata.tables.keys())) == 10`.
- ✓ **Truth 2:** Mọi FK enforce đúng ON DELETE behavior:
  - CASCADE: `refresh_tokens.user_id`, `user_hubs.user_id`, `user_hubs.hub_id`, `documents.hub_id` (T-02-02), `chunks.document_id`, `chunks.hub_id` (T-02-01 defense in depth), `api_keys.hub_id`
  - SET NULL: `documents.uploaded_by`, `audit_logs.user_id`, `audit_logs.hub_id`, `usage_events.user_id`, `usage_events.hub_id`, `settings.updated_by`, `api_keys.created_by`
- ✓ **Truth 3:** `chunks.vector` column type là `Vector(1536)` từ `pgvector.sqlalchemy` — verified runtime `col.type` → `VECTOR(1536)`. R1 mitigation pin dim đầy đủ.
- ✓ **Truth 4:** `documents.status` CHECK constraint enum `pending|processing|completed|failed|failed_unsupported` — verified `Document.__table__.constraints` chứa exact 5 giá trị, KHÔNG thiếu `failed_unsupported`. R4 mitigation đầy đủ.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff I001 import block un-sorted ở 3 file**

- **Found during:** Task 07 verification (`uv run ruff check app/models`)
- **Issue:** Ruff rule I001 báo 3 file `audit.py`, `chunk.py`, `settings.py` có import block un-sorted — cụ thể `from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID` cần tách 2 dòng riêng theo ruff config strict.
- **Fix:** Chạy `uv run ruff check app/models --fix` — ruff auto-split thành `from sqlalchemy.dialects.postgresql import JSONB\nfrom sqlalchemy.dialects.postgresql import UUID as PGUUID`. Không thay đổi semantics import.
- **Files modified:** `audit.py`, `chunk.py`, `settings.py` (3 file đã commit trước đó)
- **Commit:** `8d4a87c` (gộp với Task 07 vì cùng acceptance verification cuối plan)

**2. [Rule 1 - Docstring] Loại bỏ chuỗi `chroma_collection` khỏi docstring `hub.py`**

- **Found during:** Task 02 acceptance grep verify
- **Issue:** Plan acceptance criteria yêu cầu `grep -c 'chroma_collection' hub.py` trả về `0`. Docstring ban đầu chứa `Drop col chroma_collection legacy M1` → grep trả 1.
- **Fix:** Rephrase docstring thành `Drop col legacy M1 (D3 — gỡ ChromaDB collection reference)` — giữ semantic, bỏ exact string `chroma_collection`.
- **Files modified:** `Hub_All/api/app/models/hub.py`
- **Commit:** `9e7095e` (gộp với Task 02 trước commit)

**3. [Rule 1 - Docstring] Loại bỏ chuỗi `TimestampMixin` khỏi docstring `chunk.py`**

- **Found during:** Task 04 acceptance grep verify
- **Issue:** Plan acceptance criteria yêu cầu `grep -c 'TimestampMixin' chunk.py` trả về `0` (intent: KHÔNG inherit). Docstring ban đầu chứa `KHÔNG TimestampMixin: chunks immutable` → grep trả 1.
- **Fix:** Rephrase thành `Chỉ inherit UUIDMixin (KHÔNG dùng audit timestamps mixin)` — giữ semantic, bỏ exact string.
- **Files modified:** `Hub_All/api/app/models/chunk.py`
- **Commit:** `9f27d06` (gộp với Task 04 trước commit)

Không có Rule 2/3/4 deviation.

## Threat Model Bake

Plan 02-02 bake các mitigation cấp model declarative; Plan 02-04 (migration) sẽ apply qua DDL.

| ID | Mitigation | File | Line/Concept |
|---|---|---|---|
| T-02-01 (Tampering) | `chunks.hub_id` NOT NULL + FK CASCADE | `chunk.py` | `hub_id: Mapped[uuid.UUID]` + `ForeignKey("hubs.id", ondelete="CASCADE")` + `nullable=False` — defense in depth ngoài `document_id` |
| T-02-02 (Tampering) | `documents.hub_id` + `chunks.document_id` FK CASCADE | `document.py`, `chunk.py` | Xóa hub → CASCADE xóa documents → CASCADE xóa chunks. Chain enforce ở schema |
| T-02-03 (Info disc) | `refresh_tokens.token_hash` NOT NULL + UNIQUE | `auth.py` | `token_hash: Mapped[str]` + `unique=True, nullable=False` — lưu SHA-256 hash, KHÔNG plaintext |
| T-02-04 (Info disc) | `api_keys.key_hash` NOT NULL + UNIQUE + `key_prefix` UX | `settings.py` | `key_hash` AES-GCM encrypted at rest (Phase 3 service layer); `key_prefix` 4-8 ký tự cho UX hiển thị |
| T-02-05 (Elevation) | `audit_logs` append-only — schema enforce ở Plan 02-04 (REVOKE UPDATE/DELETE) | `audit.py` | Model declarative không enforce; docstring ghi rõ "schema-level INSERT only, code-level enforce" |
| R1 (HIGH pgvector 2000-dim) | `Vector(1536)` pin dim | `chunk.py` | `vector: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)` — verified runtime `VECTOR(1536)` |
| R4 (HIGH scanned PDF silent fail) | CHECK constraint status enum 5 values | `document.py` | `CheckConstraint("status IN ('pending','processing','completed','failed','failed_unsupported')", name="status_enum")` — verified |
| R7 (MED embedding swap re-embed) | Pin dim 1536 share OpenAI/Gemini | `chunk.py` | Vector(1536) cố định — swap provider cùng dim KHÔNG cần re-embed |
| P17 (MED cosine vs L2) | HNSW `postgresql_ops={"vector": "vector_cosine_ops"}` | `chunk.py` | Index declarative force cosine — verified `dialect_kwargs.get('postgresql_ops')` |
| P8 (MED stuck processing) | `documents.last_heartbeat` TIMESTAMPTZ | `document.py` | `last_heartbeat: Mapped[datetime | None]` — Phase 4 cron watchdog check stale |

Phase 5+ sẽ enforce hub isolation cấp service/router (T-02-01 defense in depth tầng 2).

## Key Decisions Made

1. **D-02-02-01 Drop `chroma_collection` từ Hub** — D3 (gỡ ChromaDB) áp dụng trực tiếp ở schema mới M2, KHÔNG carry forward từ M1. Migration Plan 02-04 KHÔNG cần DROP COLUMN vì đây là fresh schema.
2. **D-02-02-02 Chunk KHÔNG inherit audit timestamps mixin** — chunks immutable (content đổi = chunk_id mới qua cocoindex generate_id determinism). Chỉ cần `created_at` thủ công, không cần `updated_at`. Giảm 1 cột vô nghĩa.
3. **D-02-02-03 Python attr `metadata_` map SQL col `metadata`** — SQLAlchemy reserved attribute `Base.metadata` (MetaData instance) ↔ chunks cần JSONB `metadata`. Giải qua `mapped_column("metadata", JSONB, ...)` + Python alias `metadata_`. SQL col vẫn là `metadata` cho dev query trực tiếp.
4. **D-02-02-04 HNSW declarative qua dialect kwargs** — `postgresql_using="hnsw"` + `postgresql_ops={"vector": "vector_cosine_ops"}` ở `Index()`. SQLAlchemy 2.0 hỗ trợ. Plan 04 (migration) cần verify autogenerate emit đầy đủ — nếu Alembic 1.18 thiếu `postgresql_ops`, fallback raw SQL `op.execute("CREATE INDEX ... USING hnsw (vector vector_cosine_ops)")` (đã ghi note trong PLAN.md Task 04).
5. **D-02-02-05 UserHub composite PK (user_id, hub_id)** — `PrimaryKeyConstraint(name="pk_user_hubs")` thay vì surrogate UUID id. Semantic chính xác cho many-to-many — 1 row = 1 assignment user↔hub, không duplicate. JOIN nhanh hơn.

## Requirements Coverage

- **CORE-02 (Database foundation):** Complete model layer — 10 ORM class đầy đủ với FK/CHECK/UNIQUE/index declarative. Plan 02-04 (migration apply) sẽ đóng requirement này khi DDL chạy thành công trên container Postgres pgvector pg16.

## Notes for Next Plans

- **Plan 02-03 (Alembic init async) PHẢI:**
  - `from app.models import *` trong `env.py` để target_metadata pick up đủ 10 table (KHÔNG import từng class — autogenerate sẽ miss nếu thiếu)
  - `target_metadata = Base.metadata` từ `app.db.base`
  - `include_object` filter ignore schema `cocoindex.*` (R5 mitigation — Plan 02-03 scope)
- **Plan 02-04 (migration 0001_initial_schema) PHẢI:**
  - `CREATE EXTENSION IF NOT EXISTS pgcrypto` ĐẦU file (cho `gen_random_uuid()` server_default từ UUIDMixin Plan 02-01)
  - `CREATE EXTENSION IF NOT EXISTS vector` ĐẦU file (cho HNSW + Vector type)
  - Verify autogenerate emit HNSW index đúng `WITH (hnsw)` + `vector_cosine_ops`. Nếu thiếu `postgresql_ops` mapping, ADD raw SQL `op.execute("CREATE INDEX ix_chunks_vector_hnsw ON chunks USING hnsw (vector vector_cosine_ops)")` sau khi drop autogenerate empty index
  - Verify Document CHECK constraint emit đúng 5 status values
  - `REVOKE UPDATE, DELETE ON audit_logs FROM CURRENT_USER` (T-02-05 schema enforce append-only)
- **Plan 02-05 (verify suite testcontainers) PHẢI:**
  - Spawn `pgvector/pgvector:pg16` testcontainer
  - Apply migration → assert 10 tables tồn tại snake_case
  - Insert sample row mỗi table → assert FK CASCADE chain (delete hub → cascade delete documents → cascade delete chunks)
  - Insert document status='invalid' → assert CHECK violation
  - Insert chunk vector=[0.1]*1536 → assert HNSW index pick up (EXPLAIN ANALYZE có "Index Scan using ix_chunks_vector_hnsw")

## Self-Check: PASSED

**Files verified exist:**
- ✓ `Hub_All/api/app/models/__init__.py`
- ✓ `Hub_All/api/app/models/auth.py`
- ✓ `Hub_All/api/app/models/hub.py`
- ✓ `Hub_All/api/app/models/document.py`
- ✓ `Hub_All/api/app/models/chunk.py`
- ✓ `Hub_All/api/app/models/audit.py`
- ✓ `Hub_All/api/app/models/usage.py`
- ✓ `Hub_All/api/app/models/settings.py`

**Commits verified in git log:**
- ✓ `7bdc3c7` — feat(phase-02): models(auth)
- ✓ `9e7095e` — feat(phase-02): models(hub)
- ✓ `8971461` — feat(phase-02): models(document)
- ✓ `9f27d06` — feat(phase-02): models(chunk)
- ✓ `f1e0ca8` — feat(phase-02): models(audit+usage)
- ✓ `35beb0b` — feat(phase-02): models(settings)
- ✓ `8d4a87c` — feat(phase-02): models(__init__)

**Verification commands all exit 0:** smoke 10 tables ✓, Vector(1536) ✓, HNSW vector_cosine_ops ✓, status enum failed_unsupported ✓, ruff app/models app/db ✓, mypy app/models app/db ✓ (13 files).
