# Deploy guide — Medinet Wiki Hub_All M2

> Mã dự án: **MEDWIKI** · Milestone: **v2.0 Full RAG Rewrite** · HARD-04 Plan 10-05 (Phase 10 hardening + docs).

Tài liệu này hướng dẫn ops triển khai stack Python `Hub_All` lên production: prerequisites, quickstart, .env config, backup/restore, observability, security checklist, M2 closeout summary.

---

## 1. Prerequisites

### Tooling
- **Docker 24+** + **Docker Compose v2** (chuẩn chạy production)
- (Optional native) **Python 3.12** + **uv** (Astral) nếu chạy `uvicorn` native (không Docker build)
- **psql 16+** client để chạy `make eval-seed` và `pg_dump` backup
- **OpenSSL** để sinh JWT RS256 keypair (`make api-keys`)

### Resource minimum
- **RAM:** 4GB tối thiểu (cocoindex Rust core init + LMDB fingerprint memo + 2 DB Postgres + Redis)
- **Disk:** 10GB cho `medinet_pgdata/` + `file_store/` + `.cocoindex/` LMDB + backup rotation 30 ngày
- **Network:** Port 80/443 mở ra Internet nếu dùng Caddy auto-TLS (Phase 8.3); fallback Cloudflare Tunnel zero-port nếu không mở được port 80/443.

### Services bắt buộc
- **Postgres 16** image `pgvector/pgvector:pg16` — **KHÔNG** dùng `postgres:16-alpine` (sẽ FAIL `CREATE EXTENSION vector`).
- **Redis 7** — cache search + rate limit slowapi + audit log queue.

### Credentials cần chuẩn bị
- **OpenAI API key** tier paid (model `text-embedding-3-large@1536` + `gpt-4o-mini`). Chi phí eval gate verdict ~$0.20/run cho 10 file × 25 chunk.
- **Gemini API key** (fallback hot-swap LiteLLM).
- **Domain public HTTPS** cho MCP Service (Phase 8.3 Claude web connector yêu cầu HTTPS + OAuth 2.0, KHÔNG accept `X-API-Key`).

---

## 2. Quickstart deploy

```bash
cd Hub_All

# 1. Copy file .env mẫu
cp api/.env.example api/.env
cp mcp_service/.env.example mcp_service/.env

# 2. Điền secret thật vào api/.env: OPENAI_API_KEY, GEMINI_API_KEY, AES_KEY, POSTGRES_PASSWORD
#    (xem section 3 dưới đây để hiểu từng biến)

# 3. Sinh JWT keypair RS256 PKCS#8 (KHÔNG commit .pem ra git)
make api-keys

# 4. Boot stack 4-service (postgres + redis + python-api + mcp_service + caddy)
make up

# 5. Verify health
curl http://localhost:8180/healthz
curl http://localhost:8180/readyz
curl http://localhost:8180/metrics
```

### Lưu ý prod env

- **CORS:** `CORS_ALLOWED_ORIGINS` prod **CHỈ origin thật** (HTTPS). Validator `_no_lan_in_prod` (P12) reject `localhost/127.0.0.1/192.168.*/10.*/172.16-31.*` khi `APP_ENV=production`.
- **JWT key rotation:** Defer v4.0 (KHÔNG có rotation tool trong M2). Mất `keys/private.pem` = invalidate toàn bộ refresh token; ops phải re-issue keypair + force re-login.
- **AES_KEY rotation:** Defer v4.0 (chưa có migration script re-encrypt cột `api_keys.key_hash`). Sinh 1 lần lúc deploy đầu tiên + lưu offline.
- **MCP OAuth issuer:** `MCP_OAUTH_ISSUER_URL` **PHẢI** là `https://` domain thật (P-MCP-6 — issuer localhost làm hỏng discovery + redirect).

---

## 3. .env config — biến môi trường chi tiết

### `api/.env` (FastAPI backend)

| Biến | Default `.env.example` | Mô tả |
|------|------------------------|-------|
| `POSTGRES_PASSWORD` | `medinet_dev_pwd` | Password Postgres user `medinet`. Prod đổi sang chuỗi random 32+ ký tự. |
| `DATABASE_URL` | `postgresql+asyncpg://medinet:.../medinet_central` | App DB chính (users/hubs/documents/chunks/audit_logs/usage_events/refresh_tokens/api_keys/mcp_oauth_clients). |
| `COCOINDEX_DATABASE_URL` | `postgresql://medinet:.../medinet_cocoindex` | DB state CocoIndex (lineage + flow registry — P7 schema isolation). |
| `REDIS_URL` | `redis://localhost:6379/0` | Cache search (Phase 6 SEARCH-04) + rate limit (Phase 5 AUX-03) + audit queue (Phase 5 AUX-01). |
| `APP_NAMESPACE` | `medinet_prod` | Cố định mọi env (R5). Đổi giữa env = bảng cocoindex orphan + re-index toàn bộ. |
| `COCOINDEX_DB_SCHEMA` | `cocoindex` | Schema riêng tách khỏi `public` (P7). |
| `COCOINDEX_DB` | `.cocoindex/state.lmdb` | LMDB local state cocoindex 1.0.3 (Q5). Container override `/app/.cocoindex/state.lmdb` trên named volume `medinet_cocoindex_state`. |
| `JWT_PRIVATE_KEY_PATH` | `./keys/private.pem` | RSA 2048-bit PKCS#8 private key. Sinh bằng `make api-keys`. |
| `JWT_PUBLIC_KEY_PATH` | `./keys/public.pem` | RSA public key (cho verify). |
| `JWT_ACCESS_TOKEN_TTL` | `900` (15 phút) | TTL access token JWT. |
| `JWT_REFRESH_TOKEN_TTL` | `604800` (7 ngày) | TTL refresh token (rotation Phase 3 + race fix Plan 03-04). |
| `FILE_STORE_DIR` | `./file_store` | Thư mục local lưu file upload (Phase 4 INGEST-02). Container mount `./file_store:/file_store`. |
| `OPENAI_API_KEY` | `sk-replace-me` | **BẮT BUỘC** prod — embedding + LLM answerer. |
| `GEMINI_API_KEY` | `replace-me` | Fallback hot-swap LiteLLM (D5). |
| `RAG_EMBEDDING_PROVIDER` | `openai` | `openai` hoặc `gemini` (hot-swap runtime qua `PUT /api/rag-config`). |
| `RAG_EMBEDDING_MODEL` | `text-embedding-3-small` | Prod đổi sang `text-embedding-3-large` cho quality. Pin `dim=1536` (R1). |
| `RAG_EMBEDDING_DIM` | `1536` | **KHÔNG đổi** (R1 pgvector 2000-dim index limit + R7 cross-dim swap REFUSE). |
| `RAG_LLM_PROVIDER` | `openai` | LLM answerer hot-swap. |
| `RAG_LLM_MODEL` | `gpt-4o-mini` | Phase 7 ASK-04. |
| `AES_KEY` | (rỗng) | **BẮT BUỘC** prod. AES-256-GCM 32-byte base64 cho api_keys encryption-at-rest. Sinh: `python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`. |
| `APP_ENV` | `dev` | `dev` / `staging` / `production`. Validator `_no_lan_in_prod` enforce CORS strict ở `production`. |
| `APP_PORT` | `8180` | Container nội bộ 8080, host map 8180 (Hyper-V excluded range 8038-8137 Windows). |
| `LOG_LEVEL` | `info` | structlog level. |
| `LOG_FORMAT` | `json` | Plan 10-01 structlog JSON output (Docker capture). |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated. Prod: chỉ origin HTTPS thật. |
| `RATE_LIMIT_SEARCH_PER_MINUTE` | (mặc định trong code) | Phase 5 AUX-03 slowapi. |
| `RATE_LIMIT_UPLOAD_PER_MINUTE` | (mặc định trong code) | Phase 5 AUX-03 slowapi. |
| `WATCHDOG_TIMEOUT_SECONDS` | (mặc định trong code) | Phase 4 INGEST-06 watchdog cocoindex stuck processing. |

### `mcp_service/.env` (MCP standalone process)

| Biến | Default `.env.example` | Mô tả |
|------|------------------------|-------|
| `MCP_API_BASE_URL` | `http://localhost:8180` | URL API Service (KHÔNG kèm `/api`). Container Docker: `http://python-api:8080`. Scheme chỉ `http`/`https`. |
| `MCP_SERVICE_HOST` | `0.0.0.0` | Bind host. |
| `MCP_SERVICE_PORT` | `8190` | Port MCP Service. |
| `MCP_HTTP_TIMEOUT` | `30` | Timeout giây cho mỗi HTTP call sang API Service. |
| `MCP_PATH_PREFIX` | `mcp` (path-prefix mode) hoặc rỗng (subdomain mode) | Phase 8.3 routing. |
| `MCP_OAUTH_ISSUER_URL` | `http://localhost:8190` | **Prod PHẢI HTTPS** (P-MCP-6). Caddy auto-TLS hoặc Cloudflare Tunnel. |
| `MCP_OAUTH_ACCESS_TOKEN_TTL` | `3600` (1 giờ) | OAuth access token lifetime. |
| `MCP_OAUTH_REFRESH_TOKEN_TTL` | `2592000` (30 ngày) | OAuth refresh token lifetime. |
| `MCP_OAUTH_STATE_DB_PATH` | `.oauth/state.db` | SQLite OAuth state (clients/codes/tokens/pending). Container `/app/.oauth/state.db` trên named volume `medinet_mcp_oauth_state`. |
| `MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS` | `https://claude.ai,https://inspector.modelcontextprotocol.io,http://localhost:6274,http://127.0.0.1:6274` | **Plan 10-04 CRIT-01 fix** — CORS whitelist cho sensitive path `/token, /authorize, /revoke, /register, /mcp[/*]`. Metadata path `/.well-known/*` vẫn `ACAO *` theo RFC 8414 §3.1. |
| `MCP_INTERNAL_TOKEN` | (rỗng) | Phase 8.3 per-user bind — internal token gọi MCP từ API service. Sinh random 32+ ký tự. |

---

## 4. Backup / Restore (HARD-04 mandatory)

> Backup script này là **acceptance bắt buộc** HARD-04 Plan 10-05. Ops PHẢI test restore quy trình ít nhất 1 lần trước khi deploy production.

### Backup (daily cron khuyến nghị)

```bash
BACKUP_DIR=/var/backups/medinet
mkdir -p $BACKUP_DIR

# (1) Postgres app DB — chứa users/hubs/documents/chunks/audit_logs/usage_events
#     Dump CẢ schema public + schema cocoindex (lineage flow registry shared instance).
pg_dump --schema=public --schema=cocoindex medinet_central > $BACKUP_DIR/central_$(date +%F).sql

# (2) Postgres cocoindex DB — state riêng (flow snapshot + memo)
#     MẤT cocoindex DB = full re-embed (~$6.50/100K chunks OpenAI text-embedding-3-large).
pg_dump medinet_cocoindex > $BACKUP_DIR/cocoindex_$(date +%F).sql

# (3) File store (raw upload — DOCX/TXT/MD/PDF)
tar czf $BACKUP_DIR/file_store_$(date +%F).tar.gz Hub_All/file_store/

# (4) CocoIndex LMDB fingerprint (memo cache + lineage)
#     MẤT LMDB = cocoindex coi MỌI source là mới → re-extract toàn bộ (NHƯNG content-hash
#     diff vẫn skip re-embed nếu chunk content unchanged → cost dập tắt một phần).
tar czf $BACKUP_DIR/cocoindex_lmdb_$(date +%F).tar.gz Hub_All/.cocoindex/

# (5) OAuth state SQLite (Phase 8.3 MCP — clients/codes/tokens/pending)
tar czf $BACKUP_DIR/mcp_oauth_state_$(date +%F).tar.gz Hub_All/mcp_service/.oauth/

# (6) JWT keypair (mất = invalidate toàn bộ refresh token, force re-login)
tar czf $BACKUP_DIR/jwt_keys_$(date +%F).tar.gz Hub_All/api/keys/

# (7) Rotation 30 ngày
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

### Restore (disaster recovery)

```bash
BACKUP_DIR=/var/backups/medinet
RESTORE_DATE=2026-XX-XX  # đổi sang ngày backup muốn restore

# Step 1: stop stack
cd Hub_All && make down

# Step 2: restore Postgres app DB
psql -c "DROP DATABASE IF EXISTS medinet_central; CREATE DATABASE medinet_central;"
psql medinet_central < $BACKUP_DIR/central_${RESTORE_DATE}.sql

# Step 3: restore Postgres cocoindex DB
psql -c "DROP DATABASE IF EXISTS medinet_cocoindex; CREATE DATABASE medinet_cocoindex;"
psql medinet_cocoindex < $BACKUP_DIR/cocoindex_${RESTORE_DATE}.sql

# Step 4: restore file store
tar xzf $BACKUP_DIR/file_store_${RESTORE_DATE}.tar.gz -C Hub_All/

# Step 5: restore LMDB fingerprint
tar xzf $BACKUP_DIR/cocoindex_lmdb_${RESTORE_DATE}.tar.gz -C Hub_All/

# Step 6: restore OAuth state (Phase 8.3 MCP)
tar xzf $BACKUP_DIR/mcp_oauth_state_${RESTORE_DATE}.tar.gz -C Hub_All/mcp_service/

# Step 7: restore JWT keypair
tar xzf $BACKUP_DIR/jwt_keys_${RESTORE_DATE}.tar.gz -C Hub_All/api/

# Step 8: boot lại stack
make up

# Step 9: verify
curl http://localhost:8180/healthz
curl http://localhost:8180/readyz
```

### Note quan trọng về backup

- **Backup CẢ 2 DB** (`medinet_central` + `medinet_cocoindex`) — mất `medinet_cocoindex` DB = full re-embed ~$6.50/100K chunks (OpenAI `text-embedding-3-large@1536`).
- **Backup LMDB fingerprint** `Hub_All/.cocoindex/` — mất LMDB = cocoindex coi mọi source mới + re-extract. Content-hash diff dập tắt một phần cost re-embed nếu chunk content unchanged.
- **KHÔNG cần backup `file_store/`** nếu original files lưu nguồn khác (GDrive/S3 defer v4.0). M2 hiện chỉ có local FS.
- **Backup OAuth state SQLite** — mất = client OAuth phải re-register; user phải re-login.
- **Backup JWT keypair offline** — `keys/private.pem` mất = invalidate toàn bộ refresh token đang live.

---

## 5. Observability (Plan 10-01 + Plan 10-02)

### Prometheus scrape

Cấu hình `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'medinet-api'
    scrape_interval: 15s
    static_configs:
      - targets: ['api:8180']
        labels:
          env: 'production'
          service: 'medinet-wiki-api'
```

5 metric expose ở `/metrics` (Plan 10-02 HARD-02):

| Metric | Type | Labels | SLA target |
|--------|------|--------|------------|
| `requests_total` | Counter | method/path/status | — |
| `errors_total` | Counter | method/path | < 1% req |
| `request_duration_seconds` | Histogram | method/path | p95 < 1s |
| `search_latency_seconds` | Histogram | hub_scope (single/cross) | p95 single < 800ms / cross < 1.5s (SC2) |
| `ingest_duration_seconds` | Histogram | (no label) | DOCX 50 trang < 30s |

**Content-Type:** `text/plain; version=1.0.0; charset=utf-8` (OpenMetrics text format prometheus-client 0.23+). Parse được qua `prometheus_client.parser.text_string_to_metric_families`.

Grafana dashboard defer v4.0 — ops tạm xem qua `promtool query` hoặc raw `/metrics`.

### Log aggregation

- **structlog JSON stdout** → Docker logs capture native.
- Forward sang **Loki** hoặc **Datadog** qua promtail/datadog-agent.
- Field schema 10 field match Go `log/slog` (CONVENTIONS section 5 + Plan 10-01):

```json
{
  "level": "info",
  "msg": "request_completed",
  "ts": "2026-05-21T08:20:49.813514Z",
  "request_id": "70b3a8e2-fc4d-4d6a-99cf-c5a4b9c0e1d3",
  "user_id": "uuid-or-null",
  "hub_id": "uuid-or-null",
  "latency_ms": 4,
  "path": "/healthz",
  "method": "GET",
  "status": 200
}
```

### Trace correlation

- Header `X-Request-Id` (UUID4 sinh nếu client KHÔNG gửi) propagate vào log entry + cocoindex flow log qua ContextVar + `asyncio.create_task` copy_context.
- Query Loki/Datadog: `{service="medinet-wiki-api"} | json | request_id="<uuid>"` để trace full request (HTTP handler + cocoindex BackgroundTask).

---

## 6. Security checklist (production)

| # | Item | Check |
|---|------|-------|
| 1 | JWT keypair PKCS#8 sinh qua `make api-keys` | KHÔNG commit `.pem` vào git — `.gitignored` |
| 2 | AES_KEY rotate annual | Defer v4.0 (chưa có migration tool) |
| 3 | `CORS_ALLOWED_ORIGINS` prod chỉ origin HTTPS thật | Validator `_no_lan_in_prod` reject localhost/192.168.* (P12) |
| 4 | `MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS` whitelist tối thiểu | Default 4 origin: claude.ai + inspector.modelcontextprotocol.io + 2 localhost dev (Plan 10-04 CRIT-01) |
| 5 | Rate limit slowapi enabled | Phase 5 AUX-03 — search/upload per-minute cap |
| 6 | Audit log async batch | Phase 5 AUX-01 — security.* events flushed every 5s hoặc 100 entries |
| 7 | `pg_dump` backup daily automated | Cron + monitor + alert nếu fail 2 ngày liên tiếp |
| 8 | Postgres password ≥ 32 ký tự random | `openssl rand -base64 32` |
| 9 | MCP OAuth issuer HTTPS thật | KHÔNG localhost prod (P-MCP-6) |
| 10 | Hub isolation E4 verify | `pytest tests/integration/test_hub_isolation.py` PASS trước mỗi release |
| 11 | Critical path coverage ≥ 50% | Plan 10-03 `.coveragerc-critical` gate enforce |
| 12 | structlog JSON KHÔNG log PII raw | `email_hash` SHA-256 + KHÔNG log password/token (CONVENTIONS section 5) |

---

## 7. M2 closeout summary

### Phase 1-10 ship status (2026-05-21)

- **M2a (Phase 1-4):** Infra + Schema + Auth + CocoIndex MVP — **COMPLETE** + M2a EXIT GATE PASS (demo upload DOCX → chunks pgvector verify).
- **M2b (Phase 5-9):** CRUD + Search + Ask + Frontend smoke + Eval — **COMPLETE** + Phase 9 quality gate (top-3 ≥75%) target chờ HUMAN UAT real OPENAI_API_KEY.
- **Phase 10 (Hardening + Observability + Docs):** 4/6 plan done — HARD-01 structlog · HARD-02 Prometheus · HARD-03 critical path coverage ≥50% · CRIT-01 CORS split. Còn HARD-04 (plan 10-05 = bản DEPLOY này) + CI workflow (10-06).
- **REQ-ID:** 38/38 v1 done (HARD-04 đóng sau Plan 10-05 ship).

### Critical path test coverage (HARD-03)

- 5 acceptance test crisp gom 1 file `test_critical_path_coverage.py`:
  - auth happy login envelope + JWT
  - hub isolation editor KHÔNG xoá cross-hub
  - ingest VN filename UTF-8 roundtrip
  - search hub filter isolation
  - ask citation marker map đúng chunk_id
- Coverage thực đo: **57.75% ≥ 50%** PASS trên 17 file critical path (auth 8 file + routers 4 + services 4 + repositories.hub_isolation).
- CI gate Plan 10-06 wire: `pytest --cov-config=.coveragerc-critical --cov-fail-under=50`.

### Next milestone: v3.0 — Multi-Hub Split

Seed: `.planning/seeds/v3.0-multi-hub-split.md` (4 architectural decision LOCKED 2026-05-21):

- **D-V3-01:** DB topology = Postgres database riêng cùng instance
- **D-V3-02:** Dataflow hub con → hub tổng = chunks + vector (denormalized read replica, sync 1 chiều)
- **D-V3-03:** Scoping = milestone-level (KHÔNG nhét vào M2 dưới dạng phase đơn lẻ)
- **D-V3-04:** M2 closeout = bắt buộc trước v3.0 (Phase 10 done là tiền đề)

Trigger v3.0: `/gsd-new-milestone v3.0` sau khi Phase 10 ship full + human UAT pass + retrospective ghi nhận.

---

*Deploy guide tạo: 2026-05-21 (Phase 10 Plan 10-05 — HARD-04 docs closeout). Sau Phase 10 ship 4/6 plan: HARD-01 structlog + HARD-02 Prometheus + HARD-03 critical path coverage + CRIT-01 CORS split. M2 closeout pending HARD-04 + Plan 10-06 CI workflow.*
