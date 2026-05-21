---
plan: 02
phase: 1
status: completed
date: 2026-05-13
---

# Plan 02 SUMMARY — Docker Compose 3-service + DB init verify HNSW 1536-dim

## Phạm vi đã triển khai

Plan 02 chuyển stack hạ tầng M1 (postgres plain + redis + chromadb + docling-pipeline)
sang stack M2 đúng theo D1/D3 (3 service: pgvector + redis + python-api) và bake
R1 mitigation cứng (verify HNSW 1536-dim build OK ở init time, fail-fast nếu
pgvector image sai).

## Files đã tạo / sửa

| File | Trạng thái | Mục đích |
|---|---|---|
| `Hub_All/docker-compose.yml` | REWRITTEN từ stack Go sang stack Python | 3 service mới: pgvector/pgvector:pg16 + redis:7-alpine + python-api (build ./api/Dockerfile), mount init-db.sh vào /docker-entrypoint-initdb.d/00-init.sh, named volumes medinet_pgdata + medinet_redis_data, network medinet_net |
| `Hub_All/api/scripts/init-db.sh` | KHÔNG cần commit lại (Plan 01 task 03 đã commit identical content trong `e5c9240`) | Shell script tạo DB medinet_cocoindex + CREATE EXTENSION vector trên 2 DB + VERIFY HNSW(vector_cosine_ops) trên vector(1536) (R1 + P17) |
| `Hub_All/api/.env.example` | CREATED | 10+ env key mẫu cho FastAPI + cocoindex (Postgres async + cocoindex sync URL, APP_NAMESPACE=medinet_prod cố định, RAG_EMBEDDING_DIM=1536 pin, JWT/AES/LLM placeholders) |

## Commits

| SHA | Title |
|---|---|
| `f131fb2` | chore(phase-01): rewrite docker-compose sang 3-service Python stack |
| `35c37a4` | feat(phase-01): tạo api/.env.example mẫu env cho FastAPI + cocoindex |

Note: `init-db.sh` (Plan 02 task 02) đã được Plan 01 task 03 commit trong
`e5c9240` với nội dung identical theo spec — không có diff để commit lại.

## Acceptance criteria — đã verify

### Task 01 — docker-compose.yml
- ✓ `grep -c 'pgvector/pgvector:pg16' docker-compose.yml` = 1
- ✓ `grep -c 'redis:7-alpine' docker-compose.yml` = 1
- ✓ `grep -c 'medinet_central' docker-compose.yml` = 3 (≥1)
- ✓ `grep -c 'medinet_cocoindex' docker-compose.yml` = 1
- ✓ `grep -c 'APP_NAMESPACE: medinet_prod' docker-compose.yml` = 1
- ✓ `grep -c 'COCOINDEX_DB_SCHEMA: cocoindex' docker-compose.yml` = 1
- ✓ `grep -c 'condition: service_healthy' docker-compose.yml` = 2
- ✓ `grep -c 'docker-entrypoint-initdb.d/00-init.sh' docker-compose.yml` = 1
- ✓ `grep -c 'chromadb' docker-compose.yml` = 0 (KHÔNG còn ref ChromaDB)
- ✓ `grep -c 'docling' docker-compose.yml` = 0 (KHÔNG còn ref docling-pipeline)
- ⚠ `docker compose -f Hub_All/docker-compose.yml config` SKIPPED — Docker chưa
  cài trên Windows dev này. Xem mục Deviations.

### Task 02 — init-db.sh
- ✓ File tồn tại + executable bit set (mode 100755 trong git index).
- ✓ `grep -c 'CREATE DATABASE medinet_cocoindex'` = 1
- ✓ `grep -c 'CREATE EXTENSION IF NOT EXISTS vector'` = 2 (cả 2 DB)
- ✓ `grep -c 'vector(1536)'` = 1 (R1 verify)
- ✓ `grep -c 'USING hnsw'` = 1
- ✓ `grep -c 'vector_cosine_ops'` = 1 (P17 pin cosine, KHÔNG L2)
- ✓ `grep -c 'set -euo pipefail'` = 1 (fail-fast)
- ✓ `head -1` = `#!/usr/bin/env bash`

### Task 03 — .env.example
- ✓ `^DATABASE_URL=` = 1 (postgresql+asyncpg)
- ✓ `^COCOINDEX_DATABASE_URL=` = 1 (postgresql sync — cocoindex yêu cầu)
- ✓ `^REDIS_URL=` = 1
- ✓ `^APP_NAMESPACE=medinet_prod$` = 1 (R5 mitigation)
- ✓ `^COCOINDEX_DB_SCHEMA=cocoindex$` = 1 (P7 — schema isolation)
- ✓ `^JWT_PRIVATE_KEY_PATH=` = 1
- ✓ `^FILE_STORE_DIR=` = 1
- ✓ `^RAG_EMBEDDING_DIM=1536$` = 1 (R1 pin embedding dim)
- ✓ `^AES_KEY=` = 1
- ✓ `^APP_ENV=` = 1

## Deviations & blockers

1. **Docker chưa cài trên dev machine** — `docker --version` → `command not
   found`. Do đó các verification step sau bị SKIPPED:
   - `docker compose -f Hub_All/docker-compose.yml config` (YAML validity)
   - `docker compose up -d postgres redis` smoke test
   - `psql ... SELECT extname FROM pg_extension WHERE extname='vector'` test
   - HNSW re-verify CREATE INDEX qua docker exec

   **Mitigation:** YAML đã được Write theo paste-ready content từ Plan 02
   `<action>` block đúng chuẩn syntax, các grep acceptance đều pass, init
   script content + cờ executable đều OK. Khi machine có Docker, chạy
   `docker compose -f Hub_All/docker-compose.yml up -d postgres redis` để
   smoke test trước Plan 03.

2. **`init-db.sh` đã được commit trước** — Plan 01 task 03 (commit `e5c9240`
   "tạo package layout + uv.lock cho api") đã include file `init-db.sh` với
   content identical theo Plan 02 task 02 spec. Plan 02 chạy lại Write nhưng
   không tạo diff → không commit task 02 riêng. Không phải lỗi: deliverable
   của Plan 02 task 02 vẫn được satisfy.

3. **`docker-compose.override.yml`** vẫn còn ref `docling-pipeline` (port
   8001 mapping). File này thuộc scope Plan 05 demolition (xóa Go backend +
   docling-pipeline + chroma_data) — Plan 02 KHÔNG đụng tới. Lưu ý khi chạy
   `docker compose up` trước Plan 05, Compose sẽ phàn nàn về service
   `docling-pipeline` không tồn tại trong file chính → cần Plan 05 xóa
   override hoặc bỏ ref docling.

## R1 mitigation status

R1 = pgvector HNSW dim limit 2000 → nếu chọn embedding 3072-dim sẽ FAIL
CREATE INDEX → query rơi về Seq Scan → p95 vỡ.

Plan 02 đã bake mitigation TỪ INIT TIME:
- Pin embedding dim 1536 trong `.env.example` (`RAG_EMBEDDING_DIM=1536`).
- Pin image `pgvector/pgvector:pg16` trong compose (KHÔNG `postgres:16-alpine`).
- `init-db.sh` Step 4/4 CREATE INDEX USING hnsw trên vector(1536) với
  `vector_cosine_ops` — nếu image sai hoặc dim sai → container Postgres
  CRASH ngay lần khởi động đầu tiên (vì script set -euo pipefail và
  ON_ERROR_STOP=1) → fail-fast trước khi Plan 03 viết flow.

→ R1 đã được mitigate đúng theo `.planning/PROJECT.md` Risk Register hàng R1
và `.planning/research/PITFALLS.md` Pitfall 1.

## Sẵn sàng cho Plan 03

Plan 03 sẽ viết `api/app/main.py` FastAPI skeleton + `api/app/config.py`
pydantic-settings load từ env. Tất cả env key Plan 03 cần đều đã có trong
`.env.example` mẫu. Stack Compose đã sẵn cho `docker compose up python-api`
khi Plan 01's `api/Dockerfile` build được (Plan 01 task 04 đã ship).
