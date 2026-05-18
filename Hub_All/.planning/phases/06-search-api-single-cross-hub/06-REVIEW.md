---
phase: 06-search-api-single-cross-hub
reviewed: 2026-05-18T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - Hub_All/api/app/main.py
  - Hub_All/api/app/routers/__init__.py
  - Hub_All/api/app/routers/documents.py
  - Hub_All/api/app/routers/search.py
  - Hub_All/api/app/schemas/__init__.py
  - Hub_All/api/app/schemas/search.py
  - Hub_All/api/app/services/documents_service.py
  - Hub_All/api/app/services/search_cache.py
  - Hub_All/api/app/services/search_service.py
  - Hub_All/api/tests/integration/conftest.py
  - Hub_All/api/tests/integration/test_search_hub_isolation.py
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# Phase 6: Báo cáo Code Review

**Reviewed:** 2026-05-18
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Tóm tắt

Review tập trung vào phần thay đổi Phase 6 (Search API Single + Cross-Hub): search router mount, lifespan step 9 subscriber, DI redis param, và search service / search cache mới. Phần code pre-existing trong `main.py`, `documents.py`, `routers/__init__.py` nằm ngoài phạm vi.

Đánh giá tổng thể: chất lượng tốt. Hub isolation defense-in-depth (D-07) được triển khai đúng — `intersect_hubs()` lọc lớp service TRƯỚC SQL, và SQL filter lại bằng `c.hub_id = ANY($N::uuid[])`. Mọi SQL dùng bind param hoặc literal đã được parametrize qua asyncpg/SQLAlchemy — không phát hiện SQL injection. Cache key băm SHA-256 trên `query|hub_ids|top_k|min_score` với `hub_ids` đã intersect nên cache hub-scoped đúng — không phát hiện cache poisoning trực tiếp.

**KHÔNG có vấn đề Critical.** Phát hiện 4 Warning và 5 Info — chủ yếu liên quan edge case re-rank cross-hub, cache key thiếu phân biệt admin-scope, và một vài chi tiết quality.

## Warnings

### WR-01: Cache key KHÔNG phân biệt admin-all với non-admin → nguy cơ trả kết quả sai scope

**File:** `Hub_All/api/app/services/search_service.py:246` (và `:344`)
**Issue:** `_cache_key(body.query, hub_ids, top_k, body.min_score)` được tính TỪ `hub_ids` sau `intersect_hubs()`. Với admin gọi search KHÔNG truyền `hub_ids`, `intersect_hubs()` trả `[]` (sentinel admin-all) và `is_admin_all=True`. Cache key khi đó băm trên `hub_ids=[]`.

Một non-admin user chưa được assign hub nào cũng có `hub_ids=[]` — nhưng nhánh đó đã return empty result sớm (dòng 237) nên KHÔNG ghi cache, do đó không đụng cache key của admin-all. Tuy nhiên rủi ro thực sự: hai admin khác nhau, hoặc cùng admin tại hai thời điểm corpus khác nhau, share chung 1 cache key `search:<hash của []>`. Quan trọng hơn — khi 1 hub mới được tạo/document mới upload, `publish_invalidate` chỉ phát `hub:{hub_id}:invalidate`, và `tag_cache_key` cho nhánh admin-all gắn cache key vào... `hub_ids=[]` tức KHÔNG hub nào (vòng `for hub_id in hub_ids` rỗng). Hệ quả: cache admin-all KHÔNG BAO GIỜ bị invalidate khi document thay đổi → admin nhận kết quả search stale tới khi TTL 300s hết hạn.

**Fix:** Với nhánh admin-all, sau khi xác định tập hub thực sự query (đã có ở `search_cross_hub` qua `SELECT id FROM hubs WHERE is_active = TRUE`), dùng tập đó làm input cho `tag_cache_key` để cache được gắn tag đúng và invalidate được. Với `search()` (single SQL union), cần resolve danh sách hub active TRƯỚC khi tính cache key hoặc tag, ví dụ:
```python
if is_admin_all:
    async with self.pool.acquire() as conn:
        active = await conn.fetch("SELECT id FROM hubs WHERE is_active = TRUE")
    tag_hub_ids = [str(r["id"]) for r in active]
else:
    tag_hub_ids = hub_ids
# ... dùng tag_hub_ids cho tag_cache_key (cache key vẫn có thể giữ [] cho admin-all)
await tag_cache_key(self.redis, cache_key, tag_hub_ids)
```
Tối thiểu: ghi rõ trade-off "admin-all cache chỉ TTL-expire, KHÔNG event-invalidate" vào docstring nếu chấp nhận ở M2.

### WR-02: Cross-hub re-rank cắt top-k TRƯỚC khi áp min_score → kết quả bị thiếu

**File:** `Hub_All/api/app/services/search_service.py:376-380`
**Issue:** Trong `search_cross_hub`, thứ tự xử lý là: sort toàn bộ rows theo score → `all_rows[:top_k]` (dòng 376) → SAU ĐÓ mới lọc `min_score` (dòng 379-380). Nếu trong top_k rows đầu có vài row dưới `min_score`, chúng bị loại và kết quả cuối có ÍT HƠN `top_k` item, mặc dù tồn tại row hợp lệ (score >= min_score) ở vị trí `top_k+1` trở đi đáng lẽ phải được đôn lên.

`search()` (single-hub) không có lỗi này vì SQL `LIMIT` áp trên toàn bộ rows đã sort và `min_score` lọc sau cũng chấp nhận được — nhưng cross-hub aggregate thì khác: việc cắt `[:top_k]` xảy ra trong Python sau khi đã gom đủ rows từ mọi hub.

**Fix:** Lọc `min_score` TRƯỚC khi cắt top-k:
```python
all_rows.sort(key=lambda r: float(r["score"]), reverse=True)
if body.min_score is not None:
    all_rows = [r for r in all_rows if float(r["score"]) >= body.min_score]
items = [_row_to_item(r) for r in all_rows[:top_k]]
```

### WR-03: `find_similar` cross-hub trả về toàn bộ chunk của mọi hub active, không giới hạn theo hub user

**File:** `Hub_All/api/app/services/search_service.py:421-437`
**Issue:** Trong `find_similar`, khi user là admin và KHÔNG truyền `hub_id`, `is_admin_all=True` và `_run_vector_query` được gọi với `all_hubs=True` — đúng. Nhưng với non-admin: `requested = [body.hub_id] if body.hub_id else None`. Nếu non-admin KHÔNG truyền `hub_id`, `requested=None` → `intersect_hubs(None, user_hub_ids, role)` trả `sorted(set(user_hub_ids) & set(user_hub_ids))` = toàn bộ hub user — đúng, hợp lý.

Vấn đề tinh tế hơn: `_run_vector_query` được gọi với `all_hubs=is_admin_all`. Với non-admin có `hub_ids` non-empty, `all_hubs=False` → SQL nhánh `ANY($2::uuid[])` đúng. OK. Nhưng nếu `body.hub_id` được truyền là một hub user KHÔNG được assign, `intersect_hubs` loại nó → `hub_ids=[]` → nhánh `not is_admin_all and not hub_ids` (dòng 426) return empty — đúng.

Đây KHÔNG phải lỗ hổng isolation thực sự (defense-in-depth giữ vững), nhưng `find_similar` KHÔNG cache và KHÔNG có `MAX_TOP_K` clamp riêng — `top_k = DEFAULT_TOP_K` hardcoded (dòng 420). Nếu admin-all với corpus lớn, query quét mọi chunk active mỗi lần gọi không cache → chi phí lặp lại. Đồng thời `threshold` không bị clamp [0,1], client gửi `threshold=-5` thì lọc vô nghĩa nhưng không sai an toàn.

**Fix:** Xác nhận chủ ý "find_similar không cache" (D-04 ghi vậy — chấp nhận được). Nên thêm validate/clamp `body.threshold` vào `[0.0, 1.0]` để tránh nhận giá trị vô nghĩa, và cân nhắc giới hạn admin-all `find_similar` hoặc ghi rõ chi phí vào docstring. Đây là Warning mức thấp — đánh dấu để Phase 9 perf xử lý nếu không fix ngay.

### WR-04: Race condition cache invalidation — invalidate có thể chạy TRƯỚC khi cache được ghi

**File:** `Hub_All/api/app/services/documents_service.py:236` + `Hub_All/api/app/services/search_cache.py:42-57`
**Issue:** Luồng: upload document → `publish_invalidate` phát event → subscriber chạy `invalidate_hub` xoá SET `search:hubtag:{hub_id}` và mọi member. Nhưng nếu một search request cho cùng hub đang chạy ĐỒNG THỜI: search có thể đọc cache miss, query DB (chưa thấy document mới vì transaction upload chưa commit hoặc vừa commit), rồi `redis.set` + `tag_cache_key` GHI cache SAU khi `invalidate_hub` đã chạy xong. Kết quả: cache stale tồn tại tới TTL 300s.

Đây là race kinh điển của cache-aside + invalidation, khó loại bỏ hoàn toàn không có versioning. Tác động giới hạn: chỉ stale tối đa 300s, và `HUBTAG_TTL=600` đảm bảo SET hub-tag không rò vĩnh viễn. Không phải lỗi an toàn (không cross-hub leak — cache vẫn hub-scoped đúng).

**Fix:** Chấp nhận được ở M2 nếu ghi rõ trade-off "cửa sổ stale tối đa = CACHE_TTL_SECONDS khi invalidate race với cache write" vào docstring `search_cache.py`. Giải pháp triệt để (defer): dùng version counter per-hub (`INCR hub:{id}:ver`) đưa vào cache key, hoặc invalidate bằng cách bump version thay vì DEL. Đánh dấu cho Phase 9.

## Info

### IN-01: `_to_pgvector_literal` dùng `repr(float(x))` — phụ thuộc định dạng repr của Python

**File:** `Hub_All/api/app/services/search_service.py:68-70`
**Issue:** Vector literal được build bằng `repr(float(x))`. `repr` của float trên CPython trả chuỗi round-trippable (vd `0.1`, `1e-05`), pgvector parse được. Tuy nhiên đây là phụ thuộc ngầm vào hành vi `repr`; với giá trị như `float('inf')`/`float('nan')` (không xảy ra với embedding hợp lệ nhưng vẫn) sẽ tạo literal pgvector từ chối. Vector đến từ `embed_text` đã validate dim nhưng KHÔNG validate finite.
**Fix:** Dùng format tường minh `f"{float(x):.9g}"` hoặc `json.dumps` cho list số; hoặc truyền vector như tham số `$N` kiểu `vector` thay vì literal string (asyncpg hỗ trợ register codec). Mức Info — không phải bug thực tế với input hợp lệ.

### IN-02: `search()` đọc cache TRƯỚC khi embed nhưng tính cache key dùng `body.min_score`, trong khi min_score cũng được filter sau

**File:** `Hub_All/api/app/services/search_service.py:246` + `271-272`
**Issue:** Cache key bao gồm `min_score`, và kết quả ghi cache là kết quả ĐÃ lọc `min_score`. Đúng về mặt correctness. Nhưng hệ quả: hai request cùng query/hub khác `min_score` tạo 2 cache entry tách biệt dù có thể dùng chung kết quả thô. Không phải bug — chỉ là cache hit rate thấp hơn mức tối ưu.
**Fix:** Cân nhắc cache kết quả CHƯA lọc min_score (key bỏ min_score) rồi lọc min_score sau khi đọc cache. Defer — tối ưu hiệu năng ngoài scope M2.

### IN-03: `_truncate_snippet` rsplit có thể trả chuỗi rỗng khi 300 ký tự đầu không có space

**File:** `Hub_All/api/app/services/search_service.py:81-83`
**Issue:** `head.rsplit(" ", 1)[0]` — nếu `content[:300]` không chứa space nào (vd nội dung CJK không dấu cách, hoặc 1 token rất dài), `rsplit` trả `[head]` và `[0]` = nguyên `head` — OK thực ra. Nhưng nếu space nằm ở vị trí 0 (`" abc..."`), `rsplit` trả `["", "abc..."]` và `[0]` = `""` → snippet thành chỉ `"…"`. Nội dung tiếng Việt có dấu cách nên hiếm gặp, nhưng vẫn là edge case làm mất snippet.
**Fix:** Fallback khi phần cắt rỗng: `cut = head.rsplit(" ", 1)[0] or head`.

### IN-04: `search_cache_subscriber` nuốt mọi exception non-cancel → subscriber chết âm thầm

**File:** `Hub_All/api/app/services/search_cache.py:120-133`
**Issue:** Vòng `async for message in pubsub.listen()` nằm trong `try`; nếu `pubsub.listen()` raise (vd Redis connection drop giữa chừng) exception non-`CancelledError` bị log warning rồi `finally` đóng pubsub — task kết thúc. Subscriber KHÔNG tự khởi động lại; kể từ đó mọi invalidation event bị bỏ lỡ, cache stale tới TTL. `main.py` cũng không giám sát task này sau khi tạo.
**Fix:** Bọc vòng listen trong retry loop (reconnect + psubscribe lại sau backoff) cho lỗi non-cancel, thay vì thoát hẳn. Tối thiểu nâng log lên `error` level để alerting bắt được. Mức Info vì cache fail-open (search vẫn đúng, chỉ stale) — nhưng nên cải thiện độ bền.

### IN-05: `tag_cache_key` gọi `sadd` + `expire` tuần tự — N round-trip Redis, không atomic

**File:** `Hub_All/api/app/services/search_cache.py:51-55`
**Issue:** Vòng lặp gọi `await redis.sadd(...)` rồi `await redis.expire(...)` riêng cho từng hub — với cross-hub nhiều hub là 2N round-trip. Không sai logic (best-effort fail-open) nhưng kém hiệu quả; cũng có khoảng giữa `sadd` và `expire` mà key chưa có TTL (nếu process chết giữa chừng → key rò, nhưng `invalidate_hub` cũng DEL nên impact thấp).
**Fix:** Gộp bằng pipeline: `async with redis.pipeline() as pipe: ... await pipe.execute()`. Tối ưu Info.

---

_Reviewed: 2026-05-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
