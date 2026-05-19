---
status: diagnosed
phase: 08-frontend-e2e-smoke
source: [08-04-PLAN.md, 08-SMOKE-CHECKLIST.md, 08-CONTRACT-DIFF.md]
started: 2026-05-18T00:00:00Z
updated: 2026-05-19T00:00:00Z
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

[testing paused — 1 issue blocker (Test 1), 2 test blocked phụ thuộc (Test 2/3)]

## Tests

### 1. SC5 — docker compose 3-service healthy không Go
expected: `bash api/scripts/smoke/boot_stack.sh` (chạy từ `Hub_All/`) exit 0; poll `docker compose ps` cho thấy 3 service `postgres` + `redis` + `python-api` đều `healthy`; `curl http://localhost:8180/healthz` trả `{"success":true,"data":{"status":"ok"}}`; `/readyz` OK; `alembic upgrade head` OK; `docker compose config --services` chỉ liệt kê 3 service, KHÔNG có service tên chứa `go`/`backend`. Script Plan 08-04 Task 1 (`api/scripts/smoke/boot_stack.sh`) tự động hoá phần boot kiểm được; cần con người chạy lệnh thật trên máy có Docker. Tham chiếu: 08-SMOKE-CHECKLIST.md Section A (A1–A4) + Section D (D1).
result: issue
reported: "boot_stack.sh: postgres+redis healthy, python-api container crash khi startup. docker compose logs python-api: lifespan main.py:144 → setup_cocoindex (rag/setup.py:100 coco.start_blocking()) → cocoindex Environment.__init__ → RuntimeError: Permission denied (os error 13). Application startup failed. Exiting."
severity: blocker

### 2. SC1 — 11 trang React render OK qua npm run dev
expected: Sau `cd frontend && npm install && npm run dev` (Vite 6 → http://localhost:5173) và login admin, mở lần lượt 11 route — mỗi trang phải render khung nội dung, DevTools Console + Network KHÔNG có lỗi `500` / lỗi `CORS` / `401 sai` (đã login mà vẫn 401). 11 trang: Dashboard `/`, HubRegistry `/registry`, DocumentIngestion `/documents`, UserManagement `/users`, AuditLog `/logs`, APIKeyManagement `/api-keys`, CrossHubSearch `/search`, Settings `/settings`, GeminiAssistant (component trên `/` + `/settings`), TokenUsage `/usage`, Profile `/profile`. NGOẠI LỆ EXCLUDED — KHÔNG tính PASS: `/sync` (SyncQueue.tsx) + `/sync/review/:batchId` (SyncReview.tsx) — sync queue loại khỏi M2 (Phase 5 CONTEXT D-01), `/api/sync/*` không implement → dự kiến lỗi API. Lỗi cục bộ feature version history (EXCLUDED v4.1 — RAG-V4-03) trên DocumentIngestion KHÔNG làm FAIL trang. Tham chiếu: 08-SMOKE-CHECKLIST.md Section B (B1–B11 + E1/E2) + Section D (D2). Cần mắt người render UI thật trên trình duyệt.
result: blocked
blocked_by: server
reason: "Không test được — python-api container không boot (Test 1 blocker: cocoindex LMDB Permission denied). Không có backend để login/render trang. Test lại sau khi gap Test 1 đóng."

### 3. SC2 — Golden path browser với citation [1] clickable
expected: Luồng end-to-end thật trên trình duyệt (08-SMOKE-CHECKLIST.md Section C, C1–C5): (C1) login admin tại `/login` → vào Dashboard không 401; (C2) `/documents` upload 1 file `.docx` vào hub `hub_y_te` → nhận 200, tài liệu xuất hiện, status `processing → completed`; (C3) `/search` chạy cross-hub search `khám bệnh` → trả chunk từ ≥1 hub, không 500; (C4) ask `quy trình khám bệnh là gì` → câu trả lời render citation dạng `[1]` và **click được** (component `CitationText.tsx`); (C5) `/logs` xác nhận thấy entry audit. Lưu ý C5 (từ Plan 08-03): golden path login + upload qua UI hiện KHÔNG sinh audit entry `auth.login`/`document.upload` — để thấy audit thật, làm thêm 1 thao tác có sinh audit (hub.create / user.create / document.delete); nếu `/logs` chỉ render khung + danh sách (kể cả rỗng) không 500 thì vẫn tính PASS render. Phần golden path API đã được verify TỰ ĐỘNG ở Plan 08-03 (`test_smoke_golden_path.py` PASS) — mục này verify lớp BROWSER, cần mắt người. Tham chiếu: Section D (D3).
result: blocked
blocked_by: server
reason: "Không test được — python-api container không boot (Test 1 blocker). Golden path browser cần backend chạy. Test lại sau khi gap Test 1 đóng."

### 4. SC3 — Contract/replay test frontend ↔ FastAPI (đã verify Plan 08-01)
expected: Đối chiếu contract 54 endpoint `frontend/src/services/api.ts` ↔ router FastAPI ↔ Go signature (`git show m1-go-archived`) — phân loại 36 MATCH / 1 BLOCKER / 15 EXCLUDED / 2 FIX-API, UNCLASSIFIED=0; envelope 3/4 key (`success`, `data`, `error`) khớp tuyệt đối, `meta.total_pages` lệch nhỏ optional không crash render. SC3 thoả qua ĐỐI CHIẾU TĨNH (D-08-01) vì Go backend đã teardown 2026-05-14 — không replay live được. Nguồn chứng minh: `08-CONTRACT-DIFF.md` (Plan 08-01, đã commit). BLOCKER `POST /api/ai/chat` đã đóng ở Plan 08-02; 2 FIX-API (`/api/documents/compose`, `/api/documents/{id}/file`) xử lý api-side Plan 08-02.
result: passed (verified Plan 08-01 — đối chiếu tĩnh 3 lớp, artifact `08-CONTRACT-DIFF.md`)

### 5. SC4 — Vietnamese filename UTF-8 roundtrip (đã verify Plan 08-03)
expected: Upload file tên tiếng Việt có dấu (`Khám bệnh đa khoa.docx`) → response upload + `GET /api/documents/{id}` trả `name` UTF-8 nguyên vẹn, không mojibake; threat T-08-03-01 — FileStore UUID-rename, `file_path` stem khớp UUID4, không chứa `..`, nằm trong `file_store_dir` (no path traversal). Nguồn chứng minh: `api/tests/integration/test_vietnamese_filename.py` (Plan 08-03, test critical PASS per-file, đã commit `74a7e3c`).
result: passed (verified Plan 08-03 — `test_vietnamese_filename.py` critical PASS)

## Summary

total: 5
passed: 2
issues: 1
pending: 0
skipped: 0
blocked: 2

> **2 passed** (SC3, SC4) — đã verify tự động/tĩnh ở Plan 08-01 và 08-03, có artifact chứng minh.
> **1 issue blocker** (SC5 — Test 1) — `boot_stack.sh` chạy thật 2026-05-19: python-api container crash startup vì cocoindex LMDB `Permission denied (os error 13)`. Chẩn đoán xong — xem Gaps.
> **2 blocked** (SC1, SC2 — Test 2/3) — phụ thuộc backend chạy được; chặn bởi issue Test 1. Test lại sau khi gap đóng.

## Gaps

<!-- YAML format cho /gsd-plan-phase 8 --gaps consumption -->
- truth: "`docker compose up` lên healthy 3-service (postgres + redis + python-api); python-api container boot thành công và phục vụ `GET /healthz` 200 (ROADMAP Phase 8 SC5)"
  status: failed
  reason: "User reported (boot_stack.sh chạy thật 2026-05-19): postgres+redis healthy, python-api container crash khi startup — lifespan main.py:144 setup_cocoindex → rag/setup.py:100 coco.start_blocking() → cocoindex Environment.__init__ → RuntimeError: Permission denied (os error 13). Application startup failed. Exiting."
  severity: blocker
  test: 1
  root_cause: "`api/app/config.py:52` đặt `cocoindex_lmdb_path` default = `Path(\"Hub_All/.cocoindex/state.lmdb\")` — đường dẫn TƯƠNG ĐỐI kèm tiền tố `Hub_All/` lạc. Trong container (`WORKDIR /app`, `USER apiuser` uid 1000) đường dẫn này resolve thành `/app/Hub_All/.cocoindex/state.lmdb`. Thư mục `/app` do root sở hữu (Dockerfile `WORKDIR /app` chạy trước `USER apiuser`; chỉ `chown apiuser` cho `/app/app` và `/app/.venv`). `apiuser` không có quyền tạo thư mục con trong `/app` → cocoindex Rust core ném Permission denied. Trên host chạy được do tình cờ — cwd thuộc về user. Đây là bug Phase 4 (cocoindex_lmdb_path thêm ở Plan 04-01, Phase 4 chưa execute/verify) lộ ra qua smoke test SC5 Phase 8."
  artifacts:
    - path: "api/app/config.py"
      issue: "Dòng 52: `cocoindex_lmdb_path` default là đường dẫn tương đối `Hub_All/.cocoindex/state.lmdb` — không writable trong container, tiền tố `Hub_All/` sai ngữ cảnh"
    - path: "api/Dockerfile"
      issue: "Không tạo + chown thư mục cocoindex LMDB state cho `apiuser`; `/app` root-owned nên runtime không tạo được thư mục con"
    - path: "docker-compose.yml"
      issue: "Service python-api không mount volume writable cho cocoindex LMDB state — state không persist + không có nơi ghi"
  missing:
    - "Đổi `cocoindex_lmdb_path` default sang đường dẫn tuyệt đối writable, vd `/app/.cocoindex/state.lmdb` (bỏ tiền tố `Hub_All/`)"
    - "Dockerfile: `RUN mkdir -p /app/.cocoindex && chown apiuser:apiuser /app/.cocoindex` TRƯỚC `USER apiuser`"
    - "docker-compose.yml: thêm named volume mount cho `/app/.cocoindex` (cocoindex LMDB state persist qua restart) + set env `COCOINDEX_LMDB_PATH` nếu cần override"
    - "Verify lại: `boot_stack.sh` exit 0, python-api healthy, `curl :8180/healthz` 200"
  debug_session: ""

> Lưu ý phạm vi: fix thuần api-side / hạ tầng (config.py + Dockerfile + docker-compose.yml) — tôn trọng D6 (KHÔNG sửa frontend). Đây là lỗi cocoindex Phase 4 nhưng chặn SC5 Phase 8 → đóng như gap Phase 8.

## COMPAT-01

Requirement COMPAT-01 (frontend React 19 tương thích Python `api/` qua URL `/api/*`
+ envelope `{success, data, error, meta}`) — **PARTIAL → có gap blocker**:

- **Lớp tĩnh / tự động ĐẠT:** đối chiếu contract 54 endpoint (SC3 — 08-01),
  fix gap api-side BLOCKER + 2 FIX-API + port 8180 + CORS (08-02), golden path
  API end-to-end + VN filename UTF-8 tự động (SC2 API + SC4 — 08-03).
- **Lớp browser CHẶN bởi gap:** docker compose python-api không boot (SC5 FAIL —
  cocoindex LMDB Permission denied); SC1 (11 trang render) + SC2 browser bị block
  vì không có backend chạy.

COMPAT-01 chỉ kết luận **ĐẠT** sau khi gap SC5 được vá, stack boot được, và
SC1/SC2/SC5 PASS bằng mắt người.

## Verdict

**FAIL (1 blocker) — Phase 8 có gap chặn, cần gap closure.**

UAT chạy thật 2026-05-19: Test 1 (SC5 boot stack) = issue blocker — python-api
container crash vì cocoindex LMDB `Permission denied`. Test 2/3 (SC1 render, SC2
golden path browser) blocked vì không có backend. Test 4/5 (SC3, SC4) đã passed.

**Bước tiếp theo:** `/gsd-plan-phase 8 --gaps` → tạo fix plan đóng gap SC5
(config.py + Dockerfile + docker-compose.yml) → `/gsd-execute-phase 8 --gaps-only`
→ re-run `/gsd-verify-work 8` để verify SC5 + mở khoá SC1/SC2.
