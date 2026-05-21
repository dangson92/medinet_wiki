# Phase 6: Search API Single + Cross-Hub - Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 9 (4 new, 5 modified)
**Analogs found:** 9 / 9

> Mọi đường dẫn dưới đây tương đối với `Hub_All/api/`. Codebase Python FastAPI layered: router → service → repository → raw SQL.

## File Classification

| New/Modified File | New/Mod | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|---------|------|-----------|----------------|---------------|
| `app/routers/search.py` | NEW | router | request-response | `app/routers/audit_logs.py` (slowapi) + `app/routers/documents.py` (DI/envelope) | role-match |
| `app/services/search_service.py` | NEW | service | request-response + transform | `app/services/documents_service.py` (raw SQL) + `app/services/rag_config_service.py` (asyncpg pool) | role-match |
| `app/schemas/search.py` | NEW | schema | — | `app/schemas/rag_config.py` (request) + `app/schemas/documents.py` (response) | exact |
| `app/repositories/search_repo.py` (optional) | NEW | repository | request-response | `app/repositories/hub_isolation.py` | partial |
| `app/services/documents_service.py` | MOD | service | event-driven (Pub/Sub publish) | self (existing upload/delete paths) | exact |
| `app/main.py` | MOD | config | — | self (`create_app()` router mount + lifespan task) | exact |
| `app/routers/__init__.py` | MOD | config | — | self (barrel export) | exact |
| `app/schemas/__init__.py` | MOD | config | — | self (barrel export) | exact |
| `tests/integration/test_search_hub_isolation.py` (hoặc `test_search.py`) | NEW | test | — | `tests/integration/test_hub_isolation.py` | exact |

## Pattern Assignments

### `app/routers/search.py` (router, request-response)

**Analog chính:** `app/routers/audit_logs.py` (slowapi `@limiter.limit` decoration + envelope) — đây là router DUY NHẤT trong codebase đã decorate slowapi và chạy thật. `app/routers/documents.py` cho pattern `get_*_service` DI factory.

**Imports pattern** (`audit_logs.py:24-41`, `documents.py:26-62`):
```python
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user           # viewer+ → JWT bắt buộc (D-specifics auth)
from app.db.session import get_session
from app.middleware import SEARCH_LIMIT, limiter             # SEARCH_LIMIT = "100/minute" (D-13)
from app.models.auth import User
from app.pkg import response as resp
from app.schemas.search import SearchRequest, SimilarRequest
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])
```

**DI factory pattern** (`documents.py:68-72`):
```python
def get_search_service(
    db: AsyncSession = Depends(get_session),  # noqa: B008
) -> SearchService:
    return SearchService(db=db)
```
> LƯU Ý: search query CẦN asyncpg pool (raw SQL `<=>` vector + `SET LOCAL hnsw.*`) — KHÔNG chỉ AsyncSession. Pool nằm ở `request.app.state.db_pool` (xem `main.py:72`). Service nên nhận thêm `pool` + `redis` từ `request.app.state` qua dependency tương tự `get_redis` (`auth/dependencies.py:51-53`). Planner quyết: hoặc factory đọc `request.app.state.db_pool`/`request.app.state.redis`, hoặc inject 2 dependency riêng.

**slowapi rate-limit decoration** (`audit_logs.py:50-53, 72`) — D-13 (`@limiter.limit("100/minute")`):
```python
@router.post("")
@limiter.limit(SEARCH_LIMIT)                    # decorator SÁT def — slowapi yêu cầu gần function nhất
async def search(
    request: Request,                           # BẮT BUỘC param `request: Request` (KHÔNG Depends) — slowapi đọc
    body: SearchRequest,
    user: User = Depends(get_current_user),     # noqa: B008
    service: SearchService = Depends(get_search_service),  # noqa: B008
) -> JSONResponse:
    _ = request                                 # slowapi đọc; user gate qua get_current_user
    result = await service.search(body=body, user=user, request=request)
    return resp.ok(data=result)
```
> 3 endpoint POST: `""` (`/api/search`), `"/cross-hub"`, `"/similar"`. Cả 3 decorate `@limiter.limit(SEARCH_LIMIT)`. `SEARCH_LIMIT` đã export sẵn ở `app/middleware/__init__.py` (`rate_limit.py:64`).

**Envelope response** — D6 shape `{success, data, error, meta}`:
- Success: `return resp.ok(data=search_response_dict)` (`pkg/response.py:40-42`). `data` = `SearchResponseAPI` shape.
- Validation lỗi UUID hub_id: `resp.bad_request(message=..., code="INVALID_HUB_ID")` (pattern `documents.py:108-113`).
- HubIsolationError: KHÔNG cần catch ở router — handler global đã có (`main.py:405-420`) map → 403 envelope. NHƯNG theo D-07 search KHÔNG raise HubIsolationError mà SILENT-DROP hub không có quyền (intersect, không reject). Chỉ raise nếu planner chọn reject-explicit.

> Endpoint `POST /api/search/answer` KHÔNG build (Phase 7) — sẽ vẫn 404.

---

### `app/services/search_service.py` (service, request-response + transform)

**Analog chính:** `app/services/documents_service.py` (raw SQL parametrized + `_row_to_response` mapper + `WHERE` builder) và `app/services/rag_config_service.py` (asyncpg pool `pool.acquire()` + `conn.fetch`).

**Imports pattern** (`documents_service.py:31-59`, `rag_config_service.py:14-29`):
```python
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import time
from typing import Any
from uuid import UUID

from app.repositories.hub_isolation import HubIsolationError  # D-07 — defense in depth
from app.schemas.search import SearchRequest, SearchResultItem, SearchResponse
from app.services.embedder import embed_text, EMBEDDING_DIM   # D-09 — query embed dim 1536

logger = logging.getLogger(__name__)
```

**Service class shape** (`documents_service.py:100-109`, `rag_config_service.py:146-150`):
```python
class SearchService:
    def __init__(self, db: AsyncSession, pool: Any = None, redis: Any = None) -> None:
        self.db = db
        self.pool = pool        # asyncpg pool cho raw vector SQL
        self.redis = redis      # cache SEARCH-04
```

**Query embedding** (D-09) — `app/services/embedder.py:46`:
```python
from app.services.embedder import embed_text
query_vector: list[float] = await embed_text(body.query)   # list[float] length 1536 (EMBEDDING_DIM PIN)
```
> `embed_text` raise `EmbedderError` (`embedder.py:38-43`) nếu LiteLLM fail / dim sai, và `ValueError` nếu text rỗng. Service catch → map 400/502 envelope hoặc để bubble lên.

**Raw vector SQL qua asyncpg pool + HNSW session tuning** (D-08, D-09) — pattern `pool.acquire()` từ `rag_config_service.py:312-314` + `main.py:436-437`:
```python
async with self.pool.acquire() as conn:
    async with conn.transaction():                       # SET LOCAL cần transaction (D-08)
        await conn.execute("SET LOCAL hnsw.ef_search = 200")
        await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        await conn.execute("SET LOCAL hnsw.max_scan_tuples = 20000")
        rows = await conn.fetch(
            """
            SELECT c.id, c.document_id, c.hub_id, c.content, c.heading_path,
                   c.metadata, d.filename, d.updated_at, h.name AS hub_name,
                   1 - (c.vector <=> $1) AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            JOIN hubs h ON h.id = c.hub_id
            WHERE c.hub_id = ANY($2::uuid[]) AND c.vector IS NOT NULL
            ORDER BY c.vector <=> $1
            LIMIT $3
            """,
            vector_param, allowed_hub_ids, top_k,
        )
```
> Cột THẬT (migration 0001 — `0001_initial_schema.py`): `chunks(id, document_id, hub_id, content, content_hash, heading_path, page_start, page_end, vector Vector(1536), metadata, created_at)`, `documents(id, hub_id, uploaded_by, filename, file_path, mime_type, file_size_bytes, status, ..., updated_at)`, `hubs(id, slug, code, name, subdomain, description, status, is_active, ..., updated_at)`. JOIN lấy `documents.filename`→`title`, `documents.updated_at`, `hubs.name`→`hub_name` (D-10). `category`/`tags` KHÔNG có cột → trả `null`/`[]`.
> **CHÚ Ý — sai tên index trong CONTEXT:** CONTEXT.md D-09 ghi index `chunks_vector_hnsw`; tên THẬT trong migration là **`ix_chunks_vector_hnsw`** (`0001_initial_schema.py:361`, `vector_cosine_ops`). Verification `EXPLAIN ANALYZE` phải khớp tên này.
> Vector param: `documents_service` toàn dùng SQLAlchemy `text()` bind params; KHÔNG có precedent asyncpg pgvector codec trong codebase. Planner discretion (D-09) — đơn giản nhất truyền pgvector literal string `'[0.1,0.2,...]'` cast `$1::vector`.

**Hub isolation defense in depth** (D-07) — `app/repositories/hub_isolation.py:33-57`:
```python
from app.repositories.hub_isolation import hub_filter_clause
# Lấy user hub_ids từ DB user_hubs (KHÔNG tin payload) — pattern get_current_user_with_hubs.
# Intersect: allowed = set(request.hub_ids or all_assigned) ∩ set(user_assigned_hub_ids)
# admin → bypass (search mọi hub). editor/viewer → CHỈ hub được assign.
```
> `hub_filter_clause()` sinh fragment cho SQLAlchemy `text()` named params (`hub_id IN (:uh0,...)`); search dùng asyncpg positional `$N` + `= ANY($2)`. Planner: hoặc adapt `hub_filter_clause`, hoặc tự intersect list `hub_ids` rồi pass thẳng vào `= ANY($2)`. Logic intersect THEN query là điểm cốt lõi — hub user không quyền bị loại TRƯỚC khi vào SQL.

**WHERE builder + parametrize an toàn** (chống SQL injection) — `documents_service.py:272-288` cho `min_score` filter (D-14): build clause động, bind params, KHÔNG f-string nội dung user.

**Cross-hub fan-out** (D-06) — `asyncio.gather` per-hub, pattern `asyncio` đã import sẵn ở `documents_service.py:33`:
```python
results_per_hub = await asyncio.gather(
    *[self._search_one_hub(hub_id, query_vector, top_k) for hub_id in allowed_hub_ids]
)
# aggregate + re-rank theo score → global top_k
```

**Redis cache** (SEARCH-04, D-11) — pattern Redis từ `app.state.redis` (`main.py:84-87`), `redis.asyncio` API:
```python
cache_key = "search:" + hashlib.sha256(
    f"{body.query}|{sorted(hub_ids)}|{top_k}|{min_score}".encode()
).hexdigest()
cached = await self.redis.get(cache_key)            # decode_responses=True (main.py:85)
if cached is not None:
    result = json.loads(cached); result["cache_hit"] = True; return result
# ... query ...
await self.redis.set(cache_key, json.dumps(result), ex=300)   # TTL 300s
```
> Redis có thể None (fail-open — `auth/dependencies.py:51-53` precedent). Cache CHỈ `/api/search` + `/api/search/cross-hub`, KHÔNG `/api/search/similar`.

**Logging** — `documents_service.py:220-226` pattern: `logger.info("search_completed", ...)` structured fields (CONVENTIONS §5).

**Timing** — `query_time_ms` đo bằng `time.perf_counter()` quanh embed+query.

---

### `app/schemas/search.py` (schema)

**Analog:** `app/schemas/rag_config.py` (request — all-optional partial body) + `app/schemas/documents.py` (response — `Literal` enum + derive fields).

**Source of truth:** `frontend/src/services/api.ts:490-522` (D6 — contract thắng ROADMAP/REQUIREMENTS).

**Request schema** (`rag_config.py:11-24` pattern — `from __future__`, `BaseModel`, optional fields):
```python
from __future__ import annotations
from pydantic import BaseModel

class SearchFilters(BaseModel):
    categories: list[str] | None = None         # D-14 accept-but-noop M2
    tags: list[str] | None = None               # D-14 accept-but-noop M2
    date_from: str | None = None
    date_to: str | None = None

class SearchRequest(BaseModel):                  # = SearchRequestAPI api.ts:490
    query: str                                   # D-02 — field tên `query` KHÔNG `q`
    hub_ids: list[str] | None = None
    top_k: int | None = None
    min_score: float | None = None
    filters: SearchFilters | None = None

class SimilarRequest(BaseModel):                 # api.ts:221 findSimilar body
    content: str
    hub_id: str | None = None
    threshold: float | None = None
```

**Response schema** (`documents.py:60-80` pattern — `BaseModel`, exact field names match frontend):
```python
class SearchResultItem(BaseModel):               # = SearchResultAPI api.ts:498
    id: str
    hub_id: str
    hub_name: str
    title: str
    snippet: str                                 # content truncate ~300 char word-boundary (D-10)
    content: str | None = None                   # optional — full content
    category: str | None = None                  # D-10 — M2 luôn null
    tags: list[str] = []                          # D-10 — M2 luôn []
    score: float
    raw_similarity: float                         # = score (M2 chưa rerank — D-10)
    updated_at: str | None = None
    source: str                                   # hằng "document" (D-10)

class SearchResponse(BaseModel):                  # = SearchResponseAPI api.ts:513
    results: list[SearchResultItem]
    total_hubs_searched: int
    query_time_ms: int
    cache_hit: bool

class SimilarMatch(BaseModel):                    # api.ts:521
    page_id: str
    page_title: str
    similarity_score: float
    hub_name: str

class SimilarResponse(BaseModel):
    matches: list[SimilarMatch]
```
> Router trả qua `resp.ok(data=resp_model.model_dump(mode="json"))` — pattern `documents.py:190`.

---

### `app/repositories/search_repo.py` (optional — repository)

**Analog:** `app/repositories/hub_isolation.py` — module-level pure functions, KHÔNG class; `from __future__ import annotations` only import.

> Discretion (D-`Claude's Discretion`). Nếu tách: đặt raw vector SQL builder + `hub_filter` adapter ở đây giữ service mỏng. Nếu KHÔNG tách (codebase hiện CHỈ có `hub_isolation.py` trong `repositories/` — phần lớn service tự embed SQL như `documents_service.py`), giữ SQL trong service là consistent với precedent hiện tại. Khuyến nghị: KHÔNG tạo repo riêng trừ khi SQL phức tạp — match `documents_service.py` (SQL inline trong service).

---

### `app/services/documents_service.py` (MODIFIED — wire Pub/Sub invalidate)

**Analog:** chính file này — thêm publish vào các path mutation.

**D-12 — publish Redis Pub/Sub channel `hub:{hub_id}:invalidate`** khi document thay đổi:
- Điểm wire: `create()` (sau `await self.db.commit()` line 219), `delete()` (sau DELETE line 386). Reupload/content-edit chưa có path riêng trong file hiện tại — chỉ create + delete tồn tại.
- `DocumentService.__init__` hiện CHỈ nhận `db` + `file_store` (line 103-109). Cần thêm `redis` param hoặc lấy lazy. Pattern Redis: `redis.asyncio` client từ `app.state.redis`.
- Publish best-effort — KHÔNG raise nếu Redis down (precedent fail-open `auth/dependencies.py:51-53`; precedent best-effort `documents_service.py:407-410` file unlink):
```python
if self.redis is not None:
    try:
        await self.redis.publish(f"hub:{hub_id}:invalidate", "1")
    except Exception as e:  # noqa: BLE001 — best-effort, KHÔNG raise
        logger.warning("hub_invalidate_publish_failed: %s", e)
```
> Subscriber chạy ở đâu (asyncio task lifespan vs lazy) — planner discretion (CONTEXT). Pattern asyncio task trong lifespan đã có precedent: `watchdog_task` (`main.py:203-212`) + `audit_task` (`main.py:217-222`) — `app.state.X_task = asyncio.create_task(...)` + cancel ở shutdown (`main.py:230-255`).
> Cache invalidation key scheme (hub-tag set vs namespaced key `search:{hub_id}:...`) — planner discretion (D-12). Đơn giản-hoá M2 OK miễn upload mới → search lần sau không stale.

---

### `app/main.py` (MODIFIED — mount router + optional Pub/Sub subscriber task)

**Analog:** chính file này.

**Mount search router** — pattern `create_app()` line 332-349:
```python
from app.routers import search_router          # thêm vào import block hiện có
app.include_router(search_router)
```

**Optional — Pub/Sub subscriber lifespan task** (nếu planner chọn task-in-lifespan, D-12): APPEND-ONLY sau audit task — pattern `main.py:203-222` (`asyncio.create_task` + `app.state.X_task`), cancel ở `finally` block `main.py:230-255`.

> KHÔNG cần thêm exception handler — `HubIsolationError` handler (`main.py:405-420`) + `HTTPException` handler (`main.py:376-400`) + `RateLimitExceeded` handler (`main.py:363-366`) đã wire sẵn từ Phase 5. Search dùng lại nguyên.

---

### `app/routers/__init__.py` + `app/schemas/__init__.py` (MODIFIED — barrel exports)

**Analog:** chính 2 file (`routers/__init__.py:1-27`, `schemas/__init__.py:1-17`).

`routers/__init__.py` — thêm dòng import + `__all__` entry:
```python
from app.routers.search import router as search_router
# ... thêm "search_router" vào __all__
```
`schemas/__init__.py` — export `SearchRequest, SearchResponse, SearchResultItem, SimilarRequest, SimilarResponse, SearchFilters, SimilarMatch` + thêm vào `__all__`.

---

### `tests/integration/test_search_hub_isolation.py` (NEW — test)

**Analog:** `tests/integration/test_hub_isolation.py` — E4 critical suite, đây là template chính xác cho hub-isolation test của search.

**Test file structure** (`test_hub_isolation.py:1-33`):
```python
from __future__ import annotations
import asyncio, io, uuid
from pathlib import Path
from typing import Any
import httpx, pytest
from sqlalchemy import text
from tests.integration.conftest import _assign_user_hub, _insert_hub
```

**Markers** (`test_hub_isolation.py:95-97`) — CONVENTIONS §1 + ROADMAP SC:
```python
@pytest.mark.critical          # CI gate `pytest -m critical`
@pytest.mark.integration
@pytest.mark.asyncio
async def test_viewer_hub_a_cannot_see_chunk_hub_b(...): ...
```

**Fixtures dùng lại từ conftest** (`conftest.py`): `app_with_auth`, `auth_client`, `admin_user`/`editor_user`/`viewer_user`, `admin_token`/`editor_token`/`viewer_token`, helpers `_insert_hub(name, code, subdomain)`, `_assign_user_hub(user_id, hub_id)`. KHÔNG redeclare.

**Critical test (Specifics + CONVENTIONS §1 Search row):** viewer Hub A search với explicit `hub_ids:[A,B]` → results CHỈ chứa chunk Hub A:
```python
@pytest.mark.critical
@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_cross_hub_isolation(
    auth_client, admin_token, viewer_token, viewer_user, app_with_auth, ...
):
    hub_a = await _insert_hub(name="Hub A", code="hub-a", subdomain="hub-a")
    hub_b = await _insert_hub(name="Hub B", code="hub-b", subdomain="hub-b")
    await _assign_user_hub(user_id=viewer_user["id"], hub_id=hub_a)
    # ... seed chunks vào cả 2 hub (INSERT chunks trực tiếp + vector) ...
    r = await auth_client.post(
        "/api/search",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"query": "...", "hub_ids": [hub_a, hub_b]},  # explicit B — phải bị loại
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert all(res["hub_id"] == hub_a for res in body["data"]["results"]), \
        "E4 VIOLATION — viewer Hub A thấy chunk Hub B"
```
> Seed chunks cần `vector` non-NULL — INSERT trực tiếp qua engine giống `conftest._insert_*` helpers (cần seed dataset trong `Hub_All/.planning/seeds/` — thư mục đã tồn tại trong git status). Empty-result case (`results: []`, KHÔNG lỗi) cũng cần 1 test (Specifics).
> Cache test: `cache_hit=false` lần 1, `true` lần 2 (SEARCH-04). Rate-limit test có thể tham khảo `tests/integration/test_rate_limit.py`.

## Shared Patterns

### Authentication (JWT viewer+)
**Source:** `app/auth/dependencies.py:84-144` (`get_current_user`)
**Apply to:** Cả 3 endpoint search router — `user: User = Depends(get_current_user)`. KHÔNG dùng `require_role` (viewer trở lên đều search được — Specifics). Để lấy hub assignments cho isolation, dùng `get_current_user_with_hubs` (`dependencies.py:205-219`) trả `UserWithHubs(user, hub_ids)` — `hub_ids` từ DB `user_hubs`, KHÔNG tin payload.

### Hub Isolation — defense in depth (D-07, EXIT E4)
**Source:** `app/repositories/hub_isolation.py:33-82` (`hub_filter_clause`, `verify_hub_access`)
**Apply to:** `search_service.py` — intersect `request.hub_ids` với hub user được assign TRƯỚC khi vào SQL. admin bypass (search mọi hub). Khác delete: search KHÔNG raise reject mà SILENT-DROP hub thiếu quyền (D-07 — viewer request `[A,B,C]` chỉ assign A → search A). SQL `WHERE hub_id = ANY($N)` là lớp 2, intersect ở service là lớp 1.

### Response Envelope (D6 shape)
**Source:** `app/pkg/response.py:40-160` — `resp.ok()`, `resp.bad_request()`, `resp.forbidden()`
**Apply to:** Mọi response search router. `{success, data, error, meta}` shape-identical kể cả 401/403/422/429 (handler global `main.py:363-420`). `data` = `SearchResponseAPI`/`SimilarResponseAPI` dict. Error code UPPER_SNAKE_CASE.

### Rate Limit (D-13, AUX-03)
**Source:** `app/middleware/rate_limit.py:56-66` (`limiter`, `SEARCH_LIMIT`) + `app/routers/audit_logs.py:50-72` (decoration pattern)
**Apply to:** Cả 3 endpoint search. `@limiter.limit(SEARCH_LIMIT)` SÁT def (dưới `@router.post`), endpoint function PHẢI có param `request: Request` (KHÔNG Depends). `SEARCH_LIMIT` = `"{rate_limit_search_per_minute}/minute"` (mặc định 100/min). `limiter` đã wire `app.state.limiter` + handler `RateLimitExceeded` ở `main.py:355-366` — KHÔNG cần wire lại.

### Raw SQL + asyncpg Pool
**Source:** `app/services/rag_config_service.py:305-317` (`pool.acquire()` + `conn.fetch`), `app/main.py:436-437` (`db_pool.acquire()`)
**Apply to:** `search_service.py` vector query. Pool ở `request.app.state.db_pool` (asyncpg, init `main.py:72-77`). asyncpg dùng positional `$1, $2` (KHÁC SQLAlchemy `text()` named `:param` của `documents_service.py`). `SET LOCAL hnsw.*` (D-08) cần `async with conn.transaction()`.

### Redis Client
**Source:** `app/main.py:84-87` (init `redis.asyncio.from_url(..., decode_responses=True)`), `app/auth/dependencies.py:51-53` (`get_redis` fail-open)
**Apply to:** `search_service.py` cache + `documents_service.py` Pub/Sub publish. Client ở `request.app.state.redis`, có thể None (fail-open — KHÔNG crash). `decode_responses=True` → `redis.get()` trả `str`.

## No Analog Found

| File / Concern | Reason |
|------|--------|
| Redis Pub/Sub subscriber loop | Codebase CHƯA có Pub/Sub subscriber. Có precedent asyncio background task (`watchdog_loop`, `audit_flush_loop` — `main.py:203-222`) cho lifecycle, nhưng pattern `pubsub.subscribe()` + listen loop là MỚI. Planner thiết kế từ `redis.asyncio` API + reuse asyncio-task-trong-lifespan pattern. |
| `SET LOCAL hnsw.*` trên asyncpg pool | Chưa có precedent set session config trên asyncpg connection. Pattern `pool.acquire()` + `conn.execute()` có sẵn (`rag_config_service.py:312`); ghép `conn.transaction()` + `SET LOCAL` là tổ hợp mới — D-08 đã mô tả rõ cách áp. |
| pgvector `<=>` operator + vector param binding | Chưa có raw vector search SQL nào trong codebase Python (`embedder.py` chỉ embed, cocoindex tự INSERT vector lúc index). D-09 cung cấp SQL template; planner chọn cách bind vector param (literal `$1::vector` khuyến nghị — không có pgvector codec precedent). |

## Metadata

**Analog search scope:** `Hub_All/api/app/routers/`, `app/services/`, `app/schemas/`, `app/repositories/`, `app/middleware/`, `app/pkg/`, `app/auth/`, `tests/integration/`, `migrations/versions/0001_initial_schema.py`, `frontend/src/services/api.ts`
**Files scanned:** ~20
**Pattern extraction date:** 2026-05-18
**Index name correction:** CONTEXT.md D-09 ghi `chunks_vector_hnsw` — tên THẬT là `ix_chunks_vector_hnsw` (`0001_initial_schema.py:361`). Verification `EXPLAIN ANALYZE` phải dùng tên đúng.
