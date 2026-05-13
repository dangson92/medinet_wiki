package database

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/medinet/hub-all-backend/internal/config"
)

// NewRedis tries to connect to Redis. Returns (client, nil) on success,
// or (nil, nil) if connection fails and we should run without Redis.
func NewRedis(cfg config.RedisConfig) (*redis.Client, error) {
	if cfg.URL == "" {
		return nil, nil
	}

	opts, err := redis.ParseURL(cfg.URL)
	if err != nil {
		return nil, fmt.Errorf("parse redis URL: %w", err)
	}

	rdb := redis.NewClient(opts)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := rdb.Ping(ctx).Err(); err != nil {
		slog.Warn("Redis not available, running without cache/rate-limit", "error", err)
		rdb.Close()
		return nil, nil
	}

	slog.Info("Redis connected", "addr", opts.Addr)
	return rdb, nil
}
