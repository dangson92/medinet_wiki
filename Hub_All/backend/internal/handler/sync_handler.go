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

type SyncHandler struct {
	syncService *service.SyncService
}

func NewSyncHandler(syncService *service.SyncService) *SyncHandler {
	return &SyncHandler{syncService: syncService}
}

// GET /api/sync/batches
func (h *SyncHandler) ListBatches(c *gin.Context) {
	hubID := c.Query("hub_id")
	status := c.Query("status")

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	batches, total, err := h.syncService.ListBatches(c.Request.Context(), hubID, status, page, perPage)
	if err != nil {
		slog.Error("list sync batches failed", "error", err)
		response.InternalError(c, "failed to list sync batches")
		return
	}

	totalPages := int(math.Ceil(float64(total) / float64(perPage)))

	response.Paginated(c, batches, response.Meta{
		Page:       page,
		PerPage:    perPage,
		Total:      total,
		TotalPages: totalPages,
	})
}

// GET /api/sync/batches/:id
func (h *SyncHandler) GetBatch(c *gin.Context) {
	id := c.Param("id")

	batch, err := h.syncService.GetBatch(c.Request.Context(), id)
	if err != nil {
		if isSyncUserError(err) {
			if strings.Contains(err.Error(), "not found") {
				response.NotFound(c, err.Error())
			} else {
				response.BadRequest(c, err.Error())
			}
			return
		}
		slog.Error("get sync batch failed", "error", err)
		response.InternalError(c, "failed to get sync batch")
		return
	}

	response.OK(c, batch)
}

// POST /api/sync/batches
func (h *SyncHandler) SubmitBatch(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}

	var req model.SubmitSyncRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body: hub_id and pages are required")
		return
	}

	batch, err := h.syncService.SubmitBatch(c.Request.Context(), req, userID.String())
	if err != nil {
		if isSyncUserError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("submit sync batch failed", "error", err)
		response.InternalError(c, "failed to submit sync batch")
		return
	}

	response.Created(c, batch)
}

// POST /api/sync/batches/:id/pages/:pid/approve
func (h *SyncHandler) ApprovePage(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}

	batchID := c.Param("id")
	pageID := c.Param("pid")

	if err := h.syncService.ApprovePage(c.Request.Context(), batchID, pageID, userID.String()); err != nil {
		if isSyncUserError(err) {
			if strings.Contains(err.Error(), "not found") {
				response.NotFound(c, err.Error())
			} else {
				response.BadRequest(c, err.Error())
			}
			return
		}
		slog.Error("approve sync page failed", "error", err)
		response.InternalError(c, "failed to approve sync page")
		return
	}

	response.OK(c, gin.H{"message": "page approved"})
}

// POST /api/sync/batches/:id/pages/:pid/reject
func (h *SyncHandler) RejectPage(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}

	batchID := c.Param("id")
	pageID := c.Param("pid")

	var req model.RejectPageRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body: reason is required")
		return
	}

	if err := h.syncService.RejectPage(c.Request.Context(), batchID, pageID, userID.String(), req.Reason); err != nil {
		if isSyncUserError(err) {
			if strings.Contains(err.Error(), "not found") {
				response.NotFound(c, err.Error())
			} else {
				response.BadRequest(c, err.Error())
			}
			return
		}
		slog.Error("reject sync page failed", "error", err)
		response.InternalError(c, "failed to reject sync page")
		return
	}

	response.OK(c, gin.H{"message": "page rejected"})
}

// GET /api/sync/stats
func (h *SyncHandler) GetStats(c *gin.Context) {
	pendingBatches, pendingPages, err := h.syncService.GetStats(c.Request.Context())
	if err != nil {
		slog.Error("get sync stats failed", "error", err)
		response.InternalError(c, "failed to get sync stats")
		return
	}

	response.OK(c, gin.H{
		"pending_batches": pendingBatches,
		"pending_pages":   pendingPages,
	})
}

// isSyncUserError checks if the error is a user-facing validation error.
func isSyncUserError(err error) bool {
	msg := err.Error()
	userErrors := []string{
		"invalid batch ID",
		"invalid page ID",
		"invalid hub ID",
		"invalid user ID",
		"invalid reviewer ID",
		"hub not found",
		"batch not found",
		"sync page not found",
		"page does not belong",
		"at least one page",
		"rejection reason must be",
		"sync page not found or already reviewed",
	}
	for _, ue := range userErrors {
		if strings.HasPrefix(msg, ue) || strings.Contains(msg, ue) {
			return true
		}
	}
	return false
}
