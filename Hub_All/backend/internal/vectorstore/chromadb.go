package vectorstore

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
)

const v2Base = "/api/v2/tenants/default_tenant/databases/default_database"

type ChromaDB struct {
	baseURL string
	token   string
	client  *http.Client
	// Collection ID cache: name → {id, expiresAt}
	colCache   map[string]colCacheEntry
	colCacheMu sync.RWMutex
}

type colCacheEntry struct {
	id        string
	expiresAt time.Time
}

func NewChromaDB(baseURL, token string) *ChromaDB {
	return &ChromaDB{
		baseURL:  baseURL,
		token:    token,
		client:   &http.Client{Timeout: 30 * time.Second},
		colCache: make(map[string]colCacheEntry),
	}
}

func (c *ChromaDB) do(ctx context.Context, method, path string, body interface{}) ([]byte, int, error) {
	var bodyReader io.Reader
	if body != nil {
		jsonBody, err := json.Marshal(body)
		if err != nil {
			return nil, 0, fmt.Errorf("marshal: %w", err)
		}
		bodyReader = bytes.NewReader(jsonBody)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, bodyReader)
	if err != nil {
		return nil, 0, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, fmt.Errorf("read response: %w", err)
	}
	return respBody, resp.StatusCode, nil
}

func (c *ChromaDB) CreateCollection(ctx context.Context, name string) error {
	body := map[string]interface{}{
		"name": name,
		"metadata": map[string]interface{}{
			"hnsw:space": "cosine",
		},
		"get_or_create": true,
	}
	_, status, err := c.do(ctx, "POST", v2Base+"/collections", body)
	if err != nil {
		return fmt.Errorf("create collection: %w", err)
	}
	if status != 200 {
		return fmt.Errorf("create collection: status %d", status)
	}
	return nil
}

func (c *ChromaDB) DeleteCollection(ctx context.Context, name string) error {
	_, _, err := c.do(ctx, "DELETE", v2Base+"/collections/"+name, nil)
	return err
}

func (c *ChromaDB) ListCollections(ctx context.Context) ([]string, error) {
	respBody, status, err := c.do(ctx, "GET", v2Base+"/collections", nil)
	if err != nil {
		return nil, err
	}
	if status != 200 {
		return nil, fmt.Errorf("list collections: status %d — %s", status, string(respBody))
	}
	var collections []struct {
		Name string `json:"name"`
	}
	if err := json.Unmarshal(respBody, &collections); err != nil {
		return nil, fmt.Errorf("unmarshal: %w", err)
	}
	names := make([]string, len(collections))
	for i, col := range collections {
		names[i] = col.Name
	}
	return names, nil
}

func (c *ChromaDB) getCollectionID(ctx context.Context, name string) (string, error) {
	// Check cache first
	c.colCacheMu.RLock()
	entry, ok := c.colCache[name]
	c.colCacheMu.RUnlock()
	if ok && time.Now().Before(entry.expiresAt) {
		return entry.id, nil
	}

	respBody, status, err := c.do(ctx, "GET", v2Base+"/collections/"+name, nil)
	if err != nil {
		return "", err
	}
	if status != 200 {
		return "", fmt.Errorf("get collection %s: status %d — %s", name, status, string(respBody))
	}
	var col struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(respBody, &col); err != nil {
		return "", fmt.Errorf("unmarshal: %w", err)
	}

	// Cache for 10 minutes
	c.colCacheMu.Lock()
	c.colCache[name] = colCacheEntry{id: col.ID, expiresAt: time.Now().Add(10 * time.Minute)}
	c.colCacheMu.Unlock()

	return col.ID, nil
}

func (c *ChromaDB) Upsert(ctx context.Context, collection string, docs []VectorDocument) error {
	colID, err := c.getCollectionID(ctx, collection)
	if err != nil {
		return err
	}

	ids := make([]string, len(docs))
	embeddings := make([][]float32, len(docs))
	documents := make([]string, len(docs))
	metadatas := make([]map[string]any, len(docs))

	for i, d := range docs {
		ids[i] = d.ID
		embeddings[i] = d.Embedding
		documents[i] = d.Content
		metadatas[i] = d.Metadata
	}

	body := map[string]interface{}{
		"ids":        ids,
		"embeddings": embeddings,
		"documents":  documents,
		"metadatas":  metadatas,
	}

	respBody, status, err := c.do(ctx, "POST", v2Base+"/collections/"+colID+"/upsert", body)
	if err != nil {
		return fmt.Errorf("upsert: %w", err)
	}
	if status != 200 {
		return fmt.Errorf("upsert: status %d — %s", status, string(respBody))
	}
	return nil
}

func (c *ChromaDB) Delete(ctx context.Context, collection string, filter map[string]any) error {
	colID, err := c.getCollectionID(ctx, collection)
	if err != nil {
		return err
	}

	body := map[string]interface{}{"where": filter}
	_, status, err := c.do(ctx, "POST", v2Base+"/collections/"+colID+"/delete", body)
	if err != nil {
		return fmt.Errorf("delete: %w", err)
	}
	if status != 200 {
		return fmt.Errorf("delete: status %d", status)
	}
	return nil
}

func (c *ChromaDB) Query(ctx context.Context, collection string, queryVec []float32, opts QueryOpts) ([]VectorSearchResult, error) {
	colID, err := c.getCollectionID(ctx, collection)
	if err != nil {
		return nil, err
	}

	topK := opts.TopK
	if topK == 0 {
		topK = 10
	}

	body := map[string]interface{}{
		"query_embeddings": [][]float32{queryVec},
		"n_results":        topK,
		"include":          []string{"documents", "metadatas", "distances"},
	}
	if len(opts.Filter) > 0 {
		body["where"] = opts.Filter
	}

	respBody, status, err := c.do(ctx, "POST", v2Base+"/collections/"+colID+"/query", body)
	if err != nil {
		return nil, fmt.Errorf("query: %w", err)
	}
	if status != 200 {
		return nil, fmt.Errorf("query: status %d — %s", status, string(respBody))
	}

	var result struct {
		IDs       [][]string         `json:"ids"`
		Documents [][]string         `json:"documents"`
		Metadatas [][]map[string]any `json:"metadatas"`
		Distances [][]float64        `json:"distances"`
	}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal query result: %w", err)
	}

	if len(result.IDs) == 0 || len(result.IDs[0]) == 0 {
		return nil, nil
	}

	var results []VectorSearchResult
	for i, id := range result.IDs[0] {
		score := 1.0 - result.Distances[0][i]
		if score < opts.MinScore {
			continue
		}
		r := VectorSearchResult{
			ID:    id,
			Score: score,
		}
		if i < len(result.Documents[0]) {
			r.Content = result.Documents[0][i]
		}
		if i < len(result.Metadatas[0]) {
			r.Metadata = result.Metadatas[0][i]
		}
		results = append(results, r)
	}
	return results, nil
}

// CollectionDimension returns the embedding dimension stored in the
// collection, or 0 if the collection is empty (no dimension lock yet).
//
// Implementation: probe the collection with a 1-element query vector. Chroma
// rejects mismatched dimensions with "Collection expecting embedding with
// dimension of N, got 1". We parse N from that error message.
//
// Why probe instead of /get + parse embeddings? Because ChromaDB versions
// vary in whether `include: ["embeddings"]` actually returns embeddings —
// some versions return null/empty even when explicitly requested. The
// dimension-mismatch error path is universal across versions because it
// comes from Chroma's HNSW index validation, not response serialization.
func (c *ChromaDB) CollectionDimension(ctx context.Context, collection string) (int, error) {
	colID, err := c.getCollectionID(ctx, collection)
	if err != nil {
		return 0, err
	}

	body := map[string]interface{}{
		"query_embeddings": [][]float32{{0.0}},
		"n_results":        1,
		"include":          []string{"distances"},
	}
	respBody, status, doErr := c.do(ctx, "POST", v2Base+"/collections/"+colID+"/query", body)
	if doErr != nil {
		return 0, fmt.Errorf("dim probe: %w", doErr)
	}
	if status == 200 {
		// Probe accepted → collection has no dimension lock (empty), OR is
		// genuinely 1D (impossible for any real embedder, so safe to treat as empty).
		return 0, nil
	}

	// Status != 200 — parse "dimension of <N>" from the error body.
	bodyStr := string(respBody)
	idx := strings.Index(bodyStr, "dimension of ")
	if idx < 0 {
		return 0, fmt.Errorf("dim probe: unexpected response (status %d): %s", status, bodyStr)
	}
	rest := bodyStr[idx+len("dimension of "):]
	var n int
	for i := 0; i < len(rest); i++ {
		ch := rest[i]
		if ch < '0' || ch > '9' {
			break
		}
		n = n*10 + int(ch-'0')
	}
	if n == 0 {
		return 0, fmt.Errorf("dim probe: could not parse dimension from %q", bodyStr)
	}
	return n, nil
}

func (c *ChromaDB) Count(ctx context.Context, collection string) (int, error) {
	colID, err := c.getCollectionID(ctx, collection)
	if err != nil {
		return 0, err
	}
	respBody, status, err := c.do(ctx, "GET", v2Base+"/collections/"+colID+"/count", nil)
	if err != nil {
		return 0, err
	}
	if status != 200 {
		return 0, fmt.Errorf("count: status %d", status)
	}
	var count int
	if err := json.Unmarshal(respBody, &count); err != nil {
		return 0, fmt.Errorf("unmarshal count: %w", err)
	}
	return count, nil
}
