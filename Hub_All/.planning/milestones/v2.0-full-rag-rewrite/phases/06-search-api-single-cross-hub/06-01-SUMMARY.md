---
phase: 06-search-api-single-cross-hub
plan: 01
subsystem: search
tags: [pgvector, hnsw, asyncpg, redis-cache, pydantic, hub-isolation, embedding]

# Dependency graph
requires:
  - phase: 02-database-schema-alembic-baseline
    provides: "Schema chunks/documents/hubs + HNSW index ix_chunks_vector_hnsw (vector_cosine_ops)"
  - phase: 04-cocoindex-flow-mvp
    provides: "embed_text() — query embedding dim 1536 PIN (LiteLLM hot-swap)"
  - phase: 05-hub-user-audit-apikey-settings-crud
    provides: "hub_isolation.py (HubIsolationError) + get_current_user_with_hubs (UserWithHubs)"
provides:
  - "app/schemas/search.py — 7 Pydantic model contract khớp api.ts 1:1 (SearchRequest/Response/ResultItem/Filters/SimilarRequest/SimilarMatch/SimilarResponse)"
  - "app/services/search_service.py — SearchService.search() single-hub union vector search + HNSW tuning + Redis cache"
  - "intersect_hubs() — defense in depth lớp 1 (D-07 silent-drop hub không quyền)"
  - "Helper dùng chung 06-02: _to_pgvector_literal/_truncate_snippet/_cache_key/_resolve_top_k/_row_to_item/_run_vector_query"
affects: [06-02, 06-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Raw vector SQL trên asyncpg pool: pool.acquire() + conn.transaction() + SET LOCAL hnsw.* + conn.fetch"
    - "pgvector param bind qua literal string '[...]' cast $1::vector (không có pgvector codec precedent)"
    - "Redis cache fail-open: try/except quanh get/set, log warning KHÔNG raise"
    - "intersect-then-query: giao hub_ids ở service layer TRƯỚC SQL filter (defense in depth 2 lớp)"

key-files:
  created:
    - "api/app/schemas/search.py"
    - "api/app/services/search_service.py"
  modified:
    - "api/app/schemas/__init__.py"

key-decisions:
  - "D-02 — request body field tên `query` (KHÔNG `q`) khớp SearchRequestAPI"
  - "D-05 — total_hubs_searched = số hub THỰC SỰ query: _run_vector_query trả (rows, hubs_queried); admin-all đếm count(*) hubs WHERE is_active=TRUE cùng predicate filter SQL"
  - "D-07 — intersect_hubs silent-drop hub user không quyền (KHÔNG raise HubIsolationError; reject-explicit để 06-02 quyết)"
  - "D-08/D-09 — HNSW tuning ef_search=200 + iterative_scan=relaxed_order + max_scan_tuples=20000 trong conn.transaction (SET LOCAL cần transaction)"
  - "D-10 — category/tags noop M2 (None/[]), source hằng 'document', raw_similarity == score (chưa rerank)"
  - "D-11 — cache key sha256(query|sorted(hub_ids)|top_k|min_score), TTL 300s, fail-open"
  - "Predicate hub admin search dùng is_active=TRUE NHẤT QUÁN — KHÔNG dùng cột status (đồng bộ 06-02 search_cross_hub)"

patterns-established:
  - "SearchService(pool, redis) — service nhận asyncpg pool + redis client trực tiếp (KHÔNG AsyncSession; raw vector SQL cần pool)"
  - "Helper module-level pure function tách khỏi class — 06-02 search_cross_hub/find_similar import dùng lại"
  - "_run_vector_query trả tuple (rows, hubs_queried) — phần tử 2 = số hub query đúng D-05"

requirements-completed: [SEARCH-01, SEARCH-02, SEARCH-04]

# Metrics
duration: 12min
completed: 2026-05-18
---

# Phase 6 Plan 01: Schema Layer + Core SearchService Summary

Tạo schema layer (7 Pydantic model contract khớp `frontend/src/services/api.ts`
1:1) và core `SearchService.search()` — single-hub union vector search trên
pgvector với HNSW session tuning + Redis cache. Foundation plan cho router
(06-02) và test (06-04): schema là contract, `search()` là engine vector query
mọi endpoint dùng lại. Không mount endpoint ở plan này.

## Tasks hoàn thành

| Task | Tên | Commit | Files |
|------|-----|--------|-------|
| 1 | Schema layer Search API — Pydantic contract khớp api.ts 1:1 | `418ea59` | `api/app/schemas/search.py` (mới), `api/app/schemas/__init__.py` |
| 2 | SearchService.search() — single-hub union + HNSW tuning + cache | `73222d8` | `api/app/services/search_service.py` (mới) |

## Chi tiết thực thi

### Task 1 — `app/schemas/search.py`
7 Pydantic v2 model, field name khớp `api.ts:490-522` chính xác:
- **Request:** `SearchFilters` (categories/tags/date_from/date_to), `SearchRequest`
  (D-02 field `query`, hub_ids/top_k/min_score/filters), `SimilarRequest`
  (content/hub_id/threshold).
- **Response:** `SearchResultItem` (= SearchResultAPI — D-10 category/tags noop,
  source hằng "document", raw_similarity == score), `SearchResponse`
  (results/total_hubs_searched/query_time_ms/cache_hit), `SimilarMatch`,
  `SimilarResponse`.
- Barrel export `app/schemas/__init__.py` thêm 7 tên (giữ thứ tự alphabet).

### Task 2 — `app/services/search_service.py`
`SearchService(pool, redis)` + helper module-level dùng chung cho 06-02:
- **`intersect_hubs()`** — defense in depth lớp 1 (D-07): admin + không filter →
  `[]` sentinel "mọi hub"; editor/viewer → giao `requested or user_hub_ids` với
  `user_hub_ids`, hub không quyền silent-drop (KHÔNG raise).
- **`_run_vector_query()`** — `pool.acquire()` + `conn.transaction()` + 3 dòng
  `SET LOCAL hnsw.*` (D-08) + raw vector SQL JOIN documents/hubs. Trả
  `(rows, hubs_queried)`: branch `all_hubs` filter `h.is_active = TRUE` + đếm
  `count(*) FROM hubs WHERE is_active = TRUE` (cùng predicate → populace query
  KHỚP count, D-05); branch filter dùng `c.hub_id = ANY($2::uuid[])`,
  count = `len(hub_ids)`.
- **`search()`** — resolve top_k (clamp [1,50]) → intersect hub → empty-result
  sớm cho non-admin chưa assign hub → cache đọc (fail-open) → embed query →
  vector query → min_score filter (D-14) → cache ghi → `model_dump(mode="json")`.
- Helper: `_to_pgvector_literal` (literal `$1::vector`), `_truncate_snippet`
  (word boundary 300 char + `…`), `_cache_key` (sha256 TTL 300s), `_resolve_top_k`,
  `_row_to_item`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Gỡ bỏ try/except re-raise no-op khi embed query**
- **Found during:** Task 2
- **Issue:** Plan bước 7 mô tả `try: query_vector = await embed_text(...)` với
  `except (ValueError, EmbedderError): raise`. Bare `raise` ngay sau khi catch
  chính exception đó là no-op — không thay đổi hành vi, là dead code; `EmbedderError`
  trở thành import thừa (ruff F401).
- **Fix:** Gọi `embed_text(body.query)` trực tiếp — exception tự bubble lên router
  như plan mong muốn (hành vi y hệt). Gỡ import `EmbedderError`. Thêm comment giải
  thích router map 400/502.
- **Files modified:** `api/app/services/search_service.py`
- **Commit:** `73222d8`

**2. [Rule 3 - Blocking] Reword docstring tránh chứa literal `status = 'active'`**
- **Found during:** Task 2 verification
- **Issue:** Acceptance criterion yêu cầu `grep -c "status = 'active'"` trả 0.
  Docstring module có câu chú thích "KHÔNG dùng `status = 'active'` ở bất kỳ đâu"
  — chính câu cảnh báo lại chứa literal string đó → grep match 1 (false positive,
  không phải SQL predicate).
- **Fix:** Đổi docstring thành "KHÔNG dùng predicate cột `status` ở bất kỳ đâu
  (chỉ `is_active`)" — giữ nguyên ý nghĩa, không còn chứa literal.
- **Files modified:** `api/app/services/search_service.py`
- **Commit:** `73222d8`

## Threat Model — kết quả

| Threat ID | Disposition | Trạng thái |
|-----------|-------------|-----------|
| T-06-01-01 (Info Disclosure — intersect_hubs) | mitigate | ✅ `intersect_hubs()` giao hub_ids với `user.hub_ids` TRƯỚC SQL |
| T-06-01-02 (Tampering — raw SQL) | mitigate | ✅ vector literal / hub_ids / top_k qua positional param `$1/$2/$3` — KHÔNG f-string user input |
| T-06-01-03 (DoS — top_k) | mitigate | ✅ `_resolve_top_k` clamp `[1, MAX_TOP_K=50]` |
| T-06-01-04 (DoS — embed query) | mitigate | ✅ `embed_text` raise ValueError text rỗng; oversized → EmbedderError bubble router 502 |
| T-06-01-05 (Info Disclosure — cache key) | mitigate | ✅ cache key sha256 với hub_ids đã intersect → cache hub-scoped |
| T-06-01-06 (DoS — Redis fail) | accept | ✅ Redis None / lỗi get/set → fail-open log warning |

## Verification

- `uv run ruff check app/schemas/search.py app/schemas/__init__.py app/services/search_service.py` — exit 0
- `uv run mypy --strict app/schemas/search.py app/services/search_service.py` — exit 0 (2 source)
- `uv run python -c "from app.schemas import SearchRequest, SearchResponse; from app.services.search_service import SearchService, intersect_hubs"` — exit 0
- `intersect_hubs(['a','b','c'],['a','b'],'viewer') == ['a','b']` — hub C bị loại ✅
- Branch admin-all dùng predicate `is_active = TRUE` (KHÔNG `status`) — nhất quán 06-02 ✅
- `grep -c "class " search.py` = 7; `SET LOCAL hnsw.*` 3 dòng; `$1::vector` 5 match;
  `c.hub_id = ANY` 3 match; `CACHE_TTL_SECONDS = 300` 1 match; `count(*) FROM hubs
  WHERE is_active = TRUE` 2 match; `status = 'active'` 0 match ✅

## Carry-over cho 06-02 / 06-04

- 06-02 thêm `search_cross_hub` (fan-out `asyncio.gather` per-hub) + `find_similar`
  vào cùng `SearchService` — dùng lại helper `_run_vector_query` / `_row_to_item` /
  `intersect_hubs` / `_cache_key`. Branch admin-all 06-02 PHẢI dùng
  `SELECT id FROM hubs WHERE is_active = TRUE` — predicate đã thống nhất ở 06-01.
- 06-02 mount router `app/routers/search.py` (3 endpoint POST + slowapi
  `@limiter.limit(SEARCH_LIMIT)`) + DI factory đọc `request.app.state.db_pool` +
  `request.app.state.redis`. Router map `ValueError` → 400, `EmbedderError` → 502.
- 06-04 cần seed dataset chunk có `vector` non-NULL (`Hub_All/.planning/seeds/`)
  cho integration test hub isolation + cache.

## Self-Check: PASSED

- `api/app/schemas/search.py` — FOUND
- `api/app/services/search_service.py` — FOUND
- `api/app/schemas/__init__.py` — FOUND (modified)
- Commit `418ea59` — FOUND
- Commit `73222d8` — FOUND
