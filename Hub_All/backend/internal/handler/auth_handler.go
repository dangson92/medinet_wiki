package handler

import (
	"log/slog"

	"github.com/gin-gonic/gin"
	"github.com/medinet/hub-all-backend/internal/middleware"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
	"github.com/medinet/hub-all-backend/internal/service"
)

type AuthHandler struct {
	authService *service.AuthService
}

func NewAuthHandler(authService *service.AuthService) *AuthHandler {
	return &AuthHandler{authService: authService}
}

// POST /api/auth/login
func (h *AuthHandler) Login(c *gin.Context) {
	var req model.LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	result, err := h.authService.Login(c.Request.Context(), req)
	if err != nil {
		slog.Debug("login failed", "email", req.Email, "error", err)
		response.Unauthorized(c, err.Error())
		return
	}

	response.OK(c, result)
}

// POST /api/auth/logout
func (h *AuthHandler) Logout(c *gin.Context) {
	jti, exists := c.Get(string(middleware.ContextJTI))
	if !exists {
		response.BadRequest(c, "no token ID in context")
		return
	}

	userID, exists := c.Get(string(middleware.ContextUserID))
	if !exists {
		response.BadRequest(c, "no user ID in context")
		return
	}

	if err := h.authService.Logout(c.Request.Context(), jti.(string), userID.(string)); err != nil {
		slog.Error("logout failed", "error", err)
		response.InternalError(c, "logout failed")
		return
	}

	response.OK(c, gin.H{"message": "logged out successfully"})
}

// POST /api/auth/refresh
func (h *AuthHandler) Refresh(c *gin.Context) {
	var req model.RefreshRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	tokenPair, err := h.authService.Refresh(c.Request.Context(), req.RefreshToken)
	if err != nil {
		slog.Debug("refresh failed", "error", err)
		response.Unauthorized(c, err.Error())
		return
	}

	response.OK(c, tokenPair)
}

// GET /api/auth/me
func (h *AuthHandler) Me(c *gin.Context) {
	userID, exists := c.Get(string(middleware.ContextUserID))
	if !exists {
		response.Unauthorized(c, "not authenticated")
		return
	}

	user, err := h.authService.GetCurrentUser(c.Request.Context(), userID.(string))
	if err != nil {
		slog.Error("get current user failed", "error", err)
		response.InternalError(c, "failed to get user info")
		return
	}

	response.OK(c, user)
}
