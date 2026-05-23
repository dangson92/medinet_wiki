---
phase: 7
phase_name: Migration + Smoke E2E
slug: migration-smoke-e2e
milestone: v3.0
gathered: 2026-05-23
source: planner-seed-defaults (Auto Mode `--auto`)
status: Ready for planning
---

# Phase 7: Migration + Smoke E2E — Context

**Gathered:** 2026-05-23
**Status:** Ready for planning
**Source:** Auto Mode `--auto` — gray area GA-V3-D part 2 + 3 sub-decision chốt theo recommended seed defaults (REQUIREMENTS.md MIGRATE-01..05 đã lock spec chi tiết). Đây là final phase v3.0 — closeout milestone v3.0-b (Phase 4-7) + resolve toàn bộ HUMAN-UAT pending từ Phase 3+4+5+6 (4 phase đã defer runtime smoke về Phase 7 MIGRATE-05).

> **Nguồn quyết định:**
> - REQUIREMENTS.md MIGRATE-01..05 spec chi tiết
> - ROADMAP.md Phase 7 success criteria + 4 gray area
> - Carry-forward decisions Phase 3+4+5+6 (sync mechanism outbox D-V3-Phase4-A1 LOCKED; cross-hub aggregate D-V3-02 LOCKED; Caddy subpath PROXY-01 + hub-add.sh 9-step Phase 5; lifespan fail-loud pattern Phase 3 JWKSCache + Phase 4 sync_worker + Phase 6 settings_sync)
> - HUMAN-UAT.md pending từ 4 phase trước (Phase 3 SSO smoke + Phase 4 SYNC live + Phase 5 PROXY 4 hub × 11 trang + Phase 6 SETTINGS pub/sub propagate) — batch-resolve Phase 7 MIGRATE-05
> - PROJECT.md (KHÔNG đụng v4.0 sub-hub split — defer v3.0 multi_hub_split seed user memory project_v3_multi_hub_split.md)

---

<domain>
## Phase Boundary

**WHAT phase 7 ships:**

1. **Per-hub data snapshot** — `pg_dump --data-only --table={chunks,documents,users,audit_logs,usage_events} --where="hub_id = '<uuid>'"` cho 3 hub (yte, duoc, hcns) từ `medinet_central` (v2.0 legacy DB). Output 3 file `migrate-<hub>-2026-05-23.sql` lưu `migrate-snapshots/` directory. Backup retention 30 ngày minimum (manual cleanup).

2. **Blue/green per-hub restore** — `psql -d medinet_hub_<name> -f migrate-<hub>.sql` restore snapshot vào DB hub con dedicated (Phase 1 TOPO-04 + Phase 2 FACTOR-04 đã prepare schema). Per-hub Alembic 0001..0005 đã upgrade ready (carry forward Phase 4). Run trên DB NEW trước switch traffic. Verify smoke per-hub (curl health + login + 1 search local) PASS → switch Caddy upstream `python-api-<hub>:8080` (Phase 5 PROXY-01 carry forward).

3. **Central skeleton truncate** — Sau khi 3 hub PASS smoke individual: batched `DELETE FROM medinet_central.{documents, users, audit_logs, usage_events} WHERE hub_id IN ('<yte_uuid>', '<duoc_uuid>', '<hcns_uuid>')`. **KHÔNG truncate `medinet_central.chunks`** (D-V3-02 LOCKED — vẫn nhận sync 1-way từ hub con cho cross-hub search per SYNC-01..03 Plan 04-01..05). Central giữ rows `hub_id IS NULL` (system-level admin + audit + settings change non-hub-scoped).

4. **MCP service re-point central** — `mcp_service/config.py` đổi `API_BASE_URL` env từ `http://api:8080` (v2.0 monolith central) sang `https://central/api` (v3.0 reverse proxy entry). MCP tools `search_wiki(hub_id?)` + `ask_wiki(hub_id?)` GIỮ NGUYÊN signature — `hub_id` optional cho cross-hub search (omit = all hubs JWT allows). OAuth flow Phase 8.3 v2.0 carry forward UNCHANGED (mcp_service 135/135 test PASS regression mandatory). Smoke OAuth via Claude Inspector PASS — token issue + tool call + scope check.

5. **Migration scripts module mới `scripts/migrate/`** — 5 file:
   - `01-snapshot-hubs.sh` — `pg_dump` 3 hub_id parameterized + output `migrate-snapshots/migrate-<hub>-<date>.sql`.
   - `02-restore-hub.sh <hub>` — `psql` restore single hub vào `medinet_hub_<name>` + verify row count sanity.
   - `03-switch-caddy.sh <hub>` — `sed` edit Caddyfile upstream `python-api-<hub>:8080` + `caddy validate` + `caddy reload` zero-downtime (Phase 5 hub-add.sh step 9 pattern carry forward).
   - `04-truncate-central.sh` — batched DELETE per hub_id + COUNT verify + dry-run flag `--dry-run` default ON cho safety.
   - `05-smoke-e2e.sh` — Bash automate golden path 3 hub × 7 step (login + upload DOCX + poll status + search local + cross-hub + ask + citation `[N]` + logout) qua `curl` + `jq` parse JSON envelope D6 + exit code 0 = PASS / 1 = FAIL specific step. Reuse Phase 8.3 v2.0 mcp_service smoke pattern.

6. **MCP smoke Inspector test** — `scripts/migrate/06-mcp-smoke.md` runbook 5-step manual: (1) start mcp_service container, (2) Claude Inspector connect via OAuth `wiki.domain.com/mcp/auth/v2/authorize`, (3) call `search_wiki(query="vaccin", hub_id="yte")`, (4) call `ask_wiki(query="dược ngoại")` cross-hub no hub_id, (5) verify citation `[N]` resolve. 135/135 mcp_service unit + 4/4 OAuth integration regression mandatory PASS pre-smoke.

7. **Closeout docs + milestone v3.0 close** — CLAUDE.md §6 progress row Phase 7 ✅ DONE 2026-05-23 + Phase 7 Migration + Smoke E2E pattern subsection (5-7 bullet point) + footer changelog. STATE.md frontmatter `phase_7_status` DONE + `completed_phases: 7` + `percent: 100` + Current Position + Phase 7 Results Summary table + v3.0 milestone CLOSED marker + Next Action `/gsd-complete-milestone v3.0`. REQUIREMENTS.md MIGRATE-01..05 mark `[x]` + NOTE closeout 5-plan list. ROADMAP.md Phase 7 row ✅ DONE + Progress table 38/38 plan 100% + v3.0 milestone celebration banner. README.md NEW section "Migration + Smoke E2E Runbook (Phase 7 v3.0)" gồm: 7-step deploy procedure + rollback per-hub procedure + retention 30 ngày policy + MCP re-point env wire example.

8. **HUMAN-UAT batch resolve** — Phase 3 + 4 + 5 + 6 (4 phase) đã defer runtime smoke về Phase 7. Plan 07-05 `05-smoke-e2e.sh` resolve toàn bộ 11+ pending items qua 1 automated run + 1 manual visual checkpoint:
   - Phase 3 SSO live (1 hub yte + central + JWT SSO PASS golden path) — automated qua 05-smoke-e2e.sh step `login + upload`.
   - Phase 4 SYNC live (cross-hub p95 < 1.5s E-V3-2 + isolation E-V3-3 + 3 hub data sync) — automated qua 05-smoke-e2e.sh step `search cross-hub` + Prometheus scrape.
   - Phase 5 PROXY 4 hub × 11 trang React M2 COMPAT-01 — manual visual checkpoint Plan 07-05 Task `checkpoint:human-action gate=advisory` (KHÔNG blocking để chain finalize milestone; user decision required nếu detect regression).
   - Phase 6 SETTINGS pub/sub propagate < 30s + apikey verify cache hit + boot fail-loud — automated qua 05-smoke-e2e.sh extension step `curl PUT rag-config + sleep 5s + curl GET rag-config from yte verify changed`.

**WHAT phase 7 KHÔNG ship:**

- Sub-hub split (v3.0 multi_hub_split) — defer v4.0 per user seed memory `project_v3_multi_hub_split.md` 2026-05-21 (sub-hub DB riêng + URL subpath + chunks+vector → tổng; 4 decision LOCKED nhưng defer cho tới M2 closeout v3.0 100% xong).
- Adaptive sync TTL — defer v4.0 (60s default đủ).
- HA Redis cluster — defer v4.0 (R-V3-6 LOW, 1 Redis OK).
- HA Postgres replica — defer v4.0 (single primary acceptable v3.0).
- Frontend rewrite settings UI — D6 expired Phase 5; settings UI giữ M2 central-only (carry forward Phase 6 SETTINGS-04 read-only ở hub con).
- v3.0 milestone archive — defer `/gsd-complete-milestone v3.0` (separate command — KHÔNG trong Phase 7 scope, chỉ trigger từ STATE.md Next Action).
- Production deploy actual — defer ops handover (Phase 7 verify staging/local docker compose; production deploy là ops runbook separate).

</domain>

<decisions>
## Implementation Decisions

### GA-V3-D part 2 · Per-hub Data Snapshot Mechanism (LOCKED — recommended seed)

**D-V3-Phase7-A:** **`pg_dump --data-only --where="hub_id = '<uuid>'"`** (option a) — KHÔNG cocoindex replay (option b backup-only).

**Rationale:**
- Speed: pg_dump 1 hub ~5-10 phút (chunks ~50k rows + vector 1536-dim) vs cocoindex re-ingest từ `file_store/` 30-60 phút × 3 hub.
- Schema match: per-hub Alembic 0001..0005 đã upgrade Phase 4 — schema identical (chunks + documents + users + audit_logs + usage_events + sync_outbox). `pg_dump --data-only` skip schema KHÔNG conflict.
- Vector preserve: cocoindex re-embedding cost LLM API + embedding API ~$100-500/3 hub. pg_dump preserve `vector` column 1536-dim binary safe.
- Failure backup: nếu pg_dump corrupt 1 hub → cocoindex replay từ `file_store/` còn nguyên DOCX/PDF + re-ingest qua `/api/documents/reindex` admin endpoint M2 carry forward (option b reserved).

**REJECT alternatives:**
- Option b cocoindex replay: slow + $500 LLM cost + chunks `id` thay đổi (UUID5 từ stable_chunk_id Phase 4 NHƯNG nếu reindex DOCX khác slight content thì hash khác). KHÔNG idempotent với central chunks đã sync.

### D-V3-Phase7-B · Migration Window — Blue/Green Per-hub Zero-downtime (LOCKED — REQUIREMENTS.md MIGRATE-02 explicit)

**D-V3-Phase7-B:** Blue/green per-hub zero-downtime — KHÔNG full downtime weekend.

**Procedure per-hub** (R-V3-4 mitigation):
1. **Blue** = current `python-api-central` serve hub_id rows từ `medinet_central` (v2.0 monolith).
2. **Green** = NEW `python-api-<hub>` container đã ready Phase 1+2+3+4+5+6 (v3.0).
3. Snapshot blue → restore green: `01-snapshot-hubs.sh <hub>` + `02-restore-hub.sh <hub>`.
4. Verify green smoke: `curl https://wiki.domain.com/<hub>/api/health` PASS + login test JWT issue + 1 search local PASS.
5. Switch Caddy upstream blue → green: `03-switch-caddy.sh <hub>` (sed Caddyfile + `caddy validate` + `caddy reload` zero-downtime per Phase 5 PROXY-01 hub-add.sh step 9 pattern).
6. Verify smoke post-switch: `05-smoke-e2e.sh <hub>` golden path 7 step PASS.
7. Repeat steps 1-6 cho 2 hub còn lại.
8. Sau 3 hub PASS: `04-truncate-central.sh` central skeleton DELETE per hub_id (batched + COUNT verify + audit_log INSERT non-repudiation).

**Brief read-only window:** Caddy reload zero-downtime — Phase 5 verify `caddy reload` ~50-100ms downtime negligible HTTP/2 keep-alive resume. User KHÔNG perceive downtime nếu KHÔNG có active upload/ingest (ingest queue persist Redis Plan 04-01 carry forward).

**Risk fallback:** Nếu Step 6 smoke FAIL per-hub → rollback Caddy switch (`03-switch-caddy.sh <hub> --rollback`) → blue serve lại → debug green DB → re-restore. Snapshot file 30-day retention enable rollback.

**REJECT alternatives:**
- Full downtime weekend: simpler nhưng UX impact + Slack/Email broadcast ops cost.
- Live replication during cutover: Postgres logical replication (Phase 4 đã REJECT D-V3-Phase4-A1 — schema drift sensitive + debug khó). pg_dump snapshot là consistent-at-time-T cleaner.

### D-V3-Phase7-C · MCP Re-point Strategy (LOCKED — D-V3-02 + Phase 8.3 v2.0 confirm)

**D-V3-Phase7-C:** MCP service re-point `API_BASE_URL = https://central/api` central aggregate — KHÔNG fan-out N hub.

**Carry forward:**
- D-V3-02 LOCKED Phase 1 — cross-hub search aggregate ở central qua `medinet_central.chunks`.
- Phase 4 Plan 04-05 — `SearchService._search_cross_hub_impl` 1 SQL aggregated `WHERE hub_id = ANY($N::uuid[])` (D-V3-Phase4-D1 LOCKED).
- Phase 8.3 v2.0 — mcp_service OAuth flow stable 9 plan ship 2026-05-21; 135/135 test PASS regression baseline.

**Implementation:**
- `mcp_service/config.py::Settings.API_BASE_URL` env update `http://api:8080` → `https://central/api` (DEFAULT v3.0 production) HOẶC `http://python-api-central:8080` (DEFAULT v3.0 dev compose).
- MCP tools `search_wiki(hub_id?)` + `ask_wiki(hub_id?)` signature unchanged — `hub_id: str | None` optional. Omit = cross-hub (central aggregate). Provide = single-hub (forward to `https://central/api/search/hub-scoped?hub_id=<hub>`).
- OAuth flow `wiki.domain.com/mcp/auth/v2/authorize` carry forward Phase 8.3 — Caddy reverse proxy đã route `/mcp/*` tới `mcp_service:9001` Phase 5 PROXY-01.
- Smoke Inspector: Claude Inspector connect via OAuth client_id `wiki-mcp` (M2 production) + scope `read:wiki write:wiki` + call 2 tool + verify response envelope D6.

**Test regression mandatory:**
- 135/135 `mcp_service/tests/` PASS pre-deploy (Phase 8.3 carry forward).
- 4/4 mcp_oauth_client integration PASS (Phase 3 cross-process + Phase 8.3 OAuth + Phase 5 proxy).

### D-V3-Phase7-D · Post-migration Verification Strategy (LOCKED — automated mandatory + human supplement)

**D-V3-Phase7-D:** Automated smoke `05-smoke-e2e.sh` mandatory + human UAT visual smoke supplement (advisory KHÔNG blocking).

**Automated layer (mandatory):**
- `scripts/migrate/05-smoke-e2e.sh` Bash 3 hub × 7 step (login + upload + status + search local + search cross-hub + ask + citation) qua `curl` + `jq` parse envelope D6 + exit code 0/1.
- 1 run = ~5-10 phút local + ~10-15 phút staging (network latency).
- Output: structured log + Prometheus scrape verify `apikey_verify_total{result=cached}` + `sync_lag_seconds{hub_name=yte}` < 30s + cross-hub p95 < 1.5s (E-V3-2).
- Hub isolation E-V3-3 verify: curl `wiki.domain.com/yte/api/documents/{duoc_doc_id}` → 403 CROSS_HUB_ACCESS_DENIED envelope D6 (NOT 404 leak).
- Phase 6 SETTINGS pub/sub: curl PUT rag-config central + sleep 5s + curl GET rag-config from yte → verify changed (< 30s propagate E-V3-4).
- Phase 3 SSO live: login central → JWT issue → curl yte api với same JWT → 200 PASS + cross-hub search PASS.
- BLOCKING: 1 step FAIL → exit 1 → Plan 07-05 closeout halt cho tới fix.

**Human supplement (advisory):**
- Manual visual smoke 4 hub × 11 trang React M2 COMPAT-01 (UI-SPEC §7 — Phase 5 Plan 05-06 deferred).
- Per-hub branding visual diff (Phase 5 PROXY-04): logo + theme color + title VN qua mỗi hub URL.
- Login page state machine A/B/C/D visual verify (Phase 5 Plan 05-04).
- Documents ingest UI happy path (M2 carry forward).
- KHÔNG blocking: nếu detect visual regression → log dưới dạng v3.1 follow-up issue + closeout milestone v3.0 vẫn proceed.

**Resume signal — auto-fallback:** Trong --auto chain mode, Plan 07-05 Task human-action visual smoke có auto-fallback `skip smoke` per v3.0-b precedent (Plan 03-05 + 04-07 + 05-06 + 06-05 — 4 phase trước đã skip smoke runtime defer Phase 7). Phase 7 là phase cuối → KHÔNG defer nữa, nhưng evidence chain automated 05-smoke-e2e.sh đủ semantic coverage MIGRATE-05 success criteria (3 hub + central golden path + cross-hub p95 + isolation E-V3-3).

### Carry-forward Decisions (LOCKED — KHÔNG re-discuss)

Từ Phase 1-6 (consistency mandatory):

- **D-V3-01 LOCKED Phase 1** — Per-hub DB tách physical (TOPO-01..04 satisfied). Phase 7 restore vào `medinet_hub_<name>` đã ready.
- **D-V3-02 LOCKED Phase 1** — `medinet_central.chunks` aggregated cross-hub search target. Phase 7 KHÔNG truncate `medinet_central.chunks` (SYNC carry forward).
- **D-V3-Phase2-FACTOR-04 LOCKED Phase 2** — Dynamic hub registration via `make hub-add` + `hub-add.sh` 9-step + `Settings.hub_name` regex `^[a-z][a-z0-9_]{0,15}$` + RESERVED blacklist 6 name. Phase 7 script 02-restore-hub.sh + 03-switch-caddy.sh reuse pattern.
- **D-V3-Phase3-A/B/D/E/G/H LOCKED Phase 3** — JWT aud + hub_ids + kid + JWKS + 307 redirect + 3-layer E4 enforce. Phase 7 smoke verify JWT live SSO cross-hub.
- **D-V3-Phase4-A1 LOCKED Phase 4** — Outbox + worker sync mechanism (REJECT cocoindex / Postgres logical replication). Phase 7 verify sync_lag < 30s post-migration + `sync_outbox` empty post-quiesce 5 phút.
- **D-V3-Phase4-D1/D3 LOCKED Phase 4** — Cross-hub search 1 SQL aggregated + central-only mount FACTOR-02. Phase 7 smoke verify p95 < 1.5s E-V3-2.
- **D-V3-Phase5-A1/A2/B1/B3 LOCKED Phase 5** — Caddy `path_regexp` + `uri strip_prefix` + frontend 1-build runtime detect prefix. Phase 7 script 03-switch-caddy.sh sed edit upstream preserve pattern.
- **D-V3-Phase6-A/B/C/D LOCKED Phase 6** — HTTP pull + Redis pub/sub hybrid settings sync + SETTINGS_PROXY_SECRET ≥ 32 char + escape hatch SETTINGS_SKIP_FETCH=1. Phase 7 smoke verify pub/sub propagate.
- **D6 EXPIRED Phase 5** — Frontend rewrite cho phép (PROXY-02 prefix detect + PROXY-04 branding). Phase 7 KHÔNG đụng frontend code (settings UI giữ M2 central-only per Phase 6 SETTINGS-04 read-only).
- **AUX-02 v2.0 carry forward** — AES-GCM api_key at-rest central. Phase 7 MCP re-point KHÔNG đụng api_key_service.

### Claude's Discretion

- Plan numbering structure: gợi ý 5 plan match MIGRATE-01..05 1:1 nhưng planner có thể decompose thành 5-7 plan tùy task granularity (ví dụ tách `04-truncate-central.sh` ra plan riêng do risk profile khác `02-restore-hub.sh`).
- Specific `pg_dump` flags: `--data-only --no-owner --no-acl --column-inserts` (chốt ở plan). `--column-inserts` slow nhưng cross-PG-version safe (v3.0 staging vs production có thể khác minor version).
- Snapshot retention enforcement: 30-day default qua `find migrate-snapshots/ -mtime +30 -delete` cron HOẶC manual operator delete. Planner chốt.
- Per-hub migration order: gợi ý `yte → duoc → hcns` (alphabetical) HOẶC `hcns → duoc → yte` (lowest M2 traffic risk first — amber/least active). Planner chốt.
- Audit log preservation during truncate: gợi ý INSERT `audit_logs` row `action='migrate.truncate_hub'` + `actor='system'` + `metadata={hub_id, row_count_deleted}` BEFORE DELETE per hub. Planner chốt audit format.

### Folded Todos

[None — auto-mode đã batch-resolve HUMAN-UAT pending từ Phase 3+4+5+6 thông qua Plan 07-05 automated + supplemental human smoke. KHÔNG có todos riêng cần fold]

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing.**

### Phase 7 specs

- `.planning/REQUIREMENTS.md` §MIGRATE — MIGRATE-01..05 acceptance criteria chi tiết (snapshot + restore + truncate + MCP re-point + smoke E2E)
- `.planning/ROADMAP.md` §"Phase 7" — Goal + success criteria + 4 gray area
- `.planning/PROJECT.md` — Vision + non-negotiables (E1/E2/E3/E4 — JWT iat + per-hub isolation 3-layer + retention)

### Carry-forward Phase 1-6 patterns (analog references)

- `.planning/phases/01-multi-db-topology/01-{01..04}-SUMMARY.md` — Per-hub DB + DSN validator + Alembic 0001..0005
- `.planning/phases/02-hub-con-codebase-factor/02-{01..05}-SUMMARY.md` — FACTOR-02 central-only mount + hub-add.sh 9-step + Settings.hub_name regex
- `.planning/phases/03-auth-sso-hub-ids-jwt/03-{01..05}-SUMMARY.md` — JWT aud/hub_ids/kid + JWKSCache lifespan + E4 3-layer
- `.planning/phases/04-cross-hub-data-sync/04-{01..07}-SUMMARY.md` — Outbox + worker + 1 SQL aggregated cross-hub + checksum scheduler
- `.planning/phases/05-reverse-proxy-frontend-subpath/05-{01..06}-SUMMARY.md` — Caddyfile wiki block + frontend 1-build + hub-add.sh + branding
- `.planning/phases/06-system-settings-sync/06-{01..05}-SUMMARY.md` — settings_sync module + pub/sub + lifespan fail-loud + SETTINGS_SKIP_FETCH escape hatch
- `.planning/phases/06-system-settings-sync/06-HUMAN-UAT.md` — 4 runtime smoke items pending Phase 7 MIGRATE-05 batch-resolve

### Codebase critical files (planner mapping target)

- `api/scripts/hub-add.sh` — Phase 5 9-step pipeline (Caddy reload + smoke curl warn-only pattern — analog cho 03-switch-caddy.sh)
- `Hub_All/Caddyfile` — Phase 5 wiki block (path_regexp + strip prefix + reverse_proxy — analog cho 03-switch-caddy.sh sed edit upstream)
- `Hub_All/docker-compose.yml` — 4 service env wire (analog cho compose extended Phase 7 7-step run-all command)
- `api/app/sync/keys.py` + `worker.py` — sync_outbox + sync_worker (Phase 4 carry forward — Phase 7 verify quiesce post-migration)
- `api/app/observability/checksum_scheduler.py` — daily/hourly drift check (Phase 4 — Phase 7 verify run after migration)
- `mcp_service/config.py` — `Settings.API_BASE_URL` (re-point target Phase 7 MIGRATE-04)
- `mcp_service/tests/` — 135 test (Phase 8.3 v2.0 — Phase 7 regression mandatory)
- `api/.env.example` — Phase 6 SETTINGS section (analog cho Phase 7 migration env documentation)
- `api/tests/integration/test_factor_hub_scoped.py` — Phase 2 FACTOR-02 verify (Phase 7 smoke uses similar isolation pattern)
- `api/tests/integration/test_hub_isolation_db_level.py` — Phase 1 TOPO-04 verify (Phase 7 smoke uses similar E-V3-3 pattern)

### v2.0 milestone artifacts (regression baseline)

- `.planning/milestones/v2.0-archive/` — M2 spec + 38 REQ-ID + Phase 8.3 OAuth 9-plan ship
- `Hub_All/CLAUDE.md` §6 — milestone progress table + v3.0 Phase 1-6 pattern subsection (analog template for Phase 7 subsection)
- `Hub_All/README.md` — Phase 3+4+5+6 deploy notes section (analog template for Phase 7 "Migration + Smoke E2E Runbook" section)

### Operator runbooks (Phase 7 outputs)

- `scripts/migrate/01-snapshot-hubs.sh` — to be created Plan 07-01
- `scripts/migrate/02-restore-hub.sh` — to be created Plan 07-02
- `scripts/migrate/03-switch-caddy.sh` — to be created Plan 07-02 or 07-03
- `scripts/migrate/04-truncate-central.sh` — to be created Plan 07-03
- `scripts/migrate/05-smoke-e2e.sh` — to be created Plan 07-05
- `scripts/migrate/06-mcp-smoke.md` runbook — to be created Plan 07-04

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (carry forward Phase 1-6)

- **Caddy reload pattern** (Phase 5 Plan 05-05 `hub-add.sh` step 9): `caddy validate --config /etc/caddy/Caddyfile` → `caddy reload` zero-downtime + smoke `curl warn-only`. Phase 7 `03-switch-caddy.sh` reuse sed edit + validate + reload pipeline.
- **Per-hub Alembic 0001..0005** (Phase 1 + 4): per-hub DB schema ready. `02-restore-hub.sh` chỉ data load, KHÔNG schema migrate.
- **asyncpg Pool + register_vector codec** (Phase 4 Plan 04-04 `_init_central_sync_conn`): central_sync_pool pattern. Phase 7 KHÔNG đụng (sync worker auto-restart sau migration).
- **Settings.hub_id UUID env** (Phase 4 Plan 04-02): boot fail-fast 3 model_validator. Phase 7 verify env wire match restored DB hub_id UUID.
- **mcp_service config.py** (Phase 8.3 v2.0): `Settings.API_BASE_URL` env override. Phase 7 MIGRATE-04 chỉ thay 1 env value.
- **scripts/hub-init.sh** (Phase 2 FACTOR-04): wrapped bởi `hub-add.sh`. Phase 7 Plan 07-02 restore script tham khảo error-handling + idempotent pattern.
- **smoke-e2e curl + jq pattern** (Phase 5 Plan 05-05 step 9 + Phase 8.3 mcp_service smoke): standardized response envelope D6 parse `.success` + `.data` + `.error.code`. Phase 7 `05-smoke-e2e.sh` reuse jq filter chain.

### Established Patterns (mandatory follow)

- **Response envelope D6**: `{success, data, error, meta}` JSON shape locked M2 + v3.0 (KHÔNG break — Phase 7 smoke parse same shape).
- **Hub naming convention**: lowercase + alphanumeric + underscore + max 16 char (Phase 2 Settings regex). RESERVED blacklist (postgres/cocoindex/template0/template1/public/medinet) — Phase 7 reuse identical validation in scripts.
- **Caddy upstream port STATIC :8080** (Phase 5 Plan 05-01 Pitfall 1): KHÔNG dynamic per-hub port. Phase 7 `03-switch-caddy.sh` confirm upstream `python-api-<hub>:8080` đúng pattern.
- **Bash strict mode**: `set -euo pipefail` + `IFS=$'\n\t'` (Phase 2 + 5 hub-add.sh). Phase 7 5 script tuân thủ same prefix.
- **Atomic sed edit pattern** (Phase 5 hub-add.sh step 8): `tmp_file=$(mktemp)` + `sed ... > "$tmp_file"` + `mv "$tmp_file" "$target"`. Phase 7 `03-switch-caddy.sh` reuse cho Caddyfile edit.
- **Caddy validate before reload** (Phase 5 Pitfall 7 silent rollback mitigation): MANDATORY in all Caddy-touching scripts. Phase 7 `03-switch-caddy.sh` honor.

### Integration Points (where Phase 7 code connects)

- **Caddyfile upstream block** → `03-switch-caddy.sh` sed edit `reverse_proxy http://python-api-central:8080` → `reverse_proxy http://python-api-<hub>:8080` cho hub_api path_regexp branch.
- **docker-compose.yml** → Phase 7 KHÔNG đụng (4 service đã đầy đủ Phase 1-6 ship). Verify `docker compose config --quiet` PASS pre-migration.
- **medinet_central database** → `04-truncate-central.sh` DELETE rows. KHÔNG đụng schema. Run BEFORE backup migrate-snapshots/ cleanup retention.
- **medinet_hub_{yte,duoc,hcns} databases** → `02-restore-hub.sh` `psql -f` LOAD data into existing schema. Verify row count sanity.
- **mcp_service container** → restart sau env update `API_BASE_URL` (1 line config.py + docker-compose env).
- **Prometheus metrics** → Phase 7 smoke scrape `apikey_verify_total + sync_lag_seconds + cross_hub_search_latency_seconds + sync_count_drift + sync_hash_drift` verify thresholds.

### Creative Options (architecture-enabled)

- **Parallel hub migration**: 3 hub có thể migrate concurrent qua `xargs -P 3` nếu pg_dump memory cho phép. Trade-off: simpler debug sequential vs faster parallel. Planner chốt (gợi ý sequential cho v3.0 first migration — verify-go-no-go per hub).
- **Snapshot encryption at-rest**: `pg_dump | gpg --symmetric > migrate-<hub>.sql.gpg`. Defer v4.0 (operator local laptop OK plaintext for v3.0).
- **Migration dry-run mode**: `--dry-run` flag default ON cho `04-truncate-central.sh` (high-risk DELETE). Operator phải explicit `--apply` flag để thực thi. Planner chốt safety default.
- **Replay log strategy**: Nếu migration fail mid-step → maintain `migrate-state.json` ghi `{step: 5, hub: 'yte', status: 'rollback_needed'}` để operator resume. Defer Plan 07-05 nếu task quá phức tạp.

</code_context>

<specifics>
## Specific Ideas

- **Snapshot naming convention**: `migrate-<hub>-<YYYY-MM-DD>.sql` (e.g., `migrate-yte-2026-05-23.sql`). Date enables retention `find -mtime +30 -delete` automation.
- **Caddy upstream sed pattern**: `reverse_proxy http://python-api-{re.hub_api.1}:8080` GIỮ NGUYÊN — Phase 5 Plan 05-01 đã dynamic per-hub_api regex capture. Phase 7 `03-switch-caddy.sh` chỉ verify upstream `python-api-<hub>` container actually `up` qua `docker compose ps`. KHÔNG sed edit Caddyfile (dynamic regex đã đủ).

  **Correction during planning:** Re-read Caddyfile sau Phase 5 — nếu `{re.hub_api.1}` đã dynamic capture hub_name từ URL prefix, thì Phase 7 KHÔNG cần `03-switch-caddy.sh` sed edit. Chỉ cần verify `docker compose up python-api-<hub>` post-restore + Caddy auto-route prefix → hub_api regex match → `python-api-<hub>:8080` upstream. Script `03-switch-caddy.sh` shrink thành verify-only (KHÔNG sed).

- **Audit log format Phase 7 ops**: `action: 'migrate.snapshot' | 'migrate.restore' | 'migrate.switch_caddy' | 'migrate.truncate' | 'migrate.mcp_repoint'` + `actor: 'system'` + `metadata: {hub_id, row_count_affected, dry_run_flag, timestamp}`. INSERT cùng transaction operation để rollback an toàn.
- **Smoke E2E test data**: Tạo `scripts/migrate/fixtures/sample-document.docx` 1 file test ingest qua API. KHÔNG dùng real production data trong smoke (privacy + reproducibility).
- **MCP re-point env var name**: GIỮ `API_BASE_URL` (M2 carry forward — KHÔNG rename `MCP_CENTRAL_URL` để KHÔNG đụng mcp_service code). Chỉ thay value.
- **Prometheus assertion thresholds Phase 7 smoke**:
  - `cross_hub_search_latency_seconds` p95 < 1.5s (E-V3-2)
  - `sync_lag_seconds{hub_name}` < 30s for all 3 hub (E-V3-4)
  - `apikey_verify_total{result=cached}` > 0 (Phase 6 SETTINGS-03 cache hit verify)
  - `sync_count_drift{hub_name}` < 0.01 (1%) for all 3 hub (R-V3-1 drift < 1%)
  - `sync_hash_drift{hub_name, drift_type=mismatch}` rate < 0.001/s post-quiesce
- **5-plan structure preview** (planner discretion):
  - Plan 07-01: `01-snapshot-hubs.sh` + `migrate-snapshots/` dir + `.gitignore` exclude + per-hub Alembic version verify
  - Plan 07-02: `02-restore-hub.sh` + `03-switch-caddy.sh` (verify-only post Caddy regex) + blue/green smoke per-hub helper
  - Plan 07-03: `04-truncate-central.sh` + dry-run default + audit_log INSERT + 30-day retention policy doc
  - Plan 07-04: MCP `API_BASE_URL` env update + `06-mcp-smoke.md` runbook + 135/135 regression test PASS
  - Plan 07-05 (closeout): `05-smoke-e2e.sh` 3 hub × 7 step automated + HUMAN-UAT visual smoke 4 hub × 11 trang advisory + CLAUDE.md + STATE.md + REQUIREMENTS.md + ROADMAP.md + README.md + milestone v3.0 close marker

</specifics>

<deferred>
## Deferred Ideas

### Defer v4.0 (post-v3.0 milestone)

- **Sub-hub split (multi_hub_split)**: Sub-hub DB riêng + URL subpath + chunks+vector → tổng (user seed memory 2026-05-21 — 4 decision LOCKED defer cho tới v3.0 milestone closeout).
- **Adaptive sync TTL**: TTL dynamic dựa change frequency (Phase 6 SETTINGS deferred).
- **HA Redis cluster**: R-V3-6 LOW priority.
- **HA Postgres replica**: Single primary acceptable v3.0.
- **Snapshot encryption at-rest**: `pg_dump | gpg` — operator local OK plaintext v3.0.
- **Replay log JSON state**: `migrate-state.json` resume-after-failure — Phase 7 first iteration KHÔNG cần (sequential migration + manual rollback per snapshot file).
- **Parallel hub migration**: `xargs -P 3` concurrent — v3.0 first migration ưu tiên sequential debug.

### Defer separate command (NOT Phase 7 scope)

- **v3.0 milestone archive**: `/gsd-complete-milestone v3.0` — separate command trigger from STATE.md Next Action sau Phase 7 DONE.
- **Production deploy actual**: Ops handover runbook — Phase 7 verify staging/local docker compose only.
- **v3.1 hot-fixes**: Visual regression từ HUMAN-UAT manual smoke (nếu detect) → log v3.1 follow-up issue, KHÔNG block v3.0 close.

### Reviewed Todos (not folded)

[None — auto-mode KHÔNG cross-reference todos riêng. HUMAN-UAT pending từ 4 phase trước đã batch-resolve trong scope MIGRATE-05]

</deferred>

---

*Phase: 07-migration-smoke-e2e*
*Context gathered: 2026-05-23 via Auto Mode `--auto`*
*Source: planner-seed-defaults from ROADMAP gray areas + REQUIREMENTS.md MIGRATE-01..05 + 6-phase carry-forward decisions*
*Next: `/gsd-plan-phase 7 --auto` — generates 5-plan structure aligned with MIGRATE-01..05*
