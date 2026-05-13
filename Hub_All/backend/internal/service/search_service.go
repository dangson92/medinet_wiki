package service

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/rag"
	"github.com/medinet/hub-all-backend/internal/repository"
)

type SearchService struct {
	searcher *rag.Searcher
	answerer *rag.Answerer
	hubRepo  *repository.HubRepo
}

func NewSearchService(searcher *rag.Searcher, answerer *rag.Answerer, hubRepo *repository.HubRepo) *SearchService {
	return &SearchService{searcher: searcher, answerer: answerer, hubRepo: hubRepo}
}

// Answer generates an AI answer from search results.
func (s *SearchService) Answer(ctx context.Context, query string, hubIDs []string, topK int) (*rag.AnswerResponse, error) {
	if s.answerer == nil {
		return nil, fmt.Errorf("answer engine not available")
	}

	hubs, err := s.getTargetHubs(ctx, hubIDs)
	if err != nil {
		return nil, err
	}

	return s.answerer.Answer(ctx, rag.AnswerRequest{
		Query:  query,
		HubIDs: hubIDs,
		TopK:   topK,
	}, hubs)
}

func (s *SearchService) getTargetHubs(ctx context.Context, hubIDs []string) ([]model.Hub, error) {
	allHubs, err := s.hubRepo.List(ctx)
	if err != nil {
		return nil, fmt.Errorf("list hubs: %w", err)
	}
	requestedIDs := make(map[string]bool)
	for _, id := range hubIDs {
		requestedIDs[id] = true
	}
	var targets []model.Hub
	for _, h := range allHubs {
		if h.Status != "active" {
			continue
		}
		if len(requestedIDs) > 0 && !requestedIDs[h.ID.String()] {
			continue
		}
		targets = append(targets, h)
	}
	return targets, nil
}

// Search performs single-hub search within the specified hub.
func (s *SearchService) Search(ctx context.Context, req model.SearchRequest, hubID string) (*model.SearchResponse, error) {
	if s.searcher == nil {
		return nil, fmt.Errorf("search engine not available")
	}

	id, err := uuid.Parse(hubID)
	if err != nil {
		return nil, fmt.Errorf("invalid hub ID")
	}

	hub, err := s.hubRepo.FindByID(ctx, id)
	if err != nil || hub == nil {
		return nil, fmt.Errorf("hub not found")
	}

	return s.searcher.Search(ctx, req, *hub)
}

// CrossHubSearch performs fan-out search across multiple hubs.
func (s *SearchService) CrossHubSearch(ctx context.Context, req model.SearchRequest) (*model.SearchResponse, error) {
	if s.searcher == nil {
		return nil, fmt.Errorf("search engine not available")
	}

	allHubs, err := s.hubRepo.List(ctx)
	if err != nil {
		return nil, fmt.Errorf("list hubs: %w", err)
	}

	// Filter to active hubs, and optionally by requested hub IDs
	var targetHubs []model.Hub
	requestedIDs := make(map[string]bool)
	for _, id := range req.HubIDs {
		requestedIDs[id] = true
	}

	for _, h := range allHubs {
		if h.Status != "active" {
			continue
		}
		if len(requestedIDs) > 0 && !requestedIDs[h.ID.String()] {
			continue
		}
		targetHubs = append(targetHubs, h)
	}

	if len(targetHubs) == 0 {
		return &model.SearchResponse{Results: []model.SearchResult{}}, nil
	}

	return s.searcher.CrossHubSearch(ctx, req, targetHubs)
}

// FindSimilar finds content similar to the given text.
func (s *SearchService) FindSimilar(ctx context.Context, req model.SimilarRequest) (*model.SimilarResponse, error) {
	if s.searcher == nil {
		return nil, fmt.Errorf("search engine not available")
	}

	// If hub_id specified, search in that hub; otherwise search all
	if req.HubID != "" {
		id, err := uuid.Parse(req.HubID)
		if err != nil {
			return nil, fmt.Errorf("invalid hub ID")
		}
		hub, err := s.hubRepo.FindByID(ctx, id)
		if err != nil || hub == nil {
			return nil, fmt.Errorf("hub not found")
		}
		return s.searcher.FindSimilar(ctx, req, *hub)
	}

	// Search across all active hubs, merge matches
	allHubs, err := s.hubRepo.List(ctx)
	if err != nil {
		return nil, fmt.Errorf("list hubs: %w", err)
	}

	var allMatches []model.SimilarMatch
	for _, h := range allHubs {
		if h.Status != "active" {
			continue
		}
		resp, err := s.searcher.FindSimilar(ctx, req, h)
		if err != nil {
			continue
		}
		allMatches = append(allMatches, resp.Matches...)
	}

	return &model.SimilarResponse{Matches: allMatches}, nil
}
