// docling_test.go — unit test cho DoclingExtractor (Plan 03-05).
//
// Dùng net/http/httptest.Server để mock service docling-pipeline (Phase 2 Python sidecar).
// Verify retry semantics (WIRE-01) + header propagation X-Request-Id (WIRE-06) + parse
// schema DSVC-02 + map metadata.
//
// 7 test case:
//  1. Success happy path (200 OK, 2 chunks, metadata đầy đủ).
//  2. 413 Payload Too Large — KHÔNG retry, chỉ 1 request.
//  3. 504 Gateway Timeout — KHÔNG retry, chỉ 1 request.
//  4. Network error (connection close) — retry 2 lần (tổng 3 attempts) rồi fail.
//  5. 500 → 200 recover sau 1 retry.
//  6. Header X-Request-Id propagate đúng từ ctx sang HTTP request.
//  7. Ctx cancel giữa retry — return ctx error ngay.
package extractor

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/medinet/hub-all-backend/internal/pkg/requestid"
)

const fixturePath = "testdata/sample.pdf"

// mockHandler ghi nhận request count + cho phép tùy biến response per-attempt.
//
// statusByAttempt: status code cho từng attempt (theo thứ tự); nếu nil hoặc index
// vượt quá length → trả 200 với defaultSuccessBody.
// closeConn: nếu true → hijack + close connection ngay → simulate network error.
type mockHandler struct {
	requestCount    atomic.Int32
	capturedRID     atomic.Value // string — header X-Request-Id của request cuối
	capturedFile    atomic.Bool  // form có field "file"
	statusByAttempt []int
	responseBody    string
	closeConn       bool
}

func (m *mockHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	n := m.requestCount.Add(1)
	m.capturedRID.Store(r.Header.Get(requestid.HeaderName))

	// Parse multipart để verify field "file" tồn tại.
	if err := r.ParseMultipartForm(10 << 20); err == nil {
		if _, _, err := r.FormFile("file"); err == nil {
			m.capturedFile.Store(true)
		}
	}

	if m.closeConn {
		// Hijack + close để simulate network error / connection reset.
		hj, ok := w.(http.Hijacker)
		if ok {
			conn, _, _ := hj.Hijack()
			_ = conn.Close()
		}
		return
	}

	status := http.StatusOK
	if int(n)-1 < len(m.statusByAttempt) {
		status = m.statusByAttempt[int(n)-1]
	}

	if status == http.StatusOK {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		body := m.responseBody
		if body == "" {
			body = defaultSuccessBody
		}
		_, _ = io.WriteString(w, body)
		return
	}

	w.WriteHeader(status)
	_, _ = io.WriteString(w, fmt.Sprintf(`{"error":"mock %d"}`, status))
}

// defaultSuccessBody khớp schema DSVC-02 (Phase 2 contract):
// 2 chunks — 1 text với headers ["Heading"] page 1, 1 table với is_table=true page 2.
const defaultSuccessBody = `{
  "request_id": "rid-from-server",
  "doc_meta": {"filename":"sample.pdf","page_count":2,"doc_type":"pdf","ocr_used":false},
  "chunks": [
    {"chunk_index":0,"text":"# Heading\n\nFirst chunk","headers":["Heading"],"caption":null,"page_start":1,"page_end":1,"is_table":false,"table_html":null,"bbox":null,"token_count":42},
    {"chunk_index":1,"text":"| col1 | col2 |\n|---|---|\n| a | b |","headers":["Heading","Sub"],"caption":null,"page_start":2,"page_end":2,"is_table":true,"table_html":"<table><tr><td>a</td><td>b</td></tr></table>","bbox":[10.0,20.0,300.0,400.0],"token_count":18}
  ]
}`

// newTestServer trả httptest.Server bind handler. Caller phải defer Close.
func newTestServer(h http.Handler) *httptest.Server {
	return httptest.NewServer(h)
}

// newTestExtractor tạo DoclingExtractor trỏ tới mock URL với timeout 30s
// (đủ buffer cho 1s+2s retry, không kéo dài test khi mock trả nhanh).
func newTestExtractor(baseURL string) *DoclingExtractor {
	return NewDoclingExtractor(baseURL, 30)
}

// ─── 1. Success happy path ───
func TestDoclingExtractor_Success(t *testing.T) {
	h := &mockHandler{}
	srv := newTestServer(h)
	defer srv.Close()
	ext := newTestExtractor(srv.URL)

	text, chunks, err := ext.ExtractStructured(context.Background(), fixturePath)
	if err != nil {
		t.Fatalf("expected nil error, got %v", err)
	}
	if got := h.requestCount.Load(); got != 1 {
		t.Errorf("expected 1 request, got %d", got)
	}
	if !h.capturedFile.Load() {
		t.Error("expected multipart field 'file' to be present")
	}
	if len(chunks) != 2 {
		t.Fatalf("expected 2 chunks, got %d", len(chunks))
	}

	// Chunk 0 — text.
	if chunks[0].Index != 0 {
		t.Errorf("chunk 0: Index expected 0, got %d", chunks[0].Index)
	}
	if chunks[0].TokenCount != 42 {
		t.Errorf("chunk 0: TokenCount expected 42, got %d", chunks[0].TokenCount)
	}
	if chunks[0].ChunkType != "docling_text" {
		t.Errorf("chunk 0: ChunkType expected docling_text, got %q", chunks[0].ChunkType)
	}
	if v, _ := chunks[0].Metadata["source"].(string); v != "docling" {
		t.Errorf("chunk 0: metadata.source expected 'docling', got %v", chunks[0].Metadata["source"])
	}
	if hs, _ := chunks[0].Metadata["headers"].([]string); len(hs) == 0 || hs[0] != "Heading" {
		t.Errorf("chunk 0: metadata.headers expected [Heading], got %v", chunks[0].Metadata["headers"])
	}
	if v, _ := chunks[0].Metadata["page_start"].(int); v != 1 {
		t.Errorf("chunk 0: page_start expected 1, got %v", chunks[0].Metadata["page_start"])
	}
	if v, _ := chunks[0].Metadata["is_table"].(bool); v {
		t.Errorf("chunk 0: is_table expected false, got true")
	}

	// Chunk 1 — table.
	if chunks[1].ChunkType != "docling_table" {
		t.Errorf("chunk 1: ChunkType expected docling_table, got %q", chunks[1].ChunkType)
	}
	if v, _ := chunks[1].Metadata["is_table"].(bool); !v {
		t.Errorf("chunk 1: metadata.is_table expected true")
	}
	if v, _ := chunks[1].Metadata["table_html"].(string); !strings.Contains(v, "<table>") {
		t.Errorf("chunk 1: metadata.table_html missing or wrong: %v", chunks[1].Metadata["table_html"])
	}
	if bbox, _ := chunks[1].Metadata["bbox"].([]float64); len(bbox) != 4 {
		t.Errorf("chunk 1: metadata.bbox expected len=4, got %v", chunks[1].Metadata["bbox"])
	}

	if !strings.Contains(text, "First chunk") || !strings.Contains(text, "col1") {
		t.Errorf("text concat wrong: %q", text)
	}
}

// ─── 2. 413 Payload Too Large — KHÔNG retry ───
func TestDoclingExtractor_413_NoRetry(t *testing.T) {
	h := &mockHandler{statusByAttempt: []int{http.StatusRequestEntityTooLarge}}
	srv := newTestServer(h)
	defer srv.Close()
	ext := newTestExtractor(srv.URL)

	_, _, err := ext.ExtractStructured(context.Background(), fixturePath)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "client error") && !strings.Contains(err.Error(), "413") {
		t.Errorf("expected 'client error' or '413' in error, got %v", err)
	}
	if got := h.requestCount.Load(); got != 1 {
		t.Errorf("expected 1 request (no retry on 4xx), got %d", got)
	}
}

// ─── 3. 504 Gateway Timeout — KHÔNG retry ───
func TestDoclingExtractor_504_NoRetry(t *testing.T) {
	h := &mockHandler{statusByAttempt: []int{http.StatusGatewayTimeout}}
	srv := newTestServer(h)
	defer srv.Close()
	ext := newTestExtractor(srv.URL)

	_, _, err := ext.ExtractStructured(context.Background(), fixturePath)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "timeout") {
		t.Errorf("expected 'timeout' in error, got %v", err)
	}
	if got := h.requestCount.Load(); got != 1 {
		t.Errorf("expected 1 request (no retry on 504), got %d", got)
	}
}

// ─── 4. Network error → retry 2 lần fail ───
func TestDoclingExtractor_NetworkError_Retry(t *testing.T) {
	h := &mockHandler{closeConn: true}
	srv := newTestServer(h)
	defer srv.Close()
	ext := newTestExtractor(srv.URL)

	start := time.Now()
	_, _, err := ext.ExtractStructured(context.Background(), fixturePath)
	elapsed := time.Since(start)

	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "unreachable") && !strings.Contains(err.Error(), "after 3 attempts") {
		t.Errorf("expected 'unreachable after 3 attempts', got %v", err)
	}
	if got := h.requestCount.Load(); got != 3 {
		t.Errorf("expected 3 requests (1 + 2 retry), got %d", got)
	}
	// Tổng delay tối thiểu = 1s + 2s = 3s.
	if elapsed < 2900*time.Millisecond {
		t.Errorf("expected ≥ 2.9s elapsed (backoff 1s+2s), got %s", elapsed)
	}
}

// ─── 5. 500 → 200 recover ───
func TestDoclingExtractor_500_Then_200(t *testing.T) {
	h := &mockHandler{statusByAttempt: []int{http.StatusInternalServerError, http.StatusOK}}
	srv := newTestServer(h)
	defer srv.Close()
	ext := newTestExtractor(srv.URL)

	_, chunks, err := ext.ExtractStructured(context.Background(), fixturePath)
	if err != nil {
		t.Fatalf("expected success after retry, got %v", err)
	}
	if len(chunks) != 2 {
		t.Errorf("expected 2 chunks from default body, got %d", len(chunks))
	}
	if got := h.requestCount.Load(); got != 2 {
		t.Errorf("expected 2 requests (1 fail + 1 success), got %d", got)
	}
}

// ─── 6. Header X-Request-Id propagation (WIRE-06) ───
func TestDoclingExtractor_RequestIDPropagation(t *testing.T) {
	h := &mockHandler{}
	srv := newTestServer(h)
	defer srv.Close()
	ext := newTestExtractor(srv.URL)

	ctx := requestid.With(context.Background(), "test-rid-xyz-123")
	_, _, err := ext.ExtractStructured(ctx, fixturePath)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	captured, _ := h.capturedRID.Load().(string)
	if captured != "test-rid-xyz-123" {
		t.Errorf("expected X-Request-Id 'test-rid-xyz-123' propagated, got %q", captured)
	}
}

// ─── 7. (Optional) Ctx cancel giữa retry ───
func TestDoclingExtractor_CtxCancel(t *testing.T) {
	h := &mockHandler{statusByAttempt: []int{http.StatusInternalServerError, http.StatusInternalServerError, http.StatusOK}}
	srv := newTestServer(h)
	defer srv.Close()
	ext := newTestExtractor(srv.URL)

	// Deadline 500ms — không đủ cho backoff 1s đầu tiên → ctx cancel trước attempt 2.
	ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
	defer cancel()

	_, _, err := ext.ExtractStructured(ctx, fixturePath)
	if err == nil {
		t.Fatal("expected ctx error, got nil")
	}
	if !strings.Contains(err.Error(), "context") && !strings.Contains(err.Error(), "deadline") {
		t.Errorf("expected ctx deadline error, got %v", err)
	}
	// Chỉ kịp 1 request trước khi backoff 1s vượt deadline 500ms.
	if got := h.requestCount.Load(); got > 2 {
		t.Errorf("expected ≤ 2 requests before ctx cancel, got %d", got)
	}
}
