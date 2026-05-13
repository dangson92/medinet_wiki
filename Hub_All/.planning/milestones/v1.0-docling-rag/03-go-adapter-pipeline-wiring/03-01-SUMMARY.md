---
phase: 03-go-adapter-pipeline-wiring
plan: 01
subsystem: rag-extractor + middleware
tags: [interface, middleware, requestid, foundation]
status: completed
requirements: [WIRE-02, WIRE-06]
dependency_graph:
  requires: []
  provides:
    - "Interface StructuredExtractor (cho Plan 03-02 DoclingExtractor implement)"
    - "Middleware RequestID + helper requestid.From/With (cho Plan 03-02 propagate X-Request-Id sang Docling sidecar)"
  affects:
    - "backend/internal/router/router.go middleware chain (insert vị trí thứ 2)"
tech-stack:
  added: []
  patterns:
    - "Extension interface qua embed (StructuredExtractor embed Extractor)"
    - "Type assertion branch ở pipeline.go (sẽ dùng ở Plan 03-03)"
    - "ctxKey private struct cho context.Value (tránh collision)"
key-files:
  created:
    - backend/internal/middleware/request_id.go
    - backend/internal/pkg/requestid/requestid.go
  modified:
    - backend/internal/rag/extractor/extractor.go
    - backend/internal/router/router.go
decisions:
  - "Reuse `github.com/google/uuid` v1.6.0 đã có trong go.mod — KHÔNG add dep mới"
  - "ctxKey private struct cho With(); string Key cho Gin context (vì Gin tự dùng string key)"
  - "From() check cả 3 nguồn: gin.Context.Get(Key), ctx.Value(ctxKey{}), ctx.Value(Key) — robust với mọi pattern propagate"
metrics:
  duration: "~10 phút"
  completed: 2026-04-29
  tasks_total: 3
  tasks_completed: 3
  files_changed: 4
  commit: 77211fb
---

# Phase 3 Plan 01: Interface StructuredExtractor + Middleware RequestID — Summary

**One-liner:** Đặt nền móng Wave 1 Phase 3 — extension interface `StructuredExtractor` cho Docling pre-chunks + middleware Gin `RequestID` auto-gen UUID v4 + helper `requestid.From/With` cho cross-service tracing Go ↔ docling-pipeline.

## Tasks executed

| # | Task | Status | Files | Verify |
|---|------|--------|-------|--------|
| 1 | Thêm interface `StructuredExtractor` vào `extractor.go` | ✅ | `extractor.go` modify | `grep "type StructuredExtractor interface"` ra 1 dòng (line 30); `go build ./internal/rag/...` PASS |
| 2 | Tạo middleware `request_id.go` + helper `pkg/requestid/requestid.go` | ✅ | 2 file mới | `go build ./internal/middleware/... ./internal/pkg/requestid/...` PASS |
| 3 | Wire `middleware.RequestID()` vào router chain | ✅ | `router.go` modify | `grep "middleware.RequestID()"` ra 1 dòng (line 63), đứng giữa Recovery (62) và SecurityHeaders (64) |

**Verify tổng:** `cd backend && go build ./...` ✅ clean · `cd backend && go vet ./...` ✅ clean (no warning).

## Interface signature đã chốt

```go
// backend/internal/rag/extractor/extractor.go
type StructuredExtractor interface {
    Extractor
    ExtractStructured(ctx context.Context, filePath string) (text string, preChunks []chunker.Chunk, err error)
}
```

- Embed `Extractor` cũ → implementor (`DoclingExtractor` ở Plan 03-02) phải có cả `Extract()` + `SupportedType()`.
- Trả về `text string` (Markdown gộp) + `preChunks []chunker.Chunk` (đã chunked sẵn từ Docling HybridChunker).
- Pipeline `branch` qua type assertion `extractor.(StructuredExtractor)` ở Plan 03-03.

## Helper API đã chốt (cho Plan 03-02 dùng)

```go
// backend/internal/pkg/requestid/requestid.go
const Key = "request_id"
const HeaderName = "X-Request-Id"

func From(ctx context.Context) string                  // Lấy rid từ Gin/context
func With(ctx context.Context, rid string) context.Context  // Gắn rid vào ctx (worker pool)
```

**Cách Plan 03-02 dùng trong `DoclingExtractor`:**
```go
import "github.com/medinet/hub-all-backend/internal/pkg/requestid"

if rid := requestid.From(ctx); rid != "" {
    req.Header.Set(requestid.HeaderName, rid)  // → "X-Request-Id"
}
```

## Vị trí middleware trong router chain

```go
r.Use(middleware.Recovery())      // 1. catch panic
r.Use(middleware.RequestID())     // 2. ★ MỚI — auto-gen X-Request-Id
r.Use(middleware.SecurityHeaders())// 3.
r.Use(middleware.CORS(...))        // 4.
r.Use(middleware.RateLimit(...))   // 5.
r.Use(gzip.Gzip(...))              // 6.
```

Lý do thứ tự: Recovery vẫn đứng đầu để catch panic kể cả khi RequestID lỗi; RequestID đứng thứ 2 để mọi log SecurityHeaders/CORS/RateLimit downstream có rid.

## Backward-compat verification (must_have #2)

- `git diff --stat backend/internal/rag/extractor/` chỉ show duy nhất `extractor.go` được sửa.
- 7 extractor Go cũ (`pdf.go`, `docx.go`, `xlsx.go`, `pptx.go`, `csv.go`, `html.go`, `text.go`, `markdown.go`) **KHÔNG bị thay đổi** — tất cả vẫn chỉ implement `Extractor` interface cũ → registry `init()` không đổi → 100% backward-compat.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Pre-existing untracked state] Toàn bộ thư mục `backend/` chưa từng commit lên git**
- **Found during:** Task 1 (khi check `git status`)
- **Issue:** Toàn bộ `backend/internal/` ở trạng thái untracked (`??`) — bao gồm cả 7 extractor Go cũ, router.go, middleware folder. Đây là tình trạng pre-existing của repo (Phase 1-2 chỉ commit `docling-pipeline/`, `eval/`, `.planning/`).
- **Fix:** Stage CHÍNH XÁC 4 file của plan (`git add` từng file một, KHÔNG `git add .`). Commit `A` (Added) chỉ 4 file mới này, KHÔNG kéo theo 7 extractor cũ + handler/service/repository khác.
- **Hệ quả:** Backend Go nếu kéo về clean repo từ commit này sẽ KHÔNG build được (vì `extractor.go` import chunker.Chunk + 7 implementor cũ chưa có). Đây là vấn đề **pre-existing** thuộc milestone "Production Hardening" (xem CONCERNS.md), KHÔNG phải scope Plan 03-01.
- **Ghi chú cho future plans:** Plan 03-02 / 03-03 cũng sẽ gặp tình trạng này — chỉ stage file của plan, KHÔNG fix backlog backend chưa-commit.
- **Files modified:** 4 file (đúng scope plan)
- **Commit:** 77211fb

### CHƯA tự ý làm

- KHÔNG tạo `.gitignore` root cho `chroma_data/` + `backend/keys/*.json` (mặc dù CONCERNS.md đã warn) — KHÔNG mix vào commit M1 theo CLAUDE.md mục 3.
- KHÔNG commit 7 extractor Go cũ — tránh kéo theo file ngoài scope.

## Authentication gates

Không có. Plan thuần code Go local.

## Self-Check: PASSED

**Files exist:**
- ✅ `backend/internal/rag/extractor/extractor.go` (modified, line 30 chứa interface)
- ✅ `backend/internal/middleware/request_id.go` (created, 28 dòng)
- ✅ `backend/internal/pkg/requestid/requestid.go` (created, 56 dòng)
- ✅ `backend/internal/router/router.go` (modified, line 63 wire middleware)

**Commit exists:**
- ✅ `git log --oneline | grep 77211fb` — `77211fb feat(rag): thêm interface StructuredExtractor + middleware RequestID + helper requestid [phase-3 plan-01]`

**Build/vet clean:**
- ✅ `cd backend && go build ./...` → exit 0, no output
- ✅ `cd backend && go vet ./...` → exit 0, no output

## Notes cho Plan 03-02 (DoclingExtractor)

1. Implement `StructuredExtractor` (embed `Extractor` — cần thêm `Extract()` + `SupportedType()` stub trả `"docling"`).
2. Import `"github.com/medinet/hub-all-backend/internal/pkg/requestid"` để dùng `requestid.From(ctx)` + `requestid.HeaderName`.
3. KHÔNG đăng ký `DoclingExtractor` vào registry `init()` của `extractor.go` (tránh import cycle vì DoclingExtractor cần `config`); tạo hàm `RegisterDocling(cfg)` riêng được gọi từ `cmd/server/main.go` ở wave sau.

---

*Plan 03-01 hoàn tất: 2026-04-29 · Wave 1 Phase 3 ready · Plan 03-02/03 có thể start song song.*
