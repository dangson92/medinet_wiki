package router

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/gin-contrib/gzip"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"github.com/medinet/hub-all-backend/internal/config"
	"github.com/medinet/hub-all-backend/internal/embedding"
	"github.com/medinet/hub-all-backend/internal/handler"
	"github.com/medinet/hub-all-backend/internal/llm"
	"github.com/medinet/hub-all-backend/internal/middleware"
	"github.com/medinet/hub-all-backend/internal/model"
	jwtpkg "github.com/medinet/hub-all-backend/internal/pkg/jwt"
	"github.com/medinet/hub-all-backend/internal/rag"
	"github.com/medinet/hub-all-backend/internal/rag/extractor"
	"github.com/medinet/hub-all-backend/internal/repository"
	"github.com/medinet/hub-all-backend/internal/vectorstore"
)

// maskKey returns a masked version of an API key for display.
func maskKey(key string) string {
	if key == "" {
		return ""
	}
	if len(key) <= 12 {
		return key[:4] + "****"
	}
	return key[:8] + "****" + key[len(key)-4:]
}

func Setup(
	cfg *config.Config,
	jwtManager *jwtpkg.Manager,
	rdb *redis.Client,
	authHandler *handler.AuthHandler,
	hubHandler *handler.HubHandler,
	docHandler *handler.DocumentHandler,
	searchHandler *handler.SearchHandler,
	syncHandler *handler.SyncHandler,
	userHandler *handler.UserHandler,
	profileHandler *handler.ProfileHandler,
	auditHandler *handler.AuditHandler,
	apikeyHandler *handler.APIKeyHandler,
	usageHandler *handler.UsageHandler,
	settingsRepo *repository.SettingsRepo,
	hubRepo *repository.HubRepo,
	vectorStore vectorstore.VectorStore,
	llmClient *llm.SwappableLLM,
	swappableEmbedder *embedding.SwappableEmbedder,
	// ─── M1 Phase 4 (CFG-03, CFG-04) ───
	doclingCircuit *extractor.DoclingCircuit,
	doclingHealthProbe *extractor.DoclingHealthProbe,
	auditRepo *repository.AuditRepo,
	pipeline *rag.Pipeline,
) *gin.Engine {
	if cfg.App.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	r := gin.New()

	// ─── Global Middleware ───
	r.Use(middleware.Recovery())
	r.Use(middleware.RequestID()) // Plan 03-01 — sau Recovery, trước SecurityHeaders để mọi log/error downstream có request_id
	r.Use(middleware.SecurityHeaders())
	r.Use(middleware.CORS(cfg.CORS.AllowedOrigins))
	r.Use(middleware.RateLimit(rdb, cfg.RateLimit.RPS, cfg.RateLimit.Burst))
	r.Use(gzip.Gzip(gzip.DefaultCompression))

	// ─── Health Check + RAG Config ───
	r.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":    "ok",
			"timestamp": time.Now().UTC().Format(time.RFC3339),
			"version":   "1.0.0",
		})
	})

	r.GET("/api/rag-config", func(c *gin.Context) {
		// Mask API keys — never return full keys
		geminiMask := maskKey(os.Getenv("GEMINI_API_KEY"))
		openaiMask := maskKey(os.Getenv("OPENAI_API_KEY"))
		llmMode := "auto"
		if llmClient != nil {
			llmMode = string(llmClient.Mode())
		}

		geminiLLMModel := os.Getenv(llm.GeminiModelEnvKey)
		if geminiLLMModel == "" {
			geminiLLMModel = llm.DefaultGeminiModel
		}

		// ─── M1 Phase 4 — Docling fields (CFG-03) ───
		// Probe health + circuit state + last fallback time để admin quan sát.
		// Tất cả best-effort: nếu probe fail / repo nil → trả "unknown" thay vì 500.
		var (
			doclingStatus  = "unknown"
			doclingVersion = ""
			circuitState   = "unknown"
			lastFallback   *string
		)
		ctx := c.Request.Context()
		if doclingHealthProbe != nil {
			doclingStatus = string(doclingHealthProbe.Status(ctx))
			doclingVersion = doclingHealthProbe.Version(ctx)
		}
		if doclingCircuit != nil {
			circuitState = doclingCircuit.State().String()
		}
		if auditRepo != nil {
			// Query last_fallback_at — slow OK trong M1 (defer index migration sang hardening).
			entries, _, err := auditRepo.List(ctx, "", "", "", "rag_fallback", "", 1, 1)
			if err == nil && len(entries) > 0 {
				ts := entries[0].Timestamp.UTC().Format(time.RFC3339)
				lastFallback = &ts
			}
		}

		c.JSON(http.StatusOK, gin.H{
			"chunker":            "Semantic Chunker (AI-powered)",
			"chunk_size":         cfg.RAG.ChunkSize,
			"chunk_overlap":      cfg.RAG.ChunkOverlap,
			"embedding_model":    cfg.RAG.EmbeddingModel,
			"embedding_provider": cfg.RAG.EmbeddingProvider,
			"batch_size":         cfg.RAG.BatchSize,
			"gemini_key_mask":    geminiMask,
			"openai_key_mask":    openaiMask,
			"gemini_key_saved":   os.Getenv("GEMINI_API_KEY") != "",
			"openai_key_saved":   os.Getenv("OPENAI_API_KEY") != "",
			"llm_provider":       llmMode,
			"gemini_llm_model":   geminiLLMModel,
			// ─── Phase 4 mới (CFG-03) ───
			"extractor_mode":         cfg.RAG.Extractor,         // native|docling|auto
			"docling_service_status": doclingStatus,             // healthy|degraded|down|unknown
			"docling_version":        doclingVersion,            // "" nếu probe fail
			"docling_circuit_state":  circuitState,              // closed|half-open|open|unknown
			"last_fallback_at":       lastFallback,              // *string nullable RFC3339
			"docling_fail_threshold": cfg.RAG.DoclingFailThreshold,
			"docling_cooldown_min":   cfg.RAG.DoclingCooldownMin,
		})
	})

	r.PUT("/api/rag-config", middleware.JWTAuth(jwtManager, rdb), middleware.RequireRole("admin"), func(c *gin.Context) {
		var req struct {
			EmbeddingProvider string `json:"embedding_provider"`
			EmbeddingModel    string `json:"embedding_model"`
			ChunkSize         int    `json:"chunk_size"`
			ChunkOverlap      int    `json:"chunk_overlap"`
			BatchSize         int    `json:"batch_size"`
			GeminiAPIKey      string `json:"gemini_api_key"`
			OpenAIAPIKey      string `json:"openai_api_key"`
			// LLMProvider controls which LLM is used for chat / answer generation.
			// "gemini" → only Gemini (no fallback even if OpenAI key exists)
			// "openai" → only OpenAI
			// "auto"   → Gemini first, OpenAI fallback (only when key present)
			LLMProvider string `json:"llm_provider"`
			// GeminiLLMModel overrides the Gemini text-generation model at runtime.
			// e.g. "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite"
			GeminiLLMModel string `json:"gemini_llm_model"`
			// ClearGeminiKey / ClearOpenAIKey: removes the key from DB + env
			// so it is never used again until a new key is saved.
			ClearGeminiKey bool `json:"clear_gemini_key"`
			ClearOpenAIKey bool `json:"clear_openai_key"`
			// ExtractorMode: hot-swap pipeline RAG mode (M1 Phase 4 CFG-03/CFG-04).
			// Hợp lệ: "native", "docling", "auto". "" = không đổi.
			ExtractorMode string `json:"extractor_mode"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": "invalid request"})
			return
		}
		if req.EmbeddingProvider != "" {
			cfg.RAG.EmbeddingProvider = req.EmbeddingProvider
		}
		if req.EmbeddingModel != "" {
			cfg.RAG.EmbeddingModel = req.EmbeddingModel
		}
		if req.ChunkSize > 0 {
			cfg.RAG.ChunkSize = req.ChunkSize
		}
		if req.ChunkOverlap >= 0 {
			cfg.RAG.ChunkOverlap = req.ChunkOverlap
		}
		if req.BatchSize > 0 {
			cfg.RAG.BatchSize = req.BatchSize
		}
		// ─── M1 Phase 4 — Hot-swap extractor mode (CFG-03, CFG-04) ───
		// Validate enum → 400 nếu invalid. Đổi mode → gọi pipeline.SetExtractorMode
		// (setter có sẵn từ Plan 04-02), reset Redis circuit state, persist qua
		// settings_repo, ghi audit `rag_config_change`. Toàn bộ guard nil cho an toàn.
		if req.ExtractorMode != "" {
			validModes := map[string]bool{"native": true, "docling": true, "auto": true}
			if !validModes[req.ExtractorMode] {
				c.JSON(http.StatusBadRequest, gin.H{
					"error": "extractor_mode không hợp lệ — chỉ chấp nhận: native, docling, auto",
				})
				return
			}
			oldMode := cfg.RAG.Extractor
			if oldMode != req.ExtractorMode {
				cfg.RAG.Extractor = req.ExtractorMode

				// Sync vào Pipeline runtime — setter có sẵn từ Plan 04-02 (CHECK round 1 B2).
				if pipeline != nil {
					pipeline.SetExtractorMode(req.ExtractorMode)
				}

				// Reset Redis circuit state (CFG-04) — admin chuyển mode → counters cũ vô nghĩa.
				if doclingCircuit != nil {
					if err := doclingCircuit.Reset(c.Request.Context()); err != nil {
						slog.Warn("reset docling circuit failed", "err", err)
					}
				}

				// Persist vào settings_repo để giá trị giữ qua restart.
				// W4 quyết: settingsRepo đã ở scope router (line 49) → option (a).
				if settingsRepo != nil {
					_ = settingsRepo.Set(c.Request.Context(), "RAG_EXTRACTOR", req.ExtractorMode, false)
				}

				// Audit (CFG-05) — ghi from→to + actor user_id để admin truy vết.
				if auditRepo != nil {
					actorID, _ := middleware.GetUserID(c)
					actorName := "admin"
					payload := map[string]any{
						"from": oldMode,
						"to":   req.ExtractorMode,
						"by":   actorID.String(),
					}
					payloadJSON, _ := json.Marshal(payload)
					var actorIDPtr *uuid.UUID
					if actorID != uuid.Nil {
						idCopy := actorID
						actorIDPtr = &idCopy
					}
					_ = auditRepo.Insert(c.Request.Context(), &model.AuditLogEntry{
						ID:        uuid.New(),
						Timestamp: time.Now().UTC(),
						UserID:    actorIDPtr,
						UserName:  &actorName,
						IsAI:      false,
						Action:    "rag_config_change",
						Payload:   payloadJSON,
					})
				}

				slog.Info("extractor_mode hot-swapped",
					"from", oldMode, "to", req.ExtractorMode)
			}
		}
		// Clear keys first (before any new key saves)
		if req.ClearGeminiKey {
			os.Unsetenv("GEMINI_API_KEY")
			cfg.RAG.EmbeddingAPIKey = ""
			if settingsRepo != nil {
				_ = settingsRepo.Delete(c.Request.Context(), "GEMINI_API_KEY")
			}
			slog.Info("Gemini API key cleared from DB + env")
		}
		if req.ClearOpenAIKey {
			os.Unsetenv("OPENAI_API_KEY")
			if cfg.RAG.EmbeddingProvider == "openai" {
				cfg.RAG.EmbeddingAPIKey = ""
			}
			if settingsRepo != nil {
				_ = settingsRepo.Delete(c.Request.Context(), "OPENAI_API_KEY")
			}
			slog.Info("OpenAI API key cleared from DB + env")
		}
		// Save API keys — persist to DB (encrypted) + set in env (runtime)
		if req.GeminiAPIKey != "" {
			os.Setenv("GEMINI_API_KEY", req.GeminiAPIKey)
			if cfg.RAG.EmbeddingProvider == "gemini" {
				cfg.RAG.EmbeddingAPIKey = req.GeminiAPIKey
			}
			if settingsRepo != nil {
				_ = settingsRepo.Set(c.Request.Context(), "GEMINI_API_KEY", req.GeminiAPIKey, true)
			}
			slog.Info("Gemini API key updated + persisted")
		}
		if req.OpenAIAPIKey != "" {
			os.Setenv("OPENAI_API_KEY", req.OpenAIAPIKey)
			if cfg.RAG.EmbeddingProvider == "openai" {
				cfg.RAG.EmbeddingAPIKey = req.OpenAIAPIKey
			}
			if settingsRepo != nil {
				_ = settingsRepo.Set(c.Request.Context(), "OPENAI_API_KEY", req.OpenAIAPIKey, true)
			}
			slog.Info("OpenAI API key updated + persisted")
		}
		// Re-resolve the active API key from env after any key updates above.
		switch cfg.RAG.EmbeddingProvider {
		case "gemini":
			cfg.RAG.EmbeddingAPIKey = os.Getenv("GEMINI_API_KEY")
		default:
			cfg.RAG.EmbeddingAPIKey = os.Getenv("OPENAI_API_KEY")
		}
		// Hot-swap the running embedder so the RAG pipeline and searcher
		// immediately use the new provider — no server restart required.
		// Only ONE embedding provider is ever active at a time.
		if swappableEmbedder != nil && cfg.RAG.EmbeddingAPIKey != "" {
			swappableEmbedder.SwapByConfig(cfg.RAG.EmbeddingProvider, cfg.RAG.EmbeddingAPIKey, cfg.RAG.EmbeddingModel)
			slog.Info("embedding provider hot-swapped",
				"provider", cfg.RAG.EmbeddingProvider,
				"model", cfg.RAG.EmbeddingModel)
		}
		// Hot-swap the LLM provider mode.
		// "gemini"  → only Gemini (no fallback even if OpenAI key exists)
		// "openai"  → only OpenAI
		// "auto"    → smart fallback: only uses providers whose key is in env
		if req.LLMProvider != "" && llmClient != nil {
			newMode := llm.Mode(req.LLMProvider)
			llmClient.SwapByMode(newMode)
			if settingsRepo != nil {
				_ = settingsRepo.Set(c.Request.Context(), "LLM_PROVIDER", req.LLMProvider, false)
			}
			slog.Info("LLM provider mode updated", "mode", req.LLMProvider)
		} else if llmClient != nil {
			// Key change only — re-evaluate auto mode in case keys changed.
			llmClient.RefreshAutoMode()
		}
		// Hot-update Gemini LLM model (takes effect on next Generate() call).
		if req.GeminiLLMModel != "" {
			os.Setenv(llm.GeminiModelEnvKey, req.GeminiLLMModel)
			if settingsRepo != nil {
				_ = settingsRepo.Set(c.Request.Context(), "LLM_GEMINI_MODEL", req.GeminiLLMModel, false)
			}
			slog.Info("Gemini LLM model updated", "model", req.GeminiLLMModel)
		}
		// Also persist non-secret RAG config
		if settingsRepo != nil {
			_ = settingsRepo.Set(c.Request.Context(), "RAG_EMBEDDING_PROVIDER", cfg.RAG.EmbeddingProvider, false)
			_ = settingsRepo.Set(c.Request.Context(), "RAG_EMBEDDING_MODEL", cfg.RAG.EmbeddingModel, false)
			_ = settingsRepo.Set(c.Request.Context(), "RAG_CHUNK_SIZE", fmt.Sprintf("%d", cfg.RAG.ChunkSize), false)
			_ = settingsRepo.Set(c.Request.Context(), "RAG_CHUNK_OVERLAP", fmt.Sprintf("%d", cfg.RAG.ChunkOverlap), false)
			_ = settingsRepo.Set(c.Request.Context(), "RAG_BATCH_SIZE", fmt.Sprintf("%d", cfg.RAG.BatchSize), false)
		}
		activeLLM := ""
		if llmClient != nil {
			activeLLM = string(llmClient.Mode())
		}
		c.JSON(http.StatusOK, gin.H{
			"message":                "config updated",
			"active_embedding":       cfg.RAG.EmbeddingProvider,
			"active_llm_provider":    activeLLM,
		})
	})

	r.GET("/api/rag-config/test", middleware.JWTAuth(jwtManager, rdb), func(c *gin.Context) {
		provider := c.Query("provider")
		var key string
		switch provider {
		case "gemini":
			key = os.Getenv("GEMINI_API_KEY")
		case "openai":
			key = os.Getenv("OPENAI_API_KEY")
		default:
			c.JSON(400, gin.H{"success": false, "message": "provider must be 'gemini' or 'openai'"})
			return
		}
		if key == "" {
			c.JSON(200, gin.H{"success": false, "message": "API key chưa được cấu hình"})
			return
		}
		// Quick test: try listing models
		var testURL string
		if provider == "gemini" {
			testURL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"
		} else {
			testURL = "https://api.openai.com/v1/models?limit=1"
		}
		req, _ := http.NewRequest("GET", testURL, nil)
		if provider == "gemini" {
			req.Header.Set("x-goog-api-key", key)
		} else {
			req.Header.Set("Authorization", "Bearer "+key)
		}
		client := &http.Client{Timeout: 10 * time.Second}
		resp, err := client.Do(req)
		if err != nil {
			c.JSON(200, gin.H{"success": false, "message": "Không thể kết nối: " + err.Error()})
			return
		}
		defer resp.Body.Close()
		if resp.StatusCode == 200 {
			c.JSON(200, gin.H{"success": true, "message": "Kết nối thành công"})
		} else {
			c.JSON(200, gin.H{"success": false, "message": fmt.Sprintf("API trả lỗi %d — kiểm tra lại key", resp.StatusCode)})
		}
	})

	// ─── GET /api/rag-config/collections ─────────────────────────────
	// Inventory of hub vector collections with their current dimension,
	// document count, and whether they match the active embedding provider.
	// Used by the Settings UI to warn BEFORE the admin saves a mismatched
	// provider that would break ingestion or search.
	r.GET("/api/rag-config/collections", middleware.JWTAuth(jwtManager, rdb), middleware.RequireRole("admin"), func(c *gin.Context) {
		type collectionInfo struct {
			HubCode    string `json:"hub_code"`
			HubName    string `json:"hub_name"`
			Collection string `json:"collection"`
			Dimension  int    `json:"dimension"`     // 0 = empty (no lock)
			Count      int    `json:"doc_count"`
			Mismatch   bool   `json:"mismatch"`      // true = dim != current provider
		}
		type response struct {
			CurrentDimension int              `json:"current_dimension"`
			CurrentProvider  string           `json:"current_provider"`
			CurrentModel     string           `json:"current_model"`
			Collections      []collectionInfo `json:"collections"`
		}

		out := response{CurrentProvider: cfg.RAG.EmbeddingProvider, CurrentModel: cfg.RAG.EmbeddingModel}
		if swappableEmbedder != nil {
			out.CurrentDimension = swappableEmbedder.Dimension()
		}

		if vectorStore == nil || hubRepo == nil {
			c.JSON(http.StatusOK, out)
			return
		}

		hubs, err := hubRepo.List(c.Request.Context())
		if err != nil {
			slog.Warn("failed to list hubs for collection inventory", "error", err)
			c.JSON(http.StatusOK, out)
			return
		}

		out.Collections = make([]collectionInfo, 0, len(hubs))
		for _, h := range hubs {
			col := h.ChromaCollection
			if col == "" {
				col = "medinet_" + h.Code
			}
			info := collectionInfo{
				HubCode:    h.Code,
				HubName:    h.Name,
				Collection: col,
			}
			// Dimension probe — best-effort; a missing collection is fine (=0).
			if dim, err := vectorStore.CollectionDimension(c.Request.Context(), col); err == nil {
				info.Dimension = dim
			}
			if cnt, err := vectorStore.Count(c.Request.Context(), col); err == nil {
				info.Count = cnt
			}
			if info.Dimension > 0 && out.CurrentDimension > 0 && info.Dimension != out.CurrentDimension {
				info.Mismatch = true
			}
			out.Collections = append(out.Collections, info)
		}
		c.JSON(http.StatusOK, out)
	})

	// ─── GET /api/system-settings ────────────────────────────────────────
	// Returns general, security, and notification settings from the DB.
	// Falls back to sensible defaults when a key has never been set.
	r.GET("/api/system-settings", middleware.JWTAuth(jwtManager, rdb), middleware.RequireRole("admin"), func(c *gin.Context) {
		defaults := map[string]string{
			"SYSTEM_NAME":             "Medinet Wiki",
			"SYSTEM_URL":              "https://wiki.medinet.vn",
			"ADMIN_EMAIL":             "admin@medinet.vn",
			"SYSTEM_LANGUAGE":         "vi",
			"SECURITY_2FA_ENABLED":    "false",
			"SECURITY_SESSION_TIMEOUT": "30",
			"NOTIFY_EMAIL_ENABLED":    "true",
			"NOTIFY_TELEGRAM_ENABLED": "false",
		}
		result := make(map[string]string, len(defaults))
		for k, def := range defaults {
			if settingsRepo == nil {
				result[k] = def
				continue
			}
			val, err := settingsRepo.Get(c.Request.Context(), k)
			if err != nil || val == "" {
				result[k] = def
			} else {
				result[k] = val
			}
		}
		c.JSON(http.StatusOK, result)
	})

	// ─── PUT /api/system-settings ─────────────────────────────────────────
	// Persists general, security, and notification settings to the DB.
	r.PUT("/api/system-settings", middleware.JWTAuth(jwtManager, rdb), middleware.RequireRole("admin"), func(c *gin.Context) {
		var req struct {
			SystemName             string `json:"SYSTEM_NAME"`
			SystemURL              string `json:"SYSTEM_URL"`
			AdminEmail             string `json:"ADMIN_EMAIL"`
			SystemLanguage         string `json:"SYSTEM_LANGUAGE"`
			Security2FA            string `json:"SECURITY_2FA_ENABLED"`
			SecuritySessionTimeout string `json:"SECURITY_SESSION_TIMEOUT"`
			NotifyEmailEnabled     string `json:"NOTIFY_EMAIL_ENABLED"`
			NotifyTelegramEnabled  string `json:"NOTIFY_TELEGRAM_ENABLED"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"error": "invalid request"})
			return
		}
		if settingsRepo == nil {
			c.JSON(http.StatusOK, gin.H{"message": "settings updated (in-memory only)"})
			return
		}
		pairs := map[string]string{
			"SYSTEM_NAME":             req.SystemName,
			"SYSTEM_URL":              req.SystemURL,
			"ADMIN_EMAIL":             req.AdminEmail,
			"SYSTEM_LANGUAGE":         req.SystemLanguage,
			"SECURITY_2FA_ENABLED":    req.Security2FA,
			"SECURITY_SESSION_TIMEOUT": req.SecuritySessionTimeout,
			"NOTIFY_EMAIL_ENABLED":    req.NotifyEmailEnabled,
			"NOTIFY_TELEGRAM_ENABLED": req.NotifyTelegramEnabled,
		}
		ctx := c.Request.Context()
		for k, v := range pairs {
			if v == "" {
				continue
			}
			if err := settingsRepo.Set(ctx, k, v, false); err != nil {
				slog.Error("failed to save system setting", "key", k, "error", err)
			}
		}
		c.JSON(http.StatusOK, gin.H{"message": "settings updated"})
	})

	// ─── API v1 ───
	api := r.Group("/api")

	// ─── Auth Routes (Public) ───
	auth := api.Group("/auth")
	{
		auth.POST("/login", middleware.LoginRateLimit(rdb), authHandler.Login)
		auth.POST("/refresh", authHandler.Refresh)
	}

	// ─── Auth Routes (Authenticated) ───
	authProtected := api.Group("/auth")
	authProtected.Use(middleware.JWTAuth(jwtManager, rdb))
	{
		authProtected.POST("/logout", authHandler.Logout)
		authProtected.GET("/me", authHandler.Me)
	}

	// ─── Hub Routes (Authenticated) ───
	hubs := api.Group("/hubs")
	hubs.Use(middleware.JWTAuth(jwtManager, rdb))
	{
		hubs.GET("", hubHandler.List)
		hubs.GET("/:id", hubHandler.GetByID)

		// Admin-only routes
		hubAdmin := hubs.Group("")
		hubAdmin.Use(middleware.RequireRole("admin"))
		{
			hubAdmin.POST("", hubHandler.Create)
			hubAdmin.PUT("/:id", hubHandler.Update)
			hubAdmin.PATCH("/:id/status", hubHandler.UpdateStatus)
			hubAdmin.POST("/:id/test-connection", hubHandler.TestConnection)
		}
	}

	// ─── Document Routes (Authenticated) ───
	docs := api.Group("/documents")
	docs.Use(middleware.JWTAuth(jwtManager, rdb))
	{
		docs.GET("", docHandler.List)
		docs.GET("/:id", docHandler.GetByID)
		docs.GET("/:id/status", docHandler.GetStatus)
		docs.GET("/:id/file", docHandler.GetFile)
		// Version history (read) — viewer cũng được xem.
		docs.GET("/:id/versions", docHandler.ListVersions)
		docs.GET("/:id/versions/:vid", docHandler.GetVersion)
		docs.GET("/:id/versions/:vid/file", docHandler.DownloadVersionFile)

		// Admin-only routes
		docsAdmin := docs.Group("")
		docsAdmin.Use(middleware.RequireRole("admin"))
		{
			docsAdmin.POST("/upload", docHandler.Upload)
			docsAdmin.POST("/compose", docHandler.Compose)
			docsAdmin.DELETE("/:id", docHandler.Delete)
			// CFG-07 M1 Phase 4 — admin reindex endpoint.
			docsAdmin.POST("/:id/reindex", docHandler.Reindex)
			// Version history (write) — admin only.
			docsAdmin.POST("/:id/reupload/preview", docHandler.PreviewReupload)
			docsAdmin.POST("/:id/reupload", docHandler.ReUpload)
			docsAdmin.PUT("/:id/content/preview", docHandler.PreviewEditContent)
			docsAdmin.PUT("/:id/content", docHandler.EditContent)
			docsAdmin.POST("/:id/versions/:vid/restore", docHandler.RestoreVersion)
		}
	}

	// ─── Search Routes (Authenticated) ───
	search := api.Group("/search")
	search.Use(middleware.JWTAuth(jwtManager, rdb))
	{
		search.POST("", searchHandler.Search)
		search.POST("/cross-hub", searchHandler.CrossHubSearch)
		search.POST("/answer", searchHandler.Answer)

		searchAdmin := search.Group("")
		searchAdmin.Use(middleware.RequireRole("admin"))
		{
			searchAdmin.POST("/similar", searchHandler.Similar)
		}
	}

	// ─── Sync Routes (Authenticated) ───
	sync := api.Group("/sync")
	sync.Use(middleware.JWTAuth(jwtManager, rdb))
	{
		sync.GET("/stats", syncHandler.GetStats)
		sync.GET("/batches", syncHandler.ListBatches)
		sync.GET("/batches/:id", syncHandler.GetBatch)

		syncAdmin := sync.Group("")
		syncAdmin.Use(middleware.RequireRole("admin"))
		{
			syncAdmin.POST("/batches", syncHandler.SubmitBatch)
			syncAdmin.POST("/batches/:id/pages/:pid/approve", syncHandler.ApprovePage)
			syncAdmin.POST("/batches/:id/pages/:pid/reject", syncHandler.RejectPage)
		}
	}

	// ─── User Management Routes (Admin Only) ───
	users := api.Group("/users")
	users.Use(middleware.JWTAuth(jwtManager, rdb), middleware.RequireRole("admin"))
	{
		users.GET("", userHandler.List)
		users.GET("/:id", userHandler.GetByID)
		users.POST("", userHandler.Create)
		users.PUT("/:id", userHandler.Update)
		users.PATCH("/:id/role", userHandler.ChangeRole)
		users.PATCH("/:id/status", userHandler.ChangeStatus)
	}

	// ─── Profile Routes (Any Authenticated User) ───
	profile := api.Group("/profile")
	profile.Use(middleware.JWTAuth(jwtManager, rdb))
	{
		profile.GET("", profileHandler.GetProfile)
		profile.PUT("", profileHandler.UpdateProfile)
		profile.POST("/password", profileHandler.ChangePassword)
	}

	// ─── Audit Log Routes (Admin Only) ───
	audit := api.Group("/audit-logs")
	audit.Use(middleware.JWTAuth(jwtManager, rdb), middleware.RequireRole("admin"))
	{
		audit.GET("", auditHandler.List)
		audit.GET("/export", auditHandler.ExportCSV)
	}

	// ─── API Key Routes (Admin Only) ───
	apikeys := api.Group("/api-keys")
	apikeys.Use(middleware.JWTAuth(jwtManager, rdb), middleware.RequireRole("admin"))
	{
		apikeys.GET("", apikeyHandler.List)
		apikeys.GET("/:id", apikeyHandler.GetByID)
		apikeys.POST("", apikeyHandler.Create)
		apikeys.PUT("/:id", apikeyHandler.Update)
		apikeys.POST("/:id/revoke", apikeyHandler.Revoke)
	}

	// ─── Token / API Usage Routes (Admin Only) ───
	usage := api.Group("/usage")
	usage.Use(middleware.JWTAuth(jwtManager, rdb), middleware.RequireRole("admin"))
	{
		usage.GET("", usageHandler.List)
		usage.GET("/stats", usageHandler.Stats)
		usage.GET("/realtime", usageHandler.Realtime)
	}

	// ─── AI Chat Proxy (Authenticated) — keeps API key on backend ───
	api.POST("/ai/chat", middleware.JWTAuth(jwtManager, rdb), func(c *gin.Context) {
		if llmClient == nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"error": "LLM not configured — set API key in Settings"})
			return
		}
		var req struct {
			Messages []struct {
				Role    string `json:"role"`
				Content string `json:"content"`
			} `json:"messages"`
			SystemInstruction string `json:"system_instruction"`
		}
		if err := c.ShouldBindJSON(&req); err != nil || len(req.Messages) == 0 {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
			return
		}
		// Build prompt from messages
		prompt := ""
		if req.SystemInstruction != "" {
			prompt += "System: " + req.SystemInstruction + "\n\n"
		}
		for _, m := range req.Messages {
			if m.Role == "user" {
				prompt += "User: " + m.Content + "\n"
			} else {
				prompt += "Assistant: " + m.Content + "\n"
			}
		}
		prompt += "Assistant:"

		result, err := llmClient.Generate(c.Request.Context(), prompt)
		if err != nil {
			slog.Error("ai chat error", "error", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "AI service unavailable"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"response": result})
	})

	return r
}
