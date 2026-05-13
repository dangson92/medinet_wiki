---
phase: 03-go-adapter-pipeline-wiring
plan: 04
subsystem: rag-pipeline-wiring
tags: [WIRE-03, WIRE-05, WIRE-06, CHUNK-05, EXTRACT-05]
status: completed
completed_at: "2026-04-29"
duration_min: ~12
commit: e541c11
dependency_graph:
  requires:
    - "03-01 (StructuredExtractor interface)"
    - "03-02 (DoclingExtractor adapter + WithHubCode/WithDocType)"
    - "03-03 (NewWorkerManager signature mới với ragCfg)"
  provides:
    - "Pipeline branch RAG_EXTRACTOR=docling/native runtime"
    - "End-to-end flow upload → worker → pipeline → Docling sidecar (mode=docling)"
    - "request_id propagate xuyên suốt handler → service → worker → DoclingExtractor → HTTP header"
    - "Docling chunk metadata persist xuống Postgres JSONB document_chunks.metadata"
  affects:
    - "Plan 03-05 (unit test mock httptest sẽ verify retry + header propagation)"
    - "Phase 4 CFG-01..05 (circuit breaker auto fallback sẽ build trên branch logic này)"
    - "Phase 5 EVAL-02..05 (eval scripts query qua metadata.is_table / metadata.headers)"
tech_stack:
  added: []
  patterns:
    - "Type assertion + mode flag để branch (cfg.RAG.Extractor == 'docling' && p.doclingExt != nil)"
    - "Helper chung extractAndChunk() dùng cho cả Process + ProcessWithChunks (DRY)"
    - "context.WithValue propagate hub_code/doc_type/request_id qua các layer"
    - "Backward-compat: setter optional (SetDoclingExtractor) — không phá NewPipeline signature cũ"
key_files:
  created: []
  modified:
    - backend/internal/rag/pipeline.go
    - backend/internal/worker/manager.go
    - backend/internal/service/document_service.go
    - backend/cmd/server/main.go
decisions:
  - "Helper extractAndChunk dùng chung Process + ProcessWithChunks — tránh duplicate branch logic 2 chỗ"
  - "dbMeta merge FULL metadata Docling (kể cả []float64 bbox) — JSONB chấp nhận mọi type, không lose data"
  - "Chroma metadata SKIP []float64 — Chroma chỉ filter scalar, bbox không có ý nghĩa filter"
  - "Worker auto-gen UUID khi job.RequestID trống — đảm bảo legacy/retry job vẫn có trace"
  - "DI Docling unconditional ở main.go — mode != 'docling' KHÔNG dispatch (an toàn, không cần if)"
metrics:
  tasks_completed: 3
  files_modified: 4
  loc_added: ~80 (4 file)
  build_time_sec: <2
---

# Phase 3 Plan 04: Wire pipeline branch RAG_EXTRACTOR + DI Docling Summary

## One-liner

Branch `pipeline.go` theo `cfg.RAG.Extractor` (docling/native) qua helper `extractAndChunk()`, propagate `request_id` xuyên handler → service → worker → DoclingExtractor, map full Docling metadata (headers/page_start/is_table/table_html/bbox/caption) vào Postgres JSONB `document_chunks.metadata`, DI `DoclingExtractor` ở `main.go` qua method `SetDoclingExtractor`.

## Vị trí branch trong pipeline.go

**Helper mới `extractAndChunk(ctx, docID, docName, filePath, fileType, hubCode) ([]chunker.Chunk, error)`:**

```go
// pipeline.go (sau SetDoclingExtractor)
if p.extractorMode == "docling" && p.doclingExt != nil {
    callCtx := extractor.WithHubCode(ctx, hubCode)
    callCtx = extractor.WithDocType(callCtx, fileType)
    _, preChunks, err := p.doclingExt.ExtractStructured(callCtx, filePath)
    // ... validate len(preChunks) > 0
    slog.Info("skipping Go chunker, using Docling preChunks",
        "doc_id", docID, "doc_name", docName, "items", len(preChunks))
    // augmenter Go vẫn chạy (Q&A enrichment không phụ thuộc nguồn)
    return preChunks, nil
}
// đường cũ: extractor.ForType(fileType) → ext.Extract() → sanitizeText → chunker.Chunk()
```

**Cả `Process()` và `ProcessWithChunks()`** đều thay đoạn extract+chunk inline cũ bằng 1 dòng:

```go
chunks, err := p.extractAndChunk(ctx, docID, docName, filePath, fileType, hubCode)
```

→ DRY, single source of truth cho branch logic.

## Pattern propagate request_id

```
Gin handler (X-Request-Id header / auto-gen UUID)
  ↓ middleware.RequestID set Gin context key "request_id"
DocumentService.Upload(ctx) / DocumentService.Compose(ctx)
  ↓ workerMgr.Enqueue(EmbedJob{ ..., RequestID: requestid.From(ctx) })
WorkerManager.processJob(parentCtx, job)
  ↓ rid := job.RequestID; if rid == "" { rid = uuid.NewString() }
  ↓ jobCtx = requestid.With(jobCtx, rid)
Pipeline.ProcessWithChunks(jobCtx, ...)
  ↓ extractAndChunk → callCtx (hub_code, doc_type) — vẫn giữ rid
DoclingExtractor.ExtractStructured(callCtx, filePath)
  ↓ rid := requestid.From(ctx)
  ↓ req.Header.Set("X-Request-Id", rid)
docling-pipeline FastAPI sidecar
```

→ Tracing end-to-end Go ↔ Python qua 1 request_id duy nhất.

## EXTRACT-05 verification

**Lệnh chạy trước commit:**

```bash
git diff --stat backend/internal/rag/extractor/pdf.go \
                backend/internal/rag/extractor/docx.go \
                backend/internal/rag/extractor/xlsx.go \
                backend/internal/rag/extractor/pptx.go \
                backend/internal/rag/extractor/csv.go \
                backend/internal/rag/extractor/html.go \
                backend/internal/rag/extractor/text.go \
                backend/internal/rag/extractor/tables.go
```

**Output:** trống (exit 0, không có dòng nào).

→ 7 file extractor Go cũ (+ `tables.go` helper) hoàn toàn KHÔNG bị đụng. Đường `RAG_EXTRACTOR=native` chạy y hệt trước Plan 03-04 (backward-compat 100%).

Chỉ 2 file trong `backend/internal/rag/extractor/` thuộc Phase 3:
- `extractor.go` — Plan 03-01 (thêm `StructuredExtractor` interface).
- `docling.go` — Plan 03-02 (DoclingExtractor adapter).

## Verification chạy thật

| Check | Lệnh | Kết quả |
|---|---|---|
| Build | `cd backend && go build ./...` | PASS (no output) |
| Vet | `cd backend && go vet ./...` | PASS (no output) |
| Log marker | `grep -c "skipping Go chunker, using Docling preChunks" backend/internal/rag/pipeline.go` | 1 |
| RequestID 2 callsite | `grep -c "RequestID:" backend/internal/service/document_service.go` | 2 |
| RequestID worker | `grep -c "RequestID" backend/internal/worker/manager.go` | 3 (struct field + comment + assignment) |
| EXTRACT-05 | `git diff --stat` 8 file extractor cũ | trống ✓ |

## Smoke test thủ công (defer)

Khi infra Docling sidecar lên + có `.env` đầy đủ, smoke flow:

```bash
# 1. Start Docling sidecar (Phase 2)
cd docling-pipeline && docker compose up -d

# 2. Set env Go backend
export RAG_EXTRACTOR=docling
export DOCLING_SERVICE_URL=http://localhost:8001
export DOCLING_TIMEOUT_SEC=180
export JOB_TIMEOUT_DOCLING_SEC=240

# 3. Start Go backend
cd backend && make run

# 4. Upload 1 file PDF qua API
curl -X POST http://localhost:8080/api/documents/upload \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-Request-Id: smoke-test-$(date +%s)" \
    -F "file=@eval/dataset/pdf/sample-vi.pdf" \
    -F "hub_id=$HUB_ID"

# 5. Verify log
#    Go log:  "skipping Go chunker, using Docling preChunks" items=N
#    Python log: matching X-Request-Id smoke-test-<timestamp>
#    Postgres: SELECT metadata FROM document_chunks WHERE document_id=... LIMIT 1;
#       → JSON có headers, page_start, is_table, source='docling'
```

→ Defer Phase 4-5 vì cần Docling sidecar chạy thật.

## Note cho Plan 03-05 (unit test mock)

Plan 05 cần test 5 case mock trên `DoclingExtractor` (file `backend/internal/rag/extractor/docling_test.go`):

1. **Success 200** — multipart parse, response 1 chunk → `ExtractStructured` trả `(text, []chunker.Chunk{...}, nil)` đúng map metadata.
2. **413 Payload Too Large** — KHÔNG retry, trả error wrap `docling client error`.
3. **504 Gateway Timeout** — KHÔNG retry, trả `docling timeout`.
4. **5xx server error** — retry exponential 1s, 2s (max 3 attempts). Mock count requests = 3.
5. **Network error (Do() trả error)** — retry như case 4.

Đặc biệt verify: mock server đọc header `X-Request-Id` = `requestid.From(ctx)` → assert exact match.

## Self-Check: PASSED

- [x] `backend/internal/rag/pipeline.go` — branch logic + helper `extractAndChunk` + dbMeta merge
- [x] `backend/internal/worker/manager.go` — EmbedJob.RequestID + processJob inject `requestid.With`
- [x] `backend/internal/service/document_service.go` — 2 callsite Enqueue có `RequestID: requestid.From(ctx)`
- [x] `backend/cmd/server/main.go` — DI `extractor.NewDoclingExtractor` + `SetDoclingExtractor` + log mode
- [x] Commit `e541c11` exists trong git log
- [x] EXTRACT-05: 8 file extractor cũ git diff --stat trống
- [x] `go build ./...` PASS, `go vet ./...` PASS
