# Queries Review — Phase 1 Eval Dataset

**Ngày sinh:** 2026-04-28
**Plan:** 01-05 (Wave 3)
**Tổng query:** 12 (10 cover-each-file + 2 bonus)
**Cách sinh:** Claude (LLM) đọc heading paths trong `eval/dataset/headings.json` (286 path từ Plan 04) + tên file dataset → draft 12 truy vấn vàng tiếng Việt tự nhiên.

> **File `eval/dataset/queries.jsonl` đã được tạo nhưng CHƯA commit — đợi user approve trong main thread parent.**

---

## User check 5 điều

1. **Câu hỏi có tự nhiên + đúng tiếng Việt không?** (không phải copy heading machine-like)
2. **`expected_doc_id` có đúng file không?** (kiến thức trong file đó thật sự trả lời được câu hỏi)
3. **`expected_section` có là heading specific nhất không?** (không phải heading lvl 1 quá broad)
4. **Phân bố có cover được edge case không?** (≥ 1 query / file, có scanned PDF, có table-heavy doc)
5. **Heading vàng `tri_thuc_chinh_tri.pdf` (đã review ở Plan 04 SUMMARY) có chính xác không?** Heading PDF gốc 11 entry đã được Plan 04 LLM-draft — review lại tại đây trước khi commit cứng.

---

## Bảng 12 query

| STT | ID  | Query (cắt 90 ký tự) | Expected Doc | Expected Section (cắt 60) | Notes |
|-----|-----|----------------------|--------------|---------------------------|-------|
| 1   | q01 | Câu tuyên bố định vị chính thức của Đỗ Minh Đường gồm bốn thành tố cốt lõi nào? | DMD_T1-01_DinhVi_TrungTam_v1.docx | PHẦN 01 > ▸ 1.2 Bốn thành tố cốt lõi không thể thiếu | Definition cụ thể, sub-section 1.2 |
| 2   | q02 | Năm nhóm từ cấm khi viết content thương hiệu Đỗ Minh Đường gồm những gì? | DMD_T1-02_TuDien_ThuongHieu_v1.docx | PHẦN 01 \| 5 NHÓM TỪ CẤM | Từ điển thương hiệu — chỉ T1-02 có |
| 3   | q03 | Khi khách hỏi 'sao đắt hơn chỗ khác vậy, giảm được không?' thì kịch bản tư vấn trả lời thế nào? | DMD_T1-03_Script_Library_v1.docx | NHÓM C \| "Sao đắt hơn chỗ khác vậy?" / "Mắc quá..." | Script Library NHÓM C xử lý hoài nghi giá |
| 4   | q04 | Tứ chẩn trong YHCT là gì và tại sao Đỗ Minh Đường cần khám phức tạp như vậy? | DMD_T1-04_FAQ_ThuongHieu_v1.docx | CHƯƠNG 03 > Q3.2 "Tứ chẩn" là gì? | FAQ Q3.2 — đặc trưng FAQ-style |
| 5   | q05 | Ma trận phân công 4 nhân vật trên 7 kênh truyền thông của Đỗ Minh Đường được tổ chức ra sao? | DMD_T3-02_PhanCong_NhanVat_v1.docx | PHẦN 01 \| MA TRẬN TỔNG QUAN — 4 NHÂN VẬT × 7 KÊNH | **Table-heavy** — ma trận 4×7 |
| 6   | q06 | Lịch biên tập nội dung tháng đầu tiên (tuần 1 đến tuần 4) của 12 tuyến nội dung được sắp xếp thế nào? | DMD_T5-01_ContentStrategy_12TuyenND_v1.docx | PHẦN 03 \| LỊCH BIÊN TẬP — THÁNG ĐẦU TIÊN | Content strategy lịch 4 tuần |
| 7   | q07 | Cấu trúc video YouTube chuẩn cho kênh truyền của Đỗ Minh Đường gồm những phần nào? | DMD_T5-02_Playbook_KenhTruyen_v1.docx | ZALO > ▸ CẤU TRÚC VIDEO YOUTUBE CHUẨN | Playbook kênh truyền |
| 8   | q08 | Các thành phần cốt lõi của tri thức chính trị bao gồm những gì? | tri_thuc_chinh_tri.pdf | TRI THỨC CHÍNH TRỊ > 2. Các Thành phần Cốt lõi... | PDF gốc — section 2 |
| 9   | q09 | Câu định vị trung tâm bản đầy đủ của Đỗ Minh Đường được phát biểu thế nào? | **DMD_T1-01_scanned.pdf** | PHẦN 01 > ▸ 1.1 Câu định vị trung tâm — Bản đầy đủ | **EDGE CASE OCR** — baseline native dự kiến FAIL extraction → top-3 hit rate = 0 |
| 10  | q10 | Bệnh nhân ở tỉnh xa không đến trực tiếp được thì Đỗ Minh Đường hỗ trợ như thế nào? | **DMD_T1-04_scanned.pdf** | CHƯƠNG 06 > Q6.5 Bệnh nhân ở tỉnh xa... | **EDGE CASE OCR** — baseline native FAIL → top-3 = 0 |
| 11  | q11 | Bảng tài sản giữ / đổi vai / giảm / bỏ trong định vị mới của Đỗ Minh Đường gồm những hạng mục nào? | DMD_T1-01_DinhVi_TrungTam_v1.docx | PHẦN 08 > ▸ 8.2 Bảng tài sản — Giữ / Đổi vai / Giảm / Bỏ | **Bonus 1** — table-heavy section |
| 12  | q12 | Hội đồng chuyên môn của Đỗ Minh Đường gồm những bác sĩ nào và hoạt động ra sao? | DMD_T1-04_FAQ_ThuongHieu_v1.docx | CHƯƠNG 02 > Q2.1 Hội đồng chuyên môn của DMD gồm những ai? | **Bonus 2** — FAQ Q&A đặc thù |

---

## Coverage check

| File | # query trỏ vào | Note |
|------|-----------------|------|
| DMD_T1-01_DinhVi_TrungTam_v1.docx | 2 | ✓ (q01 + bonus q11 table) |
| DMD_T1-02_TuDien_ThuongHieu_v1.docx | 1 | ✓ (q02) |
| DMD_T1-03_Script_Library_v1.docx | 1 | ✓ (q03) |
| DMD_T1-04_FAQ_ThuongHieu_v1.docx | 2 | ✓ (q04 + bonus q12 FAQ) |
| DMD_T3-02_PhanCong_NhanVat_v1.docx | 1 | ✓ (q05 table-heavy) |
| DMD_T5-01_ContentStrategy_12TuyenND_v1.docx | 1 | ✓ (q06) |
| DMD_T5-02_Playbook_KenhTruyen_v1.docx | 1 | ✓ (q07) |
| tri_thuc_chinh_tri.pdf | 1 | ✓ (q08 PDF gốc) |
| **DMD_T1-01_scanned.pdf** | 1 | ✓ (q09 — edge case OCR) |
| **DMD_T1-04_scanned.pdf** | 1 | ✓ (q10 — edge case OCR) |
| **Tổng** | **12** | **10 file unique** |

---

## Phân bố kiểu hỏi (đa dạng)

| Kiểu hỏi | Query | Mục đích test retrieval |
|----------|-------|-------------------------|
| Definition / List | q01, q02, q08 | Khả năng match câu hỏi "X gồm những gì" với section định nghĩa |
| FAQ-style (Q&A) | q04, q10, q12 | Match Q&A pattern Q3.2/Q6.5/Q2.1 trong T1-04 |
| Procedure / Script | q03, q07 | Match section thao tác/kịch bản — long text |
| Comparison / Decision | q05 | Match table-heavy ma trận 4×7 |
| Schedule / Timeline | q06 | Match section liên quan thời gian (lịch biên tập 4 tuần) |
| Table lookup | q11 | Match heading bảng 4 cột Giữ/Đổi/Giảm/Bỏ |
| Specific brand statement | q09 | Match câu định vị bản đầy đủ — OCR-fail edge case |

---

## Hai edge case quan trọng cho Phase 5

- **q09 + q10 trỏ vào scanned PDF** (`DMD_T1-01_scanned.pdf`, `DMD_T1-04_scanned.pdf`):
  - Đây là image-only PDF không có text layer (Plan 03 build).
  - Baseline native (extractor Go) sẽ trả `no text extracted` (`backend/internal/rag/extractor/pdf.go:52`) → tài liệu không có chunk nào lên ChromaDB.
  - Top-3 hit rate cho q09 + q10 ở baseline = **0%** (đúng kỳ vọng).
  - Phase 5 với Docling OCR `vie+eng` phải recover được nội dung → top-3 hit rate cho q09 + q10 phải **> 0%** (lý tưởng = 100%).
  - **Đây là 2 query bằng chứng cứng cho gap mà Docling cần đóng** (Phase 1 success criteria #4 trong ROADMAP).

---

## Heading vàng PDF gốc — `tri_thuc_chinh_tri.pdf` (review từ Plan 04)

Plan 04 đã LLM-draft 11 heading manual cho PDF gốc. User review lại nội dung này trước khi commit Plan 05:

```
1.  TRI THỨC CHÍNH TRỊ
2.  TRI THỨC CHÍNH TRỊ > Tóm tắt
3.  TRI THỨC CHÍNH TRỊ > 1. Khái niệm và Bản chất của Tri thức Chính trị
4.  TRI THỨC CHÍNH TRỊ > 2. Các Thành phần Cốt lõi của Tri thức Chính trị
5.  TRI THỨC CHÍNH TRỊ > 3. Vai trò của Tri thức Chính trị trong Xã hội Hiện đại
6.  TRI THỨC CHÍNH TRỊ > 4. Thực trạng Tri thức Chính trị ở Việt Nam
7.  TRI THỨC CHÍNH TRỊ > 5. Thách thức trong Kỷ nguyên Số
8.  TRI THỨC CHÍNH TRỊ > 6. Giải pháp Nâng cao Tri thức Chính trị
9.  TRI THỨC CHÍNH TRỊ > 7. Tri thức Chính trị và Phát triển Bền vững
10. TRI THỨC CHÍNH TRỊ > Kết luận
11. TRI THỨC CHÍNH TRỊ > Tài liệu Tham khảo
```

User check: nếu sai → ghi ở Comments dưới, executor sẽ sửa `MANUAL_PDF_HEADINGS` trong `eval/scripts/extract_headings.py` rồi regenerate `headings.json`.

---

## Cách user approve

```bash
# 1. Mở review file này
cat eval/dataset/QUERIES_REVIEW.md

# 2. Mở queries gốc
cat eval/dataset/queries.jsonl

# 3. Mở heading vàng PDF gốc
python -c "import json; print(json.dumps(json.load(open('eval/dataset/headings.json'))['tri_thuc_chinh_tri.pdf'], ensure_ascii=False, indent=2))"

# 4. Validate JSONL syntax (nếu sửa tay)
python -c "import json; [json.loads(l) for l in open('eval/dataset/queries.jsonl', encoding='utf-8') if l.strip()]"
```

**Trong main thread parent, reply một trong hai:**

- `approved` → executor commit Plan 01-05 và tiếp tục Plan 01-06.
- `<số STT>: <sửa gì>` (vd `q03: nên hỏi cụ thể về phần trăm giảm giá`, hoặc `q09: đổi expected_section sang 1.2`) → executor sửa `queries.jsonl` rồi present lại bảng review mới.

---

## Disposition

- [ ] User reviewed (queries + heading vàng PDF gốc)
- [ ] User approved
- [ ] User requested changes (xem comment phía dưới)

### Comments user

(để trống — user điền ở đây nếu cần sửa)
