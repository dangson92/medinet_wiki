package embedding

import "context"

// EmbeddingProvider is the interface for text embedding services.
type EmbeddingProvider interface {
	Embed(ctx context.Context, texts []string) ([][]float32, error)
	ModelName() string
	Dimension() int
}
