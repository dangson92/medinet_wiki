"""Audit logs router — Plan 05-05 (AUX-01 GET query + AUX-03 rate-limit).

1 endpoint — admin-only (`require_role("admin")`; T-05-05-04 Information
Disclosure mitigation — audit log chứa payload nhạy cảm, chỉ admin xem):

    GET /api/audit-logs — list phân trang + filter date/action/hub_id

W4 — AUX-03 rate-limit áp endpoint thật:
`@limiter.limit` decorate `GET /api/audit-logs` — endpoint Phase 5 cụ thể để
AUX-03 / 429 verify được trong Phase 5 (W4 + WARNING 1). Limit cấu hình qua
`settings.rate_limit_audit_logs_per_minute` (mặc định 60/phút). ROADMAP SC5 nêu
đích danh `/api/search` — endpoint đó thuộc Phase 6 (chưa tồn tại): decoration
`@limiter.limit` cho `/api/search` + `/api/ask` defer Phase 6/7 khi 2 endpoint
đó được tạo. Cơ chế limiter + 429 envelope đã verify ở Phase 5 qua endpoint này.

slowapi yêu cầu endpoint function khai báo param `request: Request` (KHÔNG
Depends) để limiter đọc — signature dưới có `request: Request`. Thứ tự decorator:
`@router.get("")` ở TRÊN, `@limiter.limit(...)` ở DƯỚI (sát def) — slowapi yêu
cầu limiter decorator gần function nhất. Limiter cần `app.state.limiter` wired —
Plan 05-06 Task 1 wire vào main.py.

Contract verb/path + filter param lấy từ `frontend/src/services/api.ts` (D-07).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db.session import get_session
from app.middleware import AUDIT_LOGS_LIMIT, limiter
from app.models.auth import User
from app.pkg import response as resp
from app.services.audit_query_service import AuditQueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit-logs", tags=["audit-logs"])


def get_audit_query_service(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> AuditQueryService:
    return AuditQueryService(db=db)


@router.get("")
@limiter.limit(AUDIT_LOGS_LIMIT)
async def list_audit_logs(
    request: Request,
    date_from: str | None = None,
    date_to: str | None = None,
    actor_type: str | None = None,
    action: str | None = None,
    hub_id: str | None = None,
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(require_role("admin")),  # noqa: B008
    service: AuditQueryService = Depends(get_audit_query_service),  # noqa: B008
) -> JSONResponse:
    """GET /api/audit-logs — list audit log phân trang + filter, admin-only.

    Rate-limited qua `@limiter.limit(AUDIT_LOGS_LIMIT)` (W4 — AUX-03). Vượt
    ngưỡng `rate_limit_audit_logs_per_minute` → 429 envelope RATE_LIMIT_EXCEEDED.

    `actor_type` nhận để giữ contract api.ts nhưng KHÔNG filter — bảng
    `audit_logs` M2 không có cột `actor_type` (documented ở audit_query_service).
    """
    _ = request  # slowapi đọc; user gate qua require_role.
    _ = user
    _ = actor_type  # contract param — không filter (không có cột).
    capped_per_page = max(1, min(per_page, 100))
    capped_page = max(1, page)
    items, total = await service.list(
        date_from=date_from,
        date_to=date_to,
        action=action,
        hub_id=hub_id,
        page=capped_page,
        per_page=capped_per_page,
    )
    return resp.paginated(
        items=[i.model_dump(mode="json") for i in items],
        page=capped_page,
        per_page=capped_per_page,
        total=total,
    )
