---
phase: 2
plan: 03
subsystem: api/migrations
tags: [alembic, async, autogenerate, schema-filter, drift-detection]
dependency_graph:
  requires:
    - Plan 02-01 (app.db.base.Base + NAMING_CONVENTION + Vector shim)
    - Plan 02-02 (10 ORM model class re-exported qua app.models.__init__)
  provides:
    - Hub_All/api/alembic.ini (config với DSN inject runtime, KHÔNG hardcode sqlalchemy.url)
    - Hub_All/api/migrations/env.py (async runtime + include_object P7 + compare_type/server_default P20)
    - Hub_All/api/migrations/script.py.mako (template chuẩn cho migration mới)
    - Hub_All/api/migrations/__init__.py + versions/.gitkeep (package scaffold)
    - Hub_All/api/scripts/alembic-smoke.sh (3-step smoke verify)
  affects:
    - Plan 02-04 (alembic revision --autogenerate sinh 0001_initial_schema dùng env.py này)
    - Plan 02-05 (testcontainers chạy alembic upgrade head qua env.py này)
    - Phase 4 (cocoindex tự quản schema 'cocoindex' — include_object filter đã exclude)
tech_stack:
  added: []
  patterns:
    - Alembic async runtime (async_engine_from_config + asyncio.run + connection.run_sync)
    - DSN inject runtime qua config.set_main_option (KHÔNG hardcode trong alembic.ini)
    - include_object callback filter exclude schema 'cocoindex' (P7 mitigation)
    - compare_type=True + compare_server_default=True ở cả online + offline mode (P20)
    - alembic.ini ASCII thuần để tránh configparser locale codec crash trên Windows
key_files:
  created:
    - Hub_All/api/alembic.ini
    - Hub_All/api/migrations/__init__.py
    - Hub_All/api/migrations/env.py
    - Hub_All/api/migrations/script.py.mako
    - Hub_All/api/migrations/versions/.gitkeep
    - Hub_All/api/scripts/alembic-smoke.sh
  modified: []
decisions:
  - D-02-03-01 alembic.ini KHÔNG hardcode sqlalchemy.url — env.py inject runtime qua config.set_main_option để mỗi env (dev/test/prod) dùng DSN riêng từ get_settings()
  - D-02-03-02 include_object filter dùng hasattr check (object_.schema attribute) thay vì isinstance(Table) — generic hơn, áp dụng cho cả Table + Index + Constraint nếu sau có cocoindex schema
  - D-02-03-03 compare_type + compare_server_default bake CẢ online + offline mode — Plan 04 có thể generate SQL offline để review trước khi apply, drift detect phải nhất quán 2 mode
  - D-02-03-04 alembic.ini comment ASCII thuần — Windows cp1252 configparser KHÔNG decode được em-dash/Vietnamese diacritics, comment tiếng Việt giữ trong env.py docstring (Python UTF-8)
  - D-02-03-05 file_template với timestamp prefix `%(year)d_%(month).2d_...` — file migration list theo thứ tự thời gian tự nhiên trong filesystem (KHÔNG cần xem ngày commit Git)
metrics:
  duration_minutes: 8
  tasks_completed: 5
  files_created: 6
  files_modified: 1
  commits: 6
  completed_date: 2026-05-13
requirements_covered:
  - CORE-02 (partial — Alembic baseline cho phép Plan 04 sinh migration apply 10 table; CORE-02 đóng khi Plan 04 verify upgrade head trên Postgres pgvector pg16)
---

# Phase 2 Plan 03: Alembic init async + env.py + P7/P20 mitigations — Summary

## One-liner

Khởi tạo Alembic 1.18.4 async trong `Hub_All/api/migrations/` với env.py: (a) DSN inject runtime từ `get_settings().database_url`, (b) `target_metadata = Base.metadata` qua `from app.models import *` pick up 10 tables, (c) `include_object` callback exclude schema `cocoindex` (P7 mitigation chống Alembic drop state cocoindex), (d) `compare_type=True` + `compare_server_default=True` ở CẢ online + offline mode (P20 drift detection chính xác).

## What was built

6 file mới — 4 trong `Hub_All/api/migrations/`, 1 trong `Hub_All/api/`, 1 trong `Hub_All/api/scripts/`:

| File | Mục đích | Đặc trưng chính |
|---|---|---|
| `alembic.ini` | Alembic config | `script_location = migrations`, `prepend_sys_path = .`, `file_template` timestamp+rev+slug, KHÔNG hardcode `sqlalchemy.url` |
| `migrations/__init__.py` | Empty package marker | Cho phép `from migrations import ...` nếu cần ở Plan 04+ |
| `migrations/versions/.gitkeep` | Git track dir trống | Plan 04 sẽ tạo `0001_initial_schema.py` ở đây |
| `migrations/script.py.mako` | Template Alembic chuẩn | `from __future__ import annotations` + `Union[str, None]` cho Python 3.12 PEP 604 |
| `migrations/env.py` | Async runtime + P7 + P20 | `async_engine_from_config` + `include_object` cocoindex filter + `compare_type/server_default` |
| `scripts/alembic-smoke.sh` | 3-step smoke verify | `alembic --help` → `alembic current` (no Traceback) → assert 10 tables |

**env.py architecture (4 đặc trưng M2 chủ chốt):**

1. **Async runtime** — `async_engine_from_config` tạo `AsyncEngine`, `asyncio.run(run_async_migrations())` driver, `connection.run_sync(do_run_migrations)` bridge async↔sync để `context.run_migrations()` chạy được trong async transaction.
2. **DSN inject runtime** — `_settings = get_settings()` + `config.set_main_option("sqlalchemy.url", _settings.database_url)`. `alembic.ini` cố ý KHÔNG có `sqlalchemy.url` → mỗi env dùng DSN riêng (dev = `medinet_central` local, test = testcontainer, prod = remote).
3. **`target_metadata = Base.metadata`** — `from app.models import *` (wildcard) trigger import 10 model class → register vào `Base.metadata.tables`. Verified runtime: `len(Base.metadata.tables) == 10`.
4. **`include_object` filter exclude schema `cocoindex`** — callback nhận `(object_, name, type_, reflected, compare_to)`, check `hasattr(object_, "schema") and object_.schema == "cocoindex"` → return `False`. Plan 04 sẽ test thực: nếu DB có schema cocoindex với 3 internal table, `alembic revision --autogenerate` KHÔNG được sinh ra `op.drop_table('cocoindex.__internal_*')`.

**Drift detection P20 bake CẢ 3 nơi:**

- `run_migrations_offline()` — `context.configure(..., compare_type=True, compare_server_default=True, include_object=include_object)`.
- `do_run_migrations(connection)` — cùng 3 flag (online mode).
- KHÔNG override ở online async — `do_run_migrations` là single source of truth cho context.configure.

## Tasks executed

| # | Task | Commit | Files |
|---|---|---|---|
| 01 | `alembic.ini` — config tối giản, KHÔNG hardcode DSN | `97e53fb` | `Hub_All/api/alembic.ini` |
| 02 | `migrations/__init__.py` + `versions/.gitkeep` | `cb1f141` | `migrations/__init__.py`, `migrations/versions/.gitkeep` |
| 03 | `migrations/script.py.mako` — template chuẩn | `61c1e9c` | `migrations/script.py.mako` |
| 04 | `migrations/env.py` — async + P7 + P20 | `e71a2bc` | `migrations/env.py` |
| 05 | `scripts/alembic-smoke.sh` — 3-step smoke | `bdd343d` | `scripts/alembic-smoke.sh` |
| (fix) | Rule 1 - alembic.ini ASCII (Windows cp1252) | `1c6232d` | `alembic.ini` (modified) |

Tổng cộng **6 commit** (5 task + 1 auto-fix Rule 1).

## Verification

Tất cả command verification cuối plan đã pass:

```bash
$ cd Hub_All/api && uv run alembic --help
usage: alembic [-h] [--version] [-c CONFIG] [-n NAME] [-x X] [--raiseerr] [-q]
               {branches,check,current,downgrade,edit,...}
(exit 0)

$ cd Hub_All/api && uv run python -c "from app.db.base import Base; from app.models import *; assert len(Base.metadata.tables) == 10; print('OK — 10 tables register vào Base.metadata')"
OK — 10 tables register vào Base.metadata

$ cd Hub_All/api && uv run python -c "import importlib.util; spec = importlib.util.spec_from_file_location('env_smoke', 'migrations/env.py'); print('env.py path resolves' if spec else 'FAIL')"
env.py path resolves

$ cd Hub_All/api && uv run ruff check migrations/env.py
All checks passed!

$ ls Hub_All/api/migrations/
__init__.py  env.py  script.py.mako  versions

$ ls -la Hub_All/api/migrations/versions/
.gitkeep  (chỉ duy nhất 1 file — Plan 04 sẽ tạo first migration)

$ cd Hub_All/api && DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/test COCOINDEX_DATABASE_URL=postgresql://test:test@localhost:5432/test REDIS_URL=redis://localhost:6379/0 uv run alembic check 2>&1 | grep -cE 'UnicodeDecodeError|ImportError|ModuleNotFoundError'
0   # KHÔNG có ImportError/UnicodeError; chỉ fail ở ConnectionRefusedError (expected khi Docker không up)
```

7 verification command pass đầy đủ. Alembic CLI load `alembic.ini` + execute `env.py` (import `app.config`, `app.db.base`, `app.models.*`) thành công — chỉ fail ở giai đoạn connect DB (expected).

## Truths achieved (Must-Haves)

- ✓ **Truth 1:** `cd Hub_All/api && uv run alembic --help` exits 0 — verified output có `usage: alembic`.
- ✓ **Truth 2:** `cd Hub_All/api && uv run alembic current` KHÔNG crash với ImportError — verified `alembic check` qua phase load env.py + chỉ fail ở connect (expected khi Docker down).
- ✓ **Truth 3:** `cd Hub_All/api && uv run alembic check` không crash với ImportError — verified cùng test.
- ✓ **Truth 4:** Alembic autogenerate (Plan 04) sẽ pick up đủ 10 table — verified `len(Base.metadata.tables) == 10` sau `from app.models import *`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Ruff I001 import block un-sorted ở env.py (Task 04 verify)**

- **Found during:** Task 04 acceptance — `uv run ruff check migrations/env.py`
- **Issue:** Comment `# Import models để Base.metadata pick up đủ 10 table TRƯỚC khi autogenerate run.` chèn giữa group "third-party" (`sqlalchemy.*`) và "local" (`app.*`) khiến ruff isort không nhận diện được boundary group → báo I001 un-sorted.
- **Fix:** Chạy `uv run ruff check migrations/env.py --fix` — ruff tự reorganize, comment giữ nguyên semantic nhưng vị trí được điều chỉnh để 3 group import (stdlib / third-party / local) được phân tách rõ bằng blank line. Không thay đổi semantics import — vẫn 7 import từ 4 nguồn.
- **Files modified:** `Hub_All/api/migrations/env.py` (trước commit task 04)
- **Commit:** `e71a2bc` (gộp với Task 04 vì auto-fix lúc verify acceptance).

**2. [Rule 1 - Bug] Windows cp1252 UnicodeDecodeError đọc alembic.ini**

- **Found during:** Final plan verification — chạy `uv run alembic check` với env vars
- **Issue:** Alembic dùng `configparser.read(file, encoding="locale")` (Python 3.10+ default). Trên Windows, locale = cp1252 → KHÔNG decode được em-dash (`—`, U+2014) + Vietnamese diacritics (`ưở`, `đậy`, ...) trong comment header `alembic.ini`. `alembic check` + `alembic current` crash với `UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 129`.
- **Tác động:** Mọi command Alembic trên Windows dev environment đều fail trước khi load env.py — block toàn bộ Plan 04 trên Windows.
- **Fix:** Rewrite comment header `alembic.ini` bằng tiếng Anh ASCII thuần. Comment tiếng Việt giữ trong `env.py` docstring (Python source mặc định UTF-8, KHÔNG đụng configparser). Note quan trọng được ghi rõ vào header file: "Keep this file pure ASCII to avoid UnicodeDecodeError. Vietnamese commentary lives in env.py + docs."
- **Files modified:** `Hub_All/api/alembic.ini`
- **Commit:** `1c6232d` (Rule 1 fix riêng — bug critical block plan)

Không có Rule 2/3/4 deviation.

## Authentication Gates

Không có auth gate trong plan này (chỉ tạo file config + Python module, KHÔNG cần secret/token).

## Threat Model Bake (P7 + P20)

| Pitfall | Mitigation | File | Line/Concept |
|---|---|---|---|
| **P7** (CocoIndex `cocoindex` schema isolation) | `include_object` filter return `False` cho `object_.schema == "cocoindex"` | `migrations/env.py` | Function `include_object` lines 40-55 — verified `grep` count = 1 occurrence của `object_.schema == "cocoindex"` |
| **P20** (Alembic drift detection sai) | `compare_type=True` + `compare_server_default=True` ở online + offline mode | `migrations/env.py` | `run_migrations_offline` + `do_run_migrations` — verified `grep` count = 3 (gồm 2 occurrences `compare_type=True` + có thể có docstring) |
| **P19** (stack version drift) | `alembic==1.18.4` pin trong `pyproject.toml` từ Plan 02 Phase 1 | `pyproject.toml` | Không touch ở plan này, chỉ verify dùng đúng version |

**Lý do P7 critical:** CocoIndex Phase 4 sẽ tự `CREATE TABLE cocoindex.__source_state`, `cocoindex.__incremental_diff`, `cocoindex.__lineage_tracker` (3 bảng nội bộ). Nếu Alembic autogenerate KHÔNG có filter này, `alembic revision --autogenerate` tại Plan 04 hoặc bất kỳ migration tương lai nào sẽ thấy 3 bảng đó tồn tại trong DB nhưng KHÔNG có trong `Base.metadata` → sinh ra `op.drop_table(...)` xóa state cocoindex → re-index toàn bộ corpus (rất tốn time + LLM cost).

**Lý do P20 critical:** Mặc định Alembic `compare_type=False` → đổi `Text` → `Varchar(N)` KHÔNG detect; `compare_server_default=False` → đổi `server_default='pending'` → `NULL` KHÔNG detect. Phase 2-7 sẽ có nhiều migration evolve schema; KHÔNG có 2 flag này = autogenerate báo "no changes" trong khi schema thực đã drift.

## Key Decisions Made

1. **D-02-03-01 alembic.ini KHÔNG hardcode sqlalchemy.url** — env.py inject runtime qua `config.set_main_option`. Lý do: dev DB local Docker (`postgresql+asyncpg://medinet:...@localhost:5432/medinet_central`), test DB testcontainer (port động), prod DB remote — 3 DSN khác nhau hoàn toàn. Nếu hardcode, mỗi env phải sửa `alembic.ini` (lỗi prone). Trade-off: `alembic.ini` standalone (chạy thuần `alembic upgrade head` không cần Python env) bị mất; chấp nhận vì M2 luôn chạy qua `uv run alembic` có Python env.
2. **D-02-03-02 include_object check qua `hasattr(object_, "schema")`** — pattern duck-typing thay vì isinstance(Table). Lý do: callback nhận `(object_, type_, ...)` với type_ in `{table, column, index, foreign_key_constraint, unique_constraint, check_constraint}`. CocoIndex internal có thể tạo Index hoặc Constraint trên schema cocoindex; filter generic áp dụng cho mọi type_ qua attribute `.schema`.
3. **D-02-03-03 P20 flag bake CẢ online + offline mode** — Plan 04 có thể `alembic upgrade --sql > review.sql` (offline) để review trước khi apply (online). Nếu offline KHÔNG có drift detect, output SQL sai → review vô nghĩa. Cost của bake 2 nơi: ~6 dòng code duplicate trong `context.configure()` — chấp nhận.
4. **D-02-03-04 alembic.ini ASCII thuần** — phát hiện qua Rule 1 fix. Lý do gốc: `configparser.read(..., encoding="locale")` Python 3.10+ + Windows cp1252 codec. Bake docstring note trong file để dev tương lai KHÔNG vô tình thêm Vietnamese vào file ini.
5. **D-02-03-05 file_template timestamp prefix** — `%(year)d_%(month).2d_%(day).2d_%(hour).2d%(minute).2d-%(rev)s_%(slug)s` thay vì chỉ `%(rev)s_%(slug)s`. Migration mới sẽ có tên `2026_05_13_2342-abc123_create_initial_schema.py` — sort filesystem = sort theo thời gian. Lợi ích: KHÔNG cần xem `alembic history` để biết order khi review code.

## Requirements Coverage

- **CORE-02 (Database foundation):** Partial — Alembic baseline (config + env.py + template + smoke script) sẵn sàng. Plan 04 (migration `0001_initial_schema`) + Plan 05 (testcontainers verify) sẽ đóng requirement này khi DDL apply thành công.

## Notes for Next Plans

- **Plan 02-04 (migration 0001_initial_schema) PHẢI:**
  - Chạy `cd Hub_All/api && uv run alembic revision --autogenerate -m "initial schema"` sau khi `docker compose up -d postgres` (Phase 1) — autogenerate sẽ pick up 10 table từ `target_metadata` qua env.py này.
  - Verify migration file sinh ra trong `Hub_All/api/migrations/versions/`.
  - Verify migration file KHÔNG chứa `op.drop_table('cocoindex.*')` (P7 filter hoạt động).
  - ADD `op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")` + `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` ĐẦU `upgrade()` (cho `gen_random_uuid()` server_default + Vector type).
  - Verify autogenerate emit HNSW index đúng `WITH (hnsw)` + `vector_cosine_ops`; nếu thiếu `postgresql_ops` mapping, ADD raw SQL `op.execute("CREATE INDEX ix_chunks_vector_hnsw ON chunks USING hnsw (vector vector_cosine_ops)")`.
  - ADD `op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM CURRENT_USER")` cuối `upgrade()` (T-02-05 schema enforce append-only).
- **Plan 02-05 (testcontainers verify) PHẢI:**
  - Spawn `pgvector/pgvector:pg16` testcontainer.
  - Set env vars `DATABASE_URL` + `COCOINDEX_DATABASE_URL` + `REDIS_URL` → run `uv run alembic upgrade head`.
  - Assert 10 tables tồn tại + HNSW index pick up + status CHECK enum + audit_logs REVOKE UPDATE.
  - Run `scripts/alembic-smoke.sh` cuối test để confirm config sạch.
- **Phase 3 Auth + Phase 4 CocoIndex** sẽ dùng env.py này cho mọi migration kế tiếp — KHÔNG cần đụng `env.py` trừ khi thêm schema mới ngoài `public` + `cocoindex` (vd `audit` schema riêng cho HARD-04 nếu phát sinh).

## Self-Check: PASSED

**Files verified exist:**
- ✓ `Hub_All/api/alembic.ini`
- ✓ `Hub_All/api/migrations/__init__.py`
- ✓ `Hub_All/api/migrations/env.py`
- ✓ `Hub_All/api/migrations/script.py.mako`
- ✓ `Hub_All/api/migrations/versions/.gitkeep`
- ✓ `Hub_All/api/scripts/alembic-smoke.sh`

**Commits verified in git log:**
- ✓ `97e53fb` — feat(phase-02): alembic(config): alembic.ini
- ✓ `cb1f141` — feat(phase-02): alembic(scaffold): __init__ + .gitkeep
- ✓ `61c1e9c` — feat(phase-02): alembic(template): script.py.mako
- ✓ `e71a2bc` — feat(phase-02): alembic(env): env.py async + P7 + P20
- ✓ `bdd343d` — feat(phase-02): alembic(smoke): alembic-smoke.sh
- ✓ `1c6232d` — fix(phase-02): alembic(config): alembic.ini ASCII (Rule 1)

**Verification commands all exit 0:** alembic --help ✓, target_metadata 10 tables ✓, env.py path resolves ✓, ruff migrations/env.py ✓, ls migrations/ 4 items ✓, ls versions/ chỉ .gitkeep ✓, alembic check không ImportError/UnicodeError ✓.
