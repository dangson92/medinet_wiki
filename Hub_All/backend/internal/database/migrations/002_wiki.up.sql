-- ================================================================
-- Migration: 002_wiki.up.sql
-- Wiki Pages, Categories, Tags, Page Versions
-- ================================================================

-- ─────────────── Categories (Tree Structure) ───────────────
CREATE TABLE IF NOT EXISTS categories (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hub_id     UUID REFERENCES hubs(id) NOT NULL,
    name       VARCHAR(100) NOT NULL,
    slug       VARCHAR(100) NOT NULL,
    parent_id  UUID REFERENCES categories(id),
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(hub_id, slug)
);

-- ─────────────── Tags ───────────────
CREATE TABLE IF NOT EXISTS tags (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hub_id     UUID REFERENCES hubs(id) NOT NULL,
    name       VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(hub_id, name)
);

-- ─────────────── Wiki Pages ───────────────
CREATE TABLE IF NOT EXISTS pages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hub_id        UUID REFERENCES hubs(id) NOT NULL,
    title         VARCHAR(500) NOT NULL,
    slug          VARCHAR(500) NOT NULL,
    content       TEXT NOT NULL,
    content_html  TEXT,
    category_id   UUID REFERENCES categories(id),
    author_id     UUID NOT NULL,
    status        VARCHAR(20) DEFAULT 'published'
                  CHECK (status IN ('draft','pending_review','published','archived')),
    view_count    INT DEFAULT 0,
    is_verified   BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    deleted_at    TIMESTAMPTZ,
    UNIQUE(hub_id, slug)
);

-- ─────────────── Page-Tag Junction ───────────────
CREATE TABLE IF NOT EXISTS page_tags (
    page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    tag_id  UUID REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (page_id, tag_id)
);

-- ─────────────── Page Version History ───────────────
CREATE TABLE IF NOT EXISTS page_versions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id        UUID REFERENCES pages(id) ON DELETE CASCADE,
    version        INT NOT NULL,
    title          VARCHAR(500) NOT NULL,
    content        TEXT NOT NULL,
    changed_by     UUID NOT NULL,
    change_summary VARCHAR(500),
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(page_id, version)
);

-- ─────────────── Indexes ───────────────
CREATE INDEX IF NOT EXISTS idx_pages_hub ON pages(hub_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_pages_fts ON pages
    USING GIN(to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(content,'')));
CREATE INDEX IF NOT EXISTS idx_pages_category ON pages(category_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_pages_updated ON pages(updated_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_page_versions_page ON page_versions(page_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_categories_hub ON categories(hub_id);
CREATE INDEX IF NOT EXISTS idx_tags_hub ON tags(hub_id);

CREATE TRIGGER trg_pages_updated_at
    BEFORE UPDATE ON pages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_categories_updated_at
    BEFORE UPDATE ON categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
