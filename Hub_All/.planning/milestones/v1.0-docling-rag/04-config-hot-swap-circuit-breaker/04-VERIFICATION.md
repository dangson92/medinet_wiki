---
phase: 04-config-hot-swap-circuit-breaker
verified: 2026-04-29T00:00:00Z
status: human_needed
score: 7/7 must-haves verified (code-level) — 6/7 cần smoke runtime UAT
re_verification:
  previous_status: none
  previous_score: n/a
human_verification:
  - test: "Tắt service docling-pipeline (docker compose stop) rồi upload 1 PDF với RAG_EXTRACTOR=auto"
    expected: "Document ingest thành công bằng native; sau ≥ DOCLING_FAIL_THRESHOLD (default 3) lần lỗi liên tiếp, key Redis rag:docling:circuit:state = 'open'; audit_logs có row action='rag_fallback' với payload chứa document_id, reason, request_id"
    why_human: "Cần chạy Docker Compose stack thật (docling-pipeline + Redis + Postgres) — không thể verify chỉ bằng code/unit test"
  - test: "Bật lại docling-pipeline + chờ DOCLING_COOLDOWN_MIN phút (hoặc set cooldown nhỏ test) rồi upload PDF mới"
    expected: "Ingestion đi qua Docling lại tự động (log Go: 'auto-mode: docling success'); KHÔNG cần restart Go server"
    why_human: "Cần wall-clock cooldown thực + service Docling thật khôi phục; circuit half-open → closed transition runtime"
  - test: "GET /api/rag-config với service docling-pipeline đang chạy"
    expected: "Response 200 chứa 5 field: extractor_mode, docling_service_status='healthy', docling_version='2.91.x' (parse từ /readyz), docling_circuit_state='closed', last_fallback_at (null hoặc RFC3339)"
    why_human: "docling_version parse JSON thật từ sidecar Python — unit test dùng stub, cần sidecar real để xác nhận field name 'docling_version' đúng"
  - test: "PUT /api/rag-config body {\"extractor_mode\":\"native\"} với JWT admin"
    expected: "200 OK; cfg.RAG.Extractor='native'; key Redis rag:docling:circuit:state đã DEL; audit_logs có row action='rag_config_change' payload {from, to, by}"
    why_human: "Verify Redis DEL + audit insert thật trên Postgres — unit test mock cả 2"
  - test: "Apply migration 009 (migrate up) rồi upload PDF với native"
    expected: "documents.extractor_used='native' sau khi job complete; trong log worker thấy 'set extractor_used' info"
    why_human: "Migration 009 + worker.processJob → docRepo.SetExtractorUsed cần Postgres thật để xác nhận cột tồn tại + UPDATE chạy"
  - test: "POST /api/documents/{id}/reindex?extractor=docling với JWT admin"
    expected: "202 Accepted + body.data.status='pending'; chunks Postgres + ChromaDB của doc bị xóa; audit_logs có row action='document_reindex' payload {document_id, extractor_param, previous_extractor, request_id, requester_id}; sau khi worker xong → extractor_used='docling'; doc.file_path KHÔNG bị overwrite"
    why_human: "Cần worker pool + ChromaDB + fileStore thật; verify file_path không đổi cần so sánh trước/sau trong DB"
---

# Phase 4: Config Hot-Swap & Circuit Breaker — Verification Report

**Phase Goal:** Pipeline RAG không bao giờ đứng im khi service Docling down — fallback về extractor Go cũ tự động qua circuit breaker Redis-shared, admin có thể quan sát + force chuyển mode runtime qua `PUT /api/rag-config` không restart, mọi lần fallback đều có audit log. Đồng thời ghi nhận `extractor_used` per-document và endpoint admin reindex.

**Verified:** 2026-04-29
**Status:** human_needed (code-level: PASS toàn bộ; runtime smoke UAT defer cho user — cần Docker stack thật)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (7 ROADMAP Success Criteria)

| # | Truth | Status (code-level) | Evidence |
|---|-------|---------------------|----------|
| 1 | Tắt Docling → fallback `auto` + threshold trigger circuit open | ✓ VERIFIED (code) — runtime defer human | `circuit.go:57` ReadyToTrip threshold check; `pipeline.go:165` circuit.Execute wrap; Test A `TestPipelineCircuit_OpenAfterThreshold_NoMoreCallsToDocling` PASS — sau 3 fail lần 4 KHÔNG gọi Docling, state=open |
| 2 | Cooldown half-open retry close lại | ✓ VERIFIED (code) — runtime defer human | `circuit.go:56` Timeout=cooldown; Test B `TestPipelineCircuit_HalfOpenAfterCooldown_FastTransition` PASS deterministic 100ms cooldown + 120ms sleep + final state=closed (elapsed ~130ms) |
| 3 | GET /api/rag-config trả 5 field mới | ✓ VERIFIED (code) | `router.go:142-146` thêm `extractor_mode, docling_service_status, docling_version, docling_circuit_state, last_fallback_at` (+ 2 bonus `docling_fail_threshold`/`docling_cooldown_min`); Test 1 `TestRagConfigGET_Returns5NewFields` PASS body chứa đủ 5 key |
| 4 | PUT /api/rag-config force `extractor_mode=native` runtime + reset Redis circuit | ✓ VERIFIED (code) | `router.go:175,204,256` validate enum + `pipeline.SetExtractorMode()` + `circuit.Reset()` + persist `settingsRepo.Set()` + audit `rag_config_change`; Test 2 `TestRagConfigPUT_HotSwapMode` PASS (200 + log 'circuit redis state cleared'); Test 3 `TestRagConfigPUT_InvalidMode` PASS (400 cho mode invalid) |
| 5 | Audit `rag_fallback` row khi fallback | ✓ VERIFIED (code) | `pipeline.go:195` auditFallback gọi sau cbErr non-nil; `pipeline.go:600` helper insert action='rag_fallback' payload 7+ field (document_id, hub_code, reason, request_id, extractor_from='docling', extractor_to='native', error, circuit_state, consecutive_fails); Test D `TestPipelineCircuit_AutoFallback_ReturnsChunksAndAuditEntry` PASS verify payload JSON parse đầy đủ |
| 6 | Migration 009 + `extractor_used` per-document populated khi ingestion | ✓ VERIFIED (code) — runtime defer human | `migrations/009_add_extractor_used.up.sql` ALTER TABLE + CHECK + index + COMMENT; `document_repo.go:60,79,94,99` SELECT thêm cột; `document_repo.go:161-178` SetExtractorUsed/ClearExtractorUsed; `pipeline.go` ProcessResult.ExtractorUsed + extractAndChunk(mode) trả extractorUsed; worker.processJob gọi SetExtractorUsed trước UpdateCompleted |
| 7 | POST /api/documents/{id}/reindex admin → 202 + audit `document_reindex` | ✓ VERIFIED (code) | `router.go:591` docsAdmin.POST '/:id/reindex' (RequireRole admin từ Phase 3); `document_service.go:375` Reindex validate enum + ensureLocalCopy 3-tier (KHÔNG re-upload) + DeleteChunks Postgres+Chroma + reset pending + ClearExtractorUsed + Enqueue ForcedExtractor + audit document_reindex; `document_handler.go:263` map lỗi 404/400/500; 4/4 test PASS (admin 202, viewer 403, not_found 404, invalid_extractor 400) |

**Score:** 7/7 truths verified ở mức code (structural, build, unit test). 6/7 cần smoke runtime UAT để xác nhận end-to-end với Docker stack thật (theo ghi nhận ROADMAP & SUMMARY 04-05).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/internal/rag/extractor/circuit.go` | DoclingCircuit wrap gobreaker v2 + Redis sync | ✓ VERIFIED | 117 dòng — Execute/State/Counts/Reset; threshold + cooldown + OnStateChange ghi 2 Redis key; nil-safe |
| `backend/internal/rag/extractor/health.go` | DoclingHealthProbe lazy + cache 30s | ✓ VERIFIED | 143 dòng — Status (healthy/degraded/down) + Version (parse `docling_version` JSON); httpClient timeout 3s; nil-safe |
| `backend/internal/rag/pipeline.go` | Branch auto + circuit.Execute + auditFallback + 4 setter | ✓ VERIFIED | SetDoclingCircuit/SetAuditInserter/SetExtractorMode/SetDoclingOCRLangs (line 83-99); branch auto line 165; auditFallback line 600; 6 reason classification |
| `backend/internal/router/router.go` | GET/PUT /api/rag-config extension + reindex route | ✓ VERIFIED | GET response 5 field mới (line 142-146); PUT validate enum + hot-swap (line 175-256); POST /:id/reindex docsAdmin (line 591) |
| `backend/internal/database/migrations/009_add_extractor_used.up.sql` | ALTER + CHECK + index + COMMENT | ✓ VERIFIED | 23 dòng SQL hợp lệ — IF NOT EXISTS idempotent; CHECK enum 2 giá trị; idx_documents_extractor_used; .down.sql đối xứng |
| `backend/internal/repository/document_repo.go` | SetExtractorUsed + ClearExtractorUsed + SELECT thêm cột | ✓ VERIFIED | 2 method line 161-178; List + FindByID SELECT line 60/79/94/99 |
| `backend/internal/service/document_service.go` | Reindex method + ensureLocalCopy 3-tier | ✓ VERIFIED | Reindex line 375; ensureLocalCopy line 515 (KHÔNG re-upload); audit document_reindex line 486 |
| `backend/internal/handler/document_handler.go` | Reindex handler + DocumentReindexer interface | ✓ VERIFIED | Interface line 38; SetReindexer line 64; Reindex handler line 263 (map err 404/400/500) |
| `backend/internal/worker/manager.go` | EmbedJob.IsReindex + ForcedExtractor + SetExtractorUsed call | ✓ VERIFIED (per SUMMARY) | processJob truyền ForcedExtractor + gọi SetExtractorUsed trước UpdateCompleted (non-fatal) |
| `backend/cmd/server/main.go` | DI: NewDoclingCircuit + NewDoclingHealthProbe + 4 setter | ✓ VERIFIED (per SUMMARY) | doclingCircuit + doclingHealthProbe scope main; pass vào router.Setup; SetAuditRepo + SetDefaultExtractorGetter |
| `backend/internal/pkg/jwt/jwt.go` | NewManagerWithKeys constructor (test infra) | ✓ VERIFIED (per SUMMARY) | 8 dòng helper test — KHÔNG đổi production behavior |
| Test files (5 file × 16 case) | Pipeline circuit + health + admin endpoint + reindex handler | ✓ VERIFIED | 16/16 PASS thực chạy (~1.7s tổng) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `pipeline.extractAndChunk` (auto) | `circuit.Execute(...)` | `p.circuit` field (set qua DI main.go) | ✓ WIRED | line 165 wrap doclingExt.ExtractStructured |
| `pipeline` (cbErr non-nil) | `auditFallback` → `auditRepo.Insert` | AuditInserter interface | ✓ WIRED | line 195 + line 600; mocked test PASS payload đầy đủ |
| `router.GET /api/rag-config` | `circuit.State() + healthProbe.Status/Version` | DI param `doclingCircuit, doclingHealthProbe` | ✓ WIRED | router.go line 142-146 |
| `router.PUT /api/rag-config` | `pipeline.SetExtractorMode + circuit.Reset` | DI param | ✓ WIRED | router.go line 232-244 |
| `router.POST /:id/reindex` | `docService.Reindex` (hoặc mock reindexer) | `docHandler.reindexer` | ✓ WIRED | router.go line 591; service line 375 |
| `service.Reindex` | `auditRepo.Insert(action='document_reindex')` | optional setter SetAuditRepo | ✓ WIRED | service line 486; main.go gọi setter |
| `worker.processJob` | `docRepo.SetExtractorUsed` | DI docRepo | ✓ WIRED | non-fatal log warn nếu fail |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| GET /api/rag-config response | `doclingStatus` | `healthProbe.Status(ctx)` → http GET /healthz + /readyz | Yes (sidecar thật) / Cached Redis 30s | ⚠️ HOLLOW khi healthProbe nil hoặc sidecar chưa chạy → trả "unknown" (graceful) |
| GET response | `lastFallback` | `auditRepo.List(action='rag_fallback', limit 1)` | Yes — query thật Postgres | ✓ FLOWING |
| GET response | `circuitState` | `circuit.State().String()` | Yes — gobreaker in-process state | ✓ FLOWING |
| documents.extractor_used | `result.ExtractorUsed` | `pipeline.extractAndChunk` set ở 3 nhánh + worker UPDATE | Yes — runtime cần verify nhưng code path đầy đủ | ⚠️ Cần smoke runtime UAT confirm UPDATE chạy thật |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `go build ./...` clean | `cd backend && go build ./...` | No output | ✓ PASS |
| Pipeline circuit 5 test | `go test -run TestPipelineCircuit ./internal/rag/` | 5/5 PASS ~0.62s | ✓ PASS |
| Health probe 4 test | `go test -run TestHealthProbe ./internal/rag/extractor/` | 4/4 PASS ~0.39s | ✓ PASS |
| Admin endpoint 3 test | `go test -run TestRagConfig ./internal/router/` | 3/3 PASS ~0.78s | ✓ PASS |
| Reindex handler 4 test | `go test -run TestDocumentReindex ./internal/handler/` | 4/4 PASS ~0.37s | ✓ PASS |
| Migration SQL hợp lệ | Read 009_add_extractor_used.up.sql | ALTER + CHECK + idx + COMMENT đủ 4 element | ✓ PASS |
| Smoke runtime fallback (Docker) | docker compose stop docling-pipeline + upload PDF | N/A — chưa chạy | ? SKIP (defer human) |
| Smoke runtime reindex (Docker) | POST /reindex + verify chunks deleted | N/A — chưa chạy | ? SKIP (defer human) |

### Requirements Coverage

| REQ | Source Plan | Description | Status | Evidence |
|-----|-------------|-------------|--------|----------|
| CFG-01 | 04-01 + 04-02 + 04-04 | RAG_EXTRACTOR enum + threshold/cooldown auto fallback | ✓ SATISFIED | env vars trong config.go; circuit.go; pipeline branch auto; Test A+B PASS |
| CFG-02 | 04-01 + 04-02 + 04-03 | DOCLING_SERVICE_URL, DOCLING_TIMEOUT_SEC, DOCLING_OCR_LANGS env | ✓ SATISFIED | config.go DoclingOCRLangs; .env.example 3 env mới; WithOCRLangs propagate multipart |
| CFG-03 | 04-03 + 04-04 | Admin GET/PUT /api/rag-config 5 field + force mode | ✓ SATISFIED | router.go GET response 5 field; PUT validate + hot-swap; Test 1+2+3 PASS |
| CFG-04 | 04-01 + 04-03 + 04-04 | Circuit state Redis-shared + reset on PUT | ✓ SATISFIED | redis Set/Del 2 key; Reset() DEL; Test 2 verify 'cleared by admin' log |
| CFG-05 | 04-02 + 04-04 | Audit log fallback rag_fallback | ✓ SATISFIED | auditFallback helper; Test D verify payload JSON parse 7 field |
| CFG-06 | 04-05 | extractor_used per-document column + populated | ✓ SATISFIED (code) — UAT confirm | Migration 009 + repo SetExtractorUsed + worker call non-fatal |
| CFG-07 | 04-05 | POST /reindex admin + audit document_reindex | ✓ SATISFIED | route docsAdmin; service Reindex; 4 test handler PASS |

**7/7 REQ-ID covered.** No orphaned REQ.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `service/document_service.go` | line ~205 (per SUMMARY 04-05) | Bỏ check status='pending'/'processing' trong Reindex | ℹ️ Info | Đã document trong Deviation 3 + Known Stub — admin có thể enqueue trùng (acceptable trade-off recover stuck job) |
| `router/router.go` | line ~120 | last_fallback_at full-scan audit_logs (no idx) | ℹ️ Info | Carry-over I2 từ CHECK Round 2 — defer hardening; LIMIT 1 + reverse timestamp index acceptable cho M1 |
| `cmd/server/main.go` | startup | KHÔNG load RAG_EXTRACTOR từ settings_repo lúc boot | ⚠️ Warning | Known Stub Plan 04-03 — PUT persist DB nhưng restart vẫn dùng env var. Hoãn hardening |
| `pipeline.go` | SetExtractorMode | KHÔNG mutex hot-swap | ℹ️ Info | Eventual consistency theo CONTEXT Rủi ro 1 — in-flight jobs thấy mode cũ vài giây (acceptable) |

KHÔNG có blocker hay TODO/placeholder/stub gốc trong code Phase 4.

### Human Verification Required

Xem block `human_verification` ở YAML frontmatter — 6 smoke test runtime cần Docker stack thật để confirm 6/7 success criteria end-to-end. Tất cả đã được code-level verify đầy đủ (build + unit test 16/16 PASS); UAT chỉ cần xác nhận behavior runtime khớp specification.

### Gaps Summary

KHÔNG có gap blocker. 7/7 success criteria đều có code path đầy đủ + test PASS + structural element verified.

Tuy nhiên 6/7 success criteria liên quan tới **runtime behavior** (fallback Docker, cooldown wall-clock, audit row Postgres, migration apply, reindex chunks delete) chỉ có thể UAT bằng smoke test thật với Docker Compose stack — đây là defer **chính chủ** đã ghi nhận trong SUMMARY 04-04 + 04-05 + ROADMAP. Status `human_needed` phản ánh đúng tình trạng: code-level PASS, runtime UAT pending.

Status overall **không phải `passed`** vì có 6 item human_verification — theo Step 9 decision tree, human_needed phải được ưu tiên.

---

*Verified: 2026-04-29*
*Verifier: Claude (gsd-verifier)*
