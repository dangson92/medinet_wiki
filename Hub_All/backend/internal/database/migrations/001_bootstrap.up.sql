-- ================================================================
-- Migration: 001_bootstrap.up.sql
-- CENTRAL DB — Minimal Foundation cho Phase 1 + Phase 2
-- ================================================================

-- ─────────────── Hubs ───────────────
CREATE TABLE IF NOT EXISTS hubs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    code            VARCHAR(50) UNIQUE NOT NULL,
    subdomain       VARCHAR(100) UNIQUE NOT NULL,
    description     TEXT,
    db_host         VARCHAR(255),
    db_port         INT DEFAULT 5432,
    db_name         VARCHAR(100),
    db_user         VARCHAR(100),
    db_password_enc TEXT,
    chroma_collection VARCHAR(100) NOT NULL,
    status          VARCHAR(20) DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────── Users ───────────────
CREATE TABLE IF NOT EXISTS users (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email              VARCHAR(255) UNIQUE NOT NULL,
    name               VARCHAR(100) NOT NULL,
    phone              VARCHAR(20),
    department         VARCHAR(100),
    password_hash      TEXT NOT NULL,
    avatar_url         VARCHAR(500),
    status             VARCHAR(20) DEFAULT 'active'
                       CHECK (status IN ('active', 'disabled')),
    failed_login_count INT DEFAULT 0,
    locked_until       TIMESTAMPTZ,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────── User-Hub Role Mapping ───────────────
CREATE TABLE IF NOT EXISTS user_hub_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    hub_id  UUID REFERENCES hubs(id) ON DELETE CASCADE,
    role    VARCHAR(30) NOT NULL
            CHECK (role IN ('admin', 'viewer')),
    PRIMARY KEY (user_id, hub_id)
);

-- ─────────────── API Keys ───────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    key_hash        TEXT NOT NULL,
    key_prefix      VARCHAR(12) NOT NULL,
    permissions     TEXT[] NOT NULL DEFAULT '{read}',
    allowed_hub_ids UUID[],
    allowed_rag_configs TEXT[],
    rate_limit      INT DEFAULT 60,
    expires_at      TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'active'
                    CHECK (status IN ('active', 'revoked')),
    requests_today  INT DEFAULT 0,
    requests_7d     INT DEFAULT 0,
    bandwidth_used  BIGINT DEFAULT 0,
    last_used_at    TIMESTAMPTZ,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────── Revoked Tokens ───────────────
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti        UUID PRIMARY KEY,
    user_id    UUID REFERENCES users(id),
    revoked_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires ON revoked_tokens(expires_at);

-- ─────────────── Documents ───────────────
-- Metadata tài liệu upload cho RAG pipeline
-- LƯU Ý: Ở giao diện Hub Tổng, module này hiển thị là "Danh sách tri thức"
-- Hub Tổng chỉ nhận và duyệt tri thức từ Hub con qua Sync Workflow,
-- KHÔNG có chức năng nạp tri thức mới (ẩn ở FE bằng flag IS_HUB_TONG).
-- Chỉ Hub Dự Án mới có quyền upload/compose/import tài liệu.
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(500) NOT NULL,
    file_type       VARCHAR(10) NOT NULL
                    CHECK (file_type IN ('pdf','docx','txt','md','xlsx','pptx','jpg','png','csv','html')),
    file_size       BIGINT,
    file_path       VARCHAR(1000),
    hub_id          UUID REFERENCES hubs(id) NOT NULL,
    status          VARCHAR(20) DEFAULT 'pending'
                    CHECK (status IN ('pending','processing','completed','error')),
    progress        INT DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    error_message   TEXT,
    chunk_count     INT DEFAULT 0,
    uploaded_by     UUID REFERENCES users(id),
    uploaded_at     TIMESTAMPTZ DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_documents_hub ON documents(hub_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

-- ─────────────── Document Chunks ───────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    token_count     INT,
    chroma_id       VARCHAR(100),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chroma ON document_chunks(chroma_id);

-- ─────────────── Updated At Trigger ───────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_hubs_updated_at
    BEFORE UPDATE ON hubs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
