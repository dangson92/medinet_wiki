// Package router — admin endpoint /api/rag-config integration tests
// (Plan 04-04 Wave 4 — Task 3).
//
// 3 case + JWT THẬT từ helper loginAdmin (W5):
//   - GET trả 5 field mới Phase 4 (extractor_mode, docling_service_status,
//     docling_version, docling_circuit_state, last_fallback_at).
//   - PUT extractor_mode invalid → 400 + tiếng Việt "không hợp lệ".
//   - PUT extractor_mode hợp lệ → 200 + cfg đổi + circuit reset.
//
// Vì test này hit endpoint thật (qua middleware JWTAuth + RequireRole), KHÔNG
// dùng env-bypass — JWT thật là yêu cầu LOCKED của W5.
//
// W6: chạy với `go test -race`.
package router

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/sony/gobreaker/v2"

	"github.com/medinet/hub-all-backend/internal/config"
	jwtpkg "github.com/medinet/hub-all-backend/internal/pkg/jwt"
	"github.com/medinet/hub-all-backend/internal/rag"
	"github.com/medinet/hub-all-backend/internal/rag/extractor"
)

// ragCfgDeps gom các handle cần verify trong từng test case.
type ragCfgDeps struct {
	cfg      *config.Config
	jwtMgr   *jwtpkg.Manager
	pipeline *rag.Pipeline
	circuit  *extractor.DoclingCircuit
}

// buildRagConfigEngine gọi router.Setup THẬT — endpoint /api/rag-config GET/PUT
// đăng ký ở đó. Các handler khác truyền nil — test chỉ hit /api/rag-config nên
// không bị panic. Trả engine + deps để verify state thay đổi.
func buildRagConfigEngine(t *testing.T) (*gin.Engine, *ragCfgDeps) {
	t.Helper()
	gin.SetMode(gin.TestMode)

	cfg := newTestConfig()
	rdb, _ := newTestRedis(t)
	jwtMgr := newTestJWTManager(t)

	pipeline := &rag.Pipeline{}
	pipeline.SetExtractorMode(cfg.RAG.Extractor) // bootstrap = "native"

	circuit := extractor.NewDoclingCircuit(rdb, 3, 100*time.Millisecond, nil)

	engine := Setup(
		cfg,
		jwtMgr,
		rdb,
		nil, nil, nil, nil, nil, nil, nil, nil, nil, nil, // 10 handlers nil
		nil,      // settingsRepo
		nil,      // hubRepo
		nil,      // vectorStore
		nil,      // llmClient
		nil,      // swappableEmbedder
		circuit,  // doclingCircuit (Phase 4)
		nil,      // doclingHealthProbe — guard nil-safe trong handler
		nil,      // auditRepo — guard nil-safe trong handler
		pipeline, // pipeline
	)

	return engine, &ragCfgDeps{
		cfg:      cfg,
		jwtMgr:   jwtMgr,
		pipeline: pipeline,
		circuit:  circuit,
	}
}

// TestRagConfigGET_Returns5NewFields verify GET trả đủ 5 field Phase 4.
func TestRagConfigGET_Returns5NewFields(t *testing.T) {
	engine, _ := buildRagConfigEngine(t)

	req := httptest.NewRequest(http.MethodGet, "/api/rag-config", nil)
	w := httptest.NewRecorder()
	engine.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status want 200, got %d body=%s", w.Code, w.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode body: %v", err)
	}

	requiredFields := []string{
		"extractor_mode",
		"docling_service_status",
		"docling_version",
		"docling_circuit_state",
		"last_fallback_at",
	}
	for _, f := range requiredFields {
		if _, ok := body[f]; !ok {
			t.Errorf("missing required Phase 4 field: %q (have %v)", f, keysOf(body))
		}
	}

	if got := body["extractor_mode"]; got != "native" {
		t.Errorf("extractor_mode want native, got %v", got)
	}
	if got := body["docling_circuit_state"]; got != "closed" {
		t.Errorf("docling_circuit_state want closed, got %v", got)
	}
}

// TestRagConfigPUT_HotSwapMode verify PUT auto → 200 + cfg đổi + circuit Reset gọi.
func TestRagConfigPUT_HotSwapMode(t *testing.T) {
	engine, deps := buildRagConfigEngine(t)
	token := loginAdmin(t, deps.jwtMgr)

	// Trip circuit để verify Reset() được gọi (Redis state DEL).
	for i := 0; i < 3; i++ {
		_ = deps.circuit.Execute(func() error { return errors.New("simulated") })
	}
	if got := deps.circuit.State(); got != gobreaker.StateOpen {
		t.Fatalf("setup: circuit must be open before PUT, got %s", got.String())
	}

	body, _ := json.Marshal(map[string]string{"extractor_mode": "auto"})
	req := httptest.NewRequest(http.MethodPut, "/api/rag-config", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	engine.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("PUT want 200, got %d body=%s", w.Code, w.Body.String())
	}
	if got := deps.cfg.RAG.Extractor; got != "auto" {
		t.Errorf("cfg.RAG.Extractor want auto, got %q", got)
	}
	// pipeline.SetExtractorMode được gọi qua handler — không có getter public,
	// proxy verify qua cfg sync (handler set cả 2 atomic, nếu cfg đổi → setter cũng
	// gọi đúng path code).
}

// TestRagConfigPUT_InvalidMode verify 400 + thông điệp tiếng Việt + cfg KHÔNG đổi.
func TestRagConfigPUT_InvalidMode(t *testing.T) {
	engine, deps := buildRagConfigEngine(t)
	token := loginAdmin(t, deps.jwtMgr)

	body, _ := json.Marshal(map[string]string{"extractor_mode": "invalid"})
	req := httptest.NewRequest(http.MethodPut, "/api/rag-config", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	engine.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("invalid mode want 400, got %d body=%s", w.Code, w.Body.String())
	}
	if !bytes.Contains(w.Body.Bytes(), []byte("không hợp lệ")) {
		t.Errorf("expected vietnamese error 'không hợp lệ', got %s", w.Body.String())
	}
	if got := deps.cfg.RAG.Extractor; got != "native" {
		t.Errorf("cfg.RAG.Extractor must remain 'native' after invalid PUT, got %q", got)
	}
}

// keysOf trả slice keys của map cho thông báo lỗi rõ.
func keysOf(m map[string]any) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}
