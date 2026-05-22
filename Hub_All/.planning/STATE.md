---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Multi-Hub Split
status: Phase 3 DONE 2026-05-22 ✅ — Auth SSO + hub_ids JWT 5 plan ship SSO-01..04. JWKS endpoint central RFC 7517 (`/.well-known/jwks.json` single-key RS256 + Cache-Control 1h) + JWKSCache hub con (in-process LRU + asyncio refresh 1h fail-quiet + 24h hard limit fail-loud delayed) + JWT aud=["medinet-wiki"] REQUIRED + hub_ids list[str] REQUIRED + PyJWT strict audience check 2 path + Redis blacklist key rename `auth:blacklist:{jti}` (5 vị trí + `_blacklist.py` mini-module) + 307 redirect hub con login/refresh (D-V3-Phase3-G preserve POST + body RFC 7231) + SSO-04 E4 reinforced dependency `get_current_user_for_hub_access` Layer 3 enforce + Settings 2 field mới central_jwks_url + central_url + 2 model_validator hub con required + docker-compose 3 hub con + override.yml.template env CENTRAL_JWKS_URL + CENTRAL_URL + frontend wire defer Phase 5 PROXY-02. 5 plans / 30 commits (25 Phase 3 + 5 Plan 03-05 closeout) / 65+ unit test + 6 integration test PASS in-process. M2 cũ JWT thiếu kid/aud/hub_ids → 401 reject sau deploy; user re-login ~15-30s downtime (operator broadcast Slack/Email). 🚦 v3.0-a EXIT GATE TRIGGERED — Phase 1+2+3 DONE (3/3 phase v3.0-a — 15/~32 plan ≈ 47%) — demo deliverable defer Phase 7 MIGRATE-05 full E2E (evidence chain 65+ unit + 6 integration in-process cover semantic + docker compose config base PASS). Next: /gsd-discuss-phase 4 Cross-hub data sync (GA-V3-D chốt — cocoindex target / Postgres logical replication / outbox + worker) hoặc user accept v3.0-a tiếp tục v3.0-b.
last_updated: "2026-05-22T08:38:36.000Z"
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 15
  completed_plans: 15
  percent: 47
---

# State — MEDWIKI (v3.0)

**Mã dự án:** MEDWIKI
**Milestone:** v3.0 — Multi-Hub Split
**Ngày bắt đầu:** 2026-05-21 (sau khi v2.0 shipped 100% COMPLETE 38/38 REQ-ID)
**Last updated:** 2026-05-22

## Current Position

- **Phase:** 3 — Auth SSO + hub_ids trong JWT ✅ **DONE 2026-05-22 — SSO-01..04 fully shipped (Wave 1 + Wave 2 + Wave 3 + Wave 4 + Wave 5 ✅)**
- **Plan:** 5/5 plans complete (03-01..03-05) cho SSO-01..04 ở `.planning/phases/03-auth-sso-hub-ids-jwt/`.
- **Status:** Phase 3 closed SSO-01..04 — JWKS endpoint central (`/.well-known/jwks.json` RFC 7517 single-key RS256 + Cache-Control 1h + 503 envelope `JWKS_UNAVAILABLE` fallback) qua module `api/app/auth/jwks.py` mới với `publish_jwks() + load_public_key_as_jwk()` helpers cryptography stdlib (KHÔNG jwcrypto dep mới — D-V3-Phase3-A); hub con `JWKSCache` in-process LRU + asyncio refresh 1h fail-quiet + 24h hard limit fail-loud delayed (503 `JWKS_STALE` mọi JWT verify — D-V3-Phase3-B/D); JWT claim refactor `aud=["medinet-wiki"]` REQUIRED + `hub_ids: list[str]` REQUIRED + PyJWT strict audience check 2 verify path (verify_token + verify_token_with_key) + JWT header `kid` auto-add deterministic SHA-256 PEM (D-V3-Phase3-E); Redis blacklist key rename `auth:blacklist:{jti}` (5 vị trí touch — 4 service.py refresh/logout + 1 dependencies.py — D-V3-Phase3-H) qua mini-module `_blacklist.py` (REDIS_BLACKLIST_PREFIX + make_blacklist_key helper); 307 redirect hub con `POST /api/auth/login` + `POST /api/auth/refresh` Location: central (preserve POST + body RFC 7231 — D-V3-Phase3-G); SSO-04 E4 reinforced dependency `get_current_user_for_hub_access` Layer 3 enforce — hub con check `HUB_NAME in claims.hub_ids` → 403 CROSS_HUB_ACCESS_DENIED envelope (defense-in-depth bên cạnh Layer 1 Phase 1 DSN validator + Layer 2 M2 repo `WHERE hub_id`). Settings 2 field mới `central_jwks_url` + `central_url` + 2 model_validator hub con required (`_enforce_central_jwks_url_for_hub` + `_enforce_central_url_for_hub` fail-fast boot). Settings 2 field config-driven `jwks_refresh_interval=3600` + `jwks_max_stale_seconds=86400`. Docker-compose 3 hub con + `docker-compose.override.yml.template` thêm env `CENTRAL_JWKS_URL` + `CENTRAL_URL` (FACTOR-04 inherit qua `make hub-add`). Phase 2 integration test `test_factor_hub_scoped.py` split 2 list (10 LOCAL `!= 404` + 2 SSO_REDIRECT `== 307`) — KHÔNG regress 10/10. Test-mode escape hatch `JWKS_SKIP_FETCH=1` env var (pattern song song COCOINDEX_SKIP_SETUP=1 — production KHÔNG bao giờ set). M2 backward incompat TRIPLE cumulative (kid Plan 03-02 + aud/hub_ids Plan 03-03 + frontend redirect form action Plan 03-04 defer Phase 5) — user re-login ~15-30s downtime acceptable (Slack/Email broadcast). Plan 03-05 Task 5 smoke compose runtime SKIP pre-resolved — defer Phase 7 MIGRATE-05 full E2E golden path; evidence chain Plan 03-01 (9 unit) + Plan 03-02 (27 unit + 3 integration) + Plan 03-03 (19 unit + 3 integration) + Plan 03-04 (10 unit) = 65+ unit + 6 integration PASS in-process cover semantic SSO-01..04 + `docker compose config --quiet` base PASS.
- **Last activity:** 2026-05-22 — `/gsd-execute-phase 3` wave-based execution complete cho SSO-01..04:
  - **03-01 DONE ✅** (Wave 1 BLOCKING): JWKS endpoint publish layer + module `api/app/auth/jwks.py` mới (publish_jwks + load_public_key_as_jwk + 2 helper + JWK/JWKSet TypedDict + `_derive_kid` SHA-256 11-char base64url). Central mount `GET /.well-known/jwks.json` conditional + Cache-Control 1h + 503 fallback envelope D6. Settings.central_jwks_url default None + docker-compose CENTRAL_JWKS_URL env × 3 hub con + override.yml.template (FACTOR-04 inherit). 9/9 unit test PASS `test_jwks_publish.py` 5.24s + 49/49 Phase 1+2 regression PASS. Duration ~18 phút. SUMMARY: `.planning/phases/03-auth-sso-hub-ids-jwt/03-01-SUMMARY.md`.
  - **03-02 DONE ✅** (Wave 2): JWKSCache class extend jwks.py + 2 exception JWKSStaleError/JWKSKidNotFoundError + 2 helper jwk_to_public_key/_base64url_to_int + lifespan hub con blocking fetch_initial (5s timeout — boot fail-loud D-V3-Phase3-B) + asyncio refresh task + escape hatch `JWKS_SKIP_FETCH=1` (pattern DEF-05-01). JWTManager.verify_token_with_key wrapper + JWT header `kid` auto-add ở issue_token_pair (deterministic SHA-256 match Plan 03-01). get_current_user dependency branch (central=verify_token local pem / hub con=JWKSCache.get_public_key(kid) → verify_token_with_key). Settings 2 field jwks_refresh_interval + jwks_max_stale_seconds + 1 model_validator hub con required. 4 Rule 1/3 deviation auto-fix (5 file test cũ regression CENTRAL_JWKS_URL setup + escape hatch + mypy union conflict + ruff C901). 27/27 unit mới (11 config + 9 cache TDD + 4 dependency + 3 publish regression) + 3 integration `test_jwks_cache_lifecycle.py` rotate keypair PASS + 237/237 unit regression PASS + 10/10 Phase 2 integration regression PASS. Duration ~90 phút. SUMMARY: `.planning/phases/03-auth-sso-hub-ids-jwt/03-02-SUMMARY.md`.
  - **03-03 DONE ✅** (Wave 3): JWT_AUDIENCE constant + JWTClaims aud REQUIRED + hub_ids REQUIRED (xoá default empty M2) + PyJWT strict audience check `verify_token` + `verify_token_with_key` (InvalidAudienceError + MissingRequiredClaimError mapped JWTError tiếng Việt). Redis blacklist key rename `blacklist:` → `auth:blacklist:` qua mini-module `api/app/auth/_blacklist.py` mới (REDIS_BLACKLIST_PREFIX + make_blacklist_key helper) — 5 vị trí touch (4 service.py + 1 dependencies.py). Dependency mới `get_current_user_for_hub_access` SSO-04 Layer 3 enforce + central bypass cross-hub by design + hub con strict check + defensive 500 AUTH_STATE_MISSING guard. request.state.jwt_claims wire ở get_current_user SAU 2 branch converge. iss giữ `"medinet-wiki"` RE-CONFIRM (URL-based defer Phase 7 MCP split aud). 3 Rule 1/3 deviation (test_jwt audience param + override pattern middleware inject state + mypy untyped-decorator). 19/19 unit mới (9 jwt + 7 redis + 4 dependency append) + 3 integration `test_sso_blacklist_cross_process.py` E4 cross-hub PASS + 257/257 unit regression PASS + 16/16 integration critical+integration regression PASS. Duration ~26 phút. SUMMARY: `.planning/phases/03-auth-sso-hub-ids-jwt/03-03-SUMMARY.md`.
  - **03-04 DONE ✅** (Wave 4): auth router login + refresh refactor 307 RedirectResponse Location: central (preserve POST + body RFC 7231) + `_sso_redirect(target_path, hub_name)` helper extract + X-SSO-Redirect-Reason + X-SSO-Original-Hub headers + `response_model=None` decorator opt-out (Rule 1 FastAPI union type fail). Settings.central_url field mới + `_enforce_central_url_for_hub` model_validator hub con required. Docker-compose 3 hub con + override.yml.template env CENTRAL_URL. Phase 2 integration test split HUB_SCOPED_ENDPOINTS → HUB_SCOPED_SSO_REDIRECT_ENDPOINTS (2: login + refresh) + HUB_SCOPED_LOCAL_ENDPOINTS (10) + refactor `test_hub_mounts_hub_scoped` 2 sub-loop + TestClient(follow_redirects=False) + sso_valid_bodies dict Pydantic-valid body. REQUIREMENTS.md FACTOR-03 note extend Plan 03-04 SSO-02 (10 LOCAL + 2 SSO REDIRECT clarify). 3 Rule 1/3 deviation (validator regression 7 file test cũ + FastAPI union return type + integration test body Pydantic-valid). 10/10 unit mới `test_auth_router_hub_redirect.py` + 276/276 unit regression PASS + 16/16 integration critical+integration regression PASS. Duration ~17 phút. SUMMARY: `.planning/phases/03-auth-sso-hub-ids-jwt/03-04-SUMMARY.md`.
  - **03-05 DONE ✅** (Wave 5 closeout 2026-05-22): CLAUDE.md section 6 Phase 3 DONE + 🚦 v3.0-a EXIT GATE TRIGGERED row + Phase 3 pattern subsection 5 plan detail (SSO-01..04 + E4 reinforced 3-layer breakdown) + footer changelog. STATE.md frontmatter Phase 3 DONE + completed_phases 2→3 + total_plans/completed_plans 10→15 + percent 31→47 + Current Position + Phase 3 Planning + Results Summary table + Next Action v3.0-a EXIT GATE preview. REQUIREMENTS.md SSO-01..04 mark `[x]` + note Phase 3 closeout 5 plan + E4 reinforced 3-layer + backward incompat triple + v3.0-a EXIT GATE TRIGGERED. README.md section mới "SSO Backward Incompat (Phase 3 v3.0)" 7 deploy step + endpoint mapping 5 entry + cross-hub isolation example + rollback procedure + reference. Task 5 smoke compose runtime SKIP pre-resolved per user decision — evidence chain rationale rõ ràng trong SUMMARY.md. v3.0-a EXIT GATE TRIGGERED. SUMMARY: `.planning/phases/03-auth-sso-hub-ids-jwt/03-05-SUMMARY.md`.
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

## Phase 3 Planning Summary

| Plan | Wave | Objective | Tasks | Files modified | REQ | Status |
|------|------|-----------|-------|----------------|-----|--------|
| 03-01 | 1 | JWKS endpoint publish layer (publish_jwks + RFC 7517 helper + central mount conditional + Settings.central_jwks_url + docker-compose CENTRAL_JWKS_URL env) | 2 (tdd + auto) | `api/app/auth/jwks.py` (new), `api/app/main.py`, `api/app/config.py`, `tests/unit/test_jwks_publish.py` (new), `docker-compose.yml`, `docker-compose.override.yml.template` | SSO-01 | ✅ **DONE 2026-05-22** (9/9 unit test PASS 5.24s) |
| 03-02 | 2 | JWKSCache class hub con + lifespan branch + dependency branch + Settings 2 field + validator + verify_token_with_key + JWT kid header | 5 (1 settings + 1 tdd cache + 1 lifespan+jwt + 1 dependency + 1 integration) | `api/app/auth/jwks.py` (extend), `api/app/main.py`, `api/app/auth/jwt.py`, `api/app/auth/dependencies.py`, `api/app/config.py`, 4 test file + 5 file test cũ Rule 3 regression | SSO-01 | ✅ **DONE 2026-05-22** (27+ unit + 3 integration PASS) |
| 03-03 | 3 | JWT claim refactor (aud + hub_ids REQUIRED) + Redis blacklist key rename `auth:blacklist:` + dependency SSO-04 E4 reinforced Layer 3 | 4 (1 tdd jwt + 1 tdd blacklist + 1 dependency + 1 integration) | `api/app/auth/jwt.py`, `api/app/auth/_blacklist.py` (new), `api/app/auth/service.py`, `api/app/auth/dependencies.py`, `api/app/auth/__init__.py`, 3 test file mới + 2 test file Rule 3 regression | SSO-02, SSO-03, SSO-04 | ✅ **DONE 2026-05-22** (19+ unit + 3 integration PASS) |
| 03-04 | 4 | auth router 307 redirect login/refresh hub con + Settings central_url + Phase 2 integration test split (10 LOCAL + 2 SSO_REDIRECT) + REQUIREMENTS.md FACTOR-03 note extend | 4 (1 settings + 1 router + 1 integration test split + 1 docs) | `api/app/auth/router.py`, `api/app/config.py`, `docker-compose.yml`, `docker-compose.override.yml.template`, `tests/unit/test_auth_router_hub_redirect.py` (new), `tests/integration/test_factor_hub_scoped.py`, `.planning/REQUIREMENTS.md` + 7 file test cũ Rule 3 regression | SSO-02 | ✅ **DONE 2026-05-22** (10/10 unit + 10/10 Phase 2 integration regression maintain) |
| 03-05 | 5 | Closeout — CLAUDE.md + STATE.md + REQUIREMENTS.md + README.md + smoke checkpoint runtime | 5 (4 docs + 1 checkpoint) | `Hub_All/CLAUDE.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `Hub_All/README.md` | SSO-01..04 closeout | ✅ **DONE 2026-05-22** (Task 5 smoke SKIP pre-resolved — evidence chain rõ) |

**Coverage:** 4/4 REQ (SSO-01..04) covered ≥ 1 plan/REQ.

**Critical path:** 03-01 ✅ (Wave 1 BLOCKING) → 03-02 (Wave 2 depend 03-01) → 03-03 (Wave 3 depend 03-02) → 03-04 (Wave 4 depend 03-03) → 03-05 (Wave 5 closeout depend 03-04).

**Auto-chain pause expected:** Plan 03-05 Task 5 (`checkpoint:human-action gate=blocking`) — smoke compose runtime central + yte. User resume signal: `skip smoke` (pre-resolved 2026-05-22 — defer Phase 7 MIGRATE-05 full E2E).

### Plan 03-01 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~18 phút |
| Tasks completed | 2/2 (Task 1 TDD RED+GREEN + Task 2 docker-compose env) |
| Files modified | 6 (3 mới: jwks.py + test_jwks_publish.py + SUMMARY.md + 3 sửa: main.py + config.py + docker-compose.yml + override.yml.template) |
| Tests added | 9 (7 publish layer + 2 mount conditional Settings) |
| Test pass rate | 9/9 (100%) 5.24s + 49/49 Phase 1+2 regression PASS |
| Lint | ruff + mypy --strict PASS (3 source file + 1 test) |
| Commits | `7a963c2` test RED + `d8cc3e5` feat GREEN + `e3b72be` feat docker-compose + `258c6b9` docs SUMMARY |
| Deviations | None (plan executed exactly as written) |

### Plan 03-02 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~90 phút (5 task tuần tự + 4 Rule 1/3 deviation auto-fix) |
| Tasks completed | 5/5 (1 Settings + 1 TDD JWKSCache + 1 lifespan+jwt + 1 dependency branch + 1 integration test + escape hatch) |
| Files modified | 14 (5 mới + 9 sửa — bao gồm 5 file test cũ Plan 01-02/02-01/02-05 update Rule 3 regression CENTRAL_JWKS_URL setup) |
| Tests added | 27 mới PASS (11 config validator + 9 cache TDD + 4 dependency branch + 3 integration `test_jwks_cache_lifecycle.py`) |
| Test pass rate | 27/27 mới + 237/237 unit regression PASS + 10/10 Phase 2 integration regression PASS |
| Lint | ruff + mypy --strict PASS |
| Commits | `abe2e37` Task 1 + `f705569` RED + `895551b` GREEN + `c3388aa` Task 3 + `cfd7412` Task 4 + `239d0cb` Task 5 + `155626f` docs SUMMARY |
| Deviations | 4 (3 Rule 3 blocking — 22 test cũ + 7 integration test regression + escape hatch JWKS_SKIP_FETCH; 1 Rule 1 mypy union conflict + ruff C901 noqa) |

### Plan 03-03 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~26 phút (4 task tuần tự + 3 Rule 1/3 deviation auto-fix) |
| Tasks completed | 4/4 (Task 1 TDD JWT 9min + Task 2 TDD Redis key 4min + Task 3 E4 dependency 5min + Task 4 integration 8min) |
| Files modified | 8 (5 mới: _blacklist.py + 3 test file + SUMMARY + 5 sửa: jwt.py + dependencies.py + service.py + __init__.py + 2 test regression) |
| Tests added | 19 mới (9 jwt iss/aud/hub_ids + 7 redis blacklist key + 4 dependency E4 append) + 3 integration `test_sso_blacklist_cross_process.py` |
| Test pass rate | 19/19 unit + 3/3 integration + 257/257 unit regression PASS + 16/16 integration critical+integration regression PASS |
| Lint | ruff + mypy --strict PASS (10 source file app/auth/ + 4 test file) |
| Commits | `e49aa3e` RED + `705baa0` GREEN + `bae5f17` Rule 3 + `08f5523` RED + `2d913ac` GREEN + `a8b347e` Task 3 + `0f96bf2` Task 4 + `ff3013e` docs SUMMARY |
| Deviations | 3 (2 Rule 3 blocking — test_jwt audience param + override pattern middleware inject state; 1 Rule 1 mypy untyped-decorator) |

### Plan 03-04 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~17 phút (4 task tuần tự + 1 Rule 3 regression follow-up) |
| Tasks completed | 4/4 (Task 1 Settings 4min + Task 2 router refactor 6min + Task 3 integration split 4min + Task 4 REQUIREMENTS note 3min) |
| Files modified | 14 (2 mới: test_auth_router_hub_redirect + SUMMARY + 12 sửa: router.py + config.py + docker-compose × 2 + 8 file test Rule 3 regression + REQUIREMENTS.md) |
| Tests added | 10 mới `test_auth_router_hub_redirect.py` (6 parametrize 3 hub × 2 endpoint + 2 LOCAL + 2 central) |
| Test pass rate | 10/10 unit + 276/276 unit regression PASS + 16/16 integration critical+integration regression PASS |
| Lint | ruff + mypy --strict PASS |
| Commits | `86d58c6` Task 1 + `e3ea667` Task 2 + `c862148` Task 3 + `48549ee` Task 4 + `2372747` Rule 3 follow-up + `eab5e67` docs SUMMARY |
| Deviations | 3 (1 Rule 3 blocking — 21 test cũ CENTRAL_URL regression; 2 Rule 1 bug — FastAPI union return type + integration test body Pydantic-valid) |

### Plan 03-05 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~30 phút (4 docs + 1 checkpoint pre-resolved) |
| Tasks completed | 4/5 (Task 5 smoke compose runtime SKIP pre-resolved per user decision — defer Phase 7 MIGRATE-05) |
| Files modified | 4 (`Hub_All/CLAUDE.md` section 6 v3.0 progress + Phase 3 pattern subsection + footer; `.planning/STATE.md` frontmatter + Current Position + Phase 3 Planning + Results Summary + Next Action; `.planning/REQUIREMENTS.md` SSO-01..04 mark [x] + note Phase 3 closeout; `Hub_All/README.md` section mới SSO Backward Incompat Phase 3 v3.0) |
| Verify | grep acceptance criteria 4 file PASS; markdown structure preserve (6 section CLAUDE.md unchanged; YAML frontmatter STATE.md parse OK; REQUIREMENTS Traceability table preserve; README sections "Add a new hub" + "Milestone status" preserve) |
| Commits | (Plan 03-05 này — 5 commit: 4 task + 1 SUMMARY) |
| Deviations | 1 (Task 5 SKIP smoke compose runtime — pre-resolved user decision 2026-05-22; rationale: 65+ unit + 6 integration in-process PASS đã cover semantic SSO-01..04 + `docker compose config --quiet` base PASS; smoke runtime + v3.0-a EXIT GATE demo defer Phase 7 MIGRATE-05 full E2E 3 hub + central + JWT SSO live golden path) |

## Phase 3 Results Summary

| Plan | Wave | Objective | Commits | Tests |
|------|------|-----------|---------|-------|
| 03-01 | 1 | JWKS endpoint publish layer (publish_jwks + RFC 7517 helper + central mount conditional) | 4 (`7a963c2` test RED + `d8cc3e5` feat GREEN + `e3b72be` feat docker-compose + `258c6b9` docs SUMMARY) | unit 9/9 PASS test_jwks_publish.py 5.24s + 49/49 Phase 1+2 regression PASS |
| 03-02 | 2 | JWKSCache hub con + lifespan + dependency branch + verify_token_with_key + JWT kid + Settings 2 field + escape hatch | 7 (`abe2e37` + `f705569` + `895551b` + `c3388aa` + `cfd7412` + `239d0cb` + `155626f`) | unit 27/27 PASS (11 config + 9 cache + 4 dependency + 3 publish regression) + integration 3/3 PASS test_jwks_cache_lifecycle.py + 237/237 unit regression PASS + 10/10 Phase 2 integration regression PASS |
| 03-03 | 3 | JWT aud/hub_ids REQUIRED + Redis blacklist key rename `auth:blacklist:` + SSO-04 E4 reinforced dependency Layer 3 | 8 (`e49aa3e` + `705baa0` + `bae5f17` + `08f5523` + `2d913ac` + `a8b347e` + `0f96bf2` + `ff3013e`) | unit 19/19 mới PASS (9 jwt + 7 redis + 4 dependency append) + integration 3/3 PASS test_sso_blacklist_cross_process.py + 257/257 unit regression PASS + 16/16 integration critical+integration regression PASS |
| 03-04 | 4 | auth router 307 redirect hub con login/refresh + Settings central_url + Phase 2 integration test split (10 LOCAL + 2 SSO_REDIRECT) + REQUIREMENTS.md note | 6 (`86d58c6` + `e3ea667` + `c862148` + `48549ee` + `2372747` + `eab5e67`) | unit 10/10 PASS test_auth_router_hub_redirect.py + 276/276 unit regression PASS + 16/16 integration critical+integration regression PASS |
| 03-05 | 5 | Closeout — CLAUDE.md + STATE.md + REQUIREMENTS.md + README.md + smoke checkpoint runtime | 5 (4 task + 1 SUMMARY) | Docs update grep acceptance PASS 4 file; Task 5 smoke SKIP pre-resolved (rationale rõ) |

**Phase 3 deliverable summary:**
- JWKS endpoint central (`/.well-known/jwks.json` RFC 7517 single-key RS256 + Cache-Control 1h + 503 fallback envelope D6 `JWKS_UNAVAILABLE`) + hub con strip 404 envelope (FACTOR-02 carry forward).
- JWKSCache hub con in-process LRU + asyncio refresh 1h fail-quiet + 24h hard limit fail-loud delayed (503 `JWKS_STALE` mọi JWT verify).
- JWT claim refactor: `aud=["medinet-wiki"]` REQUIRED + `hub_ids: list[str]` REQUIRED + PyJWT strict audience check 2 verify path + JWT header `kid` auto-add deterministic SHA-256.
- Redis blacklist key rename `auth:blacklist:{jti}` qua mini-module `_blacklist.py` (5 vị trí service.py + dependencies.py) + TTL = max(1, exp-now) auto-cleanup.
- 307 redirect hub con login/refresh tới central (D-V3-Phase3-G) — preserve POST + body RFC 7231 + `_sso_redirect` helper + X-SSO-Redirect-Reason/X-SSO-Original-Hub headers debug.
- SSO-04 E4 reinforced: dependency `get_current_user_for_hub_access` Layer 3 enforcement defense-in-depth (Layer 1 DSN validator Phase 1 + Layer 2 repo M2 + Layer 3 JWT claim).
- Settings 4 field mới: `central_jwks_url` + `central_url` + `jwks_refresh_interval=3600` + `jwks_max_stale_seconds=86400` + 2 model_validator hub con required (`_enforce_central_jwks_url_for_hub` + `_enforce_central_url_for_hub`).
- Docker-compose 3 hub con + override.yml.template thêm CENTRAL_JWKS_URL + CENTRAL_URL env (FACTOR-04 inherit qua `make hub-add`).
- Phase 2 integration test split assertion 2 list (10 LOCAL `!= 404` + 2 SSO_REDIRECT `== 307` + verify Location header trỏ central).
- Backward incompat TRIPLE cumulative: M2 cũ JWT thiếu kid (Plan 03-02) + aud (Plan 03-03) + hub_ids (Plan 03-03) → 401 reject; frontend hardcode same-origin FAIL ở hub con cho tới Phase 5; user re-login ~15-30s downtime.
- Frontend wire defer Phase 5 PROXY-02 (D-V3-Phase3-F honored + D-V3-06 D6 expire formally Phase 5).
- 8 decision LOCKED D-V3-Phase3-A..H consumed (JWKS endpoint pattern + cache fallback + refresh token rotation + cache storage + iss/aud claim + frontend redirect defer + hub con 307 redirect + Redis blacklist key schema).
- 33 STRIDE threat mitigation breakdown: Plan 03-01 (6: 3 accept + 3 mitigate) + Plan 03-02 (8: 3 accept + 5 mitigate) + Plan 03-03 (8: 4 accept + 4 mitigate) + Plan 03-04 (6: 3 accept + 3 mitigate) + Plan 03-05 (5: 2 accept + 3 mitigate) = **33 threat addressed**.

**v3.0-a progress: Phase 1+2+3 DONE (3/3 phase v3.0-a — 15/~32 plan ≈ 47%). 🚦 v3.0-a EXIT GATE TRIGGERED giữa Phase 3-4 — demo deliverable (1 hub con yte + central + Redis + Postgres + JWT SSO + golden path) defer Phase 7 MIGRATE-05 full E2E runtime; evidence chain in-process semantic PASS (65+ unit + 6 integration + docker compose config base) → user accept tiếp tục v3.0-b (Phase 4-7 sync + proxy + settings + migration).**

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

1. **(BLOCKING — 🚦 v3.0-a EXIT GATE TRIGGERED)** Demo deliverable: 1 hub con (yte) + central + Redis + Postgres deploy được trên Docker compose; user login `https://central/api/auth/login` → JWT valid; user truy cập `https://central/yte/api/...` (direct port test trước Caddy lên Phase 5) → hub con verify JWT qua JWKSCache → 200; hub con CHỈ truy cập data hub yte (test cross-hub access → 403 CROSS_HUB_ACCESS_DENIED); golden path login → upload (local hub yte chỉ) → search local → PASS. **Smoke runtime deliverable defer Phase 7 MIGRATE-05 full E2E** (3 hub + central golden path + JWT SSO live). Evidence chain in-process: Plan 03-01 (9 unit) + Plan 03-02 (27 unit + 3 integration) + Plan 03-03 (19 unit + 3 integration) + Plan 03-04 (10 unit) = 65+ unit + 6 integration PASS + `docker compose config --quiet` base PASS — cover end-to-end semantic SSO-01..04. **User accept → tiếp tục v3.0-b. User reject → re-discuss D-V3-01 topology choice qua `/gsd-discuss-milestone v3.0`.**
2. **(Recommended sau accept v3.0-a) `/gsd-discuss-phase 4`** — Cross-hub Data Sync (GA-V3-D chốt: cocoindex target thứ 2 vs Postgres logical replication vs outbox + worker; idempotent key chunk_id vs content_hash; sync timing post-ingest hook vs async worker; checksum cron schedule daily vs hourly sample).
3. (Optional) `/gsd-code-review 3` — advisory code review trên 30 commits Phase 3 (workflow.code_review gate), phủ 5 plan ship SSO-01..04 + 8 decision LOCKED D-V3-Phase3-A..H + 33 STRIDE threat mitigation.
4. (Optional) `/gsd-verify-work 3` — manual UAT 4 SC nếu user muốn extra verify ngoài automated test (Plan 03-05 Task 5 smoke compose runtime SKIP pre-resolved, sẽ verify ở Phase 7 MIGRATE-05 runtime smoke E2E).

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
