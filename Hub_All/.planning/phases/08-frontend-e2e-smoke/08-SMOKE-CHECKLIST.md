# 08-SMOKE-CHECKLIST — Phase 8 Frontend E2E Smoke

> Checklist cho người verify (UAT thủ công) — Plan 08-04.
> Bao phủ ROADMAP Phase 8 SC1 (11 trang React render) + SC2 (golden path browser)
> + SC5 (docker compose 3-service healthy). Hoàn tất requirement COMPAT-01.
>
> Cách dùng: chạy lần lượt Section A → B → C, tick `[x]` mỗi mục PASS, ghi
> chú lỗi nếu FAIL. Sau khi xong, executor đọc file này để sinh `08-HUMAN-UAT.md`.

---

## Section A — Boot stack (SC1 + SC5)

Khởi động toàn bộ stack mới (Python `api/`, KHÔNG Go) rồi chạy frontend dev server.

| # | Bước | Lệnh / thao tác | Kỳ vọng | PASS? |
|---|------|-----------------|---------|-------|
| A1 | Sinh keypair JWT (nếu chưa có) | `make api-keys` (hoặc `bash api/scripts/generate_keys.sh`) | Có `api/keys/private.pem` + `public.pem` | [ ] |
| A2 | Boot stack tự động | `bash api/scripts/smoke/boot_stack.sh` (chạy từ `Hub_All/`) | Exit 0; in "3 service healthy"; `/healthz` trả `{"success":true,"data":{"status":"ok"}}`; `/readyz` OK; alembic upgrade head OK; compose chỉ 3-service không Go | [ ] |
| A3 | Khởi động frontend dev server | Terminal khác: `cd frontend && npm install && npm run dev` | Vite in `Local: http://localhost:5173/` | [ ] |
| A4 | Mở trình duyệt | Mở `http://localhost:5173/login` | Trang login render, không lỗi trắng màn hình | [ ] |

**Ghi chú Section A:**

> _(điền nếu có lỗi: ví dụ container nào không healthy, migration fail, port conflict…)_

---

## Section B — 11 trang React render (SC1)

Sau khi login admin tại `http://localhost:5173/login`, mở lần lượt từng route.
Mỗi trang: mở **DevTools → Console + Network**. Đánh dấu PASS nếu trang
**render khung nội dung** và **KHÔNG** có lỗi `500` / lỗi `CORS` / `401 sai`
(đã login mà vẫn 401 = auth flow lỗi). Lỗi cục bộ của 1 feature EXCLUDED v4.1
(version history) KHÔNG làm FAIL trang — trang vẫn phải render khung.

| # | Trang | Route (URL đầy đủ) | Component | Lỗi mong đợi KHÔNG được có | PASS? |
|---|-------|--------------------|-----------|----------------------------|-------|
| B1 | Dashboard | `http://localhost:5173/` | Dashboard.tsx (render GeminiAssistant widget) | 500 / CORS error / 401 sai khi đã login | [ ] |
| B2 | HubRegistry | `http://localhost:5173/registry` | HubRegistry.tsx | 500 / CORS error / 401 sai khi đã login | [ ] |
| B3 | DocumentIngestion | `http://localhost:5173/documents` | DocumentIngestion.tsx | 500 / CORS error / 401 sai khi đã login | [ ] |
| B4 | UserManagement | `http://localhost:5173/users` | UserManagement.tsx | 500 / CORS error / 401 sai khi đã login | [ ] |
| B5 | AuditLog | `http://localhost:5173/logs` | AuditLog.tsx | 500 / CORS error / 401 sai khi đã login | [ ] |
| B6 | APIKeyManagement | `http://localhost:5173/api-keys` | APIKeyManagement.tsx | 500 / CORS error / 401 sai khi đã login | [ ] |
| B7 | CrossHubSearch | `http://localhost:5173/search` | CrossHubSearch.tsx (render CitationText) | 500 / CORS error / 401 sai khi đã login | [ ] |
| B8 | Settings | `http://localhost:5173/settings` | Settings.tsx | 500 / CORS error / 401 sai khi đã login | [ ] |
| B9 | GeminiAssistant | (component — hiện trên Dashboard `/` và Settings `/settings`) | components/GeminiAssistant.tsx | 500 / CORS error / 401 sai khi đã login | [ ] |
| B10 | TokenUsage | `http://localhost:5173/usage` | TokenUsage.tsx | 500 / CORS error / 401 sai khi đã login | [ ] |
| B11 | Profile | `http://localhost:5173/profile` | Profile.tsx | 500 / CORS error / 401 sai khi đã login | [ ] |

### Trang EXCLUDED — KHÔNG tính vào PASS

Sync queue loại khỏi M2 (Phase 5 CONTEXT D-01); `/api/sync/*` không implement.
Hai trang dưới **dự kiến lỗi API** — chỉ ghi nhận, KHÔNG đánh FAIL.

| # | Trang | Route (URL đầy đủ) | Component | Trạng thái |
|---|-------|--------------------|-----------|-----------|
| E1 | SyncQueue | `http://localhost:5173/sync` | SyncQueue.tsx | **EXCLUDED** — dự kiến lỗi `/api/sync/*` (sync queue loại khỏi M2). KHÔNG tính PASS. |
| E2 | SyncReview | `http://localhost:5173/sync/review/:batchId` | SyncReview.tsx | **EXCLUDED** — dự kiến lỗi `/api/sync/*` (sync queue loại khỏi M2). KHÔNG tính PASS. |

### Ghi chú gap FIX-API cục bộ (từ 08-CONTRACT-DIFF)

Các feature dưới có thể lỗi cục bộ trên trang nhưng **trang vẫn phải render khung**:

- **DocumentIngestion (B3):** version history (`/api/documents/{id}/versions*`) =
  EXCLUDED v4.1 (RAG-V4-03) → nút/tab "Lịch sử phiên bản" có thể lỗi cục bộ.
  `compose mode` (`POST /api/documents/compose`) + tải file gốc
  (`GET /api/documents/{id}/file`) = FIX-API → nếu chưa stub đầy đủ thì lỗi cục
  bộ, KHÔNG làm FAIL trang.

**Ghi chú Section B (lỗi quan sát từng trang nếu có):**

> _(điền: trang nào FAIL + thông điệp Console/Network — status code, endpoint)_

---

## Section C — Golden path browser (SC2)

Chạy luồng end-to-end thật trên trình duyệt. Mỗi bước tick PASS + ghi quan sát.

| # | Bước | Thao tác | Kỳ vọng | PASS? |
|---|------|----------|---------|-------|
| C1 | Login admin | Tại `http://localhost:5173/login` đăng nhập tài khoản admin | Vào được Dashboard, không 401 | [ ] |
| C2 | Upload DOCX | Vào `/documents`, upload 1 file `.docx` vào hub **hub_y_te** | Upload nhận 200, tài liệu xuất hiện trong danh sách, status chuyển `processing → completed` | [ ] |
| C3 | Cross-hub search | Vào `/search`, chạy cross-hub search với truy vấn `khám bệnh` | Trả kết quả (chunk) từ ≥1 hub, không 500 | [ ] |
| C4 | Ask + citation `[1]` | Tại `/search` chạy ask `quy trình khám bệnh là gì` | Câu trả lời render citation dạng `[1]` và **click được** (component `CitationText.tsx`) | [ ] |
| C5 | Audit log | Vào `/logs` xác nhận có entry audit tương ứng | Thấy entry audit (xem ghi chú dưới) | [ ] |

> **Lưu ý C5 (từ Plan 08-03):** golden path login + upload qua UI hiện **KHÔNG**
> sinh audit entry — code chưa enqueue audit `auth.login` / `document.upload`.
> Để Section C5 thấy audit log có dữ liệu thực, hãy thực hiện thêm 1 thao tác
> **có sinh audit**: tạo hub (`hub.create`) hoặc tạo user (`user.create`) hoặc
> xoá 1 tài liệu (`document.delete`) — rồi quay lại `/logs` kiểm. Nếu chỉ thấy
> trang `/logs` render khung + danh sách (kể cả rỗng) không lỗi 500 → vẫn tính
> PASS render; ghi rõ quan sát.

**Ghi chú Section C (quan sát từng bước):**

> _(điền: bước nào FAIL + chi tiết — ví dụ citation [1] không clickable, search 500…)_

---

## Section D — Tiêu chí PASS tổng

Phase 8 smoke đạt khi **tất cả** mục dưới đúng:

- [ ] **D1 (SC5):** `boot_stack.sh` exit 0 — docker compose 3-service
  (postgres + redis + python-api) healthy, KHÔNG reference Go.
- [ ] **D2 (SC1):** 11 trang React (B1–B11) đều render OK — không 500 / CORS /
  401 sai. (SyncQueue + SyncReview EXCLUDED — không tính.)
- [ ] **D3 (SC2):** Golden path browser (C1–C5) PASS — login → upload DOCX →
  cross-hub search → ask citation `[1]` clickable → audit log.
- [ ] **D4:** KHÔNG phát hiện endpoint UNCLASSIFIED ngoài nhóm EXCLUDED đã biết
  (version history v4.1, sync queue M2, test-connection D-06).

**Verdict cuối (điền sau khi verify):**

> _PASS toàn bộ → Phase 8 đủ điều kiện đóng._
> _Có FAIL ngoài EXCLUDED → ghi gap, input cho `/gsd-plan-phase 8 --gaps`._
