# MEDINET WIKI — RAG PIPELINE IMPLEMENTATION PLAN

**Kế hoạch triển khai chi tiết cho Claude Code**

Entity-Centric Chunking · BGE-M3 Hybrid Retrieval · ViRanker Reranking

Tham chiếu: RAGFlow (DeepDoc) + Open Notebook (LangChain Splitters)

Phiên bản 2.0 · Tháng 7/2025

---

## PHẦN 1: TỔNG QUAN KIẾN TRÚC RAG PIPELINE

Tài liệu này đặc tả chi tiết các phase để Claude Code có thể implement từng bước một pipeline RAG tối ưu cho tài liệu tiếng Việt của Medinet Wiki — đặc biệt là tài liệu vận hành nội bộ (hồ sơ bác sĩ, phân công nhân vật, quy tắc E-E-A-T), bài báo chí, và nghiên cứu y học.

### 1.1 Kiến trúc tổng thể

| Tầng | Vai trò | Nguồn tham chiếu | Công nghệ |
|------|---------|-------------------|-----------|
| Tầng 1: Document Parsing | OCR + Layout Recognition + Table Structure | RAGFlow DeepDoc | Python microservice (ONNX models) |
| Tầng 2: Entity-Centric Chunking | Chunk theo thực thể (nhân vật, kênh, bệnh lý) + báo chí + lâm sàng | Custom (9 levels) | Go service |
| Tầng 3: Metadata Enrichment | Gắn tag entities, channels, diseases, rule_type | Custom | Go service |
| Tầng 4: Embedding | BGE-M3 dense + sparse vectors | RAGFlow + Open Notebook | Python (sentence-transformers) |
| Tầng 5: Vector Storage | Lưu trữ và index vectors | RAGFlow (Elasticsearch) | ChromaDB / Qdrant |
| Tầng 6: Hybrid Retrieval | Dense 60% + Sparse/BM25 40% + Reranking | RAGFlow | Go service + ViRanker |
| Tầng 7: Generation | LLM đọc context trả lời | N/A | Claude API / GPT API |

---

## PHASE 1: DOCUMENT PARSING SERVICE (Tuần 1–2)

**Mục tiêu: Xây dựng service nhận file PDF/DOCX → trả về JSON có cấu trúc (text blocks + tables + figures + metadata)**

### 1A. Tách DeepDoc thành microservice

Tham chiếu: RAGFlow `deepdoc/parser/` và `deepdoc/vision/`

#### Task 1A-01: Setup Python environment + DeepDoc dependencies

| Hạng mục | Chi tiết |
|----------|---------|
| Input cho Claude Code | `git clone https://github.com/infiniflow/ragflow.git && cd ragflow/deepdoc` |
| Các file cần copy | `deepdoc/vision/` (OCR, LayoutRecognizer, TableStructureRecognizer), `deepdoc/parser/` (PdfParser, DocxParser, ExcelParser), `rag/res/deepdoc/` (ONNX models, XGBoost model) |
| Dependencies | onnxruntime, opencv-python, pdfplumber, pypdf, xgboost, Pillow, numpy |
| Output | Python package độc lập: `medinet_deepdoc/` |

#### Task 1A-02: Build FastAPI wrapper

Claude Code sẽ viết file `medinet_deepdoc/api.py`:

```
POST /parse
  Input: file (PDF/DOCX) + parse_options (ocr=true, tsr=true)
  Output: {
    "pages": [{
      "page_number": 1,
      "text_blocks": [{
        "text": "...",
        "type": "heading|paragraph|list_item|caption",
        "position": {"x0": 0, "y0": 0, "x1": 100, "y1": 20},
        "confidence": 0.95
      }],
      "tables": [{
        "content_text": "Bảng dạng text tự nhiên",
        "content_markdown": "| Col1 | Col2 |...",
        "rows": [["cell1", "cell2"], ...],
        "position": {...}
      }],
      "figures": [{"caption": "...", "position": {...}}]
    }]
  }
```

#### Task 1A-03: Dockerfile + Docker Compose

Service chạy độc lập, expose port 8090 (internal network). Go backend gọi qua HTTP.

### 1B. Fallback: Không dùng DeepDoc

Nếu không muốn maintain Python service, tham chiếu cách Open Notebook làm:

| Phương pháp | Công cụ | Chất lượng bảng |
|-------------|---------|-----------------|
| Go native PDF | pdfcpu + goldmark | Kém — không nhận diện bảng |
| Python pdfplumber | pdfplumber (pip) | Trung bình — nhận bảng cơ bản |
| RAGFlow API (deploy nguyên bản) | `docker pull infiniflow/ragflow` | Tốt nhất — đầy đủ DeepDoc |

---

## PHASE 2: ENTITY-CENTRIC CHUNKING ENGINE (Tuần 2–4)

**Mục tiêu: Nhận JSON từ Phase 1 → tạo chunks thông minh theo 9 levels + router + header injection, gắn metadata**

### 2A. Tổng hợp 9 Chunk Levels + 2 Bổ sung

| Level | Tên | Loại tài liệu | Kích thước | Nguồn logic |
|-------|-----|---------------|------------|-------------|
| L1 | Entity Profile | Vận hành (operational) | 800–1200 tok | Custom |
| L2 | Channel Rule | Vận hành (operational) | 400–800 tok | Custom |
| L3 | Decision Tree | Vận hành (operational) | 200–400 tok | Custom |
| L4 | Script Template | Vận hành (operational) | 100–300 tok | Custom |
| L5 | Negative Rule | **TẤT CẢ** (always inject) | 300–600 tok | Custom |
| L6 | Matrix Table | Vận hành + Lâm sàng | 400–1000 tok | RAGFlow table template |
| L7 | Article Narrative | Báo chí + Nghiên cứu | 200–600 tok | RAGFlow book + ON splitter |
| L8A | Prescription | Lâm sàng (clinical) | 200–800 tok | RAGFlow laws template |
| L8B | Clinical Data | Lâm sàng (clinical) | 300–1000 tok | RAGFlow table + paper |
| L8C | Treatment Protocol | Lâm sàng (clinical) | 400–1200 tok | RAGFlow laws template |
| L9 | Cross-Reference | **TẤT CẢ** (post-process) | metadata only | RAGFlow GraphRAG |
| + | Contextual Header | **TẤT CẢ** (pre-embed) | +30–60 tok/chunk | RAGFlow Ingestion Pipeline |
| + | Document Router | **TẤT CẢ** (entry point) | N/A | Custom rule-based |

---

### 2B. Chi tiết Level 1–6 (Tài liệu vận hành nội bộ)

#### Level 1: Entity Profile Chunker

```go
// Go: chunker/entity_profile.go

Logic:
1. Nhận parsed JSON từ DeepDoc
2. Tìm pattern: heading chứa tên nhân vật (regex: BS|TTUT|TS|LY|CGYHCT + tên)
3. Gom tất cả text_blocks + tables từ heading đó đến heading nhân vật tiếp theo
4. GIỮ NGUYÊN bảng E-E-A-T và bảng Phân công kênh trong chunk
5. Nếu chunk > 1500 token: KHÔNG cắt — BGE-M3 hỗ trợ 8192 token
6. Gắn metadata:
   entity_name: "BS Lê Phương"
   entity_role: "Trưởng Hội đồng Chuyên môn"
   chunk_type: "entity_profile"
   source_doc: "T3-01"
```

#### Level 2: Channel Rule Chunker

```go
// Go: chunker/channel_rule.go

Logic:
1. Tìm các section bắt đầu bằng icon + tên kênh (TIKTOK, YOUTUBE, WEBSITE, PR, TƯ VẤN)
2. Gom toàn bộ 4 nhân vật trong section đó thành 1 chunk
3. BAO GỒM cả quy tắc ĐƯỢC và KHÔNG ĐƯỢC
4. Gắn metadata:
   channel: "tiktok"
   entities: ["BS Long", "BS Lê Phương", "BS Vân Anh", "LY Tuấn"]
   chunk_type: "channel_rule"
```

#### Level 3: Decision Tree Chunker

```go
// Go: chunker/decision_tree.go

Logic:
1. Tìm pattern: "Nếu:" + "→" + lý do
2. Gom các tình huống cùng nhóm (digital, PR, tư vấn) thành chunk trung bình
3. Metadata:
   chunk_type: "decision_tree"
   situation_category: "content_digital|pr|consulting"
```

#### Level 4: Script Template Chunker

```go
// Go: chunker/script_template.go

Logic:
1. Tìm pattern: mã script (LP, VA, HL, DT) + loại tình huống
2. Mỗi script = 1 chunk, BẮT BUỘC kèm context: dành cho ai, tình huống nào, kênh nào
3. Metadata:
   chunk_type: "script_template"
   target_entity: "BS Lê Phương"
   situation: "KH hỏi BS giỏi nhất"
   channel: "tư vấn"
```

#### Level 5: Negative Rule Aggregator

> **⚠️ ĐÂY LÀ CHUNK QUAN TRỌNG NHẤT — luôn được kéo vào context bất kể query nào liên quan đến nhân vật.**

```go
// Go: chunker/negative_rule.go

Logic:
1. Scan toàn bộ tài liệu, tìm pattern:
   - "✖ TUYỆT ĐỐI"
   - "✖ KHÔNG"
   - "KHÔNG ĐƯỢC"
   - "KHÔNG BAO GIỜ"
   - LỖI: (12 lỗi phổ biến)
2. Gom thành 1–2 chunk với:
   chunk_type: "negative_rule"
   priority: "critical"
   always_include: true  // <-- flag đặc biệt
3. Retrieval engine PHẢI check flag này và luôn append chunk vào context
```

#### Level 6: Matrix Table Chunker

```go
// Go: chunker/matrix_table.go

Logic:
1. DeepDoc đã nhận diện table → check nếu là bảng ma trận (nhiều cột x nhiều dòng)
2. GIỮ NGUYÊN bảng, chuyển sang text có cấu trúc
3. Metadata:
   chunk_type: "matrix_table"
   table_dimensions: "4x7"
   table_title: "Ma trận 4 nhân vật × 7 kênh"
```

---

### 2C. Level 7: Article Narrative Chunk — Báo chí & Bài viết

**Dành cho: Bài PR, bài báo sức khỏe, blog YHCT, bài nghiên cứu học thuật dạng narrative**

#### Vấn đề với báo chí

Bài báo không có entity cố định như tài liệu DMD. Cấu trúc là narrative dài: đoạn mở → case bệnh nhân → trích dẫn bác sĩ → phương pháp → kết luận. Cắt theo kích thước cố định sẽ phá vỡ ngữ nghĩa. Cắt theo heading không hiệu quả vì báo chí ít dùng heading rõ ràng.

#### Chiến lược: Semantic Paragraph Chunking

```go
// Go: chunker/article_narrative.go

Logic:
1. PHÂN LOẠI ĐOẠN: Scan từng paragraph, gán section_type:
   - "intro"          : Đoạn đầu, giới thiệu chủ đề
   - "case_study"     : Chứa pattern: "bệnh nhân", "anh/chị X", "năm tuổi"
   - "expert_quote"   : Chứa dấu ngoặc kép + tên BS/TS/TTUT
   - "method"         : Chứa: "phác đồ", "bài thuốc", "phương pháp", "điều trị"
   - "evidence"       : Chứa: "nghiên cứu", "kết quả", "tỷ lệ", "theo", "cho thấy"
   - "conclusion"     : Đoạn cuối, chứa: "kết luận", "tóm lại", "như vậy"
   - "cta"            : Chứa: "liên hệ", "đặt lịch", "hotline", "địa chỉ"
   - "general"        : Không match pattern nào

2. GOM ĐOẠN THEO NGỮ NGHĨA:
   - Các paragraph liên tiếp cùng section_type → gom thành 1 chunk
   - expert_quote LUÔN đi kèm paragraph trước/sau (context)
   - Nếu chunk > 600 token: dùng RecursiveCharacterTextSplitter (Open Notebook)
     với overlap 15% và giữ nguyên sentence boundary

3. CONTEXTUAL HEADER INJECTION (bắt buộc):
   Mỗi chunk được prepend:
   "[Tài liệu: {doc_title}] [Mục: {section_title_or_inferred}]"
   Ví dụ: "[Tài liệu: Tri thức Chính trị] [Mục: 5. Thách thức trong Kỷ nguyên Số]"

4. METADATA:
   chunk_type:          "article_narrative"
   article_section_type: "intro|case_study|expert_quote|method|evidence|conclusion|cta"
   document_type:        "pr_article|health_blog|research_paper|news"
   quoted_experts:       ["BS Lê Phương"]  // nếu có trích dẫn
   has_contextual_header: true
```

#### Ví dụ cụ thể với bài báo "Tri thức Chính trị"

| Chunk # | Nội dung | section_type | Token |
|---------|----------|--------------|-------|
| 1 | [TL: Tri thức CT] [Tóm tắt] Tri thức chính trị là một trong những nền tảng cốt lõi... | intro | ~180 |
| 2 | [TL: Tri thức CT] [Mục 1: Khái niệm] Tri thức chính trị (political knowledge) được hiểu là... Robert Dahl từng nhận định... | evidence | ~350 |
| 3 | [TL: Tri thức CT] [Mục 2: Thành phần] Thứ nhất là tri thức thực tế... + blockquote "Tri thức CT không phải đặc quyền..." | evidence + expert_quote | ~400 |
| 4 | [TL: Tri thức CT] [Mục 4: Thực trạng VN] Việt Nam là quốc gia có bề dày... tồn tại khoảng cách đáng kể... | evidence | ~380 |
| 5 | [TL: Tri thức CT] [Mục 6: Giải pháp] Cần đổi mới phương pháp... xây dựng văn hóa báo chí... | method | ~350 |
| 6 | [TL: Tri thức CT] [Kết luận + TLTK] Tri thức CT là tài sản vô giá... Dahl (1989)... | conclusion + reference | ~300 |

#### Tham chiếu implementation Level 7

| Logic | Lấy từ | Chi tiết |
|-------|--------|---------|
| Semantic boundary detection | RAGFlow `rag/app/book.py` | Book template dùng layout_type (heading/paragraph) làm ranh giới — áp dụng tương tự cho article section |
| RecursiveCharacterTextSplitter fallback | Open Notebook `chunking.py` | Khi đoạn > 600 token: recursive split với overlap 15%, giữ sentence boundary |
| Content-type detection | Open Notebook `chunking.py` | Detect HTML/Markdown/plain text trước khi chọn splitter |
| Blockquote preservation | RAGFlow deepdoc parser | Nhận diện blockquote (trích dẫn) — giữ nguyên và gắn vào chunk paragraph liền kề |

---

### 2D. Level 8: Clinical Evidence Chunk — Nghiên cứu y học

**Dành cho: Bài nghiên cứu y học, phác đồ điều trị, bài thuốc đông y, báo cáo lâm sàng**

#### Vấn đề cốt lõi

Tài liệu y học chứa 3 loại thông tin KHÔNG ĐƯỢC cắt rời: bảng số liệu lâm sàng (tỷ lệ khỏi, p-value), bài thuốc đầy đủ (tên dược liệu + liều lượng + cách dùng), và phác đồ điều trị (các bước + thời gian + chỉ định). Cắt ngang giữa tên dược liệu và liều lượng là lỗi nghiêm trọng nhất trong RAG y tế.

#### 8A. Prescription Chunk (Bài thuốc)

```go
// Go: chunker/clinical_prescription.go

Logic:
1. Detect bài thuốc bằng pattern:
   - Tên bài thuốc: "Bài thuốc X", "Phương thuốc Y"
   - Danh sách dược liệu: regex "[Tên VN/Hán Việt] + [số]g/ml/thìa"
   - Cách dùng: "sắc uống", "ngày X lần", "trước/sau ăn"
2. GOM toàn bộ thành 1 chunk:
   Tên bài thuốc + Tất cả dược liệu + Liều lượng + Cách dùng + Chỉ định + Chống chỉ định
3. TUYỆT ĐỐI KHÔNG cắt ngang bài thuốc dù vượt max_token
4. Metadata:
   chunk_type:        "clinical_evidence"
   evidence_subtype:  "prescription"
   prescription_name: "Bổ Trung Ích Khí Thang"
   ingredients:       ["Hoàng Kỳ 12g", "Bạch Truật 10g", ...]
   diseases:          ["suy nhược", "mệt mỏi"]
```

#### 8B. Clinical Data Chunk (Bảng số liệu lâm sàng)

```go
// Go: chunker/clinical_data.go

Logic:
1. Detect bảng số liệu bằng pattern:
   - DeepDoc đã nhận diện table → check nội dung có số liệu (%, số ca, p-value)
   - Regex: "tỷ lệ", "hiệu quả", "kết quả", "nhóm đối chứng", "p <"
2. GIỮ NGUYÊN bảng — chuyển sang markdown table format
3. Prepend context: tên nghiên cứu + mục tiêu + phương pháp (lấy từ đoạn trước bảng)
4. Metadata:
   chunk_type:       "clinical_evidence"
   evidence_subtype: "clinical_data"
   study_type:       "observational|rct|case_series|meta_analysis"
   sample_size:      150  // nếu detect được
   efficacy_rate:    "85%"  // nếu detect được
```

#### 8C. Treatment Protocol Chunk (Phác đồ điều trị)

```go
// Go: chunker/clinical_protocol.go

Logic:
1. Detect phác đồ bằng pattern:
   - "Phác đồ", "Quy trình điều trị", "Bước 1... Bước 2..."
   - "Giai đoạn 1", "Tuần 1–4", "Ngày 1–14"
2. GOM toàn bộ các bước + thời gian + chỉ định thành 1 chunk
3. Liên kết với prescription chunks liên quan qua metadata:
   related_prescriptions: ["chunk_id_bai_thuoc_X"]
4. Metadata:
   chunk_type:       "clinical_evidence"
   evidence_subtype: "treatment_protocol"
   protocol_name:    "Điều trị thoái hóa cột sống YHCT"
   duration:         "8 tuần"
   diseases:         ["thoái hóa cột sống"]
```

#### Tham chiếu implementation Level 8

| Logic | Lấy từ | Chi tiết |
|-------|--------|---------|
| Table preservation + chuyển sang text | RAGFlow `deepdoc/parser/pdf_parser.py` | Bảng số liệu được giữ nguyên và chuyển thành câu tự nhiên (như Level 6) |
| Template Laws — giữ nguyên đơn vị logic | RAGFlow `rag/app/laws.py` | Cách laws.py giữ điều/khoản = cách 8A giữ bài thuốc/liều lượng: không bao giờ cắt ngang |
| Template Paper — cấu trúc IMRaD | RAGFlow `rag/app/paper.py` | Nhận diện Abstract/Methods/Results/Discussion làm ranh giới chunk |
| Mean pooling cho long content | Open Notebook `embedding.py` | Nếu bảng số liệu quá lớn: chunk → embed từng phần → mean pool |

---

### 2E. Level 9: Cross-Reference Chunk — Liên kết chéo

**Dành cho: Liên kết giữa các tài liệu — bài báo trích dẫn BS, nghiên cứu đề cập bài thuốc, SOP tham chiếu phác đồ**

#### Vấn đề

Khi bài PR trích dẫn BS Lê Phương, AI cần biết thêm về BS Lê Phương (từ T3-01) để trả lời chính xác. Khi nghiên cứu đề cập bài thuốc Bổ Trung Ích Khí Thang, AI cần kéo được chunk prescription của bài thuốc đó. Hiện tại các chunk là độc lập — không có liên kết chéo.

#### Chiến lược: Reference Graph Metadata

```go
// Go: chunker/cross_reference.go

Logic (chạy SAU tất cả Level 1–8):

1. SCAN tất cả chunks đã tạo, tìm entity mentions:
   - Chunk L7 (article) chứa "BS Lê Phương" → link đến chunk L1 (entity profile BS LP)
   - Chunk L8 (protocol) chứa "Bài thuốc X" → link đến chunk L8A (prescription X)
   - Chunk L7 (article) dẫn nguồn "T3-01" → link đến document T3-01

2. GẮN metadata liên kết:
   referenced_chunks:    ["chunk_id_L1_BS_LP", "chunk_id_L8A_bai_thuoc"]
   referenced_documents: ["T3-01", "T3-02"]
   referenced_entities:  ["BS Lê Phương"]
   reference_direction:  "outgoing"  // chunk này tham chiếu đến chunk khác

3. TẠO chunk liên kết ngược:
   Chunk L1 (BS Lê Phương) được update:
   referenced_by: ["chunk_id_L7_bai_PR_ve_BS_LP"]
   reference_direction: "incoming"  // có chunk khác tham chiếu đến chunk này

4. RETRIEVAL enhancement:
   Khi retrieve chunk L7 (bài PR có BS LP):
   → Tự động kéo thêm chunk L1 (entity profile BS LP) vào context
   → Tự động kéo thêm chunk L5 (negative rules) vào context
   → AI có đủ thông tin để trả lời chính xác
```

#### Ví dụ: Retrieval với cross-reference

| Query | Chunks được retrieve | Cross-reference bổ sung | Kết quả |
|-------|---------------------|------------------------|---------|
| Bài PR về BS Lê Phương nên viết gì? | L7 (article PR về BS LP) | +L1 (profile BS LP) +L5 (negative rules) +L2 (PR channel rule) | AI biết: profile + được/không được + tone PR |
| Nghiên cứu nào dùng bài thuốc Bổ Trung Ích Khí? | L8A (prescription) | +L8B (clinical data) +L8C (protocol liên quan) | AI biết: thành phần + liều + kết quả lâm sàng |
| SOP khám YHCT tham chiếu phác đồ nào? | L7 (SOP article) | +L8C (protocol) +L8A (prescriptions trong protocol) | AI biết: quy trình + phác đồ cụ thể |

#### Bước tiến đến GraphRAG (Phase 3+)

Level 9 là bước đệm cho GraphRAG đầy đủ. Khi số lượng liên kết chéo tăng (>1000 chunks), chuyển sang Knowledge Graph:

```
Tham chiếu: RAGFlow GraphRAG (rag/app/ + knowledge graph construction)

Entity nodes:  BS Lê Phương, Bài thuốc X, Bệnh Y, Kênh Z
Relationships: BS_LP --[điều_trị]--> Bệnh_xương_khớp
               Bài_thuốc_X --[chỉ_định]--> Bệnh_thoái_hóa
               BS_LP --[KHÔNG_xuất_hiện]--> TikTok
               BS_Long --[NHÂN_VẬT_CHÍNH]--> TikTok
```

---

### 2F. Bổ sung: Contextual Header Injection

**Bổ sung vào TOÀN BỘ Level 1–9 — không chỉ Level 7**

#### Vấn đề

Khi 1 chunk được retrieve độc lập, AI không biết chunk đó thuộc tài liệu nào, mục nào. Ví dụ: chunk chứa "Không được quay TikTok" — AI không biết quy tắc này áp dụng cho ai nếu không có header context.

#### Giải pháp

```go
// Go: chunker/header_injector.go
// Chạy SAU khi tạo chunk, TRƯỚC khi embed

func InjectContextualHeader(chunk Chunk, doc Document) Chunk {
  header := fmt.Sprintf("[Tài liệu: %s] [Mã: %s] [Hub: %s]",
    doc.Title, doc.DocumentID, doc.HubID)

  // Thêm section context nếu có
  if chunk.SectionTitle != "" {
    header += fmt.Sprintf(" [Mục: %s]", chunk.SectionTitle)
  }

  // Thêm entity context nếu có
  if len(chunk.Entities) > 0 {
    header += fmt.Sprintf(" [Nhân vật: %s]", strings.Join(chunk.Entities, ", "))
  }

  chunk.Content = header + "\n" + chunk.Content
  chunk.HasContextualHeader = true
  return chunk
}
```

#### Ví dụ kết quả

| Level | Chunk TRƯỚC inject | Chunk SAU inject |
|-------|-------------------|-----------------|
| L1 | TTƯT BSCKII Lê Phương — Trưởng HĐCM... | [TL: Hồ sơ BS E-E-A-T] [Mã: T3-01] [Hub: dmd] [NV: BS Lê Phương] TTƯT BSCKII Lê Phương... |
| L5 | TUYỆT ĐỐI không dùng từ truyền nhân... | [TL: Phân công NV] [Mã: T3-02] [Hub: dmd] [QUY TẮC CẤM] TUYỆT ĐỐI không... |
| L7 | Tri thức chính trị là một trong... | [TL: Tri thức Chính trị] [Mục: 1. Khái niệm] Tri thức chính trị là... |
| L8A | Bài thuốc Bổ Trung Ích Khí... | [TL: Phác đồ YHCT] [Mã: YH-03] [Hub: tamdao] [Bài thuốc] Bổ Trung Ích Khí... |

Tham chiếu: RAGFlow Ingestion Pipeline detect heading hierarchy và append parent heading vào mỗi chunk con. Open Notebook không có tính năng này.

---

### 2G. Bổ sung: Document Type Router

**Bổ sung vào đầu Phase 2 — tự động chọn chunking strategy theo loại tài liệu**

#### Vấn đề

Với 9 chunk levels, cần 1 router tự động phân loại tài liệu và chọn levels phù hợp. Không thể chạy cả 9 levels cho mọi file.

#### Implementation

```go
// Go: chunker/document_router.go

type DocumentType string
const (
  DocTypeOperational   DocumentType = "operational"    // T3-01, T3-02, SOP
  DocTypeArticle       DocumentType = "article"        // PR, blog, báo chí
  DocTypeClinical      DocumentType = "clinical"       // Nghiên cứu, phác đồ, bài thuốc
  DocTypeResearch      DocumentType = "research"       // Bài báo học thuật (dạng "Tri thức CT")
  DocTypeGeneral       DocumentType = "general"        // Không xác định
)

func DetectDocumentType(parsed ParsedDocument) DocumentType {
  // Rule-based detection:
  // 1. Chứa entity patterns (BS/TTUT/BSCKII + tên) + bảng phân công kênh
  //    → DocTypeOperational
  // 2. Có cấu trúc IMRaD (Tóm tắt/Mục lục/TLTK) + không có bài thuốc
  //    → DocTypeResearch
  // 3. Có bài thuốc/liều lượng/phác đồ điều trị
  //    → DocTypeClinical
  // 4. Có trích dẫn nguồn báo + CTA + case bệnh nhân
  //    → DocTypeArticle
  // 5. Không match → DocTypeGeneral
}
```

#### Routing Table

| DocumentType | Levels sử dụng | Ví dụ tài liệu |
|-------------|----------------|-----------------|
| operational | L1 + L2 + L3 + L4 + L5 + L6 + L9 | T3-01 Hồ sơ BS, T3-02 Phân công NV, SOP |
| article | L7 + L9 + (L5 nếu có entity DMD) | Bài PR về BS Lê Phương, Blog YHCT, Báo sức khỏe |
| clinical | L8A + L8B + L8C + L9 + (L5 nếu có entity) | Phác đồ điều trị, Danh mục bài thuốc, Báo cáo lâm sàng |
| research | L7 (section-based) + L9 | Bài "Tri thức Chính trị", nghiên cứu xã hội |
| general | L7 (fallback RecursiveCharacterTextSplitter) | Tài liệu không có cấu trúc rõ ràng |

> **Lưu ý:** L5 (negative rules) và L9 (cross-reference) luôn chạy bất kể document type nào. L5 được inject vào retrieval context. L9 chạy sau cùng để liên kết chéo giữa các tài liệu.

---

### 2H. Tham chiếu implementation từ 2 repo

| Logic cần dùng | Lấy từ | File gốc | Cách áp dụng |
|---------------|--------|----------|--------------|
| RecursiveCharacterTextSplitter | Open Notebook | `open_notebook/utils/chunking.py` | Fallback khi chunk Level 1–8 vượt max_token: recursive split với overlap 10–20% |
| HTML/Markdown content detection | Open Notebook | `open_notebook/utils/chunking.py` | Detect content type trước khi chọn splitter phù hợp |
| Table preservation | RAGFlow | `deepdoc/parser/pdf_parser.py` | Bảng được giữ nguyên, chuyển sang text có cấu trúc |
| Layout-aware splitting | RAGFlow | `rag/app/book.py`, `rag/app/laws.py` | Dùng layout type (heading/paragraph/table) làm ranh giới chunk |
| Mean pooling for long content | Open Notebook | `open_notebook/utils/embedding.py` | Khi content vượt embedding window: chunk → embed từng phần → mean pool |
| Knowledge Graph chunks | RAGFlow | `rag/app/` (GraphRAG) | Phase 3: tạo entity-relationship chunks cho dược liệu – bệnh lý |

---

## PHASE 3: METADATA ENRICHMENT (Tuần 3–4)

**Mục tiêu: Mỗi chunk được gắn metadata đầy đủ để retrieval chính xác hơn**

### 3A. Schema metadata cho mỗi chunk

```go
// Go struct: models/chunk_metadata.go

type ChunkMetadata struct {
  DocumentID      string   `json:"document_id"`      // T3-01, T3-02
  DocumentTitle   string   `json:"document_title"`   // Hồ sơ Bác sĩ E-E-A-T
  ChunkType       string   `json:"chunk_type"`       // 9 levels + subtypes
  Entities        []string `json:"entities"`         // ["BS Lê Phương"]
  EntityAliases   []string `json:"entity_aliases"`   // ["TTUT BSCKII", "Thầy thuốc Ưu tú"]
  Channels        []string `json:"channels"`         // ["tiktok", "youtube"]
  Diseases        []string `json:"diseases"`         // ["xương khớp", "tiêu hóa"]
  RuleType        string   `json:"rule_type"`        // positive | negative
  Priority        string   `json:"priority"`         // critical | high | medium
  AlwaysInclude   bool     `json:"always_include"`   // true cho negative rules
  HubID           string   `json:"hub_id"`           // dmd, tamdao, hcns
  ArticleSectionType string `json:"article_section_type"` // intro|case_study|expert_quote|...
  EvidenceSubtype string   `json:"evidence_subtype"` // prescription|clinical_data|treatment_protocol
  ReferencedChunks []string `json:"referenced_chunks"` // cross-reference links
  HasContextualHeader bool `json:"has_contextual_header"`
}
```

### 3B. Entity Recognition cho tiếng Việt

Không cần NER model phức tạp. Tài liệu DMD có tên nhân vật rõ ràng — dùng rule-based extraction:

```go
// Go: enricher/entity_extractor.go

var entityPatterns = map[string][]string{
  "BS Lê Phương":     {"TTUT", "BSCKII Lê Phương", "Thầy thuốc Ưu tú"},
  "BS Vân Anh":       {"TS Y học", "Nguyễn Thị Vân Anh", "GĐ CM"},
  "BS Hải Long":      {"Trần Hải Long", "BS Long"},
  "LY Đỗ Minh Tuấn": {"CGYHCT", "Người sáng lập", "Đỗ Minh Tuấn"},
}

var channelPatterns = []string{"TikTok", "YouTube", "Facebook", "Website", "PR", "Tư vấn", "Reels"}
var diseasePatterns = []string{"xương khớp", "tiêu hóa", "phụ khoa", "da liễu", "hô hấp", "suy nhược"}
```

---

## PHASE 4: EMBEDDING + VECTOR STORAGE (Tuần 4–5)

### 4A. Embedding Service

| Hạng mục | Lựa chọn | Lý do |
|----------|---------|-------|
| Model chính | BGE-M3 (BAAI/bge-m3) | Hỗ trợ 100+ ngôn ngữ, hybrid dense+sparse, 8192 token context |
| Deployment | Python service (sentence-transformers) | GPU nếu có, CPU fallback với ONNX quantized |
| Fallback (Phase 2+) | Qwen3-Embedding-0.6B | Benchmark MMTEB cao hơn BGE-M3 7.9%, test trên dữ liệu y tế |
| Reranker | ViRanker (HuggingFace) | Xây trên BGE-M3, chuyên cho tiếng Việt, NDCG@3 = 0.6815 |

### 4B. Embedding API Design

```
POST /embed
  Input: {"texts": ["chunk1", "chunk2", ...], "mode": "dense+sparse"}
  Output: {
    "embeddings": [{
      "dense": [0.1, 0.2, ...],     // 1024-dim vector
      "sparse": {"token_id": weight}, // BM25-like weights
      "colbert": [[...], [...]]       // multi-vector (optional Phase 2)
    }]
  }

POST /rerank
  Input: {"query": "...", "passages": ["chunk1", "chunk2", ...], "top_k": 5}
  Output: {"ranked": [{"index": 2, "score": 0.95}, ...]}
```

### 4C. Tham chiếu từ 2 repo

| Logic | Nguồn | Cách dùng |
|-------|-------|-----------|
| `generate_embedding()` với mean pooling | Open Notebook (`embedding.py`) | Khi 1 chunk vượt 8192 token (hiếm với entity-centric chunking): chia nhỏ, embed từng phần, lấy mean vector |
| Hybrid dense+sparse embedding | RAGFlow (BGE-M3 integration) | Gọi BGE-M3 với mode=dense+sparse, lưu cả 2 loại vector vào DB |
| Async embed queue | Cả 2 repo dùng Redis queue | Tạo/sửa wiki page → push Redis job → worker embed async → không block API |

---

## PHASE 5: HYBRID RETRIEVAL ENGINE (Tuần 5–6)

### 5A. Retrieval Pipeline

Tham chiếu: RAGFlow `rag/` (hybrid retrieval + fused re-ranking)

```go
// Go: retrieval/engine.go

func Search(query string, hubID string, topK int) []RankedChunk {
  // Bước 1: Embed query bằng BGE-M3 (dense + sparse)
  queryEmb := embeddingService.Embed(query, "dense+sparse")

  // Bước 2: Song song 2 đường retrieval (goroutine)
  denseResults  := vectorDB.SearchDense(queryEmb.Dense, hubID, topK*3)
  sparseResults := vectorDB.SearchSparse(queryEmb.Sparse, hubID, topK*3)

  // Bước 3: Fused scoring (dense 60% + sparse 40%)
  fused := fuseResults(denseResults, sparseResults, 0.6, 0.4)

  // Bước 4: ALWAYS inject negative_rule chunks
  negRules := vectorDB.GetByFlag("always_include", hubID)
  fused = append(negRules, fused...)

  // Bước 5: Cross-reference expansion
  expanded := expandCrossReferences(fused, topK)

  // Bước 6: Rerank bằng ViRanker
  reranked := rerankerService.Rerank(query, expanded, topK)

  return reranked
}
```

### 5B. Metadata-Boosted Scoring

Tham chiếu từ PRD Medinet Wiki (ALG-001): kết hợp vector similarity với metadata matching.

```
FinalScore = VectorScore * 0.6
           + MetadataBoost * 0.2  // entity/channel/disease match
           + Recency * 0.1
           + VerifiedBonus * 0.1  // chunk đã được review
```

### 5C. Query ví dụ với tài liệu DMD + báo chí + lâm sàng

| Câu hỏi | Chunks được retrieve | Tại sao chính xác |
|---------|---------------------|-------------------|
| Ai quay TikTok về xương khớp? | L2 (TikTok channel rule) + L5 (negative rules) + L3 (decision tree TikTok) | Metadata match: channel=tiktok + disease=xương khớp. Negative rule luôn kèm |
| BS Vân Anh là ai? | L1 (Entity profile BS Vân Anh) + L5 (negative rules) | Entity match. Đầy đủ học vị + kinh nghiệm + triết lý + E-E-A-T |
| Tóm tắt bài "Tri thức Chính trị"? | L7 chunks (6 section chunks) | Document type = research → L7 section-based chunking. Mỗi section = 1 chunk |
| Echo chamber là gì theo bài nghiên cứu? | L7 chunk (Mục 5: Thách thức) | Contextual header giúp AI biết chunk thuộc mục nào |
| Bài thuốc Bổ Trung Ích Khí gồm gì? | L8A (prescription) + cross-ref L8C (protocol) | Prescription chunk giữ nguyên toàn bộ bài thuốc + liều lượng |
| Bài PR nào đề cập BS Lê Phương? | L9 cross-reference → L7 (articles) + L1 (profile) | Cross-reference metadata: referenced_entities = BS Lê Phương |

---

## PHASE 6: INTEGRATION VỚI MEDINET WIKI (Tuần 6–8)

### 6A. Kết nối Go Backend → RAG Pipeline

```go
// Go: services/rag_service.go

// Khi Editor tạo/sửa wiki page:
func OnPageCreated(page WikiPage) {
  // 1. Push job vào Redis queue
  redis.Push("embed_queue", EmbedJob{
    PageID: page.ID,
    HubID:  page.HubID,
    Action: "create",
  })
}

// Worker xử lý async:
func EmbedWorker() {
  for job := range redis.Subscribe("embed_queue") {
    // 1. Lấy content page từ PostgreSQL
    // 2. Gọi DeepDoc parse (nếu có file đính kèm)
    // 3. Document Router → chọn chunk levels phù hợp
    // 4. Chạy chunking theo levels đã chọn
    // 5. Enrich metadata + Inject contextual header
    // 6. Cross-reference scan (Level 9)
    // 7. Gọi BGE-M3 embed (dense + sparse)
    // 8. Lưu vào ChromaDB (collection per Hub)
  }
}
```

### 6B. MCP Tool: wiki_search tích hợp RAG

```go
// Go: mcp/tools/wiki_search.go

// Claude/ChatGPT gọi: wiki_search(query="ai quay TikTok", hub_id="dmd")
func WikiSearch(query string, hubID string, topK int) MCPResponse {
  // 1. Gọi retrieval engine (Phase 5)
  chunks := retrievalEngine.Search(query, hubID, topK)
  // 2. Format kết quả với citations
  return MCPResponse{
    Results: formatWithCitations(chunks),
    Sources: extractSources(chunks),
  }
}
```

---

## PHASE 7: TỐI ƯU CHO TIẾNG VIỆT (Tuần 8–10)

### 7A. Vietnamese-specific optimizations

| Vấn đề | Giải pháp | Nguồn tham chiếu |
|--------|----------|-------------------|
| Tên thuốc đông y (Hoàng Kỳ, Bạch Truật) cần exact match | Sparse retrieval weight 40% (thay vì 30% mặc định) | RAGFlow hybrid retrieval config |
| Thuật ngữ y học (Tứ chẩn, Biện chứng luận trị) | Thêm vào keyword dict của sparse index | RAGFlow: custom BM25 vocab |
| Tên riêng có dấu (Lê Phương, Vân Anh) | Normalize dấu + giữ original: tìm cả 2 | Custom: Go unicode normalizer |
| Viết tắt y khoa (TTUT, BSCKII, YHCT) | Expand viết tắt trong query preprocessing | Custom: Go abbreviation dict |
| Reranking tiếng Việt | ViRanker (BGE-M3 fine-tuned cho Việt) | ViRanker paper (arXiv:2509.09131) |
| Thuật ngữ chính trị/xã hội | Thêm vào domain dict: "pháp quyền", "thể chế", "chủ quyền" | Custom domain vocabulary |
| Tên dược liệu Hán Việt | Mapping Hán Việt ↔ tên thường: Hoàng Kỳ = Astragalus | Custom: bilingual herb dict |

### 7B. Evaluation & Tuần hoàn

Tạo test set 20 câu hỏi / Hub (theo PRD RG-09) — BAO GỒM câu hỏi cho cả 3 loại tài liệu:

| Loại | Câu hỏi test | Kết quả mong đợi | Đánh giá |
|------|-------------|-------------------|----------|
| Operational | BS Vân Anh có được quay TikTok không? | KHÔNG — TUYỆT ĐỐI không | Pass nếu có negative rule |
| Operational | KH 55 tuổi thoái hóa khớp, gặp BS nào? | BS Lê Phương + script giới thiệu | Pass nếu đúng NV + script |
| Operational | Câu giới thiệu LY Đỗ Minh Tuấn? | Người sáng lập, 20+ năm | Pass nếu KHÔNG có gia truyền |
| Article | Tóm tắt bài "Tri thức Chính trị"? | 5 ý chính: khái niệm, thành phần, vai trò, thách thức, giải pháp | Pass nếu cover ≥4 ý |
| Article | Robert Dahl nói gì về dân chủ? | Công dân cần tri thức để thực hành quyền bỏ phiếu có trách nhiệm | Pass nếu trích đúng ý |
| Article | Echo chamber là gì theo bài này? | Thuật toán chỉ hiển thị nội dung phù hợp quan điểm sẵn có | Pass nếu đúng định nghĩa |
| Clinical | Bài thuốc Bổ Trung Ích Khí gồm những gì? | Danh sách đầy đủ dược liệu + liều lượng | Pass nếu đủ thành phần + liều |
| Clinical | Phác đồ thoái hóa cột sống YHCT? | Các bước + thời gian + bài thuốc | Pass nếu đủ protocol |
| Cross-ref | Bài PR nào đề cập BS Lê Phương? | Danh sách bài + link | Pass nếu có cross-ref |

---

## TỔNG HỢP TIMELINE & CHECKLIST CHO CLAUDE CODE (CẬP NHẬT)

| Tuần | Phase | Output cụ thể | Để Claude Code làm được |
|------|-------|---------------|------------------------|
| 1–2 | Phase 1: Document Parsing | `deepdoc_service/` (Python FastAPI + Docker) | Copy DeepDoc từ RAGFlow, bọc FastAPI wrapper, viết Dockerfile |
| 2–4 | Phase 2: Chunking Engine | `chunker/` (Go package, 12 files: L1–L9 + router + header_injector) | Viết Go code cho 9 level chunker + `document_router.go` + `header_injector.go` |
| 2–4 | ↳ L1–L6 (Operational) | 6 chunker files cho tài liệu vận hành | `entity_profile`, `channel_rule`, `decision_tree`, `script`, `negative_rule`, `matrix_table` |
| 2–4 | ↳ L7 (Article) | `article_narrative.go` | Semantic paragraph chunking + section_type detection |
| 2–4 | ↳ L8A/B/C (Clinical) | 3 files: `prescription`, `clinical_data`, `protocol` | Pattern detection cho bài thuốc, bảng số liệu, phác đồ |
| 2–4 | ↳ L9 (Cross-ref) | `cross_reference.go` | Scan entity mentions, gắn `referenced_chunks` metadata |
| 2–4 | ↳ Router + Header | `document_router.go` + `header_injector.go` | Auto-detect doc type, inject contextual header vào mọi chunk |
| 3–4 | Phase 3: Metadata Enrichment | `enricher/` (Go package) | Entity extractor, channel/disease tagger, `article_section_type` classifier |
| 4–5 | Phase 4: Embedding | `embedding_service/` (Python + BGE-M3 + ViRanker) | Setup sentence-transformers, `/embed` (dense+sparse) + `/rerank` |
| 5–6 | Phase 5: Retrieval Engine | `retrieval/` (Go package) | Hybrid search + negative rule injection + cross-ref expansion |
| 6–8 | Phase 6: Integration | `services/rag_service.go` + `mcp/tools/` | Redis queue, MCP tools, kết nối Go backend |
| 8–10 | Phase 7: Việt optimization | `config/` + `test/` | Keyword dict (thuốc, chính trị, Hán Việt), test set 20 câu × 3 loại |

---

> **GHI CHÚ QUAN TRỌNG:** Mỗi Phase đều có đầy đủ thông tin để Claude Code có thể implement độc lập. Cung cấp file này như là `CLAUDE.md` hoặc prompt context cho mỗi coding session. Claude Code sẽ biết cần viết gì, ở đâu, và tham chiếu logic từ repo nào.
