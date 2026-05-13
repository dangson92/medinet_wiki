# Templates Tài liệu Tri thức Medinet Wiki

Bộ 4 template chuẩn để biên soạn tài liệu nạp vào RAG. **Tuân thủ format này → top-3 hit rate cải thiện 10-20pp** so với DOCX tự do.

## Quy ước chung (áp dụng cho mọi template)

1. **Format**: Markdown (`.md`) — heading `#/##/###`, không bold thay heading.
2. **Hierarchy 3 cấp**: H1 (1 lần) → H2 (section) → H3 (chunk). Tránh H4-H6.
3. **Section atomic**: 150-400 từ tiếng Việt, đứng độc lập, không refer "ở trên/dưới".
4. **Front-load entity**: tên người/sản phẩm/quy trình ở dòng đầu mỗi section.
5. **Self-contained**: đọc 1 section riêng vẫn hiểu, không cần đọc trước/sau.
6. **Bảng đơn giản**: header rõ + cells ngắn.
7. **Tránh viết tắt** không giải thích (lần đầu: "khách hàng (KH)").

## 4 templates

| Template | File | Dùng cho |
|---|---|---|
| 1. Hồ sơ nhân vật | `01_HoSo_NhanVat.md` | Bác sĩ, bệnh nhân VIP, đối tác, nhân viên |
| 2. Quy trình SOP | `02_QuyTrinh_SOP.md` | Quy trình khám, xử lý đơn, vận hành |
| 3. FAQ Câu hỏi thường gặp | `03_FAQ.md` | Hỏi đáp khách hàng, hỏi đáp nội bộ |
| 4. Bài viết kiến thức | `04_KienThuc.md` | Bài viết bệnh học, sản phẩm, dịch vụ |

## Quy trình biên soạn 3 bước

### Bước 1: Copy template + fill nội dung
```bash
cp documents/templates/01_HoSo_NhanVat.md documents/profiles/BS_Le_Phuong.md
# Edit, replace placeholder [...] với nội dung thật
```

### Bước 2: Self-check trước upload (8 mục)
- [ ] H1 duy nhất ở đầu file
- [ ] H2/H3 logic theo cấu trúc
- [ ] Mỗi section đứng độc lập
- [ ] Tên entity front-load
- [ ] Section 150-400 từ
- [ ] Bảng đơn giản, có header
- [ ] Không jargon viết tắt
- [ ] Không phải template Q&A reference rỗng

### Bước 3: Test 3 query sau khi upload
- 1 câu definition: "[X] là gì?"
- 1 câu procedure: "Làm thế nào để [X]?"
- 1 câu specific: "[Entity Y] có [property Z] không?"

Nếu cả 3 trả đúng file + chunk có nội dung → format OK.

## Kết quả dự kiến

| Format hiện tại (mix) | Format theo template |
|---|---|
| Top-3 hit rate ~75% | Top-3 hit rate ~85-95% |
| Section dài/ngắn không đều | Section đều 150-400 từ |
| Heading sometimes bold | Heading H1/H2/H3 chuẩn |
| Section refer "ở trên" | Self-contained 100% |

---
*Templates v1 — 2026-05-04*
