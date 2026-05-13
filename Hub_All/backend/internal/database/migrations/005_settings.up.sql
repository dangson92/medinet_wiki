-- ================================================================
-- Migration: 005_settings.up.sql
-- System settings (key-value store, encrypted values for secrets)
-- ================================================================

CREATE TABLE IF NOT EXISTS settings (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT NOT NULL,
    is_secret   BOOLEAN DEFAULT FALSE,
    updated_by  UUID,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
