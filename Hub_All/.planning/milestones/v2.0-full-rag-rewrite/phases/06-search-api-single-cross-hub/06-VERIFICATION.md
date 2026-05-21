---
phase: 06-search-api-single-cross-hub
verified: 2026-05-18T00:00:00Z
status: human_needed
score: 4/6 success criteria verified (2 cần human — không có dataset 5K/eval set ở M2)
overrides_applied: 0
human_verification:
  - test: "Đo latency p95 GET/POST /api/search trên dataset 5K chunks thật (single hub)"
    expected: "p95 < 800ms"
    why_human: "Repo M2 không có dataset 5K chunks (chunks table rỗng — Phase 9 mới dựng eval set). Test 06-04 chỉ seed ~50 chunk synthetic, không đủ để đo p95 có ý nghĩa. Cần dataset thật + load test."
  - test: "Đo latency p95 POST /api/search/cross-hub trên dataset thật nhiều hub"
    expected: "p95 < 1.5s"
    why_human: "Cùng lý do — chưa có dataset thật; fan-out asyncio.gather chỉ verify được hành vi đúng, không verify được số latency."
  - test: "Recall sanity check 50 query VN sample (manual review) — chuẩn bị data cho Phase 9"
    expected: "Top-k chunks trả về liên quan ngữ nghĩa câu truy vấn VN"
    why_human: "SC5 yêu cầu manual review chất lượng retrieval. M2 dùng OPENAI_API_KEY placeholder + chunks table rỗng; eval dataset thật do Phase 9 (EVAL-01..04) dựng. Test 06-04 monkeypatch embed_text nên không verify được recall thật."
  - test: "End-to-end cache invalidation qua Pub/Sub: search hub X (cache_hit=true lần 2) → upload document mới vào hub X → search lại → cache_hit=false"
    expected: "Search sau upload trả cache miss (không stale) trong vài trăm ms (subscriber xử lý Pub/Sub bất đồng bộ)"
    why_human: "Wiring publish_invalidate (create/delete) + search_cache_subscriber + tag_cache_key đã verify tồn tại và đúng logic qua code; test 06-04 verify cache HIT (test 5) nhưng KHÔNG có test verify cache INVALIDATE-sau-upload end-to-end. Subscriber Pub/Sub bất đồng bộ — cần chạy stack thật + thao tác upload để xác nhận luồng đóng kín."
---

# Phase 6: Search API Single + Cross-Hub — Báo cáo Verification

**Phase Goal:** Người dùng có thể search trong hub đơn hoặc cross-hub (chỉ hub được assigned), kết quả top-k chunks pgvector với latency p95 <800ms (single hub) và <1.5s (cross-hub).
**Verified:** 2026-05-18
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| #  | Truth (Success Criteria) | Status | Evidence |
| -- | ------------------------ | ------ | -------- |
| SC1 | `POST /api/search` trả top-k chunks theo cosine similarity, hub filter enforce — viewer Hub A KHÔNG thấy chunk Hub B; latency p95 <800ms ở 5K chunks | ⚠️ PARTIAL | Endpoint mount + cosine SQL (`1 - (c.vector <=> $1::vector)`) + hub isolation đã verify (test `test_search_single_hub_returns_results` + `test_search_hub_isolation_explicit_hub_ids` PASS). **Latency p95 <800ms KHÔNG verify được** — không có dataset 5K. → human |
| SC2 | `POST /api/search/cross-hub` parallel `asyncio.gather` → aggregate + re-rank theo score; result kèm hub_id; viewer A+B request [A,B,C] → C bị filter ở repo layer | ⚠️ PARTIAL | `search_cross_hub` fan-out `asyncio.gather(*[_search_one(h) ...])` + `all_rows.sort(reverse=True)` + `intersect_hubs` defense-in-depth — verify code + test `test_cross_hub_search_isolation` PASS (viewer A+B request [A,B,C] → `seen_hubs ⊆ {A,B}`, `total_hubs_searched == 2`). **Latency p95 <1.5s KHÔNG verify được.** → human |
| SC3 | `EXPLAIN ANALYZE` show `Index Scan using ix_chunks_vector_hnsw` (KHÔNG Seq Scan) trên 1K+ chunks | ✓ VERIFIED (confidence: partial) | Test `test_explain_analyze_uses_hnsw_index` PASS — assert `ix_chunks_vector_hnsw` trong EXPLAIN plan + `Seq Scan` không xuất hiện. **Lưu ý:** test seed ~50 chunk (KHÔNG 1K+) và đặt `SET LOCAL enable_seqscan = off`; xác nhận index TỒN TẠI + dùng được cho `ORDER BY vector <=>`. Verify cost-model ở scale 1K+ là việc Phase 9. Deviation đã ghi nhận có chủ đích trong 06-04-SUMMARY (Auto-fixed #1). |
| SC4 | Redis cache: 2 lần gọi giống nhau trong 5 phút → lần 2 hit; upload document mới → cache invalidate qua Pub/Sub `hub:{hub_id}:invalidate` | ⚠️ PARTIAL | Cache HIT verified — test `test_search_cache_hit` PASS (lần 1 `cache_hit=false`, lần 2 `cache_hit=true`). Invalidation wiring đầy đủ trong code (publish_invalidate ở create/delete, subscriber lifespan, tag_cache_key, hub-tagged SET) — nhưng **KHÔNG có test end-to-end verify invalidate-sau-upload**. → human |
| SC5 | Recall sanity check 50 query VN sample (manual review) — chuẩn bị data cho Phase 9 | ❓ HUMAN | Không có eval dataset thật ở M2 (Phase 9 dựng EVAL-01..04). Test 06-04 monkeypatch `embed_text` → không verify được recall thật. → human |

**Score:** SC3 verified (confidence partial); SC1/SC2/SC4 PARTIAL (phần hành vi PASS, phần latency/invalidation cần human); SC5 human.

### Plan must_haves (06-01..06-04) — đối chiếu codebase

| Plan | Must-have truth | Status | Evidence |
| ---- | --------------- | ------ | -------- |
| 06-01 | Service embed query qua `embed_text()` + raw vector SQL trên asyncpg pool | ✓ VERIFIED | `search_service.py:260` `embed_text(body.query)`; `_run_vector_query` dùng `pool.acquire()` + raw SQL |
| 06-01 | Set HNSW session config trước mỗi vector query | ✓ VERIFIED | `search_service.py:181-183` 3 dòng `SET LOCAL hnsw.ef_search=200 / iterative_scan=relaxed_order / max_scan_tuples=20000` trong `conn.transaction()` |
| 06-01 | `intersect_hubs` giao hub TRƯỚC SQL (defense in depth lớp 1) | ✓ VERIFIED | `search_service.py:116-132` `intersect_hubs`; gọi ở `search()`/`search_cross_hub()`/`find_similar()` |
| 06-01 | Redis cache key sha256, TTL 300s, set `cache_hit` đúng | ✓ VERIFIED | `_cache_key` sha256 prefix `search:`; `CACHE_TTL_SECONDS=300`; `redis.set(..., ex=300)` |
| 06-01 | Empty result trả `results: []` KHÔNG raise | ✓ VERIFIED | `search_service.py:237-243`; test `test_search_empty_hub_returns_empty_list` PASS |
| 06-02 | 3 endpoint POST `/api/search`, `/cross-hub`, `/similar` reachable | ✓ VERIFIED | `create_app()` boot OK — 3 path mounted (chạy xác nhận) |
| 06-02 | Cross-hub `asyncio.gather` fan-out + re-rank theo score | ✓ VERIFIED | `search_service.py:362-376` `_search_one` + `asyncio.gather` + `sort(reverse=True)` |
| 06-02 | Cả 3 endpoint decorate `@limiter.limit(SEARCH_LIMIT)` | ✓ VERIFIED | `routers/search.py:60,79,98` — 3 decorator |
| 06-03 | Document upload/delete publish `hub:{hub_id}:invalidate` | ✓ VERIFIED | `documents_service.py:236` (create) + `:419` (delete) `publish_invalidate(self.redis, str(hub_id))` |
| 06-03 | Subscriber asyncio task lắng nghe `hub:*:invalidate` | ✓ VERIFIED | `search_cache.py:98` `search_cache_subscriber` `psubscribe`; `main.py:226-236` task start, `:273-281` cancel |
| 06-03 | Cache key hub-tagged (invalidate 1 hub không xoá hub khác) | ✓ VERIFIED | `search_cache.py` `tag_cache_key`/`invalidate_hub` qua SET `search:hubtag:{hub_id}` |
| 06-04 | 6 test critical PASS (hub isolation E4 + cross-hub + empty + cache + EXPLAIN) | ✓ VERIFIED | `pytest test_search_hub_isolation.py -m critical` → **6 passed in 14.53s** |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `api/app/schemas/search.py` | 7 Pydantic model khớp api.ts | ✓ VERIFIED | 7 class (SearchFilters/SearchRequest/SimilarRequest/SearchResultItem/SearchResponse/SimilarMatch/SimilarResponse); field `query` (KHÔNG `q`); barrel export `__init__.py` đủ 7 tên |
| `api/app/services/search_service.py` | SearchService.search() + search_cross_hub() + find_similar() | ✓ VERIFIED | 457 dòng; 3 method đầy đủ + helper module-level; HNSW tuning, cache, intersect, fan-out |
| `api/app/routers/search.py` | 3 POST endpoint + DI factory | ✓ VERIFIED | 114 dòng; 3 endpoint, `get_search_service` DI đọc `db_pool`+`redis` |
| `api/app/services/search_cache.py` | hub-tagged scheme + publish + subscriber | ✓ VERIFIED | 139 dòng; `tag_cache_key`/`invalidate_hub`/`publish_invalidate`/`search_cache_subscriber`/`invalidate_channel` |
| `api/tests/integration/test_search_hub_isolation.py` | 6 critical test | ✓ VERIFIED | 358 dòng; 6 test `@pytest.mark.critical` — 6 passed |
| `api/tests/integration/conftest.py` | `_insert_document` + `_insert_chunk` helper | ✓ VERIFIED | 2 helper tồn tại (import OK, dùng trong test) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `main.py create_app()` | `routers/search.py` | `include_router(search_router)` | ✓ WIRED | `main.py:378-380`; `create_app()` boot → 3 path mounted |
| `routers/search.py` | `search_service.py` | `SearchService(pool=, redis=)` | ✓ WIRED | `get_search_service` factory |
| `search_service.py` | `embedder.py` | `embed_text(body.query)` | ✓ WIRED | `search_service.py:39,260,358,430` |
| `search_service.py` | asyncpg pool | `pool.acquire() + SET LOCAL hnsw.*` | ✓ WIRED | `_run_vector_query` |
| `documents_service.py` | Redis Pub/Sub `hub:{id}:invalidate` | `publish_invalidate` | ✓ WIRED | create + delete path |
| `main.py lifespan` | `search_cache.py search_cache_subscriber` | `asyncio.create_task` | ✓ WIRED | `main.py:226-236` start + `:273-281` cancel |
| `search_service.py` | `search_cache.py tag_cache_key` | cache-write block | ✓ WIRED | `search():290` + `search_cross_hub():399` trong block fail-open |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| App boot + search router mount | `create_app()` + assert 3 path | OK — 3 search endpoint mounted | ✓ PASS |
| Search critical suite | `pytest test_search_hub_isolation.py -m critical` | 6 passed in 14.53s | ✓ PASS |
| Regression Phase 5 documents (redis param backward-compat) | `pytest test_documents_list_delete.py` | 7 passed in 17.91s | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Mô tả | Status | Evidence |
| ----------- | ----------- | ----- | ------ | -------- |
| SEARCH-01 | 06-01/02/04 | Single-hub vector search (embed query + raw SQL pgvector) | ✓ SATISFIED | `search()` + `_run_vector_query` + test 1/2 PASS. (D-01: dùng POST+JSON thay GET — frontend contract D6 thắng, đã ghi CONTEXT) |
| SEARCH-02 | 06-01/02/04 | Per-query HNSW session config | ✓ SATISFIED | 3 dòng `SET LOCAL hnsw.*`; test 6 EXPLAIN PASS |
| SEARCH-03 | 06-02/04 | `POST /api/search/cross-hub` parallel + re-rank + isolation | ✓ SATISFIED | `search_cross_hub` fan-out + test 3 PASS |
| SEARCH-04 | 06-01/03/04 | Redis cache + invalidate Pub/Sub | ✓ SATISFIED (cache hit) / ⚠️ invalidate end-to-end chưa test | `search_cache.py` + test 5 cache hit PASS; invalidate-sau-upload → human |

Tất cả 4 REQ-ID (SEARCH-01..04) được khai báo trong PLAN frontmatter và khớp REQUIREMENTS.md §SEARCH — **không có REQ-ID orphan**. `/api/search/similar` là addition D-04 (không có REQ-ID — đúng quyết định CONTEXT).

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
| ---- | ------- | -------- | ------ |
| — | Không phát hiện stub/TODO/placeholder/empty-impl trong code Phase 6 | ℹ️ Info | Code substantive, không phải placeholder |
| `test_search_hub_isolation.py:327` | `SET LOCAL enable_seqscan = off` trong test EXPLAIN | ℹ️ Info | Đã ghi nhận có chủ đích (06-04-SUMMARY Auto-fixed #1) — verify index TỒN TẠI + dùng được, không verify planner cost model ở scale lớn |

REVIEW.md (06-REVIEW.md) phát hiện 4 Warning (WR-01..04) — KHÔNG có Critical. Các Warning đáng lưu ý:
- **WR-01:** cache admin-all gắn tag vào `hub_ids=[]` → cache admin-all KHÔNG bị event-invalidate, chỉ TTL-expire 300s. Tác động giới hạn admin (corpus stale tối đa 5 phút) — không phải lỗ hổng isolation. Không block goal.
- **WR-02:** `search_cross_hub` cắt `top_k` TRƯỚC khi áp `min_score` → khi `min_score` được dùng, kết quả có thể ít hơn top_k. Edge case correctness, không phải security. Không block goal phase nhưng nên fix ở Phase tương lai/9.
- **WR-03/04:** find_similar không clamp threshold; race cache invalidate — đều mức thấp, accept M2.

Các Warning này không làm vỡ phase goal — đánh dấu để Phase 9 (perf/eval) cân nhắc.

### Human Verification Required

1. **Latency p95 single-hub <800ms** — đo trên dataset 5K chunks thật. Lý do human: repo không có dataset 5K (chunks rỗng M2; Phase 9 dựng eval set).
2. **Latency p95 cross-hub <1.5s** — đo trên dataset thật nhiều hub. Cùng lý do.
3. **Recall sanity check 50 query VN (SC5)** — manual review chất lượng retrieval. Cần eval dataset thật + OpenAI API key thật (M2 dùng placeholder).
4. **Cache invalidation end-to-end** — search hub X (cache_hit lần 2) → upload document mới hub X → search lại → cache_hit=false. Wiring đã verify qua code nhưng chưa có integration test đóng kín luồng Pub/Sub.

### Gaps Summary

Không có gap blocking goal. Toàn bộ artifact tồn tại, substantive, wired, và 6 test critical PASS — chứng minh hành vi cốt lõi: search single/cross-hub, hub isolation E4 (defense in depth), empty result, cache hit, HNSW index dùng được. Regression Phase 5 (documents create/delete với `redis` param mới) PASS — `redis` mặc định `None`, `publish_invalidate` fail-open, backward-compatible.

Phần CHƯA verify được bằng automation là các con số định lượng (p95 latency, recall %) và luồng invalidation end-to-end — đều phụ thuộc dataset thật / eval set mà M2 chưa có (Phase 9 dựng). Đây KHÔNG phải lỗi implementation — đúng như ghi chú phase: SC1/SC2 latency + SC5 recall vốn là human verification items. Status `human_needed` phản ánh trung thực: code đạt goal về mặt hành vi, các ngưỡng số cần human đo trên môi trường thật.

---

_Verified: 2026-05-18_
_Verifier: Claude (gsd-verifier)_
