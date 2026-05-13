-- ================================================================
-- Migration: 003_sync.up.sql
-- Sync Workflow: Hub Dự Án → Hub Tổng
-- ================================================================

CREATE TABLE IF NOT EXISTS sync_batches (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hub_id            UUID REFERENCES hubs(id) NOT NULL,
    hub_name          VARCHAR(100) NOT NULL,
    page_count        INT NOT NULL,
    files_summary     JSONB DEFAULT '{}',
    total_size        BIGINT DEFAULT 0,
    submitted_by      UUID REFERENCES users(id) NOT NULL,
    submitted_by_name VARCHAR(100) NOT NULL,
    status            VARCHAR(20) DEFAULT 'pending'
                      CHECK (status IN ('pending','processing','completed')),
    approved_count    INT DEFAULT 0,
    rejected_count    INT DEFAULT 0,
    submitted_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sync_pages (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id           UUID REFERENCES sync_batches(id) ON DELETE CASCADE,
    title              VARCHAR(500) NOT NULL,
    file_name          VARCHAR(500) NOT NULL,
    file_type          VARCHAR(10) NOT NULL
                       CHECK (file_type IN ('pdf','docx','txt','md','xlsx','pptx','jpg','png','csv','html')),
    file_size          BIGINT DEFAULT 0,
    content            TEXT NOT NULL,
    category           VARCHAR(100),
    tags               TEXT[],
    author             VARCHAR(100),
    status             VARCHAR(20) DEFAULT 'pending'
                       CHECK (status IN ('pending','approved','rejected')),
    rejection_reason   TEXT,
    similarity_score   FLOAT,
    similar_page_id    UUID,
    similar_page_title VARCHAR(500),
    reviewed_by        UUID REFERENCES users(id),
    reviewed_at        TIMESTAMPTZ,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sync_batches_status ON sync_batches(status);
CREATE INDEX IF NOT EXISTS idx_sync_batches_hub ON sync_batches(hub_id);
CREATE INDEX IF NOT EXISTS idx_sync_pages_batch ON sync_pages(batch_id);
CREATE INDEX IF NOT EXISTS idx_sync_pages_status ON sync_pages(status);
