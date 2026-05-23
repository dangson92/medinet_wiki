# Requirements: Medinet Wiki — Milestone v3.1 (RBAC hub_admin)

**Defined:** 2026-05-23
**Milestone:** v3.1 — RBAC hub_admin (proper role-per-hub fix)
**Core Value (carry forward v3.0):** Ingestion tri thức Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn. v3.1 đóng gap RBAC role-per-hub được defer v4.0 trong M2 — user "quản lý hub" phải CHỈ vào và quản lý hub được gán.

**Trigger:** User bug report 2026-05-23 sau v3.0 close — tạo user gán hub `dmd` nhưng vẫn vào được central. Memory: `project_rbac_hub_admin_gap`.

---

## v1 Requirements (v3.1 scope — 15 REQ-ID đề xuất)

### ROLE — DB schema migration (4 REQ)

- [ ] **ROLE-01** Phase 1: Mở rộng CHECK constraint `role_enum` ở table `users` thêm value `'hub_admin'` (Alembic migration idempotent). Existing rows giữ nguyên; INSERT mới chấp nhận 4 giá trị `admin | hub_admin | editor | viewer`. CHECK constraint name preserve (carry forward M2 schema).
- [ ] **ROLE-02** Phase 1: Thêm column `user_hubs.role` (nullable, default NULL) per-hub role override. Khi `user_hubs.role IS NOT NULL`, override `users.role` cho hub đó; NULL = inherit `users.role` global. Migration backward compat — toàn bộ row hiện tại `role=NULL`.
- [ ] **ROLE-03** Phase 1: Migration script seed — existing users với `users.role='admin'` giữ semantic super-admin global (`user_hubs.role=NULL` cho tất cả hub assignment). Audit trail INSERT row `action='migration.role_seed'` ghi nhận count + timestamp.
- [ ] **ROLE-04** Phase 1: Helper function `get_effective_role(user_id, hub_id)` → string. Logic: SELECT `user_hubs.role` WHERE user=user_id AND hub=hub_id; nếu NOT NULL → return; nếu NULL → return `users.role`. Unit test cover 4 case (super admin / hub_admin / viewer per-hub / no membership).

### DEP — Backend RBAC enforcement (5 REQ)

- [ ] **DEP-01** Phase 2: Dependency mới `require_hub_admin_for(hub_id)` ở `auth/dependencies.py`. Logic: verify JWT user có role `admin` (super) HOẶC `get_effective_role(user_id, hub_id) == 'hub_admin'`. Fail → 403 `HUB_ADMIN_REQUIRED` envelope. Test cover 5 case (super admin pass / hub_admin pass for own hub / hub_admin fail for other hub / viewer fail / no membership fail).
- [ ] **DEP-02** Phase 2: Refactor `GET /api/hubs` (`routers/hubs.py:73-77`) — bỏ branch `if user.role == "admin"` bypass; CHỈ super admin (role='admin' global, user_hubs.role NULL toàn bộ) trả ALL hub, mọi role khác (kể cả hub_admin) filter theo `user_hubs`. Test: hub_admin assigned `dmd` → chỉ thấy `dmd` trong list, KHÔNG thấy central.
- [ ] **DEP-03** Phase 2: Endpoint `routers/users.py` — `GET /api/users` (list) + `POST /api/users` (create) + `PATCH /api/users/:id/role` (change_role) + `DELETE /api/users/:id` (delete) check `require_hub_admin_for(target_hub_id)` cho hub_admin (hoặc super admin pass). Hub_admin của `dmd` KHÔNG list/create/edit user của hub `tdt`. Cross-hub admin operation (đổi user từ hub này sang hub khác) chỉ super admin.
- [ ] **DEP-04** Phase 2: Endpoint `routers/hubs.py` — `POST/PUT/PATCH /api/hubs` mutate hub registry chỉ super admin (hub_admin KHÔNG được tạo hub mới hoặc đổi metadata hub khác). `require_role("admin")` giữ nguyên cho 5 endpoint mutate.
- [ ] **DEP-05** Phase 2: Audit log tag actor scope — extend `AuditEntry` payload thêm field `actor_role` (admin / hub_admin) + `actor_hub_id` (NULL nếu super). Mọi audit emit từ user_service / hub_service / api_key_service include 2 field này. Forensic queries có thể filter by scope.

### FE — Frontend form refactor (4 REQ)

- [ ] **FE-01** Phase 3: `pages/UserManagement.tsx` form tạo user — radio group "Quyền" tách 3 option (KHÔNG còn "Admin Hub" mơ hồ): "Admin toàn hệ thống" (role='admin', cảnh báo bằng warning banner màu vàng), "Quản lý hub này" (role='hub_admin', áp scope chỉ hub được chọn), "Viewer" (role='viewer'). Description ngắn dưới mỗi option giải thích quyền.
- [ ] **FE-02** Phase 3: Hub switcher (sidebar Layout.tsx hoặc HubSwitcher component) — dùng `currentUser.role + currentUser.hub_ids` filter danh sách hubs. Nếu non-super-admin (role != 'admin'): ẩn hub `central` (special slug check); chỉ show hubs trong `currentUser.hub_ids`. Super admin thấy tất cả + chỉ định active.
- [ ] **FE-03** Phase 3: Edit modal "Quản lý hub & quyền" (handleOpenManageHub) — KHÔNG cho phép hub_admin assign "Admin toàn hệ thống" cho user khác (option disabled với tooltip "Cần Admin toàn hệ thống"). Hub_admin chỉ assign hub_admin/viewer cho hub được gán quyền.
- [ ] **FE-04** Phase 3: API types update — `frontend/src/services/api.ts` UserRole type thêm `'hub_admin'`; UserManagement state + form component update accept role mới. `mockData.ts` thêm sample hub_admin user cho dev test.

### MIGRATE — Migration + smoke E2E (2 REQ)

- [ ] **MIGRATE-01** Phase 4: Migration smoke test idempotent — re-run Alembic upgrade head 2 lần → KHÔNG fail (CHECK constraint already exists detect + skip); rollback Alembic downgrade -1 → restore CHECK constraint cũ 3 value; existing data preserve.
- [ ] **MIGRATE-02** Phase 4: Smoke E2E 4 scenario qua pytest httpx — (1) super admin `admin@medinet.vn` thấy ALL hub + CRUD all user; (2) hub_admin assigned `dmd` thấy CHỈ `dmd` + CRUD user trong `dmd`, GET central → 403; (3) hub_admin assigned `tdt` không thấy `dmd` hoặc central; (4) viewer chỉ list documents trong hub được gán. Audit log inspect actor_role + actor_hub_id chính xác. Closeout docs CLAUDE.md + STATE.md + ROADMAP.md mark v3.1 SHIPPED.

---

## Traceability (filled by roadmap)

100% REQ → phase coverage. Mỗi REQ map đúng 1 phase, không có REQ orphan.

| REQ-ID | Phase | Note |
|---|---|---|
| ROLE-01: role_enum + hub_admin | 1 | Alembic migration CHECK constraint idempotent |
| ROLE-02: user_hubs.role column | 1 | Per-hub override (NULL = inherit global) |
| ROLE-03: Migration script seed existing admins | 1 | Backward compat audit log |
| ROLE-04: get_effective_role helper | 1 | 4-case unit test |
| DEP-01: require_hub_admin_for dependency | 2 | 403 HUB_ADMIN_REQUIRED envelope |
| DEP-02: GET /api/hubs filter cả admin | 2 | Close routers/hubs.py:73-77 gap |
| DEP-03: users.py CRUD scope | 2 | Hub admin CHỈ user trong hub mình |
| DEP-04: hubs.py mutate super admin only | 2 | 5 endpoint giữ require_role("admin") |
| DEP-05: Audit actor.scope tag | 2 | actor_role + actor_hub_id payload |
| FE-01: UserManagement form 3 option | 3 | Warning banner Admin toàn hệ thống |
| FE-02: Hub switcher filter central | 3 | Non-super-admin ẩn central |
| FE-03: Edit modal disabled assign super | 3 | Hub_admin KHÔNG assign super_admin |
| FE-04: api.ts UserRole type extend | 3 | Type-safe FE-BE contract |
| MIGRATE-01: Migration idempotent + rollback | 4 | Re-run safety + downgrade -1 |
| MIGRATE-02: Smoke E2E 4 scenario + closeout | 4 | pytest httpx + audit verify + docs |

**Tổng:** 15 REQ-ID v1 → 4 phase. Coverage: 100% (4+5+4+2=15).

---

## Future Requirements (deferred v4.0+)

- **RBAC v4.0 advanced:** Per-resource permission (read/write/delete granular trên documents, api_keys, settings) thay vì role-based blanket. Defer v4.0 sau khi hub_admin proven stable.
- **OAuth role mapping:** SSO provider (Google Workspace, AzureAD) → role auto-mapping qua group claim. Defer v4.0.
- **Audit log search UI:** Frontend filter audit_logs theo actor_role / actor_hub_id (currently chỉ backend query). Defer v4.0.

## Out of Scope (v3.1)

- **Rename `users.role='admin'` → `'super_admin'`** — break v3.0 JWT/user_hubs/audit chain + cần migration full data. Giữ `admin` semantic = super-admin (D-V3.1-01 LOCKED).
- **Per-resource ACL** — out scope role-based; defer v4.0.
- **Multi-role assignment** (1 user 2 role trong cùng hub) — out scope; mỗi `user_hubs` row 1 role override.
- **Cross-hub data sync changes** — v3.1 KHÔNG đụng v3.0 outbox + worker pattern (D-V3-Phase4 LOCKED carry forward).
- **Frontend Tailwind cascade redesign** — v3.1 chỉ touch UserManagement.tsx + HubSwitcher component (giống Phase 5 v3.0 minimal scope R-V3-2 mitigation).
- **Visual regression smoke 4 hub × 11 trang** — carry forward defer ops handover (v3.0 deferred item).
- **Local embedding model (SEED-001)** — dormant v4.1.

---

*Defined: 2026-05-23 sau `/gsd-new-milestone v3.1`. Scope confirmed user 2026-05-23. Phase numbering reset về 1 (D-V3.1-04 + precedent D9/D-V3-05). Triple anti-pivot pattern KHÔNG cần thiết — v3.1 nhỏ ~4 phase. Next: `/gsd-discuss-phase 1` ROLE migration.*
