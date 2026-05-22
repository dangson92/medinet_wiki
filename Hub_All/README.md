# Medinet Wiki — Hub_All (M2 Full RAG Rewrite)

> Mã dự án: **MEDWIKI** · Milestone: **v2.0 — Full RAG Rewrite** · Trạng thái: **M2 closeout đang đóng — Phase 10 ship 4/6 plan**

Hệ thống quản lý tri thức nội bộ đa-Hub (y tế / dược / HCNS) cho Medinet — kết hợp wiki truyền thống với RAG (Retrieval Augmented Generation), expose qua MCP cho AI agent. `Hub_All/` là kho chứa toàn bộ source (backend API + MCP service + frontend SPA + eval framework + planning docs) trước khi tách deploy ở milestone v3.0 (Multi-Hub Split).

---

## Stack

### Backend API (`api/`)
- **Python 3.12** · `uv` package manager
- **FastAPI 0.136.1** + Uvicorn 0.46 (ASGI server)
- **CocoIndex 1.0.3** — RAG indexing dataflow (extract → chunk → embed → upsert), incremental diff content-hash, Rust core
- **pgvector pg16** — vector store (HNSW cosine 1536-dim, `pgvector/pgvector:pg16` image)
- **asyncpg 0.30** + **SQLAlchemy 2.0 async** + **Alembic 1.18** — DB layer
- **Redis 7** — cache (search) + rate limit (slowapi) + audit log queue
- **LiteLLM** — embedding + LLM hot-swap (OpenAI / Gemini, 1536-dim pinned)
- **structlog 25** (Plan 10-01) + **prometheus-client 0.23** (Plan 10-02) — observability
- **PyJWT (RS256)** + **pwdlib (Argon2)** — auth

### MCP Service (`mcp_service/`)
- Tiến trình **độc lập** (port 8190), gọi API qua HTTP `X-API-Key` hoặc OAuth 2.0
- MCP Python SDK + httpx, KHÔNG truy cập trực tiếp DB/Redis/cocoindex
- Phase 8.3: OAuth 2.0 (Authorization Server + Resource Server) + Caddy auto-TLS public HTTPS
- Phase 10-04: `MultiPolicyCORSMiddleware` tách metadata wildcard vs sensitive whitelist (CRIT-01)

### Frontend (`frontend/`)
- **React 19 · Vite 6 · TypeScript 5.8 · Tailwind v4**
- Context API (`AuthContext`, `ThemeContext`) + tập trung `services/api.ts`
- D6: **KHÔNG sửa trong M2** — URL `/api/*` giữ nguyên qua FastAPI port 8180 (Hyper-V excluded range 8038-8137)

### Infra (Docker Compose 4-service + Caddy)
- `postgres` (pgvector pg16) · `redis` (7-alpine) · `python-api` (FastAPI) · `mcp_service` (MCP standalone) · `caddy` (reverse proxy auto-TLS Phase 8.3)

---

## Quickstart (dev)

```bash
cd Hub_All

# 1. Copy file .env mẫu
cp api/.env.example api/.env
cp mcp_service/.env.example mcp_service/.env

# 2. Sinh JWT keypair RS256 PKCS#8 (KHÔNG commit .pem)
make api-keys

# 3. Boot stack 4-service (postgres + redis + python-api + mcp_service + caddy)
make up

# 4. Health check + metrics
curl http://localhost:8180/healthz
curl http://localhost:8180/readyz
curl http://localhost:8180/metrics
```

Stop stack: `make down`. Logs follow: `make logs`.

---

## Test

```bash
# Critical path mandatory (HARD-03 gate)
cd Hub_All/api
uv run pytest -m critical

# Toàn bộ unit + integration (testcontainers Postgres pgvector pg16 + Redis 7)
uv run pytest

# Coverage gate Plan 10-03 (≥50% trên 17 file critical path)
uv run pytest tests/integration/test_critical_path_coverage.py \
    --cov --cov-config=.coveragerc-critical \
    --cov-report=term-missing --cov-fail-under=50
```

### MCP Service test (respx mock HTTP, KHÔNG cần Postgres/Redis)

```bash
cd Hub_All/mcp_service
uv run pytest -q
```

---

## Eval (Phase 9 EVAL framework)

```bash
cd Hub_All
make eval-install   # cài deps Python eval (1 lần)
make eval-seed      # seed eval_hub (1 lần)
make eval-smoke     # smoke regression < 60s (mock embedding, KHÔNG cần OPENAI_API_KEY)
make eval-all       # gate verdict ≥75% top-3 (cần OPENAI_API_KEY thật ~$0.20/run)
make eval-report    # tái sinh EVAL.md từ results.json
```

Quality gate: top-3 recall **≥ 75%** PASS · `60-75%` FAIL borderline → iterate 3 vòng chunker/prompt · `<60%` FAIL E5 → STOP M2b (xem PROJECT.md EXIT criteria).

---

## Observability (Plan 10-01 + 10-02)

- **`GET /metrics`** — Prometheus exposition format (OpenMetrics text `version=1.0.0`). 5 metric:
  - `requests_total{method,path,status}` Counter
  - `errors_total{method,path}` Counter (status ≥ 500)
  - `request_duration_seconds{method,path}` Histogram
  - `search_latency_seconds{hub_scope}` Histogram (single / cross)
  - `ingest_duration_seconds` Histogram (per-doc cocoindex)
- **structlog JSON** stdout (Docker capture native). Schema 10 field match Go `log/slog`:
  - `{level, msg, ts, request_id, user_id, hub_id, latency_ms, path, method, status}`
- **`X-Request-Id`** middleware (UUID4 sinh nếu client KHÔNG gửi) — propagate xuống cocoindex BackgroundTask qua ContextVar + `asyncio.create_task` copy_context.

---

## Documentation

| File | Nội dung |
|------|----------|
| `DEPLOY.md` | Production deploy + backup + restore + observability + security checklist |
| `CLAUDE.md` | Hướng dẫn AI assistant (Claude Code) làm việc với repo |
| `.planning/PROJECT.md` | Core value + risk register R1-R7 + EXIT criteria E1-E5 |
| `.planning/REQUIREMENTS.md` | 38 REQ-ID M2 + traceability table |
| `.planning/ROADMAP.md` | 10 phase + plan status + critical path |
| `.planning/STATE.md` | Trạng thái phase/plan hiện tại + decisions + blockers |
| `.planning/CONVENTIONS.md` | Test strategy + naming + namespace + middleware order + logging fields |
| `.planning/seeds/v3.0-multi-hub-split.md` | Seed milestone tiếp theo (Multi-Hub Split, 4 decision LOCKED 2026-05-21) |

---

## Add a new hub (dynamic registration — FACTOR-04 Plan 02-05)

Thêm hub mới (vd `phap_che`, `marketing`) hoàn chỉnh bằng 1 lệnh — KHÔNG sửa code Python / `docker-compose.yml` base:

```bash
# 1. Đảm bảo postgres + redis up
docker compose up -d postgres redis

# 2. Tạo hub mới (DB + ext vector + alembic + compose service block)
make hub-add HUB=phap_che              # auto-detect port (8184 trở lên)
# HOẶC explicit port:
make hub-add HUB=phap_che PORT=8200

# 3. Build + up service mới
docker compose up -d python-api-phap_che

# 4. Verify health
curl http://localhost:<port>/api/health
# Expected: {"success":true,"data":{"status":"ok"},...}
```

**Validation rules:**
- Pattern hub name: `^[a-z][a-z0-9_]{0,15}$` (lowercase a-z bắt đầu, max 16 char, a-z0-9_ rest — KHÔNG hyphen/uppercase).
- Reserved name reject: `postgres`, `cocoindex`, `template0`, `template1`, `public`, `medinet` (Postgres system collision).
- `central` reject (aggregator special-case đã có sẵn).

**Phía sau hậu trường:**
- `make hub-add` → `scripts/hub-add.sh` validate format + reserved + duplicate.
- Call `scripts/hub-init.sh` (Phase 1 ship) — `CREATE DATABASE medinet_hub_<name>` + `CREATE EXTENSION vector` + HNSW verify + `alembic upgrade head`.
- Sed substitute `docker-compose.override.yml.template` → append `docker-compose.override.yml` (gitignored — operator-local).
- Docker compose tự merge `docker-compose.yml` base + override khi `up`.

**Cleanup hub mới:**
```bash
docker compose stop python-api-<name>
docker compose rm -f python-api-<name>
psql -h localhost -U medinet -d postgres -c "DROP DATABASE IF EXISTS medinet_hub_<name>"
# Manual edit docker-compose.override.yml — xoá block python-api-<name> + volume medinet_cocoindex_<name>
docker volume rm medinet_cocoindex_<name>
```

Reverse script (`hub-remove.sh`) defer v3.0-b (Phase 7 MIGRATE-03 sẽ ship tooling truncate central skeleton).

**Hub registry source-of-truth (long-term):** Phase 6 SETTINGS-04 sẽ ship `hub_registry` table ở `medinet_central` — central admin CRUD; hub con đọc TTL cache. Hiện Plan 02-05 chỉ validate format Settings + sinh compose block — operator phải manual track danh sách hub đã add.

---

## v3.0 Auth SSO deployment notes (Phase 3 ship 2026-05-22)

Phase 3 ship SSO infrastructure mới (JWKS endpoint + cache + JWT claim refactor + Redis blacklist key rename + 307 redirect hub con login/refresh + E4 reinforced 3-layer). **Backward incompat — User cần re-login sau khi deploy.**

### Backward incompat warning (TRIPLE cumulative)

JWT M2 cũ KHÔNG có `kid` header + `aud` claim + `hub_ids` claim → reject 401 sau Phase 3 deploy. User re-login forced ~15-30s downtime.

Plan 03-02 + 03-03 add 3 yêu cầu mới cho JWT:

1. **Header `kid`** (Plan 03-02 D-V3-Phase3-B): JWT phát hành sau Plan 03-02 có header `kid` = SHA-256 8-byte PEM (base64url unpadded, 11 char). Hub con dùng kid để match public key trong JWKSCache. M2 cũ JWT KHÔNG có kid → hub con verify fail `401 INVALID_TOKEN` (`"Token thiếu kid header — JWT phát hành trước Phase 3 SSO, vui lòng đăng nhập lại"`).
2. **Claim `aud=["medinet-wiki"]`** (Plan 03-03 D-V3-Phase3-E): PyJWT strict audience check ở `verify_token` + `verify_token_with_key`. M2 cũ JWT KHÔNG có aud → `401 InvalidAudienceError`.
3. **Claim `hub_ids: list[str]`** REQUIRED (Plan 03-03 D-V3-Phase3-E): JWTClaims pydantic validate REQUIRED (KHÔNG default empty M2). M2 cũ JWT KHÔNG có hub_ids → `401 Claims không hợp lệ`.

Ngoài ra, frontend M2 hiện tại hardcode `/api/auth/login` same-origin POST → ở hub con sẽ FAIL (Plan 03-04 đã refactor backend trả 307 nhưng frontend chưa wire `<form action="https://central/api/auth/login">`). Defer Phase 5 PROXY-02 sau D-V3-06 D6 expire chính thức.

### Operator pre-deploy checklist (30 phút advance)

1. **Broadcast user re-login** qua Slack/Email banner:

   > "Hệ thống Medinet Wiki vừa nâng cấp SSO (Phase 3 v3.0 Multi-Hub Split). Vui lòng đăng xuất + đăng nhập lại để nhận token mới. Phiên hiện tại sẽ tự động hết hạn trong vài phút. Mọi tài liệu đã upload + lịch sử search KHÔNG ảnh hưởng. Dự kiến downtime: 15-30 giây."

2. **Verify central RS256 keypair PKCS#8** còn tồn tại (Plan 03-01 reuse M2 baseline — KHÔNG sinh lại):

   ```bash
   ls -la api/keys/private.pem api/keys/public.pem
   # Nếu mất: cd api && make keys  (CẢNH BÁO: rotation = mọi JWT cũ revoke ngay)
   ```

3. **Verify Redis instance** up (cross-process blacklist `auth:blacklist:{jti}` Plan 03-03):

   ```bash
   docker compose ps redis
   docker compose exec redis redis-cli PING  # Expect PONG
   ```

4. **Verify central reachable** từ 3 hub con qua Docker network `medinet_net` (intra-network DNS resolve `python-api-central:8080`):

   ```bash
   docker compose exec python-api-yte ping -c 1 python-api-central
   ```

### Deploy steps (Phase 3 v3.0)

1. **Backup database** (M2 baseline carry forward — KHÔNG schema migration Phase 3):

   ```bash
   docker exec medinet-postgres pg_dumpall -U medinet > backup-pre-phase3-$(date +%Y%m%d).sql
   ```

2. **Update env** `CENTRAL_JWKS_URL` + `CENTRAL_URL` cho 3 hub con (docker-compose.yml ship sẵn — operator override.yml override nếu cần):

   ```bash
   # docker-compose.yml đã có sẵn 3 hub con env:
   # CENTRAL_JWKS_URL: http://python-api-central:8080/.well-known/jwks.json
   # CENTRAL_URL: http://python-api-central:8080
   ```

3. **Restart central first** → verify `GET /.well-known/jwks.json` 200 trước khi restart hub con (R-V3-5 boot dependency):

   ```bash
   docker compose up -d --force-recreate python-api-central
   sleep 10  # đợi lifespan startup (asyncpg pool + redis + cocoindex + JWT keypair load)
   curl http://localhost:8180/.well-known/jwks.json | jq .
   # Expect: {"keys":[{"kty":"RSA","kid":"<11-char>","use":"sig","alg":"RS256","n":"...","e":"AQAB"}]}
   ```

4. **Restart 3 hub con song song** → verify lifespan log "JWKSCache fetched N keys":

   ```bash
   docker compose up -d --force-recreate python-api-yte python-api-duoc python-api-hcns
   sleep 15  # đợi lifespan blocking fetch_initial 5s timeout × 3 hub
   docker logs medinet-api-yte 2>&1 | grep -E "lifespan_jwks_cache_ready|jwks_cache_updated"
   # Expect:
   #   lifespan_jwks_cache_ready: hub_name=yte url=http://python-api-central:8080/.well-known/jwks.json refresh_interval=3600s
   #   jwks_cache_updated: kids=['<kid>'] last_refresh_ts=<ts>
   ```

5. **Verify hub con `GET /api/auth/me`** với Bearer JWT mới 200 (verify path JWKSCache + Redis blacklist):

   ```bash
   # Login central
   TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
     -d '{"email":"admin@medinet.vn","password":"<password>"}' \
     http://localhost:8180/api/auth/login | jq -r '.data.access_token')

   # Verify hub yte accept JWT mới qua JWKSCache verify path
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8181/api/auth/me | jq .
   # Expect: 200 nếu user có hub_ids chứa "yte"
   #         403 CROSS_HUB_ACCESS_DENIED nếu user chỉ có hub khác (E4 reinforced)
   ```

6. **Verify hub con strip JWKS** (FACTOR-02 enforce — Plan 03-01 mount conditional):

   ```bash
   curl -o /dev/null -w "%{http_code}\n" http://localhost:8181/.well-known/jwks.json
   # Expect: 404
   ```

7. **Verify hub con 307 redirect login** (D-V3-Phase3-G):

   ```bash
   curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" \
     -X POST -H "Content-Type: application/json" \
     -d '{"email":"u@m.vn","password":"x"}' \
     http://localhost:8181/api/auth/login
   # Expect: 307 http://python-api-central:8080/api/auth/login
   ```

8. **Verify old session reject** 401 (expected behavior — confirm backward incompat working):

   ```bash
   OLD_TOKEN="<M2_jwt_token_pre_phase3>"
   curl -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $OLD_TOKEN" http://localhost:8181/api/auth/me
   # Expect: 401 (thiếu kid header HOẶC aud HOẶC hub_ids)
   ```

### Endpoint mapping mới (Phase 3 Plan 03-04 SSO-02)

| Endpoint | Central (port 8180) | Hub yte/duoc/hcns (port 8181-8183) |
|---|---|---|
| `POST /api/auth/login` | Handle local (M2 path) | **307 Location: `{CENTRAL_URL}/api/auth/login`** |
| `POST /api/auth/refresh` | Handle local (M2 path) | **307 Location: `{CENTRAL_URL}/api/auth/refresh`** |
| `POST /api/auth/logout` | Handle local (blacklist Redis chung) | Handle local (blacklist Redis chung — central thấy ngay < 1s) |
| `GET /api/auth/me` | Handle local | Handle local (verify JWT qua JWKSCache + Redis blacklist) |
| `GET /.well-known/jwks.json` | **200 JWK Set RFC 7517** | 404 envelope (FACTOR-02 strip) |

### Cross-hub isolation enforcement (SSO-04 E4 reinforced 3-layer)

Plan 03-03 thêm dependency `get_current_user_for_hub_access` — Layer 3 defense-in-depth:

- **Layer 1 (Phase 1 Plan 01-02):** DB-level `_enforce_hub_dsn_match` Settings validator — hub con KHÔNG kết nối DB hub khác.
- **Layer 2 (M2 carry forward):** Repository layer `WHERE hub_id = settings.hub_name` query-time filter.
- **Layer 3 (Plan 03-03 MỚI):** Dependency check `HUB_NAME in JWT.hub_ids` → reject `403 CROSS_HUB_ACCESS_DENIED` nếu mismatch.

**Example:** Stale JWT compromised từ user duoc (`hub_ids=["duoc"]`) post tới hub yte API:

```bash
TOKEN="eyJ..."  # Stale JWT hub_ids=["duoc"]
curl -H "Authorization: Bearer $TOKEN" http://localhost:8181/api/profile
# Expect: 403 {"success":false,"error":{"code":"CROSS_HUB_ACCESS_DENIED","message":"Token KHÔNG có quyền truy cập hub 'yte' (hub_ids JWT = ['duoc'])"}}
```

### Rollback procedure (nếu deploy fail)

```bash
# 1. Stop services
docker compose down

# 2. Revert commit Plan 03-01..05 (xem git log --grep "(03-0")
git checkout <commit-pre-phase-3-sha>

# 3. Re-build + restart 4 service
docker compose build python-api-central python-api-yte python-api-duoc python-api-hcns
docker compose up -d

# 4. Clear Redis blacklist keys mới (auth:blacklist:* prefix Plan 03-03)
docker compose exec redis redis-cli --scan --pattern 'auth:blacklist:*' | xargs -r docker compose exec -T redis redis-cli DEL

# 5. (Optional) Restore database backup nếu cần — KHÔNG bắt buộc vì Phase 3 KHÔNG migration schema
# psql -U medinet -d medinet_central < backup-pre-phase3-<date>.sql
```

Phase 3 KHÔNG Alembic migration schema — rollback chỉ revert source code + restart container + clear Redis prefix mới → JWT M2 cũ valid lại.

### v3.0-a EXIT GATE preview (giữa Phase 3-4)

🚦 **v3.0-a EXIT GATE TRIGGERED 2026-05-22** sau Plan 03-05 close. Demo deliverable list:

1. 1 hub con (yte) + central + Redis + Postgres deploy được trên Docker compose.
2. User login `https://central/api/auth/login` → JWT valid (có kid + aud + hub_ids).
3. User truy cập `https://central/yte/api/...` (direct port test trước Caddy lên Phase 5) → hub con verify JWT qua JWKSCache → 200.
4. Hub con CHỈ truy cập data hub yte (test cross-hub access → 403 CROSS_HUB_ACCESS_DENIED).
5. Golden path: login → upload (local hub yte chỉ) → search local → PASS.

**Smoke runtime defer Phase 7 MIGRATE-05 full E2E** (3 hub + central golden path + JWT SSO live). Evidence chain in-process: Plan 03-01..04 ship 65+ unit + 6 integration test PASS đã cover semantic SSO-01..04 + `docker compose config --quiet` base PASS.

**User accept criteria → tiếp tục v3.0-b (Phase 4 trigger):** 1 hub con + tổng deploy được, JWT SSO PASS, hub isolation reinforce, golden path PASS. **User reject → re-discuss D-V3-01 topology choice** qua `/gsd-discuss-milestone v3.0`.

### Reference

- `.planning/phases/03-auth-sso-hub-ids-jwt/03-CONTEXT.md` — 8 decision LOCKED D-V3-Phase3-A..H.
- `.planning/phases/03-auth-sso-hub-ids-jwt/03-{01..05}-PLAN.md` — Implementation detail per plan.
- `.planning/phases/03-auth-sso-hub-ids-jwt/03-{01..05}-SUMMARY.md` — Deliverable + commit + test count per plan.
- `.planning/REQUIREMENTS.md` § SSO-01..04 — REQ-ID spec + Phase 3 closeout note.
- `Hub_All/CLAUDE.md` section 6 — v3.0 progress + Phase 3 SSO pattern subsection.

---

## Cross-hub Sync Deploy Notes (Phase 4 v3.0)

Phase 4 ship cross-hub data sync infrastructure — chunks + vector denormalized push từ hub con → central qua **outbox + worker pattern** (D-V3-Phase4-A1 LOCKED). 7 plan ship 2026-05-22 SYNC-01..05 + 9 D-V3-Phase4-A1..D3 LOCKED consumed + 6 Prometheus metric infrastructure.

### Architecture

Hub con cocoindex flow `index_document` ingest chunks → Postgres trigger `enqueue_sync_outbox` AFTER INSERT/DELETE chunks atomic cùng transaction → `sync_outbox` table local (per-hub-con) → in-process asyncio worker hub con lifespan poll batch 100/5s + SELECT FOR UPDATE SKIP LOCKED concurrency-safe + push central qua asyncpg pool (`central_sync_pool`) `ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT FROM EXCLUDED.content_hash` 1 SQL atomic idempotent.

Central checksum scheduler (FastAPI lifespan asyncio task) tick daily 2AM `COUNT(*)` per hub vs central → `sync_count_drift{hub_name}` gauge + hourly `TABLESAMPLE BERNOULLI(1)` chunks created last 1h → content_hash diff → `sync_hash_drift{hub_name, drift_type}` counter. Admin `POST /api/sync/replay` endpoint reset dead rows manual recovery.

### Env vars mới (operator MUST set trước `docker compose up`)

**Hub con (yte/duoc/hcns/dynamic FACTOR-04):**

| Env | Required | Format | Note |
|-----|----------|--------|------|
| `HUB_YTE_ID` | ✅ | UUID4 | Khớp `medinet_central.hubs.id` row UUID — Phase 7 MIGRATE-01 sẽ centralize. v3.0-b operator export manual |
| `HUB_DUOC_ID` | ✅ | UUID4 | Tương tự |
| `HUB_HCNS_ID` | ✅ | UUID4 | Tương tự |
| `CENTRAL_SYNC_DSN` | ✅ (hub con) | asyncpg DSN tới `medinet_central` | Hardcoded ở docker-compose 3 hub con; production deploy qua secrets backing |
| `SYNC_BATCH_SIZE` | optional | int (default 100) | Worker claim batch size — operator tune sau observe metrics |
| `SYNC_POLL_INTERVAL` | optional | float seconds (default 5.0) | Idle sleep khi outbox empty |
| `SYNC_MAX_ATTEMPTS` | optional | int (default 5) | Mark dead sau N attempts |
| `SYNC_BACKOFF_SECONDS` | optional | CSV "1,5,30,120" (length = MAX_ATTEMPTS-1) | Exp backoff retry seconds |

**Central:**

| Env | Required | Format | Note |
|-----|----------|--------|------|
| `CHECKSUM_HUB_DSNS_JSON` | optional | JSON dict `{"yte":"asyncpg DSN read-only","duoc":"..."}` | Central checksum scheduler connect tới N hub con; empty/None → scheduler no-op (deploy lần đầu CHƯA register hub con) |

### Export env shell example

```bash
export HUB_YTE_ID="00000000-0000-0000-0000-000000000001"
export HUB_DUOC_ID="00000000-0000-0000-0000-000000000002"
export HUB_HCNS_ID="00000000-0000-0000-0000-000000000003"
export CHECKSUM_HUB_DSNS_JSON='{"yte":"postgresql+asyncpg://medinet_ro:medinet@postgres:5432/medinet_hub_yte","duoc":"postgresql+asyncpg://medinet_ro:medinet@postgres:5432/medinet_hub_duoc","hcns":"postgresql+asyncpg://medinet_ro:medinet@postgres:5432/medinet_hub_hcns"}'
docker compose up -d
```

### Per-hub Alembic migration

Apply migration 0005 (sync_outbox per-hub):
```bash
cd api
make migrate-all  # apply 4 DB sequentially: central + yte + duoc + hcns
# rev 0005 SKIP central runtime guard (sync_outbox per-hub-only — current_database() check)
alembic -x hub=yte current  # expect rev "0005" (head)
alembic current             # expect rev "0005" (central — guard skip nhưng vẫn ghi rev alembic_version table)
```

### Prometheus metrics mới

Scrape `/metrics` endpoint central + hub con — 6 metric mới (label `hub_name` bounded ~240 series):

- `sync_lag_seconds{hub_name}` (histogram) — outbox.created_at → central INSERT processed_at lag
- `sync_outbox_pending{hub_name}` (gauge) — current pending count
- `sync_attempt_total{hub_name, status=success|fail}` (counter) — cumulative attempts
- `sync_dead_total{hub_name, error_class=network|timeout|conflict|unknown}` (counter) — cumulative dead rows
- `sync_count_drift{hub_name}` (gauge) — daily ratio diff symmetric `abs(diff) / max(hub_count, 1)`
- `sync_hash_drift{hub_name, drift_type=mismatch|missing}` (counter) — hourly TABLESAMPLE diff

Recommended AlertManager rules (defer Phase 7 deploy guide):

- `sync_count_drift > 0.01` sustained 7 days → STOP (E-V3-5 trigger)
- `sync_hash_drift_total > 0` increase last 1h → Slack alert
- `sync_dead_total` increase rate > 0 → Slack alert (1 hub con sync fail systematic)

### Admin replay endpoint

```bash
# Replay dead rows trong sync_outbox hub yte since 2026-05-22 (manual recovery sau khi fix root cause)
curl -X POST https://central.medinet.vn/api/sync/replay \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{"hub_id":"yte","since":"2026-05-22T00:00:00Z"}'

# Response D6 envelope:
# {"success":true,"data":{"hub_id":"yte","replayed_count":42,"since":"2026-05-22T00:00:00+00:00"},"error":null,"meta":null}
```

Endpoint chỉ available ở central (FACTOR-02 extend — hub con strip → 404 NOT_FOUND envelope). Require admin role (Phase 3 SSO-04 `require_role("admin")` dependency carry forward). Reset 4 field dead row atomic (`status='pending', attempt_count=0, last_error=NULL, next_retry_at=NULL`) WHERE status='dead' AND created_at >= since → worker re-pickup. audit_logs INSERT non-repudiation `action='sync.replay'` ghi lại operator + hub_id + since (W8 fix T-04-06-03 reinforced).

### Cross-hub search behavior change

Hub con `POST /api/search/cross-hub` → **404 NOT_FOUND envelope** (FACTOR-02 extend Plan 04-05 D-V3-Phase4-D3). Frontend M2 hardcode same-origin sẽ FAIL ở hub con cho tới Phase 5 PROXY-02 wire base URL detect prefix (D-V3-06 D6 expire formally).

Central `POST /api/search/cross-hub` giữ behavior M2 — public API `SearchService.search_cross_hub(*, body, user)` signature unchanged (backward compat M2 ask_service.py + frontend api.ts crossHubSearch). Implementation refactor 1 SQL aggregated `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector LIMIT $3` thay fan-out `asyncio.gather(*[_search_one(h) for h in hub_ids])` N task (D-V3-Phase4-D1). HNSW `iterative_scan=relaxed_order` + `ef_search=200` + `max_scan_tuples=20000` SET LOCAL session tuning carry forward M2 Phase 6. Re-rank tự nhiên qua SQL ORDER BY (KHÔNG Python merge sort).

### Rollback procedure

Nếu sync drift > 1% sustained 7 days (E-V3-5 trigger):

1. **Stop worker hub con:** `docker compose stop python-api-yte python-api-duoc python-api-hcns`
2. **Verify outbox state:**
   ```bash
   psql -d medinet_hub_yte -c "SELECT status, COUNT(*) FROM sync_outbox GROUP BY status"
   ```
3. **Replay dead rows:** `POST /api/sync/replay { hub_id, since: <root-cause-fix-date> }` (xem section trên).
4. **Resume worker:** `docker compose start python-api-yte python-api-duoc python-api-hcns`
5. **Re-discuss GA-V3-D mechanism** (xem `.planning/PROJECT.md` EXIT criteria E-V3-5) nếu drift recurring nhiều lần — có thể chuyển sang Postgres logical replication hoặc cocoindex target thứ 2 (option a/b GA-V3-D đã REJECT 2026-05-22 nhưng có thể revisit nếu evidence chain outbox+worker insufficient).

### Reference

- `.planning/phases/04-cross-hub-data-sync/04-CONTEXT.md` — 9 D-V3-Phase4-A1..D3 LOCKED 2026-05-22.
- `.planning/phases/04-cross-hub-data-sync/04-{01..07}-PLAN.md` — 7 plan implementation chi tiết.
- `.planning/phases/04-cross-hub-data-sync/04-{01..07}-SUMMARY.md` — deliverable + commit + test per plan.
- `.planning/REQUIREMENTS.md` § SYNC-01..05 — REQ-ID spec + Phase 4 closeout note.
- `Hub_All/CLAUDE.md` section 6 — v3.0 progress + Phase 4 Cross-hub Data Sync pattern subsection.

---

## Milestone status

- ✅ **M2 v2.0 — Full RAG Rewrite** đang đóng (Phase 1-10, 38/38 REQ-ID done, M2a EXIT GATE PASS).
- 🟢 **Phase 10 (Hardening + Observability + Docs)** ship 4/6 plan: HARD-01 structlog · HARD-02 Prometheus · HARD-03 critical path + coverage ≥50% · CRIT-01 CORS split. Còn HARD-04 (plan này) + CI workflow (10-06).
- 🔜 **Next milestone:** v3.0 — Multi-Hub Split (subpath routing, multi-DB, cocoindex flow per-hub đẩy chunks+vector lên hub tổng). Seed `.planning/seeds/v3.0-multi-hub-split.md` (4 architectural decision LOCKED 2026-05-21).

---

*README cập nhật: 2026-05-21 (Plan 10-05 — HARD-04 docs closeout). Trước đó README đã rỗng (Go cũ xoá TEARDOWN-01 pull-in 2026-05-14).*
