package service

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/hash"
	jwtpkg "github.com/medinet/hub-all-backend/internal/pkg/jwt"
	"github.com/medinet/hub-all-backend/internal/repository"
)

type AuthService struct {
	userRepo   *repository.UserRepo
	tokenRepo  *repository.TokenRepo
	jwtManager *jwtpkg.Manager
	rdb        *redis.Client
}

func NewAuthService(
	userRepo *repository.UserRepo,
	tokenRepo *repository.TokenRepo,
	jwtManager *jwtpkg.Manager,
	rdb *redis.Client,
) *AuthService {
	return &AuthService{
		userRepo:   userRepo,
		tokenRepo:  tokenRepo,
		jwtManager: jwtManager,
		rdb:        rdb,
	}
}

func (s *AuthService) Login(ctx context.Context, req model.LoginRequest) (*model.LoginResponse, error) {
	user, err := s.userRepo.FindByEmail(ctx, req.Email)
	if err != nil {
		return nil, fmt.Errorf("find user: %w", err)
	}
	if user == nil {
		return nil, fmt.Errorf("invalid email or password")
	}

	// Check if account is disabled
	if user.Status == "disabled" {
		return nil, fmt.Errorf("account is disabled")
	}

	// Check if account is locked
	if user.LockedUntil != nil && user.LockedUntil.After(time.Now()) {
		return nil, fmt.Errorf("account is locked until %s", user.LockedUntil.Format(time.RFC3339))
	}

	// Verify password
	valid, err := hash.VerifyPassword(req.Password, user.PasswordHash)
	if err != nil || !valid {
		// Increment failed login count
		if incErr := s.userRepo.IncrementFailedLogin(ctx, user.ID); incErr != nil {
			slog.Error("increment failed login", "error", incErr, "user_id", user.ID)
		}
		return nil, fmt.Errorf("invalid email or password")
	}

	// Reset failed login count on successful login
	if err := s.userRepo.ResetFailedLogin(ctx, user.ID); err != nil {
		slog.Error("reset failed login", "error", err, "user_id", user.ID)
	}

	// Get user roles
	roles, err := s.userRepo.GetUserRoles(ctx, user.ID)
	if err != nil {
		return nil, fmt.Errorf("get user roles: %w", err)
	}

	// Determine role for JWT (use first role, or specific hub role if hub_id provided)
	role := "viewer"
	hubID := ""
	for _, r := range roles {
		if req.HubID != "" && r.HubID.String() == req.HubID {
			role = r.Role
			hubID = r.HubID.String()
			break
		}
		if r.Role == "admin" {
			role = r.Role
			hubID = r.HubID.String()
		}
	}
	if hubID == "" && len(roles) > 0 {
		role = roles[0].Role
		hubID = roles[0].HubID.String()
	}

	// Generate token pair
	tokenPair, err := s.jwtManager.GenerateTokenPair(
		user.ID.String(), user.Email, user.Name,
		hubID, role, "",
	)
	if err != nil {
		return nil, fmt.Errorf("generate tokens: %w", err)
	}

	slog.Info("user logged in", "user_id", user.ID, "email", user.Email, "role", role)

	return &model.LoginResponse{
		AccessToken:  tokenPair.AccessToken,
		RefreshToken: tokenPair.RefreshToken,
		ExpiresAt:    tokenPair.ExpiresAt,
		User: model.UserWithRoles{
			User:  *user,
			Roles: roles,
		},
	}, nil
}

func (s *AuthService) Logout(ctx context.Context, jtiStr, userIDStr string) error {
	jti, err := uuid.Parse(jtiStr)
	if err != nil {
		return fmt.Errorf("invalid JTI: %w", err)
	}

	userID, err := uuid.Parse(userIDStr)
	if err != nil {
		return fmt.Errorf("invalid user ID: %w", err)
	}

	expiresAt := time.Now().Add(s.jwtManager.AccessTokenTTL())

	// Store in DB
	if err := s.tokenRepo.RevokeToken(ctx, jti, userID, expiresAt); err != nil {
		return fmt.Errorf("revoke token in DB: %w", err)
	}

	// Cache in Redis for fast lookup
	if s.rdb != nil {
		s.rdb.Set(ctx, "revoked:"+jti.String(), "1", s.jwtManager.AccessTokenTTL())
	}

	slog.Info("user logged out", "user_id", userID, "jti", jti)
	return nil
}

func (s *AuthService) Refresh(ctx context.Context, refreshToken string) (*jwtpkg.TokenPair, error) {
	claims, err := s.jwtManager.VerifyToken(refreshToken)
	if err != nil {
		return nil, fmt.Errorf("invalid refresh token: %w", err)
	}

	if claims.TokenType != "refresh" {
		return nil, fmt.Errorf("invalid token type, refresh token required")
	}

	// Check if refresh token is revoked
	jti, err := uuid.Parse(claims.ID)
	if err != nil {
		return nil, fmt.Errorf("invalid token ID: %w", err)
	}

	revoked, err := s.tokenRepo.IsTokenRevoked(ctx, jti)
	if err != nil {
		return nil, fmt.Errorf("check revoked: %w", err)
	}
	if revoked {
		return nil, fmt.Errorf("refresh token has been revoked")
	}

	// Find user to get fresh data
	userID, err := uuid.Parse(claims.Subject)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID in token: %w", err)
	}

	user, err := s.userRepo.FindByID(ctx, userID)
	if err != nil || user == nil {
		return nil, fmt.Errorf("user not found")
	}

	if user.Status == "disabled" {
		return nil, fmt.Errorf("account is disabled")
	}

	// Get roles for new token
	roles, err := s.userRepo.GetUserRoles(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("get user roles: %w", err)
	}

	role := "viewer"
	hubID := ""
	if len(roles) > 0 {
		role = roles[0].Role
		hubID = roles[0].HubID.String()
	}

	// Generate new token pair
	tokenPair, err := s.jwtManager.GenerateTokenPair(
		user.ID.String(), user.Email, user.Name,
		hubID, role, "",
	)
	if err != nil {
		return nil, fmt.Errorf("generate new tokens: %w", err)
	}

	// Revoke old refresh token
	expiresAt := time.Now().Add(s.jwtManager.RefreshTokenTTL())
	_ = s.tokenRepo.RevokeToken(ctx, jti, userID, expiresAt)
	if s.rdb != nil {
		s.rdb.Set(ctx, "revoked:"+jti.String(), "1", s.jwtManager.RefreshTokenTTL())
	}

	return tokenPair, nil
}

func (s *AuthService) GetCurrentUser(ctx context.Context, userIDStr string) (*model.UserWithRoles, error) {
	userID, err := uuid.Parse(userIDStr)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID: %w", err)
	}

	user, err := s.userRepo.FindByID(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("find user: %w", err)
	}
	if user == nil {
		return nil, fmt.Errorf("user not found")
	}

	roles, err := s.userRepo.GetUserRoles(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("get user roles: %w", err)
	}

	return &model.UserWithRoles{
		User:  *user,
		Roles: roles,
	}, nil
}
