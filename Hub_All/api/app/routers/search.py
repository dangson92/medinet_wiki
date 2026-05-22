"""Search router — Plan 06-02 (SEARCH-01..03 + D-04 find-similar) +
Plan 04-05 (SYNC-03 / D-V3-Phase4-D3) — tách router central-only cross-hub.

Phase 8.2 — 3 endpoint chấp nhận X-API-Key HOặC JWT (cho MCP Service forward
X-API-Key của client); hub isolation vẫn enforce qua `user.hub_ids` như cũ
(intersect ở `SearchService` — D-07 defense in depth).

Phase 4 Plan 04-05 (SYNC-03 / D-V3-Phase4-D3) — Tách 2 router cho FACTOR-02 extend:
- `router` (universal): POST /api/search + /api/search/similar — mount mọi process
  (hub con + central). Single-hub local search trên DB của process đó.
- `cross_hub_router` (central-only): POST /api/search/cross-hub — chỉ mount
  ở central process. Hub con KHÔNG own cross-hub aggregated data
  (medinet_central.chunks denormalized read replica per D-V3-02) → strip endpoint
  là correct semantic. Hub con request /api/search/cross-hub → 404 envelope D6.

3 endpoint POST — auth viewer+, shape khớp `frontend/src/services/
api.ts` (`search()`, `crossHubSearch()`, `findSimilar()` — D6 contract):

    POST /api/search            — union search 1 câu SQL (SEARCH-01 / SEARCH-02)
    POST /api/search/cross-hub  — 1 SQL aggregated WHERE hub_id = ANY (SEARCH-03 +
                                  Plan 04-05 D-V3-Phase4-D1 refactor; central-only)
    POST /api/search/similar    — find-similar (D-04 — không có REQ-ID)

Cả 3 decorate `@limiter.limit(SEARCH_LIMIT)` (D-13 — 100/min/user). slowapi yêu
cầu endpoint function khai báo param `request: Request` (KHÔNG Depends) để
limiter đọc; thứ tự decorator: `@router.post(...)` ở TRÊN, `@limiter.limit(...)`
ở DƯỚI (sát def).

Hub isolation defense in depth (D-07): hub user không được assign bị loại ở
`SearchService` (intersect TRƯỚC SQL) — router chỉ chuyển `UserWithHubs` (hub_ids
từ DB `user_hubs`, KHÔNG payload) xuống service.

DI factory `get_search_service` đọc asyncpg pool + redis từ `request.app.state`
— search dùng raw vector SQL (`<=>` + `SET LOCAL hnsw.*`), KHÔNG AsyncSession.

HubIsolationError + RateLimitExceeded handler đã wire `main.py` (Phase 5) —
KHÔNG cần thêm exception handler.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import UserWithHubs, get_api_key_or_jwt_with_hubs
from app.middleware import SEARCH_LIMIT, limiter
from app.pkg import response as resp
from app.schemas.search import SearchRequest, SimilarRequest
from app.services.embedder import EmbedderError
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

# Phase 4 Plan 04-05 — `router` (universal): POST /api/search + /api/search/similar.
# Mount ở MỌI process (central + hub con). Hub con dùng local DB
# `medinet_hub_<name>` để local single-hub search.
router = APIRouter(prefix="/api/search", tags=["search"])

# Phase 4 Plan 04-05 (SYNC-03 / D-V3-Phase4-D3) — `cross_hub_router` (central-only):
# POST /api/search/cross-hub. Tách khỏi `router` để main.py mount conditional theo
# settings.hub_name. FACTOR-02 extend: hub con KHÔNG own cross-hub aggregated
# data (medinet_central.chunks denormalized read replica per D-V3-02). Hub con
# request endpoint nay → 404 NOT_FOUND envelope D6 qua Starlette HTTPException
# handler (Plan 02-03 carry forward).
cross_hub_router = APIRouter(prefix="/api/search", tags=["search-central"])


def get_search_service(request: Request) -> SearchService:
    """DI factory — SearchService cần asyncpg pool + redis từ `app.state`.

    Search dùng raw vector SQL (`<=>` + `SET LOCAL hnsw.*`) → cần asyncpg pool,
    KHÔNG AsyncSession. `redis` có thể None (cache fail-open). `pool` None →
    `RuntimeError` → ErrorHandlerMiddleware map 500 envelope (pool down = service
    unavailable thực sự — chấp nhận M2).
    """
    pool = getattr(request.app.state, "db_pool", None)
    redis = getattr(request.app.state, "redis", None)
    if pool is None:
        raise RuntimeError("db_pool chưa sẵn sàng — search không khả dụng")
    return SearchService(pool=pool, redis=redis)


@router.post("")
@limiter.limit(SEARCH_LIMIT)
async def search_endpoint(
    request: Request,
    body: SearchRequest,
    user: UserWithHubs = Depends(get_api_key_or_jwt_with_hubs),  # noqa: B008
    service: SearchService = Depends(get_search_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/search — union vector search (SEARCH-01 / SEARCH-02).

    Universal mount (central + hub con). Hub con dùng local DB
    `medinet_hub_<name>` cho local single-hub search.
    """
    _ = request  # slowapi đọc; auth gate qua get_api_key_or_jwt_with_hubs.
    try:
        result = await service.search(body=body, user=user)
    except ValueError as e:
        return resp.bad_request(message=str(e), code="INVALID_QUERY")
    except EmbedderError as e:
        return resp.internal_error(message=f"Embedding lỗi: {e}", code="EMBEDDING_FAILED")
    return resp.ok(data=result)


@cross_hub_router.post("/cross-hub")
@limiter.limit(SEARCH_LIMIT)
async def cross_hub_search_endpoint(
    request: Request,
    body: SearchRequest,
    user: UserWithHubs = Depends(get_api_key_or_jwt_with_hubs),  # noqa: B008
    service: SearchService = Depends(get_search_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/search/cross-hub — 1 SQL aggregated WHERE hub_id = ANY (SEARCH-03).

    Phase 4 Plan 04-05 (SYNC-03 / D-V3-Phase4-D1 refactor + D-V3-Phase4-D3 strip).
    Central-only mount — `main.py` include router này trong block
    `if settings.hub_name == "central"`. Hub con strip → 404 NOT_FOUND envelope
    D6 (FACTOR-02 extend).

    Public API `SearchService.search_cross_hub()` signature giữ NGUYÊN — backward
    compat M2 contract (ask_service.py consumer + frontend api.ts crossHubSearch).
    """
    _ = request
    try:
        result = await service.search_cross_hub(body=body, user=user)
    except ValueError as e:
        return resp.bad_request(message=str(e), code="INVALID_QUERY")
    except EmbedderError as e:
        return resp.internal_error(message=f"Embedding lỗi: {e}", code="EMBEDDING_FAILED")
    return resp.ok(data=result)


@router.post("/similar")
@limiter.limit(SEARCH_LIMIT)
async def find_similar_endpoint(
    request: Request,
    body: SimilarRequest,
    user: UserWithHubs = Depends(get_api_key_or_jwt_with_hubs),  # noqa: B008
    service: SearchService = Depends(get_search_service),  # noqa: B008
) -> JSONResponse:
    """POST /api/search/similar — find-similar (D-04).

    Universal mount (central + hub con). Local single-hub similar search.
    """
    _ = request
    try:
        result = await service.find_similar(body=body, user=user)
    except ValueError as e:
        return resp.bad_request(message=str(e), code="INVALID_QUERY")
    except EmbedderError as e:
        return resp.internal_error(message=f"Embedding lỗi: {e}", code="EMBEDDING_FAILED")
    return resp.ok(data=result)
