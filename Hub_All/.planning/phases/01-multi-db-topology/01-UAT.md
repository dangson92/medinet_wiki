---
status: complete
phase: 01-multi-db-topology
source:
  - 01-01-SUMMARY.md
  - 01-02-SUMMARY.md
  - 01-03-SUMMARY.md
  - 01-04-SUMMARY.md
  - 01-05-SUMMARY.md
started: "2026-05-22T08:00:00.000Z"
updated: "2026-05-22T08:15:00.000Z"
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: |
  `docker restart medinet-postgres` → container healthy lại sau ≤ 30s → 5 DB tồn tại + Alembic head `0004` uniform + M2 documents COUNT=3 preserved.
result: pass
observed: |
  Container healthy lại sau ~6s (4 attempts × 2s sleep + restart). Post-restart query:
  - 5 DB persist: medinet_central, medinet_cocoindex, medinet_hub_yte, medinet_hub_duoc, medinet_hub_hcns
  - Alembic head 0004 uniform: central=0004, yte=0004, duoc=0004, hcns=0004
  - M2 documents COUNT=3 PRESERVED
  Volume medinet_pgdata không bị reset (init-db.sh không re-trigger trên existing volume — đúng Postgres entrypoint hook semantics).

### 2. SC1 — 4 business DB + extension vector + HNSW 1536-dim
expected: |
  Postgres có 5 DB. Mỗi business DB có `CREATE EXTENSION vector` enabled + `ix_chunks_vector_hnsw` index trên cột `chunks.vector vector(1536)`.
result: pass
observed: |
  4 business DB (medinet_central + 3 hub) đều có:
  - `vector` 0.8.2 + `pgcrypto` 1.3 extensions enabled
  - `chunks.vector vector(1536)` column
  - `ix_chunks_vector_hnsw hnsw (vector vector_cosine_ops)` index
  init-db.sh (4 DB fresh init) + hub-init.sh (dynamic add) đều wire HNSW verify block đúng (R1 mitigation).

### 3. SC2 — alembic-head-check.sh PASS + head SHA uniform
expected: |
  `cd Hub_All/api && ./scripts/alembic-head-check.sh` exit 0 + stdout "tất cả 4 DB cùng head SHA: 0004" (R-V3-3 mitigation).
result: pass
observed: |
  Script exit 0. Stdout:
  ```
  [alembic-head-check] Collect head SHA per hub...
  [alembic-head-check]   hub=central head=0004
  [alembic-head-check]   hub=yte head=0004
  [alembic-head-check]   hub=duoc head=0004
  [alembic-head-check]   hub=hcns head=0004
  [alembic-head-check] PASS - tat ca 4 DB cung head SHA: 0004
  ```

### 4. SC3 — Cocoindex per-hub naming + APP_NAMESPACE
expected: |
  pytest test_flow_per_hub_naming.py → 9/9 PASS. resolve_cocoindex_app_name per hub + COCOINDEX_APP_NAME_LEGACY fallback.
result: pass
observed: |
  9/9 PASS in 16.65s. Test coverage:
  - 4 valid hub mapping (central/yte/duoc/hcns → medinet_<hub>_ingest)
  - invalid hub name raises
  - module app name default central
  - module app name per-hub yte (subprocess HUB_NAME=yte env)
  - COCOINDEX_APP_NAME_LEGACY override preserves M2 name
  - LEGACY empty string falls back to resolve

### 5. SC4 — E-V3-3 hub isolation integration test
expected: |
  pytest test_hub_isolation_db_level.py → 5/5 PASS (testcontainers pgvector/pgvector:pg16).
result: pass
observed: |
  5/5 PASS in 3.63s:
  - test_settings_yte_with_central_dsn_raises (ValidationError "DSN mismatch")
  - test_settings_yte_with_duoc_dsn_raises (cross-hub blocked)
  - test_settings_yte_with_yte_dsn_succeeds (same-hub OK)
  - test_db_connection_yte_cannot_reach_duoc (asyncpg connection-bound semantics)
  - test_4_dbs_independent_data (4 DB independent rows verify)

### 6. TOPO-04 — Settings.hub_name validator unit test
expected: |
  pytest test_config_hub_name.py → 11/11 PASS.
result: pass
observed: |
  11/11 PASS in 0.23s. Covers: central+central ok, yte+yte ok, yte+central raises, duoc+yte raises, invalid HUB_NAME raises, default central, resolve_database_url yte/central/invalid_base, DSN query string preserve.

### 7. M2 data preservation (BLOCKER 2 SAFE option B verify)
expected: |
  medinet_central.documents COUNT=3 (M2 baseline preserved); medinet_pgdata volume KHÔNG bị xóa.
result: pass
observed: |
  COUNT=3 với 3 documents thật từ M2:
  - DMD_T1-01_DinhVi_TrungTam_v1.docx (completed)
  - DMD_T3-01_HoSo_BacSi_EEAT_v1.docx (completed)
  - DMD_T3-02_PhanCong_NhanVat_v1.docx (completed)
  BLOCKER 2 fix (Option B SAFE default) confirmed — M2 corpus + container volume preserved qua schema push runtime.

### 8. CI gate present in test.yml (R-V3-3 mitigation)
expected: |
  ../.github/workflows/test.yml chứa step "Verify Alembic head SHA match 4 DB" với working-directory Hub_All/api + chạy alembic-head-check.sh chain.
result: pass
observed: |
  test.yml grep evidence (line numbers):
  - L20: `working-directory: Hub_All/api` (M2 pattern preserved cho default)
  - L112: step name "Apply migrate-all + verify head SHA match (TOPO-02, R-V3-3 mitigation)"
  - L121-126: comment "working-directory default Hub_All/api (preserve M2)" + `make migrate-all` (chain calls alembic-head-check.sh internally per Plan 03 Makefile target)
  BLOCKER 1 path fix (`../.github/workflows/test.yml` OUTSIDE Hub_All/) confirmed wired.

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

[none — all 8 tests PASS]
