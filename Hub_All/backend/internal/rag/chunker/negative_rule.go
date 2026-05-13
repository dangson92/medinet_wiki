package chunker

import (
	"regexp"
	"strings"
)

// NegativeRuleExtractor implements Level 5 from RAG Pipeline v3:
// scan the entire document for "forbidden" / "never do" patterns and
// aggregate them into dedicated chunks flagged AlwaysInclude=true.
//
// These chunks MUST be injected into every retrieval context that touches
// the same document / hub, regardless of query similarity. The retrieval
// engine reads Chunk.AlwaysInclude (or metadata["always_include"]) to
// decide whether to inject.
type NegativeRuleExtractor struct {
	// MaxChunkTokens bounds each aggregated chunk. When exceeded, rules
	// are split into multiple always_include chunks.
	MaxChunkTokens int
}

// Patterns that identify a negative/forbidden rule line.
var negativeRulePatterns = []*regexp.Regexp{
	regexp.MustCompile(`(?i)^\s*[✖✗×x]\s*(TUYỆT ĐỐI|KHÔNG)`),
	regexp.MustCompile(`(?i)(TUYỆT ĐỐI KHÔNG|KHÔNG ĐƯỢC|KHÔNG BAO GIỜ|CẤM|NGHIÊM CẤM)`),
	regexp.MustCompile(`(?i)^\s*LỖI\s*\d*\s*[:：]`),
	regexp.MustCompile(`(?i)^\s*[-•]\s*KHÔNG\b`),
}

// Extract scans the input text and returns zero or more negative-rule chunks.
// Each line that matches any pattern is collected along with its immediate
// surrounding context (the previous non-empty line acts as a section tag).
//
// The returned chunks all carry:
//
//	ChunkType     = "negative_rule"
//	AlwaysInclude = true
//	Metadata["priority"] = "critical"
//
// If no negative rules are found, Extract returns nil.
func (e *NegativeRuleExtractor) Extract(text string) []Chunk {
	maxTokens := e.MaxChunkTokens
	if maxTokens <= 0 {
		maxTokens = 600
	}

	lines := strings.Split(text, "\n")
	lastHeading := ""
	var collected []string

	for _, raw := range lines {
		line := strings.TrimSpace(raw)
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "#") {
			lastHeading = strings.TrimLeft(line, "# ")
			continue
		}

		if matchesAnyNegative(line) {
			prefix := ""
			if lastHeading != "" {
				prefix = "[" + lastHeading + "] "
			}
			collected = append(collected, prefix+line)
		}
	}

	if len(collected) == 0 {
		return nil
	}

	return e.pack(collected, maxTokens)
}

func (e *NegativeRuleExtractor) pack(lines []string, maxTokens int) []Chunk {
	header := "⚠️ QUY TẮC CẤM — NEGATIVE RULES (luôn áp dụng)\n\n"
	var chunks []Chunk
	var buf strings.Builder
	buf.WriteString(header)
	idx := 0

	flush := func() {
		content := strings.TrimRight(buf.String(), "\n ")
		if content == "" || content == strings.TrimSpace(header) {
			return
		}
		chunks = append(chunks, Chunk{
			Index:         idx,
			Content:       content,
			TokenCount:    CountTokens(content),
			ChunkType:     "negative_rule",
			AlwaysInclude: true,
			Metadata: map[string]any{
				"priority":       "critical",
				"always_include": true,
				"rule_type":      "negative",
				"level":          "L5",
			},
		})
		idx++
		buf.Reset()
		buf.WriteString(header)
	}

	for _, line := range lines {
		candidate := buf.String() + "- " + line + "\n"
		if CountTokens(candidate) > maxTokens && buf.Len() > len(header) {
			flush()
		}
		buf.WriteString("- ")
		buf.WriteString(line)
		buf.WriteString("\n")
	}
	flush()

	return chunks
}

func matchesAnyNegative(line string) bool {
	for _, re := range negativeRulePatterns {
		if re.MatchString(line) {
			return true
		}
	}
	return false
}
