package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"mime/multipart"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/requestid"
	"github.com/medinet/hub-all-backend/internal/repository"
	"github.com/medinet/hub-all-backend/internal/storage"
	"github.com/medinet/hub-all-backend/internal/vectorstore"
	"github.com/medinet/hub-all-backend/internal/worker"
)

// Allowed file extensions for upload.
var allowedFileTypes = map[string]bool{
	"pdf":  true,
	"docx": true,
	"txt":  true,
	"md":   true,
	"xlsx": true,
	"pptx": true,
	"jpg":  true,
	"png":  true,
	"csv":  true,
	"html": true,
}

type DocumentService struct {
	docRepo     *repository.DocumentRepo
	hubRepo     *repository.HubRepo
	workerMgr   *worker.WorkerManager
	vecStore    vectorstore.VectorStore
	fileStore   storage.FileStorage
	uploadDir   string // local temp dir for pipeline processing
	maxFileSize int64
	// CFG-07 M1 Phase 4 — audit repo cho action="document_reindex".
	// Optional: nil → service vẫn chạy nhưng skip audit log (best-effort).
	// Set qua SetAuditRepo từ main.go để giữ constructor signature cũ.
	auditRepo *repository.AuditRepo
	// Version history (lịch sử phiên bản tài liệu). Optional.
	// Set qua SetVersionRepo từ main.go.
	versionRepo *repository.DocumentVersionRepo
}

// SetAuditRepo wire audit repo cho Reindex (CFG-07).
// Optional setter để KHÔNG đổi NewDocumentService signature ripple ra cmd/server.
func (s *DocumentService) SetAuditRepo(r *repository.AuditRepo) {
	s.auditRepo = r
}

func NewDocumentService(
	docRepo *repository.DocumentRepo,
	hubRepo *repository.HubRepo,
	workerMgr *worker.WorkerManager,
	vecStore vectorstore.VectorStore,
	fileStore storage.FileStorage,
	uploadDir string,
	maxFileSize int64,
) *DocumentService {
	if maxFileSize <= 0 {
		maxFileSize = 52428800 // 50MB
	}
	if uploadDir == "" {
		uploadDir = "./uploads"
	}
	return &DocumentService{
		docRepo:     docRepo,
		hubRepo:     hubRepo,
		workerMgr:   workerMgr,
		vecStore:    vecStore,
		fileStore:   fileStore,
		uploadDir:   uploadDir,
		maxFileSize: maxFileSize,
	}
}

// Upload handles file upload, saves to disk, creates DB record, and enqueues for processing.
func (s *DocumentService) Upload(ctx context.Context, file multipart.File, header *multipart.FileHeader, hubID, userID string) (*model.Document, error) {
	// Validate hub
	hubUUID, err := uuid.Parse(hubID)
	if err != nil {
		return nil, fmt.Errorf("invalid hub ID")
	}
	hub, err := s.hubRepo.FindByID(ctx, hubUUID)
	if err != nil {
		return nil, fmt.Errorf("find hub: %w", err)
	}
	if hub == nil {
		return nil, fmt.Errorf("hub not found")
	}

	// Validate user
	uploaderID, err := uuid.Parse(userID)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID")
	}

	// Validate file size
	if header.Size > s.maxFileSize {
		return nil, fmt.Errorf("file size %d exceeds maximum %d bytes", header.Size, s.maxFileSize)
	}

	// Validate file type (strip dot: ".pdf" → "pdf")
	ext := strings.ToLower(strings.TrimPrefix(filepath.Ext(header.Filename), "."))
	if !allowedFileTypes[ext] {
		return nil, fmt.Errorf("unsupported file type %q", ext)
	}

	// Read file content into memory (multipart reader can only be read once)
	docID := uuid.New()
	folder := hub.Code + "/" + docID.String()

	fileBytes, err := io.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("read upload file: %w", err)
	}
	slog.Info("upload: file read into memory", "name", header.Filename, "bytes", len(fileBytes), "header_size", header.Size)
	if len(fileBytes) == 0 {
		return nil, fmt.Errorf("uploaded file is empty (0 bytes read from multipart)")
	}

	// 1. Save locally for pipeline processing
	localDir := filepath.Join(s.uploadDir, hub.Code, docID.String())
	if err := os.MkdirAll(localDir, 0o755); err != nil {
		return nil, fmt.Errorf("create upload dir: %w", err)
	}
	localPath := filepath.Join(localDir, filepath.Base(header.Filename))
	if err := os.WriteFile(localPath, fileBytes, 0o644); err != nil {
		return nil, fmt.Errorf("save local file: %w", err)
	}
	slog.Info("upload: file saved locally", "path", localPath, "size_on_disk", len(fileBytes))

	// 2. Upload to remote storage (GDrive or local)
	remoteID := localPath
	if s.fileStore != nil {
		remoteID, err = s.fileStore.Upload(ctx, folder, header.Filename, bytes.NewReader(fileBytes))
		if err != nil {
			slog.Error("remote upload failed, keeping local only", "error", err)
			remoteID = localPath
		} else {
			slog.Info("file uploaded to remote storage", "remote_id", remoteID, "folder", folder)
		}
	}

	doc := &model.Document{
		ID:         docID,
		Name:       header.Filename,
		FileType:   ext,
		FileSize:   header.Size,
		FilePath:   remoteID, // GDrive file ID or local path
		HubID:      hubUUID,
		Status:     "pending",
		Progress:   0,
		ChunkCount: 0,
		UploadedBy: uploaderID,
		UploadedAt: time.Now().UTC(),
	}

	if err := s.docRepo.Create(ctx, doc); err != nil {
		_ = os.RemoveAll(localDir)
		return nil, fmt.Errorf("create document record: %w", err)
	}

	collection := hub.ChromaCollection
	if collection == "" {
		collection = "hub_" + hub.Code
	}

	// Enqueue for processing (uses local path for text extraction)
	if s.workerMgr != nil {
		s.workerMgr.Enqueue(worker.EmbedJob{
			DocumentID: docID.String(),
			DocName:    header.Filename,
			FilePath:   localPath,
			FileType:   ext,
			HubCode:    hub.Code,
			Collection: collection,
			RequestID:  requestid.From(ctx), // M1 Phase 3 — propagate (WIRE-06)
		})
	} else {
		slog.Warn("worker manager not available, document will not be processed", "doc_id", docID)
	}

	slog.Info("document uploaded", "doc_id", docID, "name", header.Filename, "hub", hub.Code)
	return doc, nil
}

// Compose creates a document from text content, saves as .md, and enqueues for processing.
func (s *DocumentService) Compose(ctx context.Context, name, content, hubID, userID string) (*model.Document, error) {
	if name == "" {
		return nil, fmt.Errorf("name is required")
	}
	if content == "" {
		return nil, fmt.Errorf("content is required")
	}

	// Validate hub
	hubUUID, err := uuid.Parse(hubID)
	if err != nil {
		return nil, fmt.Errorf("invalid hub ID")
	}
	hub, err := s.hubRepo.FindByID(ctx, hubUUID)
	if err != nil {
		return nil, fmt.Errorf("find hub: %w", err)
	}
	if hub == nil {
		return nil, fmt.Errorf("hub not found")
	}

	// Validate user
	uploaderID, err := uuid.Parse(userID)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID")
	}

	// Ensure .md extension
	if !strings.HasSuffix(name, ".md") {
		name = name + ".md"
	}

	docID := uuid.New()
	dirPath := filepath.Join(s.uploadDir, hub.Code, docID.String())
	if err := os.MkdirAll(dirPath, 0o755); err != nil {
		return nil, fmt.Errorf("create upload dir: %w", err)
	}

	filePath := filepath.Join(dirPath, filepath.Base(name))
	if err := os.WriteFile(filePath, []byte(content), 0o644); err != nil {
		return nil, fmt.Errorf("write file: %w", err)
	}

	doc := &model.Document{
		ID:         docID,
		Name:       name,
		FileType:   "md",
		FileSize:   int64(len(content)),
		FilePath:   filePath,
		HubID:      hubUUID,
		Status:     "pending",
		Progress:   0,
		ChunkCount: 0,
		UploadedBy: uploaderID,
		UploadedAt: time.Now().UTC(),
	}

	if err := s.docRepo.Create(ctx, doc); err != nil {
		_ = os.RemoveAll(dirPath)
		return nil, fmt.Errorf("create document record: %w", err)
	}

	collection := hub.ChromaCollection
	if collection == "" {
		collection = "hub_" + hub.Code
	}

	if s.workerMgr != nil {
		s.workerMgr.Enqueue(worker.EmbedJob{
			DocumentID: docID.String(),
			DocName:    name,
			FilePath:   filePath,
			FileType:   "md",
			HubCode:    hub.Code,
			Collection: collection,
			RequestID:  requestid.From(ctx), // M1 Phase 3 — propagate (WIRE-06)
		})
	} else {
		slog.Warn("worker manager not available, document will not be processed", "doc_id", docID)
	}

	slog.Info("document composed", "doc_id", docID, "name", name, "hub", hub.Code)
	return doc, nil
}

// List returns paginated documents.
func (s *DocumentService) List(ctx context.Context, hubID, status, fileType string, page, perPage int) ([]model.Document, int64, error) {
	if page < 1 {
		page = 1
	}
	if perPage < 1 {
		perPage = 20
	}
	if perPage > 100 {
		perPage = 100
	}

	offset := (page - 1) * perPage
	docs, total, err := s.docRepo.List(ctx, hubID, status, fileType, perPage, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("list documents: %w", err)
	}
	return docs, total, nil
}

// GetByID returns a single document.
func (s *DocumentService) GetByID(ctx context.Context, id string) (*model.Document, error) {
	docUUID, err := uuid.Parse(id)
	if err != nil {
		return nil, fmt.Errorf("invalid document ID")
	}

	doc, err := s.docRepo.FindByID(ctx, docUUID)
	if err != nil {
		return nil, fmt.Errorf("find document: %w", err)
	}
	if doc == nil {
		return nil, fmt.Errorf("document not found")
	}
	return doc, nil
}

// GetFile opens the original file for a document and returns a reader,
// along with the document metadata. Caller must Close the reader.
// Falls back to local upload directory when remote storage is unavailable
// or fails (covers both local-only and GDrive setups).
func (s *DocumentService) GetFile(ctx context.Context, id string) (io.ReadCloser, *model.Document, error) {
	doc, err := s.GetByID(ctx, id)
	if err != nil {
		return nil, nil, err
	}

	// 1. Try remote storage first if configured
	if s.fileStore != nil && doc.FilePath != "" {
		reader, err := s.fileStore.Download(ctx, doc.FilePath)
		if err == nil {
			return reader, doc, nil
		}
		slog.Warn("remote download failed, trying local fallback", "doc_id", id, "error", err)
	}

	// 2. Try the path stored in DB directly (covers local storage)
	if doc.FilePath != "" {
		if f, err := os.Open(doc.FilePath); err == nil {
			return f, doc, nil
		}
	}

	// 3. Fallback: reconstruct local path under uploadDir
	hub, err := s.hubRepo.FindByID(ctx, doc.HubID)
	if err == nil && hub != nil {
		localPath := filepath.Join(s.uploadDir, hub.Code, doc.ID.String(), doc.Name)
		if f, err := os.Open(localPath); err == nil {
			return f, doc, nil
		}
	}

	return nil, doc, fmt.Errorf("file not found")
}

// GetStatus returns the processing status and progress of a document.
func (s *DocumentService) GetStatus(ctx context.Context, id string) (string, int, error) {
	doc, err := s.GetByID(ctx, id)
	if err != nil {
		return "", 0, err
	}
	return doc.Status, doc.Progress, nil
}

// Reindex xóa chunks cũ (Postgres + ChromaDB), reset trạng thái document,
// và enqueue job mới với ForcedExtractor (CFG-07 M1 Phase 4).
//
// extractor ∈ {docling, native, auto}: handler đã default về runtime mode
// nếu user omit query param. KHÔNG re-upload remote storage — file_path
// giữ nguyên, pipeline đọc lại từ local copy hoặc download từ remote.
//
// Trả về document đã reset status='pending' (frontend dùng để update UI ngay).
// Caller (handler) chịu trách nhiệm map error → HTTP code.
func (s *DocumentService) Reindex(ctx context.Context, id, extractor, requesterID string) (*model.Document, error) {
	docUUID, err := uuid.Parse(id)
	if err != nil {
		return nil, fmt.Errorf("invalid document ID")
	}

	// Validate extractor enum.
	switch extractor {
	case "docling", "native", "auto":
		// ok
	default:
		return nil, fmt.Errorf("invalid extractor %q (must be docling|native|auto)", extractor)
	}

	doc, err := s.docRepo.FindByID(ctx, docUUID)
	if err != nil {
		return nil, fmt.Errorf("find document: %w", err)
	}
	if doc == nil {
		return nil, fmt.Errorf("document not found")
	}

	hub, err := s.hubRepo.FindByID(ctx, doc.HubID)
	if err != nil {
		return nil, fmt.Errorf("find hub: %w", err)
	}
	if hub == nil {
		return nil, fmt.Errorf("hub not found for document")
	}

	collection := hub.ChromaCollection
	if collection == "" {
		collection = "hub_" + hub.Code
	}

	// ─── Resolve local file path ──────────────────────────────────
	// Pipeline cần local path. Nếu doc.FilePath là local readable → dùng trực tiếp.
	// Nếu remote (GDrive ID) → download xuống uploadDir/<hub.Code>/<docID>/<name>.
	// KHÔNG đổi doc.FilePath (CFG-07: giữ nguyên file_path).
	localPath, err := s.ensureLocalCopy(ctx, doc, hub)
	if err != nil {
		return nil, fmt.Errorf("ensure local copy: %w", err)
	}

	// ─── Snapshot version trước khi xoá chunks ────────────────────
	// Để có thể restore về trạng thái trước reindex (file gốc + chunks).
	var requesterUUID *uuid.UUID
	if u, perr := uuid.Parse(requesterID); perr == nil {
		requesterUUID = &u
	}
	if vErr := s.snapshotCurrentAsVersion(ctx, doc, hub.Code, "reextract",
		fmt.Sprintf("Reindex với extractor=%s", extractor), requesterUUID); vErr != nil {
		slog.Warn("reindex: snapshot version failed (continuing)", "doc_id", id, "error", vErr)
	}

	// ─── Xóa chunks cũ TRƯỚC khi enqueue ──────────────────────────
	// Tránh trường hợp pipeline mới fail giữa chừng để lại chunks cũ + chunks mới
	// lẫn lộn. Pipeline mới chạy từ trạng thái sạch.
	if err := s.docRepo.DeleteChunksByDocID(ctx, docUUID); err != nil {
		slog.Error("reindex: delete chunks Postgres failed (continuing)", "doc_id", id, "error", err)
	}
	if s.vecStore != nil {
		if err := s.vecStore.Delete(ctx, collection, map[string]any{"document_id": id}); err != nil {
			slog.Error("reindex: delete chunks Chroma failed (continuing)", "doc_id", id, "error", err)
		}
	}

	// ─── Reset trạng thái + clear extractor_used ──────────────────
	if err := s.docRepo.UpdateStatus(ctx, docUUID, "pending", nil); err != nil {
		return nil, fmt.Errorf("reset status: %w", err)
	}
	if err := s.docRepo.UpdateProgress(ctx, docUUID, 0); err != nil {
		return nil, fmt.Errorf("reset progress: %w", err)
	}
	if err := s.docRepo.ClearExtractorUsed(ctx, docUUID); err != nil {
		slog.Warn("reindex: clear extractor_used failed (non-fatal)", "doc_id", id, "error", err)
	}

	// ─── Enqueue job mới với ForcedExtractor ──────────────────────
	if s.workerMgr == nil {
		return nil, fmt.Errorf("worker manager not available")
	}
	s.workerMgr.Enqueue(worker.EmbedJob{
		DocumentID:      docUUID.String(),
		DocName:         doc.Name,
		FilePath:        localPath,
		FileType:        doc.FileType,
		HubCode:         hub.Code,
		Collection:      collection,
		RequestID:       requestid.From(ctx),
		IsReindex:       true,
		ForcedExtractor: extractor,
	})

	// ─── Audit log action="document_reindex" ──────────────────────
	if s.auditRepo != nil {
		previousExtractor := ""
		if doc.ExtractorUsed != nil {
			previousExtractor = *doc.ExtractorUsed
		}
		reqID := requestid.From(ctx)
		payload := map[string]any{
			"document_id":        id,
			"extractor_param":    extractor,
			"previous_extractor": previousExtractor,
			"request_id":         reqID,
			"requester_id":       requesterID,
		}
		payloadJSON, _ := json.Marshal(payload)
		var actorIDPtr *uuid.UUID
		if requesterID != "" {
			if u, err := uuid.Parse(requesterID); err == nil {
				actorIDPtr = &u
			}
		}
		actorName := "admin"
		if err := s.auditRepo.Insert(ctx, &model.AuditLogEntry{
			ID:        uuid.New(),
			Timestamp: time.Now().UTC(),
			UserID:    actorIDPtr,
			UserName:  &actorName,
			IsAI:      false,
			Action:    "document_reindex",
			Payload:   payloadJSON,
		}); err != nil {
			slog.Warn("reindex: audit insert failed (non-fatal)", "doc_id", id, "error", err)
		}
	}

	slog.Info("document reindex enqueued",
		"doc_id", id, "extractor", extractor, "requester", requesterID)

	// Trả document mới (status reset). Đọc lại để có giá trị extractor_used=NULL chuẩn.
	updated, _ := s.docRepo.FindByID(ctx, docUUID)
	if updated != nil {
		return updated, nil
	}
	// Fallback nếu read lại fail — vẫn trả doc cũ với patch tay status.
	doc.Status = "pending"
	doc.Progress = 0
	doc.ExtractorUsed = nil
	return doc, nil
}

// ensureLocalCopy đảm bảo có file local cho pipeline đọc (CFG-07 reindex).
// Thứ tự thử:
//  1. doc.FilePath nếu là local file readable → dùng trực tiếp.
//  2. uploadDir/<hub.Code>/<docID>/<name> canonical path.
//  3. Download từ remote (fileStore.Download(doc.FilePath)) ghi xuống path canonical.
//
// Trả lỗi nếu cả 3 fallback đều miss.
func (s *DocumentService) ensureLocalCopy(ctx context.Context, doc *model.Document, hub *model.Hub) (string, error) {
	// 1. doc.FilePath là local file readable.
	if doc.FilePath != "" {
		if _, err := os.Stat(doc.FilePath); err == nil {
			return doc.FilePath, nil
		}
	}

	// 2. Reconstruct canonical local path.
	localDir := filepath.Join(s.uploadDir, hub.Code, doc.ID.String())
	localPath := filepath.Join(localDir, doc.Name)
	if _, err := os.Stat(localPath); err == nil {
		return localPath, nil
	}

	// 3. Download từ remote storage.
	if s.fileStore != nil && doc.FilePath != "" {
		reader, err := s.fileStore.Download(ctx, doc.FilePath)
		if err != nil {
			return "", fmt.Errorf("remote download: %w", err)
		}
		defer reader.Close()

		if err := os.MkdirAll(localDir, 0o755); err != nil {
			return "", fmt.Errorf("mkdir local: %w", err)
		}
		out, err := os.Create(localPath)
		if err != nil {
			return "", fmt.Errorf("create local file: %w", err)
		}
		defer out.Close()
		if _, err := io.Copy(out, reader); err != nil {
			return "", fmt.Errorf("write local file: %w", err)
		}
		return localPath, nil
	}

	return "", fmt.Errorf("file not found locally and no remote storage configured")
}

// Delete removes a document from DB, ChromaDB, and disk.
func (s *DocumentService) Delete(ctx context.Context, id string) error {
	docUUID, err := uuid.Parse(id)
	if err != nil {
		return fmt.Errorf("invalid document ID")
	}

	doc, err := s.docRepo.FindByID(ctx, docUUID)
	if err != nil {
		return fmt.Errorf("find document: %w", err)
	}
	if doc == nil {
		return fmt.Errorf("document not found")
	}

	// Delete chunks from DB
	if err := s.docRepo.DeleteChunksByDocID(ctx, docUUID); err != nil {
		slog.Error("failed to delete chunks from DB", "doc_id", id, "error", err)
	}

	// Delete from ChromaDB
	if s.vecStore != nil {
		hub, err := s.hubRepo.FindByID(ctx, doc.HubID)
		if err == nil && hub != nil {
			collection := hub.ChromaCollection
			if collection == "" {
				collection = "hub_" + hub.Code
			}
			filter := map[string]any{"document_id": id}
			if err := s.vecStore.Delete(ctx, collection, filter); err != nil {
				slog.Error("failed to delete from ChromaDB", "doc_id", id, "error", err)
			}
		}
	}

	// Delete from DB
	if err := s.docRepo.Delete(ctx, docUUID); err != nil {
		return fmt.Errorf("delete document: %w", err)
	}

	// Delete from remote storage (GDrive)
	if s.fileStore != nil {
		if err := s.fileStore.Delete(ctx, doc.FilePath); err != nil {
			slog.Error("failed to delete from remote storage", "doc_id", id, "error", err)
		}
	}

	// Delete local temp files
	dirPath := filepath.Dir(doc.FilePath)
	_ = os.RemoveAll(dirPath) // ignore error — may not exist locally

	slog.Info("document deleted", "doc_id", id)
	return nil
}
