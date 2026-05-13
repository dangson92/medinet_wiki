package handler

import (
	"log/slog"
	"math"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
	"github.com/medinet/hub-all-backend/internal/service"
)

type UserHandler struct {
	userService *service.UserService
}

func NewUserHandler(userService *service.UserService) *UserHandler {
	return &UserHandler{userService: userService}
}

// GET /api/users
func (h *UserHandler) List(c *gin.Context) {
	hubID := c.Query("hub_id")
	role := c.Query("role")
	status := c.Query("status")
	search := c.Query("search")

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	users, total, err := h.userService.List(c.Request.Context(), hubID, role, status, search, page, perPage)
	if err != nil {
		slog.Error("list users failed", "error", err)
		response.InternalError(c, "failed to list users")
		return
	}

	totalPages := int(math.Ceil(float64(total) / float64(perPage)))

	response.Paginated(c, users, response.Meta{
		Page:       page,
		PerPage:    perPage,
		Total:      total,
		TotalPages: totalPages,
	})
}

// GET /api/users/:id
func (h *UserHandler) GetByID(c *gin.Context) {
	id := c.Param("id")

	user, err := h.userService.GetByID(c.Request.Context(), id)
	if err != nil {
		if isUserMgmtError(err) {
			if strings.Contains(err.Error(), "not found") {
				response.NotFound(c, err.Error())
			} else {
				response.BadRequest(c, err.Error())
			}
			return
		}
		slog.Error("get user failed", "error", err)
		response.InternalError(c, "failed to get user")
		return
	}

	response.OK(c, user)
}

// POST /api/users
func (h *UserHandler) Create(c *gin.Context) {
	var req model.CreateUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	user, err := h.userService.Create(c.Request.Context(), req)
	if err != nil {
		if isUserMgmtError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("create user failed", "error", err)
		response.InternalError(c, "failed to create user")
		return
	}

	response.Created(c, user)
}

// PUT /api/users/:id
func (h *UserHandler) Update(c *gin.Context) {
	id := c.Param("id")

	var req model.UpdateUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	user, err := h.userService.Update(c.Request.Context(), id, req)
	if err != nil {
		if isUserMgmtError(err) {
			if strings.Contains(err.Error(), "not found") {
				response.NotFound(c, err.Error())
			} else {
				response.BadRequest(c, err.Error())
			}
			return
		}
		slog.Error("update user failed", "error", err)
		response.InternalError(c, "failed to update user")
		return
	}

	response.OK(c, user)
}

// PATCH /api/users/:id/role
func (h *UserHandler) ChangeRole(c *gin.Context) {
	id := c.Param("id")

	var req model.ChangeRoleRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body: hub_id and role are required")
		return
	}

	if err := h.userService.ChangeRole(c.Request.Context(), id, req.HubID, req.Role); err != nil {
		if isUserMgmtError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("change user role failed", "error", err)
		response.InternalError(c, "failed to change user role")
		return
	}

	response.OK(c, gin.H{"message": "role updated"})
}

// PATCH /api/users/:id/status
func (h *UserHandler) ChangeStatus(c *gin.Context) {
	id := c.Param("id")

	var req model.ChangeStatusRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body: status is required")
		return
	}

	if err := h.userService.ChangeStatus(c.Request.Context(), id, req.Status); err != nil {
		if isUserMgmtError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("change user status failed", "error", err)
		response.InternalError(c, "failed to change user status")
		return
	}

	response.OK(c, gin.H{"message": "status updated"})
}

func isUserMgmtError(err error) bool {
	msg := err.Error()
	userErrors := []string{
		"invalid user ID",
		"invalid hub ID",
		"user not found",
		"email already exists",
		"email is required",
		"invalid email format",
		"password must be",
		"role must be",
		"status must be",
	}
	for _, ue := range userErrors {
		if strings.HasPrefix(msg, ue) || strings.Contains(msg, ue) {
			return true
		}
	}
	return false
}
