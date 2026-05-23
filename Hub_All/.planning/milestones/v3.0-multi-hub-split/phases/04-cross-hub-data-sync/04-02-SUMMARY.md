---
phase: 04-cross-hub-data-sync
plan: 02
subsystem: sync
tags:
  - settings
  - config
  - docker-compose
  - validator
  - pydantic-settings
requirements:
  - SYNC-01
  - SYNC-03
  - SYNC-04
dependency_graph:
  requires:
    - Phase 1 Plan 01-02 Settings _enforce_hub_dsn_match validator pattern carry forward
    - Phase 3 Plan 03-02 _enforce_central_jwks_url_for_hub validator pattern (model_validator mode=after)
    - Phase 3 Plan 03-04 _enforce_central_url_for_hub validator pattern
    - Phase 2 Plan 02-05 FACTOR-04 docker-compose.override.yml.template sed substitute pattern
    - Plan 04-01 sync_outbox migration 0005 (env.py helper ready — consumer Plan 04-03 worker)
  provides:
    - "Settings.hub_id: str | None (UUID4 field_validator format check)"
    - "Settings.central_sync_dsn: str | None (asyncpg DSN trỏ medinet_central)"
    - "Settings.checksum_hub_dsns_json: str | None (JSON dict env qua property parse)"
    - "Settings.sync_batch_size/sync_poll_interval/sync_max_attempts/sync_backoff_seconds (config-driven worker)"
    - "3 model_validator hub con/central required (boot fail-fast Phase 1/3 pattern carry forward)"
    - "1 length validator _validate_backoff_length (max_attempts - 1 enforce)"
    - "1 helper property checksum_hub_dsns -> dict[str, str] (cached JSON parse)"
    - "docker-compose.yml 3 hub con HUB_ID + CENTRAL_SYNC_DSN; central CHECKSUM_HUB_DSNS_JSON optional"
    - "docker-compose.override.yml.template FACTOR-04 extend {{HUB_UPPER}}_ID placeholder + CENTRAL_SYNC_DSN"
  affects:
    - Plan 04-03 (worker consume Settings.sync_batch_size/poll/max/backoff + central_sync_dsn pool spawn)
    - Plan 04-04 (lifespan hub con spawn worker task → settings.hub_name != central branch)
    - Plan 04-05 (chunks.hub_id INSERT cocoindex flow consume settings.hub_id)
    - Plan 04-06 (central checksum scheduler consume settings.checksum_hub_dsns property dict)
    - Phase 7 MIGRATE-01 (operator deploy HUB_*_ID export workflow + CHECKSUM_HUB_DSNS_JSON compile)
tech-stack:
  added: []
  patterns:
    - "Pydantic v2 @model_validator(mode='after') boot fail-fast (Phase 1/3 carry forward)"
    - "Pydantic v2 @field_validator(mode='before') + NoDecode CSV parse (cors_allowed_origins carry forward)"
    - "Pydantic v2 @field_validator(mode='after') UUID format check (uuid.UUID stdlib)"
    - "Helper @property JSON parse cached read-once (D-V3-Phase4-C3)"
    - "Docker compose env interpolation `${VAR:?msg}` fail-loud + `${VAR:-}` optional default"
key-files:
  created:
    - api/tests/unit/test_config_phase4_fields.py (266 LOC, 17 test)
    - .planning/phases/04-cross-hub-data-sync/04-02-SUMMARY.md
  modified:
    - api/app/config.py (+143 LOC — 7 field + 2 field_validator + 3 model_validator + 1 length validator + 1 property)
    - docker-compose.yml (+19 LOC — 3 hub con HUB_ID/CENTRAL_SYNC_DSN + central CHECKSUM_HUB_DSNS_JSON)
    - docker-compose.override.yml.template (+10 LOC — FACTOR-04 placeholder HUB_ID + CENTRAL_SYNC_DSN)
    - api/tests/unit/test_config_hub_name.py (regression — 2 test setenv Phase 4 fields)
    - api/tests/unit/test_config_hub_name_dynamic.py (regression — _set_env helper)
    - api/tests/unit/test_config_jwks.py (regression — _common_env helper)
    - api/tests/unit/test_main_factory.py (regression — _setup_env helper)
    - api/tests/unit/test_auth_router_hub_redirect.py (regression — _setup_env helper)
    - api/tests/unit/test_get_current_user_jwks_branch.py (regression — _common_hub_env helper)
    - api/tests/unit/test_jwks_publish.py (regression — _setup_env helper)
    - api/tests/unit/test_flow_per_hub_naming.py (regression — subprocess env dict yte test)
decisions:
  - "D-V3-Phase4-D2 LOCKED: hub_id field UUID4 str từ env HUB_ID + field_validator format check + model_validator hub con required (boot fail-loud)"
  - "D-V3-Phase4-A1 LOCKED: central_sync_dsn field asyncpg DSN từ env CENTRAL_SYNC_DSN + model_validator hub con required"
  - "D-V3-Phase4-A5 LOCKED: sync_batch_size=100 + sync_poll_interval=5.0 + sync_max_attempts=5 + sync_backoff_seconds=[1,5,30,120] defaults (operator tune via env override)"
  - "D-V3-Phase4-C3 LOCKED: checksum_hub_dsns_json optional ở central (default None — scheduler tick no-op khi dict empty); JSON parseable + dict[str,str] type check fail-fast"
  - "Implementation: backoff length validator _validate_backoff_length enforce length==max_attempts-1 — boot fail-loud thay vì IndexError worker runtime mid-batch (T-04-02-05 DoS mitigation)"
  - "Implementation: helper property checksum_hub_dsns -> dict[str,str] (read-once JSON parse; validator đã verify format)"
  - "Implementation: docker-compose 3 hub con `${HUB_*_ID:?error}` fail-loud syntax (operator must export shell env trước `docker compose up`)"
  - "Implementation: docker-compose central `${CHECKSUM_HUB_DSNS_JSON:-}` default empty string (deploy lần đầu CHƯA register hub con)"
  - "Implementation: docker-compose.override.yml.template FACTOR-04 extend `${HUB_{{HUB_UPPER}}_ID:?...}` placeholder cho dynamic hub (hub-add.sh sed substitute Plan 02-05 carry forward)"
metrics:
  duration_minutes: 22
  completed_date: 2026-05-22
  task_count: 2
  commit_count: 3
  file_count: 12
  test_count: 17
  test_pass_rate: "17/17 (100%)"
  regression_pass_rate: "310/310 unit (8 file fixture updated Rule 3) — KHÔNG break"
---

# Phase 4 Plan 02: Settings Phase 4 Sync Config + Docker-compose Env Wire Summary

**One-liner:** Settings 7 field mới Phase 4 (hub_id UUID4 + central_sync_dsn + checksum_hub_dsns_json + sync_batch_size=100 + sync_poll_interval=5.0 + sync_max_attempts=5 + sync_backoff_seconds=[1,5,30,120]) + 2 field_validator (UUID format + CSV parse) + 3 model_validator (hub con/central required boot fail-fast) + 1 length validator + 1 helper property `checksum_hub_dsns` + docker-compose 3 hub con env wire `${HUB_*_ID:?error}` fail-loud + central CHECKSUM_HUB_DSNS_JSON optional + FACTOR-04 template extend `${HUB_{{HUB_UPPER}}_ID:?...}` placeholder — đóng SYNC-01/03/04 Settings layer cho Plan 04-03 worker + Plan 04-06 checksum scheduler.

---

## Files Created/Modified

### Created

| Path | LOC | Purpose |
|------|-----|---------|
| `api/tests/unit/test_config_phase4_fields.py` | 266 | 17 unit test cover 7 field + 3 model_validator + 1 length validator + 1 property + boundary cases (CSV parse, UUID format, JSON dict type check) |

### Modified

| Path | Change | Purpose |
|------|--------|---------|
| `api/app/config.py` | +143 LOC | 7 field + 2 field_validator (UUID + CSV) + 3 model_validator (hub_id/sync_dsn/checksum_json) + 1 length validator + 1 property |
| `docker-compose.yml` | +19 LOC | 3 hub con HUB_ID + CENTRAL_SYNC_DSN (`${HUB_*_ID:?msg}` fail-loud) + central CHECKSUM_HUB_DSNS_JSON optional |
| `docker-compose.override.yml.template` | +10 LOC | FACTOR-04 dynamic hub placeholder `${HUB_{{HUB_UPPER}}_ID:?...}` + CENTRAL_SYNC_DSN |
| 8 file test cũ | +7-10 LOC mỗi file | Rule 3 regression auto-fix — `_setup_env` helper auto-set HUB_ID + CENTRAL_SYNC_DSN cho hub con |

---

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| `5da264d` | test | Task 1 RED — failing test Settings 5 field Phase 4 sync + 3 validator (17 test FAIL AttributeError sync_batch_size) |
| `20fc792` | feat | Task 1 GREEN — 7 field + 2 field_validator + 3 model_validator + 1 length validator + 1 property + 8 file test fixture regression (Rule 3 auto-fix HUB_ID + CENTRAL_SYNC_DSN setenv pattern carry forward Plan 03-02/03-04) |
| `50643d3` | feat | Task 2 — docker-compose 3 hub con env + central + FACTOR-04 template extend |

**Total:** 3 commits atomic (RED test + GREEN feat config + feat docker-compose).

---

## Test Results

### test_config_phase4_fields.py — 17/17 PASS (100%)

| Test | Validates |
|------|-----------|
| `test_central_boot_ok_without_phase4_fields` | Central aggregator KHÔNG required hub_id/central_sync_dsn (D-V3-Phase4-D2 — aggregator KHÔNG own data) |
| `test_hub_con_requires_hub_id[yte/duoc/hcns/phap_che]` (4 parametrize) | Hub con + HUB_ID=None → ValidationError "HUB_ID" (T-04-02-01 Tampering mitigation) |
| `test_hub_con_hub_id_invalid_uuid_raises` | HUB_ID="not-a-uuid" → ValidationError "hub_id invalid UUID" (T-04-02-03 Tampering mitigation; field_validator) |
| `test_hub_con_requires_central_sync_dsn` | Hub con + CENTRAL_SYNC_DSN=None → ValidationError "CENTRAL_SYNC_DSN" (T-04-02-02 DoS worker spawn fail mitigation) |
| `test_hub_con_with_all_required_fields_ok` | Hub con + HUB_ID UUID4 + CENTRAL_SYNC_DSN → boot OK |
| `test_central_without_checksum_hub_dsns_json_ok` | Central deploy lần đầu CHƯA register hub con → CHECKSUM_HUB_DSNS_JSON=None OK + property = {} |
| `test_central_checksum_hub_dsns_property_parse` | JSON dict valid → property parse `{"yte": "...", "duoc": "..."}` |
| `test_central_checksum_hub_dsns_invalid_json_raises` | CHECKSUM_HUB_DSNS_JSON="not-json" → ValidationError "invalid JSON" (T-04-02-03 mitigation) |
| `test_central_checksum_hub_dsns_not_dict_raises` | JSON list thay vì dict → ValidationError "dict" |
| `test_sync_defaults_match_d_v3_phase4_a5` | Defaults sync_batch_size=100 + sync_poll_interval=5.0 + sync_max_attempts=5 + sync_backoff_seconds=[1,5,30,120] |
| `test_sync_backoff_seconds_csv_parse` | env SYNC_BACKOFF_SECONDS="2,10,60,300" → list [2,10,60,300] (NoDecode CSV pattern carry forward) |
| `test_backoff_length_mismatch_raises` | max_attempts=3 + backoff length=4 → ValidationError "length mismatch" (T-04-02-05 DoS mitigation) |
| `test_backoff_length_match_custom_max_attempts` | max_attempts=3 + backoff length=2 → boot OK (operator tune scenario) |
| `test_sync_batch_and_poll_override` | env SYNC_BATCH_SIZE=50 + SYNC_POLL_INTERVAL=2.5 → Settings load đúng (float precision) |

**Duration:** 0.30s. **Pass rate:** 17/17 (100%).

### Regression — 310/310 PASS (full unit suite)

| Suite | Result |
|-------|--------|
| `test_config_hub_name.py` (Phase 1 Plan 01-02 + Plan 02-05 dynamic) | 11/11 PASS (regression update: test 2 + test_dsn_with_query_string_validates setenv HUB_ID+CENTRAL_SYNC_DSN) |
| `test_config_hub_name_dynamic.py` (Plan 02-05 FACTOR-04) | 29/29 PASS (regression: _set_env helper auto-set) |
| `test_config_jwks.py` (Plan 03-02) | 13/13 PASS (regression: _common_env helper auto-set hub con only) |
| `test_main_factory.py` (Plan 02-01 FACTOR-01) | 9/9 PASS (regression: _setup_env helper) |
| `test_auth_router_hub_redirect.py` (Plan 03-04) | 10/10 PASS (regression: _setup_env helper) |
| `test_get_current_user_jwks_branch.py` (Plan 03-03 SSO-04 E4) | 8/8 PASS (regression: _common_hub_env helper) |
| `test_jwks_publish.py` (Plan 03-01) | 9/9 PASS (regression: _setup_env helper) |
| `test_flow_per_hub_naming.py` (Phase 1 Plan 01-04) | 4/4 PASS (regression: subprocess env dict test_module_app_name_per_hub_yte) |
| Full unit suite | 310/310 PASS (34.23s) — KHÔNG break |
| `ruff check` config.py + 8 test file | All checks passed |
| `mypy --strict app/config.py` | Success: no issues found in 1 source file |

### docker-compose verify

| Command | Result |
|---------|--------|
| `docker compose config --quiet` với 3 dummy UUID exported | exit 0 |
| `docker compose config \| grep HUB_ID` | 3 line (1 per hub con) — values interpolated UUIDs |
| `docker compose config \| grep CENTRAL_SYNC_DSN` | 3 line (1 per hub con) — DSN render với password |
| `docker compose config \| grep CHECKSUM_HUB_DSNS_JSON` | 1 line (central, empty string default) |

---

## Acceptance Criteria (Plan 04-02)

### Task 1 (Settings 7 field + 3 validator + property)

| Criterion | Result |
|-----------|--------|
| `grep "hub_id: str \| None = None" app/config.py` | 1 match ✅ |
| `grep "central_sync_dsn: str \| None = None" app/config.py` | 1 match ✅ |
| `grep "checksum_hub_dsns_json: str \| None = None" app/config.py` | 1 match ✅ |
| `grep "sync_batch_size: int = 100" app/config.py` | 1 match ✅ |
| `grep "sync_poll_interval: float = 5.0" app/config.py` | 1 match ✅ |
| `grep "sync_max_attempts: int = 5" app/config.py` | 1 match ✅ |
| `grep "sync_backoff_seconds" app/config.py` | 5 match (field + parse_backoff_csv + 2 doc + property internal) ✅ |
| `grep "_enforce_hub_id_for_hub_con" app/config.py` | 1 match ✅ |
| `grep "_enforce_central_sync_dsn_for_hub" app/config.py` | 1 match ✅ |
| `grep "_enforce_checksum_hub_dsns_for_central" app/config.py` | 1 match ✅ |
| `grep "_validate_backoff_length" app/config.py` | 1 match ✅ |
| `grep "def checksum_hub_dsns" app/config.py` | 1 match (property) ✅ |
| `pytest test_config_phase4_fields.py -v` | 17/17 PASS ≥ 12 ✅ |
| Phase 1+3 regression `test_config_hub_name + dynamic + jwks` | 53/53 PASS ✅ |
| `ruff check app/config.py + test_config_phase4_fields.py` | exit 0 ✅ |
| `mypy --strict app/config.py` | exit 0 ✅ |

### Task 2 (docker-compose env + FACTOR-04 template)

| Criterion | Result |
|-----------|--------|
| `grep -c "HUB_ID:" docker-compose.yml` | 3 ✅ |
| `grep -c "CENTRAL_SYNC_DSN:" docker-compose.yml` | 3 ✅ |
| `grep "CHECKSUM_HUB_DSNS_JSON" docker-compose.yml` | 1 line ✅ |
| `grep "HUB_YTE_ID" docker-compose.yml` | 4 line ✅ |
| `grep "HUB_DUOC_ID" docker-compose.yml` | 2 line ✅ |
| `grep "HUB_HCNS_ID" docker-compose.yml` | 2 line ✅ |
| `grep "{{HUB_UPPER}}_ID" docker-compose.override.yml.template` | 1 line ✅ |
| `grep "CENTRAL_SYNC_DSN" docker-compose.override.yml.template` | 1 line ✅ |
| `docker compose config --quiet` (3 dummy UUID exported) | exit 0 ✅ |
| `docker compose config \| grep HUB_ID \| wc -l` | 3 ✅ |
| Phase 2/3 regression CENTRAL_JWKS_URL + CENTRAL_URL render OK | confirmed ✅ |

**Tổng: 27/27 acceptance criteria PASS.**

---

## Decisions Made

### LOCKED Carry Forward (Phase Context)
- **D-V3-Phase4-A1:** Outbox + worker mechanism (hub con dedicated asyncpg pool → central INSERT ON CONFLICT chunks). `central_sync_dsn` field landed.
- **D-V3-Phase4-A5:** Worker config defaults `batch=100/poll=5.0/max=5/backoff=[1,5,30,120]` Recommended option 1. Operator tune via env override.
- **D-V3-Phase4-C3:** Central checksum scheduler dict env `CHECKSUM_HUB_DSNS_JSON` parse → `dict[str, str]` property. Hub con KHÔNG dùng (skip).
- **D-V3-Phase4-D2:** Hub con UUID identity từ `medinet_central.hubs.id` row. Operator deploy responsibility export shell env trước `docker compose up`.

### Implementation Details (Plan 04-02 specific)
- **field_validator `_validate_hub_id_uuid`** (mode="after"): `uuid.UUID(v)` stdlib parse — None pass-through (caught bởi model_validator sau); invalid format → ValueError fail-fast tránh runtime PG UUID cast error.
- **field_validator `_parse_backoff_csv`** (mode="before") + `Annotated[list[int], NoDecode]`: pydantic-settings v2 mặc định JSON-decode complex type → CSV "1,5,30,120" raise SettingsError. NoDecode bypass + validator parse manually (pattern song song `cors_allowed_origins`).
- **model_validator `_validate_backoff_length`**: enforce `len(backoff) == max_attempts - 1` boot fail-loud. Logic: attempt 1 KHÔNG backoff (immediate first try), attempts 2..N dùng backoff[0..N-2]. max_attempts=5 → length=4. Operator override max_attempts=3 + backoff="1,5" length=2 PASS.
- **model_validator `_enforce_checksum_hub_dsns_for_central`**: KHÔNG require central deploy lần đầu (CHƯA register hub con) — default None OK. CHỈ enforce format khi set: JSON parseable + `dict[str, str]` type check (loop verify mọi key + value là str).
- **Helper property `checksum_hub_dsns`**: read-once JSON parse → `dict[str, str]`. Validator đã verify format, property safe parse lại. Empty `{}` nếu None (scheduler tick no-op Plan 04-06).
- **docker-compose syntax `${HUB_*_ID:?error}`**: compose interpolation fail-loud nếu shell env không set (KHÁC `${VAR:-default}` fallback). Operator pháp lý phải export trước boot — UUID actual từ Phase 7 MIGRATE-01 / Phase 6 SETTINGS-04 hub_registry CRUD.
- **docker-compose syntax `${CHECKSUM_HUB_DSNS_JSON:-}`**: default empty string (KHÁC fail-loud `:?`). Central deploy lần đầu CHƯA register hub con → property = {} → scheduler tick no-op.
- **FACTOR-04 template extend `${HUB_{{HUB_UPPER}}_ID:?...}`**: hub-add.sh sed substitute `{{HUB_UPPER}}` thành uppercase hub_name (vd `HUB=phap_che` → `HUB_PHAP_CHE_ID`). Operator export `HUB_PHAP_CHE_ID=<uuid>` sau khi register hub mới.

### Decisions deferred to next plans
- **Worker class structure** (`SyncWorker` class vs functional `sync_worker_loop`) — defer Plan 04-03 Task 1.
- **Lifespan conditional spawn** (hub con only — skip central) — defer Plan 04-04.
- **Checksum scheduler structure** (in-process asyncio loop with cron-like time check) — defer Plan 04-06.
- **Production sync_user role grant scope** (INSERT/UPDATE/DELETE ON chunks WHERE hub_id) — defer Phase 7 MIGRATE deploy doc.
- **CHECKSUM_HUB_DSNS_JSON automation** (compile từ hub_registry table) — defer Phase 6 SETTINGS-04.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Test regression] 8 file test cũ Phase 1/2/3 fixture cần auto-set HUB_ID + CENTRAL_SYNC_DSN**

- **Found during:** Task 1 GREEN (sau khi config.py landed) — full unit suite chạy báo 28 test failure (17 file). Pattern song song Plan 03-02 (CENTRAL_JWKS_URL added) + Plan 03-04 (CENTRAL_URL added).
- **Issue:** Settings validator `_enforce_hub_id_for_hub_con` + `_enforce_central_sync_dsn_for_hub` mới yêu cầu hub con set HUB_ID + CENTRAL_SYNC_DSN. Test cũ instantiate Settings với hub_name != "central" mà KHÔNG set 2 field này → ValidationError boot.
- **Fix:** Modify mỗi `_setup_env` / `_common_env` helper trong 8 test file để auto-set HUB_ID + CENTRAL_SYNC_DSN khi `hub_name != "central"` (cùng pattern Plan 03-02/03-04 carry forward CENTRAL_JWKS_URL + CENTRAL_URL fixture update).
- **Files modified:** 8 file
  - `test_config_hub_name.py` (2 test riêng setenv inline — KHÔNG có helper centralize)
  - `test_config_hub_name_dynamic.py` (_set_env helper)
  - `test_config_jwks.py` (_common_env helper)
  - `test_main_factory.py` (_setup_env helper)
  - `test_auth_router_hub_redirect.py` (_setup_env helper)
  - `test_get_current_user_jwks_branch.py` (_common_hub_env helper)
  - `test_jwks_publish.py` (_setup_env helper)
  - `test_flow_per_hub_naming.py` (subprocess env dict test `test_module_app_name_per_hub_yte_subprocess`)
- **Commit:** `20fc792` (gộp Task 1 GREEN — file change atomic với config.py do logically là 1 unit Rule 3 regression).
- **Rationale:** Pattern Rule 3 đã được Phase 3 Plan 03-02 + 03-04 thiết lập (test fixture auto-set hub con required env mỗi khi validator mới added). KHÔNG đổi semantic test, chỉ thêm setenv setup cho hub con scenario.

**2. [Out-of-scope] Pre-existing `prometheus_client` module missing trong local Python env**

- **Found during:** Task 1 GREEN — test_main_factory.py báo `ModuleNotFoundError: No module named 'prometheus_client'`.
- **Issue:** `app/observability/metrics.py:24` import `prometheus_client` (HARD-02 ship M2 Plan 10-02). Local Python env hiện chưa install.
- **Fix:** `pip install prometheus_client` — pre-existing env gap (M2 ship dùng `uv` runtime cài; native pytest fallback dùng pip).
- **Files modified:** None (env-level fix, KHÔNG đụng repo).
- **Rationale:** Pre-existing — KHÔNG do Plan 04-02 introduce. Verify git stash + reproduce trên main pre-Plan 04-02 cùng failure. Logged để track — KHÔNG block Plan 04-02 ship.

### Plan-strict adherence
- KHÔNG bump stack version (Python 3.12, FastAPI 0.136.1, pgvector 0.4.2, asyncpg 0.30.0).
- KHÔNG sửa `frontend/`, `STATE.md`, `ROADMAP.md`, `REQUIREMENTS.md` (out-of-scope cho executor).
- KHÔNG dùng `--no-verify` cho commit (sequential mode, pre-commit hooks run).
- KHÔNG đụng `api/app/sync/` directory (Plan 04-03 file-disjoint Wave 2).
- Commit message prefix tiếng Anh + body tiếng Việt theo CLAUDE.md §5.

---

## Authentication Gates

**None.** Plan 04-02 thuần Settings layer + docker-compose env config — KHÔNG cần auth setup. Runtime auth integration (sync_user role grant) defer Phase 7 MIGRATE deploy guide.

---

## Known Stubs

**None.** Plan 04-02 ship config layer chuẩn — 7 field + 3 validator + property all wired và verified qua 17 unit test. KHÔNG có stub data UI/runtime trong scope plan này. Consumer (Plan 04-03 worker + Plan 04-04 lifespan + Plan 04-06 checksum scheduler) sẽ wire actual asyncpg pool + scheduler loop trong các plan tiếp theo.

---

## Threat Flags

**Không phát hiện threat surface mới ngoài `<threat_model>` của Plan 04-02.** 6 threat (T-04-02-01..06) trong plan đã cover toàn bộ surface:
- T-04-02-01..03 (Tampering/DoS hub_id + central_sync_dsn + checksum_json) → mitigated bởi 3 model_validator + 1 field_validator UUID format
- T-04-02-04 (Info Disclosure DSN password) → accept dev (dummy `medinet:medinet_dev_pwd`); production defer Phase 7 deploy guide qua Docker Swarm secrets / K8s Secret
- T-04-02-05 (DoS backoff length IndexError) → mitigated bởi `_validate_backoff_length`
- T-04-02-06 (Elevation sync_user superuser DROP central) → accept v3.0-a; production deploy guide defer Plan 04-06 admin doc + Phase 7 MIGRATE

---

## Verification Status

### Automated (in-process)
- ✅ 17/17 unit test mới PASS `test_config_phase4_fields.py` (0.30s)
- ✅ 310/310 full unit suite PASS (34.23s) — KHÔNG break Phase 1+2+3
- ✅ ruff check 9 file (config.py + 8 test) — All checks passed
- ✅ mypy --strict app/config.py — Success: no issues found in 1 source file
- ✅ `docker compose config --quiet` exit 0 với 3 dummy UUID exported
- ✅ `docker compose config | grep HUB_ID | wc -l` = 3 (1 per hub con)
- ✅ `docker compose config | grep CENTRAL_SYNC_DSN | wc -l` = 3
- ✅ `docker compose config | grep CHECKSUM_HUB_DSNS_JSON | wc -l` = 1 (central, empty default)

### Deferred (downstream plans)
- Worker spawn lifespan + asyncpg pool dedicated central_sync_dsn — Plan 04-03 + 04-04
- Checksum scheduler tick + property `checksum_hub_dsns` consume — Plan 04-06
- Operator workflow `export HUB_*_ID=$(psql ...)` automation — Phase 7 MIGRATE-01 deploy guide
- Production sync_user role grant scope verification — Phase 7 MIGRATE deploy doc

---

## Self-Check

### Files Created/Modified Verification

| Claim | Verified |
|-------|----------|
| `api/tests/unit/test_config_phase4_fields.py` exists (266 LOC) | FOUND |
| `api/app/config.py` modified — 12 grep pattern (5 field + 3 model_validator + 1 length + 1 property + 2 field_validator) | FOUND all 12 grep PASS |
| `docker-compose.yml` modified — 3 hub con HUB_ID + CENTRAL_SYNC_DSN + central CHECKSUM_HUB_DSNS_JSON | FOUND (`docker compose config` render 7 entry) |
| `docker-compose.override.yml.template` modified — `{{HUB_UPPER}}_ID` + CENTRAL_SYNC_DSN | FOUND |
| 8 file test cũ fixture update (Rule 3 regression auto-fix) | FOUND (full unit suite 310/310 PASS) |

### Commit Verification

| Hash | Verified |
|------|----------|
| `5da264d` (test RED) | FOUND in git log |
| `20fc792` (feat GREEN Task 1 — config + 8 test fixture) | FOUND in git log |
| `50643d3` (feat Task 2 — docker-compose env wire + FACTOR-04 template) | FOUND in git log |

## Self-Check: PASSED

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~22 phút (3 commit atomic — 1 RED + 2 GREEN) |
| Tasks completed | 2/2 |
| Files created | 2 (test file + SUMMARY.md) |
| Files modified | 11 (config.py + docker-compose × 2 + 8 test file fixture) |
| LOC added | ~150 implementation (config.py +143) + 266 test + ~40 fixture regression + 30 docker-compose = ~480 LOC |
| Tests added | 17 (1 central baseline + 4 hub_id required + 1 UUID + 1 sync_dsn required + 1 hub con full OK + 1 central optional + 3 checksum validator + 2 defaults + 1 CSV parse + 1 length validator + 2 bonus override) |
| Test pass rate | 17/17 (100%) — 0.30s |
| Acceptance criteria | 27/27 PASS (16 Task 1 + 11 Task 2) |
| Regression | 310/310 unit + 0 break Phase 1/2/3 |
| Lint | ruff + mypy --strict PASS no new errors |
| Commits | 3 (RED test + GREEN feat config + feat docker-compose) |
| Deviations | 2 (Rule 3 regression — 8 file test fixture update; Pre-existing env gap — prometheus_client install) |

---

## Next: Plan 04-03 Worker Implementation (Wave 2)

Plan 04-02 đã ship Settings + docker-compose foundation Wave 2. Plan 04-03 consume:

1. **`Settings.central_sync_dsn`** — Worker spawn dedicated asyncpg pool (`asyncpg.create_pool(dsn=settings.central_sync_dsn, ...)`) ở lifespan hub con startup.
2. **`Settings.sync_batch_size`** — Worker SELECT FOR UPDATE SKIP LOCKED LIMIT 100 query.
3. **`Settings.sync_poll_interval`** — Worker `asyncio.sleep(poll_interval)` khi outbox empty.
4. **`Settings.sync_max_attempts` + `sync_backoff_seconds`** — Worker exp backoff retry loop: `wait = backoff_seconds[attempt - 2]` (attempt 1 immediate, attempts 2..N use backoff[0..N-2]).
5. **`Settings.hub_id`** — Worker ChunkPayload Pydantic schema include `hub_id` từ row (cocoindex flow rag/flow.py:ChunkRow đã có biến local — Plan 04-05 wire qua doc_row['hub_id']).

Plan 04-03 + 04-02 hoàn thành Wave 2. Plan 04-04 (lifespan integration) Wave 3 phụ thuộc cả 2.

**Phase 4 progress:** 2/7 plan complete (~29%). SYNC-05 đóng (Plan 04-01). SYNC-01/03/04 Settings layer ship (Plan 04-02); worker layer formally đóng SYNC-01..04 khi Plan 04-03 ship.

---

*Plan 04-02 ship 2026-05-22 sau ~22 phút thực thi. Wave 2 part 1 DONE (file-disjoint với Plan 04-03 — chỉ touch app/config.py + docker-compose + tests/unit/). 3 commit atomic (1 RED test + 2 GREEN feat). 17/17 test PASS + 310/310 regression PASS + 27/27 acceptance + ruff + mypy --strict PASS. Next: Plan 04-03 sync worker implementation (file-disjoint app/sync/worker.py + tests/unit/test_sync_worker.py + ...).*
