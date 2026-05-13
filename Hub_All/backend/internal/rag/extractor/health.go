// Package extractor — DoclingHealthProbe (M1 Phase 4 CFG-03).
//
// On-demand health check service docling-pipeline. Cache result 30s trong Redis
// để tránh spam /healthz mỗi job (worker pool 4-8 jobs concurrent).
//
// Pattern: lazy probe — chỉ gọi khi admin GET /api/rag-config hoặc trước job
// ingestion ở mode "auto". KHÔNG dùng background poller (rủi ro goroutine leak).
package extractor

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	redisKeyHealth     = "rag:docling:health"
	redisKeyVersion    = "rag:docling:version"
	healthCacheTTL     = 30 * time.Second
	versionCacheTTL    = 5 * time.Minute
	healthProbeTimeout = 3 * time.Second
)

// HealthStatus là enum-like string trả về cho admin endpoint.
type HealthStatus string

const (
	HealthHealthy  HealthStatus = "healthy"  // /healthz 200 + /readyz 200
	HealthDegraded HealthStatus = "degraded" // /healthz 200 + /readyz != 200 (models warming)
	HealthDown     HealthStatus = "down"     // /healthz lỗi hoặc != 200
)

// DoclingHealthProbe gọi GET /healthz + /readyz với cache 30s.
type DoclingHealthProbe struct {
	baseURL    string
	redis      *redis.Client
	httpClient *http.Client
}

// NewDoclingHealthProbe khởi tạo từ config.
func NewDoclingHealthProbe(baseURL string, rdb *redis.Client) *DoclingHealthProbe {
	return &DoclingHealthProbe{
		baseURL: strings.TrimRight(baseURL, "/"),
		redis:   rdb,
		httpClient: &http.Client{
			Timeout: healthProbeTimeout,
		},
	}
}

// Status trả health hiện tại. Cache 30s qua Redis. Nếu cache miss → probe live.
func (h *DoclingHealthProbe) Status(ctx context.Context) HealthStatus {
	if h.redis != nil {
		if cached, err := h.redis.Get(ctx, redisKeyHealth).Result(); err == nil && cached != "" {
			return HealthStatus(cached)
		}
	}

	status := h.probe(ctx)
	if h.redis != nil {
		_ = h.redis.Set(ctx, redisKeyHealth, string(status), healthCacheTTL).Err()
	}
	return status
}

// Version trả Docling version từ /readyz response. Cache 5 phút (ít đổi).
// Trả "" nếu probe fail.
func (h *DoclingHealthProbe) Version(ctx context.Context) string {
	if h.redis != nil {
		if cached, err := h.redis.Get(ctx, redisKeyVersion).Result(); err == nil {
			return cached
		}
	}

	v := h.probeVersion(ctx)
	if v != "" && h.redis != nil {
		_ = h.redis.Set(ctx, redisKeyVersion, v, versionCacheTTL).Err()
	}
	return v
}

func (h *DoclingHealthProbe) probe(ctx context.Context) HealthStatus {
	// /healthz check
	healthOK := h.getStatusCode(ctx, "/healthz") == http.StatusOK
	if !healthOK {
		return HealthDown
	}
	// /readyz check
	readyOK := h.getStatusCode(ctx, "/readyz") == http.StatusOK
	if !readyOK {
		return HealthDegraded
	}
	return HealthHealthy
}

func (h *DoclingHealthProbe) getStatusCode(ctx context.Context, path string) int {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, h.baseURL+path, nil)
	if err != nil {
		return 0
	}
	resp, err := h.httpClient.Do(req)
	if err != nil {
		return 0
	}
	defer resp.Body.Close()
	return resp.StatusCode
}

// probeVersion gọi /readyz và parse field "version" hoặc "docling_version" từ JSON.
func (h *DoclingHealthProbe) probeVersion(ctx context.Context) string {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, h.baseURL+"/readyz", nil)
	if err != nil {
		return ""
	}
	resp, err := h.httpClient.Do(req)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return ""
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if err != nil {
		return ""
	}
	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		return ""
	}
	if v, ok := payload["docling_version"].(string); ok && v != "" {
		return v
	}
	if v, ok := payload["version"].(string); ok {
		return v
	}
	return ""
}
