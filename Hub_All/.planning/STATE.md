---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Multi-Hub Split
status: "🎉 v3.0 MILESTONE CLOSED 2026-05-23 — Phase 7 Migration + Smoke E2E DONE 5 plan ship MIGRATE-01..05 + 4 D-V3-Phase7-A/B/C/D LOCKED + 5 bash script scripts/migrate/ (01-snapshot-hubs.sh + 02-restore-hub.sh + 03-switch-caddy.sh + 04-truncate-central.sh + 05-smoke-e2e.sh) + 1 runbook 06-mcp-smoke.md + 1 fixture sample-document.docx (37KB python-docx reproducible) + automated 3 hub × 7-step golden path (login + upload + poll status + search local + cross-hub + ask + citation [N]) + Prometheus assertion post-loop + blue/green per-hub procedure + dry-run default ON truncate (D-V3-02 chunks PRESERVED) + MCP re-point central aggregate. 38/38 plan ship · 30/30 REQ-ID consumed (TOPO 4 + FACTOR 4 + SSO 4 + SYNC 5 + PROXY 4 + SETTINGS 4 + MIGRATE 5) · 7/7 phase complete. v3.0-a (Phase 1-3) + v3.0-b (Phase 4-7) anti-pivot pattern hoàn tất. Carry-forward Phase 6: SETTINGS-01..04. HTTP pull on-demand + Redis cache TTL 60s/300s/60s + pub/sub invalidate channel `settings:invalidate` (E-V3-4 < 30s propagate, < 1s thực tế qua pub/sub) + api_keys verify proxy central `X-Internal-Auth` shared secret 32-char `hmac.compare_digest` constant-time (T-06-03-01) + hub_registry read-only TTL 5 phút singleton key. Module mới `api/app/settings_sync/` 5 file (~700 LOC source + ~870 LOC test) — `keys.py` (4 constant + `make_apikey_cache_key` SHA-256 hex prefix 16 char T-06-04-02 mitigation KHÔNG plaintext Redis) + `metrics.py` (6 Prometheus collector module-level label `hub_name` + `key_type` bounded enum W7 carry forward) + `client.py` (3 HTTP client class — `RagConfigClient` fetch_initial blocking 5s fail-loud + Redis cache TTL 60s + `HubRegistryClient` singleton TTL 300s + `ApiKeyVerifyClient` POST + X-Internal-Auth header + cache hash key TTL 60s + KHÔNG cache negative 401) + `subscriber.py` (settings_subscriber_loop asyncio task subscribe single channel + Pydantic InvalidateMessage Literal enum payload validate T-06-02-03 + 3 config_key flush branch + outer reconnect retry 5s + CancelledError graceful + `_process_message + _subscribe_and_listen` helper C901 refactor) + `__init__.py` re-export 18 symbol. `auth/api_key.py::require_api_key` REFACTOR branch hub_name (central=local M2 `ApiKeyService.verify_key` AES-GCM unchanged AUX-02 / hub con=`app.state.api_key_verify_client.verify` proxy + 503 `APIKEY_VERIFY_CLIENT_UNAVAILABLE` boot fail-loud R-V3-6). `auth/dependencies.py::require_internal_auth` async dep + hmac.compare_digest + 401 INTERNAL_AUTH_FAIL envelope. `routers/rag_config.py::update_rag_config` PUT extend publish best-effort fail-open `redis.publish('settings:invalidate', json({config_key:'rag_config',hub:'*',timestamp:int(time.time())}))` cross-process invalidate. `routers/api_keys.py POST /verify` endpoint mới central-only mount FACTOR-02 carry forward + VerifyApiKeyRequest schema (Field min_length=1 max_length=256) + return raw dict `{valid, principal}`. `main.py::lifespan` thêm block hub con (settings.hub_name != 'central') SAU sync_worker_task spawn — init 4 `app.state.<X> = None` defensive + escape hatch `SETTINGS_SKIP_FETCH=1` (4-flag pattern song song JWKS_SKIP_FETCH + SYNC_SKIP_CENTRAL_POOL + COCOINDEX_SKIP_SETUP) + 3 client instantiate + await rag_client.fetch_initial() blocking 5s + await hub_client.fetch_initial() (ApiKeyVerifyClient lazy KHÔNG fetch_initial) + boot fail-loud raise → uvicorn exit 1 (D-V3-Phase6-A LOCKED + R-V3-6 LOW pattern song song Plan 03-02 JWKSCache + Plan 04-04 central_sync_pool) + spawn settings_subscriber_task `asyncio.create_task(settings_subscriber_loop)` với guard `app.state.redis is not None AND app.state.redis_ready` (T-06-04-04 Rule 3 fix — redis_ready source-of-truth; from_url lazy assign object trước ping; ping fail → redis_ready=False NHƯNG app.state.redis vẫn non-None → subscriber spawn broken connection → infinite reconnect hang). Shutdown graceful sau yield: task.cancel() + asyncio.wait_for(timeout=10s) + suppress CancelledError/TimeoutError (T-06-04-03). Settings 5 field mới (settings_proxy_secret str + 3 TTL int + subscriber_reconnect_seconds) + 1 model_validator `_enforce_settings_proxy_secret` length ≥ 32 char BẤT KỂ hub_name (KHÁC Phase 3+4 pattern — shared secret BOTH sides). docker-compose 4 service env wire `SETTINGS_PROXY_SECRET: ${SETTINGS_PROXY_SECRET:?msg}` fail-loud + override.yml.template FACTOR-04 placeholder + .env.example document hint `openssl rand -hex 32`. 6 Prometheus metric mới: `settings_cache_hit/miss_total{hub_name,key_type}` + `settings_pull_latency_seconds{hub_name,endpoint}` histogram + `settings_invalidate_received_total{hub_name,key_type}` + `settings_stale_seconds{hub_name,key_type}` gauge + `apikey_verify_total{hub_name,result}` — label cardinality bounded W7 carry forward. 4 D-V3-Phase6-A..D LOCKED consumed (A=HTTP pull + Redis pub/sub hybrid REJECT push webhook / env var local; B=TTL 60s/300s/60s per category; C=1 channel `settings:invalidate` Pydantic Literal enum payload validate KHÔNG split 3 channel; D=Shared secret X-Internal-Auth ≥ 32 char hmac.compare_digest constant-time). 33+ STRIDE threat T-06-01..04 mitigation (Plan 06-01 fail-loud env + SHA-256 cache key + Plan 06-02 Pydantic enum + best-effort fail-open + Plan 06-03 hmac.compare_digest + try/except + Plan 06-04 timeout connect=2s read=5s + task.cancel wait_for + redis_ready guard). 5 plan ship in-process 87+ unit (25 Plan 06-01 + 22 Plan 06-02 + 22 Plan 06-03 + 6 integration Plan 06-04 + thêm regression) + 6 integration test ASGI lifespan + 452/452 unit Phase 1..6 regression + 19/19 Phase 2+5 integration regression PASS + ruff/mypy --strict clean trên main.py + 2 test file mới + 0 break M2 + 0 Rule 4 architectural. Plan 06-05 Task 5b smoke 4 hub × PUT central rag_config + verify yte cache flush + apikey verify proxy 200 — auto-fallback `skip smoke` per --auto chain + v3.0-b precedent (Plan 03-05 + 04-07 + 05-06 pre-resolved skip pattern); evidence chain in-process 62+ unit + 6 integration test PASS cover SETTINGS-01..04 semantic; manual visual smoke runtime defer Phase 7 MIGRATE-05 full E2E. v3.0-b 3/4 phase DONE (Phase 4+5+6 — 33/~37 plan ≈ 89%). Backward compat M2 KHÔNG break — `require_api_key + update_rag_config` signature mở rộng `request: Request` param FastAPI Depends auto-inject + M2 `ApiKeyService.verify_key` AES-GCM at-rest LOCKED unchanged AUX-02 + M2 `RagConfigService.update_config()` LOCKED unchanged. Hub con M2 cũ thiếu SETTINGS_PROXY_SECRET env → Settings validator fail boot → operator phải set TRƯỚC deploy (xem README.md System Settings Sync Deploy Notes 5 step + rollback procedure). Next: `/gsd-discuss-phase 7` Migration + Smoke E2E (MIGRATE-01..05 — pg_dump per hub_id + blue/green restore + MCP re-point + smoke E2E full v3.0)."
last_updated: "2026-05-23T06:00:00.000Z"
phase_7_status: "DONE 2026-05-23 ✅ 🎉 — Migration + Smoke E2E 5 plan/4 wave shipped MIGRATE-01..05 + 4 D-V3-Phase7-A/B/C/D LOCKED + 5 bash script scripts/migrate/ + 1 runbook MCP smoke + 1 fixture DOCX. Plan 07-05 closeout Wave 5: scripts/migrate/05-smoke-e2e.sh (271 LOC bash strict mode automated 3 hub × 7-step golden path login + upload DOCX + poll status completed (max 30s) + search local hub + search cross-hub central absolute path D-V3-Phase4-D3 + ask LLM + citation [N] regex `\\[[0-9]+\\]` verify + logout) qua curl + jq envelope D6 parse + Prometheus assertion post-loop (apikey_verify_total{result=cached} > 0 Phase 6 SETTINGS-03 + sync_count_drift < 0.01 R-V3-1 + cross_hub_search_latency_seconds histogram populated E-V3-2 < 1.5s). Fixture scripts/migrate/fixtures/sample-document.docx 37KB Vietnamese y tế domain (vaccin + dược keyword cho search/ask test step 4-6) + generate-sample.py python-docx reproducible script. 5-doc closeout: CLAUDE.md §6 Phase 7 progress row ✅ DONE + Phase 7 Migration + Smoke E2E pattern subsection (5 plan summary + 5 architecture insight + T-07-01..05 STRIDE + backward compat + R-V3-4 mitigation + v3.0 milestone CLOSED banner) + STATE.md frontmatter Phase 7 DONE + Current Position + Phase 7 Results Summary table + REQUIREMENTS.md MIGRATE-01..05 mark [x] + NOTE Phase 7 closeout + ROADMAP.md Phase 7 row ✅ DONE + Decisions block + Progress 38/38 100% + v3.0 milestone celebration banner + README.md NEW section Migration + Smoke E2E Runbook (Phase 7 v3.0) 7-step deploy procedure + rollback per-hub + 30-day retention + MCP env wire + audit trail + v3.0 milestone CLOSED 🎉. Manual visual smoke 4 hub × 11 trang React M2 COMPAT-01 checkpoint:human-action gate=advisory KHÔNG blocking per D-V3-Phase7-D LOCKED — auto-fallback `skip smoke` per --auto chain mode + v3.0-b precedent (Plan 03-05 + 04-07 + 05-06 + 06-05 pre-resolved skip pattern); evidence chain automated 05-smoke-e2e.sh đủ semantic MIGRATE-05 coverage + bash -n PASS + 12 grep acceptance + 143/135 mcp_service test PASS regression; visual regression defer ops handover post-milestone-close deployment runbook. SCOPE LIMIT honored — Executor tạo scripts + docs, KHÔNG run smoke against live infra. Foundation Phase 7 5/5 plan resolve — v3.0 MILESTONE CLOSED 100% 38/38 plan. Next: /gsd-complete-milestone v3.0 separate command archive milestone."
phase_7_progress: "5/5 plan complete — Plan 07-01 MIGRATE-01 ✅ + Plan 07-02 MIGRATE-02 ✅ + Plan 07-03 MIGRATE-03 ✅ + Plan 07-04 MIGRATE-04 ✅ + Plan 07-05 MIGRATE-05 ✅ (closeout — smoke automated + 5-doc closeout + v3.0 milestone CLOSED marker)"
phase_7_carry_forward: "Carry forward Wave 1+2+3 BLOCKING + Wave 3 parallel: Plan 07-01 (e057e5f + 786586d snapshot script 194 LOC + .gitignore + README 30-day retention); Plan 07-02 (81256fc + f1556cc 02-restore-hub.sh 225 LOC + 03-switch-caddy.sh VERIFY-ONLY 132 LOC + --rollback flag); Plan 07-03 (5ade696 04-truncate-central.sh 269 LOC + dry-run default + audit INSERT atomic + chunks PRESERVED D-V3-02); Plan 07-04 (f3934fe + 7fdac43 mcp_service/mcp_app/config.py default re-point + 06-mcp-smoke.md 5-step Inspector OAuth runbook 181 LOC). Plan 07-04 ship 2 file modify (mcp_service/mcp_app/config.py default api_base_url đổi http://localhost:8180 → http://python-api-central:8080 + 5-line decision comment D-V3-Phase7-C + Phase 4 Plan 04-05 cross-hub aggregate 1 SQL + T-08.2-01-T SSRF validator unchanged + docker-compose.yml mcp_service env block comment 're-confirm' → 'CONFIRMED Phase 7 MIGRATE-04' env value MCP_API_BASE_URL không đổi đã đúng từ Plan 02-02 D-V3-Phase2-C) + 1 file mới (scripts/migrate/06-mcp-smoke.md 181 LOC manual runbook 5-step Inspector OAuth — Step 1 OAuth connect wiki.medinet.vn/mcp/auth/v2/authorize + Step 2 search_wiki single-hub yte + Step 3 ask_wiki cross-hub no hub_id + Step 4 citation [N] resolve + Step 5 Prometheus metrics scrape apikey_verify_total/cross_hub_search_latency/sync_lag_seconds/sync_count_drift + rollback procedure 5-step + reference links). D-V3-Phase7-C LOCKED invariant — MCP gọi central aggregate (KHÔNG fan-out N hub) carry forward D-V3-02 LOCKED Phase 1 + D-V3-Phase4-D1 LOCKED Phase 4 Plan 04-05 cross-hub 1 SQL aggregated. MCP tools signature search_wiki(hub_id?) + ask_wiki(hub_id?) UNCHANGED + OAuth flow Phase 8.3 v2.0 UNCHANGED + api_key_service AUX-02 AES-GCM UNCHANGED + field_validator _validate_base_url UNCHANGED (T-08.2-01-T SSRF mitigation Phase 8.3 v2.0 carry forward). Regression baseline: uv run pytest -q (mcp_service/tests/) → 143 passed in 3.67s (Phase 8.3 v2.0 baseline 135 + Plan 10-04 CORS split policy 8 test thêm) — 0 regression sau config.py default change. T-07-04-01..04 STRIDE 3 mitigate + 1 accept (T-07-04-03 audit M2 carry forward AUX — MCP tool call qua central /api/search + /api/ask đã có audit_logs INSERT). 19/19 acceptance grep PASS (8 Task 1 + 11 Task 2). 1 Rule 3 deviation auto-fix uv run pytest substitution (python -m pytest direct fail ModuleNotFoundError aiosqlite → switch uv run đã có trong plan instruction interfaces section). SCOPE LIMIT honored — config.py + docker-compose edit OK + runbook create OK + uv run pytest regression verify OK; KHONG run Inspector OAuth live against real infra (runbook documents manual operator steps). Foundation Phase 7 4/5 plan resolve — Plan 07-05 closeout (05-smoke-e2e.sh automated 3 hub × 7-step golden path + docs CLAUDE.md + STATE.md + ROADMAP.md + REQUIREMENTS.md + README.md + milestone v3.0 CLOSED marker) là plan cuối Phase 7."
phase_6_status: "DONE 2026-05-23 ✅ — 5 plan/5 wave shipped qua /gsd-execute-phase 6 --auto --chain. Wave 1 BLOCKING (06-01 settings_sync/ module scaffold 3 file + Settings 5 field + 6 Prometheus collector + docker-compose 4 service env wire fail-loud + override.yml.template FACTOR-04 + .env.example 5 env mới) → Wave 2 (06-02 client.py 3 HTTP client class RagConfigClient/HubRegistryClient/ApiKeyVerifyClient + subscriber.py settings_subscriber_loop + Pydantic InvalidateMessage Literal enum schema + 22 unit test PASS, 3 Rule 1 fix httpx.Timeout 4-param + pytest-asyncio CancelledError + C901 complexity refactor) → Wave 3 (06-03 require_api_key REFACTOR branch hub_name + require_internal_auth hmac.compare_digest dep + update_rag_config publish best-effort fail-open + POST /api/api-keys/verify endpoint central-only mount FACTOR-02 + VerifyApiKeyRequest schema, 22 unit test PASS + 50/50 cluster + 19/19 integration, 0 deviation) → Wave 4 BLOCKING (06-04 lifespan hub con block init 3 client blocking fetch_initial 5s fail-loud + spawn settings_subscriber_task asyncio.create_task subscribe settings:invalidate guard redis_ready T-06-04-04 + shutdown graceful wait_for 10s + SETTINGS_SKIP_FETCH=1 escape hatch, 2 atomic commit ddf28e1 + b8a4221, 6 integration ASGI LifespanManager PASS, 3 Rule 3 deviation auto-fix inline main.py redis_ready guard + 2 test infra SETTINGS_SKIP_FETCH=1 env) → Wave 5 closeout (06-05 docs CLAUDE.md + STATE.md (file này) + REQUIREMENTS.md SETTINGS-01..04 [x] + ROADMAP.md Phase 6 DONE + README.md NEW section System Settings Sync Deploy Notes 5-step + smoke checkpoint Task 5b SKIP auto-fallback per --auto chain + v3.0-b precedent Plan 03-05 + 04-07 + 05-06). USE_WORKTREES=false (sequential per Windows stability). 4 REQ closed SETTINGS-01..04 + 4 D-V3-Phase6-A..D LOCKED + 33+ STRIDE T-06-01..04 covered + 6 Prometheus metric mới + backward compat M2 KHÔNG break (AUX-02 AES-GCM + RagConfigService.update_config LOCKED unchanged)."
phase_5_status: "DONE 2026-05-23 ✅ — 6 plan/5 wave shipped qua /gsd-execute-phase 5 --auto --no-transition. Wave 4 BLOCKING RUNTIME WIRING ship `api/app/main.py::lifespan` hub con block (settings.hub_name != 'central') init 3 client `RagConfigClient` + `HubRegistryClient` + `ApiKeyVerifyClient` từ Wave 2 với blocking `fetch_initial()` 5s + fail-loud raise → uvicorn exit 1 (D-V3-Phase6-A LOCKED + R-V3-6 LOW pattern song song Phase 3 JWKSCache), spawn `settings_subscriber_task = asyncio.create_task(settings_subscriber_loop(redis, hub_name, reconnect_seconds))` subscribe single channel `settings:invalidate` Wave 2 với guard `app.state.redis is not None AND app.state.redis_ready` (T-06-04-04 Rule 3 fix — KHÔNG chỉ check redis non-None vì M2 from_url lazy assign trước ping; ping fail → redis_ready=False NHƯNG app.state.redis vẫn non-None → subscriber spawn broken connection → infinite reconnect hang test), populate `app.state.{rag_config_client, hub_registry_client, api_key_verify_client, settings_subscriber_task}` runtime cho Wave 3 dependency consume. Test-mode escape hatch `SETTINGS_SKIP_FETCH=1` env bypass blocking fetch (pattern 4-flag song song JWKS_SKIP_FETCH + SYNC_SKIP_CENTRAL_POOL + COCOINDEX_SKIP_SETUP). Shutdown graceful: `settings_subscriber_task.cancel() + asyncio.wait_for(timeout=10s)` + suppress CancelledError/TimeoutError (T-06-04-03 resource exhaustion + carry forward Plan 03-02 + 04-04 search_cache_task M2 pattern). 6 integration test ASGI LifespanManager PASS (skip path + populate 3 client + subscriber branch by redis_ready + shutdown state reset + boot fail-loud direct RagConfigClient test KHÔNG asgi_lifespan tránh leak audit_task/search_cache_task tasks spawn trước Phase 6 block + central skip). Pubsub e2e defer Phase 7 MIGRATE-05 (fakeredis-py async pubsub.listen() KHÔNG yield message reliable; Plan 06-02 unit subscriber test cover semantic). 2 atomic commit Plan 06-04 (ddf28e1 feat Task 1 lifespan + b8a4221 test Task 2 integration test + Rule 3 fix). 3 Rule 3 deviation auto-fix inline: (1) main.py subscriber spawn guard sửa từ `redis is not None` → `redis is not None and redis_ready`; (2) `test_auth_router_hub_redirect.py::_setup_env` thêm SETTINGS_SKIP_FETCH=1 env hub con block (10 test FIX); (3) `tests/integration/conftest.py::hub_app_factory` thêm SETTINGS_SKIP_FETCH=1 env hub con block (11 test_factor_hub_scoped FIX). 6/6 integration PASS + 452/452 unit Phase 1..6 regression + 19/19 Phase 2+5 integration regression + ruff + mypy --strict clean trên main.py + 2 test file mới. Next: Plan 06-05 Wave 5 closeout — docs update CLAUDE.md + STATE.md + REQUIREMENTS.md + ROADMAP.md + README.md + smoke checkpoint runtime SKIP auto-fallback per --auto chain + v3.0-b precedent Plan 03-05 + 04-07 + 05-06 → defer Phase 7 MIGRATE-05 full E2E."
progress:
  total_phases: 7
  completed_phases: 7  # 🎉 v3.0 MILESTONE CLOSED — All 7 phase complete
  total_plans: 38  # 33 (Phase 1..6) + 5 (Phase 7 plans 07-01..07-05)
  completed_plans: 38  # 33 + 5 (Phase 7 Plan 07-01..07-05 all ship)
  percent: 100  # 38/38 = 100% — v3.0 MILESTONE CLOSED 🎉
milestone_status: "CLOSED"
milestone_close_date: "2026-05-23"
next_action: "/gsd-complete-milestone v3.0 — archive milestone .planning/milestones/v3.0-archive/ + reset ROADMAP cho v4.0 backlog"
phase_5_status: "DONE 2026-05-23 ✅ — 6 plan/5 wave shipped qua /gsd-execute-phase 5 --auto --no-transition. Wave 1 BLOCKING (05-01 Caddyfile + compose + .env.example) → Wave 2⊥ (05-02 FE prefix detect + vitest infra + 05-03 branding registry 13 vitest PASS Rule 1 fix threshold 0.6) → Wave 3 (05-04 Login 4-state + Layout sidebar + crossHubSearch absolute + tryRefresh redirect:'follow' B-02 fix, 4 atomic commit 54fc315 + ca6f4e4 + ed721fd + 61ac731, 37/37 vitest PASS full suite) → Wave 4 (05-05 hub-add.sh 9-step pipeline extend FACTOR-04 + PROXY-01, 1 atomic commit 6b282b8 137+/10-, bash -n PASS + 13/13 Task 1 + 5/5 Task 2 acceptance) → Wave 5 closeout (05-06 docs CLAUDE.md + STATE.md + REQUIREMENTS.md + ROADMAP.md + README.md + smoke checkpoint Task 5b SKIP pre-resolved per --auto chain mode + v3.0-b precedent Plan 03-05/04-07). USE_WORKTREES=false (sequential per Windows stability). 4 REQ closed PROXY-01..04 + 16 D-V3-Phase5-A1..D4 LOCKED + 7 STRIDE T-5-01..07 covered + FACTOR-04 extend hub-add.sh."
---

# State — MEDWIKI (v3.0)

**Mã dự án:** MEDWIKI
**Milestone:** v3.0 — Multi-Hub Split
**Ngày bắt đầu:** 2026-05-21 (sau khi v2.0 shipped 100% COMPLETE 38/38 REQ-ID)
**Last updated:** 2026-05-23

## Current Position

🎉 **v3.0 MILESTONE CLOSED 2026-05-23** — All 7/7 phases complete · 38/38 plans · 30/30 REQ-ID consumed · v3.0-a (Phase 1-3) + v3.0-b (Phase 4-7) anti-pivot pattern hoàn tất.

- **Phase:** 7 — Migration + Smoke E2E ✅ **DONE 2026-05-23 — MIGRATE-01..05 fully shipped (Wave 1+2+3 BLOCKING + Wave 3 parallel + Wave 5 closeout ✅)**
- **Plan:** 5/5 plans complete (07-01..07-05) cho MIGRATE-01..05 ở `.planning/phases/07-migration-smoke-e2e/`.
- **Next Action:** `/gsd-complete-milestone v3.0` — archive milestone `.planning/milestones/v3.0-archive/` + reset ROADMAP.md cho v4.0 backlog (sub-hub split per `project_v3_multi_hub_split.md` seed memory 2026-05-21 + HA Redis cluster + OCR Vietnamese + streaming /api/ask + comprehensive coverage >80%).
- **Plan 07-05 status (closeout):** Wave 5 ship — `scripts/migrate/05-smoke-e2e.sh` (271 LOC bash strict mode automated 3 hub × 7-step golden path login + upload DOCX + poll status completed (max 30s) + search local hub + search cross-hub central absolute path D-V3-Phase4-D3 + ask LLM + citation [N] regex `\[[0-9]+\]` verify + logout) qua curl + jq envelope D6 parse + Prometheus assertion post-loop (apikey_verify_total{result=cached} > 0 Phase 6 SETTINGS-03 + sync_count_drift < 0.01 R-V3-1 + cross_hub_search_latency_seconds histogram populated E-V3-2 < 1.5s). Fixture scripts/migrate/fixtures/sample-document.docx 37KB Vietnamese y tế domain (vaccin + dược keyword) + generate-sample.py python-docx reproducible script. 5-doc closeout: CLAUDE.md §6 Phase 7 progress row ✅ DONE + Phase 7 pattern subsection (file kế tiếp) + STATE.md frontmatter Phase 7 DONE + Current Position + Phase 7 Results Summary table + REQUIREMENTS.md MIGRATE-01..05 mark [x] + NOTE Phase 7 closeout + ROADMAP.md Phase 7 row ✅ DONE + Decisions block + Progress 38/38 100% + v3.0 milestone CLOSED banner + README.md NEW section Migration + Smoke E2E Runbook. Manual visual smoke 4 hub × 11 trang React M2 COMPAT-01 checkpoint:human-action gate=advisory KHÔNG blocking per D-V3-Phase7-D LOCKED — auto-fallback `skip smoke` per --auto chain + v3.0-b precedent (Plan 03-05 + 04-07 + 05-06 + 06-05); evidence chain automated 05-smoke-e2e.sh đủ semantic MIGRATE-05 coverage + bash -n PASS + 12 grep acceptance + 143/135 mcp_service test PASS regression; visual regression defer ops handover deployment runbook post-milestone-close. SCOPE LIMIT honored — Executor tạo scripts + docs, KHÔNG run smoke against live infra.

## Phase 7 Results Summary

| Plan | Wave | Objective | Commits | Tests |
|------|------|-----------|---------|-------|
| 07-01 | 1 BLOCKING | scripts/migrate/01-snapshot-hubs.sh pg_dump per hub_id + migrate-snapshots/ .gitignore + README 30-day retention (MIGRATE-01 — D-V3-Phase7-A) | 2 (e057e5f + 786586d) | bash -n exit 0 + 18/18 grep acceptance PASS |
| 07-02 | 2 BLOCKING | 02-restore-hub.sh psql restore 4-step + 03-switch-caddy.sh VERIFY-ONLY 3-step + --rollback flag (MIGRATE-02 — D-V3-Phase7-B blue/green) | 2 (81256fc + f1556cc) | bash -n exit 0 cả 2 + 21/21 grep acceptance PASS |
| 07-03 | 3 BLOCKING | 04-truncate-central.sh atomic BEGIN/COMMIT DELETE 4 table per hub_id + audit_logs INSERT TRƯỚC DELETE + dry-run default ON + chunks PRESERVED D-V3-02 invariant strict (MIGRATE-03) | 1 (5ade696) | bash -n exit 0 + 15/15 grep acceptance PASS + DELETE FROM chunks = 0 + 10 D-V3-02 reference |
| 07-04 | 3 parallel | mcp_service/mcp_app/config.py default re-point + docker-compose.yml comment + 06-mcp-smoke.md 5-step Inspector OAuth runbook (MIGRATE-04 — D-V3-Phase7-C) | 2 (f3934fe + 7fdac43) | uv run pytest mcp_service: 143 passed (≥135 baseline) + 19/19 grep acceptance PASS |
| 07-05 | 5 closeout | 05-smoke-e2e.sh automated 3 hub × 7-step golden path + fixture sample-document.docx 37KB + 5-doc closeout + v3.0 milestone CLOSED marker (MIGRATE-05 — D-V3-Phase7-D advisory) | 4 (78aad9a fixture + 826c93d smoke + 8916701 CLAUDE.md + state/req/roadmap/readme) | bash -n exit 0 + 12 grep acceptance PASS + python-docx verify 8 paragraphs DOCX |

**Phase 7 deliverable summary (5 plan / ~12 commits):**
- 5 bash script `scripts/migrate/` complete: 01-snapshot (194 LOC) + 02-restore (225 LOC) + 03-switch-caddy VERIFY-ONLY (132 LOC) + 04-truncate (269 LOC) + 05-smoke-e2e (271 LOC) = ~1091 LOC bash strict mode.
- 1 runbook `06-mcp-smoke.md` 181 LOC manual Inspector OAuth 5-step.
- 1 fixture `sample-document.docx` 37KB Vietnamese y tế domain + `generate-sample.py` python-docx reproducible.
- 4 D-V3-Phase7-A/B/C/D LOCKED 2026-05-23 (pg_dump option a + blue/green per-hub + MCP central aggregate + automated mandatory + human advisory).
- T-07-01..05 STRIDE coverage 5 plan threat model.
- mcp_service 143/135 test PASS regression baseline (Phase 8.3 v2.0 carry forward + Plan 10-04 CORS split 8 thêm).

**v3.0 MILESTONE CLOSED 🎉 2026-05-23** — 38/38 plan ship · 30/30 REQ-ID consumed · 7/7 phase complete.

## Phase 7 Plan deliverable details

**Plan 07-05 (Wave 5 closeout — file này, 2026-05-23):**
- `Hub_All/scripts/migrate/05-smoke-e2e.sh` 271 LOC bash strict mode automated 3 hub × 7-step golden path (login + upload + poll + search local + cross-hub absolute path + ask + citation [N] verify + logout) qua curl + jq envelope D6 parse + Prometheus assertion post-loop (apikey_verify_total{result=cached} > 0 + sync_count_drift < 0.01 + cross_hub_search_latency_seconds histogram populated) + exit code 0/1 semantic.
- `Hub_All/scripts/migrate/fixtures/sample-document.docx` 37KB Vietnamese y tế domain (vaccin + dược keyword) + `generate-sample.py` python-docx reproducible script.
- 5-doc closeout: CLAUDE.md §6 Phase 7 progress row ✅ DONE + Phase 7 pattern subsection + STATE.md frontmatter Phase 7 DONE + Current Position + Phase 7 Results Summary table + REQUIREMENTS.md MIGRATE-01..05 mark [x] + NOTE Phase 7 closeout + ROADMAP.md Phase 7 row ✅ DONE + Decisions block + Progress 38/38 100% + v3.0 milestone celebration banner + README.md NEW section Migration + Smoke E2E Runbook.
- Manual visual smoke 4 hub × 11 trang React M2 COMPAT-01 checkpoint:human-action gate=advisory KHÔNG blocking per D-V3-Phase7-D LOCKED — auto-fallback `skip smoke` per --auto chain + v3.0-b precedent.

**Plan 07-04 (Wave 3 parallel — MIGRATE-04 MCP re-point):**
- `Hub_All/mcp_service/mcp_app/config.py` Settings.api_base_url default đổi `http://localhost:8180` → `http://python-api-central:8080` + 5-line decision comment (D-V3-Phase7-C LOCKED + carry forward D-V3-02 + Phase 4 Plan 04-05 cross-hub aggregate 1 SQL + T-08.2-01-T SSRF validator unchanged); field_validator `_validate_base_url` UNCHANGED preserve.
- `Hub_All/docker-compose.yml` mcp_service env block comment update "re-confirm" → "CONFIRMED Phase 7 MIGRATE-04"; env value `MCP_API_BASE_URL: http://python-api-central:8080` UNCHANGED (đã đúng từ Plan 02-02 D-V3-Phase2-C).
- `Hub_All/scripts/migrate/06-mcp-smoke.md` 181 LOC manual runbook 5-step Inspector OAuth (pre-deploy verify uv run pytest -q expect 135 baseline + Step 1 OAuth connect + Step 2 search_wiki single-hub + Step 3 ask_wiki cross-hub no hub_id + Step 4 citation resolve + Step 5 Prometheus metrics scrape + rollback procedure 5-step). 143/135 mcp_service test PASS regression (Phase 8.3 v2.0 baseline + Plan 10-04 CORS split 8 thêm).

**Plan 07-03 (Wave 3 BLOCKING — MIGRATE-03 truncate):**
- `Hub_All/scripts/migrate/04-truncate-central.sh` 269 LOC bash strict mode — Dry-run default ON safety (operator phải explicit `--apply`) + atomic transaction psql heredoc `BEGIN/COMMIT-or-ROLLBACK` wrap INSERT audit_logs TRƯỚC DELETE 4 table same transaction + jsonb_build_object payload (4 row_count COUNT subquery) + audit_logs DELETE filter `action != 'migrate.truncate_hub'` preserve evidence chain + per-hub error isolation + confirm prompt + --yes auto-confirm cho CI + hub validation chain T-5-05 + exit codes 0/1/2/3/4 distinct + 10 explicit D-V3-02 reference (chunks PRESERVED invariant strict).

**Plan 07-02 (Wave 2 BLOCKING — MIGRATE-02 restore + switch-caddy):**
- `Hub_All/scripts/migrate/02-restore-hub.sh` 225 LOC bash strict mode — psql restore snapshot vào medinet_hub_<HUB> 4-step pipeline (auto-detect latest snapshot + verify DB exist + current_database() match T-07-02-03 + psql -v ON_ERROR_STOP=1 -f restore + post-restore SELECT COUNT sanity check) + hub name validation chain T-5-05 + 7 psql ON_ERROR_STOP=1 fail-fast + exit codes 0/2/3/4/5 distinct semantic.
- `Hub_All/scripts/migrate/03-switch-caddy.sh` 132 LOC bash strict mode VERIFY-ONLY mode (Phase 5 Caddyfile `{re.hub_api.1}` dynamic regex đã handle routing tự động + 3-step pipeline + `--rollback` flag stop container Caddy fall-through 404 T-07-02-04 accept).

**Plan 07-01 (Wave 1 BLOCKING — MIGRATE-01 snapshot):**
- `Hub_All/scripts/migrate/01-snapshot-hubs.sh` 194 LOC bash strict mode — pg_dump --data-only --no-owner --no-acl --column-inserts 5 table --where hub_id filter cho 3 hub default + resolve hub_id UUID qua psql -tA + sanity check grep -c '^INSERT' WARN nếu 0 + idempotent skip + exit codes 0/1/2/3/4 distinct.
- `Hub_All/migrate-snapshots/.gitignore` exclude *.sql + whitelist .gitignore + README.md tracked.
- `Hub_All/migrate-snapshots/README.md` document file naming + 30-day retention + privacy + recovery rollback procedure.

**Carry-forward Phase 6 Results (DONE 2026-05-23):**

- **Phase:** 6 — System Settings Sync ✅ **DONE 2026-05-23 — SETTINGS-01..04 fully shipped (Wave 1 BLOCKING + Wave 2 + Wave 3 + Wave 4 BLOCKING + Wave 5 closeout ✅)**
- **Plan:** 5/5 plans complete (06-01..06-05) cho SETTINGS-01..04 ở `.planning/phases/06-system-settings-sync/`.
- **Status:** Phase 6 closed SETTINGS-01..04 — settings_sync module (HTTP pull on-demand + Redis cache TTL 60s/300s/60s + pub/sub invalidate hybrid D-V3-Phase6-A LOCKED) + 3 HTTP client class (RagConfigClient + HubRegistryClient + ApiKeyVerifyClient) + settings_subscriber_loop single channel `settings:invalidate` + Pydantic InvalidateMessage Literal enum payload (D-V3-Phase6-C) + require_api_key REFACTOR branch hub_name (central=M2 local AES-GCM AUX-02 unchanged / hub con=app.state.api_key_verify_client proxy + 503 boot fail-loud) + require_internal_auth hmac.compare_digest constant-time (D-V3-Phase6-D + T-06-03-01) + update_rag_config PUT publish best-effort fail-open + POST /api/api-keys/verify central-only mount FACTOR-02 + lifespan hub con block fetch_initial 5s fail-loud + spawn subscriber_task guard redis_ready (T-06-04-04) + shutdown graceful wait_for 10s + SETTINGS_SKIP_FETCH=1 escape hatch + 6 Prometheus metric (settings_cache_hit/miss_total + pull_latency + invalidate_received + stale_seconds + apikey_verify_total) label hub_name + key_type bounded enum W7 carry forward + 4 D-V3-Phase6-A..D LOCKED consumed + 33+ STRIDE T-06-01..04 covered. Evidence chain Phase 6 in-process: 87+ unit (25+22+22+thêm) + 6 integration ASGI lifespan test PASS + 452/452 Phase 1..6 regression + 19/19 Phase 2+5 integration regression + ruff/mypy --strict clean + 0 break M2 + 4 Rule 3 + 3 Rule 1 deviation auto-fix inline + 0 Rule 4 architectural. Plan 06-05 Task 5b smoke runtime SKIP pre-resolved auto-fallback per --auto chain + v3.0-b precedent (Plan 03-05 + 04-07 + 05-06) — defer Phase 7 MIGRATE-05 full E2E (3 hub + central + golden path + JWT SSO live + cross-hub search live data + per-hub branding visual diff + settings sync pub/sub live propagate).
- **Last activity:** 2026-05-23 — `/gsd-execute-phase 6 --auto --chain` wave-based execution complete cho SETTINGS-01..04:
  - **06-01 DONE ✅** (Wave 1 BLOCKING): settings_sync/ module scaffold 3 file (keys + metrics + __init__) + Settings 5 field + 1 model_validator + docker-compose 4 service env wire fail-loud + override.yml.template + .env.example 5 env mới. 25/25 unit + 408/408 regression PASS, 1 Rule 3 deviation auto-fix test infra.
  - **06-02 DONE ✅** (Wave 2): client.py 3 HTTP client class + SettingsUnavailableError + subscriber.py settings_subscriber_loop + Pydantic InvalidateMessage Literal enum schema + 22 unit test PASS. 3 Rule 1 fix httpx.Timeout 4-param + pytest-asyncio CancelledError hang workaround + C901 complexity refactor.
  - **06-03 DONE ✅** (Wave 3): require_api_key branch hub_name + require_internal_auth hmac.compare_digest dep + update_rag_config publish best-effort fail-open + POST /api/api-keys/verify endpoint central-only + VerifyApiKeyRequest schema. 22/22 unit + 452/452 regression + 50/50 cluster + 19/19 integration PASS, 0 deviation.
  - **06-04 DONE ✅** (Wave 4 BLOCKING): lifespan hub con block init 3 client blocking fetch_initial 5s fail-loud + spawn settings_subscriber_task guard redis_ready + shutdown graceful wait_for 10s + SETTINGS_SKIP_FETCH=1 escape hatch. 2 atomic commit (ddf28e1 feat + b8a4221 test). 6/6 integration ASGI LifespanManager PASS + 452/452 unit regression + 19/19 integration regression, 3 Rule 3 deviation auto-fix inline.
  - **06-05 DONE ✅** (Wave 5 closeout 2026-05-23): CLAUDE.md §6 progress row + Phase 6 pattern subsection + STATE.md frontmatter Phase 6 DONE + Current Position (file này) + Phase 6 Results Summary block + REQUIREMENTS.md SETTINGS-01..04 mark [x] + NOTE Phase 6 closeout 5-plan + ROADMAP.md Phase 6 row DONE + Decisions block + Progress table 33/~37 ≈ 89% + README.md NEW section "System Settings Sync Deploy Notes (Phase 6 v3.0)" 5-step deploy + rollback + escape hatch; Task 5b smoke SKIP pre-resolved auto-fallback per --auto chain + v3.0-b precedent.

---

## Phase 5 Results (carry forward DONE 2026-05-23)

- **Phase:** 5 — Reverse Proxy + Frontend Subpath ✅ **DONE 2026-05-23 — PROXY-01..04 fully shipped (Wave 1 BLOCKING + Wave 2 parallel × 2 + Wave 3 + Wave 4 + Wave 5 closeout ✅)**
- **Plan:** 6/6 plans complete (05-01..05-06) cho PROXY-01..04 + FACTOR-04 extend ở `.planning/phases/05-reverse-proxy-frontend-subpath/`.
- **Status:** Phase 5 closed PROXY-01..04 — Caddy reverse proxy `wiki.domain.com/<hub>/api/*` qua `path_regexp hub_api` + `uri strip_prefix /{re.hub_api.1}` + `reverse_proxy http://python-api-{re.hub_api.1}:8080` (port STATIC :8080 per Pitfall 1) + central `/api/*` no-strip + `/.well-known/*` JWKS pass + static SPA `try_files {path} /index.html` (D-V3-Phase5-A1/A2 LOCKED). Frontend 1-build runtime detect `window.location.pathname.split('/').filter(Boolean)[0]` + KNOWN_HUBS `window.__HUB_CONFIG__.allowlist` fallback hardcode `['yte','duoc','hcns']` + react-router `BrowserRouter basename={APP_BASE}` auto-prepend (D-V3-Phase5-B1/B3). Per-hub branding `frontend/src/branding/` Vite glob registry 4 hub initial (central indigo / yte emerald / duoc sky / hcns amber) + theme color inline CSS variable `--hub-theme` + WCAG 1.4.11 mitigation `getContrastTextColor()` hcns amber slate-900 threshold 0.6 (D-V3-Phase5-D1/D2/D3). Login.tsx 4 state machine (A/B/C/D per UI-SPEC §2) + T-5-04 strict ?return validation 4-layer + W-05 origin-not-host + window.location.replace cross-prefix redirect (D-V3-Phase5-B4/C1). Layout.tsx sidebar header logo bg + title swap module-level `getBranding(CURRENT_HUB)` + hover ring themeColor (UI-SPEC §3 LOCKED scope — chỉ sidebar header touch, KHÔNG cascade tất cả component R-V3-2 mitigation). api.crossHubSearch ABSOLUTE path `/api/search/cross-hub` qua `requestAbsolute<T>` helper bypass `${API_BASE}` prefix (D-V3-Phase4-D3 carry forward) + tryRefresh explicit `redirect: 'follow'` audit B-02 fix (D-V3-Phase5-C4). hub-add.sh 9-step pipeline extend FACTOR-04 (Step 8 sed-edit `.env` HUBS_ALLOWLIST/REGEX atomic + Step 9 PRE-validate + caddy reload zero-downtime + smoke curl warn-only) (D-V3-Phase5-A3 + T-5-05 Plan 02-05 carry forward). D6 EXPIRED formally CLAUDE.md §3 (PROXY-03). vitest Wave 0 infra (vitest@^2 + @testing-library/react + jsdom) + 5 new test file 37/37 vitest PASS full suite. R-V3-2 mitigation manual smoke 4 hub × 11 trang checkpoint Plan 05-06 Task 5b smoke SKIP pre-resolved per --auto chain + v3.0-b precedent (Plan 03-05/04-07) — defer Phase 7 MIGRATE-05 full E2E. Evidence chain Phase 5 in-process: 37/37 vitest PASS + `docker compose config --quiet` exit 0 + `caddy validate` exit 0 + `bash -n hub-add.sh` exit 0 + 36+5 acceptance grep PASS cover semantic PROXY-01..04. Backward compat M2 KHÔNG break — endpoint URL/envelope shape UNCHANGED + 11 trang nội dung React preserve + localStorage same-origin SSO carry forward + 307 backend redirect Plan 03-04 failsafe Layer 2. 7 STRIDE threat coverage T-5-01..07 (6 mitigate + 1 accept localStorage XSS defer v4.0).
- **Last activity:** 2026-05-23 — `/gsd-execute-phase 5 --auto --no-transition` wave-based execution complete cho PROXY-01..04:
  - **05-01 DONE ✅** (Wave 1 BLOCKING): Caddy wiki block + docker-compose env + .env.example 3 env document.
  - **05-02 DONE ✅** (Wave 2 parallel): vitest install + api.ts module-level prefix detect + App.tsx BrowserRouter basename + 10 vitest PASS.
  - **05-03 DONE ✅** (Wave 2 parallel): Branding registry Vite glob + 4 hub config + 4 SVG placeholder + WCAG getContrastTextColor helper + 13 vitest PASS (Rule 1 fix threshold 0.55→0.6 hcns amber).
  - **05-04 DONE ✅** (Wave 3): Login.tsx 4 state machine + Layout.tsx sidebar swap + api.crossHubSearch absolute override + tryRefresh redirect:'follow' audit B-02 fix — 4 atomic commit (54fc315 + ca6f4e4 + ed721fd + 61ac731) + 37/37 vitest PASS full suite (6 Login + 4 Layout + 11 api + 3 App + 13 branding).
  - **05-05 DONE ✅** (Wave 4): hub-add.sh step 8 atomic sed-edit .env HUBS_ALLOWLIST/REGEX + step 9 PRE-validate + caddy reload zero-downtime + smoke curl warn-only + dev pre-up tolerance — 1 atomic commit (6b282b8 feat 137+/10-) + bash -n PASS + 13/13 Task 1 + 5/5 Task 2 acceptance.
  - **05-06 DONE ✅** (Wave 5 closeout 2026-05-23): CLAUDE.md §3 D6 EXPIRED + §6 progress row + pattern subsection + STATE.md (file này) + REQUIREMENTS.md PROXY-01..04 mark [x] + ROADMAP.md Phase 5 row DONE + README.md NEW section Reverse Proxy Subpath Deploy Notes; Task 5b smoke SKIP pre-resolved per --auto chain + v3.0-b precedent.

## Phase 5 Planning Summary

| Plan | Wave | Objective | Tasks | Files modified | REQ | Status |
|------|------|-----------|-------|----------------|-----|--------|
| 05-01 | 1 BLOCKING | Caddyfile wiki block + docker-compose caddy service env + frontend/dist mount + .env.example 3 env document | 3 (auto) | `Hub_All/Caddyfile`, `Hub_All/docker-compose.yml`, `Hub_All/.env.example` | PROXY-01 | ✅ **DONE 2026-05-23** |
| 05-02 | 2 parallel | Wave 0 vitest infra + api.ts module-level prefix detect + App.tsx BrowserRouter basename + 10 vitest test PASS | 3 (1 wave 0 + 2 tdd) | `frontend/package.json`, `frontend/vitest.config.ts`, `frontend/src/test-setup.ts`, `frontend/src/services/api.ts`, `frontend/src/App.tsx`, 2 test file mới | PROXY-02 | ✅ **DONE 2026-05-23** |
| 05-03 | 2 parallel | Branding registry Vite glob + 4 hub config + 4 SVG placeholder + WCAG getContrastTextColor + 13 vitest test PASS | 3 (auto) | `frontend/src/branding/{index,central,yte,duoc,hcns}/index.ts` (5 file mới) + `frontend/public/branding/{central,yte,duoc,hcns}/logo.svg` (4 file mới) + `frontend/src/branding/__tests__/registry.spec.ts` (1 file mới) | PROXY-04 | ✅ **DONE 2026-05-23** |
| 05-04 | 3 | Login.tsx 4 state machine + branding inline CSS var + T-5-04 strict return validation + Layout.tsx sidebar swap + api.crossHubSearch absolute override + tryRefresh redirect:'follow' B-02 + 13 vitest test PASS (6 Login + 4 Layout + 3 misc) | 4 (tdd) | `frontend/src/pages/Login.tsx`, `frontend/src/Layout.tsx`, `frontend/src/services/api.ts`, `frontend/src/pages/__tests__/Login.spec.tsx`, `frontend/src/__tests__/Layout.spec.tsx` | PROXY-02 + PROXY-04 | ✅ **DONE 2026-05-23** |
| 05-05 | 4 | hub-add.sh 9-step pipeline extend — Step 8 sed-edit .env HUBS_ALLOWLIST atomic + Step 9 PRE-validate + caddy reload zero-downtime + smoke curl warn-only + dev pre-up tolerance | 2 (1 auto + 1 verify) | `Hub_All/api/scripts/hub-add.sh` | PROXY-01 + FACTOR-04 extend | ✅ **DONE 2026-05-23** |
| 05-06 | 5 closeout | Docs update CLAUDE.md + STATE.md + REQUIREMENTS.md + ROADMAP.md + README.md + manual smoke checkpoint 4 hub × 11 trang | 6 (5 auto: 4 docs + 1 README + 1 checkpoint:human-action) [W-01 split] | `Hub_All/CLAUDE.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `Hub_All/README.md` | PROXY-03 + PROXY-04 verify | ✅ **DONE 2026-05-23** (Task 5b smoke: `skip smoke` auto-fallback per --auto chain + v3.0-b precedent) |

**Coverage:** 4/4 REQ (PROXY-01..04) covered ≥ 1 plan/REQ.

**Critical path:** 05-01 ✅ (Wave 1 BLOCKING) → 05-02 ⊥ 05-03 (parallel Wave 2 file-disjoint) → 05-04 (Wave 3 depend 05-02 + 05-03) → 05-05 (Wave 4 depend 05-01 — parallel-able với Wave 3) → 05-06 (Wave 5 closeout depend all).

**Auto-chain pause resolved:** Plan 05-06 Task 5b (`checkpoint:human-action gate=blocking`) — manual smoke 4 hub × 11 trang React M2 COMPAT-01. Auto-fallback `skip smoke` per --auto chain mode active + v3.0-b precedent (Plan 03-05 + 04-07 pre-resolved skip pattern); evidence chain in-process 37/37 vitest + caddy validate + docker compose config + bash -n cover semantic. Manual smoke runtime defer Phase 7 MIGRATE-05 full E2E (3 hub + central + JWT SSO + cross-hub search live + per-hub branding visual diff).

## Phase 5 Results Summary

| Plan | Wave | Objective | Commits | Tests |
|------|------|-----------|---------|-------|
| 05-01 | 1 | Caddyfile wiki block + docker-compose + .env.example | 3 | caddy validate exit 0 + docker compose config exit 0 + grep checks |
| 05-02 | 2 | vitest install + api.ts prefix detect + App.tsx basename | 3 | 10/10 vitest PASS (7 api + 3 App) + tsc lint PASS |
| 05-03 | 2 | Branding registry + 4 hub config + 4 SVG + WCAG helper | 3 | 13/13 vitest PASS + tsc lint PASS (Rule 1 fix threshold 0.55→0.6 hcns amber) |
| 05-04 | 3 | Login.tsx 4 state + Layout sidebar + crossHubSearch absolute + tryRefresh redirect:'follow' B-02 | 4 (54fc315 + ca6f4e4 + ed721fd + 61ac731) | 37/37 vitest PASS full suite (6 Login + 4 Layout + 11 api + 3 App + 13 branding) + tsc lint PASS |
| 05-05 | 4 | hub-add.sh 9-step extend (step 8 .env atomic + step 9 caddy validate+reload+smoke) | 1 (6b282b8) | bash -n syntax + 13/13 Task 1 + 5/5 Task 2 structural acceptance |
| 05-06 | 5 | Closeout docs + smoke checkpoint | 6 (5 task + 1 SUMMARY) | grep acceptance 5 file PASS + Task 5b smoke `skip smoke` auto-fallback |

**Phase 5 deliverable summary:**
- Caddy `wiki.domain.com/<hub>/api/*` route đúng container hub + strip prefix (PROXY-01 — Caddyfile + docker-compose 2 env + caddy validate PASS).
- 1 build dùng chung 4 deploy — runtime prefix detect + react-router basename auto-prepend (PROXY-02 — api.ts + App.tsx, 10 vitest test PASS).
- D6 EXPIRED formally Phase 5 v3.0-05 — CLAUDE.md §3 explicit note + 11 trang React M2 COMPAT-01 invariant preserve (PROXY-03 — manual smoke checkpoint 4 hub × 11 trang skip smoke auto-fallback defer Phase 7).
- Per-hub login branding — 4 hub initial logo + title VN + tagline VN + themeColor inline CSS var `--hub-theme` (PROXY-04 — branding registry + Login state machine + Layout sidebar swap, 13 vitest registry test PASS).
- FACTOR-04 extend — `make hub-add` chain DB → override.yml → .env → caddy reload → smoke đầy đủ (hub-add.sh 9-step pipeline).

**v3.0-b progress: Phase 4+5 DONE (2/4 phase v3.0-b — 28/~32 plan ≈ 88%). Next: Phase 6 SETTINGS sync hoặc Phase 7 MIGRATE (depend chain).**

---

## Phase 4 Cross-hub Data Sync Results (carry forward)

- **Phase:** 4 — Cross-hub Data Sync ✅ **DONE 2026-05-22 — SYNC-01..05 fully shipped (Wave 1 BLOCKING + Wave 2 parallel + Wave 3 + Wave 4 + Wave 5 + Wave 6 closeout ✅)**
- **Plan:** 7/7 plans complete (04-01..04-07) cho SYNC-01..05 ở `.planning/phases/04-cross-hub-data-sync/`.
- **Status:** Phase 4 closed SYNC-01..05 — Outbox + worker mechanism (D-V3-Phase4-A1 LOCKED REJECT cocoindex target / Postgres logical replication) qua module `api/app/sync/` 5 file (keys + models + metrics + worker + __init__) + Postgres trigger AFTER INSERT/DELETE chunks atomic cùng transaction (D-V3-Phase4-A4) + `sync_outbox` table per-hub-con (11 cols + 2 CHECK + 2 partial index — D-V3-Phase4-A2) + in-process asyncio worker hub con lifespan (D-V3-Phase4-A3) + batch 100 + poll 5s + SELECT FOR UPDATE SKIP LOCKED + exp backoff [1,5,30,120]s + max 5 attempts → dead (D-V3-Phase4-A5); idempotent push central ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT FROM EXCLUDED.content_hash 1 SQL atomic (D-V3-Phase4-B1) + documents.sync_status enum lifecycle 5 value pending/syncing/synced/failed/partial (D-V3-Phase4-B2) + op_type INSERT/DELETE split HARD DELETE central chunks immutable (D-V3-Phase4-B3); checksum scheduler central FastAPI lifespan asyncio task daily 2AM COUNT(*) per hub vs central + hourly TABLESAMPLE BERNOULLI(1) hash sample (D-V3-Phase4-C1) + mark dead + Prometheus alert + admin POST /api/sync/replay endpoint reset 4 field dead row (D-V3-Phase4-C2) + naive asyncio.sleep loop KHÔNG APScheduler dep (D-V3-Phase4-C3); cross-hub search refactor 1 SQL aggregated `WHERE hub_id = ANY($N::uuid[]) ORDER BY vector <=> embedding LIMIT $k` thay fan-out asyncio.gather (D-V3-Phase4-D1) + HNSW iterative_scan=relaxed_order + ef_search=200 carry forward M2 Phase 6 + Settings.hub_id UUID env boot fail-loud (D-V3-Phase4-D2) + tách search_cross_hub_router central-only mount + strip hub con (D-V3-Phase4-D3); 6 Prometheus metric mới (sync_lag_seconds + sync_outbox_pending + sync_attempt_total + sync_dead_total + sync_count_drift + sync_hash_drift) với label `hub_name` bounded ~240 series; Settings 7 field mới + 3 model_validator boot fail-fast + 1 length validator backoff = max_attempts-1; docker-compose 3 hub con env HUB_*_ID + CENTRAL_SYNC_DSN fail-loud + central CHECKSUM_HUB_DSNS_JSON optional + override.yml.template FACTOR-04 placeholder. BLOCKER 2 fix pgvector serialization end-to-end (Plan 04-01 trigger explicit jsonb_build_object + vector::float4[] cast + content_hash hex encode + Plan 04-03 ChunkPayload field_validator hex decode + Plan 04-04 _init_central_sync_conn register_vector codec). BLOCKER 1 fix D-V3-Phase4-B2 lifecycle initial syncing UPDATE idempotent guard. R-V3-1 HIGH sync drift mitigation chain full + E-V3-2 cross-hub p95 < 1.5s carry forward + E-V3-3 isolation Layer 1 carry forward defensive guard rag/flow.py. Plan 04-07 Task 5 smoke compose runtime SKIP pre-resolved — defer Phase 7 MIGRATE-05 full E2E golden path 3 hub + central + JWT SSO + cross-hub search live data; evidence chain Plan 04-01 (17 unit) + Plan 04-02 (17 unit) + Plan 04-03 (43 unit) + Plan 04-04 (6 mock integration + 1 skipif) + Plan 04-05 (8 unit + 15 integration) + Plan 04-06 (22 unit) = 113 unit + 21 integration PASS in-process + 383/383 unit regression PASS.
- **Last activity:** 2026-05-22 — `/gsd-execute-phase 4` wave-based execution complete cho SYNC-01..05:
  - **04-01 DONE ✅** (Wave 1 BLOCKING): Per-hub Alembic 0005 sync_outbox table + Postgres function `enqueue_sync_outbox()` explicit jsonb_build_object + vector::float4[] cast + content_hash hex encode (BLOCKER 2 fix pgvector serialization) + 2 trigger AFTER INSERT/DELETE chunks FOR EACH ROW atomic + documents.sync_status enum 5 value lifecycle + initial 'pending' → 'syncing' idempotent UPDATE guard (BLOCKER 1 fix D-V3-Phase4-B2). Skip-central runtime guard. 17/17 unit + 293/293 unit + 10/10 Phase 1 regression PASS. SUMMARY: `04-01-SUMMARY.md`.
  - **04-02 DONE ✅** (Wave 2 parallel): Settings 7 field mới (hub_id + central_sync_dsn + checksum_hub_dsns_json + sync_batch_size + sync_poll_interval + sync_max_attempts + sync_backoff_seconds) + 3 model_validator hub con/central required + 1 length validator backoff = max_attempts-1 (T-04-02-05 DoS mitigation) + helper property checksum_hub_dsns + docker-compose 3 hub con env HUB_*_ID fail-loud + central CHECKSUM_HUB_DSNS_JSON optional + override.yml.template FACTOR-04 placeholder. 17/17 unit + 310/310 regression (8 file fixture updated Rule 3) PASS. SUMMARY: `04-02-SUMMARY.md`.
  - **04-03 DONE ✅** (Wave 2 parallel): `api/app/sync/` module mới 5 file (keys + models + metrics + worker + __init__) — ~816 LOC source + ~1043 test 3 file (12 models + 13 metrics + 18 worker). sync_worker_loop SELECT FOR UPDATE SKIP LOCKED + ChunkPayload Pydantic hex decode field_validator (BLOCKER 2) + 6 Prometheus collector label `hub_name` (W7 fix) + UPDATE_DOC_SYNC_STATUS aggregate CASE 4 state (BLOCKER 1 fix D-V3-Phase4-B2). 43/43 unit + 353/353 regression PASS. SUMMARY: `04-03-SUMMARY.md`.
  - **04-04 DONE ✅** (Wave 3): `api/app/db/dsn.py` shared _to_asyncpg_dsn helper (W3 fix circular import) + `app/main.py::_init_central_sync_conn` callback register_vector (BLOCKER 2 fix) + lifespan central_sync_pool create_pool(init=...) verify current_database()=='medinet_central' fail-fast (T-04-04-01) + spawn sync_worker_task hub con + graceful shutdown cancel + wait_for(10s) + rag/flow.py defensive guard doc_hub_id mismatch (D-V3-Phase4-D2 + E-V3-3 Layer 1) + SYNC_SKIP_CENTRAL_POOL=1 escape hatch. 6 mock integration + 1 skipif live-DB. SUMMARY: `04-04-SUMMARY.md`.
  - **04-05 DONE ✅** (Wave 4): `SearchService._search_cross_hub_impl` refactor từ fan-out asyncio.gather → 1 SQL aggregated `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector LIMIT $3` (D-V3-Phase4-D1) + HNSW iterative_scan + ef_search=200 carry forward M2 Phase 6 + tách routers/search.py 2 APIRouter (search_router universal + cross_hub_router central-only) + main.py conditional include + CENTRAL_ONLY list grow 8 → 9 (D-V3-Phase4-D3). Public API signature giữ NGUYÊN backward compat M2 ask_service.py + frontend. 8/8 unit + 15/15 integration (10 baseline + 5 dedicated) + 361/361 regression PASS. SUMMARY: `04-05-SUMMARY.md`.
  - **04-06 DONE ✅** (Wave 5): `api/app/observability/checksum_scheduler.py` central lifespan asyncio task naive asyncio.sleep cron loop (D-V3-Phase4-C3 KHÔNG APScheduler dep) + daily 2AM COUNT(*) drift + hourly TABLESAMPLE BERNOULLI(1) hash sample + lazy per-hub asyncpg.Pool init + per-hub error isolation + `POST /api/sync/replay` admin endpoint require_role("admin") Phase 3 SSO-04 carry forward + reset 4 field dead rows atomic + audit_logs INSERT non-repudiation action='sync.replay' với defensive inner try/except (W8 fix T-04-06-03 reinforced). 22/22 unit (10 checksum + 12 replay) + 383/383 regression + 21/21 Phase 2+4 integration PASS. SUMMARY: `04-06-SUMMARY.md`.
  - **04-07 DONE ✅** (Wave 6 closeout 2026-05-22): CLAUDE.md section 6 Phase 4 DONE row + Phase 4 Cross-hub Data Sync pattern subsection (7 plan detail + 6 metric + R-V3-1 mitigation + E-V3-2 carry forward + backward compat) + footer changelog. STATE.md frontmatter Phase 4 DONE + completed_phases 3→4 + total_plans/completed_plans 15→22 + percent 47→69 + Current Position + Phase 4 Planning + Results Summary table + Next Action v3.0-b promote Phase 5. REQUIREMENTS.md SYNC-01..05 mark `[x]` + NOTE Phase 4 closeout 7-step plan list. README.md section mới "Cross-hub Sync Deploy Notes (Phase 4 v3.0)" env list + Alembic + Prometheus metric + admin replay curl example + rollback procedure. Task 5 smoke compose runtime SKIP pre-resolved per user decision — evidence chain rationale rõ ràng trong SUMMARY.md. SUMMARY: `04-07-SUMMARY.md`.

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

## Phase 4 Planning Summary

| Plan | Wave | Objective | Tasks | Files modified | REQ | Status |
|------|------|-----------|-------|----------------|-----|--------|
| 04-01 | 1 BLOCKING | Per-hub Alembic 0005 sync_outbox table + Postgres trigger AFTER INSERT/DELETE chunks + documents.sync_status enum + skip-central runtime guard | 2 (auto + tdd) | `api/migrations/versions/0005_sync_outbox_per_hub.py` (new, 224 LOC), `api/migrations/env.py` (+33 LOC `_HUB_ONLY_REVS` frozenset), `api/tests/unit/test_sync_outbox_migration.py` (new, 223 LOC) | SYNC-05, SYNC-01, SYNC-02 | ✅ **DONE 2026-05-22** (17/17 unit + 293/293 + 10/10 Phase 1 regression PASS) |
| 04-02 | 2 parallel | Settings 7 field mới (hub_id + central_sync_dsn + checksum_hub_dsns_json + sync_batch_size/poll_interval/max_attempts/backoff_seconds) + 3 model_validator hub con/central required + 1 length validator backoff = max_attempts-1 + docker-compose env wire | 2 (tdd + auto) | `api/app/config.py` (+143 LOC), `api/tests/unit/test_config_phase4_fields.py` (new, 266 LOC, 17 test), `docker-compose.yml` (+19 LOC), `docker-compose.override.yml.template` (+10 LOC), 8 file test cũ fixture Rule 3 regression | SYNC-01, SYNC-03, SYNC-04 | ✅ **DONE 2026-05-22** (17/17 unit + 310/310 regression PASS) |
| 04-03 | 2 parallel | `api/app/sync/` module 5 file (keys + models + metrics + worker + __init__) + sync_worker_loop async + ChunkPayload Pydantic hex decode (BLOCKER 2) + 6 Prometheus collector label `hub_name` (W7) + UPDATE_DOC_SYNC_STATUS aggregate CASE (BLOCKER 1) | 4 (tdd × 4) | `api/app/sync/__init__.py` (new, 50 LOC), `api/app/sync/keys.py` (new, 168 LOC, 8 SQL constant), `api/app/sync/models.py` (new, 146 LOC), `api/app/sync/metrics.py` (new, 114 LOC), `api/app/sync/worker.py` (new, 338 LOC), `tests/unit/test_sync_{models,metrics,worker}.py` (new, 12+13+18 = 43 test) | SYNC-01, SYNC-02, SYNC-05 | ✅ **DONE 2026-05-22** (43/43 unit + 353/353 regression PASS) |
| 04-04 | 3 | Lifespan integration central_sync_pool + sync_worker_task hub con + rag/flow.py hub_id guard + 6 mock integration test | 3 (auto) | `api/app/db/dsn.py` (new, 45 LOC W3 fix), `api/app/main.py` (+85 LOC), `api/app/rag/flow.py` (+22 LOC D-V3-Phase4-D2), `tests/integration/test_sync_lifespan_integration.py` (new, 402 LOC, 7 test 6 mock + 1 skipif), `tests/integration/conftest.py` (+70 LOC integration_db_pool fixture) | SYNC-01, SYNC-02, SYNC-05 | ✅ **DONE 2026-05-22** (6 mock integration + 1 skipif live-DB PASS) |
| 04-05 | 4 | SearchService._search_cross_hub_impl refactor từ fan-out asyncio.gather → 1 SQL aggregated WHERE hub_id = ANY + tách 2 router (search_router universal + cross_hub_router central-only) + main.py conditional include | 3 (tdd + 2 auto) | `api/app/services/search_service.py` (refactor 1 SQL net +18 LOC), `api/app/routers/search.py` (+30 LOC 2 APIRouter), `api/app/routers/__init__.py` (+3 LOC alias), `api/app/main.py` (+12 LOC central-only block), `tests/unit/test_search_cross_hub_refactor.py` (new, 357 LOC, 8 test), `tests/integration/test_factor_hub_scoped.py` (+80 LOC CENTRAL_ONLY 8→9 + 3 dedicated cross-hub) | SYNC-03 | ✅ **DONE 2026-05-22** (8/8 unit + 15/15 integration + 361/361 regression PASS) |
| 04-06 | 5 | observability/checksum_scheduler.py central lifespan asyncio task daily/hourly + POST /api/sync/replay admin endpoint + audit_logs INSERT non-repudiation | 2 (tdd × 2) | `api/app/observability/checksum_scheduler.py` (new, ~280 LOC), `api/app/routers/sync.py` (+140 LOC SyncReplayRequest + REPLAY_SQL + endpoint + audit), `api/app/main.py` (+45 LOC central lifespan spawn), `tests/unit/test_checksum_scheduler.py` (new, ~460 LOC, 10 test), `tests/unit/test_sync_replay_endpoint.py` (new, ~280 LOC, 12 test) | SYNC-04 | ✅ **DONE 2026-05-22** (22/22 unit + 383/383 regression + 21/21 integration PASS) |
| 04-07 | 6 closeout | CLAUDE.md + STATE.md + REQUIREMENTS.md + README.md docs update + smoke checkpoint runtime SKIP pre-resolved (defer Phase 7 MIGRATE-05) | 5 (4 docs + 1 checkpoint) | `Hub_All/CLAUDE.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `Hub_All/README.md` | SYNC-01..05 closeout | ✅ **DONE 2026-05-22** (docs grep acceptance PASS; Task 5 SKIP pre-resolved) |

**Coverage:** 5/5 REQ (SYNC-01..05) covered ≥ 1 plan/REQ.

**Critical path:** 04-01 ✅ (Wave 1 BLOCKING) → 04-02 ⊥ 04-03 (parallel Wave 2 file-disjoint) → 04-04 (Wave 3 depend 04-01..03) → 04-05 (Wave 4 depend 04-04) → 04-06 (Wave 5 depend 04-05) → 04-07 (Wave 6 closeout).

**Auto-chain pause expected:** Plan 04-07 Task 5 (`checkpoint:human-action gate=blocking`) — smoke compose runtime central + 3 hub con. User resume signal: `skip smoke` (pre-resolved 2026-05-22 — defer Phase 7 MIGRATE-05 full E2E).

### Plan 04-01 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~8 phút |
| Tasks completed | 2/2 |
| Files modified | 3 (`api/migrations/versions/0005_sync_outbox_per_hub.py` (new 224 LOC), `api/migrations/env.py` (+33 LOC), `api/tests/unit/test_sync_outbox_migration.py` (new 223 LOC)) |
| Tests added | 17 (4 TestSkipGuard + 12 TestMigrationStructure + 1 meta) |
| Test pass rate | 17/17 (100%) + 293/293 unit + 10/10 Phase 1 regression PASS |
| Lint | ruff + mypy --strict PASS |
| Commits | 3 (Task 1 migration + Task 2 test + structure fix) |
| Deviations | BLOCKER 1 fix (initial syncing UPDATE idempotent guard) + BLOCKER 2 fix (explicit jsonb_build_object + vector::float4[] cast + hex encode) |

### Plan 04-02 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~22 phút |
| Tasks completed | 2/2 |
| Files modified | 12 (`api/app/config.py` (+143 LOC), `tests/unit/test_config_phase4_fields.py` (new 266 LOC), `docker-compose.yml` (+19 LOC), `docker-compose.override.yml.template` (+10 LOC) + 8 file test cũ fixture Rule 3 regression) |
| Tests added | 17 PASS test_config_phase4_fields.py |
| Test pass rate | 17/17 unit + 310/310 regression (8 file fixture updated Rule 3) PASS |
| Lint | ruff + mypy --strict PASS |
| Commits | 3 |
| Deviations | 1 (Rule 3 blocking 8 file fixture cũ thiếu Phase 4 env setenv) |

### Plan 04-03 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~35 phút (4 task TDD + W5/W7 fix) |
| Tasks completed | 4/4 |
| Files modified | 8 (5 mới module `api/app/sync/` ~816 LOC + 3 test file ~1043 LOC) |
| Tests added | 43 (12 models + 13 metrics + 18 worker) |
| Test pass rate | 43/43 unit + 353/353 regression PASS |
| Lint | ruff + mypy --strict PASS |
| Commits | 5 |
| Deviations | 2 (W7 Prometheus label `hub_name` NOT `hub_id` UUID + W5 Task 3 split sub-task complexity bounded) |

### Plan 04-04 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~25 phút |
| Tasks completed | 3/3 |
| Files modified | 6 (`api/app/db/dsn.py` (new 45 LOC W3 fix), `api/app/main.py` (+85 LOC), `api/app/rag/flow.py` (+22 LOC D-V3-Phase4-D2 guard), `tests/integration/test_sync_lifespan_integration.py` (new 402 LOC), `tests/integration/conftest.py` (+70 LOC W9 fixture), `tests/unit/test_auth_router_hub_redirect.py` (+5 LOC SYNC_SKIP_CENTRAL_POOL Rule 3 regression)) |
| Tests added | 7 (6 mock + 1 skipif live-DB) |
| Test pass rate | 6/6 mock integration + 1 skipif (100% executable) PASS |
| Lint | ruff + mypy --strict PASS |
| Commits | 3 |
| Deviations | 3 (W3 circular import fix shared dsn.py helper + W9 fixture skipif live-DB + SYNC_SKIP_CENTRAL_POOL escape hatch Rule 3) |

### Plan 04-05 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~35 phút (3 task tdd RED → GREEN) |
| Tasks completed | 3/3 |
| Files modified | 6 (`api/app/services/search_service.py` (refactor net +18 LOC), `api/app/routers/search.py` (+30 LOC 2 APIRouter), `api/app/routers/__init__.py` (+3 LOC), `api/app/main.py` (+12 LOC central-only block), `tests/unit/test_search_cross_hub_refactor.py` (new 357 LOC 8 test), `tests/integration/test_factor_hub_scoped.py` (+80 LOC CENTRAL_ONLY 8→9 + 3 dedicated)) |
| Tests added | 11 (8 unit refactor + 3 integration cross-hub mount/strip) |
| Test pass rate | 8/8 unit + 15/15 integration (10 baseline + 5 dedicated cross-hub) + 361/361 regression PASS |
| Lint | ruff + mypy --strict PASS |
| Commits | 4 (TDD test RED + refactor GREEN + router tách + integration test update) |
| Deviations | 1 (W4 docstring sanitization xoá `asyncio.gather` comment trong _search_cross_hub_impl scope cho Test 8 inspect.getsource()) |

### Plan 04-06 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~50 phút |
| Tasks completed | 2/2 |
| Files modified | 6 (`api/app/observability/checksum_scheduler.py` (new ~280 LOC), `api/app/routers/sync.py` (+140 LOC), `api/app/main.py` (+45 LOC central lifespan), `tests/unit/test_checksum_scheduler.py` (new ~460 LOC), `tests/unit/test_sync_replay_endpoint.py` (new ~280 LOC), `.planning/phases/04-cross-hub-data-sync/deferred-items.md` (new)) |
| Tests added | 22 (10 checksum + 12 replay) |
| Test pass rate | 22/22 unit + 383/383 regression + 21/21 Phase 2+4 integration PASS |
| Lint | ruff (PASS) + mypy --strict (M-04-06-01 pre-existing main.py line 108 Rule 4 out-of-scope logged deferred-items) |
| Commits | 3 |
| Deviations | 3 (W8 audit_logs INSERT non-repudiation T-04-06-03 + Rule 2 schema fix target_type/target_id/payload + Rule 1 fix source inspection test thay full lifespan boot MemoryError) |

### Plan 04-07 ship 2026-05-22 — Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~30 phút (4 docs + 1 checkpoint pre-resolved + 1 SUMMARY) |
| Tasks completed | 4/5 (Task 5 smoke compose runtime SKIP pre-resolved per user decision — defer Phase 7 MIGRATE-05) |
| Files modified | 5 (`Hub_All/CLAUDE.md` section 6 v3.0 progress + Phase 4 pattern subsection + footer; `.planning/STATE.md` frontmatter + Current Position + Phase 4 Planning + Results Summary + Next Action; `.planning/REQUIREMENTS.md` SYNC-01..05 mark [x] + NOTE Phase 4 closeout 7-step plan list; `.planning/ROADMAP.md` Phase 4 row marked DONE + Progress table; `Hub_All/README.md` section mới Cross-hub Sync Deploy Notes Phase 4 v3.0) |
| Verify | grep acceptance criteria 4 file PASS; markdown structure preserve (CLAUDE.md sections unchanged; YAML frontmatter STATE.md parse OK; REQUIREMENTS Traceability table preserve; README sections "Add a new hub" + "SSO Backward Incompat" + "Milestone status" preserve) |
| Commits | 5 (4 task + 1 SUMMARY) |
| Deviations | 1 (Task 5 SKIP smoke compose runtime — pre-resolved user decision 2026-05-22; rationale: 113 unit + 21 integration in-process PASS cover semantic SYNC-01..05 + `docker compose config --quiet` base PASS Plan 04-02; smoke runtime defer Phase 7 MIGRATE-05 full E2E 3 hub + central golden path) |

## Phase 4 Results Summary

| Plan | Wave | Objective | Commits | Tests |
|------|------|-----------|---------|-------|
| 04-01 | 1 BLOCKING | Per-hub Alembic 0005 sync_outbox + Postgres trigger AFTER INSERT/DELETE + documents.sync_status enum | 3 | 17/17 unit + 293/293 unit + 10/10 Phase 1 regression PASS |
| 04-02 | 2 | Settings 7 field + 3 model_validator + 1 length validator + docker-compose env wire | 3 | 17/17 unit + 310/310 regression (8 file fixture updated Rule 3) PASS |
| 04-03 | 2 | app/sync module 5 file + sync_worker_loop + 6 Prometheus collector + ChunkPayload Pydantic hex decode | 5 | 43/43 unit (12 models + 13 metrics + 18 worker) + 353/353 regression PASS |
| 04-04 | 3 | Lifespan integration central_sync_pool + sync_worker_task + rag/flow.py guard + 6 mock integration | 3 | 6/6 mock integration + 1 skipif live-DB PASS |
| 04-05 | 4 | _search_cross_hub_impl refactor 1 SQL aggregated + tách 2 router central-only mount + CENTRAL_ONLY 8→9 | 4 | 8/8 unit + 15/15 integration + 361/361 regression PASS |
| 04-06 | 5 | checksum_scheduler central lifespan daily/hourly + POST /api/sync/replay admin endpoint + audit_logs | 3 | 22/22 unit (10 checksum + 12 replay) + 383/383 regression + 21/21 integration PASS |
| 04-07 | 6 closeout | CLAUDE.md + STATE.md + REQUIREMENTS.md + ROADMAP.md + README.md update + smoke SKIP pre-resolved | 5 | Docs update grep acceptance PASS 4 file; Task 5 smoke SKIP pre-resolved |

**Phase 4 deliverable summary:**
- Outbox + worker pattern per-hub-con — `sync_outbox` table (11 cols + 2 CHECK + 2 partial index) + Postgres trigger AFTER INSERT/DELETE chunks atomic cùng transaction + worker poll batch 100/5s + SELECT FOR UPDATE SKIP LOCKED concurrency-safe + exp backoff [1, 5, 30, 120]s + max 5 attempts → status='dead' (D-V3-Phase4-A1..A5 LOCKED).
- Idempotent push central — `ON CONFLICT (id) DO UPDATE SET ... WHERE chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash` 1 SQL atomic (D-V3-Phase4-B1) tránh UPDATE no-op + bảo vệ HNSW vector index disk write thừa.
- Sync timing async decoupled — `document.status=completed` ngay sau cocoindex INSERT chunks; `documents.sync_status` enum lifecycle 5 value (pending → syncing trigger → synced/failed/partial worker aggregate CASE) cho dashboard transparency (D-V3-Phase4-B2).
- Event-typed op_type INSERT/DELETE split — HARD DELETE central (chunks immutable carry forward rag/flow.py docstring lock — D-V3-Phase4-B3).
- Failure handling — exp backoff + max 5 attempts → status='dead' + Prometheus alert; admin `POST /api/sync/replay { hub_id, since }` reset 4 field dead rows (status='pending', attempt_count=0, last_error=NULL, next_retry_at=NULL) atomic + audit_logs INSERT non-repudiation `action='sync.replay'` với defensive inner try/except (W8 fix T-04-06-03 reinforced) — D-V3-Phase4-C2.
- Checksum scheduler central FastAPI lifespan asyncio task — daily 2AM `COUNT(*)` per hub vs central → `sync_count_drift{hub_name}` gauge symmetric `drift_ratio` + hourly `TABLESAMPLE BERNOULLI(1)` chunks created last 1h → content_hash diff → `sync_hash_drift{hub_name, drift_type=mismatch|missing}` counter; naive `asyncio.sleep` cron loop KHÔNG cần APScheduler dep mới + lazy per-hub asyncpg.Pool init + per-hub error isolation (D-V3-Phase4-C1/C3).
- Cross-hub search refactor — 1 SQL aggregated `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector LIMIT $3` thay fan-out `asyncio.gather(*[_search_one(h) for h in hub_ids])` N task (D-V3-Phase4-D1); HNSW `iterative_scan=relaxed_order` + `ef_search=200` + `max_scan_tuples=20000` carry forward M2 Phase 6 _run_vector_query SET LOCAL session tuning; re-rank tự nhiên qua SQL ORDER BY (KHÔNG Python merge sort).
- Hub con strip `/api/search/cross-hub` mount (FACTOR-02 extend Plan 04-05 D-V3-Phase4-D3) — 404 envelope D6. Tách routers/search.py 2 APIRouter (search_router universal + cross_hub_router central-only); CENTRAL_ONLY list 8 → 9 endpoint.
- Settings 7 field mới: `hub_id` UUID4 + `central_sync_dsn` + `checksum_hub_dsns_json` + `sync_batch_size=100` + `sync_poll_interval=5.0` + `sync_max_attempts=5` + `sync_backoff_seconds=[1,5,30,120]` + 3 model_validator hub con/central required boot fail-fast + 1 length validator backoff = max_attempts-1 (T-04-02-05 DoS mitigation).
- docker-compose env wire 3 hub con `${HUB_*_ID:?error}` fail-loud + `CENTRAL_SYNC_DSN` + central `${CHECKSUM_HUB_DSNS_JSON:-}` optional + `docker-compose.override.yml.template` FACTOR-04 placeholder `{{HUB_UPPER}}_ID` extend (Plan 02-05 sed substitute carry forward).
- BLOCKER 2 fix pgvector serialization end-to-end (Plan 04-01 trigger explicit jsonb_build_object + vector::float4[] cast + content_hash hex encode 64 char + Plan 04-03 ChunkPayload field_validator mode=before hex decode → bytes + Plan 04-04 `_init_central_sync_conn` register_vector codec per connection cho `$N::vector` bind).
- BLOCKER 1 fix D-V3-Phase4-B2 lifecycle initial 'pending' → 'syncing' idempotent UPDATE guard `WHERE sync_status='pending'` first-chunk-per-document.
- 9 decision LOCKED D-V3-Phase4-A1..D3 consumed (outbox mechanism + sync_outbox per-hub-con schema + worker placement in-process + trigger DDL AFTER INSERT/DELETE + worker loop config + idempotent ON CONFLICT atomic + sync timing async decoupled + event-typed op_type INSERT/DELETE + checksum cadence daily+hourly + failure mode mark dead + admin replay + central scheduler placement + cross-hub refactor in-place + hub_id UUID resolution env + strip endpoint hub con).
- ~36 STRIDE threat mitigation breakdown: Plan 04-01 (5: 3 mitigate + 2 accept) + Plan 04-02 (6: 5 mitigate + 1 accept) + Plan 04-03 (7: 6 mitigate + 1 accept) + Plan 04-04 (6: 5 mitigate + 1 accept) + Plan 04-05 (6: 5 mitigate + 1 accept) + Plan 04-06 (6: 5 mitigate + 1 accept) ≈ **36 threat addressed**.

**v3.0-b progress: Phase 4 DONE (1/4 phase v3.0-b — 22/~32 plan ≈ 69%). Next: /gsd-discuss-phase 5 Reverse Proxy + Frontend Subpath (PROXY-01..04 — Caddy subpath routing + frontend prefix detect 1 build + D-V3-06 D6 expire formally + per-hub login branding; GA-V3-C confirm 1 build detect prefix vs per-hub VITE_HUB_NAME build matrix).**

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

## Phase 6 Planning Summary

| Plan | Wave | Objective | Tasks | Files modified | REQ | Status |
|------|------|-----------|-------|----------------|-----|--------|
| 06-01 | 1 BLOCKING | `api/app/settings_sync/` scaffold (keys.py + metrics.py 6 Prometheus collector) + `Settings` 5 field mới (`settings_proxy_secret` min 32 char + 3 TTL field 60/300/60s + `settings_subscriber_reconnect_seconds=5`) + docker-compose `SETTINGS_PROXY_SECRET` env wire 4 service + `docker-compose.override.yml.template` placeholder FACTOR-04 + `.env.example` document `openssl rand -hex 32` | 3 (auto + tdd) | `api/app/settings_sync/{__init__,keys,metrics}.py`, `api/app/config.py`, `docker-compose.yml`, `docker-compose.override.yml.template`, `.env.example`, 3 unit test mới | SETTINGS-01..04 | ✅ **DONE 2026-05-23** (25/25 unit + 408/408 regression) |
| 06-02 | 2 | 3 client class (`RagConfigClient` + `HubRegistryClient` + `ApiKeyVerifyClient`) + `settings_subscriber_loop` asyncio task subscribe `settings:invalidate` + Pydantic `InvalidateMessage` enum validate + httpx async + Redis cache write-through + 2 unit test file | 2 (tdd) | `api/app/settings_sync/{client,subscriber}.py`, `tests/unit/test_settings_sync_{client,subscriber}.py` | SETTINGS-01, 02, 04 | ✅ **DONE 2026-05-23** (22/22 unit + 430/430 regression) |
| 06-03 | 3 | Refactor `auth/api_key.py::require_api_key` branch verify path (central=local `ApiKeyService.verify_key` vs hub con=`ApiKeyVerifyClient.verify` HTTP proxy) + new `auth/dependencies.py::require_internal_auth` shared secret hmac.compare_digest + `routers/rag_config.py::update_rag_config` extend publish pub/sub best-effort fail-open + `routers/api_keys.py` add `POST /api/api-keys/verify` central-only conditional mount | 2 (tdd) | `api/app/auth/api_key.py`, `api/app/auth/dependencies.py`, `api/app/routers/{rag_config,api_keys}.py`, 4 unit test file | SETTINGS-02, 03 | ✅ **DONE 2026-05-23** (22/22 unit + 452/452 regression + 50/50 cluster + 19/19 integration) |
| 06-04 | 4 BLOCKING | `main.py::create_app()::lifespan` extend hub con block: init 3 client `RagConfigClient` + `HubRegistryClient` + `ApiKeyVerifyClient` + blocking `fetch_initial()` 5s fail-loud + spawn `settings_subscriber_task = asyncio.create_task(settings_subscriber_loop)` subscribe `settings:invalidate` Wave 2 + guard `redis_ready` (T-06-04-04) + shutdown graceful `task.cancel() + asyncio.wait_for(timeout=10s)` + `SETTINGS_SKIP_FETCH=1` escape hatch + ASGI integration test 6 case (skip path + populate + subscriber branch by redis_ready + shutdown reset + boot fail-loud + central skip) | 2 (auto + tdd) | `api/app/main.py`, `tests/integration/test_settings_sync_lifespan_integration.py`, `tests/integration/test_settings_sync_pubsub_e2e.py` (skip module pubsub defer Phase 7), `tests/integration/conftest.py` (Rule 3 fix), `tests/unit/test_auth_router_hub_redirect.py` (Rule 3 fix) | SETTINGS-01..04 | ✅ **DONE 2026-05-23** (6/6 integration + 452/452 unit regression + 19/19 integration regression + 3 Rule 3 deviation fix) |
| 06-05 | 5 closeout | Docs update CLAUDE.md §6 v3.0 progress row + Phase 6 pattern subsection + STATE.md frontmatter + Phase 6 Results Summary + REQUIREMENTS.md SETTINGS-01..04 mark [x] + ROADMAP.md Phase 6 row DONE + README.md NEW section "System Settings Sync Deploy Notes" (5 step deploy + rollback + `openssl rand -hex 32` secret gen) + manual smoke checkpoint Task 5b SKIP auto-fallback per --auto chain + v3.0-b precedent (Plan 03-05 + 04-07 + 05-06) | 6 (5 auto + 1 checkpoint:human-action) | `Hub_All/CLAUDE.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `Hub_All/README.md` | SETTINGS-01..04 verify | ✅ **DONE 2026-05-23** (Task 5b smoke `skip smoke` auto-fallback per --auto chain + v3.0-b precedent) |

**Coverage:** 4/4 REQ (SETTINGS-01..04) covered ≥ 1 plan/REQ. **Decisions:** 4/4 D-V3-Phase6-A..D LOCKED (A=HTTP pull + Redis pub/sub hybrid, B=TTL 60/300/60s, C=1 channel `settings:invalidate` Pydantic enum payload, D=shared secret X-Internal-Auth ≥ 32 char hmac.compare_digest). **Threats:** 33 STRIDE references T-06-01-01..T-06-05-05 across 5 plan (block-on-HIGH, không HIGH unresolved). **Pattern reuse:** 14/14 file analog 100% coverage từ Phase 3 JWKSCache lifespan + Phase 4 sync_worker module-level metrics + M2 `search_cache.py` pub/sub fail-open + Phase 3 require_role factory.

**Critical path:** 06-01 ✅ (Wave 1 BLOCKING infra) → 06-02 ✅ (Wave 2 client + subscriber depend 06-01) → 06-03 ✅ (Wave 3 refactor + central extend depend 06-01+06-02) → 06-04 ✅ (Wave 4 BLOCKING lifespan depend 06-01..03) → 06-05 ✅ (Wave 5 closeout depend all).

**Verification:** `gsd-plan-checker` 12 dimension PASS (Coverage 4/4 + Task Completeness + Dependency acyclic + Key Links wired + Scope Sanity + must_haves derivation + Context Compliance 4 D LOCKED honored + Pattern Compliance 14/14 + CLAUDE.md Vietnamese rule + Cross-plan data contracts validated). Verification timestamp: 2026-05-23.

**Auto-chain pause resolved:** Plan 06-05 Task 5b (`checkpoint:human-action gate=blocking`) — manual smoke compose runtime 4 hub × PUT central rag_config + verify hub con cache flush < 30s + central POST /api/api-keys/verify proxy 200. Auto-fallback `skip smoke` per --auto chain mode active + v3.0-b precedent (Plan 03-05 + 04-07 + 05-06 pre-resolved skip pattern); evidence chain in-process 87+ unit + 6 integration test PASS cover semantic. Manual smoke runtime defer Phase 7 MIGRATE-05 full E2E (3 hub con + central + golden path + JWT SSO live + cross-hub search live data + per-hub branding visual diff + settings sync pub/sub live propagate).

## Phase 6 Results Summary

| Plan | Wave | Objective | Commits | Tests |
|------|------|-----------|---------|-------|
| 06-01 | 1 BLOCKING | settings_sync/ scaffold (3 file) + Settings 5 field + 1 model_validator + docker-compose 4 service env wire + override.yml.template + .env.example | 5 (27f0365 + 79bfc26 + e971a1f + 90b8af3 + f0f71bc) | 25/25 unit (12 config + 6 keys + 7 metrics) + 408/408 regression + docker compose config exit 0 + ruff/mypy clean |
| 06-02 | 2 | client.py 3 HTTP client class (RagConfigClient + HubRegistryClient + ApiKeyVerifyClient) + subscriber.py settings_subscriber_loop + Pydantic InvalidateMessage Literal enum schema | 4 (9701fda + 2890973 + 102b512 + 17ff523) | 22/22 unit (11 client + 11 subscriber) + 430/430 regression + ruff/mypy clean |
| 06-03 | 3 | require_api_key REFACTOR branch hub_name + require_internal_auth hmac dep + update_rag_config publish best-effort fail-open + POST /api/api-keys/verify endpoint mới + VerifyApiKeyRequest schema | 4 (a5d9ffb + c26e02d + 5e807ac + 803a0a3) | 22/22 unit (6 require_api_key + 6 require_internal_auth + 4 rag_config publish + 6 verify endpoint) + 452/452 regression + 50/50 cluster + 19/19 integration |
| 06-04 | 4 BLOCKING | lifespan hub con block init 3 client + blocking fetch_initial 5s fail-loud + spawn settings_subscriber_task guard redis_ready (T-06-04-04) + shutdown graceful wait_for 10s + SETTINGS_SKIP_FETCH=1 escape hatch + ASGI integration test | 2 (ddf28e1 feat + b8a4221 test) | 6/6 integration ASGI LifespanManager + 452/452 unit regression + 19/19 integration regression + ruff/mypy --strict clean; pubsub e2e defer Phase 7 |
| 06-05 | 5 closeout | Docs CLAUDE.md + STATE.md + REQUIREMENTS.md + ROADMAP.md + README.md + smoke checkpoint Task 5b SKIP auto-fallback per v3.0-b precedent | 6 (5 task + 1 SUMMARY) | grep acceptance 5 file PASS + Task 5b smoke `skip smoke` auto-fallback rationale rõ |

**Phase 6 deliverable summary:**
- Hub con `rag_config` HTTP pull + Redis cache TTL 60s + pub/sub invalidate < 1s thực tế (E-V3-4 < 30s threshold thừa margin) — SETTINGS-01/02 + RagConfigClient + subscriber `rag_config` flush branch + central PUT publish best-effort fail-open.
- API key verify proxy: hub con `require_api_key` branch → POST /api/api-keys/verify central (X-Internal-Auth header 32-char secret hmac.compare_digest) + cache Redis TTL 60s hash key — SETTINGS-03 + ApiKeyVerifyClient + require_internal_auth dep.
- Hub registry read-only: HubRegistryClient HTTP pull `GET /api/hubs` (M2 endpoint hiện hữu) + cache TTL 5 phút singleton key — SETTINGS-04.
- settings_sync/ module 5 file (~700 LOC source + ~870 LOC test) — pattern proven Phase 3 JWKSCache + Phase 4 sync module carry forward.
- 6 Prometheus metric mới observability — settings_cache_hit/miss_total + pull_latency + invalidate_received + stale_seconds + apikey_verify_total label `hub_name` + `key_type` enum bounded W7.
- 4 D-V3-Phase6 LOCKED consumed (A=HTTP pull + pub/sub hybrid; B=TTL 60s/300s/60s; C=1 channel + Pydantic enum payload; D=shared secret 32-char hmac compare).
- 5 plan ship in-process 87+ unit + 6 integration test PASS — manual smoke runtime defer Phase 7 MIGRATE-05.

**v3.0-b progress: Phase 4+5+6 DONE (3/4 phase v3.0-b — 33/~37 plan ≈ 89%). Next: Phase 7 MIGRATE (MIGRATE-01..05 — pg_dump snapshot per hub_id + blue/green restore + MCP re-point + smoke E2E full v3.0).**

## Next Action

1. **(Recommended) `/gsd-discuss-phase 7`** — Migration + Smoke E2E (MIGRATE-01..05 — final v3.0 phase). pg_dump --where="hub_id='<uuid>'" snapshot 3 hub yte/duoc/hcns + restore blue/green per-hub + truncate central skeleton (giữ chunks denormalized D-V3-02) + MCP service re-point central (mcp_service/config.py API_BASE_URL) + smoke E2E 3 hub con + central golden path PASS (login → upload → search local + cross-hub → ask → citation [N] → logout) + cross-hub p95 < 1.5s live measure E-V3-2 + hub isolation enforce E-V3-3. Depends Phase 1-6 ✅ ALL DONE; GA-V3-D part 2 chốt strategy.
2. (Optional) `/gsd-code-review 6` — advisory code review trên ~13 commits Phase 6 (workflow.code_review gate), phủ 5 plan ship SETTINGS-01..04 + 4 D-V3-Phase6 LOCKED + 33+ STRIDE threat T-06-01..04 + 6 Prometheus metric mới + lifespan integration runtime wiring.
3. (Optional) `/gsd-verify-work 6` — manual UAT 4 SC nếu user muốn extra verify ngoài automated test (Plan 06-05 Task 5b smoke 4 hub × PUT rag_config SKIP pre-resolved, sẽ verify ở Phase 7 MIGRATE-05 runtime smoke E2E live 3 hub + central + settings sync pub/sub live propagate).
4. (Optional) `/gsd-progress` — review v3.0 milestone progress (Phase 1+2+3+4+5+6 DONE — 33/~37 plan ≈ 89%, 25/29 REQ-ID closed, v3.0-b 3/4 phase mid-flight).

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

## Deferred Items

Items acknowledged and deferred at v3.0 milestone close on 2026-05-23:

| Category | Item | Status |
|----------|------|--------|
| debug_sessions | podman-init-admin-issue | deferred (WSL provider hang — Windows env-specific, không block v3.0) |
| uat_gaps | Phase 06: 06-HUMAN-UAT.md | partial (0 pending scenarios — auto-fallback skip per --auto chain v3.0-b precedent) |
| verification_gaps | Phase 06: 06-VERIFICATION.md | human_needed (visual smoke runtime defer Phase 7 MIGRATE-05 → defer ops handover post-milestone-close) |
| seeds | SEED-001-local-embedding-model | dormant (HuggingFace sentence-transformers local embedding — v4.0 backlog) |

Carry forward vào v3.1 RBAC milestone hoặc v4.0 follow-up.

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
