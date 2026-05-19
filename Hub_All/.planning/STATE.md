---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
status: Executing Phase 08.2
last_updated: "2026-05-19T15:00:00Z"
progress:
  total_phases: 12
  completed_phases: 9
  total_plans: 51
  completed_plans: 50
  percent: 98
---

# State — MEDWIKI

**Mã dự án:** MEDWIKI
**Milestone:** v2.0 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)
**Ngày tạo state:** 2026-05-13 (pivot lần 2 — M1 Docling abandoned)
**Last updated:** 2026-05-19 (Phase 8.2 Plan 03 — lõi MCP Service standalone: FastMCP + 3 tool gọi API qua HTTP + entrypoint; 24/24 test PASS)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-13) + `.planning/ROADMAP.md` (created 2026-05-13)

**Core value:** Ingestion tri thức của Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức, OCR tiếng Việt cho scanned PDF — defer trong M2 vì D4) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.

**Current focus:** Phase 08.2 — mcp-service-standalone-process

**Mode:** YOLO · **Granularity:** Large (10 phase — reconciled từ FEATURES 8 + ARCHITECTURE 12 trong SUMMARY.md) · **Phase numbering:** Reset về Phase 1 (`--reset-phase-numbers`)

**M2a/M2b split (R3 anti-pivot fatigue mitigation):**

- **M2a = Phase 1-4** (Infra + Schema + Auth + CocoIndex MVP) — Có thể ship standalone. Nếu user accept M2a → never pivot.
- **M2b = Phase 5-10** (CRUD + Search + Ask + Frontend smoke + Eval + Hardening) — Pivot M2b OK nếu cocoindex critical fail.
- 🚦 **M2a EXIT GATE** giữa Phase 4 và Phase 5 — demo upload DOCX → chunks pgvector → SELECT verify. User accept là điều kiện tiếp tục M2b.

---

## Current Position

Phase: 08.2 (mcp-service-standalone-process) — EXECUTING
Plan: 5 of 5 (08.2-01 ✅ + 08.2-02 ✅ + 08.2-03 ✅ + 08.2-04 ✅ COMPLETE 2026-05-19)
- 08.2-04 ✅: gỡ MCP server in-process khỏi API Service — main.py không còn `/mcp`, `_composed_lifespan`, `_mcp_app`, `mcp_set_pool` (dùng `FastAPI(lifespan=lifespan)` trực tiếp); xoá hẳn package `api/app/mcp/` (4 file) + test `api/tests/unit/mcp/` (4 file, 939 dòng); gỡ dependency `mcp>=1.27.0,<1.28` khỏi `pyproject.toml` (httpx giữ). Đảo D-04 hoàn tất ở tầng API Service — API Service không còn biết gì về MCP. SC1 phase đạt. 2 task, regression 119 unit PASS, `create_app()` 59 routes không còn route `/mcp`.
- 08.2-03 ✅: lõi MCP Service — auth.py trích X-API-Key từ HTTP header (bỏ verify DB); server.py FastMCP + 3 tool (list_hubs/search_wiki/ask_wiki) gọi API Service qua HTTP bằng ApiClient, map 401/403/400/5xx → ToolError; entrypoint build_asgi_app()+main() chạy standalone qua `python -m mcp_app.server` port 8190. Đảo D-04 hoàn tất ở tầng tool. 3 task (TDD Task 1+2), 14 test mới PASS (5 auth + 9 server), tổng 24/24 test mcp_service PASS, ruff clean. MCP-02: expose 3 tool, list_documents/get_document DEFER (nợ kỹ thuật).
- 08.2-02 ✅: mở auth API Service cho MCP Service — get_api_key_or_jwt_with_hubs (X-API-Key HOặC JWT → UserWithHubs); 4 endpoint search/ask + GET /api/hubs nhận X-API-Key; HubService.list_for_hubs scope non-admin. BLOCKER fix SC2/SC3/SC4. 3 task, 13 test PASS, regression 122 unit PASS.
| Field | Value |
|---|---|
| Milestone | v2.0 Full RAG Rewrite |
| Phase | **Phase 8 — Frontend E2E Smoke** ✅ COMPLETE (4/4 plans, 2026-05-19) · Phase 7 ✅ COMPLETE trước đó (5/5 plans) |
| Plan | 08-01 ✅ (Wave 1: contract diff script + báo cáo — COMPAT-01). 08-02 ✅ (Wave 2: fix gap api-side router /api/ai/chat + port 8180 — COMPAT-01). 08-03 ✅ (Wave 3: test suite tự động golden path + VN filename — COMPAT-01). 08-04 ✅ (Wave 4: boot stack + checklist + biên bản UAT — COMPAT-01). 08-05 ✅ (Wave 5: gap closure SC5 — fix cocoindex LMDB Permission denied; `boot_stack.sh` 6/6 PASS). Tất cả 2026-05-19. |
| Status | **Phase 8 COMPLETE — user accept đóng phase 2026-05-19.** Frontend E2E Smoke verify-only, KHÔNG sửa frontend (D6 tôn trọng tuyệt đối — 0 file `frontend/` toàn phase). 08-01 đối chiếu contract 54 endpoint `api.ts` ↔ router FastAPI ↔ Go signature `m1-go-archived` → `08-CONTRACT-DIFF.md` (SC3). 08-02 fix gap api-side: router `POST /api/ai/chat` proxy LiteLLM + port mapping `8180:8080` + CORS dev (SC1/SC5). 08-03 test integration golden path API + VN filename UTF-8 (SC2/SC4 — 2 test critical PASS per-file). 08-04 `boot_stack.sh` + `08-SMOKE-CHECKLIST.md` + checkpoint human-verify (auto-approve `--auto`). Verify `human_needed`: 8/11 must-have auto-verified, regression 109/109 unit PASS, code review 0 Critical/3 Warning/5 Info (`08-REVIEW.md`). 3 mục cần con người (SC1 render 11 trang React, SC2-browser citation `[1]` clickable, SC5 docker compose healthy) defer sang `/gsd-verify-work 8` — lưu `08-HUMAN-UAT.md` (status partial, 2 passed / 3 pending) — cùng pattern Phase 6/7. ⚠️ Khôi phục: `ROADMAP.md` bị gsd-planner cắt cụt 464→10 dòng ở commit `15cbb22`, đã restore đầy đủ từ git `6040c46`. Khuyến nghị verify Phase 8 thật + chạy `/gsd-secure-phase 8` (security gate). |
| Last activity | 2026-05-19 — `/gsd-execute-phase 8.2`: thực thi 08.2-04 (Wave 3) — gỡ MCP server in-process khỏi API Service. `api/app/main.py`: gỡ block inject `mcp_set_pool` trong `lifespan()`, gỡ `_mcp_server`/`_mcp_app`/`_mcp_lifespan`/`_composed_lifespan` + `app.mount("/mcp", ...)` trong `create_app()`; đổi sang `FastAPI(lifespan=lifespan)` trực tiếp. Xoá hẳn package `api/app/mcp/` (`__init__.py`/`server.py`/`auth.py`/`schemas.py`) + thư mục test `api/tests/unit/mcp/` (4 file — 939 dòng). Gỡ dependency `mcp>=1.27.0,<1.28` khỏi `api/pyproject.toml` (`httpx` giữ — `ai_chat` router dùng). Đảo D-04 hoàn tất ở tầng API Service — API Service không còn biết gì về MCP; MCP là process riêng gọi API qua HTTP. **SC1 phase đạt:** `main.py` không còn `/mcp` + `_composed_lifespan`. 2 task, regression 119 unit PASS, `create_app()` 59 routes — không còn route `/mcp`. Trước đó 08.2-03 — lõi MCP Service standalone (FastMCP + 3 tool). |
| Total phases | 10 (M2a: 4 + M2b: 6) — Phase 1/2/3/5/6/7/8 complete · Phase 4 + M2a EXIT GATE chưa đóng (theo dõi riêng) |
| Total requirements | 38 v1 REQ-ID · 6 Phase 3 (AUTH-01..06) · 8 Phase 4 (INGEST-01..08) · 9 Phase 5 (HUB/USER/AUX) · 4 Phase 6 (SEARCH-01..04) · 5 Phase 7 (ASK-01..05) · **COMPAT-01 Phase 8** — lớp tĩnh/tự động ĐẠT (SC3/SC4 + regression); SC1/SC2-browser/SC5 chờ human UAT (`/gsd-verify-work 8`) |
| Critical path | 1 ✓ → 2 ✓ → 4 📋 → 6 ✓ → 7 ✓ → 9 → 10 |
| Auth branch | 3 ✓ (5/5 plans done) → 5 ✓ (6/6 plans done) → 8 ✓ (4/4 plans done) |

**Progress bar:** `[█████████░] 91% (Phase 8.1 ✅ COMPLETE — MCP Server 3/3 plans; verify human_needed — SC1/SC5 chờ /gsd-verify-work 8.1) · Next: Phase 9 Eval Framework + Quality Gate ≥75% top-3`

**Phase 8.1 — MCP Server ✅ COMPLETE (2026-05-19):** Phase chèn khẩn (defer v4.0 MCP-01/MCP-02 kéo lên). Research → pattern map → 3 plan → plan-checker `VERIFICATION PASSED` → execute 3 wave. MCP server Streamable HTTP mount `/mcp` cùng process FastAPI (D-02), 3 tool read-only `search_wiki`/`ask_wiki`/`list_hubs` gọi trực tiếp service layer (D-04), auth `X-API-Key` tái dùng `ApiKeyService.verify_key` (D-05), hub isolation enforce ở service layer (D-12/D-13), usage logging non-blocking (D-14). **Deviation:** `mcp` resolve `1.27.1` thay vì `1.9.4` research khuyến nghị — API khác (`streamable_http_app()`, `_composed_lifespan` tự viết, header qua `ctx.request_context`); code đã adapt, pin `>=1.27.0,<1.28`. **Code review:** 1 Critical CR-01 (`asyncio.create_task` usage-log drop âm thầm) ĐÃ VÁ — thêm `_spawn_usage_log` giữ strong reference + done-callback log lỗi; 4 Warning (WR-01/03/04 còn tồn — `08.1-REVIEW.md`). **Verify `human_needed`:** SC2/SC3/SC4 auto-verified, `tests/unit/mcp/` 9 PASS + regression 118 PASS, ruff clean; SC1 (kết nối AI client thật vào `/mcp`) + SC5 (`usage_events` ghi row với DB thật) chờ human UAT — `08.1-HUMAN-UAT.md` (status partial, 2 pending). Cùng pattern Phase 6/7/8.

---

## Performance Metrics

| Target | Source | Verified at |
|---|---|---|
| Search single-hub p95 <800ms | PRD v1.3 + PROJECT.md Constraints | Phase 6 (sanity) + Phase 9 (eval) |
| Search cross-hub p95 <1.5s | PRD v1.3 | Phase 6 + Phase 9 |
| CRUD endpoint p95 <300ms | PRD v1.3 | Phase 5 |
| Ingest 1 DOCX VN end-to-end <5s | Phase 4 MVP | Phase 4 |
| Quality gate top-3 retrieval ≥75% | EVAL-03 + Core Value | Phase 9 |
| Integration test coverage ≥50% critical path | HARD-03 | Phase 10 |
| HNSW recall WITH hub filter — measure ≥75% | R2 mitigation | Phase 9 |

---

## Accumulated Context

### Key decisions (lấy từ PROJECT.md)

- **D1: Toàn bộ backend Go → Python FastAPI** — codebase đồng nhất Python; tránh boundary Go↔Python phức tạp.
- **D2: CocoIndex v1.0.3+ làm indexing layer** — incremental diff content-hash + lineage built-in.
- **D3: Postgres pgvector** thay ChromaDB — bớt 1 service, dùng Postgres sẵn có.
- **D4: Gỡ Docling hoàn toàn** — ⚠️ risk regress scanned PDF tiếng Việt + bảng phức tạp; documented.
- **D5: LLM answerer giữ hot-swap OpenAI/Gemini** (port sang LiteLLM).
- **D6: Frontend KHÔNG sửa trong M2** — URL `/api/*` giữ nguyên.
- **D7: Abandon M1 hoàn toàn** — chưa runtime verify, chưa production.
- **D8: Eval framework làm lại từ đầu**.
- **D9: Phase numbering reset về 1**.
- **D-08-01: SC3 (replay/contract test) thoả qua đối chiếu TĨNH** — Go backend đã teardown 2026-05-14 nên không replay live được; đối chiếu 3 lớp (path api.ts↔FastAPI↔router.go, envelope shape, classification gap) qua script regex. Go signature lấy qua `git show m1-go-archived`.
- **D-08-01-B: `meta.total_pages` lệch nhỏ KHÔNG nâng BLOCKER** — `paginated()` FastAPI thiếu field `total_pages`; frontend khai báo optional → không crash render. Ghi nhận làm ứng viên polish Plan 08-02.
- **D-08-05: cocoindex LMDB path default TƯƠNG ĐỐI `.cocoindex/state.lmdb`** — KHÔNG dùng tuyệt đối `/app/...` (hỏng chạy native Windows). Container ép tuyệt đối qua env `COCOINDEX_DB` (`environment:` thắng `env_file:`). Pattern "default an toàn 2 môi trường + env override".
- **D-08-05-B: Follow-up `documents.file_path` nên lưu tương đối theo `FILE_STORE_DIR`** — hiện lưu tuyệt đối host (Windows path) → không portable host↔container, cocoindex backfill fail FileNotFoundError. Thuộc Phase 4/5, chưa xử lý.

### Risk register (active)

| # | Risk | Severity | Phase address | Mitigation status |
|---|---|---|---|---|
| R1 | pgvector index 2000-dim limit | HIGH | Phase 1, 4 | OpenAI `dimensions=1536` API param; verify Phase 1 |
| R2 | HNSW post-filter recall collapse | HIGH | Phase 6, 9 | pgvector ≥0.8 + iterative_scan; measure WITH filter |
| R3 | Pivot fatigue → pivot 3 | CRITICAL | Phase 1 (bake) | M2a/M2b split + EXIT criteria E1-E5 + weekly check-in |
| R4 | Scanned PDF silent fail | HIGH | Phase 4, 8 | Whitelist format + enum `failed_unsupported` |
| R5 | CocoIndex naming + APP_NAMESPACE | MEDIUM | Phase 1, 4 | Snake_case + `medinet_prod` cố định + `db_schema_name="cocoindex"` |
| R6 | Argon2 hash cross-compat | MEDIUM | Phase 3 | Pin params Go-compat + integration test |
| R7 | Embedding swap = re-embed | MEDIUM | Phase 7 | Pin dim 1536 + cost preview UI + refuse cross-dim |

### EXIT Criteria (R3 mitigation, từ PROJECT.md)

| # | Trigger | Action |
|---|---|---|
| E1 | CocoIndex critical bug no-fix 14 ngày | STOP, `/gsd-discuss-milestone` |
| E2 | pgvector p95 >2000ms ở 50K chunks dù tune | STOP, discuss Qdrant |
| E3 | Phase 1-3 vượt 21 ngày calendar | STOP, scope review |
| E4 | Hub isolation bug không fixable trong 7 ngày | STOP, security review |
| E5 | Quality gate fail <60% top-3 dù iterate 3 vòng | Stop M2b, ship M2a standalone |

### Roadmap Evolution

- Phase 8.1 inserted after Phase 8: MCP Server — expose wiki tools `ask`/`search`/RAG cho AI client ngoài (Claude Desktop, ChatGPT, Cursor) qua Model Context Protocol (URGENT, 2026-05-19)
- Phase 8.2 inserted after Phase 8.1: tách MCP Service thành process độc lập (`Hub_All/mcp_service/`, port riêng) gọi API qua HTTP — đảo decision D-04 của Phase 8.1 (URGENT, 2026-05-19)

### Weekly check-in calendar (R3 mitigation)

- **Day 7:** Phase 1-2 done? Schema migration applied? Docker compose 3-service up?
- **Day 14:** Phase 3 PASS Argon2 cross-compat test? Phase 4 MVP ingest 1 file?
- **Day 21:** 🚦 **M2a EXIT GATE** — demo upload DOCX → chunks pgvector → user accept?
- **Day 28:** Phase 6-7 wire? Phase 8 frontend smoke pass?

### Todos cấp milestone

- [ ] (Phase 4 open question) Quyết định storage backend — local default, GDrive port optional confirm với user
- [ ] (Phase 3 open question) Verify JWT keypair format PKCS#1 vs PKCS#8 — convert nếu cần
- [ ] (Phase 4 open question) Quyết định PDF table extraction lib — pdfplumber vs camelot vs accept-loss (empirical test 3 VN medical PDF)
- [ ] (Phase 4 open question) Quyết định cocoindex augmenter — RTFM, default skip M2 nếu phức tạp
- [ ] (Phase 9 open question) Empirical confirm dim 1536 quality cho VN medical (gate ≥75%)

### Blockers

- Không có blocker khởi đầu. Codebase Go hiện hữu chạy được — Phase 1 (skeleton FastAPI + tear-down) chạy được ngay sau khi user approve roadmap.
- **DEF-05-01 (deferred, không block 05-01):** cocoindex 1.0.3 `Environment` KHÔNG re-open được trong cùng process → mọi test file dùng fixture `app_with_auth` cho >1 test FAIL từ test thứ 2 (`RuntimeError: environment already open`). Pre-existing limitation Phase 4 — `test_documents_list_delete.py` cũng fail giống. Plan 05-01 Task 4 né bằng fixture `audit_db` tự cấp. Wave 3-4 Phase 5 (hub/user/apikey CRUD integration test) sẽ cần giải pháp chung — đề xuất Plan 05-06/Phase 10 thêm fixture mock cocoindex. Chi tiết: `.planning/phases/05-hub-user-audit-apikey-settings-crud/deferred-items.md`.
- **DEF-05-02 (deferred, không block 05-02):** 5 test `tests/unit/test_watchdog.py` (Phase 4) FAIL `NotNullViolationError` cột `hubs.code` — migration 0003 (05-01) thêm `hubs.code` NOT NULL nhưng helper insert hub trong test chưa truyền `code`. Pre-existing do 05-01, KHÔNG do 05-02. Đề xuất: Wave 3 (05-03 Hub CRUD) hoặc Phase 10 cập nhật helper. Chi tiết: `deferred-items.md`.

### Notes

- **M2 = pivot lần 2 trong 15 ngày.** Tốc độ thay đổi định hướng đáng lưu ý — sau M2 cần ổn định ít nhất 4-8 tuần trước pivot tiếp. EXIT criteria E1-E5 bake để chống pivot lần 3.
- **Backlog 999.1 (incremental chunk re-embed)** được hợp nhất vào M2 vì đây chính là core value của cocoindex (content-hash diff). KHÔNG còn là backlog riêng.
- **Frontend KHÔNG đổi** — toàn bộ trang quản trị React 19 hiện hữu tương thích qua URL `/api/*` (nginx hoặc FastAPI mount port :8080).
- **Phases M1 archive:** `.planning/milestones/v1.0-docling-rag/` chứa 5 phase + 1 backlog 999.1 (git mv, history giữ nguyên).
- **Code Go sẽ bị xóa trong Phase 8** sau khi frontend smoke pass + git tag `m1-go-archived` backup.
- **OCR Vietnamese gỡ trong M2** — nếu user feedback regress, revisit ở milestone v4.0 (đưa Docling/Tesseract trở lại như extract function trong cocoindex flow).
- **Research flags theo phase:** Phase 3 MEDIUM (Argon2 cross-compat), Phase 4 HIGH (augmenter + PDF table + VN chunking), Phase 7 MEDIUM (memo cache invalidation), Phase 9 MEDIUM (dim quality empirical).

---

## Session Continuity

**Last session (2026-05-18 — `/gsd-execute-phase 8 plan 08-04` — continuation sau checkpoint auto-approve):** continuation agent tiếp tục Plan 08-04 từ Task 2 (Task 1 đã xong commit `422243a` ở agent trước). Bối cảnh: plan có `checkpoint:human-verify` (gate blocking) — orchestrator chế độ `--auto` (`auto_advance:true`) AUTO-APPROVE checkpoint cơ học để giữ chuỗi chạy; KHÔNG có người thật boot stack hay click 11 trang React; `08-SMOKE-CHECKLIST.md` CHƯA điền.

- Task 2 (`76afc02` — `docs(08-04)`): sinh `.planning/phases/08-frontend-e2e-smoke/08-HUMAN-UAT.md` từ cấu trúc `08-SMOKE-CHECKLIST.md` + 5 SC Phase 8, dùng UAT template chuẩn (mẫu `07-HUMAN-UAT.md`, frontmatter `status:partial`). KHÔNG fabricate PASS: SC1 (11 trang React render) / SC2 (golden path browser + citation `[1]` clickable) / SC5 (docker compose 3-service healthy) đánh `result:[pending]` — cần mắt người; SC3 (08-01 đối chiếu tĩnh contract, artifact `08-CONTRACT-DIFF.md`) + SC4 (08-03 `test_vietnamese_filename.py` critical PASS) đánh `passed` vì có artifact thật. Summary: total 5 / passed 2 / pending 3. Verdict UAT = PARTIAL; COMPAT-01 = PARTIAL.
- Deviation: [Continuation - Quy trình] KHÔNG ghi PASS cho SC1/SC2/SC5 — auto-approve cơ học không tương đương human verification; ghi PASS giả sẽ làm sai lệch trạng thái Phase 8.
- `08-04-SUMMARY.md` tạo xong — ghi rõ checkpoint auto-approved, human-UAT pending. STATE.md + ROADMAP.md cập nhật: 08-04 ✅ artifact, Phase 8 status `human_uat_pending`, COMPAT-01 PARTIAL.
- **BẮT BUỘC tiếp theo: `/gsd-verify-work 8`** — người dùng boot stack thật (`bash api/scripts/smoke/boot_stack.sh` + `npm run dev`), render 11 trang React, chạy golden path browser, điền `08-SMOKE-CHECKLIST.md`, cập nhật `result:` Test 1/2/3 trong `08-HUMAN-UAT.md`. Chỉ khi SC1/SC2/SC5 PASS → COMPAT-01 ĐẠT → Phase 8 đóng → Phase 9.
- D6 tuân thủ tuyệt đối — chỉ thêm file `.planning/.../08-HUMAN-UAT.md` + `08-04-SUMMARY.md`; KHÔNG file nào trong `frontend/` bị sửa; không deletion.

**Last session (2026-05-17 — Plan 05-05 execute):** `/gsd-execute-phase 5 plan 05-05` → executor agent (sequential) thực thi 3 task atomic:

- Task 01 (`b3d97f8`): `pkg/crypto.py` — AES-256-GCM helper: `_load_key` (đọc `settings.aes_key`, base64url-decode, validate 32-byte → ValueError), `encrypt_secret` (nonce 12B random prepend ciphertext → base64url token), `decrypt_secret` (tách nonce decrypt). `schemas/api_keys.py` — 4 Pydantic v2 schema: `CreateApiKeyRequest`/`UpdateApiKeyRequest`/`ApiKeyResponse` (= APIKeyAPI — status derive is_active; requests_today/7d/bandwidth_used=0, allowed_rag_configs=[] hằng)/`ApiKeyWithPlaintext(ApiKeyResponse)` (+plain_key — POST create only). `schemas/audit.py` — `AuditLogResponse` (= AuditLogAPI; is_ai=False, ip/user_agent/duration_ms=None hằng). `pyproject.toml` thêm `cryptography`. `.env.example` AES_KEY documented placeholder.
- Task 02 (`06c3a8f`): `services/api_key_service.py` — `ApiKeyService` 6 method: `create` (plaintext `mdk_<token_urlsafe(32)>`, key_prefix 8 ký tự, key_hash=encrypt_secret, INSERT JSONB cast → ApiKeyWithPlaintext), `get`/`list` (KHÔNG plaintext), `update` (SET động JSONB cast), `revoke` (soft `is_active=FALSE` + RETURNING id — D-07, KHÔNG DELETE), `verify_key` (BLOCKER 1 canonical name — SELECT WHERE key_prefix + is_active=TRUE, decrypt loop so khớp exact, UPDATE last_used_at, return principal dict). `services/audit_query_service.py` — `AuditQueryService.list` WHERE-builder filter date/action/hub_id + LEFT JOIN users/hubs; actor_type bỏ qua (không có cột).
- Task 03 (`a7a3571`): `routers/api_keys.py` 5 endpoint admin-only — GET list (cap≤100), POST create→201 (data có plain_key), GET/:id, PUT/:id update, POST/:id/revoke soft; UUID validate→400 INVALID_API_KEY_ID. `routers/audit_logs.py` GET /api/audit-logs admin-only + `@limiter.limit(AUDIT_LOGS_LIMIT)` (W4 AUX-03 — endpoint function có `request: Request` param). `auth/dependencies.py` thêm `get_api_key_or_jwt` (X-API-Key Header alias HOẶC Bearer JWT — gọi `ApiKeyService.verify_key`, Phase 6/7 scaffolding). `auth/__init__.py` re-export.
- Verification: `ruff check` + `mypy --strict` 8 file clean; crypto round-trip smoke OK; route smoke api-keys 5 endpoint + audit-logs 1. 3 auto-fix deviation (Rule 1: mypy generic `dict`→`dict[str,Any]`; Rule 1: ruff UP017 `timezone.utc`→`UTC`; Rule 3: dead `stmt` + thiếu `text` import). `git diff --diff-filter=D HEAD~3 HEAD` rỗng.
- AES_KEY: dev key 32-byte base64 sinh local → set vào `Hub_All/api/.env` (gitignored — confirm `git check-ignore`), `.env.example` placeholder rỗng documented. Test fixture AES_KEY defer Plan 05-06 conftest update.
- SUMMARY.md `.planning/phases/05-hub-user-audit-apikey-settings-crud/05-05-SUMMARY.md` tạo với 3 commit hash + threat model T-05-05-01..08 (7 mitigate + 1 accept) + AUX-03 SC5 partial defer (WARNING 1) + Settings CRUD omission (BLOCKER 2) + self-check PASSED.
- **AUX-01 + AUX-02 + AUX-03 requirements — API key CRUD + AES-GCM encrypt-at-rest + soft revoke + X-API-Key dependency + audit-logs query + @limiter.limit hoàn tất (router mount + integration test E4 defer Wave 4 Plan 05-06).**

**Previous session (2026-05-17 — Plan 05-04 execute):** `/gsd-execute-phase 5 plan 05-04` → executor agent (sequential) thực thi 3 task atomic:

- Task 01 (`00ff3b4`): `schemas/users.py` — 10 Pydantic v2 schema: `CreateUserRequest` (email EmailStr + name/password min_length + hub_id + role), `UpdateUserRequest`/`UpdateProfileRequest` (name/phone/department optional — D-07 tách khỏi role/status), `ChangeUserRoleRequest`/`ChangeUserStatusRequest`, `ChangePasswordRequest` (old min_length=1 + new min_length=8), `UserResponse` (= UserAPI — KHÔNG `password_hash` T-05-04-03, `name` map `full_name`, `failed_login_count` hằng 0), `RoleAssignment`, `UserWithRolesResponse`. `UserRole`/`UserStatus` Literal khớp CHECK constraint.
- Task 02 (`31b6ea5`): `services/user_service.py` — `UserService` 9 method: `create` (hash argon2 + INSERT users + INSERT user_hubs + enqueue audit `user.create` payload chỉ email+role, IntegrityError→`UserConflictError`), `_build_user_with_roles`/`get` (SELECT user + user_hubs join), `list` (WHERE-builder filter role/status/search ILIKE + hub_id subquery + COUNT + LIMIT/OFFSET), `update`/`update_profile`/`_update_fields` (SET clause động — D-07), `change_role` (UPDATE role + upsert user_hubs ON CONFLICT DO NOTHING), `change_status`, `reset_password` (`secrets.token_urlsafe(32)` + Redis ex=3600 + log-only USER-02 — KHÔNG trả token), `change_password_self` (verify_password old → 3-state None/False/True). Raw SQL parametrized, timestamp NOW().
- Task 03 (`4192f22`): `routers/users.py` 7 endpoint admin-only (`require_role("admin")` mọi endpoint) — list cap per_page≤100 + filter, create→201 conflict→409 EMAIL_CONFLICT, get, PUT update profile (D-07), PATCH role + PATCH status riêng (D-07), POST reset-password (message generic KHÔNG token T-05-04-04). UUID validate→400 INVALID_USER_ID. `routers/profile.py` 3 endpoint self-scoped `get_current_user` (KHÔNG `require_role`, KHÔNG `:id` param — T-05-04-02 viewer chỉ truy cập profile chính mình); change_password 3-state → 404/400 INVALID_PASSWORD/200.
- Verification: `ruff check` + `mypy --strict` 4 file clean (4 source); route smoke test users 7 path đúng verb + profile 3 path KHÔNG `{` path param. 0 deviation. `git diff --diff-filter=D HEAD~3 HEAD` rỗng (không xoá file ngoài ý muốn).
- SUMMARY.md `.planning/phases/05-hub-user-audit-apikey-settings-crud/05-04-SUMMARY.md` tạo với 3 commit hash + threat model T-05-04-01..07 (7 mitigate) + self-check PASSED.
- **USER-01 + USER-02 + USER-03 requirements — user CRUD + reset-password + profile self-scoped router/service/schema hoàn tất (router mount defer Wave 4 Plan 05-06).**

**Previous session (2026-05-17 — Plan 05-02 execute):** `/gsd-execute-phase 5 plan 05-02` → executor agent (sequential) thực thi 2 task atomic:

- Task 01 (`3710b00`): `repositories/hub_isolation.py` — `HubIsolationError` (lưu `resource_hub_id` cho audit), `hub_filter_clause(role, hub_ids, param_prefix)` sinh SQL fragment `WHERE hub_id IN (...)` (admin → `("", {})` bypass; hub_ids rỗng → `"hub_id IN (NULL)"` luôn-false; editor/viewer có hub → placeholders + params), `verify_hub_access(role, user_hub_ids, resource_hub_id)` raise `HubIsolationError` khi cross-hub. `repositories/__init__.py` package docstring. `auth/dependencies.py` thêm `UserWithHubs` class + `get_current_user_with_hubs` dependency (hub_ids từ `user_hubs` DB — KHÔNG payload). `auth/__init__.py` re-export 2 symbol. `tests/unit/test_hub_isolation.py` — 14 unit test pure-Python phủ E4 (TDD RED→GREEN: ModuleNotFoundError → 14 passed). Defense in depth 3 lớp documented.
- Task 02 (`a42e3d4`): `middleware/rate_limit.py` — slowapi `Limiter` key_func `_rate_limit_key` (user_id từ JWT `sub`, fallback `get_remote_address`, bọc try/except KHÔNG raise), Redis storage `settings.redis_url`; `rate_limit_exceeded_handler` map `RateLimitExceeded` → `resp.too_many_requests` envelope 429 `RATE_LIMIT_EXCEEDED`; constant `SEARCH_LIMIT`/`UPLOAD_LIMIT`/`AUDIT_LOGS_LIMIT` cho router decorator. `middleware/__init__.py` re-export `limiter` + handler + 3 constant. `pyproject.toml` thêm `slowapi==0.1.9` (uv add). Wiring main.py defer Plan 05-06.
- Verification: `ruff check app` exit 0 (toàn bộ app); `mypy --strict app/repositories app/middleware/rate_limit.py app/auth/dependencies.py` exit 0 (4 source); `pytest tests/unit/test_hub_isolation.py` 14 passed; smoke test logic + import OK; `grep RATE_LIMIT_EXCEEDED` match.
- Deviation: 0 auto-fix. Out-of-scope: DEF-05-02 logged (test_watchdog.py fixture thiếu `hubs.code` — pre-existing do 05-01 migration, KHÔNG fix).
- SUMMARY.md `.planning/phases/05-hub-user-audit-apikey-settings-crud/05-02-SUMMARY.md` tạo với 2 commit hash + threat model T-05-02-01..05 (3 mitigate + 2 accept) + self-check PASSED.
- **HUB-02 + AUX-03 requirements — hạ tầng isolation helper + rate-limit module hoàn tất (enforce + wiring ở Wave 3-4).**

**Previous session (2026-05-17 — Plan 05-01 execute):** `/gsd-execute-phase 5 plan 05-01` → executor agent thực thi 4 task atomic:

- Task 01 (`769e0d4`): Migration 0003 `0003_phase5_schema_reconcile.py` — additive 10 cột: hubs (code/subdomain/status), users (phone/department/avatar_url/status), api_keys (permissions/allowed_hub_ids/rate_limit). server_default backfill existing rows → alter_column drop default cho code/subdomain. CheckConstraint hub_status_enum + user_status_enum + uq_hubs_code. downgrade đảo ngược clean. Cập nhật model Hub/User/ApiKey khớp. D-05 KHÔNG thêm field di sản Go. W1: hubs giữ cả slug (legacy NOT NULL mirror) + code (contract frontend). Alembic round-trip upgrade→downgrade→upgrade PASS clean trên DB `medinet_mig0003_test` sạch, chỉ 1 head.
- Task 02 (`4e3de9b`): `audit_service.py` — AuditEntry dataclass, enqueue_audit non-blocking (drop+warning khi QueueFull, KHÔNG raise — T-05-01-03), audit_flush_loop batch INSERT 2s/128 qua get_engine() executemany, flush_pending drain shutdown, AUDIT_ACTIONS frozenset gồm security.hub_isolation_violation, reset_queue test helper. config.py thêm audit knobs + rate_limit_*_per_minute.
- Task 03 (`f122b74`): wire audit_flush_loop vào main.py lifespan — startup step 8 create_task; shutdown flush_pending + cancel TRƯỚC dispose_engine.
- Task 04 (`a7a3311`): `test_audit_logger.py` — 3 test (1 @critical). test_audit_logger_100_concurrent: 100 concurrent enqueue → COUNT(*)==100 + COUNT(DISTINCT request_id)==100 (AUX-01 SC4). test_enqueue_non_blocking_when_queue_full + test_audit_flush_loop_batches (130 entry > batch_size). Deviation Rule 3: fixture `audit_db` tự cấp thay `app_with_auth` — né cocoindex Environment re-open bug (DEF-05-01).
- Verification: ruff app + mypy --strict app clean (44 source); create_app() OK; pytest test_audit_logger 3 passed; pytest -m critical -k audit_logger 1 passed.
- SUMMARY.md `.planning/phases/05-hub-user-audit-apikey-settings-crud/05-01-SUMMARY.md` tạo với 4 commit hash + threat model T-05-01-01..04 mitigated + Settings CRUD omission có chủ đích (BLOCKER 2) + DEF-05-01 deferred note.
- **HUB-01 + AUX-01 requirements partial — schema + audit infra hoàn tất (CRUD endpoint Wave 3).**

**Previous session (2026-05-14 — Plan 03-05 execute — PHASE 3 COMPLETE):** `/gsd-execute-phase 3 plan 03-05` → executor agent thực thi 6 task atomic:

- Task 01 (`010c8a1`): replace `app/auth/dependencies.py::require_role` stub NotImplementedError → implementation đầy đủ. ValueError gate empty roles (security gate — tránh route mở cho mọi role). `allowed = set(roles)` + `user.role in allowed` check → raise HTTPException 403 `{code:FORBIDDEN, message:...}`. Thêm `@app.exception_handler(HTTPException)` trong `app/main.py::create_app()` map `exc.detail` dict {code, message} → envelope `{success:false, data:null, error:{code, message}, meta:null}`. Plan 03-01 ErrorHandlerMiddleware pass-through StarletteHTTPException → handler này render envelope đúng cho mọi 401/403 từ get_current_user + require_role. 5 unit test test_require_role.py PASS.
- Task 02 (`29d4edf`): extend `tests/integration/conftest.py` với 10 fixture Plan 03-05: `redis_container` (scope=module, redis:7-alpine), `auth_env` (legacy backward-compat), `app_with_auth` (alembic upgrade + lifespan), `auth_client` (httpx ASGITransport), `admin_user/editor_user/viewer_user` (INSERT users qua engine với Go seed hash), `admin_token/editor_token/viewer_token` (POST /login), `admin_token_pair` (cả access+refresh cho AC5). pyproject.toml bump `testcontainers[postgres]` → `testcontainers[postgres,redis]`. uv sync install redis extra. docker pull redis:7-alpine prerequisite.
- Task 03 (`a01b7d1`): tests/integration/test_auth_login.py — 5 critical test AC1: happy admin Go-seed hash → 200 envelope; wrong password → 401 INVALID_CREDENTIALS; unknown email → 401 same shape (anti-timing oracle); bad email → 422; envelope keys EXACTLY {success, data, error, meta}. **Rule 3 fix**: alembic.command.upgrade trong async fixture → asyncio.to_thread. **Rule 1 fix**: postgres_container scope=module → TRUNCATE users/refresh_tokens/user_hubs RESTART IDENTITY CASCADE per-test. 5/5 PASS.
- Task 04 (`41b8d5c`): tests/integration/test_auth_refresh_race.py — 5 critical test AC5/AUTH-02: happy refresh new pair; concurrent 5 asyncio.gather → exactly 1 PASS + 4 fail-401 (P16 SETNX); revoked replay → 401; garbage JWT → 401 INVALID_REFRESH_TOKEN; access vs refresh type → 401. **Rule 1 fix**: alembic_cfg fixture set REDIS_URL=localhost (Phase 2 placeholder), pytest fixture resolution order không guarantee auth_env chạy sau → lifespan đọc localhost. Chuyển env override (DATABASE_URL+REDIS_URL+JWT+CORS) trực tiếp vào app_with_auth fixture với postgres+redis containers làm depend → set CUỐI CÙNG + cache_clear trước create_app. 5/5 PASS.
- Task 05 (`0f1fdc6`): tests/integration/test_rbac_dependency.py — 6 critical test AC3: anonymous → 401 MISSING_AUTHORIZATION; viewer require_role('admin') → 403 FORBIDDEN; editor require_role('admin') → 403; admin require_role('admin') → 200; admin require_role('admin','editor') → 200 (multi-role pass); viewer require_role('admin','editor') → 403 (multi-role reject). Test-only route /test/role-check mount qua `_spawn_rbac_app()` helper — KHÔNG sửa production app/main.py. AC3 reformulation: production endpoint defer Phase 5 HUB-02. 6/6 PASS.
- Task 06 (`6e178e4`): tests/integration/test_jwt_compat.py — 5 critical test AC2/AUTH-06: login token decode bằng keys/public.pem RS256 PyJWT raw → 10 claim spec; /me Bearer → UserPublic; logout blacklist access JTI → /me cũ 401 TOKEN_REVOKED; scripts/verify_jwt_format.sh exit 0 "PKCS#8 OK"; PII regression (caplog scan password + JWT eyJ pattern KHÔNG match). **Rule 1 fix**: verify_jwt_format.sh trên Windows git bash `head -1` trả trailing \\r (CRLF) → case match fail → strip với `tr -d '\\r'`. 5/5 PASS.
- Verification suite 17/17 PASS: pytest tests/ → 62/62 PASS (27 mới Plan 03-05 + 25 unit cũ + 11 integration Phase 2 + others); pytest -m critical → 29/29 PASS (HARD-03 CI gate); ruff app + tests clean; mypy strict 29 source clean; require_role + get_current_user + auth_router exports OK; verify_jwt_format.sh exit 0.
- SUMMARY.md `.planning/phases/03-auth-port-rbac-response-envelope/03-05-SUMMARY.md` tạo với 6 commit hash + threat model 9 entry (5 mitigated + 1 accepted + 3 regression-mitigated) + Phase 5 Carry-Over (AC3 production endpoint integration + audit_log trigger) + DOC-BUG cleanup follow-up note.
- **5/5 ROADMAP success criteria VERIFIED end-to-end**: AC1 (login envelope) + AC2 (JWT decode + PKCS#8) + AC3 (RBAC 403/200) + AC4 (Argon2 cross-compat regression) + AC5 (concurrent refresh race). **6/6 AUTH requirements complete**. Phase 3 hoàn tất.

**Previous session (2026-05-14 — Plan 03-04 execute):** `/gsd-execute-phase 3 plan 03-04` → executor agent thực thi 5 task atomic:

- Task 01 (`c165c4d`): tạo `app/auth/schemas.py` — 5 Pydantic v2 model (LoginRequest, LoginResponse, UserPublic, RefreshRequest, LogoutRequest). LoginRequest.email: EmailStr + password min/max length. UserPublic.hub_assignments: list[str] (USER-03). role Literal["admin","editor","viewer"] match Go enum. Rule 3 deviation: pyproject `pydantic>=2.7.0,<3` → `pydantic[email]>=2.7.0,<3` + uv sync install email-validator 2.3.0 + dnspython 2.8.0 cho EmailStr (plan đã anticipate trong task 01 lưu ý).
- Task 02 (`6b7d8a6`): tạo `app/auth/service.py` — AuthService class với 4 async method (login/refresh/logout/get_current_user_info). AuthError(code, message) exception class. _hash_refresh_token SHA-256 64-char (T-02-03). Constructor injection: db, redis, jwt_manager, dummy_password_hash. Anti-timing oracle: login luôn gọi verify_password kể cả user None với dummy hash. P16 SETNX: refresh dùng redis.set(lock:refresh:<jti>, nx=True, ex=30) → fail → AuthError REFRESH_RACE. Blacklist old jti + UPDATE refresh_tokens.revoked_at + INSERT new hash. 5 error code Go-compat (INVALID_CREDENTIALS, INVALID_REFRESH_TOKEN, REFRESH_RACE, TOKEN_REVOKED, USER_DISABLED).
- Task 03 (`31d54fd`): tạo `app/auth/dependencies.py` — 5 FastAPI dependency + oauth2_scheme + require_role stub. OAuth2PasswordBearer(tokenUrl=/api/auth/login, auto_error=False). get_current_user reject 5 case 401: MISSING_AUTHORIZATION (rỗng) / INVALID_TOKEN (decode fail) / TOKEN_REVOKED (Redis blacklist exists) / USER_DISABLED (user None hoặc is_active False). require_role raise NotImplementedError — Plan 03-05 implement. Rule 3 deviation: noqa B008 cho 4 Depends() default (FastAPI pattern, false positive).
- Task 04 (`8aaad3f`): tạo `app/auth/router.py` (4 endpoint) + extend `app/auth/__init__.py` re-export 8 symbol mới (15 export total). APIRouter(prefix=/api/auth, tags=[auth]). _auth_error_to_response helper map AuthError.code → resp.unauthorized. POST /login + /refresh + /logout (Bearer + body LogoutRequest) + GET /me. Logout endpoint: parse Authorization header lấy access JTI + exp → service.logout(jti, exp, refresh_token). Rule 3 deviation: noqa B008 cho 5 Depends() default.
- Task 05 (`1c9237f`): extend `app/main.py` — lifespan +3 step (JWTManager init từ keys/private.pem + public.pem, dummy_password_hash = hash_password("dummy..."), init_engine cho SQLAlchemy async session), shutdown +1 (dispose_engine + reset jwt_manager), create_app +1 (include_router(auth_router)), readyz +1 check (jwt). Rule 3 deviation: noqa C901 cho lifespan (complexity 13) + create_app (complexity 11) — init sequence vốn nhiều step linear.
- Verification suite 13/13 PASS: 6 path mount (4 auth + 2 health), all exports OK, ruff app/auth + main.py clean (8 source), mypy strict clean (8 source), pytest 36/36 no regress (25 unit + 11 integration), schemas/service/deps/router import + functional verify.
- SUMMARY.md `.planning/phases/03-auth-port-rbac-response-envelope/03-04-SUMMARY.md` tạo với 5 commit hash + threat model 7 entry (6 mitigated + 1 accepted Redis fail-open Phase 3) + forward links cho Plan 03-05 (RBAC require_role + integration test) + Phase 5 (CRUD endpoint với get_current_user).

**Previous session (2026-05-14 — Plan 03-03 execute):** `/gsd-execute-phase 3 plan 03-03` → executor agent thực thi 3 task atomic:

- Task 01 (`e205920`): tạo `app/auth/password.py` wrap `pwdlib.PasswordHash` + `pwdlib.hashers.argon2.Argon2Hasher` với params LẤY TỪ GO SOURCE (`backend/internal/pkg/hash/argon2.go` line 13-19): `memory_cost=65_536, time_cost=3, parallelism=4, salt_len=16, hash_len=32`. Expose 2 helper `hash_password(plain) -> str` + `verify_password(plain, hash) -> bool`. verify_password wrap try/except để KHÔNG raise UnknownHashError — trả False. Extend `app/auth/__init__.py` re-export 7 symbol (hash_password, verify_password + 5 ARGON2_* constants). Docstring document DOC-BUG explicit. Pre-implementation verify pwdlib API qua `inspect.signature(Argon2Hasher.__init__)` — defaults match Go source nguyên xi.
- Task 02 (`a4f5203`): tests/unit/test_password.py — 6 unit test pure Python (KHÔNG cần Postgres): hash prefix Go-compat / round-trip Tiếng Việt / reject wrong / garbage hash → False / salt random / params constants regression guard. 6/6 PASS in 0.61s.
- Task 03 (`b68e4d9`): tests/integration/test_argon2_cross_compat.py — 4 critical R6 mitigation test với fixture hash thật từ `Hub_All/backend/scripts/seed.sql` line 13 (admin@medinet.vn, plaintext "Admin@123"). All 4 test marker `@pytest.mark.critical + @pytest.mark.integration` cho CI gate HARD-03. Test 1: pwdlib verify Go-generated hash production → True (R6 CORE proof). Test 2: phản chứng wrong password / case-sensitive / empty → False. Test 3: 5 Python plaintext sample round-trip. Test 4: hash format byte-identical Go (split $ → 6 segment với parts[3]='m=65536,t=3,p=4'). 4/4 PASS in 1.39s.
- Verification suite 10/10 PASS: pytest combined 10 test + pytest -m critical 11 (4 mới + 7 Phase 2 chunks/migration — no regress) + ruff app/auth + tests PASS + mypy app/auth strict 3 source PASS + full unit suite 25/25 (19 cũ + 6 mới — no regress) + R6 manual sanity check `verify_password('Admin@123', <go_seed_hash>)` → True.
- 0 deviation — toàn bộ paste-ready code apply nguyên xi (chỉ bỏ unused `import pytest` để pass ruff F401).
- **DOC-BUG DISCOVERED + DOCUMENTED:** REQUIREMENTS.md AUTH-05 + PITFALLS.md P6 + CLAUDE.md section 3 ghi `t=1, p=2` SAI — Go source `backend/internal/pkg/hash/argon2.go` line 13-19 ghi `t=3, p=4`. Production seed hash prefix `$argon2id$v=19$m=65536,t=3,p=4$...` confirm Go source là single source of truth. SUMMARY.md document doc-bug explicit + suggest follow-up sed fix 3 doc (out of Plan 03-03 scope, defer Plan 03-04/03-05 cleanup commit).
- SUMMARY.md `.planning/phases/03-auth-port-rbac-response-envelope/03-03-SUMMARY.md` tạo với 3 commit hash + threat model 5 entry (1 partial T-03-pw-timing chờ Plan 03-04 dummy compare + 2 accepted + 2 mitigated) + forward links cho Plan 03-04/03-05.

**2026-05-14 (TEARDOWN-01 PULL-IN — ngoài lịch):** User quyết định xoá `Hub_All/backend/` Go toàn bộ NGAY (sớm hơn Phase 8) để chuyển 100% sang Python + cocoindex. Backup: `git tag m1-go-archived` (commit `72f18ef`). 147 file Go xoá khỏi working tree. Hệ luỵ:

- D6 vẫn giữ — frontend KHÔNG sửa, Python `api/` phải mimic surface Go khi port Phase 5/6/7. Reference Go: `git show m1-go-archived:Hub_All/backend/internal/router/<file>.go`.
- Phase 8 SC3 (replay test live Go vs FastAPI) → REVISED: dùng router signature từ git tag + frontend types làm contract reference (không còn Go runtime A/B test).
- ⚠️ R3 / E1 safety net giảm: nếu cocoindex critical fail thì không còn rollback Go runtime, chỉ pivot lần 3. User accept risk.
- Update: `Makefile` root (gỡ eval-* M1 + backend-* proxy), `.env.example` (gỡ Docling/ChromaDB/backend Go), `.gitignore` (gỡ `backend/chroma_data/`), `CLAUDE.md` (gỡ section DEPRECATED Go, đổi sang "ARCHIVED"), `ROADMAP.md` (Phase 8 đổi title + SC5 đánh dấu done).
- TEARDOWN-01 trong Phase 8 ✓ done. Còn lại Phase 8 chỉ là frontend E2E smoke.

**Last session (2026-05-18 — `/gsd-execute-phase 7 plan 07-04`):** executor agent sequential trên main working tree thực thi 2 task atomic của Plan 07-04 (Wave 2 — Ask API lắp ráp đầy đủ, ASK-01/02/03/05 + AUX-03):

- BƯỚC 0 (P19 mid-phase drift guard): xác nhận LiteLLM version TRƯỚC khi code — `litellm` đã pin `litellm>=1.82,<2` trong `pyproject.toml`; version resolve thực tế **1.83.14**; `litellm.acompletion(model=..., messages=...)` + `litellm.completion_cost(completion_response=...)` tồn tại + chữ ký khớp `<interfaces>` nguyên xi → không drift, không pin lại.
- Task 1 (`74bf598`): `services/ask_service.py` — `AskError`/`UsageRecord`/`AskOutcome`/`_AskChunk` dataclass; `_resolve_llm_model()` đọc `get_settings()` mỗi lần (hot-swap ASK-04, prefix `gemini/` khi provider gemini); `_resolve_top_k()` clamp [1,12]. `AskService.ask()`/`ask_cross_hub()`: `_retrieve()` gọi `SearchService.search`/`search_cross_hub` Phase 6 rồi bù `document_id` qua `SELECT id, document_id FROM chunks WHERE id = ANY($1::uuid[])` (D-07-04-C — search Phase 6 không trả field này), bọc `_AskChunk`; `_call_llm()` gọi `litellm.acompletion` non-streaming bọc lỗi provider → `AskError` (D-07-04-F); `_extract_usage()` token an toàn `getattr` None + `completion_cost` bọc try/except None. Service KHÔNG tự ghi `usage_events` (D-07-04-D). Log `ask_completed` KHÔNG ghi query/answer (PII).
- Task 2 (`f998b62`): `routers/ask.py` — `APIRouter` KHÔNG prefix, 3 endpoint POST `/api/ask` (ASK-01) + `/api/ask/cross-hub` (ASK-03) + alias `/api/search/answer` (D-07-04-A frontend `searchAnswer()`); helper `_run_ask()` dùng chung map `ValueError`→400 `INVALID_QUERY` / `EmbedderError`→500 `EMBEDDING_FAILED` / `AskError`→500 `LLM_FAILED` (D-07-04-F — `resp` không có helper `bad_gateway`); cả 3 `limiter.limit(SEARCH_LIMIT)` 100/min (AUX-03); usage log `background_tasks.add_task(log_usage_event, pool, **usage)` sau response, `request_id` từ `request.state.request_id`. `routers/__init__.py` re-export `ask_router`; `main.py create_app()` mount cạnh `usage_router`.
- Verification: `ruff check` 4 file + `mypy --strict` 2 source clean; `create_app()` mount đúng 3 path `/api/ask`, `/api/ask/cross-hub`, `/api/search/answer`; `@limiter.limit` đúng 3 decorator; acceptance grep (litellm.acompletion / build_ask_messages / parse_citations / SearchService / SELECT id, document_id / INSERT INTO usage no-match) pass; `git diff --diff-filter=D HEAD~2 HEAD` rỗng.
- 1 deviation Rule 3 (blocking — tránh grep false-positive): module docstring nhắc literal `@limiter.limit` 2 lần → `grep -c` trả 5 dù decorator thực tế 3. Đổi docstring dùng `limiter.limit` (không `@`), decorator thực giữ nguyên — sau sửa `grep -c` đúng 3. Cùng pattern deviation 06-01.
- SUMMARY.md `.planning/phases/07-ask-api-litellm-citation-hot-swap-usage/07-04-SUMMARY.md` tạo với 2 commit hash + threat model T-07-04-01..06 (6 mitigate) + BƯỚC 0 LiteLLM version note + self-check PASSED.
- **ASK-01/02/03/05 + AUX-03 — Ask API lắp ráp đầy đủ (AskService + 3 endpoint POST + rate-limit + usage BackgroundTasks). ROADMAP SC1 (citation map) / SC5 (10-ask usage_events) verify end-to-end + anti-injection critical test thuộc Plan 07-05.** Note: `gsd-sdk query` state handlers vẫn không khả dụng — STATE/ROADMAP cập nhật thủ công.

**Previous session (2026-05-18 — `/gsd-execute-phase 7 plan 07-03`):** executor agent sequential trên main working tree thực thi 3 task atomic của Plan 07-03 (Wave 1 — rag-config dimension guard + cost preview, ASK-04 / R7):

- Task 1 (`789bc0d`): `schemas/rag_config.py` — thêm model `EmbeddingCostPreview` (n_chunks/est_cost_usd/est_minutes/message) mô tả shape cost preview within-dim swap. `UpdateRagConfigRequest` GIỮ NGUYÊN — request không đổi. Service build nội dung rồi `.model_dump()` ghép vào response dict raw (contract D6).
- Task 2 (`2752d0b`): `services/rag_config_service.py` — hằng `PINNED_DIM=1536`/`COST_PER_CHUNK_USD=0.000013`/`CHUNKS_PER_MINUTE=450` + import math/re. Helper `_embedding_dim_of(model)` regex `@(\d+)\s*$` parse hậu tố dim, fallback 1536 (D-07-03-A). Method `_embedding_cost_preview()` count(*) chunks bọc try/except fallback n=0 (T-07-03-04), message format `:.2f` cost luôn 2 chữ số. `update_config()` chèn dimension guard sau validate provider name — cross-dim → trả str (router map 400 "dimension mismatch — defer cross-dim swap v4.0"), within-dim embedding swap → tính cost_preview; return dict thêm `warning`+`cost_preview`.
- Task 3 (`29a11db`): `tests/unit/test_rag_config_dim_guard.py` — 6 unit test pure-Python (1 `@pytest.mark.critical` nhánh refuse cross-dim): phủ `_embedding_dim_of` no-suffix/within/cross-dim + cost formula + message 2 chữ số thập phân (n=7692 → cost 0.10 trailing-zero case, khớp regex `est \$\d+\.\d{2},` — ROADMAP SC4).
- Verification: `ruff check` + `mypy --strict` 2 source clean; `pytest test_rag_config_dim_guard.py` 6/6 pass; `pytest -m critical` 1 pass; `git diff --stat HEAD~3 HEAD` xác nhận CHỈ 3 file (service+schema+test) — router `rag_config.py` KHÔNG đụng (contract D6 raw JSON giữ nguyên); `git diff --diff-filter=D` rỗng. 0 deviation — code plan paste-ready apply nguyên xi.
- SUMMARY.md `.planning/phases/07-ask-api-litellm-citation-hot-swap-usage/07-03-SUMMARY.md` tạo với 3 commit hash + threat model T-07-03-01..04 (3 mitigate + 1 accept) + self-check PASSED.
- **ASK-04 / R7 dimension guard + cost preview hoàn tất — cross-dim swap refuse 400, within-dim swap cho phép kèm WARNING cost preview. Endpoint `/api/rag-config` đầy đủ. Note: `gsd-sdk query` state handlers vẫn không khả dụng — STATE/ROADMAP cập nhật thủ công.**

**Previous session (2026-05-18 — `/gsd-execute-phase 7 plan 07-02`):** executor agent sequential trên main working tree thực thi 3 task atomic của Plan 07-02 (Wave 1 — token usage write + read path, ASK-05):

- Task 1 (`12c3a2d` TDD RED → `476b8d7` GREEN): `schemas/usage.py` — 6 model Pydantic v2 (`UsageEventResponse`/`UsageGroup`/`UsageDailyPoint`/`UsageStats`/`UsageRealtimePoint`/`UsageRealtime`) khớp 1:1 contract D6 `api.ts` (`TokenUsageAPI`/`TokenUsageStatsAPI`/`TokenUsageRealtimeAPI`). `test_usage_schema.py` 3 unit test pure-Python (RED `ModuleNotFoundError` → GREEN 3/3 pass).
- Task 2 (`cf3a522`): `services/usage_service.py` — tách write path `log_usage_event()` (ghi 1 row `usage_events` best-effort, bọc try/except KHÔNG raise — gọi từ BackgroundTasks Plan 07-04; PII-safe by schema T-07-02-PII) khỏi read path `query_usage()` (list filter date/model/hub/provider, cap per_page 100) + `aggregate_usage()` (by_model/by_provider/by_operation/daily — phục vụ cả `/stats` và `?group_by=`) + `realtime_usage()` (window 60 phút group theo phút). Toàn bộ query asyncpg parametrized `$N` — KHÔNG nối chuỗi (T-07-02-03).
- Task 3 (`634114f`): `routers/usage.py` — 3 endpoint GET admin-only (`require_role("admin")` — T-07-02-02): `GET /api/usage` (+`?group_by=` delegate `aggregate_usage()` cho ROADMAP SC5 URL literal) + `/stats` + `/realtime`. Wiring `routers/__init__.py` re-export `usage_router` + `main.py create_app()` mount cạnh `search_router`. `create_app()` xác nhận mount đúng 3 path `/api/usage{,/stats,/realtime}`.
- Verification: `ruff check` + `mypy --strict` 3 source clean; `pytest test_usage_schema.py` 3/3 pass; `create_app()` mount check pass; acceptance grep (INSERT INTO usage_events match, 4 async def, PII no-match). 0 deviation — code plan paste-ready apply nguyên xi.
- SUMMARY.md `.planning/phases/07-ask-api-litellm-citation-hot-swap-usage/07-02-SUMMARY.md` tạo với 4 commit hash + threat model T-07-02-01..04 (4 mitigate) + TDD gate compliance (RED `12c3a2d` → GREEN `476b8d7`) + self-check PASSED.
- **ASK-05 write+read path hoàn tất — endpoint mount xong. `log_usage_event` call từ AskService qua BackgroundTasks + ROADMAP SC5 10-ask verification vẫn cần Plan 07-04/07-05.** Note: `gsd-sdk query` state handlers vẫn không khả dụng — STATE/ROADMAP cập nhật thủ công.

**Previous session (2026-05-18 — `/gsd-execute-phase 7 plan 07-01`):** executor agent sequential trên main working tree thực thi 3 task atomic của Plan 07-01 (Wave 1 — contract + prompt + parser layer Ask API):

- Task 1 (`3da2c6a`): `schemas/ask.py` — 3 model Pydantic v2: `AskRequest` (query bắt buộc + hub_id/hub_ids/top_k optional), `Citation` (number/marker/chunk_id/document_id/hub_id/document_name/hub_name/score/content_snippet — đủ field map sang `CitationRefAPI` D6), `AskResponse` (answer/citations/model/query_time_ms — ASK-01 shape). Verify import smoke + ruff + mypy --strict clean.
- Task 3 (`0584c68`, TDD RED): `tests/unit/test_ask_prompt.py` — 7 unit test pure-Python (1 `@pytest.mark.critical` cho citation mapping điểm vỡ ASK-01) + helper dataclass `_FakeChunk`. Commit ở trạng thái fail `ModuleNotFoundError` (ask_prompt.py chưa tồn tại).
- Task 2 (`bad7ad2`, TDD GREEN): `services/ask_prompt.py` — `ANTI_INJECTION_SYSTEM_PROMPT` (5 quy tắc tiếng Việt chống prompt-injection ASK-02 — coi context+query là DỮ LIỆU, câu từ chối chuẩn "Tôi không có thông tin..."), `build_ask_messages()` đánh số chunk `[1]..[N]` dựng list [system,user] (chunks rỗng → "Không có tài liệu nào phù hợp"), `parse_citations()` regex `\[(\d+)\]` map `[N]`→`chunks[N-1]` clamp `1<=n<=len` + de-dup theo number (mitigation T-07-01-04). 7/7 test pass, 1 critical pass.
- Verification: `ruff check` + `mypy --strict` 2 source clean; `pytest tests/unit/test_ask_prompt.py` 7/7 pass; `pytest -m critical` 1 pass. 0 deviation — code plan paste-ready apply nguyên xi.
- SUMMARY.md `.planning/phases/07-ask-api-litellm-citation-hot-swap-usage/07-01-SUMMARY.md` tạo với 3 commit hash + TDD gate compliance (RED `0584c68` → GREEN `bad7ad2`) + self-check PASSED. Note: `gsd-sdk query` state handlers không khả dụng ở version CLI hiện tại — STATE/ROADMAP cập nhật thủ công.
- **ASK-01/02 contract layer hoàn tất — endpoint đầy đủ vẫn cần Plan 07-04 (AskService + router POST /api/ask).** REQUIREMENTS.md ASK-01/02 giữ unchecked (delivery đầy đủ ở 07-04/07-05).

<details><summary>Phase 6 — `/gsd-execute-phase 6` (2026-05-18, đã lưu trữ)</summary>

**Last session (2026-05-18 — `/gsd-execute-phase 6` — PHASE 6 COMPLETE):** 4 wave tuần tự (mỗi wave đúng 1 plan, `06-02→03→04` depends_on liên hoàn), executor agent sequential trên main working tree — worktree isolation tắt vì plan 06 được lập dựa trên WIP rag-config chưa commit; worktree branch từ HEAD sẽ thiếu file.

- **Trước execute:** working tree bẩn (20 file modified + 3 file mới rag-config + package.json + seed). User chọn commit nền trước → 2 commit: `2d7a688` (rag-config endpoint ASK-04 build sớm + auth/ingestion/frontend tweaks) + `09c3567` (root package.json dev scripts + SEED-001). Tree sạch trước Phase 6.
- 06-01 (`418ea59` schema layer search.py 7 model khớp api.ts; `73222d8` SearchService.search single-hub union + HNSW SET LOCAL tuning + Redis cache fail-open + intersect_hubs defense-in-depth lớp 1). 2 deviation auto-fix (Rule 1 gỡ bare re-raise dead code; Rule 3 docstring tránh false-positive grep).
- 06-02 (`6e5f1c9` search_cross_hub fan-out asyncio.gather + re-rank score desc + find_similar; `00cb5c9` routers/search.py 3 endpoint POST @limiter.limit + mount create_app). 1 deviation (Rule 3 noqa C901).
- 06-03 (`85fe632` search_cache.py hub-tagged scheme + publish_invalidate + subscriber loop psubscribe `hub:*:invalidate`; `3b1b6f1` wire publish vào documents create/delete + redis DI factory + subscriber lifespan task step 9). 0 deviation.
- 06-04 (`143fda5` conftest _insert_document/_insert_chunk seed helper; `f90285d` test_search_hub_isolation.py 6 critical test). **6/6 PASS** với Docker testcontainers — hub isolation E4, cross-hub isolation, empty result, cache hit, EXPLAIN HNSW. 1 deviation (Rule 1 — test EXPLAIN: planner chọn B-tree trên dataset nhỏ → tách query vector-ordering thuần để buộc HNSW; verify index tồn tại + dùng được, không verify cost model).
- Code review (`31f9ab3`): 0 Critical / 4 Warning / 5 Info — WR-02 (cross-hub cắt top_k trước min_score), WR-01 (admin-all cache chỉ TTL-expire), WR-03/04 — non-blocking, cân nhắc fix Phase 9.
- Verifier (`4c8fd84`): status `human_needed` — 4/6 SC verified qua code + test (hub isolation E4, cross-hub, SC3 EXPLAIN HNSW partial-confidence, regression Phase 5 OK 7/7). 4 mục human-UAT (`06-HUMAN-UAT.md`): latency p95 single/cross-hub, recall 50 query VN, cache invalidation E2E — cần dữ liệu thật (chunks rỗng + OPENAI_API_KEY placeholder ở M2; eval set Phase 9). User approve checkpoint → phase đánh dấu complete.
- **SEARCH-01/02/03/04 — 4/4 REQ-ID done.** Carry-over: DEF-05-01 (pytest integration phải chạy per-file — cocoindex Environment singleton) vẫn áp dụng cho test_search_hub_isolation.py.

</details>

<details><summary>Phase 5 — Plan 05-06 (2026-05-17, đã lưu trữ)</summary>

**Last session (2026-05-17 — Plan 05-06 execute — PHASE 5 PLANS COMPLETE):** `/gsd-execute-phase 5 plan 05-06` → executor agent (sequential) thực thi 3 task atomic:

- Task 01 (`d9e59e2`): `routers/__init__.py` export 6 router. `main.py` `create_app()` mount 5 router Phase 5 (hubs/users/profile/api_keys/audit_logs — tổng 7 router) + wire slowapi (`app.state.limiter = limiter` + `add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)` → 429 envelope) + `@app.exception_handler(HubIsolationError)` → 403 envelope. `auth/api_key.py` mới — `require_api_key` X-API-Key dependency (thiếu header → 401 API_KEY_MISSING; key sai → 401 API_KEY_INVALID; gọi `ApiKeyService.verify_key` — BLOCKER 1). `auth/__init__.py` re-export.
- Task 02 (`e32af03`): `documents_service.delete()` retrofit hub isolation — signature `deleted_by:UUID` → `actor:User` + `actor_hub_ids:Sequence[str]`; gọi `verify_hub_access` (hub_id load TỪ DB row — T-05-06-02 KHÔNG payload); cross-hub reject → `enqueue_audit(security.hub_isolation_violation)` TẠI điểm reject TRƯỚC raise (T-05-06-03); admin bypass. `documents.py` DELETE endpoint auth `require_role("admin")` → `get_current_user_with_hubs` (editor-eligible); viewer reject 403 trước service; `HubIsolationError` → 403 envelope.
- Task 03 (`5f5bfea`): `conftest.py` TRUNCATE mở rộng (hubs/audit_logs/api_keys/documents/chunks) + helper `_insert_hub`/`_assign_user_hub` + AES_KEY test deterministic. `test_hub_isolation.py` 6 critical test E4 (editor cross-hub 403 + document tồn tại, audit logged, admin bypass 204, editor own-hub 204, viewer 403, verify_hub_access unit). `test_rate_limit.py` 4 test (429 envelope shape, under-limit pass, X-API-Key 401, auth/me không limit). Fix DEF-05-02 leftover (`_create_hub` test_documents_upload + test_ingest_e2e) + DEF-05-01 leftover (`_spawn_rbac_app` COCOINDEX_SKIP_SETUP + reset_queue).
- Verification: `ruff check app tests` clean; `mypy --strict app` 62 source clean. **E4 EXIT criteria VERIFIED — test_hub_isolation.py 6 critical test genuinely PASS against real DB testcontainer.** `pytest -m critical` per-file (DEF-05-01 — cocoindex Environment singleton KHÔNG chạy nhiều file boot cocoindex 1 process): 4 unit + 44 integration critical PASS; ngoại lệ DUY NHẤT `test_ingest_e2e::test_e2e_upload_docx_to_chunks_completed` (DEF-05-03 pre-existing — test cần cocoindex thật, mâu thuẫn shared fixture).
- 4 auto-fix deviation: Rule 3 (mypy type-ignore add_exception_handler), Rule 3 (Sequence[str] tránh shadow class method `list`), Rule 1 (_create_hub DEF-05-02 leftover 2 file), Rule 3 (_spawn_rbac_app DEF-05-01 leftover). DEF-05-03 logged deferred-items.md.
- SUMMARY.md `.planning/phases/05-hub-user-audit-apikey-settings-crud/05-06-SUMMARY.md` tạo với 3 commit hash + threat model T-05-06-01..07 (6 mitigate + 1 accept) + E4 verified + self-check PASSED.
- **HUB-02 + AUX-02 + AUX-03 requirements — router wiring + hub isolation enforce + E4 critical test + rate-limit + X-API-Key hoàn tất. Phase 5 PLANS COMPLETE (6/6).**

</details>

**Next action:** **Phase 7 IN PROGRESS — Plan 07-01 + 07-02 + 07-03 + 07-04 done (4/5).** Execute plan còn lại Phase 7: 07-05 (integration test suite — bao gồm ROADMAP SC1 citation map + SC2 anti-injection + SC3 hot-swap LLM + SC5 10-ask `usage_events` verify end-to-end + test `update_config` cross-dim 400 / within-dim warning). Plan 07-05 test 3 endpoint `/api/ask` + `/api/ask/cross-hub` + `/api/search/answer` (07-04) + `AskService` — LLM mock return citation `[N]` map đúng `chunks[N-1].chunk_id` (CONVENTIONS critical-path test bắt buộc cho Ask). Carry-over Phase 6: (1) 4 mục `06-HUMAN-UAT.md` chờ dữ liệu thật — latency p95 single/cross-hub + recall 50 query VN giải ở Phase 9 eval, cache invalidation E2E test bổ sung Phase 9/10; (2) code review 06-REVIEW.md 4 Warning — WR-02 (cross-hub cắt top_k trước min_score) + WR-01 (admin-all cache không event-invalidate) đáng fix khi đụng search ở Phase 7/9; (3) DEF-05-01 vẫn buộc chạy pytest integration per-file. Phase 4 + M2a EXIT GATE vẫn mở — theo dõi nếu cần đóng trước khi ship.

**Files cần đọc khi resume:**

- `.planning/PROJECT.md` (core value + 9 key decisions D1-D9 + risk register R1-R7 + EXIT criteria E1-E5)
- `.planning/ROADMAP.md` (10 phase + success criteria + critical path)
- `.planning/REQUIREMENTS.md` (38 REQ-ID + Traceability section)
- `.planning/research/SUMMARY.md` (research synthesis)
- `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS}.md` (chi tiết khi cần)
- `.planning/MILESTONES.md` (v1.0 abandoned context)

---

*Last updated: 2026-05-18 (**Phase 7 Plan 07-04 done** — `/gsd-execute-phase 7 plan 07-04`: ask_service.py AskService LiteLLM acompletion + citation + usage; routers/ask.py 3 endpoint POST /api/ask + /cross-hub + alias /api/search/answer rate-limit 100/min + usage BackgroundTasks, 2 commit, ruff + mypy --strict + mount 3 path PASS, 1 deviation Rule 3. Next: execute 07-05).*
