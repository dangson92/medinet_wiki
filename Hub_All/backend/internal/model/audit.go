package model

import (
	"time"

	"github.com/google/uuid"
)

type AuditLogEntry struct {
	ID         uuid.UUID  `json:"id"`
	Timestamp  time.Time  `json:"timestamp"`
	UserID     *uuid.UUID `json:"user_id,omitempty"`
	UserName   *string    `json:"user_name,omitempty"`
	IsAI       bool       `json:"is_ai"`
	Action     string     `json:"action"`
	Target     *string    `json:"target,omitempty"`
	HubID      *uuid.UUID `json:"hub_id,omitempty"`
	HubName    *string    `json:"hub_name,omitempty"`
	IPAddress  *string    `json:"ip_address,omitempty"`
	UserAgent  *string    `json:"user_agent,omitempty"`
	RequestID  *uuid.UUID `json:"request_id,omitempty"`
	DurationMs *int       `json:"duration_ms,omitempty"`
	Payload    []byte     `json:"payload,omitempty"`
}
