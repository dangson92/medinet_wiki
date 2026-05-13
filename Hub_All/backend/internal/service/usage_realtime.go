package service

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"sort"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/medinet/hub-all-backend/internal/model"
)

// UsageRealtime provides the sub-100ms "last hour" counter that sits in
// front of the Postgres rollup. It uses Redis HINCRBY on per-minute hash
// keys — one key per minute holds multiple fields (total_calls, total_tokens,
// plus per-provider / per-operation counters). The dashboard reads the
// last 60 minutes in a single pipelined call.
//
// Failure mode: if Redis is down, the logger skips the Increment() path
// and the dashboard falls back to the 5min rollup (trễ ~10s). Accuracy
// degradation is gradual, never catastrophic.
type UsageRealtime struct {
	rdb    *redis.Client
	window time.Duration // how far back the `/realtime` endpoint reads
}

func NewUsageRealtime(rdb *redis.Client) *UsageRealtime {
	return &UsageRealtime{rdb: rdb, window: 60 * time.Minute}
}

const (
	realtimeKeyTTL = 2 * time.Hour // buffer beyond window so slow reads still hit
)

func rtKey(minute time.Time) string {
	return fmt.Sprintf("usage:rt:%s", minute.UTC().Format("200601021504"))
}

// Increment is fire-and-forget. Called from the hot UsageLogger.Record()
// path (inside a goroutine) so HTTP latency is never impacted by Redis.
func (u *UsageRealtime) Increment(ctx context.Context, rec model.TokenUsage) {
	if u == nil || u.rdb == nil {
		return
	}
	ctx, cancel := context.WithTimeout(ctx, 500*time.Millisecond)
	defer cancel()

	minute := rec.Timestamp.UTC().Truncate(time.Minute)
	key := rtKey(minute)

	// HINCRBY is O(1). Pipeline the 4-5 fields + EXPIRE in one round-trip.
	pipe := u.rdb.Pipeline()
	pipe.HIncrBy(ctx, key, "calls", int64(rec.RequestCount))
	pipe.HIncrBy(ctx, key, "total_tokens", int64(rec.TotalTokens))
	pipe.HIncrBy(ctx, key, "prompt_tokens", int64(rec.PromptTokens))
	pipe.HIncrBy(ctx, key, "output_tokens", int64(rec.OutputTokens))
	pipe.HIncrBy(ctx, key, "latency_sum", int64(rec.LatencyMs))
	if rec.Status == "error" {
		pipe.HIncrBy(ctx, key, "errors", int64(rec.RequestCount))
	}
	// Per-provider fan-out (small fixed set).
	pipe.HIncrBy(ctx, key, "p:"+rec.Provider+":calls", int64(rec.RequestCount))
	pipe.HIncrBy(ctx, key, "p:"+rec.Provider+":tokens", int64(rec.TotalTokens))
	// Per-operation fan-out (chat | embed).
	pipe.HIncrBy(ctx, key, "op:"+rec.Operation+":calls", int64(rec.RequestCount))
	pipe.HIncrBy(ctx, key, "op:"+rec.Operation+":tokens", int64(rec.TotalTokens))
	pipe.Expire(ctx, key, realtimeKeyTTL)

	if _, err := pipe.Exec(ctx); err != nil {
		slog.Debug("usage realtime increment failed", "error", err)
	}
}

// RealtimePoint is one minute in the rolling window.
type RealtimePoint struct {
	Minute       string            `json:"minute"` // YYYY-MM-DD HH:MM
	Calls        int64             `json:"calls"`
	TotalTokens  int64             `json:"total_tokens"`
	PromptTokens int64             `json:"prompt_tokens"`
	OutputTokens int64             `json:"output_tokens"`
	AvgLatencyMs float64           `json:"avg_latency_ms"`
	Errors       int64             `json:"errors"`
	ByProvider   map[string]int64  `json:"by_provider"`
	ByOperation  map[string]int64  `json:"by_operation"`
}

// RealtimeSnapshot is what the handler returns.
type RealtimeSnapshot struct {
	WindowMinutes int             `json:"window_minutes"`
	Points        []RealtimePoint `json:"points"`
	Totals        RealtimePoint   `json:"totals"`
}

// Snapshot fetches the last `window` minutes in a single pipelined read.
// 60 HGETALLs on tiny hashes → typically <20ms from a local Redis.
func (u *UsageRealtime) Snapshot(ctx context.Context) (*RealtimeSnapshot, error) {
	if u == nil {
		return &RealtimeSnapshot{WindowMinutes: 0}, nil
	}
	if u.rdb == nil {
		return &RealtimeSnapshot{WindowMinutes: int(u.window.Minutes())}, nil
	}
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	now := time.Now().UTC().Truncate(time.Minute)
	minutes := int(u.window.Minutes())

	pipe := u.rdb.Pipeline()
	cmds := make([]*redis.MapStringStringCmd, minutes)
	keys := make([]time.Time, minutes)
	for i := 0; i < minutes; i++ {
		m := now.Add(-time.Duration(minutes-1-i) * time.Minute)
		keys[i] = m
		cmds[i] = pipe.HGetAll(ctx, rtKey(m))
	}
	if _, err := pipe.Exec(ctx); err != nil && err != redis.Nil {
		return nil, fmt.Errorf("realtime pipeline: %w", err)
	}

	snap := &RealtimeSnapshot{
		WindowMinutes: minutes,
		Points:        make([]RealtimePoint, 0, minutes),
		Totals: RealtimePoint{
			ByProvider:  map[string]int64{},
			ByOperation: map[string]int64{},
		},
	}

	var totalLatencySum, totalCallsForLat int64
	for i, cmd := range cmds {
		fields, _ := cmd.Result()
		p := RealtimePoint{
			Minute:      keys[i].Format("2006-01-02 15:04"),
			ByProvider:  map[string]int64{},
			ByOperation: map[string]int64{},
		}
		var latSum int64
		for k, v := range fields {
			n := parseInt64(v)
			switch k {
			case "calls":
				p.Calls = n
				snap.Totals.Calls += n
				totalCallsForLat += n
			case "total_tokens":
				p.TotalTokens = n
				snap.Totals.TotalTokens += n
			case "prompt_tokens":
				p.PromptTokens = n
				snap.Totals.PromptTokens += n
			case "output_tokens":
				p.OutputTokens = n
				snap.Totals.OutputTokens += n
			case "latency_sum":
				latSum = n
				totalLatencySum += n
			case "errors":
				p.Errors = n
				snap.Totals.Errors += n
			default:
				// p:<provider>:calls | op:<op>:calls
				if len(k) > 2 && k[:2] == "p:" {
					// provider metric
					name, kind := splitProviderField(k)
					if kind == "calls" {
						p.ByProvider[name] += n
						snap.Totals.ByProvider[name] += n
					}
				} else if len(k) > 3 && k[:3] == "op:" {
					name, kind := splitProviderField(k)
					if kind == "calls" {
						p.ByOperation[name] += n
						snap.Totals.ByOperation[name] += n
					}
				}
			}
		}
		if p.Calls > 0 {
			p.AvgLatencyMs = float64(latSum) / float64(p.Calls)
		}
		snap.Points = append(snap.Points, p)
	}

	if totalCallsForLat > 0 {
		snap.Totals.AvgLatencyMs = float64(totalLatencySum) / float64(totalCallsForLat)
	}

	return snap, nil
}

func splitProviderField(k string) (name, kind string) {
	// Input: "p:gemini:calls" or "op:chat:tokens"
	parts := 0
	colonIdx := [2]int{-1, -1}
	for i := 0; i < len(k); i++ {
		if k[i] == ':' {
			colonIdx[parts] = i
			parts++
			if parts == 2 {
				break
			}
		}
	}
	if parts < 2 {
		return "", ""
	}
	return k[colonIdx[0]+1 : colonIdx[1]], k[colonIdx[1]+1:]
}

func parseInt64(s string) int64 {
	var n int64
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			if i == 0 && c == '-' {
				continue
			}
			return 0
		}
		n = n*10 + int64(c-'0')
	}
	if len(s) > 0 && s[0] == '-' {
		return -n
	}
	return n
}

// ─── Stats cache layer ────────────────────────────────────────────

// StatsCache is a Redis-backed cache for the Stats endpoint. The
// versioning scheme means cache-busts are O(1) on write path: the
// UsageLogger bumps the version after each flush, and the next read
// computes a fresh key (old entries just expire naturally).
type StatsCache struct {
	rdb *redis.Client
	ttl time.Duration
}

func NewStatsCache(rdb *redis.Client) *StatsCache {
	return &StatsCache{rdb: rdb, ttl: 5 * time.Second}
}

const statsCacheVersionKey = "usage:stats:version"

// version returns the current bump counter. Missing key → "0".
func (c *StatsCache) version(ctx context.Context) string {
	if c == nil || c.rdb == nil {
		return "0"
	}
	v, err := c.rdb.Get(ctx, statsCacheVersionKey).Result()
	if err == redis.Nil || err != nil {
		return "0"
	}
	return v
}

// BumpVersion invalidates all cached stats responses. O(1).
func (c *StatsCache) BumpVersion(ctx context.Context) {
	if c == nil || c.rdb == nil {
		return
	}
	c.rdb.Incr(ctx, statsCacheVersionKey)
}

// Get / Set are JSON-encoded so the handler layer stays oblivious to the
// underlying structure.
func (c *StatsCache) Get(ctx context.Context, filterHash string, out any) (bool, error) {
	if c == nil || c.rdb == nil {
		return false, nil
	}
	key := fmt.Sprintf("usage:stats:%s:%s", c.version(ctx), filterHash)
	b, err := c.rdb.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if err := json.Unmarshal(b, out); err != nil {
		return false, err
	}
	return true, nil
}

func (c *StatsCache) Set(ctx context.Context, filterHash string, in any) error {
	if c == nil || c.rdb == nil {
		return nil
	}
	b, err := json.Marshal(in)
	if err != nil {
		return err
	}
	key := fmt.Sprintf("usage:stats:%s:%s", c.version(ctx), filterHash)
	return c.rdb.Set(ctx, key, b, c.ttl).Err()
}

// HashFilter is a helper that produces a stable key from the query params.
// We sort keys so permutations collapse to the same hash.
func HashFilter(filter map[string]string) string {
	keys := make([]string, 0, len(filter))
	for k := range filter {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var b []byte
	for _, k := range keys {
		b = append(b, k...)
		b = append(b, '=')
		b = append(b, filter[k]...)
		b = append(b, ';')
	}
	// Cheap non-cryptographic hash — collisions here only cause a cache
	// miss, so strength does not matter.
	var h uint64 = 1469598103934665603
	for _, c := range b {
		h ^= uint64(c)
		h *= 1099511628211
	}
	return fmt.Sprintf("%x", h)
}
