---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: M2 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)
status: ready_to_execute
last_updated: "2026-05-18T00:00:00Z"
progress:
  total_phases: 10
  completed_phases: 5
  total_plans: 32
  completed_plans: 32
  percent: 78
current_phase:
  number: 7
  name: Ask API + LiteLLM + Citation + Hot-Swap + Usage
  plans_total: 5
  plans_complete: 3
  status: in_progress
  waves: 3
next_phase:
  number: 8
  name: Frontend E2E Smoke
---

# State — MEDWIKI

**Mã dự án:** MEDWIKI
**Milestone:** v2.0 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)
**Ngày tạo state:** 2026-05-13 (pivot lần 2 — M1 Docling abandoned)
**Last updated:** 2026-05-13 (roadmap 10 phase tạo xong)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-13) + `.planning/ROADMAP.md` (created 2026-05-13)

**Core value:** Ingestion tri thức của Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức, OCR tiếng Việt cho scanned PDF — defer trong M2 vì D4) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.

**Current focus:** M2 = Full RAG Rewrite. Pivot lần 2 ngày 2026-05-13 từ "RAG Quality with Docling" sang "Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)". M1 cũ abandoned (28 plans code complete nhưng chưa runtime verify) — phases archive vào `.planning/milestones/v1.0-docling-rag/`.

**Mode:** YOLO · **Granularity:** Large (10 phase — reconciled từ FEATURES 8 + ARCHITECTURE 12 trong SUMMARY.md) · **Phase numbering:** Reset về Phase 1 (`--reset-phase-numbers`)

**M2a/M2b split (R3 anti-pivot fatigue mitigation):**
- **M2a = Phase 1-4** (Infra + Schema + Auth + CocoIndex MVP) — Có thể ship standalone. Nếu user accept M2a → never pivot.
- **M2b = Phase 5-10** (CRUD + Search + Ask + Frontend smoke + Eval + Hardening) — Pivot M2b OK nếu cocoindex critical fail.
- 🚦 **M2a EXIT GATE** giữa Phase 4 và Phase 5 — demo upload DOCX → chunks pgvector → SELECT verify. User accept là điều kiện tiếp tục M2b.

---

## Current Position

| Field | Value |
|---|---|
| Milestone | v2.0 Full RAG Rewrite |
| Phase | **Phase 7 — Ask API + LiteLLM + Citation + Hot-Swap + Usage** 🔵 IN PROGRESS (3/5 plans — 07-01 + 07-02 + 07-03 Wave 1 done) · Phase 6 ✅ COMPLETE trước đó |
| Plan | 07-01 ✅ (Wave 1: schema ask.py + ask_prompt.py anti-injection + citation parser; ASK-01/02 contract layer). 07-02 ✅ (Wave 1: schemas/usage.py 6 model TokenUsage + usage_service.py log_usage_event write + query/aggregate/realtime read + routers/usage.py 3 endpoint GET admin-only mount; ASK-05 write+read path). 07-03 ✅ (Wave 1: rag_config_service dimension guard + cost preview; ASK-04/R7 — DONE 2026-05-18). 07-04/05 chưa execute. |
| Status | **Phase 7 Plan 07-03 COMPLETE — rag-config dimension guard + cost preview (ASK-04 / R7).** Hoàn thiện endpoint `/api/rag-config` đã build sớm (commit `2d7a688`): `_embedding_dim_of()` parse hậu tố `@<dim>` từ model name; `update_config()` thêm dimension guard — cross-dim swap (1536↔3072) trả str → router map 400 "dimension mismatch — defer cross-dim swap v4.0", within-dim embedding swap trả dict + `warning` + `cost_preview` (re-embed N chunks, est $X.YZ, est T phút — cost luôn 2 chữ số `:.2f`); `_embedding_cost_preview()` count(*) chunks best-effort. `EmbeddingCostPreview` schema mới. 6/6 unit test pass (1 critical). 0 deviation. Router `rag_config.py` KHÔNG đụng (contract D6 raw JSON). Tiếp theo: execute 07-04/05. |
| Last activity | 2026-05-18 — `/gsd-execute-phase 7 plan 07-03`: executor sequential trên main tree. 3 task atomic — `789bc0d` (feat EmbeddingCostPreview schema), `2752d0b` (feat dimension guard + cost preview update_config), `29a11db` (test test_rag_config_dim_guard.py 6 test). Verification suite ruff + mypy --strict + pytest 6/6 + 1 critical pass sạch; `git diff --stat` xác nhận router KHÔNG đụng. |
| Total phases | 10 (M2a: 4 + M2b: 6) — Phase 1/2/3/5/6 complete · Phase 4 + M2a EXIT GATE chưa đóng (theo dõi riêng) |
| Total requirements | 38 v1 REQ-ID · 6 Phase 3 (AUTH-01..06) · 8 Phase 4 (INGEST-01..08) · 9 Phase 5 (HUB/USER/AUX) · **4 Phase 6 DONE** — SEARCH-01/02/03/04 (3 endpoint search + HNSW tuning + Redis cache + Pub/Sub invalidation; hub isolation E4 verified) |
| Critical path | 1 ✓ → 2 ✓ → 4 📋 → 6 ✓ → 7 → 9 → 10 |
| Auth branch | 3 ✓ (5/5 plans done) → 5 ✓ (6/6 plans done) → 8 |

**Progress bar:** `[████████░░] 80% (Phase 7 🔵 IN PROGRESS — Plan 07-01 + 07-02 + 07-03 done: Ask API contract layer + token usage write/read path + rag-config dimension guard/cost preview) · Next: execute 07-04/05`

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

**Last session (2026-05-18 — `/gsd-execute-phase 7 plan 07-03`):** executor agent sequential trên main working tree thực thi 3 task atomic của Plan 07-03 (Wave 1 — rag-config dimension guard + cost preview, ASK-04 / R7):
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

**Next action:** **Phase 7 IN PROGRESS — Plan 07-01 + 07-02 + 07-03 done (3/5).** Execute các plan còn lại Phase 7: 07-04 (AskService LiteLLM + router POST /api/ask — delivery đầy đủ ASK-01/02/03/05; gọi `log_usage_event` từ usage_service qua BackgroundTasks), 07-05 (integration test suite — bao gồm ROADMAP SC5 10-ask `usage_events` verify + test `update_config` cross-dim 400 / within-dim warning end-to-end). Plan 07-04 dùng contract `schemas/ask.py` + `build_ask_messages`/`parse_citations` từ 07-01 — KHÔNG dò codebase. Carry-over Phase 6: (1) 4 mục `06-HUMAN-UAT.md` chờ dữ liệu thật — latency p95 single/cross-hub + recall 50 query VN giải ở Phase 9 eval, cache invalidation E2E test bổ sung Phase 9/10; (2) code review 06-REVIEW.md 4 Warning — WR-02 (cross-hub cắt top_k trước min_score) + WR-01 (admin-all cache không event-invalidate) đáng fix khi đụng search ở Phase 7/9; (3) DEF-05-01 vẫn buộc chạy pytest integration per-file. Phase 4 + M2a EXIT GATE vẫn mở — theo dõi nếu cần đóng trước khi ship.

**Files cần đọc khi resume:**

- `.planning/PROJECT.md` (core value + 9 key decisions D1-D9 + risk register R1-R7 + EXIT criteria E1-E5)
- `.planning/ROADMAP.md` (10 phase + success criteria + critical path)
- `.planning/REQUIREMENTS.md` (38 REQ-ID + Traceability section)
- `.planning/research/SUMMARY.md` (research synthesis)
- `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS}.md` (chi tiết khi cần)
- `.planning/MILESTONES.md` (v1.0 abandoned context)

---

*Last updated: 2026-05-18 (**Phase 7 Plan 07-03 done** — `/gsd-execute-phase 7 plan 07-03`: rag_config_service dimension guard + cost preview + EmbeddingCostPreview schema, 3 commit, 6 unit test PASS (1 critical), 0 deviation, router KHÔNG đụng. Next: execute 07-04/05).*
