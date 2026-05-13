# CLAUDE.md — Medinet Wiki (Hub_All)

> Hướng dẫn cho Claude làm việc trong repository này. Toàn bộ giao tiếp BẰNG TIẾNG VIỆT có dấu (xem `~/.claude/CLAUDE.md`). Tên kỹ thuật, REQ-ID, lệnh shell, đường dẫn file giữ nguyên tiếng Anh.

---

## 1. Tổng quan dự án

**Medinet Wiki** là hệ thống quản lý tri thức nội bộ đa-Hub cho Medinet — wiki + RAG + MCP. Codebase này (`Hub_All/`) chứa:

- `backend/` — Go 1.25 · Gin · pgx/v5 (PostgreSQL 16) · Redis 7 · ChromaDB · JWT RS256. Layered architecture: handler → service → repository.
- `frontend/` — React 19 · Vite 6 · TypeScript 5.8 · Tailwind v4. Hiện là **single SPA** (multi-SPA defer sang M2).
- `docling-pipeline/` — **service Python mới (M1)**: FastAPI sidecar bọc Docling cho extract + chunk chất lượng cao.
- `eval/` — **dataset + scripts** đo so sánh extractor native vs Docling (M1).
- `documents/` — PRD v1.3, RAG Pipeline v3, BACKEND_DEVELOPMENT_PLAN, các prompt design.
- `chroma_data/` — vector store persistence (KHÔNG commit).
- `.planning/` — GSD planning docs (PROJECT, REQUIREMENTS, ROADMAP, STATE, codebase map).

**Core value (M1):** Ingestion tri thức Medinet phải tái hiện trung thực cấu trúc tài liệu nguồn (heading, bảng, ảnh có chú thích, công thức, OCR tiếng Việt cho scanned PDF) — biến mọi tài liệu y tế / dược / HCNS thành chunk semantic giàu metadata, để top-3 retrieval đạt ≥ 75% trên eval set thật.

## 2. Milestone hiện tại

**M1 — RAG Quality with Docling** · Granularity: standard · Mode: YOLO · 5 phases · 32 REQ.

> Pivot 2026-04-28: M1 cũ (Multi-subdomain SPA) defer sang M2. Lý do: RAG quality kém là blocker thực sự cho production; SPA chỉ là kiến trúc deploy, không tạo giá trị nếu RAG kém. Tham chiếu git history: commit `bca2ede` / `2bd9f56` / `e00fda7` (M1 cũ).

| # | Phase | Trọng tâm | REQ |
|---|-------|----------|-----|
| 1 | Eval Dataset & Baseline Native | Build `eval/dataset/` + queries vàng + baseline measurement với extractor Go hiện tại | EVAL-01 |
| 2 | Docling Service (Python Sidecar) | Stand up `docling-pipeline/` FastAPI + Docling v2.91+, OCR `vie+eng`, HybridChunker | DSVC-01..06, EXTRACT-01..05, CHUNK-01..04 |
| 3 | Go Adapter & Pipeline Wiring | `DoclingExtractor` Go, refactor interface, `pipeline.go` branch theo preChunks | WIRE-01..06, CHUNK-05 |
| 4 | Config Hot-Swap & Circuit Breaker | `RAG_EXTRACTOR=docling\|native\|auto`, fallback, admin endpoint, audit log | CFG-01..05 |
| 5 | Eval Compare & Quality Gate | Scripts so sánh trước/sau, EVAL.md, gate ≥ +15pp hoặc ≥ 75% top-3 | EVAL-02..05 |

Phase 2 và 3 có thể chạy song song nếu Phase 3 dùng mock service trước.

## 3. Quy tắc làm việc

### Ngôn ngữ
- Tất cả tài liệu sinh ra (PLAN.md, REVIEW.md, SPEC.md, commit message phần mô tả, PR body) viết tiếng Việt có dấu.
- KHÔNG xen đoạn tiếng Anh dài. Chỉ giữ tiếng Anh cho: tên hàm/biến, lệnh code, REQ-ID, tên thư viện, đường dẫn file, prefix commit (`feat:` `fix:` `chore:` `docs:` `test:`).

### GSD workflow
- Mỗi phase: `/gsd-discuss-phase N` → `/gsd-plan-phase N` → `/gsd-execute-phase N`. Mode YOLO → có thể chạy `/gsd-autonomous` để chuỗi tự động.
- Các tài liệu nguồn sự thật: `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`.
- Không sửa REQ-ID đã commit; thay đổi requirement phải qua `/gsd-discuss-phase` hoặc commit có lý do rõ trong message.

### Constraint M1 (RAG Quality)
- **Service split chuẩn:** `docling-pipeline/` (Python) chỉ làm extract + chunk. Embedding pipeline ở Go KHÔNG đổi — vẫn `SwappableEmbedder` (OpenAI/Gemini) + ChromaDB upsert + usage logging async.
- **Fallback bắt buộc:** `RAG_EXTRACTOR=auto` mặc định — Docling fail liên tục N lần → fallback `native` trong T phút rồi tự retry. Pipeline RAG KHÔNG được đứng im khi service Python down.
- **Embedding model:** Giữ OpenAI/Gemini hot-swap. KHÔNG thêm sentence-transformers / BGE-M3 trong M1 (defer v2).
- **Vector DB:** Giữ ChromaDB. KHÔNG migrate Qdrant/pgvector.

### Code conventions (tóm tắt từ `.planning/codebase/CONVENTIONS.md`)
- **Backend Go:** layered (handler/service/repository/model). Error wrap `fmt.Errorf("...: %w", err)`. Logging `log/slog`. Helper `pkg/response` chuẩn hoá `{success, data, error, meta}`. Lệnh: `make build`, `make run`, `make lint` (= `golangci-lint`), `make test`.
- **Frontend React:** Context API cho global state (`AuthContext`, `ThemeContext`). API client tập trung tại `frontend/src/services/api.ts`. CHƯA có ESLint/Prettier — `npm run lint` thực chất là `tsc --noEmit`. Lệnh: `npm run dev`, `npm run build`, `npm run lint`.
- **Python service `docling-pipeline/`** (mới): FastAPI + Docling, structured JSON logging, propagate `X-Request-Id` từ Go. Pin chính xác phiên bản Docling + Tesseract Vietnamese language pack. Format/lint: ruff (chọn ở phase 2).

### Testing
- Coverage backend/frontend hiện tại **0%**. Việc thêm test tổng quát hoãn sang milestone "Production Hardening" riêng — M1 chỉ thêm test cho Python service (`docling-pipeline/tests/`) và eval scripts.

### Concerns đáng nhớ (chi tiết: `.planning/codebase/CONCERNS.md`)
- Thiếu `.gitignore` root → `chroma_data/` (1.3 MB + 20 MB) và `backend/keys/*.json` (GCP service account) có nguy cơ bị commit. Nếu khắc phục, tạo task riêng — KHÔNG mix vào commit M1.
- Token JWT lưu `localStorage` (XSS risk) — hoãn sang milestone hardening.
- `IS_HUB_TONG = false` ở `frontend/src/pages/DocumentIngestion.tsx:43-45` thuộc M2 (Multi-subdomain SPA) — KHÔNG đụng trong M1.
- Nếu Docling service cần đọc credential cloud nào, đọc từ `.env` — KHÔNG hard-code.

## 4. Lệnh GSD nhanh

| Lệnh | Khi dùng |
|------|---------|
| `/gsd-progress` | Xem trạng thái milestone hiện tại |
| `/gsd-plan-phase N` | Lập plan chi tiết cho phase N |
| `/gsd-execute-phase N` | Thực thi plan đã được duyệt |
| `/gsd-verify-work N` | UAT phase N |
| `/gsd-next` | Tự động đi tiếp bước hợp lý kế tiếp |
| `/gsd-debug` | Khi gặp bug khó |
| `/gsd-help` | Bảng đầy đủ |

## 5. Cấu trúc commit

- Phần prefix tiếng Anh chuẩn: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- Phần mô tả tiếng Việt có dấu, ngắn gọn, nói "tại sao" trước "làm gì".
- Mỗi plan trong phase commit atomic — không gộp nhiều plan vào một commit.

---

*Cập nhật: 2026-04-28 (pivot M1 sang RAG Quality with Docling) · Project: MEDWIKI · Phase 1 sẵn sàng để `/gsd-plan-phase 1`.*
