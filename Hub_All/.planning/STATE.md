---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: M2 — Full RAG Rewrite (CocoIndex + Python FastAPI + pgvector)
status: phase_in_progress
last_updated: "2026-05-14T04:01:09Z"
progress:
  total_phases: 10
  completed_phases: 2
  total_plans: 16
  completed_plans: 15
  percent: 38
current_phase:
  number: 3
  name: Auth Port + RBAC + Response Envelope
  plans_total: 5
  plans_complete: 4
  status: in_progress
next_phase:
  number: 4
  name: CocoIndex Flow MVP + Document Ingest
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
| Phase | **Phase 3 — Auth Port + RBAC + Response Envelope** (5 plans / 4 waves, **4/5 executed** — Plan 03-01 + 03-02 + 03-03 + 03-04 DONE) |
| Plan | 03-01 ✓ DONE (Wave 1: middleware infra + envelope UPPER_SNAKE_CASE + CORS P12 validator). 03-02 ✓ DONE (Wave 1: JWT keypair + PyJWT RS256 wrapper). 03-03 ✓ DONE (Wave 2: Argon2 password module + cross-compat R6 verified). 03-04 ✓ DONE (Wave 3: 4 endpoint /api/auth/login+refresh+logout+me + AuthService + Redis SETNX P16 + anti-timing dummy_password_hash + lifespan wire). 03-05 NEXT Wave 4 (RBAC require_role + 5-AC integration test). |
| Status | Phase 3 in progress — Plan 03-04 thực thi xong 5/5 task, 36/36 pytest no regress, AUTH-01/02/03 complete. 4 endpoint mount: POST/login + POST/refresh + POST/logout + GET/me. Lifespan wire JWTManager + dummy_password_hash + SQLAlchemy init_engine. P16 SETNX atomic lock cho refresh race + anti-timing oracle verified. |
| Last activity | 2026-05-14 — `/gsd-execute-phase 3 plan 03-04`: 5 commits atomic (c165c4d → 6b7d8a6 → 31d54fd → 8aaad3f → 1c9237f). 3 deviation Rule 3: (1) pydantic[email] bump pyproject.toml + uv sync install email-validator 2.3.0 cho EmailStr (plan đã anticipate); (2) ruff B008 false positive với FastAPI Depends → noqa 9 vị trí; (3) ruff C901 lifespan+create_app complexity 13/11 → noqa 2 vị trí (init sequence vốn nhiều step). 4 file created (schemas, service, dependencies, router) + 4 file modified (__init__.py extend 8 export, main.py lifespan+include_router+readyz check[jwt], pyproject.toml, uv.lock). |
| Total phases | 10 (M2a: 4 + M2b: 6) |
| Total requirements | 38 v1 REQ-ID · 1 satisfied CORE (CORE-02) · 5 satisfied Phase 3 (AUTH-01 — login; AUTH-02 — refresh + P16 SETNX; AUTH-03 — me + logout; AUTH-05 — Argon2 cross-compat; AUTH-06 — JWT keypair PKCS#8) · 1 planned remaining Phase 3 (AUTH-04 — RBAC require_role + integration test) |
| Critical path | 1 ✓ → 2 ✓ → 4 → 6 → 7 → 9 → 10 |
| Auth branch | 3 (2/5 plans) → 5 → 8 |

**Progress bar:** `[████░░░░░░] 38% (2/10 phase + 4/5 Phase 3 plans) · Phase 3 in progress: 4/5 plans done · Next: /gsd-execute-phase 3 plan 03-05 (RBAC require_role + 5-AC integration test suite)`

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

**Last session (2026-05-14 — Plan 03-04 execute):** `/gsd-execute-phase 3 plan 03-04` → executor agent thực thi 5 task atomic:
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

**Next action:** Chạy `/gsd-execute-phase 3 plan 03-05` để tiếp tục Wave 4 (RBAC `require_role(*roles)` implement đầy đủ + 5-AC integration test suite với testcontainers Postgres+Redis: login envelope shape + JWT compat / RBAC 403 viewer-editor / refresh race concurrent / PKCS#8 cross-process Go→Python verify / logout blacklist). Plan 03-05 sẽ extend `app/auth/dependencies.py::require_role` từ stub NotImplementedError → check `user.role in roles raise resp.forbidden()`. Sẽ wire FastAPI exception_handler render envelope cho HTTPException pass-through từ get_current_user. Sau 03-05 → Phase 3 COMPLETE → Phase 4 (CocoIndex Flow MVP).

**Files cần đọc khi resume:**

- `.planning/PROJECT.md` (core value + 9 key decisions D1-D9 + risk register R1-R7 + EXIT criteria E1-E5)
- `.planning/ROADMAP.md` (10 phase + success criteria + critical path)
- `.planning/REQUIREMENTS.md` (38 REQ-ID + Traceability section)
- `.planning/research/SUMMARY.md` (research synthesis)
- `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS}.md` (chi tiết khi cần)
- `.planning/MILESTONES.md` (v1.0 abandoned context)

---

*Last updated: 2026-05-14 (Phase 3 Plan 03-03 thực thi xong — 3/5 plans complete, R6 mitigation verified, DOC-BUG documented. Next: `/gsd-execute-phase 3 plan 03-04`)*
