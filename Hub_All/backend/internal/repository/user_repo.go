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

type UserRepo struct {
	pool *pgxpool.Pool
}

func NewUserRepo(pool *pgxpool.Pool) *UserRepo {
	return &UserRepo{pool: pool}
}

func (r *UserRepo) FindByEmail(ctx context.Context, email string) (*model.User, error) {
	var u model.User
	err := r.pool.QueryRow(ctx, `
		SELECT id, email, name, phone, department, password_hash, avatar_url,
		       status, failed_login_count, locked_until, created_at, updated_at
		FROM users WHERE email = $1
	`, email).Scan(
		&u.ID, &u.Email, &u.Name, &u.Phone, &u.Department, &u.PasswordHash,
		&u.AvatarURL, &u.Status, &u.FailedLoginCount, &u.LockedUntil,
		&u.CreatedAt, &u.UpdatedAt,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("find user by email: %w", err)
	}
	return &u, nil
}

func (r *UserRepo) FindByID(ctx context.Context, id uuid.UUID) (*model.User, error) {
	var u model.User
	err := r.pool.QueryRow(ctx, `
		SELECT id, email, name, phone, department, password_hash, avatar_url,
		       status, failed_login_count, locked_until, created_at, updated_at
		FROM users WHERE id = $1
	`, id).Scan(
		&u.ID, &u.Email, &u.Name, &u.Phone, &u.Department, &u.PasswordHash,
		&u.AvatarURL, &u.Status, &u.FailedLoginCount, &u.LockedUntil,
		&u.CreatedAt, &u.UpdatedAt,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("find user by id: %w", err)
	}
	return &u, nil
}

func (r *UserRepo) GetUserRoles(ctx context.Context, userID uuid.UUID) ([]model.UserHubRole, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT user_id, hub_id, role
		FROM user_hub_roles WHERE user_id = $1
	`, userID)
	if err != nil {
		return nil, fmt.Errorf("get user roles: %w", err)
	}
	defer rows.Close()

	var roles []model.UserHubRole
	for rows.Next() {
		var role model.UserHubRole
		if err := rows.Scan(&role.UserID, &role.HubID, &role.Role); err != nil {
			return nil, fmt.Errorf("scan user role: %w", err)
		}
		roles = append(roles, role)
	}
	return roles, nil
}

func (r *UserRepo) IncrementFailedLogin(ctx context.Context, userID uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE users
		SET failed_login_count = failed_login_count + 1,
		    locked_until = CASE
		        WHEN failed_login_count + 1 >= 5
		        THEN NOW() + INTERVAL '15 minutes'
		        ELSE locked_until
		    END
		WHERE id = $1
	`, userID)
	return err
}

func (r *UserRepo) ResetFailedLogin(ctx context.Context, userID uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE users
		SET failed_login_count = 0, locked_until = NULL
		WHERE id = $1
	`, userID)
	return err
}

func (r *UserRepo) ListUsers(ctx context.Context, hubID, role, status, search string, limit, offset int) ([]model.User, int64, error) {
	var conditions []string
	var args []interface{}
	argIdx := 1
	joinClause := ""

	if hubID != "" {
		joinClause = " INNER JOIN user_hub_roles uhr ON uhr.user_id = u.id"
		conditions = append(conditions, fmt.Sprintf("uhr.hub_id = $%d", argIdx))
		args = append(args, hubID)
		argIdx++

		if role != "" {
			conditions = append(conditions, fmt.Sprintf("uhr.role = $%d", argIdx))
			args = append(args, role)
			argIdx++
		}
	}
	if status != "" {
		conditions = append(conditions, fmt.Sprintf("u.status = $%d", argIdx))
		args = append(args, status)
		argIdx++
	}
	if search != "" {
		conditions = append(conditions, fmt.Sprintf("(u.name ILIKE $%d OR u.email ILIKE $%d)", argIdx, argIdx))
		args = append(args, "%"+search+"%")
		argIdx++
	}

	where := ""
	if len(conditions) > 0 {
		where = " WHERE " + strings.Join(conditions, " AND ")
	}

	// Count total
	countQuery := "SELECT COUNT(DISTINCT u.id) FROM users u" + joinClause + where
	var total int64
	if err := r.pool.QueryRow(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count users: %w", err)
	}

	// Fetch page
	query := fmt.Sprintf(`
		SELECT DISTINCT u.id, u.email, u.name, u.phone, u.department, u.password_hash,
		       u.avatar_url, u.status, u.failed_login_count, u.locked_until,
		       u.created_at, u.updated_at
		FROM users u%s%s
		ORDER BY u.created_at DESC
		LIMIT $%d OFFSET $%d
	`, joinClause, where, argIdx, argIdx+1)
	args = append(args, limit, offset)

	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("list users: %w", err)
	}
	defer rows.Close()

	var users []model.User
	for rows.Next() {
		var u model.User
		if err := rows.Scan(
			&u.ID, &u.Email, &u.Name, &u.Phone, &u.Department, &u.PasswordHash,
			&u.AvatarURL, &u.Status, &u.FailedLoginCount, &u.LockedUntil,
			&u.CreatedAt, &u.UpdatedAt,
		); err != nil {
			return nil, 0, fmt.Errorf("scan user: %w", err)
		}
		users = append(users, u)
	}

	return users, total, nil
}

func (r *UserRepo) CreateUser(ctx context.Context, email, name, passwordHash, phone, department string) (*model.User, error) {
	var phonePtr, deptPtr *string
	if phone != "" {
		phonePtr = &phone
	}
	if department != "" {
		deptPtr = &department
	}

	var u model.User
	err := r.pool.QueryRow(ctx, `
		INSERT INTO users (email, name, password_hash, phone, department, status)
		VALUES ($1, $2, $3, $4, $5, 'active')
		RETURNING id, email, name, phone, department, password_hash, avatar_url,
		          status, failed_login_count, locked_until, created_at, updated_at
	`, email, name, passwordHash, phonePtr, deptPtr).Scan(
		&u.ID, &u.Email, &u.Name, &u.Phone, &u.Department, &u.PasswordHash,
		&u.AvatarURL, &u.Status, &u.FailedLoginCount, &u.LockedUntil,
		&u.CreatedAt, &u.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("create user: %w", err)
	}
	return &u, nil
}

func (r *UserRepo) UpdateUser(ctx context.Context, id uuid.UUID, name, phone, department *string) (*model.User, error) {
	var u model.User
	err := r.pool.QueryRow(ctx, `
		UPDATE users SET
			name       = COALESCE($2, name),
			phone      = COALESCE($3, phone),
			department = COALESCE($4, department)
		WHERE id = $1
		RETURNING id, email, name, phone, department, password_hash, avatar_url,
		          status, failed_login_count, locked_until, created_at, updated_at
	`, id, name, phone, department).Scan(
		&u.ID, &u.Email, &u.Name, &u.Phone, &u.Department, &u.PasswordHash,
		&u.AvatarURL, &u.Status, &u.FailedLoginCount, &u.LockedUntil,
		&u.CreatedAt, &u.UpdatedAt,
	)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("update user: %w", err)
	}
	return &u, nil
}

func (r *UserRepo) UpdateStatus(ctx context.Context, id uuid.UUID, status string) error {
	result, err := r.pool.Exec(ctx, `
		UPDATE users SET status = $2 WHERE id = $1
	`, id, status)
	if err != nil {
		return fmt.Errorf("update user status: %w", err)
	}
	if result.RowsAffected() == 0 {
		return fmt.Errorf("user not found")
	}
	return nil
}

func (r *UserRepo) UpdatePassword(ctx context.Context, id uuid.UUID, passwordHash string) error {
	result, err := r.pool.Exec(ctx, `
		UPDATE users SET password_hash = $2 WHERE id = $1
	`, id, passwordHash)
	if err != nil {
		return fmt.Errorf("update password: %w", err)
	}
	if result.RowsAffected() == 0 {
		return fmt.Errorf("user not found")
	}
	return nil
}

func (r *UserRepo) UpsertUserRole(ctx context.Context, userID, hubID uuid.UUID, role string) error {
	_, err := r.pool.Exec(ctx, `
		INSERT INTO user_hub_roles (user_id, hub_id, role)
		VALUES ($1, $2, $3)
		ON CONFLICT (user_id, hub_id) DO UPDATE SET role = $3
	`, userID, hubID, role)
	if err != nil {
		return fmt.Errorf("upsert user role: %w", err)
	}
	return nil
}
