package model

import (
	"time"

	"github.com/google/uuid"
)

type Page struct {
	ID          uuid.UUID  `json:"id"`
	HubID       uuid.UUID  `json:"hub_id"`
	Title       string     `json:"title"`
	Slug        string     `json:"slug"`
	Content     string     `json:"content"`
	ContentHTML *string    `json:"content_html,omitempty"`
	CategoryID  *uuid.UUID `json:"category_id,omitempty"`
	AuthorID    uuid.UUID  `json:"author_id"`
	Status      string     `json:"status"`
	ViewCount   int        `json:"view_count"`
	IsVerified  bool       `json:"is_verified"`
	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`
	DeletedAt   *time.Time `json:"deleted_at,omitempty"`
}

type PageVersion struct {
	ID            uuid.UUID `json:"id"`
	PageID        uuid.UUID `json:"page_id"`
	Version       int       `json:"version"`
	Title         string    `json:"title"`
	Content       string    `json:"content"`
	ChangedBy     uuid.UUID `json:"changed_by"`
	ChangeSummary *string   `json:"change_summary,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
}

type Category struct {
	ID        uuid.UUID  `json:"id"`
	HubID     uuid.UUID  `json:"hub_id"`
	Name      string     `json:"name"`
	Slug      string     `json:"slug"`
	ParentID  *uuid.UUID `json:"parent_id,omitempty"`
	SortOrder int        `json:"sort_order"`
	CreatedAt time.Time  `json:"created_at"`
	UpdatedAt time.Time  `json:"updated_at"`
}

type Tag struct {
	ID        uuid.UUID `json:"id"`
	HubID     uuid.UUID `json:"hub_id"`
	Name      string    `json:"name"`
	CreatedAt time.Time `json:"created_at"`
}

// ─── Request DTOs ───

type CreatePageRequest struct {
	HubID      string   `json:"hub_id" binding:"required"`
	Title      string   `json:"title" binding:"required"`
	Content    string   `json:"content" binding:"required"`
	CategoryID *string  `json:"category_id"`
	Tags       []string `json:"tags"`
	Status     string   `json:"status"`
}

type UpdatePageRequest struct {
	Title         *string  `json:"title"`
	Content       *string  `json:"content"`
	CategoryID    *string  `json:"category_id"`
	Tags          []string `json:"tags"`
	Status        *string  `json:"status"`
	ChangeSummary *string  `json:"change_summary"`
}

type CreateCategoryRequest struct {
	HubID    string  `json:"hub_id" binding:"required"`
	Name     string  `json:"name" binding:"required"`
	ParentID *string `json:"parent_id"`
}

type UpdateCategoryRequest struct {
	Name     *string `json:"name"`
	ParentID *string `json:"parent_id"`
}
