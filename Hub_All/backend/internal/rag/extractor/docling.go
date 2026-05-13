// Package extractor — DoclingExtractor adapter.
//
// File này tạo ở Plan 03-02 (Phase 3 Wave 2) — implement HTTP client gọi
// service docling-pipeline (Phase 2 Python sidecar) qua REST POST /v1/process.
//
// Implement cả `Extractor` (legacy compat) và `StructuredExtractor` (Plan 03-01).
// Pipeline branch ở Plan 03-04 sẽ dùng type assertion `extractor.(StructuredExtractor)`
// kết hợp với cfg.RAG.Extractor == "docling" để bypass chunker Go khi có preChunks.
//
// Retry semantics: 3 attempts max — exponential backoff 1s, 2s giữa các lần.
// KHÔNG retry: 4xx (client error, vd 413 payload too large), 504 (server đã
// tự timeout), 2xx success. CHỈ retry: network error (Do() trả error) và 5xx
// khác (500/502/503).
//
// Mapping response → chunker.Chunk: xem CONTEXT Phase 3 mục "Chunk metadata mapping".
package extractor

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/medinet/hub-all-backend/internal/pkg/requestid"
	"github.com/medinet/hub-all-backend/internal/rag/chunker"
)

// DoclingKey là khóa đăng ký DoclingExtractor (KHÔNG phải extension như ".pdf").
// Pipeline branch theo cfg.RAG.Extractor == DoclingKey thay vì MIME match.
const DoclingKey = "docling"

// Default HTTP timeout (giây) khi NewDoclingExtractor được gọi với timeoutSec <= 0.
// Khớp với DOCLING_REQUEST_TIMEOUT_SEC server-side mặc định (Phase 2).
const defaultDoclingTimeoutSec = 180

// DoclingExtractor gọi service docling-pipeline qua HTTP để extract + chunk.
// Singleton an toàn dùng chung qua nhiều worker (http.Client thread-safe).
type DoclingExtractor struct {
	baseURL    string
	httpClient *http.Client
}

// NewDoclingExtractor khởi tạo từ config. timeoutSec là per-request HTTP timeout
// (khớp với DOCLING_REQUEST_TIMEOUT_SEC server-side để không cắt sớm hơn server).
func NewDoclingExtractor(baseURL string, timeoutSec int) *DoclingExtractor {
	if timeoutSec <= 0 {
		timeoutSec = defaultDoclingTimeoutSec
	}
	return &DoclingExtractor{
		baseURL: strings.TrimRight(baseURL, "/"),
		httpClient: &http.Client{
			Timeout: time.Duration(timeoutSec) * time.Second,
		},
	}
}

// SupportedType trả khóa registry (không phải extension file). Pipeline dùng
// để look up DoclingExtractor khi cfg.RAG.Extractor == "docling".
func (d *DoclingExtractor) SupportedType() string { return DoclingKey }

// Extract giữ tương thích Extractor cũ — gọi ExtractStructured rồi join Content.
// Đường cũ trong pipeline.go (chưa branch StructuredExtractor) vẫn nhận được
// text raw nếu lỡ resolve sai.
func (d *DoclingExtractor) Extract(ctx context.Context, filePath string) (string, error) {
	text, _, err := d.ExtractStructured(ctx, filePath)
	return text, err
}

// processChunkDTO khớp DSVC-02 schema (Phase 2 contract).
// CHÚ Ý: caption/table_html dùng pointer để phân biệt nil vs "" trong JSON.
type processChunkDTO struct {
	ChunkIndex int       `json:"chunk_index"`
	Text       string    `json:"text"`
	Headers    []string  `json:"headers"`
	Caption    *string   `json:"caption"`
	PageStart  int       `json:"page_start"`
	PageEnd    int       `json:"page_end"`
	IsTable    bool      `json:"is_table"`
	TableHTML  *string   `json:"table_html"`
	BBox       []float64 `json:"bbox"`
	TokenCount int       `json:"token_count"`
}

type processResponse struct {
	RequestID string            `json:"request_id"`
	DocMeta   map[string]any    `json:"doc_meta"`
	Chunks    []processChunkDTO `json:"chunks"`
}

// ExtractStructured upload file qua multipart/form-data sang POST /v1/process,
// retry exponential backoff (1s, 2s), parse JSON, map sang []chunker.Chunk.
//
// Trả về (text, preChunks, err). text = nối tất cả chunk.Content bằng "\n\n"
// để giữ tương thích đường cũ (pipeline.go chưa branch vẫn dùng được).
func (d *DoclingExtractor) ExtractStructured(ctx context.Context, filePath string) (string, []chunker.Chunk, error) {
	rid := requestid.From(ctx)

	// Closure build request — phải rebuild MỖI attempt vì io.Reader đã consume.
	buildReq := func() (*http.Request, error) {
		f, err := os.Open(filePath)
		if err != nil {
			return nil, fmt.Errorf("open file: %w", err)
		}
		defer f.Close()

		var buf bytes.Buffer
		mw := multipart.NewWriter(&buf)

		fw, err := mw.CreateFormFile("file", filepath.Base(filePath))
		if err != nil {
			return nil, fmt.Errorf("create form file: %w", err)
		}
		if _, err := io.Copy(fw, f); err != nil {
			return nil, fmt.Errorf("copy file body: %w", err)
		}

		if rid != "" {
			_ = mw.WriteField("request_id", rid)
		}
		// hub_code/doc_type — Plan 03-04 sẽ inject qua context.WithValue.
		// Plan 03-02 chỉ stub: nếu ctx có thì gửi, không có thì bỏ qua.
		if v, _ := ctx.Value(ctxHubCodeKey{}).(string); v != "" {
			_ = mw.WriteField("hub_code", v)
		}
		if v, _ := ctx.Value(ctxDocTypeKey{}).(string); v != "" {
			_ = mw.WriteField("doc_type", v)
		}
		// M1 Phase 4 (CFG-02) — propagate OCR languages tới sidecar Python.
		// Pipeline.go inject qua extractor.WithOCRLangs(ctx, cfg.RAG.DoclingOCRLangs).
		// Default "vie+eng" cho scanned PDF tiếng Việt (theo PROJECT.md core value).
		if v, _ := ctx.Value(ctxOCRLangsKey{}).(string); v != "" {
			_ = mw.WriteField("ocr_langs", v)
		}

		if err := mw.Close(); err != nil {
			return nil, fmt.Errorf("close multipart: %w", err)
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, d.baseURL+"/v1/process", &buf)
		if err != nil {
			return nil, fmt.Errorf("build request: %w", err)
		}
		req.Header.Set("Content-Type", mw.FormDataContentType())
		if rid != "" {
			req.Header.Set(requestid.HeaderName, rid)
		}
		return req, nil
	}

	// Retry loop — exponential 1s, 2s (chỉ sleep sau attempt 0 và 1, KHÔNG sau 2).
	const maxAttempts = 3
	backoffs := []time.Duration{1 * time.Second, 2 * time.Second}

	var (
		lastErr error
		resp    *http.Response
	)

	for attempt := 0; attempt < maxAttempts; attempt++ {
		if err := ctx.Err(); err != nil {
			return "", nil, err
		}

		req, err := buildReq()
		if err != nil {
			// KHÔNG retry lỗi build (file không mở được, ...).
			return "", nil, err
		}

		resp, lastErr = d.httpClient.Do(req)
		if lastErr == nil {
			// Success 2xx → break ra parse.
			if resp.StatusCode >= 200 && resp.StatusCode < 300 {
				break
			}

			// Đọc body (tối đa 2KB) để log + wrap error.
			body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
			resp.Body.Close()
			statusErr := fmt.Errorf("docling http %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))

			// 4xx (vd 413 payload too large): KHÔNG retry — fix bằng cách thay đổi input.
			if resp.StatusCode >= 400 && resp.StatusCode < 500 {
				return "", nil, fmt.Errorf("docling client error: %w", statusErr)
			}
			// 504 (server timeout): KHÔNG retry vì server đã hết giờ — retry càng tệ.
			if resp.StatusCode == http.StatusGatewayTimeout {
				return "", nil, fmt.Errorf("docling timeout: %w", statusErr)
			}
			// 5xx khác (500/502/503): retry.
			lastErr = statusErr
			resp = nil
		}

		// Sleep backoff, nhưng KHÔNG sleep sau attempt cuối.
		if attempt < len(backoffs) {
			slog.Warn("docling extractor retry",
				"attempt", attempt+1,
				"max", maxAttempts,
				"wait", backoffs[attempt],
				"error", lastErr,
				"request_id", rid,
			)
			select {
			case <-ctx.Done():
				return "", nil, ctx.Err()
			case <-time.After(backoffs[attempt]):
			}
		}
	}

	if resp == nil {
		return "", nil, fmt.Errorf("docling unreachable after %d attempts: %w", maxAttempts, lastErr)
	}
	defer resp.Body.Close()

	// Parse JSON response theo schema DSVC-02.
	var pr processResponse
	if err := json.NewDecoder(resp.Body).Decode(&pr); err != nil {
		return "", nil, fmt.Errorf("decode docling response: %w", err)
	}
	if len(pr.Chunks) == 0 {
		return "", nil, fmt.Errorf("docling returned 0 chunks for %q", filepath.Base(filePath))
	}

	// Map response.chunks → []chunker.Chunk.
	preChunks := make([]chunker.Chunk, 0, len(pr.Chunks))
	var textBuilder strings.Builder

	for _, c := range pr.Chunks {
		meta := map[string]any{
			"headers":    c.Headers,
			"page_start": c.PageStart,
			"page_end":   c.PageEnd,
			"is_table":   c.IsTable,
			"source":     "docling",
		}
		if c.Caption != nil {
			meta["caption"] = *c.Caption
		}
		if c.TableHTML != nil {
			meta["table_html"] = *c.TableHTML
		}
		if len(c.BBox) > 0 {
			meta["bbox"] = c.BBox
		}

		chunkType := "docling_text"
		if c.IsTable {
			chunkType = "docling_table"
		}

		preChunks = append(preChunks, chunker.Chunk{
			Index:      c.ChunkIndex,
			Content:    c.Text,
			TokenCount: c.TokenCount,
			ChunkType:  chunkType,
			Metadata:   meta,
		})

		if textBuilder.Len() > 0 {
			textBuilder.WriteString("\n\n")
		}
		textBuilder.WriteString(c.Text)
	}

	slog.Info("docling extracted",
		"doc", filepath.Base(filePath),
		"chunks", len(preChunks),
		"request_id", pr.RequestID,
	)

	return textBuilder.String(), preChunks, nil
}

// Context keys cho hub_code/doc_type/ocr_langs — pipeline inject trước khi vào DoclingExtractor.
// Dùng struct private để tránh collision khi context được propagate qua nhiều layer.
type ctxHubCodeKey struct{}
type ctxDocTypeKey struct{}
type ctxOCRLangsKey struct{}

// WithHubCode gắn hub_code vào ctx. Plan 03-04 gọi trước khi vào pipeline để
// DoclingExtractor đính kèm field multipart `hub_code` cho service Python log.
func WithHubCode(ctx context.Context, hubCode string) context.Context {
	return context.WithValue(ctx, ctxHubCodeKey{}, hubCode)
}

// WithDocType gắn doc_type vào ctx (vd "policy", "guide", "spec").
func WithDocType(ctx context.Context, docType string) context.Context {
	return context.WithValue(ctx, ctxDocTypeKey{}, docType)
}

// WithOCRLangs gắn ocr_langs (vd "vie+eng") vào ctx. M1 Phase 4 CFG-02 —
// pipeline.go đọc cfg.RAG.DoclingOCRLangs (qua setter SetDoclingOCRLangs)
// và inject vào ctx trước khi gọi ExtractStructured. DoclingExtractor sẽ
// đính field multipart `ocr_langs` cho sidecar Python.
func WithOCRLangs(ctx context.Context, langs string) context.Context {
	return context.WithValue(ctx, ctxOCRLangsKey{}, langs)
}

// Compile-time assertion — đảm bảo DoclingExtractor implement đúng cả 2 interface.
// Nếu vi phạm contract, build sẽ fail ngay tại đây thay vì runtime.
var (
	_ Extractor           = (*DoclingExtractor)(nil)
	_ StructuredExtractor = (*DoclingExtractor)(nil)
)
