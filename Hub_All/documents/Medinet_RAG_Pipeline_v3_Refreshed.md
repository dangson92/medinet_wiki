# MEDINET WIKI — RAG PIPELINE v3.0 (REFRESHED)

**Quy trình chunking tài liệu — bản làm mới tháng 4/2026**

Late Chunking · Contextual Retrieval · Hierarchical Parent-Child · Entity-Centric 9 Levels · Hybrid Retrieval

Tham chiếu mới: Jina AI Late Chunking (2024) · Anthropic Contextual Retrieval (9/2024) · Microsoft GraphRAG GA (2025) · RAGFlow DeepDoc · Open Notebook

> **Quan hệ với v2.0:** Bản này KHÔNG thay thế hoàn toàn 9 levels của v2 — nó **bổ sung 5 kỹ thuật chunking thế hệ mới** lên trên kiến trúc 9 levels và làm mới Phase 1/4/5 cho phù hợp. Đọc kèm `Medinet_RAG_Pipeline_v2_Full_9Levels.md` để hiểu nền tảng.

---

## PHẦN 1: NHỮNG GÌ ĐÃ THAY ĐỔI SO VỚI v2.0

### 1.1 Tổng kết các thay đổi chính

| Hạng mục | v2.0 (7/2025) | v3.0 (4/2026) | Lý do refresh |
|---------|---------------|---------------|----------------|
| Phase 1: Parsing | DeepDoc ONNX (RAGFlow) | DeepDoc + **VLM Fallback** (Qwen2-VL / Claude Sonnet vision) | VLM hiểu layout phức tạp + bảng tiếng Việt tốt hơn ONNX cũ |
| Phase 2: Chunking | 9 levels flat | **9 levels + 5 kỹ thuật mới** (Late, Contextual, Hierarchical, Proposition, Agentic) | Best practices 2024–2025 đã trưởng thành |
| Phase 3: Metadata | Rule-based extractor | Rule-based + **LLM-assisted entity extraction** với cache | Bắt được entity ngầm và alias mới |
| Phase 4: Embedding | BGE-M3 dense+sparse | BGE-M3 (chính) + **Jina v3 / Qwen3-Embedding** (A/B) | Có model mới mạnh hơn cho tiếng Việt |
| Phase 5: Retrieval | Hybrid 60/40 + ViRanker | Hybrid + **Parent expansion** + **Contextual rerank** + ViRanker | Giảm retrieval failure ~50% (theo Anthropic) |
| Phase 6: Integration | Redis queue + MCP | Như v2 + **Eval loop tự động** | Đo chất lượng theo thời gian, không chỉ test thủ công |
| Phase 9 (mới) | — | **GraphRAG đầy đủ** | L9 cross-ref đã đủ trưởng thành để lên KG |

### 1.2 Triết lý mới

> **Chunking không còn là "cắt văn bản" — chunking là "đóng gói ngữ cảnh".** Mỗi chunk khi rời khỏi tài liệu gốc phải tự đứng được trong context window của LLM mà không mất nghĩa.

Ba nguyên tắc bất biến (giữ nguyên từ v2):
1. **Không cắt ngang đơn vị nghĩa** — bài thuốc, bảng E-E-A-T, profile nhân vật, prescription
2. **Negative rules luôn được inject** — bất kể query nào liên quan entity DMD
3. **Mỗi chunk phải tự giải thích được nguồn gốc** — header context bắt buộc

Ba nguyên tắc mới (v3):
4. **Embed trước, cắt sau khi hợp lý** — Late Chunking cho tài liệu < 8K tokens
5. **LLM viết context cho chunk** — Contextual Retrieval cho article + research
6. **Retrieve nhỏ, generate to** — Hierarchical chunking với parent-child

---

## PHẦN 2: 5 KỸ THUẬT CHUNKING MỚI (BỔ SUNG VÀO PHASE 2)

### 2.1 Kỹ thuật #1 — Late Chunking (Jina AI)

**Khi nào dùng:** Tài liệu vận hành ngắn < 8000 tokens (T3-01, T3-02, SOP). Cũng dùng cho bài báo trung bình.

**Vấn đề giải quyết:** Chunking truyền thống cắt văn bản TRƯỚC khi embed → mỗi chunk mất ngữ cảnh của các câu xung quanh. Câu "Anh ấy là người sáng lập" không biết "anh ấy" là ai nếu cắt khỏi đoạn trước.

**Cách hoạt động:**
```
Truyền thống:  Text → Cắt chunks → Embed từng chunk → Lưu
Late Chunking: Text → Embed cả document (BGE-M3 8192 tok) → Cắt token-level embeddings → Mean pool theo chunk boundary → Lưu
```

**Implementation:**
```go
// Go: chunker/late_chunking.go

func LateChunk(doc Document, chunkBoundaries []Boundary) []Chunk {
  // 1. Gọi embedding service với mode="token_embeddings"
  //    BGE-M3 trả về 1 vector / token thay vì 1 vector / chunk
  tokenEmbeds := embeddingService.EmbedTokens(doc.FullText)
  // tokenEmbeds: [[1024-dim], [1024-dim], ...] — 1 vector / token

  // 2. Với mỗi chunk boundary (từ 9 levels chunking), mean pool
  //    các token embeddings nằm trong boundary đó
  chunks := []Chunk{}
  for _, b := range chunkBoundaries {
    chunkEmb := meanPool(tokenEmbeds[b.Start:b.End])
    chunks = append(chunks, Chunk{
      Content:    doc.FullText[b.Start:b.End],
      Embedding:  chunkEmb,
      Metadata:   b.Metadata,
      Method:     "late_chunking",
    })
  }
  return chunks
}
```

**Yêu cầu cho Embedding Service (Phase 4):**
```
POST /embed_tokens
  Input:  {"text": "...", "return": "token_embeddings"}
  Output: {
    "tokens": ["BS", "Lê", "Phương", ...],
    "embeddings": [[1024 floats], [1024 floats], ...],
    "offsets": [[0, 2], [3, 5], [6, 13], ...]   // char offset map
  }
```

**Tham chiếu:** Jina AI blog "Late Chunking in Long-Context Embedding Models" (2024). BGE-M3 hỗ trợ token-level output qua sentence-transformers `output_value="token_embeddings"`.

**Áp dụng vào 9 levels:**
- L1 (Entity Profile), L2 (Channel Rule), L6 (Matrix Table) → BẮT BUỘC dùng Late Chunking
- L3, L4 (Decision Tree, Script) → Tùy chọn (chunks đã ngắn, lợi ích nhỏ)
- L7 (Article), L8 (Clinical) → Dùng nếu doc < 8K, fallback sang Contextual Retrieval nếu dài hơn

---

### 2.2 Kỹ thuật #2 — Contextual Retrieval (Anthropic)

**Khi nào dùng:** Tài liệu DÀI > 8000 tokens (research papers, phác đồ điều trị nhiều trang, sách YHCT). Đặc biệt tốt cho L7 (article) và L8 (clinical).

**Vấn đề giải quyết:** Header injection tĩnh trong v2 chỉ thêm `[Tài liệu: X] [Mục: Y]` — không đủ ngữ cảnh khi câu hỏi cần thông tin từ các phần khác của tài liệu.

**Cách hoạt động:**
```
1. Cắt tài liệu thành chunks (theo 9 levels)
2. Với MỖI chunk: gọi LLM (Claude Haiku) với prompt:
   "<document>{full_doc}</document>
    <chunk>{chunk}</chunk>
    Cho 50–100 token ngữ cảnh ngắn để định vị chunk này trong tài liệu."
3. Prepend ngữ cảnh sinh ra vào chunk
4. Embed chunk đã có context
```

**Implementation:**
```go
// Go: chunker/contextual_retrieval.go

const CONTEXT_PROMPT = `<document>
%s
</document>

Đây là chunk cần định vị trong tài liệu trên:
<chunk>
%s
</chunk>

Hãy viết 50-100 token ngữ cảnh ngắn để định vị chunk này trong tài liệu tổng thể, giúp cải thiện retrieval. Chỉ trả lời ngữ cảnh, không giải thích thêm. Trả lời bằng tiếng Việt.`

func AddContextualHeader(doc Document, chunks []Chunk) []Chunk {
  // PROMPT CACHING là CHÌA KHÓA giảm chi phí 90%
  // Cache cả document trong system prompt
  for i, chunk := range chunks {
    ctx := llmService.Generate(LLMRequest{
      Model:        "claude-haiku-4-5",
      SystemPrompt: fmt.Sprintf(CONTEXT_PROMPT, doc.FullText, ""),
      CacheControl: "ephemeral",  // cache full doc
      UserPrompt:   chunk.Content,
      MaxTokens:    150,
    })
    chunks[i].Content = ctx + "\n\n" + chunk.Content
    chunks[i].ContextualHeader = ctx
    chunks[i].Method = "contextual_retrieval"
  }
  return chunks
}
```

**Chi phí (theo Anthropic):**
- Prompt caching: $1.02 / 1M document tokens (one-time per chunking pass)
- Giảm retrieval failure 35% (chỉ Contextual) → 49% (Contextual + Reranker)

**Áp dụng vào 9 levels:**
- L7 (Article Narrative) → Mọi research paper > 5 chunks
- L8C (Treatment Protocol) → Phác đồ dài có nhiều giai đoạn
- L1 → Dùng cho doc T3-01 (vì có 4 nhân vật × nhiều bảng → cần định vị)

**Tham chiếu:** Anthropic blog "Introducing Contextual Retrieval" (9/2024).

---

### 2.3 Kỹ thuật #3 — Hierarchical Parent-Child Chunking

**Khi nào dùng:** L7 (Article), L8B (Clinical Data), L1 (Entity Profile dài).

**Vấn đề giải quyết:** Chunk to (1000+ tokens) tốt cho generation nhưng kém cho retrieval (vector "loãng"). Chunk nhỏ (200 tokens) tốt cho retrieval nhưng thiếu ngữ cảnh khi gen.

**Cách hoạt động:**
```
Mỗi tài liệu được chunk hai tầng:
- PARENT chunks: 800–1500 tokens (đơn vị nghĩa hoàn chỉnh — bài thuốc, profile)
- CHILD chunks:  150–300 tokens (câu hoặc 2–3 câu liền kề)

Mỗi child chunk có metadata: parent_id

Retrieval:
1. Tìm top-K theo CHILD vectors (precise)
2. Lấy PARENT của các child match (full context)
3. Dedup parent → trả về cho LLM gen
```

**Implementation:**
```go
// Go: chunker/hierarchical.go

type ParentChunk struct {
  ID       string
  Content  string  // 800–1500 tok
  Metadata ChunkMetadata
}

type ChildChunk struct {
  ID       string
  ParentID string
  Content  string  // 150–300 tok
  Embedding []float32
}

func HierarchicalChunk(doc Document) ([]ParentChunk, []ChildChunk) {
  // 1. Tạo parent chunks bằng 9 levels (L1, L7, L8...)
  parents := nineLevelsChunker.Chunk(doc)

  // 2. Mỗi parent → tách thành children theo câu
  var children []ChildChunk
  for _, p := range parents {
    sentences := sentenceSplitter.Split(p.Content)
    for i := 0; i < len(sentences); i += 3 {
      end := min(i+3, len(sentences))
      child := ChildChunk{
        ID:       fmt.Sprintf("%s_c%d", p.ID, i/3),
        ParentID: p.ID,
        Content:  strings.Join(sentences[i:end], " "),
      }
      children = append(children, child)
    }
  }

  return parents, children
}
```

**Storage strategy:**
- ChromaDB collection "children" — embed children, search ở đây
- ChromaDB collection "parents" — store parents, lookup theo ID khi gen
- Metadata link: child.parent_id → parent.id

**Áp dụng vào 9 levels:**
- L1 (Entity Profile có nhiều bảng) → child = từng dòng E-E-A-T
- L7 (Article dài) → child = từng paragraph
- L8B (Clinical Data) → child = từng row của bảng số liệu
- L2, L4, L5 → KHÔNG dùng (đã đủ nhỏ và self-contained)

---

### 2.4 Kỹ thuật #4 — Proposition-based Chunking

**Khi nào dùng:** Tài liệu research dày fact (như "Tri thức Chính trị"), nghiên cứu lâm sàng có nhiều con số, văn bản pháp lý.

**Vấn đề giải quyết:** Một paragraph có thể chứa 5 fact độc lập. Khi query hỏi về fact thứ 3, paragraph 600 token bị "loãng" — vector không đủ mạnh.

**Cách hoạt động:**
```
1. LLM phân rã mỗi paragraph thành các "propositions" — câu khẳng định nguyên tử
2. Mỗi proposition tự đứng được, không cần đại từ hoặc anaphora
3. Embed từng proposition riêng
4. Retrieve proposition → truy ngược về parent paragraph để gen
```

**Ví dụ:**
```
Paragraph gốc:
"Robert Dahl từng nhận định rằng tri thức chính trị không phải đặc quyền của giới
tinh hoa. Ông cho rằng dân chủ chỉ vận hành tốt khi công dân có hiểu biết về
quyền và nghĩa vụ. Theo Dahl (1989), tỷ lệ công dân hiểu biết chính trị ở Mỹ
chỉ đạt 35% trong khảo sát của ông."

→ Propositions:
P1: "Robert Dahl cho rằng tri thức chính trị không phải đặc quyền của giới tinh hoa."
P2: "Robert Dahl cho rằng dân chủ vận hành tốt khi công dân hiểu biết về quyền và nghĩa vụ."
P3: "Theo khảo sát của Dahl năm 1989, 35% công dân Mỹ hiểu biết chính trị."
```

**Implementation:**
```go
// Go: chunker/proposition.go

const PROPOSITION_PROMPT = `Phân rã đoạn văn sau thành các propositions (câu khẳng định nguyên tử).
Mỗi proposition phải:
- Tự đứng được (không có "ông", "anh ấy", "điều này")
- Chứa đúng 1 fact
- Giữ đầy đủ tên người, năm, số liệu
Trả về JSON array.

Đoạn văn: %s`

func ExtractPropositions(paragraph string) []string {
  resp := llmService.Generate(LLMRequest{
    Model:      "claude-haiku-4-5",
    UserPrompt: fmt.Sprintf(PROPOSITION_PROMPT, paragraph),
    MaxTokens:  500,
  })
  return parseJSONArray(resp)
}
```

**Áp dụng vào 9 levels:**
- L7 (research papers) → Tách theo proposition
- L8B (Clinical Data) → Mỗi finding lâm sàng = 1 proposition
- L1, L2, L3, L4, L5 → KHÔNG dùng (đã có entity-level granularity)

**Lưu ý chi phí:** Chỉ dùng cho tài liệu high-value (research được trích dẫn nhiều). Không dùng cho mass ingestion.

---

### 2.5 Kỹ thuật #5 — Agentic Chunking (LLM-as-Chunker)

**Khi nào dùng:** Tài liệu KHÔNG có cấu trúc rõ — file ghi âm transcribe, ghi chú họp, tài liệu cũ scan OCR sai lệch.

**Vấn đề giải quyết:** Rule-based chunker (9 levels) không hoạt động với tài liệu không có heading, bảng hoặc pattern rõ ràng.

**Cách hoạt động:**
```
LLM đọc cả tài liệu và quyết định ranh giới chunk dựa trên:
- Chuyển chủ đề (topic shift)
- Kết thúc một luận điểm
- Bắt đầu case mới
- Trích dẫn dài
```

**Implementation:**
```go
// Go: chunker/agentic.go

const AGENTIC_PROMPT = `Bạn là expert chunking. Đọc tài liệu sau và đề xuất ranh giới chunks
theo nguyên tắc:
1. Mỗi chunk là 1 đơn vị nghĩa hoàn chỉnh
2. Chunk size 200–800 tokens
3. Không cắt giữa đoạn case, trích dẫn, danh sách
4. Trả về JSON: [{"start_char": 0, "end_char": 543, "topic": "..."}, ...]

Tài liệu:
%s`

func AgenticChunk(doc Document) []Chunk {
  if len(doc.FullText) > 50000 {
    // Sliding window: chia 10K token segments với overlap 1K
    return slidingAgenticChunk(doc)
  }
  resp := llmService.Generate(LLMRequest{
    Model:      "claude-sonnet-4-6",
    UserPrompt: fmt.Sprintf(AGENTIC_PROMPT, doc.FullText),
    MaxTokens:  4000,
  })
  boundaries := parseJSONBoundaries(resp)
  return boundariesToChunks(doc, boundaries)
}
```

**Áp dụng:** Document Router (Phase 2G) thêm type mới `unstructured` → fallback sang Agentic Chunking.

**Lưu ý:** Đắt nhất trong 5 kỹ thuật. Chỉ dùng khi 9 levels rule-based fail.

---

## PHẦN 3: DOCUMENT ROUTER v3 (CẬP NHẬT)

Router cần biết khi nào dùng kỹ thuật nào. Đây là decision tree mới:

```go
// Go: chunker/document_router_v3.go

func RouteV3(doc ParsedDocument) ChunkingStrategy {
  docType := DetectDocumentType(doc)
  tokens := countTokens(doc.FullText)

  switch docType {
  case DocTypeOperational:
    // T3-01, T3-02, SOP
    return ChunkingStrategy{
      Levels:           []string{"L1", "L2", "L3", "L4", "L5", "L6", "L9"},
      LateChunking:     tokens < 8000,        // Bật nếu fit BGE-M3 window
      Contextual:       tokens >= 8000,        // Fallback nếu doc dài
      Hierarchical:     true,                  // L1 luôn cần parent-child
      Proposition:      false,
      Agentic:          false,
    }

  case DocTypeArticle:
    return ChunkingStrategy{
      Levels:           []string{"L7", "L9"},
      LateChunking:     tokens < 8000,
      Contextual:       tokens >= 8000,
      Hierarchical:     true,                  // Parent = section, Child = paragraph
      Proposition:      false,
      Agentic:          false,
    }

  case DocTypeResearch:
    // Bài "Tri thức Chính trị", paper học thuật
    return ChunkingStrategy{
      Levels:           []string{"L7", "L9"},
      LateChunking:     false,                 // Doc thường dài
      Contextual:       true,                  // BẮT BUỘC
      Hierarchical:     true,
      Proposition:      true,                  // High-value content
      Agentic:          false,
    }

  case DocTypeClinical:
    return ChunkingStrategy{
      Levels:           []string{"L8A", "L8B", "L8C", "L9"},
      LateChunking:     true,                  // Bài thuốc thường < 8K
      Contextual:       true,                  // Phác đồ dài cần
      Hierarchical:     true,                  // L8B parent-child
      Proposition:      true,                  // Số liệu lâm sàng
      Agentic:          false,
    }

  case DocTypeUnstructured:
    return ChunkingStrategy{
      Levels:           []string{},            // Bỏ rule-based
      LateChunking:     false,
      Contextual:       true,
      Hierarchical:     false,
      Proposition:      false,
      Agentic:          true,                  // LLM-as-chunker
    }

  default:
    return ChunkingStrategy{
      Levels:           []string{"L7"},
      LateChunking:     true,
      Contextual:       false,
      Hierarchical:     false,
    }
  }
}
```

### Bảng tổng hợp routing v3

| Doc Type | 9 Levels dùng | Late | Contextual | Hierarchical | Proposition | Agentic |
|----------|----------------|------|------------|--------------|-------------|---------|
| operational | L1–L6, L9 | ✅ < 8K | ✅ ≥ 8K | ✅ | — | — |
| article | L7, L9 | ✅ < 8K | ✅ ≥ 8K | ✅ | — | — |
| research | L7, L9 | — | ✅ | ✅ | ✅ | — |
| clinical | L8A/B/C, L9 | ✅ | ✅ | ✅ | ✅ | — |
| unstructured | — | — | ✅ | — | — | ✅ |

> **L5 (Negative Rules) và L9 (Cross-Reference) luôn chạy** bất kể strategy nào — giữ nguyên từ v2.

---

## PHẦN 4: PIPELINE CHUNKING v3 — LUỒNG XỬ LÝ ĐẦY ĐỦ

```
┌──────────────────────────────────────────────────────────────┐
│ INPUT: PDF / DOCX / HTML / Markdown                          │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 1: PARSING                                             │
│  - DeepDoc (RAGFlow) cho PDF có bảng phức tạp               │
│  - VLM (Qwen2-VL/Claude vision) fallback cho scan OCR kém   │
│  Output: ParsedDocument {pages, blocks, tables, figures}    │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 2.0: DOCUMENT ROUTER v3                                │
│  → Detect type (operational/article/research/clinical/      │
│     unstructured)                                            │
│  → Quyết định ChunkingStrategy (9 levels + 5 techniques)    │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 2.1: CHUNKING (theo strategy)                          │
│                                                              │
│  ┌─ 9 Levels Chunker (rule-based, từ v2) ─────────────┐    │
│  │  L1 entity / L2 channel / L3 decision / L4 script  │    │
│  │  L5 negative / L6 matrix / L7 article              │    │
│  │  L8A/B/C clinical / L9 cross-ref                   │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─ Hierarchical Splitter (NEW) ──────────────────────┐    │
│  │  parents (800–1500) + children (150–300)           │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─ Proposition Extractor (NEW, optional) ─────────────┐   │
│  │  LLM phân rã thành atomic facts                     │   │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─ Agentic Chunker (NEW, fallback) ──────────────────┐    │
│  │  Chỉ chạy khi doc_type = unstructured              │    │
│  └─────────────────────────────────────────────────────┘    │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 2.2: CONTEXT INJECTION                                 │
│  - Static Header (từ v2): [TL: ...] [Mã: ...] [Hub: ...]   │
│  - Contextual Retrieval (NEW): LLM viết 50-100 tok context  │
│    + prompt caching để giảm 90% chi phí                     │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 3: METADATA ENRICHMENT                                 │
│  - Rule-based entity extractor (từ v2)                      │
│  - LLM-assisted entity discovery cho entity ngầm (NEW)      │
│  - Tag channel, disease, rule_type, priority                │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 4: EMBEDDING                                           │
│  ┌─ Late Chunking path (NEW) ──┐  ┌─ Standard path ────┐   │
│  │ embed_tokens → mean pool   │  │ embed full chunks  │   │
│  │ theo chunk boundary         │  │ với context header │   │
│  └────────────┬────────────────┘  └─────────┬──────────┘   │
│               │                              │              │
│               └──────────────┬──────────────┘              │
│                              ▼                              │
│  BGE-M3 dense + sparse → ChromaDB (dual collection:        │
│  parents + children)                                        │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 5: HYBRID RETRIEVAL                                    │
│  1. Dense (60%) + Sparse (40%) trên CHILDREN                │
│  2. Lookup PARENTS từ child.parent_id                       │
│  3. Inject L5 negative_rule (always_include=true)           │
│  4. Cross-ref expansion (L9)                                │
│  5. ViRanker rerank (top_k chunks)                          │
│  6. Trả về parents để LLM generate                          │
└──────────────────────────────────────────────────────────────┘
```

---

## PHẦN 5: PHASE 4 (EMBEDDING) — CẬP NHẬT v3

### 5.1 Lựa chọn embedding model (4/2026)

| Model | Strength | Khi dùng |
|-------|----------|----------|
| **BGE-M3** (chính) | Hybrid dense+sparse, 8K context, hỗ trợ Late Chunking | Default cho mọi hub |
| **Jina embeddings v3** | Late Chunking native, 8K context, multilingual | A/B test với BGE-M3 trên test set Việt |
| **Qwen3-Embedding-0.6B** | Benchmark MMTEB cao, optimize cho CJK + tiếng Việt | Fallback cho clinical (Hán Việt) |
| **Voyage-3** (API) | Dense rất mạnh, 32K context | Chỉ dùng nếu data không nhạy cảm (gửi cloud) |

**Quyết định mặc định v3:** Vẫn BGE-M3 nhưng BẮT BUỘC bật token-level embedding cho Late Chunking. Set up A/B với Jina v3 trong Phase 7.

### 5.2 API Embedding mở rộng

```
POST /embed                    # giữ nguyên từ v2
POST /embed_tokens             # MỚI - cho Late Chunking
  Input:  {"text": "...", "return": "token_embeddings"}
  Output: {"tokens":[...], "embeddings":[[1024],...], "offsets":[[0,2],...]}

POST /rerank                   # giữ nguyên từ v2
POST /rerank_contextual        # MỚI - rerank với contextual headers
  Input:  {"query":"...", "passages":[{"text":"...", "context":"..."}]}
```

### 5.3 ChromaDB schema mới

```python
# Collection per Hub, dual-tier
chroma_client.create_collection(
  name=f"{hub_id}_parents",
  metadata={"tier": "parent", "size_range": "800-1500"}
)
chroma_client.create_collection(
  name=f"{hub_id}_children",
  metadata={"tier": "child", "size_range": "150-300", "embedded": True}
)

# Mỗi child document có metadata: {parent_id, chunk_type, entities, ...}
# Mỗi parent document có metadata: {child_ids[], full_metadata, ...}
```

---

## PHẦN 6: PHASE 5 (RETRIEVAL) — CẬP NHẬT v3

```go
// Go: retrieval/engine_v3.go

func SearchV3(query string, hubID string, topK int) []RankedChunk {
  // 1. Embed query (dense + sparse)
  queryEmb := embeddingService.Embed(query, "dense+sparse")

  // 2. Query expansion (NEW) — viết lại query bằng LLM nếu < 5 từ
  if len(strings.Fields(query)) < 5 {
    query = llmService.ExpandQuery(query)
    queryEmb = embeddingService.Embed(query, "dense+sparse")
  }

  // 3. Search trên CHILDREN collection (NEW — Hierarchical)
  childrenColl := vectorDB.Collection(hubID + "_children")
  denseChildren  := childrenColl.SearchDense(queryEmb.Dense, topK*4)
  sparseChildren := childrenColl.SearchSparse(queryEmb.Sparse, topK*4)
  fusedChildren  := fuseResults(denseChildren, sparseChildren, 0.6, 0.4)

  // 4. Lookup PARENTS từ child.parent_id (NEW)
  parentIDs := dedupParentIDs(fusedChildren)
  parents := vectorDB.Collection(hubID + "_parents").GetByIDs(parentIDs)

  // 5. Inject L5 negative rules (giữ từ v2)
  negRules := vectorDB.GetByFlag("always_include", hubID)
  parents = append(negRules, parents...)

  // 6. Cross-reference expansion (L9, giữ từ v2)
  expanded := expandCrossReferences(parents, topK)

  // 7. Contextual rerank (NEW) — pass context header vào reranker
  reranked := rerankerService.RerankContextual(query, expanded, topK)

  return reranked
}
```

---

## PHẦN 7: TIMELINE TRIỂN KHAI v3 (REFRESH)

| Tuần | Nội dung refresh | Output | Phụ thuộc |
|------|-------------------|--------|-----------|
| 1 | Cập nhật Embedding Service: thêm `/embed_tokens` cho Late Chunking | Python service v2 với token-level output | BGE-M3 |
| 1–2 | Implement `chunker/late_chunking.go` | Go module Late Chunking | embed_tokens API |
| 2 | Implement `chunker/hierarchical.go` | Parent-child splitter | 9 levels chunker (v2) |
| 2–3 | Implement `chunker/contextual_retrieval.go` với Anthropic prompt caching | Contextual headers | Claude API |
| 3 | Cập nhật ChromaDB schema: dual collection (parents + children) | Migration script | ChromaDB |
| 3–4 | Cập nhật `document_router_v3.go` với strategy table | Router v3 | Tất cả ở trên |
| 4 | Implement `chunker/proposition.go` (chỉ cho research) | LLM proposition extractor | Claude API |
| 4 | Implement `chunker/agentic.go` (fallback) | LLM-as-chunker | Claude API |
| 5 | Cập nhật `retrieval/engine_v3.go` | Hybrid với parent expansion | Phase 4 mới |
| 5–6 | Cập nhật `services/rag_service.go` worker để chạy strategy mới | Integration | Phase 5 mới |
| 6 | Eval loop tự động (RAGAS hoặc custom) | Continuous quality monitoring | Phase 7 v2 test set |
| 7+ | A/B test BGE-M3 vs Jina v3 vs Qwen3-Embedding | Decision report | Eval loop |
| 8+ | Phase 8: GraphRAG đầy đủ (từ L9) | KG service | Tất cả ở trên |

---

## PHẦN 8: CHECKLIST CHO CLAUDE CODE

### 8.1 Files cần TẠO MỚI
```
chunker/
  late_chunking.go          # MỚI
  contextual_retrieval.go   # MỚI
  hierarchical.go           # MỚI
  proposition.go            # MỚI
  agentic.go                # MỚI
  document_router_v3.go     # MỚI (replace v2 router)

embedding_service/
  api.py                    # CẬP NHẬT (thêm /embed_tokens)
  late_chunking.py          # MỚI

retrieval/
  engine_v3.go              # MỚI (replace v2 engine)
  query_expansion.go        # MỚI

storage/
  migrate_dual_collection.py # MỚI (migration script)

eval/
  ragas_runner.go           # MỚI
  test_set_v3.json          # MỚI (mở rộng test v2)
```

### 8.2 Files cần CẬP NHẬT
```
chunker/
  entity_profile.go         # Thêm parent-child split
  article_narrative.go      # Bỏ static header → contextual
  clinical_*.go             # Thêm proposition extraction option
  header_injector.go        # Giữ static header, contextual gọi separate

services/
  rag_service.go            # Worker chạy strategy v3

models/
  chunk_metadata.go         # Thêm: ParentID, ContextualHeader, Method
```

### 8.3 Files KHÔNG ĐỘNG (giữ nguyên từ v2)
```
chunker/
  channel_rule.go           # L2 — không cần parent-child
  decision_tree.go          # L3 — đã đủ nhỏ
  script_template.go        # L4 — đã đủ nhỏ
  negative_rule.go          # L5 — always inject, không thay đổi logic
  matrix_table.go           # L6 — Late Chunking chỉ thêm embed step
  cross_reference.go        # L9 — giữ nguyên, sẽ nâng GraphRAG ở Phase 8
```

---

## PHẦN 9: LƯU Ý CHI PHÍ & TRADE-OFF

### 9.1 Chi phí mới (so với v2)

| Kỹ thuật | Chi phí thêm | Lợi ích | Khi nào BẬT |
|----------|--------------|---------|-------------|
| Late Chunking | 0 (chỉ thay đổi cách gọi embed) | Giữ context dài | Mặc định cho doc < 8K |
| Contextual Retrieval | ~$1/1M doc tokens (cached) | -49% retrieval failure | Doc > 8K hoặc high-value |
| Hierarchical | 2× storage (parent + child) | Precise retrieve + rich gen | Doc dài, content quan trọng |
| Proposition | LLM call mỗi paragraph | Best precision với fact-heavy | Chỉ research papers |
| Agentic | LLM call cả tài liệu | Cứu doc unstructured | Fallback only |

### 9.2 Quyết định phòng thủ

> Nếu ngân sách hạn chế: Bật **Late Chunking + Hierarchical** trước (chi phí gần 0). Bật Contextual Retrieval cho top 20% tài liệu được truy vấn nhiều nhất. Để Proposition + Agentic là optional.

---

## PHẦN 10: GHI CHÚ DI CHUYỂN TỪ v2 → v3

1. **Không cần re-ingest mọi tài liệu cũ** — v2 chunks vẫn dùng được. Chạy v3 cho doc mới và doc được sửa.
2. **Migration script** sẽ tạo `_children` collection mới và build child chunks từ parent chunks v2 hiện có. L1, L7, L8 chạy lại; L2-L6 giữ nguyên.
3. **API v2 vẫn hoạt động** — engine_v3 fallback sang engine_v2 nếu collection `_children` không tồn tại.
4. **Test set v2 vẫn dùng** — chỉ thêm câu hỏi mới cho test Late Chunking và Contextual Retrieval.

---

> **GHI CHÚ:** Đây là bản refresh tháng 4/2026 dựa trên kinh nghiệm 9 tháng vận hành v2.0 và best practices từ Anthropic Contextual Retrieval, Jina AI Late Chunking, Microsoft GraphRAG GA. Đọc kèm `Medinet_RAG_Pipeline_v2_Full_9Levels.md` để hiểu kiến trúc nền tảng — file này KHÔNG thay thế v2 mà BỔ SUNG lên trên.
