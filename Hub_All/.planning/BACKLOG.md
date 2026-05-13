# Backlog — Medinet Wiki (MEDWIKI)

Parking lot cho ý tưởng/cải thiện chưa thuộc milestone hiện tại. Promote sang milestone bằng `/gsd-review-backlog` hoặc thủ công khi quyết định ưu tiên.

**Format:** số 999.X (decimal), mỗi item có context + ROI estimate + suggested target milestone.

---

## 999.1 — Backend batch embedding (1 chunk/call → 100/batch)

**Phát sinh từ:** Phase 1 Eval baseline 2026-04-28. `DMD_T1-03_Script_Library` (283 chunks) timeout 180s khi baseline.py poll. Backend Go `internal/embedding/openai.go` đang gọi 1 chunk/API request → 4253 OpenAI calls trong 1 giờ test.

**Vấn đề:**
- OpenAI hỗ trợ batch tối đa 100 input/request → giảm 100x latency.
- Cost không đổi (tính theo tokens) nhưng wall-clock time giảm 90%+.
- Backend Go ingestion 10 file × 200 chunks hiện tại = ~5-15 phút; với batch sẽ < 1 phút.

**ROI:** 🔴 Cao. Performance critical cho production khi user upload nhiều file.

**Effort:** ~1 ngày (sửa `backend/internal/embedding/openai.go` + `gemini.go` để batch + wrapper `SwappableEmbedder` truyền batch). Có thể test với eval baseline (re-run sẽ < 1 phút thay vì 5-15 phút).

**Target milestone:** **M2 hoặc M3 "Performance & Production Hardening"** (sau khi M1 Docling ship). Không phải blocker M1 — chỉ làm baseline chạy chậm, không ảnh hưởng quality metrics.

**Refs:**
- `backend/internal/embedding/openai.go` (call hiện tại 1-by-1).
- `backend/internal/embedding/swappable.go` (wrapper).
- `eval/baseline.py` (sẽ benchmark trước/sau).

---

## 999.2 — Reranker layer (BGE / Cohere / Voyage rerank top-50 → top-5)

**Phát sinh từ:** Phase 1 Eval baseline 2026-04-28. Sau fix `min_score`, baseline native đã đạt 75% top-3. Phase 5 Docling kỳ vọng đạt ~91-100%. Reranker là bước tiếp theo để boost thêm 5-10pp khi cần đẩy chất lượng lên ngưỡng cao hơn.

**Vấn đề:**
- Vector similarity (cosine) chỉ là approximate semantic match. Khi dataset lớn (>1000 chunks/Hub), top-5 vector dễ bị nhiễu — cần re-rank lại bằng cross-encoder.
- BGE-reranker-v2 (free, multilingual VN), Cohere Rerank ($), Voyage Rerank ($) đều tốt cho tiếng Việt.
- Cải tiến typical: +5-10pp top-3 hit rate; với q05 (table disambiguation T1-01 vs T3-02) có khả năng fix.

**ROI:** 🟡 Trung bình. Boost quality khi đã có dataset đủ lớn; với 10 file eval thì gain marginal.

**Effort:** ~2-3 ngày.
- Thêm `internal/rag/reranker/` package với interface + 2 impl (BGE local Python sidecar / Cohere API).
- Wire vào `searcher.go` sau bước vector retrieval (top-50 → rerank → top-K).
- Hot-swap như embedder/LLM.
- Eval lại trên Phase 1 dataset.

**Target milestone:** **M3 "Hybrid retrieval + Reranker"** (sau M2 hardening). PRD §7.3 đã nhắc tới Hybrid retrieval BM25+vector — gắn liền với reranker.

**Refs:**
- PRD §7.3 (Hybrid Retrieval — Phase 2).
- `backend/internal/rag/searcher.go` (vị trí inject reranker).
- BGE-reranker-v2-m3 (multilingual, MIT license).

---

## Quy ước

- Items defer khi: ngoài scope milestone hiện tại + không phải blocker + chưa đủ dữ liệu để chốt design.
- Promote khi: milestone hiện tại đóng + còn capacity + ROI vẫn còn cao theo tình hình mới.
- Mỗi item bắt buộc có: trigger (tại sao xuất hiện), ROI, effort, target milestone — để khi promote không cần re-research.

---

*Last updated: 2026-04-28 sau Phase 1 baseline eval (top-3 41.7% → 75% sau fix min_score)*
