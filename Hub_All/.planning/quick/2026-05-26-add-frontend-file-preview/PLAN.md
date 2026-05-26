---
title: Xem trực tiếp file gốc trong browser (DOCX/XLSX/CSV/HTML)
slug: add-frontend-file-preview
date: 2026-05-26
status: complete
---

# Quick task — Render DOCX/XLSX/CSV/HTML trong preview modal

## Bối cảnh

Sau quick task `2026-05-26-add-file-format-readers` (backend extract text 8 format), user mở preview file DOCX trong frontend `DocumentIngestion` page vẫn thấy modal "Không thể xem trực tiếp file DOCX — Tải xuống để mở bằng ứng dụng phù hợp". Bug screenshot user gửi 2026-05-26.

Nguyên do: `DocumentIngestion.tsx:1185-1236` preview switch cũ chỉ render iframe cho PDF/TXT/MD + img cho ảnh; mọi format khác fall-back download. Backend đã serve được `/api/documents/{id}/file` blob, FE chỉ thiếu viewer in-browser.

## Scope

Add 3 frontend lib + 1 iframe sandbox để render trực tiếp 4 format:

| Format | Library | Bundle (gzipped) |
|--------|---------|------------------|
| DOCX   | `docx-preview` (renderAsync DOCX → HTML faithful) | 51 KB |
| XLSX   | `xlsx` (SheetJS Community — sheet → HTML table) | 143 KB |
| CSV    | `papaparse` (auto delimiter detect + BOM strip) | 7 KB |
| HTML   | `<iframe sandbox="">` (native, no lib) | 0 KB |

**Lazy load:** Cả 3 lib dùng `await import('lib')` dynamic import → chỉ tải khi user mở preview matching format. Initial bundle KHÔNG ảnh hưởng (verified `npm run build` — 3 chunk riêng).

**PPTX:** Giữ fall-back download (KHÔNG có lib lightweight; defer v4.0).

## Files (5 changed)

1. **`frontend/package.json`** — +3 dep (`docx-preview`, `xlsx`, `papaparse`) + 1 type (`@types/papaparse`).
2. **`frontend/src/components/DocxPreview.tsx`** (mới) — `useEffect` mount `renderAsync(blob, container)` qua dynamic import. Loading + error state.
3. **`frontend/src/components/XlsxPreview.tsx`** (mới) — parse `XLSX.read(arrayBuffer)` → tab navigation per sheet → `dangerouslySetInnerHTML` HTML table từ `XLSX.utils.sheet_to_html`. Tailwind arbitrary selectors style table.
4. **`frontend/src/components/CsvPreview.tsx`** (mới) — `Papa.parse` auto delimiter + BOM strip TextDecoder utf-8/latin-1 fallback → native `<table>` render. Hover row + sticky header.
5. **`frontend/src/pages/DocumentIngestion.tsx`** — import 3 component + `previewBlob` state mới + preview switch dispatch (DOCX → DocxPreview, XLSX → XlsxPreview, CSV → CsvPreview, HTML → iframe sandbox).

## Pitfall + mitigation

1. **CSV BOM:** Excel Windows export hay có BOM `﻿` đầu file → strip thủ công sau TextDecoder (`text.charCodeAt(0) === 0xfeff && text.slice(1)`). PapaParse delimiter `''` để auto-detect (`,`, `;`, `\t`, `|`).
2. **HTML XSS:** File HTML user upload có thể chứa `<script>` malicious → `sandbox=""` empty attribute disable ALL capabilities (script, form, popup) — iframe render thuần text/layout.
3. **XLSX dangerouslySetInnerHTML:** SheetJS `sheet_to_html` output sanitized + KHÔNG eval script (nó render data cells thuần text). Acceptable risk vì source là file user vừa upload (admin-only — D6).
4. **Blob cleanup:** `URL.revokeObjectURL(previewUrl)` đã có sẵn `closePreview`; thêm `setPreviewBlob(null)` để giải phóng reference.
5. **Cancel race:** Mỗi `useEffect` dùng `let cancelled = false; return () => { cancelled = true; }` pattern — user đổi blob khi parsing chưa xong KHÔNG set state outdated.

## Acceptance criteria

- [x] User mở preview DOCX → thấy nội dung document render trực tiếp (KHÔNG còn modal "Không thể xem").
- [x] User mở preview XLSX 2 sheet → thấy tab navigation + bảng nội dung mỗi sheet.
- [x] User mở preview CSV → thấy bảng có header + body row.
- [x] User mở preview HTML → thấy nội dung render trong iframe sandboxed (script bị block).
- [x] PPTX vẫn fall-back download (acceptable).
- [x] Initial bundle KHÔNG bloat — 3 chunk riêng load on-demand.
- [x] `npm run lint` (tsc) clean.
- [x] `npm run build` clean.

## Out of scope

- PPTX in-browser viewer (defer v4.0 — chưa có lib lightweight cho format này).
- `.doc` legacy Word 97-2003 (user convert sang .docx).
- OCR images (D4 LOCKED M2 — defer v4.0).
- Page navigation / search-in-document UX (P1 v4.0).
- Edit-in-place rich text (defer — tách feature lớn).
