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

type UserService struct {
	userRepo *repository.UserRepo
	hubRepo  *repository.HubRepo
}

func NewUserService(userRepo *repository.UserRepo, hubRepo *repository.HubRepo) *UserService {
	return &UserService{userRepo: userRepo, hubRepo: hubRepo}
}

func (s *UserService) List(ctx context.Context, hubID, role, status, search string, page, perPage int) ([]model.UserWithRoles, int64, error) {
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
	users, total, err := s.userRepo.ListUsers(ctx, hubID, role, status, search, perPage, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("list users: %w", err)
	}

	// Fetch roles for each user
	var result []model.UserWithRoles
	for _, u := range users {
		roles, err := s.userRepo.GetUserRoles(ctx, u.ID)
		if err != nil {
			return nil, 0, fmt.Errorf("get roles for user %s: %w", u.ID, err)
		}
		if roles == nil {
			roles = []model.UserHubRole{}
		}
		result = append(result, model.UserWithRoles{User: u, Roles: roles})
	}

	return result, total, nil
}

func (s *UserService) GetByID(ctx context.Context, id string) (*model.UserWithRoles, error) {
	userID, err := uuid.Parse(id)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID")
	}

	user, err := s.userRepo.FindByID(ctx, userID)
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

func (s *UserService) Create(ctx context.Context, req model.CreateUserRequest) (*model.User, error) {
	// Validate email
	if err := validator.ValidateEmail(req.Email); err != nil {
		return nil, err
	}

	// Validate password
	if err := validator.ValidatePassword(req.Password); err != nil {
		return nil, err
	}

	// Check email uniqueness
	existing, err := s.userRepo.FindByEmail(ctx, req.Email)
	if err != nil {
		return nil, fmt.Errorf("check email: %w", err)
	}
	if existing != nil {
		return nil, fmt.Errorf("email already exists")
	}

	// Hash password
	passwordHash, err := hash.HashPassword(req.Password)
	if err != nil {
		return nil, fmt.Errorf("hash password: %w", err)
	}

	// Create user
	user, err := s.userRepo.CreateUser(ctx, req.Email, req.Name, passwordHash, req.Phone, req.Department)
	if err != nil {
		return nil, fmt.Errorf("create user: %w", err)
	}

	// Assign role if hub_id and role provided
	if req.HubID != "" && req.Role != "" {
		hubUUID, err := uuid.Parse(req.HubID)
		if err != nil {
			return nil, fmt.Errorf("invalid hub ID")
		}
		if err := s.userRepo.UpsertUserRole(ctx, user.ID, hubUUID, req.Role); err != nil {
			return nil, fmt.Errorf("assign role: %w", err)
		}
	}

	slog.Info("user created", "user_id", user.ID, "email", user.Email)
	return user, nil
}

func (s *UserService) Update(ctx context.Context, id string, req model.UpdateUserRequest) (*model.User, error) {
	userID, err := uuid.Parse(id)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID")
	}

	user, err := s.userRepo.UpdateUser(ctx, userID, req.Name, req.Phone, req.Department)
	if err != nil {
		return nil, fmt.Errorf("update user: %w", err)
	}
	if user == nil {
		return nil, fmt.Errorf("user not found")
	}

	slog.Info("user updated", "user_id", user.ID)
	return user, nil
}

func (s *UserService) ChangeRole(ctx context.Context, userID, hubID, role string) error {
	uid, err := uuid.Parse(userID)
	if err != nil {
		return fmt.Errorf("invalid user ID")
	}
	hid, err := uuid.Parse(hubID)
	if err != nil {
		return fmt.Errorf("invalid hub ID")
	}

	validRoles := map[string]bool{"admin": true, "editor": true, "viewer": true}
	if !validRoles[role] {
		return fmt.Errorf("role must be 'admin', 'editor', or 'viewer'")
	}

	if err := s.userRepo.UpsertUserRole(ctx, uid, hid, role); err != nil {
		return fmt.Errorf("change role: %w", err)
	}

	slog.Info("user role changed", "user_id", userID, "hub_id", hubID, "role", role)
	return nil
}

func (s *UserService) ChangeStatus(ctx context.Context, userID, status string) error {
	uid, err := uuid.Parse(userID)
	if err != nil {
		return fmt.Errorf("invalid user ID")
	}

	validStatuses := map[string]bool{"active": true, "inactive": true, "locked": true}
	if !validStatuses[status] {
		return fmt.Errorf("status must be 'active', 'inactive', or 'locked'")
	}

	if err := s.userRepo.UpdateStatus(ctx, uid, status); err != nil {
		return fmt.Errorf("change status: %w", err)
	}

	slog.Info("user status changed", "user_id", userID, "status", status)
	return nil
}
