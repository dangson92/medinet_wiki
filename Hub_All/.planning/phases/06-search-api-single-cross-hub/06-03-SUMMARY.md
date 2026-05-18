---
phase: 06-search-api-single-cross-hub
plan: 03
subsystem: search
tags: [redis-pubsub, cache-invalidation, hub-tagged-cache, asyncio-task, fail-open]

# Dependency graph
requires:
  - phase: 06-search-api-single-cross-hub
    provides: "06-01 — SearchService.search() + _cache_key + cache-write block fail-open"
  - phase: 06-search-api-single-cross-hub
    provides: "06-02 — search_cross_hub() + _cross_cache_key + cache-write block fail-open"
  - phase: 05-hub-user-audit-apikey-settings-crud
    provides: "documents_service.create()/delete() + documents.py DI factory + main.py lifespan asyncio-task pattern"
provides:
  - "app/services/search_cache.py — hub-tagged cache scheme: tag_cache_key + invalidate_hub + publish_invalidate + search_cache_subscriber + invalidate_channel"
  - "search_service.py — tag_cache_key chèn vào cache-write của search() + search_cross_hub()"
  - "documents_service.py — publish hub:{hub_id}:invalidate sau create + delete"
  - "main.py lifespan — search_cache_subscriber asyncio task (step 9) + shutdown cancel"
affects: [06-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Redis Pub/Sub subscriber loop: pubsub.psubscribe(pattern) + async for pubsub.listen() trong asyncio task lifespan (analog mới — codebase chưa có Pub/Sub subscriber)"
    - "Hub-tagged cache invalidation: cache key thêm vào SET search:hubtag:{hub_id} (TTL 600s) → invalidate đọc SET + DEL member — xoá cache theo hub không chạm hub khác"
    - "publish_invalidate best-effort fail-open: Redis None/down → log warning KHÔNG raise (upload/delete vẫn thành công)"
    - "Subscriber task cancel TRƯỚC redis aclose ở shutdown (subscriber dùng redis connection)"

key-files:
  created:
    - "api/app/services/search_cache.py"
  modified:
    - "api/app/services/search_service.py"
    - "api/app/services/documents_service.py"
    - "api/app/routers/documents.py"
    - "api/app/main.py"

key-decisions:
  - "D-12 — cache key scheme hub-tagged set: mỗi cache key thêm vào Redis SET search:hubtag:{hub_id} cho từng hub trong query; invalidate hub X chỉ DEL key gắn X — không cross-hub cache poisoning"
  - "D-12 — wiring publish vào create() + delete() (đúng 2 path tồn tại ở M2); edit/reupload path không có trong documents_service.py M2 — gap chấp nhận có chủ đích, helper publish_invalidate sẵn sàng cho path tương lai"
  - "Subscriber chạy như asyncio task trong lifespan (step 9) — tái dùng pattern audit_task/watchdog_task; chỉ start khi app.state.redis có"
  - "HUBTAG_TTL = 600s — SET hub-tag tự hết hạn nếu subscriber miss event (phòng rò key); kết hợp cache TTL 300s → stale tối đa 5 phút worst-case khi subscriber chết (T-06-03-04 accept)"
  - "tag_cache_key nằm TRONG cùng block try/except fail-open với redis.set ở cả search() và search_cross_hub() — cache tagging fail không làm hỏng search"

patterns-established:
  - "search_cache.py module-level pure async helper — KHÔNG class; import chỉ asyncio/logging/typing (không circular import)"
  - "Channel format validation: subscriber validate len(parts)==3 + parts[0]=='hub' + parts[2]=='invalidate' TRƯỚC khi invalidate — channel rác bỏ qua"

requirements-completed: [SEARCH-04]

# Metrics
duration: 6min
completed: 2026-05-18
---

# Phase 6 Plan 03: Cache Invalidation Pub/Sub cho Search Summary

Hoàn tất SEARCH-04 (D-12) — wire cache invalidation theo event cho search:
tạo `app/services/search_cache.py` với scheme hub-tagged cache key + Redis
Pub/Sub publish + subscriber loop; chèn `tag_cache_key` vào cache-write của
`search()` và `search_cross_hub()`; publish `hub:{hub_id}:invalidate` khi
document upload/delete; chạy subscriber asyncio task trong lifespan. Sau plan,
document mới upload → search lần kế tiếp KHÔNG trả kết quả cũ (cache miss) —
fix Success Criteria #4 ROADMAP. Không có invalidation, cache TTL 300s sẽ trả
stale 5 phút sau mỗi upload.

## Tasks hoàn thành

| Task | Tên | Commit | Files |
|------|-----|--------|-------|
| 1 | Tạo search_cache.py hub-tagged scheme + publish + subscriber + refactor search_service | `85fe632` | `api/app/services/search_cache.py` (mới), `api/app/services/search_service.py` |
| 2 | Wire publish_invalidate vào documents create+delete + subscriber task lifespan | `3b1b6f1` | `api/app/services/documents_service.py`, `api/app/routers/documents.py`, `api/app/main.py` |

## Chi tiết thực thi

### Task 1 — `app/services/search_cache.py` (mới) + refactor `search_service.py`

**`search_cache.py` mới** — module-level async pure helper (KHÔNG class):

- **Constants:** `INVALIDATE_CHANNEL_PATTERN = "hub:*:invalidate"`,
  `HUBTAG_PREFIX = "search:hubtag:"`, `HUBTAG_TTL = 600`.
- **`invalidate_channel(hub_id)`** — trả `f"hub:{hub_id}:invalidate"`.
- **`tag_cache_key(redis, cache_key, hub_ids)`** — gắn cache key vào SET
  `search:hubtag:{hub_id}` cho mỗi hub + `expire` TTL 600s; best-effort
  fail-open (Redis None / lỗi → log warning, KHÔNG raise).
- **`invalidate_hub(redis, hub_id)`** — đọc SET `search:hubtag:{hub_id}`,
  `DEL` mọi member + `DEL` chính SET; trả số key đã xoá; fail-open.
- **`publish_invalidate(redis, hub_id)`** — publish channel
  `hub:{hub_id}:invalidate` value `"1"`; best-effort fail-open (precedent
  fail-open documents_service / auth dependencies).
- **`search_cache_subscriber(redis)`** — subscriber loop: `pubsub.psubscribe`
  pattern → `async for message in pubsub.listen()` → lọc `type == "pmessage"`
  → tách `hub_id` từ channel + validate format chặt (`len(parts)==3` +
  `parts[0]=="hub"` + `parts[2]=="invalidate"`) → `invalidate_hub`.
  `CancelledError` → log + re-raise; lỗi khác → log warning (KHÔNG crash
  lifespan); `finally` đóng pubsub. `decode_responses=True` → channel là `str`.

**Refactor `search_service.py`** — `import tag_cache_key`; chèn
`await tag_cache_key(self.redis, cache_key, hub_ids)` vào cache-write block
của CẢ `search()` (single-hub) LẪN `search_cross_hub()` (cross-hub), NẰM TRONG
cùng block `try/except` fail-open với `redis.set` tương ứng. Dùng đúng biến
`hub_ids` đã intersect và đúng `cache_key` của mỗi method. KHÔNG đổi logic
search khác.

### Task 2 — wire `documents_service.py` + `documents.py` + `main.py`

**`documents_service.py`** — `import publish_invalidate` đầu file (không
circular — `search_cache` chỉ import asyncio/logging/typing).
`DocumentService.__init__` thêm param `redis: Any = None` → `self.redis`.
`create()` publish `await publish_invalidate(self.redis, str(hub_id))` NGAY
SAU `db.commit()` + log `document_created`. `delete()` publish sau bước 4
(INSERT audit_logs) + TRƯỚC bước 5 (xoá file), bọc `if hub_id is not None`.

**`documents.py`** — `get_document_service` thêm param `request: Request`,
đọc `redis = getattr(request.app.state, "redis", None)` → truyền
`DocumentService(db=db, redis=redis)`. `Request` đã import sẵn từ `fastapi`.

**`main.py`** — lifespan step 9 sau audit task: tạo
`app.state.search_cache_task = asyncio.create_task(search_cache_subscriber(
app.state.redis))` CHỈ khi `app.state.redis is not None`, bọc try/except
KHÔNG crash lifespan. Shutdown: cancel `search_cache_task` SAU audit task
cancel + TRƯỚC `dispose_engine` (subscriber dùng redis connection — phải
cancel TRƯỚC `redis.aclose()` ở cuối shutdown).

## Phạm vi scope có chủ đích (D-12 vs codebase M2)

D-12 liệt kê upload/edit/delete path. Codebase M2 `documents_service.py` CHỈ
có `create()` + `delete()` — KHÔNG có content-edit/reupload method (xác nhận
PATTERNS.md §documents_service). Plan wire `publish_invalidate` vào ĐÚNG 2 path
tồn tại. Edit-invalidation KHÔNG bị bỏ sót: khi edit/reupload path được thêm ở
phase tương lai, chỉ cần thêm 1 dòng `await publish_invalidate(self.redis,
str(hub_id))` — `publish_invalidate` đã là helper dùng chung. Đây là gap được
nhận diện và chấp nhận có chủ đích, KHÔNG phải thiếu sót.

## Deviations from Plan

None — plan executed exactly as written. Cả 2 task áp dụng paste-ready code
nguyên xi; cache-write block của `search()` + `search_cross_hub()` đã có
try/except fail-open sẵn từ 06-01/06-02 nên không cần dùng nhánh FALLBACK
(không cần bọc thêm try/except mới).

## Threat Model — kết quả

| Threat ID | Disposition | Trạng thái |
|-----------|-------------|-----------|
| T-06-03-01 (Tampering — subscriber channel parse) | mitigate | ✅ `psubscribe("hub:*:invalidate")` + validate `len(parts)==3 and parts[0]=="hub" and parts[2]=="invalidate"` TRƯỚC khi invalidate — channel rác bỏ qua |
| T-06-03-02 (Info Disclosure — hub-tagged invalidation) | mitigate | ✅ cache key gắn SET `search:hubtag:{hub_id}`; `invalidate_hub` CHỈ DEL key của hub đó — không cross-hub cache poisoning |
| T-06-03-03 (DoS — publish trong upload/delete path) | mitigate | ✅ `publish_invalidate` best-effort fail-open — Redis down KHÔNG raise, create/delete vẫn thành công |
| T-06-03-04 (DoS — subscriber loop crash) | accept | ✅ subscriber bọc try/except KHÔNG crash lifespan; loop chết → cache TTL 300s + HUBTAG_TTL 600s tự hết hạn (stale tối đa 5 phút). Chấp nhận M2 |
| T-06-03-05 (Repudiation — invalidation event) | accept | ✅ invalidation log qua `logger.info` (không audit_logs) — cache là tối ưu hiệu năng, không phải security control cần forensic trail |

## Verification

- `uv run ruff check` 5 file (search_cache.py, search_service.py,
  documents_service.py, documents.py, main.py) — exit 0
- `uv run mypy --strict` 5 file — exit 0 (Success: no issues found in 5 source files)
- `uv run python -c "from app.main import create_app; create_app()"` — exit 0
  (create_app OK with search cache wiring)
- `invalidate_channel('abc') == 'hub:abc:invalidate'` — assert PASS
- `grep -c "tag_cache_key" search_service.py` = 5 (1 import + 2 call +
  2 comment) — vượt ngưỡng >= 3
- `search_cache_subscriber` / `publish_invalidate` / `invalidate_hub` /
  `psubscribe` đều có trong `search_cache.py` ✅
- `git diff --diff-filter=D HEAD~2 HEAD` — rỗng (không xoá file ngoài ý muốn)

## Carry-over cho 06-04

- 06-04 integration test cache invalidation thực sự: upload document mới vào
  hub → search lần kế tiếp `cache_hit=false` (không trả stale). Cần
  testcontainer Redis có Pub/Sub + đợi subscriber xử lý event (Pub/Sub
  bất đồng bộ — test cần `asyncio.sleep` ngắn hoặc poll).
- Subscriber task chỉ start khi `app.state.redis is not None` — test cần
  Redis container up; nếu test không có Redis, subscriber không chạy nhưng
  cache cũng không hoạt động (fail-open) → không trả stale theo cách khác.

## Self-Check: PASSED

- `api/app/services/search_cache.py` — FOUND
- `api/app/services/search_service.py` — FOUND (modified)
- `api/app/services/documents_service.py` — FOUND (modified)
- `api/app/routers/documents.py` — FOUND (modified)
- `api/app/main.py` — FOUND (modified)
- Commit `85fe632` — FOUND
- Commit `3b1b6f1` — FOUND
