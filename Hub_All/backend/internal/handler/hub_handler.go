package handler

import (
	"log/slog"

	"github.com/gin-gonic/gin"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
	"github.com/medinet/hub-all-backend/internal/service"
)

type HubHandler struct {
	hubService *service.HubService
}

func NewHubHandler(hubService *service.HubService) *HubHandler {
	return &HubHandler{hubService: hubService}
}

// GET /api/hubs
func (h *HubHandler) List(c *gin.Context) {
	hubs, err := h.hubService.List(c.Request.Context())
	if err != nil {
		slog.Error("list hubs failed", "error", err)
		response.InternalError(c, "failed to list hubs")
		return
	}

	response.OK(c, hubs)
}

// GET /api/hubs/:id
func (h *HubHandler) GetByID(c *gin.Context) {
	id := c.Param("id")

	hub, err := h.hubService.GetByID(c.Request.Context(), id)
	if err != nil {
		if err.Error() == "hub not found" {
			response.NotFound(c, "hub not found")
			return
		}
		slog.Error("get hub failed", "error", err)
		response.InternalError(c, "failed to get hub")
		return
	}

	response.OK(c, hub)
}

// POST /api/hubs
func (h *HubHandler) Create(c *gin.Context) {
	var req model.CreateHubRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	hub, err := h.hubService.Create(c.Request.Context(), req)
	if err != nil {
		slog.Error("create hub failed", "error", err)
		response.BadRequest(c, err.Error())
		return
	}

	response.Created(c, hub)
}

// PUT /api/hubs/:id
func (h *HubHandler) Update(c *gin.Context) {
	id := c.Param("id")

	var req model.UpdateHubRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	hub, err := h.hubService.Update(c.Request.Context(), id, req)
	if err != nil {
		if err.Error() == "hub not found" {
			response.NotFound(c, "hub not found")
			return
		}
		slog.Error("update hub failed", "error", err)
		response.BadRequest(c, err.Error())
		return
	}

	response.OK(c, hub)
}

// PATCH /api/hubs/:id/status
func (h *HubHandler) UpdateStatus(c *gin.Context) {
	id := c.Param("id")

	var req model.UpdateHubStatusRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body")
		return
	}

	if err := h.hubService.UpdateStatus(c.Request.Context(), id, req); err != nil {
		slog.Error("update hub status failed", "error", err)
		response.BadRequest(c, err.Error())
		return
	}

	response.OK(c, gin.H{"message": "hub status updated"})
}

// POST /api/hubs/:id/test-connection
func (h *HubHandler) TestConnection(c *gin.Context) {
	id := c.Param("id")

	if err := h.hubService.TestConnection(c.Request.Context(), id); err != nil {
		slog.Error("test connection failed", "error", err)
		response.BadRequest(c, err.Error())
		return
	}

	response.OK(c, gin.H{"message": "connection successful"})
}
