package chunker

import (
	"context"
	"log/slog"
)

// StrategicChunker is the top-level chunker for RAG Pipeline v3.
// It implements the base Chunker interface (so it is a drop-in replacement
// for RecursiveChunker) while internally routing each document to the right
// combination of the 9 levels + 5 v3 techniques.
//
// The Chunk() method takes no document-type hint because the legacy interface
// doesn't carry one — instead StrategicChunker auto-detects the type from
// the text itself using the rule-based Document Type Router.
//
// Execution flow per document:
//  1. Detect DocumentType and pick ChunkingStrategy
//  2. Run L1 entity profile chunker if strategy includes "L1"
//     (falls back to base chunker if no entities detected)
//  3. Run base chunker (Recursive/Semantic) on non-entity content
//  4. Run L5 negative rule extractor on the whole text (always_include chunks)
//  5. Wrap with HierarchicalChunker if strategy.Hierarchical is true
//  6. Enrich with ContextualEnricher if strategy.Contextual is true and LLM set
//
// Parallelism, cancellation, and error handling are all best-effort: no step
// is allowed to fail the chunking call. Each failure degrades gracefully to
// the previous tier's output.
type StrategicChunker struct {
	// Base is the fallback Chunker used for plain text / article / research
	// content. Typically a RecursiveChunker.
	Base Chunker

	// Entity extracts L1 entity profile chunks. Optional — nil skips L1.
	Entity *EntityProfileChunker

	// Negative extracts L5 always-include negative-rule chunks. Optional.
	Negative *NegativeRuleExtractor

	// Hierarchical wraps the base output with parent-child split. If nil,
	// StrategicChunker uses a default HierarchicalChunker over Base when
	// the strategy asks for it.
	Hierarchical *HierarchicalChunker

	// Contextual enriches chunks with LLM-generated context headers. Nil-safe.
	Contextual *ContextualEnricher

	// If true, StrategicChunker logs strategy decisions at debug level.
	Verbose bool
}

var _ Chunker = (*StrategicChunker)(nil)

// Chunk implements the Chunker interface. Document type is auto-detected.
func (s *StrategicChunker) Chunk(text string, opts ChunkOpts) []Chunk {
	opts = opts.Defaults()
	base := s.Base
	if base == nil {
		base = &RecursiveChunker{}
	}

	tokens := CountTokens(text)
	docType := DetectDocumentType(text)
	strategy := StrategyFor(docType, tokens)

	slog.Info("chunking strategy selected",
		"doc_type", string(docType),
		"tokens", tokens,
		"levels", strategy.Levels,
		"hierarchical", strategy.Hierarchical,
		"contextual", strategy.Contextual,
	)

	var mainChunks []Chunk
	entityRanges := [][2]int{} // [start,end] ranges covered by entity chunks

	// ── L1: entity profile ──
	if s.Entity != nil && stringsContains(strategy.Levels, "L1") {
		entityChunks := s.Entity.Chunk(text)
		if len(entityChunks) > 0 {
			mainChunks = append(mainChunks, entityChunks...)
			for _, c := range entityChunks {
				entityRanges = append(entityRanges, [2]int{c.StartChar, c.EndChar})
			}
			slog.Info("L1 entity profile chunks emitted", "count", len(entityChunks))
		}
	}

	// ── Base chunker on remainder ──
	remainder := subtractRanges(text, entityRanges)
	if len(remainder) > 0 {
		var baseOut []Chunk
		// When the strategy wants hierarchical output, use HierarchicalChunker
		// (wrapping the base). Otherwise use the raw base chunker.
		if strategy.Hierarchical {
			hc := s.Hierarchical
			if hc == nil {
				hc = &HierarchicalChunker{Base: base}
			} else if hc.Base == nil {
				clone := *hc
				clone.Base = base
				hc = &clone
			}
			baseOut = hc.Chunk(remainder, opts)
		} else {
			baseOut = base.Chunk(remainder, opts)
		}
		// Re-index so all chunks have unique global indices
		offset := len(mainChunks)
		for i := range baseOut {
			baseOut[i].Index = offset + i
		}
		mainChunks = append(mainChunks, baseOut...)
	}

	// ── L5: negative rule (scan FULL text, not remainder) ──
	if s.Negative != nil && stringsContains(strategy.Levels, "L5") {
		negChunks := s.Negative.Extract(text)
		if len(negChunks) > 0 {
			offset := len(mainChunks)
			for i := range negChunks {
				negChunks[i].Index = offset + i
			}
			mainChunks = append(mainChunks, negChunks...)
			slog.Info("L5 negative rule chunks emitted", "count", len(negChunks))
		}
	}

	// ── Contextual Retrieval ──
	if strategy.Contextual && s.Contextual != nil {
		ctx, cancel := context.WithCancel(context.Background())
		defer cancel()
		mainChunks = s.Contextual.Enrich(ctx, text, mainChunks)
	}

	// Ensure every chunk has a populated Metadata map and doc type tag
	for i := range mainChunks {
		if mainChunks[i].Metadata == nil {
			mainChunks[i].Metadata = map[string]any{}
		}
		mainChunks[i].Metadata["doc_type"] = string(docType)
		if mainChunks[i].ChunkType == "" {
			mainChunks[i].ChunkType = "generic"
		}
	}

	if len(mainChunks) == 0 {
		// Absolute fallback — never return zero chunks
		return base.Chunk(text, opts)
	}
	return mainChunks
}

// subtractRanges returns the text with the given [start,end] char ranges
// removed (replaced by a single newline to preserve paragraph boundaries).
// Used to avoid double-chunking content already captured by L1 entity profiles.
func subtractRanges(text string, ranges [][2]int) string {
	if len(ranges) == 0 {
		return text
	}
	// ranges are produced in document order by the entity chunker, but be safe
	sorted := make([][2]int, len(ranges))
	copy(sorted, ranges)
	for i := 1; i < len(sorted); i++ {
		for j := i; j > 0 && sorted[j-1][0] > sorted[j][0]; j-- {
			sorted[j-1], sorted[j] = sorted[j], sorted[j-1]
		}
	}
	var out []byte
	cursor := 0
	for _, r := range sorted {
		if r[0] < cursor {
			continue // overlap — skip
		}
		out = append(out, text[cursor:r[0]]...)
		out = append(out, '\n')
		cursor = r[1]
		if cursor > len(text) {
			cursor = len(text)
		}
	}
	out = append(out, text[cursor:]...)
	return string(out)
}

func stringsContains(slice []string, v string) bool {
	for _, s := range slice {
		if s == v {
			return true
		}
	}
	return false
}
