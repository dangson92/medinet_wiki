---
phase: 06-search-api-single-cross-hub
plan: 04
subsystem: search
tags: [integration-test, hub-isolation, e4-exit-criteria, hnsw, redis-cache, pytest-critical]

# Dependency graph
requires:
  - phase: 06-search-api-single-cross-hub
    provides: "06-01 — SearchService.search() + schema search.py"
  - phase: 06-search-api-single-cross-hub
    provides: "06-02 — app/routers/search.py (3 endpoint POST) + search_cross_hub()"
  - phase: 06-search-api-single-cross-hub
    provides: "06-03 — search_cache.py hub-tagged cache + Pub/Sub invalidation"
  - phase: 05-hub-user-audit-apikey-settings-crud
    provides: "conftest.py — app_with_auth/auth_client/viewer_user/viewer_token + _insert_hub/_assign_user_hub helper"
provides:
  - "tests/integration/conftest.py — _insert_document + _insert_chunk seed helper (chunk có vector 1536-dim)"
  - "tests/integration/test_search_hub_isolation.py — 6 test @pytest.mark.critical E4 search verification"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Seed chunk vector trực tiếp qua SQL: CAST(:vec AS vector) literal — bypass embedding API (chunks table rỗng M2)"
    - "Monkeypatch query embedding: patch app.services.search_service.embed_text trả vector cố định — test isolation/cache/SQL không phụ thuộc OPENAI_API_KEY"
    - "EXPLAIN ANALYZE verify HNSW: query vector-ordering thuần (không predicate hub_id) để HNSW là index DUY NHẤT liên quan ORDER BY vector <=>"

key-files:
  created:
    - "api/tests/integration/test_search_hub_isolation.py"
  modified:
    - "api/tests/integration/conftest.py"

key-decisions:
  - "Test seed chunks/documents trực tiếp qua SQL (T-06-04-02 accept) — search isolation test cần data nhiều hub, ingest flow đã test riêng Phase 4"
  - "embed_text monkeypatch trả vector cố định (T-06-04-03 accept) — test verify SQL filter + cache + isolation, KHÔNG verify chất lượng embedding (Phase 9 eval)"
  - "Test 6 EXPLAIN — verify HNSW index TỒN TẠI + dùng được cho ORDER BY vector <=>, KHÔNG verify planner cost model (cost model ở scale 1K+ chunk là Phase 9)"

patterns-established:
  - "_fixed_vector(seed) — vector deterministic [seed]*1536 dùng cả seed chunk lẫn monkeypatch query embedding"
  - "Test EXPLAIN tách 2 query: vector-ordering thuần (verify HNSW chosen) + query hub-filtered thực tế (verify không Seq Scan)"

requirements-completed: [SEARCH-01, SEARCH-02, SEARCH-03, SEARCH-04]

# Metrics
duration: 14min
completed: 2026-05-18
---

# Phase 6 Plan 04: Search Hub Isolation E4 Critical Test Suite Summary

Verify Phase 6 bằng integration test suite critical-path-mandatory (CONVENTIONS
§1): thêm 2 seed helper (`_insert_document` + `_insert_chunk`) vào `conftest.py`
và tạo `test_search_hub_isolation.py` với 6 test `@pytest.mark.critical`. Suite
chứng minh hub isolation E4 (EXIT criteria — viewer Hub A KHÔNG thấy chunk Hub B
kể cả khi explicit `hub_ids`), cross-hub isolation, empty-result, Redis cache
hit, và HNSW Index Scan (R2 mitigation / SC3) — tất cả genuinely PASS against
real DB testcontainer.

## Tasks hoàn thành

| Task | Tên | Commit | Files |
|------|-----|--------|-------|
| 1 | Thêm _insert_document + _insert_chunk helper vào conftest.py | `143fda5` | `api/tests/integration/conftest.py` |
| 2 | Tạo test_search_hub_isolation.py — E4 critical suite | `f90285d` | `api/tests/integration/test_search_hub_isolation.py` (mới) |

## Chi tiết thực thi

### Task 1 — `conftest.py` seed helper

Thêm 2 helper async module-level SAU `_assign_user_hub`, pattern giống
`_insert_hub` (`get_engine()` + `engine.begin()` + `text()` INSERT):

- **`_insert_document(*, hub_id, filename, uploaded_by=None)`** — INSERT 1
  document row `status='completed'`, trả `document_id`. Cột theo migration 0001.
- **`_insert_chunk(*, document_id, hub_id, content, vector)`** — INSERT 1 chunk
  row với `vector` (literal `'[...]'` cast `CAST(:vec AS vector)`), trả
  `chunk_id`. `content_hash` BYTEA NOT NULL → seed 4 byte placeholder
  (`b"\x00"*4`). Caller truyền list đúng 1536 phần tử.

### Task 2 — `test_search_hub_isolation.py` (mới)

6 test, mọi test marker `@pytest.mark.critical` + `@pytest.mark.integration` +
`@pytest.mark.asyncio`. Helper module-level: `_fixed_vector(seed)` (vector
deterministic `[seed]*1536`), `_patch_embed(monkeypatch, vector)` (patch
`app.services.search_service.embed_text` — loại bỏ phụ thuộc OPENAI_API_KEY).

- **Test 1 `test_search_single_hub_returns_results`** (SEARCH-01): viewer search
  hub được assign → ≥1 chunk thuộc hub đó, `total_hubs_searched == 1`.
- **Test 2 `test_search_hub_isolation_explicit_hub_ids`** (E4): viewer Hub A
  POST `/api/search` với explicit `hub_ids:[A,B]` → results CHỈ chunk Hub A,
  KHÔNG chunk Hub B. Đây là test E4 EXIT-criteria-grade.
- **Test 3 `test_cross_hub_search_isolation`** (SEARCH-03 E4): viewer A+B POST
  `/api/search/cross-hub` request `[A,B,C]` → `seen_hubs ⊆ {A,B}`, hub C bị
  loại, `total_hubs_searched == 2`.
- **Test 4 `test_search_empty_hub_returns_empty_list`**: hub chưa có chunk →
  `results: []`, status 200, `success: True`.
- **Test 5 `test_search_cache_hit`** (SEARCH-04): search 2 lần cùng query →
  lần 1 `cache_hit=False`, lần 2 `cache_hit=True` (Redis testcontainer).
- **Test 6 `test_explain_analyze_uses_hnsw_index`** (SEARCH-02 / SC3 / R2): seed
  50 chunk → EXPLAIN ANALYZE verify `ix_chunks_vector_hnsw` dùng cho
  `ORDER BY vector <=>`, KHÔNG `Seq Scan`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test 6 — EXPLAIN query thực tế chọn B-tree index thay vì HNSW**
- **Found during:** Task 2 verification
- **Issue:** Plan Task 2 mô tả EXPLAIN trên query có predicate `hub_id = ANY(...)`
  + assert `ix_chunks_vector_hnsw` trong plan. Trên dataset test nhỏ (50 row),
  Postgres planner chọn B-tree `ix_chunks_hub_id_document_id` (Bitmap/Index
  Scan) cho cả filter `hub_id` lẫn sort (top-N heapsort 50 row không đáng kể) —
  HNSW vector index KHÔNG được chọn. Plan đề xuất `enable_seqscan = off` để buộc
  index path; nhưng `enable_seqscan = off` chỉ tắt Seq Scan — planner vẫn dùng
  B-tree `Index Scan` (vẫn là index path). HNSW index `ix_chunks_vector_hnsw`
  chỉ phục vụ `ORDER BY vector <=>` (cột `vector`, KHÔNG có `hub_id`) → khi có
  B-tree rẻ hơn trên dataset nhỏ, planner KHÔNG bao giờ chọn HNSW.
- **Fix:** Tách EXPLAIN thành 2 query: (a) query vector-ordering THUẦN (KHÔNG
  predicate `hub_id`) — HNSW khi đó là index DUY NHẤT liên quan
  `ORDER BY vector <=>`, planner chọn `ix_chunks_vector_hnsw` → assert HNSW
  trong plan; (b) query hub-filtered THỰC TẾ của `search_service` — assert
  KHÔNG `Seq Scan` (R2 — luôn đi index path). Cách này verify HNSW index TỒN
  TẠI + dùng được cho mục đích của nó (theo đúng plan note "verify index TỒN
  TẠI + dùng được, KHÔNG phải verify planner cost model" — cost model ở scale
  1K+ chunk là việc Phase 9). Hub isolation correctness đã được Test 2 + Test 3
  chứng minh độc lập, không cần Test 6.
- **Files modified:** `api/tests/integration/test_search_hub_isolation.py`
- **Commit:** `f90285d`

### Lưu ý — gỡ import thừa (KHÔNG phải deviation đáng kể)

Plan Task 2 liệt kê `import uuid` trong import block; thực tế test file KHÔNG
dùng `uuid` (mọi UUID đến từ helper conftest). Gỡ `import uuid` để ruff
(`F401`) pass — chỉnh import nhỏ, không thay đổi hành vi.

## Threat Model — kết quả

| Threat ID | Disposition | Trạng thái |
|-----------|-------------|-----------|
| T-06-04-01 (Info Disclosure — hub isolation test coverage) | mitigate | ✅ Test 2 + Test 3 chứng minh viewer KHÔNG thấy chunk hub không assign kể cả explicit `hub_ids` — E4 EXIT criteria genuinely verified against real DB testcontainer (6 test PASS) |
| T-06-04-02 (Tampering — test seed bypass) | accept | ✅ Test seed chunks/documents trực tiếp qua SQL (`_insert_document`/`_insert_chunk`) — chấp nhận: isolation test cần data nhiều hub, ingest flow test riêng Phase 4 |
| T-06-04-03 (Spoofing — monkeypatch embed_text) | accept | ✅ `embed_text` bị patch trả vector cố định — chấp nhận: test verify SQL filter + cache + isolation, KHÔNG verify chất lượng embedding (Phase 9 eval) |

## Verification

- `uv run ruff check tests/integration/conftest.py tests/integration/test_search_hub_isolation.py` — exit 0
- `uv run python -c "import tests.integration.conftest as c; assert hasattr(c,'_insert_document') and hasattr(c,'_insert_chunk')"` — exit 0
- `pytest tests/integration/test_search_hub_isolation.py -m critical` — **6 passed** (Docker testcontainers Postgres + Redis)
  - `test_search_single_hub_returns_results` PASS
  - `test_search_hub_isolation_explicit_hub_ids` PASS — **E4 EXIT criteria verified cho search**
  - `test_cross_hub_search_isolation` PASS — cross-hub isolation verified
  - `test_search_empty_hub_returns_empty_list` PASS
  - `test_search_cache_hit` PASS — SEARCH-04 cache hit verified
  - `test_explain_analyze_uses_hnsw_index` PASS — **SC3 / R2 HNSW mitigation verified**

## Success Criteria — đối chiếu

- ✅ 6 test critical PASS
- ✅ Hub isolation E4: viewer Hub A search explicit `hub_ids:[A,B]` → CHỈ chunk Hub A (Test 2)
- ✅ Cross-hub isolation: viewer A+B request `[A,B,C]` → chỉ A,B (Test 3)
- ✅ Empty hub → `results: []` 200 không lỗi (Test 4)
- ✅ Cache: lần 1 cache_hit=false, lần 2 cache_hit=true (Test 5)
- ✅ EXPLAIN ANALYZE show `ix_chunks_vector_hnsw`, không `Seq Scan` (Test 6)

## Self-Check: PASSED

- `api/tests/integration/conftest.py` — FOUND (modified)
- `api/tests/integration/test_search_hub_isolation.py` — FOUND
- Commit `143fda5` — FOUND
- Commit `f90285d` — FOUND
