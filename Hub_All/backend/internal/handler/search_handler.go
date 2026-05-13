package handler

import (
	"log/slog"

	"github.com/gin-gonic/gin"
	"github.com/medinet/hub-all-backend/internal/middleware"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
	"github.com/medinet/hub-all-backend/internal/service"
)

type SearchHandler struct {
	searchService *service.SearchService
}

func NewSearchHandler(searchService *service.SearchService) *SearchHandler {
	return &SearchHandler{searchService: searchService}
}

// POST /api/search/answer — RAG answer generation
func (h *SearchHandler) Answer(c *gin.Context) {
	var req struct {
		Query  string   `json:"query" binding:"required"`
		HubIDs []string `json:"hub_ids"`
		TopK   int      `json:"top_k"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body: query is required")
		return
	}

	resp, err := h.searchService.Answer(c.Request.Context(), req.Query, req.HubIDs, req.TopK)
	if err != nil {
		slog.Error("answer generation failed", "error", err)
		response.InternalError(c, err.Error())
		return
	}

	response.OK(c, resp)
}

// POST /api/search
func (h *SearchHandler) Search(c *gin.Context) {
	var req model.SearchRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body: query is required")
		return
	}

	// Use hub from JWT context, or from request hub_ids
	hubID, _ := c.Get(string(middleware.ContextHubID))
	hubIDStr := ""
	if hubID != nil {
		hubIDStr = hubID.(string)
	}

	// If hub_ids specified in request, use first one
	if len(req.HubIDs) > 0 {
		hubIDStr = req.HubIDs[0]
	}

	if hubIDStr == "" {
		response.BadRequest(c, "hub context required for single-hub search")
		return
	}

	resp, err := h.searchService.Search(c.Request.Context(), req, hubIDStr)
	if err != nil {
		slog.Error("search failed", "error", err)
		response.InternalError(c, err.Error())
		return
	}

	response.OK(c, resp)
}

// POST /api/search/cross-hub
func (h *SearchHandler) CrossHubSearch(c *gin.Context) {
	var req model.SearchRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body: query is required")
		return
	}

	resp, err := h.searchService.CrossHubSearch(c.Request.Context(), req)
	if err != nil {
		slog.Error("cross-hub search failed", "error", err)
		response.InternalError(c, err.Error())
		return
	}

	response.OK(c, resp)
}

// POST /api/search/similar
func (h *SearchHandler) Similar(c *gin.Context) {
	var req model.SimilarRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body: content is required")
		return
	}

	resp, err := h.searchService.FindSimilar(c.Request.Context(), req)
	if err != nil {
		slog.Error("similar search failed", "error", err)
		response.InternalError(c, err.Error())
		return
	}

	response.OK(c, resp)
}
