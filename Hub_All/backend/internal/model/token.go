package model

import (
	"time"

	"github.com/google/uuid"
)

type RevokedToken struct {
	JTI       uuid.UUID `json:"jti"`
	UserID    uuid.UUID `json:"user_id"`
	RevokedAt time.Time `json:"revoked_at"`
	ExpiresAt time.Time `json:"expires_at"`
}
