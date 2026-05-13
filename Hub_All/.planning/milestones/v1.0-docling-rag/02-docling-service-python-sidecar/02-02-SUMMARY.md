---
phase: 02-docling-service-python-sidecar
plan: 02
subsystem: infra
tags: [docker-compose, infra, postgres, redis, chromadb, docling]
requires:
  - "docling-pipeline/Dockerfile (Plan 02-01)"
provides:
  - "docker-compose.yml root: orchestration 4 service (postgres, redis, chroma, docling-pipeline)"
  - ".env.example root: mẫu env hạ tầng compose"
  - "W2 gate: infra YAML sẵn sàng cho user `docker compose up` (defer runtime)"
affects:
  - "Workflow dev local — 1 lệnh start full infra (sau khi user backup chroma_data)"
tech_stack_added:
  - "Docker Compose v2 schema"
  - "postgres:16-alpine"
  - "redis:7-alpine"
  - "chromadb/chroma:latest"
patterns_used:
  - "Service-level healthcheck với interval/timeout/retries chuẩn"
  - "depends_on condition: service_healthy gate cho docling-pipeline"
  - "expose-only (KHÔNG ports mapping) cho service internal — DSVC-05"
  - "env_file + environment override layered cho docling-pipeline"
  - "Volume mount HuggingFace cache (./docling_models:/root/.cache/docling) tránh re-download"
key_files_created:
  - docker-compose.yml
  - .env.example
key_files_modified: []
decisions:
  - "Thêm `redis: condition: service_healthy` vào depends_on docling-pipeline (ngoài postgres + chroma trong PLAN gốc) — DSVC ecosystem cần Redis ready cho cache layer tương lai (Rule 2: tránh race start-up)"
  - "Thêm `env_file: ./docling-pipeline/.env` vào service docling-pipeline (theo task spec) — cho phép service Python load env runtime ngoài override compose"
  - "redis volume `./redis_data:/data` + `--appendonly yes` cho persistence (PLAN gốc CONTEXT mục B chỉ liệt kê 4 service, không cấm persistence; thêm để consistent với postgres/chroma)"
  - "KHÔNG `docker compose up` runtime — defer cho user vì rủi ro port conflict 5432/8000 và mount đè ./chroma_data/ (1.3 MB persistence hiện hữu)"
metrics:
  duration_minutes: 4
  completed_date: "2026-04-29"
  tasks_completed: 1
  files_created: 2
  files_modified: 0
requirements_addressed:
  - DSVC-05
---

# Phase 2 Plan 02: Docker Compose Root + .env.example Summary

**One-liner:** Tạo `docker-compose.yml` ROOT với 4 service hạ tầng (postgres:16-alpine, redis:7-alpine, chromadb/chroma:latest, docling-pipeline build local) join network `medinet-net`, healthchecks đầy đủ, docling-pipeline chỉ `expose:` (không host ports) — cộng `.env.example` root mẫu env compose, sẵn sàng W2 gate cho Wave 2.

## Outcome

- File `docker-compose.yml` (102 dòng) commit atomic ở `ba490cf`.
- File `.env.example` root (40 dòng) commit cùng commit.
- 4 service đầy đủ: postgres, redis, chroma, docling-pipeline. Tất cả join `medinet-net` (bridge).
- Healthcheck mỗi service:
  - postgres: `pg_isready` interval 10s
  - redis: `redis-cli ping` interval 10s
  - chroma: `curl /api/v2/heartbeat` interval 15s
  - docling-pipeline: `curl /healthz` interval 15s **start_period 60s** cho lifespan warm models
- depends_on docling-pipeline: postgres + redis + chroma đều `condition: service_healthy`.
- Volume mount đầy đủ: `./postgres_data`, `./redis_data`, `./chroma_data`, `./docling_models:/root/.cache/docling`.
- docling-pipeline KHÔNG có `ports:` mapping — chỉ `expose: ["8001"]` (DSVC-05 internal-only).
- YAML parse hợp lệ qua `python -c "import yaml; yaml.safe_load(...)"` (Docker Desktop chưa start trên môi trường dev → defer `docker compose config` sang Plan 02-08 smoke test).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1    | Tạo docker-compose.yml root + .env.example root | ba490cf | docker-compose.yml, .env.example |

## Decisions Made

1. **Thêm `redis: condition: service_healthy` vào depends_on docling-pipeline** — PLAN gốc chỉ liệt kê postgres + chroma nhưng theo task spec user yêu cầu cả 3 healthy gate. Áp dụng Rule 2: critical functionality — tránh race start-up khi docling cần cache layer Redis tương lai.
2. **Thêm `env_file: ./docling-pipeline/.env`** — task spec yêu cầu rõ; tách giữa env compose-level (root .env) vs service-level (docling-pipeline/.env riêng) cho phép layered override.
3. **Redis persistence (`./redis_data` + `--appendonly yes`)** — consistent pattern với postgres/chroma. CONTEXT mục B không cấm.
4. **KHÔNG run `docker compose up` runtime** — đúng theo `<objective>` cảnh báo. Lý do: port 5432/8000 có thể conflict với Postgres/Chroma local đang chạy, và mount đè `./chroma_data/` (1.3 MB persistence từ Phase 1) có rủi ro mất dữ liệu nếu init container ghi đè permission.

## Verification Performed

- `python -c "import yaml; yaml.safe_load(open('docker-compose.yml', encoding='utf-8'))"` → OK.
- `grep "postgres:16-alpine" docker-compose.yml` → match.
- `grep "redis:7-alpine" docker-compose.yml` → match.
- `grep "chromadb/chroma:latest" docker-compose.yml` → match.
- `grep "docling-pipeline:" docker-compose.yml` → match.
- `grep "medinet-net" docker-compose.yml` → 5 hits (4 service `networks:` + network declaration).
- `grep "/root/.cache/docling" docker-compose.yml` → match.
- `grep "service_healthy" docker-compose.yml` → 3 hits (postgres + redis + chroma).
- `grep "start_period: 60s" docker-compose.yml` → match.
- File `.env.example` root tồn tại với 4 nhóm env: POSTGRES_*, REDIS_PORT, CHROMA_PORT, DOCLING_*.

## Deviations from Plan

**1. [Rule 2 - Critical functionality] Bổ sung `redis: condition: service_healthy` vào depends_on**
- **Found during:** Task 1 (so sánh task spec user vs PLAN.md gốc).
- **Issue:** PLAN.md gốc chỉ list `depends_on: postgres + chroma`; task spec user yêu cầu `postgres+redis+chroma healthy`.
- **Fix:** Thêm `redis: condition: service_healthy` block.
- **Files modified:** `docker-compose.yml` (+3 dòng).
- **Commit:** `ba490cf`.

**2. [Rule 2 - Critical functionality] Thêm `env_file: ./docling-pipeline/.env`**
- **Found during:** Task 1.
- **Issue:** PLAN.md gốc không có `env_file:` trong service docling-pipeline; task spec user yêu cầu rõ.
- **Fix:** Thêm `env_file: - ./docling-pipeline/.env` block trên `environment:`.
- **Files modified:** `docker-compose.yml` (+2 dòng).
- **Commit:** `ba490cf`.

**3. [Skip] `docker compose config` runtime validate**
- **Found during:** Verification step.
- **Issue:** Docker Desktop trên Windows dev chưa start, không thể chạy `docker compose config` để parse + resolve YAML.
- **Resolution:** Fallback dùng `python -c "import yaml; yaml.safe_load(...)"` parse OK. Defer `docker compose config` validate sang Plan 02-08 smoke test khi user start Docker Desktop. Đã ghi rõ trong commit message.
- **Files modified:** Không có.

## Known Stubs

Không có stub. File compose đầy đủ chức năng — chỉ defer runtime execution.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: persistence-mount | `docker-compose.yml` | Volume `./chroma_data:/chroma/chroma` mount đè vào ChromaDB persistence hiện hữu (1.3 MB từ Phase 1) — nếu container chroma init ghi permission khác user host, có thể block backend Go native đọc file. **Mitigation:** User backup `chroma_data/` trước khi `up` lần đầu (đã note trong commit + .env.example). |
| threat_flag: port-host-mapping | `docker-compose.yml` | Postgres (5432), Redis (6379), Chroma (8000) expose ra host. Nếu deploy production cùng máy với service public, **PHẢI** đổi sang bind `127.0.0.1:` only hoặc xóa `ports:` (chỉ giữ network internal). M1 chấp nhận vì dev mode. |
| threat_flag: default-credentials | `.env.example` | `POSTGRES_PASSWORD=medinet_dev` default. User phải đổi trước production deploy. |

## ⚠️ CẢNH BÁO QUAN TRỌNG

**KHÔNG chạy `docker compose up` từ commit này cho đến khi user xác nhận:**
1. Đã backup `./chroma_data/` (1.3 MB persistence Phase 1).
2. Đã stop Postgres local (port 5432) nếu đang chạy.
3. Đã stop Chroma local (port 8000) nếu đang chạy.
4. Đã copy `.env.example` → `.env` và đổi `POSTGRES_PASSWORD`.

Plan 02-02 chỉ commit YAML — runtime defer Plan 02-08 (smoke test toàn bộ service).

## Next Step

- Wave 2 song song: Plan 02-03 (Docling Extractor wrapper), Plan 02-04 (HybridChunker wrapper), Plan 02-05 (Serializer DoclingDocument → response schema).
- Wave 2 đã unblock vì có cả Wave 1 plans (02-01 skeleton + 02-02 compose).

## Self-Check: PASSED

- File `docker-compose.yml` → FOUND.
- File `.env.example` → FOUND.
- File `.planning/phases/02-docling-service-python-sidecar/02-02-SUMMARY.md` → FOUND (file này).
- Commit `ba490cf` → FOUND in `git log`.
