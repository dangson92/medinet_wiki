package repository

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

type TokenRepo struct {
	pool *pgxpool.Pool
}

func NewTokenRepo(pool *pgxpool.Pool) *TokenRepo {
	return &TokenRepo{pool: pool}
}

// RevokeToken adds a token JTI to the blacklist.
func (r *TokenRepo) RevokeToken(ctx context.Context, jti, userID uuid.UUID, expiresAt time.Time) error {
	_, err := r.pool.Exec(ctx, `
		INSERT INTO revoked_tokens (jti, user_id, expires_at)
		VALUES ($1, $2, $3)
		ON CONFLICT (jti) DO NOTHING
	`, jti, userID, expiresAt)
	if err != nil {
		return fmt.Errorf("revoke token: %w", err)
	}
	return nil
}

// IsTokenRevoked checks if a token JTI has been revoked.
func (r *TokenRepo) IsTokenRevoked(ctx context.Context, jti uuid.UUID) (bool, error) {
	var exists bool
	err := r.pool.QueryRow(ctx, `
		SELECT EXISTS(SELECT 1 FROM revoked_tokens WHERE jti = $1)
	`, jti).Scan(&exists)
	if err != nil {
		return false, fmt.Errorf("check revoked token: %w", err)
	}
	return exists, nil
}

// CleanupExpired removes expired tokens from the blacklist.
func (r *TokenRepo) CleanupExpired(ctx context.Context) (int64, error) {
	result, err := r.pool.Exec(ctx, `
		DELETE FROM revoked_tokens WHERE expires_at < NOW()
	`)
	if err != nil {
		return 0, fmt.Errorf("cleanup expired tokens: %w", err)
	}
	return result.RowsAffected(), nil
}
