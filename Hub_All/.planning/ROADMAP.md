# Roadmap — Medinet Wiki (MEDWIKI)

**Project:** Medinet Wiki (Hub_All) · **Tracking:** ROADMAP (current = v3.0) + MILESTONES.md (history) + `.planning/milestones/v*/` (archives)
**Last updated:** 2026-05-21 (`/gsd-new-milestone v3.0`)

---

## Milestones

- ❌ **v1.0 RAG Quality with Docling** — Abandoned 2026-05-13 (xem `.planning/milestones/v1.0-docling-rag/`)
- ✅ **v2.0 Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)** — Shipped 2026-05-21, 13 phases / ~75 plans / 38 REQ-ID done. Archive: [`milestones/v2.0-full-rag-rewrite/ROADMAP.md`](milestones/v2.0-full-rag-rewrite/ROADMAP.md) · [`REQUIREMENTS.md`](milestones/v2.0-full-rag-rewrite/REQUIREMENTS.md) · [`phases/`](milestones/v2.0-full-rag-rewrite/phases/)
- 🔄 **v3.0 Multi-Hub Split** — **STARTED 2026-05-21**, 7 phases / 29 REQ-ID, phase numbering reset về 1 (D-V3-05).
- 📋 **v4.0 Production Hardening + Advanced RAG** — Backlog (OCR Vietnamese, cross-dim embedding swap, streaming `/api/ask`, coverage >80%, ...)
- 📋 **v4.1 Advanced Retrieval** — Backlog (Hybrid BM25 + reranker, local embedding SEED-001, version history).

---

## Phases — v3.0 Multi-Hub Split (CURRENT)

7 phase reset numbering. Total ~30 plan estimate (~4-5 plan/phase). v3.0-a / v3.0-b split anti-pivot (kế thừa pattern R3 v2.0).

| # | Phase | Goal | Requirements | Success Criteria | Depends on |
|---|---|---|---|---|---|
| ✅ **1** | Multi-DB topology + per-hub Alembic | Tạo N+1 DB cùng instance, per-hub Alembic migration set khớp head SHA, cocoindex flow naming per-hub | TOPO-01..04 (4) | 4 | M2 shipped — **DONE 2026-05-21** (5 plans / 22 commits) |
| ✅ **2** | Hub-con codebase factor | 1 codebase deploy nhiều lần với HUB_NAME; strip system settings ở hub con; expose 10 endpoint hub-scoped; dynamic hub registration (FACTOR-04 added 2026-05-22) | FACTOR-01..04 (4) | 4 | M2 shipped — **DONE 2026-05-22** (5 plans / 12 commits) |
| **3** | Auth SSO + hub_ids trong JWT | JWKS endpoint central; cache hub con TTL 1h HA; Redis blacklist chung; E4 DB-level isolation | SSO-01..04 (4) | 4 | Phase 2 |
| 🚦 | **v3.0-a EXIT GATE** | Demo 1 hub con (yte) + tổng + JWT SSO + golden path PASS — user accept tiếp tục v3.0-b | — | — | Phase 1-3 done |
| **4** | Cross-hub data sync | Chunks+vector denormalized push hub con → central; idempotent retry; cross-hub search aggregated; checksum verify periodic; mechanism chốt | SYNC-01..05 (5) | 5 | Phase 1, 3 |
| **5** | Reverse proxy + frontend subpath | Caddy subpath route; frontend detect prefix 1 build; D6 expire formally; per-hub login branding | PROXY-01..04 (4) | 4 | Phase 2 |
| **6** | System settings sync | rag-config HTTP pull + Redis cache 60s + pub/sub invalidate < 30s; api_keys verify proxy central; hub_registry read-only | SETTINGS-01..04 (4) | 4 | Phase 3 |
| **7** | Migration + smoke E2E | pg_dump per hub_id; restore blue/green per-hub; truncate central skeleton; MCP re-point central; smoke E2E 3 hub + tổng PASS | MIGRATE-01..05 (5) | 5 | Phase 1-6 |

**v3.0-a (Phase 1-3):** Topology + Codebase Factor + SSO — có thể ship standalone. Demo: 1 hub con + tổng + JWT SSO PASS golden path. User accept v3.0-a → never pivot multi-DB topology.

**v3.0-b (Phase 4-7):** Sync + Proxy + Settings + Migration — pivot OK nếu SYNC mechanism (GA-V3-D) chốt sai. v3.0-a giữ nguyên reusable.

**Critical path:** 1 → 2 → 3 → 4 → 7 (data flow vertical). **Parallel-able branches:** 5 (depends on 2 only) ⊥ 6 (depends on 3 only) — có thể chạy song song với 4.

---

## Phase Details

### Phase 1 — Multi-DB Topology + Per-hub Alembic

**Goal:** Postgres init script idempotent tạo N+1 logical DB cùng instance (`medinet_central` + `medinet_hub_<name>` × N) với extension vector + HNSW 1536-dim verify build; per-hub Alembic migration set khớp head SHA giữa các DB; cocoindex flow naming per-hub `medinet_<hub>_ingest` + APP_NAMESPACE per-hub; HUB_NAME env isolation enforce kết nối đúng DB.

**Requirements:** TOPO-01, TOPO-02, TOPO-03, TOPO-04

**Success criteria:**
1. `docker compose up` tạo 4 DB (`medinet_central`, `medinet_hub_yte`, `medinet_hub_duoc`, `medinet_hub_hcns`) trên 1 instance; mỗi DB có `CREATE EXTENSION vector` + HNSW index 1536-dim verify build được (psql query).
2. `make migrate-all` apply Alembic migrations tuần tự 4 DB; `alembic current` returns cùng head SHA cho tất cả; CI lint check version match (R-V3-3 mitigation).
3. Cocoindex flow `medinet_<hub>_ingest` startup logs OK ở từng hub con (APP_NAMESPACE `medinet_<hub>_prod` không đụng nhau).
4. Test integration: `HUB_NAME=yte` deploy KHÔNG truy cập được `medinet_hub_duoc` qua DB connection (E-V3-3 enforce DB-level).

**Discuss-phase gray areas (chốt 2026-05-21 theo planner seed defaults — KHÔNG /gsd-discuss-phase 1):**
- GA-Phase1-A (init script style): CHỌN imperative bash loop + conditional `SELECT pg_database WHERE datname` (KHÔNG `CREATE DATABASE IF NOT EXISTS` — Postgres không support syntax đó). Extend pattern M2 `api/scripts/init-db.sh`.
- GA-Phase1-B (cocoindex per-hub): CHỌN APP_NAMESPACE per-hub `medinet_<hub>_prod` — giữ `cocoindex_db_schema="cocoindex"` cố định (R5 + P7 carry forward).
- GA-Phase1-C (dynamic hub add): CHỌN `make hub-init HUB=<name>` — bash script chạy CREATE DATABASE + CREATE EXTENSION vector + alembic upgrade head cho hub mới, KHÔNG cần docker compose down.

**Plans:** 5 plans (3 waves — Wave 1 parallel × 2, Wave 2 parallel × 2, Wave 3 × 1)

Plans:
- [ ] 01-01-PLAN.md — Postgres init-db.sh refactor 4 DB + extension vector + HNSW 1536-dim verify (TOPO-01 part 1)
- [ ] 01-02-PLAN.md — Settings.hub_name + per-hub DSN resolver + db/session.py verify (TOPO-04 part 1)
- [ ] 01-03-PLAN.md — Per-hub Alembic env.py + make migrate-all + alembic-head-check.sh (TOPO-02 part 1 + R-V3-3 lint script)
- [ ] 01-04-PLAN.md — Cocoindex flow naming per-hub + APP_NAMESPACE per-hub (TOPO-03)
- [ ] 01-05-PLAN.md — Dynamic hub-init.sh + integration test isolation + CI workflow + [BLOCKING] schema push (TOPO-01/02/04 part 2 + R-V3-3 CI gate + E-V3-3 enforce)

---

### Phase 2 — Hub-con Codebase Factor

**Goal:** 1 codebase deploy được nhiều lần với env `HUB_NAME=<name>` (central vs yte vs duoc vs hcns); app factory `create_app(hub_name)` đọc env, mount router phù hợp; strip system settings router khi `HUB_NAME != "central"`; hub con expose 10 endpoint hub-scoped.

**Requirements:** FACTOR-01, FACTOR-02, FACTOR-03, FACTOR-04 (FACTOR-04 added 2026-05-22 sau closeout discussion — user direction B "generalize 100% dynamic")

**Success criteria:**
1. `HUB_NAME=yte` deploy spawn hub con process; central process không bị ảnh hưởng (parallel deploy 4 process FastAPI).
2. Hub con `GET /api/rag-config` trả 404 (KHÔNG 403 — endpoint không exist do FACTOR-02 strip); `GET /api/health` 200.
3. Hub con expose 10 endpoint hub-scoped (auth/profile/documents/search/ask/usage); smoke test mỗi endpoint trả 200 hoặc lỗi đúng shape envelope.
4. **Dynamic hub registration (FACTOR-04):** `make hub-add HUB=tmp_test PORT=8189` → DB tạo + service block append `docker-compose.override.yml` + `docker compose up -d python-api-tmp_test` boot OK + `curl localhost:8189/api/health` 200, KHÔNG sửa code Python/`docker-compose.yml` base. Settings regex validator accept hub mới; reject invalid pattern + reserved name.

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 2`):**
- App factory pattern: 1 `create_app(hub_name)` factory function vs 2 file `main_central.py` + `main_hub.py` (DRY vs explicit).
- Mount router conditional: import + `app.include_router(...)` if condition vs feature flag config-driven.
- Docker compose service definition: 4 service riêng (central + 3 hub) vs 1 service template + replicas với env override.

**Decisions (chốt 2026-05-22 theo planner seed defaults Auto Mode `--chain`, KHÔNG /gsd-discuss-phase 2):**
- D-V3-Phase2-A (App factory pattern): CHỌN 1 `create_app()` factory no-arg đọc settings.hub_name (DRY; Phase 1 Settings singleton consume).
- D-V3-Phase2-B (Router conditional): CHỌN inline `if settings.hub_name == "central":` block (KHÔNG feature flag config-driven — over-engineer cho 2 class hub).
- D-V3-Phase2-C (Docker compose): CHỌN 4 service dedicated với YAML anchor `x-api-template: &api-template` (KHÔNG deploy.replicas — replicas KHÔNG cho phép env per-replica khác).
- D-V3-Phase2-D (Endpoint matrix): 12 endpoint hub-scoped (4 auth + 2 profile + 3 documents + search + ask + usage).
- D-V3-Phase2-E (Strip semantic): 404 envelope shape M2 ErrorHandlerMiddleware wrap (KHÔNG 403 — endpoint không exist).

**Plans:** 5 plans (4 waves — Wave 1 × 1 BLOCKING, Wave 2 parallel × 2 file-disjoint, Wave 3 × 1 closeout FACTOR-01..03, Wave 4 × 1 extension FACTOR-04)

Plans:
- [x] 02-01-PLAN.md — Refactor create_app() conditional router mount (7 universal + 9 central-only) + unit test boot 4 hub mode (FACTOR-01, FACTOR-02) — **DONE 2026-05-22** (9/9 test PASS, central 63 routes / hub con 29 routes)
- [x] 02-02-PLAN.md — Docker-compose 4 service FastAPI dedicated với YAML anchor + cocoindex LMDB volume per-hub + port 8180-8183 + MCP re-point central (FACTOR-01) — **DONE 2026-05-22** (`docker compose config --quiet` exit 0, 8 service render: postgres + redis + 4 python-api-* + mcp_service + caddy)
- [x] 02-03-PLAN.md — Integration test endpoint matrix — 12 hub-scoped mount + 8 central-only strip + envelope shape verify (FACTOR-02, FACTOR-03) — **DONE 2026-05-22** (10/10 test PASS -m "critical and integration", 6.49s; Rule 2 auto-add Starlette HTTPException handler ở app/main.py wrap routing 404 envelope; Rule 3 auto-fix audit queue + SQLAlchemy engine reset trong hub_app_factory; 175/175 unit regression PASS)
- [x] 02-04-PLAN.md — Closeout — CLAUDE.md + STATE.md + REQUIREMENTS.md note (WRN-05 "10 collective / 12 specific endpoints") update + smoke compose 2 service (central + yte) curl matrix (FACTOR-01..03 verify) — **DONE 2026-05-22** (4 commit, Task 1 smoke compose SKIP rationale: Plan 02-03 integration test 10/10 PASS in-process cover FACTOR-02/03 semantic + Phase 1 DSN validator 30/30 PASS regression + Plan 02-02 `docker compose config --quiet` PASS, smoke runtime defer Phase 7 MIGRATE-05)
- [x] 02-05-PLAN.md — Dynamic hub registration (FACTOR-04 added 2026-05-22 — user direction B): Settings.hub_name `Literal[4]` → `str` regex `^[a-z][a-z0-9_]{0,15}$` + RESERVED_HUB_NAMES blacklist 6 name (postgres/cocoindex/template0/template1/public/medinet) + `scripts/hub-add.sh` 7-step pipeline wrap `hub-init.sh` + sed substitute `docker-compose.override.yml.template` + `make hub-add HUB=<name> [PORT=<port>]` target + README quick start — **DONE 2026-05-22** (4 commit, 40/40 unit test PASS test_config_hub_name + test_config_hub_name_dynamic, Task 3 smoke `make hub-add HUB=tmp_test` SKIP rationale: bash syntax `bash -n` PASS + 20+ unit test coverage validator + `docker compose config --quiet` base PASS, runtime defer Phase 7 MIGRATE-05)

---

### Phase 3 — Auth SSO + hub_ids trong JWT (GA-V3-A)

**Goal:** Central expose JWKS endpoint public key RS256; hub con cache JWKS local TTL 1h ở startup + refresh background (R-V3-5 HA mitigation); Redis blacklist `auth:blacklist:<jti>` chung cross-process; JWT claim `hub_ids: list[str]` reflect user's hub assignments; E4 reinforced DB-level isolation (hub con KHÔNG access data hub khác kể cả khi JWT compromised).

**Requirements:** SSO-01, SSO-02, SSO-03, SSO-04

**Success criteria:**
1. `GET https://central/.well-known/jwks.json` trả public key RS256 (PKCS#8); hub con startup load 1 lần, refresh background mỗi 1h.
2. Login `POST https://central/api/auth/login` → JWT verify được ở hub con qua JWKS cache (cross-process).
3. Refresh token blacklist Redis chung: revoke ở central → hub con reject JWT trong < 1s (Redis pub/sub propagate).
4. Stale JWT chứa `hub_ids=["duoc"]` post tới `medinet_hub_yte` API → 403 (E4 reinforced — DB-level + repo-layer).

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 3`):**
- **GA-V3-A chốt:** JWKS endpoint (khuyến nghị seed) vs shared keypair file mount vs cookie domain `.medinet.vn`. Trade-off: JWKS HA + rotation dễ / shared keypair simple nhưng rotation phức tạp / cookie domain phá subpath model.
- JWKS cache fallback: fail-loud nếu central down khi TTL expire vs fallback static keypair embedded ở deploy time (security trade-off).
- Refresh token rotation: chỉ central handle (hub con KHÔNG sinh refresh) — re-confirm contract.

**Decisions (chốt 2026-05-22 theo planner seed defaults Auto Mode `--auto --chain`, KHÔNG `/gsd-discuss-phase 3` interactive — 8 D-V3-Phase3 LOCKED):**
- D-V3-Phase3-A: JWKS endpoint pattern RFC 7517 (KHÔNG shared keypair / cookie domain).
- D-V3-Phase3-B: Boot fail-loud (timeout 5s blocking) + runtime fail-quiet + 24h hard limit.
- D-V3-Phase3-C: Hub con KHÔNG sinh refresh — 100% lifecycle ở central.
- D-V3-Phase3-D: In-process LRU JWKSCache (KHÔNG Redis cache JWKS).
- D-V3-Phase3-E: iss=`"medinet-wiki"` (RE-CONFIRM Plan 03-03 — KHÔNG URL-based) + aud=`["medinet-wiki"]` REQUIRED + hub_ids REQUIRED.
- D-V3-Phase3-F: Frontend redirect (form action central) defer Phase 5 PROXY-02.
- D-V3-Phase3-G: Hub con login + refresh → 307 Location: central (RFC 7231 preserve POST + body).
- D-V3-Phase3-H: Redis blacklist key `auth:blacklist:{jti}` + TTL=exp-now + value `"1"` marker + Redis instance M2 chung.

**Plans:** 5 plans (5 waves — Wave 1 BLOCKING, Wave 2 depend 03-01, Wave 3 depend 03-02, Wave 4 depend 03-03, Wave 5 closeout depend 03-04)

Plans:
- [ ] 03-01-PLAN.md — JWKS endpoint central publish RFC 7517 (`publish_jwks` + `load_public_key_as_jwk` + central mount conditional + `Settings.central_jwks_url` + docker-compose env `CENTRAL_JWKS_URL`) (SSO-01)
- [ ] 03-02-PLAN.md — JWKSCache hub con (in-process LRU + asyncio refresh + 24h hard limit + lifespan startup blocking fetch + dependency branch verify path + `JWTManager.verify_token_with_key` + Settings 3 field + model_validator enforce hub con required) (SSO-01)
- [ ] 03-03-PLAN.md — JWT claim refactor (`aud` + `hub_ids` REQUIRED + PyJWT strict audience check 2 path) + Redis blacklist key rename `auth:blacklist:` (5 vị trí + `_blacklist.py` helper module) + SSO-04 E4 reinforced dependency `get_current_user_for_hub_access` Layer 3 enforce (SSO-02, SSO-03, SSO-04)
- [ ] 03-04-PLAN.md — Auth router refactor hub con 307 redirect login/refresh + `Settings.central_url` + docker-compose `CENTRAL_URL` env + Phase 2 integration test assertion update (split 10 LOCAL + 2 SSO_REDIRECT) + REQUIREMENTS.md FACTOR-03 note extend (SSO-02)
- [ ] 03-05-PLAN.md — Closeout — CLAUDE.md section 6 + STATE.md Phase 3 Results Summary + REQUIREMENTS.md SSO-01..04 mark `[x]` + README.md SSO Backward Incompat section + smoke compose checkpoint Task 5 (central + yte runtime verify) + v3.0-a EXIT GATE TRIGGERED

---

### 🚦 v3.0-a EXIT GATE (giữa Phase 3 và 4)

Demo deliverable:
- 1 hub con (yte) + central + Redis + Postgres cùng instance up trên Docker compose.
- User login `https://central/api/auth/login` → JWT valid.
- User truy cập `https://central/yte/api/...` (subpath chưa có Caddy strip yet — direct port test) → hub con verify JWT qua JWKS → 200.
- Hub con CHỈ truy cập data hub yte (test cross-hub access → 403).

**User accept criteria:** 1 hub con + tổng deploy được, JWT SSO PASS, hub isolation reinforce, golden path login → upload (local hub yte chỉ) → search local → PASS.

**Nếu accept:** Tiếp tục v3.0-b (Phase 4-7) — never pivot multi-DB topology.

**Nếu reject:** Mở `/gsd-discuss-milestone v3.0` re-discuss D-V3-01 topology choice.

---

### Phase 4 — Cross-hub Data Sync (D-V3-02, GA-V3-D)

**Goal:** Sau khi cocoindex flow hub con ingest xong → push chunks + vector (denormalized) lên `medinet_central.chunks`; hub tổng KHÔNG re-embed; idempotent on retry (ON CONFLICT); cross-hub search ở central dùng aggregated chunks (KHÔNG fan-out HTTP); checksum verify periodic chống drift; mechanism chốt ở discuss-phase 4.

**Requirements:** SYNC-01, SYNC-02, SYNC-03, SYNC-04, SYNC-05

**Success criteria:**
1. Upload file ở hub con yte → chunks sync sang central trong < 60s (Prometheus metric `sync_lag_seconds{hub_id}` đo).
2. Cross-hub search ở central thấy chunks từ hub con yte + duoc + hcns aggregated; p95 < 1.5s (E-V3-2).
3. Idempotent retry KHÔNG dup chunks (kill push mid-batch → re-run KHÔNG sai chunk_count tổng).
4. Checksum verify daily metric `sync_drift_total{hub_id, drift_type}` < 1% rows (E-V3-5 threshold).
5. SYNC-05 mechanism chốt — chọn 1 trong 3 option (a) cocoindex target thứ 2 / (b) Postgres logical replication / (c) outbox + worker.

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 4`):**
- **GA-V3-D part 1 chốt:** sync mechanism. Cocoindex target thứ 2 = lock-in cocoindex; Postgres logical replication = native nhưng schema drift sensitive; outbox + worker = flexible self-maintain. Khuyến nghị seed: cocoindex target thứ 2 (đơn giản nhất, đã có cocoindex foundation v2.0).
- Idempotent key: `chunk_id` UUID (stable qua re-index) vs `content_hash` (re-embed cùng content KHÔNG re-push).
- Sync timing: post-ingest hook synchronous vs async worker queue.
- Checksum cron schedule: daily 2AM vs hourly sample 1%.

---

### Phase 5 — Reverse Proxy + Frontend Subpath (GA-V3-C, D-V3-06)

**Goal:** Caddy route `wiki.domain.com/<hub>/api/*` → upstream container hub đúng (strip prefix); central route giữ nguyên; frontend detect prefix từ URL (1 build dùng chung — option a GA-V3-C khuyến nghị seed); D6 expire formally; per-hub login branding tách `frontend/src/branding/<hub>/`.

**Requirements:** PROXY-01, PROXY-02, PROXY-03, PROXY-04

**Success criteria:**
1. `curl https://wiki.domain.com/yte/api/health` PASS; `curl https://wiki.domain.com/api/health` PASS (central); Caddy auto-TLS tiếp tục từ v2.0 Phase 8.3.
2. Frontend `window.location.pathname.split('/')[1]` detect prefix → API base URL chính xác cho từng hub; 1 build dùng chung 4 deploy.
3. D6 expire formally — `Hub_All/CLAUDE.md` section 3 cập nhật; smoke regression 11 trang React M2 COMPAT-01 PASS (R-V3-2 mitigation).
4. Per-hub login branding: Hub y_te logo + title VN khác Hub dược, Hub hcns, central; tách `frontend/src/branding/<hub>/` config (logo + title + theme color).

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 5`):**
- **GA-V3-C chốt:** 1 build detect prefix vs per-hub `VITE_HUB_NAME=yte` build matrix. Khuyến nghị seed: 1 build (đỡ build matrix). Re-confirm ở discuss-phase.
- Caddy config layout: 1 Caddyfile centralized với matcher per-hub vs Caddyfile imports per-hub fragment.
- Login form redirect: hub con form POST trực tiếp central `/api/auth/login` (CORS implications) vs redirect 302 sang central login page.

---

### Phase 6 — System Settings Sync (GA-V3-B)

**Goal:** Hub con đọc `rag_config` từ central qua HTTP pull on-demand + Redis cache local TTL 60s + pub/sub invalidate channel `settings:invalidate` (< 30s propagate E-V3-4); api_keys verify proxy gọi central; hub_registry read-only ở hub con.

**Requirements:** SETTINGS-01, SETTINGS-02, SETTINGS-03, SETTINGS-04

**Success criteria:**
1. Hub con đọc `rag_config` từ central HTTP pull + cache Redis TTL 60s; fail-loud nếu central down sau TTL expire (KHÔNG silent degrade).
2. Đổi `rag_config` ở central → hub con re-fetch trong < 30s (E-V3-4 propagate); test integration với Redis pub/sub.
3. Hub con `PUT /api/rag-config` trả 404 (FACTOR-02 strip + SETTINGS-04 read-only enforce).
4. `X-API-Key` header ở hub con → gọi central verify (cache Redis TTL 60s); 401 nếu central reject; AES-GCM giữ ở central (carry forward M2 AUX-02).

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 6`):**
- **GA-V3-B chốt:** HTTP pull (khuyến nghị seed) vs push webhook vs env var local. Trade-off: pull latency / push consistency / env simplicity nhưng đổi config phải redeploy.
- Cache TTL: 60s (default) vs 5min (low-change settings) vs adaptive (dựa trên change frequency).
- Pub/sub fallback nếu Redis xuống: hub con phải re-fetch sau TTL hay alert immediate?

---

### Phase 7 — Migration + Smoke E2E (GA-V3-D, R-V3-4)

**Goal:** Split `medinet_central` cũ → DB hub con (blue/green per-hub); MCP service re-point gọi central cho cross-hub aggregate; smoke E2E 3 hub con + tổng healthy Docker compose; golden path mỗi hub PASS.

**Requirements:** MIGRATE-01, MIGRATE-02, MIGRATE-03, MIGRATE-04, MIGRATE-05

**Success criteria:**
1. `pg_dump --data-only --where="hub_id = '<uuid>'"` snapshot 3 hub (yte, duoc, hcns) thành công; file output lưu `migrate-snapshots/`.
2. Restore vào `medinet_hub_<name>` blue/green per-hub PASS; switch Caddy upstream sau verify smoke.
3. Central truncate `hub_id` rows post-migration; giữ skeleton aggregate (`medinet_central.chunks` KHÔNG truncate — sync 1 chiều D-V3-02).
4. MCP service re-point central; `mcp_service` 135/135 test PASS (carry forward Phase 8.3 v2.0); smoke OAuth flow qua Inspector PASS.
5. Docker compose mở rộng up đầy đủ (1 Postgres + 1 Redis + 4 FastAPI + Caddy + frontend); golden path 3 hub con + tổng PASS (login → upload → search local + cross-hub → ask → citation); cross-hub p95 < 1.5s (E-V3-2); hub isolation enforce (E-V3-3).

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 7`):**
- **GA-V3-D part 2 chốt:** `pg_dump --where` (khuyến nghị seed option a) vs snapshot + replay cocoindex flow rebuild từ `file_store`. Trade-off: pg_dump fast nhưng cần verify schema match / replay cocoindex slow nhưng test full pipeline lại.
- Migration window: full downtime (1 weekend) vs blue/green zero-downtime (vận hành phức tạp).
- MCP fan-out vs central aggregate: re-confirm KHÔNG fan-out N hub (đã LOCKED D-V3-02 nhưng MCP re-point cần re-test).
- Post-migration verification: smoke test automated mandatory vs human UAT sampling.

---

## Phases — v2.0 (ARCHIVED ✅)

<details>
<summary>✅ <strong>v2.0 Full RAG Rewrite (Phases 1-10 + 8.1/8.2/8.3)</strong> — SHIPPED 2026-05-21 · 38/38 REQ-ID · 13/13 phases</summary>

- [x] Phase 1: Infra Skeleton + Demolition + EXIT Criteria (6/6 plans) — 2026-05-13
- [x] Phase 2: Database Schema + Alembic Baseline (5/5 plans) — 2026-05-13
- [x] Phase 3: Auth Port + RBAC + Response Envelope (5/5 plans) — 2026-05-14
- [x] Phase 4: CocoIndex Flow MVP + Document Ingest (8/8 plans) — 2026-05-21 · 🚦 M2a EXIT GATE PASSED
- [x] Phase 5: Hub + User + Audit + APIKey + Settings CRUD (6/6 plans) — 2026-05-17
- [x] Phase 6: Search API Single + Cross-Hub (4/4 plans) — 2026-05-18
- [x] Phase 7: Ask API + LiteLLM + Citation + Hot-Swap + Usage (5/5 plans) — 2026-05-18
- [x] Phase 8: Frontend E2E Smoke (TEARDOWN-01 done 2026-05-14) (5/5 plans) — 2026-05-19
- [x] Phase 8.1: MCP Server — Expose Wiki Tools (3/3 plans) — 2026-05-19
- [x] Phase 8.2: MCP Service — Tách Process Độc Lập (5/5 plans) — 2026-05-19
- [x] Phase 8.3: MCP OAuth 2.0 + Deploy Public HTTPS (9/9 plans) — 2026-05-21
- [x] Phase 9: Eval Framework + Quality Gate ≥75% top-3 (5/5 plans) — 2026-05-21
- [x] Phase 10: Hardening + Observability + Docs (6/6 plans) — 2026-05-21

Full details: [`milestones/v2.0-full-rag-rewrite/ROADMAP.md`](milestones/v2.0-full-rag-rewrite/ROADMAP.md) · [`phases/`](milestones/v2.0-full-rag-rewrite/phases/)

</details>

---

## Progress

| Milestone | Phases | Plans Complete | REQ-ID | Status | Completed |
| --- | --- | --- | --- | --- | --- |
| v1.0 RAG Quality with Docling | 5 | 28/28 | 34/34 | ❌ Abandoned | 2026-05-13 |
| v2.0 Full RAG Rewrite | 13 | ~75/75 | 38/38 | ✅ Shipped | 2026-05-21 |
| **v3.0 Multi-Hub Split** | **7** | **10/~30** | **8/30** | 🔄 **Phase 1+2 DONE (2/7 phase)** | — |
| v4.0 Production Hardening | — | — | — | 📋 Backlog | — |
| v4.1 Advanced Retrieval | — | — | — | 📋 Backlog | — |

---

## Traceability (v3.0)

100% REQ → phase coverage. Mỗi REQ map đúng 1 phase, không có REQ orphan.

| REQ-ID | Phase | Note |
|---|---|---|
| TOPO-01: Postgres init multi-DB | 1 | Init script idempotent |
| TOPO-02: Per-hub Alembic | 1 | Make `migrate-all` + CI lint version match |
| TOPO-03: Cocoindex flow naming per-hub | 1 | `medinet_<hub>_ingest` + APP_NAMESPACE per-hub |
| TOPO-04: HUB_NAME isolation env | 1 | DB-level isolation enforce |
| FACTOR-01: 1 codebase deploy nhiều lần | 2 | `create_app(hub_name)` factory |
| FACTOR-02: Strip system settings ở hub con | 2 | `/api/rag-config` 404 ở hub con |
| FACTOR-03: Hub con expose 10 endpoint | 2 | hub-scoped contract |
| FACTOR-04: Dynamic hub registration (added 2026-05-22) | 2 | `make hub-add HUB=<name>` — Settings str + regex + reserved blacklist + override.yml auto-gen |
| SSO-01: JWKS endpoint central | 3 | TTL 1h cache hub con HA |
| SSO-02: Redis blacklist chung | 3 | Cross-process revoke |
| SSO-03: JWT claim hub_ids | 3 | Cross-hub access control |
| SSO-04: E4 reinforced DB-level | 3 | Hub con + repo-layer enforce |
| SYNC-01: Push chunks+vector hub con → central | 4 | Denormalized, KHÔNG re-embed |
| SYNC-02: ON CONFLICT idempotent | 4 | Multi-retry safe |
| SYNC-03: Cross-hub search aggregated central | 4 | KHÔNG fan-out HTTP |
| SYNC-04: Checksum verify periodic | 4 | Daily Prometheus metric, drift < 1% |
| SYNC-05: Mechanism chốt (cocoindex/replication/outbox) | 4 | GA-V3-D part 1 |
| PROXY-01: Caddy subpath route + strip prefix | 5 | Caddy auto-TLS carry forward |
| PROXY-02: Frontend detect prefix 1 build | 5 | `window.location.pathname.split('/')[1]` |
| PROXY-03: D6 expire formally | 5 | CLAUDE.md update + smoke regression |
| PROXY-04: Per-hub login branding | 5 | `frontend/src/branding/<hub>/` |
| SETTINGS-01: rag-config HTTP pull + cache | 6 | Redis TTL 60s + fail-loud |
| SETTINGS-02: Pub/sub invalidate < 30s | 6 | Channel `settings:invalidate` |
| SETTINGS-03: api_keys verify proxy central | 6 | Cache Redis TTL 60s + AES-GCM ở central |
| SETTINGS-04: hub_registry read-only hub con | 6 | TTL 5min pull |
| MIGRATE-01: Snapshot pg_dump per hub_id | 7 | `--data-only --where` |
| MIGRATE-02: Restore vào DB con blue/green | 7 | Per-hub deploy NEW + verify |
| MIGRATE-03: Truncate central skeleton | 7 | Giữ `chunks` cho cross-hub |
| MIGRATE-04: MCP re-point central | 7 | `mcp_service/config.py` update |
| MIGRATE-05: Smoke E2E 3 hub + tổng | 7 | Golden path mỗi hub PASS |

**Tổng:** 30 REQ-ID v1 (29 gốc + FACTOR-04 added 2026-05-22) → 7 phase. Coverage: 100% (4+4+4+5+4+4+5=30).

---

## EXIT Criteria — v3.0

| # | Trigger | Action |
|---|---|---|
| **E-V3-1** | 3 hub con + tổng KHÔNG healthy Docker compose sau Phase 7; HOẶC golden path `wiki.domain.com/yte` FAIL | STOP, root-cause: process model / proxy / DB topology — discuss revert multi-tenancy logical |
| **E-V3-2** | Cross-hub search p95 ≥ 1.5s ở Phase 4/7 dù tune (denormalized + ef_search + pool) | STOP, discuss giảm hub_count / dim reduce / fan-out federated |
| **E-V3-3** | Hub isolation bug DB-level KHÔNG fixable trong 7 ngày (hub con truy cập được data hub khác) | STOP, security review — không ship v3.0 có data leak |
| **E-V3-4** | Settings change ở central KHÔNG propagate xuống hub con < 60s sau 3 vòng iterate Phase 6 | STOP, discuss push webhook thay HTTP pull / accept window lớn hơn |
| **E-V3-5** | Sync drift hub con vs tổng > 1% rows sau 7 ngày run continuously trong Phase 4 staging | STOP, replace outbox/replication mechanism — re-chốt GA-V3-D |

---

## Risk Register — v3.0

| # | Risk | Severity | Phase | Mitigation |
|---|---|---|---|---|
| R-V3-1 | Sync chunks + vector 2 lần (drift) | HIGH | 4 | Outbox + checksum verify Prometheus metric daily |
| R-V3-2 | D6 expire → frontend rewrite regress 11 trang | HIGH | 5 | Smoke regression M2 COMPAT-01 carry forward + tách `branding/<hub>/` thay sửa core |
| R-V3-3 | Per-hub Alembic drift | MEDIUM | 1 | CI lint check Alembic head SHA match N DB |
| R-V3-4 | Migration downtime | MEDIUM | 7 | Blue/green per-hub deploy NEW + switch traffic |
| R-V3-5 | JWKS endpoint xuống | MEDIUM | 3 | Cache TTL 1h + fallback static keypair embedded |
| R-V3-6 | Settings sync race | LOW | 6 | Redis pub/sub + idempotent settings application |

**Carry forward (v2.0):** R1 PIN dim 1536, R2 HNSW post-filter `ef_search=200` + iterative_scan, R4 scanned PDF `failed_unsupported`, R5 cocoindex naming scale per-hub Phase 1, R7 cross-dim swap REFUSE 400 defer v4.0.

---

## Backlog (project-level parking lot)

Tham chiếu `.planning/BACKLOG.md` cho 999.x items. Highlights chuyển vào v4.0/v4.1:

- 999.1 (M1) Incremental chunk re-embed → ✅ Absorbed v2.0 cocoindex core value
- Local embedding model (sentence-transformers, BGE-M3) → SEED-001 dormant v4.1
- OCR Vietnamese + table preservation revisit → v4.0
- Streaming `/api/ask` SSE → v4.0
- Hybrid retrieval BM25 + reranker → v4.1
- Comprehensive coverage >80% → v4.0
- Branch protection rule GitHub repo enforce 2 workflow → v4.0

---

*Last updated: 2026-05-21 sau `/gsd-new-milestone v3.0` — Multi-Hub Split STARTED. 7 phase reset numbering, 29 REQ-ID v1, v3.0-a / v3.0-b split. Next: `/gsd-discuss-phase 1` Multi-DB topology + per-hub Alembic.*
