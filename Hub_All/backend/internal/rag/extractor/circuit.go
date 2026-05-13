// Package extractor — DoclingCircuit (M1 Phase 4 CFG-01, CFG-04).
//
// Wrap mọi call sang DoclingExtractor.ExtractStructured() qua sony/gobreaker/v2
// để pipeline mode "auto" tự fallback sang native khi Docling sidecar down.
//
// State sync Redis: workers Go khác nhau share cùng view qua 2 key
// `rag:docling:circuit:state` và `:changed_at`. KHÔNG read-modify-write fail_count
// (gobreaker quản lý in-process; Redis chỉ để observe + admin reset).
package extractor

import (
	"context"
	"log/slog"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/sony/gobreaker/v2"
)

const (
	redisKeyCircuitState     = "rag:docling:circuit:state"
	redisKeyCircuitChangedAt = "rag:docling:circuit:changed_at"
)

// CircuitResult là payload generic của circuit — dùng struct rỗng vì
// pipeline.go gọi Execute(func() error) và bỏ result.
// Kết quả thực (text + chunks) được capture qua closure variable.
type CircuitResult struct{}

// DoclingCircuit gói gobreaker với Redis observability.
// Singleton — main.go khởi tạo 1 lần, share qua các worker.
type DoclingCircuit struct {
	cb     *gobreaker.CircuitBreaker[CircuitResult]
	redis  *redis.Client
	logger *slog.Logger
}

// NewDoclingCircuit khởi tạo wrapper. threshold = consecutive failures trước
// khi open. cooldown = thời gian giữ open trước half-open thử lại.
func NewDoclingCircuit(rdb *redis.Client, threshold uint32, cooldown time.Duration, logger *slog.Logger) *DoclingCircuit {
	if logger == nil {
		logger = slog.Default()
	}
	if threshold == 0 {
		threshold = 3
	}
	if cooldown <= 0 {
		cooldown = 5 * time.Minute
	}

	settings := gobreaker.Settings{
		Name:        "docling-extractor",
		MaxRequests: 1, // half-open: chỉ thử 1 request
		Interval:    0, // 0 = không reset counts theo interval (chỉ reset khi state change)
		Timeout:     cooldown,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			return counts.ConsecutiveFailures >= threshold
		},
		OnStateChange: func(name string, from, to gobreaker.State) {
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			// KHÔNG có TTL — admin reset bằng DEL ở Plan 04-03.
			if rdb != nil {
				if err := rdb.Set(ctx, redisKeyCircuitState, to.String(), 0).Err(); err != nil {
					logger.Warn("circuit redis set state failed", "err", err)
				}
				if err := rdb.Set(ctx, redisKeyCircuitChangedAt, strconv.FormatInt(time.Now().Unix(), 10), 0).Err(); err != nil {
					logger.Warn("circuit redis set changed_at failed", "err", err)
				}
			}
			logger.Info("docling circuit state changed",
				"name", name, "from", from.String(), "to", to.String())
		},
	}

	return &DoclingCircuit{
		cb:     gobreaker.NewCircuitBreaker[CircuitResult](settings),
		redis:  rdb,
		logger: logger,
	}
}

// Execute chạy fn qua circuit breaker. Trả `gobreaker.ErrOpenState` nếu circuit
// đang open. Caller (pipeline.go) check error này để fallback sang native + audit.
func (c *DoclingCircuit) Execute(fn func() error) error {
	_, err := c.cb.Execute(func() (CircuitResult, error) {
		return CircuitResult{}, fn()
	})
	return err
}

// State trả state hiện tại (closed/half-open/open). Dùng ở admin endpoint
// (Plan 04-03 GET /api/rag-config) để báo cáo `docling_circuit_state`.
func (c *DoclingCircuit) State() gobreaker.State {
	return c.cb.State()
}

// Counts trả counts hiện tại (consecutive_failures, total_failures, ...).
// Dùng cho audit log fallback (Plan 04-02).
func (c *DoclingCircuit) Counts() gobreaker.Counts {
	return c.cb.Counts()
}

// Reset xóa state Redis (gọi khi admin PUT extractor_mode khác — Plan 04-03).
// gobreaker không có public Reset(); thay bằng cách DEL Redis state + log;
// in-process state sẽ tự reset sau cooldown hoặc khi 1 success qua half-open.
func (c *DoclingCircuit) Reset(ctx context.Context) error {
	if c.redis == nil {
		return nil
	}
	if err := c.redis.Del(ctx, redisKeyCircuitState, redisKeyCircuitChangedAt).Err(); err != nil {
		return err
	}
	c.logger.Info("docling circuit redis state cleared by admin")
	return nil
}
