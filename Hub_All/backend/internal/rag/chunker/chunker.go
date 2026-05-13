package chunker

import (
	"log/slog"
	"sync"

	tiktoken "github.com/pkoukk/tiktoken-go"
)

// Chunker splits text into overlapping chunks suitable for embedding.
type Chunker interface {
	Chunk(text string, opts ChunkOpts) []Chunk
}

// ChunkOpts configures the chunking behaviour.
type ChunkOpts struct {
	MaxTokens int // Maximum tokens per chunk. Default: 512.
	Overlap   int // Number of overlap tokens between adjacent chunks. Default: 50.
}

// Defaults applies default values where fields are zero.
func (o ChunkOpts) Defaults() ChunkOpts {
	if o.MaxTokens <= 0 {
		o.MaxTokens = 512
	}
	if o.Overlap < 0 {
		o.Overlap = 0
	}
	if o.Overlap == 0 && o.MaxTokens > 50 {
		o.Overlap = 50
	}
	return o
}

// Chunk represents a piece of text produced by the chunker.
//
// v3 extensions (all optional — nil/empty is safe for backward compat):
//   - Metadata: arbitrary per-chunk metadata propagated to VectorDocument.Metadata
//   - ParentID: for hierarchical parent-child chunking; set on child chunks
//   - ChunkType: taxonomy tag (e.g. "entity_profile", "negative_rule", "article_narrative")
//   - AlwaysInclude: L5 flag — retrieval engine must always inject these chunks
type Chunk struct {
	Index         int
	Content       string
	TokenCount    int
	StartChar     int
	EndChar       int
	ParentID      string         // v3: set on child chunks (hierarchical)
	ChunkType     string         // v3: taxonomy tag
	AlwaysInclude bool           // v3: L5 negative rule flag
	Metadata      map[string]any // v3: extra metadata (entities, channels, section_type, ...)
}

// ─── Token Counting ───

var (
	tiktokenOnce sync.Once
	tiktokenEnc  *tiktoken.Tiktoken
	useTiktoken  bool
)

func initTiktoken() {
	tiktokenOnce.Do(func() {
		enc, err := tiktoken.EncodingForModel("gpt-4")
		if err != nil {
			slog.Warn("tiktoken init failed, falling back to word estimation", "error", err)
			useTiktoken = false
			return
		}
		tiktokenEnc = enc
		useTiktoken = true
		slog.Info("tiktoken initialized (cl100k_base encoding)")
	})
}

// CountTokens returns the exact token count using tiktoken (cl100k_base).
// Falls back to word-based estimation if tiktoken is not available.
func CountTokens(text string) int {
	if len(text) == 0 {
		return 0
	}

	initTiktoken()

	if useTiktoken && tiktokenEnc != nil {
		tokens := tiktokenEnc.Encode(text, nil, nil)
		return len(tokens)
	}

	return estimateByWords(text)
}

// EstimateTokens is an alias for CountTokens (backward compatible).
func EstimateTokens(text string) int {
	return CountTokens(text)
}

// TokensToChars converts a token count to approximate character count.
// Used by chunker to determine split points.
func TokensToChars(tokens int) int {
	initTiktoken()

	if useTiktoken {
		// cl100k_base: ~4 chars/token for English, ~2.5 for Vietnamese
		// Use 3.5 as average for mixed content
		return int(float64(tokens) * 3.5)
	}
	// Fallback: word-based (1 token ~ 1 word ~ 5.5 chars)
	return tokens * 6
}

// estimateByWords counts words × 1.3 as token approximation.
func estimateByWords(text string) int {
	words := 0
	inWord := false
	for _, r := range text {
		if r == ' ' || r == '\n' || r == '\t' || r == '\r' {
			if inWord {
				words++
				inWord = false
			}
		} else {
			inWord = true
		}
	}
	if inWord {
		words++
	}
	tokens := int(float64(words) * 1.3)
	if tokens == 0 && len(text) > 0 {
		tokens = 1
	}
	return tokens
}
