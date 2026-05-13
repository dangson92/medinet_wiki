package extractor

import (
	"strings"
	"unicode/utf8"
)

// renderTableAsProse converts a table (2D cell grid) into prose paragraphs,
// one paragraph per data row, formatted as "Header1: Value1. Header2: Value2. ...".
//
// Why prose and not markdown tables:
// recursive chunking splits on "\n" and later merges small pieces. Markdown table
// rows ("| A | B |") survive the split but their embeddings are dominated by the
// column-pipe noise and the header row is far from each data row — so a doctor
// profile row looks nothing like the query "bs Trần Hải Long". Prose rows keep
// field labels attached to values, so each row stands on its own as a searchable
// unit separated by blank lines (the strongest separator the chunker respects).
func renderTableAsProse(rows [][]string) string {
	var clean [][]string
	for _, r := range rows {
		if !rowIsEmpty(r) {
			clean = append(clean, r)
		}
	}
	if len(clean) == 0 {
		return ""
	}

	maxCols := 0
	for _, r := range clean {
		if len(r) > maxCols {
			maxCols = len(r)
		}
	}

	var out strings.Builder
	switch {
	case maxCols == 2:
		// 2-column tables are almost always key→value (field: value on each row)
		// rather than header+data. Emit each row as its own "Key: Value." sentence.
		for _, row := range clean {
			if line := rowAsKeyValue(row); line != "" {
				out.WriteString(line)
				out.WriteString("\n\n")
			}
		}
	case len(clean) > 1 && looksLikeHeader(clean[0]):
		header := clean[0]
		for _, row := range clean[1:] {
			if line := rowAsLabeledProse(header, row); line != "" {
				out.WriteString(line)
				out.WriteString("\n\n")
			}
		}
	default:
		for _, row := range clean {
			if line := rowAsFlatProse(row); line != "" {
				out.WriteString(line)
				out.WriteString("\n\n")
			}
		}
	}
	return strings.TrimRight(out.String(), "\n")
}

func rowAsKeyValue(row []string) string {
	if len(row) < 2 {
		return rowAsFlatProse(row)
	}
	key := strings.TrimSpace(row[0])
	val := strings.TrimSpace(row[1])
	if key == "" && val == "" {
		return ""
	}
	if key == "" {
		return val
	}
	if val == "" {
		return key
	}
	s := key + ": " + val
	if !strings.HasSuffix(s, ".") {
		s += "."
	}
	return s
}

func rowIsEmpty(row []string) bool {
	for _, c := range row {
		if strings.TrimSpace(c) != "" {
			return false
		}
	}
	return true
}

// looksLikeHeader: short non-empty cells (<= 60 runes), no sentence-ending period,
// at least 2 columns. Heuristic matches typical Vietnamese document headers like
// "Họ tên | Vai trò | Chuyên môn".
func looksLikeHeader(row []string) bool {
	if len(row) < 2 {
		return false
	}
	for _, c := range row {
		t := strings.TrimSpace(c)
		if t == "" {
			return false
		}
		if utf8.RuneCountInString(t) > 60 {
			return false
		}
		if strings.HasSuffix(t, ".") {
			return false
		}
	}
	return true
}

func rowAsLabeledProse(header, row []string) string {
	var parts []string
	for i, cell := range row {
		val := strings.TrimSpace(cell)
		if val == "" {
			continue
		}
		var key string
		if i < len(header) {
			key = strings.TrimSpace(header[i])
		}
		if key == "" || strings.Contains(val, ":") {
			parts = append(parts, val)
			continue
		}
		parts = append(parts, key+": "+val)
	}
	if len(parts) == 0 {
		return ""
	}
	s := strings.Join(parts, ". ")
	if !strings.HasSuffix(s, ".") {
		s += "."
	}
	return s
}

func rowAsFlatProse(row []string) string {
	var parts []string
	for _, c := range row {
		if t := strings.TrimSpace(c); t != "" {
			parts = append(parts, t)
		}
	}
	if len(parts) == 0 {
		return ""
	}
	return strings.Join(parts, " — ")
}
