package model

import (
	"time"

	"github.com/google/uuid"
)

// TokenUsage records a single external AI / embedding API call.
type TokenUsage struct {
	ID           uuid.UUID  `json:"id"`
	Timestamp    time.Time  `json:"timestamp"`
	Provider     string     `json:"provider"`             // gemini | openai
	Model        string     `json:"model"`                // gemini-2.0-flash, gpt-4o-mini, ...
	Operation    string     `json:"operation"`            // chat | embed
	SourceModule *string    `json:"source_module,omitempty"`
	UserID       *uuid.UUID `json:"user_id,omitempty"`
	UserName     *string    `json:"user_name,omitempty"`
	HubID        *uuid.UUID `json:"hub_id,omitempty"`
	RequestCount int        `json:"request_count"`
	PromptTokens int        `json:"prompt_tokens"`
	OutputTokens int        `json:"output_tokens"`
	TotalTokens  int        `json:"total_tokens"`
	LatencyMs    int        `json:"latency_ms"`
	Status       string     `json:"status"`               // success | error
	ErrorMessage *string    `json:"error_message,omitempty"`
}

// TokenUsageStats is an aggregate roll-up returned to the dashboard.
type TokenUsageStats struct {
	TotalCalls       int64                   `json:"total_calls"`
	TotalTokens      int64                   `json:"total_tokens"`
	TotalPromptToks  int64                   `json:"total_prompt_tokens"`
	TotalOutputToks  int64                   `json:"total_output_tokens"`
	ErrorCalls       int64                   `json:"error_calls"`
	AvgLatencyMs     float64                 `json:"avg_latency_ms"`
	ByProvider       []TokenUsageGroup       `json:"by_provider"`
	ByModel          []TokenUsageGroup       `json:"by_model"`
	ByOperation      []TokenUsageGroup       `json:"by_operation"`
	Daily            []TokenUsageDailyPoint  `json:"daily"`
}

type TokenUsageGroup struct {
	Key         string `json:"key"`
	Calls       int64  `json:"calls"`
	TotalTokens int64  `json:"total_tokens"`
}

type TokenUsageDailyPoint struct {
	Date        string `json:"date"` // YYYY-MM-DD
	Calls       int64  `json:"calls"`
	TotalTokens int64  `json:"total_tokens"`
}
