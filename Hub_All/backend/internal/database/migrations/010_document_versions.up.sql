-- ================================================================
-- Migration: 010_document_versions.up.sql
-- Lịch sử phiên bản tài liệu tri thức.
--
-- Thiết kế:
--   * document_versions       — 1 row = 1 snapshot tại 1 thời điểm.
--   * document_version_chunks — bản chụp text chunks của version đó
--                               (KHÔNG re-embed Chroma — chỉ phục vụ
--                                hiển thị/diff/restore).
--   * Retention "3 gốc + 2 gần nhất": v1, v2, v3 luôn pin
--     (is_original=TRUE) + 2 version có version_number lớn nhất
--     được giữ. Còn lại auto DELETE bằng trigger AFTER INSERT.
--   * File binary của version cũ được lưu riêng dưới
--     storage/documents/{doc_id}/versions/v{n}.{ext} — application
--     code chịu trách nhiệm dọn file khi DB row bị xoá (qua
--     repository hook), Postgres KHÔNG biết filesystem.
-- ================================================================

-- ─────────────── document_versions ───────────────
CREATE TABLE IF NOT EXISTS document_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number  INT  NOT NULL,
    is_original     BOOLEAN NOT NULL DEFAULT FALSE,

    -- Snapshot metadata document tại version này
    name            VARCHAR(500) NOT NULL,
    file_type       VARCHAR(10)  NOT NULL,
    file_size       BIGINT       NOT NULL,
    file_path       VARCHAR(1000) NOT NULL,
    file_hash       VARCHAR(64),                       -- sha256 hex (nullable cho content_edit nếu skip)
    extractor_used  VARCHAR(20),
    chunk_count     INT NOT NULL DEFAULT 0,

    -- Lý do tạo version
    change_type     VARCHAR(20) NOT NULL
                    CHECK (change_type IN ('reupload','reextract','content_edit','restore')),
    change_note     TEXT,

    -- Audit
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (document_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_doc_versions_doc_id
    ON document_versions(document_id, version_number DESC);
CREATE INDEX IF NOT EXISTS idx_doc_versions_created_at
    ON document_versions(created_at DESC);

COMMENT ON TABLE  document_versions IS 'Lịch sử phiên bản tài liệu tri thức — retention 3 gốc + 2 gần nhất.';
COMMENT ON COLUMN document_versions.is_original IS 'TRUE cho v1/v2/v3 — pin vĩnh viễn để giữ "nguồn gốc xác thực".';
COMMENT ON COLUMN document_versions.change_type IS 'reupload | reextract | content_edit | restore';

-- ─────────────── document_version_chunks ───────────────
CREATE TABLE IF NOT EXISTS document_version_chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id   UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    chunk_index  INT  NOT NULL,
    content      TEXT NOT NULL,
    token_count  INT  NOT NULL DEFAULT 0,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,

    UNIQUE (version_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_doc_version_chunks_version_id
    ON document_version_chunks(version_id);

-- ─────────────── Retention trigger ───────────────
-- Sau mỗi INSERT vào document_versions, dọn các version "ở giữa":
--   keep = (is_original = TRUE)  ∪  TOP 2 version_number DESC.
-- Các row bị DELETE sẽ CASCADE xoá document_version_chunks.
-- File binary trên đĩa do application code dọn (xem
-- repository.PruneVersions). Trigger trả về tập file_path đã xoá
-- thông qua bảng tạm session-local document_version_pruned_files
-- để application đọc lại sau INSERT.
CREATE OR REPLACE FUNCTION prune_document_versions()
RETURNS TRIGGER AS $$
BEGIN
    -- Bảng tạm UNLOGGED per-session — cho phép Go code đọc danh
    -- sách file_path của version vừa bị prune mà KHÔNG cần round-trip
    -- riêng. Tạo nếu chưa có (idempotent trong cùng session).
    CREATE TEMP TABLE IF NOT EXISTS document_version_pruned_files (
        document_id UUID,
        file_path   VARCHAR(1000),
        pruned_at   TIMESTAMPTZ DEFAULT NOW()
    ) ON COMMIT PRESERVE ROWS;

    WITH ranked AS (
        SELECT id, file_path,
               ROW_NUMBER() OVER (
                   PARTITION BY document_id
                   ORDER BY version_number DESC
               ) AS recency_rank
        FROM document_versions
        WHERE document_id = NEW.document_id
    ),
    to_delete AS (
        SELECT r.id, r.file_path
        FROM ranked r
        JOIN document_versions v ON v.id = r.id
        WHERE v.is_original = FALSE
          AND r.recency_rank > 2
    ),
    archived AS (
        INSERT INTO document_version_pruned_files (document_id, file_path)
        SELECT NEW.document_id, file_path FROM to_delete
        RETURNING file_path
    )
    DELETE FROM document_versions
    WHERE id IN (SELECT id FROM to_delete);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_document_versions_prune ON document_versions;
CREATE TRIGGER trg_document_versions_prune
    AFTER INSERT ON document_versions
    FOR EACH ROW EXECUTE FUNCTION prune_document_versions();
