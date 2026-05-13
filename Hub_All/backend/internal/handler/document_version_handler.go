package handler

import (
	"io"
	"log/slog"
	"net/url"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/medinet/hub-all-backend/internal/middleware"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
)

// GET /api/documents/:id/versions — list version (max 5).
func (h *DocumentHandler) ListVersions(c *gin.Context) {
	id := c.Param("id")
	versions, err := h.docService.ListVersions(c.Request.Context(), id)
	if err != nil {
		if err.Error() == "invalid document ID" {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("list versions failed", "doc_id", id, "error", err)
		response.InternalError(c, "failed to list versions")
		return
	}
	if versions == nil {
		versions = nil // serialize thành []
	}
	response.OK(c, gin.H{"versions": versions})
}

// GET /api/documents/:id/versions/:vid — chi tiết 1 version + chunks.
func (h *DocumentHandler) GetVersion(c *gin.Context) {
	vid := c.Param("vid")
	v, chunks, err := h.docService.GetVersion(c.Request.Context(), vid)
	if err != nil {
		switch err.Error() {
		case "invalid version ID":
			response.BadRequest(c, err.Error())
		case "version not found":
			response.NotFound(c, err.Error())
		case "version history not enabled":
			response.NotFound(c, err.Error())
		default:
			slog.Error("get version failed", "vid", vid, "error", err)
			response.InternalError(c, "failed to get version")
		}
		return
	}
	response.OK(c, gin.H{"version": v, "chunks": chunks})
}

// GET /api/documents/:id/versions/:vid/file — tải file binary của version.
func (h *DocumentHandler) DownloadVersionFile(c *gin.Context) {
	vid := c.Param("vid")
	reader, v, err := h.docService.OpenVersionFile(c.Request.Context(), vid)
	if err != nil {
		switch err.Error() {
		case "invalid version ID":
			response.BadRequest(c, err.Error())
		case "version not found", "version history not enabled":
			response.NotFound(c, err.Error())
		case "version file missing":
			response.NotFound(c, "version file no longer available")
		default:
			slog.Error("download version file failed", "vid", vid, "error", err)
			response.InternalError(c, "failed to download version file")
		}
		return
	}
	defer reader.Close()

	contentType, ok := mimeByExt[strings.ToLower(v.FileType)]
	if !ok {
		contentType = "application/octet-stream"
	}
	encodedName := url.PathEscape(v.Name)
	c.Header("Content-Type", contentType)
	c.Header("Content-Disposition", "attachment; filename*=UTF-8''"+encodedName)
	c.Header("X-Content-Type-Options", "nosniff")
	if _, err := io.Copy(c.Writer, reader); err != nil {
		slog.Warn("stream version file failed", "vid", vid, "error", err)
	}
}

// POST /api/documents/:id/versions/:vid/restore — admin restore document về version.
func (h *DocumentHandler) RestoreVersion(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}
	vid := c.Param("vid")
	doc, err := h.docService.RestoreVersion(c.Request.Context(), vid, userID.String())
	if err != nil {
		msg := err.Error()
		switch {
		case msg == "invalid version ID", strings.HasPrefix(msg, "invalid"):
			response.BadRequest(c, msg)
		case msg == "version not found", msg == "document not found",
			msg == "hub not found", msg == "version history not enabled":
			response.NotFound(c, msg)
		case msg == "version file missing — cannot restore":
			response.BadRequest(c, msg)
		default:
			slog.Error("restore version failed", "vid", vid, "error", err)
			response.InternalError(c, "failed to restore version")
		}
		return
	}
	response.Accepted(c, doc)
}

// POST /api/documents/:id/reupload/preview — admin: preview diff trước khi commit.
// Multipart: file=<new>. Trả PreviewResult (text diff hoặc metadata diff).
// KHÔNG ghi DB, KHÔNG snapshot, KHÔNG enqueue.
func (h *DocumentHandler) PreviewReupload(c *gin.Context) {
	id := c.Param("id")
	file, header, err := c.Request.FormFile("file")
	if err != nil {
		response.BadRequest(c, "file is required")
		return
	}
	defer file.Close()

	res, err := h.docService.PreviewReupload(c.Request.Context(), id, file, header)
	if err != nil {
		if isUserError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("preview reupload failed", "doc_id", id, "error", err)
		response.InternalError(c, "failed to preview reupload")
		return
	}
	response.OK(c, res)
}

// PUT /api/documents/:id/content/preview — admin: preview diff text edit.
// Body: {content}. Trả PreviewResult (text diff). KHÔNG ghi DB.
func (h *DocumentHandler) PreviewEditContent(c *gin.Context) {
	id := c.Param("id")
	var req struct {
		Content string `json:"content" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "content is required")
		return
	}
	res, err := h.docService.PreviewEditContent(c.Request.Context(), id, req.Content)
	if err != nil {
		if isUserError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		if strings.HasPrefix(err.Error(), "edit content not supported") {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("preview edit content failed", "doc_id", id, "error", err)
		response.InternalError(c, "failed to preview edit")
		return
	}
	response.OK(c, res)
}

// POST /api/documents/:id/reupload — admin thay file gốc, tự snapshot version.
func (h *DocumentHandler) ReUpload(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}
	id := c.Param("id")
	file, header, err := c.Request.FormFile("file")
	if err != nil {
		response.BadRequest(c, "file is required")
		return
	}
	defer file.Close()
	note := c.PostForm("note")

	doc, err := h.docService.ReUpload(c.Request.Context(), id, file, header, userID.String(), note)
	if err != nil {
		if isUserError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("reupload failed", "doc_id", id, "error", err)
		response.InternalError(c, "failed to reupload")
		return
	}
	response.Accepted(c, doc)
}

// PUT /api/documents/:id/content — admin sửa nội dung text, tự snapshot version.
func (h *DocumentHandler) EditContent(c *gin.Context) {
	userID, ok := middleware.GetUserID(c)
	if !ok {
		response.Unauthorized(c, "user not authenticated")
		return
	}
	id := c.Param("id")
	var req struct {
		Content string `json:"content" binding:"required"`
		Note    string `json:"note"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		response.BadRequest(c, "content is required")
		return
	}
	doc, err := h.docService.EditContent(c.Request.Context(), id, req.Content, userID.String(), req.Note)
	if err != nil {
		if isUserError(err) {
			response.BadRequest(c, err.Error())
			return
		}
		if strings.HasPrefix(err.Error(), "edit content not supported") {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("edit content failed", "doc_id", id, "error", err)
		response.InternalError(c, "failed to edit content")
		return
	}
	response.Accepted(c, doc)
}
