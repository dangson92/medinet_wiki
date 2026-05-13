package model

import (
	"time"

	"github.com/google/uuid"
)

type Document struct {
	ID           uuid.UUID  `json:"id"`
	Name         string     `json:"name"`
	FileType     string     `json:"file_type"`
	FileSize     int64      `json:"file_size"`
	FilePath     string     `json:"file_path"`
	HubID        uuid.UUID  `json:"hub_id"`
	Status       string     `json:"status"`
	Progress     int        `json:"progress"`
	ErrorMessage *string    `json:"error_message,omitempty"`
	ChunkCount   int        `json:"chunk_count"`
	UploadedBy   uuid.UUID  `json:"uploaded_by"`
	UploadedAt   time.Time  `json:"uploaded_at"`
	ProcessedAt  *time.Time `json:"processed_at,omitempty"`
	// CFG-06 M1 Phase 4 — extractor đã dùng cho ingestion cuối cùng.
	// Nullable: document cũ trước M1 hoặc đang chờ ingest sẽ là NULL.
	ExtractorUsed *string `json:"extractor_used,omitempty"`
}

// DocumentVersion = 1 snapshot của document tại 1 thời điểm.
// Retention "3 gốc + 2 gần nhất": v1/v2/v3 luôn pin (IsOriginal=true);
// ngoài ra giữ thêm 2 version có VersionNumber lớn nhất.
type DocumentVersion struct {
	ID            uuid.UUID  `json:"id"`
	DocumentID    uuid.UUID  `json:"document_id"`
	VersionNumber int        `json:"version_number"`
	IsOriginal    bool       `json:"is_original"`
	Name          string     `json:"name"`
	FileType      string     `json:"file_type"`
	FileSize      int64      `json:"file_size"`
	FilePath      string     `json:"file_path"`
	FileHash      *string    `json:"file_hash,omitempty"`
	ExtractorUsed *string    `json:"extractor_used,omitempty"`
	ChunkCount    int        `json:"chunk_count"`
	ChangeType    string     `json:"change_type"` // reupload | reextract | content_edit | restore
	ChangeNote    *string    `json:"change_note,omitempty"`
	CreatedBy     *uuid.UUID `json:"created_by,omitempty"`
	CreatedAt     time.Time  `json:"created_at"`
}

// DocumentVersionChunk = bản chụp text 1 chunk tại 1 version (KHÔNG embed).
type DocumentVersionChunk struct {
	ID         uuid.UUID              `json:"id"`
	VersionID  uuid.UUID              `json:"version_id"`
	ChunkIndex int                    `json:"chunk_index"`
	Content    string                 `json:"content"`
	TokenCount int                    `json:"token_count"`
	Metadata   map[string]interface{} `json:"metadata"`
}

type DocumentChunk struct {
	ID         uuid.UUID              `json:"id"`
	DocumentID uuid.UUID              `json:"document_id"`
	ChunkIndex int                    `json:"chunk_index"`
	Content    string                 `json:"content"`
	TokenCount int                    `json:"token_count"`
	ChromaID   *string                `json:"chroma_id,omitempty"`
	Metadata   map[string]interface{} `json:"metadata"`
	CreatedAt  time.Time              `json:"created_at"`
}
