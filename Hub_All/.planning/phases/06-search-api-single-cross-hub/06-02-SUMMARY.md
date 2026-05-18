---
phase: 06-search-api-single-cross-hub
plan: 02
subsystem: search
tags: [fastapi-router, slowapi, asyncio-gather, cross-hub, redis-cache, hub-isolation]

# Dependency graph
requires:
  - phase: 06-search-api-single-cross-hub
    provides: "06-01 — app/schemas/search.py (7 model) + SearchService.search() + helper module-level (_run_vector_query/_row_to_item/intersect_hubs/_cache_key/_resolve_top_k)"
  - phase: 05-hub-user-audit-apikey-settings-crud
    provides: "get_current_user_with_hubs (UserWithHubs) + slowapi limiter + SEARCH_LIMIT + HubIsolationError/RateLimitExceeded handler"
  - phase: 04-cocoindex-flow-mvp
    provides: "embed_text() + EmbedderError — query embedding dim 1536"
provides:
  - "app/services/search_service.py — search_cross_hub() fan-out asyncio.gather + re-rank + find_similar()"
  - "app/routers/search.py — 3 endpoint POST /api/search, /api/search/cross-hub, /api/search/similar"
  - "search router mounted vào create_app() — 3 endpoint reachable, decorate @limiter.limit(SEARCH_LIMIT)"
affects: [06-03, 06-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cross-hub fan-out: asyncio.gather(*[_search_one(h) for h in hub_ids]) per-hub rồi aggregate + sort(reverse=True) re-rank"
    - "Cache namespace tách: search:cross: cho cross-hub vs search: cho single-hub — 06-03 invalidation chung prefix search:"
    - "DI factory đọc request.app.state.db_pool + request.app.state.redis (raw vector SQL cần asyncpg pool, KHÔNG AsyncSession)"
    - "slowapi @limiter.limit(SEARCH_LIMIT) sát def + endpoint param request: Request (KHÔNG Depends)"

key-files:
  created:
    - "api/app/routers/search.py"
  modified:
    - "api/app/services/search_service.py"
    - "api/app/routers/__init__.py"
    - "api/app/main.py"

key-decisions:
  - "D-06 — search_cross_hub fan-out song song mỗi hub qua asyncio.gather, mỗi hub top_k riêng, aggregate + re-rank score desc → global top-k"
  - "D-06 — admin không filter: query SELECT id FROM hubs WHERE is_active = TRUE để có danh sách hub fan-out (predicate NHẤT QUÁN branch admin-all _run_vector_query 06-01)"
  - "D-11 — cache cross-hub namespace search:cross:<sha256> tách khỏi single-hub search:; find_similar KHÔNG cache"
  - "D-04 — find_similar không có REQ-ID (addition Phase 6 phục vụ frontend), threshold filter mặc định 0.0, top_k = DEFAULT_TOP_K"
  - "D-13 — cả 3 endpoint decorate @limiter.limit(SEARCH_LIMIT) 100/min/user"
  - "Router map ValueError → 400 INVALID_QUERY, EmbedderError → 500 EMBEDDING_FAILED"

patterns-established:
  - "search_cross_hub/find_similar unpack tuple (rows, _) từ _run_vector_query — chỉ lấy rows"
  - "_cross_cache_key tách namespace cache cross-hub khỏi single-hub"
  - "noqa C901 cho method chuỗi step phẳng — nhất quán precedent main.py lifespan + rag_config_service.update_config"

requirements-completed: [SEARCH-01, SEARCH-02, SEARCH-03]

# Metrics
duration: 3min
completed: 2026-05-18
---

# Phase 6 Plan 02: Search Endpoint Layer — Cross-Hub Fan-out + Router Mount Summary

Hoàn thiện search endpoint layer: thêm `search_cross_hub()` (fan-out
`asyncio.gather` per-hub + re-rank theo score — SEARCH-03 / D-06) và
`find_similar()` (D-04) vào `SearchService`; tạo `app/routers/search.py` với 3
endpoint POST khớp `api.ts` 1:1; mount router vào `create_app()`. Sau plan, 3
endpoint frontend gọi (`search`, `crossHubSearch`, `findSimilar`) reachable và
rate-limited. Cache invalidation Pub/Sub là 06-03.

## Tasks hoàn thành

| Task | Tên | Commit | Files |
|------|-----|--------|-------|
| 1 | Thêm search_cross_hub() + find_similar() vào SearchService | `6e5f1c9` | `api/app/services/search_service.py` |
| 2 | Tạo app/routers/search.py — 3 POST endpoint + mount create_app() | `00cb5c9` | `api/app/routers/search.py` (mới), `api/app/routers/__init__.py`, `api/app/main.py` |

## Chi tiết thực thi

### Task 1 — `app/services/search_service.py` (extend)

EXTEND `SearchService` (KHÔNG ghi đè) — thêm `import asyncio`, mở rộng import
schema (`SimilarMatch`/`SimilarRequest`/`SimilarResponse`), helper module-level
`_cross_cache_key`, và 2 method:

- **`search_cross_hub()`** (SEARCH-03 / D-06): resolve top_k → `intersect_hubs`
  → branch admin-all `SELECT id FROM hubs WHERE is_active = TRUE` (predicate
  NHẤT QUÁN 06-01) → empty-result sớm nếu `hub_ids` rỗng → cache đọc namespace
  `search:cross:` (fail-open) → embed query 1 lần → fan-out per-hub qua
  `asyncio.gather(*[_search_one(h) for h in hub_ids])` (`_search_one` unpack
  tuple `(rows, _)` chỉ lấy `rows`) → aggregate `all_rows` + `sort(key=score,
  reverse=True)` re-rank → `_row_to_item` top-k → min_score filter (D-14) →
  `SearchResponse` với `total_hubs_searched = len(hub_ids)` → cache ghi
  (fail-open) → log `cross_hub_search_completed`.
- **`find_similar()`** (D-04, KHÔNG cache D-11): `top_k = DEFAULT_TOP_K` →
  hub scope từ `body.hub_id` → `intersect_hubs` → empty-result sớm cho
  non-admin chưa assign → embed `content` → `_run_vector_query` unpack
  `(rows, _)` → threshold filter (mặc định 0.0) → map `SimilarMatch`
  (`page_id`=document_id, `page_title`=filename, `similarity_score`=score,
  `hub_name`) → `SimilarResponse`.

### Task 2 — `app/routers/search.py` (mới) + mount

- **`app/routers/search.py`** mới — `router = APIRouter(prefix="/api/search")`,
  DI factory `get_search_service` đọc `request.app.state.db_pool` +
  `request.app.state.redis` (`RuntimeError` nếu pool None → 500 envelope qua
  ErrorHandlerMiddleware), 3 endpoint POST: `""` (`search`), `/cross-hub`
  (`search_cross_hub`), `/similar` (`find_similar`). Cả 3 decorate
  `@limiter.limit(SEARCH_LIMIT)` sát def, có param `request: Request`. Envelope:
  `ValueError → 400 INVALID_QUERY`, `EmbedderError → 500 EMBEDDING_FAILED`,
  success → `resp.ok(data=result)`.
- **`app/routers/__init__.py`** — thêm `search_router` import + `__all__`
  (giữ alphabet).
- **`app/main.py`** — `create_app()` mount block: `from app.routers import
  search_router` + `app.include_router(search_router)` sau `rag_config_router`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Thêm `# noqa: C901` cho `search_cross_hub`**
- **Found during:** Task 1 verification
- **Issue:** ruff báo `C901 search_cross_hub is too complex (11 > 10)`. Method
  là chuỗi 12 step phẳng (resolve → intersect → admin-all → empty-guard → cache
  đọc → embed → fan-out → aggregate → re-rank → min_score → cache ghi → log);
  độ phức tạp đến từ các nhánh try/except cache fail-open chứ không phải logic
  rẽ nhánh thực sự.
- **Fix:** Thêm `# noqa: C901 — chuỗi step fan-out + cache phẳng` ngay tại
  signature. NHẤT QUÁN precedent codebase: `main.py:59` lifespan, `main.py:290`
  `create_app`, `rag_config_service.py:185` `update_config` — đều dùng
  `noqa: C901` cho method chuỗi step linear.
- **Files modified:** `api/app/services/search_service.py`
- **Commit:** `6e5f1c9`

### Lưu ý — false positive grep (KHÔNG phải deviation)

Acceptance criterion `grep -c "@limiter.limit(SEARCH_LIMIT)"` trả 4 thay vì 3:
3 là decorator thực tế (1/endpoint), 1 là docstring module nhắc tên decorator.
Tương tự `grep -c "request: Request"` trả 5 (3 endpoint + 1 DI factory + 1
docstring) — vượt ngưỡng `>=4`. Đây là false positive giống deviation #2 của
06-01 (docstring chứa literal grep target) — KHÔNG sửa vì docstring giải thích
pattern là hợp lý; số decorator/param THỰC TẾ đúng spec.

## Threat Model — kết quả

| Threat ID | Disposition | Trạng thái |
|-----------|-------------|-----------|
| T-06-02-01 (Spoofing — 3 endpoint) | mitigate | ✅ cả 3 endpoint `Depends(get_current_user_with_hubs)` — verify Bearer JWT, anonymous → 401; `hub_ids` lấy từ DB `user_hubs` KHÔNG payload |
| T-06-02-02 (Info Disclosure — cross-hub) | mitigate | ✅ `search_cross_hub` fan-out CHỈ trên `hub_ids` đã `intersect_hubs` — viewer Hub A request `[A,B,C]` chỉ fan-out hub được assign |
| T-06-02-03 (Elevation of Privilege — admin-all) | mitigate | ✅ branch `SELECT id FROM hubs WHERE is_active = TRUE` CHỈ kích hoạt khi `user.user.role == "admin"`; editor/viewer luôn qua `intersect_hubs` |
| T-06-02-04 (DoS — 3 endpoint) | mitigate | ✅ `@limiter.limit(SEARCH_LIMIT)` 100/min/user cả 3 — vượt → 429 envelope (handler Phase 5) |
| T-06-02-05 (DoS — cross-hub fan-out) | accept | ✅ `asyncio.gather` N hub song song, N giới hạn bởi số hub user assign (≤10 thực tế) — chấp nhận M2 |

## Verification

- `uv run ruff check app/services/search_service.py app/routers/search.py app/routers/__init__.py app/main.py` — exit 0
- `uv run mypy --strict app/services/search_service.py app/routers/search.py` — exit 0 (2 source)
- `create_app()` mount 3 path: `/api/search`, `/api/search/cross-hub`, `/api/search/similar` — assert PASS
- `grep -c "asyncio.gather"` = 4 (import + dùng + 2 docstring); `grep -c "reverse=True"` = 1 (re-rank score desc)
- `grep -c "status = 'active'"` = 0 (KHÔNG dùng predicate cột status — chỉ is_active)
- `search_cross_hub` admin-all branch dùng `SELECT id FROM hubs WHERE is_active = TRUE` — NHẤT QUÁN 06-01 ✅
- `git diff --diff-filter=D HEAD~2 HEAD` — rỗng (không xoá file ngoài ý muốn)

## Carry-over cho 06-03 / 06-04

- 06-03 wire Redis Pub/Sub invalidation: cache key 2 namespace `search:` (single)
  + `search:cross:` (cross) — subscriber xoá theo prefix `search:` chung khi
  document upload/edit/delete. `find_similar` KHÔNG cache → không cần invalidate.
- 06-04 integration test hub isolation: viewer Hub A POST `/api/search` +
  `/api/search/cross-hub` với explicit `hub_ids:[A,B]` → results CHỈ chunk Hub A.
  Cache test `cache_hit` false→true. Rate-limit test 429. Cần seed dataset chunk
  `vector` non-NULL (`Hub_All/.planning/seeds/`).

## Self-Check: PASSED

- `api/app/routers/search.py` — FOUND
- `api/app/services/search_service.py` — FOUND (modified)
- `api/app/routers/__init__.py` — FOUND (modified)
- `api/app/main.py` — FOUND (modified)
- Commit `6e5f1c9` — FOUND
- Commit `00cb5c9` — FOUND
