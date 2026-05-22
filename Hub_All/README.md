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

## Milestone status

- ✅ **M2 v2.0 — Full RAG Rewrite** đang đóng (Phase 1-10, 38/38 REQ-ID done, M2a EXIT GATE PASS).
- 🟢 **Phase 10 (Hardening + Observability + Docs)** ship 4/6 plan: HARD-01 structlog · HARD-02 Prometheus · HARD-03 critical path + coverage ≥50% · CRIT-01 CORS split. Còn HARD-04 (plan này) + CI workflow (10-06).
- 🔜 **Next milestone:** v3.0 — Multi-Hub Split (subpath routing, multi-DB, cocoindex flow per-hub đẩy chunks+vector lên hub tổng). Seed `.planning/seeds/v3.0-multi-hub-split.md` (4 architectural decision LOCKED 2026-05-21).

---

*README cập nhật: 2026-05-21 (Plan 10-05 — HARD-04 docs closeout). Trước đó README đã rỗng (Go cũ xoá TEARDOWN-01 pull-in 2026-05-14).*
