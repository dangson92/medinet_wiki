---
phase: 03-go-adapter-pipeline-wiring
plan: 02
subsystem: rag-extractor
tags: [docling, http-client, retry, multipart, adapter]
status: completed
requirements: [WIRE-01]
dependency_graph:
  requires:
    - "Plan 03-01 (interface StructuredExtractor + helper requestid)"
  provides:
    - "DoclingExtractor singleton implement StructuredExtractor (cho Plan 03-04 wire pipeline)"
    - "Constructor NewDoclingExtractor(baseURL, timeoutSec) (cho main.go khởi tạo từ cfg)"
    - "Context helpers WithHubCode/WithDocType (cho Plan 03-04 inject metadata trước pipeline)"
    - "DTO processChunkDTO/processResponse exported nội package (cho Plan 03-05 mock httptest)"
    - "3 env config: RAG_EXTRACTOR / DOCLING_SERVICE_URL / DOCLING_TIMEOUT_SEC (cho Phase 4 CFG)"
  affects:
    - "RAGConfig struct trong backend/internal/config/config.go (+3 field)"
tech-stack:
  added: []
  patterns:
    - "HTTP client stdlib net/http (zero deps mới — go.mod/go.sum unchanged)"
    - "Multipart upload qua mime/multipart, rebuild MỖI attempt vì io.Reader đã consume"
    - "Retry exponential backoff thủ công 1s/2s với select ctx.Done()/time.After"
    - "Compile-time interface assertion: var _ StructuredExtractor = (*DoclingExtractor)(nil)"
    - "Pointer cho field nullable JSON (caption/table_html) — phân biệt nil vs empty string"
key-files:
  created:
    - backend/internal/rag/extractor/docling.go
  modified:
    - backend/internal/config/config.go
    - backend/.env.example
decisions:
  - "KHÔNG đăng ký DoclingExtractor vào registry init() — Plan 03-04 instantiate qua DI từ main.go"
  - "Default RAG_EXTRACTOR=native (KHÔNG đổi behavior cũ); Phase 4 CFG-01 mới đổi mặc định sang 'auto'"
  - "Retry KHÔNG áp dụng 4xx (client lỗi không tự fix bằng retry) và 504 (server đã hết giờ)"
  - "Buffer multipart in-memory (đủ với DOCLING_MAX_FILE_MB=50 server-side)"
  - "Helper WithHubCode/WithDocType placeholder — Plan 03-04 sẽ wire từ DocumentRequest"
metrics:
  duration: "~12 phút"
  completed: 2026-04-29
  tasks_total: 2
  tasks_completed: 2
  files_changed: 3
  commit: a4af6ae
---

# Phase 3 Plan 02: DoclingExtractor — HTTP Client Adapter Summary

**One-liner:** Wave 2 Phase 3 — DoclingExtractor singleton implement `StructuredExtractor` qua `net/http` stdlib gọi `POST /v1/process`, retry exponential 1s/2s/4s, multipart upload, parse DSVC-02 response, map sang `[]chunker.Chunk` 8 metadata field — zero deps mới.

## Tasks executed

| # | Task | Status | Files | Verify |
|---|------|--------|-------|--------|
| 1 | Mở rộng `RAGConfig` (+3 field) + cập nhật `.env.example` | ✅ | `config.go` (modify), `.env.example` (modify) | `go build ./internal/config/...` PASS, `go vet` clean |
| 2 | Tạo `DoclingExtractor` HTTP client + retry + multipart + parse | ✅ | `docling.go` (mới ~290 dòng) | `go build ./internal/rag/extractor/...` PASS, compile-time assert OK |

**Verify tổng:**
- `cd backend && go build ./...` → exit 0 (toàn repo PASS, không lỗi cross-package).
- `cd backend && go vet ./...` → clean.
- `grep -n "_ StructuredExtractor" docling.go` → line 298 (compile-time assert hiện diện).
- `grep -c "DOCLING_SERVICE_URL\|RAG_EXTRACTOR\|DOCLING_TIMEOUT_SEC" .env.example` → 4 (>= 3 spec).
- `git diff backend/go.mod backend/go.sum` → rỗng (zero deps mới — đáp ứng CONTEXT mục B "stdlib + retry tự viết").

## API signature đã chốt (cho Plan 03-04 dùng)

```go
// backend/internal/rag/extractor/docling.go
const DoclingKey = "docling"

func NewDoclingExtractor(baseURL string, timeoutSec int) *DoclingExtractor

// Implement Extractor:
func (d *DoclingExtractor) Extract(ctx context.Context, filePath string) (string, error)
func (d *DoclingExtractor) SupportedType() string  // → "docling"

// Implement StructuredExtractor:
func (d *DoclingExtractor) ExtractStructured(
    ctx context.Context, filePath string,
) (text string, preChunks []chunker.Chunk, err error)

// Context helpers (Plan 03-04 inject metadata):
func WithHubCode(ctx context.Context, hubCode string) context.Context
func WithDocType(ctx context.Context, docType string) context.Context
```

**Cách Plan 03-04 sẽ dùng:**

```go
// main.go (DI):
doclingExt := extractor.NewDoclingExtractor(cfg.RAG.DoclingServiceURL, cfg.RAG.DoclingTimeoutSec)

// pipeline.go (branch theo cfg.RAG.Extractor):
ctx = extractor.WithHubCode(ctx, doc.HubCode)
ctx = extractor.WithDocType(ctx, doc.DocType)
if cfg.RAG.Extractor == extractor.DoclingKey {
    if se, ok := ext.(extractor.StructuredExtractor); ok {
        text, preChunks, err := se.ExtractStructured(ctx, filePath)
        // skip chunker Go nếu preChunks != nil
    }
}
```

## DTO nội bộ (Plan 03-05 reuse cho mock httptest)

```go
type processChunkDTO struct {
    ChunkIndex int       `json:"chunk_index"`
    Text       string    `json:"text"`
    Headers    []string  `json:"headers"`
    Caption    *string   `json:"caption"`
    PageStart  int       `json:"page_start"`
    PageEnd    int       `json:"page_end"`
    IsTable    bool      `json:"is_table"`
    TableHTML  *string   `json:"table_html"`
    BBox       []float64 `json:"bbox"`
    TokenCount int       `json:"token_count"`
}

type processResponse struct {
    RequestID string            `json:"request_id"`
    DocMeta   map[string]any    `json:"doc_meta"`
    Chunks    []processChunkDTO `json:"chunks"`
}
```

**Plan 03-05 mock test sẽ:** dùng `httptest.NewServer`, encode `processResponse` JSON trả về, assert `DoclingExtractor.ExtractStructured` parse + map đúng.

## Map metadata fields (DSVC-02 → chunker.Chunk.Metadata)

| Field nguồn (Docling JSON) | Field đích (`chunker.Chunk`) | Nullable handling |
|---|---|---|
| `chunk_index`               | `Index`                  | required |
| `text`                      | `Content`                | required |
| `token_count`               | `TokenCount`             | required |
| `is_table` (true)           | `ChunkType = "docling_table"` | bool |
| `is_table` (false)          | `ChunkType = "docling_text"`  | bool |
| `headers` []string          | `Metadata["headers"]`    | always set |
| `page_start` int            | `Metadata["page_start"]` | always set |
| `page_end` int              | `Metadata["page_end"]`   | always set |
| `is_table` bool             | `Metadata["is_table"]`   | always set |
| (constant)                  | `Metadata["source"] = "docling"` | always — phân biệt với native |
| `caption` *string           | `Metadata["caption"]`    | bỏ nếu nil |
| `table_html` *string        | `Metadata["table_html"]` | bỏ nếu nil |
| `bbox` []float64            | `Metadata["bbox"]`       | bỏ nếu len = 0 |

→ Đúng 8 field metadata theo CONTEXT mục "Chunk metadata mapping" (7 từ Docling + 1 marker `source`).

## Retry semantics đã verify (logic, runtime test ở Plan 03-05)

| Tình huống | Retry? | Lý do |
|---|---|---|
| Network error (`Do()` trả error) | ✅ Có (max 3 attempts, sleep 1s rồi 2s) | Có thể tạm thời (service đang restart) |
| HTTP 200 success | ❌ Không | Đã thành công |
| HTTP 4xx (vd 413 payload too large) | ❌ Không | Client lỗi — retry không fix |
| HTTP 504 Gateway Timeout | ❌ Không | Server đã hết giờ — retry càng tệ |
| HTTP 500/502/503 | ✅ Có | Server tạm thời lỗi |
| Build request lỗi (file không mở được) | ❌ Không | Lỗi local — retry vô nghĩa |
| `ctx.Done()` trong khi sleep | ❌ Không | Caller hủy — return `ctx.Err()` |

Backoff sequence: attempt 0 → sleep 1s → attempt 1 → sleep 2s → attempt 2 → fail (KHÔNG sleep sau attempt cuối — đúng spec must_have #3).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Hook PostToolUse báo `doclingTimeoutSec declared and not used`**
- **Found during:** Task 1 (sau khi thêm dòng `strconv.Atoi` đọc env nhưng chưa wire vào struct init).
- **Issue:** Edit thứ 2 chỉ thêm biến local; chưa kịp gắn vào `RAG: RAGConfig{...}`.
- **Fix:** Edit thứ 3 thêm `DoclingTimeoutSec: doclingTimeoutSec` (cùng `Extractor` + `DoclingServiceURL`) vào struct init → biến được dùng → build PASS.
- **Files modified:** `backend/internal/config/config.go`.
- **Commit:** `a4af6ae` (single atomic).

### KHÔNG tự ý làm

- KHÔNG tạo unit test `docling_test.go` — Plan 03-05 (Wave 5 Test) đã có scope riêng (mock httptest.Server, 6 test case).
- KHÔNG đăng ký DoclingExtractor vào `init()` của `extractor.go` — đúng theo CONTEXT mục B + notes Plan 03-01.
- KHÔNG modify pipeline.go — Plan 03-04 (Wave 4 Wire) sẽ làm.
- KHÔNG `git add .` — chỉ stage 3 file thuộc plan (theo notes Plan 03-01: backend/ untracked toàn bộ, không kéo theo).
- KHÔNG fix concerns pre-existing (`.gitignore`, `chroma_data/`, `backend/keys/*.json`) — milestone hardening riêng.

## Authentication gates

Không có. Plan thuần code Go local + viết file.

## Self-Check: PASSED

**Files exist:**
- ✅ `backend/internal/rag/extractor/docling.go` (created, 302 dòng).
- ✅ `backend/internal/config/config.go` (modified, +3 field RAGConfig + 1 dòng `Atoi` + 3 dòng struct init).
- ✅ `backend/.env.example` (modified, append 16 dòng cuối — section Docling).

**Commit exists:**
- ✅ `git log --oneline | grep a4af6ae` → `a4af6ae feat(rag): DoclingExtractor HTTP client gọi /v1/process + retry exp + 3 env config [phase-3 plan-02]`.

**Build/vet clean:**
- ✅ `cd backend && go build ./...` → exit 0, no output.
- ✅ `cd backend && go vet ./...` → exit 0, no output.
- ✅ `cd backend && grep -n "_ StructuredExtractor" internal/rag/extractor/docling.go` → line 298 (compile-time assert hiện diện).
- ✅ `cd backend && grep -c "DOCLING_SERVICE_URL\|RAG_EXTRACTOR\|DOCLING_TIMEOUT_SEC" .env.example` → 4 (>= 3 spec).
- ✅ `cd backend && git diff go.mod go.sum` → rỗng (zero deps mới).

## Notes cho Plan 03-03 / 03-04 / 03-05

**Plan 03-03 (Branch pipeline) có thể chạy song song:**
- Reuse `extractor.DoclingKey` constant + `extractor.StructuredExtractor` interface (Plan 01) để branch.
- Ngay cả trước khi Plan 04 wire DI, có thể dùng MOCK service (httptest) để verify branch logic.

**Plan 03-04 (Wire pipeline + main.go DI):**
- Khởi tạo qua `extractor.NewDoclingExtractor(cfg.RAG.DoclingServiceURL, cfg.RAG.DoclingTimeoutSec)`.
- Inject `hub_code`/`doc_type` vào ctx qua `extractor.WithHubCode/WithDocType` TRƯỚC khi gọi `pipeline.Run`.
- Đường cũ KHÔNG đụng — đăng ký DoclingExtractor riêng (key `"docling"`, không qua MIME registry).

**Plan 03-05 (Unit test):**
- Mock `httptest.NewServer`, encode `processResponse` JSON.
- Test 6 case: success / 413 / 504 / network error retry / 500 retry / 500→200 recover.
- Có thể parse JSON ra DTO public-in-package (`processChunkDTO`) — plan 02 đã expose.

---

*Plan 03-02 hoàn tất: 2026-04-29 · Wave 2 Phase 3 ready · Plan 03-03/04/05 unblocked.*
