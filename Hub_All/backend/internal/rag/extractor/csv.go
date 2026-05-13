package extractor

import (
	"context"
	"encoding/csv"
	"fmt"
	"os"
	"strings"
)

// CSVExtractor handles CSV files.
type CSVExtractor struct{}

func (e *CSVExtractor) SupportedType() string {
	return ".csv"
}

func (e *CSVExtractor) Extract(_ context.Context, filePath string) (string, error) {
	f, err := os.Open(filePath)
	if err != nil {
		return "", fmt.Errorf("csv extractor: failed to open %q: %w", filePath, err)
	}
	defer f.Close()

	reader := csv.NewReader(f)
	reader.LazyQuotes = true
	reader.FieldsPerRecord = -1 // Allow variable number of fields.

	records, err := reader.ReadAll()
	if err != nil {
		return "", fmt.Errorf("csv extractor: failed to parse %q: %w", filePath, err)
	}

	var result strings.Builder
	for i, record := range records {
		if i > 0 {
			result.WriteString("\n")
		}
		result.WriteString(strings.Join(record, " | "))
	}

	return result.String(), nil
}
