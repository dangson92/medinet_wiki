package model

import (
	"time"

	"github.com/google/uuid"
)

type User struct {
	ID               uuid.UUID  `json:"id"`
	Email            string     `json:"email"`
	Name             string     `json:"name"`
	Phone            *string    `json:"phone,omitempty"`
	Department       *string    `json:"department,omitempty"`
	PasswordHash     string     `json:"-"` // never expose
	AvatarURL        *string    `json:"avatar_url,omitempty"`
	Status           string     `json:"status"`
	FailedLoginCount int        `json:"failed_login_count"`
	LockedUntil      *time.Time `json:"locked_until,omitempty"`
	CreatedAt        time.Time  `json:"created_at"`
	UpdatedAt        time.Time  `json:"updated_at"`
}

type UserHubRole struct {
	UserID uuid.UUID `json:"user_id"`
	HubID  uuid.UUID `json:"hub_id"`
	Role   string    `json:"role"`
}

type UserWithRoles struct {
	User  User          `json:"user"`
	Roles []UserHubRole `json:"roles"`
}

type LoginRequest struct {
	Email    string `json:"email" binding:"required"`
	Password string `json:"password" binding:"required"`
	HubID    string `json:"hub_id"`
}

type LoginResponse struct {
	AccessToken  string        `json:"access_token"`
	RefreshToken string        `json:"refresh_token"`
	ExpiresAt    int64         `json:"expires_at"`
	User         UserWithRoles `json:"user"`
}

type RefreshRequest struct {
	RefreshToken string `json:"refresh_token" binding:"required"`
}
