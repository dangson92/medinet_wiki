"""role_hub_admin

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-23 14:00:00.000000

Phase 1 Plan 01-01 (ROLE-01 + ROLE-02 + ROLE-03) — Mở rộng schema RBAC v3.1:
- ROLE-01: CHECK constraint users.role + 'hub_admin' (4 value: admin|hub_admin|editor|viewer).
- ROLE-02: user_hubs.role TEXT nullable default NULL (per-hub override).
- ROLE-03: audit_logs INSERT row action='migration.role_seed' (audit trail).

Áp dụng cho CẢ central + 3 hub con (schema users + user_hubs đồng nhất mọi DB
theo D-V3-01 multi-DB topology). KHÔNG skip-guard như Plan 04-01 (sync_outbox
per-hub-only) — RBAC schema cần unify mọi DB để hub con verify role local.

Idempotent strategy (GA-V3.1-C — introspect, KHÔNG PL/pgSQL DO block):
- CHECK constraint: introspect users CHECK constraints qua sa.inspect(),
  detect tên thực tế (M2 có thể là 'ck_users_role_enum' từ 0001 hoặc
  'role_enum' từ model auth.py discrepancy — KHÔNG hardcode), skip nếu
  đã có 'hub_admin' trong sqltext.
- user_hubs.role column: op.add_column qua raw SQL `ADD COLUMN IF NOT EXISTS`
  + introspect Python-level guard get_columns() check trước khi DDL,
  skip nếu column đã tồn tại.
- audit_logs seed row: INSERT ... WHERE NOT EXISTS guard tránh duplicate
  khi re-run upgrade head lần 2 (BLOCKER fix idempotent semantic).

Mitigations:
- T-01-01-01 Tampering — CHECK constraint mở rộng KHÔNG xoá data; DROP + ADD
  atomic trong cùng transaction (Alembic wrap upgrade qua BEGIN/COMMIT).
- T-01-01-02 Integrity — user_hubs.role nullable default NULL → existing rows
  preserve semantic inherit global (D-V3.1-02 LOCKED — NULL = inherit
  users.role). Postgres ≥11 ADD COLUMN với default NULL = O(1) metadata-only.
- T-01-01-03 Repudiation — audit_logs seed row action='migration.role_seed'
  với jsonb_build_object payload (migration_revision + admin_count +
  user_hubs_count + timestamp_utc + note) — operator trace post-migration.
- T-01-01-04 DoS — Introspect-based idempotent guard ở 3 STEP (CHECK /
  user_hubs.role / audit seed) — re-run an toàn; print() log operator
  visibility step nào skip/apply.
- T-01-01-05 Elevation of Privilege — Downgrade defensive RuntimeError nếu
  COUNT(*) WHERE users.role='hub_admin' > 0 → E-V3.1-1 STOP trigger;
  operator phải clean manual (UPDATE users SET role='viewer' hoặc xoá)
  trước khi rollback. KHÔNG auto-delete data.
- R-V3.1-1 HIGH mitigation — downgrade impl đầy đủ + idempotent re-run
  safety (Phase 4 MIGRATE-01 sẽ verify runtime upgrade/downgrade chain).

Carry forward Plan 04-01 (0005_sync_outbox_per_hub.py):
- Explicit raw SQL `op.execute()` cho CHECK constraint manipulation
  (Alembic `op.create_check_constraint` tên constraint không reliable
  across Postgres versions; introspect via `sa.inspect()` verify post-apply).
- audit_logs schema preserve: KHÔNG add column mới — payload jsonb đủ
  chứa count + timestamp event (D-V3-Phase4-C2 audit pattern).
- Print log Vietnamese-tagged `[0006]` operator debug visibility.
"""
from __future__ import annotations

from typing import (  # noqa: UP035 — match Alembic template baseline 0001-0005
    Sequence,
    Union,
)

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"  # noqa: UP007 — match baseline 0001-0005
branch_labels: Union[str, Sequence[str], None] = None  # noqa: UP007
depends_on: Union[str, Sequence[str], None] = None  # noqa: UP007


def upgrade() -> None:
    """ROLE-01 CHECK constraint mở rộng + ROLE-02 user_hubs.role + ROLE-03 seed audit."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ============================================================
    # 1) ROLE-01 — CHECK constraint users.role mở rộng (4 value).
    # ============================================================
    # Introspect tên constraint thực tế (M2 có 2 candidate name do model/migration
    # discrepancy: 'ck_users_role_enum' từ 0001 vs 'role_enum' từ model auth.py).
    # Source-of-truth = migration 0001 nhưng vẫn introspect runtime để chống case
    # operator có thể đã rename manual hoặc model autogen tạo nhầm constraint khác.
    check_constraints = inspector.get_check_constraints("users")
    role_constraint_name: str | None = None
    role_constraint_sqltext: str | None = None
    for cc in check_constraints:
        sqltext = cc.get("sqltext", "") or ""
        # Detect constraint chứa role IN (...) — phân biệt với user_status_enum
        # (status IN ('active','disabled')) qua filter "status" not in sqltext.
        if "role" in sqltext and "admin" in sqltext and "status" not in sqltext:
            role_constraint_name = cc.get("name")
            role_constraint_sqltext = sqltext
            break

    if role_constraint_name is None:
        raise RuntimeError(
            "Không tìm thấy CHECK constraint users.role trong DB — "
            "schema baseline 0001 có thể chưa apply hoặc đã bị drop manual. "
            "Vui lòng chạy `alembic upgrade 0001` trước rồi re-run 0006."
        )

    # Idempotent: skip nếu đã có 'hub_admin' trong sqltext (re-run safety).
    if "hub_admin" in (role_constraint_sqltext or ""):
        print(
            f"[0006] SKIP CHECK constraint users.role — đã có 'hub_admin' "
            f"trong sqltext của {role_constraint_name!r}"
        )
    else:
        # DROP cũ + ADD mới — atomic trong cùng transaction Alembic.
        # Giữ NGUYÊN tên constraint (DROP + ADD cùng tên) để downgrade restore
        # chính xác semantic baseline 0001.
        op.execute(f'ALTER TABLE users DROP CONSTRAINT "{role_constraint_name}"')
        op.execute(
            f'ALTER TABLE users ADD CONSTRAINT "{role_constraint_name}" '
            f"CHECK (role IN ('admin', 'hub_admin', 'editor', 'viewer'))"
        )
        print(
            f"[0006] OK CHECK constraint {role_constraint_name!r} mở rộng → "
            f"4 value (admin|hub_admin|editor|viewer)"
        )

    # ============================================================
    # 2) ROLE-02 — user_hubs.role TEXT nullable default NULL.
    # ============================================================
    # Per-hub role override (NULL = inherit users.role global — D-V3.1-02 LOCKED).
    # Idempotent: introspect user_hubs columns, skip nếu 'role' đã tồn tại.
    user_hubs_columns = {col["name"] for col in inspector.get_columns("user_hubs")}
    if "role" in user_hubs_columns:
        print("[0006] SKIP user_hubs.role — column đã tồn tại")
    else:
        # Raw SQL `ADD COLUMN IF NOT EXISTS` — defensive double-guard (introspect
        # check ở Python level + IF NOT EXISTS ở DDL level đề phòng concurrent
        # migration race condition extreme edge case).
        # DEFAULT NULL redundant với NULL (Postgres default behavior) — GIỮ explicit
        # để document intent: existing rows backfill NULL khi ADD COLUMN.
        # ADD COLUMN với default NULL trên Postgres ≥11 = O(1) metadata-only.
        op.execute("""
            ALTER TABLE user_hubs
            ADD COLUMN IF NOT EXISTS role TEXT NULL DEFAULT NULL
        """)
        # Optional CHECK constraint trên user_hubs.role — chấp nhận cùng 4 value
        # NHƯNG cho phép NULL. PostgreSQL CHECK constraint auto-pass NULL (3-value
        # logic), nên syntax `CHECK (role IS NULL OR role IN (...))` explicit
        # để document intent cho operator đọc schema.
        # Tên constraint prefix `ck_` đồng nhất với `ck_users_role_enum` baseline 0001.
        op.execute("""
            ALTER TABLE user_hubs
            ADD CONSTRAINT ck_user_hubs_role_enum
            CHECK (role IS NULL OR role IN ('admin', 'hub_admin', 'editor', 'viewer'))
        """)
        print(
            "[0006] OK user_hubs.role nullable column added "
            "(4 value CHECK + NULL allowed)"
        )

    # ============================================================
    # 3) ROLE-03 — Migration seed audit log (action='migration.role_seed').
    # ============================================================
    # Ghi nhận count user role='admin' (giữ semantic super-admin global) +
    # count user_hubs row hiện tại (preserve nguyên — role=NULL inherit).
    # Idempotent: WHERE NOT EXISTS guard tránh duplicate khi re-run upgrade head
    # (match `migration_revision='0006'` trong payload jsonb).
    # KHÔNG migration column mới — audit_logs.payload JSONB nullable đủ chứa
    # (D-V3-Phase4-C2 audit pattern carry forward Plan 04-06).
    op.execute("""
        INSERT INTO audit_logs (action, target_type, payload, created_at)
        SELECT
            'migration.role_seed',
            'schema',
            jsonb_build_object(
                'migration_revision', '0006',
                'admin_count', (SELECT COUNT(*) FROM users WHERE role = 'admin'),
                'user_hubs_count', (SELECT COUNT(*) FROM user_hubs),
                'timestamp_utc', NOW()::text,
                'note', 'ROLE-03 seed: existing users.role=admin giữ super-admin semantic; user_hubs.role mặc định NULL (inherit global)'
            ),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM audit_logs
            WHERE action = 'migration.role_seed'
              AND payload->>'migration_revision' = '0006'
        )
    """)
    print("[0006] OK audit_logs seed row inserted (action='migration.role_seed')")


def downgrade() -> None:
    """Idempotent rollback — restore CHECK 3 value + drop user_hubs.role + keep audit.

    Thứ tự ngược upgrade:
    1. Defensive check — count user role='hub_admin'; RuntimeError nếu > 0
       (E-V3.1-1 STOP trigger — operator phải clean manual).
    2. Drop user_hubs CHECK constraint ck_user_hubs_role_enum.
    3. Drop column user_hubs.role.
    4. Restore CHECK constraint users.role về 3 value (drop + add cùng tên).
    5. KHÔNG xoá audit_logs seed row (audit trail forensic preserve —
       D-V3-Phase4-C2 carry forward Plan 04-06 audit pattern).

    Lưu ý: Nếu downgrade chạy mà users đã có row role='hub_admin' → CHECK constraint
    3-value sẽ FAIL khi ADD. Defensive: raise RuntimeError sớm, KHÔNG auto-delete
    (operator phải UPDATE users SET role='viewer' hoặc xoá row manual).
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ============================================================
    # 0) Defensive check — count user role='hub_admin' trước khi rollback CHECK.
    # ============================================================
    # Dùng bind.execute().scalar() (KHÔNG op.execute — op.execute return None,
    # không lấy được result row). E-V3.1-1 STOP trigger nếu data tồn tại.
    hub_admin_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE role = 'hub_admin'")
    ).scalar()
    if hub_admin_count and hub_admin_count > 0:
        raise RuntimeError(
            f"Cannot downgrade 0006 → 0005: {hub_admin_count} user(s) hiện có role='hub_admin' "
            f"sẽ FAIL CHECK constraint 3-value khi restore. Vui lòng UPDATE users SET role='viewer' "
            f"hoặc xoá user role='hub_admin' trước khi downgrade (E-V3.1-1 carry forward)."
        )

    # ============================================================
    # 1) Drop user_hubs.role CHECK constraint (nếu tồn tại).
    # ============================================================
    op.execute("ALTER TABLE user_hubs DROP CONSTRAINT IF EXISTS ck_user_hubs_role_enum")

    # ============================================================
    # 2) Drop user_hubs.role column (nếu tồn tại).
    # ============================================================
    user_hubs_columns = {col["name"] for col in inspector.get_columns("user_hubs")}
    if "role" in user_hubs_columns:
        op.execute("ALTER TABLE user_hubs DROP COLUMN role")
        print("[0006 downgrade] OK user_hubs.role column dropped")
    else:
        print("[0006 downgrade] SKIP user_hubs.role — column không tồn tại")

    # ============================================================
    # 3) Restore CHECK constraint users.role về 3 value — introspect tên thật.
    # ============================================================
    # Introspect lại (state có thể đã đổi sau STEP 1/2) để lấy tên constraint
    # hiện tại — đảm bảo restore đúng semantic baseline 0001.
    check_constraints = inspector.get_check_constraints("users")
    role_constraint_name: str | None = None
    for cc in check_constraints:
        sqltext = cc.get("sqltext", "") or ""
        if "role" in sqltext and "admin" in sqltext and "status" not in sqltext:
            role_constraint_name = cc.get("name")
            break

    if role_constraint_name is None:
        print("[0006 downgrade] SKIP users.role CHECK — constraint không tồn tại")
    else:
        op.execute(f'ALTER TABLE users DROP CONSTRAINT "{role_constraint_name}"')
        op.execute(
            f'ALTER TABLE users ADD CONSTRAINT "{role_constraint_name}" '
            f"CHECK (role IN ('admin', 'editor', 'viewer'))"
        )
        print(
            f"[0006 downgrade] OK CHECK constraint {role_constraint_name!r} restored → 3 value"
        )

    # KHÔNG xoá audit_logs seed row — audit trail forensic giữ nguyên dù rollback schema.
    # (Operator có thể manual DELETE nếu cần — out of scope migration.)
