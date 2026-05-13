package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// DefaultGeminiModel is the model used when none is configured.
// gemini-2.0-flash was deprecated for new API keys; gemini-2.0-flash-lite
// is the recommended lightweight replacement.
const DefaultGeminiModel = "gemini-2.0-flash-lite"

// GeminiModelEnvKey is the env var that overrides the model at runtime,
// allowing Settings UI → PUT /api/rag-config to change the model without restart.
const GeminiModelEnvKey = "GEMINI_LLM_MODEL"

type GeminiLLM struct {
	envKey      string // env var name for API key (supports runtime update)
	defaultModel string // fallback if GEMINI_LLM_MODEL env var is not set
	client      *http.Client
	recorder    UsageRecorder
}

func NewGemini(apiKey, model string) *GeminiLLM {
	if model == "" {
		model = DefaultGeminiModel
	}
	// Store key + model in env so both can be updated at runtime without restart.
	if apiKey != "" {
		os.Setenv("GEMINI_API_KEY", apiKey)
	}
	// Only set the model env var when explicitly provided (don't overwrite a
	// previously saved value with the code-level default on server restart).
	if model != DefaultGeminiModel {
		os.Setenv(GeminiModelEnvKey, model)
	} else if os.Getenv(GeminiModelEnvKey) == "" {
		os.Setenv(GeminiModelEnvKey, model)
	}
	return &GeminiLLM{
		envKey:       "GEMINI_API_KEY",
		defaultModel: model,
		client:       &http.Client{Timeout: 30 * time.Second},
	}
}

// SetUsageRecorder attaches an async usage recorder. Safe to leave nil —
// when unset, no usage events are emitted (the LLM still works).
func (g *GeminiLLM) SetUsageRecorder(r UsageRecorder) { g.recorder = r }

func (g *GeminiLLM) getKey() string { return os.Getenv(g.envKey) }

// getModel reads the active model from env so Settings UI changes take effect
// without a server restart.
func (g *GeminiLLM) getModel() string {
	if m := os.Getenv(GeminiModelEnvKey); m != "" {
		return m
	}
	return g.defaultModel
}

func (g *GeminiLLM) Name() string { return "gemini/" + g.getModel() }

func (g *GeminiLLM) Generate(ctx context.Context, prompt string) (string, error) {
	start := time.Now()
	key := g.getKey()
	if key == "" {
		g.report(ctx, 0, 0, 0, time.Since(start), fmt.Errorf("api key not configured"))
		return "", fmt.Errorf("gemini: API key not configured")
	}
	url := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent", g.getModel())

	body := map[string]interface{}{
		"contents": []map[string]interface{}{
			{
				"parts": []map[string]interface{}{
					{"text": prompt},
				},
			},
		},
		"generationConfig": map[string]interface{}{
			"temperature":     0.3,
			"maxOutputTokens": 2048,
		},
	}

	jsonBody, _ := json.Marshal(body)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(jsonBody))
	if err != nil {
		g.report(ctx, 0, 0, 0, time.Since(start), err)
		return "", fmt.Errorf("gemini: create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-goog-api-key", key)

	resp, err := g.client.Do(req)
	if err != nil {
		g.report(ctx, 0, 0, 0, time.Since(start), err)
		return "", fmt.Errorf("gemini: send request: %w", err)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		err := fmt.Errorf("gemini: API error %d: %s", resp.StatusCode, string(respBody))
		g.report(ctx, 0, 0, 0, time.Since(start), err)
		return "", err
	}

	var result struct {
		Candidates []struct {
			Content struct {
				Parts []struct {
					Text string `json:"text"`
				} `json:"parts"`
			} `json:"content"`
		} `json:"candidates"`
		UsageMetadata struct {
			PromptTokenCount     int `json:"promptTokenCount"`
			CandidatesTokenCount int `json:"candidatesTokenCount"`
			TotalTokenCount      int `json:"totalTokenCount"`
		} `json:"usageMetadata"`
	}
	if err := json.Unmarshal(respBody, &result); err != nil {
		g.report(ctx, 0, 0, 0, time.Since(start), err)
		return "", fmt.Errorf("gemini: unmarshal: %w", err)
	}

	if len(result.Candidates) == 0 || len(result.Candidates[0].Content.Parts) == 0 {
		err := fmt.Errorf("gemini: empty response")
		g.report(ctx, result.UsageMetadata.PromptTokenCount, result.UsageMetadata.CandidatesTokenCount, result.UsageMetadata.TotalTokenCount, time.Since(start), err)
		return "", err
	}

	g.report(ctx,
		result.UsageMetadata.PromptTokenCount,
		result.UsageMetadata.CandidatesTokenCount,
		result.UsageMetadata.TotalTokenCount,
		time.Since(start), nil)

	return result.Candidates[0].Content.Parts[0].Text, nil
}

func (g *GeminiLLM) report(ctx context.Context, prompt, output, total int, dur time.Duration, callErr error) {
	if g.recorder == nil {
		return
	}
	uid, uname, hid, src := metaFromCtx(ctx)
	if src == "" {
		src = "llm_chat"
	}
	rec := UsageRecord{
		Provider:     "gemini",
		Model:        g.getModel(),
		Operation:    "chat",
		SourceModule: src,
		UserID:       uid,
		UserName:     uname,
		HubID:        hid,
		RequestCount: 1,
		PromptTokens: prompt,
		OutputTokens: output,
		TotalTokens:  total,
		LatencyMs:    int(dur.Milliseconds()),
		Status:       "success",
	}
	if callErr != nil {
		rec.Status = "error"
		rec.ErrorMessage = callErr.Error()
	}
	g.recorder.RecordUsage(rec)
}
