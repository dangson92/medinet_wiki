package repository

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/medinet/hub-all-backend/internal/model"
)

type UsageRepo struct {
	pool *pgxpool.Pool
}

func NewUsageRepo(pool *pgxpool.Pool) *UsageRepo {
	return &UsageRepo{pool: pool}
}

// InsertCopy uses pgx.CopyFrom for bulk insertion — ~5-10× faster than
// multi-VALUES INSERT at batch sizes ≥ 32. The UsageLogger service picks
// CopyFrom for large batches and falls back to InsertBatch for small ones
// to avoid the per-call overhead of opening a COPY cursor.
func (r *UsageRepo) InsertCopy(ctx context.Context, entries []model.TokenUsage) error {
	if len(entries) == 0 {
		return nil
	}
	rows := make([][]interface{}, len(entries))
	for i, e := range entries {
		if e.ID == uuid.Nil {
			e.ID = uuid.New()
		}
		rows[i] = []interface{}{
			e.ID, e.Timestamp, e.Provider, e.Model, e.Operation,
			e.SourceModule, e.UserID, e.UserName, e.HubID,
			e.RequestCount, e.PromptTokens, e.OutputTokens, e.TotalTokens,
			e.LatencyMs, e.Status, e.ErrorMessage,
		}
	}
	_, err := r.pool.CopyFrom(ctx,
		pgx.Identifier{"token_usage"},
		[]string{
			"id", "timestamp", "provider", "model", "operation",
			"source_module", "user_id", "user_name", "hub_id",
			"request_count", "prompt_tokens", "output_tokens", "total_tokens",
			"latency_ms", "status", "error_message",
		},
		pgx.CopyFromRows(rows),
	)
	if err != nil {
		return fmt.Errorf("copy token usage: %w", err)
	}
	return nil
}

// InsertBatch writes many records in a single round-trip. The UsageLogger
// service coalesces records to keep DB pressure bounded under burst load.
func (r *UsageRepo) InsertBatch(ctx context.Context, entries []model.TokenUsage) error {
	if len(entries) == 0 {
		return nil
	}

	const allCols = 16
	args := make([]interface{}, 0, len(entries)*allCols)
	placeholders := make([]string, 0, len(entries))
	for i, e := range entries {
		if e.ID == uuid.Nil {
			e.ID = uuid.New()
		}
		base := i * allCols
		ph := make([]string, allCols)
		for j := 0; j < allCols; j++ {
			ph[j] = fmt.Sprintf("$%d", base+j+1)
		}
		placeholders = append(placeholders, "("+strings.Join(ph, ",")+")")
		args = append(args,
			e.ID, e.Timestamp, e.Provider, e.Model, e.Operation,
			e.SourceModule, e.UserID, e.UserName, e.HubID,
			e.RequestCount, e.PromptTokens, e.OutputTokens, e.TotalTokens,
			e.LatencyMs, e.Status, e.ErrorMessage,
		)
	}

	query := `INSERT INTO token_usage (
		id, timestamp, provider, model, operation,
		source_module, user_id, user_name, hub_id,
		request_count, prompt_tokens, output_tokens, total_tokens,
		latency_ms, status, error_message
	) VALUES ` + strings.Join(placeholders, ",")

	if _, err := r.pool.Exec(ctx, query, args...); err != nil {
		return fmt.Errorf("insert token usage batch: %w", err)
	}
	return nil
}

func (r *UsageRepo) buildWhere(dateFrom, dateTo, provider, model, operation, hubID, status string) (string, []interface{}) {
	var conds []string
	var args []interface{}
	idx := 1
	add := func(c string, v interface{}) {
		conds = append(conds, fmt.Sprintf(c, idx))
		args = append(args, v)
		idx++
	}
	if dateFrom != "" {
		add("timestamp >= $%d::timestamptz", dateFrom)
	}
	if dateTo != "" {
		add("timestamp <= $%d::timestamptz", dateTo)
	}
	if provider != "" {
		add("provider = $%d", provider)
	}
	if model != "" {
		add("model = $%d", model)
	}
	if operation != "" {
		add("operation = $%d", operation)
	}
	if hubID != "" {
		add("hub_id = $%d", hubID)
	}
	if status != "" {
		add("status = $%d", status)
	}
	where := ""
	if len(conds) > 0 {
		where = " WHERE " + strings.Join(conds, " AND ")
	}
	return where, args
}

// MaxDetailRangeDays is the hard cap on the detail-table query window.
// The raw `token_usage` table can grow to ~180M rows/year; scanning an
// unbounded range would block Postgres workers and starve other queries.
// The dashboard UI enforces the same cap.
const MaxDetailRangeDays = 7

func (r *UsageRepo) List(ctx context.Context, dateFrom, dateTo, provider, modelName, operation, hubID, status string, page, perPage int) ([]model.TokenUsage, int64, error) {
	where, args := r.buildWhere(dateFrom, dateTo, provider, modelName, operation, hubID, status)
	idx := len(args) + 1

	var total int64
	if err := r.pool.QueryRow(ctx, "SELECT COUNT(*) FROM token_usage"+where, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count token usage: %w", err)
	}

	query := fmt.Sprintf(`
		SELECT id, timestamp, provider, model, operation,
		       source_module, user_id, user_name, hub_id,
		       request_count, prompt_tokens, output_tokens, total_tokens,
		       latency_ms, status, error_message
		FROM token_usage%s
		ORDER BY timestamp DESC
		LIMIT $%d OFFSET $%d
	`, where, idx, idx+1)

	offset := (page - 1) * perPage
	args = append(args, perPage, offset)

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("list token usage: %w", err)
	}
	defer rows.Close()

	var out []model.TokenUsage
	for rows.Next() {
		var e model.TokenUsage
		if err := rows.Scan(
			&e.ID, &e.Timestamp, &e.Provider, &e.Model, &e.Operation,
			&e.SourceModule, &e.UserID, &e.UserName, &e.HubID,
			&e.RequestCount, &e.PromptTokens, &e.OutputTokens, &e.TotalTokens,
			&e.LatencyMs, &e.Status, &e.ErrorMessage,
		); err != nil {
			return nil, 0, fmt.Errorf("scan token usage: %w", err)
		}
		out = append(out, e)
	}
	return out, total, nil
}

// Granularity determines which rollup table the Stats query reads from.
// Picked by the handler based on the requested date range:
//
//	≤ 7 days   → Gran5Min      (bucket = 5 min)
//	≤ 30 days  → GranHourly    (bucket = 1 hour)
//	> 30 days  → GranDaily     (bucket = 1 day)
//
// Raw table is NEVER GROUP BY'd at read time.
type Granularity string

const (
	Gran5Min   Granularity = "5min"
	GranHourly Granularity = "hourly"
	GranDaily  Granularity = "daily"
)

// rollupTable returns the SQL table name and the bucket-column type for a
// given granularity. All three tables share identical column layout, so
// the same query template works for each.
func rollupTable(g Granularity) string {
	switch g {
	case GranHourly:
		return "token_usage_rollup_hourly"
	case GranDaily:
		return "token_usage_rollup_daily"
	default:
		return "token_usage_rollup_5min"
	}
}

// bucketFormat chooses the TO_CHAR mask for the daily timeline array.
// 5min and hourly use a minute/hour precision; daily uses YYYY-MM-DD.
func bucketFormat(g Granularity) string {
	switch g {
	case GranDaily:
		return "YYYY-MM-DD"
	case GranHourly:
		return "YYYY-MM-DD HH24:00"
	default:
		return "YYYY-MM-DD HH24:MI"
	}
}

// StatsFromRollup reads pre-aggregated rollup rows and produces the dashboard
// stats payload in a single query per dimension (provider/model/op/timeline).
// Because rollup tables are 3-5 orders of magnitude smaller than the raw
// table, these queries return in single-digit ms even at 180M raw rows.
func (r *UsageRepo) StatsFromRollup(ctx context.Context, g Granularity, dateFrom, dateTo, provider, modelName, operation, hubID string) (*model.TokenUsageStats, error) {
	where, args := r.buildRollupWhere(dateFrom, dateTo, provider, modelName, operation, hubID)
	table := rollupTable(g)

	stats := &model.TokenUsageStats{}

	// Top-line totals — one roundtrip.
	totalsQ := fmt.Sprintf(`
		SELECT
			COALESCE(SUM(calls), 0)::bigint,
			COALESCE(SUM(total_tokens), 0)::bigint,
			COALESCE(SUM(prompt_tokens), 0)::bigint,
			COALESCE(SUM(output_tokens), 0)::bigint,
			COALESCE(SUM(error_calls), 0)::bigint,
			COALESCE(SUM(latency_ms_sum)::float8 / NULLIF(SUM(calls), 0), 0)::float8
		FROM %s%s
	`, table, where)
	if err := r.pool.QueryRow(ctx, totalsQ, args...).Scan(
		&stats.TotalCalls, &stats.TotalTokens, &stats.TotalPromptToks,
		&stats.TotalOutputToks, &stats.ErrorCalls, &stats.AvgLatencyMs,
	); err != nil {
		return nil, fmt.Errorf("scan totals (%s): %w", g, err)
	}

	var err error
	if stats.ByProvider, err = r.rollupGroupBy(ctx, table, "provider", where, args); err != nil {
		return nil, err
	}
	if stats.ByModel, err = r.rollupGroupBy(ctx, table, "model", where, args); err != nil {
		return nil, err
	}
	if stats.ByOperation, err = r.rollupGroupBy(ctx, table, "operation", where, args); err != nil {
		return nil, err
	}

	// Timeline — granularity matches the rollup bucket so this is a
	// straight pass-through without any extra GROUP BY beyond the PK.
	timelineQ := fmt.Sprintf(`
		SELECT TO_CHAR(bucket, '%s') AS b,
		       SUM(calls)::bigint,
		       SUM(total_tokens)::bigint
		FROM %s%s
		GROUP BY b ORDER BY b ASC
	`, bucketFormat(g), table, where)
	rows, err := r.pool.Query(ctx, timelineQ, args...)
	if err != nil {
		return nil, fmt.Errorf("timeline (%s): %w", g, err)
	}
	defer rows.Close()
	for rows.Next() {
		var p model.TokenUsageDailyPoint
		if err := rows.Scan(&p.Date, &p.Calls, &p.TotalTokens); err != nil {
			return nil, fmt.Errorf("scan timeline (%s): %w", g, err)
		}
		stats.Daily = append(stats.Daily, p)
	}

	return stats, nil
}

func (r *UsageRepo) buildRollupWhere(dateFrom, dateTo, provider, modelName, operation, hubID string) (string, []interface{}) {
	var conds []string
	var args []interface{}
	idx := 1
	add := func(tmpl string, v interface{}) {
		conds = append(conds, fmt.Sprintf(tmpl, idx))
		args = append(args, v)
		idx++
	}
	if dateFrom != "" {
		add("bucket >= $%d::timestamptz", dateFrom)
	}
	if dateTo != "" {
		add("bucket <= $%d::timestamptz", dateTo)
	}
	if provider != "" {
		add("provider = $%d", provider)
	}
	if modelName != "" {
		add("model = $%d", modelName)
	}
	if operation != "" {
		add("operation = $%d", operation)
	}
	if hubID != "" {
		add("hub_id = $%d", hubID)
	}
	where := ""
	if len(conds) > 0 {
		where = " WHERE " + strings.Join(conds, " AND ")
	}
	return where, args
}

func (r *UsageRepo) rollupGroupBy(ctx context.Context, table, col, where string, args []interface{}) ([]model.TokenUsageGroup, error) {
	q := fmt.Sprintf(`
		SELECT %s, SUM(calls)::bigint, SUM(total_tokens)::bigint
		FROM %s%s
		GROUP BY %s ORDER BY 3 DESC
	`, col, table, where, col)
	rows, err := r.pool.Query(ctx, q, args...)
	if err != nil {
		return nil, fmt.Errorf("rollup group by %s: %w", col, err)
	}
	defer rows.Close()
	var out []model.TokenUsageGroup
	for rows.Next() {
		var g model.TokenUsageGroup
		if err := rows.Scan(&g.Key, &g.Calls, &g.TotalTokens); err != nil {
			return nil, fmt.Errorf("scan rollup group %s: %w", col, err)
		}
		out = append(out, g)
	}
	return out, nil
}

// ─── Rollup write path (called by service.UsageRollup worker) ──

// UsageRollupState is the checkpoint watermark for one rollup granularity.
type UsageRollupState struct {
	Name    string
	LastTS  time.Time
}

func (r *UsageRepo) GetRollupState(ctx context.Context, name string) (UsageRollupState, error) {
	var s UsageRollupState
	s.Name = name
	err := r.pool.QueryRow(ctx,
		`SELECT last_ts FROM usage_rollup_state WHERE name = $1`, name,
	).Scan(&s.LastTS)
	if err == pgx.ErrNoRows {
		return s, nil
	}
	if err != nil {
		return s, fmt.Errorf("get rollup state %s: %w", name, err)
	}
	return s, nil
}

// RollupTick runs a single watermark-driven rollup pass for one granularity.
// ATOMIC: the aggregate UPSERT and the watermark UPDATE happen in one txn,
// so a crash between steps re-runs the same window idempotently (ON CONFLICT
// ADD is not idempotent by itself — atomicity is what makes it safe).
//
//   bucketExpr — SQL expression producing the bucket column from timestamp
//                (e.g. `date_trunc('hour', timestamp)`)
//   table      — rollup target
//   name       — state row name ('5min' | 'hourly' | 'daily')
//   grace      — how far behind `now()` we watermark, to avoid racing with
//                still-being-inserted rows (default 5s).
//
// Returns (rowsAggregated, newWatermark, err).
func (r *UsageRepo) RollupTick(ctx context.Context, name, table, bucketExpr string, grace time.Duration) (int64, time.Time, error) {
	tx, err := r.pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return 0, time.Time{}, fmt.Errorf("rollup tx begin: %w", err)
	}
	defer tx.Rollback(ctx) //nolint:errcheck // committed on success

	var lastTS time.Time
	err = tx.QueryRow(ctx, `SELECT last_ts FROM usage_rollup_state WHERE name=$1 FOR UPDATE`, name).Scan(&lastTS)
	if err != nil {
		return 0, time.Time{}, fmt.Errorf("rollup state lock %s: %w", name, err)
	}

	var newTS time.Time
	if err := tx.QueryRow(ctx, `SELECT NOW() - $1::interval`, grace.String()).Scan(&newTS); err != nil {
		return 0, time.Time{}, fmt.Errorf("rollup now: %w", err)
	}
	if !newTS.After(lastTS) {
		// Nothing new to roll up (tick fired faster than grace period).
		return 0, lastTS, tx.Commit(ctx)
	}

	upsertSQL := fmt.Sprintf(`
		INSERT INTO %s (bucket, provider, model, operation, hub_id,
		                calls, prompt_tokens, output_tokens, total_tokens,
		                latency_ms_sum, error_calls)
		SELECT %s AS bucket,
		       provider, model, operation,
		       COALESCE(hub_id, '00000000-0000-0000-0000-000000000000'::uuid),
		       SUM(request_count)::bigint,
		       SUM(prompt_tokens)::bigint,
		       SUM(output_tokens)::bigint,
		       SUM(total_tokens)::bigint,
		       SUM(latency_ms)::bigint,
		       SUM(CASE WHEN status='error' THEN 1 ELSE 0 END)::bigint
		FROM token_usage
		WHERE timestamp > $1 AND timestamp <= $2
		GROUP BY bucket, provider, model, operation,
		         COALESCE(hub_id, '00000000-0000-0000-0000-000000000000'::uuid)
		ON CONFLICT (bucket, provider, model, operation, hub_id) DO UPDATE SET
		    calls          = %s.calls          + EXCLUDED.calls,
		    prompt_tokens  = %s.prompt_tokens  + EXCLUDED.prompt_tokens,
		    output_tokens  = %s.output_tokens  + EXCLUDED.output_tokens,
		    total_tokens   = %s.total_tokens   + EXCLUDED.total_tokens,
		    latency_ms_sum = %s.latency_ms_sum + EXCLUDED.latency_ms_sum,
		    error_calls    = %s.error_calls    + EXCLUDED.error_calls
	`, table, bucketExpr, table, table, table, table, table, table)

	tag, err := tx.Exec(ctx, upsertSQL, lastTS, newTS)
	if err != nil {
		return 0, time.Time{}, fmt.Errorf("rollup upsert %s: %w", name, err)
	}

	if _, err := tx.Exec(ctx,
		`UPDATE usage_rollup_state SET last_ts=$1, updated_at=NOW() WHERE name=$2`,
		newTS, name,
	); err != nil {
		return 0, time.Time{}, fmt.Errorf("rollup advance watermark %s: %w", name, err)
	}

	if err := tx.Commit(ctx); err != nil {
		return 0, time.Time{}, fmt.Errorf("rollup commit %s: %w", name, err)
	}
	return tag.RowsAffected(), newTS, nil
}

// ─── Partition maintenance (raw table) ──

// EnsurePartitionForMonth creates the month-range partition for
// `token_usage` if it does not exist. Idempotent and cheap — runs
// once per day via the partition worker.
func (r *UsageRepo) EnsurePartitionForMonth(ctx context.Context, month time.Time) error {
	start := time.Date(month.Year(), month.Month(), 1, 0, 0, 0, 0, time.UTC)
	end := start.AddDate(0, 1, 0)
	name := fmt.Sprintf("token_usage_%04d_%02d", start.Year(), start.Month())
	q := fmt.Sprintf(
		`CREATE TABLE IF NOT EXISTS %s PARTITION OF token_usage FOR VALUES FROM ('%s') TO ('%s')`,
		name, start.Format("2006-01-02"), end.Format("2006-01-02"),
	)
	if _, err := r.pool.Exec(ctx, q); err != nil {
		return fmt.Errorf("ensure partition %s: %w", name, err)
	}
	return nil
}

// DropOldPartitions removes `token_usage_YYYY_MM` partitions whose upper
// bound is older than `cutoff`. Retention policy: default 1 year.
func (r *UsageRepo) DropOldPartitions(ctx context.Context, cutoff time.Time) ([]string, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT child.relname
		FROM pg_inherits
		JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
		JOIN pg_class child  ON pg_inherits.inhrelid  = child.oid
		WHERE parent.relname = 'token_usage'
		  AND child.relname ~ '^token_usage_[0-9]{4}_[0-9]{2}$'
	`)
	if err != nil {
		return nil, fmt.Errorf("list usage partitions: %w", err)
	}
	defer rows.Close()

	var dropped []string
	var candidates []string
	for rows.Next() {
		var n string
		if err := rows.Scan(&n); err != nil {
			return nil, err
		}
		candidates = append(candidates, n)
	}
	rows.Close()

	for _, n := range candidates {
		// n format: token_usage_YYYY_MM
		var y, m int
		if _, err := fmt.Sscanf(n, "token_usage_%04d_%02d", &y, &m); err != nil {
			continue
		}
		// Partition upper bound
		upper := time.Date(y, time.Month(m), 1, 0, 0, 0, 0, time.UTC).AddDate(0, 1, 0)
		if upper.Before(cutoff) {
			if _, err := r.pool.Exec(ctx, fmt.Sprintf(`DROP TABLE IF EXISTS %s`, n)); err != nil {
				return dropped, fmt.Errorf("drop partition %s: %w", n, err)
			}
			dropped = append(dropped, n)
		}
	}
	return dropped, nil
}
