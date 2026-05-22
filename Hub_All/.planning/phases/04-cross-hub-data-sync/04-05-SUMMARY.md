---
phase: 04-cross-hub-data-sync
plan: 05
subsystem: search
tags:
  - search
  - cross-hub
  - refactor
  - hnsw
  - factor-02-extend
  - sync-03
  - w4-fix-verified
requirements:
  - SYNC-03
dependency_graph:
  requires:
    - Plan 04-04 lifespan integration ship (central_sync_pool ready cho admin replay re-use; SYNC-03 KHÔNG cần pool nhưng Wave 4 file-disjoint)
    - Phase 1 chunks table schema + hub_id FK
    - Phase 2 Plan 02-01 create_app conditional mount pattern (central-only block)
    - Phase 2 Plan 02-03 hub_app_factory integration fixture + CENTRAL_ONLY_ENDPOINTS list
    - Phase 3 Plan 03-03 SSO-03 intersect_hubs logic carry forward (defense in depth D-07)
    - M2 Phase 6 SearchService._run_vector_query với HNSW iterative_scan + ef_search=200 + ANY($N::uuid[]) multi-hub support
  provides:
    - "app/services/search_service.py::_search_cross_hub_impl — 1 SQL aggregated WHERE hub_id = ANY thay fan-out asyncio.gather"
    - "app/routers/search.py::cross_hub_router — APIRouter central-only cho POST /api/search/cross-hub (FACTOR-02 extend)"
    - "app/routers/__init__.py::search_cross_hub_router re-export (alias từ cross_hub_router)"
    - "app/main.py::create_app central-only block mount search_cross_hub_router"
    - "tests/unit/test_search_cross_hub_refactor.py — 8 test verify refactor SQL shape + signature unchanged + asyncio.gather xoá"
    - "tests/integration/test_factor_hub_scoped.py — CENTRAL_ONLY 9 endpoint (was 8) + 3 dedicated cross-hub test"
  affects:
    - Plan 04-06 admin replay endpoint /api/sync/replay (central RBAC — KHÔNG đụng search_service)
    - Plan 04-07 checksum scheduler central (KHÔNG đụng search_service)
    - Plan 04-08 closeout REQUIREMENTS.md SYNC-03 mark complete
    - M2 ask_service.py SearchService.search_cross_hub consumer (signature giữ NGUYÊN — backward compat)
    - Frontend api.ts crossHubSearch() (URL /api/search/cross-hub giữ — D6)
    - Phase 7 MIGRATE-05 smoke E2E test cross-hub p95 < 1.5s (E-V3-2) runtime measure
tech-stack:
  added: []
  patterns:
    - "1 SQL aggregated WHERE hub_id = ANY($N::uuid[]) ORDER BY vector <=> embedding LIMIT $k (thay fan-out asyncio.gather + manual re-rank)"
    - "Tách APIRouter 2 instance trong cùng module để main.py mount conditional (universal + central-only — extend Phase 2 FACTOR-02)"
    - "Test mocked asyncpg pool fan-in verify call_count (verify _run_vector_query gọi 1 lần với hub_ids list[str], NOT N lần single hub_id)"
    - "inspect.getsource() assertion guarantee xoá pattern code cũ (refactor enforce)"
key-files:
  created:
    - api/tests/unit/test_search_cross_hub_refactor.py (357 LOC, 8 test)
    - .planning/phases/04-cross-hub-data-sync/04-05-SUMMARY.md
  modified:
    - api/app/services/search_service.py (-36 LOC fan-out + 54 LOC refactor 1 SQL — net +18 LOC chú thích + xóa import asyncio không dùng)
    - api/app/routers/search.py (+~30 LOC tách 2 APIRouter + decorator move @cross_hub_router.post)
    - api/app/routers/__init__.py (+3 LOC import alias + __all__ entry)
    - api/app/main.py (+12 LOC import + include_router trong block central-only)
    - api/tests/integration/test_factor_hub_scoped.py (+80 LOC — CENTRAL_ONLY entry mới + 3 dedicated test)
decisions:
  - "D-V3-Phase4-D1 LOCKED: 1 SQL aggregated `WHERE hub_id = ANY($N::uuid[])` thay fan-out asyncio.gather per-hub. Re-rank tự nhiên qua ORDER BY vector <=> embedding LIMIT $k của SQL — KHÔNG cần Python merge sort. HNSW iterative_scan=relaxed_order + ef_search=200 + max_scan_tuples=20000 carry forward M2 Phase 6 _run_vector_query SET LOCAL session tuning."
  - "D-V3-Phase4-D3 LOCKED: Tách `cross_hub_router` riêng (Approach A inline) thay vì dependency-based central-only check (Approach B). Lý do: route KHÔNG expose ngoài OpenAPI/docs hub con (Approach B vẫn expose). main.py conditional include_router trong block central-only nhất quán với 9 router central-only hiện có."
  - "Public API LOCKED: `SearchService.search_cross_hub(*, body, user) -> dict[str, Any]` signature KHÔNG đổi — backward compat M2 contract (ask_service.py consumer + frontend api.ts crossHubSearch + integration test reusing fixtures). Refactor IN-PLACE _search_cross_hub_impl private."
  - "W4 fix pre-task verify PASS: `grep \"async def _search\" search_service.py` returned `_search_single_impl` (239) + `_search_cross_hub_impl` (338) + `_search_one` (391) — inner function tên khớp acceptance grep mà plan dự đoán. KHÔNG cần adjust pattern."
  - "TDD RED → GREEN cycle (Task 1 tdd=true): commit `test(04-05): them 8 unit test cross-hub refactor RED phase` (4 FAIL + 4 PASS backward compat carry forward) → commit `refactor(04-05): _search_cross_hub_impl 1 SQL aggregated thay fan-out` (8/8 PASS). REFACTOR phase KHÔNG cần commit riêng — Task 1 done sau GREEN."
  - "Approach docstring sanitization: source comment `asyncio.gather` (line 333 public method + line 411 inline) xoá khỏi `_search_cross_hub_impl` scope để Test 8 inspect.getsource() assertion PASS. Module-level docstring (line 18) giữ `asyncio.gather` để document refactor lý do — KHÔNG bị quét bởi inspect.getsource(method)."
  - "CENTRAL_ONLY list grow 8 → 9 endpoint trong test_factor_hub_scoped.py — POST /api/search/cross-hub thêm vào end list với comment trace Plan 04-05 SYNC-03 / D-V3-Phase4-D3."
metrics:
  duration_minutes: 35
  completed_date: 2026-05-22
  task_count: 3
  commit_count: 4
  file_count: 6
  test_count: 11
  test_pass_rate: "8/8 unit cross-hub refactor PASS + 5/5 integration cross-hub mount/strip PASS (was 10/10 baseline; +5 new = 15/15)"
  regression_pass_rate: "361/361 unit + 15/15 Phase 2 integration + 6/6 Phase 4 lifespan integration mock PASS — KHÔNG break Phase 1+2+3 + Plan 04-01..04"
---

# Phase 4 Plan 05: Cross-hub Search Refactor Summary

**One-liner:** Wave 4 refactor `SearchService._search_cross_hub_impl` từ fan-out parallel `asyncio.gather(*[_search_one(h) for h in hub_ids])` qua N task thành 1 SQL aggregated `_run_vector_query(hub_ids=<full list>)` dùng `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector LIMIT $3` — re-rank tự nhiên qua SQL ORDER BY (KHÔNG Python merge sort) + HNSW iterative_scan=relaxed_order + ef_search=200 + max_scan_tuples=20000 carry forward M2 Phase 6; tách `routers/search.py` thành 2 APIRouter (`router` universal /api/search + /api/search/similar mount mọi process + `cross_hub_router` central-only /api/search/cross-hub) + `main.py` conditional include trong block central-only — đóng SYNC-03 D-V3-Phase4-D1/D3 file-disjoint với Plan 04-04 lifespan integration; backward compat M2 `SearchService.search_cross_hub()` signature giữ NGUYÊN cho ask_service.py consumer + frontend api.ts crossHubSearch.

---

## Files Created/Modified

### Created (2 file)

| Path | LOC | Purpose |
|------|-----|---------|
| `api/tests/unit/test_search_cross_hub_refactor.py` | 357 | 8 unit test — verify _search_cross_hub_impl refactor (signature unchanged + empty hub_ids early return + admin no-filter SELECT active hubs + SSO-03 intersect logic + _run_vector_query called 1 lần với hub_ids list[str] NOT N lần single + Redis cache get/set carry forward + SearchResponse envelope shape + asyncio.gather + `async def _search_one` xoá khỏi `_search_cross_hub_impl` scope). |
| `.planning/phases/04-cross-hub-data-sync/04-05-SUMMARY.md` | — | This summary. |

### Modified (5 file)

| Path | Change | Purpose |
|------|--------|---------|
| `api/app/services/search_service.py` | -36 LOC fan-out + 54 LOC refactor — net ~+18 LOC (chú thích trace) + xóa `import asyncio` không dùng | Plan 04-05 Task 1 (SYNC-03 D-V3-Phase4-D1) — `_search_cross_hub_impl` refactor 1 SQL aggregated `WHERE c.hub_id = ANY` qua single `_run_vector_query(hub_ids=<list>)`. Xóa `async def _search_one(hub_id)` inner function + `asyncio.gather(*[_search_one(h) for h in hub_ids])` + manual re-rank `sort(key=score, reverse=True)[:top_k]`. Giữ admin no-filter SELECT id FROM hubs WHERE is_active = TRUE branch + intersect_hubs SSO-03 + Redis cache D-11 + tag_cache_key per hub + SearchResponse envelope. Sanitize source comment `asyncio.gather` (line 333 public method docstring + line 411 inline comment) khỏi `_search_cross_hub_impl` scope cho Test 8 inspect.getsource() assertion PASS. Module-level docstring giữ trace lý do refactor. |
| `api/app/routers/search.py` | +~30 LOC tách 2 APIRouter | Plan 04-05 Task 2 (SYNC-03 D-V3-Phase4-D3) — Tách `router` (universal /api/search + /api/search/similar mount mọi process) khỏi `cross_hub_router` (central-only /api/search/cross-hub). Decorator move `@router.post("/cross-hub")` → `@cross_hub_router.post("/cross-hub")` cho `cross_hub_search_endpoint`. Doc update Plan 04-05 marker. |
| `api/app/routers/__init__.py` | +3 LOC import alias + __all__ entry | Re-export `cross_hub_router as search_cross_hub_router` cho main.py import. |
| `api/app/main.py` | +12 LOC import + include_router trong block central-only | Plan 04-05 Task 2 — block `if settings.hub_name == "central"` thêm `search_cross_hub_router` import + `app.include_router(search_cross_hub_router)` sau 9 router central-only hiện có với comment trace Plan 04-05 SYNC-03 / D-V3-Phase4-D3. |
| `api/tests/integration/test_factor_hub_scoped.py` | +80 LOC — CENTRAL_ONLY entry mới + 3 dedicated test | Plan 04-05 Task 3 — `CENTRAL_ONLY_ENDPOINTS` grow 8 → 9 thêm `("POST", "/api/search/cross-hub")` với comment trace. 3 dedicated test mới: `test_hub_con_strips_search_cross_hub[yte\|duoc\|hcns]` parametrize 3 hub con + `test_central_mounts_search_cross_hub` + `test_hub_con_mounts_search_local` (regression guard universal `/api/search` mount hub con). |

---

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| `d93ef0a` | test | Task 1 RED — 8 unit test cross-hub refactor (test_search_cross_hub_refactor.py). 4 PASS (signature + empty hub_ids + Redis cache + intersect) + 4 FAIL (admin-all + single SQL no fanout + response shape + no asyncio.gather) — expected RED state trước GREEN. |
| `9a1ad0f` | refactor | Task 1 GREEN — `_search_cross_hub_impl` 1 SQL aggregated thay fan-out (SYNC-03 D-V3-Phase4-D1). 8/8 unit PASS + 361/361 unit suite regression + ruff + mypy --strict PASS. |
| `5b18d04` | feat | Task 2 — tách `search_cross_hub_router` central-only (SYNC-03 D-V3-Phase4-D3). routers/search.py 2 APIRouter + __init__.py re-export + main.py conditional mount. 9/9 test_main_factory.py PASS + ruff + mypy --strict PASS. |
| `c5cdf6f` | test | Task 3 — endpoint matrix update tests/integration/test_factor_hub_scoped.py. CENTRAL_ONLY 8 → 9 endpoint + 3 dedicated cross-hub test. 15/15 PASS (was 10/10 + 5 new). |

**Total:** 4 commits atomic (1 RED test + 1 GREEN refactor + 1 feat router split + 1 test endpoint matrix update).

---

## Test Results

### test_search_cross_hub_refactor.py — 8/8 unit PASS (TDD GREEN)

| Test | Validates |
|------|-----------|
| `test_search_cross_hub_signature_unchanged` | `inspect.signature(SearchService.search_cross_hub)` — kwargs `body` + `user` + return annotation hiện diện. Backward compat M2 contract. |
| `test_search_cross_hub_empty_hub_ids_returns_empty` | Non-admin user.hub_ids=[] → return SearchResponse empty envelope `{results:[], total_hubs_searched:0, cache_hit:False}` — KHÔNG raise. |
| `test_search_cross_hub_admin_no_filter_queries_all_active` | Admin + body.hub_ids=None → SELECT id FROM hubs WHERE is_active = TRUE → resolve full list → pass vào `_run_vector_query(hub_ids=<full>, all_hubs=False)`. total_hubs_searched = 3. |
| `test_search_cross_hub_intersects_jwt_and_body` | SSO-03 carry forward: user.hub_ids=[yte,duoc] + body.hub_ids=[yte,hcns] → intersect=[yte] → pass single-element list (KHÔNG raise hub không thuộc user). |
| `test_search_cross_hub_uses_single_sql_no_fanout` | **KEY ASSERTION** — `_run_vector_query` mock AsyncMock — `call_count == 1` (NOT 3 lần fan-out) + `hub_ids` passed là FULL list (NOT single element). |
| `test_search_cross_hub_redis_cache_get_set_unchanged` | Cache hit path: redis.get trả JSON → service flip cache_hit=True + KHÔNG call `_run_vector_query` (D-11 carry forward). |
| `test_search_cross_hub_response_shape_results_list` | Response dict `results` (list), `total_hubs_searched` (int), `query_time_ms` (int), `cache_hit` (bool) — SearchResponse envelope shape. |
| `test_search_cross_hub_no_asyncio_gather` | `inspect.getsource(_search_cross_hub_impl)` KHÔNG chứa `asyncio.gather(` AND `async def _search_one` — guarantee refactor xoá fan-out pattern. |

**Duration:** 4.23s. **Pass rate:** 8/8 (100%).

### test_factor_hub_scoped.py — 15/15 integration PASS (was 10/10 baseline + 5 new)

| Test | Validates |
|------|-----------|
| `test_central_mounts_all_endpoints` | Central mount 12 hub-scoped + **9 central-only** (was 8 + cross-hub mới Plan 04-05). |
| `test_hub_strips_central_only[yte\|duoc\|hcns]` (3 parametrize) | Hub con strip **9 central-only** (was 8) → 404 envelope D6. Bao gồm `/api/search/cross-hub` mới. |
| `test_hub_mounts_hub_scoped[yte\|duoc\|hcns]` (3 parametrize) | Hub con mount 12 hub-scoped (10 LOCAL + 2 SSO REDIRECT 307) — Phase 3 carry forward. |
| `test_404_envelope_shape_hub_strip` | Hub yte GET /api/rag-config envelope shape (D-V3-Phase2-E). |
| `test_404_envelope_unknown_route_central` | Central path không tồn tại → envelope shape (ErrorHandlerMiddleware). |
| `test_hub_con_strips_search_cross_hub[yte\|duoc\|hcns]` (3 parametrize) **NEW** | Hub con POST /api/search/cross-hub → 404 envelope D6 (FACTOR-02 extend Plan 04-05). |
| `test_central_mounts_search_cross_hub` **NEW** | Central POST /api/search/cross-hub → != 404 (200/401/422 acceptable; endpoint tồn tại). |
| `test_hub_con_mounts_search_local` **NEW** | Hub yte POST /api/search → != 404 (universal router mount hub con — regression guard). |
| `test_hub_yte_dsn_mismatch_raises` | Phase 1 _enforce_hub_dsn_match validator regression — Settings raise ValidationError. |

**Duration:** 6.94s. **Pass rate:** 15/15 (100%).

### Regression

| Suite | Result |
|-------|--------|
| `tests/unit/` full unit suite | **361/361 PASS** (31.14s) — KHÔNG break Phase 1+2+3 + Plan 04-01..04 + Task 1 mới (8 test) |
| `tests/integration/test_factor_hub_scoped.py` (Phase 2 + Plan 04-05) | **15/15 PASS** (was 10/10 + 5 new) |
| `tests/integration/test_sync_lifespan_integration.py` (Plan 04-04) | **6/6 mock PASS + 1 skipif** (KHÔNG break) |
| Aggregate `tests/unit/ + Phase 2 integration + Plan 04-04 integration` | **382/382 PASS + 1 skipif** |
| `ruff check` 5 file touched | All checks passed |
| `mypy --strict app/services/search_service.py app/routers/search.py app/main.py` | Success: no issues found in 3 source files |

---

## Acceptance Criteria (Plan 04-05)

### Task 1 — Refactor `_search_cross_hub_impl` 1 SQL aggregated

| Criterion | Result |
|-----------|--------|
| `grep -n "_run_vector_query" app/services/search_service.py` ≥ 2 | 10 matches (2 method def + 8 reference) |
| `grep -c "asyncio.gather" _search_cross_hub_impl scope` = 0 | 0 (inspect.getsource verify) |
| `grep -n "async def _search_one" _search_cross_hub_impl scope` = 0 | 0 (inspect.getsource verify) |
| `grep -n "Phase 4 Plan 04-05" app/services/search_service.py` ≥ 1 | 4 matches (module doc + public method + impl docstring + inline comment) |
| `grep -n "hub_ids=hub_ids" app/services/search_service.py` ≥ 1 | 3 matches (2 cũ + 1 mới refactor) |
| Unit test 8 PASS | 8/8 PASS (test_search_cross_hub_refactor.py) |
| M2 search service regression | KHÔNG có test_search_service.py — 361/361 unit suite PASS = effective regression |
| `ruff check app/services/search_service.py` exit 0 | PASS |
| `mypy --strict app/services/search_service.py` exit 0 | PASS |

### Task 2 — Tách search_router → 2 router + main.py conditional mount

| Criterion | Result |
|-----------|--------|
| `grep "search_cross_hub_router\|cross_hub_router" routers/search.py` ≥ 2 | 4 matches (declaration + alias rename + decorator + doc) |
| `grep "search_cross_hub_router" routers/__init__.py` ≥ 1 | 4 matches (import alias + __all__ + comment) |
| `grep "search_cross_hub_router" app/main.py` ≥ 2 | 2 matches (import + include_router) |
| `grep "@cross_hub_router.post" routers/search.py` ≥ 1 | 1 match (cross_hub_search_endpoint decorator) |
| `grep "@router.post" routers/search.py` ≥ 1 | 2 matches (search_endpoint + find_similar_endpoint giữ universal) |
| `test_main_factory.py` 9 test PASS | 9/9 PASS (Phase 2 Plan 02-01 regression) |
| `ruff + mypy --strict 2 file` | PASS |

### Task 3 — Integration test endpoint matrix update

| Criterion | Result |
|-----------|--------|
| `grep "/api/search/cross-hub" test_factor_hub_scoped.py` ≥ 2 | 9 matches (CENTRAL_ONLY list + 3 test def + 5 trong test body) |
| `grep "test_hub_con_strips_search_cross_hub" test_factor_hub_scoped.py` ≥ 1 | 1 match |
| `grep "test_central_mounts_search_cross_hub" test_factor_hub_scoped.py` ≥ 1 | 1 match |
| Integration test PASS ≥ 14 | **15/15 PASS** (10 baseline + 5 new) |
| Phase 2+3 unit regression `test_main_factory.py + test_auth_router_hub_redirect.py` | (chỉ test trực tiếp test_main_factory.py 9/9 — auth_router_hub_redirect KHÔNG affected; 361/361 unit suite full PASS) |
| `ruff check tests/integration/test_factor_hub_scoped.py` exit 0 | PASS |

**Tổng: 22/22 acceptance criteria PASS.**

---

## Decisions Made

### LOCKED Carry Forward (Phase Context)

- **D-V3-Phase4-D1:** Cross-hub search refactor in-place 1 SQL aggregated `WHERE hub_id = ANY` thay fan-out per-hub. Public API signature giữ NGUYÊN backward compat M2.
- **D-V3-Phase4-D3:** Strip `/api/search/cross-hub` ở hub con (FACTOR-02 extend). Central-only mount conditional theo `settings.hub_name`.
- **D-V3-02 honored:** Aggregated `medinet_central.chunks` đã có (sync 1 chiều từ hub con qua Plan 04-04 sync_worker_loop + central_sync_pool). Cross-hub query → query trên local central DB (KHÔNG cần fan-out HTTP tới hub con).
- **R2 carry forward:** pgvector ≥ 0.8 HNSW + iterative_scan=relaxed_order + ef_search=200 + max_scan_tuples=20000 carry forward M2 Phase 6 `_run_vector_query` SET LOCAL session tuning.
- **D-07 defense in depth:** intersect_hubs SSO-03 logic carry forward — service layer Lớp 1 (intersect TRƯỚC SQL) + SQL Lớp 2 (`WHERE hub_id = ANY` filter lại).
- **D-11 cache D6:** Redis cache get/set với `_cross_cache_key("search:cross:...")` namespace + tag_cache_key per hub fail-open carry forward unchanged.

### Implementation Details (Plan 04-05 specific)

- **W4 fix pre-task verify PASS:** Plan dự đoán inner function name `_search_one` line 391 chính xác — `grep "async def _search" app/services/search_service.py` returned `_search_single_impl` (239) + `_search_cross_hub_impl` (338) + `_search_one` (391). KHÔNG cần adjust acceptance grep pattern. Documented trong RED commit message.
- **Approach A inline split** (chosen) vs Approach B dependency-check: Tách 2 APIRouter instance trong cùng module `app/routers/search.py`. Lý do: (1) Route KHÔNG expose ngoài OpenAPI/docs hub con — Approach B dependency raise 404 vẫn để route trong `app.routes` list (test_factor_hub_scoped.py `test_central_mounts_all_endpoints` sẽ false-positive); (2) Conditional include nhất quán với 9 router central-only hiện có trong main.py block; (3) Test main_factory.py prefix-based assertion KHÔNG ảnh hưởng (`/api/search` universal mount vẫn match — split chỉ affect endpoint cụ thể, KHÔNG prefix-level).
- **Sanitize source comment cho Test 8:** `inspect.getsource(SearchService._search_cross_hub_impl)` quét toàn bộ function source — bao gồm comment + docstring. Source `asyncio.gather` mention trong public method docstring (line 333 cũ) + inline comment Plan 04-05 trace (line 411 cũ) bị quét và FAIL Test 8. Fix: xoá literal `asyncio.gather` khỏi 2 vị trí trong scope `_search_cross_hub_impl` + public method `search_cross_hub` docstring. Module-level docstring (line 18) giữ trace lý do refactor — KHÔNG bị quét bởi `inspect.getsource(method)`.
- **TDD strict gate (Task 1 tdd=true):** Commit `test(04-05): them 8 unit test cross-hub refactor RED phase` LẦN ĐẦU với 4 PASS (signature + empty + cache + intersect carry forward backward compat) + 4 FAIL (admin-all + single SQL no fanout + response shape + no asyncio.gather). GREEN commit `refactor(04-05): _search_cross_hub_impl 1 SQL aggregated thay fan-out` flip 4 FAIL → PASS. REFACTOR phase KHÔNG cần commit riêng — code đã clean sau GREEN (xoá fan-out + sanitize comment + xoá import asyncio).
- **`_hubs_queried` placeholder ignored:** Refactor signature `_run_vector_query` trả `tuple(rows, hubs_queried_count)`. Cross-hub call `rows, _hubs_queried = await self._run_vector_query(hub_ids=hub_ids, all_hubs=False)` ignore count vì `total_hubs_searched = len(hub_ids)` đã lấy từ caller scope (hub_ids resolved sau admin-all branch + intersect). `_hubs_queried` chỉ ý nghĩa cho `all_hubs=True` branch single-hub search (count from `SELECT count(*) FROM hubs WHERE is_active = TRUE`).
- **`import asyncio` xoá:** Sau refactor, `_search_cross_hub_impl` KHÔNG còn dùng `asyncio.gather`. File `search_service.py` KHÔNG còn import `asyncio` ở top-level → xoá để clean. mypy + ruff KHÔNG complain unused import.
- **`# noqa: C901` xoá:** `_search_cross_hub_impl` cũ có `# noqa: C901 — chuỗi step fan-out + cache phẳng` cho complexity warning McCabe. Sau refactor giảm complexity (xoá inner function _search_one + asyncio.gather + manual re-rank sort) → KHÔNG cần `noqa` nữa. mypy + ruff KHÔNG complain complexity.
- **Public method docstring refactor reference:** Đổi `search_cross_hub` public docstring từ "Cross-hub fan-out search (SEARCH-03 / D-06). Query SONG SONG mỗi hub qua `asyncio.gather` (mỗi hub lấy `top_k` riêng), aggregate toàn bộ rồi re-rank theo score desc → global top-k." → "Cross-hub aggregated search (SEARCH-03 / D-06 + Plan 04-05 D-V3-Phase4-D1). Phase 4 Plan 04-05 refactor — 1 SQL aggregated `WHERE c.hub_id = ANY` thay fan-out per-hub. Re-rank tự nhiên qua ORDER BY vector <=> embedding LIMIT $k của SQL (KHÔNG cần Python merge sort). Public API signature giữ NGUYÊN — backward compat M2 contract." — `asyncio.gather` literal KHÔNG còn xuất hiện cho Test 8.

### Decisions deferred to next plans

- **E-V3-2 runtime measure cross-hub p95 < 1.5s:** Defer Phase 7 MIGRATE-05 (smoke E2E 3 hub con + central + golden path). Unit test mock asyncpg KHÔNG đo latency thực; cần Postgres + chunks data thật + HNSW index build.
- **`/api/search/cross-hub` admin replay hookup:** Plan 04-06 (admin replay endpoint) KHÔNG đụng search_service.py — file-disjoint.
- **Frontend api.ts crossHubSearch() URL switch khi v3.0 deploy multi-hub:** Defer Phase 5 PROXY-02 (D-V3-06 D6 expire formally). Hiện tại URL `/api/search/cross-hub` giữ — frontend hardcode same-origin sẽ work ở central process (port 8180).
- **MCP service cross-hub aggregate re-point:** Defer Phase 7 MIGRATE-04 (MCP forward X-API-Key tới central process — KHÔNG fan-out N hub con).

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test fixture] Test 8 inspect.getsource() quét toàn bộ function source bao gồm docstring + comment**

- **Found during:** Task 1 GREEN — sau khi refactor xong, Test 8 vẫn FAIL với "asyncio.gather is contained here". inspect.getsource() trên method bao gồm: signature + docstring + body + nested comment.
- **Issue:** Refactor logic đã xoá `asyncio.gather` call code, nhưng public method `search_cross_hub` docstring + inline comment `_search_cross_hub_impl` body vẫn mention literal `asyncio.gather` (như trace history "thay fan-out asyncio.gather"). Test 8 strict `assert "asyncio.gather" not in source` FAIL.
- **Fix:** Sanitize 2 vị trí literal `asyncio.gather` khỏi scope `_search_cross_hub_impl` + parent `search_cross_hub` docstring:
  - Line 333 (public method docstring): "Query SONG SONG mỗi hub qua `asyncio.gather`" → "Phase 4 Plan 04-05 refactor — 1 SQL aggregated `WHERE c.hub_id = ANY` thay fan-out per-hub. Re-rank tự nhiên qua ORDER BY..."
  - Line 411 (inline comment _search_cross_hub_impl scope): "1 SQL aggregated thay fan-out asyncio.gather." → "1 SQL aggregated thay fan-out per-hub."
- **Files modified:** `api/app/services/search_service.py` (inline trong Task 1 GREEN commit `9a1ad0f`).
- **Commit:** `9a1ad0f` (gộp với Task 1 GREEN refactor — logically là 1 unit Rule 1 minor docstring cleanup).
- **Rationale:** Rule 1 — test assertion enforces refactor completeness; source literal `asyncio.gather` mention (cho dù chỉ trong comment) vi phạm intent của test (guarantee xoá fan-out pattern). Module-level docstring (line 18) giữ literal mention cho trace history — KHÔNG bị quét bởi `inspect.getsource(method)`.

### Plan-strict adherence

- KHÔNG bump stack version (Python 3.12, FastAPI 0.136.1, pgvector 0.4.2, asyncpg 0.30.0).
- KHÔNG sửa `frontend/`, `STATE.md`, `ROADMAP.md`, `REQUIREMENTS.md` (out-of-scope cho executor).
- KHÔNG dùng `--no-verify` cho commit (sequential mode, pre-commit hooks run).
- KHÔNG đụng `api/migrations/` directory (Plan 04-01 file-disjoint).
- KHÔNG đụng `api/app/config.py` (Plan 04-02 file-disjoint).
- KHÔNG đụng `api/app/sync/` directory (Plan 04-03 file-disjoint).
- KHÔNG đụng `api/app/db/dsn.py`, `api/tests/integration/conftest.py` ngoài chỗ Plan 04-04 đã ship (file-disjoint Wave 4).
- Public API `SearchService.search_cross_hub()` signature KHÔNG đổi.
- Backward compat M2 ask_service.py `search_cross_hub` consumer giữ nguyên call path.
- Backward compat M2 frontend api.ts crossHubSearch() URL `/api/search/cross-hub` giữ (D6 honored cho central process).
- Phase 2 hub_app_factory fixture pattern carry forward — KHÔNG thêm escape hatch mới.
- Commit message prefix tiếng Anh + body tiếng Việt theo CLAUDE.md §5.

---

## Authentication Gates

**None.** Plan 04-05 thuần refactor service + router split + integration test — KHÔNG cần auth setup. JWT verification logic carry forward Phase 3 SSO-03 + SSO-04 (Layer 3 dependency `get_current_user_for_hub_access`). Plan 04-05 không tạo endpoint cần secret/credential mới.

---

## Known Stubs

**None.** Plan 04-05 ship refactor đầy đủ:
- `_search_cross_hub_impl` real 1 SQL aggregated qua `_run_vector_query` existing M2 helper (verified accept `hub_ids: list[str]` multi-element qua `WHERE c.hub_id = ANY($2::uuid[])` line 214 M2 Phase 6).
- `cross_hub_router` real APIRouter với decorator `@cross_hub_router.post("/cross-hub")` cho `cross_hub_search_endpoint` — fully wired.
- main.py `app.include_router(search_cross_hub_router)` real conditional mount trong block central-only.

---

## Threat Flags

**Không phát hiện threat surface mới ngoài `<threat_model>` của Plan 04-05.** 6 threat (T-04-05-01..06) trong plan đã cover toàn bộ surface:

- T-04-05-01 (Spoofing stale JWT cross-hub access) → mitigated bởi SSO-03 intersect_hubs Lớp 1 + SSO-04 Layer 3 dependency (central bypass cho cross-hub by design).
- T-04-05-02 (Tampering body.hub_ids hub user KHÔNG quyền) → mitigated bởi intersect_hubs silent-drop pattern (KHÔNG raise).
- T-04-05-03 (Info Disclosure hub con leak central data qua /api/search/cross-hub) → mitigated bởi FACTOR-02 extend strip endpoint hub con → 404 NOT_FOUND envelope D6 (verify qua 3 dedicated test trong test_factor_hub_scoped.py).
- T-04-05-04 (Repudiation cross-hub search KHÔNG audit) → accept disposition; logger.info `cross_hub_search_completed` enough cho v3.0-b.
- T-04-05-05 (DoS aggregated SQL 4 hub × 1M chunks query timeout) → mitigated bởi HNSW iterative_scan=relaxed_order + ef_search=200 + max_scan_tuples=20000 carry forward M2 Phase 6 _run_vector_query SET LOCAL session tuning.
- T-04-05-06 (Elevation hub con compromise → bypass strip mount) → accept disposition (in-process mount conditional KHÔNG cross-process attack).

---

## Verification Status

### Automated (in-process)

- 8/8 unit test PASS `test_search_cross_hub_refactor.py` (4.23s)
- 15/15 integration test PASS `test_factor_hub_scoped.py` (was 10/10 baseline + 5 new = cross-hub strip/mount + local mount; 6.94s)
- 361/361 full unit suite regression PASS (31.14s) — KHÔNG break Phase 1+2+3 + Plan 04-01..04
- 6/6 mock integration `test_sync_lifespan_integration.py` PASS + 1 skipif (KHÔNG break Plan 04-04)
- 22/22 acceptance criteria PASS (8 Task 1 + 7 Task 2 + 7 Task 3)
- `ruff check` 5 file changed — All checks passed
- `mypy --strict app/services/search_service.py app/routers/search.py app/main.py` Success no issues found in 3 source files

### Deferred (cần Postgres runtime + chunks data)

- Live-DB cross-hub search runtime measure p95 < 1.5s — defer Phase 7 MIGRATE-05 smoke E2E (E-V3-2 enforce).
- HNSW index build performance trên hub_ids = ANY($1::uuid[]) với 4 hub × 1M chunks aggregate — defer Phase 7 load test.
- Redis cache cross-hub `search:cross:` namespace hit/miss ratio runtime — defer Phase 7 observability.

---

## Self-Check

### Files Created/Modified Verification

| Claim | Verified |
|-------|----------|
| `api/tests/unit/test_search_cross_hub_refactor.py` exists (357 LOC) | FOUND |
| `api/app/services/search_service.py` modified — net ~+18 LOC (refactor 1 SQL aggregated + xóa asyncio.gather + import asyncio) | FOUND `_run_vector_query` 10 grep + `Phase 4 Plan 04-05` 4 grep + `hub_ids=hub_ids` 3 grep |
| `api/app/routers/search.py` modified — 2 APIRouter tách + decorator split | FOUND `cross_hub_router` 4 grep + `@cross_hub_router.post` 1 grep + `@router.post` 2 grep |
| `api/app/routers/__init__.py` modified — import alias + __all__ entry | FOUND `search_cross_hub_router` 4 grep |
| `api/app/main.py` modified — import + include_router central-only | FOUND `search_cross_hub_router` 2 grep |
| `api/tests/integration/test_factor_hub_scoped.py` modified — CENTRAL_ONLY 9 entry + 3 dedicated test | FOUND `/api/search/cross-hub` 9 grep + 3 new test function |

### Commit Verification

| Hash | Verified |
|------|----------|
| `d93ef0a` (test Task 1 RED — 8 unit test cross-hub refactor) | FOUND in git log |
| `9a1ad0f` (refactor Task 1 GREEN — _search_cross_hub_impl 1 SQL aggregated) | FOUND in git log |
| `5b18d04` (feat Task 2 — tach search_cross_hub_router central-only mount conditional) | FOUND in git log |
| `c5cdf6f` (test Task 3 — update endpoint matrix /api/search/cross-hub central-only) | FOUND in git log |

## Self-Check: PASSED

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Duration | ~35 phút (4 commit atomic — 1 RED test + 1 GREEN refactor + 1 router split feat + 1 endpoint matrix test) |
| Tasks completed | 3/3 (Task 1 refactor _search_cross_hub_impl + Task 2 router split + Task 3 endpoint matrix update) |
| Files created | 2 (test_search_cross_hub_refactor.py + SUMMARY.md) |
| Files modified | 5 (search_service.py + routers/search.py + routers/__init__.py + main.py + test_factor_hub_scoped.py) |
| LOC delta | -36 LOC fan-out + 54 LOC refactor + ~30 LOC router split + ~3 LOC __init__ + ~12 LOC main.py + ~80 LOC integration test + 357 LOC unit test = **~500 LOC source/test** |
| Tests added | **11** (8 unit cross-hub refactor + 3 integration dedicated cross-hub mount/strip) |
| Test pass rate | **8/8 unit + 15/15 integration PASS** (was 10/10 + 5 new) — 11.17s aggregate |
| Acceptance criteria | **22/22 PASS** (8 Task 1 + 7 Task 2 + 7 Task 3) |
| Regression | **361/361 unit + 15/15 Phase 2 integration + 6/6 Plan 04-04 mock integration PASS + 1 skipif** — KHÔNG break Phase 1+2+3 + Plan 04-01..04 |
| Lint | ruff + mypy --strict PASS all touched file (3 source) |
| Commits | 4 atomic (RED test + GREEN refactor + feat router split + test endpoint matrix) |
| Deviations | 1 (Rule 1 - test fixture: sanitize source comment `asyncio.gather` literal khỏi scope _search_cross_hub_impl + public method docstring để Test 8 inspect.getsource() PASS — inline trong GREEN commit) |

---

## Next: Plan 04-06 (Admin Replay Endpoint) + Plan 04-07 (Checksum Scheduler) Wave 4 Parallel + Plan 04-08 Closeout

Plan 04-05 đã ship Wave 4 cross-hub search refactor. Plan 04-06 + 04-07 mở (file-disjoint với search_service.py):

1. **Plan 04-06 SYNC-02/04 — Admin replay endpoint:** `POST /api/sync/replay { hub_id, since }` central RBAC admin. Manipulate sync_outbox dead rows tại hub con DSN (KHÔNG re-use `central_sync_pool` — central spawn new pool tới `CHECKSUM_HUB_DSNS_JSON` dict). File-disjoint với Plan 04-05 (`app/routers/sync.py` thay vì `app/routers/search.py`).
2. **Plan 04-07 SYNC-04 — Checksum scheduler:** Central lifespan asyncio task. Daily 2AM count drift + Hourly 1% sample hash drift. Spawn N asyncpg.Pool tới hub con DB (read-only role). 2 Prometheus metric ship Plan 04-03 module-level. File-disjoint với Plan 04-05 + 04-06.
3. **Plan 04-08 closeout:** Mark SYNC-01..05 complete REQUIREMENTS.md sau Plan 04-04..07 ship. Defer Phase 7 MIGRATE-05 full E2E smoke (3 hub + central + golden path + cross-hub p95 < 1.5s E-V3-2 measure).

Plan 04-05 phụ thuộc Plan 04-04 (lifespan integration Wave 3 ship) — pre-req satisfied. Plan 04-06 + 04-07 parallel sau Plan 04-05 ship — file-disjoint.

**Phase 4 progress:** 5/7 plan complete (~71%). SYNC-03 (cross-hub search refactor) đóng end-to-end ở Plan 04-05; formally đóng Phase 4 closeout (Plan 04-08) khi REQUIREMENTS.md mark check.

---

*Plan 04-05 ship 2026-05-22 sau ~35 phút thực thi. Wave 4 cross-hub search refactor DONE — `_search_cross_hub_impl` 1 SQL aggregated `WHERE hub_id = ANY` thay fan-out asyncio.gather + `cross_hub_router` central-only + endpoint matrix update. 4 commit atomic (1 RED test + 1 GREEN refactor + 1 feat router split + 1 test endpoint matrix). 8/8 unit + 15/15 Phase 2 integration PASS + 361/361 unit suite regression + 22/22 acceptance + ruff + mypy --strict PASS. Next: Plan 04-06 + 04-07 Wave 4 parallel (file-disjoint app/routers/sync.py admin replay + app/observability/checksum_scheduler.py).*
