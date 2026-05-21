# Archive — Milestone v2.0 ROADMAP (Full RAG Rewrite)

> **Trạng thái:** ✅ SHIPPED 2026-05-21
> **Goal:** Xóa toàn bộ stack RAG + backend Go hiện hữu, viết lại bằng **Python FastAPI + cocoindex v1.0.3+ + Postgres pgvector**. CocoIndex sở hữu indexing dataflow (extract → chunk → embed → upsert) + incremental diff theo content-hash; FastAPI handle auth/hub/user/audit/search/ask. ChromaDB và toàn bộ Go backend đã xoá.
> **Phases:** 13 (10 gốc + 8.1/8.2/8.3 inserted) · **Plans:** ~75 · **Tasks:** 38/38 REQ-ID v1 done · **Granularity:** Large · **Mode:** YOLO · **Phase numbering:** Reset về 1 (`--reset-phase-numbers`)
> **Created:** 2026-05-13 · **Shipped:** 2026-05-21 · **Calendar days:** 8 (rất nhanh nhờ AI-assisted execution)
> **Critical path:** 1 → 2 → 4 → 6 → 7 → 9 → 10 · **Auth branch:** 3 → 5 → 8

Đây là snapshot ROADMAP.md đầy đủ tại thời điểm `/gsd-complete-milestone v2.0` (2026-05-21). File gốc `.planning/ROADMAP.md` đã thu gọn thành dòng tham chiếu sau snapshot này.

---

## Milestone summary

- **Includes:** 13 phase — 01 (Infra) · 02 (Schema) · 03 (Auth) · 04 (CocoIndex Ingest) · 05 (CRUD) · 06 (Search) · 07 (Ask) · 08 (Frontend Smoke) · 08.1 (MCP Server) · 08.2 (MCP standalone process) · 08.3 (MCP OAuth + public HTTPS) · 09 (Eval Framework) · 10 (Hardening + Observability + Docs).
- **M2a/M2b split (R3 anti-pivot mitigation):**
  - M2a = Phase 1-4 backend foundation + cocoindex MVP demo, EXIT GATE ✅ PASSED 2026-05-21.
  - M2b = Phase 5-10 RAG completion + MCP + eval + hardening — toàn bộ COMPLETE.
- **Coverage:** 38/38 v1 REQ-ID done (CORE-01..05, AUTH-01..06, INGEST-01..08, HUB-01..03, USER-01..03, AUX-01..03, SEARCH-01..04, ASK-01..05, COMPAT-01, TEARDOWN-01, MCP-01/02, EVAL-01..04, HARD-01..04).
- **Git range:** `db30528` (08.3 audit seed) → `2669cd4` (Plan 10-06 ship) — 55 commits trong session đóng cuối.
- **Tag:** `v2.0` (annotated, local — push remote defer).

### Key accomplishments (v2.0)

1. **Backend rewrite Go → Python FastAPI** — JWT RS256 (PKCS#8) + Argon2 cross-compat Go params `m=65536,t=3,p=4` + envelope `{success,data,error,meta}` + RBAC (`require_role`) + Redis SETNX refresh-race lock + Postgres async + lifespan-managed pool/cocoindex.
2. **CocoIndex 1.0.3 ingest dataflow** end-to-end runnable — extract/chunk VN/embed dim 1536/pgvector + content-hash incremental dedup + heartbeat watchdog 300s + asyncpg pool race vá Plan 04-08; M2a EXIT GATE demo `make m2a-demo` PASS.
3. **pgvector + HNSW search** single-hub & cross-hub — `vector(1536)` + `vector_cosine_ops` + `ef_search=200` + `iterative_scan=relaxed_order` + Redis cache TTL 5' + hub-tagged Pub/Sub invalidate; E4 critical 6/6 PASS.
4. **Ask API + LiteLLM citation `[N]` map chunk_id** + anti-injection prompt + provider hot-swap runtime (cross-dim REFUSE 400) + token usage `BackgroundTasks` ghi `usage_events`.
5. **MCP server cho AI client ngoài** — Phase 8.1 in-process FastMCP 3 tool → Phase 8.2 tách process độc lập `mcp_service/` gọi API qua HTTP → Phase 8.3 OAuth 2.0 + DCR + Caddy auto-TLS + 9 plan đóng audit (CRIT-01 CORS split + HIGH-02 refresh-family revoke + HIGH-03 concurrency lock + ...).
6. **Eval framework + quality gate ≥75% top-3** — pytest-based runnable `make eval-smoke` (mock <60s) + `make eval-all` (real LLM gate verdict) + report.py 7 section EVAL.md + pytest smoke regression CI gate `pytest -m critical api/tests/integration/test_eval_pipeline.py` zero external dep.
7. **Hardening + observability** — structlog JSON (10 field match Go log/slog + `X-Request-Id` ContextVar propagate) + Prometheus `/metrics` 5 metric + integration test critical-path coverage 57.75% ≥50% gate + GitHub Actions CI `test.yml` + `lint.yml` secret detection guard + README/DEPLOY/2 .env.example/CLAUDE.md/CONVENTIONS docs closeout.
8. **Demolition M1 (TEARDOWN-01)** — `Hub_All/backend/` Go pull-in xoá sớm 2026-05-14 (git tag `m1-go-archived` backup), `docling-pipeline/` + `eval/` cũ xoá Phase 1.

### Key decisions taken in v2.0

| # | Decision | Outcome |
|---|---|---|
| D1 | Backend Go → Python FastAPI | ✓ Good — codebase đồng nhất Python, không boundary Go↔Python |
| D2 | CocoIndex v1.0.3+ làm indexing layer | ✓ Good — incremental diff content-hash + race vá Plan 04-08; pin `>=1.0.3,<1.1` |
| D3 | Postgres pgvector thay ChromaDB | ✓ Good — bớt 1 service; HNSW + `iterative_scan` enough |
| D4 | Gỡ Docling hoàn toàn | ⚠️ Revisit v4.0 — scanned PDF VN trả 415 `failed_unsupported` (R4 mitigation OK), table preservation accept-loss |
| D5 | LLM answerer hot-swap OpenAI/Gemini qua LiteLLM | ✓ Good |
| D6 | Frontend KHÔNG sửa trong M2 | ✓ Good — 0 file `frontend/` đụng (Phase 8 verify-only); CSS deviation rule documented |
| D7 | Abandon M1 hoàn toàn | ✓ Good |
| D8 | Eval framework làm lại từ đầu (Python pytest) | ✓ Good |
| D9 | Phase numbering reset về 1 | ✓ Good |
| D-04 (Phase 8.1) | MCP in-process gọi service layer trực tiếp | ❌ Reverted Phase 8.2 — tách process gọi API HTTP để separate concerns |
| D-V3-01..04 (LOCKED 2026-05-21) | Multi-DB cùng instance + chunks+vector sync 1 chiều + milestone-level scoping + M2 closeout precondition | Carry forward sang v3.0 seed |

### Issues encountered & resolutions

- **Argon2 doc-bug** (Plan 03-03): REQUIREMENTS ghi `t=1,p=2` SAI; Go source `backend/internal/pkg/hash/argon2.go` là source of truth `t=3,p=4` → fix in-place + production seed hash verify.
- **CocoIndex 1.0.3 actual API khác research** (Phase 4): `LocalFile` source không phù hợp, dùng `coco.App + VectorSchema + mount_table_target` + `BackgroundTasks` trigger_cocoindex_update + `update_blocking()` thay LISTEN/NOTIFY (cocoindex 1.0.3 KHÔNG support).
- **Race pool A/pool B** (Plan 04-08, debug session 2026-05-21): SQLAlchemy commit pool A vs cocoindex asyncpg pool B REPEATABLE READ snapshot → initial delay 0.1s + retry loop max 3 attempts linear backoff.
- **mcp 1.27.1 thay 1.9.4** (Phase 8.1): `combine_lifespans` không tồn tại upstream → tự viết `_composed_lifespan`; pin `mcp>=1.27.0,<1.28`.
- **OAuth audit 2026-05-21** (Phase 8.3): sau 12 hot-fix phát hiện 3 Critical mới (CORS double-add + cross-client code exchange + DCR redirect_uri whitelist) → 3 plan gap closure (07/08/09) đóng tất cả, mcp_service 135/135 PASS.
- **CRIT-01 CORS allow_origins=`*`** (Phase 8.3 audit): tách `MultiPolicyCORSMiddleware` ASGI metadata wildcard vs sensitive whitelist origin, Plan 10-04 đóng.

### Known deferred items (KHÔNG block M2 close, ghi nhận retrospective)

| Type | Item | Status / next action |
|---|---|---|
| HUMAN UAT | Phase 9 Wave 4 gate verdict ≥75% top-3 với OpenAI key thật | Track standalone — chạy `make eval-all` khi user release key + budget ~$0.20/run |
| HUMAN UAT | Phase 8.3 — kết nối Claude web "Add custom connector" tới domain MeWiki MCP | `08.3-HUMAN-UAT.md` — chờ user deploy public HTTPS thật |
| HUMAN UAT | Phase 8 — render 11 trang React + citation `[1]` clickable + docker compose healthy 5-service | `08-HUMAN-UAT.md` — defer `/gsd-verify-work 8` |
| HUMAN UAT | Phase 8.1 SC1 (kết nối AI client thật) + SC5 (`usage_events` DB thật) | `08.1-HUMAN-UAT.md` |
| HUMAN UAT | Phase 8.2 SC4 (`usage_events` row sau `ask_wiki` E2E thật) | mcp_service README ghi nhận |
| Tech debt | Migrate service module log cũ sang `structlog.get_logger(__name__)` (Plan 10-01 chỉ HARD-01 ship — defer v4.0) | DEF-10-01-B |
| Tech debt | Branch protection rule GitHub repo enforce 2 workflow trước merge main | Defer v4.0 cần admin permission |
| Tech debt | Push tag `v2.0` lên remote | Defer user trigger sau khi user verify |

> **CRIT-01 status:** ✅ Đã ĐÓNG ở Plan 10-04 (2026-05-21). KHÔNG còn defer.

---

## Phases (snapshot)

### M2a — Backend Foundation + Ingest MVP

- [x] **Phase 1: Infra Skeleton + Demolition + EXIT Criteria** — FastAPI skeleton + Docker Compose 3-service + xoá code M1 + CONVENTIONS.md ✓ (2026-05-13, 6 plans / 4 waves / 28 commits)
- [x] **Phase 2: Database Schema + Alembic Baseline** — schema migrations cho users/hubs/documents/chunks/audit_logs/usage_events/refresh_tokens/api_keys/user_hubs/settings + HNSW `vector_cosine_ops` 1536-dim verified runtime ✓ (2026-05-13, 5 plans / 5 waves / 28 commits, 7/7 pytest PASS)
- [x] **Phase 3: Auth Port + RBAC + Response Envelope** — JWT RS256 + Argon2 cross-compat + RBAC + envelope ✓ (2026-05-14, 5 plans / 4 waves / 22 commits, 62/62 pytest no regress, 29/29 critical PASS, 5/5 ROADMAP AC verified)
- [x] **Phase 4: CocoIndex Flow MVP + Document Ingest** — cocoindex flow BackgroundTask + extract/chunk/embed/pgvector + status tracking + content-hash dedup ✓ (2026-05-21, 8 plans / 5 waves, E2E `test_ingest_e2e` PASSED testcontainers, race pool A/B vá Plan 04-08 debug session)

🚦 **M2a EXIT GATE PASSED 2026-05-21** — E2E upload DOCX VN → chunks pgvector → content-hash dedup verify thành công.

### M2b — RAG Completion

- [x] **Phase 5: Hub + User + Audit + APIKey + Settings CRUD** — CRUD endpoint FastAPI (contract = `frontend/src/services/api.ts` + envelope), isolation theo `hub_id`, rate limit slowapi ✓ (2026-05-17, 6 plans / 4 waves, 9/9 REQ-ID, E4 hub-isolation verified 6/6 critical, verify PASSED 5/5)
- [x] **Phase 6: Search API Single + Cross-Hub** — vector search direct pgvector + `iterative_scan` + Redis cache hub-tagged ✓ (2026-05-18, 4 plans / 4 waves, 4/4 REQ-ID SEARCH-01..04; hub isolation E4 6/6 critical PASS; 4/6 SC verified, 4 human-UAT pending)
- [x] **Phase 7: Ask API + LiteLLM + Citation + Hot-Swap + Usage** — LLM answerer với citation `[N]` + provider hot-swap + token usage logging ✓ (2026-05-18, 5 plans / 3 waves, 5/5 REQ-ID ASK-01..05; integration 18 test / 11 critical PASS; latency p95 + anti-injection LLM thật defer Phase 9 — `07-HUMAN-UAT.md`)
- [x] **Phase 8: Frontend E2E Smoke** — verify React 19 hoạt động end-to-end với FastAPI mới (KHÔNG sửa frontend) ✓ (2026-05-19, 5 plans / 5 waves, COMPAT-01; 8/11 auto-verified, regression 109/109 unit PASS, code review 0 Critical; SC1/SC2-browser/SC5 human UAT — `08-HUMAN-UAT.md`)
- [x] **Phase 8.1: MCP Server — Expose Wiki Tools** *(INSERTED 2026-05-19)* — MCP server Streamable HTTP tại `/mcp` expose 3 tool read-only ✓ (3 plans / 3 waves; `tests/unit/mcp/` 9 PASS, regression 118 PASS, CR-01 đã vá; SC1/SC5 human UAT)
- [x] **Phase 8.2: MCP Service — Tách Process Độc Lập** *(INSERTED 2026-05-19)* — đảo D-04, tách MCP khỏi FastAPI thành service riêng `mcp_service/` gọi API qua HTTP ✓ (5 plans / 4 waves; 33 test mcp_service/ PASS + 119 regression API unit PASS, ruff clean; SC4 human UAT)
- [x] **Phase 8.3: MCP OAuth 2.0 + Deploy Public HTTPS** *(INSERTED 2026-05-19)* — OAuth 2.0 + DCR + Caddy auto-TLS + 9 plan (4 gốc + 5 gap closure đóng audit 2026-05-21 CRIT/HIGH) ✓ (2026-05-21, mcp_service 135/135 PASS, pytest -m critical 17/17 PASS, ruff sạch; SC4 human UAT cần domain thật)
- [x] **Phase 9: Eval Framework + Quality Gate ≥75% top-3** — pytest-based eval + 10 file VN medical + queries.jsonl + gate ✓ (2026-05-21, 5 plans / 3 waves, EVAL-01..04 COMPLETE, framework runnable `make eval-smoke` + `make eval-all` + pytest smoke regression CI gate `pytest -m critical api/tests/integration/test_eval_pipeline.py`; verdict ≥75% top-3 với OpenAI key thật = HUMAN UAT track standalone)
- [x] **Phase 10: Hardening + Observability + Docs** — structlog JSON + Prometheus + integration test ≥50% + DEPLOY.md + CI workflow GitHub Actions ✓ (2026-05-21, 6 plans / 4 waves; 10-01 structlog · 10-02 Prometheus · 10-03 critical-path 57.75% coverage · 10-04 CRIT-01 CORS split · 10-05 docs closeout · 10-06 test.yml + lint.yml secret detection)

---

## Progress Table (final)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infra Skeleton + Demolition + EXIT Criteria | 6/6 | ✓ Complete | 2026-05-13 |
| 2. Database Schema + Alembic Baseline | 5/5 | ✓ Complete | 2026-05-13 |
| 3. Auth Port + RBAC + Response Envelope | 5/5 | ✓ Complete | 2026-05-14 |
| 4. CocoIndex Flow MVP + Document Ingest | 8/8 | ✓ Complete | 2026-05-21 |
| 🚦 M2a EXIT GATE | — | ✅ PASSED | 2026-05-21 |
| 5. Hub + User + Audit + APIKey + Settings CRUD | 6/6 | ✓ Complete | 2026-05-17 |
| 6. Search API Single + Cross-Hub | 4/4 | ✓ Complete | 2026-05-18 |
| 7. Ask API + LiteLLM + Citation + Hot-Swap + Usage | 5/5 | ✓ Complete | 2026-05-18 |
| 8. Frontend E2E Smoke (TEARDOWN-01 done 2026-05-14) | 5/5 | ✓ Complete (verify human_needed) | 2026-05-19 |
| 8.1 MCP Server — Expose Wiki Tools | 3/3 | ✓ Complete (verify human_needed) | 2026-05-19 |
| 8.2 MCP Service — Tách Process Độc Lập | 5/5 | ✓ Complete (verify human_needed — SC4) | 2026-05-19 |
| 8.3 MCP OAuth 2.0 + Deploy Public HTTPS | 9/9 | ✓ Complete | 2026-05-21 |
| 9. Eval Framework + Quality Gate ≥75% top-3 | 5/5 | ✓ Complete (gate verdict HUMAN UAT) | 2026-05-21 |
| 10. Hardening + Observability + Docs | 6/6 | ✓ Complete | 2026-05-21 |

**Tổng:** 13/13 phases COMPLETE ✅ — M2a 4/4 + M2b 9/9. **M2 v2.0 100% COMPLETE 38/38 REQ-ID 2026-05-21.**

---

## Dependencies Map

```
Phase 1 (Infra) ─→ Phase 2 (Schema) ─┬─→ Phase 3 (Auth) ─────────────────┐
                                     │                                   │
                                     └─→ Phase 4 (CocoIndex Flow) ──┐    │
                                          ★ M2a EXIT GATE           │    │
                                                                    ▼    ▼
                                                   Phase 5 (CRUD) ◄──────┤
                                                          │              │
                                                   Phase 6 (Search) ◄────┤
                                                          │              │
                                                   Phase 7 (Ask)         │
                                                          │              │
                                                   Phase 8 (FE smoke + Tear-down) ◄┘
                                                          │
                                          ┌──────────────┴──────────────┐
                                          ▼                              ▼
                                   Phase 8.1 (MCP)            Phase 9 (Eval)  ─┐
                                          │                                    │
                                   Phase 8.2 (MCP standalone)                  │
                                          │                                    │
                                   Phase 8.3 (MCP OAuth + HTTPS)               │
                                                                               ▼
                                                                   Phase 10 (Hardening)
```

---

## EXIT Criteria status (R3 mitigation — final)

| # | Trigger | Status |
|---|---|---|
| E1 | CocoIndex critical bug không có fix trong 14 ngày | ❌ NOT triggered — race condition Plan 04-08 vá in-place dưới 24h |
| E2 | pgvector p95 search latency >2000ms ở 50K chunks | ❌ NOT triggered — dataset M2 không đến 50K, p95 measure defer eval thật |
| E3 | Phase 1-3 vượt 21 ngày calendar | ❌ NOT triggered — Phase 1-3 hoàn tất trong 2 ngày (2026-05-13/14) |
| E4 | Hub isolation bug không fixable trong 7 ngày | ❌ NOT triggered — `test_hub_isolation.py` 6/6 critical PASS đầu lần (Phase 5/6) |
| E5 | Quality gate Phase 9 fail <60% top-3 dù iterate 3 vòng | ⏸ NOT measured — gate verdict cần OpenAI key thật, framework runnable đã chứng minh PASS smoke; defer HUMAN UAT |

**M2a EXIT GATE giữa Phase 4 và Phase 5:** ✅ PASSED 2026-05-21 — demo upload DOCX VN → chunks pgvector → SELECT verify thành công, user accept tiếp tục M2b.

---

*Archive created: 2026-05-21 (`/gsd-complete-milestone v2.0`)*
*Original ROADMAP.md preserved here verbatim trước khi collapse về 1 dòng link.*
