---
status: partial
phase: 08-frontend-e2e-smoke
source: [08-04-PLAN.md, 08-SMOKE-CHECKLIST.md, 08-CONTRACT-DIFF.md]
started: 2026-05-18T00:00:00Z
updated: 2026-05-18T00:00:00Z
---

> **LƯU Ý QUAN TRỌNG.** Biên bản này được sinh sau khi checkpoint `human-verify`
> của Plan 08-04 bị **AUTO-APPROVE** trong chế độ `--auto` (`auto_advance: true`)
> để giữ chuỗi tự động chạy tiếp. **KHÔNG có người thật nào đã boot stack hay
> click 11 trang React.** File `08-SMOKE-CHECKLIST.md` CHƯA được con người điền.
> Vì vậy mọi mục cần mắt người (boot stack thật, render 11 trang, citation `[1]`
> clickable, docker compose healthy thật) để `result: [pending]`.
>
> **Để verify thật:** chạy `/gsd-verify-work 8` — người dùng làm theo
> `08-SMOKE-CHECKLIST.md`, điền PASS/FAIL từng mục, rồi cập nhật lại biên bản này.

## Current Test

[awaiting human testing — chạy `/gsd-verify-work 8`]

## Tests

### 1. SC5 — docker compose 3-service healthy không Go
expected: `bash api/scripts/smoke/boot_stack.sh` (chạy từ `Hub_All/`) exit 0; poll `docker compose ps` cho thấy 3 service `postgres` + `redis` + `python-api` đều `healthy`; `curl http://localhost:8180/healthz` trả `{"success":true,"data":{"status":"ok"}}`; `/readyz` OK; `alembic upgrade head` OK; `docker compose config --services` chỉ liệt kê 3 service, KHÔNG có service tên chứa `go`/`backend`. Script Plan 08-04 Task 1 (`api/scripts/smoke/boot_stack.sh`) tự động hoá phần boot kiểm được; cần con người chạy lệnh thật trên máy có Docker. Tham chiếu: 08-SMOKE-CHECKLIST.md Section A (A1–A4) + Section D (D1).
result: [pending]

### 2. SC1 — 11 trang React render OK qua npm run dev
expected: Sau `cd frontend && npm install && npm run dev` (Vite 6 → http://localhost:5173) và login admin, mở lần lượt 11 route — mỗi trang phải render khung nội dung, DevTools Console + Network KHÔNG có lỗi `500` / lỗi `CORS` / `401 sai` (đã login mà vẫn 401). 11 trang: Dashboard `/`, HubRegistry `/registry`, DocumentIngestion `/documents`, UserManagement `/users`, AuditLog `/logs`, APIKeyManagement `/api-keys`, CrossHubSearch `/search`, Settings `/settings`, GeminiAssistant (component trên `/` + `/settings`), TokenUsage `/usage`, Profile `/profile`. NGOẠI LỆ EXCLUDED — KHÔNG tính PASS: `/sync` (SyncQueue.tsx) + `/sync/review/:batchId` (SyncReview.tsx) — sync queue loại khỏi M2 (Phase 5 CONTEXT D-01), `/api/sync/*` không implement → dự kiến lỗi API. Lỗi cục bộ feature version history (EXCLUDED v4.1 — RAG-V4-03) trên DocumentIngestion KHÔNG làm FAIL trang. Tham chiếu: 08-SMOKE-CHECKLIST.md Section B (B1–B11 + E1/E2) + Section D (D2). Cần mắt người render UI thật trên trình duyệt.
result: [pending]

### 3. SC2 — Golden path browser với citation [1] clickable
expected: Luồng end-to-end thật trên trình duyệt (08-SMOKE-CHECKLIST.md Section C, C1–C5): (C1) login admin tại `/login` → vào Dashboard không 401; (C2) `/documents` upload 1 file `.docx` vào hub `hub_y_te` → nhận 200, tài liệu xuất hiện, status `processing → completed`; (C3) `/search` chạy cross-hub search `khám bệnh` → trả chunk từ ≥1 hub, không 500; (C4) ask `quy trình khám bệnh là gì` → câu trả lời render citation dạng `[1]` và **click được** (component `CitationText.tsx`); (C5) `/logs` xác nhận thấy entry audit. Lưu ý C5 (từ Plan 08-03): golden path login + upload qua UI hiện KHÔNG sinh audit entry `auth.login`/`document.upload` — để thấy audit thật, làm thêm 1 thao tác có sinh audit (hub.create / user.create / document.delete); nếu `/logs` chỉ render khung + danh sách (kể cả rỗng) không 500 thì vẫn tính PASS render. Phần golden path API đã được verify TỰ ĐỘNG ở Plan 08-03 (`test_smoke_golden_path.py` PASS) — mục này verify lớp BROWSER, cần mắt người. Tham chiếu: Section D (D3).
result: [pending]

### 4. SC3 — Contract/replay test frontend ↔ FastAPI (đã verify Plan 08-01)
expected: Đối chiếu contract 54 endpoint `frontend/src/services/api.ts` ↔ router FastAPI ↔ Go signature (`git show m1-go-archived`) — phân loại 36 MATCH / 1 BLOCKER / 15 EXCLUDED / 2 FIX-API, UNCLASSIFIED=0; envelope 3/4 key (`success`, `data`, `error`) khớp tuyệt đối, `meta.total_pages` lệch nhỏ optional không crash render. SC3 thoả qua ĐỐI CHIẾU TĨNH (D-08-01) vì Go backend đã teardown 2026-05-14 — không replay live được. Nguồn chứng minh: `08-CONTRACT-DIFF.md` (Plan 08-01, đã commit). BLOCKER `POST /api/ai/chat` đã đóng ở Plan 08-02; 2 FIX-API (`/api/documents/compose`, `/api/documents/{id}/file`) xử lý api-side Plan 08-02.
result: passed (verified Plan 08-01 — đối chiếu tĩnh 3 lớp, artifact `08-CONTRACT-DIFF.md`)

### 5. SC4 — Vietnamese filename UTF-8 roundtrip (đã verify Plan 08-03)
expected: Upload file tên tiếng Việt có dấu (`Khám bệnh đa khoa.docx`) → response upload + `GET /api/documents/{id}` trả `name` UTF-8 nguyên vẹn, không mojibake; threat T-08-03-01 — FileStore UUID-rename, `file_path` stem khớp UUID4, không chứa `..`, nằm trong `file_store_dir` (no path traversal). Nguồn chứng minh: `api/tests/integration/test_vietnamese_filename.py` (Plan 08-03, test critical PASS per-file, đã commit `74a7e3c`).
result: passed (verified Plan 08-03 — `test_vietnamese_filename.py` critical PASS)

## Summary

total: 5
passed: 2
issues: 0
pending: 3
skipped: 0
blocked: 0

> **2 passed** (SC3, SC4) — đã verify tự động/tĩnh ở Plan 08-01 và 08-03, có artifact chứng minh.
> **3 pending** (SC1, SC2, SC5) — cần con người boot stack thật + render 11 trang React + chạy golden path browser. Checkpoint Plan 08-04 đã bị auto-approve về mặt cơ học (`--auto`), KHÔNG phải human verify thật → KHÔNG đánh PASS.

## Gaps

- **SC1, SC2, SC5 chưa được con người verify.** Plan 08-04 Task 1 đã tạo công cụ
  đầy đủ (`api/scripts/smoke/boot_stack.sh` + `08-SMOKE-CHECKLIST.md` 4 section
  A/B/C/D), nhưng checkpoint `human-verify` bị auto-approve trong chế độ `--auto`
  để giữ chuỗi chạy — không có người thật boot stack hay click 11 trang. Để đóng
  Phase 8 đúng quy trình, người dùng chạy `/gsd-verify-work 8`: làm theo
  `08-SMOKE-CHECKLIST.md`, điền PASS/FAIL từng mục, rồi cập nhật `result:` của
  Test 1/2/3 trong biên bản này.
- **Chưa phát hiện gap kỹ thuật mới** ngoài nhóm EXCLUDED đã biết (version history
  v4.1 — RAG-V4-03, sync queue M2 — Phase 5 CONTEXT D-01, test-connection — D-06).
  Nếu khi verify thật phát hiện trang FAIL ngoài EXCLUDED → ghi thành gap, input
  cho `/gsd-plan-phase 8 --gaps`.

## COMPAT-01

Requirement COMPAT-01 (frontend React 19 tương thích Python `api/` qua URL `/api/*`
+ envelope `{success, data, error, meta}`) — **PARTIAL**:

- **Lớp tĩnh / tự động ĐẠT:** đối chiếu contract 54 endpoint (SC3 — 08-01),
  fix gap api-side BLOCKER + 2 FIX-API + port 8180 + CORS (08-02), golden path
  API end-to-end + VN filename UTF-8 tự động (SC2 API + SC4 — 08-03).
- **Lớp browser CHƯA xác nhận:** 11 trang React render thật (SC1), golden path
  browser với citation `[1]` clickable (SC2 browser), docker compose 3-service
  healthy thật (SC5) — chờ human UAT.

COMPAT-01 chỉ kết luận **ĐẠT** sau khi `/gsd-verify-work 8` xác nhận SC1/SC2/SC5
PASS bằng mắt người. Hiện trạng: artifact + tự động hoá hoàn tất, human verification PENDING.

## Verdict

**PARTIAL — Phase 8 chưa đủ điều kiện đóng.**

Mọi artifact của Plan 08-04 đã tạo xong (boot script + checklist + biên bản UAT này).
Tự động hoá và đối chiếu tĩnh (SC3, SC4 + golden path API) đã PASS. Còn lại 3 mục
cần mắt người (SC1, SC2, SC5) ở trạng thái `pending`.

**Bước tiếp theo:** người dùng chạy `/gsd-verify-work 8` → boot stack thật theo
`08-SMOKE-CHECKLIST.md` → điền kết quả → cập nhật biên bản. Nếu SC1/SC2/SC5 đều
PASS → verdict chuyển PASS, COMPAT-01 ĐẠT, Phase 8 đóng, tiếp Phase 9. Nếu có FAIL
ngoài EXCLUDED → gap closure qua `/gsd-plan-phase 8 --gaps`.
