---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Multi-Hub Split
status: Phase 1 DONE 2026-05-21 ✅. 5 plans / 22 commits / 166 unit tests + 5 integration test PASS. Live Postgres state verified — 5 DB (medinet_central + medinet_cocoindex + 3 hub) cùng Alembic head SHA 0004, M2 documents COUNT=3 preserved. VERIFICATION 4/4 SC PASS. Next phase 2 — Hub-con Codebase Factor (FACTOR-01..03).
last_updated: "2026-05-21T18:00:00.000Z"
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 5
  completed_plans: 5
  percent: 14
---

# State — MEDWIKI (v3.0)

**Mã dự án:** MEDWIKI
**Milestone:** v3.0 — Multi-Hub Split
**Ngày bắt đầu:** 2026-05-21 (sau khi v2.0 shipped 100% COMPLETE 38/38 REQ-ID)
**Last updated:** 2026-05-21

## Current Position

- **Phase:** 1 — Multi-DB Topology + Per-hub Alembic ✅ **DONE 2026-05-21**
- **Plan:** 5/5 plans complete (01-01..01-05) ở `.planning/phases/01-multi-db-topology/`
- **Status:** Phase 1 closed — VERIFICATION 4/4 SC PASS
- **Last activity:** 2026-05-21 — `/gsd-execute-phase 1` wave-based execution complete. Wave 1 (Plans 01+02) + Wave 2 (Plans 03+04) + Wave 3 (Plan 05 với [BLOCKING] schema push). 22 commits total. 166/166 unit tests + 5/5 integration tests E-V3-3 PASS. Live Postgres: 5 DB (`medinet_central` + `medinet_cocoindex` + 3 hub `yte/duoc/hcns`) cùng Alembic head SHA `0004`, M2 documents COUNT=3 PRESERVED. Verifier: PASSED 4/4 SC.

## Phase 1 Results Summary

| Plan | Wave | Objective | Commits | Tests |
|------|------|-----------|---------|-------|
| 01-01 | 1 | Postgres init-db.sh refactor 4 DB + HNSW 1536-dim verify | 3 | acceptance 15/15 |
| 01-02 | 1 | Settings.hub_name + DSN validator + resolve_database_url | 6 | TDD 11/11 PASS, deviation Rule 1 fix conftest |
| 01-03 | 2 | Per-hub Alembic env -x hub + make migrate-all + head-check | 5 | TDD 10/10 PASS, deviation Rule 3 Windows substitute |
| 01-04 | 2 | Cocoindex dynamic App name + APP_NAMESPACE per-hub + LEGACY fallback | 4 | TDD 9/9 PASS, M2 cocoindex state reset documented |
| 01-05 | 3 | hub-init.sh dynamic + integration test E-V3-3 + CI gate + [BLOCKING] schema push | 5+1 | integration 5/5 PASS, schema push 4 DB head SHA uniform 0004 |

**Live state verified post-execute:**
- 5 DB exist: `medinet_central`, `medinet_cocoindex`, `medinet_hub_yte`, `medinet_hub_duoc`, `medinet_hub_hcns`
- 4 hub Alembic head uniform: `0004`
- M2 `medinet_central.documents` COUNT = 3 (preserved)
- `ix_chunks_vector_hnsw` index per-DB verified

**M2 cocoindex state migration (BLOCKER 4 mitigation chain documented):**
- App name M2 `medinet_wiki_ingest` → v3.0 `medinet_central_ingest` — state orphan accepted cho v3.0-a.
- Optional fallback `COCOINDEX_APP_NAME_LEGACY=medinet_wiki_ingest` env override.
- Post-deploy re-ingest qua `UPDATE documents SET status='pending' WHERE status='completed'` (content_hash idempotent skip nếu unchanged).
- Phase 7 sẽ migrate data formally qua `pg_dump --where`.

## Next Action

1. **(Recommended) `/gsd-discuss-phase 2`** — Hub-con Codebase Factor. Gray areas chốt: app factory pattern (`create_app(hub_name)` vs 2 file `main_central.py`/`main_hub.py`), mount router conditional, docker compose service definition.
2. (Optional) `/gsd-code-review 1` — advisory code review trên 22 commits Phase 1 (workflow.code_review=true gate).
3. (Optional) `/gsd-verify-work 1` — manual UAT 4 SC nếu user muốn extra verify ngoài automated test.

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
