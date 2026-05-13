package extractor

import (
	"context"
	"fmt"
	"os"
)

// TextExtractor handles plain text (.txt) files.
type TextExtractor struct{}

func (e *TextExtractor) SupportedType() string {
	return ".txt"
}

func (e *TextExtractor) Extract(ctx context.Context, filePath string) (string, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return "", fmt.Errorf("text extractor: failed to read file %q: %w", filePath, err)
	}
	return string(data), nil
}

// MarkdownExtractor handles Markdown (.md) files.
type MarkdownExtractor struct{}

func (e *MarkdownExtractor) SupportedType() string {
	return ".md"
}

func (e *MarkdownExtractor) Extract(ctx context.Context, filePath string) (string, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return "", fmt.Errorf("markdown extractor: failed to read file %q: %w", filePath, err)
	}
	return string(data), nil
}
