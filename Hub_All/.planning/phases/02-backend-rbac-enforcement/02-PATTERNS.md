---
phase: 02-backend-rbac-enforcement
mapped: 2026-05-24
status: Ready for planning
source: 02-CONTEXT.md §"Specific Implementation Hints" (10 file thay đổi) + 6 D-V3.1-Phase2-A..F LOCKED
language: Vietnamese có dấu (REQ-ID + đường dẫn file + tên hàm giữ tiếng Anh)
---

# Phase 2: Backend RBAC enforcement — Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 10 (1 dependency mới + 2 router refactor + 3 service refactor + 4 test mới)
**Analogs found:** 10 / 10 (100% — toàn bộ pattern carry forward từ Phase 1 v3.1 + Phase 3 SSO v3.0 + Plan 05 M2)

## File Classification

| File | Loại file | Role | Data flow | Analog gần nhất | Match quality |
|------|-----------|------|-----------|-----------------|---------------|
| `api/app/auth/dependencies.py` | **modify (extend)** | dependency factory + inline validator | request → DB lookup → 403/return User | `require_role` (line 290-333) + `require_internal_auth` (line 251-287) + `get_current_user_for_hub_access` (line 365-431) | **exact** |
| `api/app/routers/hubs.py` | **modify (verify only — có thể KHÔNG code change)** | router refactor GET /api/hubs | HTTP request → admin branch / hub_admin else branch → service.list_for_hubs | `list_hubs` handler (line 54-91) ĐÃ có pattern `if user.role == "admin"` else branch ✓ | **exact (đã đúng)** |
| `api/app/routers/users.py` | **modify (5 endpoint refactor scope)** | router CRUD + inline scope check | HTTP body → assert_hub_admin_for inline → service call → audit enqueue | `routers/hubs.py:73-85` branch admin/non-admin + `routers/users.py:90-108` create handler pattern | **role-match (refactor inline)** |
| `api/app/services/audit_service.py` | **modify (add helper)** | utility helper build payload | dict input → nest actor metadata → return dict | `AuditEntry` dataclass (line 51-65) + `enqueue_audit` (line 85-94) | **exact (extend existing)** |
| `api/app/services/user_service.py` | **modify (2 callsite enqueue_audit)** | service refactor signature + payload nest | service args (actor_role + actor_hub_id) → audit payload nest → enqueue | `create()` line 129-202 + `delete()` line 408-490 (callsite 182-192 + 465-478) | **exact** |
| `api/app/services/hub_service.py` | **modify (3 callsite enqueue_audit)** | service refactor signature + payload nest | service args (actor_role + actor_hub_id) → audit payload nest → enqueue | `create()` line 68-129 + `update()` line 210-258 + `update_status()` line 260-302 (callsite 113-122 + 246-256 + 285-295) | **exact** |
| `api/app/services/api_key_service.py` | **review (verify KHÔNG enqueue_audit)** | service (no-op confirm) | — | `ApiKeyService` line 91-460 — verify `enqueue_audit` count = 0 (grep confirmed KHÔNG có) | **no-op (skip)** |
| `api/tests/unit/test_require_hub_admin_for.py` | **create (NEW)** | unit test dependency 5-case | mock AsyncSession.execute + mock get_effective_role → assert HTTPException code | `tests/unit/test_role_helper.py` (line 1-150 — AsyncMock(AsyncSession) pattern) + `tests/unit/test_require_internal_auth.py` (line 1-160 — HTTPException assert pattern) | **exact (carry forward)** |
| `api/tests/unit/test_audit_actor_scope.py` | **create (NEW)** | unit test build_audit_payload | dict input → assert dict shape có actor_role + actor_hub_id key | `tests/unit/test_role_helper.py` (pure Python pytest) | **role-match (pure unit)** |
| `api/tests/integration/test_dep_users_scope.py` | **create (NEW)** | integration test 5 scenario | httpx AsyncClient → POST /api/users → assert 201/403 + DB inspect | `tests/integration/test_rbac_dependency.py` (line 1-332 — `_spawn_rbac_app` + `_insert_user_via_engine` + `_login` pattern) + `tests/integration/conftest.py` (line 442-535 — `admin_user/editor_user/viewer_user` fixture) | **exact (extend conftest)** |

---

## Pattern Assignments

### 1. `api/app/auth/dependencies.py` (dependency factory + inline validator)

**Analog:** `require_role` closure pattern (line 290-333) + `get_current_user_for_hub_access` runtime check (line 365-431) + `require_internal_auth` defensive 401 (line 251-287)

**Imports pattern** (lines 12-30 hiện có — Phase 2 KHÔNG cần thêm import mới ngoài `get_effective_role`):
```python
from __future__ import annotations
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.auth import User
# Phase 2 thêm:
from app.auth.role import UserNotFoundError, get_effective_role
```

**Closure factory pattern** (carry forward `require_role` lines 290-333) cho `require_hub_admin_for(hub_id_source: str)` — KHI hub_id có trong path param (vd `/api/hubs/{hub_id}/...` future):
```python
def require_role(
    *roles: str,
) -> Callable[[User], Awaitable[User]]:
    # ... line 290-320 build closure
    if not roles:
        raise ValueError("require_role cần ít nhất 1 role")
    allowed = set(roles)

    async def _dependency(user: User = Depends(get_current_user)) -> User:  # noqa: B008
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"Không đủ quyền — yêu cầu một trong {sorted(allowed)}",
                },
            )
        return user

    return _dependency
```

**Inline validator pattern** (carry forward `get_current_user_for_hub_access` lines 401-431) cho `assert_hub_admin_for(...)` — KHI hub_id trong body POST/PATCH (case Phase 2 chủ đạo):
```python
# get_current_user_for_hub_access pattern:
async def get_current_user_for_hub_access(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    from app.config import get_settings
    settings = get_settings()
    if settings.hub_name == "central":
        return user  # bypass — cross-hub by design

    claims = getattr(request.state, "jwt_claims", None)
    # ...
    if settings.hub_name not in claims.hub_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "CROSS_HUB_ACCESS_DENIED",
                "message": (
                    f"Token KHÔNG có quyền truy cập hub "
                    f"{settings.hub_name!r} (hub_ids JWT = {claims.hub_ids!r})"
                ),
            },
        )
    return user
```

**Recommended Phase 2 implementation** (hybrid D-V3.1-Phase2-D LOCKED):
```python
async def assert_hub_admin_for(
    *,
    user: User,
    db: AsyncSession,
    target_hub_id: str,
) -> None:
    """Phase 2 DEP-01 (D-V3.1-Phase2-D LOCKED) — Pure validator function.

    Gọi INLINE trong handler SAU khi parse body (vì hub_id trong body, KHÔNG path).
    Super admin (user.role='admin') → bypass. Hub_admin của target_hub_id → pass.
    Other → raise 403 HUB_ADMIN_REQUIRED.
    """
    if user.role == "admin":
        return  # super admin bypass — cross-hub by design

    try:
        effective = await get_effective_role(db, user.id, target_hub_id)
    except UserNotFoundError as e:
        # Defensive — stale JWT user_id → reject như hub_admin fail.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "HUB_ADMIN_REQUIRED",
                "message": "User không tồn tại — token stale",
            },
        ) from e

    if effective != "hub_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "HUB_ADMIN_REQUIRED",
                "message": (
                    f"Yêu cầu hub_admin của hub {target_hub_id!r} — "
                    f"effective role: {effective!r}"
                ),
            },
        )
```

**Error handling pattern** (line 174-184 + line 252-287 + line 308-330):
- 401 → `WWW-Authenticate: Bearer` header (KHÔNG 403 nếu auth fail).
- 403 → envelope `detail={"code": "<CODE>", "message": "<msg tiếng Việt>"}` — frontend FE-01 switch trên `error.code`.
- 500 → `AUTH_STATE_MISSING` (defensive — get_current_user contract broken).

---

### 2. `api/app/routers/hubs.py` (GET /api/hubs verify only)

**Analog:** Chính `routers/hubs.py:73-85` ĐÃ có branch admin / non-admin → list_for_hubs pattern.

**Core pattern (đã đúng — Phase 2 chỉ cần verify qua integration test)** lines 73-85:
```python
if user.role == "admin":
    # admin quản trị cross-hub — thấy mọi hub.
    items, total = await service.list(
        page=capped_page, per_page=capped_per_page
    )
else:
    # non-admin — chỉ hub được assign (load hub_ids từ DB user_hubs,
    # KHÔNG tin payload; T-08.2-02-I Information Disclosure mitigation).
    stmt = select(UserHub.hub_id).where(UserHub.user_id == user.id)
    hub_ids = [str(h) for h in (await db.execute(stmt)).scalars().all()]
    items, total = await service.list_for_hubs(
        hub_ids=hub_ids, page=capped_page, per_page=capped_per_page
    )
```

**Phase 2 verify task:**
- Hub_admin user (`users.role='editor'` global + `user_hubs.role='hub_admin'` per-hub) RƠI VÀO else branch (vì `users.role != 'admin'`) → đúng theo D-V3.1-Phase2-A LOCKED.
- 5 endpoint mutate (POST/PUT/PATCH/stats — lines 94-218) GIỮ `Depends(require_role("admin"))` — Phase 2 KHÔNG đụng (DEP-04 LOCKED).

**Service `list_for_hubs` pattern** (hub_service.py line 171-208) ĐÃ có — Phase 2 reuse:
```python
async def list_for_hubs(
    self,
    *,
    hub_ids: list[str],
    page: int,
    per_page: int,
) -> tuple[list[HubResponse], int]:
    if not hub_ids:
        return [], 0  # tránh SQL ANY([])
    # WHERE id = ANY(:hub_ids) — named bind param asyncpg
    # ...
```

---

### 3. `api/app/routers/users.py` (5 endpoint CRUD scope hub_admin)

**Analog:** Hiện trạng 7 endpoint đều dùng `Depends(require_role("admin"))` (lines 64/94/114/138/162/188/212/261). Phase 2 cần REPLACE 5 endpoint scope check sang hybrid pattern (super admin → assert_hub_admin_for inline check).

**Recommended refactor pattern** (carry forward hubs.py:94-112 create handler — admin-only NHƯNG Phase 2 thay bằng `get_current_user` + inline `assert_hub_admin_for`):
```python
# Hiện trạng users.py:90-108 (cần refactor):
@router.post("")
async def create_user(
    req: CreateUserRequest,
    request: Request,
    user: User = Depends(require_role("admin")),  # ← Phase 2 thay
    service: UserService = Depends(get_user_service),
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    try:
        result = await service.create(
            req=req, created_by=user.id, request_id=request_id
        )
    except UserConflictError as e:
        return resp.conflict(message=str(e), code="EMAIL_CONFLICT")
    return resp.created(data=result.model_dump(mode="json"))
```

**Refactor target** (Phase 2 DEP-03):
```python
@router.post("")
async def create_user(
    req: CreateUserRequest,
    request: Request,
    user: User = Depends(get_current_user),  # ← thay require_role("admin")
    db: AsyncSession = Depends(get_session),
    service: UserService = Depends(get_user_service),
) -> JSONResponse:
    # DEP-03 — inline scope check: super admin bypass, hub_admin gate hub target.
    await assert_hub_admin_for(user=user, db=db, target_hub_id=req.hub_id)

    # DEP-05 — derive actor metadata cho audit payload nest.
    actor_role = "admin" if user.role == "admin" else "hub_admin"
    actor_hub_id = None if user.role == "admin" else req.hub_id

    request_id = getattr(request.state, "request_id", None)
    try:
        result = await service.create(
            req=req,
            created_by=user.id,
            actor_role=actor_role,          # ← Phase 2 DEP-05 mới
            actor_hub_id=actor_hub_id,      # ← Phase 2 DEP-05 mới
            request_id=request_id,
        )
    except UserConflictError as e:
        return resp.conflict(message=str(e), code="EMAIL_CONFLICT")
    return resp.created(data=result.model_dump(mode="json"))
```

**5 endpoint cần refactor scope check** (theo CONTEXT.md §"Specific Implementation Hints"):
| Endpoint | Line | hub_id source | Cross-hub semantics (D-V3.1-Phase2-E) |
|----------|------|---------------|----------------------------------------|
| `POST /api/users` create | 90-108 | `req.hub_id` body | hub_admin → check `req.hub_id`; super admin → any |
| `GET /api/users` list | 56-87 | `hub_id` query optional | hub_admin → force filter `hub_id ∈ user_hubs(user.id, role='hub_admin')`; super admin → any |
| `PATCH /api/users/:id/role` change_role | 158-181 | `req.hub_id` body | hub_admin → check `req.hub_id` + block role='admin' transition (T-02-02-E mitigation) |
| `PATCH /api/users/:id/status` change_status | 184-205 | KHÔNG có hub_id → derive từ user target | hub_admin → derive `target_hub_id` qua SELECT user_hubs WHERE user_id=:target; user thuộc nhiều hub → super admin only |
| `DELETE /api/users/:id` delete_user | 208-254 | KHÔNG có hub_id | hub_admin → user target thuộc CHỈ hub mình → OK; user thuộc nhiều hub → super admin only |

**Error envelope pattern** (carry forward users.py:107 + 122-129):
```python
return resp.conflict(message=str(e), code="EMAIL_CONFLICT")
return resp.bad_request(message=f"user_id không hợp lệ: {user_id!r}", code="INVALID_USER_ID")
return resp.forbidden(message="...", code="HUB_ADMIN_REQUIRED")  # ← Phase 2 thêm code mới
```

`resp.forbidden(message, code)` ĐÃ chấp nhận `code` param (response.py:98-103) — KHÔNG cần helper mới.

---

### 4. `api/app/services/audit_service.py` (build_audit_payload helper)

**Analog:** `AuditEntry` dataclass (line 51-65) + `enqueue_audit` (line 85-94).

**Existing pattern** (lines 51-65):
```python
@dataclass
class AuditEntry:
    """1 audit record chờ flush vào bảng `audit_logs`."""
    action: str
    user_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    hub_id: str | None = None
    payload: dict[str, Any] | None = None
    request_id: str | None = None
```

**Phase 2 add helper pattern** (recommend free function thay vì method để KHÔNG đổi shape dataclass):
```python
# Add ở api/app/services/audit_service.py (after AuditEntry dataclass):
def build_audit_payload(
    *,
    actor_role: str,
    actor_hub_id: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Phase 2 DEP-05 (D-V3.1-Phase2-C LOCKED) — Nest actor scope vào payload.

    Helper convenience để dedup pattern 5 callsite enqueue_audit (user_service +
    hub_service). KHÔNG migration schema thêm cột — payload JSONB đủ chứa
    metadata (audit_logs.payload nullable JSONB — migration 0001).

    Args:
        actor_role: 'admin' (super admin) | 'hub_admin' (per-hub).
        actor_hub_id: NULL nếu super admin (cross-hub op); hub_id cụ thể nếu hub_admin.
        extra: payload-specific data (email, role, code, name, ...) — merge vào dict.

    Returns:
        dict shape: {actor_role: str, actor_hub_id: str | None, **extra}

    Example:
        >>> build_audit_payload(
        ...     actor_role='hub_admin',
        ...     actor_hub_id='dmd-uuid',
        ...     extra={'email': 'new@dmd.vn', 'role': 'viewer'},
        ... )
        {'actor_role': 'hub_admin', 'actor_hub_id': 'dmd-uuid',
         'email': 'new@dmd.vn', 'role': 'viewer'}
    """
    base: dict[str, Any] = {
        "actor_role": actor_role,
        "actor_hub_id": actor_hub_id,
    }
    if extra:
        base.update(extra)
    return base
```

**Enqueue pattern carry forward** (line 85-94 — KHÔNG đổi):
```python
def enqueue_audit(entry: AuditEntry) -> None:
    try:
        _get_queue().put_nowait(entry)
    except asyncio.QueueFull:
        logger.warning("audit_queue_full_dropped: action=%s", entry.action)
```

---

### 5. `api/app/services/user_service.py` (2 callsite refactor — create + delete)

**Analog:** `create()` callsite line 182-192 + `delete()` callsite line 465-478.

**Existing create callsite** (lines 182-192):
```python
enqueue_audit(
    AuditEntry(
        action="user.create",
        user_id=str(created_by),
        target_type="user",
        target_id=str(user_id),
        hub_id=req.hub_id,
        payload={"email": req.email, "role": req.role},
        request_id=request_id,
    )
)
```

**Phase 2 refactor** (signature + payload nest):
```python
async def create(
    self,
    *,
    req: CreateUserRequest,
    created_by: UUID,
    actor_role: str,                # ← Phase 2 thêm
    actor_hub_id: str | None,       # ← Phase 2 thêm
    request_id: str | None = None,
) -> UserWithRolesResponse:
    # ... INSERT users + user_hubs (lines 144-178 GIỮ NGUYÊN)
    enqueue_audit(
        AuditEntry(
            action="user.create",
            user_id=str(created_by),
            target_type="user",
            target_id=str(user_id),
            hub_id=req.hub_id,
            payload=build_audit_payload(    # ← Phase 2 thay dict literal
                actor_role=actor_role,
                actor_hub_id=actor_hub_id,
                extra={"email": req.email, "role": req.role},
            ),
            request_id=request_id,
        )
    )
    # ... rest unchanged
```

**Existing delete callsite** (lines 465-478) — apply same pattern:
```python
# Phase 2 refactor:
enqueue_audit(
    AuditEntry(
        action="user.delete",
        user_id=str(deleted_by),
        target_type="user",
        target_id=str(user_id),
        hub_id=None,
        payload=build_audit_payload(
            actor_role=actor_role,
            actor_hub_id=actor_hub_id,
            extra={
                "deleted_email": email_to_delete,
                "deleted_role": role_to_delete,
            },
        ),
        request_id=request_id,
    )
)
```

**Imports cần thêm** ở user_service.py top:
```python
from app.services.audit_service import AuditEntry, build_audit_payload, enqueue_audit
```

---

### 6. `api/app/services/hub_service.py` (3 callsite refactor — create + update + update_status)

**Analog:** Existing 3 callsite:
- `create()` line 113-122 → action='hub.create'
- `update()` line 246-256 → action='hub.update' (payload changed dict)
- `update_status()` line 285-295 → action='hub.update' (payload status)

**D-V3.1-Phase2-D LOCKED carry forward:** Hub mutate endpoints GIỮ `require_role("admin")` (DEP-04) → mọi caller hub_service là SUPER ADMIN → `actor_role='admin'`, `actor_hub_id=None` LUÔN. Tuy nhiên signature vẫn cần thêm params để consistent với user_service (giảm risk forget pass khi future endpoint mở cho hub_admin):

```python
# Phase 2 signature update:
async def create(
    self,
    *,
    req: CreateHubRequest,
    created_by: UUID,
    actor_role: str = "admin",        # ← default 'admin' vì DEP-04 LOCKED
    actor_hub_id: str | None = None,  # ← default None
    request_id: str | None = None,
) -> HubResponse:
    # ... INSERT (lines 83-110 GIỮ NGUYÊN)
    enqueue_audit(
        AuditEntry(
            action="hub.create",
            user_id=str(created_by),
            target_type="hub",
            target_id=str(hub_id),
            hub_id=str(hub_id),
            payload=build_audit_payload(
                actor_role=actor_role,
                actor_hub_id=actor_hub_id,
                extra={"code": req.code, "name": req.name},
            ),
            request_id=request_id,
        )
    )
```

**Update + update_status** áp dụng cùng pattern (line 246-256 + line 285-295).

---

### 7. `api/app/services/api_key_service.py` (review — no-op)

**Grep result:** `enqueue_audit` KHÔNG xuất hiện trong api_key_service.py (chỉ 3 file dùng: audit_service, hub_service, user_service, documents_service).

**Phase 2 action:** SKIP — KHÔNG cần thay đổi api_key_service.py. CONTEXT.md §"Specific Implementation Hints #7" đã note "Verify nếu có audit emit, update tương tự" → đã verify KHÔNG có → no-op.

---

### 8. `api/tests/unit/test_require_hub_admin_for.py` (NEW — 5-case unit test)

**Analog 1:** `tests/unit/test_role_helper.py` (line 1-150 — AsyncMock(AsyncSession) pattern Phase 1 v3.1).

**Analog 2:** `tests/unit/test_require_internal_auth.py` (line 1-160 — `pytest.raises(HTTPException)` + assert `.detail["code"]` pattern).

**Imports + AsyncMock factory pattern** (carry forward test_role_helper.py line 14-42):
```python
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.auth.dependencies import assert_hub_admin_for  # NEW Phase 2
from app.auth.role import UserNotFoundError


def _make_session(*fetchone_returns: object) -> AsyncMock:
    """Build AsyncMock(AsyncSession) — carry forward test_role_helper.py."""
    session = AsyncMock()
    result_mocks = []
    for fetchone_value in fetchone_returns:
        result = MagicMock()
        result.fetchone.return_value = fetchone_value
        result_mocks.append(result)
    session.execute = AsyncMock(side_effect=result_mocks)
    return session


def _make_user(role: str, user_id=None):
    """SimpleNamespace user — pattern carry forward test_require_internal_auth.py."""
    return SimpleNamespace(id=user_id or uuid4(), role=role)
```

**5-case test pattern** (carry forward D-V3.1-Phase2-D LOCKED logic):
```python
@pytest.mark.asyncio
async def test_super_admin_bypass_returns_none() -> None:
    """Case 1: user.role='admin' (super admin) → bypass, KHÔNG check get_effective_role."""
    user = _make_user("admin")
    session = AsyncMock()  # KHÔNG cần session.execute (bypass trước query)

    # Không raise → pass.
    await assert_hub_admin_for(user=user, db=session, target_hub_id=str(uuid4()))

    # Verify session.execute KHÔNG được gọi (bypass).
    assert session.execute.call_count == 0


@pytest.mark.asyncio
async def test_hub_admin_correct_hub_returns_none() -> None:
    """Case 2: hub_admin của hub đúng → get_effective_role='hub_admin' → pass."""
    user = _make_user("editor")  # global role editor
    hub_id = str(uuid4())
    # Mock 1 query: user_hubs.role='hub_admin' → fetchone trả ('hub_admin',).
    session = _make_session(('hub_admin',))

    await assert_hub_admin_for(user=user, db=session, target_hub_id=hub_id)
    # No raise = pass.


@pytest.mark.asyncio
async def test_hub_admin_wrong_hub_raises_403() -> None:
    """Case 3: hub_admin của hub KHÁC → effective='viewer' (no override) → 403."""
    user = _make_user("editor")
    # Mock: user_hubs.role NULL cho hub này → fallthrough → users.role='viewer'.
    session = _make_session(None, ('viewer',))

    with pytest.raises(HTTPException) as exc_info:
        await assert_hub_admin_for(
            user=user, db=session, target_hub_id=str(uuid4())
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "HUB_ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_viewer_not_hub_admin_raises_403() -> None:
    """Case 4: viewer/editor không phải hub_admin → 403 HUB_ADMIN_REQUIRED."""
    user = _make_user("viewer")
    session = _make_session(None, ('viewer',))

    with pytest.raises(HTTPException) as exc_info:
        await assert_hub_admin_for(
            user=user, db=session, target_hub_id=str(uuid4())
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "HUB_ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_no_membership_raises_403() -> None:
    """Case 5: user KHÔNG có user_hubs row + global role='editor' → fallback 403."""
    user = _make_user("editor")
    # Mock: cả 2 query trả None → UserNotFoundError → catch → 403.
    session = _make_session(None, None)

    with pytest.raises(HTTPException) as exc_info:
        await assert_hub_admin_for(
            user=user, db=session, target_hub_id=str(uuid4())
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "HUB_ADMIN_REQUIRED"
```

**Acceptance criteria** (carry forward Plan 01-02 acceptance pattern):
- File chứa ≥ 5 test function `async def test_...`.
- Tất cả import từ `app.auth.dependencies` + `app.auth.role`.
- `@pytest.mark.asyncio` decorator ≥ 5 lần.
- `pytest.raises(HTTPException)` cho 3 case fail.
- Assert `exc_info.value.detail["code"] == "HUB_ADMIN_REQUIRED"` cho mọi case fail.
- `cd Hub_All/api && python -m pytest tests/unit/test_require_hub_admin_for.py -x` exit 0.

---

### 9. `api/tests/unit/test_audit_actor_scope.py` (NEW — unit test build_audit_payload)

**Analog:** `tests/unit/test_role_helper.py` (pure Python, no fixture conftest).

**Test pattern (~3-4 test minimum):**
```python
"""Unit test build_audit_payload helper — Phase 2 DEP-05 (D-V3.1-Phase2-C LOCKED).

Pure Python test — KHÔNG cần Postgres/Redis. Verify shape dict output.
"""
from __future__ import annotations

from app.services.audit_service import build_audit_payload


def test_super_admin_nests_actor_role_admin_and_null_hub() -> None:
    """Super admin → actor_role='admin' + actor_hub_id=None."""
    result = build_audit_payload(
        actor_role="admin",
        actor_hub_id=None,
        extra={"email": "x@y.com", "role": "viewer"},
    )
    assert result["actor_role"] == "admin"
    assert result["actor_hub_id"] is None
    assert result["email"] == "x@y.com"
    assert result["role"] == "viewer"


def test_hub_admin_nests_actor_role_and_hub_id() -> None:
    """Hub_admin → actor_role='hub_admin' + actor_hub_id=<hub-uuid>."""
    hub_id = "dmd-uuid-123"
    result = build_audit_payload(
        actor_role="hub_admin",
        actor_hub_id=hub_id,
        extra={"code": "dmd", "name": "Đỗ Minh Đường"},
    )
    assert result["actor_role"] == "hub_admin"
    assert result["actor_hub_id"] == hub_id


def test_extra_none_returns_only_actor_keys() -> None:
    """extra=None → dict chỉ chứa 2 key actor."""
    result = build_audit_payload(
        actor_role="admin", actor_hub_id=None, extra=None
    )
    assert set(result.keys()) == {"actor_role", "actor_hub_id"}


def test_extra_overrides_actor_keys_warning() -> None:
    """Defensive: extra KHÔNG được override actor_role/actor_hub_id (caller bug guard).

    Hiện implementation merge — extra có actor_role sẽ override. Document
    behavior + test → caller có quyền override (vd test seed data).
    """
    result = build_audit_payload(
        actor_role="admin",
        actor_hub_id=None,
        extra={"actor_role": "override"},
    )
    # behavior accept: extra override actor_role.
    assert result["actor_role"] == "override"
```

---

### 10. `api/tests/integration/test_dep_users_scope.py` (NEW — 5 scenario integration)

**Analog:** `tests/integration/test_rbac_dependency.py` (line 1-332 — `_spawn_rbac_app` + `_insert_user_via_engine` + `_login` pattern Phase 3 Plan 05-05).

**Analog 2:** `tests/integration/conftest.py` (line 442-535 — `admin_user/editor_user/viewer_user` fixture + `app_with_auth` LifespanManager).

**Spawn app pattern** (carry forward test_rbac_dependency.py:54-129):
```python
"""Integration test users.py scope hub_admin — Phase 2 DEP-03 + DEP-05.

5 scenario carry forward ROADMAP §"Phase 2 success criteria 2":
1. Hub_admin assigned dmd POST /api/users (hub_id=dmd) → 201.
2. Hub_admin assigned dmd POST /api/users (hub_id=tdt) → 403 HUB_ADMIN_REQUIRED.
3. Super admin POST /api/users any hub → 201.
4. Hub_admin assigned dmd DELETE /api/users/:id (user thuộc dmd only) → 200.
5. Audit log row chứa actor_role + actor_hub_id chính xác.
"""
from __future__ import annotations
# Carry forward import block từ test_rbac_dependency.py:19-36 + conftest.py admin_user

import httpx
import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import text

# Fixture chain: admin_user (super), hub_admin_dmd (hub_admin của dmd),
# auth_client (httpx + ASGITransport in-process).
```

**Seed hub_admin user pattern** (extend conftest `_insert_user_via_engine` + `_insert_hub` + `_assign_user_hub`):
```python
# Cần thêm fixture vào conftest.py HOẶC inline trong test file:
async def _seed_hub_admin(*, email: str, hub_id: str) -> str:
    """Phase 2: seed user role='editor' global + user_hubs.role='hub_admin' per-hub.

    Carry forward conftest._insert_user (Phase 3) + _assign_user_hub (Phase 5 Plan 05-06).
    KHÁC: thêm UPDATE user_hubs SET role='hub_admin' SAU INSERT (Plan 01-01 migration 0006
    đã add column user_hubs.role TEXT NULL).
    """
    from app.db.session import get_engine
    import uuid as _uuid
    from tests.integration.conftest import GO_SEED_HASH
    engine = get_engine()
    user_id = str(_uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, role, "
                "is_active, created_at, updated_at) "
                "VALUES (:id, :email, :hash, :name, 'editor', TRUE, NOW(), NOW())"
            ),
            {"id": user_id, "email": email, "hash": GO_SEED_HASH, "name": "Hub Admin"},
        )
        # Plan 01-01 migration 0006 — user_hubs.role NULL default, override 'hub_admin'.
        await conn.execute(
            text(
                "INSERT INTO user_hubs (user_id, hub_id, role, assigned_at) "
                "VALUES (:uid, :hid, 'hub_admin', NOW())"
            ),
            {"uid": user_id, "hid": hub_id},
        )
    return user_id
```

**Test scenario pattern** (carry forward test_rbac_dependency.py:205-237):
```python
@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_dmd_create_user_in_dmd_returns_201(
    auth_client: httpx.AsyncClient,
) -> None:
    """Case 2 success criteria #2: hub_admin dmd POST /api/users (hub=dmd) → 201."""
    dmd_id = await _insert_hub(name="Đỗ Minh Đường", code="dmd", subdomain="dmd")
    await _seed_hub_admin(email="admin.dmd@medinet.vn", hub_id=dmd_id)
    token = await _login(auth_client, "admin.dmd@medinet.vn", "Admin@123")

    r = await auth_client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "viewer@dmd.vn",
            "name": "Viewer DMD",
            "password": "Pass1234",
            "hub_id": dmd_id,
            "role": "viewer",
        },
    )
    assert r.status_code == 201, r.text


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_hub_admin_dmd_create_user_in_tdt_returns_403(
    auth_client: httpx.AsyncClient,
) -> None:
    """Case 3 success criteria #2: hub_admin dmd POST /api/users (hub=tdt) → 403."""
    dmd_id = await _insert_hub(name="Đỗ Minh Đường", code="dmd", subdomain="dmd")
    tdt_id = await _insert_hub(name="Thuốc Dân Tộc", code="tdt", subdomain="tdt")
    await _seed_hub_admin(email="admin.dmd@medinet.vn", hub_id=dmd_id)
    token = await _login(auth_client, "admin.dmd@medinet.vn", "Admin@123")

    r = await auth_client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "viewer@tdt.vn",
            "name": "Viewer TDT",
            "password": "Pass1234",
            "hub_id": tdt_id,
            "role": "viewer",
        },
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "HUB_ADMIN_REQUIRED"


@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_log_actor_metadata_nested_correctly(
    auth_client: httpx.AsyncClient,
) -> None:
    """Case 5 success criteria #4: audit_logs.payload chứa actor_role + actor_hub_id.

    Hub_admin operation → actor_role='hub_admin' + actor_hub_id='<dmd-uuid>'.
    Super admin operation → actor_role='admin' + actor_hub_id IS NULL.
    """
    # ... POST /api/users qua hub_admin token + super admin token
    # Wait audit flush (poll pattern _wait_usage_count carry forward conftest.py:778-806):
    # Query audit_logs WHERE action='user.create' ORDER BY created_at DESC LIMIT 2
    # Assert payload->>'actor_role' + payload->>'actor_hub_id'
```

**Acceptance criteria** (carry forward ROADMAP §"Phase 2 success criteria 5" — coverage ≥ 80% file thay đổi):
- 5 test scenario PASS (testcontainers Postgres + Redis live).
- Audit log inspect: 2 row có payload nested đúng (1 hub_admin + 1 super admin).
- Coverage report `dependencies.py` + `users.py` ≥ 80%.

---

## Shared Patterns

### Pattern A: Raw SQL `text()` + named bind params (carry forward CLAUDE.md §3 stack pin)

**Source:** `app/auth/role.py:91-97` + `app/services/user_service.py:147-164` + `app/services/hub_service.py:86-105`.

**Apply to:** Mọi file service/dependency Phase 2 query DB.

**Pattern:**
```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

result = await session.execute(
    text("SELECT col FROM table WHERE id = :id AND hub_id = :hub_id"),
    {"id": str(user_id), "hub_id": str(hub_id)},
)
row = result.fetchone()  # tuple hoặc None
```

**Anti-pattern (T-01-02-01 SQL injection):**
```python
# ❌ KHÔNG f-string concat user input
await session.execute(text(f"SELECT * FROM users WHERE email = '{email}'"))
```

---

### Pattern B: Response envelope helpers `app.pkg.response`

**Source:** `app/pkg/response.py:98-103` (`forbidden(message, code)`).

**Apply to:** Mọi router endpoint Phase 2 trả error.

**Pattern:**
```python
from app.pkg import response as resp

# 403 hub_admin gate fail:
return resp.forbidden(
    message=f"Yêu cầu hub_admin của hub {hub_id!r}",
    code="HUB_ADMIN_REQUIRED",  # ← Phase 2 NEW code
)

# 400 validate input:
return resp.bad_request(message=f"hub_id không hợp lệ: {hub_id!r}", code="INVALID_HUB_ID")

# 409 conflict:
return resp.conflict(message=str(e), code="EMAIL_CONFLICT")

# 201 created:
return resp.created(data=result.model_dump(mode="json"))
```

**Envelope shape (LOCKED M2 D6 + v3.0 PROXY-01):** `{success: bool, data: any, error: {code, message}, meta: any}`.

---

### Pattern C: AsyncMock(AsyncSession) factory for unit test (carry forward Phase 1 Plan 01-02)

**Source:** `tests/unit/test_role_helper.py:24-42`.

**Apply to:** `test_require_hub_admin_for.py` + bất kỳ unit test mới Phase 2 cần mock AsyncSession.

**Pattern:**
```python
from unittest.mock import AsyncMock, MagicMock

def _make_session(*fetchone_returns: object) -> AsyncMock:
    """Build AsyncMock(AsyncSession) trả về sequence fetchone results."""
    session = AsyncMock()
    result_mocks = []
    for fetchone_value in fetchone_returns:
        result = MagicMock()
        result.fetchone.return_value = fetchone_value
        result_mocks.append(result)
    session.execute = AsyncMock(side_effect=result_mocks)
    return session
```

---

### Pattern D: `pytest.raises(HTTPException)` + detail code assert (carry forward Phase 6 Plan 06-03)

**Source:** `tests/unit/test_require_internal_auth.py:54-65`.

**Apply to:** Mọi unit test Phase 2 verify dependency raise HTTPException.

**Pattern:**
```python
import pytest
from fastapi import HTTPException

with pytest.raises(HTTPException) as exc_info:
    await some_dependency(...)

assert exc_info.value.status_code == 403
assert exc_info.value.detail["code"] == "HUB_ADMIN_REQUIRED"
```

---

### Pattern E: Integration test spawn pattern (LifespanManager + ASGITransport)

**Source:** `tests/integration/test_rbac_dependency.py:54-129` + `tests/integration/conftest.py:184-289`.

**Apply to:** `test_dep_users_scope.py`.

**Pattern:**
```python
from asgi_lifespan import LifespanManager
import httpx

async with LifespanManager(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # ... test calls
        r = await client.post("/api/users", headers={"Authorization": f"Bearer {token}"}, json={...})
```

**Module isolation note (DEF-05-01 carry forward):**
- `monkeypatch.setenv("COCOINDEX_SKIP_SETUP", "1")` — bypass cocoindex singleton.
- `from app.services.audit_service import reset_queue; reset_queue()` — reset module-global queue trước mỗi test (tránh event loop leak).
- `await dispose_engine()` — reset SQLAlchemy engine state.
- `TRUNCATE TABLE users, refresh_tokens, user_hubs, hubs, audit_logs, api_keys ... CASCADE` — per-test isolation.

---

### Pattern F: Audit poll-based wait (avoid flaky sleep)

**Source:** `tests/integration/conftest.py:778-806` (`_wait_usage_count`).

**Apply to:** `test_dep_users_scope.py` test #5 (audit payload verify) — audit_logs INSERT qua background `audit_flush_loop`, KHÔNG sync.

**Pattern:**
```python
async def _wait_audit_count(conn, action: str, expected: int, *, timeout_s: float = 2.0):
    import asyncio, time
    deadline = time.monotonic() + timeout_s
    last = -1
    while time.monotonic() < deadline:
        last = await conn.fetchval(
            "SELECT count(*) FROM audit_logs WHERE action = $1", action
        )
        if last == expected:
            return int(last)
        await asyncio.sleep(0.05)
    raise AssertionError(f"audit_logs count={last}, kỳ vọng {expected}")
```

---

### Pattern G: Service signature `*` keyword-only + audit metadata params

**Source:** `app/services/user_service.py:129-135` + `app/services/hub_service.py:68-74`.

**Apply to:** Mọi service mutation method touched Phase 2.

**Pattern:**
```python
async def create(
    self,
    *,                                  # ← force keyword-only (Python 3.10+ PEP)
    req: CreateXxxRequest,
    created_by: UUID,
    actor_role: str,                    # ← Phase 2 DEP-05 mới
    actor_hub_id: str | None,           # ← Phase 2 DEP-05 mới
    request_id: str | None = None,
) -> XxxResponse:
    ...
```

**Lý do:** Force keyword-only → caller MUST name actor_role + actor_hub_id explicit → tránh positional bug khi thêm params giữa.

---

## No Analog Found

KHÔNG file Phase 2 nào không có analog — toàn bộ 10 file đều có pattern carry forward từ:
- Phase 1 v3.1 (`get_effective_role` + `test_role_helper`).
- Phase 3 v3.0 SSO (`get_current_user_for_hub_access` Layer 3 + `require_internal_auth`).
- Phase 5 M2 Plan 05-03..05 (`hub_service` + `user_service` + `audit_service` + `routers/hubs.py` GET branch + `routers/users.py` CRUD).
- Phase 5 M2 Plan 05-06 (`tests/integration/test_rbac_dependency.py` + `conftest.py` LifespanManager fixture chain).

---

## Cross-references — Phase 2 plan estimate (carry forward ROADMAP §"Plans estimate")

| Plan | Files touched | Pattern reference |
|------|---------------|-------------------|
| **02-01** DEP-01 dependency + unit test | `auth/dependencies.py` + `tests/unit/test_require_hub_admin_for.py` | §1 + §8 (Pattern A/C/D) |
| **02-02** routers/hubs.py verify + routers/hubs.py mutate preserve | `routers/hubs.py` (verify only) | §2 (Pattern B) |
| **02-03** routers/users.py CRUD scope + integration test | `routers/users.py` + `tests/integration/test_dep_users_scope.py` | §3 + §10 (Pattern E/F/G) |
| **02-04** Audit payload nest + 3 service update | `audit_service.py` + `user_service.py` + `hub_service.py` + `tests/unit/test_audit_actor_scope.py` | §4 + §5 + §6 + §9 (Pattern G) |
| **02-05** Closeout — CLAUDE.md + STATE.md + REQUIREMENTS.md | docs only | — |

---

## Metadata

**Analog search scope:**
- `Hub_All/api/app/auth/` (dependencies.py, role.py, jwks.py, service.py, __init__.py, _blacklist.py, api_key.py, password.py, router.py, jwt.py).
- `Hub_All/api/app/routers/` (hubs.py, users.py).
- `Hub_All/api/app/services/` (audit_service.py, user_service.py, hub_service.py, api_key_service.py).
- `Hub_All/api/app/pkg/response.py` (envelope helpers).
- `Hub_All/api/app/schemas/users.py` (Pydantic schemas).
- `Hub_All/api/app/models/auth.py` (User + UserHub ORM).
- `Hub_All/api/tests/unit/` (test_require_role.py, test_role_helper.py, test_require_internal_auth.py, test_require_api_key_hub_branch.py).
- `Hub_All/api/tests/integration/` (test_rbac_dependency.py, conftest.py).

**Files scanned:** ~25 (focused on RBAC + audit + test patterns).

**Pattern extraction date:** 2026-05-24.

**Pattern source-of-truth confidence:** HIGH — toàn bộ analog là production code đã ship M2 + v3.0 + v3.1 Phase 1 (38+38+3 plan complete). Phase 2 chỉ extend, KHÔNG rewrite.

---

*Phase: 02-backend-rbac-enforcement*
*Pattern mapped: 2026-05-24 (auto mode — derived từ 02-CONTEXT.md §"Specific Implementation Hints" + 6 D-V3.1-Phase2-A..F LOCKED)*
