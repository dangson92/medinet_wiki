-- ================================================================
-- Migration: 004_audit.up.sql
-- Audit Logs (partitioned by month)
-- ================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID DEFAULT gen_random_uuid(),
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    user_id     UUID,
    user_name   VARCHAR(100),
    is_ai       BOOLEAN DEFAULT FALSE,
    action      VARCHAR(50) NOT NULL,
    target      VARCHAR(255),
    hub_id      UUID,
    hub_name    VARCHAR(100),
    ip_address  INET,
    user_agent  TEXT,
    request_id  UUID,
    duration_ms INT,
    payload     JSONB,
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Create partitions for current and next months
CREATE TABLE IF NOT EXISTS audit_logs_2026_04 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS audit_logs_2026_05 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS audit_logs_2026_06 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS audit_logs_default PARTITION OF audit_logs DEFAULT;

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_hub ON audit_logs(hub_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
