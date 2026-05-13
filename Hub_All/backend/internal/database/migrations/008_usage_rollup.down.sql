-- Revert: 008_usage_rollup
DROP TABLE IF EXISTS token_usage_rollup_5min   CASCADE;
DROP TABLE IF EXISTS token_usage_rollup_hourly CASCADE;
DROP TABLE IF EXISTS token_usage_rollup_daily  CASCADE;
DROP TABLE IF EXISTS usage_rollup_state        CASCADE;

-- Restore original single-column indexes
CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp ON token_usage(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_token_usage_provider  ON token_usage(provider);
CREATE INDEX IF NOT EXISTS idx_token_usage_model     ON token_usage(model);
CREATE INDEX IF NOT EXISTS idx_token_usage_operation ON token_usage(operation);

DROP INDEX IF EXISTS idx_token_usage_ts_brin;
DROP INDEX IF EXISTS idx_token_usage_ts_hub;
DROP INDEX IF EXISTS idx_token_usage_ts_user;
