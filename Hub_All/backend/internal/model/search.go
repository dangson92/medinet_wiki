package model

type SearchRequest struct {
	Query   string        `json:"query" binding:"required"`
	HubIDs  []string      `json:"hub_ids"`
	TopK    int           `json:"top_k"`
	MinScore float64      `json:"min_score"`
	Filters SearchFilters `json:"filters"`
}

type SearchFilters struct {
	Categories []string `json:"categories"`
	Tags       []string `json:"tags"`
	DateFrom   string   `json:"date_from"`
	DateTo     string   `json:"date_to"`
}

type SearchResult struct {
	ID            string   `json:"id"`
	HubID         string   `json:"hub_id"`
	HubName       string   `json:"hub_name"`
	Title         string   `json:"title"`
	Snippet       string   `json:"snippet"`
	Content       string   `json:"content,omitempty"` // full chunk content for detail view
	Category      string   `json:"category,omitempty"`
	Tags          []string `json:"tags,omitempty"`
	Score         float64  `json:"score"`
	RawSimilarity float64  `json:"raw_similarity"`
	UpdatedAt     string   `json:"updated_at,omitempty"`
	Source        string   `json:"source"`
}

type SearchResponse struct {
	Results          []SearchResult `json:"results"`
	TotalHubsSearched int          `json:"total_hubs_searched"`
	QueryTimeMs      int64         `json:"query_time_ms"`
	CacheHit         bool          `json:"cache_hit"`
}

type SimilarRequest struct {
	Content   string  `json:"content" binding:"required"`
	HubID     string  `json:"hub_id"`
	Threshold float64 `json:"threshold"`
}

type SimilarMatch struct {
	PageID          string  `json:"page_id"`
	PageTitle       string  `json:"page_title"`
	SimilarityScore float64 `json:"similarity_score"`
	HubName         string  `json:"hub_name"`
}

type SimilarResponse struct {
	Matches []SimilarMatch `json:"matches"`
}
