---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: M2 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)
status: phase_planned
last_updated: "2026-05-15T00:00:00Z"
progress:
  total_phases: 10
  completed_phases: 3
  total_plans: 28
  completed_plans: 16
  percent: 50
current_phase:
  number: 5
  name: Hub + User + Audit + APIKey + Settings CRUD
  plans_total: 6
  plans_complete: 0
  status: planned
  waves: 4
next_phase:
  number: 6
  name: Search API Single + Cross-Hub
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
| Phase | **Phase 5 — Hub + User + Audit + APIKey + Settings CRUD** 📋 PLANNED (6 plans / 4 waves / 0/6 executed) — Ready to execute |
| Plan | 05-01 📋 (Wave 1: Migration 0003 additive cột hubs `code`/`subdomain`/`status` + users `phone`/`department`/`avatar_url`/`status` + api_keys cols; audit_service asyncio.Queue batch logger; test_audit_logger 100-concurrent; HUB-01/AUX-01). 05-02 📋 (Wave 2: hub isolation helper `hub_isolation.py` + slowapi rate-limit module; HUB-02/AUX-03). 05-03 📋 (Wave 3: Hub CRUD router/service/schema + stats; HUB-01/HUB-03). 05-04 📋 (Wave 3: User CRUD 3 update endpoint tách + reset-password log-only + Profile `/api/profile`; USER-01/02/03). 05-05 📋 (Wave 3: APIKey CRUD + AES-GCM + soft revoke + X-API-Key + GET /api/audit-logs; AUX-01/AUX-02). 05-06 📋 (Wave 4: wiring main.py + hub-isolation enforce + E4 critical test; HUB-02/AUX-02/AUX-03). |
| Status | **Phase 5 PLANNED** — `/gsd-plan-phase 5` ship 6 PLAN.md. Discuss inline → 05-CONTEXT.md (7 quyết định D-01..D-07: gỡ sync queue, rag-config riêng, token usage fresh, HubAPI bỏ field Go, frontend api.ts thắng). Pattern-mapper → 05-PATTERNS.md (22 file mapped). Plan checker iter 1: 2 BLOCKER (verify_key/verify_plaintext mismatch; Settings CRUD chưa resolve) + 5 WARNING. Revision → iter 2: 0 BLOCKER + 1 WARNING (HubStats `queries` count). Patch trực tiếp Plan 05-03 (document defer `queries` count) → 0/0. Coverage: 9/9 REQ-ID. Wave: W1 (05-01) → W2 (05-02) → W3 (05-03+04+05 parallel, zero file overlap) → W4 (05-06). Ready for `/gsd-execute-phase 5`. |
| Last activity | 2026-05-16 — `/gsd-plan-phase 5`: discuss-phase inline (3 user decision sync/rag-config/token-usage + 2 AskUserQuestion sync-D6/hub-legacy-fields) → 05-CONTEXT.md. Spawn gsd-pattern-mapper (1) + gsd-planner (1 draft + 1 revision) + gsd-plan-checker (2 verify). Manual patch Plan 05-03 document `queries` count defer. KHÔNG run research (config research:false + user chọn skip); KHÔNG run UI gate (Phase 5 backend-only, "per_page" false-positive); Nyquist N/A (research disabled). |
| Total phases | 10 (M2a: 4 + M2b: 6) — **3/10 complete (Phase 1 + 2 + 3)** · **Phase 5 planned** |
| Total requirements | 38 v1 REQ-ID · 6 satisfied Phase 3 (AUTH-01..06) · 8 Phase 4 (INGEST-01..08) · **9 planned Phase 5** (HUB-01/02/03 hub registry CRUD + isolation + stats; USER-01/02/03 user CRUD + reset-password + profile; AUX-01/02/03 audit logger + apikey AES-GCM + rate limit) |
| Critical path | 1 ✓ → 2 ✓ → 4 📋 → 6 → 7 → 9 → 10 |
| Auth branch | 3 ✓ (5/5 plans done) → 5 📋 → 8 |

**Progress bar:** `[██████░░░░] 50% (3/10 phase complete · Phase 5 📋 planned 6/6 plans + 0/6 executed) · Next: /gsd-execute-phase 5 (HUB/USER/AUX 9 REQ-ID)`

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

**Last session (2026-05-14 — Plan 03-05 execute — PHASE 3 COMPLETE):** `/gsd-execute-phase 3 plan 03-05` → executor agent thực thi 6 task atomic:
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

**Next action:** **Phase 3 COMPLETE.** Chạy `/gsd-execute-phase 4` để bắt đầu Phase 4 (CocoIndex Flow MVP + Document Ingest — INGEST-01..08). Phase 4 sẽ implement: cocoindex flow LISTEN/NOTIFY với extract/chunk/embed/pgvector pipeline, format whitelist `{.docx, .txt, .md, .pdf text-only}` (D4 — scanned PDF → `failed_unsupported`), heartbeat watchdog cron (P8 mitigation), Vietnamese chunking boundary (P13 custom regex `Mục N.`/`Chương N.`), char-based tokenizer (P14 cross-provider). Phase 4 mở `M2a EXIT GATE` 🚦 cuối phase: demo upload DOCX → chunks pgvector → SELECT verify (R3 mitigation, user accept condition). Research flag HIGH (3 open question: cocoindex augmenter parity / PDF table VN / chunking boundary empirical resolve).

**Files cần đọc khi resume:**

- `.planning/PROJECT.md` (core value + 9 key decisions D1-D9 + risk register R1-R7 + EXIT criteria E1-E5)
- `.planning/ROADMAP.md` (10 phase + success criteria + critical path)
- `.planning/REQUIREMENTS.md` (38 REQ-ID + Traceability section)
- `.planning/research/SUMMARY.md` (research synthesis)
- `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS}.md` (chi tiết khi cần)
- `.planning/MILESTONES.md` (v1.0 abandoned context)

---

*Last updated: 2026-05-14 (**Phase 3 COMPLETE** — Plan 03-05 thực thi xong, 5/5 plans done, 5/5 ROADMAP AC verified end-to-end, 6/6 AUTH requirements done. Next: `/gsd-execute-phase 4` CocoIndex Flow MVP).*
