---
title: Xem trực tiếp file gốc trong browser (DOCX/XLSX/CSV/HTML)
slug: add-frontend-file-preview
date: 2026-05-26
status: complete
---

# SUMMARY — Render DOCX/XLSX/CSV/HTML trong preview modal

## Outcome

User mở preview file DOCX/XLSX/CSV/HTML trong `DocumentIngestion` page hết bị modal "Không thể xem trực tiếp". 4 format render trực tiếp in-browser; PPTX vẫn fall-back download (chưa có lib lightweight).

Là follow-up của quick task song song `2026-05-26-add-file-format-readers` (backend extract text). Backend đã serve `/api/documents/{id}/file` blob, FE giờ có viewer.

## Files changed (5)

| File | Change |
|------|--------|
| [frontend/package.json](../../frontend/package.json) | +3 dep (`docx-preview`, `xlsx`, `papaparse`) + 1 type (`@types/papaparse`) |
| [frontend/src/components/DocxPreview.tsx](../../frontend/src/components/DocxPreview.tsx) | Mới — `useEffect` mount `renderAsync(blob, container)` dynamic import, loading + error state |
| [frontend/src/components/XlsxPreview.tsx](../../frontend/src/components/XlsxPreview.tsx) | Mới — parse `XLSX.read` → tab navigation per sheet → HTML table render |
| [frontend/src/components/CsvPreview.tsx](../../frontend/src/components/CsvPreview.tsx) | Mới — `Papa.parse` auto delimiter + BOM strip + native `<table>` |
| [frontend/src/pages/DocumentIngestion.tsx](../../frontend/src/pages/DocumentIngestion.tsx) | +3 import + `previewBlob` state + 4 branch dispatch (docx/xlsx/csv/html) |

## Build verification

```
npm run lint   → tsc --noEmit clean
npm run build  → 2384 modules transformed in 9.23s
  ✓ papaparse.min  19.86 KB (gzip 7.43 KB)
  ✓ docx-preview  173.84 KB (gzip 51.01 KB)
  ✓ xlsx          429.53 KB (gzip 143.08 KB)
  ✓ index        1309.15 KB (gzip 380.93 KB — KHÔNG đổi so trước, dynamic import work)
```

3 lib code-split thành chunk riêng → chỉ tải khi user mở preview matching format. Initial bundle KHÔNG bloat.

## Architecture insights

1. **Lazy load 3 lib qua `await import('lib')` trong `useEffect`** — Pattern giống `React.lazy` nhưng inside effect (đỡ Suspense boundary). User hiếm khi xem CSV/XLSX/DOCX → tránh paying cost upfront.
2. **Blob state alongside URL state** — `previewBlob: Blob | null` mới song song `previewUrl: string`. Lib parse blob trực tiếp (KHÔNG double-fetch qua blob URL). `closePreview` cleanup cả 2.
3. **HTML iframe `sandbox=""`** — Empty sandbox attribute disable ALL capabilities (script/form/popup/same-origin) → safe render user-uploaded HTML mà KHÔNG cần parse + sanitize thủ công.
4. **CSV BOM strip trong TextDecoder fallback** — `utf-8` strict mode try → catch fallback `latin1` → manual `charCodeAt(0) === 0xfeff && slice(1)`. PapaParse delimiter `''` để Sniffer auto-detect.
5. **XLSX `dangerouslySetInnerHTML` acceptable risk** — SheetJS `sheet_to_html` output là HTML table thuần text cell content (KHÔNG eval formula → script). Source admin-uploaded (D6 admin-only upload).
6. **Cancel race pattern `let cancelled = false`** — User đóng preview hoặc đổi file khi parse chưa xong → return cleanup set flag → setState branch check skip.

## Cancel pattern

Mỗi 3 component dùng pattern:

```ts
useEffect(() => {
  let cancelled = false;
  (async () => {
    const lib = await import('lib');
    if (cancelled) return;
    // ... parse + setState
  })();
  return () => { cancelled = true; };
}, [blob]);
```

→ Chống setState trên unmounted component + memory leak.

## Out of scope (defer v4.0)

- **PPTX viewer:** Chưa có lib lightweight render trực tiếp; `pptxjs` quá nặng. Fall-back download giữ nguyên.
- **OCR ảnh + scanned PDF:** D4 LOCKED — Tesseract VN model defer.
- **Edit-in-place trong preview:** Defer feature riêng (rich text editor đã có cho 1 luồng khác `EditContentModal`).
- **Search-in-document / page navigation UX:** Default browser viewer chưa cover; defer v4.0.
- **`.doc` legacy:** User convert thủ công sang .docx.

## Reference

- Plan: [./PLAN.md](./PLAN.md)
- Sibling backend quick task: [../2026-05-26-add-file-format-readers/](../2026-05-26-add-file-format-readers/) (commit `520d55f`)
- Trigger: user screenshot 2026-05-26 mở preview DOCX vẫn thấy modal "Không thể xem"
