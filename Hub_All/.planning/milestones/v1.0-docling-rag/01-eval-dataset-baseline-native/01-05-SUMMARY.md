# Plan 01-05 — SUMMARY

**Phase:** 01-eval-dataset-baseline-native
**Plan:** 05 (Wave 3)
**Status:** ✅ COMPLETED
**Completed:** 2026-04-28
**Commit:** `e13102d`

---

## Tasks

| # | Task | Result |
|---|---|---|
| 1 | LLM-draft 12 queries vàng (cover 10 file) | ✅ Done — `queries.jsonl` 12 dòng JSONL valid |
| 2 | Tạo `QUERIES_REVIEW.md` cho user duyệt | ✅ Done — 137 dòng, bảng đầy đủ + coverage check |
| 3 | Checkpoint: user review + approve | ✅ User reply `approved` trong main thread |

## Artifacts

| File | Lines | Note |
|---|---|---|
| `eval/dataset/queries.jsonl` | 12 | Schema 5 field `{id, query, expected_doc_id, expected_section, notes}`, `expected_doc_id` LÀ filename |
| `eval/dataset/QUERIES_REVIEW.md` | 137 | Bảng review + coverage 10/10 file + heading vàng PDF gốc |

## Coverage

- 10/10 file unique được trỏ tới (ít nhất 1 query / file).
- 2 query bonus (q11 table-heavy, q12 FAQ).
- 2 query edge case OCR (q09, q10) trỏ scanned PDF — dự kiến baseline native FAIL = 0% top-3.
- Phân bố kiểu hỏi đa dạng: definition, FAQ, script, table lookup, schedule.

## Verification

- ✅ `python -c "import json; [json.loads(l) for l in open('eval/dataset/queries.jsonl', encoding='utf-8') if l.strip()]"` — không lỗi.
- ✅ Mọi `expected_doc_id` khớp filename trong `eval/dataset/sources/` hoặc `eval/dataset/scanned/`.
- ✅ Mọi `expected_section` là heading path hợp lệ trong `headings.json` của file đó.
- ✅ User approved trong main thread (checkpoint:human-verify pass).

## Heading vàng PDF gốc (`tri_thuc_chinh_tri.pdf`)

Plan 04 đã LLM-draft 11 entry. User review chung trong checkpoint Plan 05 — không yêu cầu sửa.

## Deviations

Không có. Tất cả must_haves pass.

## Next

Wave 4: Plan 01-06 — `baseline.py` upload all → poll → search → snapshot.
