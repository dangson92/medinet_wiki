---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Multi-Hub Split
status: Phase 2 DONE 2026-05-22 ✅ (5 plans total — Plan 02-05 ship 2026-05-22 FACTOR-04 dynamic hub registration; user direction B sau Plan 02-04 closeout). 5 plans / 9+ commits / 49+ unit tests + 12+ integration test PASS. create_app() factory conditional mount (7 universal + 9 central-only); docker-compose 4 service dedicated (central/yte/duoc/hcns) port 8180-8183 + cocoindex LMDB volume per-hub; endpoint matrix 12 hub-scoped mount + 8 central-only strip envelope shape; Settings.hub_name str + regex + reserved blacklist 6 name + scripts/hub-add.sh + docker-compose.override.yml.template + Makefile target hub-add (FACTOR-04). Phase 1+2 = 10/~32 plan ≈ 31%. Next phase 3 — Auth SSO + hub_ids JWT (GA-V3-A chốt).
last_updated: "2026-05-22T15:30:00.000Z"
progress:
  total_phases: 7
  completed_phases: 2
  total_plans: 10
  completed_plans: 10
  percent: 31
---

# State — MEDWIKI (v3.0)

**Mã dự án:** MEDWIKI
**Milestone:** v3.0 — Multi-Hub Split
**Ngày bắt đầu:** 2026-05-21 (sau khi v2.0 shipped 100% COMPLETE 38/38 REQ-ID)
**Last updated:** 2026-05-22

## Current Position

- **Phase:** 2 — Hub-con Codebase Factor ✅ **DONE 2026-05-22 — FACTOR-01..04 fully shipped (Wave 1 + Wave 2 + Wave 3 + Wave 4 ✅); Plan 02-05 FACTOR-04 dynamic hub registration ship 2026-05-22 (user direction B sau Plan 02-04 closeout)**
- **Plan:** 5/5 plans complete (02-01..02-05) cho FACTOR-01..04 ở `.planning/phases/02-hub-con-codebase-factor/`.
- **Status:** Phase 2 closed FACTOR-01..03 — `create_app()` factory conditional router mount (7 universal + 9 central-only). Docker-compose mở rộng 4 service dedicated với YAML anchor `x-api-template`. Integration test endpoint matrix verify 12 hub-scoped mount + 8 central-only strip với 404 envelope shape M2 ErrorHandlerMiddleware wrap (Starlette HTTPException handler Rule 2 auto-add ở Plan 02-03). Phase 1 `_enforce_hub_dsn_match` validator carry forward (E-V3-3 không regress). CLAUDE.md + STATE.md + REQUIREMENTS.md update FACTOR-03 note "10 collective endpoint group / 12 specific HTTP method endpoints" (WRN-05 fix). Plan 02-04 Task 1 smoke compose runtime SKIP — rationale: Plan 02-03 integration test in-process (10/10 PASS 6.49s) đã cover semantic FACTOR-02/03; Phase 1 DSN validator + routing verify Plan 01-02; `docker compose config --quiet` exit 0 Plan 02-02; smoke compose runtime defer Phase 7 migration smoke E2E (MIGRATE-05).
- **Last activity:** 2026-05-22 — `/gsd-execute-phase 2` wave-based execution complete cho FACTOR-01..03:
  - **02-01 DONE ✅** (Wave 1 BLOCKING): `create_app()` factory refactor mount conditional 9 central-only router theo `settings.hub_name`; unit test 9/9 PASS boot 4 hub mode (central/yte/duoc/hcns); Phase 1 DSN validator regression KHÔNG break (30/30 PASS). FACTOR-01 + FACTOR-02 đóng unit-level. SUMMARY: `.planning/phases/02-hub-con-codebase-factor/02-01-SUMMARY.md`.
  - **02-02 DONE ✅** (Wave 2, first half): Docker compose refactor 4 service FastAPI dedicated với YAML anchor `x-api-template: &api-template` + cocoindex LMDB volume per-hub (medinet_cocoindex_{central,yte,duoc,hcns}) + port 8180-8183 + mcp_service re-point `python-api-central` (D-V3-02 LOCKED). `docker compose config --quiet` exit 0, 8 service render đúng. FACTOR-01 đóng Docker layer. SUMMARY: `.planning/phases/02-hub-con-codebase-factor/02-02-SUMMARY.md`.
  - **02-03 DONE ✅** (Wave 2, second half): Integration test endpoint matrix 12 hub-scoped MOUNT + 8 central-only STRIP (sync_router dùng `/api/sync/stats` BLK-01 fix) + envelope shape 404 D6 + autouse cleanup CỤC BỘ (WRN-03 fix). 10/10 test PASS qua TestClient in-process (6.49s). 175/175 unit test regression PASS (KHÔNG break Phase 1 + Plan 02-01). Rule 2 auto-add Starlette HTTPException handler ở `app/main.py` (M2 chỉ register `fastapi.HTTPException` — NOT match Starlette routing 404). Rule 3 auto-fix `reset_queue()` + SQLAlchemy engine sentinel-None reset trong `hub_app_factory` (audit queue cross-loop hang). FACTOR-02 + FACTOR-03 đóng integration level. SUMMARY: `.planning/phases/02-hub-con-codebase-factor/02-03-SUMMARY.md`.
  - **02-04 DONE ✅** (Wave 3 closeout): CLAUDE.md section 6 update Phase 2 DONE + 4 service compose pattern + endpoint matrix reference; STATE.md frontmatter + Current Position + Phase 2 Results Summary + Next Action update; REQUIREMENTS.md FACTOR-03 note "10 collective / 12 specific HTTP method endpoints" inline matrix 12 entry (WRN-05 fix). Task 1 smoke compose SKIP — Plan 02-03 integration test in-process đã cover semantic; smoke compose runtime defer Phase 7. SUMMARY: `.planning/phases/02-hub-con-codebase-factor/02-04-SUMMARY.md`.
  - **02-05 DONE ✅** (Wave 4 extension, FACTOR-04 dynamic hub registration — ship 2026-05-22 sau Plan 02-04 closeout): Settings.hub_name Literal[4] → str + regex `^[a-z][a-z0-9_]{0,15}$` + reserved blacklist 6 name + `scripts/hub-add.sh` wrap hub-init.sh + `docker-compose.override.yml.template` sed substitute + `make hub-add HUB=<name> [PORT=<port>]` + README "Add a new hub" section + CLAUDE.md FACTOR-04 subsection. Task 3 smoke runtime SKIP (pre-resolved user decision — 20+ unit test cover validator + bash syntax check + docker compose config base verify đã PASS Plan 02-02; smoke Docker runtime defer Phase 7 MIGRATE-05 full E2E). 29/29 unit dynamic + 11/11 unit original PASS, ruff + mypy --strict PASS, regression test_main_factory.py 9/9 PASS. SUMMARY: `.planning/phases/02-hub-con-codebase-factor/02-05-SUMMARY.md`.

## Phase 2 Planning Summary

| Plan | Wave | Objective | Tasks | Files modified | REQ | Status |
|------|------|-----------|-------|----------------|-----|--------|
| 02-01 | 1 | create_app() inline conditional 9 central-only router | 2 (auto) | `api/app/main.py`, `tests/unit/test_main_factory.py` | FACTOR-01, FACTOR-02 | ✅ **DONE 2026-05-22** (9/9 test PASS) |
| 02-02 | 2 | Docker compose 4 service + YAML anchor + cocoindex LMDB per-hub | 1 (auto) | `docker-compose.yml` | FACTOR-01 | ✅ **DONE 2026-05-22** (docker compose config exit 0, 8 service render) |
| 02-03 | 2 | Integration test 12 hub-scoped + 8 central-only + envelope 404 | 2 (tdd) | `tests/integration/conftest.py`, `tests/integration/test_factor_hub_scoped.py`, `app/main.py` (Rule 2) | FACTOR-02, FACTOR-03 | ✅ **DONE 2026-05-22** (10/10 test PASS, 6.49s; 175/175 unit regression PASS) |
| 02-04 | 3 | Closeout: docs update + smoke compose checkpoint | 4 (1 checkpoint + 3 auto) | `CLAUDE.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md` | FACTOR-01..03 verify | Ready (Wave 3 — depends on 02-03 ✅) |
| 02-05 | 4 | Dynamic hub registration: Settings str + regex + reserved blacklist + hub-add.sh + override.yml.template + Makefile + README + smoke checkpoint | 4 (1 checkpoint + 3 auto) | `api/app/config.py`, `tests/unit/test_config_hub_name*.py`, `api/scripts/hub-add.sh`, `docker-compose.override.yml.template`, `Hub_All/Makefile`, `api/Makefile`, `api/scripts/hub-init.sh`, `README.md`, `CLAUDE.md`, `.planning/STATE.md`, `.gitignore` | FACTOR-04 | ✅ **DONE 2026-05-22** (29/29 unit dynamic + 11/11 unit original PASS; Task 3 smoke runtime SKIP pre-resolved) |

**Coverage:** 4/4 REQ (FACTOR-01..04) covered ≥ 1 plan/REQ.

**Critical path:** 02-01 ✅ (BLOCKING DONE) → 02-02 ⊥ 02-03 (parallel Wave 2) → 02-04 (closeout FACTOR-01..03) → 02-05 (extension FACTOR-04).

**Auto-chain pause expected:** Plan 02-04 Task 1 + Plan 02-05 Task 3 đều là `checkpoint:human-action gate=blocking` (smoke compose + dynamic hub-add). User resume signal `approved` / `skip smoke` / `failed`.

### Plan 02-01 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~12 minutes |
| Tasks completed | 2/2 |
| Files modified | 2 (`api/app/main.py` + new `api/tests/unit/test_main_factory.py`) |
| Tests added | 9 (1 central full mount + 3 parametrize hub strip + 3 explicit hub strip + 1 log evidence + 1 DSN mismatch regression) |
| Test pass rate | 9/9 (100%) in 5.39s |
| Phase 1 regression | 30/30 PASS (config_hub_name + alembic_env_hub_arg + flow_per_hub_naming) |
| Lint | ruff + mypy --strict PASS |
| Commits | `8d164ef` feat + `8f0caf8` test |
| Deviations | None (plan executed exactly as written) |

### Plan 02-02 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~5 minutes |
| Tasks completed | 1/1 |
| Files modified | 1 (`docker-compose.yml` — 145 insertions, 23 deletions) |
| Verify | `docker compose config --quiet` exit 0; `docker compose config --services \| sort` → 8 service (caddy + mcp_service + postgres + 4 python-api-* + redis) |
| Acceptance criteria | 15/15 PASS (anchor + 4 service + inherit + HUB_NAME + DSN + ports + cocoindex vol + MCP re-point + 8 service signature) |
| Commits | `05a39a4` feat |
| Deviations | None (plan executed exactly as written; 1 micro-adjustment comment wording để acceptance grep match đúng 4, KHÔNG đổi YAML semantic) |

### Plan 02-03 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~65 minutes (bao gồm 2 Rule 2/3 deviation auto-fix Starlette HTTPException handler + audit queue reset) |
| Tasks completed | 2/2 |
| Files modified | 3 (`tests/integration/conftest.py` +96 append-only; `tests/integration/test_factor_hub_scoped.py` mới 228 LOC; `app/main.py` +57 Rule 2 fix) |
| Tests added | 10 (1 central full mount + 3 parametrize hub strip + 3 parametrize hub mount + 1 envelope shape verify + 1 envelope unknown route central + 1 DSN mismatch regression) |
| Test pass rate | 10/10 (100%) -m "critical and integration" in 6.49s |
| Phase 1+02-01 regression | 20/20 PASS (test_main_factory.py + test_config_hub_name.py) — KHÔNG break |
| Full unit suite regression | 175/175 PASS — KHÔNG break |
| Lint | ruff + mypy --strict PASS (conftest + test file + main.py) |
| Commits | `81543e0` test (Task 1 hub_app_factory fixture) + `c5e6036` test (Task 2 endpoint matrix + Rule 2 Starlette handler + Rule 3 audit reset) |
| Deviations | 3 (Rule 2 auto-add Starlette HTTPException handler — M2 docs claim sai; Rule 3 auto-fix audit queue cross-loop hang — `reset_queue` pattern carry forward Phase 3 Plan 05; Rule 3 comment refactor BLK-01 grep guard) |

### Plan 02-04 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~10 minutes |
| Tasks completed | 3/4 (Task 1 SKIP smoke compose — Plan 02-03 integration test in-process đã cover; defer Phase 7 migration smoke runtime) |
| Files modified | 3 (`Hub_All/CLAUDE.md` section 6 +41 lines; `.planning/STATE.md` frontmatter + Current Position + Phase 2 Results Summary + Next Action; `.planning/REQUIREMENTS.md` FACTOR-03 note 10 collective vs 12 specific endpoint matrix inline) |
| Verify | grep acceptance criteria 3 file PASS; markdown structure preserve (6 section CLAUDE.md unchanged; YAML frontmatter STATE.md parse OK) |
| Commits | `f293f71` docs (Task 2 CLAUDE.md) + 1 docs (Task 3 STATE.md) + 1 docs (Task 4 REQUIREMENTS.md) + 1 docs (SUMMARY.md final) = 4 commit |
| Deviations | 1 (Task 1 SKIP smoke compose runtime — pre-resolved user decision; rationale: Plan 02-03 in-process 10/10 PASS đã cover semantic; smoke compose runtime defer Phase 7 MIGRATE-05) |

## Phase 2 Results Summary

| Plan | Wave | Objective | Commits | Tests |
|------|------|-----------|---------|-------|
| 02-01 | 1 | Refactor create_app() conditional router mount (7 universal + 9 central-only) + unit test boot 4 hub mode | 2 (`8d164ef` feat + `8f0caf8` test) | unit 9/9 PASS (test_main_factory.py 5.39s) |
| 02-02 | 2 | Docker-compose 4 service FastAPI dedicated với YAML anchor + cocoindex LMDB volume per-hub + port 8180-8183 + MCP re-point central | 1 (`05a39a4` feat) | `docker compose config --quiet` exit 0; 8 service render đúng |
| 02-03 | 2 | Integration test endpoint matrix — 12 hub-scoped mount + 8 central-only strip + envelope shape verify | 2 (`81543e0` test fixture + `c5e6036` test matrix + Rule 2 Starlette handler) | integration 10/10 PASS (test_factor_hub_scoped.py 6.49s); 175/175 unit regression PASS |
| 02-04 | 3 | Closeout — CLAUDE.md + STATE.md + REQUIREMENTS.md note update + smoke compose 2 service (central + yte) checkpoint | 4 (3 task commit + 1 SUMMARY) | Task 1 smoke compose SKIP (rationale rõ); Task 2-4 docs update + grep acceptance criteria PASS |
| 02-05 | 4 | Dynamic hub registration FACTOR-04 — Settings str + regex + reserved blacklist + scripts/hub-add.sh + docker-compose.override.yml.template + Makefile target + README quick start (user direction B 2026-05-22) | 3 (Task 1 + 2 + 4 — Task 3 smoke runtime SKIP pre-resolved) | unit 29/29 PASS test_config_hub_name_dynamic.py (4 regression + 3 dynamic + 2 boundary + 10 reject pattern + 6 reject reserved + 1 central-not-reserved + 1 size-lock + 2 DSN match dynamic); test_config_hub_name.py 11/11 PASS (test 5 đổi sang test_invalid_hub_name_pattern_raises); ruff + mypy --strict PASS; regression test_main_factory.py 9/9 PASS; bash -n hub-add.sh + hub-init.sh exit 0; docker compose config --quiet exit 0 base parse OK |

**Phase 2 deliverable summary:**
- 4 service compose dedicated (central + yte + duoc + hcns) deploy được song song mỗi container kết nối DB riêng (`docker compose config --quiet` exit 0).
- Hub con (yte/duoc/hcns) strip 9 router central-only → 404 envelope shape (FACTOR-02 — integration test 10/10 PASS).
- Hub con mount 12 endpoint hub-scoped specific (FACTOR-03 contract — ROADMAP label gộp thành "10 collective endpoint group"; xem note REQUIREMENTS.md FACTOR-03).
- Phase 1 DSN validator + E-V3-3 isolation carry forward — KHÔNG regress (30/30 unit Phase 1 PASS; 175/175 unit toàn bộ PASS).
- **FACTOR-04 dynamic hub registration (added 2026-05-22 user direction B):** operator add hub mới (vd `phap_che`, `marketing`) bằng `make hub-add HUB=<name> [PORT=<port>]` mà KHÔNG sửa code/compose base. Settings `hub_name: Literal[4]` → `str` + regex `^[a-z][a-z0-9_]{0,15}$` + reserved blacklist 6 name (`postgres`/`cocoindex`/`template0`/`template1`/`public`/`medinet`) + `scripts/hub-add.sh` wrap `hub-init.sh` (DB layer Phase 1) + `docker-compose.override.yml.template` sed-substitute. Hub registry source-of-truth defer Phase 6 SETTINGS-04 (`hub_registry` table central CRUD).

**v3.0-a progress: Phase 1+2 DONE (2/3 phase v3.0-a). Phase 3 Auth SSO sẽ trigger v3.0-a EXIT GATE giữa Phase 3-4 (demo 1 hub con yte + central + JWT SSO + golden path PASS → user accept tiếp tục v3.0-b).**

---

## Phase 1 Results Summary (carry forward)

- **Phase:** 1 — Multi-DB Topology + Per-hub Alembic ✅ **DONE 2026-05-21**
- **Status:** VERIFICATION 4/4 SC PASS. 5 plans / 22 commits / 166 unit tests + 5 integration tests E-V3-3 PASS. Live Postgres: 5 DB (`medinet_central` + `medinet_cocoindex` + 3 hub) cùng Alembic head SHA `0004`, M2 documents COUNT=3 PRESERVED.

## Phase 1 Results Summary

| Plan | Wave | Objective | Commits | Tests |
|------|------|-----------|---------|-------|
| 01-01 | 1 | Postgres init-db.sh refactor 4 DB + HNSW 1536-dim verify | 3 | acceptance 15/15 |
| 01-02 | 1 | Settings.hub_name + DSN validator + resolve_database_url | 6 | TDD 11/11 PASS, deviation Rule 1 fix conftest |
| 01-03 | 2 | Per-hub Alembic env -x hub + make migrate-all + head-check | 5 | TDD 10/10 PASS, deviation Rule 3 Windows substitute |
| 01-04 | 2 | Cocoindex dynamic App name + APP_NAMESPACE per-hub + LEGACY fallback | 4 | TDD 9/9 PASS, M2 cocoindex state reset documented |
| 01-05 | 3 | hub-init.sh dynamic + integration test E-V3-3 + CI gate + [BLOCKING] schema push | 5+1 | integration 5/5 PASS, schema push 4 DB head SHA uniform 0004 |

**Live state verified post-execute:**
- 5 DB exist: `medinet_central`, `medinet_cocoindex`, `medinet_hub_yte`, `medinet_hub_duoc`, `medinet_hub_hcns`
- 4 hub Alembic head uniform: `0004`
- M2 `medinet_central.documents` COUNT = 3 (preserved)
- `ix_chunks_vector_hnsw` index per-DB verified

**M2 cocoindex state migration (BLOCKER 4 mitigation chain documented):**
- App name M2 `medinet_wiki_ingest` → v3.0 `medinet_central_ingest` — state orphan accepted cho v3.0-a.
- Optional fallback `COCOINDEX_APP_NAME_LEGACY=medinet_wiki_ingest` env override.
- Post-deploy re-ingest qua `UPDATE documents SET status='pending' WHERE status='completed'` (content_hash idempotent skip nếu unchanged).
- Phase 7 sẽ migrate data formally qua `pg_dump --where`.

## Next Action

1. **(Recommended) `/gsd-discuss-phase 3`** — Auth SSO + hub_ids trong JWT (GA-V3-A chốt). Gray areas: JWKS endpoint vs shared keypair vs cookie domain `.medinet.vn`; JWKS cache fallback fail-loud vs static keypair embedded; refresh token rotation contract.
2. (Optional) `/gsd-code-review 2` — advisory code review trên 9+ commits Phase 2 (workflow.code_review gate), nay phủ cả Plan 02-05 FACTOR-04 dynamic hub registration.
3. (Optional) `/gsd-verify-work 2` — manual UAT 3 SC nếu user muốn extra verify ngoài automated test (compose-level smoke checkpoint Plan 02-04 + Plan 02-05 Task 3 đều SKIP runtime, sẽ verify ở Phase 7 MIGRATE-05 runtime smoke E2E).

## Accumulated Context (carry forward từ v2.0)

### v2.0 SHIPPED ✅ 2026-05-21 — Foundation đã có

- **Backend:** Python 3.12 · FastAPI 0.136.1 · cocoindex 1.0.3 · pgvector pg16 · asyncpg/SQLAlchemy 2 async · pwdlib Argon2 · PyJWT RS256 · redis-py · LiteLLM. Single FastAPI process, single DB `medinet_central`, multi-tenancy LOGICAL `WHERE hub_id`.
- **Frontend:** React 19 · Vite 6 · TypeScript 5.8 · Tailwind v4 — D6 đã ràng buộc v2.0 (chỉ verify-only). **D6 EXPIRES ở v3.0 Phase 5** (D-V3-06).
- **MCP service:** Standalone process `mcp_service/` + OAuth 2.0 + DCR + Caddy auto-TLS (Phase 8.3 ship 2026-05-21). Re-point sang central ở v3.0 Phase 7.
- **Eval framework:** `eval/` Python pytest + 12 query VN medical + smoke regression CI gate (`pytest -m critical` < 60s mock). HUMAN UAT gate verdict OpenAI key thật ~$0.20/run defer track standalone.
- **CI:** GitHub Actions `test.yml` 7 step + `lint.yml` 6 step (secret detection 3 pattern). Branch protection rule defer v4.0.
- **Observability:** structlog JSON 10 field + Prometheus `/metrics` 5 metric + critical-path coverage 57.75% ≥50% gate.

### v3.0 LOCKED decisions (2026-05-21)

- **D-V3-01:** Multi-DB cùng instance (`medinet_central` + `medinet_hub_<name>` × N).
- **D-V3-02:** Chunks + vector denormalized sync 1 chiều hub con → tổng. Hub tổng KHÔNG re-embed.
- **D-V3-03:** Milestone-level scoping (KHÔNG nhét vào M2).
- **D-V3-04:** M2 closeout precondition (✓ v2.0 100% COMPLETE 2026-05-21).
- **D-V3-05:** Phase numbering reset về 1.
- **D-V3-06:** D6 expire formally ở Phase 5 — frontend rewrite được phép.

### v3.0 open gray areas (chốt ở discuss-phase tương ứng)

- **GA-V3-A** (Phase 3 — Auth SSO): JWT shared keypair vs JWKS endpoint vs cookie domain `.medinet.vn`. Khuyến nghị seed: JWKS endpoint từ central + Redis blacklist chung.
- **GA-V3-B** (Phase 6 — Settings sync): HTTP pull / push webhook / env var local. Khuyến nghị seed: HTTP pull + Redis cache 60s + pub/sub invalidate.
- **GA-V3-C** (Phase 5 — Proxy + frontend): 1 build detect prefix vs per-hub `VITE_HUB_NAME` build. Khuyến nghị seed: 1 build detect prefix (đỡ build matrix).
- **GA-V3-D** (Phase 4 + 7 — Sync mechanism + migration): cocoindex target thứ 2 / Postgres logical replication / outbox + worker; `pg_dump` per `hub_id` vs snapshot + replay.

### Carry-forward risks từ v2.0

- **R1** pgvector 2000-dim limit → PIN dim 1536 cho cả OpenAI + Gemini.
- **R2** HNSW post-filter → `ef_search=200` + `iterative_scan=relaxed_order` + `max_scan_tuples=20000`.
- **R4** Scanned PDF → `failed_unsupported` enum (KHÔNG silent fail).
- **R5** CocoIndex naming + APP_NAMESPACE — sẽ scale per-hub ở v3.0 Phase 1 (mỗi hub có flow naming riêng `medinet_<hub>_ingest` + APP_NAMESPACE per-hub).
- **R7** Cross-dim embedding swap REFUSE 400 — defer v4.0.

### v3.0 new risks (R-V3-1..6)

| # | Risk | Severity | Phase |
|---|---|---|---|
| R-V3-1 | Sync drift hub con vs tổng | HIGH | Phase 4 |
| R-V3-2 | D6 expire → frontend rewrite regress | HIGH | Phase 5 |
| R-V3-3 | Per-hub Alembic drift | MEDIUM | Phase 1 |
| R-V3-4 | Migration downtime | MEDIUM | Phase 7 |
| R-V3-5 | JWKS endpoint xuống | MEDIUM | Phase 3 |
| R-V3-6 | Settings sync race | LOW | Phase 6 |

### v2.0 deferred items (acknowledge — KHÔNG block v3.0)

| Category | Item | Status / Next action |
|----------|------|---------------------|
| HUMAN UAT | Phase 9 gate verdict ≥75% top-3 OpenAI key thật | `make eval-all` khi user release key ~$0.20/run — defer v3.0 reconfirm |
| HUMAN UAT | Phase 8.3 Claude web "Add custom connector" tới domain MeWiki MCP | `08.3-HUMAN-UAT.md` archive — chờ deploy public HTTPS thật |
| HUMAN UAT | Phase 8 SC1/SC2-browser/SC5 (11 trang React + citation `[1]` + docker compose 5-service) | `08-HUMAN-UAT.md` archive — sẽ smoke lại ở v3.0 Phase 5 sau D6 expire |
| HUMAN UAT | Phase 8.1 SC1 + 8.2 SC4 (`usage_events` thật) | Archives — defer v4.0 |
| Tech debt | Migrate service module log cũ sang `structlog.get_logger(__name__)` (Plan 10-01 chỉ HARD-01 ship) | DEF-10-01-B → v4.0 |
| Tech debt | Branch protection rule GitHub repo enforce 2 workflow trước merge main | Admin permission → v4.0 |
| Tech debt | Push tag `v2.0` lên remote | Defer user trigger sau verify |

> **CRIT-01 status:** ✅ ĐÃ ĐÓNG Plan 10-04 (2026-05-21) — KHÔNG còn defer.

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-21 v3.0 milestone start) + `.planning/REQUIREMENTS.md` (v3.0 — 29 REQ-ID v1) + `.planning/ROADMAP.md` (v3.0 — 7 phase reset numbering)

**Core value (unchanged from v2.0):** Ingestion tri thức Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata. v3.0 mở rộng theo trục tách hub vật lý + cross-hub aggregation.

**Mode:** YOLO · **Granularity:** Large (7 phase) · **Phase numbering:** Reset về 1 (D-V3-05)

**v3.0-a / v3.0-b split (anti-pivot mitigation):**

- **v3.0-a = Phase 1-3** (Topology + codebase factor + Auth SSO) — có thể ship standalone, demo 1 hub con + tổng + JWT SSO PASS. Nếu user accept v3.0-a → never pivot multi-DB topology.
- **v3.0-b = Phase 4-7** (Sync + proxy + settings + migration) — pivot OK nếu sync mechanism GA-V3-D chốt sai.
- 🚦 **v3.0-a EXIT GATE** giữa Phase 3 và 4 — demo 1 hub con + tổng + JWT SSO + golden path PASS → user accept là điều kiện tiếp tục v3.0-b.

---

*State khởi tạo 2026-05-21 ở milestone v3.0 sau khi v2.0 shipped 100% COMPLETE. Phase 1 chưa start. Tham chiếu PROJECT.md + REQUIREMENTS.md + ROADMAP.md cùng commit.*
