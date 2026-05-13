package service

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/google/uuid"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/repository"
)

type SyncService struct {
	syncRepo *repository.SyncRepo
	hubRepo  *repository.HubRepo
	userRepo *repository.UserRepo
}

func NewSyncService(
	syncRepo *repository.SyncRepo,
	hubRepo *repository.HubRepo,
	userRepo *repository.UserRepo,
) *SyncService {
	return &SyncService{
		syncRepo: syncRepo,
		hubRepo:  hubRepo,
		userRepo: userRepo,
	}
}

// ListBatches returns paginated sync batches with optional filters.
func (s *SyncService) ListBatches(ctx context.Context, hubID, status string, page, perPage int) ([]model.SyncBatch, int64, error) {
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
	batches, total, err := s.syncRepo.ListBatches(ctx, hubID, status, perPage, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("list sync batches: %w", err)
	}
	return batches, total, nil
}

// GetBatch returns a single sync batch with its pages.
func (s *SyncService) GetBatch(ctx context.Context, id string) (*model.SyncBatch, error) {
	batchUUID, err := uuid.Parse(id)
	if err != nil {
		return nil, fmt.Errorf("invalid batch ID")
	}

	batch, err := s.syncRepo.GetBatch(ctx, batchUUID)
	if err != nil {
		return nil, fmt.Errorf("get sync batch: %w", err)
	}
	if batch == nil {
		return nil, fmt.Errorf("batch not found")
	}
	return batch, nil
}

// SubmitBatch creates a new sync batch with its pages.
func (s *SyncService) SubmitBatch(ctx context.Context, req model.SubmitSyncRequest, submitterID string) (*model.SyncBatch, error) {
	// Validate hub
	hubUUID, err := uuid.Parse(req.HubID)
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

	// Validate submitter
	userUUID, err := uuid.Parse(submitterID)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID")
	}

	if len(req.Pages) == 0 {
		return nil, fmt.Errorf("at least one page is required")
	}

	// Build files summary and total size
	filesSummary := make(map[string]int)
	var totalSize int64
	for _, p := range req.Pages {
		filesSummary[p.FileType]++
		totalSize += p.FileSize
	}

	now := time.Now().UTC()
	batch := &model.SyncBatch{
		ID:            uuid.New(),
		HubID:         hubUUID,
		HubName:       hub.Name,
		PageCount:     len(req.Pages),
		FilesSummary:  filesSummary,
		TotalSize:     totalSize,
		SubmittedBy:   userUUID,
		Status:        "pending",
		ApprovedCount: 0,
		RejectedCount: 0,
		SubmittedAt:   now,
	}

	if err := s.syncRepo.CreateBatch(ctx, batch); err != nil {
		return nil, fmt.Errorf("create sync batch: %w", err)
	}

	// Create individual pages
	for _, p := range req.Pages {
		var category *string
		if p.Category != "" {
			category = &p.Category
		}
		var author *string
		if p.Author != "" {
			author = &p.Author
		}

		syncPage := &model.SyncPage{
			ID:        uuid.New(),
			BatchID:   batch.ID,
			Title:     p.Title,
			FileName:  p.FileName,
			FileType:  p.FileType,
			FileSize:  p.FileSize,
			Content:   p.Content,
			Category:  category,
			Tags:      p.Tags,
			Author:    author,
			Status:    "pending",
			CreatedAt: now,
		}
		if err := s.syncRepo.CreateSyncPage(ctx, syncPage); err != nil {
			return nil, fmt.Errorf("create sync page: %w", err)
		}
	}

	slog.Info("sync batch submitted", "batch_id", batch.ID, "hub", hub.Code, "pages", len(req.Pages))
	return batch, nil
}

// ApprovePage approves a sync page and checks if the batch is complete.
func (s *SyncService) ApprovePage(ctx context.Context, batchID, pageID, reviewerID string) error {
	batchUUID, err := uuid.Parse(batchID)
	if err != nil {
		return fmt.Errorf("invalid batch ID")
	}
	pageUUID, err := uuid.Parse(pageID)
	if err != nil {
		return fmt.Errorf("invalid page ID")
	}
	reviewerUUID, err := uuid.Parse(reviewerID)
	if err != nil {
		return fmt.Errorf("invalid reviewer ID")
	}

	// Verify page belongs to batch
	page, err := s.syncRepo.GetSyncPage(ctx, pageUUID)
	if err != nil {
		return fmt.Errorf("get sync page: %w", err)
	}
	if page == nil {
		return fmt.Errorf("sync page not found")
	}
	if page.BatchID != batchUUID {
		return fmt.Errorf("page does not belong to this batch")
	}

	if err := s.syncRepo.ApprovePage(ctx, pageUUID, reviewerUUID); err != nil {
		return fmt.Errorf("approve page: %w", err)
	}

	// Check if batch is complete
	complete, err := s.syncRepo.CheckBatchComplete(ctx, batchUUID)
	if err != nil {
		slog.Error("failed to check batch completion", "batch_id", batchID, "error", err)
		return nil // page was approved, don't fail on this
	}
	if complete {
		if err := s.syncRepo.CompleteBatch(ctx, batchUUID); err != nil {
			slog.Error("failed to complete batch", "batch_id", batchID, "error", err)
		} else {
			slog.Info("sync batch completed", "batch_id", batchID)
		}
	}

	slog.Info("sync page approved", "batch_id", batchID, "page_id", pageID)
	return nil
}

// RejectPage rejects a sync page with a reason and checks if the batch is complete.
func (s *SyncService) RejectPage(ctx context.Context, batchID, pageID, reviewerID, reason string) error {
	batchUUID, err := uuid.Parse(batchID)
	if err != nil {
		return fmt.Errorf("invalid batch ID")
	}
	pageUUID, err := uuid.Parse(pageID)
	if err != nil {
		return fmt.Errorf("invalid page ID")
	}
	reviewerUUID, err := uuid.Parse(reviewerID)
	if err != nil {
		return fmt.Errorf("invalid reviewer ID")
	}

	if len(reason) < 10 {
		return fmt.Errorf("rejection reason must be at least 10 characters")
	}

	// Verify page belongs to batch
	page, err := s.syncRepo.GetSyncPage(ctx, pageUUID)
	if err != nil {
		return fmt.Errorf("get sync page: %w", err)
	}
	if page == nil {
		return fmt.Errorf("sync page not found")
	}
	if page.BatchID != batchUUID {
		return fmt.Errorf("page does not belong to this batch")
	}

	if err := s.syncRepo.RejectPage(ctx, pageUUID, reviewerUUID, reason); err != nil {
		return fmt.Errorf("reject page: %w", err)
	}

	// Check if batch is complete
	complete, err := s.syncRepo.CheckBatchComplete(ctx, batchUUID)
	if err != nil {
		slog.Error("failed to check batch completion", "batch_id", batchID, "error", err)
		return nil
	}
	if complete {
		if err := s.syncRepo.CompleteBatch(ctx, batchUUID); err != nil {
			slog.Error("failed to complete batch", "batch_id", batchID, "error", err)
		} else {
			slog.Info("sync batch completed", "batch_id", batchID)
		}
	}

	slog.Info("sync page rejected", "batch_id", batchID, "page_id", pageID)
	return nil
}

// GetStats returns pending sync statistics.
func (s *SyncService) GetStats(ctx context.Context) (int, int, error) {
	pendingBatches, pendingPages, err := s.syncRepo.GetSyncStats(ctx)
	if err != nil {
		return 0, 0, fmt.Errorf("get sync stats: %w", err)
	}
	return pendingBatches, pendingPages, nil
}
