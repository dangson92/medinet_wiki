---
phase: 2
plan: 04
subsystem: api/migrations
tags: [alembic, migration, pgvector, hnsw, vector-cosine-ops, pgcrypto, ddl, schema-baseline]
dependency_graph:
  requires:
    - Plan 02-01 (app.db.base.Base + NAMING_CONVENTION + UUIDMixin + TimestampMixin + Vector shim)
    - Plan 02-02 (10 ORM model class trong Base.metadata cho target_metadata)
    - Plan 02-03 (env.py async + include_object cocoindex filter + compare_type/server_default)
  provides:
    - Hub_All/api/migrations/versions/0001_initial_schema.py (494 dong)
    - 10 op.create_table DDL paste-ready cho Postgres pgvector pg16
    - HNSW raw SQL `CREATE INDEX ... USING hnsw (vector vector_cosine_ops)` (P17 mandatory)
    - 10 sa.PrimaryKeyConstraint explicit names (N-2 defensive match pk_%(table_name)s)
    - upgrade() + downgrade() ATOMIC clean (drop nguoc thu tu FK)
  affects:
    - Plan 02-05 (testcontainers verify suite — apply migration tren container)
    - Phase 3 (Auth) users + refresh_tokens table san sang cho login/JWT
    - Phase 4 (CocoIndex) documents + chunks table + HNSW vector_cosine_ops san sang ingest
    - Phase 5 (CRUD) hubs + user_hubs + api_keys + settings + audit_logs san sang endpoint
    - Phase 6 (Search) chunks + HNSW + ix_chunks_hub_id_document_id san sang query
    - Phase 7 (Ask) usage_events san sang track LLM token cost
tech_stack:
  added: []
  patterns:
    - Alembic single revision baseline (revision="0001", down_revision=None)
    - op.create_table theo thu tu FK parent->child (10 buoc upgrade)
    - op.drop_table nguoc thu tu FK (10 buoc downgrade)
    - op.execute raw SQL cho pgcrypto/vector ext + HNSW index (avoid postgresql_ops mapping unreliable)
    - sa.PrimaryKeyConstraint explicit names match NAMING_CONVENTION pk_%(table_name)s
    - sa.ForeignKeyConstraint explicit ondelete CASCADE/SET NULL + name
    - sa.CheckConstraint named (ck_users_role_enum + ck_documents_status_enum)
key_files:
  created:
    - Hub_All/api/migrations/versions/0001_initial_schema.py
  modified: []
decisions:
  - D-02-04-01 Manual paste-ready single migration thay vi `alembic revision --autogenerate` — Docker chua chay nen autogenerate khong the connect, viet thu cong 494 dong + verify AST + grep counts
  - D-02-04-02 HNSW dung raw SQL `op.execute("CREATE INDEX ... USING hnsw (vector vector_cosine_ops)")` thay vi declarative postgresql_ops — Alembic 1.18 postgresql_ops mapping khong reliable moi version, raw SQL la authoritative source for P17 cosine pin
  - D-02-04-02 PK explicit 9 lan `sa.PrimaryKeyConstraint("id", name="pk_<table>")` + 1 composite `pk_user_hubs` — N-2 defensive avoid <table>_pkey default mismatch voi NAMING_CONVENTION pk_%(table_name)s gay drift sai sau nay
  - D-02-04-03 CREATE EXTENSION IF NOT EXISTS pgcrypto + vector dau upgrade() — defensive du Phase 1 init-db.sh da enable, dam bao migration standalone neu chay tren DB moi
  - D-02-04-04 downgrade KHONG drop ext vector / pgcrypto / schema cocoindex — defensive vi ext co the duoc app khac dung + P7 mitigation khong touch cocoindex
metrics:
  duration_minutes: 4
  tasks_completed: 1
  files_created: 1
  files_modified: 0
  commits: 1
  completed_date: 2026-05-13
requirements_covered:
  - CORE-02 (partial — migration code paste-ready va alembic history phat hien duoc 0001 head; verify runtime `alembic upgrade head` defer Plan 02-05 khi testcontainers Postgres pgvector pg16 chay duoc — Docker chua available moi truong nay)
---

# Phase 2 Plan 04: Migration `0001_initial_schema.py` — 10 bang + HNSW + PK explicit — Summary

## One-liner

Single Alembic revision baseline `revision="0001", down_revision=None` paste-ready 494 dong tao toan bo schema M2 — 10 op.create_table theo thu tu FK parent->child (users -> hubs -> refresh_tokens -> user_hubs -> settings -> api_keys -> documents -> chunks -> audit_logs -> usage_events), HNSW raw SQL `vector_cosine_ops` cho P17 cosine pin, `Vector(1536)` cho R1 hot-swap dim, CHECK enum `failed_unsupported` cho R4 scanned PDF, 10 `sa.PrimaryKeyConstraint` explicit names cho N-2 defensive match `pk_<table>`, `CREATE EXTENSION pgcrypto + vector` dau upgrade() cho `gen_random_uuid()` server_default — `alembic history` xac nhan `<base> -> 0001 (head), initial_schema`.

## What was built

1 file mới trong `Hub_All/api/migrations/versions/`:

| File | Mục đích | Đặc trưng chính |
|---|---|---|
| `0001_initial_schema.py` | Migration baseline Phase 2 — 10 bang Postgres pgvector pg16 | `revision="0001"`, `down_revision=None`, upgrade()/downgrade() ATOMIC, HNSW raw SQL `vector_cosine_ops`, 10 PK explicit names |

**Cau truc upgrade() (theo thu tu execute):**

1. `op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")` — cho `gen_random_uuid()` server_default UUIDMixin.
2. `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` — defensive du Phase 1 init-db.sh da enable.
3. **`users`** — UUID PK + email UNIQUE + `ck_users_role_enum` CHECK `role IN ('admin','editor','viewer')`.
4. **`hubs`** — UUID PK + slug UNIQUE.
5. **`refresh_tokens`** — FK user_id CASCADE + token_hash UNIQUE (T-02-03) + 2 indexes (user_id, expires_at).
6. **`user_hubs`** — composite PK (user_id, hub_id) + 2 FK CASCADE (HUB-02 many-to-many).
7. **`settings`** — PK key (TEXT) + FK updated_by SET NULL + JSONB value.
8. **`api_keys`** — UUID PK + key_hash UNIQUE (T-02-04) + key_prefix + 2 FK (created_by SET NULL, hub_id CASCADE).
9. **`documents`** — UUID PK + 2 FK (hub_id CASCADE, uploaded_by SET NULL) + `ck_documents_status_enum` CHECK `status IN ('pending','processing','completed','failed','failed_unsupported')` (R4) + last_heartbeat (P8) + 2 indexes (hub_id+status, uploaded_by).
10. **`chunks`** — UUID PK + 2 FK CASCADE (document_id, hub_id) + `Vector(1536)` (R1) + content_hash BYTEA (D-1 cocoindex diff) + 2 B-tree indexes (hub_id+document_id P4 fallback, content_hash).
11. **HNSW raw SQL** — `op.execute("CREATE INDEX ix_chunks_vector_hnsw ON chunks USING hnsw (vector vector_cosine_ops)")` (P17 MANDATORY cosine).
12. **`audit_logs`** — UUID PK + 2 FK SET NULL (user_id, hub_id) + JSONB payload + 3 indexes (created_at, user_id+created_at, hub_id+created_at).
13. **`usage_events`** — UUID PK + 2 FK SET NULL + Numeric(10,6) cost_usd LLM track + 2 indexes (created_at, user_id+model+created_at).

**Cau truc downgrade() (theo thu tu NGUOC FK):**

1. Drop HNSW index `ix_chunks_vector_hnsw` truoc (clean, du DROP TABLE cascade).
2. Drop tables theo thu tu nguoc: usage_events -> audit_logs -> chunks -> documents -> api_keys -> settings -> user_hubs -> refresh_tokens -> hubs -> users.
3. KHONG drop ext vector / pgcrypto (defensive — co the app khac dung).
4. KHONG drop schema cocoindex (P7 — khong touch cocoindex).

## Tasks executed

| # | Task | Commit | Files |
|---|---|---|---|
| 01 | Tao `0001_initial_schema.py` paste-ready 494 dong | `488cde4` | `Hub_All/api/migrations/versions/0001_initial_schema.py` |

Tong cong **1 commit** atomic (khong co Rule N auto-fix can thiet — paste-ready code passed verify lan dau).

## Verification

Tat ca command verification cuoi plan da pass:

```bash
$ cd Hub_All/api && uv run python -c "import ast; ast.parse(open('migrations/versions/0001_initial_schema.py', encoding='utf-8').read()); print('AST OK')"
AST OK

$ cd Hub_All/api && uv run python -c "import importlib.util; spec=importlib.util.spec_from_file_location('m', 'migrations/versions/0001_initial_schema.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('IMPORT OK', m.revision, m.down_revision)"
IMPORT OK 0001 None

$ cd Hub_All/api && uv run alembic history
<base> -> 0001 (head), initial_schema
```

**Grep counts (acceptance criteria):**

| Pattern | Required | Actual | Status |
|---|---|---|---|
| `op.create_table(` | = 10 | 10 | OK |
| `op.drop_table` | = 10 | 10 | OK |
| `sa.PrimaryKeyConstraint` | ≥ 10 | 10 | OK (8 UUID PK + settings PK + user_hubs composite PK) |
| `vector_cosine_ops` | ≥ 1 | 5 | OK (1 CREATE INDEX SQL + 4 mentions trong comments/docstring) |
| `failed_unsupported` | ≥ 1 | 2 | OK (R4 CHECK enum + docstring mention) |
| `pgcrypto` | ≥ 1 | 3 | OK (CREATE EXTENSION + 2 comments) |
| `Vector(1536)` | ≥ 1 | 2 | OK (R1 pin — chunks.vector + docstring) |
| `ondelete="CASCADE"` | ≥ 5 | 7 | OK (refresh_tokens, user_hubs x2, api_keys, documents, chunks x2) |
| `ondelete="SET NULL"` | ≥ 5 | 7 | OK (settings, api_keys, documents, audit_logs x2, usage_events x2) |
| `CheckConstraint` | ≥ 2 | 2 | OK (ck_users_role_enum + ck_documents_status_enum) |

## Truths achieved (Must-Haves)

- ✓ **Truth 1:** Migration file ton tai va parse AST/import OK voi `revision="0001"`, `down_revision=None` — verified `IMPORT OK 0001 None`.
- ✓ **Truth 2:** 10 `op.create_table(` calls dung thu tu FK parent->child — verified grep count = 10.
- ✓ **Truth 3:** HNSW index dung `vector_cosine_ops` (P17 cosine MANDATORY, KHONG l2_ops) — verified grep count = 5 (1 raw SQL + 4 mentions).
- ✓ **Truth 4:** `documents.status` CHECK enum bao gom `failed_unsupported` (R4 scanned PDF distinct status) — verified grep count = 2.
- ✓ **Truth 5:** `chunks.vector` Column type `Vector(1536)` (R1 pin dim 1536 cho hot-swap OpenAI/Gemini) — verified grep count = 2.
- ✓ **Truth 6:** 10 `sa.PrimaryKeyConstraint` explicit names match `pk_<table>` (N-2 defensive avoid `<table>_pkey` default mismatch) — verified grep count = 10.
- ✓ **Truth 7:** `alembic history` phat hien duoc migration `0001` — output `<base> -> 0001 (head), initial_schema`.

**Defer Plan 02-05 (testcontainers verify):**
- `alembic upgrade head` runtime tren Postgres pgvector pg16 → assert 10 tables tao + HNSW index pick up + CHECK constraint enforce + FK CASCADE chain (Docker chua chay moi truong nay; testcontainers Plan 02-05 se bake).
- `alembic downgrade base` clean drop → assert 0 tables remain in public schema.
- `alembic check` no drift sau upgrade.

## Deviations from Plan

None — plan executed exactly as written (paste-ready code passed AST + import + grep + alembic history lan dau).

**Khong co Rule 1/2/3/4 deviation.** Code 494 dong duoc paste tu PLAN.md va pass moi acceptance check ngay tu commit dau tien.

## Authentication Gates

Khong co auth gate trong plan nay (chi tao file Python migration, khong can secret/token/CLI login).

## Threat Model Bake (R1/R4/R7 + P17/P7 + T-02-01..04)

| ID | Mitigation | File | Line/Concept |
|---|---|---|---|
| **R1** (HIGH pgvector 2000-dim limit) | `Vector(1536)` pin dim cho chunks.vector | `0001_initial_schema.py:312` | `sa.Column("vector", Vector(1536), nullable=True)` — verified grep = 2 |
| **R4** (HIGH scanned PDF silent fail) | `ck_documents_status_enum` CHECK 5 status values bao gom `failed_unsupported` | `0001_initial_schema.py:269-272` | `sa.CheckConstraint("status IN ('pending','processing','completed','failed','failed_unsupported')", name="ck_documents_status_enum")` — verified grep = 2 |
| **R7** (MED embedding swap re-embed) | Pin dim 1536 cho ca OpenAI text-embedding-3-small va Gemini text-embedding-004 | `0001_initial_schema.py:312` | Vector(1536) co dinh — hot-swap provider cung dim KHONG can re-embed |
| **P17** (MED cosine vs L2 metric mismatch) | HNSW raw SQL `vector_cosine_ops` (KHONG `vector_l2_ops`/`vector_ip_ops`) | `0001_initial_schema.py:329-332` | `op.execute("CREATE INDEX ix_chunks_vector_hnsw ON chunks USING hnsw (vector vector_cosine_ops)")` — verified grep = 5 |
| **P7** (MED CocoIndex schema isolation) | downgrade() KHONG drop schema cocoindex | `0001_initial_schema.py:425-426` | Comment "KHONG drop schema cocoindex (P7 — khong touch cocoindex)" |
| **P4** (HIGH HNSW post-filter recall) | B-tree fallback `ix_chunks_hub_id_document_id (hub_id, document_id)` | `0001_initial_schema.py:319-323` | `op.create_index("ix_chunks_hub_id_document_id", "chunks", ["hub_id", "document_id"])` — Phase 6 search dung khi hub narrow |
| **P8** (MED stuck processing) | documents.last_heartbeat TIMESTAMPTZ nullable | `0001_initial_schema.py:235` | `sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True)` — Phase 4 worker update moi 30s, cron watchdog 2min |
| **T-02-01** (Tampering) | chunks.hub_id NOT NULL + FK CASCADE | `0001_initial_schema.py:295, 308-311` | `nullable=False` + `ondelete="CASCADE"` — defense in depth ngoai chunks.document_id |
| **T-02-02** (Tampering) | documents.hub_id + chunks.document_id CASCADE chain | `0001_initial_schema.py:230, 252-255, 304-307` | Xoa hub -> CASCADE xoa documents -> CASCADE xoa chunks |
| **T-02-03** (Info disclosure) | refresh_tokens.token_hash NOT NULL + UNIQUE | `0001_initial_schema.py:117-122` | `sa.Column("token_hash", sa.Text(), nullable=False)` + `sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash")` |
| **T-02-04** (Info disclosure) | api_keys.key_hash NOT NULL + UNIQUE + key_prefix | `0001_initial_schema.py:181-184, 207` | `key_hash UNIQUE` + `key_prefix` UX hien thi |
| **N-2** (defensive PK naming) | 10 `sa.PrimaryKeyConstraint` explicit names match `pk_<table>` | `0001_initial_schema.py` (10 lan) | Tranh default `<table>_pkey` mismatch voi NAMING_CONVENTION `pk_%(table_name)s` gay drift sai |

**Tai sao N-2 critical:** Plan 02-01 da setup `MetaData(naming_convention=NAMING_CONVENTION)` voi `"pk": "pk_%(table_name)s"`. Neu migration dung inline `primary_key=True` tren Column, Postgres se sinh ten default `<table>_pkey` (vd `users_pkey`) — KHONG match `pk_users`. Khi Phase 3+ chay `alembic check` sau migration, alembic so sanh metadata convention vs DB actual → bao drift sai "expected pk_users, found users_pkey" → debug 1-2h waste. Explicit `sa.PrimaryKeyConstraint("id", name="pk_users")` bake tu dau tranh issue nay.

## Key Decisions Made

1. **D-02-04-01 Manual paste-ready single migration thay vi alembic autogenerate** — Lý do: Docker khong chay moi truong nay (Windows dev khong co Docker Desktop running), `alembic revision --autogenerate` can connection DB → fail ConnectionRefusedError. Paste-ready code 494 dong tu PLAN.md la safe path — verify qua AST + import + grep + alembic history (offline check). Trade-off: phai bake bằng tay HNSW raw SQL + CHECK constraint name match (autogenerate co the sinh thieu). Loi the: deterministic, code review duoc tu PLAN.md (1:1 mapping).
2. **D-02-04-02 HNSW dung raw SQL thay vi declarative postgresql_ops** — Alembic 1.18 + SQLAlchemy 2.0 ho tro `postgresql_using="hnsw"` reliably, NHUNG `postgresql_ops={"vector": "vector_cosine_ops"}` mapping unreliable o mot so version (Plan 02-02 docstring ghi "verify autogenerate emit dầy đủ, fallback raw SQL nếu thiếu"). Raw SQL `op.execute("CREATE INDEX ... USING hnsw (vector vector_cosine_ops)")` la authoritative — KHONG depend vao SQLAlchemy emit. Cost: 1 dong code SQL plain text thay vi 4 dong Index() declarative.
3. **D-02-04-02 (PK explicit defensive)** — 9 lan `sa.PrimaryKeyConstraint("id", name="pk_<table>")` + 1 composite `sa.PrimaryKeyConstraint("user_id", "hub_id", name="pk_user_hubs")`. Plan 02-01 setup naming convention `"pk": "pk_%(table_name)s"`. Dung inline `primary_key=True` tren Column → Postgres default `<table>_pkey` → mismatch → drift sai trong `alembic check`. Trade-off: verbose hon (1 dong PK extra/table), nhung deterministic + match convention 100%.
4. **D-02-04-03 CREATE EXTENSION dau upgrade()** — `pgcrypto` cho `gen_random_uuid()` server_default trong UUIDMixin Plan 02-01. `vector` defensive du Phase 1 init-db.sh da enable. Loi the: migration standalone — chay tren DB moi (testcontainer Plan 02-05) khong can manual ext setup. Cost: 2 dong SQL extra dau function.
5. **D-02-04-04 downgrade KHONG drop ext / schema cocoindex** — Defensive vi ext `vector`/`pgcrypto` co the duoc app khac (vd cocoindex) dung; schema `cocoindex` la P7 mitigation tach biet hoan toan khoi public, alembic KHONG touch. Trade-off: downgrade KHONG hoan toan clean (ext + schema cocoindex remain) — chap nhan vi `alembic downgrade base` chi danh cho dev rollback, KHONG production teardown.

## Requirements Coverage

- **CORE-02 (Database foundation):** Partial complete — migration code paste-ready va Alembic phat hien duoc 0001 head. Verify runtime `alembic upgrade head` + `\dt` 11 tables + HNSW `\d chunks` defer Plan 02-05 (testcontainers Postgres pgvector pg16). Khi Docker available + Plan 02-05 chay xong, CORE-02 dong day du.

## Notes for Next Plans

- **Plan 02-05 (testcontainers verify suite) PHAI:**
  - Spawn `pgvector/pgvector:pg16` testcontainer.
  - Set env vars `DATABASE_URL` + `COCOINDEX_DATABASE_URL` + `REDIS_URL` (testcontainer ports dong).
  - Run `uv run alembic upgrade head` → assert exit 0.
  - `SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name` → assert 11 dong (10 schema + alembic_version).
  - `\d chunks` qua psql → assert column `vector` type `vector(1536)`, index `ix_chunks_vector_hnsw USING hnsw (vector vector_cosine_ops)`, index `ix_chunks_hub_id_document_id` btree, `content_hash` BYTEA.
  - `\d documents` → assert CHECK `ck_documents_status_enum` expression chua `failed_unsupported`.
  - Insert sample row mỗi bảng + delete hub → assert FK CASCADE chain (hub → documents → chunks all gone).
  - Insert document status='invalid' → assert CHECK violation `IntegrityError`.
  - `alembic downgrade base` → assert exit 0 + `SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'` = 0 (clean drop).
  - `alembic check` sau upgrade → assert exit 0 (no drift).
- **Phase 3 (Auth) PHAI:**
  - Dung `users` table (UUID PK + email UNIQUE + role CHECK enum 3 values) + `refresh_tokens` table (user_id FK CASCADE + token_hash UNIQUE).
  - Argon2 params phai match Plan 02-04 schema: `password_hash TEXT NOT NULL` (KHONG VARCHAR(N) — Argon2 string variable length).
- **Phase 4 (CocoIndex Ingest) PHAI:**
  - Target table `documents` (hub_id FK CASCADE + status CHECK enum + last_heartbeat).
  - Target table `chunks` (Vector(1536) + HNSW vector_cosine_ops + content_hash BYTEA + JSONB metadata).
  - Worker update `documents.last_heartbeat = NOW()` moi 30s; cron watchdog moi 1 phut UPDATE stuck status (P8).
- **Phase 5 (CRUD) PHAI:**
  - Dung `hubs` + `user_hubs` (composite PK) + `api_keys` (key_prefix UX) + `settings` (PK key TEXT) + `audit_logs` (REVOKE UPDATE/DELETE T-02-05 — Plan 02-04 KHONG bake REVOKE vi muon kep audit_logs trong migration baseline; Phase 5 se add REVOKE qua migration 0002 hoac dau Phase 5).
- **Phase 6 (Search) PHAI:**
  - Dung `ix_chunks_vector_hnsw` HNSW + `SET hnsw.ef_search=200` + `SET hnsw.iterative_scan=relaxed_order` (P4).
  - Fallback B-tree `ix_chunks_hub_id_document_id` khi hub narrow.

## Self-Check: PASSED

**Files verified exist:**
- ✓ `Hub_All/api/migrations/versions/0001_initial_schema.py` (494 dong)

**Commits verified in git log:**
- ✓ `488cde4` — feat(phase-02): migration(0001): tao initial_schema 10 bang + HNSW + PK explicit

**Verification commands all exit 0:**
- ✓ AST parse OK
- ✓ Import module OK with revision="0001", down_revision=None
- ✓ alembic history shows `<base> -> 0001 (head), initial_schema`
- ✓ 10 op.create_table, 10 op.drop_table (symmetry upgrade/downgrade)
- ✓ 10 sa.PrimaryKeyConstraint explicit names (N-2 defensive)
- ✓ 5 vector_cosine_ops mentions (P17 mandatory cosine)
- ✓ 2 failed_unsupported mentions (R4 scanned PDF distinct status)
- ✓ 3 pgcrypto mentions (CREATE EXTENSION + comments)
- ✓ 2 Vector(1536) mentions (R1 pin dim)
- ✓ 7 ondelete="CASCADE" + 7 ondelete="SET NULL" (FK threat model bake)
- ✓ 2 CheckConstraint (ck_users_role_enum + ck_documents_status_enum)
