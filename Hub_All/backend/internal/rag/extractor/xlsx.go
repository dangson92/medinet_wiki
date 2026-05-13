package extractor

import (
	"context"
	"fmt"
	"strings"

	"github.com/xuri/excelize/v2"
)

// XlsxExtractor extracts structured Markdown from XLSX files.
// Each row becomes a context-rich text block with column headers attached.
// This ensures chunking preserves what each value means.
type XlsxExtractor struct{}

func (e *XlsxExtractor) SupportedType() string { return ".xlsx" }

func (e *XlsxExtractor) Extract(_ context.Context, filePath string) (string, error) {
	f, err := excelize.OpenFile(filePath)
	if err != nil {
		return "", fmt.Errorf("xlsx: open: %w", err)
	}
	defer f.Close()

	var result strings.Builder

	for sheetIdx, sheetName := range f.GetSheetList() {
		rows, err := f.GetRows(sheetName)
		if err != nil || len(rows) == 0 {
			continue
		}

		if sheetIdx > 0 {
			result.WriteString("\n\n")
		}
		result.WriteString("## Sheet: ")
		result.WriteString(sheetName)
		result.WriteString("\n\n")

		// First row = column headers
		headers := rows[0]

		// If only headers, output as table
		if len(rows) == 1 {
			result.WriteString("| ")
			result.WriteString(strings.Join(headers, " | "))
			result.WriteString(" |\n")
			continue
		}

		// For small tables (< 50 rows): output as Markdown table (good for search)
		if len(rows) <= 50 {
			result.WriteString(formatMarkdownTable(headers, rows[1:]))
			continue
		}

		// For large tables: output each row as a labeled text block
		// This gives chunker the ability to cut per row without losing column context
		for i, row := range rows[1:] {
			result.WriteString(fmt.Sprintf("### Dòng %d\n", i+1))
			for j, cell := range row {
				cell = strings.TrimSpace(cell)
				if cell == "" {
					continue
				}
				header := ""
				if j < len(headers) && strings.TrimSpace(headers[j]) != "" {
					header = strings.TrimSpace(headers[j])
				} else {
					header = fmt.Sprintf("Cột %d", j+1)
				}
				result.WriteString(fmt.Sprintf("- **%s**: %s\n", header, cell))
			}
			result.WriteString("\n")
		}
	}

	text := strings.TrimSpace(result.String())
	if text == "" {
		return "", fmt.Errorf("xlsx: no data extracted from %q", filePath)
	}
	return text, nil
}

func formatMarkdownTable(headers []string, dataRows [][]string) string {
	maxCols := len(headers)
	for _, row := range dataRows {
		if len(row) > maxCols {
			maxCols = len(row)
		}
	}
	// Pad headers
	for len(headers) < maxCols {
		headers = append(headers, fmt.Sprintf("Cột %d", len(headers)+1))
	}

	var b strings.Builder
	// Header row
	b.WriteString("| ")
	b.WriteString(strings.Join(headers, " | "))
	b.WriteString(" |\n")

	// Separator
	sep := make([]string, maxCols)
	for i := range sep {
		sep[i] = "---"
	}
	b.WriteString("| ")
	b.WriteString(strings.Join(sep, " | "))
	b.WriteString(" |\n")

	// Data rows
	for _, row := range dataRows {
		cells := make([]string, maxCols)
		for i := range cells {
			if i < len(row) {
				cells[i] = strings.TrimSpace(row[i])
			}
		}
		b.WriteString("| ")
		b.WriteString(strings.Join(cells, " | "))
		b.WriteString(" |\n")
	}

	return b.String()
}
