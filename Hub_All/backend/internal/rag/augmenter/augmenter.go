// Package augmenter enriches chunks with LLM-generated Q&A and keywords
// before embedding (RAGFlow-style auto-augmentation).
//
// For every chunk the augmenter asks an LLM for:
//   - 3–5 natural-language questions this chunk answers
//   - 5–10 salient keywords
//
// The result is prepended to chunk.Content (so it is embedded and retrievable)
// and stored in chunk.Metadata (so it can be filtered or surfaced in the UI).
//
// This stage is BEST-EFFORT: any per-chunk failure is logged and the chunk
// passes through unchanged. It MUST NOT fail ingestion.
package augmenter

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/medinet/hub-all-backend/internal/rag/chunker"
)

// LLM is the minimal interface this package needs. Concrete llm.LLM / llm.FallbackLLM
// satisfy it directly; kept local to avoid an import cycle.
type LLM interface {
	Generate(ctx context.Context, prompt string) (string, error)
}

// Augmenter generates questions + keywords per chunk and folds them into the
// chunk's content + metadata.
type Augmenter struct {
	LLM            LLM
	MaxParallel    int           // concurrent LLM calls (default 4)
	PerCallTimeout time.Duration // per-chunk timeout (default 20s)
	MinChars       int           // skip chunks shorter than this (default 150)
	MaxChars       int           // truncate chunk to this before prompting (default 4000)
}

// Augment mutates chunks in place. Returns the same slice for chaining.
// No-op when Augmenter is nil, LLM is nil, or chunks is empty.
func (a *Augmenter) Augment(ctx context.Context, chunks []chunker.Chunk) []chunker.Chunk {
	if a == nil || a.LLM == nil || len(chunks) == 0 {
		return chunks
	}

	maxPar := a.MaxParallel
	if maxPar <= 0 {
		maxPar = 4
	}
	timeout := a.PerCallTimeout
	if timeout <= 0 {
		timeout = 20 * time.Second
	}
	minChars := a.MinChars
	if minChars <= 0 {
		minChars = 150
	}
	maxChars := a.MaxChars
	if maxChars <= 0 {
		maxChars = 4000
	}

	type result struct {
		idx       int
		questions []string
		keywords  []string
		skipped   bool
	}

	sem := make(chan struct{}, maxPar)
	out := make([]result, len(chunks))
	done := make(chan result, len(chunks))
	launched := 0

	for i, ch := range chunks {
		// Skip augmentation for always-include (negative rules) — their text is
		// already directive, questions would add noise.
		if ch.AlwaysInclude {
			out[i] = result{idx: i, skipped: true}
			continue
		}
		// Skip very short chunks — LLM usually returns generic/useless questions.
		if len([]rune(ch.Content)) < minChars {
			out[i] = result{idx: i, skipped: true}
			continue
		}
		launched++
		sem <- struct{}{}
		go func(idx int, content string) {
			defer func() { <-sem }()
			callCtx, cancel := context.WithTimeout(ctx, timeout)
			defer cancel()

			trimmed := content
			if len([]rune(trimmed)) > maxChars {
				runes := []rune(trimmed)
				trimmed = string(runes[:maxChars]) + "\n[...truncated...]"
			}

			prompt := buildAugmentPrompt(trimmed)
			raw, err := a.LLM.Generate(callCtx, prompt)
			if err != nil {
				slog.Warn("augment llm call failed", "chunk_index", idx, "error", err)
				done <- result{idx: idx, skipped: true}
				return
			}
			qs, kws := parseAugmentResponse(raw)
			if len(qs) == 0 && len(kws) == 0 {
				slog.Debug("augment yielded nothing", "chunk_index", idx, "raw_len", len(raw))
				done <- result{idx: idx, skipped: true}
				return
			}
			done <- result{idx: idx, questions: qs, keywords: kws}
		}(i, ch.Content)
	}

	// Collect results from launched goroutines only.
	for k := 0; k < launched; k++ {
		r := <-done
		out[r.idx] = r
	}
	// Drain semaphore (wait for any stragglers).
	for i := 0; i < cap(sem); i++ {
		sem <- struct{}{}
	}

	augmented := 0
	for i := range chunks {
		r := out[i]
		if r.skipped || (len(r.questions) == 0 && len(r.keywords) == 0) {
			continue
		}
		header := buildAugmentHeader(r.questions, r.keywords)
		chunks[i].Content = header + "\n\n" + chunks[i].Content
		chunks[i].TokenCount = chunker.CountTokens(chunks[i].Content)
		if chunks[i].Metadata == nil {
			chunks[i].Metadata = map[string]any{}
		}
		// Store as delimited strings — ChromaDB metadata must be scalar.
		// Use "|" between questions (questions may contain commas) and "," for keywords.
		chunks[i].Metadata["auto_questions"] = strings.Join(r.questions, " | ")
		chunks[i].Metadata["auto_keywords"] = strings.Join(r.keywords, ", ")
		chunks[i].Metadata["augmented"] = true
		augmented++
	}
	slog.Info("augmenter: chunks enriched",
		"total", len(chunks),
		"augmented", augmented,
		"skipped", len(chunks)-augmented)

	return chunks
}

const augmentPromptTemplate = `Bạn là trợ lý RAG tiếng Việt. Phân tích ĐOẠN VĂN BẢN sau và trả về JSON đúng định dạng:

{
  "questions": ["câu hỏi 1?", "câu hỏi 2?", "câu hỏi 3?"],
  "keywords": ["từ khóa 1", "từ khóa 2", "từ khóa 3", "từ khóa 4", "từ khóa 5"]
}

Yêu cầu:
- "questions": 3–5 câu hỏi TỰ NHIÊN mà đoạn văn này trả lời được. Viết như người dùng thật sự hỏi (ngắn, đời thường, có dấu ?).
- "keywords": 5–10 từ/cụm từ CÔNG CỤ tra cứu (tên riêng, thuật ngữ, bệnh, thuốc, kênh, quy trình). KHÔNG chứa stopword.
- Trả về CHỈ JSON. KHÔNG giải thích. KHÔNG markdown code fence.
- Tiếng Việt, giữ nguyên dấu.

ĐOẠN VĂN BẢN:
%s

JSON:`

func buildAugmentPrompt(content string) string {
	return fmt.Sprintf(augmentPromptTemplate, content)
}

// parseAugmentResponse extracts questions + keywords from the LLM output.
// Tolerates: surrounding whitespace, leading "json" label, markdown fences,
// trailing prose. Returns empty slices on any parse failure (best-effort).
func parseAugmentResponse(raw string) (questions []string, keywords []string) {
	s := strings.TrimSpace(raw)
	// Strip common markdown fences.
	s = strings.TrimPrefix(s, "```json")
	s = strings.TrimPrefix(s, "```JSON")
	s = strings.TrimPrefix(s, "```")
	s = strings.TrimSuffix(s, "```")
	s = strings.TrimSpace(s)

	// Find the first `{` and last `}` — tolerate prose before/after.
	lo := strings.Index(s, "{")
	hi := strings.LastIndex(s, "}")
	if lo < 0 || hi <= lo {
		return nil, nil
	}
	s = s[lo : hi+1]

	var parsed struct {
		Questions []string `json:"questions"`
		Keywords  []string `json:"keywords"`
	}
	if err := json.Unmarshal([]byte(s), &parsed); err != nil {
		return nil, nil
	}
	questions = cleanList(parsed.Questions, 5, 160)
	keywords = cleanList(parsed.Keywords, 10, 60)
	return questions, keywords
}

func cleanList(items []string, maxCount, maxRunesPerItem int) []string {
	out := make([]string, 0, len(items))
	seen := map[string]bool{}
	for _, it := range items {
		t := strings.TrimSpace(it)
		t = strings.Trim(t, "\"'“”‘’-•*")
		t = strings.TrimSpace(t)
		if t == "" {
			continue
		}
		runes := []rune(t)
		if len(runes) > maxRunesPerItem {
			t = string(runes[:maxRunesPerItem]) + "…"
		}
		key := strings.ToLower(t)
		if seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, t)
		if len(out) >= maxCount {
			break
		}
	}
	return out
}

// buildAugmentHeader builds the compact block prepended to chunk.Content.
// It is written in plain Vietnamese — NOT markdown — so downstream regex-based
// title extractors in searcher.go ignore it (they only match ## / ### headings).
func buildAugmentHeader(questions, keywords []string) string {
	var b strings.Builder
	if len(questions) > 0 {
		b.WriteString("Câu hỏi tham chiếu: ")
		b.WriteString(strings.Join(questions, " | "))
	}
	if len(keywords) > 0 {
		if b.Len() > 0 {
			b.WriteString("\n")
		}
		b.WriteString("Từ khoá: ")
		b.WriteString(strings.Join(keywords, ", "))
	}
	return b.String()
}
