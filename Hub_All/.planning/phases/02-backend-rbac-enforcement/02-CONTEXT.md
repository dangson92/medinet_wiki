---
phase: 02-backend-rbac-enforcement
gathered: 2026-05-24
status: Ready for planning
source: ROADMAP gray-area recommendations (auto mode skipped /gsd-discuss-phase)
---

# Phase 2: Backend RBAC enforcement (DEP) — Context

**Trigger:** v3.1 milestone đóng RBAC hub_admin gap (project_rbac_hub_admin_gap memory + ROADMAP §"Phase 2"). Phase 1 đã ship schema migration 0006 + helper `get_effective_role` (ROLE-01..04). Phase 2 add backend enforcement; Phase 3 sẽ add frontend; Phase 4 verify E2E.

**Auto mode note:** `/gsd-discuss-phase 2` được skip; CONTEXT.md này derive trực tiếp từ ROADMAP §"Discuss-phase gray areas" — mỗi gray area đã có recommendation rõ ràng, treat như LOCKED decision.

<domain>
## Phase Boundary

**Trong scope Phase 2 (DEP):**
- DEP-01: Dependency mới `require_hub_admin_for(hub_id)` ở `api/app/auth/dependencies.py` + 5-case unit test + 403 envelope `HUB_ADMIN_REQUIRED`.
- DEP-02: Refactor `GET /api/hubs` (`api/app/routers/hubs.py:73-77`) — remove admin bypass; admin role='admin' global trả ALL, role !='admin' (kể cả hub_admin) filter qua `user_hubs`.
- DEP-03: `api/app/routers/users.py` CRUD scope hub_admin — list/create/edit role/edit status/delete check `require_hub_admin_for(target_hub_id)` (hub_admin) hoặc super admin pass; cross-hub admin operation (đổi user giữa hub) → super admin only.
- DEP-04: `api/app/routers/hubs.py` mutate endpoints (POST/PUT/PATCH `/api/hubs[/{id}[/status]]`) GIỮ `require_role("admin")` — hub_admin KHÔNG được tạo hub mới hoặc đổi metadata hub khác.
- DEP-05: Audit log payload extend `actor_role` (admin / hub_admin) + `actor_hub_id` (NULL nếu super admin) — nest vào `payload` JSONB hiện có; KHÔNG schema migration thêm cho `audit_logs`.

**Ngoài scope (defer Phase 3/4):**
- FE-01..04: Frontend form refactor + hub switcher (Phase 3 v3.1).
- MIGRATE-01..02: Migration idempotent + smoke E2E 4 scenario qua pytest httpx live DB (Phase 4 v3.1).
- audit_logs schema migration thêm cột (KHÔNG cần — nest vào payload đủ).
- Role-per-resource ACL granular (defer v4.0).
- Multi-role 1 user trong cùng hub (defer; mỗi user_hubs row 1 role override).

</domain>

<decisions>
## Implementation Decisions (LOCKED)

### D-V3.1-Phase2-A — Backend filter cho GET /api/hubs (defense in depth)

**Recommendation từ ROADMAP §"GA-V3.1-B":** Backend trả CHỈ hub được gán cho hub_admin (giống non-admin path hiện tại `routers/hubs.py:78-85`); KHÔNG dựa vào frontend UI hide central.

**Lý do LOCKED:**
- Defense in depth — stale JWT / FE bug / direct API call KHÔNG bypass.
- Giảm dependency FE — Phase 3 FE-02 chỉ cần render data backend trả, KHÔNG cần re-filter list.
- Đối xứng với `get_current_user_for_hub_access` (Phase 3 v3.0 SSO-04 Layer 3) — backend là source-of-truth cho RBAC.

**Cách implement:**
- Sửa branch `if user.role == "admin":` (line 73) thành `if user.role == "admin":` GIỮ NGUYÊN, NHƯNG đảm bảo hub_admin (`user.role` global = 'editor'/'viewer'/'admin' tuỳ migration; effective role per-hub qua `get_effective_role` mới quan trọng) đi vào branch `else:` cùng path với non-admin → filter `user_hubs`.
- Theo D-V3.1-01 LOCKED (Phase 1): `users.role='admin'` GIỮ semantic super-admin global. Hub_admin = user có `user_hubs.role='hub_admin'` cho hub cụ thể (per-hub override). User với `users.role='admin'` global = super admin → branch `if user.role == "admin":` đúng nguyên (return ALL). Hub_admin → `user.role` global thường 'editor' → đi vào else branch list_for_hubs.
- **Hệ quả:** Logic GET /api/hubs branch hiện tại `if user.role == "admin"` ĐÃ tương thích nếu hub_admin được giữ `users.role='editor'` global + override `user_hubs.role='hub_admin'`. CẦN verify hub_admin user thực sự rơi vào else branch — viết unit/integration test xác nhận.

### D-V3.1-Phase2-B — 403 envelope `HUB_ADMIN_REQUIRED` riêng (KHÔNG reuse FORBIDDEN chung)

**Recommendation từ ROADMAP §"gray areas":** 403 envelope code mới `HUB_ADMIN_REQUIRED` thay vì reuse `FORBIDDEN`.

**Lý do LOCKED:**
- Frontend Phase 3 FE-01 có thể switch trên `error.code` để show UX khác biệt ("Bạn không phải hub_admin của hub này" vs "Bạn không đủ quyền chung").
- Match pattern Phase 3 v3.0 SSO-04 (`CROSS_HUB_ACCESS_DENIED`) + Phase 6 v3.0 SETTINGS-03 (`INTERNAL_AUTH_FAIL`) — code cụ thể cho từng failure mode.

**Cách implement:**
- `require_hub_admin_for(hub_id)` raise `HTTPException(403, detail={"code":"HUB_ADMIN_REQUIRED","message":"..."})`.
- Helper `resp.forbidden(message="...", code="HUB_ADMIN_REQUIRED")` ĐÃ chấp nhận `code` param (xem `api/app/pkg/response.py:98`); KHÔNG cần helper mới.

### D-V3.1-Phase2-C — Audit log payload nest (KHÔNG schema migration audit_logs)

**Recommendation từ ROADMAP §"gray areas":** Nest `actor_role` + `actor_hub_id` vào `payload` JSONB; KHÔNG thêm cột mới cho audit_logs.

**Lý do LOCKED:**
- `audit_logs.payload` đã JSONB nullable (migration 0001) — đủ chứa metadata thêm.
- Đối xứng pattern Phase 4 v3.0 sync `migration.role_seed` payload nest count+timestamp.
- KHÔNG migration schema thêm cho v3.1 = giảm rủi ro + dễ rollback.
- Forensic query vẫn filter được qua `audit_logs.payload->>'actor_role'` + `payload->>'actor_hub_id'`.

**Cách implement:**
- Sửa `AuditEntry.payload` callers (`user_service.py`, `hub_service.py`, `api_key_service.py`) để inject `actor_role` + `actor_hub_id` vào `payload` dict TRƯỚC khi enqueue.
- Helper convenience: Thêm hàm `build_audit_payload(*, actor_role: str, actor_hub_id: str | None, extra: dict | None) -> dict` ở `audit_service.py` để dedup; hoặc constructor `AuditEntry.with_actor_scope(...)` factory method.
- Caller path: router phải pass `actor_role` + `actor_hub_id` xuống service. Hub_admin với hub_id cụ thể → `actor_hub_id=<hub_id>`. Super admin → `actor_hub_id=None`.

### D-V3.1-Phase2-D — Dependency design `require_hub_admin_for(hub_id)`

**Recommendation:** Closure pattern giống `require_role(*roles)` (xem `api/app/auth/dependencies.py:290-333`) — return Callable mà FastAPI inject `user = Depends(get_current_user) + db = Depends(get_session)`.

**Logic 5 case (acceptance test):**
1. Super admin (`user.role == 'admin'` global) → PASS (bypass — quản trị cross-hub theo thiết kế).
2. Hub_admin của hub đúng (`get_effective_role(user.id, hub_id) == 'hub_admin'`) → PASS.
3. Hub_admin của hub khác → 403 HUB_ADMIN_REQUIRED.
4. Viewer / editor không phải hub_admin → 403 HUB_ADMIN_REQUIRED.
5. User không có membership user_hubs row của hub → 403 HUB_ADMIN_REQUIRED (`get_effective_role` fallback global; nếu global != 'admin' → reject).

**Lưu ý:** `hub_id` là **runtime value** (lấy từ path param hoặc query param) → dependency phải accept hub_id từ context. Pattern FastAPI: viết dep factory `require_hub_admin_for(hub_id_source: str)` return Callable extract hub_id từ request path/query — HOẶC dùng explicit Depends signature trong handler ("hub_id" path param đã có).

**Recommended pattern:**
```python
async def require_hub_admin_for(
    hub_id: str,  # path param hoặc query
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> User:
    if user.role == "admin":
        return user  # super admin bypass
    role = await get_effective_role(db, user.id, hub_id)
    if role != "hub_admin":
        raise HTTPException(403, detail={"code":"HUB_ADMIN_REQUIRED","message":"..."})
    return user
```
→ Endpoint dùng: `async def create_user(req, user=Depends(require_hub_admin_for))` — FastAPI auto-resolve `hub_id` từ req body hoặc path. **Khó:** `users.py` create POST body chứa `hub_id` → cần đọc body trước Depends → workaround: viết wrapper hoặc validate inline trong handler.

**Alternative:** Pure validator function `await assert_hub_admin(user, db, hub_id)` (không phải dep) — gọi inline trong handler sau khi parse body. Linh hoạt hơn cho POST/PATCH endpoints có hub_id trong body.

Planner cần quyết định final pattern (dep vs validator function) — recommend hybrid:
- Endpoint có `hub_id` trong path (vd `/api/hubs/{hub_id}/...` Phase 3 v4.0 future) → Depends pattern.
- Endpoint Phase 2 (`users.py` POST body hub_id, PATCH /role body hub_id, DELETE không hub_id) → inline validator function `assert_hub_admin_for(...)` trong handler sau body parse.

### D-V3.1-Phase2-E — Cross-hub admin operation = super admin only

**Lý do LOCKED:** ROADMAP §"DEP-03" — "Cross-hub admin operation (đổi user từ hub này sang hub khác) chỉ super admin."

**Cách implement:**
- `PATCH /api/users/:id/role` body có `hub_id` field — nếu user target hiện thuộc hub khác (`user_hubs` row khác hub_id mới) → cần super admin (`user.role == 'admin'` global). Hub_admin chỉ được đổi role TRONG hub của mình.
- `DELETE /api/users/:id` — user target có thể thuộc nhiều hub; hub_admin của hub A xoá user thuộc CHỈ hub A → OK; user thuộc cả hub A + hub B → CẦN super admin.

### D-V3.1-Phase2-F — Test coverage target ≥ 80% trên file thay đổi

**Lý do LOCKED:** ROADMAP §"Phase 2 success criteria 5". Pattern Phase 1 test coverage carry forward (pure Python unit + mocked AsyncSession).

**Cách implement:**
- Unit test cho `require_hub_admin_for` 5 case (mocked `get_effective_role` AsyncSession) — pattern `tests/unit/test_role_helper.py` carry forward.
- Integration test pytest httpx AsyncClient + testcontainers Postgres cho 5 endpoint thay đổi (`users.py` CRUD scope). Carry forward Phase 1 integration test pattern (`test_migration_0006_idempotent.py` skip-if-no-DB fixture).
- Pure unit cho audit payload nest helper (mocked enqueue_audit).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 v3.1 (foundation Phase 2 depends on)
- `Hub_All/.planning/phases/01-rbac-schema-migration/01-01-PLAN.md` — Alembic 0006 schema (CHECK + user_hubs.role + audit seed)
- `Hub_All/.planning/phases/01-rbac-schema-migration/01-02-PLAN.md` — get_effective_role helper API contract
- `Hub_All/.planning/phases/01-rbac-schema-migration/01-02-SUMMARY.md` — Phase 1 helper finalized
- `Hub_All/api/app/auth/role.py` — `get_effective_role(session, user_id, hub_id) -> str` + `UserNotFoundError`
- `Hub_All/api/migrations/versions/0006_role_hub_admin.py` — schema source of truth (4-value CHECK + user_hubs.role)

### Backend RBAC convention carry forward (v3.0 + M2)
- `Hub_All/api/app/auth/dependencies.py` — `require_role(*roles)` closure pattern (line 290-333); `get_current_user` Phase 3 SSO-01 branch verify (line 86-248); `get_current_user_for_hub_access` Phase 3 SSO-04 Layer 3 (line 365-431); `require_internal_auth` Phase 6 SETTINGS-03 (line 251-287)
- `Hub_All/api/app/routers/hubs.py` — `GET /api/hubs` admin bypass (line 73-77) cần refactor + 5 endpoint mutate (POST/PUT/PATCH/stats) GIỮ require_role("admin")
- `Hub_All/api/app/routers/users.py` — 7 endpoint admin-only require_role("admin") (line 64/94/114/138/162/188/212/261) cần refactor 5 trong số chúng

### Audit service contract
- `Hub_All/api/app/services/audit_service.py` — `AuditEntry` dataclass (line 51-65) + `enqueue_audit` non-blocking + `audit_flush_loop` batch flush
- `Hub_All/api/app/services/user_service.py:182-192` — pattern enqueue_audit cho `user.create` action
- `Hub_All/api/app/services/user_service.py:465-478` — pattern enqueue_audit cho `user.delete` action
- `Hub_All/api/app/services/hub_service.py:113-122` — pattern enqueue_audit cho `hub.create` action
- `Hub_All/api/app/services/hub_service.py:246-256` — pattern enqueue_audit cho `hub.update` action

### Response envelope (D6 LOCKED M2)
- `Hub_All/api/app/pkg/response.py:98-103` — `resp.forbidden(message, code)` 403 envelope shape `{success:false, data:null, error:{code, message}, meta:null}`

### Models + schema
- `Hub_All/api/app/models/auth.py:30-114` — User + UserHub ORM model (UserHub composite PK user_id+hub_id; Phase 1 migration 0006 thêm `role` nullable column NHƯNG ORM model CHƯA reflect — Phase 2 KHÔNG cần add column vào model nếu chỉ truy cập qua `get_effective_role` raw SQL; nhưng nếu service code dùng ORM SELECT UserHub.role thì cần update model)
- `Hub_All/api/app/schemas/users.py` — `CreateUserRequest`, `UpdateUserRequest`, `ChangeUserRoleRequest`, `ChangeUserStatusRequest` Pydantic schemas (cần verify hub_id field có tồn tại)

### Tests carry forward
- `Hub_All/api/tests/unit/test_require_role.py` — pattern unit test cho `require_role` closure
- `Hub_All/api/tests/unit/test_role_helper.py` — pattern AsyncMock(AsyncSession) cho test helper async
- `Hub_All/api/tests/unit/test_require_internal_auth.py` — pattern unit test cho header-based dep
- `Hub_All/api/tests/unit/test_require_api_key_hub_branch.py` — pattern integration unit test branch logic

### Project + memory
- `Hub_All/.planning/ROADMAP.md` §"Phase 2 — Backend RBAC enforcement (DEP)" — requirements DEP-01..05 + success criteria 5 + gray areas
- `Hub_All/.planning/REQUIREMENTS.md` §"DEP" — 5 REQ-ID DEP-01..05 acceptance text
- `Hub_All/.planning/STATE.md` — current milestone v3.1 Phase 1 DONE, Phase 2 next
- `Hub_All/CLAUDE.md` — language convention (Vietnamese có dấu) + stack pin Python 3.12 + ruff/mypy strict + test pytest + httpx + testcontainers
- Memory `project_rbac_hub_admin_gap` — trigger context (user bug report 2026-05-23) + user accept option B "proper fix"

</canonical_refs>

<specifics>
## Specific Implementation Hints

### File modifications (planner sẽ chia waves)

1. **`api/app/auth/dependencies.py`** — ADD `require_hub_admin_for` dep + ADD `assert_hub_admin_for` validator function (hybrid pattern D-V3.1-Phase2-D). KHÔNG đụng `require_role` hoặc các dep khác đã có.
2. **`api/app/routers/hubs.py`** — GET /api/hubs verify hub_admin rơi đúng else branch (test-driven, có thể KHÔNG code change nếu logic đã đúng). 5 endpoint mutate (POST/PUT/PATCH/stats) GIỮ NGUYÊN `require_role("admin")`.
3. **`api/app/routers/users.py`** — 5 endpoint (POST create, GET list, PUT update, PATCH role, PATCH status, DELETE, POST reset-password) → REFACTOR scope check. Super admin pass; hub_admin check qua `assert_hub_admin_for(user, db, target_hub_id)` inline trong handler sau body parse.
4. **`api/app/services/audit_service.py`** — ADD helper `build_audit_payload(*, actor_role, actor_hub_id, extra)` HOẶC method `AuditEntry.with_actor_scope(...)`. Caller inject actor metadata vào payload.
5. **`api/app/services/user_service.py`** — UPDATE 2 callsite enqueue_audit (line 182-192 user.create + line 465-478 user.delete) để inject actor_role + actor_hub_id. Signature `create` + `delete` thêm params `actor_role: str + actor_hub_id: str | None`.
6. **`api/app/services/hub_service.py`** — UPDATE 3 callsite enqueue_audit (hub.create + hub.update twice) để inject actor_role + actor_hub_id. Hub admin KHÔNG được tạo hub mới (DEP-04) → super admin call only → actor_role='admin', actor_hub_id=None luôn.
7. **`api/app/services/api_key_service.py`** — Verify nếu có audit emit, update tương tự. Plan 06-03 SETTINGS-03 đã touch — review xem có audit action nào không.
8. **`api/tests/unit/test_require_hub_admin_for.py`** — NEW file 5-case unit test pattern test_require_role + test_role_helper carry forward.
9. **`api/tests/unit/test_audit_actor_scope.py`** — NEW file unit test audit payload nest helper.
10. **`api/tests/integration/test_dep_users_scope.py`** — NEW file integration test 5 case scenario (hub_admin dmd pass dmd CRUD, fail tdt CRUD, super admin pass any, cross-hub admin op super-only).

### Test scenario reference (carry forward ROADMAP §"success criteria")

1. Hub_admin assigned `dmd` GET /api/hubs → CHỈ trả `dmd` (KHÔNG central, KHÔNG `tdt`).
2. Super admin GET /api/hubs → trả ALL.
3. Hub_admin POST /api/users (hub_id=`tdt`) → 403 HUB_ADMIN_REQUIRED.
4. Hub_admin POST /api/users (hub_id=`dmd`) → 201.
5. Super admin POST /api/users any hub → 201.
6. Hub_admin POST /api/hubs (create hub mới) → 403 (envelope code = FORBIDDEN — `require_role("admin")` reject với code FORBIDDEN; ROADMAP "403 ROLE_REQUIRED" có thể đổi tên cho rõ → recommend GIỮ FORBIDDEN match existing `require_role`).
7. Super admin POST /api/hubs → 201.
8. Audit log row `action='user.create'` chứa `payload->>'actor_role' = 'hub_admin'` + `payload->>'actor_hub_id' = '<dmd-uuid>'` cho hub_admin operation.
9. Audit log row `action='user.create'` chứa `payload->>'actor_role' = 'admin'` + `payload->>'actor_hub_id' IS NULL` cho super admin.

### Backward compat (Phase 2 KHÔNG break v3.0)

- M2 + v3.0 + v3.1 Phase 1 user `users.role='admin'` GIỮ semantic super-admin global (D-V3.1-01 LOCKED).
- M2 + v3.0 endpoint URL/envelope `{success, data, error, meta}` LOCKED — chỉ change error code (`HUB_ADMIN_REQUIRED` mới, KHÔNG break existing FORBIDDEN consumer FE).
- Hub_admin = user mới được tạo bởi admin ở Phase 3 FE-01 → tại thời điểm Phase 2 ship, có thể CHƯA có hub_admin user nào trong DB (Phase 3 FE chưa cho phép tạo). Integration test có thể tự seed test fixture user role='hub_admin' qua direct DB INSERT.
- `require_role("admin")` semantic KHÔNG đổi (super admin only). `require_hub_admin_for` mới = layer thêm cho per-hub gate.

### Threat model preview (Phase 2 STRIDE)

- **T-02-01-E** Elevation: hub_admin gọi `POST /api/hubs` create → mitigated bởi DEP-04 require_role("admin") GIỮ.
- **T-02-02-E** Elevation: hub_admin gán role='admin' cho user khác qua PATCH /api/users/:id/role → mitigated bởi `require_hub_admin_for(target_hub_id)` + business logic block role='admin' cho non-super-admin caller (recommend block role transition admin trong handler).
- **T-02-03-I** Information Disclosure: hub_admin list users hub khác qua GET /api/users?hub_id=tdt → mitigated bởi filter scope hub_admin chỉ list user trong user_hubs scope.
- **T-02-04-R** Repudiation: hub_admin operation KHÔNG audit trail → mitigated bởi DEP-05 audit payload extend.
- **T-02-05-T** Tampering: stale JWT hub_admin gọi sau khi bị demote → mitigated bởi `get_effective_role` query DB live mỗi request (KHÔNG cache role trong JWT cho per-hub).

### Schema status note

- Phase 1 migration 0006 đã add column `user_hubs.role TEXT NULL DEFAULT NULL` + CHECK NULL-aware constraint.
- Phase 1 ORM model `UserHub` (`api/app/models/auth.py:91-114`) CHƯA reflect column `role` — Phase 2 cần verify xem có ORM SELECT UserHub.role nào không; nếu service dùng raw SQL `text()` đọc user_hubs.role (như `get_effective_role`) thì KHÔNG cần update ORM model. **Recommend:** ADD `role: Mapped[str | None]` vào `UserHub` class để type-check + dùng ORM SELECT thuần nếu cần. Optional — KHÔNG blocking.

</specifics>

<deferred>
## Deferred Ideas

- **Per-resource ACL granular** (read/write/delete trên documents, api_keys, settings) — defer v4.0 sau khi hub_admin proven stable.
- **OAuth role mapping SSO** (Google Workspace, AzureAD group claim → role auto-mapping) — defer v4.0.
- **Audit log search UI** filter theo actor_role / actor_hub_id ở frontend — defer v4.0 (Phase 2 chỉ ship backend payload; query qua SQL/Grafana cho v3.1).
- **Multi-role 1 user trong cùng hub** (vd user vừa hub_admin vừa viewer) — out scope; mỗi user_hubs row 1 role override.
- **Rename `users.role='admin'` → `'super_admin'`** — out scope (D-V3.1-01 LOCKED giữ semantic 'admin').
- **Visual regression smoke 4 hub × 11 trang** — Phase 4 v3.1 MIGRATE-02 carry forward defer ops handover.
- **audit_logs schema migration thêm 2 column actor_role + actor_hub_id** — out scope Phase 2 (nest payload đủ — D-V3.1-Phase2-C LOCKED).

</deferred>

---

*Phase: 02-backend-rbac-enforcement*
*Context gathered: 2026-05-24 (auto mode — skipped `/gsd-discuss-phase 2`, derived from ROADMAP §"Phase 2" gray-area recommendations LOCKED)*
