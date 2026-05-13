# CONTEXT — Phase 3: Go Adapter & Pipeline Wiring

**Phase:** 3 / 5
**Milestone:** M1 — RAG Quality with Docling
**Goal:** Backend Go gọi được service Docling qua REST, branch pipeline ingestion bypass chunker Go khi nguồn là Docling, vẫn dùng nguyên `SwappableEmbedder` + ChromaDB upsert + usage logging async. Stage progress 0→100% báo cáo đúng.
**Requirements:** WIRE-01..06, CHUNK-05, EXTRACT-05 (8 REQ — EXTRACT-05 move từ Phase 2 sang Phase 3 vì là fallback policy thuộc WIRE)
**Ngày discuss:** 2026-04-29

---

## Decisions Locked

### A. Interface design — thêm `StructuredExtractor` mới (KHÔNG đổi `Extractor` cũ)

**Lý do:** Backward-compat 100% với 7 file extractor Go hiện tại (`pdf.go`, `docx.go`, `xlsx.go`, `pptx.go`, `csv.go`, `html.go`, `text.go`).

**Implementation:**

```go
// backend/internal/rag/extractor/extractor.go (giữ nguyên)
type Extractor interface {
    Extract(ctx context.Context, filePath string) (string, error)
    SupportedType() string
}

// Mới — thêm cùng file
type StructuredExtractor interface {
    Extractor // embed — implementor phải có cả Extract() text legacy
    ExtractStructured(ctx context.Context, filePath string) (text string, preChunks []rag.Chunk, err error)
}
```

**Pipeline check qua type assertion** (`backend/internal/rag/pipeline.go`):
```go
if structured, ok := extractor.(StructuredExtractor); ok && cfg.RAG.Extractor == "docling" {
    text, preChunks, err := structured.ExtractStructured(ctx, filePath)
    // ... skip chunker Go nếu preChunks != nil
} else {
    text, err := extractor.Extract(ctx, filePath)
    // ... đường cũ qua chunker Go
}
```

**Chỉ `DoclingExtractor` implement `StructuredExtractor`** — extractor Go cũ giữ nguyên chỉ implement `Extractor`.

### B. HTTP client — `net/http` stdlib + retry tự viết

**Lý do:** Match convention Go backend hiện tại (zero deps), 30 dòng code đủ.

**Implementation skeleton (`backend/internal/rag/extractor/docling.go`):**

```go
type DoclingExtractor struct {
    baseURL    string        // env DOCLING_SERVICE_URL
    timeout    time.Duration // env DOCLING_TIMEOUT_SEC, default 180s
    httpClient *http.Client
}

func (d *DoclingExtractor) ExtractStructured(ctx context.Context, filePath string) (string, []rag.Chunk, error) {
    // Multipart file upload
    body, contentType := buildMultipart(filePath)
    req, _ := http.NewRequestWithContext(ctx, "POST", d.baseURL+"/v1/process", body)
    req.Header.Set("Content-Type", contentType)
    if rid := requestid.From(ctx); rid != "" {
        req.Header.Set("X-Request-Id", rid)
    }
    
    // Retry exponential 2 lần max (theo WIRE-01)
    var resp *http.Response
    for attempt := 0; attempt < 3; attempt++ {
        resp, err = d.httpClient.Do(req)
        if err == nil && resp.StatusCode < 500 { break }
        if resp != nil { resp.Body.Close() }
        time.Sleep(time.Duration(1<<attempt) * time.Second) // 1s, 2s, 4s
    }
    
    // Parse response → ProcessResponse → []rag.Chunk
    // ...
}
```

**Default `httpClient.Timeout` = 180s** (DOCLING_TIMEOUT_SEC) để vẫn để Docling xử lý PDF lớn.

### C. Request_id middleware — reuse nếu có, add mới nếu không

**Quy trình:** Phase 3 đầu tiên check `backend/internal/middleware/` cho file có sẵn handle request_id (vd `requestid.go`, `tracing.go`). Nếu có → reuse + verify ghi vào Gin context với key `request_id`. Nếu không có → thêm middleware mới:

```go
// backend/internal/middleware/request_id.go (mới nếu cần)
func RequestID() gin.HandlerFunc {
    return func(c *gin.Context) {
        rid := c.GetHeader("X-Request-Id")
        if rid == "" {
            rid = uuid.NewString()
        }
        c.Set("request_id", rid)
        c.Header("X-Request-Id", rid) // echo back response
        c.Next()
    }
}
```

Helper `pkg/requestid/requestid.go`:
```go
func From(ctx context.Context) string {
    if c, ok := ctx.(*gin.Context); ok {
        if v, exists := c.Get("request_id"); exists {
            return v.(string)
        }
    }
    return ""
}
```

`DoclingExtractor.ExtractStructured` dùng `requestid.From(ctx)` để propagate header sang Docling sidecar (DSVC-04 Phase 2 đã expect).

### D. `DOCLING_SERVICE_URL` default — `http://localhost:8001` cho dev

**Default env:** `DOCLING_SERVICE_URL=http://localhost:8001`.

**Compose override:** trong `docker-compose.yml`, backend Go sau này (khi dockerize) dùng env override `DOCLING_SERVICE_URL=http://docling-pipeline:8001`.

**Hiện tại M1 backend Go chạy native** (xem `.planning/phases/02-docling-service-python-sidecar/02-CONTEXT.md` mục B) → chỉ cần `localhost:8001` work, mà compose override port 8001:8001 (qua `docker-compose.override.yml` đã tạo) → work cả hai mode.

---

## Implementation Tasks (planner sẽ decompose)

### WIRE-01 — Tạo `DoclingExtractor`

File: `backend/internal/rag/extractor/docling.go` (mới).
- Implement `StructuredExtractor` interface.
- HTTP client gọi `POST /v1/process` qua multipart.
- Retry exponential backoff (1s, 2s, 4s — max 2 retry).
- Propagate `X-Request-Id` header.
- Parse response JSON → `[]rag.Chunk`.

### WIRE-02 — Refactor interface

File: `backend/internal/rag/extractor/extractor.go` (modify).
- Giữ nguyên interface `Extractor` cũ.
- Thêm interface mới `StructuredExtractor` (embed `Extractor` + thêm `ExtractStructured` method).
- Update `init()` registry: `DoclingExtractor` đăng ký riêng (key = `"docling"` thay vì extension), KHÔNG ghi đè extractor Go theo MIME.

### WIRE-03 — Branch pipeline

File: `backend/internal/rag/pipeline.go` (modify).
- Check env `RAG_EXTRACTOR` (`docling`/`native`/`auto`).
- Nếu `docling` AND extractor implement `StructuredExtractor` → gọi `ExtractStructured` → nếu `preChunks != nil` thì skip chunker Go (StrategicChunker), đi thẳng vào augmenter Go (nếu bật) → embedder.
- Nếu `native` hoặc Docling fail (CFG-01 fallback Phase 4) → đường cũ qua chunker Go.
- Stage progress 0→100% giữ nguyên semantics (extract = 0-30%, chunk/skip = 30-50%, embed = 50-90%, upsert = 90-100%).

### WIRE-04 — Worker timeout

File: `backend/internal/worker/manager.go` (modify).
- Thêm env `JOB_TIMEOUT_DOCLING_SEC` (default 240s — gấp đôi `DOCLING_REQUEST_TIMEOUT_SEC` để có buffer cho retry).
- Per-job timeout: `if extractor=docling → JOB_TIMEOUT_DOCLING_SEC, else → JOB_TIMEOUT_DEFAULT_SEC`.

### WIRE-05 — Embedding pipeline KHÔNG đổi

Verify `backend/internal/embedding/swappable.go` + `backend/internal/vectorstore/chromadb.go` + `backend/internal/service/usage_*.go` KHÔNG bị side-effect từ thay đổi pipeline branch. Test: chunks Docling (đã có `token_count` từ Python) vẫn pass đúng vào `Embedder.Embed()` + `Store.Upsert()`.

### WIRE-06 — Request_id middleware

File: `backend/internal/middleware/request_id.go` (mới nếu chưa có).
- Auto-gen UUID nếu header thiếu.
- Set Gin context key `request_id`.
- Echo header response.
- Wire vào `router.Setup()` đầu chain (sau Recovery, trước CORS).

Helper `backend/internal/pkg/requestid/requestid.go` (mới):
- `From(ctx) string` lấy request_id từ Gin context hoặc context.Context.

### CHUNK-05 — Bypass chunker Go khi `RAG_EXTRACTOR=docling`

Đã cover trong WIRE-03. Smoke test: upload 1 file với `RAG_EXTRACTOR=docling`, log Go phải show "skipping Go chunker, using Docling preChunks (N items)".

### EXTRACT-05 — Giữ Go extractor cũ làm fallback

KHÔNG xóa `pdf.go`, `docx.go`, ..., `text.go` trong `backend/internal/rag/extractor/`. Chỉ thêm `docling.go`. Pipeline branch (WIRE-03) đảm bảo có thể switch về native qua env `RAG_EXTRACTOR=native` mà không cần code change.

---

## Chunk metadata mapping (DSVC-02 → DocumentChunk.Metadata)

`document_chunks.metadata` là `JSONB` (đã có sẵn schema, KHÔNG cần migration). Map từ Docling response:

```go
chunk.Metadata = map[string]any{
    "headers":      doclingChunk.Headers,        // []string heading path
    "page_start":   doclingChunk.PageStart,      // int
    "page_end":     doclingChunk.PageEnd,        // int
    "is_table":     doclingChunk.IsTable,        // bool
    "table_html":   doclingChunk.TableHTML,      // string nullable
    "bbox":         doclingChunk.BBox,           // []float64 nullable
    "caption":      doclingChunk.Caption,        // string nullable
    "source":       "docling",                   // marker phân biệt với native
}
```

Phase 5 eval sẽ filter ChromaDB query qua `metadata.is_table` hoặc `metadata.headers` (Chroma where clause).

---

## Out of Scope Phase 3 (defer)

- ❌ Config flag + circuit breaker — Phase 4 (CFG-01..05).
- ❌ Eval scripts so sánh — Phase 5 (EVAL-02..05).
- ❌ Smoke test với Docling service real — Phase 4-5 (cần Docling sidecar chạy thật, hiện tại deferred infra).
- ❌ UI thay đổi (DocumentIngestion page) — không cần, flow upload không đổi.
- ❌ Test coverage Go — milestone hardening riêng.
- ❌ Dockerize backend Go — milestone hardening riêng.

## Test strategy Phase 3

**Unit test mock service Python:**
- Tạo `backend/internal/rag/extractor/docling_test.go` với httptest.Server mock trả response DSVC-02 schema.
- Test các case: success, 413 payload too large, 504 timeout, network error retry, 5xx server error.

**Integration test:** defer Phase 4-5 khi Docling service real chạy được.

---

## Gray Areas đã decide bằng default (không thảo luận)

- DB migration: KHÔNG cần (metadata JSONB đủ).
- Test mocking: httptest.Server stdlib (consistent với conventions Go backend).

## Deferred Ideas (cho roadmap backlog)

- 999.6 — Bidirectional streaming gRPC giữa Go ↔ Python sidecar (giảm latency multipart upload).
- 999.7 — Connection pooling cho HTTP client gọi Docling (hiện tại 1 client singleton, không pool — OK với worker pool single-flight).

## Rủi ro & Câu hỏi mở

- **Rủi ro 1:** Smoke runtime Phase 3 cần Docling service chạy thật → bị block bởi infra Phase 2 deferred. Mitigation: **mock service Python httptest** trong unit test Go, integration runtime defer Phase 4-5.
- **Rủi ro 2:** Type assertion `extractor.(StructuredExtractor)` có thể fail silently nếu `RAG_EXTRACTOR=docling` nhưng extractor không phải Docling (vd file extension không match). Mitigation: pipeline branch validate `extractor` được resolve từ key `"docling"` (theo registry), không từ MIME type.
- **Rủi ro 3:** Worker pool timeout cũ (60s?) bị quá cho job Docling — kill job ngay khi Docling extract chưa xong. Mitigation: WIRE-04 phân biệt timeout theo extractor mode.

---

## Downstream

**gsd-planner Phase 3 sẽ đọc CONTEXT này để biết:**
- Interface design chốt → 1 file modify (extractor.go) + 1 file mới (docling.go).
- HTTP client stdlib → không add dep `go.mod`.
- Request_id middleware reuse hoặc add → 1 task check existing trước.
- Mapping DSVC-02 → metadata JSONB → planner viết struct chính xác.

---

*Last updated: 2026-04-29*
