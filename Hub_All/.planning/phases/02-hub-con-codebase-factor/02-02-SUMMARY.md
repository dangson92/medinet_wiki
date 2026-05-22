---
phase: 02-hub-con-codebase-factor
plan: 02
subsystem: docker-compose
tags:
  - docker-compose
  - 4-service
  - yaml-anchor
  - cocoindex-lmdb-per-hub
  - port-mapping
  - mcp-re-point
  - d-v3-phase2-c
  - factor-01
dependency_graph:
  requires:
    - "02-01-PLAN.md (create_app() factory mount conditional — runtime consume HUB_NAME env)"
    - "01-01-PLAN.md (init-db.sh tạo 4 DB medinet_central + medinet_hub_yte/duoc/hcns)"
    - "01-02-PLAN.md (Settings._enforce_hub_dsn_match validator boot-time)"
  provides:
    - "docker-compose.yml 4 service FastAPI dedicated (python-api-central + python-api-yte + python-api-duoc + python-api-hcns)"
    - "YAML anchor x-api-template dedupe shared config"
    - "Cocoindex LMDB volume per-hub (medinet_cocoindex_<hub>)"
    - "mcp_service re-point sang python-api-central (D-V3-02 LOCKED)"
  affects:
    - "Plan 02-03 (integration test endpoint matrix — smoke 2 service compose up)"
    - "Plan 02-04 (closeout — checkpoint:human-action smoke 4 service compose live)"
    - "Phase 5 PROXY-01 (Caddy subpath route extend Caddyfile)"
    - "Phase 7 MIGRATE-04 (MCP service re-point central re-confirm)"
tech_stack:
  added: []
  patterns:
    - "Docker compose YAML anchor + merge key (<<: *anchor) dedupe shared config"
    - "Per-hub named volume cho cocoindex Environment singleton isolation"
    - "Host port range 8180-8183 (Hyper-V excluded 8038-8137 Windows backward-compat)"
key_files:
  created: []
  modified:
    - "docker-compose.yml (145 insertions, 23 deletions — anchor + 4 service template + 4 cocoindex vol + mcp re-point)"
decisions:
  - "D-V3-Phase2-C consumed: 4 service dedicated với YAML anchor (KHÔNG deploy.replicas — limitation env per-replica)"
  - "D-V3-02 honored: MCP service re-point central single endpoint (KHÔNG fan-out N hub con)"
  - "Cocoindex LMDB volume per-hub (defensive layer 2 — Phase 1 APP_NAMESPACE đã isolate layer 1)"
  - "Port mapping host: central 8180 (M2 backward-compat frontend hardcode) + yte 8181 + duoc 8182 + hcns 8183"
  - "Mỗi service VIẾT LẠI environment + volumes thay vì merge từ anchor (docker compose YAML merge key KHÔNG merge dict lồng cấp 2 — override 1 env key sẽ XOÁ TOÀN BỘ env template)"
metrics:
  duration_minutes: 5
  tasks_completed: 1
  files_modified: 1
  completed_date: 2026-05-22
requirements:
  - FACTOR-01
---

# Phase 2 Plan 02: Docker Compose 4 Service FastAPI Dedicated + YAML Anchor Summary

**One-liner:** Refactor `Hub_All/docker-compose.yml` từ 1 service `python-api` M2 sang 4 service FastAPI dedicated (`python-api-central` + `python-api-yte` + `python-api-duoc` + `python-api-hcns`) với YAML anchor `x-api-template: &api-template` dedupe shared config, cocoindex LMDB volume per-hub, port host 8180-8183, mcp_service re-point sang `python-api-central` — đóng FACTOR-01 ở Docker layer wiring.

---

## Mục tiêu

Wire Docker layer cho Phase 2 v3.0 Multi-Hub Split:

- **4 service FastAPI dedicated** — mỗi service inherit `<<: *api-template` rồi override `HUB_NAME` + `DATABASE_URL` + cocoindex LMDB volume + container_name + ports.
- **YAML anchor `x-api-template`** ở top-level dedupe shared config (build/env_file/depends_on/networks).
- **Cocoindex LMDB volume per-hub** — `medinet_cocoindex_{central,yte,duoc,hcns}` (cocoindex 1.0.3 Environment singleton KHÔNG share state cross HUB_NAME; defensive layer 2 — Phase 1 APP_NAMESPACE đã isolate layer 1).
- **Port mapping** — central 8180 (M2 backward-compat frontend hardcode), yte 8181, duoc 8182, hcns 8183. Container internal vẫn 8080.
- **mcp_service re-point** — `MCP_API_BASE_URL: http://python-api-central:8080` + `depends_on: python-api-central` (LOCKED D-V3-02 — KHÔNG fan-out N hub con).

---

## Output

### Task 1 — Refactor `docker-compose.yml` (commit `05a39a4`)

**Diff:** 145 insertions, 23 deletions.

**Thay đổi cụ thể:**

| Phần | Trước (M2) | Sau (v3.0) |
|------|------------|-----------|
| Anchor block | KHÔNG có | `x-api-template: &api-template` top-level — shared config (build/env_file/13 env shared/2 volume shared/depends_on/networks) |
| Service `python-api` | 1 service `python-api` (container_name `medinet-api`, port `8180:8080`, volume `medinet_cocoindex_state`) | XOÁ — thay bằng 4 service dedicated |
| Service `python-api-central` | — | inherit anchor + HUB_NAME=central + DATABASE_URL=...@postgres:5432/medinet_central + container_name=medinet-api-central + volume medinet_cocoindex_central + port 8180:8080 |
| Service `python-api-yte` | — | inherit anchor + HUB_NAME=yte + DSN .../medinet_hub_yte + container medinet-api-yte + vol medinet_cocoindex_yte + port 8181:8080 |
| Service `python-api-duoc` | — | inherit anchor + HUB_NAME=duoc + DSN .../medinet_hub_duoc + container medinet-api-duoc + vol medinet_cocoindex_duoc + port 8182:8080 |
| Service `python-api-hcns` | — | inherit anchor + HUB_NAME=hcns + DSN .../medinet_hub_hcns + container medinet-api-hcns + vol medinet_cocoindex_hcns + port 8183:8080 |
| `mcp_service.MCP_API_BASE_URL` | `http://python-api:8080` | `http://python-api-central:8080` (re-point D-V3-Phase2-C) |
| `mcp_service.depends_on` | `python-api: service_healthy` | `python-api-central: service_healthy` |
| `volumes:` block | `medinet_cocoindex_state` | XOÁ; thêm 4 vol `medinet_cocoindex_{central,yte,duoc,hcns}` |
| `postgres` / `redis` / `caddy` / `networks` | — | KHÔNG đổi (Phase 5 PROXY-01 sẽ extend Caddyfile) |

**Tổng service compose:** 8 (postgres + redis + 4 python-api-* + mcp_service + caddy).

**Lý do override toàn bộ environment + volumes ở mỗi service thay vì kế thừa từ anchor:**

Docker Compose YAML merge key `<<:` KHÔNG merge dict lồng cấp 2. `environment:` và `volumes:` là list/dict — override 1 key sẽ XOÁ TOÀN BỘ environment template gây thiếu `APP_NAMESPACE`/`JWT_*`. Safe pattern: viết lại đầy đủ 13 env var ở mỗi service. `build`/`env_file`/`depends_on`/`networks` merge OK qua anchor (top-level key đơn giản).

---

## Verification

**Verify command (acceptance criteria automated):**

```bash
cd Hub_All && docker compose config --quiet && docker compose config --services | sort
```

**Kết quả:** Exit 0 ✓ — 8 service render đúng:

```
caddy
mcp_service
postgres
python-api-central
python-api-duoc
python-api-hcns
python-api-yte
redis
```

**Acceptance criteria check (15/15 PASS):**

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| `grep -c "^x-api-template: &api-template$"` | ≥ 1 | 1 | ✓ |
| `grep -cE "^  python-api-(central\|yte\|duoc\|hcns):$"` | == 4 | 4 | ✓ |
| `grep -c "<<: \*api-template"` | == 4 | 4 | ✓ |
| `grep -c "HUB_NAME: central"` | ≥ 1 | 1 | ✓ |
| `grep -c "HUB_NAME: yte"` | ≥ 1 | 1 | ✓ |
| `grep -c "HUB_NAME: duoc"` | ≥ 1 | 1 | ✓ |
| `grep -c "HUB_NAME: hcns"` | ≥ 1 | 1 | ✓ |
| `grep -cE "/medinet_central$\|/medinet_hub_yte$\|/medinet_hub_duoc$\|/medinet_hub_hcns$"` | ≥ 4 | 4 | ✓ |
| `grep -cE '^      - "818[0-3]:8080"'` | == 4 | 4 | ✓ |
| `grep -c "medinet_cocoindex_{central\|yte\|duoc\|hcns}:"` | ≥ 8 | 8 | ✓ |
| `grep -c "MCP_API_BASE_URL: http://python-api-central:8080"` | ≥ 1 | 1 | ✓ |
| `grep -c "MCP_API_BASE_URL: http://python-api:8080"` (M2 stale) | == 0 | 0 | ✓ |
| `grep -cE "^      python-api-central:"` (mcp depends_on) | ≥ 1 | 1 | ✓ |
| `grep -c "container_name: medinet-api-{central\|yte\|duoc\|hcns}"` | == 4 | 4 | ✓ |
| `docker compose config --quiet` exit code | 0 | 0 | ✓ |
| `docker compose config --services` 8 service signature | == 1 | 1 | ✓ |

**Per-service env render check (python-api-yte):**

`docker compose config | awk '/^  python-api-yte:/,...'` → 13 env var resolved:

```
APP_ENV: dev
APP_NAMESPACE: medinet_prod
COCOINDEX_DATABASE_URL: postgresql://medinet:medinet_dev_pwd@postgres:5432/medinet_cocoindex
COCOINDEX_DB: /app/.cocoindex/state.lmdb
COCOINDEX_DB_SCHEMA: cocoindex
COCOINDEX_LMDB_PATH: /app/.cocoindex/state.lmdb
DATABASE_URL: postgresql+asyncpg://medinet:medinet_dev_pwd@postgres:5432/medinet_hub_yte
FILE_STORE_DIR: /file_store
HUB_NAME: yte
JWT_PRIVATE_KEY_PATH: /keys/private.pem
JWT_PUBLIC_KEY_PATH: /keys/public.pem
LOG_LEVEL: info
REDIS_URL: redis://redis:6379/0
```

`HUB_NAME=yte` ↔ `DATABASE_URL=.../medinet_hub_yte` match → Phase 1 `Settings._enforce_hub_dsn_match` validator sẽ PASS ở boot.

---

## Decisions Made

1. **D-V3-Phase2-C consumed:** 4 service dedicated với YAML anchor `x-api-template: &api-template` (KHÔNG `deploy.replicas` — Docker Compose limitation env per-replica khác nhau). Mỗi service `container_name` unique để `docker logs medinet-api-yte` phân biệt được.

2. **D-V3-02 honored:** MCP service re-point sang `python-api-central` single endpoint (KHÔNG fan-out N hub con). Cross-hub aggregate ở central — Phase 7 MIGRATE-04 re-confirm contract.

3. **Cocoindex LMDB volume per-hub:** Defensive layer 2 — Phase 1 đã isolate qua `APP_NAMESPACE` (`medinet_prod` cố định mọi env theo R5) + flow name `medinet_<hub>_ingest` per-hub (TOPO-03). Volume per-hub là defensive layer thứ 2 cho cocoindex 1.0.3 Environment singleton (process-global, KHÔNG re-open được sau khi đã open + close).

4. **Port host mapping 8180-8183:**
   - `central 8180` = M2 backward-compat (frontend `api.ts` hardcode + Hyper-V excluded range 8038-8137 Windows).
   - `yte 8181`, `duoc 8182`, `hcns 8183` = continuous range cho dev/test direct curl.
   - Phase 5 Caddy sẽ strip prefix `/<hub>` + route subpath qua port internal — port host chỉ dùng cho direct dev/test trước khi Caddy lên.

5. **Override toàn bộ environment + volumes mỗi service:** Docker Compose YAML merge key `<<:` chỉ merge top-level dict đơn giản (build/env_file/depends_on/networks). `environment:` và `volumes:` là list/dict — override 1 key sẽ XOÁ TOÀN BỘ template environment. Safe pattern: viết lại 13 env var ở mỗi service.

6. **XOÁ `medinet_cocoindex_state` M2 volume:** No longer referenced. M2 cocoindex state orphan accepted cho v3.0-a (Phase 1 đã reset cocoindex state qua app name change `medinet_wiki_ingest` → `medinet_central_ingest`). Phase 7 sẽ migrate data formally qua `pg_dump --where`.

---

## Deviations from Plan

**None — plan executed exactly as written.**

1 micro-adjustment KHÔNG phải deviation:
- Acceptance criteria `grep -c "<<: \*api-template" == 4`. Lần đầu count = 5 vì 1 dòng comment đầu file mô tả pattern có chứa literal string `<<: *api-template`. Sửa wording comment thành `merge-key inherit (<< api-template)` (loại escape special characters trong literal text) — KHÔNG đổi YAML semantic, chỉ giúp acceptance grep match đúng 4 (1 per service).

Lint/verify đều PASS lần đầu sau micro-adjustment. Không có Rule 1/2/3 deviation.

---

## Authentication Gates

**None.** Plan 02-02 chỉ refactor YAML compose — không boot service thật, không cần secret env, không có auth gate. Plan 02-04 closeout sẽ có `checkpoint:human-action` cho live smoke 4 service compose up (cần Docker engine + Postgres healthy + OpenAI API key thật nếu test ingest).

---

## Notable Implementation Details

### YAML anchor merge key limitation

Docker Compose YAML merge key `<<: *anchor` chỉ merge **top-level dict đơn giản**:
- ✓ Merge OK: `build` (dict 2 key), `env_file` (list), `depends_on` (dict), `networks` (list).
- ✗ KHÔNG merge: `environment` (dict — override 1 key xóa toàn bộ template), `volumes` (list — override append vs replace ambiguous).

Workaround: Viết lại đầy đủ `environment` + `volumes` ở mỗi service (verbose nhưng safe). Anchor vẫn dedupe được `build` + `env_file` + `depends_on` + `networks` (5 key shared).

### Port mapping rationale

- **8180 central:** M2 backward-compat. Frontend `frontend/src/services/api.ts` hardcode `localhost:8180` (theo D6 KHÔNG sửa frontend M2). Windows Hyper-V excluded range 8038-8137 chặn port 80xx-81xx default.
- **8181/8182/8183 hub con:** Continuous range cho dev/test direct curl. Phase 5 Caddy sẽ strip prefix `/<hub>` + route `wiki.domain.com/yte/*` → upstream `python-api-yte:8080`. Production sẽ siết firewall port host (T-02-02-01 mitigation defer Phase 7 hardening).

### Cocoindex LMDB volume per-hub

Cocoindex 1.0.3 `core.Environment` là **process-global singleton** — KHÔNG share state cross HUB_NAME. Mỗi container mount volume riêng `medinet_cocoindex_<hub>` → state isolated.

Layer 1 isolation (Phase 1 TOPO-03): `APP_NAMESPACE=medinet_prod` cố định + flow name `medinet_<hub>_ingest` per-hub. Cocoindex internal tables (`__cocoindex.flows`, `__cocoindex.tasks`) trong cocoindex DB phân biệt qua flow name.

Layer 2 isolation (Plan 02-02): LMDB filesystem volume per-hub. Defensive — nếu cocoindex singleton bug cross-process, layer 1 đã đủ. Layer 2 fail-safe khi dev mount volume khác vào container hcns (T-02-02-03 accept).

### M2 cocoindex_state volume orphan

`medinet_cocoindex_state` (M2 single volume) XOÁ khỏi compose. Existing data trên volume:
- Nếu user `docker compose down -v` trước Phase 2 deploy → volume xóa cùng.
- Nếu user `docker compose down` (giữ volume) → volume orphan, vẫn nằm trong Docker daemon nhưng KHÔNG mount vào container nào sau Plan 02-02. Cleanup manual: `docker volume rm medinet-wiki_medinet_cocoindex_state`.

M2 cocoindex state đã reset ở Phase 1 (app name change `medinet_wiki_ingest` → `medinet_central_ingest` — state file orphan). Phase 7 sẽ migrate formally.

### mcp_service re-point traceability

| Field | M2 | v3.0 Phase 2 |
|-------|-----|--------------|
| `MCP_API_BASE_URL` | `http://python-api:8080` | `http://python-api-central:8080` |
| `depends_on` | `python-api: service_healthy` | `python-api-central: service_healthy` |

KHÔNG fan-out per-hub. LOCKED D-V3-02 — MCP gọi central cho cross-hub aggregate. Phase 7 MIGRATE-04 sẽ re-confirm contract sau khi cross-hub search ở central go-live (SYNC-03 Phase 4).

---

## Self-Check: PASSED

**Files verified exist:**
- `Hub_All/docker-compose.yml` — FOUND (modified, 145 insertions / 23 deletions)
- `Hub_All/.planning/phases/02-hub-con-codebase-factor/02-02-SUMMARY.md` — FOUND (this file)

**Commits verified exist:**
- `05a39a4` — `feat(02-02): 4 service FastAPI dedicated + YAML anchor + cocoindex LMDB per-hub` — FOUND

**Verification command result:**
- `cd Hub_All && docker compose config --quiet` → exit 0 ✓
- `docker compose config --services | sort` → 8 service render đúng (caddy + mcp_service + postgres + python-api-central + python-api-duoc + python-api-hcns + python-api-yte + redis) ✓
- Acceptance criteria 15/15 PASS (grep + docker compose config rendered env vars).

---

## Next Steps

**Plan 02-02 đóng FACTOR-01 ở Docker layer wiring** — Plan 02-01 đã đóng ở app factory level (unit test 9/9 PASS). Wave 2 còn 1 plan:

- **Plan 02-03 (Wave 2, parallel — file-disjoint với 02-02):** Integration test `tests/integration/test_factor_hub_scoped.py` — endpoint matrix 12 hub-scoped + 8 central-only + envelope shape 404 verify khi router strip + pytest fixture `hub_app_factory` parameterized. Tiêu thụ FACTOR-02 strip behavior từ Plan 02-01 unit-level + FACTOR-03 hub-scoped endpoint contract.

- **Plan 02-04 (Wave 3 closeout):** CLAUDE.md section 2 update Phase 2 DONE + STATE.md move + REQUIREMENTS.md mark FACTOR-01/02/03 ✓ + smoke compose checkpoint:human-action live 4 service Docker.

**Live smoke test (defer Plan 02-04):**

```bash
cd Hub_All
docker compose up -d postgres redis
docker compose up -d python-api-central python-api-yte  # 2 service smoke
curl http://localhost:8180/api/health  # central
curl http://localhost:8181/api/health  # yte
docker logs medinet-api-yte | grep central_only_routers_skipped  # FACTOR-02 evidence
```

---

*Plan 02-02 completed 2026-05-22. Wave 2 first half (02-02) ship ✅ — 02-03 ready execute parallel hoặc sau.*
