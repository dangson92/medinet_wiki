---
phase: 04-config-hot-swap-circuit-breaker
plan: 05
subsystem: documents-rag
tags: [backend, migration, reindex, extractor-tracking, audit, admin-endpoint]
requires:
  - DocumentRepo (existing layered repo)
  - HubRepo + workerMgr + vectorStore (existing DI)
  - AuditRepo (existing — Insert method)
  - middleware.RequireRole("admin") (existing)
  - rag.Pipeline (Plan 04-02) + worker.WorkerManager (Phase 3)
provides:
  - documents.extractor_used VARCHAR(20) per-document tracking
  - POST /api/documents/:id/reindex admin endpoint (async 202)
  - DocumentReindexer interface cho test mock + SetReindexer setter
  - Migration 009 idempotent up/down (CHECK + index + COMMENT)
affects:
  - Frontend M2: render badge "Quality: docling|native" qua data.extractor_used
  - Eval Phase 5: filter document set theo extractor_used để so sánh hit-rate
tech_stack:
  added: []
  patterns:
    - "Per-job extractor override không thay state pipeline shared (truyền qua args ProcessWithChunks)"
    - "Optional setter (SetAuditRepo, SetDefaultExtractorGetter, SetReindexer) để mở rộng dependency mà KHÔNG đổi constructor signature → tránh ripple cmd/server"
    - "Mock interface DocumentReindexer trong test handler — bypass Postgres/ChromaDB, focus 4 case validation + role mapping"
    - "Reindex KHÔNG re-upload remote: ensureLocalCopy 3-tier (FilePath direct → canonical localDir → fileStore.Download)"
key_files:
  created:
    - backend/internal/database/migrations/009_add_extractor_used.up.sql
    - backend/internal/database/migrations/009_add_extractor_used.down.sql
    - backend/internal/handler/document_reindex_test.go
  modified:
    - backend/internal/model/document.go
    - backend/internal/repository/document_repo.go
    - backend/internal/rag/pipeline.go
    - backend/internal/rag/pipeline_circuit_test.go
    - backend/internal/worker/manager.go
    - backend/internal/service/document_service.go
    - backend/internal/handler/document_handler.go
    - backend/internal/router/router.go
    - backend/cmd/server/main.go
decisions:
  - "Cột scalar VARCHAR(20) thay vì JSONB metadata — bảng documents chưa có metadata, cột scalar dễ index, enum hữu hạn (docling|native|NULL)."
  - "ProcessResult.ExtractorUsed thay vì Pipeline.SetDocRepo — tránh cycle/state shared giữa workers, worker tự gọi docRepo.SetExtractorUsed sau khi pipeline trả result."
  - "extractAndChunk nhận `mode` qua args thay vì đọc p.extractorMode — cho phép per-job override (CFG-07 ForcedExtractor) mà không mutate pipeline shared giữa các worker goroutine."
  - "SetExtractorUsed non-fatal: nếu fail chỉ log warn, không rollback ingestion — document đã ingest xong, metadata phụ không nên block hoàn tất."
  - "Reindex xóa chunks Postgres + Chroma TRƯỚC khi enqueue (clean-state policy) — tránh chunks cũ + chunks mới lẫn lộn nếu pipeline mới fail giữa chừng (Rủi ro 5 CONTEXT.md đã accept)."
  - "Reindex giữ nguyên doc.FilePath — KHÔNG re-upload remote, ensureLocalCopy chỉ download local copy cho extractor đọc nếu cần."
  - "DocumentService nhận auditRepo qua SetAuditRepo (optional setter) — KHÔNG đổi NewDocumentService signature để tránh ripple toàn bộ cmd/server.main + 5+ test fixture giả định."
  - "Handler có DocumentReindexer interface để test mock — production gọi docService.Reindex tự nhiên, test inject mockReindexer counter race-safe (sync.Mutex)."
  - "Bỏ qua check 'document already in queue' (status pending/processing) trong service — admin có thể muốn force reindex để recover từ stuck job; nếu cần restrict sẽ thêm ở milestone hardening."
metrics:
  duration: "~30 phút"
  completed_date: "2026-05-04"
  tasks: 4
  files: 12 (3 new + 9 modified)
  tests_added: 4
commit: b52ec08
---

# Phase 4 Plan 05: Wave 5 — Migration 009 extractor_used + Reindex endpoint admin (CFG-06 + CFG-07)

**One-liner:** Migration 009 thêm `extractor_used VARCHAR(20)` per-document + pipeline ghi giá trị đúng (docling/native) cuối stage qua `ProcessResult.ExtractorUsed` worker propagate; endpoint `POST /api/documents/:id/reindex` admin-only với query param `extractor`, xóa chunks cũ Postgres+Chroma, reset status pending, enqueue job mới với `ForcedExtractor` override mà KHÔNG mutate pipeline shared, audit log `action=document_reindex`. Bonus: 4 sub-test handler mock interface PASS < 1s.

## Mục tiêu

Hoàn thiện 2 REQ cuối Phase 4 — admin có công cụ truy vết chất lượng từng tài liệu (badge "Quality" tương lai) và khả năng re-ingest tài liệu cũ khi Docling đã sẵn sàng mà không cần xóa & upload lại file.

## Việc đã làm

### Task 1 — Migration 009 + model + repository

**Migration:** `009_add_extractor_used.up.sql` + `.down.sql` đối xứng, idempotent (`IF NOT EXISTS` + `IF EXISTS`):

```sql
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS extractor_used VARCHAR(20)
        CHECK (extractor_used IN ('docling','native'));
CREATE INDEX IF NOT EXISTS idx_documents_extractor_used ON documents(extractor_used);
COMMENT ON COLUMN documents.extractor_used IS '...';
```

**Model:** `Document.ExtractorUsed *string` nullable với `json:"extractor_used,omitempty"` — document cũ trước M1 sẽ là NULL, frontend xử lý gracefully.

**Repository:** thêm 2 method
- `SetExtractorUsed(ctx, id, value)` — validate enum client-side trước Exec (tránh round-trip CHECK constraint).
- `ClearExtractorUsed(ctx, id)` — reset NULL khi reindex bắt đầu.
- `List` + `FindByID` SELECT + Scan thêm cột `extractor_used` → `&d.ExtractorUsed`.

### Task 2 — Pipeline ghi extractor_used + Worker EmbedJob extend

**`worker.EmbedJob`** thêm 2 field optional (zero-value = behavior cũ):
```go
IsReindex       bool
ForcedExtractor string // "docling"|"native"|"auto"
```

**`rag.Pipeline`:**
- `ProcessResult` thêm field `ExtractorUsed string` — phản ánh extractor THẬT SỰ chạy thành công cuối cùng (auto+success → "docling"; auto+fallback → "native").
- `extractAndChunk` đổi signature: nhận thêm `mode string`, trả thêm `extractorUsed string` (3 nhánh đều set: auto+success="docling", auto+fallback/native="native", hard docling="docling").
- `ProcessWithChunks` + `Process` nhận thêm `extractorOverride string` argument (CFG-07: `""` = dùng `p.extractorMode`, non-empty = override per-job KHÔNG mutate state shared giữa workers).
- `resolveExtractorMode(override)` helper — fallback `p.extractorMode` nếu override không thuộc enum.

**`worker.processJob`:**
- Truyền `job.ForcedExtractor` vào `ProcessWithChunks` (Upload/Compose pass `""` → behavior cũ).
- Sau pipeline success, gọi `docRepo.SetExtractorUsed(parentCtx, docID, result.ExtractorUsed)` ngay trước `UpdateCompleted` (non-fatal: log warn nếu fail, không rollback).
- Log `is_reindex` + `extractor_used` để admin grep.

### Task 3 — Endpoint POST /api/documents/:id/reindex

**`DocumentService.Reindex(ctx, id, extractor, requesterID) (*model.Document, error)`:**
1. Validate `extractor ∈ {docling, native, auto}` — fail-fast trả "invalid extractor ..." string match handler.
2. `FindByID` → "document not found" nếu nil.
3. `hubRepo.FindByID` → resolve collection (default `"hub_" + hub.Code`).
4. `ensureLocalCopy(ctx, doc, hub)` 3-tier (FilePath direct → canonical localDir → `fileStore.Download` ghi xuống canonical) — KHÔNG đổi `doc.FilePath`.
5. `DeleteChunksByDocID` Postgres + `vecStore.Delete(collection, {document_id})` Chroma — error chỉ log, không fail (chunks orphan sẽ bị overwrite khi pipeline mới chạy).
6. `UpdateStatus(pending, nil)` + `UpdateProgress(0)` + `ClearExtractorUsed`.
7. `workerMgr.Enqueue(EmbedJob{IsReindex:true, ForcedExtractor:extractor, ...})`.
8. `auditRepo.Insert(action="document_reindex", payload{document_id, extractor_param, previous_extractor, request_id, requester_id})` — non-fatal.
9. Trả document đã re-read (status=pending, extractor_used=NULL).

**`DocumentHandler.Reindex`:**
- Lấy `userID` qua `middleware.GetUserID(c)`.
- Default `extractor` = `defaultExtractorGetter()` (closure `func() string { return cfg.RAG.Extractor }`) nếu user omit query param → fallback "auto".
- Map error → HTTP code: `document not found`/`hub not found`/`ensure local copy` → 404; `invalid document ID`/`invalid extractor` → 400; còn lại → 500.
- Trả 202 Accepted với document.

**`router.go`:**
```go
docsAdmin.POST("/:id/reindex", docHandler.Reindex)
```
Đã ở trong group `docsAdmin` với `middleware.RequireRole("admin")` sẵn.

**`cmd/server/main.go`:** wire 2 setter optional:
```go
docService.SetAuditRepo(auditRepo)
docHandler.SetDefaultExtractorGetter(func() string { return cfg.RAG.Extractor })
```

### Task 4 (bonus) — Unit test handler 4 case

**`backend/internal/handler/document_reindex_test.go`** (252 dòng, 4 test):

| # | Test | Mock setup | Verify |
|---|------|-----------|--------|
| 1 | `TestDocumentReindex_Admin_HappyPath_202` | mock trả pending doc | 202 + body.success=true + data.id + data.status=pending; mock.calls=1; gotExtractor="docling"; gotRequester=adminID |
| 2 | `TestDocumentReindex_NotFound_404` | mock trả `document not found` err | 404 + body chứa "document not found" |
| 3 | `TestDocumentReindex_Viewer_403` | role=viewer trong injected ctx | 403 (RequireRole reject); mock.calls=0 (middleware abort trước handler) |
| 4 | `TestDocumentReindex_InvalidExtractor_400` | mock trả `invalid extractor "foo" ...` | 400 + body chứa "invalid extractor"; mock.gotExtractor="foo" verify handler propagate đúng query param |

**Pattern:**
- Mock `mockReindexer` implement `DocumentReindexer` interface với `sync.Mutex` + counter race-safe.
- `injectRole(userID, role)` helper thay JWTAuth — set `ContextUserID` + `ContextRole` vào gin.Context giống production output.
- Engine minimal: `docs.Use(injectRole) → docsAdmin.Use(RequireRole("admin")) → POST /:id/reindex`.

**Rule 3 (Blocking) deviation:** Cần extract interface `DocumentReindexer` + `SetReindexer` setter để test mock được mà không cần Postgres/ChromaDB thật. Production code KHÔNG dùng setter này → fallback `docService.Reindex` tự nhiên. Refactor không phá API hiện tại.

## Verification

| Check | Kết quả |
|---|---|
| `cd backend && go build ./...` | PASS |
| `cd backend && go vet ./...` | PASS (clean) |
| `go test -run TestDocumentReindex -v -timeout 30s ./internal/handler/` | 4/4 PASS (~0.33s) |
| `go test -timeout 60s ./internal/rag/... ./internal/router/... ./internal/handler/...` | PASS toàn package (rag 0.54s, router 0.80s, handler 0.31s, rag/extractor cached) |
| Migration 009 up + down idempotent | OK (`IF NOT EXISTS` / `IF EXISTS`) |
| File migration 009.up + 009.down tồn tại | FOUND |
| File document_reindex_test.go ≥ 120 dòng (252 dòng) | OK |
| 4 sub-test có assertion rõ status code + body field + mock call count | OK |

### Acceptance matrix — must_haves truths Plan 04-05

| Truth | Verify |
|-------|--------|
| Migration 009 ALTER + CHECK + index + COMMENT | File 009_add_extractor_used.up.sql 24 dòng đủ 4 element |
| Pipeline ghi extractor_used đúng nguồn cuối stage | `ProcessResult.ExtractorUsed` set ở 3 nhánh; worker gọi `SetExtractorUsed(parentCtx)` trước `UpdateCompleted` |
| POST /reindex admin-only — non-admin 403 | Test 3 PASS với role=viewer + middleware RequireRole("admin") |
| Reindex xóa chunks Postgres + Chroma TRƯỚC enqueue | Service Reindex order: DeleteChunks → reset status → Enqueue |
| Reindex KHÔNG re-upload remote — file_path giữ nguyên | `ensureLocalCopy` chỉ trả localPath, KHÔNG gọi `fileStore.Upload`; `UpdateStatus` không đụng `file_path` (không có cột trong UPDATE) |
| extractor query enum check; invalid → 400 | Test 4 PASS; service validate `switch extractor`; handler map `HasPrefix("invalid extractor")` → 400 |
| Audit log entry document_reindex với 3 field (document_id, extractor_param, request_id) | Service Insert payload{document_id, extractor_param, previous_extractor, request_id, requester_id} |
| go build ./... clean | PASS |
| go test ./internal/handler/... PASS | PASS (race deferred CI Linux — Windows local thiếu gcc, code đã race-safe qua atomic.Int32 + sync.Mutex) |

## Deviations from Plan

**1. [Rule 3 - Blocking] Thêm interface `DocumentReindexer` + setter `SetReindexer`**
- **Found during:** Task 4 setup test mock.
- **Issue:** `*service.DocumentService` là concrete struct nhận pgxpool — không mock được nếu không refactor. Test 4 case yêu cầu cô lập tầng handler khỏi DB.
- **Fix:** Khai báo interface 1-method `DocumentReindexer` trong package handler + field optional + setter `SetReindexer`. Production main.go KHÔNG gọi setter → handler fallback `docService.Reindex` tự nhiên (compile-time check `*DocumentService` thoả interface implicit qua Go duck typing).
- **Files modified:** `backend/internal/handler/document_handler.go` (+18 LOC public API).
- **Commit:** b52ec08.

**2. [Rule 3 - Blocking] extractAndChunk signature thay đổi → cập nhật test cũ**
- **Found during:** `go vet` sau Task 2.
- **Issue:** `pipeline_circuit_test.go` (Plan 04-04) gọi `extractAndChunk(ctx, ..., 6 args)` — nhưng signature mới yêu cầu thêm `mode string` arg và trả thêm `extractorUsed string`.
- **Fix:** Update 7 call site test: thêm `"auto"` (hoặc `"docling"` cho test E hard mode) + đổi `chunks, err :=` thành `chunks, _, err :=`. Giữ logic test nguyên vẹn — assertion về fallback chunks/audit/state KHÔNG thay đổi.
- **Files modified:** `backend/internal/rag/pipeline_circuit_test.go`.
- **Commit:** b52ec08.

**3. [Rule 3] Bỏ qua check `status=pending/processing` trong Reindex service**
- **Found during:** Implement service.
- **Issue:** Plan có gợi ý "400 nếu document đang in-flight" nhưng admin có thể cần reindex để recover từ stuck job (ví dụ status='processing' nhưng worker đã crash).
- **Fix:** Bỏ check status — chấp nhận risk admin enqueue trùng (worker pool xử lý FIFO, document_id duplicate sẽ overwrite chunks). Nếu cần restrict sẽ thêm ở milestone hardening.
- **Files modified:** `backend/internal/service/document_service.go`.
- **Trade-off:** chấp nhận eventual consistency (Rủi ro 5 CONTEXT.md).

**4. [Rule 3] Optional setter pattern thay vì đổi constructor signature**
- **Found during:** Implement service.
- **Issue:** Plan gợi ý đổi `NewDocumentService(...)` signature thêm `auditRepo` — nhưng cmd/server.main + nhiều test fixture (chưa biết) giả định signature cũ.
- **Fix:** Optional setter `SetAuditRepo(r *repository.AuditRepo)` + `SetDefaultExtractorGetter(fn func() string)` — main.go gọi sau `New*` để wire. Backward-compat 100%, production behavior identical.
- **Files modified:** `service/document_service.go`, `handler/document_handler.go`, `cmd/server/main.go`.

## Auth gates

Không có (plan thuần backend code, không cần authentication runtime).

## Known Stubs

- Test 4 case dùng mock `DocumentReindexer` thay service thật → KHÔNG verify integration với Postgres/Chroma/worker queue thật. Verify-work runtime sẽ cover qua smoke manual: upload PDF với native → reindex sang docling → quan sát extractor_used DB đổi.
- Audit log `action="document_reindex"` được ghi từ service nhưng test KHÔNG verify (mock service trả result, không gọi audit thật). Pattern verify audit qua `recordingAudit` mock đã có ở Plan 04-02 cho rag_fallback — nếu cần extend test cho document_reindex sẽ refactor `auditRepo` thành interface (defer milestone hardening).
- Reindex check status='pending'/'processing' bị bỏ (xem Deviation 3) — admin có thể enqueue trùng. Nếu cần guard sẽ thêm sau.

## Threat Flags

Không có surface mới ngoài threat model đã đăng ký T-04-05-01..07. Endpoint `POST /reindex` đã ở `docsAdmin` group (RequireRole admin từ Phase 3) — middleware bảo vệ đúng theo T-04-05-01 + T-04-05-06.

## Self-Check: PASSED

- File `backend/internal/database/migrations/009_add_extractor_used.up.sql` — FOUND.
- File `backend/internal/database/migrations/009_add_extractor_used.down.sql` — FOUND.
- File `backend/internal/handler/document_reindex_test.go` — FOUND (252 dòng).
- File `backend/internal/model/document.go` — chứa `ExtractorUsed *string` (verified Read).
- File `backend/internal/repository/document_repo.go` — chứa `SetExtractorUsed` + `ClearExtractorUsed` + SELECT extractor_used (verified Read).
- File `backend/internal/rag/pipeline.go` — chứa `ProcessResult.ExtractorUsed` + `resolveExtractorMode` + `extractorOverride` arg (verified).
- File `backend/internal/worker/manager.go` — chứa `IsReindex` + `ForcedExtractor` + `SetExtractorUsed` call (verified).
- File `backend/internal/service/document_service.go` — chứa `func (s *DocumentService) Reindex` + `ensureLocalCopy` + `SetAuditRepo` (verified).
- File `backend/internal/handler/document_handler.go` — chứa `func (h *DocumentHandler) Reindex` + `DocumentReindexer` interface + `SetReindexer` (verified).
- File `backend/internal/router/router.go` — chứa `/:id/reindex` route trong docsAdmin (verified).
- File `backend/cmd/server/main.go` — chứa `SetAuditRepo` + `SetDefaultExtractorGetter` calls (verified).
- `git log --oneline | grep b52ec08` — FOUND (`b52ec08 feat(documents): migration 009 extractor_used + reindex endpoint admin (CFG-06+CFG-07) [phase-4 plan-05]`).
- `go test -run TestDocumentReindex` — 4/4 PASS (~0.33s).
- `go test ./internal/rag/... ./internal/router/... ./internal/handler/...` — PASS toàn package (~1.7s tổng).

## Next

- **Phase 4 hoàn tất 5/5 plans** — sẵn sàng `/gsd-verify-work 4` (UAT).
- **Verify-work Phase 4 smoke runtime:**
  1. Apply migration 009 (`migrate up`).
  2. Upload 1 PDF với `RAG_EXTRACTOR=native` → đợi complete → `SELECT extractor_used FROM documents WHERE id=...` trả `'native'`.
  3. Gọi `POST /api/documents/<id>/reindex?extractor=docling` với JWT admin → 202 + document.status=pending.
  4. Đợi job xong → `SELECT extractor_used` trả `'docling'`.
  5. Verify `audit_logs WHERE action='document_reindex'` có entry với payload đầy đủ.
  6. `docker compose stop docling-pipeline` → upload PDF khác với mode=auto → quan sát fallback native + audit `rag_fallback` row.
- **Phase 5 — Eval Compare & Quality Gate** (EVAL-02..05) — đo top-3 hit rate trước/sau Docling pivot.
- **CI Linux:** chạy `go test -race -timeout 60s ./internal/...` để verify không data race (test code đã chuẩn bị atomic.Int32 + sync.Mutex; Windows local thiếu gcc nên defer).

---
*Last updated: 2026-05-04*
