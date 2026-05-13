package rag

import (
	"context"
	"fmt"
	"log/slog"
	"regexp"
	"strings"
	"time"

	"github.com/medinet/hub-all-backend/internal/llm"
	"github.com/medinet/hub-all-backend/internal/model"
)

// Answerer generates natural language answers from search results using LLM.
type Answerer struct {
	llm      llm.LLM
	searcher *Searcher
}

func NewAnswerer(l llm.LLM, s *Searcher) *Answerer {
	return &Answerer{llm: l, searcher: s}
}

// AnswerRequest is the input for generating an answer.
type AnswerRequest struct {
	Query  string   `json:"query"`
	HubIDs []string `json:"hub_ids"`
	TopK   int      `json:"top_k"`
}

// AnswerResponse is the output with AI-generated answer + sources + inline citations.
type AnswerResponse struct {
	Answer        string               `json:"answer"`
	Sources       []AnswerSource       `json:"sources"`
	Citations     []CitationRef        `json:"citations"`
	SearchResults []model.SearchResult `json:"search_results"`
	QueryTimeMs   int64                `json:"query_time_ms"`
	Model         string               `json:"model"`
}

// AnswerSource references where the answer came from (aggregate view).
type AnswerSource struct {
	DocName string  `json:"doc_name"`
	HubName string  `json:"hub_name"`
	Snippet string  `json:"snippet"`
	Score   float64 `json:"score"`
}

// CitationRef describes one inline citation that the LLM emitted in the answer
// via a [src:<chunk_id>] marker. Frontend renders `[N]` superscripts and
// shows the snippet in a popover when users hover/click.
type CitationRef struct {
	ID           string  `json:"id"`            // chunk id (chroma_id) the LLM cited
	Marker       string  `json:"marker"`        // literal substring the LLM emitted, e.g. "[src:abc_chunk_3]"
	Number       int     `json:"number"`        // 1-based ordinal in order of first appearance
	DocumentID   string  `json:"document_id"`   // parent document uuid (best-effort, may be empty)
	DocumentName string  `json:"document_name"` // display title
	HubName      string  `json:"hub_name"`
	ChunkIndex   int     `json:"chunk_index"`
	Snippet      string  `json:"snippet"`
	Score        float64 `json:"score"`
}

// citationMarkerRe matches `[src:<id>]` where <id> is any non-space, non-`]` chars.
// LLM-friendly syntax: IDs may include dashes, underscores, digits.
var citationMarkerRe = regexp.MustCompile(`\[src:([^\]\s]+)\]`)

// Answer performs search → collect context → generate answer via LLM.
func (a *Answerer) Answer(ctx context.Context, req AnswerRequest, hubs []model.Hub) (*AnswerResponse, error) {
	start := time.Now()

	if req.TopK <= 0 {
		req.TopK = 5
	}

	// 1. Search for relevant chunks
	searchReq := model.SearchRequest{
		Query:  req.Query,
		HubIDs: req.HubIDs,
		TopK:   req.TopK,
	}

	var searchResp *model.SearchResponse
	var err error
	if len(hubs) == 1 {
		searchResp, err = a.searcher.Search(ctx, searchReq, hubs[0])
	} else {
		searchResp, err = a.searcher.CrossHubSearch(ctx, searchReq, hubs)
	}
	if err != nil {
		return nil, fmt.Errorf("search: %w", err)
	}

	if len(searchResp.Results) == 0 {
		return &AnswerResponse{
			Answer:      "Không tìm thấy thông tin liên quan trong hệ thống tri thức.",
			Sources:     nil,
			Citations:   nil,
			QueryTimeMs: time.Since(start).Milliseconds(),
			Model:       a.llm.Name(),
		}, nil
	}

	// 2. Build context block — each chunk is labeled with its chunk id so the
	//    LLM can cite it inline. Also build the aggregate Sources array.
	var contextParts []string
	var sources []AnswerSource
	for i, r := range searchResp.Results {
		contextParts = append(contextParts, fmt.Sprintf(
			"[Nguồn %d | id=%s | %s | %s | match %.0f%%]\n%s",
			i+1, r.ID, r.Title, r.HubName, r.Score*100, r.Snippet,
		))
		sources = append(sources, AnswerSource{
			DocName: r.Title,
			HubName: r.HubName,
			Snippet: truncateRunes(r.Snippet, 150),
			Score:   r.Score,
		})
	}
	contextText := strings.Join(contextParts, "\n\n---\n\n")

	// 3. Build prompt with inline-citation instructions
	prompt := buildRAGPrompt(req.Query, contextText)

	// 4. Generate answer via LLM
	answer, err := a.llm.Generate(ctx, prompt)
	if err != nil {
		return nil, fmt.Errorf("generate answer: %w", err)
	}

	// 5. Parse [src:...] markers from the answer and map to retrieved chunks.
	//    Unknown ids (LLM hallucinations) are stripped from the answer text so
	//    they never leak to clients (web/MCP/external API). Hallucination rate
	//    is logged for quality monitoring.
	citations := extractCitations(answer, searchResp.Results)
	answer, dropped := stripHallucinatedMarkers(answer, citations)
	if dropped > 0 {
		slog.Warn("rag.answerer: dropped hallucinated citation markers",
			"query", req.Query,
			"model", a.llm.Name(),
			"hub_count", len(hubs),
			"top_k_returned", len(searchResp.Results),
			"valid_citations", len(citations),
			"dropped_markers", dropped,
		)
	}

	return &AnswerResponse{
		Answer:        answer,
		Sources:       sources,
		Citations:     citations,
		SearchResults: searchResp.Results,
		QueryTimeMs:   time.Since(start).Milliseconds(),
		Model:         a.llm.Name(),
	}, nil
}

// stripHallucinatedMarkers removes any [src:<id>] marker whose <id> is not in
// the validated citations list. Returns the cleaned answer and the count of
// removed markers (for telemetry). Trailing whitespace introduced by the
// removal is collapsed so the prose stays clean.
func stripHallucinatedMarkers(answer string, citations []CitationRef) (string, int) {
	if answer == "" {
		return answer, 0
	}
	valid := make(map[string]struct{}, len(citations))
	for _, c := range citations {
		valid[c.ID] = struct{}{}
	}
	var dropped int
	cleaned := citationMarkerRe.ReplaceAllStringFunc(answer, func(m string) string {
		sub := citationMarkerRe.FindStringSubmatch(m)
		if len(sub) < 2 {
			return ""
		}
		if _, ok := valid[sub[1]]; ok {
			return m
		}
		dropped++
		return ""
	})
	// Collapse runs of spaces and clean up "punctuation followed by space" left
	// behind when a marker was removed mid-sentence: "abc . [src:x] xyz" → "abc . xyz".
	cleaned = multiSpaceRe.ReplaceAllString(cleaned, " ")
	cleaned = spaceBeforePunctRe.ReplaceAllString(cleaned, "$1")
	return cleaned, dropped
}

var (
	multiSpaceRe       = regexp.MustCompile(`[ \t]{2,}`)
	spaceBeforePunctRe = regexp.MustCompile(` +([.,;:!?])`)
)

// extractCitations scans the answer text for [src:<id>] markers and builds a
// deduplicated, numbered list of CitationRef entries that map back to entries
// in `results`. IDs that don't appear in results (LLM hallucination or typo)
// are ignored.
func extractCitations(answer string, results []model.SearchResult) []CitationRef {
	if answer == "" || len(results) == 0 {
		return nil
	}
	// Build a lookup from chunk id → search result.
	resByID := make(map[string]*model.SearchResult, len(results))
	for i := range results {
		resByID[results[i].ID] = &results[i]
	}

	matches := citationMarkerRe.FindAllStringSubmatchIndex(answer, -1)
	if len(matches) == 0 {
		return nil
	}

	out := make([]CitationRef, 0)
	seen := make(map[string]int) // id → number assigned
	for _, m := range matches {
		// m = [fullStart, fullEnd, groupStart, groupEnd]
		fullStart, fullEnd := m[0], m[1]
		idStart, idEnd := m[2], m[3]
		id := answer[idStart:idEnd]
		r, ok := resByID[id]
		if !ok {
			continue
		}
		if _, dup := seen[id]; dup {
			continue
		}
		num := len(out) + 1
		seen[id] = num

		// Best-effort parse: chroma id is "<documentID>_chunk_<N>". Recover
		// document id and chunk index without failing if the format differs.
		docID, chunkIdx := parseChromaID(r.ID)

		out = append(out, CitationRef{
			ID:           id,
			Marker:       answer[fullStart:fullEnd],
			Number:       num,
			DocumentID:   docID,
			DocumentName: r.Title,
			HubName:      r.HubName,
			ChunkIndex:   chunkIdx,
			Snippet:      truncateRunes(r.Snippet, 220),
			Score:        r.Score,
		})
	}
	return out
}

// parseChromaID splits "<docID>_chunk_<N>" into (docID, N). Returns ("", 0) on
// unexpected shapes.
func parseChromaID(id string) (string, int) {
	idx := strings.LastIndex(id, "_chunk_")
	if idx < 0 {
		return "", 0
	}
	docID := id[:idx]
	var n int
	_, err := fmt.Sscanf(id[idx+len("_chunk_"):], "%d", &n)
	if err != nil {
		return docID, 0
	}
	return docID, n
}

func buildRAGPrompt(query, context string) string {
	return fmt.Sprintf(`Bạn là trợ lý tri thức của hệ thống Medinet Wiki. Nhiệm vụ của bạn là trả lời câu hỏi dựa HOÀN TOÀN trên dữ liệu được cung cấp bên dưới.

## Quy tắc:
1. CHỈ trả lời dựa trên thông tin trong phần "Dữ liệu tham khảo" bên dưới.
2. Nếu dữ liệu không đủ để trả lời, nói rõ "Dữ liệu hiện có chưa đủ để trả lời đầy đủ câu hỏi này".
3. KHÔNG bịa thêm thông tin ngoài dữ liệu.
4. **BẮT BUỘC trích dẫn nội tuyến.** Sau MỖI mệnh đề lấy từ dữ liệu, chèn ngay marker theo định dạng chính xác:
   [src:<id>]
   trong đó <id> là trường "id=..." của nguồn tương ứng (ví dụ: [src:abc123_chunk_5]). Không đổi dạng, không thêm khoảng trắng giữa "src:" và id.
5. **TUYỆT ĐỐI KHÔNG bịa id.** Quy tắc bất di bất dịch về id:
   - CHỈ ĐƯỢC PHÉP dùng id xuất hiện nguyên văn trong dòng "[Nguồn N | id=... ]" của phần Dữ liệu tham khảo bên dưới.
   - KHÔNG suy luận, KHÔNG đoán pattern, KHÔNG tự tăng số chunk (vd: nếu chỉ có "id=abc_chunk_1" trong dữ liệu thì KHÔNG được viết [src:abc_chunk_2], [src:abc_chunk_3]...).
   - KHÔNG ghép id từ nhiều nguồn lại với nhau, KHÔNG đổi UUID, KHÔNG đổi số chunk.
   - Trước khi viết bất kỳ [src:<id>], hãy KIỂM TRA chuỗi id đó có khớp 100% với một dòng "id=..." trong dữ liệu hay không. Nếu không chắc → đừng cite mệnh đề đó.
   - Có thể ghép nhiều nguồn liên tiếp khi cùng support 1 mệnh đề: [src:id1] [src:id2].
   - Thà cite ÍT mà ĐÚNG còn hơn cite NHIỀU mà SAI. Marker bịa sẽ bị hệ thống phát hiện và xoá, kéo theo điểm chất lượng câu trả lời giảm.
6. Trả lời bằng tiếng Việt, rõ ràng, có cấu trúc (markdown hợp lý).
7. Nếu câu hỏi liên quan đến y khoa/thuốc, luôn ghi chú cuối câu trả lời: "Tham khảo ý kiến bác sĩ trước khi áp dụng."

## Ví dụ cách cite:
Câu hỏi: "BS Dương có tư vấn ung thư online không?"
Giả sử dữ liệu chỉ có 2 nguồn với id=550e8400_chunk_3 và id=550e8400_chunk_7.
Trả lời ĐÚNG: "Theo quy tắc của Medinet, BS Dương không chẩn đoán ung thư qua online [src:550e8400_chunk_3]. Khách hàng cần đặt lịch khám trực tiếp [src:550e8400_chunk_7]."
Trả lời SAI (bịa id): "...không chẩn đoán online [src:550e8400_chunk_3]. Cần đặt lịch [src:550e8400_chunk_4] [src:550e8400_chunk_5]." ← chunk_4 và chunk_5 KHÔNG có trong dữ liệu, TUYỆT ĐỐI cấm.

## Câu hỏi:
%s

## Dữ liệu tham khảo:
%s

## Trả lời (chỉ cite id có thật trong dữ liệu trên — KHÔNG bịa số chunk):`, query, context)
}
