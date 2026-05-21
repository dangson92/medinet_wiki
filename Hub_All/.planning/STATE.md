---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Multi-Hub Split
status: Phase 1 PLANNED 2026-05-21. 5 plans / 3 waves, 4 REQ TOPO-01..04 coverage 100%. Plan checker iteration 2/3 PASSED (4 blocker + 5 warning fixed, 3 skip). [BLOCKING] schema push task gated SAFE (Option B `make hub-init` preserve M2; Option A reset only with env confirm). Next: `/gsd-execute-phase 1` Multi-DB topology execution.
last_updated: "2026-05-21T17:30:00.000Z"
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 5
  completed_plans: 0
  percent: 0
---

# State — MEDWIKI (v3.0)

**Mã dự án:** MEDWIKI
**Milestone:** v3.0 — Multi-Hub Split
**Ngày bắt đầu:** 2026-05-21 (sau khi v2.0 shipped 100% COMPLETE 38/38 REQ-ID)
**Last updated:** 2026-05-21

## Current Position

- **Phase:** 1 — Multi-DB Topology + Per-hub Alembic (PLANNED — 5 plans ready cho execute)
- **Plan:** 5 plans (01-01..01-05) ở `.planning/phases/01-multi-db-topology/`
- **Status:** Ready to execute
- **Last activity:** 2026-05-21 — `/gsd-plan-phase 1` chạy (SKIP `/gsd-discuss-phase 1`, dùng ROADMAP seeded recommendations cho gray areas). Planner spawn → 5 plan / 3 wave (commit `1ac0ae7`). Plan-checker iteration 1/3 found 4 BLOCKER + 8 WARNING. Planner revision iteration 1/3 fixed 4 BLOCKER + 5 WARNING (commit `b19f5bf`). Plan-checker iteration 2/3 PASSED — no regression, TOPO-01..04 coverage 100%, [BLOCKING] schema push SAFE (Option B preserve M2 volume).

## Phase 1 Plans Summary

| Plan | Wave | Objective | REQ | Tasks |
|------|------|-----------|-----|-------|
| 01-01 | 1 | Postgres init-db.sh refactor 4 DB + vector ext + HNSW 1536-dim verify | TOPO-01 (part 1) | 2 |
| 01-02 | 1 | Settings.hub_name + DSN validator + per-hub resolver | TOPO-04 (part 1) | 3 (1 TDD) |
| 01-03 | 2 | Per-hub Alembic env -x hub + make migrate-all + alembic-head-check.sh | TOPO-02 (part 1) | 3 (1 TDD) |
| 01-04 | 2 | Cocoindex flow `medinet_<hub>_ingest` + APP_NAMESPACE `medinet_<hub>_prod` | TOPO-03 | 2 (1 TDD) |
| 01-05 | 3 | hub-init.sh dynamic + integration test E-V3-3 + CI workflow + [BLOCKING] schema push | TOPO-01/02/04 (part 2) | 4 (1 TDD, 1 BLOCKING) |

**Gray-area decisions LOCKED (seeded từ ROADMAP, không qua discuss-phase 1):**
- GA-Phase1-A: imperative bash loop `SELECT pg_database WHERE datname` + conditional CREATE (Postgres không support `IF NOT EXISTS` cho CREATE DATABASE).
- GA-Phase1-B: APP_NAMESPACE per-hub `medinet_<hub>_prod`; giữ `cocoindex_db_schema="cocoindex"` cố định (R5 + P7 carry forward). M2 cocoindex state reset acceptable cho v3.0-a (re-ingest qua content_hash idempotent + Phase 7 sẽ migrate formally).
- GA-Phase1-C: `make hub-init HUB=<name>` dynamic add — preserve M2 central volume (không cần docker compose down).

## Next Action

1. (Optional) `cat .planning/phases/01-multi-db-topology/*-PLAN.md` — review 5 plans trước khi execute.
2. `/gsd-execute-phase 1` — execute 5 plans theo wave order (W1 parallel 01+02 → W2 parallel 03+04 → W3 final 05 với BLOCKING schema push).
3. (Optional after execute) `/gsd-verify-work 1` — UAT 4 success criteria + E-V3-3 hub isolation.

## Accumulated Context (carry forward từ v2.0)

### v2.0 SHIPPED ✅ 2026-05-21 — Foundation đã có

- **Backend:** Python 3.12 · FastAPI 0.136.1 · cocoindex 1.0.3 · pgvector pg16 · asyncpg/SQLAlchemy 2 async · pwdlib Argon2 · PyJWT RS256 · redis-py · LiteLLM. Single FastAPI process, single DB `medinet_central`, multi-tenancy LOGICAL `WHERE hub_id`.
- **Frontend:** React 19 · Vite 6 · TypeScript 5.8 · Tailwind v4 — D6 đã ràng buộc v2.0 (chỉ verify-only). **D6 EXPIRES ở v3.0 Phase 5** (D-V3-06).
- **MCP service:** Standalone process `mcp_service/` + OAuth 2.0 + DCR + Caddy auto-TLS (Phase 8.3 ship 2026-05-21). Re-point sang central ở v3.0 Phase 7.
- **Eval framework:** `eval/` Python pytest + 12 query VN medical + smoke regression CI gate (`pytest -m critical` < 60s mock). HUMAN UAT gate verdict OpenAI key thật ~$0.20/run defer track standalone.
- **CI:** GitHub Actions `test.yml` 7 step + `lint.yml` 6 step (secret detection 3 pattern). Branch protection rule defer v4.0.
- **Observability:** structlog JSON 10 field + Prometheus `/metrics` 5 metric + critical-path coverage 57.75% ≥50% gate.

### v3.0 LOCKED decisions (2026-05-21)

- **D-V3-01:** Multi-DB cùng instance (`medinet_central` + `medinet_hub_<name>` × N).
- **D-V3-02:** Chunks + vector denormalized sync 1 chiều hub con → tổng. Hub tổng KHÔNG re-embed.
- **D-V3-03:** Milestone-level scoping (KHÔNG nhét vào M2).
- **D-V3-04:** M2 closeout precondition (✓ v2.0 100% COMPLETE 2026-05-21).
- **D-V3-05:** Phase numbering reset về 1.
- **D-V3-06:** D6 expire formally ở Phase 5 — frontend rewrite được phép.

### v3.0 open gray areas (chốt ở discuss-phase tương ứng)

- **GA-V3-A** (Phase 3 — Auth SSO): JWT shared keypair vs JWKS endpoint vs cookie domain `.medinet.vn`. Khuyến nghị seed: JWKS endpoint từ central + Redis blacklist chung.
- **GA-V3-B** (Phase 6 — Settings sync): HTTP pull / push webhook / env var local. Khuyến nghị seed: HTTP pull + Redis cache 60s + pub/sub invalidate.
- **GA-V3-C** (Phase 5 — Proxy + frontend): 1 build detect prefix vs per-hub `VITE_HUB_NAME` build. Khuyến nghị seed: 1 build detect prefix (đỡ build matrix).
- **GA-V3-D** (Phase 4 + 7 — Sync mechanism + migration): cocoindex target thứ 2 / Postgres logical replication / outbox + worker; `pg_dump` per `hub_id` vs snapshot + replay.

### Carry-forward risks từ v2.0

- **R1** pgvector 2000-dim limit → PIN dim 1536 cho cả OpenAI + Gemini.
- **R2** HNSW post-filter → `ef_search=200` + `iterative_scan=relaxed_order` + `max_scan_tuples=20000`.
- **R4** Scanned PDF → `failed_unsupported` enum (KHÔNG silent fail).
- **R5** CocoIndex naming + APP_NAMESPACE — sẽ scale per-hub ở v3.0 Phase 1 (mỗi hub có flow naming riêng `medinet_<hub>_ingest` + APP_NAMESPACE per-hub).
- **R7** Cross-dim embedding swap REFUSE 400 — defer v4.0.

### v3.0 new risks (R-V3-1..6)

| # | Risk | Severity | Phase |
|---|---|---|---|
| R-V3-1 | Sync drift hub con vs tổng | HIGH | Phase 4 |
| R-V3-2 | D6 expire → frontend rewrite regress | HIGH | Phase 5 |
| R-V3-3 | Per-hub Alembic drift | MEDIUM | Phase 1 |
| R-V3-4 | Migration downtime | MEDIUM | Phase 7 |
| R-V3-5 | JWKS endpoint xuống | MEDIUM | Phase 3 |
| R-V3-6 | Settings sync race | LOW | Phase 6 |

### v2.0 deferred items (acknowledge — KHÔNG block v3.0)

| Category | Item | Status / Next action |
|----------|------|---------------------|
| HUMAN UAT | Phase 9 gate verdict ≥75% top-3 OpenAI key thật | `make eval-all` khi user release key ~$0.20/run — defer v3.0 reconfirm |
| HUMAN UAT | Phase 8.3 Claude web "Add custom connector" tới domain MeWiki MCP | `08.3-HUMAN-UAT.md` archive — chờ deploy public HTTPS thật |
| HUMAN UAT | Phase 8 SC1/SC2-browser/SC5 (11 trang React + citation `[1]` + docker compose 5-service) | `08-HUMAN-UAT.md` archive — sẽ smoke lại ở v3.0 Phase 5 sau D6 expire |
| HUMAN UAT | Phase 8.1 SC1 + 8.2 SC4 (`usage_events` thật) | Archives — defer v4.0 |
| Tech debt | Migrate service module log cũ sang `structlog.get_logger(__name__)` (Plan 10-01 chỉ HARD-01 ship) | DEF-10-01-B → v4.0 |
| Tech debt | Branch protection rule GitHub repo enforce 2 workflow trước merge main | Admin permission → v4.0 |
| Tech debt | Push tag `v2.0` lên remote | Defer user trigger sau verify |

> **CRIT-01 status:** ✅ ĐÃ ĐÓNG Plan 10-04 (2026-05-21) — KHÔNG còn defer.

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-21 v3.0 milestone start) + `.planning/REQUIREMENTS.md` (v3.0 — 29 REQ-ID v1) + `.planning/ROADMAP.md` (v3.0 — 7 phase reset numbering)

**Core value (unchanged from v2.0):** Ingestion tri thức Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata. v3.0 mở rộng theo trục tách hub vật lý + cross-hub aggregation.

**Mode:** YOLO · **Granularity:** Large (7 phase) · **Phase numbering:** Reset về 1 (D-V3-05)

**v3.0-a / v3.0-b split (anti-pivot mitigation):**

- **v3.0-a = Phase 1-3** (Topology + codebase factor + Auth SSO) — có thể ship standalone, demo 1 hub con + tổng + JWT SSO PASS. Nếu user accept v3.0-a → never pivot multi-DB topology.
- **v3.0-b = Phase 4-7** (Sync + proxy + settings + migration) — pivot OK nếu sync mechanism GA-V3-D chốt sai.
- 🚦 **v3.0-a EXIT GATE** giữa Phase 3 và 4 — demo 1 hub con + tổng + JWT SSO + golden path PASS → user accept là điều kiện tiếp tục v3.0-b.

---

*State khởi tạo 2026-05-21 ở milestone v3.0 sau khi v2.0 shipped 100% COMPLETE. Phase 1 chưa start. Tham chiếu PROJECT.md + REQUIREMENTS.md + ROADMAP.md cùng commit.*
