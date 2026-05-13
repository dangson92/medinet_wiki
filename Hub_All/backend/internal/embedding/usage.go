package embedding

import (
	"context"

	"github.com/google/uuid"
)

// UsageRecord mirrors llm.UsageRecord but kept here to avoid an import
// cycle (embedding → service → repository → model → embedding).
type UsageRecord struct {
	Provider     string
	Model        string
	Operation    string
	SourceModule string
	UserID       *uuid.UUID
	UserName     *string
	HubID        *uuid.UUID
	RequestCount int
	PromptTokens int
	OutputTokens int
	TotalTokens  int
	LatencyMs    int
	Status       string
	ErrorMessage string
}

type UsageRecorder interface {
	RecordUsage(rec UsageRecord)
}

type ctxKey int

const (
	ctxKeyUserID ctxKey = iota
	ctxKeyUserName
	ctxKeyHubID
	ctxKeySourceModule
)

func WithUsageMeta(ctx context.Context, userID *uuid.UUID, userName *string, hubID *uuid.UUID, sourceModule string) context.Context {
	if userID != nil {
		ctx = context.WithValue(ctx, ctxKeyUserID, userID)
	}
	if userName != nil {
		ctx = context.WithValue(ctx, ctxKeyUserName, userName)
	}
	if hubID != nil {
		ctx = context.WithValue(ctx, ctxKeyHubID, hubID)
	}
	if sourceModule != "" {
		ctx = context.WithValue(ctx, ctxKeySourceModule, sourceModule)
	}
	return ctx
}

func metaFromCtx(ctx context.Context) (userID *uuid.UUID, userName *string, hubID *uuid.UUID, source string) {
	if v, ok := ctx.Value(ctxKeyUserID).(*uuid.UUID); ok {
		userID = v
	}
	if v, ok := ctx.Value(ctxKeyUserName).(*string); ok {
		userName = v
	}
	if v, ok := ctx.Value(ctxKeyHubID).(*uuid.UUID); ok {
		hubID = v
	}
	if v, ok := ctx.Value(ctxKeySourceModule).(string); ok {
		source = v
	}
	return
}

// approxTokens is a cheap heuristic for providers that don't return token
// counts (Gemini batchEmbedContents). ~4 chars per token is the typical
// rule of thumb for English/Vietnamese mixed text.
func approxTokens(texts []string) int {
	total := 0
	for _, t := range texts {
		total += (len(t) + 3) / 4
	}
	return total
}
