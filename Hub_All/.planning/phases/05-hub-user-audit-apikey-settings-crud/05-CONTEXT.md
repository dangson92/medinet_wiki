# Phase 5: Hub + User + Audit + APIKey + Settings CRUD - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning
**Source:** Inline discussion (thay cho /gsd-discuss-phase)

<domain>
## Phase Boundary

Phase 5 giao các REST endpoint quản trị: hub registry CRUD, user management CRUD, audit log query, API key management — tất cả với **hub isolation enforce ở repository layer**. Search/Ask/Ingest thuộc phase khác. Phase 5 chạy trên FastAPI `api/` (Go đã teardown 2026-05-14); contract endpoint lấy từ `frontend/src/services/api.ts` (D6 — frontend KHÔNG sửa).

Requirements: HUB-01, HUB-02, HUB-03, USER-01, USER-02, USER-03, AUX-01, AUX-02, AUX-03.

</domain>

<decisions>
## Implementation Decisions

### Sync Queue — GỠ KHỎI M2
- **D-01:** KHÔNG implement `/api/sync/*` endpoints. Tính năng sync queue (bulk import + approval workflow) loại khỏi M2 hoàn toàn.
- **D-02:** Hệ quả D6: trang `SyncQueue` React + 6 method trong `api.ts` (`getSyncBatches`, `getSyncBatch`, `submitSyncBatch`, `approveSyncPage`, `rejectSyncPage`, `getSyncStats`) sẽ vỡ khi gọi API. **Chấp nhận** — D6 exception có chủ đích. Dọn ở milestone frontend rewrite (v3.0). KHÔNG implement stub.

### RAG Config — endpoint đứng riêng
- **D-03:** `GET/PUT /api/rag-config` là endpoint **độc lập**, KHÔNG gộp vào Settings CRUD. Implementation thuộc Phase 7 (ASK-04 hot-swap embedding/LLM provider). Phase 5 KHÔNG touch rag-config — chỉ ghi nhận boundary để Settings CRUD không nuốt nhầm.

### Token Usage — fresh Python, không bám Go
- **D-04:** Token usage thiết kế lại hoàn toàn bằng Python — KHÔNG port kiến trúc Go 3-service (`usage_partition`/`usage_realtime`/`usage_rollup`). Thuộc Phase 7 (ASK-05). Phase 5 chỉ cần đảm bảo bảng `usage_events` (đã có từ schema Phase 2) không bị block bởi CRUD work.

### Hub schema — bỏ field di sản Go
- **D-05:** Python `HubAPI` DROP hẳn các field di sản thời Go multi-DB-per-hub + ChromaDB: `chroma_collection`, `db_host`, `db_port`, `db_name`, `db_user`. `HubAPI` Python CHỈ trả field M2 thật: `id`, `name`, `code`, `subdomain`, `description`, `status`, `created_at`, `updated_at`. (HUB-01 trong REQUIREMENTS.md đã chỉ định drop `chroma_collection` — quyết định này mở rộng drop cả cụm `db_*`.)
- **D-06:** Endpoint `POST /api/hubs/:id/test-connection` (frontend `testHubConnection`) — KHÔNG implement. M2 dùng 1 Postgres chung, không có per-hub DB để test. D6 exception, accepted — UI test-connection button sẽ lỗi.

### Contract source — frontend api.ts thắng REQUIREMENTS.md
- **D-07:** Khi REST verb/path trong `REQUIREMENTS.md` khác `frontend/src/services/api.ts`, **frontend thắng** (D6 — frontend không sửa được). Planner PHẢI đối chiếu từng endpoint với `frontend/src/services/api.ts`. Các discrepancy đã biết:
  - **Hub update:** frontend `PUT /api/hubs/:id`; REQUIREMENTS HUB-01 ghi `PATCH`. → dùng **PUT**.
  - **Hub status:** frontend `PATCH /api/hubs/:id/status` — endpoint riêng, giữ.
  - **User update:** frontend tách `PUT /api/users/:id` (profile fields) + `PATCH /api/users/:id/role` + `PATCH /api/users/:id/status`; REQUIREMENTS USER-01 gộp `PATCH /api/users/:id`. → theo **frontend** (3 endpoint tách).
  - **Profile:** frontend `GET /api/profile` + `PUT /api/profile` + `POST /api/profile/password`; REQUIREMENTS USER-03 ghi `/api/users/:id/profile` + `/api/users/me/profile`. → dùng **`/api/profile`** của frontend.
  - **APIKey:** frontend `GET/POST /api/api-keys` + `GET/PUT /api/api-keys/:id` + `POST /api/api-keys/:id/revoke`; REQUIREMENTS AUX-02 ghi `GET/POST/DELETE`. → theo **frontend** (có PUT update + POST revoke; revoke = soft, không DELETE cứng).

### Claude's Discretion
- Bảng `settings` (key-value app config) — schema + có cần endpoint riêng không. ROADMAP Phase 5 title nhắc "Settings" nhưng không có REQ-ID SETTINGS-NN. Giữ tối thiểu, chỉ thêm endpoint nếu frontend `api.ts` thực sự gọi.
- Pattern hub isolation ở repository layer (cách inject `WHERE hub_id = $1` từ user's `hub_assignments`).
- Backend store cho slowapi rate limit (in-memory vs Redis).
- Chi tiết flush của audit logger asyncio.Queue (batch 2s/128 theo AUX-01).
- Soft-delete vs hard-delete cho hub/user DELETE.

</decisions>

<specifics>
## Specific Ideas

- **Hub isolation là điều kiện ship** (EXIT criteria E4): integration test mandatory cho mỗi mutation endpoint — Editor of Hub A KHÔNG được PATCH/DELETE resource của Hub B kể cả khi truyền explicit `hub_id` trong payload. Test fail = critical bug, không ship.
- Response envelope `{success, data, error, meta}` shape-identical mọi endpoint (kể cả error 403/404/429).
- Audit log phải có entry `action='security.hub_isolation_violation'` khi reject cross-hub mutation.
- USER-02 reset-password: M2 chỉ log token ra console (defer email send v4.0).

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope
- `.planning/ROADMAP.md` §"Phase 5: Hub + User + Audit + APIKey + Settings CRUD" — goal + 5 success criteria
- `.planning/REQUIREMENTS.md` §HUB §USER §"AUDIT + APIKEY + AUX" — 9 REQ-ID (HUB-01..03, USER-01..03, AUX-01..03)

### Contract reference (D6 — SOURCE OF TRUTH cho endpoint shape)
- `Hub_All/frontend/src/services/api.ts` — URL path + request/response types frontend mong đợi. Khi mâu thuẫn với REQUIREMENTS.md → file này thắng (xem D-07).

### Project constraints
- `.planning/PROJECT.md` — D6 (frontend không sửa), R3/E4 (hub isolation = EXIT criteria), response envelope
- `.planning/CONVENTIONS.md` — layered architecture (router → service → repository → model), middleware order, test strategy pytest + testcontainers
- Phase 3 artifacts (`.planning/phases/03-auth-port-rbac-response-envelope/`) — auth dependency `get_current_user` + `require_role`, envelope handler, đã ship; Phase 5 endpoint dùng lại
- Go source cũ (nếu cần tra shape): git tag `m1-go-archived` — `git show m1-go-archived:Hub_All/backend/internal/...`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/auth/dependencies.py` — `get_current_user`, `require_role("admin")` đã ship Phase 3; mọi endpoint admin-only Phase 5 dùng lại
- `app/main.py` envelope exception handler — error 401/403/404/429 render `{success, data, error, meta}` đúng
- `app/db/` SQLAlchemy async engine + session factory (Phase 2)
- `app/models/` — models cho `hubs`, `users`, `user_hubs`, `audit_logs`, `api_keys`, `settings` đã tạo Phase 2

### Established Patterns
- Layered: router → service → repository → model (CONVENTIONS.md)
- Test: pytest + httpx AsyncClient + testcontainers Postgres + Redis; marker `@pytest.mark.critical` cho CI gate HARD-03

### Integration Points
- Endpoint mount vào `app/main.py::create_app()` qua `include_router`
- Hub isolation enforce ở repository layer dựa `user.hub_assignments` (từ `user_hubs` join table)

</code_context>

<deferred>
## Deferred Ideas

- **Sync Queue** (D-01/D-02) — toàn bộ feature loại khỏi M2; revisit ở milestone frontend rewrite v3.0
- **rag-config endpoint** — Phase 7 (ASK-04), Phase 5 chỉ giữ boundary
- **Token usage endpoint + aggregation** — Phase 7 (ASK-05), fresh Python design
- **Email send cho password reset** — v4.0 (USER-02 chỉ log token M2)
- **Avatar upload** — v4.0 (USER-03 chỉ full_name M2)
- **Dọn dead code frontend** (SyncQueue page, testHubConnection, hub legacy fields) — milestone frontend rewrite v3.0

</deferred>

---

*Phase: 05-hub-user-audit-apikey-settings-crud*
*Context gathered: 2026-05-15 (inline discussion)*
