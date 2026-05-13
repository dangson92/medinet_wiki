package service

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
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
	"github.com/medinet/hub-all-backend/internal/worker"
)

// SetVersionRepo wire repository version vào DocumentService.
// Optional setter để KHÔNG đổi NewDocumentService signature.
// nil → service skip mọi version snapshot (degrade gracefully).
func (s *DocumentService) SetVersionRepo(r *repository.DocumentVersionRepo) {
	s.versionRepo = r
}

// snapshotCurrentAsVersion chụp trạng thái hiện tại của document thành 1
// row document_versions + chunks. Copy file binary sang versions/v{n}.{ext}
// để file gốc của document KHÔNG bị ảnh hưởng khi version cũ bị prune.
//
// changeType ∈ {reupload, reextract, content_edit, restore}.
// Caller trách nhiệm gọi trước khi mutate document (xoá chunks, đổi file).
func (s *DocumentService) snapshotCurrentAsVersion(
	ctx context.Context,
	doc *model.Document,
	hubCode string,
	changeType string,
	changeNote string,
	createdBy *uuid.UUID,
) error {
	if s.versionRepo == nil {
		slog.Debug("snapshot skipped: versionRepo not wired", "doc_id", doc.ID)
		return nil
	}

	versionNum, err := s.versionRepo.NextVersionNumber(ctx, doc.ID)
	if err != nil {
		return fmt.Errorf("next version number: %w", err)
	}

	// 1. Chụp file binary sang storage versions/v{n}.{ext}
	//    Đọc bằng GetFile (đã cover remote/local fallback).
	//    Hash sha256 đồng thời để dedup tham khảo.
	versionsDir := filepath.Join(s.uploadDir, hubCode, doc.ID.String(), "versions")
	if err := os.MkdirAll(versionsDir, 0o755); err != nil {
		return fmt.Errorf("mkdir versions dir: %w", err)
	}
	versionFilePath := filepath.Join(versionsDir, fmt.Sprintf("v%d.%s", versionNum, doc.FileType))

	var fileHash *string
	reader, _, err := s.GetFile(ctx, doc.ID.String())
	if err != nil {
		// File gốc không tìm thấy — vẫn cho phép tạo version metadata-only.
		// Hiếm gặp, nhưng tránh block flow chính.
		slog.Warn("snapshot: original file not found, version metadata-only",
			"doc_id", doc.ID, "error", err)
		versionFilePath = ""
	} else {
		defer reader.Close()
		out, cErr := os.Create(versionFilePath)
		if cErr != nil {
			return fmt.Errorf("create version file: %w", cErr)
		}
		hasher := sha256.New()
		if _, wErr := io.Copy(io.MultiWriter(out, hasher), reader); wErr != nil {
			_ = out.Close()
			_ = os.Remove(versionFilePath)
			return fmt.Errorf("copy version file: %w", wErr)
		}
		_ = out.Close()
		h := hex.EncodeToString(hasher.Sum(nil))
		fileHash = &h
	}

	// 2. Snapshot chunks từ document_chunks hiện tại.
	chunksLive, err := s.docRepo.GetChunks(ctx, doc.ID)
	if err != nil {
		slog.Warn("snapshot: get chunks failed (continuing with empty)",
			"doc_id", doc.ID, "error", err)
	}
	versionID := uuid.New()
	versionChunks := make([]model.DocumentVersionChunk, 0, len(chunksLive))
	for _, c := range chunksLive {
		versionChunks = append(versionChunks, model.DocumentVersionChunk{
			ID:         uuid.New(),
			VersionID:  versionID,
			ChunkIndex: c.ChunkIndex,
			Content:    c.Content,
			TokenCount: c.TokenCount,
			Metadata:   c.Metadata,
		})
	}

	var note *string
	if strings.TrimSpace(changeNote) != "" {
		n := changeNote
		note = &n
	}

	v := &model.DocumentVersion{
		ID:            versionID,
		DocumentID:    doc.ID,
		VersionNumber: versionNum,
		Name:          doc.Name,
		FileType:      doc.FileType,
		FileSize:      doc.FileSize,
		FilePath:      versionFilePath,
		FileHash:      fileHash,
		ExtractorUsed: doc.ExtractorUsed,
		ChunkCount:    doc.ChunkCount,
		ChangeType:    changeType,
		ChangeNote:    note,
		CreatedBy:     createdBy,
		CreatedAt:     time.Now().UTC(),
	}

	prunedFiles, err := s.versionRepo.CreateWithChunks(ctx, v, versionChunks)
	if err != nil {
		// Rollback file binary nếu DB fail.
		if versionFilePath != "" {
			_ = os.Remove(versionFilePath)
		}
		return fmt.Errorf("create version with chunks: %w", err)
	}

	// 3. Dọn file binary của các version đã bị prune.
	for _, p := range prunedFiles {
		if p == "" {
			continue
		}
		if rmErr := os.Remove(p); rmErr != nil && !os.IsNotExist(rmErr) {
			slog.Warn("prune: remove version file failed",
				"path", p, "error", rmErr)
		}
	}

	slog.Info("document version snapshotted",
		"doc_id", doc.ID, "version", versionNum, "change_type", changeType,
		"chunks", len(versionChunks), "pruned_files", len(prunedFiles))
	return nil
}

// ListVersions trả tất cả version của document (max 5).
func (s *DocumentService) ListVersions(ctx context.Context, docID string) ([]model.DocumentVersion, error) {
	if s.versionRepo == nil {
		return []model.DocumentVersion{}, nil
	}
	id, err := uuid.Parse(docID)
	if err != nil {
		return nil, fmt.Errorf("invalid document ID")
	}
	return s.versionRepo.ListByDocument(ctx, id)
}

// GetVersion trả 1 version + chunks snapshot.
func (s *DocumentService) GetVersion(
	ctx context.Context, versionID string,
) (*model.DocumentVersion, []model.DocumentVersionChunk, error) {
	if s.versionRepo == nil {
		return nil, nil, fmt.Errorf("version history not enabled")
	}
	vid, err := uuid.Parse(versionID)
	if err != nil {
		return nil, nil, fmt.Errorf("invalid version ID")
	}
	v, err := s.versionRepo.FindByID(ctx, vid)
	if err != nil {
		return nil, nil, err
	}
	if v == nil {
		return nil, nil, fmt.Errorf("version not found")
	}
	chunks, err := s.versionRepo.GetChunks(ctx, vid)
	if err != nil {
		return v, nil, err
	}
	return v, chunks, nil
}

// OpenVersionFile mở file binary của 1 version (download/preview).
func (s *DocumentService) OpenVersionFile(
	ctx context.Context, versionID string,
) (io.ReadCloser, *model.DocumentVersion, error) {
	v, _, err := s.GetVersion(ctx, versionID)
	if err != nil {
		return nil, nil, err
	}
	if v.FilePath == "" {
		return nil, v, fmt.Errorf("version file missing")
	}
	f, err := os.Open(v.FilePath)
	if err != nil {
		return nil, v, fmt.Errorf("open version file: %w", err)
	}
	return f, v, nil
}

// RestoreVersion khôi phục document về 1 version cũ:
//  1. Snapshot trạng thái hiện tại (change_type=restore) — bảo toàn audit.
//  2. Copy file binary của version đích → file gốc của document.
//  3. Xoá chunks Postgres + Chroma, reset status='pending'.
//  4. Enqueue worker re-extract + re-embed (giữ extractor cũ nếu có).
//
// Trả document đã reset (status='pending', progress=0).
func (s *DocumentService) RestoreVersion(
	ctx context.Context, versionID, requesterID string,
) (*model.Document, error) {
	if s.versionRepo == nil {
		return nil, fmt.Errorf("version history not enabled")
	}
	vid, err := uuid.Parse(versionID)
	if err != nil {
		return nil, fmt.Errorf("invalid version ID")
	}
	v, err := s.versionRepo.FindByID(ctx, vid)
	if err != nil {
		return nil, err
	}
	if v == nil {
		return nil, fmt.Errorf("version not found")
	}
	if v.FilePath == "" {
		return nil, fmt.Errorf("version file missing — cannot restore")
	}

	doc, err := s.docRepo.FindByID(ctx, v.DocumentID)
	if err != nil {
		return nil, fmt.Errorf("find document: %w", err)
	}
	if doc == nil {
		return nil, fmt.Errorf("document not found")
	}
	hub, err := s.hubRepo.FindByID(ctx, doc.HubID)
	if err != nil || hub == nil {
		return nil, fmt.Errorf("hub not found")
	}

	var requesterUUID *uuid.UUID
	if u, perr := uuid.Parse(requesterID); perr == nil {
		requesterUUID = &u
	}

	// 1. Snapshot trạng thái hiện tại trước khi ghi đè.
	if err := s.snapshotCurrentAsVersion(ctx, doc, hub.Code, "restore",
		fmt.Sprintf("Khôi phục từ v%d", v.VersionNumber), requesterUUID); err != nil {
		return nil, fmt.Errorf("snapshot before restore: %w", err)
	}

	// 2. Copy file version đích → file gốc của document.
	localDir := filepath.Join(s.uploadDir, hub.Code, doc.ID.String())
	if err := os.MkdirAll(localDir, 0o755); err != nil {
		return nil, fmt.Errorf("mkdir local: %w", err)
	}
	targetPath := filepath.Join(localDir, doc.Name)
	if err := copyFile(v.FilePath, targetPath); err != nil {
		return nil, fmt.Errorf("copy version → current: %w", err)
	}

	collection := hub.ChromaCollection
	if collection == "" {
		collection = "hub_" + hub.Code
	}

	// 3. Xoá chunks Postgres + Chroma + reset trạng thái.
	if err := s.docRepo.DeleteChunksByDocID(ctx, doc.ID); err != nil {
		slog.Error("restore: delete chunks Postgres failed", "error", err)
	}
	if s.vecStore != nil {
		_ = s.vecStore.Delete(ctx, collection, map[string]any{"document_id": doc.ID.String()})
	}
	_ = s.docRepo.UpdateStatus(ctx, doc.ID, "pending", nil)
	_ = s.docRepo.UpdateProgress(ctx, doc.ID, 0)
	_ = s.docRepo.ClearExtractorUsed(ctx, doc.ID)

	// 4. Enqueue re-extract.
	if s.workerMgr != nil {
		s.workerMgr.Enqueue(worker.EmbedJob{
			DocumentID: doc.ID.String(),
			DocName:    doc.Name,
			FilePath:   targetPath,
			FileType:   doc.FileType,
			HubCode:    hub.Code,
			Collection: collection,
			RequestID:  requestid.From(ctx),
			IsReindex:  true,
		})
	}

	slog.Info("document restored from version",
		"doc_id", doc.ID, "from_version", v.VersionNumber, "requester", requesterID)

	updated, _ := s.docRepo.FindByID(ctx, doc.ID)
	if updated != nil {
		return updated, nil
	}
	doc.Status = "pending"
	doc.Progress = 0
	return doc, nil
}

// ReUpload thay file gốc của document bằng file mới (cùng doc ID, cùng hub),
// snapshot version trước, rồi enqueue re-extract.
func (s *DocumentService) ReUpload(
	ctx context.Context,
	docID string,
	file multipart.File,
	header *multipart.FileHeader,
	requesterID, note string,
) (*model.Document, error) {
	id, err := uuid.Parse(docID)
	if err != nil {
		return nil, fmt.Errorf("invalid document ID")
	}
	doc, err := s.docRepo.FindByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("find document: %w", err)
	}
	if doc == nil {
		return nil, fmt.Errorf("document not found")
	}
	if header.Size > s.maxFileSize {
		return nil, fmt.Errorf("file size %d exceeds maximum %d bytes", header.Size, s.maxFileSize)
	}
	ext := strings.ToLower(strings.TrimPrefix(filepath.Ext(header.Filename), "."))
	if !allowedFileTypes[ext] {
		return nil, fmt.Errorf("unsupported file type %q", ext)
	}
	hub, err := s.hubRepo.FindByID(ctx, doc.HubID)
	if err != nil || hub == nil {
		return nil, fmt.Errorf("hub not found")
	}

	var requesterUUID *uuid.UUID
	if u, perr := uuid.Parse(requesterID); perr == nil {
		requesterUUID = &u
	}

	// 1. Snapshot trước.
	if err := s.snapshotCurrentAsVersion(ctx, doc, hub.Code, "reupload", note, requesterUUID); err != nil {
		return nil, fmt.Errorf("snapshot before reupload: %w", err)
	}

	// 2. Ghi file mới đè vị trí cũ (giữ tên doc.Name; nếu ext khác → cập nhật).
	fileBytes, err := io.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("read upload: %w", err)
	}
	if len(fileBytes) == 0 {
		return nil, fmt.Errorf("uploaded file is empty")
	}
	localDir := filepath.Join(s.uploadDir, hub.Code, doc.ID.String())
	if err := os.MkdirAll(localDir, 0o755); err != nil {
		return nil, fmt.Errorf("mkdir local: %w", err)
	}
	// Giữ tên gốc của document để URL/path ổn định; chỉ đổi nội dung + size + type.
	newName := doc.Name
	if !strings.EqualFold(filepath.Ext(newName), "."+ext) {
		newName = strings.TrimSuffix(newName, filepath.Ext(newName)) + "." + ext
	}
	localPath := filepath.Join(localDir, newName)
	if err := os.WriteFile(localPath, fileBytes, 0o644); err != nil {
		return nil, fmt.Errorf("write file: %w", err)
	}

	// 3. Update document row: name/file_type/file_size/file_path.
	if err := s.docRepo.UpdateFileInfo(ctx, doc.ID, newName, ext, int64(len(fileBytes)), localPath); err != nil {
		return nil, fmt.Errorf("update file info: %w", err)
	}

	collection := hub.ChromaCollection
	if collection == "" {
		collection = "hub_" + hub.Code
	}

	// 4. Xoá chunks cũ + reset + enqueue.
	_ = s.docRepo.DeleteChunksByDocID(ctx, doc.ID)
	if s.vecStore != nil {
		_ = s.vecStore.Delete(ctx, collection, map[string]any{"document_id": doc.ID.String()})
	}
	_ = s.docRepo.UpdateStatus(ctx, doc.ID, "pending", nil)
	_ = s.docRepo.UpdateProgress(ctx, doc.ID, 0)
	_ = s.docRepo.ClearExtractorUsed(ctx, doc.ID)

	if s.workerMgr != nil {
		s.workerMgr.Enqueue(worker.EmbedJob{
			DocumentID: doc.ID.String(),
			DocName:    newName,
			FilePath:   localPath,
			FileType:   ext,
			HubCode:    hub.Code,
			Collection: collection,
			RequestID:  requestid.From(ctx),
			IsReindex:  true,
		})
	}

	updated, _ := s.docRepo.FindByID(ctx, doc.ID)
	if updated != nil {
		return updated, nil
	}
	return doc, nil
}

// EditContent thay nội dung text của document (.md/.txt) bằng content mới,
// snapshot version trước, rồi enqueue re-extract.
func (s *DocumentService) EditContent(
	ctx context.Context, docID, content, requesterID, note string,
) (*model.Document, error) {
	id, err := uuid.Parse(docID)
	if err != nil {
		return nil, fmt.Errorf("invalid document ID")
	}
	if strings.TrimSpace(content) == "" {
		return nil, fmt.Errorf("content is required")
	}
	doc, err := s.docRepo.FindByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("find document: %w", err)
	}
	if doc == nil {
		return nil, fmt.Errorf("document not found")
	}
	// Chỉ cho phép edit content khi file là text (md/txt/html/csv).
	switch strings.ToLower(doc.FileType) {
	case "md", "txt", "html", "csv":
		// ok
	default:
		return nil, fmt.Errorf("edit content not supported for file type %q", doc.FileType)
	}
	hub, err := s.hubRepo.FindByID(ctx, doc.HubID)
	if err != nil || hub == nil {
		return nil, fmt.Errorf("hub not found")
	}

	var requesterUUID *uuid.UUID
	if u, perr := uuid.Parse(requesterID); perr == nil {
		requesterUUID = &u
	}

	if err := s.snapshotCurrentAsVersion(ctx, doc, hub.Code, "content_edit", note, requesterUUID); err != nil {
		return nil, fmt.Errorf("snapshot before edit: %w", err)
	}

	localDir := filepath.Join(s.uploadDir, hub.Code, doc.ID.String())
	if err := os.MkdirAll(localDir, 0o755); err != nil {
		return nil, fmt.Errorf("mkdir local: %w", err)
	}
	localPath := filepath.Join(localDir, doc.Name)
	if err := os.WriteFile(localPath, []byte(content), 0o644); err != nil {
		return nil, fmt.Errorf("write file: %w", err)
	}
	if err := s.docRepo.UpdateFileInfo(ctx, doc.ID, doc.Name, doc.FileType, int64(len(content)), localPath); err != nil {
		return nil, fmt.Errorf("update file info: %w", err)
	}

	collection := hub.ChromaCollection
	if collection == "" {
		collection = "hub_" + hub.Code
	}
	_ = s.docRepo.DeleteChunksByDocID(ctx, doc.ID)
	if s.vecStore != nil {
		_ = s.vecStore.Delete(ctx, collection, map[string]any{"document_id": doc.ID.String()})
	}
	_ = s.docRepo.UpdateStatus(ctx, doc.ID, "pending", nil)
	_ = s.docRepo.UpdateProgress(ctx, doc.ID, 0)
	_ = s.docRepo.ClearExtractorUsed(ctx, doc.ID)

	if s.workerMgr != nil {
		s.workerMgr.Enqueue(worker.EmbedJob{
			DocumentID: doc.ID.String(),
			DocName:    doc.Name,
			FilePath:   localPath,
			FileType:   doc.FileType,
			HubCode:    hub.Code,
			Collection: collection,
			RequestID:  requestid.From(ctx),
			IsReindex:  true,
		})
	}

	updated, _ := s.docRepo.FindByID(ctx, doc.ID)
	if updated != nil {
		return updated, nil
	}
	return doc, nil
}

// IsTextFileType trả TRUE nếu file type có thể đọc trực tiếp dưới dạng text
// (cho diff preview). PDF/DOCX/XLSX/PPTX/ảnh được xem là binary, cần
// extractor pipeline → KHÔNG diff inline.
func IsTextFileType(t string) bool {
	switch strings.ToLower(t) {
	case "md", "txt", "csv", "html":
		return true
	}
	return false
}

// PreviewMeta là metadata hiển thị diff cho file binary.
type PreviewMeta struct {
	Name     string `json:"name"`
	FileType string `json:"file_type"`
	FileSize int64  `json:"file_size"`
	FileHash string `json:"file_hash"`
}

// PreviewResult là payload trả cho FE để render DiffPreview.
type PreviewResult struct {
	IsText  bool         `json:"is_text"`
	OldText string       `json:"old_text,omitempty"`
	NewText string       `json:"new_text,omitempty"`
	OldMeta *PreviewMeta `json:"old_meta,omitempty"`
	NewMeta *PreviewMeta `json:"new_meta,omitempty"`
	Note    string       `json:"note,omitempty"`
}

// loadCurrentText đọc nội dung text hiện tại của document để diff:
//   - Text-based file → đọc thẳng file gốc.
//   - Binary file → concat chunks (nếu có), prefix mỗi chunk bằng "--- chunk N ---".
//
// Nếu không có file/chunks → trả "".
func (s *DocumentService) loadCurrentText(ctx context.Context, doc *model.Document) (string, error) {
	if IsTextFileType(doc.FileType) {
		reader, _, err := s.GetFile(ctx, doc.ID.String())
		if err != nil {
			return "", nil // không có file → text rỗng
		}
		defer reader.Close()
		b, rErr := io.ReadAll(reader)
		if rErr != nil {
			return "", fmt.Errorf("read current text: %w", rErr)
		}
		return string(b), nil
	}
	// Binary → ghép chunks (nếu pipeline đã chạy).
	chunks, err := s.docRepo.GetChunks(ctx, doc.ID)
	if err != nil {
		return "", nil
	}
	var b strings.Builder
	for _, c := range chunks {
		b.WriteString(fmt.Sprintf("--- chunk %d ---\n", c.ChunkIndex))
		b.WriteString(c.Content)
		b.WriteString("\n\n")
	}
	return b.String(), nil
}

// PreviewReupload preview thay đổi khi reupload file mới:
//   - Text-based + new file cũng text-based → diff text.
//   - Binary → trả metadata diff (kèm hash sha256).
//
// KHÔNG ghi DB, KHÔNG snapshot version, KHÔNG enqueue worker.
func (s *DocumentService) PreviewReupload(
	ctx context.Context, docID string, file multipart.File, header *multipart.FileHeader,
) (*PreviewResult, error) {
	id, err := uuid.Parse(docID)
	if err != nil {
		return nil, fmt.Errorf("invalid document ID")
	}
	doc, err := s.docRepo.FindByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("find document: %w", err)
	}
	if doc == nil {
		return nil, fmt.Errorf("document not found")
	}
	if header.Size > s.maxFileSize {
		return nil, fmt.Errorf("file size %d exceeds maximum %d bytes", header.Size, s.maxFileSize)
	}
	newExt := strings.ToLower(strings.TrimPrefix(filepath.Ext(header.Filename), "."))
	if !allowedFileTypes[newExt] {
		return nil, fmt.Errorf("unsupported file type %q", newExt)
	}

	newBytes, err := io.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("read upload: %w", err)
	}
	newHasher := sha256.New()
	newHasher.Write(newBytes)
	newHash := hex.EncodeToString(newHasher.Sum(nil))

	bothText := IsTextFileType(doc.FileType) && IsTextFileType(newExt)

	res := &PreviewResult{IsText: bothText}
	if bothText {
		oldText, _ := s.loadCurrentText(ctx, doc)
		res.OldText = oldText
		res.NewText = string(newBytes)
	} else {
		// Hash file hiện tại nếu đọc được.
		oldHash := ""
		if reader, _, err := s.GetFile(ctx, doc.ID.String()); err == nil {
			h := sha256.New()
			_, _ = io.Copy(h, reader)
			_ = reader.Close()
			oldHash = hex.EncodeToString(h.Sum(nil))
		}
		res.OldMeta = &PreviewMeta{
			Name: doc.Name, FileType: doc.FileType, FileSize: doc.FileSize, FileHash: oldHash,
		}
		res.NewMeta = &PreviewMeta{
			Name: header.Filename, FileType: newExt, FileSize: int64(len(newBytes)), FileHash: newHash,
		}
		res.Note = "Không thể preview nội dung cho file binary. Vector hóa sẽ chạy lại sau khi xác nhận."
	}
	return res, nil
}

// PreviewEditContent preview thay đổi khi edit nội dung text (.md/.txt/...).
// KHÔNG ghi DB.
func (s *DocumentService) PreviewEditContent(
	ctx context.Context, docID, newContent string,
) (*PreviewResult, error) {
	id, err := uuid.Parse(docID)
	if err != nil {
		return nil, fmt.Errorf("invalid document ID")
	}
	doc, err := s.docRepo.FindByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("find document: %w", err)
	}
	if doc == nil {
		return nil, fmt.Errorf("document not found")
	}
	if !IsTextFileType(doc.FileType) {
		return nil, fmt.Errorf("edit content not supported for file type %q", doc.FileType)
	}
	oldText, _ := s.loadCurrentText(ctx, doc)
	return &PreviewResult{
		IsText:  true,
		OldText: oldText,
		NewText: newContent,
	}, nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	return nil
}
