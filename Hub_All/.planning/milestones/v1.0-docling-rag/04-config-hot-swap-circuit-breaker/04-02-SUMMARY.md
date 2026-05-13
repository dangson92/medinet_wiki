---
phase: 04-config-hot-swap-circuit-breaker
plan: 02
subsystem: rag-pipeline
tags: [rag, pipeline, circuit-breaker, audit, fallback, ocr]
requires:
  - extractor.DoclingCircuit (Plan 04-01)
  - extractor.DoclingExtractor (Phase 3)
  - repository.AuditRepo (Phase 1 brownfield)
  - requestid.From (Phase 3)
provides:
  - rag.AuditInserter interface (1-method, mock-friendly, tránh cycle import repository)
  - Pipeline.SetDoclingCircuit / SetAuditInserter / SetExtractorMode / SetDoclingOCRLangs (4 setter mới)
  - Branch "auto" trong extractAndChunk (circuit.Execute → fallback native + audit)
  - extractor.WithOCRLangs (ctx helper) + multipart field "ocr_langs" gửi cho sidecar Python
  - Pipeline.auditFallback (best-effort insert audit_logs action="rag_fallback")
  - classifyFailureReason (6 reason cố định: docling_circuit_open / half_open_busy / timeout / empty_response / client_error / error)
affects:
  - Plan 04-03 sẽ KHÔNG cần đụng pipeline.go nữa — chỉ gọi setter SetExtractorMode + circuit.Reset từ admin endpoint.
  - Plan 04-04 (test) sẽ mock AuditInserter để verify branch logic + audit payload format.
tech_stack:
  added: []
  patterns: ["circuit-breaker fallback", "audit-on-fallback (best-effort)", "interface-segregation (AuditInserter 1-method)"]
key_files:
  created: []
  modified:
    - backend/internal/rag/pipeline.go
    - backend/internal/rag/extractor/docling.go
    - backend/cmd/server/main.go
decisions:
  - "Interface AuditInserter định nghĩa trong package rag (NOT package repository) — tránh cycle import + dễ mock test."
  - "Branch 'auto' fallback BÊN TRONG extractAndChunk — không tách method riêng để giữ progress reporting + augmenter call thống nhất."
  - "auditFallback best-effort: insert lỗi chỉ log warn, KHÔNG fail pipeline (ingestion ưu tiên hơn audit hoàn hảo)."
  - "classifyFailureReason dùng errors.Is cho gobreaker errors + strings.Contains cho HTTP error message — đủ phân loại 6 nhóm cho admin grep."
  - "WithOCRLangs thêm vào docling.go ngay trong Plan 02 (không chờ Plan 03) vì pipeline.go cần symbol để build PASS — Plan 03 sẽ extend logic gửi field nếu cần thay đổi."
  - "main.go giữ biến local doclingCircuit (placeholder _ = doclingCircuit) — Plan 04-03 sẽ truyền vào router.Setup signature mở rộng."
metrics:
  duration: "~30 phút"
  completed_date: "2026-05-04"
  tasks: 2
  files: 3
  tests_added: 0
commit: 0b6079d
---

# Phase 4 Plan 02: Pipeline branch `auto` + circuit Execute + auditFallback + 4 setter + DI (CFG-01, CFG-02, CFG-05)

**One-liner:** Wire mode `RAG_EXTRACTOR=auto` vào pipeline — circuit breaker wrap Docling, fallback native + audit log khi Docling down, đồng thời gom toàn bộ thay đổi struct Pipeline (4 setter mới + interface AuditInserter) vào file này để Plan 03 không phải đụng pipeline.go nữa (theo CHECK round 1 B2).

## Mục tiêu

Wave 2 Phase 4 — core deliverable: pipeline RAG không bao giờ đứng im khi service Docling down. Plan 01 đã đặt foundation (`circuit.go` + `health.go` + 3 env mới); Plan 02 wire `circuit.Execute(...)` quanh `doclingExtractor.ExtractStructured(...)`, fallback `nativeExtract` + audit log khi `gobreaker.ErrOpenState` hoặc closure error.

## Việc đã làm

### Task 1 — `backend/internal/rag/pipeline.go` (extend toàn diện)

**Thêm import:** `encoding/json`, `errors`, `model`, `requestid`, `gobreaker/v2`.

**Thêm interface ngay đầu file:**
```go
type AuditInserter interface {
    Insert(ctx context.Context, entry *model.AuditLogEntry) error
}
```
Lý do tách interface: `*repository.AuditRepo` đã satisfy sẵn (zero adapter); test có thể mock bằng struct nhẹ (Plan 04-04); package `rag` KHÔNG import `repository` (tránh cycle).

**Extend struct Pipeline:** thêm 3 field sau `extractorMode`:
- `circuit *extractor.DoclingCircuit`
- `auditRepo AuditInserter`
- `doclingOCRLangs string` — default "vie+eng"

**4 setter mới ngay sau SetDoclingExtractor:**
- `SetDoclingCircuit(c *extractor.DoclingCircuit)` — pass nil → mode "auto" suy biến native (an toàn).
- `SetAuditInserter(r AuditInserter)` — production pass `*repository.AuditRepo`.
- `SetExtractorMode(mode string)` — hot-swap runtime, KHÔNG mutex (accept eventual consistency theo CONTEXT Rủi ro 1).
- `SetDoclingOCRLangs(langs string)` — set OCR language code cho mọi call Docling.

**Refactor `extractAndChunk`:** 3 branch rõ rệt:

```go
// Branch "auto" (mới)
if p.extractorMode == "auto" && p.doclingExt != nil && p.circuit != nil {
    callCtx := extractor.WithHubCode(ctx, hubCode)
    callCtx = extractor.WithDocType(callCtx, fileType)
    callCtx = extractor.WithOCRLangs(callCtx, p.doclingOCRLangs)

    var doclingChunks []chunker.Chunk
    cbErr := p.circuit.Execute(func() error {
        _, chunks, err := p.doclingExt.ExtractStructured(callCtx, filePath)
        if err != nil { return err }
        if len(chunks) == 0 { return fmt.Errorf("docling returned 0 chunks") }
        doclingChunks = chunks
        return nil
    })
    if cbErr == nil {
        // success → augmenter → return doclingChunks
    } else {
        // log warn + auditFallback + ĐI XUỐNG branch native bên dưới
    }
}

// Branch "docling" (hard) — giữ logic Phase 3 + thêm WithOCRLangs
// Branch "native" (default) — không đổi
```

**2 helper mới trước `sanitizeText`:**

`classifyFailureReason(err) string` — return 1 trong 6 reason:
| Trigger | Reason |
|---|---|
| `errors.Is(err, gobreaker.ErrOpenState)` | `docling_circuit_open` |
| `errors.Is(err, gobreaker.ErrTooManyRequests)` | `docling_circuit_half_open_busy` |
| msg chứa "timeout" \| "deadline" | `docling_timeout` |
| msg chứa "0 chunks" | `docling_empty_response` |
| msg chứa "client error" \| "http 4" | `docling_client_error` |
| else | `docling_error` |

`auditFallback(ctx, docID, hubCode, reason, originalErr)` — best-effort insert audit_logs:
- Lấy `request_id` qua `requestid.From(ctx)` — TUYỆT ĐỐI KHÔNG đọc raw `ctx.Value("request_id")` (W1 fix: package requestid set bằng custom ctxKey type, raw string sẽ luôn trả "").
- Payload JSONB chứa 7 field bắt buộc: `document_id`, `hub_code`, `reason`, `request_id`, `extractor_from="docling"`, `extractor_to="native"`, `error` + 2 field bonus khi `circuit != nil`: `circuit_state`, `consecutive_fails`.
- Entry: `Action="rag_fallback"`, `UserName="system"`, `IsAI=false`.
- Insert lỗi → log slog.Warn, KHÔNG fail pipeline.

**Snippet payload mẫu (audit_logs.payload JSONB):**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "hub_code": "DUOC",
  "reason": "docling_circuit_open",
  "request_id": "req-abc123",
  "extractor_from": "docling",
  "extractor_to": "native",
  "error": "circuit breaker is open",
  "circuit_state": "open",
  "consecutive_fails": 3
}
```

**Số dòng pipeline.go thêm:** ~190 dòng (1 interface + 3 field + 4 setter + branch auto trong extractAndChunk + 2 helper + branch docling thêm WithOCRLangs).

### Task 2 — `backend/internal/rag/extractor/docling.go` (thêm WithOCRLangs)

Plan 02 phải thêm sớm vì `pipeline.go` cần symbol `extractor.WithOCRLangs` để build PASS — Plan 03 (depends_on [04-01, 04-02]) chạy SAU.

**Thêm:**
- Type `ctxOCRLangsKey struct{}` (private context key).
- Helper `WithOCRLangs(ctx, langs) context.Context`.
- Trong `buildReq` của `ExtractStructured`: nếu `ctx.Value(ctxOCRLangsKey{})` non-empty → multipart field `ocr_langs` gửi cho sidecar Python.

### Task 3 — `backend/cmd/server/main.go` (DI)

Wire ngay sau `pipeline.SetDoclingExtractor`:
```go
doclingCircuit := extractor.NewDoclingCircuit(
    rdb,
    cfg.RAG.DoclingFailThreshold,
    time.Duration(cfg.RAG.DoclingCooldownMin)*time.Minute,
    slog.Default(),
)
pipeline.SetDoclingCircuit(doclingCircuit)
pipeline.SetAuditInserter(auditRepo)
pipeline.SetDoclingOCRLangs(cfg.RAG.DoclingOCRLangs)
_ = doclingCircuit // placeholder cho Plan 04-03 truyền vào router.Setup
```

Log info xác nhận: `threshold`, `cooldown_min`, `extractor_mode`, `ocr_langs`.

KHÔNG đụng signature `router.Setup()` ở plan này (theo done criteria task 2).

## Verification

| Check | Kết quả |
|---|---|
| `cd backend && go build ./...` | PASS (no output) |
| `cd backend && go vet ./...` | PASS (no output) |
| `git diff --stat backend/internal/rag/extractor/{pdf,docx,xlsx,pptx,csv,html,text,tables}.go` | EMPTY (EXTRACT-05 untouched) |
| `grep "circuit\.Execute\|auditFallback\|SetDoclingCircuit" backend/internal/rag/pipeline.go` | 6 match (4 dòng comment + 2 dòng gọi `circuit.Execute` / `auditFallback`) |
| `grep "NewDoclingCircuit\|SetDoclingCircuit\|SetAuditInserter\|SetDoclingOCRLangs" backend/cmd/server/main.go` | 4 match |
| `git diff --diff-filter=D --name-only HEAD~1 HEAD` | EMPTY (không xóa file) |

## Deviations from Plan

**1. [Rule 3 - Blocking] Thêm `extractor.WithOCRLangs` ngay trong Plan 02**
- **Found during:** Task 1 build check.
- **Issue:** Plan 02 yêu cầu pipeline.go gọi `extractor.WithOCRLangs(...)` ở 2 branch (auto + docling), nhưng plan note ở dòng 394 nói "Plan 03 sẽ thêm." Tuy nhiên Plan 03 chạy SAU Plan 02 (depends_on [04-01, 04-02]) → pipeline.go sẽ KHÔNG build PASS sau Plan 02 nếu thiếu symbol.
- **Fix:** Thêm `WithOCRLangs` + `ctxOCRLangsKey` + multipart field `ocr_langs` vào `docling.go` ngay trong Plan 02. Đây là minimal addition — Plan 03 vẫn có thể extend logic gửi field nếu cần (chưa đụng).
- **Files modified:** `backend/internal/rag/extractor/docling.go`.
- **Commit:** 0b6079d.

**Tóm lại:** Không deviation về scope hay design — chỉ pull-up 1 helper từ Plan 03 sang Plan 02 để build PASS atomically.

## Auth gates

Không có (Wave 2 thuần code wire, không runtime call).

## Known Stubs

- `_ = doclingCircuit` trong main.go là placeholder có chủ đích — Plan 04-03 sẽ truyền `doclingCircuit` vào `router.Setup(...)` cho admin endpoint `GET /api/rag-config` đọc state + `PUT /api/rag-config` reset state. Đây KHÔNG phải bug; là chuẩn wave-by-wave decoupling.

## Self-Check: PASSED

- File `backend/internal/rag/pipeline.go` modified — FOUND.
- File `backend/internal/rag/extractor/docling.go` modified — FOUND.
- File `backend/cmd/server/main.go` modified — FOUND.
- `git log --oneline | grep 0b6079d` — FOUND (`0b6079d feat(rag): pipeline branch auto ...`).
- `grep "case \"auto\"\|extractorMode == \"auto\"" backend/internal/rag/pipeline.go` — FOUND (branch logic).
- `grep "AuditInserter" backend/internal/rag/pipeline.go` — FOUND (interface + setter).
- `grep "WithOCRLangs" backend/internal/rag/extractor/docling.go backend/internal/rag/pipeline.go` — FOUND ở cả 2 file.
- `git diff --stat` cho 8 file EXTRACT-05 — EMPTY.

## Next

- **Plan 04-03 (Wave 3):** Extend `router.Setup(...)` signature thêm param `doclingCircuit *extractor.DoclingCircuit` + `healthProbe *extractor.DoclingHealthProbe` + `pipeline *rag.Pipeline`. Sửa `GET /api/rag-config` thêm 5 field (`extractor_mode`, `docling_service_status`, `docling_version`, `docling_circuit_state`, `last_docling_error`, `last_fallback_at`). Sửa `PUT /api/rag-config` accept `extractor_mode` field — gọi `pipeline.SetExtractorMode(mode)` + `circuit.Reset(ctx)` + audit log `action="rag_config_change"`. KHÔNG cần đụng pipeline.go nữa (toàn bộ setter expose sẵn ở Plan 02).
- **Plan 04-04 (Wave 4 — test):** `pipeline_circuit_test.go` — mock `AuditInserter` + circuit từ Plan 01 + miniredis, verify 4 case: success Docling / fail-fallback-audit / circuit open / mode change runtime.

---
*Last updated: 2026-05-04*
