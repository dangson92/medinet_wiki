package chunker

import (
	"regexp"
	"strings"
)

// DocumentType classifies a document to select the appropriate chunking strategy.
// This implements the Document Type Router from RAG Pipeline v3 (§2G + §3).
type DocumentType string

const (
	DocTypeOperational   DocumentType = "operational"   // T3-01 hồ sơ BS, T3-02 phân công, SOP
	DocTypeArticle       DocumentType = "article"       // PR, blog, báo chí
	DocTypeResearch      DocumentType = "research"      // Bài nghiên cứu học thuật
	DocTypeClinical      DocumentType = "clinical"      // Bài thuốc, phác đồ, báo cáo lâm sàng
	DocTypeUnstructured  DocumentType = "unstructured"  // Transcript, ghi chú, OCR kém
	DocTypeGeneral       DocumentType = "general"       // Không rơi vào các nhóm trên
)

// ChunkingStrategy describes which chunkers and techniques to apply for a document.
type ChunkingStrategy struct {
	DocType      DocumentType
	Levels       []string // Which of the 9 levels to run: "L1","L2",...,"L9"
	Hierarchical bool     // Produce parent-child chunks
	Contextual   bool     // Use LLM contextual retrieval
	Proposition  bool     // Decompose into propositions (expensive)
	Agentic      bool     // LLM-as-chunker (fallback for unstructured)
	LateChunking bool     // Token-level embedding + mean pool (requires embed_tokens)
}

// DetectDocumentType classifies a document using rule-based pattern matching.
//
// Priority order (first match wins):
//  1. Operational: contains entity pattern (BS/TTUT/BSCKII + name) AND channel matrix keywords
//  2. Clinical: contains prescription/protocol patterns
//  3. Research: IMRaD structure (Tóm tắt / Tài liệu tham khảo) without prescription
//  4. Article: has CTA / quotes / case study patterns
//  5. General: fallback
func DetectDocumentType(text string) DocumentType {
	if text == "" {
		return DocTypeGeneral
	}
	lower := strings.ToLower(text)

	// 1. Operational — DMD internal docs
	if reEntityTitle.MatchString(text) && reChannelKeyword.MatchString(lower) {
		return DocTypeOperational
	}

	// 2. Clinical — prescription/protocol
	clinicalHits := 0
	if rePrescription.MatchString(lower) {
		clinicalHits++
	}
	if reDosage.MatchString(text) {
		clinicalHits++
	}
	if reTreatmentProtocol.MatchString(lower) {
		clinicalHits++
	}
	if clinicalHits >= 2 {
		return DocTypeClinical
	}

	// 3. Research — IMRaD structure
	researchHits := 0
	if strings.Contains(lower, "tóm tắt") || strings.Contains(lower, "abstract") {
		researchHits++
	}
	if strings.Contains(lower, "tài liệu tham khảo") || strings.Contains(lower, "references") {
		researchHits++
	}
	if strings.Contains(lower, "nghiên cứu") || strings.Contains(lower, "phương pháp") {
		researchHits++
	}
	if researchHits >= 2 && clinicalHits == 0 {
		return DocTypeResearch
	}

	// 4. Article — PR / blog
	articleHits := 0
	if reCaseStudy.MatchString(lower) {
		articleHits++
	}
	if reExpertQuote.MatchString(text) {
		articleHits++
	}
	if reCTA.MatchString(lower) {
		articleHits++
	}
	if articleHits >= 2 {
		return DocTypeArticle
	}

	// 5. Unstructured — very low structure (no heading, no bullet)
	if countHeadings(text) == 0 && countBullets(text) == 0 && len(text) > 2000 {
		return DocTypeUnstructured
	}

	return DocTypeGeneral
}

// StrategyFor returns the chunking strategy for a given document type.
// This is the routing table from RAG Pipeline v3 §3.
func StrategyFor(docType DocumentType, tokens int) ChunkingStrategy {
	switch docType {
	case DocTypeOperational:
		return ChunkingStrategy{
			DocType:      docType,
			Levels:       []string{"L1", "L2", "L3", "L4", "L5", "L6", "L9"},
			Hierarchical: true,
			Contextual:   tokens >= 8000,
			LateChunking: tokens < 8000,
		}

	case DocTypeArticle:
		return ChunkingStrategy{
			DocType:      docType,
			Levels:       []string{"L5", "L7", "L9"},
			Hierarchical: true,
			Contextual:   tokens >= 8000,
			LateChunking: tokens < 8000,
		}

	case DocTypeResearch:
		return ChunkingStrategy{
			DocType:      docType,
			Levels:       []string{"L7", "L9"},
			Hierarchical: true,
			Contextual:   true, // always
			Proposition:  false, // opt-in — expensive
		}

	case DocTypeClinical:
		return ChunkingStrategy{
			DocType:      docType,
			Levels:       []string{"L5", "L8A", "L8B", "L8C", "L9"},
			Hierarchical: true,
			Contextual:   true,
			LateChunking: tokens < 8000,
		}

	case DocTypeUnstructured:
		return ChunkingStrategy{
			DocType:    docType,
			Levels:     []string{},
			Contextual: true,
			Agentic:    true,
		}

	default: // DocTypeGeneral
		return ChunkingStrategy{
			DocType:      docType,
			Levels:       []string{"L7"},
			Hierarchical: false,
			LateChunking: tokens < 8000,
		}
	}
}

// ─── Detection patterns ───

var (
	// Vietnamese medical title prefix + given name
	reEntityTitle = regexp.MustCompile(`(?i)(BS|TTUT|TS|BSCKI|BSCKII|LY|CGYHCT|TH\.S|GS|PGS)\.?\s+[A-ZÀ-Ỹ][a-zà-ỹ]+`)

	// Channel matrix keywords — must appear multiple times
	reChannelKeyword = regexp.MustCompile(`(?i)tiktok|youtube|facebook|website|(?:^|\s)pr(?:\s|$)|t[uư] v[aấ]n`)

	// Prescription indicators
	rePrescription = regexp.MustCompile(`(?i)(bài thuốc|phương thuốc|sắc uống|dược liệu|vị thuốc)`)

	// Dosage: "Hoàng Kỳ 12g", "Bạch Truật 10g"
	reDosage = regexp.MustCompile(`[A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+)?\s+\d+\s*(?:g|ml|mg|thìa)`)

	// Treatment protocol
	reTreatmentProtocol = regexp.MustCompile(`(?i)(phác đồ|quy trình điều trị|bước \d|giai đoạn \d|tuần \d+.?\d+|điều trị)`)

	// Article case study: "bệnh nhân X tuổi", "anh A, 45 tuổi"
	reCaseStudy = regexp.MustCompile(`(?i)(bệnh nhân|case|anh|chị)\s+[^\s]+.*?\d+\s*tuổi`)

	// Expert quote — quoted text + doctor title nearby
	reExpertQuote = regexp.MustCompile(`["“][^"”]{20,}["”].*?(BS|TTUT|TS|BSCKII)`)

	// CTA — call to action
	reCTA = regexp.MustCompile(`(?i)(liên hệ|đặt lịch|hotline|địa chỉ|đăng ký khám)`)
)

func countHeadings(text string) int {
	count := 0
	for _, line := range strings.Split(text, "\n") {
		if strings.HasPrefix(strings.TrimSpace(line), "#") {
			count++
		}
	}
	return count
}

func countBullets(text string) int {
	count := 0
	for _, line := range strings.Split(text, "\n") {
		t := strings.TrimSpace(line)
		if strings.HasPrefix(t, "- ") || strings.HasPrefix(t, "* ") || strings.HasPrefix(t, "• ") {
			count++
		}
	}
	return count
}
