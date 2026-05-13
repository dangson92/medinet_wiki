package embedding

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

type GeminiProvider struct {
	envKey   string
	model    string
	dim      int
	client   *http.Client
	recorder UsageRecorder
}

// SetUsageRecorder attaches the async usage logger.
func (p *GeminiProvider) SetUsageRecorder(r UsageRecorder) { p.recorder = r }

func NewGemini(apiKey, model string) *GeminiProvider {
	if model == "" {
		model = "gemini-embedding-001"
	}
	dim := 768
	if model == "gemini-embedding-001" || model == "gemini-embedding-2-preview" {
		dim = 3072
	}
	if apiKey != "" {
		os.Setenv("GEMINI_API_KEY", apiKey)
	}
	return &GeminiProvider{
		envKey: "GEMINI_API_KEY",
		model:  model,
		dim:    dim,
		client: &http.Client{Timeout: 60 * time.Second},
	}
}

func (p *GeminiProvider) ModelName() string { return p.model }
func (p *GeminiProvider) Dimension() int    { return p.dim }

func (p *GeminiProvider) Embed(ctx context.Context, texts []string) ([][]float32, error) {
	start := time.Now()
	requests := make([]geminiEmbedRequest, len(texts))
	for i, t := range texts {
		requests[i] = geminiEmbedRequest{
			Model:   "models/" + p.model,
			Content: geminiContent{Parts: []geminiPart{{Text: t}}},
		}
	}

	body := map[string]interface{}{"requests": requests}
	jsonBody, err := json.Marshal(body)
	if err != nil {
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	key := os.Getenv(p.envKey)
	if key == "" {
		err := fmt.Errorf("Gemini API key not configured (set in Settings)")
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, err
	}
	url := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/%s:batchEmbedContents", p.model)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(jsonBody))
	if err != nil {
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-goog-api-key", key)

	resp, err := p.client.Do(req)
	if err != nil {
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != 200 {
		err := fmt.Errorf("Gemini API error %d: %s", resp.StatusCode, string(respBody))
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, err
	}

	var result geminiResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	vectors := make([][]float32, len(result.Embeddings))
	for i, e := range result.Embeddings {
		vectors[i] = e.Values
	}

	// Gemini batchEmbedContents does not return token counts — approximate
	// from input length so the dashboard still reflects relative cost.
	p.report(ctx, len(texts), approxTokens(texts), time.Since(start), nil)
	return vectors, nil
}

func (p *GeminiProvider) report(ctx context.Context, batch, tokens int, dur time.Duration, callErr error) {
	if p.recorder == nil {
		return
	}
	uid, uname, hid, src := metaFromCtx(ctx)
	if src == "" {
		src = "rag_embed"
	}
	rec := UsageRecord{
		Provider:     "gemini",
		Model:        p.model,
		Operation:    "embed",
		SourceModule: src,
		UserID:       uid,
		UserName:     uname,
		HubID:        hid,
		RequestCount: batch, // # of texts embedded in this batch call
		PromptTokens: tokens,
		OutputTokens: 0,
		TotalTokens:  tokens,
		LatencyMs:    int(dur.Milliseconds()),
		Status:       "success",
	}
	if callErr != nil {
		rec.Status = "error"
		rec.ErrorMessage = callErr.Error()
	}
	p.recorder.RecordUsage(rec)
}

type geminiEmbedRequest struct {
	Model   string        `json:"model"`
	Content geminiContent `json:"content"`
}

type geminiContent struct {
	Parts []geminiPart `json:"parts"`
}

type geminiPart struct {
	Text string `json:"text"`
}

type geminiResponse struct {
	Embeddings []struct {
		Values []float32 `json:"values"`
	} `json:"embeddings"`
}
