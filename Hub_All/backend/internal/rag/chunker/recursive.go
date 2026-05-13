package chunker

import (
	"regexp"
	"strings"
	"unicode/utf8"
)

// RecursiveChunker splits text using a recursive strategy with context preservation.
// Each chunk carries its parent heading to avoid losing context.
type RecursiveChunker struct{}

var _ Chunker = (*RecursiveChunker)(nil)

var reHeading = regexp.MustCompile(`(?m)^(#{1,6})\s+(.+)$`)
var reSentenceEnd = regexp.MustCompile(`([.!?。;:]\s)`)

// rePageMarker matches page-break headings inserted by the PDF extractor
// (e.g. "## Trang 2/5" or "## Page 2 / 5"). These are pagination artifacts,
// not semantic headings, and must not override real section context.
var rePageMarker = regexp.MustCompile(`(?i)^#{1,6}\s+(Trang|Page)\s+\d+\s*/\s*\d+\s*$`)

func isPageMarker(headingLine string) bool {
	return rePageMarker.MatchString(strings.TrimSpace(headingLine))
}

// MARKDOWN_SEPARATORS — ordered from largest to smallest semantic unit.
// Mirrors LangChain's RecursiveCharacterTextSplitter with MARKDOWN_SEPARATORS.
var markdownSeparators = []string{
	"\n# ",      // H1
	"\n## ",     // H2
	"\n### ",    // H3
	"\n#### ",   // H4
	"\n##### ",  // H5
	"\n###### ", // H6
	"```\n",     // Code block boundary
	"\n---\n",   // Horizontal rule
	"\n***\n",   // Horizontal rule variant
	"\n\n",      // Paragraph
	"\n",        // Line break
	". ",        // Sentence (period)
	"? ",        // Sentence (question)
	"! ",        // Sentence (exclamation)
	"; ",        // Clause (semicolon)
	", ",        // Clause (comma)
	" ",         // Word boundary
}

func (c *RecursiveChunker) Chunk(text string, opts ChunkOpts) []Chunk {
	opts = opts.Defaults()
	maxChars := TokensToChars(opts.MaxTokens)
	overlapChars := TokensToChars(opts.Overlap)

	// Parse into sections with their heading context
	sections := parseWithContext(text)

	// Split sections that exceed maxChars
	var enrichedChunks []enrichedChunk
	for _, sec := range sections {
		if len(sec.content) <= maxChars {
			enrichedChunks = append(enrichedChunks, sec)
		} else {
			enrichedChunks = append(enrichedChunks, splitSection(sec, maxChars)...)
		}
	}

	// Build final chunks with heading prefix + overlap
	return buildContextChunks(text, enrichedChunks, overlapChars)
}

// enrichedChunk holds content with its heading context.
type enrichedChunk struct {
	heading string // parent heading (e.g. "## Phác đồ trị đau dạ dày")
	content string // raw content of this section
}

// parseWithContext splits text by headings, tracking which heading each section belongs to.
// Page markers ("## Trang N/total") are filtered out as section boundaries — they stay
// inline in content so page info is preserved, but they don't override the real heading.
func parseWithContext(text string) []enrichedChunk {
	allLocs := reHeading.FindAllStringSubmatchIndex(text, -1)
	locs := make([][]int, 0, len(allLocs))
	for _, loc := range allLocs {
		if !isPageMarker(text[loc[0]:loc[1]]) {
			locs = append(locs, loc)
		}
	}
	if len(locs) == 0 {
		return []enrichedChunk{{content: strings.TrimSpace(text)}}
	}

	var sections []enrichedChunk
	currentHeading := ""

	// Content before first heading
	if locs[0][0] > 0 {
		pre := strings.TrimSpace(text[:locs[0][0]])
		if pre != "" {
			sections = append(sections, enrichedChunk{content: pre})
		}
	}

	for i, loc := range locs {
		// loc[0]:loc[1] = full match, loc[4]:loc[5] = heading text
		headingText := strings.TrimSpace(text[loc[0]:loc[1]])
		currentHeading = headingText

		// Content is from after heading line to next heading (or end)
		contentStart := loc[1]
		contentEnd := len(text)
		if i+1 < len(locs) {
			contentEnd = locs[i+1][0]
		}

		content := strings.TrimSpace(text[contentStart:contentEnd])
		if content != "" {
			sections = append(sections, enrichedChunk{
				heading: currentHeading,
				content: content,
			})
		} else {
			// Heading-only section (no content after it) — keep heading for context
			sections = append(sections, enrichedChunk{
				heading: currentHeading,
				content: headingText,
			})
		}
	}

	return sections
}

// splitSection splits a too-large section into smaller pieces,
// preserving the heading context on each piece.
func splitSection(sec enrichedChunk, maxChars int) []enrichedChunk {
	// Reserve space for heading prefix
	headingLen := 0
	if sec.heading != "" {
		headingLen = len(sec.heading) + 2 // heading + "\n\n"
	}
	effectiveMax := maxChars - headingLen
	if effectiveMax < 200 {
		effectiveMax = 200
	}

	pieces := splitRecursive(sec.content, effectiveMax)
	result := make([]enrichedChunk, len(pieces))
	for i, p := range pieces {
		result[i] = enrichedChunk{
			heading: sec.heading,
			content: p,
		}
	}
	return result
}

// splitRecursive tries each MARKDOWN_SEPARATOR in order (largest semantic unit first).
// If a separator produces multiple pieces, merge small ones back together.
// Falls back to hard character cut as last resort.
func splitRecursive(text string, maxChars int) []string {
	if len(text) <= maxChars {
		return []string{text}
	}

	// Try each separator in priority order
	for _, sep := range markdownSeparators {
		pieces := splitBySeparator(text, sep)
		if len(pieces) > 1 {
			merged := mergeSmallSections(pieces, maxChars)
			// Check if merging actually helped — if all merged pieces fit, return
			allFit := true
			for _, m := range merged {
				if len(m) > maxChars {
					allFit = false
					break
				}
			}
			if allFit {
				return merged
			}
			// Some pieces still too large — recursively split those
			var result []string
			for _, m := range merged {
				if len(m) > maxChars {
					result = append(result, splitRecursive(m, maxChars)...)
				} else {
					result = append(result, m)
				}
			}
			return result
		}
	}

	// Last resort: hard cut
	return hardCut(text, maxChars)
}

// splitBySeparator splits text by a separator string, keeping the separator
// with the piece that follows it (to preserve heading/list context).
func splitBySeparator(text string, sep string) []string {
	parts := strings.Split(text, sep)
	if len(parts) <= 1 {
		return parts
	}

	var result []string
	for i, p := range parts {
		trimmed := strings.TrimSpace(p)
		if trimmed == "" {
			continue
		}
		// Re-attach separator to subsequent pieces (preserve heading markers etc.)
		if i > 0 && strings.HasPrefix(sep, "\n") {
			trimmed = strings.TrimLeft(sep, "\n") + trimmed
		}
		result = append(result, trimmed)
	}
	return result
}

// mergeSmallSections merges small pieces together until approaching maxChars.
func mergeSmallSections(sections []string, maxChars int) []string {
	var result []string
	var current strings.Builder

	for _, section := range sections {
		if current.Len() == 0 {
			current.WriteString(section)
			continue
		}
		if current.Len()+2+len(section) <= maxChars {
			current.WriteString("\n\n")
			current.WriteString(section)
		} else {
			chunk := current.String()
			if len(chunk) > maxChars {
				result = append(result, splitRecursive(chunk, maxChars)...)
			} else {
				result = append(result, chunk)
			}
			current.Reset()
			current.WriteString(section)
		}
	}
	if current.Len() > 0 {
		chunk := current.String()
		if len(chunk) > maxChars {
			result = append(result, splitRecursive(chunk, maxChars)...)
		} else {
			result = append(result, chunk)
		}
	}
	return result
}

func hardCut(text string, maxChars int) []string {
	var result []string
	for len(text) > 0 {
		if len(text) <= maxChars {
			result = append(result, text)
			break
		}
		cutPoint := maxChars
		searchBack := maxChars / 5
		if searchBack < 10 {
			searchBack = 10
		}
		for i := cutPoint; i > cutPoint-searchBack && i > 0; i-- {
			if text[i] == ' ' || text[i] == '\n' {
				cutPoint = i
				break
			}
		}
		for cutPoint > 0 && !utf8.RuneStart(text[cutPoint]) {
			cutPoint--
		}
		result = append(result, strings.TrimSpace(text[:cutPoint]))
		text = strings.TrimSpace(text[cutPoint:])
	}
	return result
}

// buildContextChunks creates final Chunk structs.
// Each chunk gets its parent heading prepended for context preservation.
// Overlap takes the last complete sentence from the previous chunk.
func buildContextChunks(originalText string, enriched []enrichedChunk, overlapChars int) []Chunk {
	if len(enriched) == 0 {
		return nil
	}

	var chunks []Chunk
	searchStart := 0

	for i, ec := range enriched {
		// Build content with heading context
		var contentBuilder strings.Builder
		if ec.heading != "" && !strings.HasPrefix(ec.content, ec.heading) {
			contentBuilder.WriteString(ec.heading)
			contentBuilder.WriteString("\n\n")
		}

		// Add sentence overlap from previous chunk (same heading group)
		if i > 0 && overlapChars > 0 {
			prevContent := enriched[i-1].content
			overlap := extractLastSentences(prevContent, overlapChars)
			if overlap != "" {
				contentBuilder.WriteString(overlap)
				contentBuilder.WriteString("\n\n")
			}
		}

		contentBuilder.WriteString(ec.content)
		content := contentBuilder.String()

		// Find position in original text
		startChar := strings.Index(originalText[searchStart:], ec.content)
		if startChar >= 0 {
			startChar += searchStart
		} else {
			startChar = searchStart
		}
		endChar := startChar + len(ec.content)

		chunks = append(chunks, Chunk{
			Index:      i,
			Content:    content,
			TokenCount: EstimateTokens(content),
			StartChar:  startChar,
			EndChar:    endChar,
		})

		if endChar <= len(originalText) {
			searchStart = endChar
		}
	}

	return chunks
}

// extractLastSentences gets the last N chars of text, but aligned to sentence boundaries.
// This ensures overlap doesn't cut mid-sentence.
func extractLastSentences(text string, maxChars int) string {
	if len(text) <= maxChars {
		return ""
	}

	// Take last maxChars — căn về rune boundary để không cắt giữa multi-byte
	// rune (vd "ố" = 3 byte). Nếu cắt giữa rune, tail sẽ bắt đầu bằng
	// continuation byte (0x80–0xBF) → invalid UTF-8 → PG từ chối khi insert.
	startByte := len(text) - maxChars
	for startByte < len(text) && !utf8.RuneStart(text[startByte]) {
		startByte++
	}
	tail := text[startByte:]

	// Find first sentence boundary in tail to align
	idx := reSentenceEnd.FindStringIndex(tail)
	if idx != nil {
		tail = strings.TrimSpace(tail[idx[1]:])
	} else {
		// No sentence boundary — find first space
		if spaceIdx := strings.IndexByte(tail, ' '); spaceIdx >= 0 {
			tail = strings.TrimSpace(tail[spaceIdx+1:])
		}
	}

	if tail == "" || tail == text {
		return ""
	}
	return tail
}
