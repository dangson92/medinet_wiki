# Roadmap — Medinet Wiki (MEDWIKI)

**Project:** Medinet Wiki (Hub_All) · **Tracking:** ROADMAP (current = v3.1) + MILESTONES.md (history) + `.planning/milestones/v*/` (archives)
**Last updated:** 2026-05-23 (`/gsd-new-milestone v3.1`)

---

## Milestones

- ❌ **v1.0 RAG Quality with Docling** — Abandoned 2026-05-13 (xem [`milestones/v1.0-docling-rag/`](milestones/v1.0-docling-rag/))
- ✅ **v2.0 Full RAG Rewrite** — Shipped 2026-05-21 (archive: [`milestones/v2.0-full-rag-rewrite/`](milestones/v2.0-full-rag-rewrite/))
- ✅ **v3.0 Multi-Hub Split** — Shipped 2026-05-23 (archive: [`milestones/v3.0-multi-hub-split/`](milestones/v3.0-multi-hub-split/))
- ✅ **v3.1 RBAC hub_admin** — Shipped 2026-05-24 + Phase 5 DONE 2026-05-26 (re-open scope Document Version History), 5 phase / 20 REQ-ID / 20 plan (defer archive qua `/gsd-complete-milestone v3.1`; D-V3.1-04 phase numbering reset về 1)
- 📋 **v4.0 Production Hardening + Advanced RAG** — Backlog (OCR Vietnamese, cross-dim embedding swap, streaming `/api/ask`, coverage >80%, per-resource ACL, ...)
- 📋 **v4.1 Advanced Retrieval** — Backlog (Hybrid BM25 + reranker, local embedding SEED-001, version history)

---

## Phases — v3.1 RBAC hub_admin (CURRENT — re-opened 2026-05-26 for Phase 5)

4 phase reset numbering về 1 (precedent D9 v2.0 + D-V3-05 v3.0) + Phase 5 added 2026-05-26 (re-open v3.1 thay vì start v3.2 — scope nhỏ, version history pull từ v4.1 backlog). Total ~17-20 plan estimate.

| # | Phase | Goal | Requirements | Success Criteria | Depends on |
|---|---|---|---|---|---|
| **1** | DB schema migration (ROLE) ✅ DONE 2026-05-23 | Mở rộng `role_enum` thêm `hub_admin`; thêm column `user_hubs.role` per-hub; migration seed existing admins giữ super-admin | ROLE-01..04 (4) | 4 | v3.0 shipped — schema M2 `users.role` + `user_hubs` carry forward |
| **2** | Backend RBAC enforcement (DEP) ✅ DONE 2026-05-24 | Dependency `require_hub_admin_for(hub_id)`; refactor GET /api/hubs filter cả admin; users.py CRUD scope; hubs.py mutate super admin only; audit actor.scope | DEP-01..05 (5) | 5 | Phase 1 |
| **3** | Frontend form refactor (FE) ✅ DONE 2026-05-24 | UserManagement form 3 option; hub switcher hide central; edit modal disabled assign super; api.ts UserRole type extend | FE-01..04 (4) | 4 | Phase 2 |
| **4** | Migration + smoke E2E (MIGRATE) ✅ DONE 2026-05-24 | Migration idempotent + rollback; smoke E2E 4 scenario; closeout docs | MIGRATE-01..02 (2) | 2 | Phase 1-3 |
| **5** | Document version history (VER) ✅ DONE 2026-05-26 | Alembic migration `0007_document_versions` table 15 cột exact match DocumentVersionAPI interface + service `document_version_service.py` 5 API (snapshot dedupe-by-hash + restore append-only + retention CTE + audit emit 2 action) + router `document_versions.py` 4 endpoint exact match api.ts:268-285 + RBAC 3-layer (3 GET Layer 3 SSO-04 + POST inline assert_hub_admin_for) + 5 scenario E2E integration test PASS in 19.44s. FE `DocumentVersionHistory.tsx` 404 bug fixed. | VER-01..05 (5) | 5 | Phase 2 (RBAC) — independent của Phase 3+4 |

**Critical path:** 1 → 2 → 3 → 4 (RBAC linear). Phase 5 độc lập, depend Phase 2 RBAC (cho hub_admin scope filter).

**Parallel-able:** Phase 5 KHÔNG conflict với Phase 1-4 (đã shipped) — chỉ touch documents + audit module.

---

## Phase Details

### Phase 1 — DB schema migration (ROLE)

**Goal:** Mở rộng schema role: CHECK constraint `role_enum` table users thêm `hub_admin`; column `user_hubs.role` per-hub override (NULL = inherit global); helper `get_effective_role(user_id, hub_id)`; migration seed existing admin assignments giữ super-admin semantic.

**Requirements:** ROLE-01, ROLE-02, ROLE-03, ROLE-04

**Success criteria:**
1. `alembic upgrade head` 2 lần PASS idempotent; new CHECK constraint accept 4 value `admin | hub_admin | editor | viewer`.
2. `user_hubs.role` column nullable default NULL; existing rows preserved; helper `get_effective_role` 4-case unit test PASS.
3. Migration seed audit log INSERT row `action='migration.role_seed'` với count + timestamp.
4. `alembic downgrade -1` rollback PASS — restore CHECK constraint 3 value cũ, drop `user_hubs.role` column, existing data preserved.

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 1`):**
- **GA-V3.1-A:** Migration backward compat strategy — `users.role='admin'` map về super-admin semantic (KHÔNG rename) vs thêm flag column `users.is_super_admin` boolean (cleaner semantic / rename complexity). Khuyến nghị: giữ tên (D-V3.1-01 LOCKED).
- Helper function placement — `app/auth/role.py` module mới vs extend `app/auth/dependencies.py`.
- CHECK constraint name preserve vs rename — Alembic `op.create_check_constraint` đòi name; M2 dùng default name; cần verify post-migration introspect.

**Plans:** 3 plans (Wave 1 parallel Plan 01-01 + 01-02 — KHÔNG file conflict; Wave 2 sequential Plan 01-03 closeout).

Plans:
- [x] 01-01-PLAN.md — Alembic migration 0006_role_hub_admin (CHECK constraint mở rộng + user_hubs.role nullable + audit_logs seed `migration.role_seed`) (ROLE-01, ROLE-02, ROLE-03) ✅ DONE 2026-05-23
- [x] 01-02-PLAN.md — get_effective_role helper module + 6-case unit test (ROLE-04) ✅ DONE 2026-05-23
- [x] 01-03-PLAN.md — Closeout (integration test idempotent + STATE.md + REQUIREMENTS.md + CLAUDE.md update) ✅ DONE 2026-05-23

---

### Phase 2 — Backend RBAC enforcement (DEP)

**Goal:** Dependency `require_hub_admin_for(hub_id)` verify hub_id ∈ JWT.hub_ids + role check qua helper Phase 1; refactor `GET /api/hubs` filter cả admin (chỉ super admin trả ALL, hub_admin filter user_hubs); CRUD users.py + hubs.py scope per role; audit log tag actor.scope.

**Requirements:** DEP-01, DEP-02, DEP-03, DEP-04, DEP-05

**Success criteria:**
1. Hub_admin assigned `dmd` GET /api/hubs → CHỈ trả `dmd` (KHÔNG central, KHÔNG `tdt`); super admin GET /api/hubs → trả ALL.
2. Hub_admin POST /api/users (hub_id=`tdt`) → 403 HUB_ADMIN_REQUIRED; POST /api/users (hub_id=`dmd`) → 201; super admin POST any hub → 201.
3. Hub_admin POST /api/hubs (create hub mới) → 403 ROLE_REQUIRED (require_role("admin") giữ nguyên); super admin POST /api/hubs → 201.
4. Audit log row `action='user.create'` chứa `actor_role='hub_admin' + actor_hub_id='<dmd-uuid>'` cho hub_admin operation; super admin → `actor_role='admin' + actor_hub_id=NULL`.
5. Test coverage ≥ 80% trên dependencies.py mới + routers/hubs.py + routers/users.py thay đổi.

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 2`):**
- **GA-V3.1-B:** GET /api/hubs filter cho hub_admin — backend trả CHỈ hub được gán (giống non-admin path hiện tại) vs trả tất cả + frontend UI hide central. Khuyến nghị: backend filter (defense in depth + giảm dependency FE).
- 403 envelope code — `HUB_ADMIN_REQUIRED` mới vs reuse `FORBIDDEN` chung. Recommend new code cho frontend handle UX rõ hơn.
- Migration carry forward audit_logs schema — `actor_role` + `actor_hub_id` thêm 2 column hay nest vào `payload` JSON. Recommend payload nest (KHÔNG schema migration thêm cho audit_logs).

**Plans estimate:** 4-5 plans (BLOCKING Wave 1 dependency + Wave 2 endpoints parallel × 2 + Wave 3 audit + Wave 4 closeout).

Plans:
- [x] 02-01-PLAN.md — require_hub_admin_for validator + 5-case unit test + 403 envelope HUB_ADMIN_REQUIRED (DEP-01) ✅ DONE 2026-05-24
- [x] 02-02-PLAN.md — Integration test GET /api/hubs filter cả admin + POST hub_admin 403 verify + B2 iter 1 defensive AUTH_STATE_INCONSISTENT invariant guard (DEP-02 + DEP-04) ✅ DONE 2026-05-24
- [x] 02-03-PLAN.md — routers/users.py 4 endpoint refactor scope + UserRole Literal extend + DELETE B1 iter 1 3-branch + 7 integration test (DEP-03) ✅ DONE 2026-05-24
- [x] 02-04-PLAN.md — Audit payload actor_role + actor_hub_id nest 5 callsite + B7 iter 1 future-proof guard (DEP-05) ✅ DONE 2026-05-24
- [x] 02-05-PLAN.md — Closeout STATE.md + REQUIREMENTS.md + ROADMAP.md + CLAUDE.md update ✅ DONE 2026-05-24

---

### Phase 3 — Frontend form refactor (FE)

**Goal:** UserManagement form tạo user 3 option rõ ràng "Admin toàn hệ thống" vs "Quản lý hub này" vs "Viewer"; hub switcher filter central cho non-super-admin; edit modal disabled assign super_admin cho hub_admin; api.ts UserRole type extend `'hub_admin'`.

**Requirements:** FE-01, FE-02, FE-03, FE-04

**Success criteria:**
1. UserManagement form 3 radio option visible với description + warning banner cho "Admin toàn hệ thống" (vàng/cảnh báo); chọn role → form gửi đúng `role` value lên backend.
2. Login với hub_admin `dmd` → sidebar hub switcher CHỈ thấy `dmd`; KHÔNG có tab central; super admin login → thấy ALL hubs.
3. Hub_admin mở Manage modal user khác → option "Admin toàn hệ thống" disabled với tooltip "Cần Admin toàn hệ thống"; super admin → 3 option enable.
4. TypeScript build PASS với UserRole `'admin' | 'hub_admin' | 'editor' | 'viewer'`; vitest test cover form 3 option + hub switcher filter logic + edit modal disabled.

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 3`):**
- Hub switcher central detection logic — slug hardcode `central` vs API field `is_central` vs computed (parent_hub_id NULL).
- Backward compat existing UserManagement.tsx — currentUser.role check (frontend AuthContext có role không, hay cần fetch /api/profile)?
- Mock data update — `mockData.ts` thêm hub_admin user sample cho dev test (carry forward Phase 5 vitest pattern).

**Plans:** 4 plans (Wave 1 BLOCKING Plan 03-01 type+mock foundation + Wave 2 sequential Plan 03-02 form FE-01 → Plan 03-03 hub switcher FE-02 + Manage modal FE-03 cùng file UserManagement.tsx + Wave 3 BLOCKING Plan 03-04 closeout 3 vitest test + 4 docs).

Plans:
- [x] 03-01-PLAN.md — api.ts UserRole type extend + mockData.ts hub_admin sample + AuthContext currentUser.role verify (FE-04) ✅ DONE 2026-05-24
- [x] 03-02-PLAN.md — UserManagement.tsx form 3 option radio + warning banner + handleCreateUser update (FE-01) ✅ DONE 2026-05-24
- [x] 03-03-PLAN.md — Hub switcher filter central + Manage modal disabled assign super (FE-02, FE-03) ✅ DONE 2026-05-24
- [x] 03-04-PLAN.md — Closeout — vitest test (3 file mới / 8 file total 45 test PASS) + CLAUDE.md + STATE.md + REQUIREMENTS.md FE-01..04 [x] ✅ DONE 2026-05-24

---

### Phase 4 — Migration + smoke E2E (MIGRATE)

**Goal:** Migration script idempotent (re-run safety, rollback procedure) + smoke E2E 4 scenario (super_admin / hub_admin dmd / hub_admin tdt / viewer) qua pytest httpx + audit trail verify + closeout docs.

**Requirements:** MIGRATE-01, MIGRATE-02

**Success criteria:**
1. `alembic upgrade head` 2 lần liên tiếp PASS; `alembic downgrade -1` rollback PASS restore CHECK constraint 3 value; existing data preserve.
2. Smoke E2E pytest 4 scenario PASS:
   - **(1) super admin:** GET /api/hubs → ALL, POST user any hub → 201.
   - **(2) hub_admin dmd:** GET /api/hubs → chỉ `dmd`, POST user `dmd` → 201, POST user `tdt` → 403, GET /api/hubs/central → 403 hoặc filter ra.
   - **(3) hub_admin tdt:** Mirror (2) với hub `tdt`.
   - **(4) viewer:** list documents trong hub gán, KHÔNG create/edit user.
3. Audit log inspect: 4 scenario operation audit_logs row có `actor_role` + `actor_hub_id` đúng.
4. Closeout docs CLAUDE.md + STATE.md + ROADMAP.md + REQUIREMENTS.md mark v3.1 SHIPPED + tag `v3.1` git annotated.

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 4`):**
- **GA-V3.1-C:** Migration idempotent strategy — Alembic check `op.execute("DO $$ ... IF NOT EXISTS")` PL/pgSQL block vs introspect via `sa.inspect()` Python pre-condition. Recommend introspect (KHÔNG đụng PL/pgSQL nhiều).
- Rollback procedure — Alembic `downgrade()` function impl đầy đủ vs document-only "DROP COLUMN user_hubs.role + ALTER CHECK constraint". Recommend implement (Phase 1 carry forward Alembic 0005 v3.0 Plan 04-01 pattern).
- Smoke E2E live infra — pytest in-process (testcontainers) vs real docker compose. Recommend in-process (faster + reproducible CI).

**Plans estimate:** 2-3 plans (Wave 1 migration verify + Wave 2 smoke E2E + Wave 3 closeout).

Plans:
- [x] 04-01-PLAN.md — Migration verify (Makefile test-integration + test-migration shortcut target; 7 test PASS deferred do pre-existing test infra debt outside MIGRATE-01 scope; Migration 0006 verified LIVE Plan 01-01 ship) (MIGRATE-01) ✅ DONE 2026-05-24
- [x] 04-02-PLAN.md — Smoke E2E 4 scenario pytest httpx + audit forensic chain (test_smoke_e2e_v3_1_rbac.py ~430 LOC, 4 scenario PASS 19.86s testcontainers in-process) (MIGRATE-02) ✅ DONE 2026-05-24
- [x] 04-03-PLAN.md — Closeout v3.1 SHIPPED — 4 docs atomic update + git tag annotated v3.1 LOCAL ✅ DONE 2026-05-24

---

### Phase 5 — Document version history (VER)

**Goal:** Build version-history feature backend đang missing (frontend đã ship trước ở milestone trước — user gặp 404 console khi mở preview "Lịch sử phiên bản" tab). Alembic migration tạo `document_versions` table 14+ cột match frontend `DocumentVersionAPI` + service snapshot khi document mutate + 4 endpoint router + audit logging + RBAC hub-scope (carry forward Phase 2 `assert_hub_admin_for`).

**Requirements:** VER-01..05 (5 estimate — sẽ chốt ở `/gsd-discuss-phase 5`)
- **VER-01:** Schema migration `document_versions` table (id UUID + document_id FK + version_number INT + is_original BOOL + name TEXT + file_type TEXT + file_size BIGINT + file_path TEXT + file_hash TEXT + extractor_used TEXT + chunk_count INT + change_type ENUM `reupload|reextract|content_edit|restore` + change_note TEXT + created_by UUID FK users + created_at TIMESTAMPTZ + UNIQUE(document_id, version_number) + index document_id).
- **VER-02:** Service layer `document_version_service.py` snapshot create 4 trigger điểm — reupload preview confirm + edit content commit + reextract trigger + restore action; version_number monotonic increment per document.
- **VER-03:** Router 4 endpoint — `GET /api/documents/{id}/versions` list, `GET /api/documents/{id}/versions/{vid}` detail+chunks, `GET /api/documents/{id}/versions/{vid}/file` blob, `POST /api/documents/{id}/versions/{vid}/restore` rollback document → version cũ.
- **VER-04:** RBAC hub-scope — Layer 2 repository filter `WHERE hub_id IN (...)` carry forward + Layer 3 dependency `assert_hub_admin_for(document.hub_id)` Phase 2 carry forward + audit `document.version.{create,restore}` action.
- **VER-05:** Integration test pytest + testcontainers — 4 scenario (create version qua reupload + list returns ordered DESC + restore tạo version mới với `change_type=restore` + hub_admin scope enforce 403 cross-hub).

**Success criteria:**
1. `alembic upgrade head` idempotent (re-run KHÔNG fail) + downgrade rollback PASS; bảng `document_versions` 14+ cột + 1 UNIQUE + 1 index.
2. Reupload + edit content + reextract + restore mỗi action trigger 1 version row INSERT atomic cùng transaction; version_number monotonic per document_id.
3. Frontend `DocumentVersionHistory.tsx` mở console KHÔNG còn 404 error; list versions render OK với sample upload + reupload test.
4. RBAC enforce: hub_admin dmd GET version của doc thuộc tdt → 403 envelope `HUB_ADMIN_REQUIRED`; super admin OK; viewer GET list OK, POST restore → 403.
5. Audit forensic: 2 action `document.version.create` + `document.version.restore` row có `payload->>'actor_role'` + `payload->>'document_id'` + `payload->>'version_number'` queryable.

**Discuss-phase gray areas (chốt ở `/gsd-discuss-phase 5`):**
- **GA-V3.1-D (snapshot file storage):** Lưu file vào `file_store` UUID mới (mỗi version = file riêng — duplicate disk khi unchanged) HOẶC chỉ tham chiếu `file_path` (1 path = 1 hash, dedupe qua content-hash). Khuyến nghị: dedupe qua hash + reference; nhưng cần bảo đảm file gốc KHÔNG bị xóa khi version count = 0.
- **GA-V3.1-E (chunks snapshot):** Frontend `DocumentVersionChunkAPI` implies chunks per-version. Lưu snapshot cả `chunks` table theo version hay chỉ giữ chunk hiện tại + version_id chunks cũ overwrite? Khuyến nghị: KHÔNG snapshot chunks (chỉ giữ chunk_count + change_type metadata); restore = re-index version file qua cocoindex.
- **GA-V3.1-F (RBAC viewer):** Viewer có quyền GET list versions của doc trong hub mình không, hay chỉ admin/hub_admin? Khuyến nghị: viewer GET list OK (read-only feature; same as document detail).
- **GA-V3.1-G (3 gốc + 2 gần nhất pattern):** api.ts comment line 268 nói "3 gốc + 2 gần nhất" — limit list response hay trả full? Khuyến nghị: FE filter client-side, BE trả full chronological DESC.
- **GA-V3.1-H (Restore semantics):** Restore tạo version mới `change_type=restore` (history append-only) hay overwrite hiện tại + delete versions newer? Khuyến nghị: append-only (immutable history).

**Plans estimate:** 4-5 plans (Wave 1 schema migration + Wave 2 service snapshot 4 trigger + Wave 3 router 4 endpoint + Wave 4 RBAC integration test + Wave 5 closeout).

**Plans:** 5 plans (Wave 1 BLOCKING migration → Wave 2 BLOCKING service → Wave 3 BLOCKING router → Wave 4 BLOCKING integration test → Wave 5 BLOCKING closeout — linear critical path).

Plans:
- [x] 05-01-PLAN.md — Alembic migration 0007 document_versions table (15 cột exact match DocumentVersionAPI + UNIQUE doc_ver + INDEX document_id + CHECK change_type) + 5 integration test idempotent với DSN injection SAFETY pattern Plan 01-03 carry forward (VER-01) ✅ DONE 2026-05-26
- [x] 05-02-PLAN.md — document_version_service.py 5 public API + 3 helper (snapshot dedupe-by-hash D-V3.1-Phase5-A + restore append-only D-V3.1-Phase5-D + retention CTE D-V3.1-Phase5-E + audit emit 2 action D-V3.1-Phase5-H) + 8 unit test PASS in 4.45s (VER-02) ✅ DONE 2026-05-26
- [x] 05-03-PLAN.md — document_versions.py router 4 endpoint exact match api.ts:268-285 (envelope M2 + chunks=[] D-V3.1-Phase5-B + StreamingResponse RFC 6266 percent-encoded filename) + RBAC 3-layer (Layer 3 SSO-04 GET + inline assert_hub_admin_for POST /restore) + universal mount main.py + 10 unit test PASS in 5.04s (VER-03 + VER-04) ✅ DONE 2026-05-26
- [x] 05-04-PLAN.md — Integration test test_document_versions.py 5 scenario E2E PASS in 19.44s (create + list DESC + restore append-only + cross-hub 403 HUB_ADMIN_REQUIRED + audit forensic chain) qua app_with_auth + sample_docs python-docx inline (VER-05) ✅ DONE 2026-05-26
- [x] 05-05-PLAN.md — Closeout 4 docs atomic (STATE + REQUIREMENTS + ROADMAP + CLAUDE) + KHÔNG git tag mới mặc định (D-V3.1-Phase5 discretion semver clean) ✅ DONE 2026-05-26

---

## Phases — v3.0 (ARCHIVED ✅)

<details>
<summary>✅ <strong>v3.0 Multi-Hub Split (Phases 1-7)</strong> — SHIPPED 2026-05-23 · 38/38 plans · 30/30 REQ-ID</summary>

Full details: [`milestones/v3.0-multi-hub-split/ROADMAP.md`](milestones/v3.0-multi-hub-split/ROADMAP.md) · [`REQUIREMENTS.md`](milestones/v3.0-multi-hub-split/REQUIREMENTS.md) · [`phases/`](milestones/v3.0-multi-hub-split/phases/)

</details>

<details>
<summary>✅ <strong>v2.0 Full RAG Rewrite (Phases 1-10 + 8.1/8.2/8.3)</strong> — SHIPPED 2026-05-21 · 38/38 REQ-ID · 13/13 phases</summary>

Full details: [`milestones/v2.0-full-rag-rewrite/ROADMAP.md`](milestones/v2.0-full-rag-rewrite/ROADMAP.md) · [`phases/`](milestones/v2.0-full-rag-rewrite/phases/)

</details>

---

## Progress

| Milestone | Phases | Plans Complete | REQ-ID | Status | Completed |
| --- | --- | --- | --- | --- | --- |
| v1.0 RAG Quality with Docling | 5 | 28/28 | 34/34 | ❌ Abandoned | 2026-05-13 |
| v2.0 Full RAG Rewrite | 13 | ~75/75 | 38/38 | ✅ Shipped | 2026-05-21 |
| v3.0 Multi-Hub Split | 7 | 38/38 | 30/30 | ✅ Shipped | 2026-05-23 |
| **v3.1 RBAC hub_admin** | **5** | **20/20** | **20/20** | ✅ **SHIPPED + Phase 5 DONE** | 2026-05-26 |
| v4.0 Production Hardening | — | — | — | 📋 Backlog | — |
| v4.1 Advanced Retrieval | — | — | — | 📋 Backlog | — |

---

## EXIT Criteria — v3.1

| # | Trigger | Action |
|---|---|---|
| **E-V3.1-1** | Migration ROLE-01 / ROLE-02 fail rollback (downgrade -1 break existing data) | STOP, revert plan, redesign migration script — KHÔNG ship v3.1 nếu rollback risk production |
| **E-V3.1-2** | Hub isolation regress — super admin tạo bằng v3.0 (existing) KHÔNG còn truy cập được hubs sau migration | STOP, fix seed migration script idempotent, re-test 4 scenario |
| **E-V3.1-3** | Backward compat M2 v3.0 break — existing JWT bị reject sau deploy, user logged out toàn bộ | STOP, JWT claim schema preserve check — KHÔNG break JWT đã issue |

---

## Risk Register — v3.1

| # | Risk | Severity | Phase | Mitigation |
|---|---|---|---|---|
| R-V3.1-1 | Migration rollback unsafe — existing data lost khi downgrade | HIGH | 1, 4 | Alembic downgrade impl đầy đủ + test idempotent re-run 2 lần + smoke verify existing user preserve |
| R-V3.1-2 | Frontend role check bypass — UI hide central nhưng API trả full | MEDIUM | 2, 3 | Backend filter authoritative (DEP-02); FE chỉ UX layer (defense in depth) |
| R-V3.1-3 | Audit log incomplete — actor_role thiếu cho legacy operation post-migration | LOW | 2, 4 | DEP-05 payload nest extend; existing audit rows preserve KHÔNG cần backfill |

---

## Backlog (project-level parking lot)

Tham chiếu `.planning/BACKLOG.md` cho 999.x items. Highlights cho v4.0 / v4.1:

- 999.1 (M1) Incremental chunk re-embed → ✅ Absorbed v2.0
- Local embedding model (sentence-transformers, BGE-M3) → SEED-001 dormant v4.1
- OCR Vietnamese + table preservation revisit → v4.0
- Streaming `/api/ask` SSE → v4.0
- Hybrid retrieval BM25 + reranker → v4.1
- Comprehensive coverage >80% → v4.0
- Per-resource ACL granular (read/write/delete trên documents) → v4.0 (carry forward v3.1 RBAC foundation)
- Visual regression smoke 4 hub × 11 trang → v4.0 ops handover
- OAuth role mapping qua SSO group claim → v4.0

---

## Deferred Items (carry forward từ v3.0 close)

- **podman-init-admin-issue** (debug, deferred) — WSL Windows env-specific
- **Phase 06 HUMAN-UAT partial** — visual smoke runtime defer ops handover
- **Phase 06 VERIFICATION human_needed** — defer ops handover
- **SEED-001 local embedding model** (dormant) — v4.1

---

*Last updated: 2026-05-26 (Phase 5 DONE — Document Version History 5 plan ship VER-01..05; v3.1 milestone re-open scope catch-up FE 404 bug `DocumentVersionHistory.tsx`; total 5 phase / 20 REQ-ID / 20 plan). Original 2026-05-23 sau `/gsd-new-milestone v3.1` — RBAC hub_admin STARTED. Phase numbering reset về 1 (D-V3.1-04). Next: `/gsd-complete-milestone v3.1` archive HOẶC `/gsd-new-milestone v4.0` Production Hardening fresh discuss.*
