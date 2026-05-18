"""RAG config router — port endpoint Go /api/rag-config (ASK-04 hot-swap).

4 endpoint khớp contract frontend React 19 (`Settings.tsx`, `DocumentIngestion.tsx`):

    GET  /api/rag-config              — config hiện tại (public, key MASKED)
    PUT  /api/rag-config              — update + hot-swap (admin-only)
    GET  /api/rag-config/test         — test API key gọi provider (authenticated)
    GET  /api/rag-config/collections  — inventory vector store theo hub (admin-only)

NOTE — RAW JSON, KHÔNG envelope: frontend đọc `data.embedding_provider` trực
tiếp (KHÔNG `data.data.*`). Endpoint Go cũ cũng trả raw `gin.H` → giữ contract
D6. Vì vậy router này return `dict` / `JSONResponse` thuần, KHÔNG dùng
`app.pkg.response` helper (helper bọc envelope `{success,data,error,meta}`).

DEVIATION /test: Go trả 200 cho mọi case (kể cả key sai) — frontend chỉ check
`res.ok` nên nút Test luôn báo xanh = vô nghĩa. Router này trả 200 khi key OK,
400/502 khi fail → `res.ok` phản ánh đúng kết quả.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.db.session import get_session
from app.models.auth import User
from app.schemas.rag_config import UpdateRagConfigRequest
from app.services.rag_config_service import RagConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag-config", tags=["rag-config"])


@router.get("")
async def get_rag_config(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict:
    """GET /api/rag-config — config RAG hiện tại. Public (key đã MASKED)."""
    return await RagConfigService(db=db).get_config()


@router.put("", response_model=None)
async def update_rag_config(
    req: UpdateRagConfigRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse | dict:
    """PUT /api/rag-config — update + hot-swap provider/key, admin-only."""
    result = await RagConfigService(db=db).update_config(
        req=req, updated_by=user.id
    )
    if isinstance(result, str):
        return JSONResponse(status_code=400, content={"error": result})
    return result


@router.get("/test", response_model=None)
async def test_rag_config(
    provider: str,
    user: User = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> JSONResponse | dict:
    """GET /api/rag-config/test?provider=gemini|openai — kiểm tra API key.

    Gọi thử endpoint list-models của provider bằng key đã lưu.
    """
    _ = user  # chỉ cần authenticated.
    if provider not in ("gemini", "openai"):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "provider phải là 'gemini' hoặc 'openai'",
            },
        )

    key = await RagConfigService(db=db).get_provider_key(provider)
    if not key:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "API key chưa được cấu hình"},
        )

    if provider == "gemini":
        url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"
        headers = {"x-goog-api-key": key}
    else:
        url = "https://api.openai.com/v1/models?limit=1"
        headers = {"Authorization": f"Bearer {key}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001 — network fail → báo lỗi rõ
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "message": f"Không thể kết nối: {exc}",
            },
        )

    if res.status_code == 200:
        return {"success": True, "message": "Kết nối thành công"}
    return JSONResponse(
        status_code=502,
        content={
            "success": False,
            "message": f"API trả lỗi {res.status_code} — kiểm tra lại key",
        },
    )


@router.get("/collections")
async def rag_config_collections(
    user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict:
    """GET /api/rag-config/collections — inventory vector store theo hub, admin-only."""
    _ = user
    return await RagConfigService(db=db).collections()
