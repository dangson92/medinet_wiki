package rag

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/medinet/hub-all-backend/internal/embedding"
	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/vectorstore"
)

type Searcher struct {
	embedder embedding.EmbeddingProvider
	store    vectorstore.VectorStore
	cache    *SearchCache
}

func NewSearcher(embedder embedding.EmbeddingProvider, store vectorstore.VectorStore, cache *SearchCache) *Searcher {
	return &Searcher{
		embedder: embedder,
		store:    store,
		cache:    cache,
	}
}

// Search performs a single-hub vector search.
func (s *Searcher) Search(ctx context.Context, req model.SearchRequest, hub model.Hub) (*model.SearchResponse, error) {
	start := time.Now()

	topK := req.TopK
	if topK <= 0 {
		topK = 10
	}
	if topK > 50 {
		topK = 50
	}
	// min_score default = 0 (no filter). Caller có thể truyền min_score>0 để lọc low-score.
	// Lý do: text-embedding-3-large với tiếng Việt thường cho điểm 0.3-0.5 là match tốt;
	// hard-code 0.3 từng cắt 5/7 query empty trong eval Phase 1 (top-3 41.7% → 75% sau khi
	// hạ filter). Xem .planning/phases/01-eval-dataset-baseline-native/01-VERIFICATION.md.
	minScore := req.MinScore
	if minScore < 0 {
		minScore = 0
	}

	// Check result cache
	cacheKey := BuildCacheKey(req.Query, []string{hub.ID.String()}, req.Filters)
	if s.cache != nil {
		if cached, ok := s.cache.GetResults(ctx, cacheKey); ok {
			var resp model.SearchResponse
			if json.Unmarshal(cached, &resp) == nil {
				resp.CacheHit = true
				resp.QueryTimeMs = time.Since(start).Milliseconds()
				return &resp, nil
			}
		}
	}

	// Embed query (with cache)
	queryVec, err := s.embedQuery(ctx, req.Query)
	if err != nil {
		return nil, fmt.Errorf("embed query: %w", err)
	}

	// Vector search in ChromaDB
	collection := hub.ChromaCollection
	if collection == "" {
		collection = "medinet_" + hub.Code
	}

	opts := vectorstore.QueryOpts{
		TopK:     topK * 3, // fetch more for parent-dedup + re-ranking
		MinScore: minScore,
	}

	vectorResults, err := s.store.Query(ctx, collection, queryVec, opts)
	if err != nil {
		errStr := err.Error()
		if strings.Contains(errStr, "dimension") && strings.Contains(errStr, "got") {
			return nil, fmt.Errorf(
				"embedding dimension mismatch: documents in this hub were indexed with a different provider. "+
					"Go to Settings → Cấu hình RAG → Embedding Provider and select the provider "+
					"used when documents were originally ingested. Original error: %w", err)
		}
		return nil, fmt.Errorf("vector search: %w", err)
	}

	// v3 — dedupe hierarchical child chunks by parent_id (keep best per parent)
	vectorResults = dedupeByParent(vectorResults)

	// v3 — fetch always_include chunks (L5 negative rules) and prepend them
	if negRules := s.fetchAlwaysInclude(ctx, collection, queryVec, hub.Code); len(negRules) > 0 {
		vectorResults = append(negRules, vectorResults...)
	}

	// Convert to SearchResults with ALG-001 scoring
	results := make([]model.SearchResult, 0, len(vectorResults))
	for _, vr := range vectorResults {
		docName := ""
		if vr.Metadata != nil {
			if t, ok := vr.Metadata["document_name"]; ok {
				docName = fmt.Sprintf("%v", t)
			}
		}

		// Extract section title + clean snippet from content
		sectionTitle, cleanSnippet := extractTitleAndSnippet(vr.Content, 300)
		title := sectionTitle
		if title == "" {
			title = docName
		}
		if title == "" {
			title = vr.ID
		}

		finalScore := ComputeScore(ScoringInput{
			CosineSimilarity: vr.Score,
			DaysSinceUpdate:  0,
		})

		results = append(results, model.SearchResult{
			ID:            vr.ID,
			HubID:         hub.ID.String(),
			HubName:       hub.Name,
			Title:         title,
			Snippet:       cleanSnippet,
			Content:       vr.Content,
			Category:      docName,
			Score:         finalScore,
			RawSimilarity: vr.Score,
			Source:        "document",
		})
	}

	// Sort by final score descending
	sort.Slice(results, func(i, j int) bool {
		return results[i].Score > results[j].Score
	})

	// Trim to topK
	if len(results) > topK {
		results = results[:topK]
	}

	resp := &model.SearchResponse{
		Results:           results,
		TotalHubsSearched: 1,
		QueryTimeMs:       time.Since(start).Milliseconds(),
		CacheHit:          false,
	}

	// Cache results
	if s.cache != nil {
		if data, err := json.Marshal(resp); err == nil {
			s.cache.SetResults(ctx, cacheKey, data)
		}
	}

	return resp, nil
}

// CrossHubSearch performs fan-out search across multiple hubs concurrently.
func (s *Searcher) CrossHubSearch(ctx context.Context, req model.SearchRequest, hubs []model.Hub) (*model.SearchResponse, error) {
	start := time.Now()

	topK := req.TopK
	if topK <= 0 {
		topK = 10
	}
	if topK > 50 {
		topK = 50
	}

	// Check result cache
	hubIDs := make([]string, len(hubs))
	for i, h := range hubs {
		hubIDs[i] = h.ID.String()
	}
	cacheKey := BuildCacheKey(req.Query, hubIDs, req.Filters)
	if s.cache != nil {
		if cached, ok := s.cache.GetResults(ctx, cacheKey); ok {
			var resp model.SearchResponse
			if json.Unmarshal(cached, &resp) == nil {
				resp.CacheHit = true
				resp.QueryTimeMs = time.Since(start).Milliseconds()
				return &resp, nil
			}
		}
	}

	// Embed query ONCE
	queryVec, err := s.embedQuery(ctx, req.Query)
	if err != nil {
		return nil, fmt.Errorf("embed query: %w", err)
	}

	// Fan-out: query all hubs concurrently with 5s timeout
	searchCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	type hubResult struct {
		hub     model.Hub
		results []vectorstore.VectorSearchResult
		err     error
	}

	ch := make(chan hubResult, len(hubs))
	var wg sync.WaitGroup

	for _, hub := range hubs {
		wg.Add(1)
		go func(h model.Hub) {
			defer wg.Done()
			collection := h.ChromaCollection
			if collection == "" {
				collection = "medinet_" + h.Code
			}

			// Cross-hub: cùng policy với single-hub Search — default min_score = 0 (no filter).
			opts := vectorstore.QueryOpts{
				TopK:     topK,
				MinScore: req.MinScore,
			}
			if opts.MinScore < 0 {
				opts.MinScore = 0
			}

			results, err := s.store.Query(searchCtx, collection, queryVec, opts)
			ch <- hubResult{hub: h, results: results, err: err}
		}(hub)
	}

	// Close channel when all done
	go func() {
		wg.Wait()
		close(ch)
	}()

	// Collect results
	var allResults []model.SearchResult
	hubsSearched := 0

	for hr := range ch {
		if hr.err != nil {
			errStr := hr.err.Error()
			if strings.Contains(errStr, "dimension") && strings.Contains(errStr, "got") {
				// Dimension mismatch: documents were embedded with a different provider.
				// Admin action required: change Settings → Embedding Provider to match
				// the provider that was used when the documents were originally indexed.
				slog.Error("cross-hub search: embedding dimension mismatch — "+
					"the search query vector dimension does not match the ChromaDB collection. "+
					"Go to Settings → Cấu hình RAG → Embedding Provider and select the "+
					"same provider used when documents were originally ingested.",
					"hub", hr.hub.Code,
					"error", errStr,
				)
			} else {
				slog.Warn("cross-hub search: hub failed",
					"hub", hr.hub.Code,
					"error", hr.err,
				)
			}
			continue
		}
		hubsSearched++

		for _, vr := range hr.results {
			docName := ""
			if vr.Metadata != nil {
				if t, ok := vr.Metadata["document_name"]; ok {
					docName = fmt.Sprintf("%v", t)
				}
			}

			sectionTitle, cleanSnippet := extractTitleAndSnippet(vr.Content, 300)
			title := sectionTitle
			if title == "" {
				title = docName
			}
			if title == "" {
				title = vr.ID
			}

			finalScore := ComputeScore(ScoringInput{
				CosineSimilarity: vr.Score,
			})

			allResults = append(allResults, model.SearchResult{
				ID:            vr.ID,
				HubID:         hr.hub.ID.String(),
				HubName:       hr.hub.Name,
				Title:         title,
				Snippet:       cleanSnippet,
				Content:       vr.Content,
				Category:      docName,
				Score:         finalScore,
				RawSimilarity: vr.Score,
				Source:        "document",
			})
		}
	}

	// Global re-rank by score
	sort.Slice(allResults, func(i, j int) bool {
		return allResults[i].Score > allResults[j].Score
	})

	if len(allResults) > topK {
		allResults = allResults[:topK]
	}

	resp := &model.SearchResponse{
		Results:           allResults,
		TotalHubsSearched: hubsSearched,
		QueryTimeMs:       time.Since(start).Milliseconds(),
		CacheHit:          false,
	}

	// Cache results
	if s.cache != nil {
		if data, err := json.Marshal(resp); err == nil {
			s.cache.SetResults(ctx, cacheKey, data)
		}
	}

	return resp, nil
}

// FindSimilar finds content similar to the given text in a specific hub.
func (s *Searcher) FindSimilar(ctx context.Context, req model.SimilarRequest, hub model.Hub) (*model.SimilarResponse, error) {
	threshold := req.Threshold
	if threshold <= 0 {
		threshold = 0.85
	}

	// Embed the content
	content := req.Content
	if len(content) > 2000 {
		content = content[:2000] // Limit embedding input
	}

	vecs, err := s.embedder.Embed(ctx, []string{content})
	if err != nil {
		return nil, fmt.Errorf("embed content: %w", err)
	}
	if len(vecs) == 0 {
		return nil, fmt.Errorf("empty embedding result")
	}

	collection := hub.ChromaCollection
	if collection == "" {
		collection = "medinet_" + hub.Code
	}

	results, err := s.store.Query(ctx, collection, vecs[0], vectorstore.QueryOpts{
		TopK:     10,
		MinScore: threshold,
	})
	if err != nil {
		return nil, fmt.Errorf("query similar: %w", err)
	}

	matches := make([]model.SimilarMatch, 0, len(results))
	for _, r := range results {
		title := ""
		pageID := r.ID
		if r.Metadata != nil {
			if t, ok := r.Metadata["document_name"]; ok {
				title = fmt.Sprintf("%v", t)
			}
			if pid, ok := r.Metadata["document_id"]; ok {
				pageID = fmt.Sprintf("%v", pid)
			}
		}
		// Remove chunk index suffix from ID for display
		if idx := strings.LastIndex(pageID, "_"); idx > 0 {
			pageID = pageID[:idx]
		}

		matches = append(matches, model.SimilarMatch{
			PageID:          pageID,
			PageTitle:       title,
			SimilarityScore: r.Score,
			HubName:         hub.Name,
		})
	}

	// Deduplicate by pageID (same document multiple chunks)
	seen := make(map[string]bool)
	unique := make([]model.SimilarMatch, 0)
	for _, m := range matches {
		if !seen[m.PageID] {
			seen[m.PageID] = true
			unique = append(unique, m)
		}
	}

	return &model.SimilarResponse{Matches: unique}, nil
}

// embedQuery embeds the query text, using cache if available.
// extractTitleAndSnippet parses chunk content to extract:
// - Best section title (first meaningful heading)
// - Clean snippet text (no markdown syntax)
func extractTitleAndSnippet(content string, maxRunes int) (title, snippet string) {
	// Find headings: ## or ### anywhere in text (not just after \n)
	// Match: 2-4 # chars + space + text until next # or end
	reHeading := regexp.MustCompile(`#{2,4}\s+([^#\n]+?)(?:\s*#{2,4}\s+|\s*$)`)
	matches := reHeading.FindAllStringSubmatch(content, -1)

	// Also try simpler pattern for single heading in text
	if len(matches) == 0 {
		reSimple := regexp.MustCompile(`#{2,4}\s+(.+?)(?:\s+#{2,4}|\s*$)`)
		matches = reSimple.FindAllStringSubmatch(content, -1)
	}

	for _, m := range matches {
		heading := strings.TrimSpace(m[1])
		// Skip page markers and short fragments
		if strings.HasPrefix(heading, "Trang ") && len(heading) < 15 {
			continue
		}
		// Skip numbered references like "1. Dahl, R."
		if len(heading) > 5 && title == "" {
			title = heading
		}
	}

	// Clean: remove ALL markdown syntax
	clean := content
	// Remove heading markers (## ### ####) wherever they appear
	clean = regexp.MustCompile(`#{1,6}\s*`).ReplaceAllString(clean, "")
	// Remove bold/italic markers
	clean = strings.ReplaceAll(clean, "**", "")
	clean = strings.ReplaceAll(clean, "__", "")
	// Remove page markers like "Trang 1/5"
	clean = regexp.MustCompile(`Trang\s+\d+/\d+`).ReplaceAllString(clean, "")
	// Collapse whitespace
	clean = regexp.MustCompile(`\s+`).ReplaceAllString(clean, " ")
	clean = strings.TrimSpace(clean)

	snippet = truncateRunes(clean, maxRunes)
	return
}

// truncateRunes safely truncates a string at word boundary (UTF-8 safe).
func truncateRunes(s string, maxRunes int) string {
	runes := []rune(s)
	if len(runes) <= maxRunes {
		return s
	}
	// Find last space before maxRunes to avoid cutting mid-word
	cut := maxRunes
	for cut > maxRunes-30 && cut > 0 {
		if runes[cut] == ' ' || runes[cut] == '\n' {
			break
		}
		cut--
	}
	if cut <= maxRunes-30 {
		cut = maxRunes // no space found nearby, hard cut
	}
	return string(runes[:cut]) + "..."
}

// dedupeByParent implements the hierarchical retrieval dedup step from
// RAG Pipeline v3 §6. When multiple child chunks from the same parent match
// the query, keep only the highest-scoring child per parent. This prevents
// the result set from being dominated by near-duplicate chunks that all
// belong to the same entity profile or article section.
//
// Chunks without a parent_id (parent chunks themselves, or legacy chunks
// produced by v2 pipelines) pass through unchanged.
func dedupeByParent(results []vectorstore.VectorSearchResult) []vectorstore.VectorSearchResult {
	if len(results) <= 1 {
		return results
	}
	seenParent := make(map[string]int) // parent_id → index in out
	var out []vectorstore.VectorSearchResult
	for _, r := range results {
		parentID := ""
		if r.Metadata != nil {
			if pid, ok := r.Metadata["parent_id"]; ok {
				parentID = fmt.Sprintf("%v", pid)
			}
		}
		if parentID == "" {
			out = append(out, r)
			continue
		}
		if existingIdx, ok := seenParent[parentID]; ok {
			// Keep the higher-scoring entry
			if r.Score > out[existingIdx].Score {
				out[existingIdx] = r
			}
			continue
		}
		seenParent[parentID] = len(out)
		out = append(out, r)
	}
	return out
}

// fetchAlwaysInclude runs a secondary vector query filtered to chunks
// flagged with metadata.always_include=true (produced by the L5 negative
// rule extractor). These chunks are unconditionally injected into the
// retrieval context so critical rules never get filtered out by similarity
// scoring.
//
// Returns nil on any error — always-include is a best-effort enhancement.
func (s *Searcher) fetchAlwaysInclude(ctx context.Context, collection string, queryVec []float32, hubCode string) []vectorstore.VectorSearchResult {
	opts := vectorstore.QueryOpts{
		TopK:     5,
		MinScore: 0,
		Filter:   map[string]any{"always_include": true},
	}
	results, err := s.store.Query(ctx, collection, queryVec, opts)
	if err != nil {
		slog.Warn("fetchAlwaysInclude failed", "collection", collection, "error", err)
		return nil
	}
	// Pin their score to a high value so they sort near the top regardless
	// of semantic similarity. ALG-001 scoring later applies a flat bonus.
	for i := range results {
		if results[i].Score < 0.9 {
			results[i].Score = 0.9
		}
	}
	return results
}

func (s *Searcher) embedQuery(ctx context.Context, query string) ([]float32, error) {
	if s.cache != nil {
		if vec, ok := s.cache.GetEmbedding(ctx, query); ok {
			return vec, nil
		}
	}

	vecs, err := s.embedder.Embed(ctx, []string{query})
	if err != nil {
		return nil, err
	}
	if len(vecs) == 0 {
		return nil, fmt.Errorf("empty embedding result")
	}

	if s.cache != nil {
		s.cache.SetEmbedding(ctx, query, vecs[0])
	}

	return vecs[0], nil
}
