# migrate-snapshots/ — Phase 7 MIGRATE-01 snapshot directory

**Created:** 2026-05-23 (Phase 7 Plan 07-01)
**Purpose:** Lưu file `pg_dump` snapshot per-hub từ `medinet_central` legacy DB sang `medinet_hub_<name>` (D-V3-Phase7-A LOCKED).

## File naming convention

`migrate-<hub>-<YYYY-MM-DD>.sql`

Ví dụ:
- `migrate-yte-2026-05-23.sql`
- `migrate-duoc-2026-05-23.sql`
- `migrate-hcns-2026-05-23.sql`

Date tag enables `find -mtime +30 -delete` automation.

## Generate snapshot

```bash
# Loop 3 hub default
bash scripts/migrate/01-snapshot-hubs.sh

# Single hub
bash scripts/migrate/01-snapshot-hubs.sh yte
```

Output file size kỳ vọng: ~50-200 MB/hub (50k chunks × vector(1536) × float4 ~6 KB/row).

## 30-day retention policy

Snapshot file là **operator-local backup** cho rollback per-hub blue/green (Phase 7 Plan 07-02 D-V3-Phase7-B procedure). Giữ tối thiểu 30 ngày để enable rollback nếu post-migration smoke fail.

### Manual cleanup

```bash
# Liệt kê file > 30 ngày
find migrate-snapshots/ -name "*.sql" -mtime +30 -print

# Xóa file > 30 ngày
find migrate-snapshots/ -name "*.sql" -mtime +30 -delete
```

### Cron automation (optional)

```cron
# Daily 4AM cleanup file > 30 ngày
0 4 * * * find /path/to/Hub_All/migrate-snapshots/ -name "*.sql" -mtime +30 -delete
```

## Privacy + security

- **KHÔNG commit `.sql` vào git** — `.gitignore` enforce. Nội dung file chứa PII:
  - `users`: email, username, password_hash
  - `audit_logs`: user actions + timestamps
  - `usage_events`: usage analytics per-user
  - `documents`: file metadata (titles, hashes)
- **Operator local-only**: KHÔNG sync lên cloud storage không encrypted. Nếu cần backup remote, encrypt qua `gpg --symmetric` trước upload (defer v4.0).
- **File permission**: `chmod 600 migrate-*.sql` sau `pg_dump` nếu deploy multi-user host (default umask 644 readable).

## Recovery procedure (rollback Phase 7 migration)

Nếu post-migration smoke fail per-hub (Plan 07-05 `05-smoke-e2e.sh` exit 1):

```bash
# 1. Switch Caddy upstream về central (Plan 07-02 03-switch-caddy.sh --rollback)
bash scripts/migrate/03-switch-caddy.sh yte --rollback

# 2. Drop hub con DB + re-create từ snapshot
psql -U medinet -d postgres -c "DROP DATABASE medinet_hub_yte;"
bash api/scripts/hub-init.sh yte  # CREATE DB + alembic upgrade head
psql -U medinet -d medinet_hub_yte -f migrate-snapshots/migrate-yte-<date>.sql

# 3. Re-run smoke
bash scripts/migrate/05-smoke-e2e.sh yte
```

Snapshot file MUST PERSIST 30 ngày tối thiểu để enable rollback path.

## Reference

- `scripts/migrate/01-snapshot-hubs.sh` — Generator script.
- `.planning/phases/07-migration-smoke-e2e/07-CONTEXT.md` §domain item 1 — Snapshot rationale.
- `.planning/phases/07-migration-smoke-e2e/07-01-PLAN.md` — Plan này.
- D-V3-Phase7-A LOCKED 2026-05-23 — `pg_dump --where` option a.
