package extractor

import (
	"context"
	"fmt"
	"strings"

	"github.com/medinet/hub-all-backend/internal/rag/chunker"
)

// Extractor defines the interface for extracting text from files.
type Extractor interface {
	// Extract reads the file at filePath and returns its text content.
	Extract(ctx context.Context, filePath string) (string, error)
	// SupportedType returns the file extension this extractor handles (e.g. ".pdf").
	SupportedType() string
}

// StructuredExtractor là extension interface cho extractor có khả năng trả về
// pre-chunks giàu metadata (Docling). Implementor PHẢI cũng implement Extractor
// để giữ tương thích với pipeline đường cũ. Pipeline branch theo type assertion
// `extractor.(StructuredExtractor)` trong pipeline.go.
//
// Map sang chunker.Chunk: text Markdown → Content; headers/page_start/page_end/
// is_table/table_html/bbox/caption → Metadata (xem CONTEXT Phase 3 mục
// "Chunk metadata mapping").
//
// Chỉ DoclingExtractor implement interface này — extractor Go cũ giữ nguyên
// chỉ implement Extractor, làm fallback khi RAG_EXTRACTOR=native hoặc Docling fail.
type StructuredExtractor interface {
	Extractor
	ExtractStructured(ctx context.Context, filePath string) (text string, preChunks []chunker.Chunk, err error)
}

var registry map[string]Extractor

func init() {
	extractors := []Extractor{
		&TextExtractor{},
		&MarkdownExtractor{},
		&PDFExtractor{},
		&DocxExtractor{},
		&XlsxExtractor{},
		&PptxExtractor{},
		&CSVExtractor{},
		&HTMLExtractor{},
	}

	registry = make(map[string]Extractor, len(extractors))
	for _, e := range extractors {
		registry[e.SupportedType()] = e
	}
}

// ForType returns an extractor for the given file type (e.g. ".pdf", ".docx").
// The fileType is matched case-insensitively.
func ForType(fileType string) (Extractor, error) {
	ft := strings.ToLower(strings.TrimSpace(fileType))
	if !strings.HasPrefix(ft, ".") {
		ft = "." + ft
	}

	e, ok := registry[ft]
	if !ok {
		return nil, fmt.Errorf("unsupported file type %q: no extractor registered", fileType)
	}
	return e, nil
}

// SupportedTypes returns all file extensions that have a registered extractor.
func SupportedTypes() []string {
	types := make([]string, 0, len(registry))
	for t := range registry {
		types = append(types, t)
	}
	return types
}
