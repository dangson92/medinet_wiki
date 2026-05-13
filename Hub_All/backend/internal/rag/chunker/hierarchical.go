package chunker

import (
	"fmt"
	"regexp"
	"strings"
)

// HierarchicalChunker wraps a base Chunker and produces parent + child chunks.
//
// Strategy (from RAG Pipeline v3 §2.3):
//  1. Run the base chunker to produce "parent" chunks (800–1500 tokens, large
//     units of meaning — e.g. an entity profile, an article section)
//  2. Split each parent by sentences into small "child" chunks (150–300 tokens)
//  3. Link children to parents via ParentID + metadata["parent_id"]
//
// At retrieval time, the caller searches on children (precise recall) and then
// looks up parents (rich context for generation). Both parents and children are
// stored in the same vector collection — parent/child is distinguished by
// metadata["tier"] ∈ {"parent", "child"}.
type HierarchicalChunker struct {
	Base           Chunker // base chunker used to produce parent chunks
	ChildMaxTokens int     // soft cap for child chunks (default 300)
	ChildOverlap   int     // token overlap between children within the same parent (default 40)
}

var _ Chunker = (*HierarchicalChunker)(nil)

// sentenceSplitRe matches sentence-ending punctuation (Vietnamese + Latin).
var sentenceSplitRe = regexp.MustCompile(`([.!?。…:;]+)\s+`)

// Chunk produces a flat slice of chunks where parent and child chunks coexist.
// Parents carry metadata["tier"] = "parent" and an implicit ID; children have
// ParentID set and metadata["tier"] = "child".
//
// Order of the returned slice: parent₀, child₀₀, child₀₁, ..., parent₁, ...
// This order is preserved so downstream consumers can reconstruct the tree.
func (h *HierarchicalChunker) Chunk(text string, opts ChunkOpts) []Chunk {
	opts = opts.Defaults()
	childMax := h.ChildMaxTokens
	if childMax <= 0 {
		childMax = 300
	}
	childOverlap := h.ChildOverlap
	if childOverlap < 0 {
		childOverlap = 0
	}

	base := h.Base
	if base == nil {
		base = &RecursiveChunker{}
	}

	parents := base.Chunk(text, opts)
	if len(parents) == 0 {
		return nil
	}

	var result []Chunk
	globalIdx := 0
	for parentIdx, parent := range parents {
		parentID := fmt.Sprintf("p%d", parentIdx)
		// Assign a stable ID via metadata so the pipeline can reference it
		if parent.Metadata == nil {
			parent.Metadata = map[string]any{}
		}
		parent.Metadata["tier"] = "parent"
		parent.Metadata["local_parent_id"] = parentID
		if parent.ChunkType == "" {
			parent.ChunkType = "parent"
		}
		parent.Index = globalIdx
		result = append(result, parent)
		globalIdx++

		// Split parent into children
		children := splitIntoChildren(parent.Content, childMax, childOverlap)
		for childIdx, childContent := range children {
			child := Chunk{
				Index:      globalIdx,
				Content:    childContent,
				TokenCount: CountTokens(childContent),
				ParentID:   parentID,
				ChunkType:  "child",
				Metadata: map[string]any{
					"tier":            "child",
					"local_parent_id": parentID,
					"child_index":     childIdx,
				},
			}
			// Inherit selected metadata from parent (entity tags, section, etc.)
			inheritMetadata(parent.Metadata, child.Metadata)
			result = append(result, child)
			globalIdx++
		}
	}

	return result
}

// splitIntoChildren breaks content into sentence-aware chunks under maxTokens.
// Uses a simple greedy packer with sentence boundaries. If a single sentence
// exceeds maxTokens it is emitted as-is (never cut mid-sentence).
func splitIntoChildren(content string, maxTokens, overlap int) []string {
	sentences := splitSentencesHier(content)
	if len(sentences) == 0 {
		return nil
	}

	var out []string
	var buf []string
	bufTokens := 0

	flush := func() {
		if len(buf) == 0 {
			return
		}
		out = append(out, strings.Join(buf, " "))
		// overlap: keep last few sentences for next window
		if overlap > 0 {
			var tail []string
			tailTokens := 0
			for i := len(buf) - 1; i >= 0; i-- {
				st := CountTokens(buf[i])
				if tailTokens+st > overlap {
					break
				}
				tail = append([]string{buf[i]}, tail...)
				tailTokens += st
			}
			buf = tail
			bufTokens = tailTokens
		} else {
			buf = nil
			bufTokens = 0
		}
	}

	for _, s := range sentences {
		st := CountTokens(s)
		if bufTokens+st > maxTokens && len(buf) > 0 {
			flush()
		}
		buf = append(buf, s)
		bufTokens += st
	}
	if len(buf) > 0 {
		out = append(out, strings.Join(buf, " "))
	}
	return out
}

// splitSentencesHier splits text into sentences using Vietnamese-friendly
// punctuation. Paragraphs (\n\n) are treated as hard boundaries.
func splitSentencesHier(text string) []string {
	var sentences []string
	paragraphs := strings.Split(text, "\n\n")
	for _, p := range paragraphs {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		// Keep headings as standalone sentences
		if strings.HasPrefix(p, "#") {
			sentences = append(sentences, p)
			continue
		}
		// Split by sentence punctuation while preserving delimiters
		parts := sentenceSplitRe.Split(p, -1)
		delims := sentenceSplitRe.FindAllString(p, -1)
		for i, part := range parts {
			part = strings.TrimSpace(part)
			if part == "" {
				continue
			}
			if i < len(delims) {
				part += strings.TrimSpace(delims[i])
			}
			sentences = append(sentences, part)
		}
	}
	return sentences
}

// inheritMetadata copies selected parent metadata fields into the child's map.
// Only structural/taxonomy fields are inherited — not tier or local_parent_id.
func inheritMetadata(parent, child map[string]any) {
	if parent == nil || child == nil {
		return
	}
	inherit := []string{
		"entity_name", "entity_aliases",
		"channels", "diseases",
		"section_type", "document_type",
		"hub_code", "level",
	}
	for _, k := range inherit {
		if v, ok := parent[k]; ok {
			if _, exists := child[k]; !exists {
				child[k] = v
			}
		}
	}
}
