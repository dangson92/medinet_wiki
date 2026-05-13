package middleware

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"

	"github.com/medinet/hub-all-backend/internal/pkg/response"
)

// LoginRateLimit applies a stricter rate limit for authentication endpoints.
// Max 5 attempts per IP per 60 seconds.
func LoginRateLimit(rdb *redis.Client) gin.HandlerFunc {
	return func(c *gin.Context) {
		if rdb == nil {
			c.Next()
			return
		}
		key := fmt.Sprintf("rl:login:%s", c.ClientIP())
		ctx := context.Background()
		count, err := rdb.Incr(ctx, key).Result()
		if err != nil {
			slog.Error("login rate limit redis error", "error", err)
			c.Next()
			return
		}
		if count == 1 {
			rdb.Expire(ctx, key, 60*time.Second)
		}
		if count > 5 {
			response.TooManyRequests(c, "too many login attempts, please wait 60 seconds")
			c.Abort()
			return
		}
		c.Next()
	}
}

// RateLimit middleware using Redis sliding window counter.
// If rdb is nil (Redis unavailable), rate limiting is skipped.
func RateLimit(rdb *redis.Client, rps, burst int) gin.HandlerFunc {
	return func(c *gin.Context) {
		if rdb == nil {
			c.Next()
			return
		}

		key := fmt.Sprintf("rl:%s", c.ClientIP())
		if userID, exists := c.Get(string(ContextUserID)); exists {
			key = fmt.Sprintf("rl:%s", userID)
		}

		ctx := context.Background()
		now := time.Now().Unix()
		windowKey := fmt.Sprintf("%s:%d", key, now)

		pipe := rdb.Pipeline()
		incr := pipe.Incr(ctx, windowKey)
		pipe.Expire(ctx, windowKey, 2*time.Second)

		if _, err := pipe.Exec(ctx); err != nil {
			slog.Error("rate limit redis error", "error", err)
			c.Next()
			return
		}

		count := incr.Val()
		if count > int64(burst) {
			response.TooManyRequests(c, "rate limit exceeded, please try again later")
			c.Abort()
			return
		}

		c.Next()
	}
}
