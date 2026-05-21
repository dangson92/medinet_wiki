# Milestones — MEDWIKI

Lịch sử các milestone đã chạy / abandon của dự án Medinet Wiki (Hub_All).

---

## v1.0 — RAG Quality with Docling — ❌ ABANDONED 2026-05-13

**Trạng thái khi abandon:** Code complete 100% (28 plans / 5 phase / 34 REQ), CHƯA runtime verify (chưa chạy `make eval-all`).

**Goal cũ:** Nâng chất lượng ingestion RAG bằng Docling (extract + chunk) trong service Python sidecar, gate top-3 retrieval ≥ 75% hoặc +15pp.

**Phases archive:** `.planning/milestones/v1.0-docling-rag/` chứa 5 phase + 1 backlog 999.1:

| # | Phase | Status | Commit cuối |
|---|---|---|---|
| 1 | Eval Dataset & Baseline Native | ✅ Completed | `f37cd96` |
| 2 | Docling Service (Python Sidecar) | 🟡 PARTIAL (8/8 plans code, smoke runtime defer) | — |
| 3 | Go Adapter & Pipeline Wiring | ✅ Completed (5/5 plans, 8/8 REQ) | `c7aa5b3` |
| 4 | Config Hot-Swap & Circuit Breaker | ✅ Completed (5/5 plans, 7/7 REQ) | `b52ec08` |
| 5 | Eval Compare & Quality Gate | ✅ Completed (5/5 plans, 4/4 REQ) | `3f54aee` |
| 999.1 | Incremental chunk re-embed (backlog) | Absorbed into M2 (cocoindex core value) | — |

**Lý do abandon (2026-05-13):**
- User quyết định pivot toàn bộ RAG sang **cocoindex** ([github.com/cocoindex-io/cocoindex](https://github.com/cocoindex-io/cocoindex)) v1.0.3+ thay vì Docling+Go tự build.
- Đi kèm rewrite backend Go → Python FastAPI (mục tiêu codebase đồng nhất).
- Migrate vector store ChromaDB → Postgres pgvector (bớt service, dùng Postgres sẵn có).
- M1 chưa chạy production (chỉ commit code, chưa user upload thật), không cần data migration.

**Code sẽ bị xóa trong M2 Phase 1:**
- `Hub_All/docling-pipeline/` (Python sidecar Docling)
- `Hub_All/eval/` (eval scripts cũ)
- `Hub_All/backend/internal/rag/`
- `Hub_All/backend/internal/embedding/`
- `Hub_All/backend/internal/llm/`
- `Hub_All/backend/internal/vectorstore/`
- `Hub_All/backend/internal/worker/`
- `Hub_All/backend/internal/storage/`
- Toàn bộ backend Go sau khi đã port logic sang FastAPI (M2 Phase cuối)

**Giá trị giữ lại từ M1:**
- Decision log + research Docling vs alternatives (lưu trong git history)
- Schema documents/hubs/users/audit_logs Postgres (giữ + migrate)
- Frontend React 19 (KHÔNG đổi)
- Knowledge: yêu cầu OCR tiếng Việt + table preservation cho scanned PDF y tế (sẽ ghi vào REQUIREMENTS M2 dưới dạng risk + open question)

**Pivot lần thứ 2:** Trước đó M1 đã pivot một lần từ "Multi-subdomain SPA" sang "RAG Quality with Docling" (2026-04-28). Lần này (2026-05-13) là pivot thứ 2 trong vòng 15 ngày — cần lưu ý về tốc độ thay đổi định hướng và rủi ro thrash.

---

## v2.0 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector) — ✅ SHIPPED 2026-05-21

**Status:** 100% COMPLETE — 13 phase / ~75 plan / 38/38 REQ-ID done. Tag `v2.0` (annotated, local — push remote defer user trigger). Archive: `.planning/milestones/v2.0-full-rag-rewrite/`.

**Goal:** Xóa toàn bộ stack RAG + backend Go hiện hữu, viết lại bằng **Python FastAPI + cocoindex v1.0.3+ + pgvector**. CocoIndex sở hữu indexing dataflow; FastAPI handle auth/hub/user/audit/search/ask; MCP server expose RAG tool cho AI client ngoài.

**Calendar:** Created 2026-05-13 → Shipped 2026-05-21 (~8 ngày calendar AI-assisted; M2a Phase 1-4 trong 2 ngày 13-14/05, M2b Phase 5-10 + 8.1/8.2/8.3 trong 5 ngày 17-21/05).

**Git range:** `db30528` (08.3 audit seed) → `2669cd4` (Plan 10-06 ship) — 55 commits trong session closeout cuối. Tổng commit M2 nhiều hơn (full range từ 2026-05-13).

### Phases shipped (13/13 ✅)

| # | Phase | Plans | Status | Completed |
|---|---|---|---|---|
| 1 | Infra Skeleton + Demolition + EXIT Criteria | 6/6 | ✅ | 2026-05-13 |
| 2 | Database Schema + Alembic Baseline | 5/5 | ✅ | 2026-05-13 |
| 3 | Auth Port + RBAC + Response Envelope | 5/5 | ✅ | 2026-05-14 |
| 4 | CocoIndex Flow MVP + Document Ingest | 8/8 | ✅ M2a EXIT GATE PASSED | 2026-05-21 |
| 5 | Hub + User + Audit + APIKey + Settings CRUD | 6/6 | ✅ | 2026-05-17 |
| 6 | Search API Single + Cross-Hub | 4/4 | ✅ | 2026-05-18 |
| 7 | Ask API + LiteLLM + Citation + Hot-Swap + Usage | 5/5 | ✅ | 2026-05-18 |
| 8 | Frontend E2E Smoke (TEARDOWN-01 pull-in 2026-05-14) | 5/5 | ✅ (human UAT 3 SC) | 2026-05-19 |
| 8.1 | MCP Server — Expose Wiki Tools | 3/3 | ✅ (human UAT SC1/SC5) | 2026-05-19 |
| 8.2 | MCP Service — Tách Process Độc Lập | 5/5 | ✅ (human UAT SC4) | 2026-05-19 |
| 8.3 | MCP OAuth 2.0 + Deploy Public HTTPS | 9/9 | ✅ (human UAT domain thật) | 2026-05-21 |
| 9 | Eval Framework + Quality Gate ≥75% top-3 | 5/5 | ✅ (gate verdict OpenAI key thật = human UAT) | 2026-05-21 |
| 10 | Hardening + Observability + Docs | 6/6 | ✅ | 2026-05-21 |

### Key accomplishments

1. **Backend rewrite Go → Python FastAPI** — JWT RS256 (PKCS#8) + Argon2 cross-compat Go params `m=65536,t=3,p=4` (DOC-BUG fix: prev REQUIREMENTS ghi `t=1,p=2` SAI; Go source là source of truth) + envelope `{success,data,error,meta}` + RBAC `require_role` + Redis SETNX refresh-race lock + async session pool lifespan-managed.
2. **CocoIndex 1.0.3 ingest dataflow** — extract whitelist + scanned PDF → `failed_unsupported` (R4) + chunk VN regex + LiteLLM embed dim 1536 (R1 + R7 hot-swap) + pgvector HNSW + content-hash incremental dedup + `BackgroundTasks` thay LISTEN/NOTIFY (cocoindex 1.0.3 KHÔNG support) + heartbeat watchdog 300s + race pool A/B vá Plan 04-08; M2a EXIT GATE demo PASS.
3. **pgvector + HNSW search single + cross-hub** — `vector_cosine_ops` + `ef_search=200` + `iterative_scan=relaxed_order` + Redis cache TTL 5' hub-tagged Pub/Sub invalidate; E4 hub-isolation 6/6 critical PASS Phase 5/6.
4. **Ask API + LiteLLM citation** — `[N]` map deterministic chunk_id + anti-injection prompt + cross-hub + hot-swap within dim 1536 (cross-dim REFUSE 400) + token usage `BackgroundTasks` ghi `usage_events`; integration 18 test / 11 critical PASS.
5. **MCP server cho AI client ngoài** — Phase 8.1 in-process FastMCP 3 tool `search_wiki`/`ask_wiki`/`list_hubs` → Phase 8.2 đảo D-04 tách process `mcp_service/` gọi API HTTP → Phase 8.3 OAuth 2.0 + DCR + Caddy auto-TLS + 9 plan (4 gốc + 5 gap closure audit 2026-05-21 đóng CRIT-01 CORS split + HIGH-02 refresh-family revoke + HIGH-03 concurrency lock); mcp_service 135/135 PASS.
6. **Eval framework Python pytest** — `make eval-smoke` mock <60s + `make eval-all` real LLM gate verdict + `report.py` 7 section EVAL.md + `gate_verdict(top_3)` dict 3 field (≥0.75 PASS / 0.60-0.75 FAIL / <0.60 trigger E5) + pytest smoke regression CI gate `pytest -m critical api/tests/integration/test_eval_pipeline.py` < 60s zero external dep.
7. **Hardening + observability + docs** — structlog JSON 10 field match Go log/slog + ContextVar `request_id` propagate qua `asyncio.create_task` copy_context + Prometheus `/metrics` 5 metric + critical-path coverage 57.75% ≥50% gate + GitHub Actions `test.yml` 7 step `--cov-fail-under=50` hardcode + `lint.yml` secret detection guard 3 pattern + README + DEPLOY 7 section backup 6 artifact + 2 .env.example + CLAUDE.md M2 closeout section + CONVENTIONS Plan 10-01 note.
8. **Demolition M1 (TEARDOWN-01)** — `Hub_All/backend/` Go pull-in xoá sớm 2026-05-14 theo user decision (git tag `m1-go-archived` backup); `docling-pipeline/` + `eval/` cũ xoá Phase 1; ChromaDB hoàn toàn không reference.

### Issues encountered & resolutions

- **Argon2 doc-bug** (Plan 03-03): REQUIREMENTS/PITFALLS/CLAUDE ghi `t=1,p=2` SAI; Go source `backend/internal/pkg/hash/argon2.go:13-19` là source of truth `t=3,p=4` → fix in-place + production seed hash verify prefix `$argon2id$v=19$m=65536,t=3,p=4$`.
- **CocoIndex 1.0.3 actual API khác research** (Phase 4): `cocoindex.sources.Postgres(notification=PostgresNotification(...))` không tồn tại → REVISION 2 dùng `coco.App + VectorSchema + mount_table_target` + `BackgroundTasks trigger_cocoindex_update` chạy `cocoindex_app.update_blocking()` ngay sau response 202.
- **Race pool A/pool B** (Plan 04-08, debug session 2026-05-21 `cocoindex-zero-chunks-docx-vn`): SQLAlchemy commit pool A vs cocoindex asyncpg pool B REPEATABLE READ snapshot → initial delay 0.1s + retry loop max 3 attempts linear backoff trong `trigger_cocoindex_update`.
- **mcp 1.27.1 thay 1.9.4** (Phase 8.1 LANDMINE): `combine_lifespans` không tồn tại upstream → tự viết `_composed_lifespan`; pin `mcp>=1.27.0,<1.28`.
- **OAuth audit 2026-05-21** (Phase 8.3): sau 12 hot-fix phát hiện 3 Critical mới (CORS double-add path-prefix + cross-client code exchange + DCR redirect_uri whitelist) → 3 plan gap closure 08.3-07/08/09 đóng tất cả, mcp_service 135/135 PASS, pytest -m critical 17/17 PASS.
- **CRIT-01 CORS allow_origins=`*` cho /token /authorize /revoke** (Phase 8.3 audit): tách `MultiPolicyCORSMiddleware` ASGI metadata wildcard `*` vs sensitive whitelist origin từ `mcp_oauth_sensitive_allowed_origins` (default 4 origin: claude.ai + Inspector + 2 localhost:6274); Plan 10-04 đóng.

### Known deferred items (recorded — KHÔNG block close)

| Type | Item | Tracker |
|---|---|---|
| HUMAN UAT | Phase 9 gate verdict ≥75% top-3 với OpenAI key thật (~$0.20/run) | Track standalone `make eval-all` |
| HUMAN UAT | Phase 8.3 — kết nối Claude web "Add custom connector" tới domain MeWiki MCP thật | `08.3-HUMAN-UAT.md` |
| HUMAN UAT | Phase 8 — render 11 trang React + citation `[1]` clickable + docker compose 5-service healthy | `08-HUMAN-UAT.md` |
| HUMAN UAT | Phase 8.1 SC1/SC5 + Phase 8.2 SC4 (`usage_events` E2E thật) | `08.1-HUMAN-UAT.md` + mcp_service README |
| Tech debt | Migrate service module log cũ sang `structlog.get_logger` (Plan 10-01 chỉ HARD-01 ship) | DEF-10-01-B → v4.0 |
| Tech debt | Branch protection rule GitHub repo enforce 2 workflow trước merge main | Cần admin permission → v4.0 |
| Tech debt | Push tag `v2.0` lên remote | Defer user trigger sau verify |

> **CRIT-01 status:** ✅ Đã ĐÓNG Plan 10-04 (2026-05-21) — KHÔNG còn defer.

### Key decisions (carry forward to v3.0)

- **D-V3-01..04 LOCKED 2026-05-21:** Multi-DB cùng instance + chunks+vector sync 1 chiều + milestone-level scoping + M2 closeout precondition.
- **Anti-pivot R3 mitigation success:** E1-E5 EXIT criteria không trigger; M2a EXIT GATE PASSED; weekly check-in (day 7/14/21/28) achieve trước thời hạn.

Full archive: `.planning/milestones/v2.0-full-rag-rewrite/ROADMAP.md` + `REQUIREMENTS.md`.

---

## Milestones tương lai (sau v2.0)

### v3.0 — Multi-Hub Split (SEEDED 2026-05-21 — chờ trigger)

**Goal redefine:** Tách hub con (y_te, dược, HCNS) sang multi-tenancy PHYSICAL — mỗi hub con có process + Postgres database riêng cùng 1 instance, hub tổng aggregator nhận chunks + vector sync 1 chiều. URL subpath `wiki.domain.com/<ten_hub>` thay subdomain (đảo PRD v1.3 cũ).

**Trigger condition:** `/gsd-new-milestone v3.0` sau khi user verify v2.0 closeout (HUMAN UAT Phase 9 gate verdict ≥75% + retrospective).

**4 D-V3 LOCKED 2026-05-21:** multi-DB cùng instance + chunks+vector denormalized sync 1 chiều + milestone-level scoping + M2 closeout precondition.

**4 GA-V3 open question:** Auth SSO design + system settings sync + reverse proxy prefix detect + migration data từ `medinet_central` cũ.

Seed full: `.planning/seeds/v3.0-multi-hub-split.md` (7 phase ~35 plan + 4 R-V3 risk + 4 E-V3 exit criteria).

### v4.0 — Production Hardening + Advanced RAG (Backlog)

MCP Server đã ship trong v2.0 (Phase 8.1/8.2/8.3) → v4.0 còn lại: OCR Vietnamese revisit nếu user feedback regress + cross-dim embedding swap 1536↔3072 + streaming `/api/ask` SSE + comprehensive coverage >80% + cocoindex augmenter Q&A pair gen + Postgres pg17 upgrade + email send + avatar upload S3/GCS + GDrive file storage backend + khắc phục CONCERNS bảo mật cũ (`.gitignore` root, GCP key audit, AES_KEY rotation, XSS token storage migration httpOnly cookie) + branch protection GitHub repo.

### v4.1+ — Advanced RAG

Hybrid retrieval BM25 + reranker (Cohere / cross-encoder) + version history & concurrent editing + local embedding model (sentence-transformers / BGE-M3 cho on-prem).

---

*Last updated: 2026-05-21 (M2 v2.0 SHIPPED 100% COMPLETE 38/38 REQ-ID; v3.0 SEEDED chờ trigger)*
