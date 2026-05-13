package rag

import "math"

// ALG-001 Scoring Algorithm
// FinalScore = CosineSimilarity × 0.60 + Popularity × 0.20 + Recency × 0.20 + VerifiedBonus (+0.05)

const (
	WeightSimilarity = 0.60
	WeightPopularity = 0.20
	WeightRecency    = 0.20
	VerifiedBonus    = 0.05
	RecencyHalfLife  = 30.0 // days
)

type ScoringInput struct {
	CosineSimilarity float64
	ViewCount        int
	MaxViewCount     int
	DaysSinceUpdate  float64
	IsVerified       bool
}

func ComputeScore(input ScoringInput) float64 {
	// Cosine similarity (0-1)
	sim := input.CosineSimilarity

	// Popularity: log scale
	pop := 0.0
	if input.MaxViewCount > 0 {
		pop = math.Log(1+float64(input.ViewCount)) / math.Log(1+float64(input.MaxViewCount))
	}

	// Recency: exponential decay, half-life = 30 days
	rec := math.Exp(-0.693 * input.DaysSinceUpdate / RecencyHalfLife)

	score := sim*WeightSimilarity + pop*WeightPopularity + rec*WeightRecency

	if input.IsVerified {
		score += VerifiedBonus
	}

	return score
}
