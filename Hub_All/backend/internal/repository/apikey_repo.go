package repository

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/medinet/hub-all-backend/internal/model"
)

type APIKeyRepo struct {
	pool *pgxpool.Pool
}

func NewAPIKeyRepo(pool *pgxpool.Pool) *APIKeyRepo {
	return &APIKeyRepo{pool: pool}
}

func (r *APIKeyRepo) scanKey(row pgx.Row) (*model.APIKey, error) {
	var k model.APIKey
	err := row.Scan(
		&k.ID, &k.Name, &k.KeyHash, &k.KeyPrefix,
		&k.Permissions, &k.AllowedHubIDs, &k.AllowedRAGConfigs,
		&k.RateLimit, &k.ExpiresAt, &k.Status,
		&k.RequestsToday, &k.Requests7d, &k.BandwidthUsed,
		&k.LastUsedAt, &k.CreatedBy, &k.CreatedAt,
	)
	if err != nil {
		return nil, err
	}
	if k.Permissions == nil {
		k.Permissions = []string{}
	}
	if k.AllowedHubIDs == nil {
		k.AllowedHubIDs = []uuid.UUID{}
	}
	if k.AllowedRAGConfigs == nil {
		k.AllowedRAGConfigs = []string{}
	}
	return &k, nil
}

const apiKeyColumns = `id, name, key_hash, key_prefix,
	permissions, allowed_hub_ids, allowed_rag_configs,
	rate_limit, expires_at, status,
	requests_today, requests_7d, bandwidth_used,
	last_used_at, created_by, created_at`

func (r *APIKeyRepo) List(ctx context.Context, limit, offset int) ([]model.APIKey, int64, error) {
	var total int64
	if err := r.pool.QueryRow(ctx, `SELECT COUNT(*) FROM api_keys`).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count api keys: %w", err)
	}

	query := fmt.Sprintf(`SELECT %s FROM api_keys ORDER BY created_at DESC LIMIT $1 OFFSET $2`, apiKeyColumns)
	rows, err := r.pool.Query(ctx, query, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("list api keys: %w", err)
	}
	defer rows.Close()

	var keys []model.APIKey
	for rows.Next() {
		var k model.APIKey
		if err := rows.Scan(
			&k.ID, &k.Name, &k.KeyHash, &k.KeyPrefix,
			&k.Permissions, &k.AllowedHubIDs, &k.AllowedRAGConfigs,
			&k.RateLimit, &k.ExpiresAt, &k.Status,
			&k.RequestsToday, &k.Requests7d, &k.BandwidthUsed,
			&k.LastUsedAt, &k.CreatedBy, &k.CreatedAt,
		); err != nil {
			return nil, 0, fmt.Errorf("scan api key: %w", err)
		}
		if k.Permissions == nil {
			k.Permissions = []string{}
		}
		if k.AllowedHubIDs == nil {
			k.AllowedHubIDs = []uuid.UUID{}
		}
		if k.AllowedRAGConfigs == nil {
			k.AllowedRAGConfigs = []string{}
		}
		keys = append(keys, k)
	}

	return keys, total, nil
}

func (r *APIKeyRepo) FindByID(ctx context.Context, id uuid.UUID) (*model.APIKey, error) {
	query := fmt.Sprintf(`SELECT %s FROM api_keys WHERE id = $1`, apiKeyColumns)
	k, err := r.scanKey(r.pool.QueryRow(ctx, query, id))
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("find api key by id: %w", err)
	}
	return k, nil
}

func (r *APIKeyRepo) FindByHash(ctx context.Context, hash string) (*model.APIKey, error) {
	query := fmt.Sprintf(`SELECT %s FROM api_keys WHERE key_hash = $1 AND status = 'active'`, apiKeyColumns)
	k, err := r.scanKey(r.pool.QueryRow(ctx, query, hash))
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("find api key by hash: %w", err)
	}
	return k, nil
}

func (r *APIKeyRepo) Create(ctx context.Context, key *model.APIKey) error {
	_, err := r.pool.Exec(ctx, `
		INSERT INTO api_keys (id, name, key_hash, key_prefix, permissions,
		                      allowed_hub_ids, allowed_rag_configs, rate_limit,
		                      expires_at, status, requests_today, requests_7d,
		                      bandwidth_used, created_by, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
	`, key.ID, key.Name, key.KeyHash, key.KeyPrefix, key.Permissions,
		key.AllowedHubIDs, key.AllowedRAGConfigs, key.RateLimit,
		key.ExpiresAt, key.Status, key.RequestsToday, key.Requests7d,
		key.BandwidthUsed, key.CreatedBy, key.CreatedAt,
	)
	if err != nil {
		return fmt.Errorf("create api key: %w", err)
	}
	return nil
}

func (r *APIKeyRepo) Update(ctx context.Context, id uuid.UUID, req model.UpdateAPIKeyRequest) (*model.APIKey, error) {
	query := fmt.Sprintf(`
		UPDATE api_keys SET
			name              = COALESCE($2, name),
			permissions       = COALESCE($3, permissions),
			allowed_hub_ids   = COALESCE($4, allowed_hub_ids),
			allowed_rag_configs = COALESCE($5, allowed_rag_configs),
			rate_limit        = COALESCE($6, rate_limit),
			expires_at        = COALESCE($7, expires_at),
			status            = COALESCE($8, status)
		WHERE id = $1
		RETURNING %s
	`, apiKeyColumns)

	k, err := r.scanKey(r.pool.QueryRow(ctx, query,
		id, req.Name, req.Permissions, req.AllowedHubIDs,
		req.AllowedRAGConfigs, req.RateLimit, req.ExpiresAt, req.Status,
	))
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("update api key: %w", err)
	}
	return k, nil
}

func (r *APIKeyRepo) Revoke(ctx context.Context, id uuid.UUID) error {
	result, err := r.pool.Exec(ctx, `
		UPDATE api_keys SET status = 'revoked' WHERE id = $1
	`, id)
	if err != nil {
		return fmt.Errorf("revoke api key: %w", err)
	}
	if result.RowsAffected() == 0 {
		return fmt.Errorf("api key not found")
	}
	return nil
}

func (r *APIKeyRepo) IncrementUsage(ctx context.Context, id uuid.UUID, bytes int64) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE api_keys
		SET requests_today = requests_today + 1,
		    requests_7d    = requests_7d + 1,
		    bandwidth_used = bandwidth_used + $2,
		    last_used_at   = NOW()
		WHERE id = $1
	`, id, bytes)
	if err != nil {
		return fmt.Errorf("increment api key usage: %w", err)
	}
	return nil
}
