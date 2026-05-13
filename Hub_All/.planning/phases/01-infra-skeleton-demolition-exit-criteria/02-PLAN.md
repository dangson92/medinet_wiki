---
plan: 02
phase: 1
wave: 1
depends_on: []
files_modified:
  - Hub_All/docker-compose.yml
  - Hub_All/api/scripts/init-db.sh
  - Hub_All/api/.env.example
autonomous: true
requirements: [CORE-02]
---

# Plan 02: Docker Compose 3-service + DB init script verify HNSW 1536-dim (R1 mitigation)

## Objective
Viết lại `docker-compose.yml` thành 3 service (`postgres` pgvector pg16 + `redis` 7-alpine + `python-api`) với init script tạo 2 logical DB và VERIFY HNSW index `vector(1536)` build được trước khi Plan 03 viết flow — đây là điểm chốt R1 mitigation theo PITFALLS#P1.

## Must-Haves
- `Hub_All/docker-compose.yml` mới định nghĩa đúng 3 service với image pinned: `pgvector/pgvector:pg16`, `redis:7-alpine`, `python-api` (build từ `./api/Dockerfile`).
- `docker compose up -d` lên 3 service healthy trong dưới 30 giây trên máy dev.
- Init script `Hub_All/api/scripts/init-db.sh` được mount vào `/docker-entrypoint-initdb.d/00-init.sh`, tạo 2 DB (`medinet_central` + `medinet_cocoindex`), enable `vector` extension trên cả 2, VERIFY HNSW 1536-dim index build OK (R1 mitigation cứng).
- `Hub_All/api/.env.example` đủ 10+ env key bắt buộc với giá trị mẫu hợp lệ.

## Tasks

<task id="01">
<action>
REWRITE `Hub_All/docker-compose.yml` (xóa nội dung cũ M1 — chroma/docling references, viết lại từ đầu). Nội dung paste-ready:

```yaml
name: medinet-wiki

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: medinet-postgres
    environment:
      POSTGRES_DB: medinet_central
      POSTGRES_USER: medinet
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-medinet_dev_pwd}
    volumes:
      - medinet_pgdata:/var/lib/postgresql/data
      - ./api/scripts/init-db.sh:/docker-entrypoint-initdb.d/00-init.sh:ro
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medinet -d medinet_central"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks: [medinet_net]

  redis:
    image: redis:7-alpine
    container_name: medinet-redis
    command: ["redis-server", "--save", "60", "1", "--loglevel", "warning"]
    volumes:
      - medinet_redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks: [medinet_net]

  python-api:
    build:
      context: ./api
      dockerfile: Dockerfile
    container_name: medinet-api
    env_file:
      - ./api/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_central
      COCOINDEX_DATABASE_URL: postgresql://medinet:${POSTGRES_PASSWORD:-medinet_dev_pwd}@postgres:5432/medinet_cocoindex
      REDIS_URL: redis://redis:6379/0
      APP_NAMESPACE: medinet_prod
      COCOINDEX_DB_SCHEMA: cocoindex
      JWT_PRIVATE_KEY_PATH: /keys/private.pem
      JWT_PUBLIC_KEY_PATH: /keys/public.pem
      FILE_STORE_DIR: /file_store
      APP_ENV: ${APP_ENV:-dev}
      LOG_LEVEL: ${LOG_LEVEL:-info}
    volumes:
      - ./api/keys:/keys:ro
      - ./file_store:/file_store
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks: [medinet_net]

volumes:
  medinet_pgdata:
  medinet_redis_data:

networks:
  medinet_net:
    driver: bridge
```

LƯU Ý: dùng tag `pgvector/pgvector:pg16` (KHÔNG `postgres:16-alpine` — sẽ FAIL `CREATE EXTENSION vector` theo PITFALLS#P1).
</action>
<read_first>
- Hub_All/docker-compose.yml
- Hub_All/.planning/research/STACK.md
- Hub_All/.planning/research/ARCHITECTURE.md
- Hub_All/.planning/research/PITFALLS.md
</read_first>
<acceptance_criteria>
- File `Hub_All/docker-compose.yml` tồn tại.
- `grep -c 'pgvector/pgvector:pg16' Hub_All/docker-compose.yml` ≥ 1.
- `grep -c 'redis:7-alpine' Hub_All/docker-compose.yml` ≥ 1.
- `grep -c 'medinet_central' Hub_All/docker-compose.yml` ≥ 1.
- `grep -c 'medinet_cocoindex' Hub_All/docker-compose.yml` ≥ 1.
- `grep -c 'APP_NAMESPACE: medinet_prod' Hub_All/docker-compose.yml` ≥ 1.
- `grep -c 'COCOINDEX_DB_SCHEMA: cocoindex' Hub_All/docker-compose.yml` ≥ 1.
- `grep -c 'condition: service_healthy' Hub_All/docker-compose.yml` ≥ 2.
- `grep -c 'docker-entrypoint-initdb.d/00-init.sh' Hub_All/docker-compose.yml` ≥ 1.
- `docker compose -f Hub_All/docker-compose.yml config` exits 0 (YAML valid).
- `grep -c 'chromadb' Hub_All/docker-compose.yml` trả về `0` (KHÔNG còn reference ChromaDB).
- `grep -c 'docling' Hub_All/docker-compose.yml` trả về `0` (KHÔNG còn reference docling-pipeline).
</acceptance_criteria>
</task>

<task id="02">
<action>
Tạo `Hub_All/api/scripts/init-db.sh` — shell script chạy bởi `pgvector/pgvector:pg16` entrypoint lúc khởi tạo cluster đầu tiên (mount `/docker-entrypoint-initdb.d/00-init.sh`). Script PHẢI:
1. Tạo DB `medinet_cocoindex` (DB `medinet_central` được tạo sẵn qua env `POSTGRES_DB`).
2. `CREATE EXTENSION IF NOT EXISTS vector` trên CẢ 2 DB.
3. VERIFY HNSW 1536-dim index build OK trên DB `medinet_central` bằng test table → DROP TABLE sau khi verify. Đây là điểm chốt R1 mitigation (PITFALLS#P1).
4. Echo log rõ ràng từng bước để debug.

Nội dung paste-ready:

```bash
#!/usr/bin/env bash
# Medinet Wiki — Postgres init script
# Tạo 2 logical DB + CREATE EXTENSION vector + VERIFY HNSW 1536-dim build OK (R1 mitigation).
# Chạy 1 lần khi Postgres cluster khởi tạo lần đầu (mount /docker-entrypoint-initdb.d/00-init.sh).

set -euo pipefail

echo "[init-db] (1/4) Tạo database medinet_cocoindex..."
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "postgres" <<-EOSQL
    CREATE DATABASE medinet_cocoindex OWNER ${POSTGRES_USER};
EOSQL

echo "[init-db] (2/4) Enable extension vector trên medinet_central..."
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "medinet_central" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "[init-db] (3/4) Enable extension vector trên medinet_cocoindex..."
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "medinet_cocoindex" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "[init-db] (4/4) VERIFY HNSW 1536-dim index build OK (R1 mitigation)..."
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "medinet_central" <<-EOSQL
    CREATE TABLE _hnsw_dim_check (id serial primary key, v vector(1536));
    CREATE INDEX _hnsw_dim_check_idx ON _hnsw_dim_check USING hnsw (v vector_cosine_ops);
    DROP TABLE _hnsw_dim_check;
EOSQL

echo "[init-db] DONE — 2 DB created, vector ext enabled, HNSW 1536-dim verified."
```

Đặt quyền thực thi `chmod +x Hub_All/api/scripts/init-db.sh` (Linux/macOS) hoặc note rằng Docker mount sẽ chạy với `bash` interpreter (Windows dev không cần chmod local).
</action>
<read_first>
- Hub_All/docker-compose.yml
- Hub_All/.planning/research/PITFALLS.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/scripts/init-db.sh` tồn tại.
- `grep -c 'CREATE DATABASE medinet_cocoindex' Hub_All/api/scripts/init-db.sh` ≥ 1.
- `grep -c 'CREATE EXTENSION IF NOT EXISTS vector' Hub_All/api/scripts/init-db.sh` ≥ 2 (cả 2 DB).
- `grep -c 'vector(1536)' Hub_All/api/scripts/init-db.sh` ≥ 1 (R1 verify).
- `grep -c 'USING hnsw' Hub_All/api/scripts/init-db.sh` ≥ 1.
- `grep -c 'vector_cosine_ops' Hub_All/api/scripts/init-db.sh` ≥ 1 (PITFALLS#P17 pin cosine).
- `grep -c 'set -euo pipefail' Hub_All/api/scripts/init-db.sh` ≥ 1 (fail-fast).
- `head -1 Hub_All/api/scripts/init-db.sh` trả `#!/usr/bin/env bash`.
</acceptance_criteria>
</task>

<task id="03">
<action>
Tạo `Hub_All/api/.env.example` với mẫu env vars đầy đủ (developer copy sang `.env` rồi điền). Comment tiếng Việt giải thích từng nhóm:

```dotenv
# Medinet Wiki API — .env.example (M2)
# Copy file này thành .env và điền giá trị thực tế. KHÔNG commit .env.

# === Postgres (R1: pgvector ext bắt buộc dùng image pgvector/pgvector:pg16) ===
POSTGRES_PASSWORD=medinet_dev_pwd
DATABASE_URL=postgresql+asyncpg://medinet:medinet_dev_pwd@localhost:5432/medinet_central
COCOINDEX_DATABASE_URL=postgresql://medinet:medinet_dev_pwd@localhost:5432/medinet_cocoindex

# === Redis ===
REDIS_URL=redis://localhost:6379/0

# === CocoIndex (R5: APP_NAMESPACE cố định "medinet_prod" mọi env — xem CONVENTIONS.md) ===
APP_NAMESPACE=medinet_prod
COCOINDEX_DB_SCHEMA=cocoindex

# === JWT keypair (sinh bằng api/scripts/generate_keys.sh — xem Plan 04) ===
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
JWT_ACCESS_TOKEN_TTL=900       # 15 phút (giây)
JWT_REFRESH_TOKEN_TTL=604800   # 7 ngày (giây)

# === File storage (local default — GDrive defer v4.0) ===
FILE_STORE_DIR=./file_store

# === LLM providers (defer Phase 7 wiring, đặt placeholder trước) ===
OPENAI_API_KEY=sk-replace-me
GEMINI_API_KEY=replace-me
RAG_EMBEDDING_PROVIDER=openai
RAG_EMBEDDING_MODEL=text-embedding-3-small
RAG_EMBEDDING_DIM=1536
RAG_LLM_PROVIDER=openai
RAG_LLM_MODEL=gpt-4o-mini

# === AES (settings encryption, reuse từ Go cũ — defer Phase 5 wiring) ===
AES_KEY=replace-with-32-byte-base64-key

# === Runtime ===
APP_ENV=dev
APP_PORT=8080
LOG_LEVEL=info
LOG_FORMAT=json
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```
</action>
<read_first>
- Hub_All/docker-compose.yml
- Hub_All/.planning/research/STACK.md
- Hub_All/.planning/research/ARCHITECTURE.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/.env.example` tồn tại.
- `grep -c '^DATABASE_URL=' Hub_All/api/.env.example` trả về `1`.
- `grep -c '^COCOINDEX_DATABASE_URL=' Hub_All/api/.env.example` trả về `1`.
- `grep -c '^REDIS_URL=' Hub_All/api/.env.example` trả về `1`.
- `grep -c '^APP_NAMESPACE=medinet_prod$' Hub_All/api/.env.example` trả về `1` (R5 mitigation).
- `grep -c '^COCOINDEX_DB_SCHEMA=cocoindex$' Hub_All/api/.env.example` trả về `1` (PITFALLS#P7).
- `grep -c '^JWT_PRIVATE_KEY_PATH=' Hub_All/api/.env.example` trả về `1`.
- `grep -c '^FILE_STORE_DIR=' Hub_All/api/.env.example` trả về `1`.
- `grep -c '^RAG_EMBEDDING_DIM=1536$' Hub_All/api/.env.example` trả về `1` (R1 pin).
- `grep -c '^AES_KEY=' Hub_All/api/.env.example` trả về `1`.
- `grep -c '^APP_ENV=' Hub_All/api/.env.example` trả về `1`.
</acceptance_criteria>
</task>

## Verification
- `docker compose -f Hub_All/docker-compose.yml config` exits 0 (YAML hợp lệ).
- `docker compose -f Hub_All/docker-compose.yml up -d postgres redis` đưa 2 service lên healthy trong dưới 30 giây: `docker compose ps --filter status=running --format json | jq '. | length'` ≥ 2.
- `docker compose -f Hub_All/docker-compose.yml exec postgres psql -U medinet -d medinet_central -c "SELECT extname FROM pg_extension WHERE extname='vector';"` trả về `vector`.
- `docker compose -f Hub_All/docker-compose.yml exec postgres psql -U medinet -d medinet_cocoindex -c "SELECT extname FROM pg_extension WHERE extname='vector';"` trả về `vector`.
- `docker compose -f Hub_All/docker-compose.yml exec postgres psql -U medinet -d medinet_central -c "CREATE TABLE _t(v vector(1536)); CREATE INDEX ON _t USING hnsw (v vector_cosine_ops); DROP TABLE _t;"` exits 0 (R1 mitigation re-verify).
- `docker compose -f Hub_All/docker-compose.yml logs postgres | grep -c 'HNSW 1536-dim verified'` ≥ 1 (init script chạy đủ 4 bước).
