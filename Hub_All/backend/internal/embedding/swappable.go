package embedding

import (
	"context"
	"fmt"
	"sync"
)

// SwappableEmbedder is a thread-safe wrapper around EmbeddingProvider that
// allows hot-swapping the active provider at runtime — e.g., when the admin
// changes the embedding provider in Settings without restarting the server.
//
// All downstream consumers (RAG pipeline, searcher, worker) hold a pointer to
// this struct via the EmbeddingProvider interface. When Swap / SwapByConfig is
// called, subsequent Embed() calls transparently use the new provider.
type SwappableEmbedder struct {
	mu       sync.RWMutex
	active   EmbeddingProvider
	recorder UsageRecorder
}

// NewSwappable wraps an initial EmbeddingProvider. Pass nil if no provider is
// available at startup (embedder will return an error until Swap is called).
func NewSwappable(initial EmbeddingProvider, recorder UsageRecorder) *SwappableEmbedder {
	return &SwappableEmbedder{active: initial, recorder: recorder}
}

// Swap atomically replaces the active provider.
func (s *SwappableEmbedder) Swap(p EmbeddingProvider) {
	s.mu.Lock()
	s.active = p
	s.mu.Unlock()
}

// SwapByConfig builds a fresh provider from (providerName, apiKey, model) and
// atomically installs it. Existing in-flight Embed() calls complete on the old
// provider; new calls after return use the new one.
//
//   - providerName: "gemini" | "openai"
//   - apiKey:       the raw key (may be empty — caller must validate)
//   - model:        model string; empty → each provider's default applies
func (s *SwappableEmbedder) SwapByConfig(providerName, apiKey, model string) {
	var p EmbeddingProvider
	switch providerName {
	case "gemini":
		gp := NewGemini(apiKey, model)
		if s.recorder != nil {
			gp.SetUsageRecorder(s.recorder)
		}
		p = gp
	default: // "openai" and anything else
		op := NewOpenAI(apiKey, model)
		if s.recorder != nil {
			op.SetUsageRecorder(s.recorder)
		}
		p = op
	}
	s.Swap(p)
}

// Provider returns the currently active provider for introspection (e.g., to
// log which one is live after a swap).
func (s *SwappableEmbedder) Provider() EmbeddingProvider {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.active
}

// ─── EmbeddingProvider implementation ───

func (s *SwappableEmbedder) Embed(ctx context.Context, texts []string) ([][]float32, error) {
	s.mu.RLock()
	p := s.active
	s.mu.RUnlock()
	if p == nil {
		return nil, fmt.Errorf("embedding provider not configured — set an API key in Settings")
	}
	return p.Embed(ctx, texts)
}

func (s *SwappableEmbedder) ModelName() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.active == nil {
		return ""
	}
	return s.active.ModelName()
}

func (s *SwappableEmbedder) Dimension() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.active == nil {
		return 0
	}
	return s.active.Dimension()
}
