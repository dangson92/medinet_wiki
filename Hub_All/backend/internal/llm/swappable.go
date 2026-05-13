package llm

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"sync"
)

// Mode controls which LLM provider(s) are active.
//
//   - ModeGemini  — only Gemini, even if OpenAI key is present.
//   - ModeOpenAI  — only OpenAI, even if Gemini key is present.
//   - ModeAuto    — Gemini first; falls back to OpenAI only when Gemini fails
//                   AND the OpenAI key is configured. If a key is not
//                   configured the provider is silently skipped (no error log).
type Mode string

const (
	ModeGemini Mode = "gemini"
	ModeOpenAI Mode = "openai"
	ModeAuto   Mode = "auto"
)

// SwappableLLM is a thread-safe LLM that can be hot-swapped at runtime by the
// admin via PUT /api/rag-config. All downstream consumers (ContextualEnricher,
// RAG Answerer, AI-chat endpoint) hold a pointer to this struct through the
// LLM interface and automatically use the new mode after Swap().
type SwappableLLM struct {
	mu     sync.RWMutex
	mode   Mode
	active LLM // the resolved LLM for the current mode

	gemini   *GeminiLLM
	openai   *OpenAILLM
	recorder UsageRecorder
}

// NewSwappableLLM builds a SwappableLLM with the two underlying providers and
// activates the given mode. Pass ModeAuto for resilient fallback behaviour.
func NewSwappableLLM(gemini *GeminiLLM, openai *OpenAILLM, mode Mode, recorder UsageRecorder) *SwappableLLM {
	s := &SwappableLLM{
		gemini:   gemini,
		openai:   openai,
		recorder: recorder,
	}
	s.applyMode(mode) // sets s.mode + s.active (no lock needed at init)
	return s
}

// SwapByMode atomically switches the active LLM strategy.
//
//   - "gemini"  → only Gemini (errors propagate directly, no OpenAI fallback)
//   - "openai"  → only OpenAI
//   - "auto"    → smart fallback: skip providers whose key is empty
func (s *SwappableLLM) SwapByMode(mode Mode) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.applyMode(mode)
	slog.Info("LLM mode hot-swapped", "mode", string(mode), "active", s.active.Name())
}

// Mode returns the currently active mode (useful for logging / health checks).
func (s *SwappableLLM) Mode() Mode {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.mode
}

// ─── LLM interface ───────────────────────────────────────────────────────────

func (s *SwappableLLM) Generate(ctx context.Context, prompt string) (string, error) {
	s.mu.RLock()
	active := s.active
	s.mu.RUnlock()
	if active == nil {
		return "", fmt.Errorf("LLM not configured — set an API key in Settings")
	}
	return active.Generate(ctx, prompt)
}

func (s *SwappableLLM) Name() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if s.active == nil {
		return "none"
	}
	return s.active.Name()
}

// ─── internal ────────────────────────────────────────────────────────────────

// applyMode resolves the active LLM for the given mode.
// Caller must hold s.mu.Lock() (or call at init before the struct is shared).
func (s *SwappableLLM) applyMode(mode Mode) {
	s.mode = mode
	switch mode {
	case ModeGemini:
		// Single provider — errors go directly to caller, no silent fallback.
		s.active = s.gemini

	case ModeOpenAI:
		s.active = s.openai

	default: // ModeAuto
		// Build a smart fallback that skips providers whose key is absent.
		// This prevents "I only have a Gemini key but OpenAI is called" bugs.
		geminiOK := os.Getenv("GEMINI_API_KEY") != ""
		openaiOK := os.Getenv("OPENAI_API_KEY") != ""

		switch {
		case geminiOK && openaiOK:
			// Both available → true fallback: Gemini first, OpenAI on error.
			s.active = &FallbackLLM{Primary: s.gemini, Secondary: s.openai}
		case geminiOK:
			s.active = s.gemini
		case openaiOK:
			s.active = s.openai
		default:
			s.active = nil // no key at all
		}
	}
}

// RefreshAutoMode re-evaluates key availability (useful after a new API key is
// saved) when mode is already ModeAuto. No-op for other modes.
func (s *SwappableLLM) RefreshAutoMode() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.mode == ModeAuto {
		s.applyMode(ModeAuto)
	}
}
