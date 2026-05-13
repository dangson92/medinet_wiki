// Package rag — pipeline circuit transition tests (Plan 04-04 Wave 4).
//
// Verify pipeline mode "auto" đi qua đúng state transition của circuit breaker:
// closed → open (sau N consecutive fail) → half-open (sau cooldown) →
// closed (success) hoặc open lại (re-fail).
//
// **B3 fix (CHECK round 1):** cooldown = 100ms, sleep = 120ms — tổng wall-clock
// transition < 200ms để CI deterministic, KHÔNG dùng 1s+ flaky.
//
// **W6 fix:** mọi `go test` command phải có `-race` flag (verify ở plan).
package rag

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/sony/gobreaker/v2"

	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/rag/chunker"
	"github.com/medinet/hub-all-backend/internal/rag/extractor"
)

// ─── Test doubles ────────────────────────────────────────────────────────────

// recordingAudit ghi nhận tất cả audit entries vào slice in-memory.
// Dùng để verify branch fallback insert đúng action="rag_fallback" + payload chứa
// document_id, reason, circuit_state.
type recordingAudit struct {
	entries []*model.AuditLogEntry
}

func (r *recordingAudit) Insert(_ context.Context, e *model.AuditLogEntry) error {
	r.entries = append(r.entries, e)
	return nil
}

// fakeDoclingExt là StructuredExtractor stub — trả error theo failNext counter
// để force scenario controlled. Khi failNext > 0: trả lỗi và decrement.
// Khi failNext == 0: trả 1 chunk success.
//
// Atomic counter để goroutine-safe (vì test có cooldown wait).
type fakeDoclingExt struct {
	failNext   atomic.Int32
	callCount  atomic.Int32
	failError  error
	successOut []chunker.Chunk
}

func (f *fakeDoclingExt) Extract(_ context.Context, _ string) (string, error) {
	return "", errors.New("legacy Extract not used in auto-mode test")
}

func (f *fakeDoclingExt) ExtractStructured(_ context.Context, _ string) (string, []chunker.Chunk, error) {
	f.callCount.Add(1)
	if f.failNext.Load() > 0 {
		f.failNext.Add(-1)
		return "", nil, f.failError
	}
	return "ok", f.successOut, nil
}

func (f *fakeDoclingExt) SupportedType() string { return extractor.DoclingKey }

// noopChunker — pipeline.extractAndChunk fallback path gọi p.chunker.Chunk(text)
// → trả 1 chunk synthetic.
type noopChunker struct{}

func (noopChunker) Chunk(text string, _ chunker.ChunkOpts) []chunker.Chunk {
	return []chunker.Chunk{{Index: 0, Content: text, TokenCount: 1}}
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

func newTestPipelineForCircuit(t *testing.T, mode string, threshold uint32, cooldown time.Duration) (
	*Pipeline,
	*fakeDoclingExt,
	*recordingAudit,
	*miniredis.Miniredis,
) {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("miniredis.Run: %v", err)
	}
	t.Cleanup(mr.Close)
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = rdb.Close() })

	circuit := extractor.NewDoclingCircuit(rdb, threshold, cooldown, nil)

	fakeExt := &fakeDoclingExt{
		failError: errors.New("simulated docling fail"),
		successOut: []chunker.Chunk{
			{Index: 0, Content: "docling chunk", TokenCount: 5},
		},
	}
	audit := &recordingAudit{}

	p := &Pipeline{
		chunker:         noopChunker{},
		chunkOpts:       chunker.ChunkOpts{MaxTokens: 100},
		extractorMode:   mode,
		doclingExt:      fakeExt,
		circuit:         circuit,
		auditRepo:       audit,
		doclingOCRLangs: "vie+eng",
	}
	return p, fakeExt, audit, mr
}

// writeTempFile tạo file PDF dummy để extractAndChunk có path hợp lệ
// (extractor Go branch native đọc file thật khi fallback). Đối với mode auto,
// branch native sẽ được trigger sau khi circuit open → cần file tồn tại.
func writeTempFile(t *testing.T, ext, body string) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "doc"+ext)
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatalf("write temp file: %v", err)
	}
	return path
}

// ─── Test A: 3 fail → open + lần 4 KHÔNG gọi Docling ─────────────────────────

func TestPipelineCircuit_OpenAfterThreshold_NoMoreCallsToDocling(t *testing.T) {
	p, fakeExt, audit, _ := newTestPipelineForCircuit(t, "auto", 3, 100*time.Millisecond)
	tmpFile := writeTempFile(t, ".txt", "fallback native body")

	ctx := context.Background()

	// 3 fail liên tiếp — mỗi lần fallback native sẽ trả 1 chunk text từ noopChunker.
	fakeExt.failNext.Store(3)
	for i := 1; i <= 3; i++ {
		chunks, _, err := p.extractAndChunk(ctx, "doc-1", "doc.txt", tmpFile, ".txt", "MEDINET", "auto")
		if err != nil {
			t.Fatalf("call %d: extractAndChunk err = %v", i, err)
		}
		if len(chunks) == 0 {
			t.Fatalf("call %d: expected fallback chunks, got 0", i)
		}
	}

	if state := p.circuit.State(); state != gobreaker.StateOpen {
		t.Fatalf("after 3 fails want StateOpen, got %s", state.String())
	}

	callsBefore := fakeExt.callCount.Load()
	if callsBefore != 3 {
		t.Fatalf("expected exactly 3 docling calls, got %d", callsBefore)
	}

	// Lần 4: circuit open → KHÔNG gọi Docling, fallback native ngay.
	_, _, err := p.extractAndChunk(ctx, "doc-2", "doc.txt", tmpFile, ".txt", "MEDINET", "auto")
	if err != nil {
		t.Fatalf("call 4 fallback err: %v", err)
	}
	if got := fakeExt.callCount.Load(); got != callsBefore {
		t.Fatalf("circuit open: docling must NOT be called, but counter %d → %d", callsBefore, got)
	}

	// Audit phải có entries action="rag_fallback".
	if len(audit.entries) == 0 {
		t.Fatal("expected audit fallback entries, got none")
	}
	for _, e := range audit.entries {
		if e.Action != "rag_fallback" {
			t.Errorf("expected action=rag_fallback, got %s", e.Action)
		}
	}
}

// ─── Test B: half-open after cooldown 100ms — total < 200ms ──────────────────

func TestPipelineCircuit_HalfOpenAfterCooldown_FastTransition(t *testing.T) {
	p, fakeExt, _, _ := newTestPipelineForCircuit(t, "auto", 3, 100*time.Millisecond)
	tmpFile := writeTempFile(t, ".txt", "body")

	ctx := context.Background()

	start := time.Now()

	// Trip circuit: 3 fails consecutive.
	fakeExt.failNext.Store(3)
	for i := 0; i < 3; i++ {
		_, _, _ = p.extractAndChunk(ctx, "doc", "doc.txt", tmpFile, ".txt", "MEDINET", "auto")
	}
	if state := p.circuit.State(); state != gobreaker.StateOpen {
		t.Fatalf("setup: state want open, got %s", state.String())
	}

	// Sleep 120ms > cooldown 100ms.
	time.Sleep(120 * time.Millisecond)

	// Half-open success — fakeExt.failNext = 0 → trả success, circuit close.
	chunks, _, err := p.extractAndChunk(ctx, "doc", "doc.txt", tmpFile, ".txt", "MEDINET", "auto")
	if err != nil {
		t.Fatalf("half-open success extractAndChunk err: %v", err)
	}
	if len(chunks) == 0 {
		t.Fatalf("half-open success: expected chunks, got 0")
	}

	elapsed := time.Since(start)
	if elapsed > 200*time.Millisecond {
		t.Fatalf("transition too slow: %v (want < 200ms — flaky cooldown indicator)", elapsed)
	}

	if state := p.circuit.State(); state != gobreaker.StateClosed {
		t.Fatalf("after half-open success want closed, got %s", state.String())
	}
}

// ─── Test C: half-open fail → open lại, KHÔNG close ──────────────────────────

func TestPipelineCircuit_HalfOpenFail_ReOpens(t *testing.T) {
	p, fakeExt, _, _ := newTestPipelineForCircuit(t, "auto", 3, 100*time.Millisecond)
	tmpFile := writeTempFile(t, ".txt", "body")
	ctx := context.Background()

	// Trip circuit (3 fails).
	fakeExt.failNext.Store(3)
	for i := 0; i < 3; i++ {
		_, _, _ = p.extractAndChunk(ctx, "doc", "doc.txt", tmpFile, ".txt", "MEDINET", "auto")
	}
	if state := p.circuit.State(); state != gobreaker.StateOpen {
		t.Fatalf("setup: want open, got %s", state.String())
	}

	// Cooldown qua → half-open. Set fail thêm 1 để half-open thử fail.
	time.Sleep(120 * time.Millisecond)
	fakeExt.failNext.Store(1)

	_, _, _ = p.extractAndChunk(ctx, "doc", "doc.txt", tmpFile, ".txt", "MEDINET", "auto")

	if state := p.circuit.State(); state != gobreaker.StateOpen {
		t.Fatalf("after half-open fail want open (re-trip), got %s", state.String())
	}
}

// ─── Test D: mode=auto fallback → chunks ≥ 1 + audit insert ──────────────────

func TestPipelineCircuit_AutoFallback_ReturnsChunksAndAuditEntry(t *testing.T) {
	p, fakeExt, audit, _ := newTestPipelineForCircuit(t, "auto", 3, 100*time.Millisecond)
	tmpFile := writeTempFile(t, ".txt", "fallback native produces chunks")
	ctx := context.Background()

	fakeExt.failNext.Store(1)
	chunks, _, err := p.extractAndChunk(ctx, "doc-D", "x.txt", tmpFile, ".txt", "HUB-D", "auto")
	if err != nil {
		t.Fatalf("auto fallback err: %v", err)
	}
	if len(chunks) == 0 {
		t.Fatalf("auto fallback: expected chunks ≥ 1, got 0")
	}

	if len(audit.entries) != 1 {
		t.Fatalf("expected exactly 1 audit entry, got %d", len(audit.entries))
	}
	e := audit.entries[0]
	if e.Action != "rag_fallback" {
		t.Errorf("action want rag_fallback, got %s", e.Action)
	}
	var payload map[string]any
	if err := json.Unmarshal(e.Payload, &payload); err != nil {
		t.Fatalf("payload not valid json: %v", err)
	}
	for _, key := range []string{"document_id", "reason", "circuit_state", "extractor_from", "extractor_to"} {
		if _, ok := payload[key]; !ok {
			t.Errorf("payload missing field %q (have keys: %v)", key, payload)
		}
	}
	if payload["document_id"] != "doc-D" {
		t.Errorf("payload.document_id want doc-D, got %v", payload["document_id"])
	}
	if payload["extractor_from"] != "docling" || payload["extractor_to"] != "native" {
		t.Errorf("extractor_from/to wrong: %v / %v", payload["extractor_from"], payload["extractor_to"])
	}
}

// ─── Test E: mode=docling (hard) + Docling fail → trả error, KHÔNG fallback ──

func TestPipelineCircuit_HardDoclingMode_NoFallbackOnFail(t *testing.T) {
	p, fakeExt, audit, _ := newTestPipelineForCircuit(t, "docling", 3, 100*time.Millisecond)
	tmpFile := writeTempFile(t, ".txt", "would be fallback in auto, but not in docling mode")
	ctx := context.Background()

	fakeExt.failNext.Store(1)
	_, _, err := p.extractAndChunk(ctx, "doc-E", "x.txt", tmpFile, ".txt", "HUB-E", "docling")
	if err == nil {
		t.Fatal("hard docling mode: expected error on Docling fail, got nil")
	}

	// KHÔNG được audit fallback (chỉ branch auto mới audit).
	if len(audit.entries) != 0 {
		t.Errorf("hard docling mode: expected 0 audit entries, got %d", len(audit.entries))
	}
}
