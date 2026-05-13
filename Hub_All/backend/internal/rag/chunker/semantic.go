package chunker

import (
	"context"
	"math"
	"regexp"
	"strings"

	"github.com/medinet/hub-all-backend/internal/embedding"
)

// SemanticChunker splits text based on semantic similarity between sentences.
// It uses embedding vectors to detect topic changes — when similarity drops
// below a threshold, a new chunk begins.
//
// Algorithm:
// 1. Split text into sentences
// 2. Embed each sentence (batch call)
// 3. Compare cosine similarity between consecutive sentences
// 4. When similarity drops below threshold → start new chunk
// 5. Respect max_tokens limit — split large chunks further
type SemanticChunker struct {
	Embedder           embedding.EmbeddingProvider
	SimilarityThreshold float64 // default 0.5 — lower = more aggressive splitting
	BufferSize         int     // sentences to look ahead/behind for smoothing (default 1)
}

var _ Chunker = (*SemanticChunker)(nil)

var reSentenceSplit = regexp.MustCompile(`(?m)([.!?。\n]\s+|(?:\n\n)+)`)

func (c *SemanticChunker) Chunk(text string, opts ChunkOpts) []Chunk {
	opts = opts.Defaults()
	threshold := c.SimilarityThreshold
	if threshold <= 0 {
		threshold = 0.5
	}
	bufSize := c.BufferSize
	if bufSize <= 0 {
		bufSize = 1
	}

	// 1. Split into sentences
	sentences := splitSentences(text)
	if len(sentences) <= 1 {
		return []Chunk{{
			Index:      0,
			Content:    text,
			TokenCount: CountTokens(text),
			StartChar:  0,
			EndChar:    len(text),
		}}
	}

	// 2. Embed all sentences
	embeddings := c.embedSentences(sentences)
	if embeddings == nil {
		// Fallback to recursive chunker if embedding fails
		fallback := &RecursiveChunker{}
		return fallback.Chunk(text, opts)
	}

	// 3. Compute similarities between consecutive sentence groups
	similarities := computeGroupSimilarities(embeddings, bufSize)

	// 4. Find break points where similarity drops below threshold
	breakPoints := findBreakPoints(similarities, threshold)

	// 5. Group sentences into chunks
	groups := groupSentences(sentences, breakPoints)

	// 6. Merge small groups + split large groups to respect max_tokens
	maxTokens := opts.MaxTokens
	overlapTokens := opts.Overlap
	merged := mergeAndSplitGroups(groups, maxTokens)

	// 7. Build final chunks with overlap
	return buildSemanticChunks(text, merged, overlapTokens)
}

// splitSentences splits text into sentences, keeping heading lines as separate units.
func splitSentences(text string) []string {
	var sentences []string
	lines := strings.Split(text, "\n")
	var current strings.Builder

	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" {
			if current.Len() > 0 {
				sentences = append(sentences, current.String())
				current.Reset()
			}
			continue
		}

		// Headings are always separate
		if strings.HasPrefix(trimmed, "#") {
			if current.Len() > 0 {
				sentences = append(sentences, current.String())
				current.Reset()
			}
			sentences = append(sentences, trimmed)
			continue
		}

		// Split by sentence-ending punctuation
		parts := reSentenceSplit.Split(trimmed, -1)
		delims := reSentenceSplit.FindAllString(trimmed, -1)

		for i, part := range parts {
			part = strings.TrimSpace(part)
			if part == "" {
				continue
			}
			if current.Len() > 0 {
				current.WriteString(" ")
			}
			current.WriteString(part)
			if i < len(delims) {
				current.WriteString(strings.TrimSpace(delims[i]))
			}

			// If ends with sentence-ending punctuation → flush
			if i < len(delims) && len(delims[i]) > 0 {
				sentences = append(sentences, current.String())
				current.Reset()
			}
		}
	}

	if current.Len() > 0 {
		sentences = append(sentences, current.String())
	}

	// Filter empty
	var result []string
	for _, s := range sentences {
		s = strings.TrimSpace(s)
		if s != "" {
			result = append(result, s)
		}
	}
	return result
}

// embedSentences embeds all sentences in batches.
func (c *SemanticChunker) embedSentences(sentences []string) [][]float32 {
	if c.Embedder == nil {
		return nil
	}

	ctx := context.Background()
	batchSize := 50
	var all [][]float32

	for i := 0; i < len(sentences); i += batchSize {
		end := i + batchSize
		if end > len(sentences) {
			end = len(sentences)
		}
		batch := sentences[i:end]
		vecs, err := c.Embedder.Embed(ctx, batch)
		if err != nil {
			return nil // fallback
		}
		all = append(all, vecs...)
	}

	return all
}

// computeGroupSimilarities computes similarity between groups of consecutive sentences.
// With bufferSize=1: compare sentence[i] with sentence[i+1]
// With bufferSize=2: compare avg(sentence[i-1], sentence[i]) with avg(sentence[i+1], sentence[i+2])
func computeGroupSimilarities(embeddings [][]float32, bufSize int) []float64 {
	if len(embeddings) <= 1 {
		return nil
	}

	sims := make([]float64, len(embeddings)-1)
	for i := 0; i < len(embeddings)-1; i++ {
		// Average vectors in buffer window before and after point i
		before := avgVectors(embeddings, max(0, i-bufSize+1), i+1)
		after := avgVectors(embeddings, i+1, min(len(embeddings), i+1+bufSize))
		sims[i] = cosineSimilarity(before, after)
	}
	return sims
}

// findBreakPoints finds indices where similarity is significantly below average.
func findBreakPoints(similarities []float64, threshold float64) []int {
	if len(similarities) == 0 {
		return nil
	}

	// Use percentile-based threshold: break where similarity < mean - stddev * threshold
	mean, stddev := meanStddev(similarities)
	cutoff := mean - stddev*threshold

	var breaks []int
	for i, sim := range similarities {
		if sim < cutoff {
			breaks = append(breaks, i+1) // break AFTER sentence i
		}
	}
	return breaks
}

// groupSentences groups sentences by break points.
func groupSentences(sentences []string, breakPoints []int) [][]string {
	breakSet := make(map[int]bool)
	for _, bp := range breakPoints {
		breakSet[bp] = true
	}

	var groups [][]string
	var current []string

	for i, s := range sentences {
		current = append(current, s)
		if breakSet[i+1] || i == len(sentences)-1 {
			groups = append(groups, current)
			current = nil
		}
	}
	return groups
}

// mergeAndSplitGroups ensures each group respects maxTokens.
func mergeAndSplitGroups(groups [][]string, maxTokens int) []string {
	var result []string
	var current strings.Builder

	for _, group := range groups {
		groupText := strings.Join(group, "\n")
		groupTokens := CountTokens(groupText)

		if current.Len() == 0 {
			if groupTokens <= maxTokens {
				current.WriteString(groupText)
			} else {
				// Group too large — split by sentences within it
				for _, s := range group {
					if current.Len() > 0 && CountTokens(current.String()+"\n"+s) > maxTokens {
						result = append(result, current.String())
						current.Reset()
					}
					if current.Len() > 0 {
						current.WriteString("\n")
					}
					current.WriteString(s)
				}
			}
		} else if CountTokens(current.String()+"\n"+groupText) <= maxTokens {
			current.WriteString("\n\n")
			current.WriteString(groupText)
		} else {
			result = append(result, current.String())
			current.Reset()
			current.WriteString(groupText)
		}
	}

	if current.Len() > 0 {
		result = append(result, current.String())
	}
	return result
}

// buildSemanticChunks creates final Chunk structs with heading inheritance and overlap.
func buildSemanticChunks(originalText string, chunks []string, overlapTokens int) []Chunk {
	var result []Chunk
	searchStart := 0
	lastHeading := ""

	for i, content := range chunks {
		// Track last heading seen
		for _, line := range strings.Split(content, "\n") {
			if strings.HasPrefix(strings.TrimSpace(line), "#") {
				lastHeading = strings.TrimSpace(line)
			}
		}

		// Add heading context if chunk doesn't start with one
		finalContent := content
		if lastHeading != "" && !strings.HasPrefix(strings.TrimSpace(content), "#") {
			finalContent = lastHeading + "\n\n" + content
		}

		// Add sentence overlap from previous chunk
		if i > 0 && overlapTokens > 0 {
			prevChunk := chunks[i-1]
			overlap := extractLastSentence(prevChunk, overlapTokens)
			if overlap != "" {
				if strings.HasPrefix(strings.TrimSpace(finalContent), "#") {
					// Don't prepend overlap before heading
				} else {
					finalContent = overlap + "\n\n" + finalContent
				}
			}
		}

		// Find position in original text
		startChar := strings.Index(originalText[searchStart:], content)
		if startChar >= 0 {
			startChar += searchStart
		} else {
			startChar = searchStart
		}
		endChar := startChar + len(content)
		if endChar > len(originalText) {
			endChar = len(originalText)
		}

		result = append(result, Chunk{
			Index:      i,
			Content:    finalContent,
			TokenCount: CountTokens(finalContent),
			StartChar:  startChar,
			EndChar:    endChar,
		})

		if endChar <= len(originalText) {
			searchStart = endChar
		}
	}
	return result
}

// extractLastSentence gets the last sentence from text within token budget.
func extractLastSentence(text string, maxTokens int) string {
	sentences := strings.Split(text, ".")
	if len(sentences) < 2 {
		return ""
	}
	last := strings.TrimSpace(sentences[len(sentences)-2])
	if CountTokens(last) > maxTokens {
		return ""
	}
	return last + "."
}

// ─── Math helpers ───

func cosineSimilarity(a, b []float32) float64 {
	if len(a) != len(b) || len(a) == 0 {
		return 0
	}
	var dot, normA, normB float64
	for i := range a {
		dot += float64(a[i]) * float64(b[i])
		normA += float64(a[i]) * float64(a[i])
		normB += float64(b[i]) * float64(b[i])
	}
	if normA == 0 || normB == 0 {
		return 0
	}
	return dot / (math.Sqrt(normA) * math.Sqrt(normB))
}

func avgVectors(vecs [][]float32, start, end int) []float32 {
	if start >= end || len(vecs) == 0 {
		return nil
	}
	dim := len(vecs[0])
	avg := make([]float32, dim)
	count := float32(end - start)
	for i := start; i < end; i++ {
		for j := range avg {
			if j < len(vecs[i]) {
				avg[j] += vecs[i][j]
			}
		}
	}
	for j := range avg {
		avg[j] /= count
	}
	return avg
}

func meanStddev(vals []float64) (float64, float64) {
	if len(vals) == 0 {
		return 0, 0
	}
	sum := 0.0
	for _, v := range vals {
		sum += v
	}
	mean := sum / float64(len(vals))

	sumSq := 0.0
	for _, v := range vals {
		d := v - mean
		sumSq += d * d
	}
	stddev := math.Sqrt(sumSq / float64(len(vals)))
	return mean, stddev
}
