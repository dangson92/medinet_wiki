---
phase: 07
plan: 04
subsystem: mcp-service
tags: [mcp-repoint, oauth, inspector, runbook, regression-test, wave-3-parallel, migrate-04, d-v3-phase7-c]
status: done
date_completed: 2026-05-23
duration_minutes: 3

requires:
  - Plan 07-02 ship (Wave 2 — 02-restore-hub.sh + 03-switch-caddy.sh — blue/green per-hub procedure pre-condition)
  - Phase 2 FACTOR-02 ship (docker-compose mcp_service env MCP_API_BASE_URL=http://python-api-central:8080 đã set đúng từ Plan 02-02 D-V3-Phase2-C; Phase 7 chỉ update comment "re-confirm" → "CONFIRMED Phase 7 MIGRATE-04")
  - Phase 8.3 v2.0 ship (mcp_service OAuth flow 9 plan + 135 unit test baseline + AUX-02 AES-GCM api_key_service unchanged carry forward)
  - Phase 4 Plan 04-05 ship (SearchService._search_cross_hub_impl 1 SQL aggregated WHERE hub_id = ANY($N::uuid[]) — cross-hub aggregate qua medinet_central.chunks D-V3-02 LOCKED)
  - D-V3-Phase7-C LOCKED 2026-05-23 — MCP re-point central aggregate (KHÔNG fan-out N hub)

provides:
  - "Hub_All/mcp_service/mcp_app/config.py — Settings.api_base_url default re-point http://python-api-central:8080 (D-V3-Phase7-C LOCKED)"
  - "Hub_All/docker-compose.yml — mcp_service env block comment update CONFIRMED Phase 7 MIGRATE-04 + carry forward Phase 4 Plan 04-05 cross-hub aggregate note"
  - "Hub_All/scripts/migrate/06-mcp-smoke.md — 181 LOC manual runbook 5-step Inspector OAuth smoke + pre-deploy regression mandatory + rollback procedure"
  - "MIGRATE-04 acceptance satisfied — mcp_service re-point central + 143/135 test PASS regression baseline (Phase 8.3 v2.0 + Plan 10-04 CORS 8 thêm) + smoke Inspector OAuth runbook ready"
  - "Foundation cho Plan 07-05 closeout — 05-smoke-e2e.sh có thể reference 06-mcp-smoke.md cho MCP tool call verification post full E2E"

affects:
  - "Plan 07-05 (closeout 05-smoke-e2e.sh + docs) — MCP smoke verify chain bổ sung cho golden path 7-step v3.0 milestone closeout"
  - "Operator deploy team — chạy 06-mcp-smoke.md sau khi docker compose up -d mcp_service post-restore (Plan 07-02 + 07-03 chain done); pre-deploy uv run pytest -q 135/143 passed mandatory"
  - "Claude Inspector OAuth integration — operator manual verify wiki.medinet.vn/mcp/auth/v2/authorize flow stable post Phase 7 deploy"
  - "MCP service runtime — restart sau env update (1 line config.py default + docker-compose comment) để api_base_url default reflect central re-point"

tech-stack:
  added: []  # KHÔNG dep mới — chỉ string value đổi + markdown runbook
  patterns:
    - "1-line config default re-point + 5-line decision comment (carry forward Phase 2 FACTOR-04 pattern docker-compose env wire stable)"
    - "Validator unchanged preserve pattern — _validate_base_url scheme http/https + host required (T-08.2-01-T SSRF mitigation Phase 8.3 v2.0 carry forward)"
    - "Manual runbook 5-step markdown structure (analog Phase 5 Plan 05-06 smoke checklist + Phase 8.3 v2.0 mcp_service smoke pattern)"
    - "Pre-deploy regression mandatory (uv run pytest -q expect 135 passed baseline) + rollback procedure 5-step (docker compose stop + git revert + rebuild + regression + Inspector re-verify)"
    - "Carry forward Phase 8.3 OAuth UNCHANGED — KHÔNG đụng api_key_service AES-GCM AUX-02"

key-files:
  created:
    - "Hub_All/scripts/migrate/06-mcp-smoke.md (181 LOC manual runbook 5-step Inspector OAuth + pre-deploy verify + rollback)"
    - ".planning/phases/07-migration-smoke-e2e/07-04-SUMMARY.md (file này — closeout SUMMARY)"

  modified:
    - "Hub_All/mcp_service/mcp_app/config.py (line 33-38 — Settings.api_base_url default đổi http://localhost:8180 → http://python-api-central:8080 + 5-line comment decision reference D-V3-Phase7-C + Phase 4 Plan 04-05 + T-08.2-01-T)"
    - "Hub_All/docker-compose.yml (line 264-268 — mcp_service env block comment update 're-confirm' → 'CONFIRMED Phase 7 MIGRATE-04' + carry forward Phase 4 Plan 04-05 note; env value MCP_API_BASE_URL không đổi đã đúng từ Phase 2)"

decisions:
  - "D-V3-Phase7-C LOCKED 2026-05-23 — MCP service re-point central aggregate qua python-api-central:8080 (KHÔNG fan-out N hub con). Carry forward D-V3-02 Phase 1 LOCKED (medinet_central.chunks aggregated cross-hub search target) + Phase 4 Plan 04-05 D-V3-Phase4-D1 LOCKED (cross-hub search 1 SQL aggregated WHERE hub_id = ANY($N::uuid[]))."
  - "MCP tools signature UNCHANGED (search_wiki + ask_wiki — hub_id optional). Omit hub_id = cross-hub aggregate (central LIMIT N WHERE hub_id IN user.hub_ids). Provide hub_id = single-hub forward (verify JWT user.hub_ids ∋ hub_id else 403). Phase 8.3 v2.0 contract carry forward."
  - "OAuth flow Phase 8.3 v2.0 UNCHANGED — mcp_service KHÔNG đụng api_key_service AES-GCM AUX-02 carry forward. wiki.medinet.vn/mcp/auth/v2/authorize endpoint (Caddy reverse proxy Phase 5 PROXY-01 route /mcp/* tới mcp_service:8190 unchanged)."
  - "field_validator _validate_base_url unchanged — chỉ thay default value (KHÔNG đụng validation logic SSRF T-08.2-01-T mitigation Phase 8.3 v2.0 carry forward). Scheme http/https enforce + host required."
  - "Env var name MCP_API_BASE_URL giữ NGUYÊN (carry forward Phase 2 D-V3-Phase2-C — operator chỉ override .env value, KHÔNG đụng config.py field name). Default value đổi đảm bảo dev native không có .env vẫn point đúng central."
  - "docker-compose.yml env value MCP_API_BASE_URL=http://python-api-central:8080 đã đúng từ Plan 02-02 D-V3-Phase2-C — Phase 7 CHỈ update comment 're-confirm' → 'CONFIRMED Phase 7 MIGRATE-04' (verify-only documentation refresh, KHÔNG đụng compose semantic)."

metrics:
  duration: "3 phút (Task 1 config.py + docker-compose 1 phút + Task 2 runbook 1 phút + verify regression 1 phút)"
  task_count: 2
  file_count: 3  # 2 modified (config.py + docker-compose.yml) + 1 created (06-mcp-smoke.md) + SUMMARY tự đếm riêng
  completed_date: 2026-05-23
  commits:
    - "f3934fe: feat(07-04) re-point MCP service tới python-api-central (config.py + docker-compose comment)"
    - "7fdac43: docs(07-04) thêm runbook MCP smoke 5-step Inspector OAuth (06-mcp-smoke.md 181 LOC)"
  test_results:
    - "uv run pytest -q (mcp_service/tests/): 143 passed in 3.67s (≥ 135 baseline Phase 8.3 v2.0 — 8 test thêm Plan 10-04 CORS split policy)"
  acceptance_grep_pass:
    task_1:
      - "grep -c 'api_base_url: str = \"http://python-api-central:8080\"' = 1 (default updated)"
      - "grep -c 'D-V3-Phase7-C' config.py = 1 (decision reference)"
      - "grep -c 'Phase 4 Plan 04-05' config.py = 1 (carry forward note)"
      - "grep -c '_validate_base_url' config.py = 2 (validator unchanged + comment)"
      - "grep -c 'api_base_url: str = \"http://localhost:8180\"' = 0 (old default REMOVED)"
      - "grep -c 'Phase 7 v3.0 MIGRATE-04' docker-compose.yml = 1"
      - "grep -c 'CONFIRMED contract' docker-compose.yml = 1"
      - "grep -c 'MCP_API_BASE_URL: http://python-api-central:8080' docker-compose.yml = 1 (env value unchanged)"
    task_2:
      - "test -f scripts/migrate/06-mcp-smoke.md = exit 0"
      - "Step 1-5 count = 6 (≥5)"
      - "Inspector mentions = 11 (≥3)"
      - "search_wiki = 2 (≥1)"
      - "ask_wiki = 2 (≥1)"
      - "135 passed = 2 (≥1)"
      - "D-V3-Phase7-C = 2 (≥1)"
      - "MCP_API_BASE_URL = 3 (≥1)"
      - "Rollback section = 1 (≥1)"
      - "Prometheus metrics (cross_hub_search_latency|apikey_verify_total|sync_lag_seconds) = 5 (≥2)"
      - "envelope D6 reference = 2 (≥1)"
      - "Total LOC = 181 (≥80 min_lines)"
---

# Phase 7 Plan 07-04: MCP Service Re-point + Inspector Runbook Summary

**One-liner:** Re-point `mcp_service` từ M2 monolith `localhost:8180` sang v3.0 central `python-api-central:8080` qua 1-line config.py default change + docker-compose comment confirm + 181 LOC manual runbook Inspector OAuth 5-step smoke; regression 143/135 PASS (Phase 8.3 v2.0 baseline + Plan 10-04 CORS split policy 8 test thêm).

## Objective

Wave 3 song song với Plan 07-03 (file-disjoint — 07-03 touch `scripts/migrate/04-truncate-central.sh` + `.planning/*`; 07-04 touch `mcp_service/*` + `docker-compose.yml` + `scripts/migrate/06-mcp-smoke.md`). MIGRATE-04 acceptance criteria — MCP tools `search_wiki(hub_id?)` + `ask_wiki(hub_id?)` GIỮ NGUYÊN signature (hub_id optional cho cross-hub), OAuth flow Phase 8.3 v2.0 carry forward UNCHANGED, 135/135 mcp_service/tests/ regression PASS mandatory pre-deploy.

## Deliverables

### Task 1: config.py default + docker-compose comment update (commit f3934fe)

**File 1 — `mcp_service/mcp_app/config.py` (line 33-38):**
- Default `api_base_url: str = "http://localhost:8180"` → `"http://python-api-central:8080"`.
- 5-line decision comment: `D-V3-02 LOCKED central aggregator` + `D-V3-Phase7-C LOCKED 2026-05-23` + `MCP tools search_wiki + ask_wiki forward central` + `cross-hub search 1 SQL aggregated Phase 4 Plan 04-05 D-V3-Phase4-D1` + `Validator _validate_base_url enforce scheme + host T-08.2-01-T SSRF mitigation carry forward Phase 8.3 v2.0`.
- field_validator `_validate_base_url` (lines 106-119) UNCHANGED — scheme http/https + host required (SSRF mitigation T-08.2-01-T Phase 8.3 v2.0).

**File 2 — `docker-compose.yml` (line 264-268):**
- Comment update `re-confirm contract` → `CONFIRMED contract` + thêm `Phase 7 v3.0 MIGRATE-04 (D-V3-Phase7-C LOCKED 2026-05-23)` reference + `Cross-hub search 1 SQL aggregated Phase 4 Plan 04-05 carry forward` note.
- Env value `MCP_API_BASE_URL: http://python-api-central:8080` UNCHANGED (đã đúng từ Plan 02-02 D-V3-Phase2-C).

### Task 2: 06-mcp-smoke.md runbook (commit 7fdac43)

**File mới — `scripts/migrate/06-mcp-smoke.md` (181 LOC):**

**Pre-deploy verify mandatory:**
- `cd Hub_All/mcp_service && uv run pytest -q` → expected 135 passed (Phase 8.3 v2.0 baseline; thực tế 143 passed vì 8 test thêm Plan 10-04 CORS split policy).
- `docker compose ps mcp_service` + `docker compose logs --tail=50` + `docker compose exec mcp_service env | grep MCP_API_BASE_URL`.

**5-step Inspector OAuth smoke:**

| Step | Action | Expected | FAIL signal |
|------|--------|----------|-------------|
| 1 | Claude Inspector OAuth connect `wiki.medinet.vn/mcp/auth/v2/authorize` | Discovery `/.well-known/oauth-authorization-server` 200 + token exchange + Connected state | Discovery 404 / token 401 / CORS reject → check Caddy `/.well-known/*` + `/mcp/*` route (Phase 5 PROXY-01) |
| 2 | `search_wiki(query="vaccin", hub_id="yte")` single-hub | Envelope D6 success + all chunks `hub_id="yte"` | 403 CROSS_HUB_ACCESS_DENIED → JWT thiếu `hub_ids=["yte"]` (Phase 3 Plan 03-03) |
| 3 | `ask_wiki(query="dược ngoại")` cross-hub no hub_id | citations từ MULTIPLE hub_id (intersection user.hub_ids ∩ all hubs) + p95 < 1.5s E-V3-2 | citations chỉ 1 hub → cross-hub aggregate fail (Phase 4 Plan 04-05 D-V3-Phase4-D1) / Empty → LLM provider down |
| 4 | Citation `[N]` resolve — `GET /api/documents/<id>` | Document title + hub_id match + chunk content highlight | 404 → chunk orphan sync drift R-V3-1 → `POST /api/sync/replay` (Phase 4 Plan 04-06) |
| 5 | Prometheus metrics scrape | `apikey_verify_total{result=cached} > 0` (SETTINGS-03) + `cross_hub_search_latency_seconds` histogram + `sync_lag_seconds < 30` (E-V3-4) + `sync_count_drift < 0.01` (R-V3-1) | sync_lag > 30s → worker stale (Phase 4 Plan 04-04) / count_drift > 1% → checksum scheduler alert |

**Rollback procedure:**
1. `docker compose stop mcp_service`
2. `git revert <commit-sha-phase7-mcp-repoint>` (f3934fe + 7fdac43)
3. `docker compose up -d --build mcp_service`
4. `cd mcp_service && uv run pytest -q` → expect 135/143 passed
5. Manual Inspector connect verify

**Reference links:** config.py + docker-compose lines + 07-CONTEXT.md D-V3-Phase7-C + 07-04-PLAN.md + Phase 8.3 v2.0 archive + Phase 4 Plan 04-05 LOCKED.

## Verification Results

### Regression test (Phase 8.3 v2.0 baseline mandatory)

```
$ cd Hub_All/mcp_service && uv run pytest -q
........................................................................ [ 50%]
.......................................................................  [100%]
143 passed in 3.67s
```

- **Expected:** 135 passed (Phase 8.3 v2.0 baseline)
- **Actual:** 143 passed (135 + 8 test thêm từ Plan 10-04 CORS split policy `test_cors_split_policy.py`)
- **Result:** PASS — 0 regression sau config.py default re-point

### Acceptance grep PASS (19/19 acceptance criteria PASS — strict invariant validated)

- **Task 1 (8/8):** Default updated + decision references + validator unchanged + old default removed + docker-compose comment updated + env value unchanged
- **Task 2 (11/11):** File exists + 5-step structure + Inspector + tool names + regression baseline + decision reference + env var + Rollback section + Prometheus metrics + envelope D6 + min_lines

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] uv runtime cho mcp_service tests**
- **Found during:** Task 1 verify regression
- **Issue:** `python -m pytest tests/` direct fail với `ModuleNotFoundError: No module named 'aiosqlite'` — global Python env không có deps mcp_service.
- **Fix:** Switch sang `uv run pytest -q` (đã có trong plan instruction `read_first` từ 07-04-PLAN.md `<interfaces>` section). uv tự resolve venv `mcp_service/.venv` + sync deps từ `pyproject.toml`.
- **Files modified:** Không — chỉ command runtime
- **Commit:** Không (verification step only)

### No other deviations

Plan executed exactly as written cho cả 2 task — 1-line default change + 5-line decision comment config.py + comment refresh docker-compose + 181 LOC runbook 5-step OAuth smoke. KHÔNG đụng validator logic, KHÔNG đụng env value docker-compose, KHÔNG đụng OAuth flow Phase 8.3 v2.0, KHÔNG đụng api_key_service AUX-02 AES-GCM.

## Threat Model Coverage

| Threat | Disposition | Mitigation |
|--------|-------------|------------|
| T-07-04-01 (Information Disclosure — api_base_url SSRF) | mitigate | field_validator `_validate_base_url` UNCHANGED — scheme http/https + host required (T-08.2-01-T Phase 8.3 v2.0 carry forward) |
| T-07-04-02 (Spoofing — Claude Inspector OAuth token forgery) | mitigate | Phase 8.3 OAuth 2.0 + JWT verify UNCHANGED + CRIT-01 CORS split metadata vs sensitive (Plan 10-04 v2.0 — `test_cors_split_policy.py` 8 test) |
| T-07-04-03 (Repudiation — MCP tool call audit) | accept | M2 audit_logs Phase 5 carry forward — MCP tool call qua central `/api/search` + `/api/ask` đã có audit_logs INSERT per request (AUX); KHÔNG cần thêm Phase 7 |
| T-07-04-04 (DoS — MCP fan-out N hub, rejected) | mitigate | D-V3-Phase7-C LOCKED — MCP gọi central aggregate 1 request per tool call. Cross-hub search 1 SQL aggregated Phase 4 Plan 04-05 D-V3-Phase4-D1 carry forward |

## Backward Compatibility (Phase 7 Plan 07-04 KHÔNG break M2 / Phase 8.3 / v3.0 Phase 1-6)

- **MCP tools signature LOCKED unchanged** — `search_wiki(hub_id?)` + `ask_wiki(hub_id?)` Phase 8.3 v2.0 contract carry forward.
- **OAuth flow Phase 8.3 v2.0 UNCHANGED** — `wiki.medinet.vn/mcp/auth/v2/authorize` Caddy `/mcp/*` route Phase 5 PROXY-01 unchanged.
- **field_validator `_validate_base_url` UNCHANGED** — SSRF mitigation T-08.2-01-T Phase 8.3 v2.0 carry forward.
- **Env var name MCP_API_BASE_URL UNCHANGED** — operator chỉ override `.env` value, KHÔNG đụng `config.py` field name (Phase 2 D-V3-Phase2-C contract carry forward).
- **docker-compose env value MCP_API_BASE_URL=http://python-api-central:8080 UNCHANGED** — đã đúng từ Plan 02-02 D-V3-Phase2-C, Phase 7 CHỈ update comment.
- **api_key_service AUX-02 AES-GCM at-rest LOCKED unchanged** — Phase 7 MCP re-point KHÔNG đụng (per CONTEXT.md scope limit + D-V3-Phase7-C invariant).
- **mcp_service/tests/ 135 baseline PASS** — actual 143 passed (135 + 8 Plan 10-04 CORS split policy thêm).

## Self-Check: PASSED

**Created files verified:**
- `c:\Users\dangs\OneDrive\Máy tính\Code\medinet_wiki\Hub_All\scripts\migrate\06-mcp-smoke.md` — EXISTS (181 LOC)
- `c:\Users\dangs\OneDrive\Máy tính\Code\medinet_wiki\Hub_All\.planning\phases\07-migration-smoke-e2e\07-04-SUMMARY.md` — EXISTS (file này)

**Modified files verified:**
- `c:\Users\dangs\OneDrive\Máy tính\Code\medinet_wiki\Hub_All\mcp_service\mcp_app\config.py` — line 33-38 default + decision comment
- `c:\Users\dangs\OneDrive\Máy tính\Code\medinet_wiki\Hub_All\docker-compose.yml` — line 264-268 comment update

**Commits verified in git log:**
- `f3934fe`: feat(07-04) re-point MCP service tới python-api-central
- `7fdac43`: docs(07-04) thêm runbook MCP smoke 5-step Inspector OAuth

## Foundation Status

- **Plan 07-05 closeout BLOCKING resolved** — MCP re-point ready cho 05-smoke-e2e.sh full golden path 3 hub × 7-step (MCP tool call có thể reference 06-mcp-smoke.md cho manual Inspector verify supplement).
- **MIGRATE-04 acceptance satisfied:**
  - mcp_service re-point central ✓
  - 135/135 (actual 143/143) test PASS regression ✓
  - Smoke Inspector OAuth runbook ready ✓
  - MCP tools signature unchanged ✓
  - OAuth flow Phase 8.3 v2.0 carry forward unchanged ✓
- **v3.0 Phase 7 progress:** 4/5 plan done (07-01 + 07-02 + 07-03 + 07-04). Next: Plan 07-05 closeout (Wave 4 — `05-smoke-e2e.sh` 3 hub × 7-step automated + docs CLAUDE.md + STATE.md + ROADMAP.md + REQUIREMENTS.md + README.md + milestone v3.0 close marker).

---

*Phase: 07-migration-smoke-e2e*
*Plan: 04 — MCP Service Re-point + Inspector Runbook*
*Completed: 2026-05-23 (3 phút)*
*Commits: f3934fe (feat config + compose) + 7fdac43 (docs runbook)*
*Test regression: 143 passed (Phase 8.3 v2.0 baseline 135 + Plan 10-04 CORS 8 thêm)*
*REQ-ID closed: MIGRATE-04*
*Next: Plan 07-05 closeout — 05-smoke-e2e.sh + docs + milestone v3.0 close*
