package chunker

import (
	"regexp"
	"strings"
)

// EntityProfileChunker implements Level 1 from RAG Pipeline v3:
// for documents containing doctor/expert profiles (T3-01 Hồ sơ BS E-E-A-T),
// group all content between entity headings into a single profile chunk.
//
// Logic:
//  1. Find headings matching a medical-title prefix + proper noun
//     (BS/TTUT/BSCKII/LY/CGYHCT + Given Name)
//  2. Collect everything from one entity heading to the next as one chunk
//  3. Never split E-E-A-T tables or channel-assignment tables inside a profile
//  4. Tag with entity_name + entity_aliases metadata
//
// If no entity pattern is found, Chunk returns nil and the caller should
// fall back to its default chunker.
type EntityProfileChunker struct {
	MaxChunkTokens int // soft cap; profiles are not split even if exceeded
}

// entityHeadingRe matches a full heading line that looks like an entity title.
// Example matches:
//
//	# TTUT BSCKII Lê Phương
//	## BS Trần Hải Long
//	### LY Đỗ Minh Tuấn
var entityHeadingRe = regexp.MustCompile(`(?m)^(#{1,6})\s+((?:TTUT|BSCKII?|BS|TS|PGS|GS|TH\.S|LY|CGYHCT)(?:\s+[A-ZÀ-Ỹ][\wÀ-ỹ]*){1,5})\s*$`)

// Chunk scans the text and returns one chunk per detected entity profile.
// Returns nil if no entity headings are present.
func (c *EntityProfileChunker) Chunk(text string) []Chunk {
	locs := entityHeadingRe.FindAllStringSubmatchIndex(text, -1)
	if len(locs) == 0 {
		return nil
	}

	var result []Chunk
	for i, loc := range locs {
		// loc[0:1] = full match start; loc[4:5] = entity name group
		headingLine := text[loc[0]:loc[1]]
		entityName := strings.TrimSpace(text[loc[4]:loc[5]])

		// Content spans from this heading's end to the next heading's start
		contentStart := loc[0]
		contentEnd := len(text)
		if i+1 < len(locs) {
			contentEnd = locs[i+1][0]
		}
		content := strings.TrimSpace(text[contentStart:contentEnd])
		if content == "" {
			continue
		}

		// Prepend a contextual header so the chunk is self-explanatory
		ctxHeader := "[Hồ sơ nhân vật: " + entityName + "]\n"
		finalContent := ctxHeader + content

		result = append(result, Chunk{
			Index:      i,
			Content:    finalContent,
			TokenCount: CountTokens(finalContent),
			StartChar:  contentStart,
			EndChar:    contentEnd,
			ChunkType:  "entity_profile",
			Metadata: map[string]any{
				"level":       "L1",
				"entity_name": entityName,
				"heading":     strings.TrimLeft(headingLine, "# \t"),
			},
		})
	}

	return result
}
