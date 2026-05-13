package handler

import (
	"fmt"
	"log/slog"
	"math"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
	"github.com/medinet/hub-all-backend/internal/service"
)

type AuditHandler struct {
	auditService *service.AuditService
}

func NewAuditHandler(auditService *service.AuditService) *AuditHandler {
	return &AuditHandler{auditService: auditService}
}

// GET /api/audit-logs
func (h *AuditHandler) List(c *gin.Context) {
	dateFrom := c.Query("date_from")
	dateTo := c.Query("date_to")
	actorType := c.Query("actor_type")
	action := c.Query("action")
	hubID := c.Query("hub_id")

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	entries, total, err := h.auditService.List(c.Request.Context(), dateFrom, dateTo, actorType, action, hubID, page, perPage)
	if err != nil {
		slog.Error("list audit logs failed", "error", err)
		response.InternalError(c, "failed to list audit logs")
		return
	}

	totalPages := int(math.Ceil(float64(total) / float64(perPage)))

	response.Paginated(c, entries, response.Meta{
		Page:       page,
		PerPage:    perPage,
		Total:      total,
		TotalPages: totalPages,
	})
}

// GET /api/audit-logs/export
func (h *AuditHandler) ExportCSV(c *gin.Context) {
	dateFrom := c.Query("date_from")
	dateTo := c.Query("date_to")
	actorType := c.Query("actor_type")
	action := c.Query("action")
	hubID := c.Query("hub_id")

	c.Header("Content-Type", "text/csv")
	c.Header("Content-Disposition", fmt.Sprintf("attachment; filename=audit_logs_%s.csv", dateFrom))

	if err := h.auditService.ExportCSV(c.Request.Context(), c.Writer, dateFrom, dateTo, actorType, action, hubID); err != nil {
		slog.Error("export audit logs failed", "error", err)
		// Headers already sent, we can only log the error
		return
	}
}
