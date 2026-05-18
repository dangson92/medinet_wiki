---
phase: 08-frontend-e2e-smoke
plan: 01
subsystem: testing
tags: [contract-test, fastapi, react, smoke, regex, python]

# Dependency graph
requires:
  - phase: 03-auth-rbac-envelope
    provides: response envelope {success, data, error, meta} qua api/app/pkg/response.py
  - phase: 05-hub-user-audit-apikey-settings
    provides: router CRUD hubs/users/profile/audit-logs/api-keys/rag-config
  - phase: 06-search-api
    provides: router search single + cross-hub
  - phase: 07-ask-api
    provides: router ask + usage
provides:
  - "Script api/scripts/smoke/contract_diff.py — đối chiếu endpoint frontend api.ts vs router FastAPI vs Go router signature"
  - "Báo cáo 08-CONTRACT-DIFF.md — bản đồ 54 endpoint phân loại MATCH/BLOCKER/EXCLUDED/FIX-API"
  - "Xác định gap api-side: 1 BLOCKER (/api/ai/chat) + 2 FIX-API (compose, file) làm input Plan 08-02"
affects: [08-02, 08-03, 08-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Contract diff tĩnh bằng regex stdlib — không import app, không thực thi mã từ file đích"
    - "Exit code 1 khi có endpoint UNCLASSIFIED — CI/executor phát hiện gap mới"

key-files:
  created:
    - api/scripts/smoke/contract_diff.py
    - api/scripts/smoke/__init__.py
    - .planning/phases/08-frontend-e2e-smoke/08-CONTRACT-DIFF.md
  modified: []

key-decisions:
  - "Đối chiếu contract tĩnh (regex) thay replay live vì Go backend đã teardown 2026-05-14 — SC3 thoả qua đối chiếu 3 lớp path/envelope/classification"
  - "meta.total_pages lệch nhỏ (FastAPI paginated() thiếu field) — phân loại không-ảnh-hưởng-smoke vì frontend khai báo optional, không nâng BLOCKER"

patterns-established:
  - "Smoke tooling đặt trong api/scripts/smoke/ — package marker __init__.py cho python -m"
  - "Bảng phân loại gap hardcode trong script = quyết định planner, executor không tự suy diễn"

requirements-completed: [COMPAT-01]

# Metrics
duration: 18min
completed: 2026-05-18
---

# Phase 8 Plan 01: Contract Diff Frontend ↔ FastAPI Summary

**Script regex `contract_diff.py` lập bản đồ 54 endpoint frontend api.ts đối chiếu router FastAPI + Go signature, phân loại 36 MATCH / 1 BLOCKER / 15 EXCLUDED / 2 FIX-API — chứng minh SC3 qua đối chiếu tĩnh.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-18
- **Completed:** 2026-05-18
- **Tasks:** 2
- **Files modified:** 3 (created)

## Accomplishments

- Script `contract_diff.py` trích mọi lời gọi endpoint từ `frontend/src/services/api.ts` (3 dạng: `this.request<>()`, `fetch()` trực tiếp, URL builder) và 11 file router FastAPI, diff + phân loại theo bảng cứng của planner.
- Báo cáo `08-CONTRACT-DIFF.md`: bảng 54 endpoint + section Envelope shape (đối chiếu 4 key vs Go vs frontend) + section Kết luận SC3.
- Xác định chính xác gap cần xử lý api-side: **1 BLOCKER** (`POST /api/ai/chat` — GeminiAssistant golden path) + **2 FIX-API** (`compose`, `documents/{id}/file`) — input trực tiếp Plan 08-02.
- Xác nhận envelope `{success, data, error, meta}` tương thích D6: 3/4 key khớp tuyệt đối, chỉ `meta.total_pages` lệch nhỏ (optional, không crash render).
- Go router signature truy được từ tag `m1-go-archived` — không cần fallback; `/api/ai/chat` + `compose` + `file` xác nhận là regression FastAPI vs Go (Go từng có).

## Task Commits

Each task was committed atomically:

1. **Task 1: Viết script contract_diff.py trích endpoint + đối chiếu router FastAPI** - `2c8911e` (feat)
2. **Task 2: So envelope shape FastAPI vs Go + hoàn thiện 08-CONTRACT-DIFF.md** - `0ca55cf` (docs)

_Note: 08-CONTRACT-DIFF.md được Task 1 sinh tự động (bảng) rồi Task 2 append 2 section tĩnh — commit cùng file ở Task 2._

## Files Created/Modified

- `api/scripts/smoke/contract_diff.py` - Script Python standalone (stdlib only) trích + diff + phân loại endpoint, ghi báo cáo Markdown, exit code 0/1.
- `api/scripts/smoke/__init__.py` - Package marker cho `python -m scripts.smoke.contract_diff`.
- `.planning/phases/08-frontend-e2e-smoke/08-CONTRACT-DIFF.md` - Bản đồ contract: bảng 54 endpoint + envelope diff + kết luận SC3.

## Decisions Made

- **Đối chiếu tĩnh thay replay live:** Go backend đã teardown 2026-05-14 (TEARDOWN-01) → SC3 (replay/contract test) thoả qua đối chiếu 3 lớp tĩnh (path / envelope / classification), Go signature lấy qua `git show m1-go-archived`.
- **`meta.total_pages` không nâng BLOCKER:** FastAPI `paginated()` thiếu `total_pages` nhưng frontend khai báo field optional → không crash render; ghi nhận làm ứng viên polish 08-02 nếu component phân trang phụ thuộc.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ép stdout/stderr UTF-8 cho console Windows**
- **Found during:** Task 1 (chạy verify `python -m scripts.smoke.contract_diff`)
- **Issue:** Console Windows mặc định cp1252 — `UnicodeEncodeError` khi in bảng chứa tiếng Việt có dấu (`ư`, `—`), script crash exit 1 dù logic đúng.
- **Fix:** Thêm `sys.stdout/stderr.reconfigure(encoding="utf-8")` đầu `main()`.
- **Files modified:** api/scripts/smoke/contract_diff.py
- **Verification:** Chạy lại script in bảng đầy đủ tiếng Việt, không crash.
- **Committed in:** `2c8911e` (Task 1 commit)

**2. [Rule 1 - Bug] Sửa regex `_REQUEST_RE` cắt nhầm path template chứa dấu nháy đơn**
- **Found during:** Task 1 (chạy verify — 6 endpoint UNCLASSIFIED giả `/api/users${qs `)
- **Issue:** Regex path group `[^`']+` dừng ở dấu `'` đầu tiên; path template `` `/api/users${qs ? '?' + qs : ''}` `` chứa `'` bên trong interpolation → bắt cụt thành `/api/users${qs `.
- **Fix:** Tách regex thành 2 nhánh — chuỗi đơn `'...'` (dừng ở `'`) HOẶC template `` `...` `` (dừng ở backtick, cho phép `'` bên trong); cập nhật `extract_frontend_endpoints` xử lý 3 group.
- **Files modified:** api/scripts/smoke/contract_diff.py
- **Verification:** Chạy lại — 0 endpoint UNCLASSIFIED, exit code 0.
- **Committed in:** `2c8911e` (Task 1 commit)

**3. [Rule 1 - Bug] Sửa `_normalize_path` cắt nhầm query string trong interpolation**
- **Found during:** Task 1 (cùng lần verify trên)
- **Issue:** `_normalize_path` split path ở `?` đầu tiên — nhưng interpolation `${qs ? '?' + qs : ''}` chứa `?` → cắt sai vị trí. Lần fix đầu thay mọi `${...}` thành `{id}` rồi strip `{id}$` lại xoá nhầm path param thật (`/api/documents/{id}` → `/api/documents`).
- **Fix:** Xử lý 4 bước theo thứ tự — (1) xoá hẳn interpolation query-string (chứa `?`), (2) interpolation còn lại → `{id}`, (3) bỏ query string literal, (4) path param FastAPI → `{id}`.
- **Files modified:** api/scripts/smoke/contract_diff.py
- **Verification:** `/api/documents/{id}` giữ nguyên, `/api/users${qs...}` → `/api/users`; 36 MATCH đúng.
- **Committed in:** `2c8911e` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 bug)
**Impact on plan:** Cả 3 fix cần thiết để script chạy đúng trên môi trường Windows + parse chính xác api.ts. Không scope creep — đều thuộc Task 1, sửa inline trong file plan chỉ định.

## Issues Encountered

- `ruff`/`mypy` không có trên PATH global — tooling nằm trong uv environment của project. Chạy qua `uv run ruff` / `uv run mypy` (xác nhận `uv` khả dụng). Cả hai PASS clean trên `contract_diff.py`.

## TDD Gate Compliance

Không áp dụng — plan `type: execute`, không phải `type: tdd`. Verification qua acceptance criteria của từng task (script chạy được, ruff/mypy clean, exit code 0).

## User Setup Required

None - không cần cấu hình dịch vụ ngoài. Script thuần đọc file repo.

## Next Phase Readiness

- **Plan 08-02 (fix api-side)** có đủ input: 1 BLOCKER (`/api/ai/chat`) + 2 FIX-API (`compose`, `documents/{id}/file`) đã xác định rõ trong `08-CONTRACT-DIFF.md`. Cân nhắc thêm `total_pages` vào `paginated()` nếu component phân trang React phụ thuộc.
- **Plan 08-04 (manual smoke checklist)** dùng bảng 54 endpoint để biết trang nào pass kỳ vọng (36 MATCH), trang nào lỗi hợp lệ EXCLUDED (sync/version history).
- D6 tôn trọng tuyệt đối: không file nào trong `frontend/` bị sửa.

## Self-Check: PASSED

- FOUND: api/scripts/smoke/contract_diff.py
- FOUND: api/scripts/smoke/__init__.py
- FOUND: .planning/phases/08-frontend-e2e-smoke/08-CONTRACT-DIFF.md
- FOUND commit: 2c8911e (Task 1)
- FOUND commit: 0ca55cf (Task 2)

---
*Phase: 08-frontend-e2e-smoke*
*Completed: 2026-05-18*
