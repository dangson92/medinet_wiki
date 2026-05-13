package middleware

import (
	"context"
	"log/slog"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	jwtpkg "github.com/medinet/hub-all-backend/internal/pkg/jwt"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
)

type contextKey string

const (
	ContextUserID    contextKey = "user_id"
	ContextEmail     contextKey = "email"
	ContextName      contextKey = "name"
	ContextHubID     contextKey = "hub_id"
	ContextRole      contextKey = "role"
	ContextSubdomain contextKey = "subdomain"
	ContextJTI       contextKey = "jti"
)

// JWTAuth middleware verifies JWT access tokens.
func JWTAuth(jwtManager *jwtpkg.Manager, rdb *redis.Client) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			response.Unauthorized(c, "missing authorization header")
			c.Abort()
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || parts[0] != "Bearer" {
			response.Unauthorized(c, "invalid authorization format, use: Bearer <token>")
			c.Abort()
			return
		}

		claims, err := jwtManager.VerifyToken(parts[1])
		if err != nil {
			slog.Debug("token verification failed", "error", err)
			response.Unauthorized(c, "invalid or expired token")
			c.Abort()
			return
		}

		if claims.TokenType != "access" {
			response.Unauthorized(c, "invalid token type, access token required")
			c.Abort()
			return
		}

		// Check if token is revoked (Redis cache first, then DB)
		jti, err := uuid.Parse(claims.ID)
		if err != nil {
			response.Unauthorized(c, "invalid token ID")
			c.Abort()
			return
		}

		if rdb != nil {
			revoked, err := rdb.Exists(context.Background(), "revoked:"+jti.String()).Result()
			if err != nil {
				slog.Error("redis check revoked token", "error", err)
			}
			if revoked > 0 {
				response.Unauthorized(c, "token has been revoked")
				c.Abort()
				return
			}
		}

		// Set claims in context
		c.Set(string(ContextUserID), claims.Subject)
		c.Set(string(ContextEmail), claims.Email)
		c.Set(string(ContextName), claims.Name)
		c.Set(string(ContextHubID), claims.HubID)
		c.Set(string(ContextRole), claims.Role)
		c.Set(string(ContextSubdomain), claims.Subdomain)
		c.Set(string(ContextJTI), claims.ID)

		c.Next()
	}
}

// RequireRole middleware checks that the user has the required role.
func RequireRole(roles ...string) gin.HandlerFunc {
	return func(c *gin.Context) {
		userRole, exists := c.Get(string(ContextRole))
		if !exists {
			response.Unauthorized(c, "no role in context")
			c.Abort()
			return
		}

		roleStr, ok := userRole.(string)
		if !ok {
			response.Unauthorized(c, "invalid role format")
			c.Abort()
			return
		}

		for _, r := range roles {
			if roleStr == r {
				c.Next()
				return
			}
		}

		response.Forbidden(c, "insufficient permissions")
		c.Abort()
	}
}

// GetUserID extracts user ID from gin context.
func GetUserID(c *gin.Context) (uuid.UUID, bool) {
	val, exists := c.Get(string(ContextUserID))
	if !exists {
		return uuid.Nil, false
	}
	id, err := uuid.Parse(val.(string))
	if err != nil {
		return uuid.Nil, false
	}
	return id, true
}

// GetRole extracts role from gin context.
func GetRole(c *gin.Context) string {
	val, _ := c.Get(string(ContextRole))
	if val == nil {
		return ""
	}
	return val.(string)
}
