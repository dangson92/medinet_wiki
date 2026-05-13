package service

import (
	"context"
	"encoding/csv"
	"fmt"
	"io"
	"log/slog"
	"time"

	"github.com/medinet/hub-all-backend/internal/model"
	"github.com/medinet/hub-all-backend/internal/repository"
)

type AuditService struct {
	auditRepo *repository.AuditRepo
}

func NewAuditService(auditRepo *repository.AuditRepo) *AuditService {
	return &AuditService{auditRepo: auditRepo}
}

// Log inserts an audit log entry asynchronously.
func (s *AuditService) Log(ctx context.Context, entry *model.AuditLogEntry) error {
	go func() {
		bgCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := s.auditRepo.Insert(bgCtx, entry); err != nil {
			slog.Error("failed to insert audit log", "error", err, "action", entry.Action)
		}
	}()
	return nil
}

func (s *AuditService) List(ctx context.Context, dateFrom, dateTo, actorType, action, hubID string, page, perPage int) ([]model.AuditLogEntry, int64, error) {
	if page < 1 {
		page = 1
	}
	if perPage < 1 {
		perPage = 20
	}
	if perPage > 100 {
		perPage = 100
	}

	entries, total, err := s.auditRepo.List(ctx, dateFrom, dateTo, actorType, action, hubID, page, perPage)
	if err != nil {
		return nil, 0, fmt.Errorf("list audit logs: %w", err)
	}
	return entries, total, nil
}

func (s *AuditService) ExportCSV(ctx context.Context, w io.Writer, dateFrom, dateTo, actorType, action, hubID string) error {
	rows, err := s.auditRepo.StreamForExport(ctx, dateFrom, dateTo, actorType, action, hubID)
	if err != nil {
		return fmt.Errorf("stream audit logs: %w", err)
	}
	defer rows.Close()

	csvW := csv.NewWriter(w)
	defer csvW.Flush()

	// Header
	if err := csvW.Write([]string{
		"id", "timestamp", "user_id", "user_name", "is_ai", "action",
		"target", "hub_id", "hub_name", "ip_address", "user_agent",
		"request_id", "duration_ms",
	}); err != nil {
		return fmt.Errorf("write csv header: %w", err)
	}

	for rows.Next() {
		var e model.AuditLogEntry
		if err := rows.Scan(
			&e.ID, &e.Timestamp, &e.UserID, &e.UserName, &e.IsAI, &e.Action,
			&e.Target, &e.HubID, &e.HubName, &e.IPAddress, &e.UserAgent,
			&e.RequestID, &e.DurationMs, &e.Payload,
		); err != nil {
			return fmt.Errorf("scan audit log row: %w", err)
		}

		record := []string{
			e.ID.String(),
			e.Timestamp.Format(time.RFC3339),
			ptrStr(e.UserID),
			ptrStrVal(e.UserName),
			fmt.Sprintf("%t", e.IsAI),
			e.Action,
			ptrStrVal(e.Target),
			ptrStr(e.HubID),
			ptrStrVal(e.HubName),
			ptrStrVal(e.IPAddress),
			ptrStrVal(e.UserAgent),
			ptrStr(e.RequestID),
			ptrIntStr(e.DurationMs),
		}
		if err := csvW.Write(record); err != nil {
			return fmt.Errorf("write csv row: %w", err)
		}
		csvW.Flush()
	}

	return nil
}

func ptrStr[T fmt.Stringer](v *T) string {
	if v == nil {
		return ""
	}
	return (*v).String()
}

func ptrStrVal(v *string) string {
	if v == nil {
		return ""
	}
	return *v
}

func ptrIntStr(v *int) string {
	if v == nil {
		return ""
	}
	return fmt.Sprintf("%d", *v)
}
