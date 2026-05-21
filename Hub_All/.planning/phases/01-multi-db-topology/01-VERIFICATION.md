---
phase: 01-multi-db-topology
verified: 2026-05-21T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
notes:
  - "Initial verification — không có previous VERIFICATION.md để regression check."
  - "Phase 1 thuộc v3.0-a, cocoindex runtime smoke deferred Phase 2-3/EXIT GATE (acceptable per orchestrator brief)."
  - "M2 cocoindex state reset documented + accepted — KHÔNG flag là gap."
---

# Phase 1: Multi-DB Topology + Per-hub Alembic — Verification Report

**Phase Goal:** Postgres init script idempotent tạo N+1 logical DB cùng instance (`medinet_central` + `medinet_hub_<name>` × N) với extension vector + HNSW 1536-dim verify build per DB; per-hub Alembic migration set khớp head SHA giữa các DB; cocoindex flow naming per-hub `medinet_<hub>_ingest` + APP_NAMESPACE per-hub; HUB_NAME env isolation enforce kết nối đúng DB.

**Verified:** 2026-05-21
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (4 Success Criteria từ ROADMAP)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose up` tạo 4 DB (`medinet_central`, `medinet_hub_yte/duoc/hcns`) trên 1 instance; mỗi DB có `CREATE EXTENSION vector` + HNSW index 1536-dim verify build được. | ✓ VERIFIED | Live: 5 DB exist (central + cocoindex + 3 hub). Mỗi DB business có vector ext + `ix_chunks_vector_hnsw` index. `chunks.vector` cột `vector(1536)`. Code: `init-db.sh` (4 bước: CREATE DB → CREATE EXTENSION → HNSW verify), `hub-init.sh` (4 bước tương tự cho dynamic add). |
| 2 | `make migrate-all` apply Alembic migrations tuần tự 4 DB; `alembic current` returns cùng head SHA; CI lint check version match (R-V3-3). | ✓ VERIFIED | Live: 4 business DB cùng head `0004`. Code: `api/Makefile` `migrate-all` target loop 4 hub + gọi `alembic-head-check.sh`; `env.py` parse `-x hub=<name>` + resolve DSN; CI workflow `../.github/workflows/test.yml` có step "Apply migrate-all + verify head SHA match". |
| 3 | Cocoindex flow `medinet_<hub>_ingest` startup logs OK ở từng hub con (APP_NAMESPACE `medinet_<hub>_prod` không đụng nhau). | ✓ VERIFIED (code) | `app/rag/flow.py`: `resolve_cocoindex_app_name` (line 287) + module-level `cocoindex_app = coco.App(coco.AppConfig(name=_app_name), ...)` (line 328) build dynamic. `app/rag/setup.py`: `namespaced = f"medinet_{settings.hub_name}_prod"` + `os.environ["APP_NAMESPACE"] = namespaced` (lines 80-81). 9 unit test PASS. Runtime smoke deferred Phase 2 (acceptable). |
| 4 | Test integration: `HUB_NAME=yte` deploy KHÔNG truy cập được `medinet_hub_duoc` qua DB connection (E-V3-3 enforce DB-level). | ✓ VERIFIED | `app/config.py` `_enforce_hub_dsn_match` model_validator (line 158) fail-fast. `tests/integration/test_hub_isolation_db_level.py` 5/5 PASS (testcontainers, 5.55s) — cover Settings validator + asyncpg connection-bound + 4-DB independent seed. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/scripts/init-db.sh` | 4 DB loop + HNSW 1536-dim verify, idempotent | ✓ VERIFIED | 68 LOC, `HUBS=("yte" "duoc" "hcns")` array, `SELECT pg_database` guard, HNSW verify block với `vector(1536)` + `vector_cosine_ops`. |
| `api/scripts/hub-init.sh` | Dynamic hub add (CREATE DB + ext + HNSW + alembic) | ✓ VERIFIED | 82 LOC, regex `^[a-z][a-z0-9_]{1,30}$` sanitize, 4 bước (CREATE/EXTENSION/HNSW/alembic upgrade head). |
| `api/scripts/alembic-head-check.sh` | Verify head SHA match 4 DB | ✓ VERIFIED | 59 LOC, `declare -A HEADS` map, exit 1 nếu drift, R-V3-3 reference. |
| `api/app/config.py` | `hub_name: Literal[4]` + validator + `resolve_database_url` | ✓ VERIFIED | Line 43 field, line 158 `_enforce_hub_dsn_match` model_validator (raises "DSN mismatch hub_name"), line 200 module-level `resolve_database_url`. `cocoindex_db_schema="cocoindex"` line 54 (P7 preserve). |
| `api/app/db/session.py` | Dùng `settings.database_url` (no fallback) | ✓ VERIFIED | `create_async_engine(settings.database_url, ...)` line 38-44; KHÔNG branching hub_name; KHÔNG fallback cocoindex DSN. |
| `api/.env.example` | HUB_NAME + 4 hub DATABASE_URL pattern | ✓ VERIFIED | `HUB_NAME=central` default + 4 hub DSN pattern comments + `DATABASE_URL=...medinet_central`. |
| `api/migrations/env.py` | `-x hub=<name>` + resolve DSN + preserve M2 patterns | ✓ VERIFIED | `parse_hub_x_arg` (line 45), `resolve_env_database_url` (line 74), `context.get_x_argument` (line 149), `include_object` cocoindex filter (line 160 + 173 — P7 preserve), `compare_type=True` + `compare_server_default=True` (line 187-188, 201-202 — P20 preserve). |
| `api/app/rag/flow.py` | `resolve_cocoindex_app_name` + dynamic App + COCOINDEX_APP_NAME_LEGACY fallback | ✓ VERIFIED | `_VALID_HUBS_FLOW` frozenset (line 284), `resolve_cocoindex_app_name` (line 287), `_legacy_app_name = _os.environ.get("COCOINDEX_APP_NAME_LEGACY", "").strip()` (line 324), dynamic build (line 325-328). KHÔNG còn hard-code `name="medinet_wiki_ingest"`. |
| `api/app/rag/setup.py` | `APP_NAMESPACE = medinet_<hub>_prod` trước `start_blocking` | ✓ VERIFIED | Line 80-85: `namespaced = f"medinet_{settings.hub_name}_prod"` + `os.environ["APP_NAMESPACE"] = namespaced` + structured log event `cocoindex_app_namespace_set`. TOPO-03 reference line 48 + 63. |
| `api/Makefile` | `migrate-all`, `migrate-status`, `hub-init` targets | ✓ VERIFIED | Line 63 `HUBS_ALL ?= central yte duoc hcns`, line 65 `migrate-all`, line 74 `migrate-status`, line 89 `hub-init`. `migrate-all` chain `alembic-head-check.sh` (line 72). |
| `Makefile` (root) | `hub-init` proxy target | ✓ VERIFIED | Line 86: `hub-init:` + line 88 `$(MAKE) -C api hub-init HUB=$(HUB)`. |
| `api/tests/integration/test_hub_isolation_db_level.py` | 5 critical+integration test E-V3-3 | ✓ VERIFIED | 5 test functions (`test_settings_yte_with_central_dsn_raises`, `..._with_duoc_dsn_raises`, `..._with_yte_dsn_succeeds`, `test_db_connection_yte_cannot_reach_duoc`, `test_4_dbs_independent_data`); contextlib.closing pattern (W6 fix); 5/5 PASS runtime. |
| `../.github/workflows/test.yml` | postgres service + bootstrap + migrate-all step | ✓ VERIFIED | `services.postgres` (line 22-35, `pgvector/pgvector:pg16`), step "Bootstrap 4 DB" (line 58-73, `working-directory: Hub_All`), step "Apply migrate-all + verify head SHA match" (line 112-126), preserve `defaults.run.working-directory: Hub_All/api` (line 18-20). |
| `api/tests/unit/test_config_hub_name.py` | TDD test Settings.hub_name + validator | ✓ VERIFIED | 11 test functions (8 core + 3 bonus query string/invalid base/resolve). |
| `api/tests/unit/test_alembic_env_hub_arg.py` | TDD test env.py helpers | ✓ VERIFIED | 10 test functions (4 parse + 6 resolve, gồm W8 cross-hub yte→duoc + invalid base). |
| `api/tests/unit/test_flow_per_hub_naming.py` | TDD test cocoindex per-hub naming | ✓ VERIFIED | 6 `def test_` + 1 `@pytest.mark.parametrize` (4 hub valid params) → 9 test case effective; gồm subprocess per-hub + legacy fallback. |

### Key Link Verification (Wiring)

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `docker-compose.yml postgres` | `api/scripts/init-db.sh` | Mount `/docker-entrypoint-initdb.d/00-init.sh:ro` | ✓ WIRED | Live: 5 DB tạo từ init script khi cluster init (verified by live DB list). |
| `init-db.sh` | Postgres cluster | `psql --username POSTGRES_USER --dbname postgres` + heredoc | ✓ WIRED | Heredoc `<<-EOSQL` block + `SELECT pg_database` guard pattern. |
| `Settings (Plan 02)` | `init_engine` | `settings.database_url` (validated) | ✓ WIRED | `create_async_engine(settings.database_url, ...)`; KHÔNG fallback. |
| `make migrate-all` | `alembic env.py` | `alembic -x hub=$$hub upgrade head` | ✓ WIRED | Loop `for hub in $(HUBS_ALL)` + alembic-head-check.sh sau loop. |
| `env.py` | `Settings.database_url + resolve_database_url` | `get_settings() + parse_hub_x_arg + resolve_env_database_url` | ✓ WIRED | Lines 148-154 inject DSN runtime. |
| `make migrate-all` | `alembic-head-check.sh` | shell call sau loop | ✓ WIRED | `@bash scripts/alembic-head-check.sh` line 72 Makefile. |
| `Settings.hub_name` | `flow.py App name resolver` | `resolve_cocoindex_app_name(_settings.hub_name)` | ✓ WIRED | Line 325 + `coco.App(coco.AppConfig(name=_app_name), ...)` line 328. |
| `Settings.hub_name` | `setup.py APP_NAMESPACE env` | `os.environ["APP_NAMESPACE"] = f"medinet_{settings.hub_name}_prod"` | ✓ WIRED | Line 80-81 setup_cocoindex. |
| `Makefile root hub-init` | `api/scripts/hub-init.sh` | `$(MAKE) -C api hub-init HUB=$(HUB)` → `bash scripts/hub-init.sh $(HUB)` | ✓ WIRED | Root → api/Makefile → bash script chain. |
| `hub-init.sh` | `alembic env.py per-hub` | `uv run alembic -x hub="$HUB" upgrade head` | ✓ WIRED | Line 79 hub-init.sh, chain Plan 03 env.py. |
| `CI workflow` | `Makefile migrate-all` | step "Apply migrate-all..." dùng `make migrate-all` | ✓ WIRED | Line 126 test.yml + working-directory: Hub_All/api M2 default preserved. |
| `Integration test` | `Settings validator` | `Settings()` raise `ValidationError("DSN mismatch hub_name")` | ✓ WIRED | Tests `test_settings_yte_with_central_dsn_raises` + `..._duoc_dsn_raises` cover. |

### Data-Flow Trace (Level 4)

Phase 1 produces infrastructure/config artifacts (DB topology + Alembic + Settings + cocoindex setup), không có UI component render dynamic data. Mọi artifact đã trace upstream qua key link table trên. Level 4 N/A for this phase scope.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 5 DB exist trên live Postgres | `docker exec medinet-postgres psql -U medinet -d postgres -tA -c "SELECT datname FROM pg_database WHERE datname LIKE 'medinet_%' ORDER BY datname"` | `medinet_central, medinet_cocoindex, medinet_hub_duoc, medinet_hub_hcns, medinet_hub_yte` | ✓ PASS |
| M2 documents preserve | `docker exec medinet-postgres psql -U medinet -d medinet_central -tA -c "SELECT COUNT(*) FROM documents"` | `3` (baseline preserved) | ✓ PASS |
| Head SHA uniform 4 DB | `for db in medinet_central medinet_hub_yte medinet_hub_duoc medinet_hub_hcns; do psql ... SELECT version_num FROM alembic_version; done` | tất cả `0004` | ✓ PASS |
| HNSW index trên 4 DB | `for db in ...; do psql ... SELECT indexname FROM pg_indexes WHERE tablename='chunks' AND indexname LIKE '%hnsw%'; done` | `ix_chunks_vector_hnsw` trên 4 DB | ✓ PASS |
| vector extension trên 4 DB | `for db in ...; do psql ... SELECT extname FROM pg_extension WHERE extname='vector'; done` | `vector` trên 4 DB | ✓ PASS |
| pgvector type recognition | `psql -d medinet_hub_yte -tA -c "SELECT pg_typeof(NULL::vector(1536))::text;"` | `vector` | ✓ PASS |
| Alembic migration files exist | `ls api/migrations/versions/` | `0001_initial_schema.py, 0002_phase4_documents_indexes.py, 0003_phase5_schema_reconcile.py, 0004_mcp_oauth_clients.py` | ✓ PASS |
| chunks schema replicated to hub_yte | `psql -d medinet_hub_yte -tA -c "\d chunks"` | columns đầy đủ (id/document_id/hub_id/content/content_hash/heading_path/page_start/page_end/vector vector(1536)/metadata/created_at) | ✓ PASS |
| `bash -n` syntax check 3 scripts | per script | KHÔNG fail (SUMMARY records exit 0) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| **TOPO-01** | 01-01, 01-05 | Postgres init multi-DB + dynamic `make hub-init` | ✓ SATISFIED | `init-db.sh` tạo 4 DB + HNSW verify; `hub-init.sh` + Makefile targets dynamic add. Live verified 5 DB. |
| **TOPO-02** | 01-03, 01-05 | Per-hub Alembic + `make migrate-all` + CI lint head SHA | ✓ SATISFIED | `env.py` `-x hub`, `Makefile migrate-all`, `alembic-head-check.sh`, CI workflow step. Live verified head=0004 uniform. |
| **TOPO-03** | 01-04 | Cocoindex flow naming per-hub + APP_NAMESPACE per-hub | ✓ SATISFIED (code) | `resolve_cocoindex_app_name` + dynamic `cocoindex_app` build + `os.environ["APP_NAMESPACE"]` set trong `setup_cocoindex`. 9 unit test PASS. Runtime smoke deferred Phase 2 (acceptable per scope). |
| **TOPO-04** | 01-02, 01-05 | HUB_NAME isolation env + DB-level enforce | ✓ SATISFIED | `Settings._enforce_hub_dsn_match` model_validator fail-fast + integration test 5/5 PASS (E-V3-3 enforce). |

Tất cả 4 REQ-ID có evidence implementation. Không có orphan requirement (ROADMAP traceability table dòng 246-250 chỉ map TOPO-01..04 vào Phase 1; không có thêm REQ).

### Locked Decisions Honored

| Decision | Expected | Status | Evidence |
|----------|----------|--------|----------|
| **D-V3-01** (multi-DB cùng instance) | 4 DB hardcode v3.0 + dynamic add via hub-init.sh | ✓ HONORED | `HUBS=("yte" "duoc" "hcns")` array trong init-db.sh + `hub-init.sh` dynamic add (regex sanitize). |
| **GA-Phase1-A** (imperative bash loop + SELECT pg_database guard) | imperative bash, NOT `CREATE DATABASE IF NOT EXISTS` | ✓ HONORED | Cả init-db.sh (line 24-32) + hub-init.sh (line 52-59) dùng `SELECT 1 FROM pg_database WHERE datname=...` conditional. |
| **GA-Phase1-B** (APP_NAMESPACE per-hub + cocoindex_db_schema cố định "cocoindex") | namespace tách per-hub, schema giữ "cocoindex" | ✓ HONORED | `namespaced = f"medinet_{settings.hub_name}_prod"` (setup.py:80) + `cocoindex_db_schema: str = "cocoindex"` (config.py:54 — P7 preserve). |
| **GA-Phase1-C** (`make hub-init HUB=<name>` dynamic) | bash script chạy CREATE DB + ext + alembic upgrade head, KHÔNG cần docker compose down | ✓ HONORED | `hub-init.sh` 4-bước (CREATE/EXTENSION/HNSW/alembic) + Makefile target proxy chain (root → api → bash). |

### Risk Mitigations

| Risk | Mitigation Required | Status | Evidence |
|------|---------------------|--------|----------|
| **R-V3-3** (Alembic head drift) | `alembic-head-check.sh` + CI gate | ✓ MITIGATED | Script logic compare all heads = `HEADS[FIRST_HUB]`, exit 1 nếu drift; Makefile `migrate-all` chain script; CI workflow step "Apply migrate-all..." gọi `make migrate-all` → block PR nếu drift. |
| **R1** (HNSW 1536-dim) | Verify HNSW build trên init-db.sh + hub-init.sh | ✓ MITIGATED | Cả 2 script có block `CREATE TABLE _hnsw_dim_check (id serial primary key, v vector(1536)); CREATE INDEX ... USING hnsw (v vector_cosine_ops);`. Live verified `ix_chunks_vector_hnsw` trên 4 DB business. |
| **R5** (APP_NAMESPACE evolution per-hub) | Plan 04 setup_cocoindex set env per-hub | ✓ MITIGATED | `os.environ["APP_NAMESPACE"] = f"medinet_{settings.hub_name}_prod"` trước `coco.start_blocking()` + structured log event. |
| **E-V3-3** (DB-level isolation) | Settings validator + integration test | ✓ MITIGATED | `_enforce_hub_dsn_match` model_validator (fail-fast) + 5/5 integration test PASS (test_hub_isolation_db_level.py). |

### M2 Backward-Compat

| Preserve Item | Status | Evidence |
|---------------|--------|----------|
| `cocoindex_db_schema="cocoindex"` (P7) | ✓ PRESERVED | config.py:54 unchanged. |
| `compare_type=True` + `compare_server_default=True` (P20) | ✓ PRESERVED | env.py:187-188, 201-202 (offline + online modes). |
| `include_object` cocoindex schema filter (P7) | ✓ PRESERVED | env.py:160 (function def) + line 173 (`object_.schema == "cocoindex" → return False`). |
| M2 cocoindex state migration documented (BLOCKER 4) | ✓ DOCUMENTED | T-01-04-06 threat model + `COCOINDEX_APP_NAME_LEGACY` env fallback (flow.py:324) + post-deploy `UPDATE documents SET status='pending'` re-ingest reminder (Plan 04 SUMMARY + Plan 05 SUMMARY). |
| M2 documents COUNT=3 preserved | ✓ PRESERVED | Live: `SELECT COUNT(*) FROM documents` trong `medinet_central` = 3 (orchestrator pre-verification + spot-check). |
| Schema push DONE (Option B SAFE default) | ✓ DOCUMENTED | Plan 05 SUMMARY commits `9f62dee`, `9343020`, `5239b59`, `1fe8d9a` documented schema push runtime executed (option B preserve M2 volume). |

### Anti-Patterns Scanned

| File | Pattern Searched | Severity | Impact |
|------|------------------|----------|--------|
| `api/scripts/init-db.sh` | TODO/FIXME/placeholder, empty handlers | — | Sạch (68 LOC, all imperative bash + psql commands functional). |
| `api/scripts/hub-init.sh` | TODO/FIXME, hardcoded empty | — | Sạch (82 LOC, regex sanitize + 4 bước functional). |
| `api/scripts/alembic-head-check.sh` | TODO/FIXME, stub returns | — | Sạch (59 LOC, compare logic exit 0/1 functional). |
| `api/app/config.py` | placeholder, fallback unconditional | — | Sạch (validator raises real `ValueError`, helper deterministic). |
| `api/app/db/session.py` | hub_name branching, cocoindex fallback | — | Sạch (verified Plan 02 Task 3, KHÔNG có drift). |
| `api/app/rag/flow.py` | M2 hardcode `medinet_wiki_ingest` còn sót | — | KHÔNG còn — `grep -c 'name="medinet_wiki_ingest"' = 0` (only comment `<M2-legacy-name>` placeholder). |
| `api/app/rag/setup.py` | Stub log, missing env set | — | Sạch — `os.environ["APP_NAMESPACE"] = namespaced` thực sự ghi env + structured log. |
| `api/migrations/env.py` | M2 patterns dropped | — | Preserved (include_object, compare_type=True, compare_server_default=True intact). |
| `api/Makefile` + `Makefile` | hub-init proxy missing | — | Sạch (chain root → api → bash đầy đủ). |
| `api/tests/integration/test_hub_isolation_db_level.py` | `.replace("postgresql://", "postgresql://", 1)` no-op (W6) | — | Sạch — fixture dùng `contextlib.closing(psycopg2.connect)` + `with conn.cursor()` (W6 fix applied). |

**Behavioral spot-checks: all 9/9 PASS** (live DB state, M2 preservation, HNSW indices, vector extension, pgvector type, migration files, schema replication, bash syntax across 3 scripts).

### Human Verification Required

**None.** Phase 1 scope hoàn toàn verify được programmatically:
- File integrity: grep + bash syntax check
- Live DB state: docker exec psql query
- Unit + integration tests: pytest runtime (166/166 unit + 5/5 integration documented PASS)
- CI workflow YAML: yaml.safe_load valid
- Code-level cocoindex per-hub naming (SC3): unit test cover; runtime cocoindex flow startup smoke deferred Phase 2 (acceptable per orchestrator scope — Phase 1 standalone OK).

### Phase 1 Close Confirmation

**4/4 Success Criteria PASS:**

1. ✓ **SC1** — Live: 5 DB exist (`medinet_central, medinet_cocoindex, medinet_hub_duoc, medinet_hub_hcns, medinet_hub_yte`). HNSW index `ix_chunks_vector_hnsw` + vector extension xác nhận trên 4 DB business. Init-db.sh + hub-init.sh code path verified.

2. ✓ **SC2** — Live: 4 business DB cùng head `0004`. Code chain `make migrate-all` → loop alembic → `alembic-head-check.sh` exit 0 nếu match. CI workflow step wired (R-V3-3 mitigation).

3. ✓ **SC3** — Code-level: `resolve_cocoindex_app_name` + dynamic `cocoindex_app` build + `APP_NAMESPACE` per-hub set trong setup_cocoindex. 9 unit test PASS. Runtime startup smoke ở Phase 2 (acceptable v3.0-a scope).

4. ✓ **SC4** — Settings validator fail-fast (raise "DSN mismatch hub_name") + 5/5 integration test PASS với testcontainers (E-V3-3 DB-level enforce).

**Score:** 4/4 truths verified · **Status:** passed · **No gaps · No human verification required**

---

_Verified: 2026-05-21 (initial)_
_Verifier: Claude (gsd-verifier, Opus 4.7 [1M context])_
