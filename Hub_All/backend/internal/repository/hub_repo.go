package repository

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/medinet/hub-all-backend/internal/model"
)

type HubRepo struct {
	pool *pgxpool.Pool
}

func NewHubRepo(pool *pgxpool.Pool) *HubRepo {
	return &HubRepo{pool: pool}
}

func (r *HubRepo) List(ctx context.Context) ([]model.Hub, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, name, code, subdomain, description, db_host, db_port,
		       db_name, db_user, db_password_enc, chroma_collection,
		       status, created_at, updated_at
		FROM hubs ORDER BY name
	`)
	if err != nil {
		return nil, fmt.Errorf("list hubs: %w", err)
	}
	defer rows.Close()

	var hubs []model.Hub
	for rows.Next() {
		var h model.Hub
		if err := rows.Scan(
			&h.ID, &h.Name, &h.Code, &h.Subdomain, &h.Description,
			&h.DBHost, &h.DBPort, &h.DBName, &h.DBUser, &h.DBPasswordEnc,
			&h.ChromaCollection, &h.Status, &h.CreatedAt, &h.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("scan hub: %w", err)
		}
		hubs = append(hubs, h)
	}
	return hubs, nil
}

func (r *HubRepo) FindByID(ctx context.Context, id uuid.UUID) (*model.Hub, error) {
	var h model.Hub
	err := r.pool.QueryRow(ctx, `
		SELECT id, name, code, subdomain, description, db_host, db_port,
		       db_name, db_user, db_password_enc, chroma_collection,
		       status, created_at, updated_at
		FROM hubs WHERE id = $1
	`, id).Scan(
		&h.ID, &h.Name, &h.Code, &h.Subdomain, &h.Description,
		&h.DBHost, &h.DBPort, &h.DBName, &h.DBUser, &h.DBPasswordEnc,
		&h.ChromaCollection, &h.Status, &h.CreatedAt, &h.UpdatedAt,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("find hub by id: %w", err)
	}
	return &h, nil
}

func (r *HubRepo) FindByCode(ctx context.Context, code string) (*model.Hub, error) {
	var h model.Hub
	err := r.pool.QueryRow(ctx, `
		SELECT id, name, code, subdomain, description, db_host, db_port,
		       db_name, db_user, db_password_enc, chroma_collection,
		       status, created_at, updated_at
		FROM hubs WHERE code = $1
	`, code).Scan(
		&h.ID, &h.Name, &h.Code, &h.Subdomain, &h.Description,
		&h.DBHost, &h.DBPort, &h.DBName, &h.DBUser, &h.DBPasswordEnc,
		&h.ChromaCollection, &h.Status, &h.CreatedAt, &h.UpdatedAt,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("find hub by code: %w", err)
	}
	return &h, nil
}

func (r *HubRepo) Create(ctx context.Context, req model.CreateHubRequest) (*model.Hub, error) {
	var h model.Hub
	err := r.pool.QueryRow(ctx, `
		INSERT INTO hubs (name, code, subdomain, description, db_host, db_port,
		                  db_name, db_user, db_password_enc, chroma_collection)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING id, name, code, subdomain, description, db_host, db_port,
		          db_name, db_user, db_password_enc, chroma_collection,
		          status, created_at, updated_at
	`, req.Name, req.Code, req.Subdomain, req.Description,
		req.DBHost, req.DBPort, req.DBName, req.DBUser, nil, req.ChromaCollection,
	).Scan(
		&h.ID, &h.Name, &h.Code, &h.Subdomain, &h.Description,
		&h.DBHost, &h.DBPort, &h.DBName, &h.DBUser, &h.DBPasswordEnc,
		&h.ChromaCollection, &h.Status, &h.CreatedAt, &h.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("create hub: %w", err)
	}
	return &h, nil
}

func (r *HubRepo) Update(ctx context.Context, id uuid.UUID, req model.UpdateHubRequest) (*model.Hub, error) {
	var h model.Hub
	err := r.pool.QueryRow(ctx, `
		UPDATE hubs SET
			name        = COALESCE($2, name),
			description = COALESCE($3, description),
			db_host     = COALESCE($4, db_host),
			db_port     = COALESCE($5, db_port),
			db_name     = COALESCE($6, db_name),
			db_user     = COALESCE($7, db_user)
		WHERE id = $1
		RETURNING id, name, code, subdomain, description, db_host, db_port,
		          db_name, db_user, db_password_enc, chroma_collection,
		          status, created_at, updated_at
	`, id, req.Name, req.Description, req.DBHost, req.DBPort, req.DBName, req.DBUser,
	).Scan(
		&h.ID, &h.Name, &h.Code, &h.Subdomain, &h.Description,
		&h.DBHost, &h.DBPort, &h.DBName, &h.DBUser, &h.DBPasswordEnc,
		&h.ChromaCollection, &h.Status, &h.CreatedAt, &h.UpdatedAt,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("update hub: %w", err)
	}
	return &h, nil
}

func (r *HubRepo) UpdateStatus(ctx context.Context, id uuid.UUID, status string) error {
	result, err := r.pool.Exec(ctx, `
		UPDATE hubs SET status = $2 WHERE id = $1
	`, id, status)
	if err != nil {
		return fmt.Errorf("update hub status: %w", err)
	}
	if result.RowsAffected() == 0 {
		return fmt.Errorf("hub not found")
	}
	return nil
}

func (r *HubRepo) UpdateDBPassword(ctx context.Context, id uuid.UUID, encryptedPassword string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE hubs SET db_password_enc = $2 WHERE id = $1
	`, id, encryptedPassword)
	return err
}
