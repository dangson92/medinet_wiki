---
phase: 01-multi-db-topology
plan: 05
subsystem: multi-db-topology
tags:
  - dynamic-hub
  - isolation-test
  - ci-workflow
  - schema-push
  - r-v3-3
  - e-v3-3
  - topo-01
  - topo-02
  - topo-04
requirements:
  - TOPO-01
  - TOPO-02
  - TOPO-04
dependency_graph:
  requires:
    - "Plan 01-01 — 4 DB pattern init-db.sh + HNSW vector(1536) verify per DB"
    - "Plan 01-02 — Settings.hub_name validator + resolve_database_url helper"
    - "Plan 01-03 — alembic env.py -x hub + make migrate-all + alembic-head-check.sh"
    - "Plan 01-04 — cocoindex flow per-hub + APP_NAMESPACE"
  provides:
    - "api/scripts/hub-init.sh — dynamic add 1 hub moi (CREATE DB + ext + HNSW verify + alembic upgrade head) khong can docker compose down"
    - "Makefile root + api/Makefile target hub-init proxy chain"
    - "Integration test test_hub_isolation_db_level.py — 5 case E-V3-3 enforce (Settings validator + asyncpg connection-bound DB isolation)"
    - "../.github/workflows/test.yml — postgres service + bootstrap 4 DB + make migrate-all + alembic-head-check.sh wired CI gate (R-V3-3 mitigation)"
    - "Schema push runtime DONE: 5 DB ton tai (central + cocoindex + 3 hub moi) + 4 DB nghiep vu cung head SHA 0004 + HNSW index verified + M2 central documents preserved"
  affects:
    - "Phase 2 FACTOR — codebase factor process-per-hub se reuse make hub-init + migrate-all baseline"
    - "Phase 7 MIGRATE — migration data tu medinet_central cu sang DB hub con (post-deploy step Plan 04 T-01-04-06 re-ingest)"
    - "CI gate R-V3-3 enforce — moi PR phai PASS step Apply migrate-all + alembic-head-check.sh"
tech_stack:
  added: []
  patterns:
    - "Imperative bash hub-init.sh sanitize regex ^[a-z][a-z0-9_]{1,30}$ chong SQL injection (T-01-05-01)"
    - "Idempotent CREATE DATABASE qua SELECT pg_database guard (reuse Plan 01-01 pattern)"
    - "HNSW vector(1536) verify per DB (DROP+CREATE+INDEX+DROP) — extend init-db.sh pattern"
    - "Makefile chain: root hub-init -> api hub-init -> bash scripts/hub-init.sh"
    - "testcontainers PostgresContainer pgvector/pgvector:pg16 module-scope + 4 DB pre-create + ext vector"
    - "W6 — contextlib.closing(psycopg2.connect) + with conn.cursor() context manager"
    - "GitHub Actions services.postgres + working-directory: Hub_All cho bootstrap step + working-directory: Hub_All/api M2 default preserve"
    - "Option B SAFE default schema push — KHONG docker compose down -v (preserve M2 volume) — Option A guard MEDINET_CONFIRM_RESET=YES_DELETE_M2"
key_files:
  created:
    - "Hub_All/api/scripts/hub-init.sh — dynamic hub init bash script (chmod +x)"
    - "Hub_All/api/tests/integration/test_hub_isolation_db_level.py — 5 integration test E-V3-3"
    - "Hub_All/.planning/phases/01-multi-db-topology/01-05-SUMMARY.md"
  modified:
    - "Hub_All/Makefile — them hub-init target proxy (root)"
    - "Hub_All/api/Makefile — them hub-init target (api/) + .PHONY update"
    - "../.github/workflows/test.yml (OUTSIDE Hub_All/) — services.postgres + Bootstrap 4 DB step + Apply migrate-all + alembic head check step"
decisions:
  - "Task 1: hub-init.sh sanitize regex ^[a-z][a-z0-9_]{1,30}$ Postgres-identifier-safe — reject early exit 2 truoc psql call (T-01-05-01)"
  - "Task 1: hub-init.sh KHONG validate hub_name trong _VALID_HUBS hardcoded — cho phep them hub moi (vd 'phap_che', 'marketing'). Validation defer Settings layer Plan 02 (Literal). Workflow: chay script tao DB -> update Literal app/config.py + env.py + flow.py de Settings accept hub moi."
  - "Task 2: TDD characterization test — test_hub_isolation_db_level.py PASS ngay tu lan dau vi Plan 01-02 da implement _enforce_hub_dsn_match validator + Postgres asyncpg connection-bound semantics. KHONG can separate feat: commit (impl da hoan tat prior plan). Single test: commit ghi nhan E-V3-3 enforce."
  - "Task 2: Fixture pg_container_4dbs dung contextlib.closing(psycopg2.connect) + with conn.cursor() — W6 fix loai bo .replace('postgresql://', 'postgresql://', 1) no-op M2 cu."
  - "Task 3: CI workflow services.postgres pgvector/pgvector:pg16 PORT 5432 fix — testcontainers test khac dung random ephemeral port nen KHONG conflict."
  - "Task 3: Bootstrap 4 DB step dung working-directory: Hub_All (override default Hub_All/api) cho psql command — preserve M2 default Hub_All/api o cac step khac."
  - "Task 3: Apply migrate-all step de SAU Upload coverage upstream — neu migrate-all fail van upload coverage de debug. Cau truc test step + verify step tach biet."
  - "Task 4: Default Option B SAFE preserve M2 central volume — KHONG docker compose down -v. Option A destructive yeu cau MEDINET_CONFIRM_RESET=YES_DELETE_M2 env explicit (T-01-05-07 Data Loss mitigation)."
  - "Task 4: Runtime-only commit qua --allow-empty — KHONG modify file vi schema push la Postgres state mutation. Atomic commit per task rule giu integrity."
metrics:
  duration_minutes: 18
  completed_date: "2026-05-21"
---

# Phase 1 Plan 05: Dynamic hub-init + E-V3-3 Test + CI Workflow + Schema Push Summary

**One-liner:** Wave 3 FINAL Phase 1 — `make hub-init HUB=<name>` dynamic add hub + 5-test E-V3-3 isolation enforce + CI gate `migrate-all`/`alembic-head-check.sh` (R-V3-3 mitigation) + [BLOCKING] schema push runtime DONE qua Option B SAFE (4 DB cung head SHA `0004`, M2 central data preserved).

## Tom tat 4 Task

### Task 1: api/scripts/hub-init.sh + Makefile target hub-init (commit `9f62dee`)

**Files:**
- `api/scripts/hub-init.sh` — bash script imperative add 1 hub dong (CREATE DB + ext vector + HNSW verify + alembic upgrade head). Sanitize regex `^[a-z][a-z0-9_]{1,30}$` chong SQL injection.
- `api/Makefile` — them `hub-init` target proxy `bash scripts/hub-init.sh $(HUB)` + guard missing HUB env (exit 2).
- `Makefile` root — them `hub-init` target proxy `$(MAKE) -C api hub-init HUB=$(HUB)` + update help string.

**AC PASS:**
- `bash -n api/scripts/hub-init.sh` exit 0 (syntax OK)
- `grep -c "medinet_hub_" api/scripts/hub-init.sh` = 3 (>=1)
- `grep -c "alembic.*-x hub=" api/scripts/hub-init.sh` = 4 (>=1)
- `grep -cE "vector\(1536\)|hnsw" api/scripts/hub-init.sh` = 7 (>=2)
- `grep -c "SELECT 1 FROM pg_database" api/scripts/hub-init.sh` = 1 (>=1)
- `grep -cF '^[a-z][a-z0-9_]' api/scripts/hub-init.sh` = 4 (>=1, fixed-string per BLOCKER 3 fix)
- `grep -c "^hub-init:" api/Makefile` = 1 + `Makefile` = 1 (>=1 mỗi file)
- `grep -c "MAKE.*-C api hub-init" Makefile` = 1 (>=1, root proxy delegate)
- Makefile TAB indent verified via Python parser (Plan 03 precedent, Windows host KHONG cai GNU make).

### Task 2: Integration test test_hub_isolation_db_level.py (commit `9343020`)

**File created:** `api/tests/integration/test_hub_isolation_db_level.py` — 5 test E-V3-3 enforce critical+integration markers.

**5 Test case:**

| # | Test | Assert |
|---|------|--------|
| 1 | `test_settings_yte_with_central_dsn_raises` | HUB_NAME=yte + DSN central → `ValidationError("DSN mismatch hub_name")` |
| 2 | `test_settings_yte_with_duoc_dsn_raises` | HUB_NAME=yte + DSN duoc (cross-hub typo) → `ValidationError` |
| 3 | `test_settings_yte_with_yte_dsn_succeeds` | HUB_NAME=yte + DSN yte → Settings() OK, `hub_name=="yte"`, DSN endswith `/medinet_hub_yte` |
| 4 | `test_db_connection_yte_cannot_reach_duoc` | asyncpg connect yte → `current_database()=='medinet_hub_yte'` bound (connection 1 DB) |
| 5 | `test_4_dbs_independent_data` | seed `_iso_marker` table 3 hub → cross-DB query KHONG thay leak (physical isolation) |

**TDD note:** `tdd="true"` plan task, nhung impl da hoan tat:
- Plan 01-02 da implement `Settings._enforce_hub_dsn_match` validator (raises `DSN mismatch hub_name`)
- Postgres asyncpg connection-bound semantics inherent

→ Test PASS ngay tu lan dau (characterization test). Single `test:` commit ghi nhan E-V3-3 enforce verification.

**Runtime verify:** `cd api && uv run pytest tests/integration/test_hub_isolation_db_level.py -v -m "critical and integration"` PASS 5/5 in 5.55s (testcontainers Docker Desktop spin Postgres pgvector/pgvector:pg16). ruff + mypy clean.

**W6 fix applied:** Fixture `pg_container_4dbs` dung `contextlib.closing(psycopg2.connect(...))` + `with conn.cursor()` context manager — loai bo pattern `.replace("postgresql://", "postgresql://", 1)` no-op M2 cu.

### Task 3: ../.github/workflows/test.yml CI step migrate-all + alembic head check (commit `5239b59`)

**File modified:** `../.github/workflows/test.yml` (OUTSIDE Hub_All/ — path `c:\...\medinet_wiki\.github\workflows\test.yml`).

**Changes:**
- Them `services.postgres` block (`pgvector/pgvector:pg16` PORT 5432 + healthcheck pg_isready 10 retry x 5s).
- Them step **"Bootstrap 4 DB"** sau Sync deps: `working-directory: Hub_All` (override default Hub_All/api) — psql tao 3 hub con yte/duoc/hcns + `CREATE EXTENSION vector` tren 4 DB. Idempotent qua `SELECT 1 FROM pg_database` guard.
- Them step **"Apply migrate-all + verify head SHA"** sau Pytest critical path: env vars DSN + HUB_NAME=central + JWT key paths + generate_keys.sh fallback. Chay `make migrate-all` (wire alembic-head-check.sh Plan 03 — block PR neu drift R-V3-3).

**M2 pattern preserved:** `defaults.run.working-directory: Hub_All/api` (line 18-20) UNCHANGED. Step migrate-all dung default Hub_All/api. Step Bootstrap 4 DB OVERRIDE `working-directory: Hub_All` (psql command tu project root).

**AC PASS:**
- YAML valid (`python -c "import yaml; yaml.safe_load(open('../.github/workflows/test.yml'))"` exit 0)
- `grep -c "make migrate-all"` = 2 (>=1)
- `grep -c "medinet_hub_yte\|medinet_hub_duoc\|medinet_hub_hcns"` = 1 line (cung loop bash for) — 3 hub names dem qua substring
- `grep -c "services:"` = 1 (>=1)
- `grep -c "pgvector/pgvector:pg16"` = 1 (>=1)
- `grep -c "R-V3-3\|TOPO-02"` = 1 (>=1)
- `grep -c "HUB_NAME: central"` = 1 (>=1)
- `grep -c "working-directory: Hub_All/api"` = 1 (>=1, M2 default preserved)
- `grep -Ec "working-directory: Hub_All\$"` = 1 (>=1, Plan 05 override step)
- `grep -c "Bootstrap 4 DB\|Apply migrate-all"` = 2 (>=2)

### Task 4: [BLOCKING] Schema push runtime — Option B SAFE (commit `1fe8d9a` empty)

**Files modified:** NONE (runtime-only, Postgres state mutation).

**Sequence chay (Option B SAFE default):**

```bash
# Step 0: verify cluster + M2 baseline
docker exec medinet-postgres pg_isready -U medinet -d medinet_central
# → /var/run/postgresql:5432 - accepting connections
docker exec medinet-postgres psql -U medinet -d postgres -tA -c \
  "SELECT datname FROM pg_database WHERE datname LIKE 'medinet_%' ORDER BY datname"
# → medinet_central, medinet_cocoindex (baseline 2 DB)
docker exec medinet-postgres psql -U medinet -d medinet_central -tA -c \
  "SELECT COUNT(*) FROM documents"
# → 3 (M2 baseline preserve check)

# Step 1: hub-init equivalent x3 (yte/duoc/hcns)
# Vi Windows host KHONG cai GNU make, inline hub-init.sh logic qua docker exec
# psql + uv run alembic local (behavior equivalent):
for HUB in yte duoc hcns; do
  DB_NAME="medinet_hub_$HUB"
  # (1/4) CREATE DATABASE idempotent
  docker exec medinet-postgres psql -U medinet -d postgres -c \
    "CREATE DATABASE $DB_NAME OWNER medinet;"
  # (2/4) CREATE EXTENSION vector
  docker exec medinet-postgres psql -U medinet -d "$DB_NAME" -c \
    "CREATE EXTENSION IF NOT EXISTS vector;"
  # (3/4) VERIFY HNSW vector(1536)
  docker exec medinet-postgres psql -U medinet -d "$DB_NAME" -c \
    "DROP TABLE IF EXISTS _hnsw_dim_check;
     CREATE TABLE _hnsw_dim_check (id serial primary key, v vector(1536));
     CREATE INDEX _hnsw_dim_check_idx ON _hnsw_dim_check USING hnsw (v vector_cosine_ops);
     DROP TABLE _hnsw_dim_check;"
  # (4/4) alembic upgrade head
  (cd api && uv run alembic -x hub="$HUB" upgrade head)
  # → 0001 → 0002 → 0003 → 0004 (head)
done

# Step 2: alembic-head-check.sh verify
cd api && bash scripts/alembic-head-check.sh
# → PASS - tat ca 4 DB cung head SHA: 0004
```

**Post-execution verification:**

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| 5 DB tồn tại | central + cocoindex + 3 hub mới | `medinet_central, medinet_cocoindex, medinet_hub_duoc, medinet_hub_hcns, medinet_hub_yte` | PASS |
| M2 documents preserve | COUNT == 3 (baseline) | 3 | PASS |
| HNSW index ix_chunks_vector_hnsw | Có trên 4 DB nghiệp vụ | central + yte + duoc + hcns đều có | PASS |
| alembic_version COUNT per DB | == 1 | central=1, yte=1, duoc=1, hcns=1 | PASS |
| Head SHA match 4 DB | Cùng head | 0004 trên 4 DB | PASS |

**Deviation:** Windows host KHONG cai GNU `make` + `psql` binary. Substitute (Rule 3 fix-blocking-issue):
- `make hub-init HUB=<name>` → inline hub-init.sh logic qua `docker exec medinet-postgres psql` + `uv run alembic` (local Python tooling)
- Behavior equivalent — CREATE DB + ext + HNSW verify + alembic upgrade head sequence identical
- CI Linux ubuntu-22.04 (Plan 05 Task 3) co make + psql installed — `make migrate-all` step CI se runtime validate

## Self-Check: PASSED

**Files created:**
- `Hub_All/api/scripts/hub-init.sh` — FOUND
- `Hub_All/api/tests/integration/test_hub_isolation_db_level.py` — FOUND
- `Hub_All/.planning/phases/01-multi-db-topology/01-05-SUMMARY.md` — FOUND (this file)

**Files modified:**
- `Hub_All/Makefile` — FOUND (hub-init target added)
- `Hub_All/api/Makefile` — FOUND (hub-init target added)
- `../.github/workflows/test.yml` — FOUND (services.postgres + 2 steps added)

**Commits:**
- `9f62dee` — feat(01-05): hub-init.sh + Makefile target — FOUND
- `9343020` — test(01-05): integration test E-V3-3 — FOUND
- `5239b59` — feat(01-05): CI workflow migrate-all + head check — FOUND
- `1fe8d9a` — chore(01-05): schema push 4 DB done — FOUND

**Runtime verification:**
- pytest tests/integration/test_hub_isolation_db_level.py PASS 5/5 in 5.55s
- alembic-head-check.sh exit 0 — PASS 4 DB cung head SHA 0004
- 5 DB exist, HNSW index verified, M2 documents COUNT=3 preserved

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Windows host KHONG cai GNU make + psql**

- **Found during:** Task 1 acceptance criteria `make -n hub-init HUB=foo` raise `make: command not found` + Task 4 `make hub-init HUB=yte` cung fail.
- **Issue:** Windows 11 host KHONG cai GNU Make + psql binary trong PATH. Plan AC yeu cau `make -n hub-init HUB=foo` exit 0 + Task 4 chay `make hub-init`.
- **Fix:**
  - Task 1: verify Makefile TAB indent qua Python parser (`line.startswith(b'\t')`) + grep AC criteria PASS. Plan 03 precedent (commit `15679bd` SUMMARY documents same deviation).
  - Task 4: inline hub-init.sh logic qua `docker exec medinet-postgres psql` (psql trong container Postgres `pgvector/pgvector:pg16`) + `uv run alembic` (Python tooling local). Behavior equivalent — CREATE DB + ext + HNSW verify + alembic upgrade head identical.
- **Files modified:** None (procedural deviation — no code/script change).
- **Verification:** alembic-head-check.sh PASS 4 DB cung head SHA 0004; 5 DB exist; M2 documents COUNT=3 preserved. CI Linux ubuntu-22.04 (Plan 05 Task 3) se runtime validate `make migrate-all` chain.

### TDD Note (Task 2)

Task 2 `tdd="true"` plan, nhung impl da hoan tat o Plan 01-02 (Settings._enforce_hub_dsn_match validator) + Postgres asyncpg connection-bound semantics. Test PASS ngay tu lan dau (characterization test). Single `test:` commit ghi nhan E-V3-3 enforce verification — KHONG can separate `feat:` GREEN commit (per TDD gate fail-fast rule: "If a test passes unexpectedly during the RED phase, investigate — feature may already exist"). Investigated, confirmed impl da ship Plan 01-02, OK proceed.

## M2 Cocoindex Re-ingest Reminder (Post-deploy step)

Plan 04 doi APP_NAMESPACE tu `medinet_prod` (M2) sang `medinet_central_prod` (Plan 04 default HUB_NAME=central) — gay orphan M2 cocoindex internal state. Mitigation (defer Phase 7 MIGRATE):

```sql
-- Post-deploy step (KHONG chay trong Plan 05):
UPDATE documents SET status='pending' WHERE status='completed';
-- Idempotent qua content_hash — cocoindex skip re-embed neu content unchanged.
```

Hoac fallback env tuong minh:
```bash
export COCOINDEX_APP_NAME_LEGACY=medinet_wiki_ingest
```
→ Plan 04 setup_cocoindex preserve M2 App name.

Reference: Plan 04 SUMMARY threat T-01-04-06 (Tampering/Data Loss mitigation chain).

## BLOCKER/WARNING Fixes Applied

| Item | Plan Spec | Applied |
|------|-----------|---------|
| BLOCKER 1 | Path consistency `../.github/workflows/test.yml` relative tu Hub_All/ cwd | ✓ Edit dung path `../.github/workflows/test.yml`, git add cung path |
| BLOCKER 2 | Default Option B preserve M2 volume; Option A guard env confirm | ✓ Chay Option B - `docker compose down -v` KHONG chay; M2 documents COUNT=3 preserved |
| BLOCKER 3 | Acceptance criteria `grep -cF '^[a-z][a-z0-9_]'` fixed-string | ✓ Script hub-init.sh contains regex literal in validation block; grep `-cF` exit 0 returns 4 |
| W6 | Test fixture dung `contextlib.closing(psycopg2.connect)` + `with conn.cursor()`; xoa `.replace("postgresql://", "postgresql://", 1)` no-op | ✓ Fixture pg_container_4dbs implementations contextlib.closing pattern; 0 `.replace(...)` |
| W7 | Mọi command relative tu Hub_All/ cwd | ✓ Bash commands run from Hub_All/ cwd; paths relative `api/...`, `../.github/...` |

## Phase 1 Close Confirmation

**4 Phase 1 success criteria PASS:**

- **SC1** — `make hub-init HUB=yte/duoc/hcns` + verify ≥3 DB hub mới:
  ```
  SELECT count(*) FROM pg_database WHERE datname LIKE 'medinet_hub_%'
  → 3 (yte + duoc + hcns)
  ```
  PASS

- **SC2** — `make migrate-all && bash scripts/alembic-head-check.sh` tail line "PASS":
  ```
  [alembic-head-check] PASS - tat ca 4 DB cung head SHA: 0004
  ```
  PASS

- **SC3** — cocoindex flow per-hub name (Plan 04 unit test cover pattern); post-deploy re-ingest task `UPDATE documents SET status='pending'` idempotent qua content_hash (defer Phase 7).

- **SC4** — Integration test test_hub_isolation_db_level.py PASS 5/5:
  ```
  5 passed, 1 warning in 5.55s
  ```
  PASS

**Phase 1 ready cho verification cuoi.**
