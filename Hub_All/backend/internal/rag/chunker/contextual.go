package chunker

import (
	"context"
	"fmt"
	"log/slog"
	"regexp"
	"strings"
	"time"
)

// reLeadingHeading matches chunks whose very first non-blank line is a
// markdown heading (# … ######). Such chunks already carry section context
// from the recursive chunker and do not benefit from LLM enrichment.
var reLeadingHeading = regexp.MustCompile(`\A\s*#{1,6}\s+\S`)

// shouldSkipEnrich returns true when a chunk does not need LLM-generated
// context. We skip three cases:
//  1. Chunk already has an explicit contextual header (e.g. entity profile
//     or a previous enrichment pass).
//  2. Parent chunks in a hierarchical split — parents are large and already
//     carry heading context; only children (fragmented mid-section) need it.
//  3. Chunks whose content starts with a markdown heading — the heading
//     itself provides enough locating context.
func shouldSkipEnrich(ch Chunk) bool {
	if already, _ := ch.Metadata["has_contextual_header"].(bool); already {
		return true
	}
	if tier, _ := ch.Metadata["tier"].(string); tier == "parent" {
		return true
	}
	if ch.ChunkType == "parent" {
		return true
	}
	if reLeadingHeading.MatchString(ch.Content) {
		return true
	}
	return false
}

// ContextGenerator is a minimal interface implemented by any LLM that can
// generate a short natural-language string. Concrete implementations (e.g.
// internal/llm.Gemini, internal/llm.FallbackLLM) can be passed directly.
//
// We define it here locally to avoid an import cycle between chunker and llm.
type ContextGenerator interface {
	Generate(ctx context.Context, prompt string) (string, error)
}

// ContextualEnricher implements the "Contextual Retrieval" technique from
// Anthropic (Sept 2024). For each chunk, it asks an LLM to produce a 50–100
// token blurb that locates the chunk inside the full document, and prepends
// that blurb to the chunk content before embedding.
//
// Per Anthropic's results, this reduces retrieval failure by ~35% on its own
// and by ~49% when combined with reranking.
//
// The enricher is optional — if LLM is nil, Enrich is a no-op and the chunks
// are returned unchanged. This lets the pipeline run in environments without
// LLM access.
type ContextualEnricher struct {
	LLM            ContextGenerator
	MaxParallel    int           // max concurrent LLM calls (default 4)
	PerCallTimeout time.Duration // per-call timeout (default 15s)
	// DocCharLimit caps the document slice passed to the LLM to avoid huge
	// prompts. A safe default (12000 chars) fits well within Gemini Flash /
	// GPT-4o-mini context windows even for long documents.
	DocCharLimit int
}

// Enrich mutates each chunk's Content to prepend an LLM-generated contextual
// header. On any error the original chunk is left untouched and a warning
// is logged — this stage is best-effort, never fatal.
func (e *ContextualEnricher) Enrich(ctx context.Context, fullDoc string, chunks []Chunk) []Chunk {
	if e == nil || e.LLM == nil || len(chunks) == 0 {
		return chunks
	}

	maxPar := e.MaxParallel
	if maxPar <= 0 {
		maxPar = 4
	}
	timeout := e.PerCallTimeout
	if timeout <= 0 {
		timeout = 15 * time.Second
	}
	docLimit := e.DocCharLimit
	if docLimit <= 0 {
		docLimit = 12000
	}

	docSlice := fullDoc
	if len(docSlice) > docLimit {
		docSlice = docSlice[:docLimit] + "\n\n[...tài liệu tiếp tục...]"
	}

	sem := make(chan struct{}, maxPar)
	type resultEntry struct {
		idx     int
		context string
	}
	results := make([]resultEntry, len(chunks))
	done := make(chan resultEntry, len(chunks))

	for i, ch := range chunks {
		if shouldSkipEnrich(ch) {
			results[i] = resultEntry{idx: i, context: ""}
			continue
		}
		sem <- struct{}{}
		go func(idx int, chunk Chunk) {
			defer func() { <-sem }()
			callCtx, cancel := context.WithTimeout(ctx, timeout)
			defer cancel()

			prompt := buildContextualPrompt(docSlice, chunk.Content)
			out, err := e.LLM.Generate(callCtx, prompt)
			if err != nil {
				slog.Warn("contextual enrich failed", "chunk_index", idx, "error", err)
				done <- resultEntry{idx: idx, context: ""}
				return
			}
			done <- resultEntry{idx: idx, context: sanitizeContext(out)}
		}(i, ch)
	}

	// Wait for in-flight goroutines
	for i := range chunks {
		if shouldSkipEnrich(chunks[i]) {
			continue
		}
		r := <-done
		results[r.idx] = r
	}
	// Drain semaphore
	for i := 0; i < cap(sem); i++ {
		sem <- struct{}{}
	}

	// Apply results
	for i := range chunks {
		ctxText := results[i].context
		if ctxText == "" {
			continue
		}
		chunks[i].Content = ctxText + "\n\n" + chunks[i].Content
		chunks[i].TokenCount = CountTokens(chunks[i].Content)
		if chunks[i].Metadata == nil {
			chunks[i].Metadata = map[string]any{}
		}
		chunks[i].Metadata["has_contextual_header"] = true
		chunks[i].Metadata["contextual_method"] = "llm"
	}

	return chunks
}

const contextualPromptTemplate = `Bạn đang hỗ trợ một hệ thống RAG tiếng Việt. Nhiệm vụ: viết 1–2 câu ngắn (50–100 token) để định vị chunk sau trong tài liệu tổng thể, giúp truy xuất chính xác hơn.

Chỉ trả về đúng 1–2 câu ngữ cảnh bằng tiếng Việt. KHÔNG trả lời câu hỏi, KHÔNG thêm giải thích, KHÔNG dùng markdown.

<document>
%s
</document>

<chunk>
%s
</chunk>

Ngữ cảnh:`

func buildContextualPrompt(doc, chunk string) string {
	return fmt.Sprintf(contextualPromptTemplate, doc, chunk)
}

// sanitizeContext trims whitespace, strips leading labels like "Ngữ cảnh:" and
// caps the result to ~200 characters as a final safety net.
func sanitizeContext(s string) string {
	s = strings.TrimSpace(s)
	// Strip common leading labels
	for _, prefix := range []string{"Ngữ cảnh:", "Context:", "Ngu canh:"} {
		if strings.HasPrefix(s, prefix) {
			s = strings.TrimSpace(strings.TrimPrefix(s, prefix))
		}
	}
	// Drop surrounding quotes
	s = strings.Trim(s, "\"'“”‘’")
	if len(s) > 500 {
		s = s[:500] + "…"
	}
	return s
}
