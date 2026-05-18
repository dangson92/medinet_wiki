---
id: SEED-001
status: dormant
planted: 2026-05-18
planted_during: "M2 (v2.0 Full RAG Rewrite) — sau Phase 5, trước Phase 6"
trigger_when: "Bắt đầu milestone v4.1; hoặc sớm hơn nếu (a) yêu cầu bảo mật dữ liệu y tế cấm gửi text ra API bên thứ ba, (b) chi phí embedding cloud tăng cao, (c) cần chạy offline/air-gapped"
scope: Medium
---

# SEED-001: Tùy chọn embedding model local (HuggingFace sentence-transformers)

## Vì sao điều này quan trọng

Hiện tại (M2) bước embedding bắt buộc gọi API OpenAI/Gemini qua LiteLLM (quyết
định D5) → mỗi chunk tài liệu được gửi ra dịch vụ bên thứ ba và cần API key trả
phí. Một tùy chọn embedding model **chạy local** (HuggingFace sentence-transformers)
giải quyết 3 vấn đề:

- **Bảo mật dữ liệu y tế** — nội dung bệnh án / tài liệu nội bộ Medinet KHÔNG rời
  hạ tầng nội bộ. Đây là lý do mạnh nhất: nếu có ràng buộc tuân thủ cấm gửi dữ
  liệu y tế ra API ngoài, embedding local là bắt buộc.
- **Không cần API key + không chi phí biến đổi** — embedding chạy on-premise,
  không phụ thuộc hạn mức / giá OpenAI/Gemini.
- **Chạy offline / air-gapped** — triển khai trong mạng nội bộ không Internet.

## Khi nào nên surface

**Trigger:** Bắt đầu milestone v4.1 — đã ghi sẵn trong `ROADMAP.md` mục
"Out of Scope (M2)": dòng *"Local embedding model (v4.1)"*.

Seed này nên được trình ra trong `/gsd-new-milestone` khi scope milestone mới
khớp một trong các điều kiện:

- Milestone v4.1 được mở (target mặc định).
- Xuất hiện yêu cầu bảo mật / tuân thủ cấm gửi nội dung tài liệu y tế ra API
  bên thứ ba (OpenAI/Gemini) — kích hoạt sớm hơn v4.1.
- Chi phí embedding cloud tăng đáng kể hoặc hạn mức API trở thành nút thắt.
- Cần triển khai offline / air-gapped (mạng nội bộ không Internet).

## Ước lượng quy mô

**Medium** — một tới hai phase, cần planning. Không chỉ "thêm một setting" vì
chạm tới schema vector và một quyết định kiến trúc đã chốt.

Phạm vi triển khai khi làm:

1. `config.py` — thêm provider `huggingface` + tên model local + device (cpu/cuda).
2. `embedder.py` — rẽ nhánh theo provider: load model sentence-transformers dạng
   **singleton** (load 1 lần, không load mỗi chunk); `model.encode()` là sync
   CPU-bound → wrap `asyncio.to_thread` để không block event loop.
3. **Đổi số chiều vector** — model local hầu như không ra 1536 chiều
   (vd `dangvantuan/vietnamese-embedding` = 768, `BAAI/bge-m3` = 1024). Cần:
   migration đổi cột `chunks.vector` sang `vector(768)` (hoặc 1024);
   `EMBEDDING_DIM` chuyển thành config-driven; cập nhật `_VECTOR_SCHEMA` +
   `ChunkRow.vector` trong `rag/flow.py`.
4. Dependency mới nặng: `sentence-transformers` + `torch` (vài trăm MB–GB).
5. Cập nhật logic R7 cross-dim refuse (hiện refuse 400 khi swap khác dim).

## Model đề xuất (tiếng Việt y tế)

- `dangvantuan/vietnamese-embedding` — **768 chiều**, chuyên tiếng Việt, nhẹ
  (user đã chọn phương án này trong phiên thảo luận 2026-05-18).
- `BAAI/bge-m3` — 1024 chiều, đa ngôn ngữ mạnh hơn — phương án thay thế.

## Xung đột cần ghi nhận (LOCKED decisions sẽ bị đảo)

- **D5** — "Embedding provider: OpenAI / Gemini hot-swap qua LiteLLM". Thêm
  provider local là một deviation khỏi D5 → cần cập nhật quyết định khi làm.
- **R1 / R7** — "PIN embedding dim 1536". Model local buộc đổi dim → phá pin
  1536. Lưu ý dim mới (768/1024) vẫn dưới giới hạn HNSW 2000 nên pgvector OK,
  nhưng một index HNSW chỉ chứa được vector cùng dim.

## Lưu ý thời điểm

Tại 2026-05-18 bảng `chunks` đang **rỗng** (0 row) — đổi dim lúc này gần như
miễn phí (chỉ migration, không re-embed). Nhưng tới v4.1 corpus đã có dữ liệu
thật → đổi provider/dim sẽ phải **re-embed toàn bộ corpus**. Đây là chi phí
chính khi kích hoạt seed muộn.

## Breadcrumbs

Code và quyết định liên quan trong codebase hiện tại:

- `Hub_All/api/app/services/embedder.py` — wrapper LiteLLM `embed_text`; nơi sẽ
  rẽ nhánh provider local. Hằng `EMBEDDING_DIM = 1536`.
- `Hub_All/api/app/config.py` — `Settings.rag_embedding_provider` /
  `rag_embedding_model` / `rag_embedding_dim`; nơi thêm provider `huggingface`.
- `Hub_All/api/app/rag/flow.py` — `_VECTOR_SCHEMA` (VectorSchema dim 1536) +
  `ChunkRow.vector` + `_embed_one`; cần đồng bộ dim mới.
- `Hub_All/api/migrations/versions/` — migration `0001` tạo `chunks.vector
  vector(1536)` + HNSW index; cần migration đổi dim.
- `Hub_All/.planning/ROADMAP.md` — mục "Out of Scope (M2)" dòng "Local embedding
  model (v4.1)"; Phase 7 success criteria #4 (R7 cross-dim refuse).
- `Hub_All/CLAUDE.md` — section 3: "Embedding dim PIN 1536" (R1) + "Embedding
  provider OpenAI/Gemini qua LiteLLM" (D5).

## Notes

Seed này phát sinh từ phiên 2026-05-18: user hỏi vì sao xử lý tài liệu cần API
key. Kết luận — CocoIndex (framework) không cần key, nhưng bước embedding gọi
model cloud (D5) thì cần. User muốn thêm option model local; đối chiếu ROADMAP
thấy việc này đã nằm "Out of Scope M2 → v4.1" nên giữ nguyên kế hoạch, ghi seed
thay vì chèn phase. M2 tiếp tục dùng cloud (cần điền `OPENAI_API_KEY` /
`GEMINI_API_KEY` thật vào `.env` — hiện đang là placeholder).
