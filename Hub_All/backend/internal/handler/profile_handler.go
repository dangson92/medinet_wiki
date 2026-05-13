package handler

import (
	"log/slog"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/medinet/hub-all-backend/internal/middleware"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
	"github.com/medinet/hub-all-backend/internal/service"
)

type ProfileHandler struct {
	profileService *service.ProfileService
}

func NewProfileHandler(profileService *service.ProfileService) *ProfileHandler {
	return &ProfileHandler{profileService: profileService}
}

// GET /api/profile
func (h *ProfileHandler) GetProfile(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}

	profile, err := h.profileService.GetProfile(c.Request.Context(), userID.String())
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			response.NotFound(c, "user not found")
			return
		}
		slog.Error("get profile failed", "error", err)
		response.InternalError(c, "failed to get profile")
		return
	}

	response.OK(c, profile)
}

// PUT /api/profile
func (h *ProfileHandler) UpdateProfile(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}

	var req model.UpdateProfileRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	user, err := h.profileService.UpdateProfile(c.Request.Context(), userID.String(), req)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			response.NotFound(c, "user not found")
			return
		}
		slog.Error("update profile failed", "error", err)
		response.InternalError(c, "failed to update profile")
		return
	}

	response.OK(c, user)
}

// POST /api/profile/password
func (h *ProfileHandler) ChangePassword(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}

	var req model.ChangePasswordRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body: old_password and new_password are required")
		return
	}

	if err := h.profileService.ChangePassword(c.Request.Context(), userID.String(), req.OldPassword, req.NewPassword); err != nil {
		if isProfileError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("change password failed", "error", err)
		response.InternalError(c, "failed to change password")
		return
	}

	response.OK(c, gin.H{"message": "password changed"})
}

func isProfileError(err error) bool {
	msg := err.Error()
	userErrors := []string{
		"current password is incorrect",
		"password must be",
		"user not found",
		"invalid user ID",
	}
	for _, ue := range userErrors {
		if strings.HasPrefix(msg, ue) || strings.Contains(msg, ue) {
			return true
		}
	}
	return false
}
