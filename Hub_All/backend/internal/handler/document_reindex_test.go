// Package handler — test cho POST /api/documents/:id/reindex (CFG-07 M1 Phase 4).
//
// 4 case bắt buộc:
//  1. Happy path 202 — admin reindex doc tồn tại → mock service nhận đúng args.
//  2. 404 Not Found — service trả "document not found".
//  3. 403 Forbidden — viewer role bị middleware RequireRole("admin") chặn.
//  4. 400 Invalid extractor — query param không thuộc {docling,native,auto}.
//
// Test dùng mock interface DocumentReindexer (không cần Postgres/ChromaDB thật).
// Middleware JWTAuth được giả lập bằng injectRole helper — set role + user_id
// vào gin.Context giống production middleware.
//
// Race-safe: mock dùng sync.Mutex bảo vệ counters + captured args.
package handler

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/medinet/hub-all-backend/internal/middleware"
	"github.com/medinet/hub-all-backend/internal/model"
)

// ─── Mock reindexer ────────────────────────────────────────────────

type mockReindexer struct {
	mu    sync.Mutex
	calls int
	// Captured args last call
	gotID         string
	gotExtractor  string
	gotRequester  string
	// Stub return
	returnDoc *model.Document
	returnErr error
}

func (m *mockReindexer) Reindex(_ context.Context, id, extractor, requesterID string) (*model.Document, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.calls++
	m.gotID = id
	m.gotExtractor = extractor
	m.gotRequester = requesterID
	return m.returnDoc, m.returnErr
}

func (m *mockReindexer) Calls() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.calls
}

// ─── Test helpers ──────────────────────────────────────────────────

// injectRole giả lập output JWTAuth middleware: set user_id + role vào ctx.
// KHÔNG verify token — test focus 403/202 mapping của handler + RequireRole.
func injectRole(userID, role string) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Set(string(middleware.ContextUserID), userID)
		c.Set(string(middleware.ContextRole), role)
		c.Next()
	}
}

// buildReindexEngine tạo gin engine minimal với route reindex + middleware
// stack giống production (auth-injected → RequireRole("admin") → handler).
func buildReindexEngine(role, userID string, mock *mockReindexer) (*gin.Engine, *DocumentHandler) {
	gin.SetMode(gin.TestMode)
	r := gin.New()

	h := &DocumentHandler{}
	h.SetReindexer(mock)
	h.SetDefaultExtractorGetter(func() string { return "auto" })

	// Group bắt chước router production: docs.Use(JWTAuth) → docsAdmin.Use(RequireRole)
	docs := r.Group("/api/documents")
	docs.Use(injectRole(userID, role))
	docsAdmin := docs.Group("")
	docsAdmin.Use(middleware.RequireRole("admin"))
	docsAdmin.POST("/:id/reindex", h.Reindex)

	return r, h
}

func newPendingDoc(id uuid.UUID, name string) *model.Document {
	return &model.Document{
		ID:         id,
		Name:       name,
		FileType:   "pdf",
		FileSize:   1024,
		FilePath:   "/tmp/" + name,
		HubID:      uuid.New(),
		Status:     "pending",
		Progress:   0,
		ChunkCount: 0,
		UploadedBy: uuid.New(),
		UploadedAt: time.Now().UTC(),
	}
}

// ─── 4 case bắt buộc ──────────────────────────────────────────────

// Case 1: Happy path 202 — admin POST với extractor=docling → handler gọi
// mock.Reindex đúng args + trả 202 + body chứa document field id.
func TestDocumentReindex_Admin_HappyPath_202(t *testing.T) {
	docID := uuid.New()
	mock := &mockReindexer{
		returnDoc: newPendingDoc(docID, "test.pdf"),
		returnErr: nil,
	}
	adminID := uuid.New().String()
	engine, _ := buildReindexEngine("admin", adminID, mock)

	url := fmt.Sprintf("/api/documents/%s/reindex?extractor=docling", docID.String())
	req := httptest.NewRequest(http.MethodPost, url, nil)
	w := httptest.NewRecorder()
	engine.ServeHTTP(w, req)

	if w.Code != http.StatusAccepted {
		t.Fatalf("status want 202, got %d body=%s", w.Code, w.Body.String())
	}
	if mock.Calls() != 1 {
		t.Errorf("expected 1 service call, got %d", mock.Calls())
	}
	if mock.gotID != docID.String() {
		t.Errorf("doc id mismatch: want %s, got %s", docID.String(), mock.gotID)
	}
	if mock.gotExtractor != "docling" {
		t.Errorf("extractor mismatch: want docling, got %s", mock.gotExtractor)
	}
	if mock.gotRequester != adminID {
		t.Errorf("requester mismatch: want %s, got %s", adminID, mock.gotRequester)
	}

	// Body shape: response.Accepted wraps {success:true, data:document}
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode body: %v", err)
	}
	if body["success"] != true {
		t.Errorf("body.success want true, got %v", body["success"])
	}
	data, ok := body["data"].(map[string]any)
	if !ok {
		t.Fatalf("body.data must be object, got %T", body["data"])
	}
	if data["status"] != "pending" {
		t.Errorf("data.status want pending, got %v", data["status"])
	}
	if data["id"] != docID.String() {
		t.Errorf("data.id mismatch: want %s, got %v", docID.String(), data["id"])
	}
}

// Case 2: 404 Not Found — service trả lỗi "document not found" → handler
// map về 404. Mock VẪN được gọi (validation extractor pass trước khi tới
// service); count = 1.
func TestDocumentReindex_NotFound_404(t *testing.T) {
	mock := &mockReindexer{
		returnDoc: nil,
		returnErr: fmt.Errorf("document not found"),
	}
	engine, _ := buildReindexEngine("admin", uuid.New().String(), mock)

	unknownID := uuid.New().String()
	url := fmt.Sprintf("/api/documents/%s/reindex?extractor=auto", unknownID)
	req := httptest.NewRequest(http.MethodPost, url, nil)
	w := httptest.NewRecorder()
	engine.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("status want 404, got %d body=%s", w.Code, w.Body.String())
	}
	if !bytes.Contains(w.Body.Bytes(), []byte("document not found")) {
		t.Errorf("body should contain 'document not found', got %s", w.Body.String())
	}
}

// Case 3: 403 Forbidden — viewer role bị RequireRole("admin") từ chối.
// Mock KHÔNG được gọi (middleware abort trước khi tới handler).
func TestDocumentReindex_Viewer_403(t *testing.T) {
	mock := &mockReindexer{
		returnDoc: newPendingDoc(uuid.New(), "x.pdf"),
	}
	engine, _ := buildReindexEngine("viewer", uuid.New().String(), mock)

	url := fmt.Sprintf("/api/documents/%s/reindex?extractor=docling", uuid.New().String())
	req := httptest.NewRequest(http.MethodPost, url, nil)
	w := httptest.NewRecorder()
	engine.ServeHTTP(w, req)

	if w.Code != http.StatusForbidden {
		t.Fatalf("status want 403, got %d body=%s", w.Code, w.Body.String())
	}
	if mock.Calls() != 0 {
		t.Errorf("service must NOT be called for viewer, got %d calls", mock.Calls())
	}
}

// Case 4: 400 Invalid extractor — query ?extractor=foo → service trả
// "invalid extractor ..." → handler map về 400. Doc KHÔNG bị reset
// (service trả lỗi trước khi đụng DB — đây là contract validate đầu hàm).
func TestDocumentReindex_InvalidExtractor_400(t *testing.T) {
	mock := &mockReindexer{
		returnDoc: nil,
		returnErr: fmt.Errorf(`invalid extractor "foo" (must be docling|native|auto)`),
	}
	engine, _ := buildReindexEngine("admin", uuid.New().String(), mock)

	docID := uuid.New().String()
	url := fmt.Sprintf("/api/documents/%s/reindex?extractor=foo", docID)
	req := httptest.NewRequest(http.MethodPost, url, nil)
	w := httptest.NewRecorder()
	engine.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("status want 400, got %d body=%s", w.Code, w.Body.String())
	}
	if !bytes.Contains(w.Body.Bytes(), []byte("invalid extractor")) {
		t.Errorf("body should contain 'invalid extractor', got %s", w.Body.String())
	}
	// Verify mock đã thấy extractor=foo (handler propagate đúng query param sang service).
	if mock.gotExtractor != "foo" {
		t.Errorf("expected extractor=foo passed to service, got %s", mock.gotExtractor)
	}
}
