---
phase: 03-go-adapter-pipeline-wiring
plan: 03
subsystem: worker-pool
tags: [worker, timeout, context, wire-04, per-job-ctx]
status: completed
requirements: [WIRE-04]
dependency_graph:
  requires:
    - "Plan 03-02 (RAGConfig đã có 3 field Extractor/DoclingServiceURL/DoclingTimeoutSec)"
  provides:
    - "WorkerManager với per-job context.WithTimeout phân biệt theo extractor mode (cho Plan 04 bật RAG_EXTRACTOR=docling không bị treo/kill sớm)"
    - "Constructor mới NewWorkerManager(workers, pipeline, docRepo, ragCfg) — Plan 04+ dùng signature này"
    - "Pattern persist DB qua parentCtx (status/chunks/completed) — Phase 4 (CFG circuit breaker) sẽ kế thừa"
    - "2 env config JOB_TIMEOUT_DEFAULT_SEC / JOB_TIMEOUT_DOCLING_SEC (cho ops tinh chỉnh runtime)"
  affects:
    - "RAGConfig struct (+2 field cuối)"
    - "backend/cmd/server/main.go caller NewWorkerManager (+1 tham số cfg.RAG)"
tech-stack:
  added: []
  patterns:
    - "Per-job context.WithTimeout (parentCtx không timeout — chỉ jobCtx có) → worker không chết khi 1 job timeout"
    - "errors.Is(err, context.DeadlineExceeded) phân loại lỗi timeout vs lỗi khác → log + status message khác nhau"
    - "Persist kết quả/lỗi dùng parentCtx (không phải jobCtx) → đảm bảo lưu xong dù jobCtx đã expire"
    - "Defensive default trong constructor: timeout <= 0 fallback hằng số (120s/240s) — không crash khi cfg thiếu"
key-files:
  created: []
  modified:
    - backend/internal/config/config.go
    - backend/internal/worker/manager.go
    - backend/.env.example
    - backend/cmd/server/main.go
decisions:
  - "Constructor `NewWorkerManager` mở rộng signature thay vì add setter — đảm bảo timeout config bắt buộc khai báo lúc init, không bị quên runtime"
  - "Progress callback + persist DB (status/chunks/completed/UpdateStatus error) dùng parentCtx — chỉ ProcessWithChunks dùng jobCtx → tránh mất kết quả/lỗi cuối cùng vào DB khi jobCtx vừa expire"
  - "Default timeout cứng (120s/240s) trong constructor khi cfg <= 0 → bảo vệ trường hợp env thiếu hoặc cfg load lỗi (vd test inject empty struct)"
  - "KHÔNG dùng worker-global timeout — mỗi worker goroutine vẫn dùng parentCtx nguyên thuỷ; timeout chỉ áp ở scope job"
  - "Stage `backend/cmd/server/main.go` cùng commit (file untracked nguyên bản) — vì nếu chỉ stage 1 dòng caller NewWorkerManager mà file untracked thì git add sẽ commit toàn file, mà nếu không stage thì build FAIL → Rule 3 (blocking)"
metrics:
  duration: "~10 phút"
  completed: 2026-04-29
  tasks_total: 2
  tasks_completed: 2
  files_changed: 4
  commit: 6d45e54
---

# Phase 3 Plan 03: Worker pool — per-job timeout phân biệt extractor mode Summary

**One-liner:** Wave 3 Phase 3 — `WorkerManager.processJob` thêm `context.WithTimeout` per-job (240s cho `docling` / 120s cho `native`) qua 2 env mới `JOB_TIMEOUT_DOCLING_SEC` + `JOB_TIMEOUT_DEFAULT_SEC`; persist DB dùng `parentCtx` để không mất kết quả/lỗi khi `jobCtx` expire; worker pool không chết khi 1 job timeout.

## Tasks executed

| # | Task | Status | Files | Verify |
|---|------|--------|-------|--------|
| 1 | Mở rộng `RAGConfig` (+2 field JobTimeout*Sec) + `.env.example` | ✅ | `config.go`, `.env.example` | `go build ./internal/config/...` PASS |
| 2 | `WorkerManager` nhận `cfg.RAG` + `processJob` per-job ctx timeout + cập nhật caller `main.go` | ✅ | `worker/manager.go`, `cmd/server/main.go` | `go build ./...` PASS, `go vet ./...` clean |

**Verify tổng:**
- `cd backend && go build ./...` → exit 0.
- `cd backend && go vet ./...` → exit 0, no output.
- `grep -rn "JobTimeoutDoclingSec\|JobTimeoutDefaultSec" backend/internal/` → 6 match (2 declare config + 2 init config + 2 use worker).
- `grep -n "context.WithTimeout" backend/internal/worker/manager.go` → 1 match (line 121).
- `grep -n "DOCLING_SERVICE_URL\|RAG_EXTRACTOR\|DOCLING_TIMEOUT_SEC\|JOB_TIMEOUT_DEFAULT_SEC\|JOB_TIMEOUT_DOCLING_SEC" backend/.env.example` → 5+ env documented.

## Signature mới đã chốt

```go
// backend/internal/worker/manager.go
type WorkerManager struct {
    // ... fields cũ ...
    extractorMode  string        // "docling" | "native" | "auto"
    defaultTimeout time.Duration // job native
    doclingTimeout time.Duration // job docling
}

func NewWorkerManager(
    workers int,
    pipeline *rag.Pipeline,
    docRepo *repository.DocumentRepo,
    ragCfg config.RAGConfig,
) *WorkerManager
```

**Caller đã update:** `backend/cmd/server/main.go:330`
```go
workerMgr = worker.NewWorkerManager(cfg.RAG.WorkerCount, pipeline, docRepo, cfg.RAG)
```

## Logic per-job timeout

```go
// processJob(parentCtx, job)
timeout := m.defaultTimeout         // 120s default
if m.extractorMode == "docling" {
    timeout = m.doclingTimeout      // 240s docling
}
jobCtx, cancel := context.WithTimeout(parentCtx, timeout)
defer cancel()

result, chunkResults, err := m.pipeline.ProcessWithChunks(jobCtx, ...)
if err != nil {
    if errors.Is(err, context.DeadlineExceeded) {
        errMsg = fmt.Sprintf("job timeout after %s (extractor=%s)", timeout, m.extractorMode)
    } else {
        errMsg = err.Error()
    }
    m.docRepo.UpdateStatus(parentCtx, docID, "error", &errMsg)  // parentCtx!
    return
}
```

**Phân chia ctx:**

| Phase | Context dùng | Lý do |
|---|---|---|
| `UpdateStatus("processing")` đầu vào | `parentCtx` | Pre-pipeline, không cần timeout job |
| `SetProgressFunc` callback | `parentCtx` | Postgres write nhanh, không nên cắt cùng job timeout |
| `pipeline.ProcessWithChunks` | `jobCtx` (timeout) | Đối tượng chính cần áp timeout |
| `UpdateStatus("error", ...)` sau lỗi | `parentCtx` | jobCtx đã expire → cần ctx khác để persist lỗi |
| `BatchInsertChunks` | `parentCtx` | Persist kết quả thành công, không bị cắt |
| `UpdateStatus("error", chunk-fail)` | `parentCtx` | Tương tự |
| `UpdateCompleted` | `parentCtx` | Tương tự |

## 2 env mới

| Env | Default | Áp dụng khi |
|---|---|---|
| `JOB_TIMEOUT_DEFAULT_SEC` | `120` | `RAG_EXTRACTOR=native` (extract Go in-process — PDF/DOCX vài MB đủ trong 2 phút) |
| `JOB_TIMEOUT_DOCLING_SEC` | `240` | `RAG_EXTRACTOR=docling` (HTTP gọi sidecar; 180s server + 60s buffer cho retry exp 1s+2s+4s + multipart upload) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Phải stage `backend/cmd/server/main.go` cùng commit**
- **Found during:** Task 2 sau khi sửa caller.
- **Issue:** `backend/cmd/server/main.go` là file untracked toàn bộ (Plan 02 commit `a4af6ae` không stage file này theo notes "backend/ untracked toàn bộ"). Nếu chỉ commit 3 file kia → build sẽ FAIL trên branch chính vì caller `NewWorkerManager(workers, pipeline, docRepo)` dùng signature cũ trong khi định nghĩa đã 4 tham số.
- **Fix:** Stage cả `backend/cmd/server/main.go` cùng commit (toàn file vì untracked) — đây là cost không thể tránh được khi Plan 02 chưa stage file này. Build PASS sau khi commit.
- **Files modified:** `backend/cmd/server/main.go` (caller line 330: thêm `cfg.RAG`).
- **Commit:** `6d45e54`.

### KHÔNG tự ý làm

- KHÔNG đụng 7 file extractor Go cũ (`pdf.go`, `docx.go`, `xlsx.go`, `pptx.go`, `csv.go`, `html.go`, `text.go`) — vẫn untracked, đợi Plan 04 wire pipeline.
- KHÔNG modify `pipeline.go` — Plan 04 (Wave 4 Wire) sẽ làm.
- KHÔNG tạo unit test `manager_test.go` — Plan 05 (Wave 5 Test) đã có scope riêng cho test mock httptest cho Docling.
- KHÔNG `git add .` — chỉ stage 4 file thuộc plan.
- KHÔNG fix concerns pre-existing (`.gitignore`, `chroma_data/`, `backend/keys/*.json`) — milestone hardening.

## Authentication gates

Không có. Plan thuần code Go local + viết file env example.

## Self-Check: PASSED

**Files modified exist:**
- ✅ `backend/internal/config/config.go` (modified, +2 field RAGConfig + 2 dòng `Atoi` + 2 dòng struct init).
- ✅ `backend/internal/worker/manager.go` (modified, +3 field struct + signature constructor mới + processJob refactor parentCtx/jobCtx).
- ✅ `backend/.env.example` (modified, +6 dòng cuối — block JOB_TIMEOUT_*).
- ✅ `backend/cmd/server/main.go` (caller line 330 thêm `cfg.RAG`).

**Commit exists:**
- ✅ `git log --oneline | grep 6d45e54` → `6d45e54 feat(worker): per-job timeout phân biệt extractor mode (docling 240s / native 120s) [phase-3 plan-03]`.

**Build/vet clean:**
- ✅ `cd backend && go build ./...` → exit 0.
- ✅ `cd backend && go vet ./...` → exit 0.
- ✅ `grep -rn "JobTimeoutDoclingSec\|JobTimeoutDefaultSec" backend/internal/` → 6 match (vượt spec 4).
- ✅ `grep -n "context.WithTimeout" backend/internal/worker/manager.go` → 1 match (line 121).

## Notes cho Plan 03-04 / 03-05

**Plan 03-04 (Wire pipeline + main.go DI):**
- KHÔNG cần đụng `worker/manager.go` nữa — signature đã sẵn sàng nhận `cfg.RAG`.
- Khi tạo `DoclingExtractor` qua `extractor.NewDoclingExtractor(cfg.RAG.DoclingServiceURL, cfg.RAG.DoclingTimeoutSec)` rồi pass vào `pipeline`, worker sẽ tự dùng đúng timeout 240s khi `cfg.RAG.Extractor == "docling"`.
- Pipeline branch logic (Plan 04) chỉ ảnh hưởng path bên trong `ProcessWithChunks` — worker timeout đã isolate.

**Plan 03-05 (Unit test):**
- Có thể test `WorkerManager.processJob` với mock pipeline trả `context.DeadlineExceeded` → assert `UpdateStatus` được gọi với message `"job timeout after Xs (extractor=...)"`.
- Cần inject `repository.DocumentRepo` mock — tham khảo signature `UpdateStatus(ctx, docID, status, *errMsg)`.

**Phase 4 (CFG circuit breaker):**
- Khi mode `auto`: timeout chọn theo extractor đang active runtime (không chỉ static `cfg.RAG.Extractor`). Có thể cần thêm getter `m.SetExtractorMode(string)` để hot-swap → defer Phase 4 design.

---

*Plan 03-03 hoàn tất: 2026-04-29 · Wave 3 Phase 3 ready · Plan 03-04 (Wire pipeline) + Plan 03-05 (Unit test) unblocked.*
