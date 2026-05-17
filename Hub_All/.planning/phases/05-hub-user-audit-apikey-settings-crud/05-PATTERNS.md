# Phase 5: Hub + User + Audit + APIKey + Settings CRUD - Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 22 (16 new · 1 modified · 5 test) — inferred từ 9 REQ-ID (CONTEXT.md không có file list tường minh)
**Analogs found:** 22 / 22 (codebase Phase 3/4 cung cấp analog mạnh cho mọi layer; 3 file kết hợp nhiều pattern)

> Toàn bộ source nằm dưới `Hub_All/api/`. Đường dẫn trong doc này tương đối với repo root.
> Phase 5 KHÔNG có repository layer riêng trong codebase hiện tại — Phase 4 dùng pattern **service-chứa-SQL** (`DocumentService` raw SQL `text()` trên `AsyncSession`). CONVENTIONS.md nêu "router → service → repository → model" nhưng codebase thực tế gộp repository vào service. **Quyết định mapping:** Phase 5 nên tách 1 module `app/repositories/hub_scope.py` mỏng CHỈ cho hub-isolation query builder (HUB-02 — chỗ duy nhất cần repository riêng để test cô lập); phần CRUD còn lại theo pattern service-chứa-SQL của Phase 4. Planner xác nhận với user nếu muốn full repository layer.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `api/app/routers/hubs.py` | router | CRUD / request-response | `api/app/routers/documents.py` | exact |
| `api/app/routers/users.py` | router | CRUD / request-response | `api/app/routers/documents.py` | exact |
| `api/app/routers/audit_logs.py` | router | request-response (read-only) | `api/app/routers/documents.py` (`list_documents`) | role-match |
| `api/app/routers/api_keys.py` | router | CRUD / request-response | `api/app/routers/documents.py` | exact |
| `api/app/routers/profile.py` | router | request-response | `api/app/auth/router.py` (`me`) | exact |
| `api/app/services/hub_service.py` | service | CRUD | `api/app/services/documents_service.py` | exact |
| `api/app/services/user_service.py` | service | CRUD | `api/app/services/documents_service.py` | exact |
| `api/app/services/audit_service.py` | service | event-driven / batch (asyncio.Queue) | `api/app/services/watchdog.py` + `documents_service.delete` (audit INSERT) | role-match |
| `api/app/services/apikey_service.py` | service | CRUD + transform (AES-GCM) | `api/app/services/documents_service.py` | role-match |
| `api/app/repositories/hub_scope.py` | repository | transform (WHERE-clause builder) | `documents_service.list` (dynamic WHERE builder, lines 244-260) | role-match |
| `api/app/schemas/hubs.py` | schema | — | `api/app/schemas/documents.py` | exact |
| `api/app/schemas/users.py` | schema | — | `api/app/schemas/documents.py` + `api/app/auth/schemas.py` | exact |
| `api/app/schemas/audit_logs.py` | schema | — | `api/app/schemas/documents.py` | exact |
| `api/app/schemas/api_keys.py` | schema | — | `api/app/schemas/documents.py` | exact |
| `api/app/middleware/rate_limit.py` | middleware | request-response | `api/app/middleware/request_id.py` / `security_headers.py` | role-match |
| `api/app/main.py` (modified) | config | — | self (`include_router` + lifespan blocks) | exact |
| `api/tests/integration/test_hub_isolation.py` | test | — | `api/tests/integration/test_documents_list_delete.py` | exact |
| `api/tests/integration/test_hubs_crud.py` | test | — | `api/tests/integration/test_documents_list_delete.py` | exact |
| `api/tests/integration/test_users_crud.py` | test | — | `api/tests/integration/test_documents_list_delete.py` | exact |
| `api/tests/integration/test_api_keys.py` | test | — | `api/tests/integration/test_documents_list_delete.py` | exact |
| `api/tests/integration/test_audit_logs.py` | test | — | `api/tests/integration/test_documents_list_delete.py` | exact |

> Note: `api/app/routers/__init__.py` cũng cần sửa (re-export router mới) — gộp vào "modified" cùng `main.py`. `app/services/__init__.py` / `app/schemas/__init__.py` re-export theo nhu cầu.

---

## Pattern Assignments

### `api/app/routers/hubs.py` (router, CRUD) — HUB-01, HUB-03

**Analog:** `api/app/routers/documents.py`

**Imports pattern** (documents.py lines 26-54) — copy block, swap service/schema:
```python
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.db.session import get_session
from app.models.auth import User
from app.pkg import response as resp
from app.services.hub_service import HubService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hubs", tags=["hubs"])
```

**Service factory pattern** (documents.py lines 62-65) — every router file repeats this:
```python
def get_hub_service(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> HubService:
    return HubService(db=db)
```

**Auth pattern** — per-endpoint `Depends`, NOT a router-level guard:
- `GET /api/hubs`, `GET /api/hubs/:id`, `GET /api/hubs/:id/stats` → `user: User = Depends(get_current_user)`
- `POST /api/hubs`, `PUT /api/hubs/:id`, `PATCH /api/hubs/:id/status`, `DELETE /api/hubs/:id` → `user: User = Depends(require_role("admin"))` (documents.py line 74, 191)

**Core CRUD handler pattern** (documents.py lines 157-184 `get_by_id`) — UUID validate → service → envelope:
```python
@router.get("/{hub_id}")
async def get_hub(
    hub_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
    service: HubService = Depends(get_hub_service),  # noqa: B008
) -> JSONResponse:
    try:
        hub_uuid = UUID(hub_id)
    except ValueError:
        return resp.bad_request(message=f"hub_id không hợp lệ: {hub_id!r}", code="INVALID_HUB_ID")
    hub = await service.get(hub_uuid)
    if hub is None:
        return resp.not_found(message=f"Hub {hub_id} không tồn tại", code="NOT_FOUND")
    return resp.ok(data=hub.model_dump(mode="json"))
```

**Pagination pattern** (documents.py lines 228-292 `list_documents`) — query params + cap `per_page ≤ 100`:
```python
@router.get("")
async def list_hubs(
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(get_current_user),  # noqa: B008
    service: HubService = Depends(get_hub_service),  # noqa: B008
) -> JSONResponse:
    capped_per_page = max(1, min(per_page, 100))  # HUB-01 cap (T-04-05-01 mitigation)
    capped_page = max(1, page)
    items, total = await service.list(page=capped_page, per_page=capped_per_page)
    return resp.paginated(
        items=[i.model_dump(mode="json") for i in items],
        page=capped_page, per_page=capped_per_page, total=total,
    )
```

**DELETE 204 pattern** (documents.py lines 187-225) — `status_code=status.HTTP_204_NO_CONTENT` + `Response(status_code=204)`, pass `request_id` từ `request.state` vào service cho audit log.

**D-05 schema note:** `HubResponse` schema DROP `chroma_collection`, `db_host`, `db_port`, `db_name`, `db_user` (frontend `HubAPI` vẫn khai báo chúng — chấp nhận D6 drift). Trả ONLY: `id, name, code, subdomain, description, status, created_at, updated_at`. Lưu ý: model `Hub` (`api/app/models/hub.py`) hiện dùng cột `slug`/`is_active` — schema response phải map `slug→code` hoặc planner xác nhận field naming với frontend `HubAPI` (`code`, `subdomain`, `status`).

**D-07 contract note:** Hub update verb = **PUT** (frontend thắng REQUIREMENTS `PATCH`). `PATCH /api/hubs/:id/status` là endpoint riêng. `POST /api/hubs/:id/test-connection` — KHÔNG implement (D-06).

---

### `api/app/routers/users.py` (router, CRUD) — USER-01, USER-02

**Analog:** `api/app/routers/documents.py` (structure) + `api/app/auth/router.py` (error→envelope mapping)

Cùng imports/factory/auth/pagination pattern như `hubs.py`. Khác biệt:
- Mọi endpoint `Depends(require_role("admin"))` — USER-01 là admin-only CRUD.
- **D-07 contract:** 3 endpoint update tách rời (frontend thắng REQUIREMENTS' single `PATCH /api/users/:id`):
  - `PUT /api/users/:id` — profile fields
  - `PATCH /api/users/:id/role` — body `{hub_id, role}`
  - `PATCH /api/users/:id/status` — body `{status}`
- `POST /api/users/:id/reset-password` (USER-02) — sinh token 1-time TTL 1h, **log token ra console only** (defer email v4.0). Dùng `logger.info` (structlog) kèm `request_id` — xem CONVENTIONS §5.

**Service-error → envelope mapping pattern** (auth/router.py lines 39-53) — copy idiom cho domain error như duplicate email:
```python
def _service_error_to_response(e: ServiceError) -> JSONResponse:
    return resp.conflict(message=e.message, code=e.code)  # or bad_request per code

@router.post("")
async def create_user(req: CreateUserRequest, service=Depends(get_user_service)):
    try:
        result = await service.create(req)
    except ServiceError as e:
        return _service_error_to_response(e)
    return resp.created(data=result.model_dump())
```

---

### `api/app/routers/audit_logs.py` (router, read-only) — AUX-01

**Analog:** `api/app/routers/documents.py::list_documents` (lines 228-292)

Single endpoint `GET /api/audit-logs` — `Depends(require_role("admin"))`. Copy nguyên pattern query-param + dynamic-filter + `resp.paginated`. Filter params: `user_id`, `action`, `hub_id`, `date_from`, `date_to`. Validate optional UUID y hệt documents.py lines 254-272.

---

### `api/app/routers/api_keys.py` (router, CRUD) — AUX-02

**Analog:** `api/app/routers/documents.py`

Endpoints (D-07 — frontend thắng): `GET/POST /api/api-keys`, `GET/PUT /api/api-keys/:id`, `POST /api/api-keys/:id/revoke` (revoke = soft, set `is_active=FALSE`; KHÔNG hard DELETE). Mọi endpoint `Depends(require_role("admin"))`.

**Plaintext-once pattern:** `POST` trả `APIKeyWithPlaintextAPI` (plaintext key hiện ĐÚNG 1 LẦN trong create response); `GET` về sau chỉ trả `key_prefix`. Service sinh key, encrypt AES-GCM trước INSERT (xem apikey_service bên dưới).

---

### `api/app/routers/profile.py` (router, request-response) — USER-03

**Analog:** `api/app/auth/router.py` (`me` handler, lines 104-113)

**D-07 contract:** `GET /api/profile` + `PUT /api/profile` + `POST /api/profile/password` (frontend thắng REQUIREMENTS' `/api/users/:id/profile`). Auth = `Depends(get_current_user)` — self-service, `user` được inject CHÍNH LÀ target (không có `:id` param). `POST /api/profile/password` body `{old_password, new_password}` — verify old qua `app.auth.password.verify_password`, hash new qua `app.auth.password.hash_password`.

---

### `api/app/services/hub_service.py` (service, CRUD) — HUB-01, HUB-03

**Analog:** `api/app/services/documents_service.py`

**Class skeleton pattern** (documents_service.py lines 60-69):
```python
class HubService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
```

**INSERT pattern** (documents_service.py lines 154-172) — raw SQL `text()`, `NOW()` server-side timestamps (BLOCKER #4 — KHÔNG Python `utcnow`), `gen_random_uuid()` hoặc `uuid4()` cho id:
```python
await self.db.execute(
    text(
        "INSERT INTO hubs (id, slug, name, description, is_active, created_at) "
        "VALUES (gen_random_uuid(), :slug, :name, :desc, TRUE, NOW()) RETURNING id"
    ),
    {"slug": slug, "name": name, "desc": description},
)
# get_session() auto-commit khi success (db/session.py lines 80-86)
```

**SELECT single pattern** (documents_service.py lines 189-219) — `.fetchone()`, return `None` nếu missing, map row tuple → Pydantic schema.

**list() với dynamic WHERE + COUNT + LIMIT/OFFSET pattern** (documents_service.py lines 221-297) — pagination query chuẩn. Copy structure lines 244-284: build `where_clauses: list[str]` + `params: dict`, `COUNT(*)` rồi `ORDER BY created_at DESC LIMIT :limit OFFSET :offset`, return `tuple[list[Item], int]`.

**HUB-03 stats** — single SQL aggregate (KHÔNG ChromaDB — D-05):
```python
row = (await self.db.execute(text(
    "SELECT "
    "(SELECT COUNT(*) FROM documents WHERE hub_id=:h) AS doc_count, "
    "(SELECT COUNT(*) FROM chunks WHERE hub_id=:h) AS chunk_count, "
    "(SELECT COUNT(*) FROM user_hubs WHERE hub_id=:h) AS user_count"
), {"h": str(hub_id)})).fetchone()
```

---

### `api/app/services/user_service.py` (service, CRUD) — USER-01, USER-02

**Analog:** `api/app/services/documents_service.py` + `api/app/auth/service.py` (password helpers)

Cùng raw-SQL `text()` pattern. Thêm:
- **Duplicate email** — catch SQLAlchemy `IntegrityError` trên unique constraint `users.email` → raise domain `ServiceError(code="EMAIL_EXISTS")`.
- **Password hash on create** — `from app.auth.password import hash_password` (main.py lifespan line 142 chứng minh API).
- **hub_assignments** — ghi vào join table `user_hubs` (model `api/app/models/auth.py::UserHub`, lines 80-103, composite PK `(user_id, hub_id)`). Khi create user với `hub_assignments[]`, INSERT N row vào `user_hubs`.
- **USER-02 reset token** — `secrets.token_urlsafe(32)`, lưu hash vào Redis TTL 3600 (`get_redis` qua `app.state.redis`), `logger.info("password_reset_token_issued", request_id=..., user_id=...)` — token log ra console (M2 only).

---

### `api/app/services/audit_service.py` (service, event-driven / batch) — AUX-01

**Analog:** `api/app/services/watchdog.py` (asyncio background-loop lifecycle) + `documents_service.delete` audit INSERT (lines 334-349)

File duy nhất **không có analog đơn** — kết hợp 2 pattern có sẵn:

1. **asyncio.Queue batch-flush loop** — model theo `watchdog.py::watchdog_loop` (long-lived `asyncio` task start trong lifespan). Pattern: module-level `_queue: asyncio.Queue`, coroutine `audit_flush_loop()` drain queue mỗi 2s HOẶC khi ≥128 item (AUX-01 spec: "batch 2s/128"), batch-INSERT qua `engine.begin()` (dùng `get_engine()` như `trigger_cocoindex_update` documents_service.py lines 429-430).

2. **Audit row INSERT shape** đã proven trong `documents_service.delete` (lines 336-349):
```python
await conn.execute(
    text(
        "INSERT INTO audit_logs "
        "(id, user_id, action, target_type, target_id, hub_id, payload, request_id, created_at) "
        "VALUES (gen_random_uuid(), :user_id, :action, :target_type, "
        ":target_id, :hub_id, :payload, :request_id, NOW())"
    ),
    {...},
)
```

**Lifespan wiring** — model theo `main.py` watchdog block (lines 164-179 start, 187-195 cancel-on-shutdown):
```python
# startup
app.state.audit_task = asyncio.create_task(audit_flush_loop())
# shutdown — cancel TRƯỚC dispose_engine, await CancelledError, final drain
app.state.audit_task.cancel()
```

**Action enum** (AUX-01): `auth.login`, `auth.refresh`, `document.upload`, `document.delete`, `rag-config.update`, `hub.create`, `hub.update`, `user.create`. **+ `security.hub_isolation_violation`** (CONTEXT specifics — emit khi reject cross-hub mutation).

**Model `audit_logs`:** `api/app/models/audit.py` — append-only, có `payload JSONB`, index trên `created_at`, `(user_id, created_at)`, `(hub_id, created_at)`. Dùng các index này khi build filter `GET /api/audit-logs`.

---

### `api/app/services/apikey_service.py` (service, CRUD + AES-GCM transform) — AUX-02

**Analog:** `api/app/services/documents_service.py` (CRUD shape) + `api/app/auth/jwt.py` (key-material handling idiom)

Raw-SQL `text()` CRUD. AES-GCM specifics (không có analog — schema M2-new, không có legacy data):
- `AES_KEY` từ env qua `pydantic-settings` (`app/config.py` `Settings`) — cùng pattern `JWT_PRIVATE_KEY_PATH`.
- Sinh key → `key_prefix` = 8 ký tự đầu (UX, lưu plaintext theo model `api_keys.key_prefix`), `key_hash` = AES-GCM ciphertext lưu `api_keys.key_hash` (model `api/app/models/settings.py::ApiKey`, lines 54-81).
- Revoke = `UPDATE api_keys SET is_active=FALSE WHERE id=:id` (soft — D-07).

---

### `api/app/repositories/hub_scope.py` (repository, WHERE-builder) — HUB-02 (EXIT criteria E4)

**Analog:** `documents_service.py::list` dynamic-WHERE builder (lines 244-260)

Đây là **hub-isolation enforcement point** — chỗ duy nhất CONTEXT yêu cầu repository-layer abstraction. Là helper mỏng, không phải class hierarchy.

**Core pattern** — function nhận `User` đã auth, trả về SQL fragment + params ràng buộc mọi query/mutation vào hub user được gán:
```python
async def get_user_hub_ids(db: AsyncSession, user: User) -> set[UUID]:
    """Load hub_id set từ user_hubs join — HUB-02 source of truth."""
    rows = (await db.execute(
        text("SELECT hub_id FROM user_hubs WHERE user_id = :uid"),
        {"uid": str(user.id)},
    )).fetchall()
    return {r[0] for r in rows}

def assert_hub_access(user: User, target_hub_id: UUID, user_hub_ids: set[UUID]) -> None:
    """Raise 403 nếu target hub không thuộc user assignment — BỎ QUA payload hub_id override.
    admin bypass (cross-hub allowed — documents.py line 203 precedent T-04-05-03)."""
    if user.role == "admin":
        return
    if target_hub_id not in user_hub_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Hub không thuộc quyền truy cập"},
        )
```

**CRITICAL behavior** (CONTEXT specifics + E4): với mutation `PATCH/DELETE`, `hub_id` đọc từ **row resource trong DB** (`SELECT hub_id FROM ... WHERE id=:id`), KHÔNG BAO GIỜ từ request payload. Editor của Hub A gửi `{"hub_id": "hub_b"}` vẫn phải bị reject. Khi reject, emit audit `action='security.hub_isolation_violation'` qua `audit_service`.

`require_role` (auth/dependencies.py lines 145-188) lo role gate; `hub_scope` lo hub gate trực giao. Cả hai apply cho mutation endpoint.

---

### Schema files `api/app/schemas/{hubs,users,audit_logs,api_keys}.py`

**Analog:** `api/app/schemas/documents.py` + `api/app/auth/schemas.py`

Pydantic v2 `BaseModel`, `from __future__ import annotations`, `Literal` cho enum, `Field(min_length=..., max_length=...)` cho validation (auth/schemas.py lines 23-24). Mỗi domain 1 file. Pattern per domain: `XxxResponse` (GET payload), `XxxListItem` (compact list item), `CreateXxxRequest`, `UpdateXxxRequest`. UUID field type `str` trong response schema (documents.py line 39 precedent), `datetime` cho timestamp.

**D-05:** `HubResponse` KHÔNG include `chroma_collection`/`db_*`. **D-07:** match field name với interface frontend `HubAPI`/`UserAPI`/`APIKeyAPI`/`AuditLogAPI` trong `frontend/src/services/api.ts` (lines 373-615) ở các field M2 thật trùng nhau.

---

### `api/app/middleware/rate_limit.py` (middleware) — AUX-03

**Analog:** `api/app/middleware/request_id.py` (BaseHTTPMiddleware skeleton, CONVENTIONS §5 lines 286-296) + CONVENTIONS §4

slowapi-based. AUX-03 limits: 100/min/user trên search+ask, 30/min/user trên upload, KHÔNG limit auth+`/me`. Per-user key từ JWT `sub` claim. **Wiring (main.py):** add làm middleware **innermost** — `add_middleware` ĐẦU TIÊN theo onion model CONVENTIONS §4 (main.py lines 251-260 cho thấy order hiện tại; rate-limit slot trước CORS). Reject → `resp.too_many_requests()` (response.py lines 139-144 — envelope `429 RATE_LIMIT_EXCEEDED` đã có sẵn).

CONTEXT discretion: backend store in-memory vs Redis — Redis khuyến nghị (Redis client đã ở `app.state.redis`, lifespan main.py lines 83-91).

---

### `api/app/main.py` (modified) — router registration + audit lifespan + rate-limit middleware

**Analog:** self — `include_router` block hiện có (lines 262-270) + watchdog lifespan block (lines 164-179 start, 187-195 cancel).

Thêm:
```python
from app.routers import (
    hubs_router, users_router, audit_logs_router, api_keys_router, profile_router,
)
app.include_router(hubs_router)
app.include_router(users_router)
app.include_router(audit_logs_router)
app.include_router(api_keys_router)
app.include_router(profile_router)
```
Plus: start `audit_flush_loop` task trong lifespan startup, cancel trong shutdown (copy shape watchdog block). Add `RateLimitMiddleware` theo onion order. **`app/routers/__init__.py`** phải re-export router mới (pattern hiện tại: `documents_router` export ở đó).

---

### Test files `api/tests/integration/test_*.py`

**Analog:** `api/tests/integration/test_documents_list_delete.py`

**Fixture reuse** — KHÔNG redeclare; `tests/integration/conftest.py` cung cấp: `postgres_container`, `redis_container`, `app_with_auth`, `auth_client`, `admin_user`/`editor_user`/`viewer_user`, `admin_token`/`editor_token`/`viewer_token`. testcontainers `pgvector/pgvector:pg16` + `redis:7-alpine`.

**Test markers** (test_documents_list_delete.py lines 103-105): `@pytest.mark.critical` + `@pytest.mark.integration` + `@pytest.mark.asyncio`. Test hub-isolation PHẢI `@pytest.mark.critical` (CI gate `pytest -m critical`, HARD-03).

**Local helper pattern** — helper kiểu `_create_hub`, `_insert_user` dùng `get_engine()` + `engine.begin()` raw SQL (test_documents_list_delete.py lines 53-68, conftest lines 235-261).

**Envelope assertion pattern** (test_documents_list_delete.py lines 287-290):
```python
assert r.status_code == 403, r.text
body = r.json()
assert body["success"] is False
assert body["error"]["code"] == "FORBIDDEN"
```

**`test_hub_isolation.py` mandatory cases** (E4 EXIT criteria — CONVENTIONS §1 DO block, CONTEXT specifics):
- Editor của Hub A → `PUT /api/hubs/:hub_b_id` hoặc `DELETE` resource Hub B → 403, KỂ CẢ khi payload có explicit `{"hub_id": "hub_a"}`.
- Editor của Hub A → `PATCH/DELETE` document của Hub B → 403.
- Assert có row `audit_logs` với `action='security.hub_isolation_violation'` được ghi khi reject.
- Admin → cross-hub mutation → allowed (200/204).

---

## Shared Patterns

### Authentication & Authorization
**Source:** `api/app/auth/dependencies.py` (`get_current_user` lines 82-142, `require_role` lines 145-188)
**Apply to:** mọi endpoint router Phase 5.
- Read endpoint → `user: User = Depends(get_current_user)`
- Mutation/admin endpoint → `user: User = Depends(require_role("admin"))`
- `require_role()` raise `ValueError` nếu gọi không argument (security gate) — luôn pass explicit roles.

### Response Envelope
**Source:** `api/app/pkg/response.py` (toàn file — 12 helper)
**Apply to:** mọi router handler — KHÔNG BAO GIỜ return Pydantic model raw (D6 frontend contract).
```python
resp.ok(data=...)          # 200
resp.created(data=...)     # 201
resp.paginated(items=, page=, per_page=, total=)  # 200 list
resp.bad_request(message=, code=)     # 400
resp.forbidden(message=, code=)       # 403
resp.not_found(message=, code=)       # 404
resp.conflict(message=, code=)        # 409
resp.too_many_requests()              # 429 (AUX-03)
```
Handler return `JSONResponse`; `HTTPException` raise bởi dependency được map về cùng envelope bởi `main.py::http_exception_handler` (lines 280-304). Error code là `UPPER_SNAKE_CASE` (Go-compat, frontend switch trên `error.code`).

### Service-layer DB Access
**Source:** `api/app/services/documents_service.py`
**Apply to:** mọi service Phase 5.
- Service nhận `db: AsyncSession` ở `__init__`; router build qua factory `get_xxx_service` `Depends(get_session)`.
- Raw SQL qua `sqlalchemy.text()` với bound param (`:name`) — asyncpg parametrization, không f-string SQL injection.
- Timestamps: SQL `NOW()` server-side. IDs: `gen_random_uuid()` hoặc `uuid4()`. KHÔNG dùng deprecated Python `datetime.utcnow()` (BLOCKER #4).
- `get_session()` auto-commit khi success / rollback khi exception (`db/session.py` lines 80-86). Cho background task (audit flush) dùng `get_engine()` + `async with engine.begin()`.

### Pagination
**Source:** `documents_service.py::list` (lines 221-297) + `documents.py::list_documents` (lines 274-291)
**Apply to:** `GET /api/hubs`, `GET /api/users`, `GET /api/audit-logs`, `GET /api/api-keys`.
- Router caps: `capped_per_page = max(1, min(per_page, 100))`, `capped_page = max(1, page)`.
- Service trả `tuple[list[Item], int]` (items, total); router gọi `resp.paginated(...)`.
- Dynamic filter: build `where_clauses: list[str]` + `params: dict`, `COUNT(*)` rồi `LIMIT/OFFSET ORDER BY created_at DESC`.

### Audit Logging on Mutations
**Source:** `documents_service.py::delete` (audit INSERT lines 334-349)
**Apply to:** mọi mutation Phase 5 (`hub.create`, `hub.update`, `user.create`, ...) + `security.hub_isolation_violation`.
Phase 4 INSERT synchronous trong request transaction. Phase 5 AUX-01 nâng lên `audit_service` asyncio.Queue batch flush — service enqueue audit record thay vì INSERT inline. Pass `request_id` (từ `request.state.request_id`, set bởi `RequestIdMiddleware`).

### Models (đã tồn tại — Phase 2)
**Source:** `api/app/models/` — `hub.py` (`Hub`), `auth.py` (`User`, `UserHub`, `RefreshToken`), `audit.py` (`AuditLog`), `settings.py` (`ApiKey`, `Setting`).
Tất cả đã register trong `models/__init__.py`. Mixin `UUIDMixin`/`TimestampMixin` (`db/mixins.py`). Phase 5 KHÔNG cần đổi model — schema hoàn chỉnh. Model `Hub` đã không có `chroma_collection`/`db_*` (D-05 thoả ở DB level; việc drop enforce ở *schema response*, không phải model).

---

## No Analog Found

Không file nào hoàn toàn không có analog. 3 file kết hợp nhiều pattern thay vì copy một analog:

| File | Role | Data Flow | Note |
|------|------|-----------|------|
| `api/app/services/audit_service.py` | service | event-driven / batch | Không có asyncio.Queue batcher sẵn. Kết hợp `watchdog.py` loop lifecycle + `documents_service.delete` audit INSERT shape. Planner: design queue/flush theo AUX-01 (2s / 128). |
| `api/app/services/apikey_service.py` (phần AES-GCM) | service | transform | CRUD shape từ `documents_service.py`; AES-GCM encrypt không có analog (M2-new, không có legacy ciphertext cần tương thích). |
| `api/app/repositories/hub_scope.py` | repository | transform | Chưa có thư mục `repositories/`. CONVENTIONS nêu repository layer nhưng Phase 4 gộp vào service. Phase 5 introduce module mỏng chỉ cho HUB-02 isolation; planner xác nhận với user có retro-fit full repository layer hay giữ service-with-SQL chỗ khác. |

---

## Metadata

**Analog search scope:** `Hub_All/api/app/{routers,services,auth,models,middleware,pkg,db,schemas}/`, `Hub_All/api/tests/integration/`, `Hub_All/frontend/src/services/api.ts`
**Files scanned:** 18 source file đọc đầy đủ (routers/documents.py, services/documents_service.py, auth/router.py, auth/dependencies.py, auth/schemas.py, pkg/response.py, schemas/documents.py, main.py, models/{hub,auth,audit,settings,__init__}.py, db/{session,mixins}.py, tests/integration/{conftest,test_documents_list_delete}.py) + frontend api.ts (lines 88-323, 373-615)
**Pattern extraction date:** 2026-05-15
**Key constraints folded in:** D-05 (drop hub legacy fields), D-06 (no test-connection), D-07 (frontend api.ts thắng verb/path), E4 (hub isolation = EXIT criteria → critical tests), CONVENTIONS §4 (middleware onion order), BLOCKER #4 (SQL `NOW()` không Python `utcnow`).
