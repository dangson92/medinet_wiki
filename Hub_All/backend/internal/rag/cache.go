package rag

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

const maxMemCacheEntries = 5000

// SearchCache provides two-layer caching:
// Layer 1: Query embedding cache (TTL 1h) — avoid re-embedding same query
// Layer 2: Search result cache (TTL 5m) — avoid re-searching same query+filters
// Falls back to in-memory LRU when Redis is not available.
type SearchCache struct {
	rdb     *redis.Client
	memLock sync.RWMutex
	memEmb  map[string]cacheEntry[[]float32]
	memRes  map[string]cacheEntry[json.RawMessage]
}

type cacheEntry[T any] struct {
	value     T
	expiresAt time.Time
}

func NewSearchCache(rdb *redis.Client) *SearchCache {
	return &SearchCache{
		rdb:    rdb,
		memEmb: make(map[string]cacheEntry[[]float32]),
		memRes: make(map[string]cacheEntry[json.RawMessage]),
	}
}

func hashKey(parts ...string) string {
	h := sha256.New()
	for _, p := range parts {
		h.Write([]byte(p))
	}
	return fmt.Sprintf("%x", h.Sum(nil))[:16]
}

// evictExpired removes expired entries and enforces max size.
// Must be called with memLock held for writing.
func evictMap[T any](m map[string]cacheEntry[T], maxSize int) {
	now := time.Now()
	// Remove expired entries first
	for k, e := range m {
		if now.After(e.expiresAt) {
			delete(m, k)
		}
	}
	// If still over limit, remove oldest entries
	for len(m) >= maxSize {
		var oldestKey string
		oldestTime := time.Now().Add(time.Hour)
		for k, e := range m {
			if e.expiresAt.Before(oldestTime) {
				oldestKey = k
				oldestTime = e.expiresAt
			}
		}
		if oldestKey != "" {
			delete(m, oldestKey)
		} else {
			break
		}
	}
}

// ─── Embedding Cache ───

func (c *SearchCache) GetEmbedding(ctx context.Context, query string) ([]float32, bool) {
	key := "embed:" + hashKey(query)

	// Try Redis first
	if c.rdb != nil {
		data, err := c.rdb.Get(ctx, key).Bytes()
		if err == nil {
			var vec []float32
			if json.Unmarshal(data, &vec) == nil {
				return vec, true
			}
		}
	}

	// Fallback to memory
	c.memLock.RLock()
	entry, ok := c.memEmb[key]
	c.memLock.RUnlock()
	if ok && time.Now().Before(entry.expiresAt) {
		return entry.value, true
	}
	return nil, false
}

func (c *SearchCache) SetEmbedding(ctx context.Context, query string, vec []float32) {
	key := "embed:" + hashKey(query)
	ttl := 1 * time.Hour

	if c.rdb != nil {
		data, _ := json.Marshal(vec)
		if err := c.rdb.Set(ctx, key, data, ttl).Err(); err != nil {
			slog.Debug("cache set embedding redis error", "error", err)
		}
	}

	c.memLock.Lock()
	evictMap(c.memEmb, maxMemCacheEntries)
	c.memEmb[key] = cacheEntry[[]float32]{value: vec, expiresAt: time.Now().Add(ttl)}
	c.memLock.Unlock()
}

// ─── Search Result Cache ───

func (c *SearchCache) GetResults(ctx context.Context, cacheKey string) (json.RawMessage, bool) {
	key := "search:" + cacheKey

	if c.rdb != nil {
		data, err := c.rdb.Get(ctx, key).Bytes()
		if err == nil {
			return data, true
		}
	}

	c.memLock.RLock()
	entry, ok := c.memRes[key]
	c.memLock.RUnlock()
	if ok && time.Now().Before(entry.expiresAt) {
		return entry.value, true
	}
	return nil, false
}

func (c *SearchCache) SetResults(ctx context.Context, cacheKey string, data json.RawMessage) {
	key := "search:" + cacheKey
	ttl := 5 * time.Minute

	if c.rdb != nil {
		if err := c.rdb.Set(ctx, key, []byte(data), ttl).Err(); err != nil {
			slog.Debug("cache set results redis error", "error", err)
		}
	}

	c.memLock.Lock()
	evictMap(c.memRes, maxMemCacheEntries)
	c.memRes[key] = cacheEntry[json.RawMessage]{value: data, expiresAt: time.Now().Add(ttl)}
	c.memLock.Unlock()
}

// InvalidateHub removes all cached search results for a specific hub.
func (c *SearchCache) InvalidateHub(ctx context.Context, hubCode string) {
	// Redis: use SCAN instead of KEYS (non-blocking)
	if c.rdb != nil {
		var cursor uint64
		for {
			keys, nextCursor, err := c.rdb.Scan(ctx, cursor, "search:*", 100).Result()
			if err != nil {
				break
			}
			if len(keys) > 0 {
				c.rdb.Del(ctx, keys...)
			}
			cursor = nextCursor
			if cursor == 0 {
				break
			}
		}
	}

	// Memory: clear all result cache
	c.memLock.Lock()
	c.memRes = make(map[string]cacheEntry[json.RawMessage])
	c.memLock.Unlock()
}

func BuildCacheKey(query string, hubIDs []string, filters interface{}) string {
	filtersJSON, _ := json.Marshal(filters)
	hubsStr := fmt.Sprintf("%v", hubIDs)
	return hashKey(query, hubsStr, string(filtersJSON))
}
