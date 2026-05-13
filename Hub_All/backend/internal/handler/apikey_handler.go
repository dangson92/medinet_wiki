package handler

import (
	"log/slog"
	"math"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/medinet/hub-all-backend/internal/middleware"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
	"github.com/medinet/hub-all-backend/internal/service"
)

type APIKeyHandler struct {
	apikeyService *service.APIKeyService
}

func NewAPIKeyHandler(apikeyService *service.APIKeyService) *APIKeyHandler {
	return &APIKeyHandler{apikeyService: apikeyService}
}

// GET /api/api-keys
func (h *APIKeyHandler) List(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	keys, total, err := h.apikeyService.List(c.Request.Context(), page, perPage)
	if err != nil {
		slog.Error("list api keys failed", "error", err)
		response.InternalError(c, "failed to list api keys")
		return
	}

	totalPages := int(math.Ceil(float64(total) / float64(perPage)))

	response.Paginated(c, keys, response.Meta{
		Page:       page,
		PerPage:    perPage,
		Total:      total,
		TotalPages: totalPages,
	})
}

// GET /api/api-keys/:id
func (h *APIKeyHandler) GetByID(c *gin.Context) {
	id := c.Param("id")

	key, err := h.apikeyService.GetByID(c.Request.Context(), id)
	if err != nil {
		if isAPIKeyError(err) {
			if strings.Contains(err.Error(), "not found") {
				response.NotFound(c, err.Error())
			} else {
				response.BadRequest(c, err.Error())
			}
			return
		}
		slog.Error("get api key failed", "error", err)
		response.InternalError(c, "failed to get api key")
		return
	}

	response.OK(c, key)
}

// POST /api/api-keys
func (h *APIKeyHandler) Create(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}

	var req model.CreateAPIKeyRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	key, err := h.apikeyService.Create(c.Request.Context(), req, userID.String())
	if err != nil {
		if isAPIKeyError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("create api key failed", "error", err)
		response.InternalError(c, "failed to create api key")
		return
	}

	response.Created(c, key)
}

// PUT /api/api-keys/:id
func (h *APIKeyHandler) Update(c *gin.Context) {
	id := c.Param("id")

	var req model.UpdateAPIKeyRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	key, err := h.apikeyService.Update(c.Request.Context(), id, req)
	if err != nil {
		if isAPIKeyError(err) {
			if strings.Contains(err.Error(), "not found") {
				response.NotFound(c, err.Error())
			} else {
				response.BadRequest(c, err.Error())
			}
			return
		}
		slog.Error("update api key failed", "error", err)
		response.InternalError(c, "failed to update api key")
		return
	}

	response.OK(c, key)
}

// POST /api/api-keys/:id/revoke
func (h *APIKeyHandler) Revoke(c *gin.Context) {
	id := c.Param("id")

	if err := h.apikeyService.Revoke(c.Request.Context(), id); err != nil {
		if isAPIKeyError(err) {
			if strings.Contains(err.Error(), "not found") {
				response.NotFound(c, err.Error())
			} else {
				response.BadRequest(c, err.Error())
			}
			return
		}
		slog.Error("revoke api key failed", "error", err)
		response.InternalError(c, "failed to revoke api key")
		return
	}

	response.OK(c, gin.H{"message": "api key revoked"})
}

func isAPIKeyError(err error) bool {
	msg := err.Error()
	userErrors := []string{
		"invalid api key ID",
		"invalid creator ID",
		"api key not found",
		"name is required",
	}
	for _, ue := range userErrors {
		if strings.HasPrefix(msg, ue) || strings.Contains(msg, ue) {
			return true
		}
	}
	return false
}
