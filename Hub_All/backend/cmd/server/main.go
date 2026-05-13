package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/medinet/hub-all-backend/internal/config"
	"github.com/medinet/hub-all-backend/internal/database"
	"github.com/medinet/hub-all-backend/internal/embedding"
	"github.com/medinet/hub-all-backend/internal/handler"
	llmPkg "github.com/medinet/hub-all-backend/internal/llm"
	jwtpkg "github.com/medinet/hub-all-backend/internal/pkg/jwt"
	"github.com/medinet/hub-all-backend/internal/rag"
	"github.com/medinet/hub-all-backend/internal/rag/augmenter"
	"github.com/medinet/hub-all-backend/internal/rag/chunker"
	"github.com/medinet/hub-all-backend/internal/rag/extractor"
	"github.com/medinet/hub-all-backend/internal/repository"
	"github.com/medinet/hub-all-backend/internal/router"
	"github.com/medinet/hub-all-backend/internal/service"
	"github.com/medinet/hub-all-backend/internal/storage"
	"github.com/medinet/hub-all-backend/internal/vectorstore"
	"github.com/medinet/hub-all-backend/internal/worker"
)

func main() {
	// ─── Structured Logging ───
	logLevel := slog.LevelInfo
	if os.Getenv("APP_ENV") == "development" {
		logLevel = slog.LevelDebug
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: logLevel}))
	slog.SetDefault(logger)

	// ─── Config ───
	cfg, err := config.Load()
	if err != nil {
		slog.Error("failed to load config", "error", err)
		os.Exit(1)
	}
	slog.Info("config loaded", "env", cfg.App.Env, "port", cfg.App.Port)

	// ─── Database ───
	db, err := database.NewPostgres(cfg.DB)
	if err != nil {
		slog.Error("failed to connect to PostgreSQL", "error", err)
		os.Exit(1)
	}
	defer db.Close()
	slog.Info("PostgreSQL connected")

	// ─── Run Migrations ───
	if err := database.RunMigrations(cfg.DB.DSN()); err != nil {
		slog.Error("failed to run migrations", "error", err)
		os.Exit(1)
	}
	slog.Info("database migrations completed")

	// ─── Redis (optional — server works without it) ───
	rdb, err := database.NewRedis(cfg.Redis)
	if err != nil {
		slog.Error("failed to connect to Redis", "error", err)
		os.Exit(1)
	}
	if rdb != nil {
		defer rdb.Close()
		slog.Info("Redis connected")
	} else {
		slog.Warn("Redis not available — rate limiting and token cache disabled")
	}

	// ─── JWT Manager ───
	jwtManager, err := jwtpkg.NewManager(cfg.JWT.PrivateKeyPath, cfg.JWT.PublicKeyPath, cfg.JWT.AccessTokenTTL, cfg.JWT.RefreshTokenTTL)
	if err != nil {
		slog.Error("failed to initialize JWT manager", "error", err)
		os.Exit(1)
	}
	slog.Info("JWT manager initialized")

	// ─── Repositories ───
	userRepo := repository.NewUserRepo(db.Pool)
	hubRepo := repository.NewHubRepo(db.Pool)
	tokenRepo := repository.NewTokenRepo(db.Pool)
	docRepo := repository.NewDocumentRepo(db.Pool)
	docVersionRepo := repository.NewDocumentVersionRepo(db.Pool)
	syncRepo := repository.NewSyncRepo(db.Pool)
	auditRepo := repository.NewAuditRepo(db.Pool)
	apikeyRepo := repository.NewAPIKeyRepo(db.Pool)
	settingsRepo := repository.NewSettingsRepo(db.Pool, cfg.AES.Key)
	usageRepo := repository.NewUsageRepo(db.Pool)

	// ─── Async Token / API Usage: logger + realtime + stats cache ───
	// Architecture: non-blocking CopyFrom batcher (Postgres) +
	// per-minute Redis counter (realtime) + version-bumped stats cache.
	// See service/usage_*.go for the full rationale.
	var usageRealtime *service.UsageRealtime
	var usageStatsCache *service.StatsCache
	if rdb != nil {
		usageRealtime = service.NewUsageRealtime(rdb)
		usageStatsCache = service.NewStatsCache(rdb)
	}
	usageLogger := service.NewUsageLogger(usageRepo, service.UsageLoggerOpts{
		BufferSize:    16384,
		FlushSize:     128,
		FlushInterval: 2 * time.Second,
		CopyThreshold: 32,
		Realtime:      usageRealtime,
		CacheBuster:   usageStatsCache,
	})
	defer usageLogger.Shutdown()

	// ─── Rollup worker: 5min / hourly / daily continuous aggregates ───
	usageRollup := service.NewUsageRollup(usageRepo)
	usageRollup.Start(context.Background())
	defer usageRollup.Shutdown()

	// ─── Partition maintenance: create next-month + drop older than 1 year ───
	usagePartMgr := service.NewUsagePartitionMgr(usageRepo, 365)
	usagePartMgr.Start(context.Background())
	defer usagePartMgr.Shutdown()

	// Load persisted settings from DB (saved via Settings UI on previous runs)
	{
		ctx := context.Background()
		if key, _ := settingsRepo.Get(ctx, "GEMINI_API_KEY"); key != "" {
			os.Setenv("GEMINI_API_KEY", key)
			slog.Info("loaded persisted Gemini API key from DB")
		}
		if key, _ := settingsRepo.Get(ctx, "OPENAI_API_KEY"); key != "" {
			os.Setenv("OPENAI_API_KEY", key)
			slog.Info("loaded persisted OpenAI API key from DB")
		}
		// Restore RAG config (provider, model, chunk sizes) from DB
		if v, _ := settingsRepo.Get(ctx, "RAG_EMBEDDING_PROVIDER"); v != "" {
			cfg.RAG.EmbeddingProvider = v
		}
		if v, _ := settingsRepo.Get(ctx, "RAG_EMBEDDING_MODEL"); v != "" {
			cfg.RAG.EmbeddingModel = v
		}
		if v, _ := settingsRepo.Get(ctx, "RAG_CHUNK_SIZE"); v != "" {
			if n, err := strconv.Atoi(v); err == nil && n > 0 {
				cfg.RAG.ChunkSize = n
			}
		}
		if v, _ := settingsRepo.Get(ctx, "RAG_CHUNK_OVERLAP"); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				cfg.RAG.ChunkOverlap = n
			}
		}
		if v, _ := settingsRepo.Get(ctx, "RAG_BATCH_SIZE"); v != "" {
			if n, err := strconv.Atoi(v); err == nil && n > 0 {
				cfg.RAG.BatchSize = n
			}
		}
		// Re-resolve the embedding API key from (now updated) env vars
		switch cfg.RAG.EmbeddingProvider {
		case "gemini":
			cfg.RAG.EmbeddingAPIKey = os.Getenv("GEMINI_API_KEY")
		default:
			cfg.RAG.EmbeddingAPIKey = os.Getenv("OPENAI_API_KEY")
		}
		slog.Info("persisted settings loaded from DB",
			"provider", cfg.RAG.EmbeddingProvider,
			"model", cfg.RAG.EmbeddingModel,
			"hasKey", cfg.RAG.EmbeddingAPIKey != "")
	}

	// ─── Embedding Provider ───
	// SwappableEmbedder is a mutex-protected wrapper that lets the admin change
	// the embedding provider at runtime (via PUT /api/rag-config) without a
	// server restart. The RAG pipeline, searcher, and worker all hold a pointer
	// to this wrapper through the EmbeddingProvider interface — a Swap() call
	// takes effect for all callers on the next Embed() invocation.
	embedRecorder := handler.NewEmbedUsageRecorder(usageLogger)
	var initialEmbedder embedding.EmbeddingProvider
	if cfg.RAG.EmbeddingAPIKey != "" {
		switch cfg.RAG.EmbeddingProvider {
		case "gemini":
			gp := embedding.NewGemini(cfg.RAG.EmbeddingAPIKey, cfg.RAG.EmbeddingModel)
			gp.SetUsageRecorder(embedRecorder)
			initialEmbedder = gp
			slog.Info("embedding provider initialized", "provider", "gemini", "model", cfg.RAG.EmbeddingModel)
		default: // "openai"
			op := embedding.NewOpenAI(cfg.RAG.EmbeddingAPIKey, cfg.RAG.EmbeddingModel)
			op.SetUsageRecorder(embedRecorder)
			initialEmbedder = op
			slog.Info("embedding provider initialized", "provider", "openai", "model", cfg.RAG.EmbeddingModel)
		}
	} else {
		slog.Warn("no embedding API key configured — document embedding will not work until a key is saved in Settings")
	}
	// Wrap in SwappableEmbedder so the router can hot-swap on config changes.
	swappableEmbedder := embedding.NewSwappable(initialEmbedder, embedRecorder)

	// ─── ChromaDB (optional) ───
	var store vectorstore.VectorStore
	if cfg.Chroma.URL != "" {
		chromaDB := vectorstore.NewChromaDB(cfg.Chroma.URL, cfg.Chroma.Token)
		// Test connection by listing collections
		if _, err := chromaDB.ListCollections(context.Background()); err != nil {
			slog.Warn("ChromaDB not available — document embedding will fail", "url", cfg.Chroma.URL, "error", err)
		} else {
			store = chromaDB
			slog.Info("ChromaDB connected", "url", cfg.Chroma.URL)

			// Auto-create collections for all active hubs
			allHubs, _ := repository.NewHubRepo(db.Pool).List(context.Background())
			for _, h := range allHubs {
				if h.Status != "active" {
					continue
				}
				col := h.ChromaCollection
				if col == "" {
					col = "medinet_" + h.Code
				}
				if err := chromaDB.CreateCollection(context.Background(), col); err != nil {
					slog.Warn("failed to create collection", "collection", col, "error", err)
				} else {
					slog.Info("collection ensured", "collection", col)
				}
			}
		}
	} else {
		slog.Warn("ChromaDB URL not configured — vector storage disabled")
	}

	// ─── LLM for Contextual Retrieval + Answer Generation ───
	// Built early so the StrategicChunker can use it for Contextual Retrieval.
	// Keys are read from os.Getenv() on every Generate() call so runtime key
	// updates (saved via Settings) take effect without restart.
	//
	// SwappableLLM enforces provider exclusivity:
	//   "gemini"  → only Gemini (no silent OpenAI fallback)
	//   "openai"  → only OpenAI
	//   "auto"    → smart fallback: only calls providers whose key is present
	// Load persisted LLM model from DB (admin may have changed it via Settings).
	// Falls back to DefaultGeminiModel ("gemini-2.0-flash-lite") if never set.
	{
		ctx := context.Background()
		if v, _ := settingsRepo.Get(ctx, "LLM_GEMINI_MODEL"); v != "" {
			os.Setenv(llmPkg.GeminiModelEnvKey, v)
		}
	}
	geminiLLM := llmPkg.NewGemini(getEnvMain("GEMINI_API_KEY", ""), os.Getenv(llmPkg.GeminiModelEnvKey))
	openaiLLM := llmPkg.NewOpenAI(getEnvMain("OPENAI_API_KEY", ""), "gpt-4o-mini")
	llmRecorder := handler.NewLLMUsageRecorder(usageLogger)
	geminiLLM.SetUsageRecorder(llmRecorder)
	openaiLLM.SetUsageRecorder(llmRecorder)

	// Load persisted LLM provider mode from DB.
	// Default rule (when never explicitly saved):
	//   match the embedding provider → prevents silent cross-provider calls.
	//   "auto" (fallback) must be opted-in explicitly by the admin.
	llmMode := llmPkg.Mode(cfg.RAG.EmbeddingProvider) // gemini | openai by default
	if llmMode != llmPkg.ModeGemini && llmMode != llmPkg.ModeOpenAI {
		llmMode = llmPkg.ModeGemini // safe fallback if provider value is unexpected
	}
	{
		ctx := context.Background()
		if v, _ := settingsRepo.Get(ctx, "LLM_PROVIDER"); v != "" {
			llmMode = llmPkg.Mode(v) // explicit admin choice overrides the default
		}
	}
	llmClient := llmPkg.NewSwappableLLM(geminiLLM, openaiLLM, llmMode, llmRecorder)
	slog.Info("LLM initialized",
		"mode", string(llmMode),
		"active", llmClient.Name(),
		"gemini_key", getEnvMain("GEMINI_API_KEY", "") != "",
		"openai_key", getEnvMain("OPENAI_API_KEY", "") != "")

	// ─── RAG Pipeline v3 — StrategicChunker ───
	// The StrategicChunker detects document type and routes each document
	// through the right combination of the 9 levels + 5 v3 techniques:
	//   L1 entity profile  (BS/TTUT/BSCKII doctor profiles)
	//   L5 negative rules  (always_include flag)
	//   Hierarchical       (parent-child split)
	//   Contextual         (LLM-generated context headers)
	// It falls back to RecursiveChunker for generic content.
	baseChunker := &chunker.RecursiveChunker{}
	strategicChunker := &chunker.StrategicChunker{
		Base:     baseChunker,
		Entity:   &chunker.EntityProfileChunker{MaxChunkTokens: 1500},
		Negative: &chunker.NegativeRuleExtractor{MaxChunkTokens: 600},
		Hierarchical: &chunker.HierarchicalChunker{
			Base:           baseChunker,
			ChildMaxTokens: 300,
			ChildOverlap:   40,
		},
		Contextual: &chunker.ContextualEnricher{
			LLM:            llmClient,
			MaxParallel:    10,
			PerCallTimeout: 15 * time.Second,
			DocCharLimit:   3000,
		},
	}
	var chunkr chunker.Chunker = strategicChunker
	slog.Info("chunker: Strategic v3 (router + L1/L5 + hierarchical + contextual)")
	chunkOpts := chunker.ChunkOpts{
		MaxTokens: cfg.RAG.ChunkSize,
		Overlap:   cfg.RAG.ChunkOverlap,
	}
	var pipeline *rag.Pipeline
	// Plan 04-03: 2 biến scope main để truyền vào router.Setup() cho admin endpoint.
	var doclingCircuit *extractor.DoclingCircuit
	var doclingHealthProbe *extractor.DoclingHealthProbe
	if swappableEmbedder.Provider() != nil && store != nil {
		pipeline = rag.NewPipeline(swappableEmbedder, store, chunkr, chunkOpts, cfg.RAG.BatchSize)
		// Optional: attach auto Q&A + keyword augmenter (RAGFlow-style). Requires an
		// LLM client; silently skipped when none is available. Enable/disable via
		// RAG_AUGMENT_ENABLED env var (default: on when an LLM is present).
		if llmClient != nil && os.Getenv("RAG_AUGMENT_ENABLED") != "false" {
			pipeline.SetAugmenter(&augmenter.Augmenter{
				LLM:            llmClient,
				MaxParallel:    10,
				PerCallTimeout: 20 * time.Second,
				MinChars:       150,
				MaxChars:       4000,
			})
			slog.Info("RAG augmenter enabled (auto Q&A + keywords)")
		}

		// ─── M1 Phase 3 — wire Docling adapter (WIRE-03) ───
		// Pipeline tự branch theo cfg.RAG.Extractor:
		//   "docling" → ExtractStructured() → skip Go chunker → preChunks vào embedder.
		//   "native" (default) hoặc "auto" → đường cũ (extractor.ForType + chunker Go).
		// Set unconditional an toàn — mode != "docling" sẽ KHÔNG dispatch sang Docling.
		doclingExt := extractor.NewDoclingExtractor(cfg.RAG.DoclingServiceURL, cfg.RAG.DoclingTimeoutSec)
		pipeline.SetDoclingExtractor(doclingExt, cfg.RAG.Extractor)
		slog.Info("RAG extractor mode configured",
			"mode", cfg.RAG.Extractor,
			"docling_url", cfg.RAG.DoclingServiceURL,
			"docling_timeout_sec", cfg.RAG.DoclingTimeoutSec,
		)

		// ─── M1 Phase 4 — Circuit breaker + audit + OCR langs cho mode "auto" (CFG-01, CFG-02, CFG-05) ───
		// Khởi tạo unconditional: nếu cfg.RAG.Extractor != "auto" thì circuit
		// có sẵn vẫn không sao (pipeline.extractAndChunk chỉ check khi mode=="auto").
		// Biến doclingCircuit giữ ở scope main để Plan 04-03 truyền vào router cho admin endpoint.
		doclingCircuit = extractor.NewDoclingCircuit(
			rdb,
			cfg.RAG.DoclingFailThreshold,
			time.Duration(cfg.RAG.DoclingCooldownMin)*time.Minute,
			slog.Default(),
		)
		// Plan 04-03 — health probe cho admin endpoint GET /api/rag-config (CFG-03).
		doclingHealthProbe = extractor.NewDoclingHealthProbe(cfg.RAG.DoclingServiceURL, rdb)
		pipeline.SetDoclingCircuit(doclingCircuit)
		pipeline.SetAuditInserter(auditRepo)                 // *repository.AuditRepo satisfy AuditInserter
		pipeline.SetDoclingOCRLangs(cfg.RAG.DoclingOCRLangs) // CFG-02 — default "vie+eng"
		slog.Info("docling circuit breaker wired",
			"threshold", cfg.RAG.DoclingFailThreshold,
			"cooldown_min", cfg.RAG.DoclingCooldownMin,
			"extractor_mode", cfg.RAG.Extractor,
			"ocr_langs", cfg.RAG.DoclingOCRLangs)

		slog.Info("RAG pipeline initialized")
	} else {
		slog.Warn("RAG pipeline not initialized — missing embedder or vector store")
	}

	// ─── Worker Manager ───
	var workerMgr *worker.WorkerManager
	if pipeline != nil {
		workerMgr = worker.NewWorkerManager(cfg.RAG.WorkerCount, pipeline, docRepo, cfg.RAG)
		workerMgr.Start(context.Background())
	} else {
		// Create a no-op worker manager that will set error status on jobs
		slog.Warn("worker manager not started — pipeline not available")
	}

	// ─── Search Engine (Phase 3) ───
	searchCache := rag.NewSearchCache(rdb)
	var searcher *rag.Searcher
	if swappableEmbedder.Provider() != nil && store != nil {
		searcher = rag.NewSearcher(swappableEmbedder, store, searchCache)
		slog.Info("search engine initialized")
	} else {
		slog.Warn("search engine not initialized — missing embedder or vector store")
	}

	// ─── Services ───
	authService := service.NewAuthService(userRepo, tokenRepo, jwtManager, rdb)
	hubService := service.NewHubService(hubRepo)
	// ─── File Storage (local or Google Drive) ───
	var fileStore storage.FileStorage
	if cfg.Storage.Provider == "gdrive" && cfg.Storage.GDriveKeyFile != "" {
		gd, err := storage.NewGDrive(cfg.Storage.GDriveKeyFile, cfg.Storage.GDriveFolderID)
		if err != nil {
			slog.Error("failed to init Google Drive storage", "error", err)
		} else {
			fileStore = gd
			slog.Info("file storage: Google Drive", "folder_id", cfg.Storage.GDriveFolderID)
		}
	}
	if fileStore == nil {
		fileStore = storage.NewLocal(cfg.RAG.UploadDir)
		slog.Info("file storage: local", "dir", cfg.RAG.UploadDir)
	}

	// ─── RAG Answerer ───
	// (LLM client was constructed earlier so the chunker could use it for
	// Contextual Retrieval enrichment.)
	var answerer *rag.Answerer
	if searcher != nil {
		answerer = rag.NewAnswerer(llmClient, searcher)
		slog.Info("RAG answer engine initialized")
	}

	docService := service.NewDocumentService(docRepo, hubRepo, workerMgr, store, fileStore, cfg.RAG.UploadDir, cfg.RAG.MaxFileSize)
	// CFG-07 M1 Phase 4 — wire audit repo cho action="document_reindex".
	docService.SetAuditRepo(auditRepo)
	docService.SetVersionRepo(docVersionRepo)
	searchService := service.NewSearchService(searcher, answerer, hubRepo)
	syncService := service.NewSyncService(syncRepo, hubRepo, userRepo)
	userService := service.NewUserService(userRepo, hubRepo)
	profileService := service.NewProfileService(userRepo)
	auditService := service.NewAuditService(auditRepo)
	apikeyService := service.NewAPIKeyService(apikeyRepo)

	// ─── Handlers ───
	authHandler := handler.NewAuthHandler(authService)
	hubHandler := handler.NewHubHandler(hubService)
	docHandler := handler.NewDocumentHandler(docService)
	// CFG-07 — getter mode runtime cho default query param khi reindex omit ?extractor=.
	docHandler.SetDefaultExtractorGetter(func() string { return cfg.RAG.Extractor })
	searchHandler := handler.NewSearchHandler(searchService)
	syncHandler := handler.NewSyncHandler(syncService)
	userHandler := handler.NewUserHandler(userService)
	profileHandler := handler.NewProfileHandler(profileService)
	auditHandler := handler.NewAuditHandler(auditService)
	apikeyHandler := handler.NewAPIKeyHandler(apikeyService)
	usageHandler := handler.NewUsageHandler(usageLogger, usageRealtime, usageStatsCache)

	// ─── Router ───
	r := router.Setup(cfg, jwtManager, rdb, authHandler, hubHandler, docHandler, searchHandler, syncHandler,
		userHandler, profileHandler, auditHandler, apikeyHandler, usageHandler, settingsRepo,
		hubRepo, store, llmClient, swappableEmbedder,
		// M1 Phase 4 (CFG-03, CFG-04) — admin endpoint extension
		doclingCircuit, doclingHealthProbe, auditRepo, pipeline)

	// ─── HTTP Server ───
	srv := &http.Server{
		Addr:         fmt.Sprintf(":%s", cfg.App.Port),
		Handler:      r,
		// Ingestion route có thể chạy vài phút (extractor + contextual chunker + augmenter
		// + embedding 200+ chunk). WriteTimeout 15s sẽ đóng kết nối giữa chừng và
		// cancel request context → augmenter goroutine fail đồng loạt với
		// "context deadline exceeded". Các tầng bên trong (Docling, LLM, augmenter)
		// đã có per-call timeout riêng nên không lo treo vô hạn.
		ReadTimeout:  60 * time.Second,
		WriteTimeout: 30 * time.Minute,
		IdleTimeout:  120 * time.Second,
	}

	// ─── Graceful Shutdown ───
	go func() {
		slog.Info("server starting", "addr", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server error", "error", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	slog.Info("shutting down server...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("server forced to shutdown", "error", err)
	}

	// Stop worker manager
	if workerMgr != nil {
		workerMgr.Shutdown()
	}

	slog.Info("server stopped")
}

func getEnvMain(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
