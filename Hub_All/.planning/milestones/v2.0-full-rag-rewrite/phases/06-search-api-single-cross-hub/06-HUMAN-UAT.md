---
status: partial
phase: 06-search-api-single-cross-hub
source: [06-VERIFICATION.md]
started: 2026-05-18T00:00:00Z
updated: 2026-05-18T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Latency p95 search single-hub <800ms (SC1)
expected: Trên dataset ~5K chunks thật, `POST /api/search` (single hub) đo p95 < 800ms. M2 hiện chưa có dataset 5K chunks (bảng `chunks` rỗng, `OPENAI_API_KEY` placeholder) — cần đo lại sau khi Phase 9 dựng eval set hoặc khi có dữ liệu ingest thật.
result: [pending]

### 2. Latency p95 search cross-hub <1.5s (SC2)
expected: Trên dataset thật nhiều hub, `POST /api/search/cross-hub` fan-out đo p95 < 1.5s. Cùng lý do thiếu dataset như mục 1.
result: [pending]

### 3. Recall sanity check 50 query VN (SC5)
expected: Trên 50 query tiếng Việt mẫu, top-3 kết quả WITH hub filter trả ≥1 chunk relevant cho mỗi query (manual review). Cần eval dataset thật — Phase 9 dựng `queries.jsonl` + 10 file VN medical. Đây là dữ liệu chuẩn bị cho Phase 9 quality gate ≥75%.
result: [pending]

### 4. Cache invalidation end-to-end (SC4)
expected: Upload document mới vào 1 hub → search lần kế tiếp cùng query trong hub đó trả `cache_hit=false` (cache đã bị Pub/Sub `hub:{hub_id}:invalidate` xoá). Wiring đã verified qua code review + boot test, nhưng chưa có integration test đóng kín luồng upload→publish→subscriber→cache miss. Cần test thủ công với Redis + Docker chạy thật, hoặc bổ sung integration test ở Phase 9/10.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
