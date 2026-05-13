# CONTEXT — Phase 4: Config Hot-Swap & Circuit Breaker

**Phase:** 4 / 5
**Milestone:** M1 — RAG Quality with Docling
**Goal:** Pipeline RAG không bao giờ đứng im khi service Docling down — fallback về extractor Go cũ tự động qua circuit breaker Redis-shared, admin có thể quan sát + force chuyển mode runtime qua `PUT /api/rag-config` không restart, mọi lần fallback đều có audit log. Đồng thời ghi nhận `extractor_used` per-document để admin truy vết chất lượng từng tài liệu và cho phép re-ingest tài liệu cũ qua endpoint admin.
**Requirements:** CFG-01..07 (7 REQ — bổ sung CFG-06, CFG-07 ngày 2026-05-04)
**Ngày discuss:** 2026-05-04 (cập nhật scope CFG-06/07: 2026-05-04)

---

## Decisions Locked

### A. Circuit breaker — `sony/gobreaker` + Redis state

**Library:** `github.com/sony/gobreaker/v2` (industry standard Go circuit breaker, ~500★, light, half-open state machine chuẩn).

**Wrapper pattern:**
```go
// backend/internal/rag/extractor/circuit.go (mới)
type DoclingCircuit struct {
    cb     *gobreaker.CircuitBreaker[*ProcessResponse]
    redis  *redis.Client
    logger *slog.Logger
}

func NewDoclingCircuit(rdb *redis.Client, threshold uint32, cooldown time.Duration) *DoclingCircuit {
    settings := gobreaker.Settings{
        Name:        "docling-extractor",
        MaxRequests: 1, // half-open: chỉ thử 1 request
        Interval:    cooldown,
        Timeout:     cooldown,
        ReadyToTrip: func(counts gobreaker.Counts) bool {
            return counts.ConsecutiveFailures >= threshold
        },
        OnStateChange: func(name string, from, to gobreaker.State) {
            // Sync state vào Redis để workers khác biết
            rdb.Set(ctx, "rag:docling:circuit:state", to.String(), 0)
            rdb.Set(ctx, "rag:docling:circuit:changed_at", time.Now().Unix(), 0)
            slog.Info("circuit state changed", "from", from, "to", to)
        },
    }
    return &DoclingCircuit{
        cb:    gobreaker.NewCircuitBreaker[*ProcessResponse](settings),
        redis: rdb,
    }
}
```

**Workflow:**
- Khi `RAG_EXTRACTOR=auto`: gọi `circuit.Execute(func() { return doclingExt.ExtractStructured(ctx, file) })`.
- Nếu `gobreaker.ErrOpenState` → fallback sang native (CFG-01 + CFG-05 audit).
- Half-open sau cooldown → 1 request thử lại; success → close, fail → open lại.
- Multi-worker share state qua `OnStateChange` Redis sync.

### B. Health check — on-demand + Redis cache 30s

**Pattern:** Lazy check chỉ khi job cần Docling. Cache result trong Redis 30s.

```go
// backend/internal/rag/extractor/docling.go thêm method
func (d *DoclingExtractor) HealthStatus(ctx context.Context) string {
    cached, _ := d.redis.Get(ctx, "rag:docling:health").Result()
    if cached != "" {
        return cached // healthy / degraded / down
    }
    
    status := d.probeHealthz(ctx) // GET /healthz, GET /readyz
    d.redis.Set(ctx, "rag:docling:health", status, 30*time.Second)
    return status
}
```

**Vì sao 30s:** đủ nhanh để phát hiện Docling crash trong 1 phút, đủ chậm để không spam /healthz mỗi job. Phù hợp với worker pool 4-8 jobs concurrent.

KHÔNG dùng background poller (rủi ro goroutine leak + thêm complexity).

### C. Audit log — reuse `audit_logs` table

**Schema reuse:** `audit_logs` đã có `action VARCHAR`, `details JSONB`, `user_id`, `timestamp`.

**Insert pattern:**
```go
// trong pipeline.go khi fallback
auditRepo.Insert(ctx, &model.AuditLogEntry{
    Action:   "rag_fallback",
    UserID:   userID, // hoặc nil nếu system
    UserName: "system",
    IsAI:     false,
    Details: map[string]any{
        "document_id":     docID,
        "reason":          "docling_circuit_open" | "docling_timeout" | "docling_error",
        "request_id":      requestid.From(ctx),
        "extractor_from":  "docling",
        "extractor_to":    "native",
        "circuit_state":   circuit.State().String(),
        "consecutive_fails": circuit.Counts().ConsecutiveFailures,
    },
})
```

**Query qua audit_handler hiện tại:** `GET /api/audit-logs?action=rag_fallback` → admin xem lịch sử fallback. Không cần endpoint mới.

### D. Env vars (CFG-01 + CFG-02)

```env
# RAG extractor mode (M1 Phase 4)
RAG_EXTRACTOR=auto                     # docling|native|auto (default: auto)
DOCLING_FAIL_THRESHOLD=3               # consecutive failures → open circuit
DOCLING_COOLDOWN_MIN=5                 # minutes in open state before half-open retry

# Docling service (đã có từ Phase 3)
DOCLING_SERVICE_URL=http://localhost:8001
DOCLING_TIMEOUT_SEC=180
DOCLING_OCR_LANGS=vie+eng              # passed via request body chunker_options
```

`DOCLING_OCR_LANGS` PHẢI propagate sang Docling sidecar qua request body field `ocr_options.langs` (Phase 2 service đã accept env override per-request).

### E. Admin endpoint extension

**`GET /api/rag-config` (existing — extend):**
```json
{
  // existing fields ...
  "extractor_mode": "auto",                                  // mới
  "docling_service_status": "healthy" | "degraded" | "down", // mới
  "docling_version": "2.91.0",                               // từ /readyz response
  "docling_circuit_state": "closed" | "half-open" | "open",  // mới
  "last_docling_error": "timeout after 180s",                // mới (last error nullable)
  "last_fallback_at": "2026-05-04T10:30:00Z"                 // mới
}
```

**`PUT /api/rag-config` (existing — extend body):**
```json
{
  // existing fields ...
  "extractor_mode": "native"  // admin force runtime — clears circuit state Redis
}
```

Khi admin PUT `extractor_mode`:
- Update env runtime (in-memory config).
- Reset circuit state in Redis (`DEL rag:docling:circuit:state`).
- Audit log `action="rag_config_change"`.

### F. Pipeline integration

**Modify `backend/internal/rag/pipeline.go`** (Phase 3 đã có branch `RAG_EXTRACTOR=docling`, bây giờ extend cho `auto`):

```go
func (p *Pipeline) extractAndChunk(ctx context.Context, file string, mode string) (text string, chunks []rag.Chunk, err error) {
    switch mode {
    case "docling":
        return p.doclingExtract(ctx, file) // hard fail nếu Docling down
    
    case "native":
        return p.nativeExtract(ctx, file) // đường cũ
    
    case "auto":
        // Try Docling qua circuit breaker
        result, err := p.doclingCircuit.Execute(ctx, func() (*ProcessResponse, error) {
            return p.doclingExtractor.ExtractStructuredRaw(ctx, file)
        })
        if err == nil {
            return result.Text, mapChunks(result.Chunks), nil
        }
        
        // Fallback native + audit
        slog.Warn("Docling failed, falling back to native", "err", err)
        p.auditFallback(ctx, file, err)
        return p.nativeExtract(ctx, file)
    }
}
```

### G. Per-document extractor tracking + Reindex (CFG-06, CFG-07 — bổ sung 2026-05-04)

#### G.1 — Lưu `extractor_used` per-document (CFG-06)

**Lựa chọn schema: cột riêng `extractor_used VARCHAR(20)` trên bảng `documents` — KHÔNG dùng JSONB metadata.**

Lý do chốt cột riêng thay vì nhúng vào `documents.metadata` JSONB:
- Bảng `documents` hiện KHÔNG có cột `metadata` (xem `001_bootstrap.up.sql:88-104`) — nếu chọn JSONB sẽ phải tạo cả cột mới + helper merge → tốn công hơn cột scalar.
- Cần index/filter dễ cho dashboard tương lai (`WHERE extractor_used='docling' AND status='completed'`) — JSONB cần GIN index hoặc `->>` cast, kém hiệu năng và khó query từ admin tool.
- UI badge "Quality: high/low" chỉ cần đọc 1 field scalar — JSONB unmarshal phía Go sẽ tốn alloc.
- Giá trị ENUM hữu hạn (`docling` | `native` | NULL) → cột scalar phù hợp hơn JSONB.

**Migration mới `009_add_extractor_used.up.sql` + `.down.sql`** (số kế tiếp sau `008_usage_rollup`):

```sql
-- 009_add_extractor_used.up.sql
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS extractor_used VARCHAR(20)
        CHECK (extractor_used IN ('docling','native'));

CREATE INDEX IF NOT EXISTS idx_documents_extractor_used ON documents(extractor_used);
COMMENT ON COLUMN documents.extractor_used IS
    'Extractor được dùng cho ingestion cuối cùng (CFG-06 M1 Phase 4). NULL = chưa ingest hoặc ingest trước M1.';
```

```sql
-- 009_add_extractor_used.down.sql
DROP INDEX IF EXISTS idx_documents_extractor_used;
ALTER TABLE documents DROP COLUMN IF EXISTS extractor_used;
```

**Pipeline ghi `extractor_used` cuối stage upsert:** Trong `backend/internal/rag/pipeline.go` thêm tham số `extractorUsed string` vào `repo.UpdateCompleted(...)` (hoặc gọi method mới `repo.SetExtractorUsed(ctx, docID, "docling"|"native")` ngay trước/cùng với `UpdateCompleted`). PHẢI gọi trong CÙNG transaction (hoặc cùng batch) với `status='completed'` để tránh race khi reader đọc giữa chừng.

**Sửa model `Document`:** thêm field `ExtractorUsed *string \`json:"extractor_used,omitempty"\`` (nullable vì document cũ trước M1 không có giá trị).

**Endpoint impact:**
- `GET /api/documents` — Repo `List(...)` phải SELECT thêm `extractor_used`; response auto include vì JSON tag.
- `GET /api/documents/:id` — tương tự, FindByID select thêm field.
- Frontend (KHÔNG đụng trong Phase 4) sẽ render badge sau qua `data.extractor_used`.

#### G.2 — Endpoint admin `POST /api/documents/{id}/reindex` (CFG-07)

**Spec:**
- Method: `POST /api/documents/:id/reindex` — middleware: `RequireAuth` + `RequireRole("admin")`.
- Query param: `extractor` ∈ `{docling, native, auto}` — default lấy từ `config.RAGConfig.ExtractorMode` runtime hiện tại (sau khi đã có CFG-03 hot-swap).
- Body: rỗng (không cần upload lại file).
- Response: `202 Accepted` với `{ "job_id": "<uuid>", "document_id": "<uuid>", "extractor": "docling" }`.
- Validation lỗi:
  - 404 nếu document không tồn tại.
  - 400 nếu document `status='processing'` hoặc `status='pending'` (đang trong queue) — tránh enqueue trùng.
  - 400 nếu `extractor` query param không thuộc enum hợp lệ.
  - 404 nếu `file_path` không truy cập được (remote storage fail VÀ local fallback fail) — log + trả lỗi rõ.

**Reindex flow (gọi từ service `DocumentService.Reindex(ctx, docID, extractor)`):**

1. Lookup document qua `docRepo.FindByID`.
2. Lookup hub để biết `Code` + `ChromaCollection`.
3. **Resolve file path:** reuse logic `GetFile(...)` để lấy `io.ReadCloser` → ghi xuống lại temp local nếu file_path không phải local (vì pipeline cần local path để đọc lặp). KHÔNG re-upload remote storage (file đã có sẵn ở GDrive/local — tiết kiệm bandwidth, KHÔNG đổi `documents.file_path`).
4. Reset trạng thái: `docRepo.UpdateStatus(docID, 'pending', nil)` + `docRepo.UpdateProgress(docID, 0)` + clear `extractor_used` về NULL (hoặc giữ giá trị cũ — chốt: clear NULL để chỉ rõ "đang re-index, chưa biết extractor mới"). Đồng thời `docRepo.DeleteChunksByDocID(docID)` (Postgres) + `vecStore.Delete(collection, {document_id: id})` (ChromaDB).
5. Enqueue job mới qua `workerMgr.Enqueue(worker.EmbedJob{...})` với field MỚI `IsReindex: true` và `ForcedExtractor: extractor` (string, optional). Worker khi thấy `ForcedExtractor != ""` thì dùng giá trị này thay vì global `RAGConfig.ExtractorMode` cho job này.
6. Audit log `action="document_reindex"` với details `{document_id, requested_by, extractor_param, request_id}`.
7. Trả `job_id` (= `docID.String()` vì worker đã định danh job theo doc) + 202.

**Chốt thiết kế quan trọng:**
- **Reuse `worker.EmbedJob` + thêm 2 field optional** (`IsReindex bool`, `ForcedExtractor string`) — KHÔNG tạo job type riêng để giữ pipeline đơn giản.
- **KHÔNG re-upload file:** reuse `file_path` đã lưu trong `documents` (GDrive ID hoặc local path). Service `Reindex` chỉ cần đảm bảo có local copy cho extractor đọc — nếu file_path đã là local thì dùng trực tiếp; nếu là GDrive ID thì download xuống `uploadDir/<hub.Code>/<docID>/<name>` (cùng convention với `Upload`).
- **Xóa chunks cũ TRƯỚC khi enqueue** — tránh trường hợp job mới fail giữa chừng để lại chunks cũ + chunks mới lẫn lộn. Pipeline mới chạy từ trạng thái sạch.
- **Endpoint trả 202 ngay** (async job) — không block HTTP request chờ pipeline xong (có thể mất phút với file lớn + Docling OCR).

**Audit log entry mẫu:**
```go
auditRepo.Insert(ctx, &model.AuditLogEntry{
    Action:   "document_reindex",
    UserID:   adminUserID,
    UserName: adminEmail,
    IsAI:     false,
    Details: map[string]any{
        "document_id":      docID.String(),
        "extractor_param":  extractor,            // "docling"|"native"|"auto"
        "previous_extractor": previousExtractorUsed, // nullable
        "request_id":       requestid.From(ctx),
    },
})
```

#### G.3 — Tương tác với circuit breaker

Khi `extractor=auto` được truyền vào reindex job, vẫn đi qua `DoclingCircuit.Execute(...)` như flow upload bình thường — không có ngoại lệ. Nếu admin muốn force `docling` ngay cả khi circuit đang `open` → có thể gọi PUT /api/rag-config trước để reset circuit, rồi POST reindex với `extractor=docling`.

#### G.4 — Tổng hợp file impact (CFG-06 + CFG-07)

| File | Hành động | REQ |
|---|---|---|
| `backend/internal/database/migrations/009_add_extractor_used.up.sql` | NEW | CFG-06 |
| `backend/internal/database/migrations/009_add_extractor_used.down.sql` | NEW | CFG-06 |
| `backend/internal/model/document.go` | + `ExtractorUsed *string` | CFG-06 |
| `backend/internal/repository/document_repo.go` | + `SetExtractorUsed(ctx, id, value)`; SELECT thêm cột trong `List`/`FindByID`; INSERT nullable trong `Create` | CFG-06 + CFG-07 |
| `backend/internal/rag/pipeline.go` | Cuối Process: gọi `SetExtractorUsed(ctx, docID, used)` ngay trước hoặc cùng `UpdateCompleted`. Đọc `job.ForcedExtractor` để override mode nếu non-empty. | CFG-06 + CFG-07 |
| `backend/internal/worker/manager.go` (hoặc nơi định nghĩa `EmbedJob`) | + 2 field optional `IsReindex bool`, `ForcedExtractor string` | CFG-07 |
| `backend/internal/service/document_service.go` | + `Reindex(ctx, id, extractor) (jobID string, err error)` | CFG-07 |
| `backend/internal/handler/document_handler.go` | + handler `Reindex(c)` với validate query param + role check (qua middleware) | CFG-07 |
| `backend/internal/router/router.go` | Thêm route `documents.POST("/:id/reindex", middleware.RequireRole("admin"), docHandler.Reindex)` | CFG-07 |

---

## Implementation Tasks (planner sẽ decompose)

### CFG-01 — Env `RAG_EXTRACTOR=docling|native|auto` + circuit breaker

File: `backend/internal/rag/extractor/circuit.go` (mới).
- `DoclingCircuit` wrapper qua `sony/gobreaker/v2`.
- Threshold + cooldown từ env `DOCLING_FAIL_THRESHOLD`, `DOCLING_COOLDOWN_MIN`.

File: `backend/internal/config/config.go` (extend RAGConfig).
- Thêm 2 field: `DoclingFailThreshold uint32`, `DoclingCooldownMin int`.

File: `backend/internal/rag/pipeline.go` (modify branch — extend `auto` mode).

### CFG-02 — Env vars (đã có Phase 3) + DOCLING_OCR_LANGS propagate

File: `backend/.env.example` (extend Docling section).
- Thêm `DOCLING_OCR_LANGS=vie+eng`, `DOCLING_FAIL_THRESHOLD=3`, `DOCLING_COOLDOWN_MIN=5`.

File: `backend/internal/rag/extractor/docling.go` (modify `ExtractStructured`).
- Pass `ocr_options.langs` trong request body multipart field `chunker_options` (JSON).

### CFG-03 — Admin endpoint extension

File: `backend/internal/router/router.go` (modify GET + PUT `/api/rag-config`).
- GET response thêm 5 field mới.
- PUT body accept `extractor_mode` field (validate `docling|native|auto`), update in-memory config, reset Redis circuit state, audit log.

### CFG-04 — Circuit breaker state Redis

File: `backend/internal/rag/extractor/circuit.go` (mục A).
- `OnStateChange` callback sync state Redis.
- Keys: `rag:docling:circuit:state`, `rag:docling:circuit:changed_at`, `rag:docling:circuit:fail_count`.
- Workers READ state Redis lúc startup để có same view.

### CFG-05 — Audit log fallback

File: `backend/internal/rag/pipeline.go` (modify `auditFallback` helper).
- Insert qua `audit_repo` với `action="rag_fallback"` + details JSONB.

### CFG-06 — `extractor_used` per-document

Xem mục G.1. Plan 04-05 Task 1 + Task 2.

### CFG-07 — Endpoint admin reindex

Xem mục G.2. Plan 04-05 Task 3.

---

## Out of Scope Phase 4 (defer)

- ❌ Eval scripts — Phase 5.
- ❌ MCP endpoint — milestone sau.
- ❌ UI cho admin xem circuit state visual — defer (admin dùng API hoặc Settings page hiện tại).
- ❌ UI badge "Quality: high/low" — backend trả field, frontend wire ở milestone hardening / M2.
- ❌ Bulk reindex (reindex nhiều document một lần) — defer M2.
- ❌ Notification (email/Slack) khi circuit open — defer M2.
- ❌ Circuit breaker cho embedding (OpenAI/Gemini) — chỉ Docling trong M1.
- ❌ Multiple Docling instances + load balancing — M3 horizontal scaling.

## Test strategy Phase 4

**Unit test mock circuit:**
- `pipeline_circuit_test.go` test các state transition: closed → open (sau N fails) → half-open → closed/open.
- Verify fallback trigger khi circuit open.

**Unit test reindex endpoint (Plan 04-05 Task bonus):**
- `document_reindex_test.go` test 4 case: happy path 202 + audit log, document not found 404, role không phải admin 403, extractor query param invalid 400.
- Dùng JWT thật ký bằng test jwtManager (helper từ Plan 04-04 W5), miniredis, test DB Postgres (hoặc pgxmock).

**Integration test deferred:** cần Docling service real để test end-to-end fallback.

---

## Gray Areas đã decide bằng default (không thảo luận)

- Audit details JSONB schema chốt.
- Redis key naming convention: `rag:docling:*`.
- DOCLING_FAIL_THRESHOLD default 3, COOLDOWN_MIN default 5 (theo REQ).
- `gobreaker` v2 (latest, generic types support).
- Migration number 009 (kế tiếp 008_usage_rollup).
- Reindex giữ `documents.file_path` cũ nguyên — KHÔNG re-upload remote.
- Reindex clear `extractor_used` về NULL ngay khi reset status='pending', set lại khi job complete.
- `worker.EmbedJob` extend 2 field optional, KHÔNG tạo job type riêng cho reindex.

## Deferred Ideas (cho roadmap backlog)

- 999.8 — Circuit breaker cho embedding providers (OpenAI/Gemini fallback giữa nhau).
- 999.9 — UI admin dashboard hiển thị circuit state real-time (WebSocket).
- 999.10 — Multi-instance Docling + load balancer (horizontal scaling).
- 999.11 — Bulk reindex endpoint `POST /api/documents/reindex` với filter (hub_id, extractor_used='native', date range).
- 999.12 — UI badge chất lượng cho document list (frontend M2).
- 999.13 — Auto-reindex job nightly cho document có `extractor_used='native'` khi Docling lại healthy (best-effort upgrade chất lượng).

## Rủi ro & Câu hỏi mở

- **Rủi ro 1:** Khi admin PUT `extractor_mode=native`, jobs đang in-flight với `auto` mode chưa biết → vẫn dùng circuit. Mitigation: chấp nhận eventual consistency, in-flight jobs hoàn tất sau ~vài giây.
- **Rủi ro 2:** Multi-worker share state Redis có race condition khi update fail_count đồng thời. Mitigation: dùng `INCR` atomic Redis, không read-modify-write.
- **Rủi ro 3:** `audit_logs` table không có index trên `action` → query `WHERE action='rag_fallback'` slow khi nhiều log. Mitigation: defer migration index → milestone hardening.
- **Rủi ro 4 (CFG-07):** Reindex một file 50MB scanned PDF với Docling OCR có thể chiếm slot worker rất lâu, block các job upload mới. Mitigation: worker pool đã có per-job timeout (`JOB_TIMEOUT_DOCLING_SEC` từ Phase 3) — reindex đi cùng cơ chế đó. Defer priority queue sang M2 nếu thấy hiện tượng nghẽn thật.
- **Rủi ro 5 (CFG-07):** Nếu reindex thất bại giữa chừng → document để `status='processing'` hoặc `error` mà chunks đã bị xóa → search không còn ra document đó. Mitigation: chấp nhận trade-off, admin thấy `status='error'` thì retry. Document list vẫn hiện document (metadata còn) — chỉ search miss.
- **Rủi ro 6 (CFG-06):** Document cũ trước M1 sẽ có `extractor_used=NULL` → UI cần xử lý null gracefully (hiển thị "Unknown" thay vì crash). Mitigation: ghi rõ trong note backend response, frontend wire ở milestone sau.

---

## Downstream

**gsd-planner Phase 4 sẽ đọc CONTEXT này để biết:**
- Add 1 dep `sony/gobreaker/v2` vào `go.mod`.
- 1 file mới `circuit.go`, modify 4 file (config.go, pipeline.go, docling.go, router.go) — Plan 04-01..04-04.
- Plan 04-05 (NEW): migration 009 + model/repo/pipeline cho `extractor_used` + endpoint reindex.
- Audit reuse existing `audit_repo.Insert(...)`.
- Health check on-demand pattern.

---

*Last updated: 2026-05-04 (bổ sung Section G — CFG-06 + CFG-07).*
