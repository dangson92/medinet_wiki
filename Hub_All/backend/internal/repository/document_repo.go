package repository

import (
	"context"
	"fmt"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/medinet/hub-all-backend/internal/model"
)

type DocumentRepo struct {
	pool *pgxpool.Pool
}

func NewDocumentRepo(pool *pgxpool.Pool) *DocumentRepo {
	return &DocumentRepo{pool: pool}
}

func (r *DocumentRepo) List(ctx context.Context, hubID, status, fileType string, limit, offset int) ([]model.Document, int64, error) {
	var conditions []string
	var args []interface{}
	argIdx := 1

	if hubID != "" {
		conditions = append(conditions, fmt.Sprintf("hub_id = $%d", argIdx))
		args = append(args, hubID)
		argIdx++
	}
	if status != "" {
		conditions = append(conditions, fmt.Sprintf("status = $%d", argIdx))
		args = append(args, status)
		argIdx++
	}
	if fileType != "" {
		conditions = append(conditions, fmt.Sprintf("file_type = $%d", argIdx))
		args = append(args, fileType)
		argIdx++
	}

	where := ""
	if len(conditions) > 0 {
		where = " WHERE " + strings.Join(conditions, " AND ")
	}

	// Count total
	countQuery := "SELECT COUNT(*) FROM documents" + where
	var total int64
	if err := r.pool.QueryRow(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count documents: %w", err)
	}

	// Fetch page
	query := fmt.Sprintf(`
		SELECT id, name, file_type, file_size, file_path, hub_id,
		       status, progress, error_message, chunk_count,
		       uploaded_by, uploaded_at, processed_at, extractor_used
		FROM documents%s
		ORDER BY uploaded_at DESC
		LIMIT $%d OFFSET $%d
	`, where, argIdx, argIdx+1)
	args = append(args, limit, offset)

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("list documents: %w", err)
	}
	defer rows.Close()

	var docs []model.Document
	for rows.Next() {
		var d model.Document
		if err := rows.Scan(
			&d.ID, &d.Name, &d.FileType, &d.FileSize, &d.FilePath, &d.HubID,
			&d.Status, &d.Progress, &d.ErrorMessage, &d.ChunkCount,
			&d.UploadedBy, &d.UploadedAt, &d.ProcessedAt, &d.ExtractorUsed,
		); err != nil {
			return nil, 0, fmt.Errorf("scan document: %w", err)
		}
		docs = append(docs, d)
	}

	return docs, total, nil
}

func (r *DocumentRepo) FindByID(ctx context.Context, id uuid.UUID) (*model.Document, error) {
	var d model.Document
	err := r.pool.QueryRow(ctx, `
		SELECT id, name, file_type, file_size, file_path, hub_id,
		       status, progress, error_message, chunk_count,
		       uploaded_by, uploaded_at, processed_at, extractor_used
		FROM documents WHERE id = $1
	`, id).Scan(
		&d.ID, &d.Name, &d.FileType, &d.FileSize, &d.FilePath, &d.HubID,
		&d.Status, &d.Progress, &d.ErrorMessage, &d.ChunkCount,
		&d.UploadedBy, &d.UploadedAt, &d.ProcessedAt, &d.ExtractorUsed,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("find document by id: %w", err)
	}
	return &d, nil
}

func (r *DocumentRepo) Create(ctx context.Context, doc *model.Document) error {
	_, err := r.pool.Exec(ctx, `
		INSERT INTO documents (id, name, file_type, file_size, file_path, hub_id,
		                       status, progress, chunk_count, uploaded_by, uploaded_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
	`, doc.ID, doc.Name, doc.FileType, doc.FileSize, doc.FilePath, doc.HubID,
		doc.Status, doc.Progress, doc.ChunkCount, doc.UploadedBy, doc.UploadedAt,
	)
	if err != nil {
		return fmt.Errorf("create document: %w", err)
	}
	return nil
}

func (r *DocumentRepo) UpdateStatus(ctx context.Context, id uuid.UUID, status string, errorMsg *string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE documents SET status = $2, error_message = $3 WHERE id = $1
	`, id, status, errorMsg)
	if err != nil {
		return fmt.Errorf("update document status: %w", err)
	}
	return nil
}

func (r *DocumentRepo) UpdateProgress(ctx context.Context, id uuid.UUID, progress int) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE documents SET progress = $2 WHERE id = $1
	`, id, progress)
	if err != nil {
		return fmt.Errorf("update document progress: %w", err)
	}
	return nil
}

func (r *DocumentRepo) UpdateCompleted(ctx context.Context, id uuid.UUID, chunkCount int) error {
	now := time.Now().UTC()
	_, err := r.pool.Exec(ctx, `
		UPDATE documents SET status = 'completed', progress = 100,
		       chunk_count = $2, processed_at = $3
		WHERE id = $1
	`, id, chunkCount, now)
	if err != nil {
		return fmt.Errorf("update document completed: %w", err)
	}
	return nil
}

// SetExtractorUsed ghi extractor_used cho document (CFG-06 M1 Phase 4).
// Worker gọi ngay trước UpdateCompleted khi pipeline hoàn tất ingestion.
// Validate enum {docling, native} ở client-side để tránh round-trip lỗi
// CHECK constraint của Postgres (trùng với migration 009).
func (r *DocumentRepo) SetExtractorUsed(ctx context.Context, id uuid.UUID, value string) error {
	if value != "docling" && value != "native" {
		return fmt.Errorf("invalid extractor_used value %q (must be docling|native)", value)
	}
	_, err := r.pool.Exec(ctx, `UPDATE documents SET extractor_used = $2 WHERE id = $1`, id, value)
	if err != nil {
		return fmt.Errorf("set extractor_used: %w", err)
	}
	return nil
}

// ClearExtractorUsed reset extractor_used về NULL khi reindex bắt đầu (CFG-07).
// Pipeline mới sẽ set lại giá trị đúng khi job complete.
func (r *DocumentRepo) ClearExtractorUsed(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `UPDATE documents SET extractor_used = NULL WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("clear extractor_used: %w", err)
	}
	return nil
}

// UpdateFileInfo cập nhật metadata file của document (dùng khi reupload /
// edit content). KHÔNG đụng tới status/progress/chunk_count — caller tự
// reset bằng UpdateStatus/UpdateProgress sau khi enqueue worker.
func (r *DocumentRepo) UpdateFileInfo(ctx context.Context, id uuid.UUID, name, fileType string, fileSize int64, filePath string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE documents
		SET name = $2, file_type = $3, file_size = $4, file_path = $5
		WHERE id = $1
	`, id, name, fileType, fileSize, filePath)
	if err != nil {
		return fmt.Errorf("update document file info: %w", err)
	}
	return nil
}

func (r *DocumentRepo) Delete(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `DELETE FROM documents WHERE id = $1`, id)
	if err != nil {
		return fmt.Errorf("delete document: %w", err)
	}
	return nil
}

func (r *DocumentRepo) BatchInsertChunks(ctx context.Context, chunks []model.DocumentChunk) error {
	if len(chunks) == 0 {
		return nil
	}

	batch := &pgx.Batch{}
	for _, ch := range chunks {
		// Safety net: PG cột content kiểu TEXT/UTF8 sẽ reject byte không hợp
		// lệ UTF-8 (vd 0xb4 — continuation byte do chunker cắt giữa rune
		// tiếng Việt). ToValidUTF8 thay byte rác bằng U+FFFD, không lossy
		// với chunk hợp lệ. Đặt ở boundary này để bao mọi nguồn rò rỉ.
		content := ch.Content
		if !utf8.ValidString(content) {
			content = strings.ToValidUTF8(content, "�")
		}
		batch.Queue(`
			INSERT INTO document_chunks (id, document_id, chunk_index, content, token_count, chroma_id, metadata, created_at)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		`, ch.ID, ch.DocumentID, ch.ChunkIndex, content, ch.TokenCount, ch.ChromaID, ch.Metadata, ch.CreatedAt)
	}

	br := r.pool.SendBatch(ctx, batch)
	defer br.Close()

	for range chunks {
		if _, err := br.Exec(); err != nil {
			return fmt.Errorf("batch insert chunk: %w", err)
		}
	}

	return nil
}

func (r *DocumentRepo) DeleteChunksByDocID(ctx context.Context, docID uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `DELETE FROM document_chunks WHERE document_id = $1`, docID)
	if err != nil {
		return fmt.Errorf("delete chunks by doc id: %w", err)
	}
	return nil
}

func (r *DocumentRepo) GetChunks(ctx context.Context, docID uuid.UUID) ([]model.DocumentChunk, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, document_id, chunk_index, content, token_count, chroma_id, metadata, created_at
		FROM document_chunks WHERE document_id = $1
		ORDER BY chunk_index
	`, docID)
	if err != nil {
		return nil, fmt.Errorf("get chunks: %w", err)
	}
	defer rows.Close()

	var chunks []model.DocumentChunk
	for rows.Next() {
		var ch model.DocumentChunk
		if err := rows.Scan(
			&ch.ID, &ch.DocumentID, &ch.ChunkIndex, &ch.Content,
			&ch.TokenCount, &ch.ChromaID, &ch.Metadata, &ch.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("scan chunk: %w", err)
		}
		chunks = append(chunks, ch)
	}

	return chunks, nil
}
