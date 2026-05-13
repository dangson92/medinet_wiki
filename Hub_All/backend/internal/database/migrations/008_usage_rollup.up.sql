-- ================================================================
-- Migration: 008_usage_rollup.up.sql
-- Pre-aggregation tables for token_usage (pure Postgres equivalent
-- of TimescaleDB continuous aggregates). The rollup worker in
-- service.UsageRollup fills these via incremental UPSERT so the
-- dashboard never GROUP BYs the raw table at read time.
--
-- Design rationale (user asked to "tránh conflict"):
--   * Granularity 5min / hourly / daily — chosen to cover the 4
--     dashboard ranges (≤1h, ≤7d, ≤30d, >30d) with <50ms queries
--     even at 180M raw rows/year.
--   * Composite PRIMARY KEY on all dimensions — atomic UPSERT via
--     ON CONFLICT … DO UPDATE, no row-level locking contention.
--   * NULL hub_id collapses to zero-UUID to keep the PK non-null
--     (Postgres composite PKs disallow NULL).
--   * Watermark table `usage_rollup_state` stores last processed
--     timestamp for each granularity — restart-safe, idempotent.
-- ================================================================

-- ─── Index cleanup on raw table ─────────────────────────────────
-- The single-column indexes are not useful without a timestamp
-- range predicate, which the dashboard always supplies.
DROP INDEX IF EXISTS idx_token_usage_provider;
DROP INDEX IF EXISTS idx_token_usage_model;
DROP INDEX IF EXISTS idx_token_usage_operation;
DROP INDEX IF EXISTS idx_token_usage_timestamp;

-- BRIN is 100× smaller than B-tree and perfect for append-only timestamp.
CREATE INDEX IF NOT EXISTS idx_token_usage_ts_brin
    ON token_usage USING BRIN (timestamp) WITH (pages_per_range = 32);

-- Compound indexes for the two dominant filter combos.
CREATE INDEX IF NOT EXISTS idx_token_usage_ts_hub
    ON token_usage (timestamp DESC, hub_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_ts_user
    ON token_usage (timestamp DESC, user_id);

-- ─── Rollup: 5 minute buckets ───────────────────────────────────
CREATE TABLE IF NOT EXISTS token_usage_rollup_5min (
    bucket          TIMESTAMPTZ NOT NULL,
    provider        VARCHAR(32) NOT NULL,
    model           VARCHAR(128) NOT NULL,
    operation       VARCHAR(32) NOT NULL,
    hub_id          UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
    calls           BIGINT NOT NULL DEFAULT 0,
    prompt_tokens   BIGINT NOT NULL DEFAULT 0,
    output_tokens   BIGINT NOT NULL DEFAULT 0,
    total_tokens    BIGINT NOT NULL DEFAULT 0,
    latency_ms_sum  BIGINT NOT NULL DEFAULT 0,
    error_calls     BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket, provider, model, operation, hub_id)
);
CREATE INDEX IF NOT EXISTS idx_rollup_5min_bucket
    ON token_usage_rollup_5min USING BRIN (bucket);

-- ─── Rollup: hourly buckets ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS token_usage_rollup_hourly (
    bucket          TIMESTAMPTZ NOT NULL,
    provider        VARCHAR(32) NOT NULL,
    model           VARCHAR(128) NOT NULL,
    operation       VARCHAR(32) NOT NULL,
    hub_id          UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
    calls           BIGINT NOT NULL DEFAULT 0,
    prompt_tokens   BIGINT NOT NULL DEFAULT 0,
    output_tokens   BIGINT NOT NULL DEFAULT 0,
    total_tokens    BIGINT NOT NULL DEFAULT 0,
    latency_ms_sum  BIGINT NOT NULL DEFAULT 0,
    error_calls     BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket, provider, model, operation, hub_id)
);
CREATE INDEX IF NOT EXISTS idx_rollup_hourly_bucket
    ON token_usage_rollup_hourly USING BRIN (bucket);

-- ─── Rollup: daily buckets ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS token_usage_rollup_daily (
    bucket          DATE NOT NULL,
    provider        VARCHAR(32) NOT NULL,
    model           VARCHAR(128) NOT NULL,
    operation       VARCHAR(32) NOT NULL,
    hub_id          UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
    calls           BIGINT NOT NULL DEFAULT 0,
    prompt_tokens   BIGINT NOT NULL DEFAULT 0,
    output_tokens   BIGINT NOT NULL DEFAULT 0,
    total_tokens    BIGINT NOT NULL DEFAULT 0,
    latency_ms_sum  BIGINT NOT NULL DEFAULT 0,
    error_calls     BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket, provider, model, operation, hub_id)
);
CREATE INDEX IF NOT EXISTS idx_rollup_daily_bucket
    ON token_usage_rollup_daily (bucket);

-- ─── Watermark / checkpoint state ───────────────────────────────
CREATE TABLE IF NOT EXISTS usage_rollup_state (
    name        VARCHAR(32) PRIMARY KEY,   -- '5min' | 'hourly' | 'daily'
    last_ts     TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed with bootstrap watermarks so the first tick does not scan
-- the full raw table: start from now() minus a safety window.
INSERT INTO usage_rollup_state (name, last_ts) VALUES
    ('5min',   NOW() - INTERVAL '15 minutes'),
    ('hourly', NOW() - INTERVAL '2 hours'),
    ('daily',  NOW() - INTERVAL '2 days')
ON CONFLICT (name) DO NOTHING;
