package repository

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/medinet/hub-all-backend/internal/model"
)

// DocumentVersionRepo quản lý lịch sử phiên bản tài liệu.
//
// Retention "3 gốc + 2 gần nhất" được Postgres tự thực hiện qua trigger
// trg_document_versions_prune (xem migration 010). Trigger ghi danh sách
// file_path đã prune vào TEMP TABLE document_version_pruned_files trong
// CÙNG SESSION/connection — repository đọc lại trong cùng tx để application
// dọn file binary trên đĩa.
type DocumentVersionRepo struct {
	pool *pgxpool.Pool
}

func NewDocumentVersionRepo(pool *pgxpool.Pool) *DocumentVersionRepo {
	return &DocumentVersionRepo{pool: pool}
}

// NextVersionNumber trả version_number kế tiếp cho document (>= 1).
func (r *DocumentVersionRepo) NextVersionNumber(ctx context.Context, docID uuid.UUID) (int, error) {
	var n int
	err := r.pool.QueryRow(ctx, `
		SELECT COALESCE(MAX(version_number), 0) + 1
		FROM document_versions WHERE document_id = $1
	`, docID).Scan(&n)
	if err != nil {
		return 0, fmt.Errorf("next version number: %w", err)
	}
	return n, nil
}

// CreateWithChunks insert version + chunks snapshot trong 1 tx, rồi đọc
// danh sách file đã prune (do trigger ghi vào TEMP TABLE) để caller dọn đĩa.
//
// LƯU Ý: Phải dùng cùng connection trong cả tx để TEMP TABLE còn nhìn thấy.
// pgx tự pin connection trong scope tx → an toàn.
func (r *DocumentVersionRepo) CreateWithChunks(
	ctx context.Context,
	v *model.DocumentVersion,
	chunks []model.DocumentVersionChunk,
) (prunedFiles []string, err error) {
	tx, err := r.pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer func() {
		if err != nil {
			_ = tx.Rollback(ctx)
		}
	}()

	// is_original auto-derive từ version_number ∈ {1,2,3}
	isOriginal := v.VersionNumber >= 1 && v.VersionNumber <= 3
	v.IsOriginal = isOriginal

	_, err = tx.Exec(ctx, `
		INSERT INTO document_versions
		    (id, document_id, version_number, is_original,
		     name, file_type, file_size, file_path, file_hash,
		     extractor_used, chunk_count, change_type, change_note,
		     created_by, created_at)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
	`, v.ID, v.DocumentID, v.VersionNumber, v.IsOriginal,
		v.Name, v.FileType, v.FileSize, v.FilePath, v.FileHash,
		v.ExtractorUsed, v.ChunkCount, v.ChangeType, v.ChangeNote,
		v.CreatedBy, v.CreatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("insert version: %w", err)
	}

	if len(chunks) > 0 {
		batch := &pgx.Batch{}
		for _, ch := range chunks {
			meta, mErr := json.Marshal(ch.Metadata)
			if mErr != nil {
				meta = []byte(`{}`)
			}
			batch.Queue(`
				INSERT INTO document_version_chunks
				    (id, version_id, chunk_index, content, token_count, metadata)
				VALUES ($1,$2,$3,$4,$5,$6)
			`, ch.ID, v.ID, ch.ChunkIndex, ch.Content, ch.TokenCount, meta)
		}
		br := tx.SendBatch(ctx, batch)
		for range chunks {
			if _, bErr := br.Exec(); bErr != nil {
				_ = br.Close()
				return nil, fmt.Errorf("insert version chunk: %w", bErr)
			}
		}
		if cErr := br.Close(); cErr != nil {
			return nil, fmt.Errorf("close batch: %w", cErr)
		}
	}

	// Đọc danh sách file đã prune do trigger ghi vào TEMP TABLE.
	// TEMP TABLE chỉ tồn tại nếu trigger đã fire → ignore lỗi "không tồn tại".
	rows, qErr := tx.Query(ctx, `
		SELECT file_path FROM document_version_pruned_files
		WHERE document_id = $1
	`, v.DocumentID)
	if qErr == nil {
		defer rows.Close()
		for rows.Next() {
			var p string
			if sErr := rows.Scan(&p); sErr == nil && p != "" {
				prunedFiles = append(prunedFiles, p)
			}
		}
		// Xoá row đã đọc để tránh đọc lại lần sau trong cùng session.
		_, _ = tx.Exec(ctx, `DELETE FROM document_version_pruned_files WHERE document_id = $1`, v.DocumentID)
	}

	if err = tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("commit tx: %w", err)
	}
	return prunedFiles, nil
}

// ListByDocument trả tất cả version của 1 document, sắp xếp version_number DESC.
// Tối đa 5 row do retention.
func (r *DocumentVersionRepo) ListByDocument(ctx context.Context, docID uuid.UUID) ([]model.DocumentVersion, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, document_id, version_number, is_original,
		       name, file_type, file_size, file_path, file_hash,
		       extractor_used, chunk_count, change_type, change_note,
		       created_by, created_at
		FROM document_versions
		WHERE document_id = $1
		ORDER BY version_number DESC
	`, docID)
	if err != nil {
		return nil, fmt.Errorf("list versions: %w", err)
	}
	defer rows.Close()

	var out []model.DocumentVersion
	for rows.Next() {
		var v model.DocumentVersion
		if err := rows.Scan(
			&v.ID, &v.DocumentID, &v.VersionNumber, &v.IsOriginal,
			&v.Name, &v.FileType, &v.FileSize, &v.FilePath, &v.FileHash,
			&v.ExtractorUsed, &v.ChunkCount, &v.ChangeType, &v.ChangeNote,
			&v.CreatedBy, &v.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("scan version: %w", err)
		}
		out = append(out, v)
	}
	return out, nil
}

// FindByID trả 1 version cụ thể.
func (r *DocumentVersionRepo) FindByID(ctx context.Context, id uuid.UUID) (*model.DocumentVersion, error) {
	var v model.DocumentVersion
	err := r.pool.QueryRow(ctx, `
		SELECT id, document_id, version_number, is_original,
		       name, file_type, file_size, file_path, file_hash,
		       extractor_used, chunk_count, change_type, change_note,
		       created_by, created_at
		FROM document_versions WHERE id = $1
	`, id).Scan(
		&v.ID, &v.DocumentID, &v.VersionNumber, &v.IsOriginal,
		&v.Name, &v.FileType, &v.FileSize, &v.FilePath, &v.FileHash,
		&v.ExtractorUsed, &v.ChunkCount, &v.ChangeType, &v.ChangeNote,
		&v.CreatedBy, &v.CreatedAt,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("find version: %w", err)
	}
	return &v, nil
}

// GetChunks trả chunks snapshot của 1 version, sort theo chunk_index ASC.
func (r *DocumentVersionRepo) GetChunks(ctx context.Context, versionID uuid.UUID) ([]model.DocumentVersionChunk, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, version_id, chunk_index, content, token_count, metadata
		FROM document_version_chunks
		WHERE version_id = $1
		ORDER BY chunk_index ASC
	`, versionID)
	if err != nil {
		return nil, fmt.Errorf("get version chunks: %w", err)
	}
	defer rows.Close()

	var out []model.DocumentVersionChunk
	for rows.Next() {
		var ch model.DocumentVersionChunk
		var meta []byte
		if err := rows.Scan(&ch.ID, &ch.VersionID, &ch.ChunkIndex, &ch.Content, &ch.TokenCount, &meta); err != nil {
			return nil, fmt.Errorf("scan version chunk: %w", err)
		}
		if len(meta) > 0 {
			_ = json.Unmarshal(meta, &ch.Metadata)
		}
		out = append(out, ch)
	}
	return out, nil
}
