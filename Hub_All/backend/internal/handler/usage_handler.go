package handler

import (
	"errors"
	"log/slog"
	"math"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/medinet/hub-all-backend/internal/embedding"
	"github.com/medinet/hub-all-backend/internal/llm"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/response"
	"github.com/medinet/hub-all-backend/internal/service"
)

// UsageHandler exposes token-usage queries AND acts as the bridge that
// adapts service.UsageLogger to the llm.UsageRecorder + embedding.UsageRecorder
// interfaces. Keeping the bridge here (in the handler layer) avoids any
// import cycle between llm/embedding/service.
type UsageHandler struct {
	logger    *service.UsageLogger
	realtime  *service.UsageRealtime
	statsCache *service.StatsCache
}

func NewUsageHandler(logger *service.UsageLogger, realtime *service.UsageRealtime, statsCache *service.StatsCache) *UsageHandler {
	return &UsageHandler{
		logger:     logger,
		realtime:   realtime,
		statsCache: statsCache,
	}
}

// ─── Bridge: llm.UsageRecorder ───

type llmBridge struct{ l *service.UsageLogger }

func NewLLMUsageRecorder(l *service.UsageLogger) llm.UsageRecorder { return &llmBridge{l} }

func (b *llmBridge) RecordUsage(r llm.UsageRecord) {
	b.l.Record(model.TokenUsage{
		Provider:     r.Provider,
		Model:        r.Model,
		Operation:    r.Operation,
		SourceModule: strPtrIfNonEmpty(r.SourceModule),
		UserID:       r.UserID,
		UserName:     r.UserName,
		HubID:        r.HubID,
		RequestCount: r.RequestCount,
		PromptTokens: r.PromptTokens,
		OutputTokens: r.OutputTokens,
		TotalTokens:  r.TotalTokens,
		LatencyMs:    r.LatencyMs,
		Status:       r.Status,
		ErrorMessage: strPtrIfNonEmpty(r.ErrorMessage),
	})
}

// ─── Bridge: embedding.UsageRecorder ───

type embedBridge struct{ l *service.UsageLogger }

func NewEmbedUsageRecorder(l *service.UsageLogger) embedding.UsageRecorder {
	return &embedBridge{l}
}

func (b *embedBridge) RecordUsage(r embedding.UsageRecord) {
	b.l.Record(model.TokenUsage{
		Provider:     r.Provider,
		Model:        r.Model,
		Operation:    r.Operation,
		SourceModule: strPtrIfNonEmpty(r.SourceModule),
		UserID:       r.UserID,
		UserName:     r.UserName,
		HubID:        r.HubID,
		RequestCount: r.RequestCount,
		PromptTokens: r.PromptTokens,
		OutputTokens: r.OutputTokens,
		TotalTokens:  r.TotalTokens,
		LatencyMs:    r.LatencyMs,
		Status:       r.Status,
		ErrorMessage: strPtrIfNonEmpty(r.ErrorMessage),
	})
}

func strPtrIfNonEmpty(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

// ─── HTTP Handlers ───

// GET /api/usage — detail table. Caps range to 7 days to protect Postgres.
func (h *UsageHandler) List(c *gin.Context) {
	dateFrom := c.Query("date_from")
	dateTo := c.Query("date_to")
	provider := c.Query("provider")
	modelName := c.Query("model")
	operation := c.Query("operation")
	hubID := c.Query("hub_id")
	status := c.Query("status")

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "20"))

	entries, total, err := h.logger.List(c.Request.Context(), dateFrom, dateTo, provider, modelName, operation, hubID, status, page, perPage)
	if err != nil {
		if errors.Is(err, service.ErrDetailRangeTooWide) {
			response.BadRequest(c, err.Error())
			return
		}
		slog.Error("list token usage failed", "error", err)
		response.InternalError(c, "failed to list token usage")
		return
	}
	totalPages := int(math.Ceil(float64(total) / float64(perPage)))
	response.Paginated(c, entries, response.Meta{
		Page: page, PerPage: perPage, Total: total, TotalPages: totalPages,
	})
}

// GET /api/usage/stats — rollup-backed. Cached via Redis with 5s TTL;
// cache is version-bumped on every flush so accuracy == flush cadence.
func (h *UsageHandler) Stats(c *gin.Context) {
	filter := map[string]string{
		"date_from": c.Query("date_from"),
		"date_to":   c.Query("date_to"),
		"provider":  c.Query("provider"),
		"model":     c.Query("model"),
		"operation": c.Query("operation"),
		"hub_id":    c.Query("hub_id"),
	}
	hash := service.HashFilter(filter)

	// Cache hit path — 99%+ under dashboard load.
	if h.statsCache != nil {
		var cached model.TokenUsageStats
		if ok, err := h.statsCache.Get(c.Request.Context(), hash, &cached); err == nil && ok {
			c.Header("X-Usage-Cache", "hit")
			response.OK(c, &cached)
			return
		}
	}

	stats, err := h.logger.Stats(c.Request.Context(),
		filter["date_from"], filter["date_to"], filter["provider"],
		filter["model"], filter["operation"], filter["hub_id"])
	if err != nil {
		slog.Error("token usage stats failed", "error", err)
		response.InternalError(c, "failed to load usage stats")
		return
	}

	if h.statsCache != nil {
		if err := h.statsCache.Set(c.Request.Context(), hash, stats); err != nil {
			slog.Debug("stats cache set failed", "error", err)
		}
	}
	c.Header("X-Usage-Cache", "miss")
	response.OK(c, stats)
}

// GET /api/usage/realtime — last 60 minutes from Redis.
// Independent of the rollup worker → ~50ms end-to-end, accurate to <2s.
func (h *UsageHandler) Realtime(c *gin.Context) {
	if h.realtime == nil {
		response.OK(c, &service.RealtimeSnapshot{WindowMinutes: 0})
		return
	}
	snap, err := h.realtime.Snapshot(c.Request.Context())
	if err != nil {
		slog.Error("realtime snapshot failed", "error", err)
		response.InternalError(c, "failed to load realtime usage")
		return
	}
	response.OK(c, snap)
}
