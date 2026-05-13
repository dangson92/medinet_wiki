package extractor

import (
	"bytes"
	"context"
	"fmt"
	"regexp"
	"strings"
	"unicode/utf8"

	"github.com/ledongthuc/pdf"
)

// PDFExtractor extracts structured text from PDF files.
// Each page becomes a section with page number context.
// Tabular regions are rebuilt from row/column positions and emitted as
// prose paragraphs so each row stays semantically whole under chunking.
type PDFExtractor struct{}

func (e *PDFExtractor) SupportedType() string { return ".pdf" }

func (e *PDFExtractor) Extract(_ context.Context, filePath string) (string, error) {
	f, r, err := pdf.Open(filePath)
	if err != nil {
		return "", fmt.Errorf("pdf open: %w", err)
	}
	defer f.Close()

	var result strings.Builder
	totalPages := r.NumPage()

	for i := 1; i <= totalPages; i++ {
		p := r.Page(i)
		if p.V.IsNull() {
			continue
		}

		body := extractPageBody(p)
		if strings.TrimSpace(body) == "" {
			continue
		}

		if totalPages > 1 {
			result.WriteString(fmt.Sprintf("## Trang %d/%d\n\n", i, totalPages))
		}
		result.WriteString(body)
		result.WriteString("\n\n")
	}

	text := strings.TrimSpace(result.String())
	if text == "" {
		return "", fmt.Errorf("pdf: no text extracted from %q (scanned PDF?)", filePath)
	}
	return text, nil
}

// extractPageBody reconstructs a page using row/column layout so that table
// cells can be grouped back into rows and emitted as prose. Non-table lines
// fall through to the heading-aware cleaner unchanged.
func extractPageBody(p pdf.Page) string {
	rows, err := p.GetTextByRow()
	if err != nil || len(rows) == 0 {
		text, _ := p.GetPlainText(nil)
		return cleanPDFText(text)
	}

	var raw strings.Builder
	var tableBuf [][]string
	flushTable := func() {
		switch {
		case len(tableBuf) >= 2:
			if prose := renderTableAsProse(tableBuf); prose != "" {
				raw.WriteString("\n\n")
				raw.WriteString(prose)
				raw.WriteString("\n\n")
			}
		case len(tableBuf) == 1:
			raw.WriteString(strings.Join(tableBuf[0], " "))
			raw.WriteString("\n")
		}
		tableBuf = tableBuf[:0]
	}

	for _, row := range rows {
		if row == nil || len(row.Content) == 0 {
			continue
		}
		cells := rowContentToCells(row.Content)
		if len(cells) == 0 {
			continue
		}
		if len(cells) >= 2 {
			tableBuf = append(tableBuf, cells)
			continue
		}
		flushTable()
		raw.WriteString(cells[0])
		raw.WriteString("\n")
	}
	flushTable()

	return cleanPDFText(raw.String())
}

// rowContentToCells groups Text items on the same row into cells by X-gap.
// A gap larger than cellGapThreshold points between the right edge of one
// item and the left edge of the next is treated as a column break.
func rowContentToCells(items []pdf.Text) []string {
	if len(items) == 0 {
		return nil
	}
	const cellGapThreshold = 15.0

	var cells []string
	var cur strings.Builder
	cur.WriteString(items[0].S)
	prevEnd := textEndX(items[0])

	for i := 1; i < len(items); i++ {
		t := items[i]
		gap := t.X - prevEnd
		switch {
		case gap > cellGapThreshold:
			if s := strings.TrimSpace(cur.String()); s != "" {
				cells = append(cells, s)
			}
			cur.Reset()
		case gap > 1 && !endsWithSpace(cur):
			cur.WriteString(" ")
		}
		cur.WriteString(t.S)
		prevEnd = textEndX(t)
	}
	if s := strings.TrimSpace(cur.String()); s != "" {
		cells = append(cells, s)
	}
	return cells
}

func textEndX(t pdf.Text) float64 {
	if t.W > 0 {
		return t.X + t.W
	}
	fs := t.FontSize
	if fs <= 0 {
		fs = 10
	}
	return t.X + float64(utf8.RuneCountInString(t.S))*fs*0.5
}

func endsWithSpace(b strings.Builder) bool {
	s := b.String()
	if s == "" {
		return false
	}
	r, _ := utf8.DecodeLastRuneInString(s)
	return r == ' '
}

// cleanPDFText converts plain PDF text to structured Markdown.
// Detects headings from: ALL CAPS lines, numbered sections, short standalone titles.
func cleanPDFText(text string) string {
	var buf bytes.Buffer
	lines := strings.Split(text, "\n")
	prevEmpty := false

	for _, line := range lines {
		trimmed := strings.TrimSpace(line)

		if trimmed == "" {
			if !prevEmpty {
				buf.WriteString("\n\n")
				prevEmpty = true
			}
			continue
		}
		prevEmpty = false

		headingLevel := detectHeading(trimmed)
		if headingLevel > 0 {
			buf.WriteString("\n\n")
			buf.WriteString(strings.Repeat("#", headingLevel))
			buf.WriteString(" ")
			if trimmed == strings.ToUpper(trimmed) && len([]rune(trimmed)) > 3 {
				buf.WriteString(toTitleCase(trimmed))
			} else {
				buf.WriteString(trimmed)
			}
			buf.WriteString("\n\n")
			continue
		}

		buf.WriteString(trimmed)
		buf.WriteString("\n")
	}

	return strings.TrimSpace(buf.String())
}

// detectHeading returns heading level (1-3) or 0 if not a heading.
func detectHeading(line string) int {
	runes := []rune(line)
	lineLen := len(runes)

	// Too long for a heading
	if lineLen > 100 {
		return 0
	}

	// Already markdown heading
	if strings.HasPrefix(line, "# ") || strings.HasPrefix(line, "## ") || strings.HasPrefix(line, "### ") {
		return 0 // already formatted
	}

	// ALL CAPS line (>3 chars, no digits) → H2
	if lineLen > 3 && lineLen < 80 && line == strings.ToUpper(line) && !strings.ContainsAny(line, "0123456789|{}[]()") {
		return 2
	}

	// Numbered section: "1.", "2.", "1.1", "1.1.", "10."
	if reNumberedSection.MatchString(line) {
		// Count dots to determine depth
		parts := strings.SplitN(line, " ", 2)
		numPart := strings.TrimRight(parts[0], ".")
		dots := strings.Count(numPart, ".")
		if dots == 0 {
			return 2 // "1. Title" → ##
		}
		return 3 // "1.1 Title" → ###
	}

	// Roman numeral: "I.", "II.", "III.", "IV.", "V."
	if reRomanSection.MatchString(line) {
		return 2
	}

	// Short standalone line (< 50 chars, no period at end, starts with uppercase)
	// Likely a section title: "Tóm tắt", "Kết luận", "Tài liệu tham khảo"
	if lineLen >= 3 && lineLen <= 50 && !strings.HasSuffix(line, ".") && !strings.HasSuffix(line, ",") {
		firstRune := runes[0]
		if firstRune >= 'A' && firstRune <= 'Z' || firstRune >= 0x00C0 && firstRune <= 0x1EF9 {
			// Check it's not a normal sentence fragment (has no lowercase start of next word pattern)
			words := strings.Fields(line)
			if len(words) <= 8 {
				return 3
			}
		}
	}

	return 0
}

var reNumberedSection = regexp.MustCompile(`^(\d{1,2}\.)+\s*\d*\.?\s+[A-ZÀ-Ỹ]`)
var reRomanSection = regexp.MustCompile(`^(I{1,3}|IV|V|VI{0,3}|IX|X{0,3})\.?\s+[A-ZÀ-Ỹ]`)

// toTitleCase converts "ALL CAPS TEXT" to "All Caps Text".
func toTitleCase(s string) string {
	words := strings.Fields(strings.ToLower(s))
	for i, w := range words {
		if len(w) > 0 {
			words[i] = strings.ToUpper(w[:1]) + w[1:]
		}
	}
	return strings.Join(words, " ")
}
