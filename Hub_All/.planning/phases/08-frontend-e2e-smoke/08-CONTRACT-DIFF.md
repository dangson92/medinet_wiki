# 08-CONTRACT-DIFF — Bản đồ contract Frontend ↔ FastAPI

> Sinh tự động bởi `api/scripts/smoke/contract_diff.py` (Plan 08-01).
> Phase 8 verify-only — đối chiếu tĩnh, KHÔNG sửa frontend (D6).

## Tổng kết phân loại

**MATCH=36 · BLOCKER=1 · EXCLUDED=15 · FIX-API=2 · UNCLASSIFIED=0**

- **MATCH** — endpoint frontend gọi, FastAPI có sẵn → smoke pass kỳ vọng.
- **BLOCKER** — gap thật trên golden path → phải fix `api/` (Plan 08-02).
- **EXCLUDED** — feature out-of-scope M2 → lỗi hợp lệ, KHÔNG fix.
- **FIX-API** — gap cần stub api-side → input Plan 08-02.
- **UNCLASSIFIED** — endpoint mới chưa phân loại → planner phải xử lý.

## Bảng đối chiếu endpoint

| METHOD | PATH | STATUS | REASON |
|--------|------|--------|--------|
| DELETE | `/api/documents/{id}` | MATCH | khop router FastAPI |
| GET | `/api/api-keys` | MATCH | khop router FastAPI |
| GET | `/api/api-keys/{id}` | MATCH | khop router FastAPI |
| GET | `/api/audit-logs` | MATCH | khop router FastAPI |
| GET | `/api/auth/me` | MATCH | khop router FastAPI |
| GET | `/api/documents` | MATCH | khop router FastAPI |
| GET | `/api/documents/{id}` | MATCH | khop router FastAPI |
| GET | `/api/documents/{id}/file` | FIX-API | tai file goc — can stub api-side |
| GET | `/api/documents/{id}/status` | MATCH | khop router FastAPI |
| GET | `/api/documents/{id}/versions` | EXCLUDED | version history defer v4.1 — RAG-V4-03 |
| GET | `/api/documents/{id}/versions/{id}` | EXCLUDED | version history defer v4.1 — RAG-V4-03 |
| GET | `/api/documents/{id}/versions/{id}/file` | EXCLUDED | version history defer v4.1 — RAG-V4-03 |
| GET | `/api/hubs` | MATCH | khop router FastAPI |
| GET | `/api/hubs/{id}` | MATCH | khop router FastAPI |
| GET | `/api/profile` | MATCH | khop router FastAPI |
| GET | `/api/sync/batches` | EXCLUDED | sync queue loai khoi M2 — Phase 5 CONTEXT D-01 |
| GET | `/api/sync/batches/{id}` | EXCLUDED | sync queue loai khoi M2 — Phase 5 CONTEXT D-01 |
| GET | `/api/sync/stats` | EXCLUDED | sync queue loai khoi M2 — Phase 5 CONTEXT D-01 |
| GET | `/api/usage` | MATCH | khop router FastAPI |
| GET | `/api/usage/realtime` | MATCH | khop router FastAPI |
| GET | `/api/usage/stats` | MATCH | khop router FastAPI |
| GET | `/api/users` | MATCH | khop router FastAPI |
| GET | `/api/users/{id}` | MATCH | khop router FastAPI |
| PATCH | `/api/hubs/{id}/status` | MATCH | khop router FastAPI |
| PATCH | `/api/users/{id}/role` | MATCH | khop router FastAPI |
| PATCH | `/api/users/{id}/status` | MATCH | khop router FastAPI |
| POST | `/api/ai/chat` | BLOCKER | GeminiAssistant trên golden path Dashboard — FastAPI chưa có endpoint |
| POST | `/api/api-keys` | MATCH | khop router FastAPI |
| POST | `/api/api-keys/{id}/revoke` | MATCH | khop router FastAPI |
| POST | `/api/auth/login` | MATCH | khop router FastAPI |
| POST | `/api/auth/logout` | MATCH | khop router FastAPI |
| POST | `/api/auth/refresh` | MATCH | khop router FastAPI |
| POST | `/api/documents/compose` | FIX-API | compose mode DocumentIngestion — can stub api-side |
| POST | `/api/documents/upload` | MATCH | khop router FastAPI |
| POST | `/api/documents/{id}/reupload` | EXCLUDED | version history defer v4.1 — RAG-V4-03 |
| POST | `/api/documents/{id}/reupload/preview` | EXCLUDED | version history defer v4.1 — RAG-V4-03 |
| POST | `/api/documents/{id}/versions/{id}/restore` | EXCLUDED | version history defer v4.1 — RAG-V4-03 |
| POST | `/api/hubs` | MATCH | khop router FastAPI |
| POST | `/api/hubs/{id}/test-connection` | EXCLUDED | D-06 PROJECT.md — KHONG test-connection |
| POST | `/api/profile/password` | MATCH | khop router FastAPI |
| POST | `/api/search` | MATCH | khop router FastAPI |
| POST | `/api/search/answer` | MATCH | khop router FastAPI |
| POST | `/api/search/cross-hub` | MATCH | khop router FastAPI |
| POST | `/api/search/similar` | MATCH | khop router FastAPI |
| POST | `/api/sync/batches` | EXCLUDED | sync queue loai khoi M2 — Phase 5 CONTEXT D-01 |
| POST | `/api/sync/batches/{id}/pages/{id}/approve` | EXCLUDED | sync queue loai khoi M2 — Phase 5 CONTEXT D-01 |
| POST | `/api/sync/batches/{id}/pages/{id}/reject` | EXCLUDED | sync queue loai khoi M2 — Phase 5 CONTEXT D-01 |
| POST | `/api/users` | MATCH | khop router FastAPI |
| PUT | `/api/api-keys/{id}` | MATCH | khop router FastAPI |
| PUT | `/api/documents/{id}/content` | EXCLUDED | version history defer v4.1 — RAG-V4-03 |
| PUT | `/api/documents/{id}/content/preview` | EXCLUDED | version history defer v4.1 — RAG-V4-03 |
| PUT | `/api/hubs/{id}` | MATCH | khop router FastAPI |
| PUT | `/api/profile` | MATCH | khop router FastAPI |
| PUT | `/api/users/{id}` | MATCH | khop router FastAPI |

> Hai section dưới đây được bổ sung thủ công ở Task 2 (Plan 08-01). Nếu chạy
> lại `contract_diff.py`, script sẽ ghi đè bảng phía trên — phải append lại
> hai section này (hoặc giữ bản báo cáo hiện tại làm snapshot Phase 8).

## Envelope shape — FastAPI vs Go vs frontend kỳ vọng

### Nguồn đối chiếu

- **FastAPI shape thực tế:** `api/app/pkg/response.py` — helper `_envelope()` luôn
  build body `{success, data, error, meta}`.
- **Frontend kỳ vọng:** `frontend/src/services/api.ts` dòng 5-10 — interface
  `APIResponse<T>` (`success`, `data?`, `error?`, `meta?`).
- **Go router signature cũ:** `git show m1-go-archived:Hub_All/backend/internal/router/router.go`
  — truy được thành công từ tag `m1-go-archived` (commit `72f18ef`). Không cần
  fallback.

### Bảng xác nhận 4 key envelope

| Key | FastAPI `response.py` | Frontend `APIResponse<T>` | Khớp? |
|-----|----------------------|---------------------------|-------|
| `success` | `bool` (luôn có) | `success: boolean` | ✅ tên + kiểu khớp |
| `data` | `Any` (null khi error) | `data?: T` (optional) | ✅ khớp — frontend chấp nhận undefined/null |
| `error` | `{code, message, details?}` hoặc `null` | `error?: { code: string; message: string }` | ✅ khớp — `details` thừa ở FastAPI nhưng frontend bỏ qua |
| `meta` | `{page, per_page, total}` (từ `paginated()`) hoặc `null` | `meta?: { page; per_page; total; total_pages }` | ⚠️ FastAPI **thiếu** `total_pages` |

### Ghi chú quan trọng về `error.code`

`response.py` dùng `error.code` UPPER_SNAKE_CASE (`BAD_REQUEST`, `UNAUTHORIZED`,
`NOT_FOUND`, `VALIDATION_ERROR`, `RATE_LIMIT_EXCEEDED`...). Frontend
`api.ts` **chỉ đọc `error.message` để hiển thị** và không so khớp giá trị cụ
thể của `error.code` (chỉ check `success` boolean + status 401 để refresh
token). Do đó UPPER_SNAKE_CASE **không gây lỗi render** — envelope tương thích
D6. (Comment trong `response.py` dòng 7-9 cảnh báo không đổi sang lowercase —
giữ nguyên.)

### Lệch nhỏ — `meta.total_pages`

`paginated()` chỉ set `{page, per_page, total}`, **không có `total_pages`**.
Frontend khai báo `total_pages` là **optional** (`meta?: { ...; total_pages: number }`
— toàn bộ `meta` optional). Khi `total_pages` undefined, component phân trang
React tự tính `Math.ceil(total / per_page)` hoặc bỏ qua → **không crash render**.
Đánh dấu **không ảnh hưởng smoke** — không nâng thành BLOCKER. Ghi nhận làm
ứng viên polish (Plan 08-02 có thể thêm `total_pages` vào `paginated()` nếu
component phân trang phụ thuộc field này — kiểm tra lúc smoke 08-04).

### Route Go có mà FastAPI thiếu

| Route Go (`router.go`) | FastAPI có? | Ảnh hưởng smoke |
|------------------------|-------------|-----------------|
| `GET/PUT /api/system-settings` | ❌ không | Không — frontend `api.ts` KHÔNG gọi `/api/system-settings`. Bỏ qua. |
| `POST /api/documents/:id/reindex` | ❌ không | Không — `api.ts` KHÔNG có hàm reindex. Bỏ qua. |
| `GET /api/audit-logs/export` | ❌ không | Không — `api.ts` KHÔNG có hàm export CSV. Bỏ qua. |
| `POST /api/ai/chat` | ❌ không | **CÓ** — `api.ts` `aiChat()` gọi → đã bắt là **BLOCKER** trong bảng trên. |
| `GET /api/documents/:id/file` | ❌ không | **CÓ** — `getDocumentFileUrl()` → đã bắt là **FIX-API**. |
| `POST /api/documents/compose` | ❌ không | **CÓ** — `composeDocument()` → đã bắt là **FIX-API**. |
| version history + sync routes | ❌ không | EXCLUDED — out-of-scope M2 (đã phân loại). |

### Route FastAPI có mà Go không có

| Route FastAPI | Go có? | Ảnh hưởng smoke |
|---------------|--------|-----------------|
| `GET /api/hubs/{id}/stats` | ❌ không | Không — `api.ts` KHÔNG gọi `/api/hubs/{id}/stats`. Endpoint thừa, vô hại. |
| `POST /api/users/{id}/reset-password` | ❌ không | Không — `api.ts` KHÔNG có hàm reset-password. Endpoint thừa, vô hại. |

→ FastAPI bổ sung 2 endpoint mới (admin tiện ích) không có ở Go; frontend chưa
gọi nên không phát sinh contract gap.

## Kết luận SC3

SC3 ROADMAP Phase 8 (replay/contract test) được **thoả qua đối chiếu tĩnh** —
KHÔNG replay live vì Go backend đã teardown 2026-05-14 (TEARDOWN-01 pull-in;
`git show m1-go-archived` là cách duy nhất truy router cũ). Đối chiếu tĩnh phủ
3 lớp: (1) endpoint path `api.ts` ↔ router FastAPI ↔ `router.go`, (2) envelope
shape `{success, data, error, meta}` ↔ `APIResponse<T>`, (3) phân loại gap.

**Kết quả đếm — 54 endpoint frontend:**

- **MATCH = 36** — endpoint frontend gọi, FastAPI có sẵn → smoke pass kỳ vọng.
- **BLOCKER = 1** — `POST /api/ai/chat` (GeminiAssistant golden path Dashboard)
  → phải fix `api/` ở Plan 08-02.
- **EXCLUDED = 15** — version history (RAG-V4-03 defer v4.1), sync queue
  (Phase 5 CONTEXT D-01), `test-connection` (D-06) → lỗi smoke hợp lệ, KHÔNG fix.
- **FIX-API = 2** — `POST /api/documents/compose`, `GET /api/documents/{id}/file`
  → cần stub api-side ở Plan 08-02.
- **UNCLASSIFIED = 0** — mọi endpoint đã có nhãn.

Envelope: 3/4 key (`success`, `data`, `error`) khớp tuyệt đối; `meta` lệch nhỏ
ở field optional `total_pages` (không ảnh hưởng render). Contract D6 (frontend
không sửa, URL `/api/*` + shape giữ nguyên) được xác nhận đứng vững — gap duy
nhất cần xử lý api-side: 1 BLOCKER + 2 FIX-API, làm input trực tiếp cho Plan
08-02.
