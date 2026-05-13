package vectorstore

import "context"

type VectorStore interface {
	CreateCollection(ctx context.Context, name string) error
	DeleteCollection(ctx context.Context, name string) error
	ListCollections(ctx context.Context) ([]string, error)

	Upsert(ctx context.Context, collection string, docs []VectorDocument) error
	Delete(ctx context.Context, collection string, filter map[string]any) error
	Query(ctx context.Context, collection string, queryVec []float32, opts QueryOpts) ([]VectorSearchResult, error)
	Count(ctx context.Context, collection string) (int, error)

	// CollectionDimension returns the embedding dimension stored in the
	// collection. Returns 0 when the collection is empty (no dimension lock
	// yet) so callers can distinguish "no constraint" from "mismatch".
	CollectionDimension(ctx context.Context, collection string) (int, error)
}

type VectorDocument struct {
	ID        string
	Content   string
	Embedding []float32
	Metadata  map[string]any
}

type QueryOpts struct {
	TopK     int
	MinScore float64
	Filter   map[string]any
}

type VectorSearchResult struct {
	ID       string
	Content  string
	Score    float64
	Metadata map[string]any
}
