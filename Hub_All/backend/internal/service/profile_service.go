package service

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/google/uuid"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/hash"
	"github.com/medinet/hub-all-backend/internal/pkg/validator"
	"github.com/medinet/hub-all-backend/internal/repository"
)

type ProfileService struct {
	userRepo *repository.UserRepo
}

func NewProfileService(userRepo *repository.UserRepo) *ProfileService {
	return &ProfileService{userRepo: userRepo}
}

func (s *ProfileService) GetProfile(ctx context.Context, userID string) (*model.UserWithRoles, error) {
	uid, err := uuid.Parse(userID)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID")
	}

	user, err := s.userRepo.FindByID(ctx, uid)
	if err != nil {
		return nil, fmt.Errorf("find user: %w", err)
	}
	if user == nil {
		return nil, fmt.Errorf("user not found")
	}

	roles, err := s.userRepo.GetUserRoles(ctx, user.ID)
	if err != nil {
		return nil, fmt.Errorf("get user roles: %w", err)
	}
	if roles == nil {
		roles = []model.UserHubRole{}
	}

	return &model.UserWithRoles{User: *user, Roles: roles}, nil
}

func (s *ProfileService) UpdateProfile(ctx context.Context, userID string, req model.UpdateProfileRequest) (*model.User, error) {
	uid, err := uuid.Parse(userID)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID")
	}

	user, err := s.userRepo.UpdateUser(ctx, uid, req.Name, req.Phone, req.Department)
	if err != nil {
		return nil, fmt.Errorf("update profile: %w", err)
	}
	if user == nil {
		return nil, fmt.Errorf("user not found")
	}

	slog.Info("profile updated", "user_id", uid)
	return user, nil
}

func (s *ProfileService) ChangePassword(ctx context.Context, userID, oldPassword, newPassword string) error {
	uid, err := uuid.Parse(userID)
	if err != nil {
		return fmt.Errorf("invalid user ID")
	}

	// Get current user
	user, err := s.userRepo.FindByID(ctx, uid)
	if err != nil {
		return fmt.Errorf("find user: %w", err)
	}
	if user == nil {
		return fmt.Errorf("user not found")
	}

	// Verify old password
	match, err := hash.VerifyPassword(oldPassword, user.PasswordHash)
	if err != nil {
		return fmt.Errorf("verify password: %w", err)
	}
	if !match {
		return fmt.Errorf("current password is incorrect")
	}

	// Validate new password
	if err := validator.ValidatePassword(newPassword); err != nil {
		return err
	}

	// Hash new password
	newHash, err := hash.HashPassword(newPassword)
	if err != nil {
		return fmt.Errorf("hash password: %w", err)
	}

	// Update password
	if err := s.userRepo.UpdatePassword(ctx, uid, newHash); err != nil {
		return fmt.Errorf("update password: %w", err)
	}

	slog.Info("password changed", "user_id", uid)
	return nil
}
