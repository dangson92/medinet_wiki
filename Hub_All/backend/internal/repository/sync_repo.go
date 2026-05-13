package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/medinet/hub-all-backend/internal/model"
)

type SyncRepo struct {
	pool *pgxpool.Pool
}

func NewSyncRepo(pool *pgxpool.Pool) *SyncRepo {
	return &SyncRepo{pool: pool}
}

func (r *SyncRepo) ListBatches(ctx context.Context, hubID, status string, limit, offset int) ([]model.SyncBatch, int64, error) {
	var conditions []string
	var args []interface{}
	argIdx := 1

	if hubID != "" {
		conditions = append(conditions, fmt.Sprintf("sb.hub_id = $%d", argIdx))
		args = append(args, hubID)
		argIdx++
	}
	if status != "" {
		conditions = append(conditions, fmt.Sprintf("sb.status = $%d", argIdx))
		args = append(args, status)
		argIdx++
	}

	where := ""
	if len(conditions) > 0 {
		where = " WHERE " + strings.Join(conditions, " AND ")
	}

	// Count total
	countQuery := "SELECT COUNT(*) FROM sync_batches sb" + where
	var total int64
	if err := r.pool.QueryRow(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count sync batches: %w", err)
	}

	// Fetch page
	query := fmt.Sprintf(`
		SELECT sb.id, sb.hub_id, COALESCE(h.name, ''), sb.page_count,
		       sb.files_summary, sb.total_size, sb.submitted_by,
		       COALESCE(u.name, ''), sb.status, sb.approved_count,
		       sb.rejected_count, sb.submitted_at, sb.completed_at
		FROM sync_batches sb
		LEFT JOIN hubs h ON h.id = sb.hub_id
		LEFT JOIN users u ON u.id = sb.submitted_by
		%s
		ORDER BY sb.submitted_at DESC
		LIMIT $%d OFFSET $%d
	`, where, argIdx, argIdx+1)
	args = append(args, limit, offset)

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("list sync batches: %w", err)
	}
	defer rows.Close()

	var batches []model.SyncBatch
	for rows.Next() {
		var b model.SyncBatch
		var filesSummaryJSON []byte
		if err := rows.Scan(
			&b.ID, &b.HubID, &b.HubName, &b.PageCount,
			&filesSummaryJSON, &b.TotalSize, &b.SubmittedBy,
			&b.SubmittedByName, &b.Status, &b.ApprovedCount,
			&b.RejectedCount, &b.SubmittedAt, &b.CompletedAt,
		); err != nil {
			return nil, 0, fmt.Errorf("scan sync batch: %w", err)
		}
		if filesSummaryJSON != nil {
			if err := json.Unmarshal(filesSummaryJSON, &b.FilesSummary); err != nil {
				return nil, 0, fmt.Errorf("unmarshal files_summary: %w", err)
			}
		}
		if b.FilesSummary == nil {
			b.FilesSummary = make(map[string]int)
		}
		batches = append(batches, b)
	}

	return batches, total, nil
}

func (r *SyncRepo) GetBatch(ctx context.Context, id uuid.UUID) (*model.SyncBatch, error) {
	var b model.SyncBatch
	var filesSummaryJSON []byte
	err := r.pool.QueryRow(ctx, `
		SELECT sb.id, sb.hub_id, COALESCE(h.name, ''), sb.page_count,
		       sb.files_summary, sb.total_size, sb.submitted_by,
		       COALESCE(u.name, ''), sb.status, sb.approved_count,
		       sb.rejected_count, sb.submitted_at, sb.completed_at
		FROM sync_batches sb
		LEFT JOIN hubs h ON h.id = sb.hub_id
		LEFT JOIN users u ON u.id = sb.submitted_by
		WHERE sb.id = $1
	`, id).Scan(
		&b.ID, &b.HubID, &b.HubName, &b.PageCount,
		&filesSummaryJSON, &b.TotalSize, &b.SubmittedBy,
		&b.SubmittedByName, &b.Status, &b.ApprovedCount,
		&b.RejectedCount, &b.SubmittedAt, &b.CompletedAt,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("get sync batch: %w", err)
	}
	if filesSummaryJSON != nil {
		if err := json.Unmarshal(filesSummaryJSON, &b.FilesSummary); err != nil {
			return nil, fmt.Errorf("unmarshal files_summary: %w", err)
		}
	}
	if b.FilesSummary == nil {
		b.FilesSummary = make(map[string]int)
	}

	// Load pages
	pages, err := r.listPagesByBatch(ctx, id)
	if err != nil {
		return nil, err
	}
	b.Pages = pages

	return &b, nil
}

func (r *SyncRepo) listPagesByBatch(ctx context.Context, batchID uuid.UUID) ([]model.SyncPage, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, batch_id, title, file_name, file_type, file_size,
		       content, category, tags, author, status,
		       rejection_reason, similarity_score, similar_page_id,
		       similar_page_title, reviewed_by, reviewed_at, created_at
		FROM sync_pages
		WHERE batch_id = $1
		ORDER BY created_at
	`, batchID)
	if err != nil {
		return nil, fmt.Errorf("list sync pages: %w", err)
	}
	defer rows.Close()

	var pages []model.SyncPage
	for rows.Next() {
		var p model.SyncPage
		if err := rows.Scan(
			&p.ID, &p.BatchID, &p.Title, &p.FileName, &p.FileType, &p.FileSize,
			&p.Content, &p.Category, &p.Tags, &p.Author, &p.Status,
			&p.RejectionReason, &p.SimilarityScore, &p.SimilarPageID,
			&p.SimilarPageTitle, &p.ReviewedBy, &p.ReviewedAt, &p.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("scan sync page: %w", err)
		}
		if p.Tags == nil {
			p.Tags = []string{}
		}
		pages = append(pages, p)
	}

	return pages, nil
}

func (r *SyncRepo) CreateBatch(ctx context.Context, batch *model.SyncBatch) error {
	filesSummaryJSON, err := json.Marshal(batch.FilesSummary)
	if err != nil {
		return fmt.Errorf("marshal files_summary: %w", err)
	}

	err = r.pool.QueryRow(ctx, `
		INSERT INTO sync_batches (id, hub_id, page_count, files_summary, total_size,
		                          submitted_by, status, approved_count, rejected_count, submitted_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING submitted_at
	`, batch.ID, batch.HubID, batch.PageCount, filesSummaryJSON, batch.TotalSize,
		batch.SubmittedBy, batch.Status, batch.ApprovedCount, batch.RejectedCount, batch.SubmittedAt,
	).Scan(&batch.SubmittedAt)
	if err != nil {
		return fmt.Errorf("create sync batch: %w", err)
	}
	return nil
}

func (r *SyncRepo) CreateSyncPage(ctx context.Context, page *model.SyncPage) error {
	if page.Tags == nil {
		page.Tags = []string{}
	}
	_, err := r.pool.Exec(ctx, `
		INSERT INTO sync_pages (id, batch_id, title, file_name, file_type, file_size,
		                        content, category, tags, author, status, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`, page.ID, page.BatchID, page.Title, page.FileName, page.FileType, page.FileSize,
		page.Content, page.Category, page.Tags, page.Author, page.Status, page.CreatedAt,
	)
	if err != nil {
		return fmt.Errorf("create sync page: %w", err)
	}
	return nil
}

func (r *SyncRepo) GetSyncPage(ctx context.Context, id uuid.UUID) (*model.SyncPage, error) {
	var p model.SyncPage
	err := r.pool.QueryRow(ctx, `
		SELECT id, batch_id, title, file_name, file_type, file_size,
		       content, category, tags, author, status,
		       rejection_reason, similarity_score, similar_page_id,
		       similar_page_title, reviewed_by, reviewed_at, created_at
		FROM sync_pages WHERE id = $1
	`, id).Scan(
		&p.ID, &p.BatchID, &p.Title, &p.FileName, &p.FileType, &p.FileSize,
		&p.Content, &p.Category, &p.Tags, &p.Author, &p.Status,
		&p.RejectionReason, &p.SimilarityScore, &p.SimilarPageID,
		&p.SimilarPageTitle, &p.ReviewedBy, &p.ReviewedAt, &p.CreatedAt,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("get sync page: %w", err)
	}
	if p.Tags == nil {
		p.Tags = []string{}
	}
	return &p, nil
}

func (r *SyncRepo) ApprovePage(ctx context.Context, pageID, reviewerID uuid.UUID) error {
	now := time.Now().UTC()

	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx)

	// Update the page
	result, err := tx.Exec(ctx, `
		UPDATE sync_pages
		SET status = 'approved', reviewed_by = $2, reviewed_at = $3
		WHERE id = $1 AND status = 'pending'
	`, pageID, reviewerID, now)
	if err != nil {
		return fmt.Errorf("approve sync page: %w", err)
	}
	if result.RowsAffected() == 0 {
		return fmt.Errorf("sync page not found or already reviewed")
	}

	// Get batch_id for this page
	var batchID uuid.UUID
	if err := tx.QueryRow(ctx, `SELECT batch_id FROM sync_pages WHERE id = $1`, pageID).Scan(&batchID); err != nil {
		return fmt.Errorf("get batch id: %w", err)
	}

	// Increment approved count on batch
	_, err = tx.Exec(ctx, `
		UPDATE sync_batches SET approved_count = approved_count + 1 WHERE id = $1
	`, batchID)
	if err != nil {
		return fmt.Errorf("increment approved count: %w", err)
	}

	return tx.Commit(ctx)
}

func (r *SyncRepo) RejectPage(ctx context.Context, pageID, reviewerID uuid.UUID, reason string) error {
	now := time.Now().UTC()

	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx)

	// Update the page
	result, err := tx.Exec(ctx, `
		UPDATE sync_pages
		SET status = 'rejected', rejection_reason = $2, reviewed_by = $3, reviewed_at = $4
		WHERE id = $1 AND status = 'pending'
	`, pageID, reason, reviewerID, now)
	if err != nil {
		return fmt.Errorf("reject sync page: %w", err)
	}
	if result.RowsAffected() == 0 {
		return fmt.Errorf("sync page not found or already reviewed")
	}

	// Get batch_id for this page
	var batchID uuid.UUID
	if err := tx.QueryRow(ctx, `SELECT batch_id FROM sync_pages WHERE id = $1`, pageID).Scan(&batchID); err != nil {
		return fmt.Errorf("get batch id: %w", err)
	}

	// Increment rejected count on batch
	_, err = tx.Exec(ctx, `
		UPDATE sync_batches SET rejected_count = rejected_count + 1 WHERE id = $1
	`, batchID)
	if err != nil {
		return fmt.Errorf("increment rejected count: %w", err)
	}

	return tx.Commit(ctx)
}

func (r *SyncRepo) CheckBatchComplete(ctx context.Context, batchID uuid.UUID) (bool, error) {
	var pendingCount int
	err := r.pool.QueryRow(ctx, `
		SELECT COUNT(*) FROM sync_pages WHERE batch_id = $1 AND status = 'pending'
	`, batchID).Scan(&pendingCount)
	if err != nil {
		return false, fmt.Errorf("check batch complete: %w", err)
	}
	return pendingCount == 0, nil
}

func (r *SyncRepo) CompleteBatch(ctx context.Context, batchID uuid.UUID) error {
	now := time.Now().UTC()
	result, err := r.pool.Exec(ctx, `
		UPDATE sync_batches SET status = 'completed', completed_at = $2 WHERE id = $1
	`, batchID, now)
	if err != nil {
		return fmt.Errorf("complete batch: %w", err)
	}
	if result.RowsAffected() == 0 {
		return fmt.Errorf("batch not found")
	}
	return nil
}

func (r *SyncRepo) GetSyncStats(ctx context.Context) (int, int, error) {
	var pendingBatches, pendingPages int

	err := r.pool.QueryRow(ctx, `
		SELECT COUNT(*) FROM sync_batches WHERE status = 'pending'
	`).Scan(&pendingBatches)
	if err != nil {
		return 0, 0, fmt.Errorf("count pending batches: %w", err)
	}

	err = r.pool.QueryRow(ctx, `
		SELECT COUNT(*) FROM sync_pages WHERE status = 'pending'
	`).Scan(&pendingPages)
	if err != nil {
		return 0, 0, fmt.Errorf("count pending pages: %w", err)
	}

	return pendingBatches, pendingPages, nil
}
