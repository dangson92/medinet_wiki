---
phase: 04-config-hot-swap-circuit-breaker
plan: 01
subsystem: rag-extractor
tags: [rag, circuit-breaker, gobreaker, redis, config, health-probe]
requires:
  - github.com/redis/go-redis/v9 (đã có)
  - github.com/sony/gobreaker/v2 v2.4.0 (mới)
  - github.com/alicebob/miniredis/v2 v2.37.0 (test mới)
provides:
  - extractor.DoclingCircuit (Execute / State / Counts / Reset)
  - extractor.DoclingHealthProbe (Status / Version)
  - config.RAGConfig.DoclingFailThreshold + DoclingCooldownMin + DoclingOCRLangs
  - 2 Redis key chính: rag:docling:circuit:state, rag:docling:circuit:changed_at
  - 2 Redis key health: rag:docling:health (TTL 30s), rag:docling:version (TTL 5m)
affects:
  - Plan 04-02 sẽ import extractor.NewDoclingCircuit để wrap doclingExtract trong pipeline.go.
  - Plan 04-03 sẽ gọi healthProbe.Status / Version + circuit.State / Reset cho admin endpoint.
tech_stack:
  added: ["sony/gobreaker/v2 v2.4.0", "alicebob/miniredis/v2 v2.37.0"]
  patterns: ["circuit-breaker (closed/half-open/open)", "lazy health probe + Redis cache TTL"]
key_files:
  created:
    - backend/internal/rag/extractor/circuit.go
    - backend/internal/rag/extractor/circuit_test.go
    - backend/internal/rag/extractor/health.go
  modified:
    - backend/internal/config/config.go
    - backend/.env.example
    - backend/go.mod
    - backend/go.sum
decisions:
  - "Generic gobreaker.CircuitBreaker[CircuitResult] với CircuitResult = struct{} — pipeline capture text/chunks qua closure, không nhồi vào generic."
  - "Interval=0 (KHÔNG reset counts theo interval), Timeout=cooldown — counts chỉ reset khi state change. Phù hợp pattern fail-fast của RAG."
  - "Reset() chỉ DEL Redis key (gobreaker v2 không expose public Reset). In-process state tự reset sau cooldown qua half-open."
  - "Health probe lazy + cache 30s Redis. KHÔNG dùng background poller (tránh goroutine leak)."
  - "Default RAG_EXTRACTOR vẫn 'native' để KHÔNG đổi behavior pre-Phase-4 — Plan 04-02 mới wire 'auto' vào pipeline."
metrics:
  duration: "~25 phút"
  completed_date: "2026-05-04"
  tasks: 3
  files: 7
  tests_added: 5
commit: 839d11c
---

# Phase 4 Plan 01: Foundation — Circuit Breaker + Health Probe + Env Config (CFG-01, CFG-02, CFG-04)

**One-liner:** Đặt sẵn dependency `sony/gobreaker/v2`, 2 file mới (`circuit.go` wrap circuit breaker với Redis state sync + `health.go` lazy probe `/healthz`+`/readyz` cache 30s) và 3 env mới — chuẩn bị để Plan 04-02 wire `auto` mode pipeline mà không phải sửa go.mod nữa.

## Mục tiêu

Foundation Wave 1 cho Phase 4: cô lập commit thay đổi `go.mod` + 1 file mới (`circuit.go`) tách biệt với pipeline branch logic ở Plan 02. Khi Plan 02/03 thêm import, dependency đã sẵn sàng, tránh merge conflict nhánh sau.

## Việc đã làm

### 1. Dependencies (`go.mod` + `go.sum`)
- `go get github.com/sony/gobreaker/v2@latest` → v2.4.0.
- `go get -t github.com/alicebob/miniredis/v2` → v2.37.0 (test-only).

### 2. `backend/internal/rag/extractor/circuit.go` (mới, 116 dòng)
- Struct `DoclingCircuit` wrap `*gobreaker.CircuitBreaker[CircuitResult]` (generic v2).
- Constructor `NewDoclingCircuit(rdb, threshold, cooldown, logger)` — defensive defaults (threshold=3, cooldown=5min, logger=slog.Default).
- `OnStateChange` callback ghi 2 key Redis: `rag:docling:circuit:state` (string `closed|half-open|open`) + `rag:docling:circuit:changed_at` (unix seconds). Timeout 2s tránh treo callback nếu Redis chậm.
- 4 method public:
  - `Execute(fn func() error) error` — trả `gobreaker.ErrOpenState` khi open, fn KHÔNG được gọi.
  - `State() gobreaker.State` — cho admin endpoint Plan 04-03.
  - `Counts() gobreaker.Counts` — cho audit log fallback Plan 04-02.
  - `Reset(ctx) error` — DEL 2 Redis key, log info; in-process state tự reset qua half-open sau cooldown.

### 3. `backend/internal/rag/extractor/circuit_test.go` (mới, 5 test case PASS)
- `TestDoclingCircuit_Constructor_NotNil` — wrapper khởi tạo, initial state = closed.
- `TestDoclingCircuit_OpensAfterThresholdFailures` — 3 fail → call thứ 4 trả `ErrOpenState`, closure KHÔNG được gọi, state = open.
- `TestDoclingCircuit_RedisStateSyncedOnTransition` — sau 2 fail (threshold=2), miniredis key `rag:docling:circuit:state` = "open", `:changed_at` non-empty.
- `TestDoclingCircuit_StateStringEnum` — `State().String()` trả `"closed"` ban đầu và `"open"` sau threshold.
- `TestDoclingCircuit_BelowThresholdStaysClosed` — 2 fail (dưới threshold 3) → vẫn closed, lần 3 success reset `ConsecutiveFailures` về 0.

### 4. `backend/internal/rag/extractor/health.go` (mới, 137 dòng)
- Struct `DoclingHealthProbe` với `httpClient` (timeout 3s), `redis`, `baseURL`.
- 3 enum: `HealthHealthy`, `HealthDegraded` (healthz OK + readyz FAIL = models warming), `HealthDown`.
- `Status(ctx) HealthStatus` — đọc cache `rag:docling:health` 30s; miss → probe `/healthz` (down nếu fail) → `/readyz` (degraded nếu fail) → set cache.
- `Version(ctx) string` — đọc cache `rag:docling:version` 5m; miss → GET `/readyz`, parse JSON field `docling_version` hoặc `version`. Trả "" khi fail (admin endpoint hiển thị `null`).
- Defensive: redis nil-safe (in-test no-cache OK).

### 5. `backend/internal/config/config.go`
- Extend `RAGConfig` thêm 3 field sau `JobTimeoutDoclingSec`:
  - `DoclingFailThreshold uint32` — env `DOCLING_FAIL_THRESHOLD`, default 3.
  - `DoclingCooldownMin int` — env `DOCLING_COOLDOWN_MIN`, default 5.
  - `DoclingOCRLangs string` — env `DOCLING_OCR_LANGS`, default `"vie+eng"`.
- `Load()` parse với guard `<=0 → default`.
- KHÔNG đổi default `RAG_EXTRACTOR` (vẫn `native`) — Plan 02 sẽ wire `auto` qua pipeline.

### 6. `backend/.env.example`
- Thêm section "Docling Circuit Breaker (M1 Phase 4)" sau `JOB_TIMEOUT_DOCLING_SEC=240`:
  - `DOCLING_FAIL_THRESHOLD=3`
  - `DOCLING_COOLDOWN_MIN=5`
  - `DOCLING_OCR_LANGS=vie+eng`
- Comment giải thích scope CFG-01/CFG-02 + plan tương lai chuyển default `RAG_EXTRACTOR` sang `auto` ở Plan 04-02.

## Verification

| Check | Kết quả |
|---|---|
| `cd backend && go build ./...` | PASS (no output) |
| `cd backend && go vet ./...` | PASS (no output) |
| `cd backend && go test -run TestDoclingCircuit -v ./internal/rag/extractor/` | 5/5 PASS (~0.24s) |
| `cd backend && go test ./internal/rag/extractor/` | PASS toàn package (~4.8s) |
| `grep "gobreaker\|miniredis" backend/go.mod` | 2 match (`sony/gobreaker/v2 v2.4.0` + `alicebob/miniredis/v2 v2.37.0`) |
| `grep "DOCLING_FAIL_THRESHOLD\|DOCLING_COOLDOWN_MIN\|DOCLING_OCR_LANGS" backend/.env.example` | 3 match |
| `grep "DoclingFailThreshold" backend/internal/config/config.go` | 2 match (declaration + assignment) |

## Deviations from Plan

**1. [Rule 1 - Defensive] Redis nil-safe trong cả `circuit.go` và `health.go`**
- **Found during:** Task 2 + Task 3.
- **Issue:** Plan ban đầu giả định `rdb` non-nil. Nếu main.go khởi tạo lỗi Redis nhưng vẫn chạy (degraded mode), goroutine `OnStateChange` sẽ panic.
- **Fix:** Thêm `if rdb != nil` trong `OnStateChange` + `Reset` của circuit; tương tự cho `Status`/`Version` của health (cache miss path khi nil).
- **Files modified:** `circuit.go`, `health.go`.
- **Commit:** 839d11c.

**2. [Rule 2 - Critical] HTTP client timeout 3s cho health probe**
- **Found during:** Task 3.
- **Issue:** Plan ghi `healthProbeTimeout = 3*time.Second` nhưng không nói tại sao. Verify lại: nếu probe treo lâu (> cache TTL 30s) sẽ block toàn bộ request admin GET `/api/rag-config`.
- **Fix:** Giữ timeout 3s như plan + comment.
- **Files modified:** `health.go`.
- **Commit:** 839d11c.

**Tóm lại:** Không deviation về scope hay design — chỉ thêm 2 mitigation phòng thủ.

## Auth gates

Không có (Wave 1 thuần code, không runtime call).

## Known Stubs

Không có. Cả `circuit.go` và `health.go` được wire vào ở Plan 04-02/04-03 (Phase 4 sau).

## Self-Check: PASSED

- File `backend/internal/rag/extractor/circuit.go` — FOUND.
- File `backend/internal/rag/extractor/circuit_test.go` — FOUND.
- File `backend/internal/rag/extractor/health.go` — FOUND.
- `git log --oneline | grep 839d11c` — FOUND (`839d11c feat(rag): foundation circuit breaker ...`).
- `go.mod` chứa `sony/gobreaker/v2 v2.4.0` + `alicebob/miniredis/v2 v2.37.0` — FOUND.
- `.env.example` chứa 3 env mới — FOUND.

## Next

- **Plan 04-02 (Wave 2):** Wire `RAG_EXTRACTOR=auto` mode vào `pipeline.go` — gọi `circuit.Execute(...)` quanh `doclingExtractor.ExtractStructured(...)`, fallback `nativeExtract` + audit log khi `ErrOpenState` hoặc closure error.
- **Plan 04-03 (Wave 3):** Extend admin `GET /api/rag-config` (5 field mới) + `PUT /api/rag-config` (accept `extractor_mode` + reset circuit Redis state).

---
*Last updated: 2026-05-04*
