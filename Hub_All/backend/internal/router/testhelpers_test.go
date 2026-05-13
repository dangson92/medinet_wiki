// Package router — test helpers chia sẻ cho các *_test.go (Plan 04-04 W5).
//
// W5 LOCKED: helper `loginAdmin` ký JWT THẬT bằng test jwtManager instance
// (RSA 2048 generated runtime). KHÔNG dùng env-bypass middleware — đây là
// integration test cho admin endpoint, JWT thật đảm bảo middleware
// `JWTAuth + RequireRole("admin")` chạy đúng path production.
package router

import (
	"crypto/rand"
	"crypto/rsa"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"github.com/medinet/hub-all-backend/internal/config"
	jwtpkg "github.com/medinet/hub-all-backend/internal/pkg/jwt"
)

// newTestJWTManager sinh RSA 2048 in-memory + trả Manager dùng key đó.
// File `_test.go` không build vào binary production → key chỉ tồn tại trong
// test process. KHÔNG dùng key production.
func newTestJWTManager(t *testing.T) *jwtpkg.Manager {
	t.Helper()
	priv, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa.GenerateKey: %v", err)
	}
	return jwtpkg.NewManagerWithKeys(priv, &priv.PublicKey, 15*time.Minute, 168*time.Hour)
}

// loginAdmin trả JWT access token hợp lệ ký với role="admin".
// Dùng cho integration test admin endpoint (W5 — KHÔNG bypass middleware).
func loginAdmin(t *testing.T, mgr *jwtpkg.Manager) string {
	t.Helper()
	pair, err := mgr.GenerateTokenPair(
		uuid.New().String(),
		"admin@test.local",
		"Test Admin",
		"",      // hubID
		"admin", // role — phải khớp với RequireRole("admin")
		"",      // subdomain
	)
	if err != nil {
		t.Fatalf("loginAdmin GenerateTokenPair: %v", err)
	}
	return pair.AccessToken
}

// newTestRedis tạo miniredis + client cleanup tự động.
func newTestRedis(t *testing.T) (*redis.Client, *miniredis.Miniredis) {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("miniredis.Run: %v", err)
	}
	t.Cleanup(mr.Close)
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = rdb.Close() })
	return rdb, mr
}

// newTestConfig minimal config cho test router — chỉ field admin endpoint dùng.
func newTestConfig() *config.Config {
	return &config.Config{
		App: config.AppConfig{Env: "test", Port: "0"},
		CORS: config.CORSConfig{AllowedOrigins: "*"},
		RateLimit: config.RateLimitConfig{RPS: 1000, Burst: 1000},
		RAG: config.RAGConfig{
			EmbeddingProvider:    "openai",
			EmbeddingModel:       "text-embedding-3-small",
			ChunkSize:            512,
			ChunkOverlap:         50,
			BatchSize:            100,
			Extractor:            "native",
			DoclingFailThreshold: 3,
			DoclingCooldownMin:   5,
			DoclingOCRLangs:      "vie+eng",
		},
	}
}
