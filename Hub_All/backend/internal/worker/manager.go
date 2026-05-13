package worker

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/medinet/hub-all-backend/internal/config"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/requestid"
	"github.com/medinet/hub-all-backend/internal/rag"
	"github.com/medinet/hub-all-backend/internal/repository"
)

// EmbedJob represents a document embedding job.
type EmbedJob struct {
	DocumentID string
	DocName    string
	FilePath   string
	FileType   string
	HubCode    string
	Collection string
	// M1 Phase 3 — propagate request_id từ HTTP handler qua worker
	// xuống DoclingExtractor (HTTP header X-Request-Id). Trống nếu job
	// được seed từ retry/legacy — processJob sẽ tự gen UUID mới.
	RequestID string

	// CFG-07 M1 Phase 4 — reindex flow.
	// IsReindex = true nếu job xuất phát từ POST /api/documents/:id/reindex.
	// ForcedExtractor non-empty (docling|native|auto) → override extractorMode
	// global cho job này (admin chủ động force). Zero-value tương đương behavior
	// cũ — toàn bộ call site Upload/Compose KHÔNG cần đổi.
	IsReindex       bool
	ForcedExtractor string
}

// WorkerManager manages a pool of workers that process embedding jobs.
type WorkerManager struct {
	jobs     chan EmbedJob
	pipeline *rag.Pipeline
	docRepo  *repository.DocumentRepo
	workers  int
	wg       sync.WaitGroup
	cancel   context.CancelFunc

	// M1 Phase 3 — per-job timeout config (WIRE-04).
	extractorMode  string        // "docling" | "native" | "auto"
	defaultTimeout time.Duration // job native (extract Go in-process)
	doclingTimeout time.Duration // job docling (HTTP gọi sidecar Python)
}

// NewWorkerManager creates a new worker manager.
//
// ragCfg cung cấp Extractor mode + JobTimeout*Sec để xác định per-job
// context timeout (WIRE-04). Worker pool dùng parentCtx (không timeout)
// nhưng MỖI job có ctx.WithTimeout riêng — job timeout không kill worker.
func NewWorkerManager(workers int, pipeline *rag.Pipeline, docRepo *repository.DocumentRepo, ragCfg config.RAGConfig) *WorkerManager {
	if workers <= 0 {
		workers = 3
	}
	defTimeout := time.Duration(ragCfg.JobTimeoutDefaultSec) * time.Second
	if defTimeout <= 0 {
		defTimeout = 120 * time.Second
	}
	doclingTimeout := time.Duration(ragCfg.JobTimeoutDoclingSec) * time.Second
	if doclingTimeout <= 0 {
		doclingTimeout = 240 * time.Second
	}
	return &WorkerManager{
		jobs:           make(chan EmbedJob, workers*10),
		pipeline:       pipeline,
		docRepo:        docRepo,
		workers:        workers,
		extractorMode:  ragCfg.Extractor,
		defaultTimeout: defTimeout,
		doclingTimeout: doclingTimeout,
	}
}

// Start launches the worker goroutines.
func (m *WorkerManager) Start(ctx context.Context) {
	ctx, m.cancel = context.WithCancel(ctx)

	for i := 0; i < m.workers; i++ {
		m.wg.Add(1)
		go m.worker(ctx, i)
	}
	slog.Info("worker manager started", "workers", m.workers)
}

// Enqueue adds a job to the queue. Returns false if the queue is full.
func (m *WorkerManager) Enqueue(job EmbedJob) bool {
	select {
	case m.jobs <- job:
		slog.Info("job enqueued", "doc_id", job.DocumentID)
		return true
	default:
		slog.Warn("job queue full, dropping job", "doc_id", job.DocumentID)
		return false
	}
}

// Shutdown stops all workers and waits for them to finish.
func (m *WorkerManager) Shutdown() {
	slog.Info("shutting down worker manager...")
	if m.cancel != nil {
		m.cancel()
	}
	close(m.jobs)
	m.wg.Wait()
	slog.Info("worker manager stopped")
}

// worker is a single worker goroutine that processes jobs.
func (m *WorkerManager) worker(ctx context.Context, id int) {
	defer m.wg.Done()
	defer func() {
		if r := recover(); r != nil {
			slog.Error("worker panicked — restarting is not automatic; check the job queue",
				"worker_id", id, "panic", r)
		}
	}()
	slog.Info("worker started", "worker_id", id)

	for job := range m.jobs {
		m.processJob(ctx, job)
	}

	slog.Info("worker stopped", "worker_id", id)
}

// processJob handles a single embedding job.
//
// parentCtx là worker-level ctx (không timeout); MỖI job tự dẫn xuất jobCtx
// có timeout phân biệt theo extractorMode (WIRE-04). Khi job timeout, worker
// vẫn alive — tiếp nhận job kế. Các thao tác DB persist kết quả/lỗi dùng
// parentCtx để không bị cắt theo jobCtx.
func (m *WorkerManager) processJob(parentCtx context.Context, job EmbedJob) {
	docID, err := uuid.Parse(job.DocumentID)
	if err != nil {
		slog.Error("invalid document ID in job", "doc_id", job.DocumentID, "error", err)
		return
	}

	slog.Info("processing job", "doc_id", job.DocumentID, "extractor", m.extractorMode)

	// Update status to processing (parentCtx — không cần timeout job).
	if err := m.docRepo.UpdateStatus(parentCtx, docID, "processing", nil); err != nil {
		slog.Error("failed to update doc status to processing", "doc_id", job.DocumentID, "error", err)
		return
	}

	// ─── M1 Phase 3 — per-job timeout (WIRE-04) ───
	timeout := m.defaultTimeout
	if m.extractorMode == "docling" {
		timeout = m.doclingTimeout
	}
	jobCtx, cancel := context.WithTimeout(parentCtx, timeout)
	defer cancel()

	// ─── M1 Phase 3 — propagate request_id (WIRE-06) ───
	// Job seed/legacy có thể không có RequestID → gen UUID mới để vẫn có trace.
	rid := job.RequestID
	if rid == "" {
		rid = uuid.NewString()
	}
	jobCtx = requestid.With(jobCtx, rid)
	slog.Info("job ctx prepared",
		"doc_id", job.DocumentID,
		"extractor", m.extractorMode,
		"timeout", timeout,
		"request_id", rid,
	)

	// Set progress callback.
	// NOTE: multiple concurrent workers share a single pipeline.SetProgressFunc slot.
	// To avoid the wrong worker's captured docID being used, we parse docIDStr from
	// the callback parameter instead — the pipeline always passes the correct document
	// ID as the first argument, so the callback is correct regardless of which worker
	// last called SetProgressFunc.
	// Progress update dùng parentCtx — Postgres write nhanh, không cần bị cắt cùng job timeout.
	m.pipeline.SetProgressFunc(func(docIDStr string, progress int, stage string) {
		id, err := uuid.Parse(docIDStr)
		if err != nil {
			slog.Warn("invalid doc ID in progress callback", "doc_id", docIDStr)
			return
		}
		if err := m.docRepo.UpdateProgress(parentCtx, id, progress); err != nil {
			slog.Warn("failed to update progress", "doc_id", docIDStr, "error", err)
		}
	})

	// Run pipeline với jobCtx (timeout-bounded).
	// CFG-07: ForcedExtractor non-empty (reindex) override mode global cho job này.
	result, chunkResults, err := m.pipeline.ProcessWithChunks(
		jobCtx,
		job.DocumentID,
		job.DocName,
		job.FilePath,
		job.FileType,
		job.HubCode,
		job.Collection,
		job.ForcedExtractor,
	)
	if err != nil {
		var errMsg string
		if errors.Is(err, context.DeadlineExceeded) {
			errMsg = fmt.Sprintf("job timeout after %s (extractor=%s)", timeout, m.extractorMode)
			slog.Error("job timeout", "doc_id", job.DocumentID, "timeout", timeout, "extractor", m.extractorMode)
		} else {
			errMsg = err.Error()
			slog.Error("pipeline failed", "doc_id", job.DocumentID, "error", err)
		}
		// Update status dùng parentCtx (jobCtx có thể đã expire).
		if updateErr := m.docRepo.UpdateStatus(parentCtx, docID, "error", &errMsg); updateErr != nil {
			slog.Error("failed to update doc error status", "doc_id", job.DocumentID, "error", updateErr)
		}
		return
	}

	// Insert chunks into DB (parentCtx — đảm bảo lưu xong dù jobCtx đã cancel).
	if len(chunkResults) > 0 {
		dbChunks := make([]model.DocumentChunk, len(chunkResults))
		for i, cr := range chunkResults {
			chromaID := cr.ChromaID
			dbChunks[i] = model.DocumentChunk{
				ID:         cr.ID,
				DocumentID: cr.DocumentID,
				ChunkIndex: cr.ChunkIndex,
				Content:    cr.Content,
				TokenCount: cr.TokenCount,
				ChromaID:   &chromaID,
				Metadata:   cr.Metadata,
				CreatedAt:  time.Now().UTC(),
			}
		}
		if err := m.docRepo.BatchInsertChunks(parentCtx, dbChunks); err != nil {
			slog.Error("failed to insert chunks", "doc_id", job.DocumentID, "error", err)
			errMsg := "failed to save chunks: " + err.Error()
			_ = m.docRepo.UpdateStatus(parentCtx, docID, "error", &errMsg)
			return
		}
	}

	// CFG-06 — ghi extractor_used trước UpdateCompleted (parentCtx).
	// Non-fatal: nếu set fail chỉ log warn, không rollback ingestion vì document
	// đã ingest xong, metadata phụ không nên block hoàn tất.
	if result.ExtractorUsed != "" {
		if err := m.docRepo.SetExtractorUsed(parentCtx, docID, result.ExtractorUsed); err != nil {
			slog.Warn("set extractor_used failed (non-fatal)",
				"doc_id", job.DocumentID, "extractor", result.ExtractorUsed, "error", err)
		}
	}

	// Mark completed (parentCtx).
	if err := m.docRepo.UpdateCompleted(parentCtx, docID, result.ChunkCount); err != nil {
		slog.Error("failed to update doc completed status", "doc_id", job.DocumentID, "error", err)
		return
	}

	slog.Info("job completed",
		"doc_id", job.DocumentID,
		"chunk_count", result.ChunkCount,
		"extractor_used", result.ExtractorUsed,
		"is_reindex", job.IsReindex,
	)
}
