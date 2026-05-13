---
phase: 04-config-hot-swap-circuit-breaker
plan: 03
subsystem: rag-admin-api
tags: [router, admin, rag-config, http, circuit-breaker, audit]
requires:
  - extractor.DoclingCircuit (Plan 04-01)
  - extractor.DoclingHealthProbe (Plan 04-01)
  - rag.Pipeline.SetExtractorMode (Plan 04-02)
  - extractor.WithOCRLangs (Plan 04-02 đã add)
  - repository.AuditRepo (Phase 1 brownfield)
  - repository.SettingsRepo (đã ở scope router)
provides:
  - GET /api/rag-config — extend response 5 field mới (extractor_mode, docling_service_status, docling_version, docling_circuit_state, last_fallback_at) + 2 field bonus (docling_fail_threshold, docling_cooldown_min)
  - PUT /api/rag-config — accept body field `extractor_mode` (validate enum native|docling|auto), hot-swap pipeline + reset Redis circuit + persist settings_repo + audit `rag_config_change`
  - router.Setup() signature mở rộng 4 param mới (doclingCircuit, doclingHealthProbe, auditRepo, pipeline)
  - main.go scope main giữ doclingCircuit + doclingHealthProbe để DI vào router
affects:
  - Plan 04-04 (test) sẽ gọi GET/PUT /api/rag-config qua httptest để verify 4 case (extractor_mode invalid 400, hot-swap 200, GET response chứa 5 field, audit log có row mới sau PUT).
  - Plan 04-05 (CFG-06/07 — extractor_used + reindex) độc lập, không phụ thuộc plan này.
tech_stack:
  added: []
  patterns: ["DI via signature extension", "best-effort observability (nil-guard)", "enum validation 400 trước hot-swap", "audit-on-config-change"]
key_files:
  created: []
  modified:
    - backend/internal/router/router.go
    - backend/cmd/server/main.go
decisions:
  - "W4 quyết option (a): dùng settingsRepo có sẵn ở scope router (line 49 Setup signature) để persist RAG_EXTRACTOR — KHÔNG cần thêm param mới."
  - "Đặt validation extractor_mode TRƯỚC tất cả mutate khác (clear keys, save keys, swap embedder) để fail fast — invalid input không leave side-effects khác."
  - "Audit chỉ ghi khi `oldMode != newMode` — tránh spam audit_logs khi admin PUT mode = mode hiện tại."
  - "Nâng doclingCircuit + doclingHealthProbe lên scope main (var declaration ngoài if) để pass vào router.Setup() — pattern brownfield đã dùng cho `pipeline`, `searcher`, `workerMgr`."
  - "GET response trả `unknown` thay vì `null` cho status/circuit_state khi probe nil — UI hiển thị thân thiện hơn (RAG chưa init thấy `unknown` thay vì lỗi)."
  - "Plan này KHÔNG đụng pipeline.go (B2 đã thoả) — toàn bộ 4 setter expose từ Plan 04-02."
metrics:
  duration: "~25 phút"
  completed_date: "2026-05-04"
  tasks: 3
  files: 2
  tests_added: 0
commit: 5a8a038
---

# Phase 4 Plan 03: Admin endpoint GET/PUT /api/rag-config extension + OCR langs multipart (CFG-02, CFG-03, CFG-04)

**One-liner:** Mở rộng admin endpoint `GET/PUT /api/rag-config` để admin quan sát 5 field mới (extractor_mode + docling status/version/circuit + last_fallback_at) và force chuyển mode runtime qua PUT — gọi `pipeline.SetExtractorMode` + reset Redis circuit + audit `rag_config_change`. Toàn bộ thay đổi nằm gọn ở `router.go` + `main.go` (DI 4 param mới); `pipeline.go` KHÔNG bị đụng (B2 — Plan 02 đã expose hết setter).

## Mục tiêu

Wave 3 Phase 4 — wire HTTP API cho config hot-swap. Plan 04-01 đặt foundation (`circuit.go` + `health.go` + 3 env), Plan 04-02 wire pipeline branch `auto` + circuit.Execute + auditFallback + 4 setter; Plan 04-03 chỉ phải connect HTTP layer.

## Việc đã làm

### Task 1 — `backend/internal/router/router.go`

**Thêm import:**
- `encoding/json` — marshal payload audit.
- `github.com/google/uuid` — `uuid.New()` cho audit entry ID.
- `internal/model` — `model.AuditLogEntry`.
- `internal/rag` — type `*rag.Pipeline` cho param mới.
- `internal/rag/extractor` — type `*extractor.DoclingCircuit`, `*extractor.DoclingHealthProbe`.

**Sửa signature `Setup()`** — thêm 4 param sau `swappableEmbedder` (theo thứ tự đã chốt trong Plan 03 CONTEXT):

```go
// ─── M1 Phase 4 (CFG-03, CFG-04) ───
doclingCircuit *extractor.DoclingCircuit,
doclingHealthProbe *extractor.DoclingHealthProbe,
auditRepo *repository.AuditRepo,
pipeline *rag.Pipeline,
```

**Sửa handler `GET /api/rag-config`** — thêm block probe trước `c.JSON`:

```go
var (
    doclingStatus  = "unknown"
    doclingVersion = ""
    circuitState   = "unknown"
    lastFallback   *string
)
ctx := c.Request.Context()
if doclingHealthProbe != nil {
    doclingStatus = string(doclingHealthProbe.Status(ctx))
    doclingVersion = doclingHealthProbe.Version(ctx)
}
if doclingCircuit != nil {
    circuitState = doclingCircuit.State().String()
}
if auditRepo != nil {
    entries, _, err := auditRepo.List(ctx, "", "", "", "rag_fallback", "", 1, 1)
    if err == nil && len(entries) > 0 {
        ts := entries[0].Timestamp.UTC().Format(time.RFC3339)
        lastFallback = &ts
    }
}
```

Response gin.H thêm 7 key:

| Key | Source | Default khi nil |
|---|---|---|
| `extractor_mode` | `cfg.RAG.Extractor` | "" |
| `docling_service_status` | `healthProbe.Status(ctx)` | `"unknown"` |
| `docling_version` | `healthProbe.Version(ctx)` | `""` |
| `docling_circuit_state` | `circuit.State().String()` | `"unknown"` |
| `last_fallback_at` | `auditRepo.List(action="rag_fallback")` | `null` |
| `docling_fail_threshold` | `cfg.RAG.DoclingFailThreshold` | 0 |
| `docling_cooldown_min` | `cfg.RAG.DoclingCooldownMin` | 0 |

**Sửa handler `PUT /api/rag-config`** — extend struct `req` thêm:

```go
ExtractorMode string `json:"extractor_mode"`
```

Block xử lý hot-swap đặt **NGAY SAU** validation `BatchSize` (fail fast — invalid mode trả 400 trước khi mutate side-effects khác):

```go
if req.ExtractorMode != "" {
    validModes := map[string]bool{"native": true, "docling": true, "auto": true}
    if !validModes[req.ExtractorMode] {
        c.JSON(http.StatusBadRequest, gin.H{
            "error": "extractor_mode không hợp lệ — chỉ chấp nhận: native, docling, auto",
        })
        return
    }
    oldMode := cfg.RAG.Extractor
    if oldMode != req.ExtractorMode {
        cfg.RAG.Extractor = req.ExtractorMode
        if pipeline != nil { pipeline.SetExtractorMode(req.ExtractorMode) }
        if doclingCircuit != nil {
            if err := doclingCircuit.Reset(c.Request.Context()); err != nil {
                slog.Warn("reset docling circuit failed", "err", err)
            }
        }
        if settingsRepo != nil {
            _ = settingsRepo.Set(c.Request.Context(), "RAG_EXTRACTOR", req.ExtractorMode, false)
        }
        if auditRepo != nil {
            actorID, _ := middleware.GetUserID(c)
            // ... insert AuditLogEntry action="rag_config_change", payload {from, to, by}
        }
        slog.Info("extractor_mode hot-swapped", "from", oldMode, "to", req.ExtractorMode)
    }
}
```

**Audit payload mẫu (audit_logs.payload JSONB):**
```json
{
  "from": "auto",
  "to": "native",
  "by": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Task 2 — `backend/cmd/server/main.go`

**Nâng `doclingCircuit` + `doclingHealthProbe` lên scope main:**

```go
var pipeline *rag.Pipeline
// Plan 04-03: 2 biến scope main để truyền vào router.Setup() cho admin endpoint.
var doclingCircuit *extractor.DoclingCircuit
var doclingHealthProbe *extractor.DoclingHealthProbe
```

Bên trong `if swappableEmbedder.Provider() != nil && store != nil`: đổi `:=` thành `=` cho `doclingCircuit`, thêm khởi tạo `doclingHealthProbe = extractor.NewDoclingHealthProbe(cfg.RAG.DoclingServiceURL, rdb)`, xóa dòng `_ = doclingCircuit` placeholder.

**Sửa call `router.Setup`** — thêm 4 param cuối:

```go
r := router.Setup(cfg, jwtManager, rdb, authHandler, hubHandler, docHandler, searchHandler, syncHandler,
    userHandler, profileHandler, auditHandler, apikeyHandler, usageHandler, settingsRepo,
    hubRepo, store, llmClient, swappableEmbedder,
    // M1 Phase 4 (CFG-03, CFG-04) — admin endpoint extension
    doclingCircuit, doclingHealthProbe, auditRepo, pipeline)
```

### Task 3 — `backend/internal/rag/extractor/docling.go`

**KHÔNG cần edit** — Plan 04-02 đã add `ctxOCRLangsKey struct{}`, `WithOCRLangs(ctx, langs)` (line 305-307) + multipart field `ocr_langs` (line 139-141). Verify:

```bash
$ grep -c "ocr_langs\|WithOCRLangs" backend/internal/rag/extractor/docling.go
6
```

Đúng 6 match: 1 type, 2 comment, 1 helper, 1 ctx.Value, 1 mw.WriteField → CFG-02 satisfied từ Plan 02.

## Verification

| Check | Kết quả |
|---|---|
| `cd backend && go build ./...` | PASS (no output) |
| `cd backend && go vet ./...` | PASS (no output) |
| `git diff --stat backend/internal/rag/pipeline.go` | EMPTY (B2 satisfied) |
| `grep -c "extractor_mode\|docling_service_status\|docling_version\|docling_circuit_state\|last_fallback_at" backend/internal/router/router.go` | 9 (≥ 5) |
| `grep -c "ocr_langs\|WithOCRLangs" backend/internal/rag/extractor/docling.go` | 6 (≥ 3) |
| `grep -c "doclingHealthProbe" backend/cmd/server/main.go` | 3 (≥ 2: declare + assign + pass) |
| `git diff --diff-filter=D --name-only HEAD~1 HEAD` | EMPTY (không xóa file) |

## Quyết định settingsRepo (W4)

**Chọn option (a)** — `settingsRepo` đã có sẵn ở scope router thông qua `Setup` signature (line 49 file router.go). Lý do:

- Phase trước đã wire `settingsRepo` vào router để persist `GEMINI_API_KEY`, `OPENAI_API_KEY`, `LLM_PROVIDER`, `RAG_EMBEDDING_*`, `RAG_CHUNK_*` — không có lý do gì phải skip persistence cho `RAG_EXTRACTOR`.
- Restart server cần restore `RAG_EXTRACTOR` từ DB giống các config khác — convention thống nhất.
- Persist 1 dòng: `_ = settingsRepo.Set(ctx, "RAG_EXTRACTOR", req.ExtractorMode, false)` — không tốn thêm public API mới.

**Lưu ý:** main.go hiện CHƯA có block load `RAG_EXTRACTOR` từ settings_repo lúc startup (chỉ load `GEMINI_API_KEY`/`OPENAI_API_KEY`/`RAG_EMBEDDING_*`/`RAG_CHUNK_*`/`LLM_*`). Việc admin PUT extractor_mode sẽ persist vào DB nhưng restart server vẫn dùng `RAG_EXTRACTOR` env var hoặc default `"native"`. Đây là **known gap** — defer sang Plan 04-04 (Wave 4 test) hoặc milestone hardening để hoàn chỉnh round-trip persistence.

## Curl examples (manual verification)

GET response (admin chưa login cũng được — endpoint public):
```bash
curl -s http://localhost:8180/api/rag-config | jq '{extractor_mode, docling_service_status, docling_version, docling_circuit_state, last_fallback_at}'
```
Kết quả mẫu:
```json
{
  "extractor_mode": "auto",
  "docling_service_status": "healthy",
  "docling_version": "2.91.0",
  "docling_circuit_state": "closed",
  "last_fallback_at": null
}
```

PUT hợp lệ (cần JWT admin):
```bash
curl -s -X PUT http://localhost:8180/api/rag-config \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"extractor_mode":"native"}' | jq
```
→ 200 + `cfg.RAG.Extractor = "native"` + audit row mới + Redis key `rag:docling:circuit:state` đã DEL.

PUT invalid:
```bash
curl -s -X PUT http://localhost:8180/api/rag-config \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"extractor_mode":"foobar"}'
```
→ `400 {"error":"extractor_mode không hợp lệ — chỉ chấp nhận: native, docling, auto"}`.

Sau PUT thành công query Postgres:
```sql
SELECT action, payload::text FROM audit_logs WHERE action='rag_config_change' ORDER BY timestamp DESC LIMIT 1;
```
→ 1 row có `payload = {"from":"auto","to":"native","by":"<user_id>"}`.

## Deviations from Plan

**1. [Rule 3 - Blocking] Nâng `doclingCircuit` + `doclingHealthProbe` lên scope main**
- **Found during:** Task 2 build check.
- **Issue:** Plan 02 khai báo `doclingCircuit := extractor.NewDoclingCircuit(...)` BÊN TRONG block `if swappableEmbedder.Provider() != nil && store != nil` → biến không reach được ở dòng `router.Setup` cuối main.
- **Fix:** Khai báo `var doclingCircuit *extractor.DoclingCircuit` + `var doclingHealthProbe *extractor.DoclingHealthProbe` ở scope main (ngay trước if), đổi `:=` thành `=` trong block. Pattern brownfield đã dùng cho `pipeline`, `searcher`, `workerMgr` (cùng main.go) — convention thống nhất.
- **Files modified:** `backend/cmd/server/main.go`.
- **Commit:** 5a8a038.

**2. [Rule 2 - Critical functionality] Thêm 2 field bonus `docling_fail_threshold` + `docling_cooldown_min` vào GET response**
- **Found during:** Task 1 implement GET handler.
- **Issue:** Plan chỉ yêu cầu 5 field mới, nhưng admin observability trên UI Settings sẽ cần biết threshold + cooldown hiện tại để tự decide có chỉnh hay không (vd: thấy circuit open quá nhanh → biết threshold đang quá thấp).
- **Fix:** Thêm 2 key gin.H đọc trực tiếp từ `cfg.RAG.DoclingFailThreshold` + `cfg.RAG.DoclingCooldownMin` — zero cost (config sẵn ở memory).
- **Files modified:** `backend/internal/router/router.go`.
- **Commit:** 5a8a038.

**Tóm lại:** Không deviation về scope hay design.

## Auth gates

Không có (Wave 3 thuần code wire HTTP, không runtime call).

## Known Stubs

- **Round-trip persistence chưa hoàn chỉnh:** PUT extractor_mode persist vào `settings_repo` nhưng main.go startup chưa có block `if v, _ := settingsRepo.Get(ctx, "RAG_EXTRACTOR"); v != "" { cfg.RAG.Extractor = v }`. Defer sang Plan 04-04 hoặc hardening.
- **`extractor_mode` hot-swap KHÔNG mutex:** `pipeline.SetExtractorMode(...)` trong Plan 02 đã accept eventual consistency theo CONTEXT Rủi ro 1 — in-flight jobs vẫn thấy mode cũ ~vài giây.

## Self-Check: PASSED

- File `backend/internal/router/router.go` modified — FOUND.
- File `backend/cmd/server/main.go` modified — FOUND.
- File `backend/internal/rag/extractor/docling.go` KHÔNG modified Plan 03 — verified (Plan 02 đã add từ trước).
- File `backend/internal/rag/pipeline.go` KHÔNG modified — verified (B2).
- Commit `5a8a038` tồn tại — FOUND (`git log --oneline | grep 5a8a038`).
- Build PASS, vet PASS.

## Next

- **Plan 04-04 (Wave 4 — test):** `pipeline_circuit_test.go` mock AuditInserter + circuit + miniredis verify 4 case (success / fail-fallback-audit / circuit open / mode change runtime). Bổ sung `router_rag_config_test.go` test 3 case PUT (invalid 400, hot-swap 200, KHÔNG đổi nếu mode trùng). Optional: thêm block load `RAG_EXTRACTOR` từ settings_repo lúc startup main.go.
- **Plan 04-05 (Wave 5):** Migration 009 + `extractor_used` per-document + endpoint `POST /api/documents/:id/reindex` (CFG-06, CFG-07).

---
*Last updated: 2026-05-04 (Plan 04-03 PASS — admin endpoint extension + W4 option (a) settingsRepo + 2 field bonus + B2 satisfied; commit 5a8a038).*
