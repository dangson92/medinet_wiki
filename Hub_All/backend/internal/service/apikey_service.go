package service

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"log/slog"
	"time"

	"github.com/google/uuid"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/repository"
)

const base62Chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

type APIKeyService struct {
	apikeyRepo *repository.APIKeyRepo
}

func NewAPIKeyService(apikeyRepo *repository.APIKeyRepo) *APIKeyService {
	return &APIKeyService{apikeyRepo: apikeyRepo}
}

func (s *APIKeyService) List(ctx context.Context, page, perPage int) ([]model.APIKey, int64, error) {
	if page < 1 {
		page = 1
	}
	if perPage < 1 {
		perPage = 20
	}
	if perPage > 100 {
		perPage = 100
	}

	offset := (page - 1) * perPage
	keys, total, err := s.apikeyRepo.List(ctx, perPage, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("list api keys: %w", err)
	}
	return keys, total, nil
}

func (s *APIKeyService) GetByID(ctx context.Context, id string) (*model.APIKey, error) {
	uid, err := uuid.Parse(id)
	if err != nil {
		return nil, fmt.Errorf("invalid api key ID")
	}

	key, err := s.apikeyRepo.FindByID(ctx, uid)
	if err != nil {
		return nil, fmt.Errorf("find api key: %w", err)
	}
	if key == nil {
		return nil, fmt.Errorf("api key not found")
	}
	return key, nil
}

func (s *APIKeyService) Create(ctx context.Context, req model.CreateAPIKeyRequest, createdBy string) (*model.APIKeyWithPlaintext, error) {
	creatorID, err := uuid.Parse(createdBy)
	if err != nil {
		return nil, fmt.Errorf("invalid creator ID")
	}

	if req.Name == "" {
		return nil, fmt.Errorf("name is required")
	}

	// Generate random key: mk_ + 32 base62 chars
	plainKey, err := generateAPIKey()
	if err != nil {
		return nil, fmt.Errorf("generate api key: %w", err)
	}

	// SHA-256 hash for storage
	hashBytes := sha256.Sum256([]byte(plainKey))
	keyHash := hex.EncodeToString(hashBytes[:])

	// Prefix for display (first 8 chars after mk_)
	keyPrefix := plainKey[:11] // "mk_" + 8 chars

	if req.RateLimit <= 0 {
		req.RateLimit = 1000 // default
	}
	if req.Permissions == nil {
		req.Permissions = []string{}
	}
	if req.AllowedHubIDs == nil {
		req.AllowedHubIDs = []uuid.UUID{}
	}
	if req.AllowedRAGConfigs == nil {
		req.AllowedRAGConfigs = []string{}
	}

	now := time.Now().UTC()
	key := &model.APIKey{
		ID:                uuid.New(),
		Name:              req.Name,
		KeyHash:           keyHash,
		KeyPrefix:         keyPrefix,
		Permissions:       req.Permissions,
		AllowedHubIDs:     req.AllowedHubIDs,
		AllowedRAGConfigs: req.AllowedRAGConfigs,
		RateLimit:         req.RateLimit,
		ExpiresAt:         req.ExpiresAt,
		Status:            "active",
		RequestsToday:     0,
		Requests7d:        0,
		BandwidthUsed:     0,
		CreatedBy:         creatorID,
		CreatedAt:         now,
	}

	if err := s.apikeyRepo.Create(ctx, key); err != nil {
		return nil, fmt.Errorf("create api key: %w", err)
	}

	slog.Info("api key created", "key_id", key.ID, "name", key.Name)
	return &model.APIKeyWithPlaintext{
		APIKey:   *key,
		PlainKey: plainKey,
	}, nil
}

func (s *APIKeyService) Update(ctx context.Context, id string, req model.UpdateAPIKeyRequest) (*model.APIKey, error) {
	uid, err := uuid.Parse(id)
	if err != nil {
		return nil, fmt.Errorf("invalid api key ID")
	}

	key, err := s.apikeyRepo.Update(ctx, uid, req)
	if err != nil {
		return nil, fmt.Errorf("update api key: %w", err)
	}
	if key == nil {
		return nil, fmt.Errorf("api key not found")
	}

	slog.Info("api key updated", "key_id", uid)
	return key, nil
}

func (s *APIKeyService) Revoke(ctx context.Context, id string) error {
	uid, err := uuid.Parse(id)
	if err != nil {
		return fmt.Errorf("invalid api key ID")
	}

	if err := s.apikeyRepo.Revoke(ctx, uid); err != nil {
		return fmt.Errorf("revoke api key: %w", err)
	}

	slog.Info("api key revoked", "key_id", uid)
	return nil
}

// generateAPIKey creates a random API key in the format mk_ + 32 base62 characters.
func generateAPIKey() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}

	result := make([]byte, 32)
	for i := 0; i < 32; i++ {
		result[i] = base62Chars[int(b[i])%len(base62Chars)]
	}
	return "mk_" + string(result), nil
}
