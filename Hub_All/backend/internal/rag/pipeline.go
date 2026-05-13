package rag

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"regexp"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/medinet/hub-all-backend/internal/embedding"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/pkg/requestid"
	"github.com/medinet/hub-all-backend/internal/rag/augmenter"
	"github.com/medinet/hub-all-backend/internal/rag/chunker"
	"github.com/medinet/hub-all-backend/internal/rag/extractor"
	"github.com/medinet/hub-all-backend/internal/vectorstore"
	"github.com/sony/gobreaker/v2"
)

// AuditInserter là subset 1-method của *repository.AuditRepo dùng cho fallback audit.
// Dùng interface (thay vì import package repository) để tránh cycle import + dễ mock test.
type AuditInserter interface {
	Insert(ctx context.Context, entry *model.AuditLogEntry) error
}

// ProgressFunc is called to report pipeline progress.
type ProgressFunc func(docID string, progress int, stage string)

// ProcessResult holds the output of a successful pipeline run.
type ProcessResult struct {
	ChunkCount int
	// CFG-06 M1 Phase 4 — extractor đã THẬT SỰ chạy thành công cuối cùng
	// (không phải mode gọi vào). Khi mode="auto" rồi fallback → "native";
	// khi Docling success → "docling". Worker dùng giá trị này gọi
	// docRepo.SetExtractorUsed trước UpdateCompleted.
	ExtractorUsed string
}

// Pipeline orchestrates text extraction, chunking, embedding, and vector storage.
type Pipeline struct {
	embedder   embedding.EmbeddingProvider
	store      vectorstore.VectorStore
	chunker    chunker.Chunker
	chunkOpts  chunker.ChunkOpts
	batchSize  int
	augmenter  *augmenter.Augmenter // optional — nil disables auto-Q&A augmentation
	onProgress ProgressFunc

	// M1 Phase 3 — Docling adapter (optional). nil → luôn dùng extractor Go cũ.
	doclingExt    extractor.StructuredExtractor
	extractorMode string // "docling" | "native" | "auto" — Phase 4 sẽ thêm circuit breaker cho "auto".

	// M1 Phase 4 (CFG-01, CFG-02, CFG-05) — circuit breaker + audit fallback + OCR langs cho mode "auto".
	// Tất cả nullable: nếu nil → mode "auto" suy biến về native (không có circuit
	// = không bao giờ thử Docling = an toàn; audit nil = không log nhưng pipeline
	// vẫn chạy). main.go ALWAYS wire khi Phase 4 deploy.
	circuit         *extractor.DoclingCircuit
	auditRepo       AuditInserter
	doclingOCRLangs string // default "vie+eng" — set qua SetDoclingOCRLangs.
}

// SetAugmenter attaches an optional chunk augmenter (RAGFlow-style auto Q&A
// and keyword enrichment). Pass nil to disable. Safe to call before/after
// pipeline construction; runs between chunking and embedding.
func (p *Pipeline) SetAugmenter(a *augmenter.Augmenter) {
	p.augmenter = a
}

// SetDoclingExtractor wire Docling adapter + chế độ extractor. Pass nil để
// disable (mặc định pipeline chạy đường extractor.ForType cũ). Mode != "docling"
// sẽ KHÔNG dispatch sang Docling kể cả khi adapter đã được set — an toàn để
// gọi unconditional ở main.go.
func (p *Pipeline) SetDoclingExtractor(d extractor.StructuredExtractor, mode string) {
	p.doclingExt = d
	p.extractorMode = mode
}

// SetDoclingCircuit attach circuit breaker cho mode "auto" (Phase 4 CFG-01).
// Pass nil để disable — mode "auto" sẽ chạy như native (KHÔNG bao giờ thử Docling).
func (p *Pipeline) SetDoclingCircuit(c *extractor.DoclingCircuit) {
	p.circuit = c
}

// SetAuditInserter attach audit inserter để log fallback events (Phase 4 CFG-05).
// Production: pass *repository.AuditRepo. Test: pass mock thoả AuditInserter.
func (p *Pipeline) SetAuditInserter(r AuditInserter) {
	p.auditRepo = r
}

// SetExtractorMode hot-swap mode runtime mà không cần rebind doclingExt.
// Dùng từ admin endpoint PUT /api/rag-config (Phase 4 CFG-03, CFG-04).
// KHÔNG mutex — accept eventual consistency (CONTEXT Rủi ro 1: in-flight jobs vẫn
// hoàn tất với mode cũ, ~vài giây sau đồng bộ).
func (p *Pipeline) SetExtractorMode(mode string) {
	p.extractorMode = mode
}

// SetDoclingOCRLangs set OCR language code (vd "vie+eng") truyền cho sidecar
// qua multipart field "ocr_langs" (Phase 4 CFG-02).
func (p *Pipeline) SetDoclingOCRLangs(langs string) {
	p.doclingOCRLangs = langs
}

// NewPipeline creates a new RAG pipeline.
func NewPipeline(
	embedder embedding.EmbeddingProvider,
	store vectorstore.VectorStore,
	chunkr chunker.Chunker,
	chunkOpts chunker.ChunkOpts,
	batchSize int,
) *Pipeline {
	if batchSize <= 0 {
		batchSize = 100
	}
	return &Pipeline{
		embedder:  embedder,
		store:     store,
		chunker:   chunkr,
		chunkOpts: chunkOpts,
		batchSize: batchSize,
	}
}

// SetProgressFunc sets the progress callback.
func (p *Pipeline) SetProgressFunc(fn ProgressFunc) {
	p.onProgress = fn
}

// reportProgress calls the progress callback if set.
func (p *Pipeline) reportProgress(docID string, progress int, stage string) {
	if p.onProgress != nil {
		p.onProgress(docID, progress, stage)
	}
}

// extractAndChunk chạy Stage 1 (extract) + Stage 2 (chunk hoặc skip nếu Docling).
// Stage progress: 0→10 extract, 10→40 chunk/skip + augment.
//
// Branch theo mode (đã resolve ở Process — caller có thể override mode global
// qua tham số `mode`, ví dụ reindex job với ForcedExtractor):
//   - "docling" + p.doclingExt != nil → ExtractStructured() → preChunks → SKIP chunker Go.
//   - "auto" + p.doclingExt != nil + p.circuit != nil → thử Docling, fallback native.
//   - Else → đường cũ: extractor.ForType(fileType) → chunker.Chunk().
//
// Trả thêm `extractorUsed` ("docling"|"native") phản ánh extractor đã THẬT SỰ
// chạy thành công (CFG-06). Khi auto-fallback → "native"; khi auto-success → "docling".
func (p *Pipeline) extractAndChunk(
	ctx context.Context, docID, docName, filePath, fileType, hubCode, mode string,
) ([]chunker.Chunk, string, error) {
	p.reportProgress(docID, 0, "extracting")

	// ─── Branch "auto" (Phase 4 CFG-01): thử Docling qua circuit breaker, fallback native ───
	if mode == "auto" && p.doclingExt != nil && p.circuit != nil {
		callCtx := extractor.WithHubCode(ctx, hubCode)
		callCtx = extractor.WithDocType(callCtx, fileType)
		callCtx = extractor.WithOCRLangs(callCtx, p.doclingOCRLangs) // CFG-02

		var doclingChunks []chunker.Chunk

		cbErr := p.circuit.Execute(func() error {
			_, chunks, err := p.doclingExt.ExtractStructured(callCtx, filePath)
			if err != nil {
				return err
			}
			if len(chunks) == 0 {
				return fmt.Errorf("docling returned 0 chunks")
			}
			doclingChunks = chunks
			return nil
		})

		if cbErr == nil {
			// SUCCESS — đường Docling.
			p.reportProgress(docID, 10, "extracted")
			slog.Info("auto-mode: docling success",
				"doc_id", docID, "doc_name", docName, "items", len(doclingChunks))
			p.reportProgress(docID, 40, "chunked")
			if p.augmenter != nil {
				p.reportProgress(docID, 40, "augmenting")
				doclingChunks = p.augmenter.Augment(ctx, doclingChunks)
			}
			return doclingChunks, "docling", nil
		}

		// FAILURE — fallback native + audit.
		reason := classifyFailureReason(cbErr)
		slog.Warn("auto-mode: docling failed, falling back to native",
			"doc_id", docID, "reason", reason, "err", cbErr,
			"circuit_state", p.circuit.State().String())
		p.auditFallback(ctx, docID, hubCode, reason, cbErr)
		// Đi tiếp xuống đường native bên dưới — extractor_used sẽ = "native".
	}

	// ─── Branch "docling" (hard mode) ───
	if mode == "docling" && p.doclingExt != nil {
		// Inject hub_code + doc_type + ocr_langs vào ctx để DoclingExtractor gắn vào multipart form.
		callCtx := extractor.WithHubCode(ctx, hubCode)
		callCtx = extractor.WithDocType(callCtx, fileType)
		callCtx = extractor.WithOCRLangs(callCtx, p.doclingOCRLangs) // CFG-02

		_, preChunks, err := p.doclingExt.ExtractStructured(callCtx, filePath)
		if err != nil {
			return nil, "", fmt.Errorf("docling extract: %w", err)
		}
		p.reportProgress(docID, 10, "extracted")

		if len(preChunks) == 0 {
			return nil, "", fmt.Errorf("docling returned 0 chunks")
		}
		slog.Info("skipping Go chunker, using Docling preChunks",
			"doc_id", docID, "doc_name", docName, "items", len(preChunks))

		p.reportProgress(docID, 40, "chunked")

		// Augmenter VẪN chạy nếu bật — augmenter Go làm Q&A enrichment, không phụ thuộc nguồn.
		if p.augmenter != nil {
			p.reportProgress(docID, 40, "augmenting")
			preChunks = p.augmenter.Augment(ctx, preChunks)
		}
		return preChunks, "docling", nil
	}

	// ─── Đường cũ: extractor Go theo MIME → chunker Go (extractor_used = "native") ───
	ext, err := extractor.ForType(fileType)
	if err != nil {
		return nil, "", fmt.Errorf("get extractor: %w", err)
	}
	rawText, err := ext.Extract(ctx, filePath)
	if err != nil {
		return nil, "", fmt.Errorf("extract text: %w", err)
	}
	text := sanitizeText(rawText)
	if len(text) == 0 {
		return nil, "", fmt.Errorf("extracted text is empty")
	}
	p.reportProgress(docID, 10, "extracted")
	slog.Info("text extracted", "doc_id", docID, "chars", len(text))

	p.reportProgress(docID, 10, "chunking")
	chunks := p.chunker.Chunk(text, p.chunkOpts)
	if len(chunks) == 0 {
		return nil, "", fmt.Errorf("chunking produced zero chunks")
	}
	p.reportProgress(docID, 40, "chunked")
	slog.Info("text chunked", "doc_id", docID, "chunks", len(chunks))

	if p.augmenter != nil {
		p.reportProgress(docID, 40, "augmenting")
		chunks = p.augmenter.Augment(ctx, chunks)
	}
	return chunks, "native", nil
}

// resolveExtractorMode chọn mode runtime cho job. ForcedExtractor non-empty
// (CFG-07 reindex) override mode global cho job đó. Trả mode đã validate
// fallback "auto" nếu không hợp lệ — caller chỉ cần pass thẳng job field.
func (p *Pipeline) resolveExtractorMode(override string) string {
	if override != "" {
		switch override {
		case "docling", "native", "auto":
			return override
		}
	}
	return p.extractorMode
}

// Process runs the full RAG pipeline for a document.
//
// extractorOverride (CFG-07): nếu non-empty (docling|native|auto) sẽ override
// mode global p.extractorMode cho riêng job này. Reindex job admin truyền vào
// để force mode mà không thay state pipeline. Pass "" cho behavior cũ.
func (p *Pipeline) Process(ctx context.Context, docID, docName, filePath, fileType, hubCode, collection, extractorOverride string) (*ProcessResult, error) {
	mode := p.resolveExtractorMode(extractorOverride)
	slog.Info("pipeline started", "doc_id", docID, "doc_name", docName, "file_type", fileType, "collection", collection, "extractor_mode", mode, "override", extractorOverride)

	// ─── Stage 1+2: Extract + Chunk (0-40%) — branch theo extractor mode ───
	chunks, extractorUsed, err := p.extractAndChunk(ctx, docID, docName, filePath, fileType, hubCode, mode)
	if err != nil {
		return nil, err
	}

	// ─── Stage 3: Embed chunks in batches (40-80%) ───
	p.reportProgress(docID, 40, "embedding")

	// Ensure collection exists
	if err := p.store.CreateCollection(ctx, collection); err != nil {
		return nil, fmt.Errorf("create collection: %w", err)
	}

	// Pre-flight dimension check — fails fast BEFORE spending tokens on embedding
	// if the current provider's vector dimension doesn't match what the collection
	// already holds. Returns 0 for empty collections (no lock yet → always ok).
	if existingDim, dimErr := p.store.CollectionDimension(ctx, collection); dimErr == nil && existingDim > 0 {
		if currentDim := p.embedder.Dimension(); currentDim > 0 && currentDim != existingDim {
			return nil, fmt.Errorf(
				"pre-flight dimension mismatch: collection %q already has %dD vectors "+
					"but the current embedding provider (%s) produces %dD vectors. "+
					"Go to Settings → Khi nạp tài liệu → Vector hóa and select a model "+
					"with %d dimensions, or delete the hub's collection to re-embed everything",
				collection, existingDim, p.embedder.ModelName(), currentDim, existingDim)
		}
	}

	totalBatches := int(math.Ceil(float64(len(chunks)) / float64(p.batchSize)))
	var vecDocs []vectorstore.VectorDocument

	for batchIdx := 0; batchIdx < totalBatches; batchIdx++ {
		// Rate limit: wait between batches to avoid 429
		if batchIdx > 0 {
			time.Sleep(2 * time.Second)
		}
		start := batchIdx * p.batchSize
		end := start + p.batchSize
		if end > len(chunks) {
			end = len(chunks)
		}

		batchChunks := chunks[start:end]
		texts := make([]string, len(batchChunks))
		for i, ch := range batchChunks {
			texts[i] = ch.Content
		}

		// Embed with retry
		var vectors [][]float32
		err := retryWithBackoff(ctx, 10, 2*time.Second, func() error {
			var embedErr error
			vectors, embedErr = p.embedder.Embed(ctx, texts)
			return embedErr
		})
		if err != nil {
			return nil, fmt.Errorf("embed batch %d: %w", batchIdx, err)
		}

		for i, ch := range batchChunks {
			chromaID := fmt.Sprintf("%s_chunk_%d", docID, ch.Index)
			meta := buildChunkMetadata(docID, docName, hubCode, ch)
			vecDocs = append(vecDocs, vectorstore.VectorDocument{
				ID:        chromaID,
				Content:   ch.Content,
				Embedding: vectors[i],
				Metadata:  meta,
			})
		}

		// Report progress between 40% and 80%.
		progress := 40 + int(float64(batchIdx+1)/float64(totalBatches)*40)
		if progress > 80 {
			progress = 80
		}
		p.reportProgress(docID, progress, "embedding")
	}

	slog.Info("chunks embedded", "doc_id", docID, "vectors", len(vecDocs))

	// ─── Stage 4: Store in ChromaDB (80-100%) ───
	p.reportProgress(docID, 80, "storing")

	// Upsert in batches to avoid oversized requests.
	for i := 0; i < len(vecDocs); i += p.batchSize {
		end := i + p.batchSize
		if end > len(vecDocs) {
			end = len(vecDocs)
		}
		if err := p.store.Upsert(ctx, collection, vecDocs[i:end]); err != nil {
			errStr := err.Error()
			if strings.Contains(errStr, "dimension") && strings.Contains(errStr, "got") {
				return nil, fmt.Errorf(
					"embedding dimension mismatch: the current embedding provider produces vectors "+
						"that differ from what the ChromaDB collection already holds. "+
						"Go to Settings → Khi nạp tài liệu → Vector hóa and select the provider/model "+
						"used when documents were originally ingested in this hub. "+
						"Original error: %w", err)
			}
			return nil, fmt.Errorf("upsert batch: %w", err)
		}
	}

	p.reportProgress(docID, 100, "completed")
	slog.Info("pipeline completed", "doc_id", docID, "chunk_count", len(chunks), "extractor_used", extractorUsed)

	return &ProcessResult{ChunkCount: len(chunks), ExtractorUsed: extractorUsed}, nil
}

// ChunkResult holds a chunk along with its generated IDs for DB storage.
type ChunkResult struct {
	ID         uuid.UUID
	DocumentID uuid.UUID
	ChunkIndex int
	Content    string
	TokenCount int
	ChromaID   string
	Metadata   map[string]interface{}
}

// ProcessWithChunks runs the pipeline and also returns chunk details for DB insertion.
//
// extractorOverride (CFG-07): xem doc Process. Pass "" cho behavior cũ.
func (p *Pipeline) ProcessWithChunks(ctx context.Context, docID, docName, filePath, fileType, hubCode, collection, extractorOverride string) (*ProcessResult, []ChunkResult, error) {
	mode := p.resolveExtractorMode(extractorOverride)
	slog.Info("pipeline started", "doc_id", docID, "file_type", fileType, "collection", collection, "extractor_mode", mode, "override", extractorOverride)

	docUUID, err := uuid.Parse(docID)
	if err != nil {
		return nil, nil, fmt.Errorf("parse doc ID: %w", err)
	}

	// ─── Stage 1+2: Extract + Chunk (0-40%) — branch theo extractor mode ───
	chunks, extractorUsed, err := p.extractAndChunk(ctx, docID, docName, filePath, fileType, hubCode, mode)
	if err != nil {
		return nil, nil, err
	}

	// ─── Stage 3: Embed chunks in batches (40-80%) ───
	p.reportProgress(docID, 40, "embedding")

	if err := p.store.CreateCollection(ctx, collection); err != nil {
		return nil, nil, fmt.Errorf("create collection: %w", err)
	}

	// Pre-flight dimension check — see Process() for rationale.
	{
		existingDim, dimErr := p.store.CollectionDimension(ctx, collection)
		currentDim := p.embedder.Dimension()
		slog.Info("pre-flight dimension probe",
			"collection", collection,
			"existing_dim", existingDim,
			"current_dim", currentDim,
			"probe_error", dimErr,
		)
		if dimErr == nil && existingDim > 0 && currentDim > 0 && currentDim != existingDim {
			return nil, nil, fmt.Errorf(
				"pre-flight dimension mismatch: collection %q already has %dD vectors "+
					"but the current embedding provider (%s) produces %dD vectors. "+
					"Go to Settings → Khi nạp tài liệu → Vector hóa and select a model "+
					"with %d dimensions, or delete the hub's collection to re-embed everything",
				collection, existingDim, p.embedder.ModelName(), currentDim, existingDim)
		}
	}

	totalBatches := int(math.Ceil(float64(len(chunks)) / float64(p.batchSize)))
	var vecDocs []vectorstore.VectorDocument
	var chunkResults []ChunkResult

	for batchIdx := 0; batchIdx < totalBatches; batchIdx++ {
		// Rate limit: wait between batches to avoid 429
		if batchIdx > 0 {
			time.Sleep(2 * time.Second)
		}
		start := batchIdx * p.batchSize
		end := start + p.batchSize
		if end > len(chunks) {
			end = len(chunks)
		}

		batchChunks := chunks[start:end]
		texts := make([]string, len(batchChunks))
		for i, ch := range batchChunks {
			texts[i] = ch.Content
		}

		var vectors [][]float32
		err := retryWithBackoff(ctx, 10, 2*time.Second, func() error {
			var embedErr error
			vectors, embedErr = p.embedder.Embed(ctx, texts)
			return embedErr
		})
		if err != nil {
			return nil, nil, fmt.Errorf("embed batch %d: %w", batchIdx, err)
		}

		for i, ch := range batchChunks {
			chromaID := fmt.Sprintf("%s_chunk_%d", docID, ch.Index)
			meta := buildChunkMetadata(docID, docName, hubCode, ch)
			vecDocs = append(vecDocs, vectorstore.VectorDocument{
				ID:        chromaID,
				Content:   ch.Content,
				Embedding: vectors[i],
				Metadata:  meta,
			})

			// DB chunk metadata — keep it small (scalar values only) to avoid
			// PG jsonb bloat. Full metadata lives in ChromaDB.
			dbMeta := map[string]interface{}{
				"hub_code":   hubCode,
				"start_char": ch.StartChar,
				"end_char":   ch.EndChar,
			}
			if ch.ChunkType != "" {
				dbMeta["chunk_type"] = ch.ChunkType
			}
			if ch.ParentID != "" {
				dbMeta["parent_id"] = ch.ParentID
			}
			if ch.AlwaysInclude {
				dbMeta["always_include"] = true
			}
			// M1 Phase 3 — propagate Docling metadata vào Postgres JSONB
			// (headers, page_start/end, is_table, table_html, bbox, caption, source).
			// Phase 5 eval sẽ query qua các field này. JSONB chấp nhận mọi type
			// Go encode được sang JSON (bao gồm []float64 bbox).
			for k, v := range ch.Metadata {
				if _, exists := dbMeta[k]; exists {
					continue
				}
				dbMeta[k] = v
			}

			chunkResults = append(chunkResults, ChunkResult{
				ID:         uuid.New(),
				DocumentID: docUUID,
				ChunkIndex: ch.Index,
				Content:    ch.Content,
				TokenCount: ch.TokenCount,
				ChromaID:   chromaID,
				Metadata:   dbMeta,
			})
		}

		progress := 40 + int(float64(batchIdx+1)/float64(totalBatches)*40)
		if progress > 80 {
			progress = 80
		}
		p.reportProgress(docID, progress, "embedding")
	}

	// ─── Stage 4: Store in ChromaDB (80-100%) ───
	p.reportProgress(docID, 80, "storing")

	for i := 0; i < len(vecDocs); i += p.batchSize {
		end := i + p.batchSize
		if end > len(vecDocs) {
			end = len(vecDocs)
		}
		if err := p.store.Upsert(ctx, collection, vecDocs[i:end]); err != nil {
			errStr := err.Error()
			if strings.Contains(errStr, "dimension") && strings.Contains(errStr, "got") {
				return nil, nil, fmt.Errorf(
					"embedding dimension mismatch: the current embedding provider produces vectors "+
						"that differ from what the ChromaDB collection already holds. "+
						"Go to Settings → Khi nạp tài liệu → Vector hóa and select the provider/model "+
						"used when documents were originally ingested in this hub. "+
						"Original error: %w", err)
			}
			return nil, nil, fmt.Errorf("upsert batch: %w", err)
		}
	}

	p.reportProgress(docID, 100, "completed")
	slog.Info("pipeline completed", "doc_id", docID, "chunk_count", len(chunks), "extractor_used", extractorUsed)

	return &ProcessResult{ChunkCount: len(chunks), ExtractorUsed: extractorUsed}, chunkResults, nil
}

// Pre-compiled regex patterns for sanitizeText (avoid recompiling per document).
var (
	reTrailing  = regexp.MustCompile(`([.,:;!?)\]"'…])([ấắằẳẵặđếềểễệốồổỗộớờởỡợứừửữựõýỳỷỹỵ])\s*\n`)
	reTrailing2 = regexp.MustCompile(`([a-zA-ZÀ-ỹ]{2,})([ấắằẳẵặđếềểễệốồổỗộớờởỡợứừửữựõýỳỷỹỵ])\n`)
	reJoinedOx  = regexp.MustCompile(`([a-zà-ỹ]{3,})õ([a-zà-ỹ]{3,})`)
	reJoinLines = regexp.MustCompile(`([a-zA-ZÀ-ỹ])\n([a-zà-ỹ])`)
	reStrayLine = regexp.MustCompile(`(?m)^[ấắằẳẵặếềểễệốồổỗộớờởỡợứừửữựõđ]{1,2}\s*$`)
	reSpaces    = regexp.MustCompile(`[ \t]+`)
	reNewlines  = regexp.MustCompile(`\n{3,}`)
)

// classifyFailureReason map error sang string lý do cho audit log (Phase 4 CFG-05).
// Reason cố định để admin grep/aggregate dễ trên dashboard `audit_logs WHERE action='rag_fallback'`.
func classifyFailureReason(err error) string {
	if err == nil {
		return ""
	}
	if errors.Is(err, gobreaker.ErrOpenState) {
		return "docling_circuit_open"
	}
	if errors.Is(err, gobreaker.ErrTooManyRequests) {
		return "docling_circuit_half_open_busy"
	}
	msg := err.Error()
	switch {
	case strings.Contains(msg, "timeout") || strings.Contains(msg, "deadline"):
		return "docling_timeout"
	case strings.Contains(msg, "0 chunks"):
		return "docling_empty_response"
	case strings.Contains(msg, "client error") || strings.Contains(msg, "http 4"):
		return "docling_client_error"
	default:
		return "docling_error"
	}
}

// auditFallback ghi 1 row audit_logs khi pipeline rơi từ Docling sang native.
// Best-effort: lỗi insert chỉ log warn, KHÔNG fail pipeline (ingestion ưu tiên).
// Dùng requestid.From(ctx) — KHÔNG đọc raw key string ctx.Value("request_id")
// vì package requestid set bằng custom ctxKey type, raw string sẽ luôn trả "".
func (p *Pipeline) auditFallback(ctx context.Context, docID, hubCode, reason string, originalErr error) {
	if p.auditRepo == nil {
		return
	}
	reqID := requestid.From(ctx)

	payload := map[string]any{
		"document_id":    docID,
		"hub_code":       hubCode,
		"reason":         reason,
		"request_id":     reqID,
		"extractor_from": "docling",
		"extractor_to":   "native",
		"error":          originalErr.Error(),
	}
	if p.circuit != nil {
		payload["circuit_state"] = p.circuit.State().String()
		payload["consecutive_fails"] = p.circuit.Counts().ConsecutiveFailures
	}

	payloadJSON, err := json.Marshal(payload)
	if err != nil {
		slog.Warn("audit fallback: marshal payload failed", "err", err)
		return
	}

	systemUser := "system"
	entry := &model.AuditLogEntry{
		ID:        uuid.New(),
		Timestamp: time.Now().UTC(),
		UserName:  &systemUser,
		IsAI:      false,
		Action:    "rag_fallback",
		Payload:   payloadJSON,
	}
	if err := p.auditRepo.Insert(ctx, entry); err != nil {
		slog.Warn("audit fallback: insert failed", "err", err, "doc_id", docID)
	}
}

// sanitizeText cleans PDF-extracted Vietnamese text.
func sanitizeText(s string) string {
	// 1. Remove null bytes
	s = strings.Map(func(r rune) rune {
		if r == 0 {
			return -1
		}
		return r
	}, s)

	// 2. Remove single stray diacritic at end of line
	s = reTrailing.ReplaceAllString(s, "$1\n")

	// Also catch: letter + stray diacritic + newline
	s = reTrailing2.ReplaceAllStringFunc(s, func(m string) string {
		runes := []rune(m)
		if len(runes) < 3 {
			return m
		}
		return string(runes[:len(runes)-2]) + "\n"
	})

	// 3. Fix words joined with stray "õ" (PDF artifact)
	s = reJoinedOx.ReplaceAllString(s, "$1 $2")

	// 4. Join broken lines (word split across line break)
	s = reJoinLines.ReplaceAllStringFunc(s, func(m string) string {
		return strings.Replace(m, "\n", " ", 1)
	})

	// 5. Remove standalone diacritic lines
	s = reStrayLine.ReplaceAllString(s, "")

	// 6. Normalize whitespace
	s = reSpaces.ReplaceAllString(s, " ")
	s = reNewlines.ReplaceAllString(s, "\n\n")

	return strings.TrimSpace(s)
}

// buildChunkMetadata assembles the metadata map stored alongside a vector in
// ChromaDB. It merges:
//   - Pipeline-level fields (document_id, document_name, hub_code, chunk_index,
//     token_count, start_char, end_char)
//   - Chunk-level v3 fields (chunk_type, parent_id, always_include)
//   - Chunker-supplied metadata (entity_name, doc_type, level, tier, ...)
//
// Scalar-only values are kept so ChromaDB's metadata filter stays functional.
// Slice values are collapsed to comma-joined strings.
func buildChunkMetadata(docID, docName, hubCode string, ch chunker.Chunk) map[string]any {
	meta := map[string]any{
		"document_id":   docID,
		"document_name": docName,
		"chunk_index":   ch.Index,
		"hub_code":      hubCode,
		"token_count":   ch.TokenCount,
		"start_char":    ch.StartChar,
		"end_char":      ch.EndChar,
	}
	if ch.ChunkType != "" {
		meta["chunk_type"] = ch.ChunkType
	}
	if ch.ParentID != "" {
		meta["parent_id"] = ch.ParentID
	}
	if ch.AlwaysInclude {
		meta["always_include"] = true
	}
	for k, v := range ch.Metadata {
		if _, exists := meta[k]; exists {
			continue
		}
		switch val := v.(type) {
		case string, int, int32, int64, float32, float64, bool:
			meta[k] = val
		case []string:
			meta[k] = strings.Join(val, ",")
		case []float64:
			// bbox / numeric arrays — Chroma metadata không filter được, chỉ giữ
			// trong Postgres JSONB (xem dbMeta merge ở ProcessWithChunks).
		default:
			// Unsupported type — skip to keep the metadata flat/filterable.
		}
	}
	return meta
}

// retryWithBackoff retries fn up to maxRetries times with exponential backoff.
func retryWithBackoff(ctx context.Context, maxRetries int, baseDelay time.Duration, fn func() error) error {
	var lastErr error
	for attempt := 0; attempt <= maxRetries; attempt++ {
		if err := ctx.Err(); err != nil {
			return err
		}

		lastErr = fn()
		if lastErr == nil {
			return nil
		}

		if attempt < maxRetries {
			delay := baseDelay * time.Duration(1<<uint(attempt))

			// If rate limited (429), wait longer
			errMsg := lastErr.Error()
			if strings.Contains(errMsg, "429") || strings.Contains(errMsg, "RESOURCE_EXHAUSTED") {
				delay = 30 * time.Second // wait 30s for rate limit reset
			}

			slog.Warn("retrying after error", "attempt", attempt+1, "delay", delay, "error", lastErr)

			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(delay):
			}
		}
	}
	return fmt.Errorf("after %d retries: %w", maxRetries, lastErr)
}
