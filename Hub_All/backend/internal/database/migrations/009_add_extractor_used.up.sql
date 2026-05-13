-- ================================================================
-- Migration: 009_add_extractor_used.up.sql
-- M1 Phase 4 (CFG-06) — Lưu extractor được dùng cho ingestion cuối
-- cùng của mỗi document để admin truy vết chất lượng từng tài liệu.
--
-- Lý do chọn cột scalar VARCHAR(20) thay vì JSONB metadata:
--   * Bảng documents hiện chưa có cột metadata — tránh thêm cột phụ.
--   * Cần index/filter dễ cho dashboard tương lai
--     (WHERE extractor_used='docling' AND status='completed').
--   * Giá trị enum hữu hạn (docling | native | NULL) → CHECK constraint
--     gọn nhẹ, không cần GIN index hay JSON cast.
-- ================================================================

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS extractor_used VARCHAR(20)
        CHECK (extractor_used IN ('docling','native'));

CREATE INDEX IF NOT EXISTS idx_documents_extractor_used
    ON documents(extractor_used);

COMMENT ON COLUMN documents.extractor_used IS
    'Extractor được dùng cho ingestion cuối cùng (CFG-06 M1 Phase 4). NULL = chưa ingest hoặc ingest trước M1.';
