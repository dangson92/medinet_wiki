package model

import (
	"time"

	"github.com/google/uuid"
)

type SyncBatch struct {
	ID              uuid.UUID      `json:"id"`
	HubID           uuid.UUID      `json:"hub_id"`
	HubName         string         `json:"hub_name"`
	PageCount       int            `json:"page_count"`
	FilesSummary    map[string]int `json:"files_summary"`
	TotalSize       int64          `json:"total_size"`
	SubmittedBy     uuid.UUID      `json:"submitted_by"`
	SubmittedByName string         `json:"submitted_by_name"`
	Status          string         `json:"status"`
	ApprovedCount   int            `json:"approved_count"`
	RejectedCount   int            `json:"rejected_count"`
	SubmittedAt     time.Time      `json:"submitted_at"`
	CompletedAt     *time.Time     `json:"completed_at,omitempty"`
	Pages           []SyncPage     `json:"pages,omitempty"`
}

type SyncPage struct {
	ID               uuid.UUID  `json:"id"`
	BatchID          uuid.UUID  `json:"batch_id"`
	Title            string     `json:"title"`
	FileName         string     `json:"file_name"`
	FileType         string     `json:"file_type"`
	FileSize         int64      `json:"file_size"`
	Content          string     `json:"content"`
	Category         *string    `json:"category,omitempty"`
	Tags             []string   `json:"tags,omitempty"`
	Author           *string    `json:"author,omitempty"`
	Status           string     `json:"status"`
	RejectionReason  *string    `json:"rejection_reason,omitempty"`
	SimilarityScore  *float64   `json:"similarity_score,omitempty"`
	SimilarPageID    *uuid.UUID `json:"similar_page_id,omitempty"`
	SimilarPageTitle *string    `json:"similar_page_title,omitempty"`
	ReviewedBy       *uuid.UUID `json:"reviewed_by,omitempty"`
	ReviewedAt       *time.Time `json:"reviewed_at,omitempty"`
	CreatedAt        time.Time  `json:"created_at"`
}

// ─── Request DTOs ───

type SubmitSyncRequest struct {
	HubID string                `json:"hub_id" binding:"required"`
	Pages []SubmitSyncPageRequest `json:"pages" binding:"required"`
}

type SubmitSyncPageRequest struct {
	Title    string   `json:"title" binding:"required"`
	FileName string   `json:"file_name" binding:"required"`
	FileType string   `json:"file_type" binding:"required"`
	FileSize int64    `json:"file_size"`
	Content  string   `json:"content" binding:"required"`
	Category string   `json:"category"`
	Tags     []string `json:"tags"`
	Author   string   `json:"author"`
}

type RejectPageRequest struct {
	Reason string `json:"reason" binding:"required"`
}
