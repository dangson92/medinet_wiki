// Package extractor — DoclingHealthProbe tests (Plan 04-04 Wave 4 — Task 2).
//
// 4 case mock httptest.Server stub /healthz + /readyz:
//   - Healthy:  /healthz 200 + /readyz 200 → "healthy".
//   - Degraded: /healthz 200 + /readyz 503 → "degraded".
//   - Down:     baseURL không reachable  → "down".
//   - Cache30s: 2 lần Status() liên tiếp → server chỉ nhận 1 GET (cache 30s Redis).
//
// W6: chạy với `go test -race`.
package extractor

import (
	"context"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

// newProbeRedis tạo miniredis + redis.Client cleanup tự động.
func newProbeRedis(t *testing.T) (*redis.Client, *miniredis.Miniredis) {
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

func TestHealthProbe_HealthyResponse(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/healthz":
			w.WriteHeader(http.StatusOK)
		case "/readyz":
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"docling_version":"2.91.0"}`))
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer ts.Close()

	rdb, _ := newProbeRedis(t)
	h := NewDoclingHealthProbe(ts.URL, rdb)

	if status := h.Status(context.Background()); status != HealthHealthy {
		t.Fatalf("want healthy, got %s", status)
	}
	if v := h.Version(context.Background()); v != "2.91.0" {
		t.Fatalf("want version 2.91.0, got %q", v)
	}
}

func TestHealthProbe_DegradedReadyzFail(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/healthz":
			w.WriteHeader(http.StatusOK)
		case "/readyz":
			w.WriteHeader(http.StatusServiceUnavailable)
		}
	}))
	defer ts.Close()

	rdb, _ := newProbeRedis(t)
	h := NewDoclingHealthProbe(ts.URL, rdb)

	if status := h.Status(context.Background()); status != HealthDegraded {
		t.Fatalf("want degraded, got %s", status)
	}
}

func TestHealthProbe_DownWhenUnreachable(t *testing.T) {
	rdb, _ := newProbeRedis(t)
	// Port 1 trên localhost luôn từ chối kết nối → /healthz fail → down.
	h := NewDoclingHealthProbe("http://127.0.0.1:1", rdb)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if status := h.Status(ctx); status != HealthDown {
		t.Fatalf("want down, got %s", status)
	}
}

func TestHealthProbe_CacheHit_NoSecondGET(t *testing.T) {
	var calls int32
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		atomic.AddInt32(&calls, 1)
		w.WriteHeader(http.StatusOK)
	}))
	defer ts.Close()

	rdb, mr := newProbeRedis(t)
	h := NewDoclingHealthProbe(ts.URL, rdb)

	ctx := context.Background()
	_ = h.Status(ctx) // miss → probe → cache set
	first := atomic.LoadInt32(&calls)
	if first < 1 {
		t.Fatalf("first probe must hit server at least once, got %d", first)
	}

	// 2 lần kế tiếp PHẢI hit cache (Redis key TTL 30s).
	_ = h.Status(ctx)
	_ = h.Status(ctx)
	after := atomic.LoadInt32(&calls)
	if after != first {
		t.Fatalf("cache miss: server got %d new calls (expected 0)", after-first)
	}

	// FastForward miniredis qua TTL 31s → cache expire → probe lại.
	mr.FastForward(31 * time.Second)
	_ = h.Status(ctx)
	if atomic.LoadInt32(&calls) <= after {
		t.Fatalf("after cache expire, expected new probe call; got total %d (was %d)", atomic.LoadInt32(&calls), after)
	}
}
