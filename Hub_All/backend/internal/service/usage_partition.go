package service

import (
	"context"
	"log/slog"
	"sync"
	"time"

	"github.com/medinet/hub-all-backend/internal/repository"
)

// UsagePartitionMgr keeps the `token_usage` partition set aligned with
// the current time:
//
//   * ensures partitions for the current + next 2 months exist
//   * drops partitions whose upper bound is older than the retention
//     cutoff (default 1 year)
//
// Runs once at boot and then every 24 hours. Cheap: bounded DDL only when
// a new month rolls over.
type UsagePartitionMgr struct {
	repo          *repository.UsageRepo
	retentionDays int

	stopOnce sync.Once
	stopCh   chan struct{}
	doneCh   chan struct{}
}

func NewUsagePartitionMgr(repo *repository.UsageRepo, retentionDays int) *UsagePartitionMgr {
	if retentionDays <= 0 {
		retentionDays = 365
	}
	return &UsagePartitionMgr{
		repo:          repo,
		retentionDays: retentionDays,
		stopCh:        make(chan struct{}),
		doneCh:        make(chan struct{}),
	}
}

func (m *UsagePartitionMgr) Start(ctx context.Context) {
	go m.run(ctx)
}

func (m *UsagePartitionMgr) Shutdown() {
	m.stopOnce.Do(func() {
		close(m.stopCh)
		<-m.doneCh
	})
}

func (m *UsagePartitionMgr) run(ctx context.Context) {
	defer close(m.doneCh)

	m.tick(ctx)

	ticker := time.NewTicker(24 * time.Hour)
	defer ticker.Stop()

	for {
		select {
		case <-m.stopCh:
			return
		case <-ticker.C:
			m.tick(ctx)
		}
	}
}

func (m *UsagePartitionMgr) tick(ctx context.Context) {
	tctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	now := time.Now().UTC()
	// Ensure this month + next 2 months (buffer for month-rollover).
	for i := 0; i < 3; i++ {
		month := time.Date(now.Year(), now.Month()+time.Month(i), 1, 0, 0, 0, 0, time.UTC)
		if err := m.repo.EnsurePartitionForMonth(tctx, month); err != nil {
			slog.Error("ensure usage partition failed", "month", month.Format("2006-01"), "error", err)
		}
	}

	cutoff := now.AddDate(0, 0, -m.retentionDays)
	dropped, err := m.repo.DropOldPartitions(tctx, cutoff)
	if err != nil {
		slog.Error("drop old usage partitions failed", "error", err)
		return
	}
	if len(dropped) > 0 {
		slog.Info("dropped old usage partitions (retention)",
			"count", len(dropped), "partitions", dropped, "cutoff", cutoff.Format("2006-01-02"))
	}
}
