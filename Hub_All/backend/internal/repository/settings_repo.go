package repository

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/medinet/hub-all-backend/internal/pkg/crypto"
)

type SettingsRepo struct {
	pool   *pgxpool.Pool
	aesKey string
}

func NewSettingsRepo(pool *pgxpool.Pool, aesKey string) *SettingsRepo {
	return &SettingsRepo{pool: pool, aesKey: aesKey}
}

// Get retrieves a setting value. Decrypts if is_secret=true.
func (r *SettingsRepo) Get(ctx context.Context, key string) (string, error) {
	var value string
	var isSecret bool
	err := r.pool.QueryRow(ctx, `SELECT value, is_secret FROM settings WHERE key = $1`, key).Scan(&value, &isSecret)
	if err == pgx.ErrNoRows {
		return "", nil
	}
	if err != nil {
		return "", fmt.Errorf("get setting %s: %w", key, err)
	}
	if isSecret && r.aesKey != "" {
		decrypted, err := crypto.Decrypt(value, r.aesKey)
		if err != nil {
			return "", fmt.Errorf("decrypt setting %s: %w", key, err)
		}
		return decrypted, nil
	}
	return value, nil
}

// Set stores a setting value. Encrypts if isSecret=true.
func (r *SettingsRepo) Set(ctx context.Context, key, value string, isSecret bool) error {
	storeValue := value
	if isSecret && r.aesKey != "" {
		encrypted, err := crypto.Encrypt(value, r.aesKey)
		if err != nil {
			return fmt.Errorf("encrypt setting %s: %w", key, err)
		}
		storeValue = encrypted
	}
	_, err := r.pool.Exec(ctx, `
		INSERT INTO settings (key, value, is_secret, updated_at)
		VALUES ($1, $2, $3, NOW())
		ON CONFLICT (key) DO UPDATE SET value = $2, is_secret = $3, updated_at = NOW()
	`, key, storeValue, isSecret)
	if err != nil {
		return fmt.Errorf("set setting %s: %w", key, err)
	}
	return nil
}

// Delete removes a setting row entirely (e.g., clearing a revoked API key).
func (r *SettingsRepo) Delete(ctx context.Context, key string) error {
	_, err := r.pool.Exec(ctx, `DELETE FROM settings WHERE key = $1`, key)
	if err != nil {
		return fmt.Errorf("delete setting %s: %w", key, err)
	}
	return nil
}

// GetAll retrieves all non-secret settings as a map.
func (r *SettingsRepo) GetAll(ctx context.Context) (map[string]string, error) {
	rows, err := r.pool.Query(ctx, `SELECT key, value, is_secret FROM settings`)
	if err != nil {
		return nil, fmt.Errorf("get all settings: %w", err)
	}
	defer rows.Close()

	result := make(map[string]string)
	for rows.Next() {
		var k, v string
		var isSecret bool
		if err := rows.Scan(&k, &v, &isSecret); err != nil {
			continue
		}
		if isSecret {
			result[k] = "****" // never return secrets in bulk
		} else {
			result[k] = v
		}
	}
	return result, nil
}
