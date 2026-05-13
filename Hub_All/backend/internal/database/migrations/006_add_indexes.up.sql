-- ================================================================
-- Migration: 006_add_indexes.up.sql
-- Add missing indexes for query performance
-- ================================================================

-- user_hub_roles: filter by hub_id (JOIN in user queries)
CREATE INDEX IF NOT EXISTS idx_user_hub_roles_hub ON user_hub_roles (hub_id);

-- api_keys: lookup by created_by (list user's keys)
CREATE INDEX IF NOT EXISTS idx_api_keys_created_by ON api_keys (created_by);

-- api_keys: lookup by status for active key queries
CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys (status);

-- documents: filter by uploaded_by (user's documents)
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents (uploaded_by);

-- audit_logs: composite index for common filtered queries
CREATE INDEX IF NOT EXISTS idx_audit_action_ts ON audit_logs (action, timestamp DESC);

-- audit_logs: user activity tracking
CREATE INDEX IF NOT EXISTS idx_audit_user_ts ON audit_logs (user_id, timestamp DESC);
