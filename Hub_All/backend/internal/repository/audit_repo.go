package repository

import (
	"context"
	"fmt"
	"strings"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/medinet/hub-all-backend/internal/model"
)

type AuditRepo struct {
	pool *pgxpool.Pool
}

func NewAuditRepo(pool *pgxpool.Pool) *AuditRepo {
	return &AuditRepo{pool: pool}
}

func (r *AuditRepo) Insert(ctx context.Context, entry *model.AuditLogEntry) error {
	if entry.ID == uuid.Nil {
		entry.ID = uuid.New()
	}
	_, err := r.pool.Exec(ctx, `
		INSERT INTO audit_logs (id, timestamp, user_id, user_name, is_ai, action,
		                        target, hub_id, hub_name, ip_address, user_agent,
		                        request_id, duration_ms, payload)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::inet, $11, $12, $13, $14)
	`, entry.ID, entry.Timestamp, entry.UserID, entry.UserName, entry.IsAI,
		entry.Action, entry.Target, entry.HubID, entry.HubName,
		entry.IPAddress, entry.UserAgent, entry.RequestID,
		entry.DurationMs, entry.Payload,
	)
	if err != nil {
		return fmt.Errorf("insert audit log: %w", err)
	}
	return nil
}

func (r *AuditRepo) buildWhere(dateFrom, dateTo, actorType, action, hubID string) (string, []interface{}) {
	var conditions []string
	var args []interface{}
	argIdx := 1

	if dateFrom != "" {
		conditions = append(conditions, fmt.Sprintf("timestamp >= $%d::timestamptz", argIdx))
		args = append(args, dateFrom)
		argIdx++
	}
	if dateTo != "" {
		conditions = append(conditions, fmt.Sprintf("timestamp <= $%d::timestamptz", argIdx))
		args = append(args, dateTo)
		argIdx++
	}
	if actorType == "ai" {
		conditions = append(conditions, "is_ai = true")
	} else if actorType == "human" {
		conditions = append(conditions, "is_ai = false")
	}
	if action != "" {
		conditions = append(conditions, fmt.Sprintf("action = $%d", argIdx))
		args = append(args, action)
		argIdx++
	}
	if hubID != "" {
		conditions = append(conditions, fmt.Sprintf("hub_id = $%d", argIdx))
		args = append(args, hubID)
		argIdx++
	}

	where := ""
	if len(conditions) > 0 {
		where = " WHERE " + strings.Join(conditions, " AND ")
	}
	return where, args
}

func (r *AuditRepo) List(ctx context.Context, dateFrom, dateTo, actorType, action, hubID string, page, perPage int) ([]model.AuditLogEntry, int64, error) {
	where, args := r.buildWhere(dateFrom, dateTo, actorType, action, hubID)
	argIdx := len(args) + 1

	// Count total
	countQuery := "SELECT COUNT(*) FROM audit_logs" + where
	var total int64
	if err := r.pool.QueryRow(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count audit logs: %w", err)
	}

	// Fetch page
	query := fmt.Sprintf(`
		SELECT id, timestamp, user_id, user_name, is_ai, action,
		       target, hub_id, hub_name, ip_address::text, user_agent,
		       request_id, duration_ms, payload
		FROM audit_logs%s
		ORDER BY timestamp DESC
		LIMIT $%d OFFSET $%d
	`, where, argIdx, argIdx+1)

	offset := (page - 1) * perPage
	args = append(args, perPage, offset)

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("list audit logs: %w", err)
	}
	defer rows.Close()

	var entries []model.AuditLogEntry
	for rows.Next() {
		var e model.AuditLogEntry
		if err := rows.Scan(
			&e.ID, &e.Timestamp, &e.UserID, &e.UserName, &e.IsAI, &e.Action,
			&e.Target, &e.HubID, &e.HubName, &e.IPAddress, &e.UserAgent,
			&e.RequestID, &e.DurationMs, &e.Payload,
		); err != nil {
			return nil, 0, fmt.Errorf("scan audit log: %w", err)
		}
		entries = append(entries, e)
	}

	return entries, total, nil
}

func (r *AuditRepo) StreamForExport(ctx context.Context, dateFrom, dateTo, actorType, action, hubID string) (pgx.Rows, error) {
	where, args := r.buildWhere(dateFrom, dateTo, actorType, action, hubID)

	query := fmt.Sprintf(`
		SELECT id, timestamp, user_id, user_name, is_ai, action,
		       target, hub_id, hub_name, ip_address::text, user_agent,
		       request_id, duration_ms, payload
		FROM audit_logs%s
		ORDER BY timestamp DESC
	`, where)

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("stream audit logs: %w", err)
	}
	return rows, nil
}
