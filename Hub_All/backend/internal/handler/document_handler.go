package handler

import (
	"context"
	"io"
	"log/slog"
	"math"
	"net/url"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/medinet/hub-all-backend/internal/middleware"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
	"github.com/medinet/hub-all-backend/internal/service"
)

var mimeByExt = map[string]string{
	"pdf":  "application/pdf",
	"txt":  "text/plain; charset=utf-8",
	"md":   "text/plain; charset=utf-8",
	"csv":  "text/csv; charset=utf-8",
	"html": "text/html; charset=utf-8",
	"jpg":  "image/jpeg",
	"jpeg": "image/jpeg",
	"png":  "image/png",
	"gif":  "image/gif",
	"webp": "image/webp",
	"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	"pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

// DocumentReindexer là subset 1-method của *service.DocumentService — interface
// cho test mock (CFG-07). Production: handler dùng docService cho mọi method
// còn Reindex thì gọi qua reindexer (default = docService nếu không inject mock).
type DocumentReindexer interface {
	Reindex(ctx context.Context, id, extractor, requesterID string) (*model.Document, error)
}

type DocumentHandler struct {
	docService *service.DocumentService
	// CFG-07 M1 Phase 4 — getter mode runtime hiện tại để default cho query
	// param `extractor` của reindex. Nil → fallback "auto".
	defaultExtractorGetter func() string
	// CFG-07 — optional override cho test inject mock. Nil → dùng docService.Reindex.
	reindexer DocumentReindexer
}

func NewDocumentHandler(docService *service.DocumentService) *DocumentHandler {
	return &DocumentHandler{docService: docService}
}

// SetDefaultExtractorGetter wire closure trả mode runtime (CFG-07).
// main.go pass `func() string { return cfg.RAG.Extractor }`. Optional setter
// để KHÔNG đổi NewDocumentHandler signature.
func (h *DocumentHandler) SetDefaultExtractorGetter(fn func() string) {
	h.defaultExtractorGetter = fn
}

// SetReindexer override Reindex backend (test inject mock).
// Production main.go KHÔNG gọi setter này → handler fallback docService.Reindex.
func (h *DocumentHandler) SetReindexer(r DocumentReindexer) {
	h.reindexer = r
}

// POST /api/documents/upload
func (h *DocumentHandler) Upload(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}

	hubID := c.PostForm("hub_id")
	if hubID == "" {
		response.BadRequest(c, "hub_id is required")
		return
	}

	file, header, err := c.Request.FormFile("file")
	if err != nil {
		response.BadRequest(c, "file is required")
		return
	}
	defer file.Close()

	doc, err := h.docService.Upload(c.Request.Context(), file, header, hubID, userID.String())
	if err != nil {
		if isUserError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("upload document failed", "error", err)
		response.InternalError(c, "failed to upload document")
		return
	}

	response.Accepted(c, doc)
}

// POST /api/documents/compose
func (h *DocumentHandler) Compose(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}

	var req struct {
		Name    string `json:"name" binding:"required"`
		Content string `json:"content" binding:"required"`
		HubID   string `json:"hub_id" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "invalid request body: name, content, and hub_id are required")
		return
	}

	doc, err := h.docService.Compose(c.Request.Context(), req.Name, req.Content, req.HubID, userID.String())
	if err != nil {
		if isUserError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("compose document failed", "error", err)
		response.InternalError(c, "failed to compose document")
		return
	}

	response.Accepted(c, doc)
}

// GET /api/documents
func (h *DocumentHandler) List(c *gin.Context) {
	hubID := c.Query("hub_id")
	status := c.Query("status")
	fileType := c.Query("file_type")

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	docs, total, err := h.docService.List(c.Request.Context(), hubID, status, fileType, page, perPage)
	if err != nil {
		slog.Error("list documents failed", "error", err)
		response.InternalError(c, "failed to list documents")
		return
	}

	totalPages := int(math.Ceil(float64(total) / float64(perPage)))

	response.Paginated(c, docs, response.Meta{
		Page:       page,
		PerPage:    perPage,
		Total:      total,
		TotalPages: totalPages,
	})
}

// GET /api/documents/:id
func (h *DocumentHandler) GetByID(c *gin.Context) {
	id := c.Param("id")

	doc, err := h.docService.GetByID(c.Request.Context(), id)
	if err != nil {
		if err.Error() == "document not found" {
			response.NotFound(c, "document not found")
			return
		}
		slog.Error("get document failed", "error", err)
		response.InternalError(c, "failed to get document")
		return
	}

	response.OK(c, doc)
}

// GET /api/documents/:id/status
func (h *DocumentHandler) GetStatus(c *gin.Context) {
	id := c.Param("id")

	status, progress, err := h.docService.GetStatus(c.Request.Context(), id)
	if err != nil {
		if err.Error() == "document not found" {
			response.NotFound(c, "document not found")
			return
		}
		slog.Error("get document status failed", "error", err)
		response.InternalError(c, "failed to get document status")
		return
	}

	response.OK(c, gin.H{
		"status":   status,
		"progress": progress,
	})
}

// GET /api/documents/:id/file
func (h *DocumentHandler) GetFile(c *gin.Context) {
	id := c.Param("id")

	reader, doc, err := h.docService.GetFile(c.Request.Context(), id)
	if err != nil {
		msg := err.Error()
		if msg == "document not found" {
			response.NotFound(c, "document not found")
			return
		}
		if msg == "file not found" {
			response.NotFound(c, "file not found on storage")
			return
		}
		slog.Error("get document file failed", "error", err)
		response.InternalError(c, "failed to get document file")
		return
	}
	defer reader.Close()

	contentType, ok := mimeByExt[strings.ToLower(doc.FileType)]
	if !ok {
		contentType = "application/octet-stream"
	}

	disposition := "inline"
	if contentType == "application/octet-stream" {
		disposition = "attachment"
	}

	encodedName := url.PathEscape(doc.Name)
	c.Header("Content-Type", contentType)
	c.Header("Content-Disposition", disposition+`; filename*=UTF-8''`+encodedName)
	c.Header("X-Content-Type-Options", "nosniff")
	c.Header("Cache-Control", "private, max-age=300")

	if _, err := io.Copy(c.Writer, reader); err != nil {
		slog.Warn("stream file failed", "doc_id", id, "error", err)
	}
}

// DELETE /api/documents/:id
func (h *DocumentHandler) Delete(c *gin.Context) {
	id := c.Param("id")

	if err := h.docService.Delete(c.Request.Context(), id); err != nil {
		if err.Error() == "document not found" {
			response.NotFound(c, "document not found")
			return
		}
		slog.Error("delete document failed", "error", err)
		response.InternalError(c, "failed to delete document")
		return
	}

	response.OK(c, gin.H{"message": "document deleted"})
}

// Reindex POST /api/documents/:id/reindex — admin-only (route-level RequireRole).
// Query param: extractor=docling|native|auto (optional; default = runtime ExtractorMode).
// Body: rỗng — file đã có trong storage, không cần re-upload (CFG-07).
// Trả 202 Accepted với document đã reset status='pending'.
func (h *DocumentHandler) Reindex(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}

	id := c.Param("id")
	extractor := c.Query("extractor")
	if extractor == "" {
		// Default về mode runtime hiện tại nếu user không truyền — admin có thể
		// reindex nhanh để áp dụng config mới mà không cần biết mode đang là gì.
		if h.defaultExtractorGetter != nil {
			extractor = h.defaultExtractorGetter()
		}
		if extractor == "" {
			extractor = "auto"
		}
	}

	// Ưu tiên reindexer mock (test). Production: docService thoả interface qua method tự nhiên.
	var (
		doc *model.Document
		err error
	)
	if h.reindexer != nil {
		doc, err = h.reindexer.Reindex(c.Request.Context(), id, extractor, userID.String())
	} else {
		doc, err = h.docService.Reindex(c.Request.Context(), id, extractor, userID.String())
	}
	if err != nil {
		msg := err.Error()
		switch {
		case msg == "document not found":
			response.NotFound(c, msg)
		case strings.HasPrefix(msg, "invalid document ID"),
			strings.HasPrefix(msg, "invalid extractor"):
			response.BadRequest(c, msg)
		case strings.HasPrefix(msg, "ensure local copy"),
			strings.HasPrefix(msg, "hub not found"):
			response.NotFound(c, msg)
		default:
			slog.Error("reindex document failed", "doc_id", id, "error", err)
			response.InternalError(c, "failed to reindex document")
		}
		return
	}

	response.Accepted(c, doc)
}

// isUserError checks if the error is a user-facing validation error.
func isUserError(err error) bool {
	msg := err.Error()
	userErrors := []string{
		"invalid hub ID",
		"invalid user ID",
		"invalid document ID",
		"hub not found",
		"document not found",
		"unsupported file type",
		"file size",
		"name is required",
		"content is required",
	}
	for _, ue := range userErrors {
		if strings.HasPrefix(msg, ue) {
			return true
		}
	}
	return false
}
