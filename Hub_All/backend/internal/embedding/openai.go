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

type OpenAIProvider struct {
	envKey   string
	model    string
	dim      int
	client   *http.Client
	recorder UsageRecorder
}

func (p *OpenAIProvider) SetUsageRecorder(r UsageRecorder) { p.recorder = r }

func NewOpenAI(apiKey, model string) *OpenAIProvider {
	dim := 1536
	if model == "text-embedding-3-large" {
		dim = 3072
	}
	if apiKey != "" {
		os.Setenv("OPENAI_API_KEY", apiKey)
	}
	return &OpenAIProvider{
		envKey: "OPENAI_API_KEY",
		model:  model,
		dim:    dim,
		client: &http.Client{Timeout: 60 * time.Second},
	}
}

func (p *OpenAIProvider) ModelName() string { return p.model }
func (p *OpenAIProvider) Dimension() int    { return p.dim }

func (p *OpenAIProvider) Embed(ctx context.Context, texts []string) ([][]float32, error) {
	start := time.Now()
	body := map[string]interface{}{
		"input": texts,
		"model": p.model,
	}
	jsonBody, err := json.Marshal(body)
	if err != nil {
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", "https://api.openai.com/v1/embeddings", bytes.NewReader(jsonBody))
	if err != nil {
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	key := os.Getenv(p.envKey)
	if key == "" {
		err := fmt.Errorf("OpenAI API key not configured (set in Settings)")
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+key)

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
		err := fmt.Errorf("OpenAI API error %d: %s", resp.StatusCode, string(respBody))
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, err
	}

	var result openAIResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		p.report(ctx, len(texts), 0, time.Since(start), err)
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	vectors := make([][]float32, len(result.Data))
	for i, d := range result.Data {
		vectors[i] = d.Embedding
	}
	p.report(ctx, len(texts), result.Usage.TotalTokens, time.Since(start), nil)
	return vectors, nil
}

func (p *OpenAIProvider) report(ctx context.Context, batch, tokens int, dur time.Duration, callErr error) {
	if p.recorder == nil {
		return
	}
	uid, uname, hid, src := metaFromCtx(ctx)
	if src == "" {
		src = "rag_embed"
	}
	rec := UsageRecord{
		Provider:     "openai",
		Model:        p.model,
		Operation:    "embed",
		SourceModule: src,
		UserID:       uid,
		UserName:     uname,
		HubID:        hid,
		RequestCount: batch,
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

type openAIResponse struct {
	Data []struct {
		Embedding []float32 `json:"embedding"`
		Index     int       `json:"index"`
	} `json:"data"`
	Usage struct {
		TotalTokens int `json:"total_tokens"`
	} `json:"usage"`
}
