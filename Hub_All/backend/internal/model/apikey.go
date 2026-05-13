package model

import (
	"time"

	"github.com/google/uuid"
)

type APIKey struct {
	ID                uuid.UUID   `json:"id"`
	Name              string      `json:"name"`
	KeyHash           string      `json:"-"`
	KeyPrefix         string      `json:"key_prefix"`
	Permissions       []string    `json:"permissions"`
	AllowedHubIDs     []uuid.UUID `json:"allowed_hub_ids,omitempty"`
	AllowedRAGConfigs []string    `json:"allowed_rag_configs,omitempty"`
	RateLimit         int         `json:"rate_limit"`
	ExpiresAt         *time.Time  `json:"expires_at,omitempty"`
	Status            string      `json:"status"`
	RequestsToday     int         `json:"requests_today"`
	Requests7d        int         `json:"requests_7d"`
	BandwidthUsed     int64       `json:"bandwidth_used"`
	LastUsedAt        *time.Time  `json:"last_used_at,omitempty"`
	CreatedBy         uuid.UUID   `json:"created_by"`
	CreatedAt         time.Time   `json:"created_at"`
}

type CreateAPIKeyRequest struct {
	Name              string      `json:"name" binding:"required"`
	Permissions       []string    `json:"permissions"`
	AllowedHubIDs     []uuid.UUID `json:"allowed_hub_ids,omitempty"`
	AllowedRAGConfigs []string    `json:"allowed_rag_configs,omitempty"`
	RateLimit         int         `json:"rate_limit"`
	ExpiresAt         *time.Time  `json:"expires_at,omitempty"`
}

type UpdateAPIKeyRequest struct {
	Name              *string     `json:"name,omitempty"`
	Permissions       []string    `json:"permissions,omitempty"`
	AllowedHubIDs     []uuid.UUID `json:"allowed_hub_ids,omitempty"`
	AllowedRAGConfigs []string    `json:"allowed_rag_configs,omitempty"`
	RateLimit         *int        `json:"rate_limit,omitempty"`
	ExpiresAt         *time.Time  `json:"expires_at,omitempty"`
	Status            *string     `json:"status,omitempty"`
}

type APIKeyWithPlaintext struct {
	APIKey
	PlainKey string `json:"plain_key"`
}

type CreateUserRequest struct {
	Email      string `json:"email" binding:"required"`
	Name       string `json:"name" binding:"required"`
	Password   string `json:"password" binding:"required"`
	Phone      string `json:"phone,omitempty"`
	Department string `json:"department,omitempty"`
	HubID      string `json:"hub_id,omitempty"`
	Role       string `json:"role,omitempty"`
}

type UpdateUserRequest struct {
	Name       *string `json:"name,omitempty"`
	Phone      *string `json:"phone,omitempty"`
	Department *string `json:"department,omitempty"`
}

type ChangeRoleRequest struct {
	HubID string `json:"hub_id" binding:"required"`
	Role  string `json:"role" binding:"required"`
}

type ChangeStatusRequest struct {
	Status string `json:"status" binding:"required"`
}

type UpdateProfileRequest struct {
	Name       *string `json:"name,omitempty"`
	Phone      *string `json:"phone,omitempty"`
	Department *string `json:"department,omitempty"`
}

type ChangePasswordRequest struct {
	OldPassword string `json:"old_password" binding:"required"`
	NewPassword string `json:"new_password" binding:"required"`
}
