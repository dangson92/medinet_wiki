package llm

import (
	"context"

	"github.com/google/uuid"
)

// UsageRecord is the payload reported on every external AI call.
// Mirrors a subset of model.TokenUsage but kept here to avoid an import
// cycle (llm → service → repository → model).
type UsageRecord struct {
	Provider     string
	Model        string
	Operation    string // "chat" | "embed"
	SourceModule string
	UserID       *uuid.UUID
	UserName     *string
	HubID        *uuid.UUID
	RequestCount int
	PromptTokens int
	OutputTokens int
	TotalTokens  int
	LatencyMs    int
	Status       string // "success" | "error"
	ErrorMessage string
}

// UsageRecorder is implemented by service.UsageLogger. Decoupling via
// interface lets the LLM/embedding providers stay free of cross-package
// dependencies.
type UsageRecorder interface {
	RecordUsage(rec UsageRecord)
}

// Context keys used to enrich usage records with the calling user / hub.
// Callers that have a request context can attach these via WithUsageMeta;
// background callers (chunker, worker) leave them unset.
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
