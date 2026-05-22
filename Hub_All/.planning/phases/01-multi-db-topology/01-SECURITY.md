---
phase: 01
slug: 01-multi-db-topology
status: secured
asvs_level: 1
block_on: high
threats_total: 27
threats_closed: 27
threats_open: 0
audit_date: 2026-05-22
created: 2026-05-22
---

# Phase 1 — Multi-DB Topology + Per-hub Alembic — Security

> Per-phase security contract: threat register, accepted risks, audit trail.
> Audit run by `/gsd-secure-phase` agent — verify mitigations declared in PLAN.md `<threat_model>` blocks tồn tại trong implementation files.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Docker host → Postgres container | POSTGRES_PASSWORD truyền từ host shell qua compose; init script chạy với quyền superuser POSTGRES_USER lúc cluster lần đầu | DB credentials, init SQL |
| Postgres cluster → init-db.sh | Script thực thi với privilege POSTGRES_USER (superuser) tại entrypoint — có thể CREATE DATABASE bất kỳ | SQL DDL |
| Deployer (ops) → process env (HUB_NAME + DATABASE_URL) | docker compose / Kubernetes / .env file — untrusted nếu deployer compromised | Config/secrets |
| Process startup → Settings model_validator | Validator chạy fail-fast trước bất kỳ request handler — chống misconfiguration silent run sai data | hub_name + DSN |
| Settings → init_engine (db/session.py) | DSN đã validated truyền vào create_async_engine — không có second-pass check ở session layer | DSN (validated) |
| Caller (make / CI) → alembic env.py | -x hub argument từ command line — validate qua `_VALID_HUBS` set | CLI args |
| env.py → Postgres | DSN đã resolved qua `resolve_database_url` — không hardcode credential | SQL migration ops |
| alembic-head-check.sh → 4 DB | Lint script đọc alembic_version table mỗi DB — read-only access | rev SHA |
| Process startup → cocoindex SDK | APP_NAMESPACE set qua os.environ — cocoindex SDK đọc lazy ở start_blocking() | env var |
| flow.py import → Settings load | lru_cache singleton — 1 process = 1 hub_name = 1 App instance | hub_name |
| Different hub processes → cùng Postgres cocoindex internal schema | namespace tách table prefix `medinet_<hub>_prod__` → no clash | cocoindex tables |
| Plan 04 deploy → M2 cocoindex internal state | App name + APP_NAMESPACE đổi → M2 state orphan; mitigation re-ingest documents table | cocoindex state (orphan) |
| Dev → hub-init.sh | HUB arg shell sanitize regex `^[a-z][a-z0-9_]{1,30}$` chống injection | shell arg |
| hub-init.sh → Postgres superuser | psql -U medinet (POSTGRES_USER) — superuser cần để CREATE DATABASE | SQL DDL |
| Integration test → testcontainers postgres | PostgresContainer isolated per test module — không leak vào local dev cluster | test DSN |
| CI workflow (.github/workflows/test.yml) → service container postgres | GitHub Actions service container ephemeral; credentials hard-coded test env | CI test DSN |
| [BLOCKING] Schema push → existing M2 volume | Option B default preserve M2 central volume; Option A destructive yêu cầu `MEDINET_CONFIRM_RESET=YES_DELETE_M2` env confirm | M2 corpus data |

---

## Threat Register

**Total: 27 threats** — sourced from 5 PLAN.md `<threat_model>` blocks (Plan 01: 4, Plan 02: 5, Plan 03: 5, Plan 04: 6, Plan 05: 7).

### Plan 01 — init-db.sh 4 DB topology

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-01-01-01 | Tampering | init-db.sh script content | mitigate | Mount `:ro` ở docker-compose volume + bash idempotent guard `SELECT pg_database WHERE datname` + git-tracked | closed | `Hub_All/api/scripts/init-db.sh:24-31` (SELECT guard), `Hub_All/docker-compose.yml` (mount `:ro` baseline M2) |
| T-01-01-02 | Elevation of Privilege | POSTGRES_USER `medinet` superuser cluster init | accept | Cluster init chạy 1 lần lúc volume empty; superuser cần để CREATE DATABASE; production hardening defer v4.0 | closed | Accepted Risks Log #AR-01 |
| T-01-01-03 | Denial of Service | HNSW verify 1536-dim DROP TABLE IF EXISTS race | mitigate | `DROP TABLE IF EXISTS` trước CREATE để re-run init không fail; 4 DB verify tuần tự ~5s mỗi DB OK với healthcheck retries=10 | closed | `Hub_All/api/scripts/init-db.sh:61` (DROP TABLE IF EXISTS) |
| T-01-01-04 | Information Disclosure | psql log echo "medinet_hub_<name>" lên stdout container | accept | Tên DB không phải PII / secret; log container chỉ visible cho admin docker host | closed | Accepted Risks Log #AR-02 |

### Plan 02 — Settings.hub_name + DSN validator + resolver

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-01-02-01 | Spoofing | Process khai sai HUB_NAME (vd HUB_NAME=yte nhưng DSN central) | mitigate | `model_validator(mode="after") _enforce_hub_dsn_match` raise ValueError fail-fast trước `get_settings()` cached | closed | `Hub_All/api/app/config.py:159-188` (`_enforce_hub_dsn_match`), test `test_settings_yte_with_central_dsn_raises` PASS |
| T-01-02-02 | Information Disclosure | Process hub yte vô tình connect medinet_hub_duoc do typo DATABASE_URL | mitigate | Validator check `database_url` suffix khớp `medinet_hub_<hub_name>` — cross-hub typo bị raise ngay startup | closed | `Hub_All/api/app/config.py:181-188`, test `test_settings_yte_with_duoc_dsn_raises` PASS |
| T-01-02-03 | Elevation of Privilege | Hub con cố ý connect medinet_central để truy cập aggregated chunks | mitigate | DB-level isolation Plan 01-01 (DB riêng); validator enforce DSN match; production grant defer Phase 7 | closed | `Hub_All/api/app/config.py:159-188` + integration test `test_db_connection_yte_cannot_reach_duoc` PASS |
| T-01-02-04 | Tampering | `resolve_database_url` helper bị gọi với base_dsn sai (vd trỏ medinet_hub_yte) | mitigate | Helper raise ValueError nếu base_dsn không kết thúc `/medinet_central` | closed | `Hub_All/api/app/config.py:200-241` (helper raises ValueError) |
| T-01-02-05 | Repudiation | Settings load không log hub_name khi startup → audit khó truy | accept | Log hub_name ở Phase 2 FACTOR-01 create_app lifespan ("starting hub=<name>") — ngoài scope Plan 01-02 | closed | Accepted Risks Log #AR-03 |

### Plan 03 — Per-hub Alembic + migrate-all + head-check

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-01-03-01 | Tampering | Caller pass `-x hub=invalid` (typo / malicious) | mitigate | `parse_hub_x_arg` raise ValueError trên hub không thuộc `_VALID_HUBS` | closed | `Hub_All/api/migrations/env.py:42,45-71` (`_VALID_HUBS` + `parse_hub_x_arg`), test `test_parse_invalid_raises` PASS |
| T-01-03-02 | Tampering | Migration apply sai DB do DSN resolver bug | mitigate | `resolve_env_database_url` 2-pass check: target_hub=central + DSN suffix; cross-hub un-resolve về central trước; raise ValueError trên invalid base | closed | `Hub_All/api/migrations/env.py:74-150`, tests `test_resolve_cross_hub_yte_to_duoc` + `test_resolve_invalid_base_dsn_raises` PASS |
| T-01-03-03 | Information Disclosure | alembic-head-check.sh log full DSN ra stdout | mitigate | Script chỉ log hub name + rev SHA — KHÔNG echo $DATABASE_URL/credentials | closed | `Hub_All/api/scripts/alembic-head-check.sh:33,38,51,57` (echo chỉ chứa hub name + rev SHA), grep `DATABASE_URL` đếm = 1 line comment doc |
| T-01-03-04 | Denial of Service | migrate-all loop fail mid-way → hub-1 apply nhưng hub-2/3/4 chưa | mitigate | `for hub in ...; do ... \|\| exit 1; done` fail-fast; alembic-head-check.sh exit 1 → CI gate block merge (Plan 05) | closed | `Hub_All/api/Makefile:65-72` (fail-fast + chain head-check), CI wired |
| T-01-03-05 | Elevation of Privilege | Migration apply với superuser thay vì migration user dedicated | accept | M2 dùng POSTGRES_USER (superuser) cho mọi migration — separation of duties defer Phase 7 | closed | Accepted Risks Log #AR-04 |

### Plan 04 — Cocoindex flow per-hub + APP_NAMESPACE per-hub

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-01-04-01 | Tampering | Caller set APP_NAMESPACE env trước setup_cocoindex (ops misconfig) | mitigate | `setup_cocoindex` GHI ĐÈ qua `os.environ["APP_NAMESPACE"]` deterministic theo `settings.hub_name`; log event `cocoindex_app_namespace_set` | closed | `Hub_All/api/app/rag/setup.py:80-86` (GHI ĐÈ + log) |
| T-01-04-02 | Information Disclosure | App name `medinet_yte_ingest` leak ra error log nếu cocoindex SDK crash | accept | App name không phải PII / secret; hub identity là public info trong topology | closed | Accepted Risks Log #AR-05 |
| T-01-04-03 | Tampering | flow.py module-level `_get_settings()` cache stale nếu test thay env | mitigate | Test fixture `_minimal_env` autouse gọi `get_settings.cache_clear()` trước+sau; subprocess pattern cho per-hub test | closed | `Hub_All/api/tests/unit/test_flow_per_hub_naming.py` (subprocess + cache_clear) — 9/9 PASS |
| T-01-04-04 | Spoofing | Hub yte cố đăng ký App name `medinet_central_ingest` để consume central state | mitigate | `resolve_cocoindex_app_name` lấy hub_name từ Settings (validated qua Plan 02); hub yte process không thể đặt hub_name="central" mà không đổi DATABASE_URL → fail-fast startup | closed | `Hub_All/api/app/rag/flow.py:284-311,322-328` chain với Plan 02 validator |
| T-01-04-05 | Information Disclosure | cocoindex internal state table `cocoindex.medinet_<hub>_prod__*` cùng DB → query cross-namespace có thể đọc | accept | Phase 1 chỉ scope process layer naming; cross-namespace SQL access cần Postgres-level role grant (defer Phase 7) | closed | Accepted Risks Log #AR-06 |
| T-01-04-06 | Tampering / Data Loss | M2 cocoindex internal state orphan sau đổi App name `medinet_wiki_ingest` → `medinet_central_ingest` + APP_NAMESPACE `medinet_prod` → `medinet_central_prod` | mitigate | Accept state reset v3.0-a + mitigation chain: (1) post-deploy `UPDATE documents SET status='pending'` re-ingest idempotent qua content_hash; (2) env fallback `COCOINDEX_APP_NAME_LEGACY=medinet_wiki_ingest`; (3) structured log audit trail; (4) Phase 7 migrate formally qua pg_dump --where | closed | `Hub_All/api/app/rag/flow.py:282,318-325` (COCOINDEX_APP_NAME_LEGACY env fallback); test `test_legacy_env_override_preserves_m2_name_subprocess` PASS; also see Accepted Risks Log #AR-07 (state reset accepted) |

### Plan 05 — hub-init.sh dynamic + integration test + CI gate + [BLOCKING] schema push

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-01-05-01 | Tampering | hub-init.sh accept HUB arg với SQL injection (vd `; DROP DATABASE medinet_central;`) | mitigate | Regex `^[a-z][a-z0-9_]{1,30}$` validate HUB pattern Postgres-identifier-safe; reject sớm exit 2 trước psql call | closed | `Hub_All/api/scripts/hub-init.sh:40-43` (bash regex validation + early exit) |
| T-01-05-02 | Elevation of Privilege | Dev chạy hub-init.sh trên prod cluster vô tình | accept | Script không có guard env detection; dev responsibility; production deploy qua ops automation Phase 7 | closed | Accepted Risks Log #AR-08 |
| T-01-05-03 | Information Disclosure | Integration test seed `_iso_marker` table leak nếu test fail giữa chừng | mitigate | Test cleanup `DROP TABLE IF EXISTS _iso_marker` trong finally block + container module-scope (drop sau module xong) | closed | `Hub_All/api/tests/integration/test_hub_isolation_db_level.py` finally cleanup |
| T-01-05-04 | Denial of Service | CI service container postgres không đủ resource → migrate-all timeout | accept | Job timeout-minutes: 20 (M2 baseline); 4 DB × ~4 migration × ~5s = ~80s đủ headroom | closed | Accepted Risks Log #AR-09 |
| T-01-05-05 | Repudiation | Schema push step 4 ([BLOCKING]) chạy thủ công không log evidence | mitigate | make migrate-all output có timestamp + hub identity + rev SHA per hub; capture qua SUMMARY.md (HARD-04) | closed | `Hub_All/.planning/phases/01-multi-db-topology/01-05-SUMMARY.md` (Schema push commit `1fe8d9a` + evidence table 4 DB head SHA 0004) |
| T-01-05-06 | Information Disclosure | hub-init.sh log PGPASSWORD ra stdout vô tình | mitigate | Script KHÔNG echo $PGPASSWORD; psql đọc PGPASSWORD từ env (libpq pattern) | closed | grep `PGPASSWORD` trong `hub-init.sh` chỉ thấy ở line 16 comment doc — không có echo statement |
| T-01-05-07 | Tampering / Data Loss | [BLOCKING] Schema push Option A (`docker compose down -v`) vô tình xoá M2 central volume khi user KHÔNG chủ ý | mitigate | Plan 05 Task 4 default Option B (preserve M2 — chỉ `make hub-init` add 3 hub); Option A guard `MEDINET_CONFIRM_RESET=YES_DELETE_M2` env; M2 documents COUNT=3 preserve verified | closed | `01-05-PLAN.md` Task 4 action block (Option B default); `01-05-SUMMARY.md` evidence "M2 documents COUNT=3 preserve" + commit `1fe8d9a` |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-01-01-02 (EoP — POSTGRES_USER superuser cluster init) | Postgres không hỗ trợ delegate CREATE DATABASE; cluster init chỉ chạy 1 lần lúc volume empty. Production hardening qua dedicated migration role defer v4.0 hardening phase. | Plan 01-01 author | 2026-05-21 |
| AR-02 | T-01-01-04 (Info Disclosure — psql log echo DB name) | Tên DB (`medinet_hub_yte`, etc.) không phải PII / secret; chỉ là hub identity public trong topology. Log container chỉ visible cho admin docker host. | Plan 01-01 author | 2026-05-21 |
| AR-03 | T-01-02-05 (Repudiation — Settings load không log hub_name) | Log `starting hub=<name>` defer Phase 2 FACTOR-01 (`create_app` lifespan). Phase 1 chỉ Settings layer — application bootstrap log không scope plan này. | Plan 01-02 author | 2026-05-21 |
| AR-04 | T-01-03-05 (EoP — migration apply với superuser) | M2 dùng POSTGRES_USER (superuser) cho mọi migration vì Alembic không có production-grade role separation pattern ở v3.0-a. Per-hub dedicated migration role defer Phase 7. | Plan 01-03 author | 2026-05-21 |
| AR-05 | T-01-04-02 (Info Disclosure — App name leak error log) | App name (`medinet_yte_ingest`) không phải PII / secret; hub identity public trong topology. Cocoindex SDK crash log chứa app name nhưng KHÔNG credentials. | Plan 01-04 author | 2026-05-21 |
| AR-06 | T-01-04-05 (Info Disclosure — cocoindex.medinet_<hub>_prod__* cross-namespace SQL read) | Phase 1 chỉ scope process layer naming. Cross-namespace SQL access cần Postgres role-based grant — defer Phase 7 production hardening. Hub con KHÔNG có quyền connect cocoindex internal DB từ outside, chỉ qua coco.App SDK. | Plan 01-04 author | 2026-05-21 |
| AR-07 | T-01-04-06 (Data Loss — M2 cocoindex state reset) | v3.0-a là demo build — fresh re-ingest từ documents table OK vì content_hash idempotent (cocoindex skip re-embed nếu content unchanged). Phase 7 migrate data formally qua `pg_dump --where`. Mitigation chain (re-ingest task + COCOINDEX_APP_NAME_LEGACY fallback + structured audit log) implemented — accept state reset cho v3.0-a release. | Plan 01-04 author | 2026-05-21 |
| AR-08 | T-01-05-02 (EoP — dev chạy hub-init.sh trên prod cluster vô tình) | Script không có env-detection guard (dev vs prod); responsibility của dev. Production deploy qua ops automation (Phase 7 migration). hub-init.sh chỉ cho dev/staging dynamic add. | Plan 01-05 author | 2026-05-21 |
| AR-09 | T-01-05-04 (DoS — CI service container postgres timeout) | Job `timeout-minutes: 20` (M2 baseline) đủ headroom (4 DB × ~4 migration × ~5s = ~80s). Nếu fail timeout → ops bump timeout hoặc split CI job. Acceptable trade-off cho CI resource cost. | Plan 01-05 author | 2026-05-21 |

*9 accepted risks documented above. Accepted risks do not resurface in future audit runs unless re-opened explicitly.*

---

## Unregistered Threat Flags

Cross-referenced SUMMARY.md `## Threat Flags` sections 01-01 → 01-05:

| Plan | Threat Flags Reported | Disposition |
|------|----------------------|-------------|
| 01-01 | None | n/a |
| 01-02 | None | n/a |
| 01-03 | None | n/a |
| 01-04 | None | n/a |
| 01-05 | None (Plan 05 SUMMARY structure unified — no separate flags section, threats all in register) | n/a |

**No unregistered flags detected.** All threat surface from 5 plans baked into PLAN.md `<threat_model>` blocks và verified in this register.

---

## Implementation Evidence Snapshot (focal areas)

| Focal Area | Evidence Verified |
|------------|-------------------|
| DB privilege escalation (E-V3-3) | `app/config.py:159-188` `_enforce_hub_dsn_match` model_validator + integration test `tests/integration/test_hub_isolation_db_level.py` 5/5 PASS (UAT verified, runtime ~5.55s) |
| Alembic migration drift cross-DB (R-V3-3) | `scripts/alembic-head-check.sh` exit 1 trên drift + Makefile `migrate-all` chain auto-call + CI workflow `.github/workflows/test.yml` step "Apply migrate-all" wired (lines 112-126) |
| Env var leakage / .env.example placeholder | `.env.example` chỉ có placeholder `medinet_dev_pwd` (NOT real secret pattern); secret detection delegate cho `.github/workflows/lint.yml` (W10 fix — DRY single source of truth) |
| Data Loss [BLOCKING] schema push | Option B SAFE default verified: M2 `documents` COUNT=3 preserved trong Plan 05 Task 4 SUMMARY evidence; Option A guard `MEDINET_CONFIRM_RESET=YES_DELETE_M2` documented |
| M2 cocoindex state orphan (T-01-04-06) | Re-ingest task `UPDATE documents SET status='pending'` documented + `COCOINDEX_APP_NAME_LEGACY` env fallback at `app/rag/flow.py:282,318-325` + Phase 7 formal migrate planned |
| P7 cocoindex schema filter (carry forward) | `migrations/env.py:160-176` `include_object` filter exclude schema 'cocoindex' INTACT (4 mentions verified) |
| P20 Alembic compare_type + compare_server_default | `migrations/env.py:187-188, 201-202` `compare_type=True` + `compare_server_default=True` preserved (3 mentions each verified) |
| hub-init.sh SQL injection sanitize | `scripts/hub-init.sh:40-43` regex `^[a-z][a-z0-9_]{1,30}$` validate + exit 2 trên fail |
| PGPASSWORD non-leak | grep `PGPASSWORD` trong `hub-init.sh` chỉ thấy comment doc line 16; KHÔNG có `echo $PGPASSWORD` |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | ASVS Level | Block On | Run By |
|------------|---------------|--------|------|------------|----------|--------|
| 2026-05-22 | 27 | 27 | 0 | 1 | high | `/gsd-secure-phase` agent (initial audit) |

---

## Sign-Off

- [x] All 27 threats có disposition (18 mitigate / 9 accept / 0 transfer)
- [x] 9 accepted risks documented trong Accepted Risks Log (AR-01..AR-09)
- [x] `threats_open: 0` confirmed — toàn bộ mitigation evidence verified trong implementation files
- [x] `status: secured` set trong frontmatter
- [x] Implementation files KHÔNG modified (read-only audit)
- [x] CI gate R-V3-3 mitigation wired (`.github/workflows/test.yml` Apply migrate-all step)
- [x] E-V3-3 integration test 5/5 PASS evidence (Plan 05 Task 2 + UAT)

**Approval:** verified 2026-05-22 (auto-audit `/gsd-secure-phase`)
