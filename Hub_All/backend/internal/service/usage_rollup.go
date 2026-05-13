package service

import (
	"context"
	"log/slog"
	"sync"
	"time"

	"github.com/medinet/hub-all-backend/internal/repository"
)

// UsageRollup is the background worker that keeps the three rollup tables
// up-to-date. Single goroutine per granularity — all three share the same
// checkpoint pattern (see UsageRepo.RollupTick). Ticks are idempotent and
// crash-safe: the aggregate UPSERT and watermark UPDATE run in one txn.
//
// Cadence (chosen to match the dashboard's latency budget):
//
//	5min   → every 10s   → last-1h / last-7d views
//	hourly → every 60s   → last-7d / last-30d views
//	daily  → every 5 min → last-30d+ / historical
//
// These cadences are intentionally tighter than the bucket width so the
// leading bucket is refreshed multiple times before it closes — dashboard
// users see newly-minted data within ~10s even though the rollup row keeps
// growing until the bucket ends.
type UsageRollup struct {
	repo *repository.UsageRepo

	stopOnce sync.Once
	stopCh   chan struct{}
	doneCh   chan struct{}
}

func NewUsageRollup(repo *repository.UsageRepo) *UsageRollup {
	return &UsageRollup{
		repo:   repo,
		stopCh: make(chan struct{}),
		doneCh: make(chan struct{}),
	}
}

func (r *UsageRollup) Start(ctx context.Context) {
	go r.run(ctx)
}

func (r *UsageRollup) Shutdown() {
	r.stopOnce.Do(func() {
		close(r.stopCh)
		<-r.doneCh
	})
}

// bucketExpr5Min rounds timestamp down to the nearest 5-minute boundary.
// `date_trunc('hour', ts) + interval '5 min' * floor(extract(minute from ts)/5)`
// works without extensions and is index-friendly when we aggregate.
const bucketExpr5Min = `date_trunc('hour', timestamp) + INTERVAL '5 min' * floor(EXTRACT(minute FROM timestamp)::int / 5)`

const bucketExprHourly = `date_trunc('hour', timestamp)`

// Daily rollup uses DATE so the PK is compact; the cast is implicit in the
// INSERT because the target column is DATE.
const bucketExprDaily = `date_trunc('day', timestamp)`

func (r *UsageRollup) run(ctx context.Context) {
	defer close(r.doneCh)

	tick5m := time.NewTicker(10 * time.Second)
	defer tick5m.Stop()
	tickH := time.NewTicker(60 * time.Second)
	defer tickH.Stop()
	tickD := time.NewTicker(5 * time.Minute)
	defer tickD.Stop()

	// Run one pass immediately so the dashboard has rollup rows after a
	// fresh deploy (seed watermark is set to NOW - small grace period).
	r.runOne(ctx, "5min", "token_usage_rollup_5min", bucketExpr5Min, 5*time.Second)
	r.runOne(ctx, "hourly", "token_usage_rollup_hourly", bucketExprHourly, 5*time.Second)
	r.runOne(ctx, "daily", "token_usage_rollup_daily", bucketExprDaily, 5*time.Second)

	for {
		select {
		case <-r.stopCh:
			// Final pass to drain late inserts.
			r.runOne(ctx, "5min", "token_usage_rollup_5min", bucketExpr5Min, 0)
			r.runOne(ctx, "hourly", "token_usage_rollup_hourly", bucketExprHourly, 0)
			r.runOne(ctx, "daily", "token_usage_rollup_daily", bucketExprDaily, 0)
			return
		case <-tick5m.C:
			r.runOne(ctx, "5min", "token_usage_rollup_5min", bucketExpr5Min, 5*time.Second)
		case <-tickH.C:
			r.runOne(ctx, "hourly", "token_usage_rollup_hourly", bucketExprHourly, 5*time.Second)
		case <-tickD.C:
			r.runOne(ctx, "daily", "token_usage_rollup_daily", bucketExprDaily, 5*time.Second)
		}
	}
}

func (r *UsageRollup) runOne(ctx context.Context, name, table, bucketExpr string, grace time.Duration) {
	tctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	start := time.Now()
	rows, watermark, err := r.repo.RollupTick(tctx, name, table, bucketExpr, grace)
	dur := time.Since(start)
	if err != nil {
		slog.Error("rollup tick failed", "granularity", name, "error", err, "duration", dur)
		return
	}
	if rows > 0 {
		slog.Debug("rollup tick", "granularity", name, "rows", rows, "watermark", watermark, "duration", dur)
	}
}
