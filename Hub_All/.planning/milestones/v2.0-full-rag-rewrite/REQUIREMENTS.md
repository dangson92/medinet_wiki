# Archive — Milestone v2.0 REQUIREMENTS (Full RAG Rewrite)

> **Archived:** 2026-05-21 (`/gsd-complete-milestone v2.0`)
> **Status:** ✅ ALL COMPLETE — 38/38 v1 REQ-ID done
> **Core Value:** Ingestion tri thức Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức — OCR tiếng Việt cho scanned PDF defer M2 vì D4) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.

> ℹ️ **Preserve note:** File gốc `.planning/REQUIREMENTS.md` được GIỮ LẠI (KHÔNG `git rm` như workflow gốc) theo user request — v3.0 sẽ overwrite qua `/gsd-new-milestone v3.0`. File archive này là snapshot tại closeout.

---

## Coverage Summary

| Category | REQ Count | Complete | % |
|---|---|---|---|
| CORE | 5 | 5 | 100% |
| AUTH | 6 | 6 | 100% |
| HUB | 3 | 3 | 100% |
| USER | 3 | 3 | 100% |
| INGEST | 8 | 8 | 100% |
| SEARCH | 4 | 4 | 100% |
| ASK | 5 | 5 | 100% |
| AUX (Audit + APIKey + Rate-limit) | 3 | 3 | 100% |
| EVAL | 4 | 4 | 100% |
| COMPAT (frontend smoke) | 1 | 1 | 100% |
| TEARDOWN (Go backend remove) | 1 | 1 | 100% |
| MCP (inserted 08.1/8.2/8.3) | 2 | 2 | 100% |
| HARD (Hardening + Observability + Docs) | 4 | 4 | 100% |
| **TOTAL** | **49** | **49** | **100%** |

> Lưu ý: 38 REQ-ID v1 gốc roadmap + 2 MCP-01/02 (vốn defer v4.0 kéo lên Phase 8.1) + thực thi splitting; tổng đếm theo nhóm 49 bao gồm cả MCP. Roadmap-level "38/38" giữ con số gốc cho lịch sử.

---

## Traceability (final — all complete)

| REQ-ID | Description | Phase | Status | Completed |
|---|---|---|---|---|
| CORE-01 | `Hub_All/api/` Python skeleton (pyproject.toml + uv lockfile + Dockerfile + ruff + mypy + pytest); pin `python>=3.11,<3.13`, `fastapi==0.136.1`, `cocoindex==1.0.3` | Phase 1 | ✅ Complete | 2026-05-13 |
| CORE-02 | `docker-compose.yml` 3 services (pgvector pg16 + redis 7 + python-api); init 2 logical DB + `CREATE EXTENSION vector` + verify HNSW 1536-dim build (R1) | Phase 1 + 2 | ✅ Complete | 2026-05-13 |
| CORE-03 | Xoá code cũ — `Hub_All/docling-pipeline/`, `Hub_All/eval/`, `chroma_data/`; cập nhật `.gitignore` cho `api/keys/`, `api/.venv/`, `medinet_pgdata/` | Phase 1 | ✅ Complete | 2026-05-13 |
| CORE-04 | FastAPI app factory `api/app/main.py` với `lifespan` (init+abort `cocoindex.FlowLiveUpdater`), pydantic-settings, envelope `{success,data,error,meta}`, `GET /healthz` + `/readyz` | Phase 1 | ✅ Complete | 2026-05-13 |
| CORE-05 | `.planning/CONVENTIONS.md` mới — test strategy critical-path, naming snake_case cocoindex (R5), `APP_NAMESPACE=medinet_prod` cố định, middleware order REVERSED Go-pattern, logging fields match Go `log/slog` | Phase 1 | ✅ Complete | 2026-05-13 |
| AUTH-01 | `POST /api/auth/login` — verify Argon2 → JWT RS256 access 15min + refresh 7d, envelope match Go contract | Phase 3 Plan 03-04 | ✅ Complete | 2026-05-14 |
| AUTH-02 | `POST /api/auth/refresh` — rotate token với Redis SETNX (P16) chống concurrent race; blacklist old jti | Phase 3 Plan 03-04 | ✅ Complete | 2026-05-14 |
| AUTH-03 | `GET /api/auth/me` (Bearer) + `POST /api/auth/logout` blacklist refresh token | Phase 3 Plan 03-04 | ✅ Complete | 2026-05-14 |
| AUTH-04 | RBAC `require_role` factory + 403 cho viewer/editor trên admin endpoint + envelope handler | Phase 3 Plan 03-05 | ✅ Complete | 2026-05-14 |
| AUTH-05 | Argon2 cross-compat test R6 — pwdlib verify Go `alexedwards/argon2id` hash với params `m=65536,t=3,p=4,saltLen=16,keyLen=32` (DOC-BUG fix: prev `t=1,p=2` SAI; Go source là source of truth) | Phase 3 Plan 03-03 | ✅ Complete | 2026-05-14 |
| AUTH-06 | JWT keypair PKCS#1 vs PKCS#8 verify + PyJWT RS256 wrapper; 5 attack vector reject | Phase 3 Plan 03-02 | ✅ Complete | 2026-05-14 |
| INGEST-01 | `app/rag/flow.py` cocoindex flow `medinet_wiki_ingest` — REVISION 2 dùng `BackgroundTasks trigger_cocoindex_update` thay LISTEN/NOTIFY (cocoindex 1.0.3 không support) | Phase 4 Plan 04-03/04 | ✅ Complete | 2026-05-14 |
| INGEST-02 | Flow transform — extract whitelist `{docx,txt,md,pdf}` + detect scanned PDF → `failed_unsupported` (R4) + RecursiveSplitter VN regex + LiteLLM `aembedding` dim 1536 (R1) | Phase 4 Plan 04-02 | ✅ Complete | 2026-05-14 |
| INGEST-03 | Flow target `chunks` table — UUID PK + FK + `content_hash BYTEA` + `vector vector(1536)` HNSW `vector_cosine_ops` + `(hub_id,document_id)` B-tree | Phase 4 Plan 04-03 | ✅ Complete | 2026-05-14 |
| INGEST-04 | `POST /api/documents/upload` (multipart) — save `file_store/` + INSERT documents `pending` + return 202 + document_id + `BackgroundTasks` trigger | Phase 4 Plan 04-04 | ✅ Complete | 2026-05-14 |
| INGEST-05 | `GET /api/documents/:id` — return `status` + `chunk_count`; enum `pending|processing|completed|failed|failed_unsupported` (R4 + P8) | Phase 4 Plan 04-04 | ✅ Complete | 2026-05-14 |
| INGEST-06 | Heartbeat `documents.last_heartbeat` + `attempts` + watchdog asyncio task flip `processing > 300s` → `failed` (configurable `WATCHDOG_TIMEOUT_SECONDS`) | Phase 4 Plan 04-05 | ✅ Complete | 2026-05-14 |
| INGEST-07 | `DELETE /api/documents/:id` — delete + cocoindex tombstone + audit `document.delete` | Phase 4 Plan 04-05 | ✅ Complete | 2026-05-14 |
| INGEST-08 | `GET /api/documents` list + filter `hub_id`/`status`/`uploaded_by`/`filename`; pagination cap 100 | Phase 4 Plan 04-05 | ✅ Complete | 2026-05-14 |
| HUB-01 | `GET/POST /api/hubs` + `GET/PUT /:id` + `PATCH /:id/status` (D-07 PUT update KHÔNG PATCH; status endpoint riêng; D-06 KHÔNG test-connection); drop col `chroma_collection`/`db_*` (D-05); pagination cap 100 | Phase 5 Plan 05-03 | ✅ Complete | 2026-05-17 |
| HUB-02 | Hub isolation enforce ở repo layer — `WHERE hub_id` từ user hub_assignments, editor Hub A KHÔNG thể PATCH/DELETE doc Hub B kể cả explicit `hub_id` payload; audit `security.hub_isolation_violation`; test integration mandatory | Phase 5 Plan 05-02 + 05-06 | ✅ Complete (E4 6/6 PASS) | 2026-05-17 |
| HUB-03 | `GET /api/hubs/:id/stats` — counts documents/chunks/users từ Postgres aggregate; `query_count` defer Phase 6/7 | Phase 5 Plan 05-03 | ✅ Complete | 2026-05-17 |
| USER-01 | `GET/POST /api/users` + `PATCH /:id/role` + `PATCH /:id/status` (D-07 update tách 3 endpoint) — admin-only CRUD user | Phase 5 Plan 05-04 | ✅ Complete | 2026-05-17 |
| USER-02 | `POST /api/users/:id/reset-password` — admin trigger, token Redis ex=3600 + log console (email defer v4.0) | Phase 5 Plan 05-04 | ✅ Complete | 2026-05-17 |
| USER-03 | `GET/PUT /api/profile` self-scoped + `POST /api/profile/password`; D-07 KHÔNG `:id` param | Phase 5 Plan 05-04 | ✅ Complete | 2026-05-17 |
| AUX-01 | Audit logger `asyncio.Queue` batch 2s/128 → `audit_logs`; `GET /api/audit-logs` admin-only | Phase 5 Plan 05-01 + 05-05 | ✅ Complete | 2026-05-17 |
| AUX-02 | API key CRUD AES-GCM encrypt-at-rest + soft revoke + `X-API-Key` dep require_api_key + audit-logs query | Phase 5 Plan 05-05 + 05-06 | ✅ Complete | 2026-05-17 |
| AUX-03 | Rate limit slowapi — 100 req/min `/api/search` + 30 req/min upload; KHÔNG limit `/api/auth/me`; X-API-Key auth song song JWT | Phase 5 Plan 05-02 + 05-06 | ✅ Complete | 2026-05-17 |
| SEARCH-01 | `POST /api/search` (D-02 dùng POST + body `query`/`hub_ids`/`top_k` khớp `api.ts`) — direct pgvector raw SQL, bypass cocoindex hoàn toàn | Phase 6 Plan 06-01/02 | ✅ Complete | 2026-05-18 |
| SEARCH-02 | Per-query `SET LOCAL hnsw.ef_search=200` + connection-level `iterative_scan=relaxed_order` + `max_scan_tuples=20000` (R2); p95 target <800ms single hub | Phase 6 Plan 06-01 | ✅ Complete (p95 đo dataset thật defer HUMAN UAT) | 2026-05-18 |
| SEARCH-03 | `POST /api/search/cross-hub` body `{q, hub_ids[]}` — `asyncio.gather` + re-rank + defense in depth `intersect_hubs` ở repo layer | Phase 6 Plan 06-02 | ✅ Complete | 2026-05-18 |
| SEARCH-04 | Redis cache TTL 5' + hub-tagged invalidate Pub/Sub channel `hub:{hub_id}:invalidate` + subscriber lifespan task | Phase 6 Plan 06-01 + 06-03 | ✅ Complete | 2026-05-18 |
| ASK-01 | `POST /api/ask` — search top-k + prompt `[N]` + LiteLLM `acompletion` non-streaming + parse marker → citations `{chunk_id, document_id, score, content_snippet}` | Phase 7 Plan 07-04 + 07-05 | ✅ Complete | 2026-05-18 |
| ASK-02 | Anti-injection system prompt — "CHỈ trả lời từ context, format `[N]` cho citation"; test user query bypass prompt KHÔNG bypass được | Phase 7 Plan 07-01 + 07-05 | ✅ Complete (hành vi LLM thật defer Phase 9) | 2026-05-18 |
| ASK-03 | `POST /api/ask/cross-hub` — như ASK-01 + SEARCH-03 chunks từ nhiều hub; citation kèm `hub_id` | Phase 7 Plan 07-04 + 07-05 | ✅ Complete | 2026-05-18 |
| ASK-04 | `GET/PUT /api/rag-config` admin hot-swap embedding + LLM provider; within dim 1536 WARNING modal, cross-dim 1536↔3072 REFUSE 400 (R7 mitigation, cross-dim defer v4.0) | Phase 7 Plan 07-03 | ✅ Complete | 2026-05-18 |
| ASK-05 | Token usage logging `BackgroundTasks` async ghi `usage_events` (user_id, hub_id, model, tokens, cost_usd, request_id); `GET /api/usage` aggregate | Phase 7 Plan 07-02 + 07-04 + 07-05 | ✅ Complete | 2026-05-18 |
| COMPAT-01 | Boot stack mới + smoke 12 trang React golden path PASS (trừ SyncQueue D-01 loại); VN filename UTF-8 ("Khám bệnh đa khoa.docx"); response envelope match `git show m1-go-archived:Hub_All/backend/internal/router/router.go` | Phase 8 (5 plans) | ✅ Complete (verify human_needed — `08-HUMAN-UAT.md`) | 2026-05-19 |
| TEARDOWN-01 | Xoá `Hub_All/backend/` Go + update `docker-compose.yml` + `Makefile` root + CLAUDE.md reflect Python stack + git tag `m1-go-archived` backup | Pull-in Phase 8 sớm 2026-05-14 | ✅ Complete | 2026-05-14 |
| MCP-01 | MCP server Streamable HTTP `/mcp` expose 3 tool read-only (`search_wiki`/`ask_wiki`/`list_hubs`) cho AI client ngoài (Claude Desktop, Cursor) + auth `X-API-Key` | Phase 8.1 (3 plans) → Phase 8.2 (tách process) → Phase 8.3 (OAuth + HTTPS) | ✅ Complete | 2026-05-21 |
| MCP-02 | Tool exposure scoped theo hub_id + hub isolation enforce; OAuth 2.0 + DCR + Caddy auto-TLS cho Claude web "Add custom connector" | Phase 8.1 + 8.2 + 8.3 (9 plans) | ✅ Complete (kết nối Claude web real domain — human UAT `08.3-HUMAN-UAT.md`) | 2026-05-21 |
| EVAL-01 | Dataset 10 file VN medical (8 sources + 2 scanned) restore byte-identical từ git `0af44f0` M1 archive + `queries.jsonl` 12 truy vấn vàng schema M2 `hub_id="eval_hub"` + `seed_hub.sql` idempotent | Phase 9 Plan 09-01 | ✅ Complete | 2026-05-21 |
| EVAL-02 | `run_eval.py` orchestrator 8-step pytest-based — preflight → resolve hub → cleanup → login + upload 10 file → settle → run 12 query → metrics → write `results.json` + `EVAL.md` + exit verdict; `cleanup.py` mixed strategy 3 layer (API DELETE + Postgres defensive + Redis cache) | Phase 9 Plan 09-04 | ✅ Complete | 2026-05-21 |
| EVAL-03 | `report.py` `EVAL.md` generator 7 section qua `tabulate` + `gate_verdict(top_3)` dict 3 field (≥0.75 PASS exit 0 / 0.60-0.75 FAIL exit 1 / <0.60 trigger E5 STOP M2b); 17 unit test PASS | Phase 9 Plan 09-03 | ✅ Complete | 2026-05-21 |
| EVAL-04 | `Makefile` 8 target eval-* (install/seed/clean/smoke/all/report/readme/restore) + `eval/README.md` 249 dòng 8 section + pytest smoke regression `test_eval_pipeline.py` 3 critical test CI gate `< 60s` zero OpenAI key | Phase 9 Plan 09-04 + 09-05 | ✅ Complete (gate verdict ≥75% real LLM = HUMAN UAT track standalone) | 2026-05-21 |
| HARD-01 | structlog JSON output 10 field match Go log/slog + `RequestIdMiddleware` UUID4 + 3 ContextVar + lifespan wire + cocoindex BackgroundTask `copy_context` propagate | Phase 10 Plan 10-01 | ✅ Complete | 2026-05-21 |
| HARD-02 | Prometheus `/metrics` outside `/api/*` + 5 metric (counter requests_total/errors_total + histogram request_duration_seconds/search_latency_seconds/ingest_duration_seconds) + PrometheusMiddleware + instrument search/ingest | Phase 10 Plan 10-02 | ✅ Complete | 2026-05-21 |
| HARD-03 | Integration test critical-path ≥50% coverage — 5 acceptance test suite `test_critical_path_coverage.py` + `.coveragerc-critical` scope 17 file + GitHub Actions `test.yml` 7 step `--cov-fail-under=50` hardcode YAML; coverage thực đo 57.75% PASS | Phase 10 Plan 10-03 + 10-06 | ✅ Complete | 2026-05-21 |
| HARD-04 | README + DEPLOY (7 section + backup 6 artifact) + 2 .env.example + CLAUDE.md M2 closeout + CONVENTIONS Plan 10-01 note + lint.yml secret detection guard 3 pattern OpenAI/Gemini/AWS | Phase 10 Plan 10-05 + 10-06 | ✅ Complete | 2026-05-21 |

---

## Out of Scope (M2) — carry forward to v3.0/v4.0/v4.1

| Feature | Defer milestone | Reason |
|---|---|---|
| OCR Vietnamese cho scanned PDF | v4.0 | D4 gỡ Docling. M2 ship với enum `failed_unsupported`. Revisit nếu user feedback regress. |
| Table preservation phức tạp (merged cells, rowspan/colspan) | v4.0 | Không có Python lib battle-tested cho VN medical PDF. Camelot/pdfplumber test Phase 4 fail-fast accept-loss. |
| Frontend rewrite / Multi-subdomain SPA | v3.0 | D6 — defer; M2 giữ React 19 không sửa. |
| Cross-dim embedding swap (1536 ↔ 3072) | v4.0 | Triggers full re-embed (~$6.50/100K chunks). M2 PIN 1536 cả 2 provider. |
| Streaming `/api/ask` qua SSE | v4.0 | Citation parsing mid-stream phức tạp. Non-streaming match M1 contract. |
| Hybrid retrieval BM25 + dense | v4.1 | Phase 2 PRD original. |
| Reranker (Cohere / cross-encoder) | v4.1 | Defer. |
| Local embedding model (sentence-transformers/BGE-M3) | v4.1 | Giữ OpenAI/Gemini hot-swap. |
| Version history & concurrent editing | v4.1 | Phase 3 PRD original. |
| Comprehensive test coverage >80% | v4.0 | M2 chỉ critical path 50%+. |
| Cocoindex augmenter (Q&A pair gen) | v4.0 | Go source archived ở tag `m1-go-archived`. |
| Email send (password reset, notification) | v4.0 | M2 log only. |
| Avatar upload + S3/GCS file storage | v4.0 | Defer. |
| GDrive file storage backend | v4.0 | Defer. |
| Postgres pg16 → pg17 upgrade | v4.0 | Defer. |
| Khắc phục CONCERNS bảo mật cũ (`.gitignore` root, GCP key audit, AES_KEY rotation, XSS token storage migration httpOnly cookie) | v4.0 | Hardening. |
| Cocoindex worker tách container | v4.0 | M2 in-process đủ 100 docs/day. |
| WebSocket job progress | v4.0 | Frontend poll đủ. |
| GraphQL | — | KHÔNG add abstraction layer. |
| LangChain / LlamaIndex | — | CocoIndex + LiteLLM trực tiếp đủ. |
| Migrate service module log cũ sang `structlog.get_logger` | v4.0 | DEF-10-01-B — Plan 10-01 chỉ ship HARD-01 build pipeline. |
| Branch protection rule GitHub repo | v4.0 | Cần admin permission. |

---

## Open Questions resolved during v2.0

1. **Storage backend** (Phase 4) — chốt local `file_store/` default; GDrive port defer v4.0.
2. **JWT keypair format** (Phase 3) — verify PKCS#8 OK; PyJWT RS256 wrapper PASS 8 unit + 5 attack vector reject.
3. **PDF table extraction lib** (Phase 4) — chốt accept-loss; pdfplumber/camelot defer (R4 → 415 `failed_unsupported` cho scanned).
4. **Cocoindex augmenter** (Phase 4) — skip M2, defer v4.0 archive Go source ở `m1-go-archived`.
5. **Embedding dim 1536 vs 3072 VN quality** (Phase 9) — gate verdict ≥75% chạy với real OpenAI key = HUMAN UAT standalone track; framework runnable đã chứng minh PASS smoke.

---

*Requirements archived: 2026-05-21 (`/gsd-complete-milestone v2.0`)*
*Original `.planning/REQUIREMENTS.md` preserved (KHÔNG `git rm` per user request) — v3.0 sẽ overwrite qua `/gsd-new-milestone v3.0`.*
