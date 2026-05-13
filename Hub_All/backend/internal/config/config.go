package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	App       AppConfig
	DB        DBConfig
	Redis     RedisConfig
	Chroma    ChromaConfig
	JWT       JWTConfig
	AES       AESConfig
	CORS      CORSConfig
	RateLimit RateLimitConfig
	RAG       RAGConfig
	Storage   StorageConfig
}

type StorageConfig struct {
	Provider         string // "local" or "gdrive"
	GDriveKeyFile    string // path to service account JSON
	GDriveFolderID   string // root folder ID on Google Drive
}

type RAGConfig struct {
	EmbeddingProvider string // "openai" or "gemini"
	EmbeddingModel    string
	EmbeddingAPIKey   string
	ChunkSize         int
	ChunkOverlap      int
	BatchSize         int
	WorkerCount       int
	MaxFileSize       int64  // bytes
	UploadDir         string

	// M1 Phase 3 — Docling adapter (WIRE-01)
	// Extractor: "native" (default, đường cũ qua extractor Go) | "docling" (gọi sidecar Python)
	// "auto" sẽ được Phase 4 (CFG-01) thêm cùng circuit breaker.
	Extractor         string
	DoclingServiceURL string // env DOCLING_SERVICE_URL, default "http://localhost:8001"
	DoclingTimeoutSec int    // env DOCLING_TIMEOUT_SEC, default 180

	// M1 Phase 3 — Worker per-job timeout (WIRE-04).
	// Phân biệt mode để job Docling không bị cắt sớm khi sidecar chunk PDF lớn.
	JobTimeoutDefaultSec int // env JOB_TIMEOUT_DEFAULT_SEC, default 120s — extract Go in-process.
	JobTimeoutDoclingSec int // env JOB_TIMEOUT_DOCLING_SEC, default 240s — gấp đôi DOCLING_TIMEOUT_SEC để buffer 2 lần retry HTTP.

	// M1 Phase 4 — Circuit breaker cho Docling extractor (CFG-01, CFG-04).
	// Threshold: số lần consecutive failure trước khi open circuit.
	// Cooldown: số phút giữ open trước khi half-open thử lại.
	DoclingFailThreshold uint32 // env DOCLING_FAIL_THRESHOLD, default 3.
	DoclingCooldownMin   int    // env DOCLING_COOLDOWN_MIN, default 5.
	DoclingOCRLangs      string // env DOCLING_OCR_LANGS, default "vie+eng" (CFG-02).
}

type AppConfig struct {
	Env  string
	Port string
}

type DBConfig struct {
	Host         string
	Port         int
	Name         string
	User         string
	Password     string
	SSLMode      string
	MaxOpenConns int
	MaxIdleConns int
}

func (c DBConfig) DSN() string {
	return fmt.Sprintf(
		"postgres://%s:%s@%s:%d/%s?sslmode=%s",
		c.User, c.Password, c.Host, c.Port, c.Name, c.SSLMode,
	)
}

type RedisConfig struct {
	URL      string
	Password string
}

type ChromaConfig struct {
	URL   string
	Token string
}

type JWTConfig struct {
	PrivateKeyPath  string
	PublicKeyPath   string
	AccessTokenTTL  time.Duration
	RefreshTokenTTL time.Duration
}

type AESConfig struct {
	Key string
}

type CORSConfig struct {
	AllowedOrigins string
}

type RateLimitConfig struct {
	RPS   int
	Burst int
}

func Load() (*Config, error) {
	dbPort, _ := strconv.Atoi(getEnv("DB_PORT", "5432"))
	maxOpen, _ := strconv.Atoi(getEnv("DB_MAX_OPEN_CONNS", "25"))
	maxIdle, _ := strconv.Atoi(getEnv("DB_MAX_IDLE_CONNS", "5"))
	rps, _ := strconv.Atoi(getEnv("RATE_LIMIT_RPS", "10"))
	burst, _ := strconv.Atoi(getEnv("RATE_LIMIT_BURST", "20"))

	accessTTL, err := time.ParseDuration(getEnv("JWT_ACCESS_TOKEN_TTL", "15m"))
	if err != nil {
		accessTTL = 15 * time.Minute
	}
	refreshTTL, err := time.ParseDuration(getEnv("JWT_REFRESH_TOKEN_TTL", "168h"))
	if err != nil {
		refreshTTL = 7 * 24 * time.Hour
	}

	chunkSize, _ := strconv.Atoi(getEnv("RAG_CHUNK_SIZE", "512"))
	chunkOverlap, _ := strconv.Atoi(getEnv("RAG_CHUNK_OVERLAP", "50"))
	ragBatchSize, _ := strconv.Atoi(getEnv("RAG_BATCH_SIZE", "100"))
	ragWorkerCount, _ := strconv.Atoi(getEnv("RAG_WORKER_COUNT", "3"))
	ragMaxFileSize, _ := strconv.ParseInt(getEnv("RAG_MAX_FILE_SIZE", "52428800"), 10, 64)
	doclingTimeoutSec, _ := strconv.Atoi(getEnv("DOCLING_TIMEOUT_SEC", "180"))
	// Default 600s (10 phút) đủ cho file 400+ chunk có augmenter LLM (Q&A + keywords) +
	// contextual chunker chạy. Trước đây là 120s — quá ngắn, gây cancel hàng loạt
	// goroutine LLM ở giữa pipeline.
	jobTimeoutDefaultSec, _ := strconv.Atoi(getEnv("JOB_TIMEOUT_DEFAULT_SEC", "600"))
	jobTimeoutDoclingSec, _ := strconv.Atoi(getEnv("JOB_TIMEOUT_DOCLING_SEC", "900"))

	// M1 Phase 4 — Circuit breaker (CFG-01, CFG-04).
	doclingFailThreshold, _ := strconv.Atoi(getEnv("DOCLING_FAIL_THRESHOLD", "3"))
	if doclingFailThreshold <= 0 {
		doclingFailThreshold = 3
	}
	doclingCooldownMin, _ := strconv.Atoi(getEnv("DOCLING_COOLDOWN_MIN", "5"))
	if doclingCooldownMin <= 0 {
		doclingCooldownMin = 5
	}

	// Determine embedding API key based on provider
	ragProvider := getEnv("RAG_EMBEDDING_PROVIDER", "openai")
	ragAPIKey := getEnv("OPENAI_API_KEY", "")
	if ragProvider == "gemini" {
		ragAPIKey = getEnv("GEMINI_API_KEY", "")
	}

	cfg := &Config{
		App: AppConfig{
			Env:  getEnv("APP_ENV", "development"),
			Port: getEnv("APP_PORT", "8180"),
		},
		DB: DBConfig{
			Host:         getEnv("DB_HOST", "localhost"),
			Port:         dbPort,
			Name:         getEnv("DB_NAME", "medinet_central"),
			User:         getEnv("DB_USER", "medinet"),
			Password:     getEnv("DB_PASSWORD", ""),
			SSLMode:      getEnv("DB_SSL_MODE", "disable"),
			MaxOpenConns: maxOpen,
			MaxIdleConns: maxIdle,
		},
		Redis: RedisConfig{
			URL:      getEnv("REDIS_URL", "redis://localhost:6379/0"),
			Password: getEnv("REDIS_PASSWORD", ""),
		},
		Chroma: ChromaConfig{
			URL:   getEnv("CHROMA_URL", "http://localhost:8000"),
			Token: getEnv("CHROMA_TOKEN", ""),
		},
		JWT: JWTConfig{
			PrivateKeyPath:  getEnv("JWT_PRIVATE_KEY_PATH", "./keys/private.pem"),
			PublicKeyPath:   getEnv("JWT_PUBLIC_KEY_PATH", "./keys/public.pem"),
			AccessTokenTTL:  accessTTL,
			RefreshTokenTTL: refreshTTL,
		},
		AES: AESConfig{
			Key: getEnv("AES_KEY", ""),
		},
		CORS: CORSConfig{
			AllowedOrigins: getEnv("CORS_ALLOWED_ORIGINS", "http://localhost:5173"),
		},
		RateLimit: RateLimitConfig{
			RPS:   rps,
			Burst: burst,
		},
		RAG: RAGConfig{
			EmbeddingProvider: ragProvider,
			EmbeddingModel:    getEnv("RAG_EMBEDDING_MODEL", "text-embedding-3-small"),
			EmbeddingAPIKey:   ragAPIKey,
			ChunkSize:         chunkSize,
			ChunkOverlap:      chunkOverlap,
			BatchSize:         ragBatchSize,
			WorkerCount:       ragWorkerCount,
			MaxFileSize:       ragMaxFileSize,
			UploadDir:         getEnv("RAG_UPLOAD_DIR", "./uploads"),
			Extractor:         getEnv("RAG_EXTRACTOR", "native"),
			DoclingServiceURL: getEnv("DOCLING_SERVICE_URL", "http://localhost:8001"),
			DoclingTimeoutSec: doclingTimeoutSec,
			JobTimeoutDefaultSec: jobTimeoutDefaultSec,
			JobTimeoutDoclingSec: jobTimeoutDoclingSec,
			DoclingFailThreshold: uint32(doclingFailThreshold),
			DoclingCooldownMin:   doclingCooldownMin,
			DoclingOCRLangs:      getEnv("DOCLING_OCR_LANGS", "vie+eng"),
		},
		Storage: StorageConfig{
			Provider:       getEnv("STORAGE_PROVIDER", "local"),
			GDriveKeyFile:  getEnv("GDRIVE_KEY_FILE", ""),
			GDriveFolderID: getEnv("GDRIVE_FOLDER_ID", ""),
		},
	}

	if cfg.DB.Password == "" {
		return nil, fmt.Errorf("DB_PASSWORD is required")
	}

	return cfg, nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
