-- ================================================================
-- Migration: 007_token_usage.up.sql
-- Token & API usage logs (partitioned by month, like audit_logs).
-- Tracks every external AI/embedding API call: provider, model,
-- token counts, latency, status. Inserted asynchronously via a
-- buffered batch worker (see service.UsageLogger) to avoid blocking
-- request-path goroutines and to coalesce DB writes.
-- ================================================================

CREATE TABLE IF NOT EXISTS token_usage (
    id              UUID DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    provider        VARCHAR(32)  NOT NULL,        -- gemini | openai
    model           VARCHAR(128) NOT NULL,        -- gemini-2.0-flash, gpt-4o-mini, ...
    operation       VARCHAR(32)  NOT NULL,        -- chat | embed
    source_module   VARCHAR(64),                  -- ai_chat | rag_answer | rag_embed | chunker_contextual ...
    user_id         UUID,
    user_name       VARCHAR(100),
    hub_id          UUID,
    request_count   INT          NOT NULL DEFAULT 1,
    prompt_tokens   INT          NOT NULL DEFAULT 0,
    output_tokens   INT          NOT NULL DEFAULT 0,
    total_tokens    INT          NOT NULL DEFAULT 0,
    latency_ms      INT          NOT NULL DEFAULT 0,
    status          VARCHAR(16)  NOT NULL DEFAULT 'success', -- success | error
    error_message   TEXT,
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

CREATE TABLE IF NOT EXISTS token_usage_2026_04 PARTITION OF token_usage
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS token_usage_2026_05 PARTITION OF token_usage
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS token_usage_2026_06 PARTITION OF token_usage
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS token_usage_default PARTITION OF token_usage DEFAULT;

CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp ON token_usage(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_token_usage_provider  ON token_usage(provider);
CREATE INDEX IF NOT EXISTS idx_token_usage_model     ON token_usage(model);
CREATE INDEX IF NOT EXISTS idx_token_usage_operation ON token_usage(operation);
CREATE INDEX IF NOT EXISTS idx_token_usage_user      ON token_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_hub       ON token_usage(hub_id);
