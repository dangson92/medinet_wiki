package service

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/google/uuid"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/validator"
	"github.com/medinet/hub-all-backend/internal/repository"
)

type HubService struct {
	hubRepo *repository.HubRepo
}

func NewHubService(hubRepo *repository.HubRepo) *HubService {
	return &HubService{hubRepo: hubRepo}
}

func (s *HubService) List(ctx context.Context) ([]model.Hub, error) {
	hubs, err := s.hubRepo.List(ctx)
	if err != nil {
		return nil, fmt.Errorf("list hubs: %w", err)
	}
	return hubs, nil
}

func (s *HubService) GetByID(ctx context.Context, idStr string) (*model.Hub, error) {
	id, err := uuid.Parse(idStr)
	if err != nil {
		return nil, fmt.Errorf("invalid hub ID")
	}

	hub, err := s.hubRepo.FindByID(ctx, id)
	if err != nil {
		return nil, fmt.Errorf("find hub: %w", err)
	}
	if hub == nil {
		return nil, fmt.Errorf("hub not found")
	}
	return hub, nil
}

func (s *HubService) Create(ctx context.Context, req model.CreateHubRequest) (*model.Hub, error) {
	// Validate
	if err := validator.ValidateRequired(req.Name, "name"); err != nil {
		return nil, err
	}
	if err := validator.ValidateHubCode(req.Code); err != nil {
		return nil, err
	}
	if err := validator.ValidateRequired(req.Subdomain, "subdomain"); err != nil {
		return nil, err
	}
	if err := validator.ValidateRequired(req.ChromaCollection, "chroma_collection"); err != nil {
		return nil, err
	}

	// Check code uniqueness
	existing, err := s.hubRepo.FindByCode(ctx, req.Code)
	if err != nil {
		return nil, fmt.Errorf("check hub code: %w", err)
	}
	if existing != nil {
		return nil, fmt.Errorf("hub code '%s' already exists", req.Code)
	}

	if req.DBPort == 0 {
		req.DBPort = 5432
	}

	hub, err := s.hubRepo.Create(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("create hub: %w", err)
	}

	slog.Info("hub created", "hub_id", hub.ID, "code", hub.Code)
	return hub, nil
}

func (s *HubService) Update(ctx context.Context, idStr string, req model.UpdateHubRequest) (*model.Hub, error) {
	id, err := uuid.Parse(idStr)
	if err != nil {
		return nil, fmt.Errorf("invalid hub ID")
	}

	hub, err := s.hubRepo.Update(ctx, id, req)
	if err != nil {
		return nil, fmt.Errorf("update hub: %w", err)
	}
	if hub == nil {
		return nil, fmt.Errorf("hub not found")
	}

	slog.Info("hub updated", "hub_id", hub.ID)
	return hub, nil
}

func (s *HubService) UpdateStatus(ctx context.Context, idStr string, req model.UpdateHubStatusRequest) error {
	id, err := uuid.Parse(idStr)
	if err != nil {
		return fmt.Errorf("invalid hub ID")
	}

	if req.Status != "active" && req.Status != "inactive" {
		return fmt.Errorf("status must be 'active' or 'inactive'")
	}

	if err := s.hubRepo.UpdateStatus(ctx, id, req.Status); err != nil {
		return fmt.Errorf("update hub status: %w", err)
	}

	slog.Info("hub status updated", "hub_id", id, "status", req.Status)
	return nil
}

func (s *HubService) TestConnection(ctx context.Context, idStr string) error {
	id, err := uuid.Parse(idStr)
	if err != nil {
		return fmt.Errorf("invalid hub ID")
	}

	hub, err := s.hubRepo.FindByID(ctx, id)
	if err != nil || hub == nil {
		return fmt.Errorf("hub not found")
	}

	if hub.DBHost == nil || hub.DBName == nil {
		return fmt.Errorf("hub database not configured")
	}

	// TODO: implement actual DB connection test with 5s timeout
	slog.Info("hub connection test", "hub_id", id, "status", "not_implemented")
	return nil
}
