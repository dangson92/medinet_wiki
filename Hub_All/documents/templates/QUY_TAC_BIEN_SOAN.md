# 📝 QUY TẮC BIÊN SOẠN TÀI LIỆU TRI THỨC — Hướng dẫn từng bước cho người mới

> **Bạn không cần biết kỹ thuật.** Tài liệu này dành cho: nhân viên content marketing, bác sĩ, chuyên viên Y tế, lễ tân, nhân viên CSKH... ai cũng có thể đọc và viết tài liệu chuẩn cho hệ thống tri thức Medinet Wiki.
>
> **Đọc 30 phút → biết viết tài liệu giúp AI trả lời chính xác.**

---

## 🤔 Phần 1 — Hệ thống RAG hoạt động ra sao? (Hiểu mới viết đúng)

Hệ thống tri thức Medinet Wiki dùng công nghệ gọi là **RAG** (Retrieval Augmented Generation). Đơn giản:

1. Bạn upload file tài liệu (Word/PDF/Markdown).
2. Hệ thống **cắt** file thành các đoạn nhỏ gọi là **"chunks"** (mỗi chunk khoảng 1 đoạn văn).
3. Hệ thống **lưu** mỗi chunk vào cơ sở dữ liệu vector (như "thư viện điện tử").
4. Khi user hỏi "Bác sĩ Lê Phương là ai?" → hệ thống **tìm các chunk liên quan nhất** → đưa cho AI tổng hợp câu trả lời.

**🔑 Hiểu CHỦ CHỐT:** Hệ thống KHÔNG đọc file của bạn từ đầu đến cuối như con người. Nó chỉ đọc **các chunk rời rạc** mà nó cho là liên quan đến câu hỏi.

→ Nếu chunk không có context đầy đủ → AI sẽ trả lời không đầy đủ.
→ Nếu chunk chứa thông tin lẫn lộn → AI sẽ confuse.
→ Nếu file format kém → cắt sai chunk → AI mất thông tin.

**Mục tiêu của 8 quy tắc dưới đây:** đảm bảo MỖI chunk có đủ context, đứng độc lập, dễ tìm.

---

## 📐 Phần 2 — 8 quy tắc chi tiết

### Quy tắc 1: Có H1 duy nhất ở đầu file

#### 🎯 Quy tắc đơn giản
Mỗi file Markdown PHẢI có **đúng 1 tiêu đề lớn nhất** (gọi là H1, viết bằng `#` ở đầu dòng) ở dòng đầu tiên. KHÔNG có H1 thứ 2.

#### 🤔 Vì sao quan trọng?
H1 là **tên file** trong mắt hệ thống. Khi user search, hệ thống dùng H1 để:
- Hiển thị tên tài liệu trong kết quả.
- Phân biệt file này với file khác.
- Xác định "scope" của file (file này nói về gì).

Nếu có 2 H1 → hệ thống bối rối không biết tên thực sự của file.
Nếu không có H1 → file bị coi là "không tên".

#### ❌ Ví dụ SAI

**Sai 1: Không có H1**
```markdown
## Bác sĩ Lê Phương

Bác sĩ Lê Phương là...
```

**Sai 2: Có 2 H1**
```markdown
# Phần 1: Bác sĩ Lê Phương

[content]

# Phần 2: Bác sĩ Vân Anh

[content]
```

**Sai 3: Dùng bold thay vì H1**
```markdown
**HỒ SƠ BÁC SĨ LÊ PHƯƠNG**

[content]
```

#### ✅ Ví dụ ĐÚNG

```markdown
# Hồ sơ Bác sĩ Lê Phương — Đỗ Minh Đường

## Thông tin cơ bản

[content]

## Bằng cấp

[content]
```

#### 🔍 Cách self-check
1. Mở file Markdown.
2. Tìm dòng bắt đầu bằng `#` (chỉ 1 dấu thăng + space).
3. Đếm: phải có **đúng 1 dòng** như vậy.
4. Dòng đó phải ở **đầu file** (sau khi bỏ qua các comment hoặc front-matter nếu có).

**Mẹo:** Trong VS Code, mở file → Ctrl+F → tìm `^# ` (regex bật) → kết quả phải = 1.

---

### Quy tắc 2: H2/H3 đặt logic theo cấu trúc

#### 🎯 Quy tắc đơn giản
Sau H1, dùng **H2** (`##`) cho các phần chính, **H3** (`###`) cho các tiểu mục con. KHÔNG nhảy cóc (vd: H1 thẳng tới H4). Tránh dùng quá H3 (H4-H6 chỉ khi cực kỳ cần).

#### 🤔 Vì sao quan trọng?
Hệ thống dùng heading để **cắt file thành chunks**. Mỗi chunk thường tương ứng với 1 H2 hoặc H3:
- Heading rõ → chunks chia hợp lý → mỗi chunk có 1 chủ đề.
- Heading lung tung → chunks chia bậy → 1 chunk có 3 chủ đề khác nhau → AI confuse.

Tưởng tượng heading như **mục lục sách**. Mục lục logic → đọc dễ. Mục lục lộn xộn → đọc khó.

#### ❌ Ví dụ SAI

**Sai 1: Nhảy cóc heading**
```markdown
# Hồ sơ Bác sĩ Lê Phương

#### Bằng cấp     ← Sai: nhảy từ H1 thẳng tới H4

[content]
```

**Sai 2: Cùng cấp nhưng không cùng loại**
```markdown
# Hồ sơ Bác sĩ Lê Phương

## Bằng cấp        ← Phần chính
## Bệnh chữa       ← Phần chính (OK)
## Năm 2018       ← Sai: không phải phần chính, đây là tiểu mục thuộc "Công trình nghiên cứu"
```

**Sai 3: Quá nhiều H4-H6**
```markdown
## Chuyên môn
### Xương khớp
#### Thoái hóa cột sống
##### Cột sống cổ
###### Đốt C1     ← Sai: quá sâu, hệ thống bỏ qua
```

#### ✅ Ví dụ ĐÚNG

```markdown
# Hồ sơ Bác sĩ Lê Phương

## Thông tin cơ bản           ← H2: phần lớn
## Bằng cấp và đào tạo        ← H2: phần lớn
## Chuyên môn điều trị        ← H2: phần lớn
### Xương khớp                ← H3: tiểu mục thuộc "Chuyên môn"
### Cơ xương khớp             ← H3: tiểu mục thuộc "Chuyên môn"
## Quy trình khám             ← H2: phần lớn
## Lịch khám                  ← H2: phần lớn
```

#### 🔍 Cách self-check
1. Mở file → click vào "Outline" trong VS Code (hoặc "Toggle Markdown Preview" rồi xem mục lục bên trái).
2. Đọc outline từ trên xuống → có giống "mục lục sách" không?
3. Có heading nào "lạc loài" (đặt sai cấp) không?
4. Có nhảy cóc cấp không (vd H2 → H4 thiếu H3)?

**Quy tắc 3-cấp:** **80% file chỉ cần H1 + H2 + H3 là đủ.** Nếu phải dùng H4+ → có thể section đó cần tách thành file riêng.

---

### Quy tắc 3: Mỗi section đứng độc lập

#### 🎯 Quy tắc đơn giản
Đọc 1 section riêng (mà không đọc section trước/sau) vẫn phải hiểu được. KHÔNG viết "như đã nói ở trên", "xem phần dưới", "anh ấy", "ông", "bệnh này"... khi không có context.

#### 🤔 Vì sao quan trọng?
Hệ thống **cắt file ra thành các chunks RỜI RẠC**. AI khi trả lời chỉ thấy 1-3 chunks gần nhất với câu hỏi, **KHÔNG thấy section trước/sau**.

→ Nếu section refer "ở trên" → AI không biết "ở trên" là gì → trả lời thiếu context → user thất vọng.

Đây là quy tắc **QUAN TRỌNG NHẤT** cho RAG quality.

#### ❌ Ví dụ SAI

**Sai 1: Refer "ở trên"**
```markdown
## Chuyên môn của ông
Như đã nói ở trên, ông chuyên về xương khớp với 40 năm kinh nghiệm.
```

Khi user search "BS Lê Phương chuyên gì?" → hệ thống chỉ trả về chunk này → AI thấy "ông" + "ở trên" → KHÔNG biết "ông" là ai.

**Sai 2: Pronoun không có antecedent**
```markdown
## Quy trình điều trị
Anh ấy thường áp dụng phương pháp tứ chẩn trước khi đặt phác đồ.
```

"Anh ấy" là ai? Chunk không nói. AI bị mất context.

**Sai 3: Refer "bệnh này", "phòng khám đó"**
```markdown
## Phương pháp điều trị
Bệnh này thường được chữa bằng bài thuốc XYZ tại phòng khám đó.
```

Bệnh nào? Phòng khám nào?

#### ✅ Ví dụ ĐÚNG

**Đúng 1: Lặp lại tên đầy đủ**
```markdown
## Chuyên môn Bác sĩ Lê Phương
Bác sĩ Lê Phương chuyên về xương khớp với 40 năm kinh nghiệm tại Đỗ Minh Đường.
```

**Đúng 2: Lặp lại entity name**
```markdown
## Quy trình điều trị của Bác sĩ Lê Phương
Bác sĩ Lê Phương thường áp dụng phương pháp tứ chẩn (vọng-văn-vấn-thiết) trước khi đặt phác đồ cá nhân hóa.
```

**Đúng 3: Cụ thể hóa entity**
```markdown
## Phương pháp điều trị thoái hóa cột sống tại Đỗ Minh Đường
Thoái hóa cột sống thường được chữa bằng bài thuốc Cốt Vương Thần Hiệu tại Đỗ Minh Đường, kết hợp châm cứu 2 lần/tuần.
```

#### 🔍 Cách self-check
**Test "đọc rời":**
1. Copy 1 section bất kỳ ra notepad mới.
2. Đọc nó như chưa biết gì về tài liệu.
3. **Có hiểu được không?** Có biết "anh ấy", "bệnh này" là gì không?
4. Nếu KHÔNG → sửa lại bằng cách thay pronoun/refer bằng tên đầy đủ.

**Mẹo nhanh:** dùng Find & Replace, search các từ sau và check từng chỗ:
- "ông", "bà", "anh", "chị" → có context không?
- "ở trên", "ở dưới", "phần trước", "như đã nói" → xóa, viết lại
- "bệnh này", "thuốc này", "ông ấy" → thay bằng tên cụ thể

---

### Quy tắc 4: Tên entity (người/sản phẩm/quy trình) front-load

#### 🎯 Quy tắc đơn giản
Tên người, tên sản phẩm, tên quy trình PHẢI xuất hiện ở **30 từ đầu** của mỗi section. Tốt nhất là ở **dòng đầu tiên** hoặc trong **heading**.

#### 🤔 Vì sao quan trọng?
Hệ thống RAG tìm kiếm bằng cách **so sánh ý nghĩa** giữa câu hỏi của user và nội dung chunk. Khi user hỏi "BS Lê Phương":
- Nếu chunk có "BS Lê Phương" ở dòng đầu → hệ thống cho điểm CAO → trả lên top.
- Nếu "BS Lê Phương" ở giữa hoặc cuối chunk → điểm THẤP → có thể không trả về.

Tưởng tượng giống như Google: tiêu đề bài chứa từ khóa = SEO tốt = lên top. RAG tương tự.

#### ❌ Ví dụ SAI

**Sai: Tên ở giữa/cuối chunk**
```markdown
## Chuyên môn điều trị

Trải qua 40 năm cống hiến trong nghề y, vị bác sĩ này đã đào tạo hàng nghìn 
học trò, công bố hàng chục công trình nghiên cứu, được trao tặng danh hiệu 
Thầy thuốc Ưu tú vào năm 2015. Bác sĩ Lê Phương hiện chuyên về xương khớp 
và cột sống tại Đỗ Minh Đường.
```

→ User search "BS Lê Phương xương khớp" → match chỉ cuối chunk → điểm thấp → có thể bị bỏ qua.

#### ✅ Ví dụ ĐÚNG

**Đúng: Tên ở dòng đầu**
```markdown
## Bác sĩ Lê Phương — Chuyên môn điều trị

Bác sĩ Lê Phương chuyên về xương khớp và cột sống tại Đỗ Minh Đường, với 
40 năm kinh nghiệm. Ông được trao tặng danh hiệu Thầy thuốc Ưu tú năm 2015 
và đã đào tạo hàng nghìn học trò trong nghề YHCT.
```

→ User search "BS Lê Phương xương khớp" → match ngay 10 từ đầu → điểm cao → top kết quả.

**Đúng hơn: Tên trong heading + dòng đầu**
```markdown
## Bác sĩ Lê Phương — Chuyên môn điều trị xương khớp

Bác sĩ Lê Phương là chuyên gia hàng đầu về điều trị xương khớp tại Đỗ Minh Đường...
```

#### 🔍 Cách self-check
1. Đọc dòng đầu mỗi section.
2. **Tên entity (người/sản phẩm/quy trình) có xuất hiện không?**
3. Nếu KHÔNG → viết lại, đặt tên ngay đầu.

**Quy tắc thực dụng:**
- Section về 1 người → tên người ở heading + dòng đầu.
- Section về 1 sản phẩm → tên sản phẩm ở heading + dòng đầu.
- Section về 1 quy trình → tên quy trình ở heading + dòng đầu.

---

### Quy tắc 5: Section dài 150-400 từ

#### 🎯 Quy tắc đơn giản
Mỗi section (giữa 2 heading H2 hoặc H3) nên dài **khoảng 150-400 từ tiếng Việt** (~10-25 dòng văn bản).

#### 🤔 Vì sao quan trọng?
Hệ thống cắt chunks dựa vào **token count** (~ số từ). Mỗi chunk lý tưởng 200-500 tokens (~150-400 từ tiếng Việt):

- **Quá ngắn (< 100 từ):** Hệ thống có thể merge với section khác → mất ranh giới chủ đề.
- **Quá dài (> 600 từ):** Hệ thống cắt giữa câu/giữa ý → mất context.

Tưởng tượng giống như viết bài Facebook: quá ngắn = không đủ thông tin, quá dài = đọc lười = không ai đọc hết.

#### ❌ Ví dụ SAI

**Sai 1: Quá ngắn (< 50 từ)**
```markdown
## Bằng cấp
BSCK II.

## Năm sinh  
1962.

## Quê quán
Hà Nội.
```

→ Hệ thống merge 3 section này → trộn lẫn thông tin.

**Sai 2: Quá dài (> 600 từ)**
```markdown
## Tổng quan Bác sĩ Lê Phương

[600 từ liên tục về bằng cấp + chuyên môn + quy trình + lịch khám + công trình + 
bệnh án nổi tiếng + triết lý + đối tác + giải thưởng + ...]
```

→ Hệ thống cắt giữa chunk → "công trình" bị tách khỏi "giải thưởng" → AI mất liên kết.

#### ✅ Ví dụ ĐÚNG

```markdown
## Bác sĩ Lê Phương — Thông tin cơ bản

Bác sĩ Lê Phương là Thầy thuốc Ưu tú, Bác sĩ Chuyên khoa II Y học cổ truyền, 
hiện công tác tại Đỗ Minh Đường — Hà Nội. Sinh năm 1962 tại Hà Nội, ông tốt 
nghiệp Đại học Y Hà Nội năm 1985 và bắt đầu sự nghiệp YHCT từ đó. Sau 40 năm 
hành nghề, Bác sĩ Lê Phương đã trở thành một trong những chuyên gia hàng đầu 
về xương khớp tại Việt Nam.

[~150 từ — vừa đủ context tổng quan, không quá tải.]
```

#### 🔍 Cách self-check
1. Trong VS Code: chọn (highlight) toàn bộ 1 section → status bar hiện số từ.
2. Hoặc copy section vào Word/Google Docs → Tools → Word Count.
3. Hoặc đếm dòng: 10-25 dòng văn bản tiếng Việt thường ≈ 150-400 từ.

**Mẹo:** Nếu section của bạn:
- < 100 từ → **bổ sung context, ví dụ, chi tiết**.
- > 500 từ → **tách thành 2 H3 con riêng biệt**.

---

### Quy tắc 6: Bảng đơn giản, có header

#### 🎯 Quy tắc đơn giản
Bảng phải có **dòng header rõ ràng** (tên cột). Cells (ô) nên ngắn gọn (1 fact / 1 cell). KHÔNG hợp nhất ô (merge cell).

#### 🤔 Vì sao quan trọng?
Hệ thống RAG hiện tại (extractor Go cũ) **flatten bảng thành prose** (chuỗi text liên tục): `BS Lê Phương | Xương khớp | 40 năm | BS Vân Anh | Da liễu | 25 năm`.

- Bảng có header rõ → flatten vẫn hiểu được "cột tên BS, cột chuyên môn, cột năm KN".
- Bảng merge cell → flatten thành đống lộn xộn → AI không biết cell nào thuộc hàng/cột nào.

(**Note:** Sau Phase 5 với Docling, bảng giữ HTML structure đầy đủ — nhưng vẫn nên giữ bảng đơn giản để fallback work.)

#### ❌ Ví dụ SAI

**Sai 1: Không có header**
```markdown
| BS Lê Phương | Xương khớp | 40 năm |
| BS Vân Anh | Da liễu | 25 năm |
```

→ AI không biết cột nào là gì.

**Sai 2: Merge cell phức tạp**
```markdown
| Bác sĩ        | Chuyên môn               | Lịch khám                |
|--------------|--------------------------|--------------------------|
| BS Lê Phương | Xương khớp, Cột sống,    | T2-4-6 sáng + chiều,    |
|              | Cơ xương khớp, Phục hồi  | T7 sáng                 |
|              | chức năng                |                          |
| BS Vân Anh   | Da liễu, Mỹ phẩm,       | T3-5 sáng,              |
|              | Thẩm mỹ nội khoa        | CN sáng                  |
```

→ Cells dài lê thê, multi-line → flatten lộn xộn.

#### ✅ Ví dụ ĐÚNG

**Đúng 1: Header rõ + cell ngắn**
```markdown
| Bác sĩ | Chuyên môn chính | Năm kinh nghiệm |
|---|---|---|
| BS Lê Phương | Xương khớp | 40 |
| BS Vân Anh | Da liễu | 25 |
| BS Hải Long | Tiêu hóa | 28 |
```

**Đúng 2: Tách bảng phức tạp thành nhiều bảng đơn**

Thay vì 1 bảng to với 3 cột "Bác sĩ | Tất cả chuyên môn | Tất cả lịch khám":

```markdown
## Danh sách bác sĩ và chuyên môn chính

| Bác sĩ | Chuyên môn chính |
|---|---|
| BS Lê Phương | Xương khớp |
| BS Vân Anh | Da liễu |

## Lịch khám tuần tại Đỗ Minh Đường

| Bác sĩ | Thứ 2 | Thứ 3 | Thứ 4 | Thứ 5 | Thứ 6 | Thứ 7 |
|---|---|---|---|---|---|---|
| BS Lê Phương | ✓ | — | ✓ | — | ✓ | ✓ |
| BS Vân Anh | — | ✓ | — | ✓ | — | — |
```

#### 🔍 Cách self-check
1. Mỗi bảng có dòng header (dòng đầu tiên với tên cột) không?
2. Cells dưới có ngắn (≤ 5-7 từ) không?
3. Có cell nào trống không (sign of merge cell)? → fill nội dung hoặc tách bảng.
4. Có cell nào chứa multi-line không? → tách thành nhiều dòng.

---

### Quy tắc 7: Không jargon viết tắt không giải thích

#### 🎯 Quy tắc đơn giản
**Lần đầu** dùng từ viết tắt → viết FULL + ngoặc viết tắt: `Y học cổ truyền (YHCT)`. Sau đó có thể dùng viết tắt thoải mái trong cùng section.

NHƯNG: mỗi section MỚI nên giải thích lại (vì user search có thể chỉ thấy 1 section, không thấy section khác).

#### 🤔 Vì sao quan trọng?
User search bằng từ tự nhiên: "phòng khám y học cổ truyền" — nếu chunk chỉ có "phòng khám YHCT" → ít match (vì vector embedding của "y học cổ truyền" khác "YHCT").

→ Viết FULL ÍT NHẤT 1 LẦN trong mỗi section để chunk match được cả 2 cách user hỏi.

Ngoài ra, có những từ viết tắt nội bộ (KH = khách hàng, BN = bệnh nhân) chỉ team biết — user thông thường KHÔNG biết → viết full.

#### ❌ Ví dụ SAI

**Sai 1: Viết tắt từ đầu, không giải thích**
```markdown
## Phương pháp điều trị
Tại DMD, BS áp dụng YHCT kết hợp YHHĐ. KH được TC + đặt PĐ cá nhân hóa.
```

→ User không hiểu DMD, BS, YHCT, YHHĐ, KH, TC, PĐ là gì.

**Sai 2: Viết tắt khác nhau cho cùng entity**
```markdown
Section 1: ...phòng khám DMD...
Section 2: ...Đỗ Minh Đường...
Section 3: ...DMĐ...
```

→ User search 1 trong 3 cách → chỉ match 1 section → mất context khác.

#### ✅ Ví dụ ĐÚNG

**Đúng: Giải thích lần đầu + dùng nhất quán**
```markdown
## Phương pháp điều trị tại Đỗ Minh Đường

Tại Đỗ Minh Đường (DMD), bác sĩ áp dụng Y học cổ truyền (YHCT) kết hợp Y học 
hiện đại (YHHĐ). Khách hàng được tứ chẩn (TC: vọng-văn-vấn-thiết) và đặt 
phác đồ (PĐ) cá nhân hóa theo thể trạng.

## Quy trình tứ chẩn YHCT

Tứ chẩn (YHCT, gồm 4 phương pháp chẩn đoán cổ truyền) là bước đầu trong khám 
bệnh tại Đỗ Minh Đường:
- Vọng: nhìn sắc mặt, lưỡi.
- Văn: nghe nhịp thở, giọng nói.
- Vấn: hỏi tiền sử, sinh hoạt.
- Thiết: bắt mạch 3 vị trí cổ tay.
```

→ Mỗi section đều giải thích lần đầu, user search bất kỳ keyword nào cũng match được.

#### 🔍 Cách self-check
1. Mở file → tìm các từ viết hoa toàn bộ (ALL CAPS) hoặc ngắn (2-4 ký tự).
2. Mỗi từ viết tắt → có giải thích lần đầu trong section đó không?
3. Cùng entity có viết nhất quán không (vd luôn "Đỗ Minh Đường" + "(DMD)")?

**Bảng các từ viết tắt cần giải thích:**

| Viết tắt | Viết full lần đầu |
|---|---|
| BS | Bác sĩ (BS) |
| BN | Bệnh nhân (BN) |
| KH | Khách hàng (KH) |
| YHCT | Y học cổ truyền (YHCT) |
| YHHĐ | Y học hiện đại (YHHĐ) |
| DMD | Đỗ Minh Đường (DMD) |
| TC | Tứ chẩn (TC) |
| PĐ | Phác đồ (PĐ) |
| BSCK | Bác sĩ Chuyên khoa (BSCK) |
| LY | Lương y (LY) |
| TT | Thầy thuốc (TT) |

---

### Quy tắc 8: Không phải template "Câu hỏi tham chiếu"

#### 🎯 Quy tắc đơn giản
Section PHẢI chứa **câu trả lời** (content thật), KHÔNG chỉ là **danh sách câu hỏi** (template Q&A reference).

#### 🤔 Vì sao quan trọng?
Hệ thống có 1 tính năng tự động gọi là **Augmenter**: nó tự sinh "Câu hỏi tham chiếu" từ content của bạn để giúp AI tìm chunk dễ hơn.

→ Nếu file của bạn ĐÃ là template Q&A reference (chỉ list câu hỏi, không có câu trả lời) → augmenter sinh **meta-question** (câu hỏi về câu hỏi) → vô nghĩa → user search không match.

Đây là vấn đề chúng tôi GẶP THỰC SỰ với file `DMD_T3-01_HoSo_BacSi_EEAT_v1.md` — file chỉ chứa list "Câu hỏi tham chiếu: BS Lê Phương là ai? | Có chuyên môn gì?" mà KHÔNG có câu trả lời → search "BS Lê Phương" trả về answer thiếu nhiều thông tin.

#### ❌ Ví dụ SAI

**Sai: File chỉ là template Q&A**
```markdown
# Hồ sơ Bác sĩ Lê Phương

## Câu hỏi tham chiếu phần 1
- Bác sĩ Lê Phương là ai?
- Bác sĩ Lê Phương có chuyên môn gì?
- Bác sĩ Lê Phương có bằng cấp gì?
- Bác sĩ Lê Phương khám ở đâu?

## Câu hỏi tham chiếu phần 2
- Bác sĩ Lê Phương chữa bệnh gì giỏi nhất?
- Bác sĩ Lê Phương có tư vấn online không?
- Bác sĩ Lê Phương có nhận BHYT không?
```

→ KHÔNG có câu trả lời nào. AI không thể trả lời gì khi user hỏi.

#### ✅ Ví dụ ĐÚNG

```markdown
# Hồ sơ Bác sĩ Lê Phương

## Bác sĩ Lê Phương là ai
Bác sĩ Lê Phương là Thầy thuốc Ưu tú, Bác sĩ Chuyên khoa II Y học cổ truyền, 
hiện đang là Trưởng khoa Y học cổ truyền tại phòng khám Đỗ Minh Đường (DMD) 
ở Hà Nội. Ông có 40 năm kinh nghiệm trong nghề YHCT.

## Chuyên môn của Bác sĩ Lê Phương
Bác sĩ Lê Phương chuyên điều trị các bệnh xương khớp, cột sống và cơ xương 
khớp. Cụ thể:
- Thoái hóa cột sống cổ và thắt lưng.
- Viêm khớp dạng thấp.
- Gout cấp và mạn tính.
- Phục hồi chức năng sau chấn thương.

## Bằng cấp của Bác sĩ Lê Phương
- 1985: Bác sĩ Y khoa — ĐH Y Hà Nội.
- 1995: Chuyên khoa I Y học cổ truyền.
- 2010: Chuyên khoa II Y học cổ truyền.
- 2015: Danh hiệu Thầy thuốc Ưu tú.

## Lịch khám của Bác sĩ Lê Phương tại Đỗ Minh Đường
Bác sĩ Lê Phương khám tại Đỗ Minh Đường (DMD) Hà Nội theo lịch:
- Thứ 2-4-6: 8:00-11:30 và 14:00-17:00.
- Thứ 7: 8:00-12:00.
Đặt lịch qua hotline 1900-XXXX hoặc Zalo OA "Đỗ Minh Đường".
```

→ Mỗi câu hỏi có **câu trả lời cụ thể**. AI dễ dàng trả lời chi tiết.

#### 🔍 Cách self-check
**Test "thay câu hỏi bằng câu trả lời":**
1. Đọc 1 section bất kỳ.
2. Có câu hỏi (kết thúc bằng `?`) nào KHÔNG có câu trả lời cụ thể đi kèm không?
3. Có dòng nào dạng "Câu hỏi tham chiếu: X | Y | Z" không?
4. Nếu CÓ → đây là template Q&A reference → viết lại với content thật.

**Quy tắc:** Mỗi section phải trả lời được câu hỏi `[Chủ đề] là gì?` hoặc `[Chủ đề] làm thế nào?` bằng nội dung thực tế trong chính section đó.

---

## 🎯 Phần 3 — Cheatsheet 1 trang in ra dán bàn

```
╔══════════════════════════════════════════════════════════════════════════╗
║          8 QUY TẮC BIÊN SOẠN TÀI LIỆU TRI THỨC MEDINET WIKI              ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  1. H1 DUY NHẤT: 1 dòng `# Tên file` ở đầu file                          ║
║                                                                          ║
║  2. H2/H3 LOGIC: H1 → H2 → H3 (không nhảy cóc, không quá 3 cấp)          ║
║                                                                          ║
║  3. SECTION ĐỘC LẬP: đọc riêng vẫn hiểu (không "ở trên/dưới")            ║
║                                                                          ║
║  4. ENTITY FRONT-LOAD: tên người/SP ở dòng đầu mỗi section               ║
║                                                                          ║
║  5. SECTION 150-400 TỪ: ~10-25 dòng văn bản tiếng Việt                   ║
║                                                                          ║
║  6. BẢNG ĐƠN GIẢN: có header, không merge cell, cells ngắn               ║
║                                                                          ║
║  7. KHÔNG VIẾT TẮT mà không giải thích: full + (viết tắt) lần đầu        ║
║                                                                          ║
║  8. KHÔNG TEMPLATE Q&A REFERENCE: phải có câu TRẢ LỜI thật               ║
║                                                                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  CHECK CUỐI CÙNG (10 giây trước upload):                                 ║
║                                                                          ║
║  □ Mở Outline VS Code: heading có giống mục lục sách không?              ║
║  □ Đọc 1 section random: có hiểu mà không cần đọc trước/sau không?       ║
║  □ Ctrl+F "ông", "bà", "ở trên": có cần thay tên cụ thể không?           ║
║  □ Search file: có dòng "Câu hỏi tham chiếu" không có câu trả lời?       ║
║                                                                          ║
║  → Nếu 4 check OK → upload an toàn.                                      ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## ❓ Phần 4 — FAQ về quy tắc

### Q1: Tôi viết bằng Word/Docx được không?
**Đáp:** Được. NHƯNG bạn phải dùng **Heading styles** trong Word (Heading 1, Heading 2, Heading 3) chứ KHÔNG dùng bold + size lớn. Hệ thống đọc Word styles để cắt chunks.

**Cách dùng Heading styles trong Word:**
1. Click vào dòng tiêu đề.
2. Trong toolbar → click "Heading 1" / "Heading 2" / "Heading 3".
3. KHÔNG dùng "Title" hoặc bold.

Markdown vẫn là format CHUẨN NHẤT cho RAG (rõ ràng, đơn giản, không noise format).

### Q2: File của tôi dài quá (10000+ từ), có cần cắt nhỏ không?
**Đáp:** **CÓ.** Quy tắc:
- File 1500-3000 từ = ngọt nhất (1 chủ đề trung bình).
- File 5000+ từ → tách thành nhiều file con theo chủ đề.

Vd: file "Thoái hóa cột sống — Tổng quan" 8000 từ → tách:
- `ThoaiHoaCotSong_TongQuan.md` (định nghĩa + nguyên nhân)
- `ThoaiHoaCotSong_TrieuChung.md` (triệu chứng + chẩn đoán)
- `ThoaiHoaCotSong_DieuTri.md` (phương pháp + bài thuốc)
- `ThoaiHoaCotSong_PhongNgua.md` (phòng + sinh hoạt)

### Q3: Có cần ảnh/video không?
**Đáp:** Có thể, nhưng RAG **chỉ đọc text**. Ảnh/video không được index. Nếu thêm:
- Mỗi ảnh/video PHẢI có **caption text** mô tả đầy đủ nội dung ảnh.
- Vd: `![Bác sĩ Lê Phương đang khám bệnh nhân tại Đỗ Minh Đường](#fig-1)` → caption sẽ được index.

### Q4: Có dùng emoji được không?
**Đáp:** Hạn chế. Emoji không có ý nghĩa cho vector embedding. **Dùng emoji ở heading hoặc bullet để dễ đọc cho người, nhưng nội dung chính phải là text thuần.**

### Q5: Tôi không chắc section của tôi có tốt không, làm sao test?
**Đáp:** Sau khi upload, vào **Cross-Hub Search** trên UI, thử 3 câu hỏi user thực tế sẽ hỏi:
- 1 câu định nghĩa: "[X] là gì?"
- 1 câu quy trình: "Làm thế nào để [X]?"
- 1 câu cụ thể: "[Entity Y] có [property Z] không?"

Nếu cả 3 trả về đúng file + chunk có nội dung liên quan → file OK.

Nếu trả về "Dữ liệu hiện có chưa đủ" → review lại theo 8 quy tắc.

### Q6: Tôi có nên copy nguyên văn từ tài liệu cũ không?
**Đáp:** KHÔNG. Tài liệu cũ thường vi phạm nhiều quy tắc. **Nên re-author** bằng template (`documents/templates/`):
1. Copy template phù hợp (Hồ sơ / SOP / FAQ / Kiến thức).
2. Fill nội dung từ tài liệu cũ.
3. Apply 8 quy tắc trên.

### Q7: Tôi có thể nhờ AI viết tài liệu cho tôi không?
**Đáp:** Có thể. NHƯNG:
- AI có thể viết content nhưng KHÔNG hiểu domain Y tế chuyên sâu — bạn phải review chính xác.
- AI hay vi phạm quy tắc 3 (refer "ở trên") + quy tắc 4 (entity ở giữa câu) — bạn phải sửa.
- **Test mỗi câu**: thông tin có đúng không? Có tránh hallucination không?

Tốt nhất: bạn viết outline + nội dung chính, AI hỗ trợ rephrase + format theo template.

---

## 📊 Phần 5 — Bảng tổng hợp 8 quy tắc

| # | Quy tắc | Test 5 giây | Tác động RAG |
|---|---|---|---|
| 1 | H1 duy nhất | Đếm dòng `# ` ở đầu file = 1 | Phân biệt file |
| 2 | H2/H3 logic | Outline VS Code có giống mục lục sách | Cắt chunks chính xác |
| 3 | Section độc lập | Đọc riêng 1 section vẫn hiểu | **QUAN TRỌNG NHẤT** — mỗi chunk có context |
| 4 | Entity front-load | Tên ở 30 từ đầu | Search match điểm cao |
| 5 | Section 150-400 từ | Word count VS Code | Chunk size hợp lý |
| 6 | Bảng đơn giản | Có header + cells ≤ 5 từ | Flatten không lộn xộn |
| 7 | Không viết tắt | Ctrl+F từ viết tắt → check | Match đa cách user hỏi |
| 8 | Không Q&A template | Search "Câu hỏi tham chiếu" | Có content thực để AI trả lời |

---

## 🚀 Phần 6 — Quick start cho người mới

**Bạn vừa đọc xong → muốn viết file đầu tiên?**

```bash
# 1. Copy template phù hợp
cp documents/templates/01_HoSo_NhanVat.md documents/profiles/BS_Le_Phuong.md

# 2. Mở file trong VS Code (hoặc text editor bất kỳ)

# 3. Replace tất cả [...] với nội dung thật

# 4. Xóa các comment HTML <!-- ... -->

# 5. Chạy 4-check 10 giây cuối từ Cheatsheet

# 6. Upload qua UI: http://192.168.0.113:3000/documents/new

# 7. Test 3 query — nếu trả về đúng → DONE!
```

**Cần giúp đỡ?** Gửi câu hỏi vào Slack channel `#medinet-wiki-help` hoặc liên hệ admin team.

---

*Quy tắc v1 — 2026-05-04. Cập nhật khi ship Docling Phase 5.*
