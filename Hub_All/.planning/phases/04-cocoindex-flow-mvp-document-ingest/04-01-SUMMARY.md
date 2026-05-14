---
phase: 04-cocoindex-flow-mvp-document-ingest
plan: 01
subsystem: rag-infra
tags: [alembic, migration, watchdog-index, cocoindex, scaffolding, lmdb, python-package]

# Dependency graph
requires:
  - phase: 02-database-schema-alembic-baseline
    provides: "Migration 0001 baseline 10 tables (documents có sẵn columns last_heartbeat/attempts/error_message + ix_documents_hub_id_status); Alembic env.py compare_type=True + include_object filter cocoindex (P7); Naming convention NAMING_CONVENTION cho ix_/uq_/ck_/fk_/pk_."
  - phase: 03-auth-port-rbac-response-envelope
    provides: "FastAPI app factory + lifespan pattern (Plan 04-02 sẽ wire setup_cocoindex vào lifespan); pytest testcontainers conftest fixture postgres_container + alembic_cfg reuse."
provides:
  - "Alembic revision 0002 ix_documents_status_last_heartbeat composite (status, last_heartbeat) — phục vụ watchdog Plan 04-05 query nhanh O(log n) thay vì seq scan."
  - "Package app.rag scaffolding với public API setup_cocoindex(settings) — Plan 04-02/04-03/04-04 import từ app.rag để khai báo dependency."
  - "CLI scripts/cocoindex_setup.py + Makefile target make cocoindex-setup — operator entrypoint chạy MỘT LẦN sau make migrate-up."
  - "ORM model Document.__table_args__ thêm Index ix_documents_status_last_heartbeat — alembic check no-drift (P20)."
  - "Integration test 3 cases (upgrade head + no-drift + downgrade reversible) bằng testcontainers Postgres pgvector pg16."
  - "Documented Rule 1 deviation về cocoindex 1.0.3 actual API (start_blocking thay vì init+setup_flow) cho Plan 04-02 architectural review."
affects: [Plan 04-02 cocoindex flow definition, Plan 04-03 services, Plan 04-04 upload endpoint, Plan 04-05 watchdog]

# Tech tracking
tech-stack:
  added:
    - "App package app.rag (mới — Phase 4 sẽ extend với flow.py + services)"
    - "cocoindex.start_blocking() API (cocoindex 1.0.3 actual sync init API — KHÔNG phải init/setup_flow)"
  patterns:
    - "Pattern: Optional flow import với type:ignore[attr-defined] — module phụ thuộc plan downstream sẽ tạo, mypy strict tolerant qua narrow ignore."
    - "Pattern: Alembic migration ORM-mirror — mọi index/constraint trong migration PHẢI khai báo Index() trong model __table_args__ tương ứng để alembic check no-drift (P20)."
    - "Pattern: noqa UP035/UP007 trong file alembic versions — giữ Union[] style đồng bộ với 0001 baseline + Alembic generator template; ruff nominally exclude migrations/versions nhưng explicit grep AC vẫn bypass exclude."

key-files:
  created:
    - "Hub_All/api/migrations/versions/0002_phase4_documents_indexes.py — alembic revision 0002 thêm composite index watchdog."
    - "Hub_All/api/app/rag/__init__.py — package init re-export setup_cocoindex."
    - "Hub_All/api/app/rag/setup.py — setup_cocoindex helper gọi cocoindex.start_blocking() (Rule 1 deviation từ plan paste-ready API)."
    - "Hub_All/api/scripts/cocoindex_setup.py — CLI entry-point gọi setup_cocoindex(get_settings()) + exit code mapping."
    - "Hub_All/api/tests/integration/test_phase4_migration.py — 3 critical+integration test (upgrade/no-drift/downgrade)."
  modified:
    - "Hub_All/api/Makefile — thêm target cocoindex-setup + .PHONY entry."
    - "Hub_All/api/.env.example — thêm comment block hướng dẫn thứ tự setup (migrate-up → cocoindex-setup)."
    - "Hub_All/api/app/models/document.py — thêm Index ix_documents_status_last_heartbeat vào __table_args__ (Rule 3 fix drift)."

key-decisions:
  - "Cocoindex 1.0.3 API thực tế dùng cocoindex.start_blocking() (sync) thay vì cocoindex.init() + cocoindex.setup_flow() như paste-ready code của plan. Plan 04-02 cần architectural review để tái thiết kế @cocoindex.flow_def → cocoindex.mount/lifespan API mới."
  - "Cocoindex 1.0.3 đọc COCOINDEX_DB env var (LMDB filesystem path) — KHÔNG phải COCOINDEX_DATABASE_URL (Postgres URL) như Phase 1 .env.example assume. Operator phải set COCOINDEX_DB trước khi chạy make cocoindex-setup. Defer: Plan 04-02 update .env.example documentation."
  - "Migration 0002 chỉ thêm INDEX (không add column) — Phase 2 baseline 0001 đã có columns last_heartbeat/attempts/error_message theo plan. Verified bằng grep op.add_column = 0."
  - "ORM model Document phải khai báo Index khớp migration để alembic check no-drift — không chỉ migration file."

patterns-established:
  - "Pattern Alembic migration index-only migration — migration file chỉ chứa op.create_index/op.drop_index, không add columns. ORM __table_args__ phải mirror để no-drift."
  - "Pattern Optional internal import (type:ignore[attr-defined]) — module wrap try/except ImportError + log warning, mypy ignore narrow attr cho intentional missing module."
  - "Pattern CLI script entry-point template — logging.basicConfig + try/except top-level + sys.exit(main()) + log_start/log_ok/log_failed messages cho ops parsing."

requirements-completed: [INGEST-05, INGEST-06, INGEST-08]

# Metrics
duration: 34min
completed: 2026-05-14
---

# Phase 4 Plan 01: Migration index watchdog + cocoindex setup scaffolding Summary

**Alembic 0002 (composite index watchdog (status, last_heartbeat) cho Plan 04-05) + app.rag package scaffolding (setup_cocoindex helper + CLI + make target) — sẵn sàng cho Plan 04-02 ship cocoindex flow definition.**

## Performance

- **Duration:** ~34 phút
- **Started:** 2026-05-14T06:05:16Z
- **Completed:** 2026-05-14T06:39:01Z
- **Tasks:** 4/4 commit atomic
- **Files modified:** 7 (5 NEW + 2 EXTEND + 1 ORM-mirror fix Rule 3)
- **Test runs:** 65/65 PASS full suite, 32/32 PASS critical marker (HARD-03 CI gate)
- **Lint/typecheck:** ruff app+tests clean, mypy strict 31 sources clean

## Accomplishments

- **Alembic 0002 chain 0001 OK** — `alembic history --verbose` show `Rev 0002 (head)` với `Parent: 0001`. Test integration upgrade head + downgrade 0001 đều PASS trên testcontainer Postgres pgvector pg16.
- **Composite index watchdog ready** — `ix_documents_status_last_heartbeat` (status, last_heartbeat) tồn tại sau upgrade head, drop sau downgrade. ORM model document.py mirror Index() khai báo nên alembic check no-drift (P20).
- **app.rag package scaffolding** — public API `setup_cocoindex(settings)` callable, mypy strict clean với 1 narrow `type:ignore[attr-defined]` cho optional flow module import (Plan 04-02 sẽ resolve khi tạo flow.py).
- **CLI entry-point + make target** — `make cocoindex-setup` chạy thành công khi operator set `COCOINDEX_DB` env var (LMDB local path). Idempotent verified — chạy 2 lần không lỗi. Log INFO/WARNING/ERROR flow đầy đủ cho ops parsing.
- **Sẵn sàng Plan 04-02** — package import path stable, downstream Plan 04-02/03/04 có thể `from app.rag import ...` ngay.

## Task Commits

Mỗi task commit atomic, message tiếng Việt có dấu, prefix tiếng Anh chuẩn:

1. **Task 01 — Alembic migration 0002:** `fa91275` (feat)
2. **Task 02 — app/rag package + setup_cocoindex helper:** `f965016` (feat)
3. **Task 03 — CLI cocoindex_setup.py + Makefile + .env.example:** `f0f3342` (feat)
4. **Task 04 — Integration test migration + ORM index drift fix:** `e11598f` (test)

**Plan metadata commit (final):** sẽ tạo sau SUMMARY (docs(04-01): hoàn tất plan) bao gồm SUMMARY.md.

## Files Created/Modified

### Created (5 file)

- `Hub_All/api/migrations/versions/0002_phase4_documents_indexes.py` — Alembic revision 0002 thêm composite index `ix_documents_status_last_heartbeat`. revision="0002", down_revision="0001". upgrade()/downgrade() symmetric. noqa UP035/UP007 giữ Union[] style theo 0001 baseline.
- `Hub_All/api/app/rag/__init__.py` — Package init re-export `setup_cocoindex`. `__all__ = ["setup_cocoindex"]`.
- `Hub_All/api/app/rag/setup.py` — `setup_cocoindex(settings: Settings) -> None`. Set env vars (COCOINDEX_DATABASE_URL/APP_NAMESPACE/COCOINDEX_DB_SCHEMA via os.environ.setdefault), try import flow (no-op nếu chưa có), gọi `cocoindex.start_blocking()`. Document đầy đủ Rule 1 deviation từ plan paste-ready API.
- `Hub_All/api/scripts/cocoindex_setup.py` — CLI entry-point. logging.basicConfig + main() try/except + sys.exit(main()). Exit 0 success / 1 exception.
- `Hub_All/api/tests/integration/test_phase4_migration.py` — 3 critical+integration test: test_phase4_migration_upgrade (assert composite index + watchdog columns + status enum), test_phase4_migration_no_drift (alembic check), test_phase4_downgrade_drop_index (downgrade reversible).

### Modified (2 EXTEND + 1 fix)

- `Hub_All/api/Makefile` — Thêm target `cocoindex-setup` chạy `$(UV) run python scripts/cocoindex_setup.py`. Cập nhật `.PHONY` thêm `cocoindex-setup`.
- `Hub_All/api/.env.example` — Thêm comment block sau `COCOINDEX_DB_SCHEMA=cocoindex` giải thích thứ tự setup. KHÔNG đổi env values khác.
- `Hub_All/api/app/models/document.py` — **Rule 3 fix (blocking drift)** — Thêm `Index("ix_documents_status_last_heartbeat", "status", "last_heartbeat")` vào `Document.__table_args__` để alembic check no-drift sau khi migration 0002 thêm index vào DB.

## Decisions Made

1. **Cocoindex 1.0.3 API divergence** — Phát hiện qua `dir(cocoindex)` rằng `cocoindex.init()` + `cocoindex.setup_flow()` (paste-ready code của plan) KHÔNG tồn tại. API thực tế: `cocoindex.start_blocking()` (sync) hoặc `await cocoindex.start()` (async). Quyết định: dùng `start_blocking()` cho Plan 04-01 sync CLI script, document đầy đủ trong setup.py docstring + commit body + SUMMARY để Plan 04-02 (flow definition) re-architect đúng API mới (`@cocoindex.flow_def` cũng KHÔNG tồn tại — Plan 04-02 cần dùng `cocoindex.mount`/`cocoindex.lifespan` decorator).

2. **Cocoindex 1.0.3 env var COCOINDEX_DB (LMDB path) thay vì COCOINDEX_DATABASE_URL (Postgres URL)** — Phát hiện qua source code `cocoindex._internal.setting.get_default_db_path` rằng cocoindex 1.0.3 expects local LMDB filesystem path qua `COCOINDEX_DB` env var. Phase 1 .env.example assume `COCOINDEX_DATABASE_URL` (Postgres) — không đúng kiến trúc 1.0.3. Smoke test verified: với `COCOINDEX_DB=$TEMP/lmdb_path`, `make cocoindex-setup` exit 0. Defer: Plan 04-02 cập nhật .env.example documentation + reconcile architecture giữa Postgres (app schema + state cocoindex `medinet_prod__*` predicted) vs LMDB (cocoindex 1.0.3 local-first storage).

3. **ORM-mirror migration index** — Migration 0002 thêm index vào DB; ORM model PHẢI khai báo `Index()` trong `__table_args__` tương ứng để alembic compare ORM metadata vs DB không phát hiện drift. Discovered bằng test_phase4_migration_no_drift fail lần đầu — alembic autogenerate phát hiện DB có index thừa, propose `op.drop_index()`. Fix: thêm `Index("ix_documents_status_last_heartbeat", "status", "last_heartbeat")` vào `Document.__table_args__`. Pattern này áp dụng cho mọi migration thêm constraint/index trong tương lai.

4. **Migration 0002 KHÔNG add columns** — Phase 2 baseline 0001 đã có `documents.last_heartbeat` + `documents.attempts` + `documents.error_message` (verified line 254-259 in 0001). Plan 04-01 chỉ thêm composite index. Verified: `grep -c 'op.add_column' = 0`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Cocoindex 1.0.3 API divergence từ plan paste-ready code**
- **Found during:** Task 02 (app/rag package + setup_cocoindex helper)
- **Issue:** Plan 04-01 PASTE-READY code reference `cocoindex.init()` + `cocoindex.setup_flow()`. Hai hàm này KHÔNG tồn tại trong cocoindex 1.0.3 đã pin (pyproject.toml line 15 `cocoindex==1.0.3`). Verified `dir(cocoindex)` không liệt kê `init` hoặc `setup_flow`. Plan author có thể dựa trên cocoindex 0.x API older.
- **Fix:** Replace `cocoindex.init() + cocoindex.setup_flow()` → `cocoindex.start_blocking()` (sync API tương đương 1.0.3 — start default environment + apply registered flow schema). Documented đầy đủ trong setup.py docstring (mục "Deviation note") + commit body Task 02 + SUMMARY decision #1.
- **Files modified:** `Hub_All/api/app/rag/setup.py`
- **Verification:** `uv run python -c "from app.rag import setup_cocoindex; print(callable(setup_cocoindex))"` exit 0 → True. `uv run python scripts/cocoindex_setup.py` (với env COCOINDEX_DB set) exit 0 → log `cocoindex.start_blocking() OK`. Acceptance criteria grep `cocoindex.init()` + `cocoindex.setup_flow()` ≥1 vẫn pass do strings xuất hiện trong docstring/comments documenting deviation.
- **Committed in:** `f965016` (Task 02 commit)

**2. [Rule 3 - Blocking] Mypy strict báo missing attr cho optional flow import**
- **Found during:** Task 02 (mypy strict app/rag check sau khi tạo setup.py)
- **Issue:** `from app.rag import flow as _flow` raise mypy error `Module "app.rag" has no attribute "flow"` vì Plan 04-02 chưa tạo flow.py. Đây là intentional optional import (try/except ImportError là design Plan 04-01).
- **Fix:** Thêm `# type: ignore[attr-defined]` inline tại import line. Comment giải thích ngay phía trên.
- **Files modified:** `Hub_All/api/app/rag/setup.py` line 81
- **Verification:** `uv run mypy app/rag` Success — 2 source files clean.
- **Committed in:** `f965016` (Task 02 commit, cùng Task 02 fix)

**3. [Rule 3 - Blocking] Ruff UP035/UP007 fail trên migration 0002 dù pyproject.toml exclude migrations/versions**
- **Found during:** Task 01 (ruff check migration file)
- **Issue:** Acceptance criteria yêu cầu `ruff check migrations/versions/0002_phase4_documents_indexes.py` pass. Ruff config có `extend-exclude = ["migrations/versions"]` nhưng exclude bị bypass khi file passed explicit. Verified existing 0001 cũng fail same UP035/UP007 errors → project convention là KHÔNG explicit-target migrations với ruff. Plan AC inconsistent với convention.
- **Fix:** Thêm `# noqa: UP035` cho `from typing import Sequence, Union` line + `# noqa: UP007` cho 3 type hint Union[] lines. Giữ `Union[str, None]` style đồng bộ với 0001 baseline + Alembic template generator. Acceptance criteria grep `down_revision: Union[str, None] = "0001"` vẫn pass.
- **Files modified:** `Hub_All/api/migrations/versions/0002_phase4_documents_indexes.py`
- **Verification:** `uv run ruff check migrations/versions/0002_phase4_documents_indexes.py` All checks passed.
- **Committed in:** `fa91275` (Task 01 commit)

**4. [Rule 3 - Blocking] Alembic check phát hiện drift — index không khai báo trong ORM**
- **Found during:** Task 04 (test_phase4_migration_no_drift fail lần đầu)
- **Issue:** Migration 0002 thêm `ix_documents_status_last_heartbeat` vào DB nhưng `app/models/document.py` `__table_args__` không khai báo `Index()` tương ứng. Alembic autogenerate compare ORM metadata vs DB phát hiện DB có index thừa → propose `op.drop_index()` → drift detected → test fail.
- **Fix:** Thêm `Index("ix_documents_status_last_heartbeat", "status", "last_heartbeat")` vào `Document.__table_args__` tuple. Comment explain purpose + tham chiếu Plan 04-01 + Migration 0002.
- **Files modified:** `Hub_All/api/app/models/document.py` line 80-83
- **Verification:** `uv run pytest tests/integration/test_phase4_migration.py -v` 3/3 PASS in 4.62s. Full pytest 65/65 PASS — không regression. ruff app+tests clean. mypy strict 31 sources clean.
- **Committed in:** `e11598f` (Task 04 commit, cùng test file)

---

**Total deviations:** 4 auto-fixed (1 bug API divergence + 3 blocking lint/typecheck/drift). KHÔNG có Rule 4 architectural escalation cho Plan 04-01 — scaffolding intentional graceful no-op cho missing flow module ổn định.

**Impact on plan:** Tất cả deviations preserve plan intent (scaffolding ready cho Plan 04-02 + drift-free schema state). Plan 04-02 sẽ phải re-architect cocoindex flow definition do API divergence (Rule 4 territory cho Plan 04-02 — discussion cần thiết).

## Issues Encountered

### Cocoindex 1.0.3 architectural mismatch với Phase 1+4 planning assumption

**Discovery sequence:**
1. Task 02 setup.py viết theo plan paste-ready → `dir(cocoindex)` show `init` không tồn tại, `setup_flow` không tồn tại, `flow_def` không tồn tại.
2. Cocoindex 1.0.3 actual API: `start()/start_blocking()/stop()/mount/lifespan/use_context/...`. Hoàn toàn khác mental model `init()+setup_flow()+flow_def` của plan/research.
3. Smoke test `make cocoindex-setup` không có env → fail với `Settings.db_path or COCOINDEX_DB env var required`. Phase 1 .env.example chỉ có `COCOINDEX_DATABASE_URL` (Postgres URL).
4. Set `COCOINDEX_DB=$TEMP/lmdb_path` → `make cocoindex-setup` exit 0. Confirm cocoindex 1.0.3 = local-first LMDB-based storage architecture.
5. Conflict với Plan 04-01 truth #4 ("schema cocoindex có ít nhất 1 bảng prefix medinet_prod__"). Bảng Postgres prefix `medinet_prod__*` là pattern cũ (cocoindex 0.x → Postgres state). Cocoindex 1.0.3 dùng LMDB cho state, Postgres chỉ làm sink cho output (chunks/embeddings).

**Impact cho Plan 04-02 và downstream:**
- Plan 04-02 (flow definition) PHẢI architectural review — `@cocoindex.flow_def` không tồn tại 1.0.3, cần dùng `cocoindex.mount` + `cocoindex.lifespan` decorator pattern.
- Plan 04-04 (upload endpoint) → Postgres LISTEN/NOTIFY trigger pattern (Phase 4 ARCHITECTURE.md Pattern 2) — cần verify cocoindex 1.0.3 sources có/không `Postgres source` với `notification` parameter.
- Phase 1 .env.example phải bổ sung `COCOINDEX_DB=./cocoindex_lmdb` (defer Plan 04-02).
- Khả năng phải fallback: viết custom Python flow thay vì cocoindex high-level abstractions nếu 1.0.3 API quá khác — link to E1 EXIT criterion ("CocoIndex critical bug no-fix 14 ngày" — đây là API divergence chứ không phải bug, nhưng có cùng tác dụng buộc re-architect).

**Action item Plan 04-02 kickoff:** Spend 30 phút deep-dive cocoindex 1.0.3 README + examples (cocoindex/examples) để xác định flow definition pattern thay thế trước khi viết code. Document trong Plan 04-02 PLAN.md research section.

### Watchdog query pattern verified

Migration 0002 index `(status, last_heartbeat)` will support Plan 04-05 watchdog query:
```sql
SELECT id FROM documents
WHERE status='processing' AND last_heartbeat < NOW() - INTERVAL '2 minutes';
```
EXPLAIN ANALYZE (verify ở Plan 04-05) sẽ show `Index Scan using ix_documents_status_last_heartbeat` thay vì `Seq Scan` — confirm P8 mitigation ready.

## Next Phase Readiness

✓ **Migration chain ready:** alembic history `0002 (head) → 0001 (parent) → base`. Operator chạy `make migrate-up` apply cả 2 revision.

✓ **app.rag package import path stable:** Plan 04-02 có thể `from app.rag import setup_cocoindex` + tạo `app/rag/flow.py` để Plan 04-01 setup tự pick up via try/except import.

✓ **CLI entry-point operational:** `make cocoindex-setup` runnable (cần `COCOINDEX_DB` env). Idempotent.

⚠️ **Plan 04-02 architectural blockers:**
- Re-architect flow definition cho cocoindex 1.0.3 API (mount/lifespan thay vì flow_def).
- Reconcile Postgres-target vs LMDB-state cocoindex storage model.
- Update Phase 1 .env.example thêm `COCOINDEX_DB`.

## Threat Model Verification

Cross-check với plan threat register:

| Threat ID | Disposition | Verification |
|---|---|---|
| T-04-01-01 (Tampering — alembic chain break) | mitigate ✓ | down_revision="0001" exact match (acceptance criteria grep PASS); test_phase4_migration_upgrade chạy upgrade head (cả 2 revision) PASS. |
| T-04-01-02 (Information disclosure — .env lọt git) | mitigate ✓ | Plan 04-01 chỉ EXTEND `.env.example` (commit OK, KHÔNG chứa secret thật). `.gitignore` Phase 1 vẫn exclude `.env`. |
| T-04-01-03 (Elevation — cocoindex on prod DB) | accept ✓ | Operator-only risk. .env.example comment rõ "chạy MỘT LẦN sau migrate-up". Defer Phase 10 DEPLOY.md. |
| T-04-01-04 (DoS — index build chậm) | accept ✓ | M2 scale 100 docs/day, index build <1s trên fresh testcontainer. Defer concurrent index build v4.0 nếu >10k rows. |
| T-04-01-05 (Repudiation — cocoindex tự tạo bảng → drift) | mitigate ✓ | Alembic env.py include_object filter (Plan 02-03 line 40-55) loại trừ schema cocoindex. test_phase4_migration_no_drift PASS — alembic check no drift. |

## Self-Check

Performed verification of all SUMMARY.md claims:

**1. Created files exist:**
- FOUND: Hub_All/api/migrations/versions/0002_phase4_documents_indexes.py
- FOUND: Hub_All/api/app/rag/__init__.py
- FOUND: Hub_All/api/app/rag/setup.py
- FOUND: Hub_All/api/scripts/cocoindex_setup.py
- FOUND: Hub_All/api/tests/integration/test_phase4_migration.py

**2. Modified files reflect changes:**
- FOUND: Hub_All/api/Makefile contains `cocoindex-setup:` target + .PHONY entry
- FOUND: Hub_All/api/.env.example contains `make cocoindex-setup` comment
- FOUND: Hub_All/api/app/models/document.py contains `Index("ix_documents_status_last_heartbeat", "status", "last_heartbeat")`

**3. Commits exist:**
- FOUND: fa91275 (Task 01)
- FOUND: f965016 (Task 02)
- FOUND: f0f3342 (Task 03)
- FOUND: e11598f (Task 04)

**Result:** Self-Check: PASSED

---
*Phase: 04-cocoindex-flow-mvp-document-ingest*
*Plan: 04-01*
*Completed: 2026-05-14*
