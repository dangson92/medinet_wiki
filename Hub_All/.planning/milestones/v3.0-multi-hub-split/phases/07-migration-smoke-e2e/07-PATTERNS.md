---
phase: 7
phase_name: Migration + Smoke E2E
slug: migration-smoke-e2e
milestone: v3.0
mapped: 2026-05-23
status: Ready for planning
source: gsd-pattern-mapper (Auto Mode `--auto`)
analog_coverage: 14/14 (100%)
---

# Phase 7: Migration + Smoke E2E — Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 14 (7 NEW + 7 MODIFY)
**Analogs found:** 14 / 14 (100% — không có file thiếu analog)
**Source:** CONTEXT.md `<canonical_refs>` "Operator runbooks" + `<specifics>` "5-plan structure preview"

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/migrate/01-snapshot-hubs.sh` | bash-script | batch / file-I/O | `Hub_All/api/scripts/hub-init.sh` (psql + validation chain) | role-match (DB-touching idempotent bash) |
| `scripts/migrate/02-restore-hub.sh` | bash-script | batch / file-I/O | `Hub_All/api/scripts/hub-init.sh` (CREATE EXTENSION + alembic upgrade verify) | role-match |
| `scripts/migrate/03-switch-caddy.sh` | bash-script | event-driven (Caddy reload) | `Hub_All/api/scripts/hub-add.sh` Step 9 (validate + reload + smoke) | exact (Caddy reload pattern carry forward) |
| `scripts/migrate/04-truncate-central.sh` | bash-script | CRUD (DELETE batched + audit) | `Hub_All/api/scripts/hub-add.sh` (validation chain + idempotent) + `api/app/routers/sync.py` (audit_logs INSERT) | role-match (DB-touching destructive + dry-run safety) |
| `scripts/migrate/05-smoke-e2e.sh` | bash-script + test | request-response (curl + jq) | `Hub_All/api/scripts/hub-add.sh` Step 9 smoke + `Hub_All/api/app/observability/checksum_scheduler.py` per-hub iteration | role-match (smoke curl + envelope D6 parse) |
| `scripts/migrate/06-mcp-smoke.md` | runbook (markdown) | manual checklist | `Hub_All/README.md` §"v3.0 Auth SSO deployment notes" (deploy steps + verify curl + rollback) | exact (operator runbook template) |
| `scripts/migrate/fixtures/sample-document.docx` | test-fixture | file (binary) | KHÔNG có analog DOCX trong codebase | no-analog → tạo minimal DOCX qua `python-docx` hoặc commit binary 5-10 KB |
| `mcp_service/mcp_app/config.py` (MODIFY) | config | request-response | self (existing file — `Settings.api_base_url` default change `"http://localhost:8180"` → `"http://python-api-central:8080"`) | exact (existing pattern, 1-line edit) |
| `docker-compose.yml` (MODIFY) | config | declarative | self (existing line 267 `MCP_API_BASE_URL`) | exact (already correct `http://python-api-central:8080` — Phase 2 đã re-point; Phase 7 verify-only HOẶC update lên `https://central/api` cho production deploy) |
| `Hub_All/CLAUDE.md` (MODIFY) | doc | declarative | §6 Phase 6 pattern subsection (Phase 5 + 6 pattern subsection template) | exact (template repeat 4 lần: Phase 3+4+5+6) |
| `Hub_All/.planning/STATE.md` (MODIFY) | doc | declarative | Current `phase_6_status: DONE` frontmatter + Current Position + Phase 6 Results Summary | exact (template repeat 6 lần) |
| `Hub_All/.planning/REQUIREMENTS.md` (MODIFY) | doc | declarative | §SETTINGS-01..04 mark `[x]` + NOTE closeout (Phase 6 pattern) | exact |
| `Hub_All/.planning/ROADMAP.md` (MODIFY) | doc | declarative | Phase 6 row DONE + Decisions block (template Phase 1-6) | exact |
| `Hub_All/README.md` (MODIFY) | doc | declarative | §"System Settings Sync Deploy Notes (Phase 6 v3.0)" + §"v3.0 Auth SSO deployment notes" 7-step deploy + rollback procedure | exact (template repeat 4 lần: Phase 3+4+5+6) |

---

## Pattern Assignments

### `scripts/migrate/01-snapshot-hubs.sh` (bash-script, batch / file-I/O)

**Analog:** `Hub_All/api/scripts/hub-init.sh` (lines 31-50)

**Bash strict mode prefix** (lines 31-37):
```bash
set -euo pipefail

HUB=${1:-${HUB:-}}
if [ -z "$HUB" ]; then
    echo "[hub-init] ERROR: thieu hub name. Usage: bash hub-init.sh <hub_name>"
    exit 2
fi
```

**Regex validate hub_name pattern** (lines 39-45):
```bash
# Sanitize: chi accept lowercase a-z 0-9 underscore (Postgres identifier safe)
if ! [[ "$HUB" =~ ^[a-z][a-z0-9_]{0,15}$ ]]; then
    echo "[hub-init] ERROR: hub name '$HUB' invalid. Pattern: ^[a-z][a-z0-9_]{0,15}$ (sync Settings Plan 02-05 FACTOR-04)"
    exit 2
fi
```

**psql ON_ERROR_STOP idempotent CREATE DATABASE check** (lines 52-61) — reuse cho snapshot resolve hub_id từ central.hubs:
```bash
exists=$(psql -tA -v ON_ERROR_STOP=1 -U "$PGUSER_EFFECTIVE" -d postgres \
    -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")
if [ "$exists" != "1" ]; then
    psql -v ON_ERROR_STOP=1 -U "$PGUSER_EFFECTIVE" -d postgres \
        -c "CREATE DATABASE $DB_NAME OWNER $PGUSER_EFFECTIVE;"
else
    echo "[hub-init] (1/4) $DB_NAME da ton tai, skip."
fi
```

**Phase 7 Plan 07-01 application:**
- Loop 3 hub (`yte`, `duoc`, `hcns`) — reuse `for HUB in yte duoc hcns; do ... done` (HOẶC accept arg `$1` cho 1 hub).
- Resolve `hub_id` UUID từ `medinet_central.hubs WHERE name = $1` (carry forward `checksum_scheduler.py::_tick_daily_count` lines 102-110 pattern).
- `pg_dump --data-only --no-owner --no-acl --column-inserts --table=chunks --table=documents --table=users --table=audit_logs --table=usage_events --where="hub_id = '<uuid>'" -h postgres -U medinet medinet_central > migrate-snapshots/migrate-<HUB>-$(date +%Y-%m-%d).sql`.
- Sanity verify row count post-dump qua `grep -c "^INSERT" migrate-<HUB>-*.sql`.

---

### `scripts/migrate/02-restore-hub.sh` (bash-script, batch / file-I/O)

**Analog:** `Hub_All/api/scripts/hub-init.sh` (entire file — psql + validation chain)

**4-step pipeline header docstring pattern** (lines 1-30):
```bash
#!/usr/bin/env bash
# Medinet Wiki API — Dynamic hub initialization (Phase 1 v3.0 TOPO-01 part 2).
#
# Tao 1 hub moi khi cluster Postgres dang chay (khong can docker compose down):
#   1. CREATE DATABASE medinet_hub_<HUB> (idempotent)
#   2. CREATE EXTENSION vector
#   3. VERIFY HNSW vector(1536) build OK
#   4. uv run alembic -x hub=<HUB> upgrade head
#
# Usage:
#   bash api/scripts/hub-init.sh <hub_name>
```

**Heredoc psql verify pattern** (lines 69-75):
```bash
# (3/4) VERIFY HNSW vector(1536) build OK (R1)
echo "[hub-init] (3/4) VERIFY HNSW vector(1536) build OK..."
psql -v ON_ERROR_STOP=1 -U "$PGUSER_EFFECTIVE" -d "$DB_NAME" <<-EOSQL
    DROP TABLE IF EXISTS _hnsw_dim_check;
    CREATE TABLE _hnsw_dim_check (id serial primary key, v vector(1536));
    CREATE INDEX _hnsw_dim_check_idx ON _hnsw_dim_check USING hnsw (v vector_cosine_ops);
    DROP TABLE _hnsw_dim_check;
EOSQL
```

**Phase 7 Plan 07-02 application:**
- Assume `medinet_hub_<HUB>` đã có schema (Phase 1 hub-init.sh + Phase 4 Alembic 0001..0005 đã upgrade) — KHÔNG cần re-create.
- Load: `psql -v ON_ERROR_STOP=1 -U medinet -d medinet_hub_<HUB> -f migrate-snapshots/migrate-<HUB>-<date>.sql`.
- Verify row count sanity post-restore: `psql -tA -d medinet_hub_<HUB> -c "SELECT COUNT(*) FROM chunks"` so với snapshot expected count.
- 4-step pipeline: (1) Validate hub_name regex + RESERVED blacklist carry forward (T-5-05 mitigation hub-add.sh lines 63-91); (2) Verify DB `medinet_hub_<HUB>` exist + Alembic head match expected SHA; (3) `psql -f` restore; (4) Verify row count sanity.

---

### `scripts/migrate/03-switch-caddy.sh` (bash-script, event-driven Caddy reload — verify-only post Phase 5)

**Analog:** `Hub_All/api/scripts/hub-add.sh` Step 9 (lines 290-341) — **EXACT match (carry forward verbatim)**

**Caddy validate + reload + smoke pattern** (lines 300-341):
```bash
# Check neu caddy container dang chay (dev pre-up — operator chua start compose)
if docker compose ps caddy --format json 2>/dev/null | grep -q '"State":"running"'; then
    echo "[hub-add] (9) Validate Caddy config TRUOC reload..."

    # PRE-validate — fail-fast neu config invalid (avoid silent rollback Pitfall 7)
    if ! docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile 2>&1; then
        echo "[hub-add] ERROR: Caddy config validate FAIL — rollback .env edit can thiet."
        exit 4
    fi

    echo "[hub-add] (9) Validate PASS — reloading Caddy (zero-downtime via admin API)..."

    # Atomic reload qua Caddy admin API (zero-downtime — KHONG restart container)
    if ! docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>&1; then
        echo "[hub-add] ERROR: Caddy reload FAIL"
        exit 4
    fi

    # Smoke checkpoint: verify hub moi route work post-reload
    sleep 1  # cho Caddy settle

    if command -v curl >/dev/null 2>&1; then
        DOMAIN="${WIKI_PUBLIC_DOMAIN:-localhost}"
        SMOKE_URL="https://${DOMAIN}/${HUB}/api/health"
        echo "[hub-add] (9) Smoke check: curl -k ${SMOKE_URL}"
        if curl -k -sf -o /dev/null --max-time 5 "${SMOKE_URL}" 2>/dev/null; then
            echo "[hub-add] (9) Smoke PASS — hub '${HUB}' route work qua Caddy"
        else
            echo "[hub-add] WARN: Smoke check returned non-200 hoac timeout."
        fi
    fi
fi
```

**Phase 7 Plan 07-02 (HOẶC 07-03) application:**
- **Correction during planning (CONTEXT.md `<specifics>`):** Re-read Caddyfile sau Phase 5 — `{re.hub_api.1}` đã dynamic capture hub_name từ URL prefix, Phase 7 KHÔNG cần sed edit Caddyfile upstream. `03-switch-caddy.sh` shrink thành **verify-only**:
  - (1) `docker compose ps python-api-<HUB>` verify hub con container đang `up` post-restore Phase 7 Plan 07-02.
  - (2) `docker compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile` PRE-validate (Pitfall 7).
  - (3) `curl -k -sf https://${WIKI_PUBLIC_DOMAIN:-localhost}/<HUB>/api/health` smoke verify Caddy regex auto-route đúng container.
  - (4) Rollback flag `--rollback` → `docker compose stop python-api-<HUB>` (Caddy regex tự fall through file_server → SPA 404 user-visible signal switch revert).
- Script ~50-80 dòng (verify-only thay vì sed edit complex).

---

### `scripts/migrate/04-truncate-central.sh` (bash-script, CRUD DELETE batched + dry-run + audit_logs INSERT)

**Analog A (validation + dry-run):** `Hub_All/api/scripts/hub-add.sh` (lines 43-91) — validation chain + reserved blacklist + duplicate detect.

**Analog B (audit_logs INSERT):** `Hub_All/api/app/routers/sync.py::sync_replay` (lines 234-258) — admin endpoint audit INSERT non-repudiation pattern.

**Audit INSERT pattern** (sync.py lines 240-258):
```python
await audit_conn.execute(
    """
    INSERT INTO audit_logs
        (user_id, action, target_type, target_id, payload)
    VALUES ($1, $2, $3, $4, $5::jsonb)
    """,
    user.id,
    "sync.replay",
    "sync_outbox",
    body.hub_id,
    json.dumps(
        {
            "since": body.since.isoformat(),
            "rows_replayed": replayed_count,
        }
    ),
)
```

**Dry-run flag default ON pattern** (CONTEXT.md `<specifics>` "Migration dry-run mode"):
- Operator phải explicit `--apply` flag để thực thi DELETE.
- Default behavior: `--dry-run` → COUNT + log + KHÔNG DELETE.

**Phase 7 Plan 07-03 application:**
- Per hub_id (3 hub yte/duoc/hcns) batched: `DELETE FROM medinet_central.documents WHERE hub_id = '<uuid>'; DELETE FROM medinet_central.users WHERE hub_id = '<uuid>'; DELETE FROM medinet_central.audit_logs WHERE hub_id = '<uuid>'; DELETE FROM medinet_central.usage_events WHERE hub_id = '<uuid>'`.
- **KHÔNG truncate `medinet_central.chunks`** (D-V3-02 LOCKED — vẫn nhận sync 1-way cho cross-hub search).
- COUNT verify trước DELETE + sau DELETE qua psql `BEGIN; SELECT COUNT(*) ...; DELETE ...; SELECT COUNT(*) ...; COMMIT;` (atomic transaction).
- INSERT `audit_logs` row TRƯỚC DELETE: `action='migrate.truncate_hub'`, `actor='system'`, `target_type='central_hub_rows'`, `target_id='<hub_uuid>'`, `payload={dry_run, row_count_per_table}`. (Carry forward sync.py:240-258 pattern, dùng psql heredoc thay async).
- Dry-run default flag — operator phải pass `--apply` (HOẶC `--dry-run=false`) để DELETE thực sự thực thi.
- Retention 30-day policy doc qua comment + `find migrate-snapshots/ -mtime +30 -delete` cron command example.

---

### `scripts/migrate/05-smoke-e2e.sh` (bash-script + test, request-response curl + jq envelope D6 parse)

**Analog A (smoke curl + envelope parse):** `Hub_All/api/scripts/hub-add.sh` Step 9 (lines 324-337) — smoke curl warn-only pattern.

**Analog B (per-hub iteration + error isolation):** `Hub_All/api/app/observability/checksum_scheduler.py` lines 261-275 — per-hub tick + try/except isolation pattern.

**Per-hub iteration with error isolation** (checksum_scheduler.py lines 261-275):
```python
for hub_name in hub_dsns:
    hub_pool = hub_pools.get(hub_name)
    if hub_pool is None:
        continue  # skip hub failed init
    try:
        await _tick_daily_count(
            central_pool, hub_pool, hub_name
        )
    except Exception as e:  # noqa: BLE001 — per-hub error isolation
        logger.warning(
            "checksum_daily_hub_failed: hub=%s err=%s",
            hub_name,
            e,
        )
```

**Phase 7 Plan 07-05 application — 7-step golden path per-hub:**
- Loop 3 hub: `for HUB in yte duoc hcns; do ... done` (Bash equivalent).
- 7 step per hub qua `curl` + `jq` parse envelope D6 `{success, data, error, meta}`:
  1. `login` — POST `${BASE}/api/auth/login` → extract `data.access_token` qua `jq -r '.data.access_token'`.
  2. `upload DOCX` — POST `${BASE}/${HUB}/api/documents` multipart fixture `sample-document.docx` → extract `data.id`.
  3. `poll status completed` — GET `${BASE}/${HUB}/api/documents/<id>` retry max 30s → assert `data.status == "completed"`.
  4. `search local` — POST `${BASE}/${HUB}/api/search { "query": "vaccin", "hub_ids": ["<HUB>"] }` → assert `data.results | length > 0`.
  5. `search cross-hub` — POST `${BASE}/api/search/cross-hub { "query": "vaccin" }` (central absolute path, D-V3-Phase4-D3 carry forward) → assert `meta.latency_ms < 1500` (E-V3-2).
  6. `ask` — POST `${BASE}/${HUB}/api/ask { "query": "..." }` → assert `data.answer` non-empty + `data.citations | length > 0`.
  7. `citation [N]` — Regex `\[[0-9]+\]` xuất hiện trong `data.answer` text.
  8. `logout` — POST `${BASE}/api/auth/logout` → assert `success == true`.
- Exit code 0 = all 3 hub PASS / 1 = bất kỳ step nào FAIL (per-hub error isolation log + continue, summary cuối cùng exit code reflect overall).
- Prometheus assertion qua `curl ${BASE}/metrics | grep` (CONTEXT.md `<specifics>` thresholds): `cross_hub_search_latency_seconds` p95 < 1.5s, `sync_lag_seconds` < 30s, `apikey_verify_total{result=cached}` > 0, `sync_count_drift` < 0.01.
- Hub isolation E-V3-3 verify: curl `${BASE}/yte/api/documents/<duoc_doc_id>` → assert 403 `CROSS_HUB_ACCESS_DENIED` envelope (NOT 404 leak).
- Phase 6 SETTINGS pub/sub: curl PUT `${BASE}/api/rag-config` central + sleep 5s + curl GET `${BASE}/yte/api/rag-config-cached` (HOẶC indirect via search behavior change verify) → confirm <30s propagate (E-V3-4).
- Phase 3 SSO live: login central → JWT issue → curl `${BASE}/yte/api/...` với same JWT → 200 PASS.

---

### `scripts/migrate/06-mcp-smoke.md` (runbook, manual checklist)

**Analog:** `Hub_All/README.md` §"v3.0 Auth SSO deployment notes" (lines 179-260) — 7-step deploy procedure + verify curl + rollback.

**Deploy step structure pattern** (README.md lines 196-244):
```markdown
### Operator pre-deploy checklist (30 phút advance)

1. **Broadcast user re-login** qua Slack/Email banner: > "Hệ thống Medinet Wiki vừa nâng cấp..."

2. **Verify central RS256 keypair PKCS#8** còn tồn tại:

   ```bash
   ls -la api/keys/private.pem api/keys/public.pem
   ```

3. **Verify Redis instance** up (cross-process blacklist):

   ```bash
   docker compose ps redis
   docker compose exec redis redis-cli PING  # Expect PONG
   ```

### Deploy steps (Phase 3 v3.0)

1. **Backup database**:

   ```bash
   docker exec medinet-postgres pg_dumpall -U medinet > backup-pre-phase3-$(date +%Y%m%d).sql
   ```
...
```

**Phase 7 Plan 07-04 application — 5-step MCP smoke runbook:**
1. **Pre-deploy verify:** `docker compose ps mcp_service` running + `docker compose logs -f mcp_service` no boot errors + 135/135 `mcp_service/tests/` PASS regression (`cd mcp_service && uv run pytest -q`).
2. **Connect Claude Inspector qua OAuth** `wiki.medinet.vn/mcp/auth/v2/authorize` — verify discovery `GET /.well-known/oauth-authorization-server` 200 + `client_id=wiki-mcp` (M2 production) + scope `read:wiki write:wiki` accept.
3. **Call `search_wiki(query="vaccin", hub_id="yte")`** single-hub — verify result envelope `{citations: [...], chunks: [...]}` + chunks chứa hub_id=`yte` only.
4. **Call `ask_wiki(query="dược ngoại")`** cross-hub no hub_id — verify result chứa citations từ multiple hubs (yte + duoc + hcns intersection user.hub_ids).
5. **Verify citation `[N]`** resolve — click citation link → 200 PASS document detail page.

**Rollback procedure (mandatory section per README pattern):**
```bash
# Rollback mcp_service re-point central → M2 monolith
docker compose down mcp_service
git revert <commit-sha-phase7-mcp-repoint>
docker compose up -d mcp_service
```

---

### `scripts/migrate/fixtures/sample-document.docx` (test-fixture, file binary)

**Analog:** KHÔNG có analog DOCX trong codebase.

**Phase 7 Plan 07-05 application:**
- Tạo minimal DOCX 1 trang qua Python `python-docx` script (chạy 1 lần, commit binary):
  ```python
  from docx import Document
  doc = Document()
  doc.add_heading("Sample Document — Smoke Test Phase 7", level=1)
  doc.add_paragraph("Đây là tài liệu test ingest dùng cho smoke E2E Phase 7. Nội dung mô phỏng tài liệu y tế ngắn về vaccin và phòng dược cơ bản. KHÔNG dùng data production thật (privacy + reproducibility).")
  doc.add_paragraph("Vaccin (vaccine) là chế phẩm sinh học...")
  doc.save("sample-document.docx")
  ```
- Size 5-10 KB; commit binary trực tiếp vào repo (KHÔNG generate runtime — smoke script reproducibility).
- Content phải có ít nhất 1 keyword detectable (`vaccin`, `dược`) để smoke step 4-6 (search + ask) assert non-empty.

---

### `mcp_service/mcp_app/config.py` (MODIFY — config, request-response)

**Analog:** self (existing file `mcp_service/mcp_app/config.py` lines 33-46).

**Existing default + validator pattern** (lines 33-39):
```python
# Base URL của API Service (KHÔNG kèm /api).
api_base_url: str = "http://localhost:8180"
# Host và port MCP Service lắng nghe.
service_host: str = "0.0.0.0"
service_port: int = 8190
# Timeout (giây) cho mỗi request HTTP tới API Service.
http_timeout: float = 30.0
```

**Existing field_validator scheme check** (lines 106-119):
```python
@field_validator("api_base_url", mode="after")
@classmethod
def _validate_base_url(cls, value: str) -> str:
    """Validate base URL: strip trailing slash, ép scheme http/https, bắt buộc có host."""
    stripped = value.rstrip("/")
    parsed = urlparse(stripped)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            "MCP_API_BASE_URL phải dùng scheme http hoặc https "
            "— chống SSRF/misconfiguration"
        )
    if not parsed.netloc:
        raise ValueError("MCP_API_BASE_URL thiếu host")
    return stripped
```

**Phase 7 Plan 07-04 application:**
- 1-line change `api_base_url: str = "http://localhost:8180"` → `api_base_url: str = "http://python-api-central:8080"` (dev compose) HOẶC `"https://central/api"` (prod public — note: docker-compose.yml line 267 đã set `http://python-api-central:8080` từ Phase 2 — verify-only HOẶC update production hint comment).
- KHÔNG đụng `field_validator` (carry forward).
- KHÔNG đụng env var name `MCP_API_BASE_URL` (carry forward — operator chỉ override `.env` value).
- Update docstring nếu cần ghi context Phase 7 MIGRATE-04 re-point.

---

### `docker-compose.yml` (MODIFY — config, declarative)

**Analog:** self (existing file `Hub_All/docker-compose.yml` lines 263-273 mcp_service block).

**Existing MCP service env block** (lines 263-273):
```yaml
environment:
  # Phase 2 v3.0 (D-V3-Phase2-C): re-point từ python-api (M2) → python-api-central.
  # MCP service gọi central cho cross-hub aggregate (LOCKED D-V3-02 — KHÔNG fan-out
  # N hub con). Phase 7 MIGRATE-04 re-confirm contract.
  MCP_API_BASE_URL: http://python-api-central:8080
  # Issuer = domain public HTTPS. Operator set ở .env gốc compose:
  MCP_OAUTH_ISSUER_URL: ${MCP_OAUTH_ISSUER_URL:-http://localhost:8190}
  MCP_OAUTH_STATE_DB_PATH: /app/.oauth/state.db
```

**Phase 7 Plan 07-04 application:**
- **Verify-only (recommended):** docker-compose.yml line 267 đã đúng (`MCP_API_BASE_URL: http://python-api-central:8080`) — Phase 2 đã re-point. Phase 7 chỉ cần update comment "Phase 7 MIGRATE-04 **CONFIRMED** contract" thay vì "re-confirm".
- **Alternative (production prod compose override):** Nếu deploy production split compose file, override `MCP_API_BASE_URL: https://central/api` qua override.prod.yml.

---

### `Hub_All/CLAUDE.md` (MODIFY — doc, declarative)

**Analog:** §6 Phase 6 pattern subsection (CLAUDE.md lines 213-end — Phase 6 System Settings Sync pattern subsection 5-plan ship + 4 D-V3-Phase6 LOCKED + 6 Prometheus metric).

**Pattern subsection template structure:**
```markdown
### Phase N <Name> pattern (REQ-XXX-01..05 — YYYY-MM-DD)

N plan đóng M REQ-ID <category> + K decisions LOCKED + L Prometheus metric infrastructure (mechanism description, mitigation):

- **Plan NN-01 REQ-... — Title (D-V3-PhaseN-X LOCKED):** Description (~200-400 chars per plan).
- **Plan NN-02 ...**
- **Plan NN-03 ...**
- **Plan NN-04 ...**
- **Plan NN-05 closeout — docs + smoke checkpoint (file này, YYYY-MM-DD):** Description.

**Architecture insights (Phase N):**

1. **Pattern 1 (Decision LOCKED):** Description.
2. **Pattern 2:** ...

**T-N-NN STRIDE coverage:**
- T-N-NN-01 ...

**Backward compat (Phase N KHÔNG break M2):** ...

**R-V3-X HIGH mitigation chain:** ...

**E-V3-X carry forward:** ...

**v3.0-b progress:** Phase N hoàn tất M/M REQ-ID. v3.0-b N/4 phase DONE. Next: ...

**Reference:**
- `.planning/phases/0N-<slug>/0N-CONTEXT.md` — K decisions LOCKED YYYY-MM-DD.
- `.planning/phases/0N-<slug>/0N-{01..NN}-PLAN.md` — implementation chi tiết N plan.
- `.planning/phases/0N-<slug>/0N-{01..NN}-SUMMARY.md` — deliverable + commit + test count per plan.
```

**Phase 7 Plan 07-05 application:**
- §6 v3.0 progress table — đổi `📋 Backlog` → `✅ DONE` cho Phase 7 row + plan count + REQ count.
- **§6 ADD NEW subsection "Phase 7 Migration + Smoke E2E pattern (MIGRATE-01..05 — 2026-05-23)"** copy template Phase 6 (5-7 bullet) + 4 D-V3-Phase7-A/B/C/D LOCKED summary + 5 architecture insights + backward compat (mcp_service 135/135 PASS) + R-V3-4 migration downtime mitigation chain (blue/green per-hub).
- §6 ADD v3.0 milestone CLOSED banner sau Phase 7 row (carry forward CLAUDE.md milestone pattern v2.0 archive line 305).

---

### `Hub_All/.planning/STATE.md` (MODIFY — doc, declarative)

**Analog:** STATE.md current frontmatter `phase_6_status: DONE` (lines 4-15) + Current Position block (lines 27-36) + Phase 6 Results Summary block (lines 36-50+).

**Frontmatter pattern:**
```yaml
---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Multi-Hub Split
status: "Phase 7 DONE YYYY-MM-DD ✅ — Migration + Smoke E2E N plan ship MIGRATE-01..05..."
last_updated: "YYYY-MM-DDTHH:MM:SS.000Z"
phase_7_status: "DONE YYYY-MM-DD ✅ — N plan/M wave shipped..."
progress:
  total_phases: 7
  completed_phases: 7
  total_plans: 38  # 33 (Phase 1..6) + 5 (Phase 7)
  completed_plans: 38
  percent: 100  # MILESTONE CLOSED
---
```

**Phase 7 Plan 07-05 application:**
- Frontmatter — `phase_7_status: DONE` + `completed_phases: 7` + `percent: 100`.
- Current Position block — đổi từ Phase 6 → Phase 7 + Plan 7/7 complete.
- ADD "Phase 7 Planning Summary" table (template copy Phase 5/6).
- ADD "Phase 7 Results Summary" table — Plan/Wave/Objective/Commits/Tests columns.
- ADD "v3.0 milestone CLOSED marker" + Next Action `/gsd-complete-milestone v3.0`.

---

### `Hub_All/.planning/REQUIREMENTS.md` (MODIFY — doc, declarative)

**Analog:** §SETTINGS-01..04 mark `[x]` + NOTE Phase 6 closeout (REQUIREMENTS.md lines 131-150 in original — pattern repeat 6 lần).

**Mark `[x]` + NOTE pattern:**
```markdown
- [x] **REQ-XX** ✅ Phase N: Description (D-V3-PhaseN-X LOCKED — implementation summary). _Closed YYYY-MM-DD Plan NN-XX (commit-summary)._

> **NOTE Phase N closeout (Plan NN-05 REQ-XX-01..05 — YYYY-MM-DD):** N plan ship đầy đủ M REQ-ID:
>
> 1. Plan NN-01 — Title (D-V3-PhaseN-X) — implementation summary.
> 2. Plan NN-02 — ...
> 3. Plan NN-05 closeout — docs + smoke checkpoint.
>
> **Backward compat (Phase N KHÔNG break M2):** ...
> **R-V3-X mitigation chain:** ...
> **E-V3-X carry forward:** ...
> **v3.0-b progress:** Phase 7 hoàn tất 5/5 REQ-ID MIGRATE. **v3.0 milestone CLOSED** — 38/38 plan ≈ 100%.
```

**Phase 7 Plan 07-05 application:**
- MIGRATE-01..05 5 REQ → mark `[x]` mỗi REQ + closure plan reference.
- ADD NOTE Phase 7 closeout block sau MIGRATE-05 (template Phase 6 NOTE — 5 plan list + backward compat + R-V3-4 mitigation + v3.0 CLOSED marker).

---

### `Hub_All/.planning/ROADMAP.md` (MODIFY — doc, declarative)

**Analog:** Phase 6 row DONE + Decisions block (ROADMAP.md lines 30 — Progress table Phase 6 89%).

**Phase row update pattern:**
```markdown
| ✅ **N** | Phase Name | Goal | REQ-ID (count) | Success criteria count | M2 shipped — **DONE YYYY-MM-DD** (N plans / ~M commits / N tests PASS) |
```

**Decisions block pattern (Phase 6 — lines 252-256):**
```markdown
**Decisions (chốt YYYY-MM-DD theo planner seed defaults Auto Mode `--auto --chain`, KHÔNG `/gsd-discuss-phase N` interactive — K D-V3-PhaseN-X..Y LOCKED):**
- D-V3-PhaseN-A: Description.
- D-V3-PhaseN-B: ...
```

**Phase 7 Plan 07-05 application:**
- Phase 7 row — đổi `📋 Backlog` → `✅ DONE 2026-05-23 (N plans / M commits / K tests PASS)`.
- ADD Decisions block 4 D-V3-Phase7-A/B/C/D LOCKED (template).
- Progress table — Phases `7/7` Plans Complete `38/38` REQ-ID `30/30` Status `✅ Shipped` Completed `2026-05-23`.
- **ADD v3.0 milestone celebration banner** dưới Progress table.
- Phases — v3.0 archived section (collapsible `<details>` template carry forward v2.0 lines 290-311).

---

### `Hub_All/README.md` (MODIFY — doc, declarative)

**Analog A:** §"v3.0 Auth SSO deployment notes" (lines 179-260) — 7-step deploy + rollback.
**Analog B:** §"Add a new hub (dynamic registration — FACTOR-04 Plan 02-05)" (lines 132-175) — quick start operator.

**Deploy notes section template (Phase 3 — lines 179-260):**
```markdown
## v3.0 <Phase N name> deployment notes (Phase N ship YYYY-MM-DD)

Phase N ship <description>. **Backward incompat — <warning summary>.**

### Backward incompat warning

<warning details>

### Operator pre-deploy checklist (M phút advance)

1. **Broadcast** ...
2. **Verify** ...

### Deploy steps (Phase N v3.0)

1. **Backup database** ...
2. **Update env** ...
3. **Restart central first** ...
4. **Restart 3 hub con song song** ...

### Verify deploy

```bash
curl ...
```

### Rollback procedure

```bash
# rollback steps
```
```

**Phase 7 Plan 07-05 application — ADD NEW section "Migration + Smoke E2E Runbook (Phase 7 v3.0)":**
- 7-step deploy procedure (per CONTEXT.md `<decisions>` D-V3-Phase7-B blue/green per-hub):
  1. Pre-deploy checklist (verify central + 3 hub con + Redis + Postgres up).
  2. `01-snapshot-hubs.sh` snapshot 3 hub vào `migrate-snapshots/`.
  3. `02-restore-hub.sh <HUB>` restore từng hub blue/green per-hub.
  4. `03-switch-caddy.sh <HUB>` verify Caddy auto-route post-restore.
  5. `05-smoke-e2e.sh <HUB>` golden path 7-step automated PASS per hub.
  6. Repeat 2-5 cho 2 hub còn lại.
  7. `04-truncate-central.sh --dry-run` verify counts → `04-truncate-central.sh --apply` thực thi.
- Rollback per-hub procedure (`03-switch-caddy.sh --rollback <HUB>` + snapshot 30-day retention enable).
- Retention 30-day policy doc (`find migrate-snapshots/ -mtime +30 -delete` cron command).
- MCP re-point env wire example (`MCP_API_BASE_URL` verify + `mcp_service` regression 135/135 PASS).
- v3.0 milestone CLOSED 🎉 banner section.

---

## Shared Patterns

### Bash strict mode + validation chain (T-5-05 mitigation)

**Source:** `Hub_All/api/scripts/hub-add.sh` lines 43-91, `Hub_All/api/scripts/hub-init.sh` lines 31-45.

**Apply to:** All 5 NEW bash scripts (`01-snapshot-hubs.sh`, `02-restore-hub.sh`, `03-switch-caddy.sh`, `04-truncate-central.sh`, `05-smoke-e2e.sh`).

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'  # safer field separator

HUB=${1:-${HUB:-}}
if [ -z "$HUB" ]; then
    echo "[script-name] ERROR: thieu hub name. Usage: ..."
    exit 2
fi

# Regex validate hub_name (sync Settings Plan 02-05 FACTOR-04 + Plan 05-05 carry forward)
if ! [[ "$HUB" =~ ^[a-z][a-z0-9_]{0,15}$ ]]; then
    echo "[script-name] ERROR: hub name '$HUB' invalid. Pattern: ^[a-z][a-z0-9_]{0,15}$"
    exit 2
fi

# RESERVED blacklist (sync RESERVED_HUB_NAMES app/config.py)
RESERVED_NAMES=("postgres" "cocoindex" "template0" "template1" "public" "medinet")
for reserved in "${RESERVED_NAMES[@]}"; do
    if [ "$HUB" = "$reserved" ]; then
        echo "[script-name] ERROR: hub name '$HUB' reserved."
        exit 2
    fi
done
```

---

### Response envelope D6 jq parse

**Source:** Phase 5 hub-add.sh smoke + M2 contract LOCKED `{success, data, error, meta}`.

**Apply to:** `05-smoke-e2e.sh` per-step assert.

```bash
# Login + extract token
RESPONSE=$(curl -k -s -X POST "${BASE}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${USER}\",\"password\":\"${PASS}\"}")

SUCCESS=$(echo "$RESPONSE" | jq -r '.success')
if [ "$SUCCESS" != "true" ]; then
    ERROR_CODE=$(echo "$RESPONSE" | jq -r '.error.code')
    ERROR_MSG=$(echo "$RESPONSE" | jq -r '.error.message')
    echo "[smoke-e2e] FAIL login: ${ERROR_CODE} — ${ERROR_MSG}"
    exit 1
fi

TOKEN=$(echo "$RESPONSE" | jq -r '.data.access_token')
```

---

### Atomic .env edit (preserve other env vars)

**Source:** `Hub_All/api/scripts/hub-add.sh` Step 8 (lines 263-288).

**Apply to:** Bất kỳ Phase 7 script nào touching `.env` (potentially `04-truncate-central.sh` nếu cần track migration completion timestamp).

```bash
TMP_ENV=$(mktemp)
trap 'rm -f "$TMP_ENV"' EXIT

# Atomic single-key update via tmp file + mv
if grep -qE "^MIGRATION_PHASE7_DONE=" "$ENV_FILE"; then
    sed "s|^MIGRATION_PHASE7_DONE=.*|MIGRATION_PHASE7_DONE=$(date -u +%Y-%m-%dT%H:%M:%SZ)|" "$ENV_FILE" > "$TMP_ENV"
else
    cp "$ENV_FILE" "$TMP_ENV"
    echo "MIGRATION_PHASE7_DONE=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$TMP_ENV"
fi

mv "$TMP_ENV" "$ENV_FILE"
trap - EXIT
```

---

### Audit log INSERT for non-repudiation

**Source:** `Hub_All/api/app/routers/sync.py::sync_replay` lines 234-258 (Phase 4 Plan 04-06 W8 fix T-04-06-03).

**Apply to:** `04-truncate-central.sh` — INSERT audit row BEFORE DELETE per hub (operator non-repudiation evidence chain).

**Adapted bash + psql heredoc:**
```bash
psql -v ON_ERROR_STOP=1 -U medinet -d medinet_central <<-EOSQL
BEGIN;

-- (1) INSERT audit_log row TRUOC DELETE
INSERT INTO audit_logs (user_id, action, target_type, target_id, payload)
VALUES (
    NULL,  -- actor='system' migration
    'migrate.truncate_hub',
    'central_hub_rows',
    '${HUB_UUID}',
    jsonb_build_object(
        'hub_name', '${HUB}',
        'dry_run', ${DRY_RUN_FLAG:-false},
        'row_count_documents', (SELECT COUNT(*) FROM documents WHERE hub_id = '${HUB_UUID}'),
        'row_count_users', (SELECT COUNT(*) FROM users WHERE hub_id = '${HUB_UUID}'),
        'row_count_audit_logs', (SELECT COUNT(*) FROM audit_logs WHERE hub_id = '${HUB_UUID}'),
        'row_count_usage_events', (SELECT COUNT(*) FROM usage_events WHERE hub_id = '${HUB_UUID}'),
        'timestamp', now()::text
    )
);

-- (2) DELETE batched if --apply mode
$(if [ "$DRY_RUN_FLAG" = "false" ]; then echo "
DELETE FROM documents WHERE hub_id = '${HUB_UUID}';
DELETE FROM users WHERE hub_id = '${HUB_UUID}';
DELETE FROM audit_logs WHERE hub_id = '${HUB_UUID}' AND action != 'migrate.truncate_hub';
DELETE FROM usage_events WHERE hub_id = '${HUB_UUID}';
"; fi)

COMMIT;
EOSQL
```

---

### Docs closeout template (4-phase repeat)

**Source:** CLAUDE.md §6 Phase 3/4/5/6 pattern subsection (4 lần lặp lại).
**Source:** STATE.md frontmatter `phase_N_status` + Current Position + Results Summary (6 lần lặp lại).
**Source:** REQUIREMENTS.md mark `[x]` + NOTE closeout block (6 lần lặp lại).
**Source:** ROADMAP.md Phase row DONE + Decisions block (5 lần lặp lại).
**Source:** README.md §"v3.0 <Phase N> deployment notes" (4 lần lặp lại).

**Apply to:** Plan 07-05 closeout — 5 doc files modify cùng pattern Phase 3/4/5/6.

---

## No Analog Found

| File | Role | Data Flow | Reason | Resolution |
|------|------|-----------|--------|------------|
| `scripts/migrate/fixtures/sample-document.docx` | test-fixture (binary) | file | KHÔNG có DOCX fixture trong codebase hiện tại | Generate qua `python-docx` script 1 lần + commit binary 5-10 KB. Content có keyword `vaccin`/`dược` detectable cho smoke test step 4-6. |

---

## Metadata

**Analog search scope:**
- `Hub_All/api/scripts/` (hub-add.sh, hub-init.sh)
- `Hub_All/Caddyfile`, `Hub_All/docker-compose.yml`
- `Hub_All/api/app/routers/sync.py` (admin replay endpoint + audit_logs INSERT)
- `Hub_All/api/app/observability/checksum_scheduler.py` (per-hub iteration)
- `Hub_All/mcp_service/mcp_app/config.py` (Settings.api_base_url)
- `Hub_All/api/.env.example` (Phase 6 SETTINGS env document template)
- `Hub_All/README.md` (deploy notes section template)
- `Hub_All/CLAUDE.md` §6 (pattern subsection template — Phase 3+4+5+6 carry forward)
- `Hub_All/.planning/STATE.md` (frontmatter + Phase N Planning/Results template)
- `Hub_All/.planning/REQUIREMENTS.md` (NOTE closeout block template)
- `Hub_All/.planning/ROADMAP.md` (Phase row DONE + Decisions template)
- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-05-SUMMARY.md` (9-step pipeline pattern)
- `Hub_All/.planning/phases/05-reverse-proxy-frontend-subpath/05-01-SUMMARY.md` (Caddyfile wiki block pattern)

**Files scanned:** ~15

**Pattern extraction date:** 2026-05-23

**Key patterns identified:**
1. **9-step pipeline pattern (hub-add.sh):** Validation chain (regex + RESERVED + duplicate) → DB layer → docker-compose merge → .env atomic edit → Caddy validate + reload + smoke. **Carry forward to all 5 Phase 7 NEW bash scripts.**
2. **Caddy validate PRE-reload (Pitfall 7 mitigation):** MANDATORY in all Caddy-touching scripts. `03-switch-caddy.sh` verify-only mode reuse.
3. **psql idempotent + heredoc + ON_ERROR_STOP=1:** Carry forward from hub-init.sh — DB-touching bash scripts.
4. **Per-hub iteration with error isolation:** From checksum_scheduler.py — Phase 7 `05-smoke-e2e.sh` 3-hub loop với try/except equivalent (bash `set +e` block per hub + summary exit code).
5. **audit_logs INSERT non-repudiation (sync.py:234-258):** Phase 7 `04-truncate-central.sh` adapt psql heredoc syntax.
6. **Response envelope D6 jq parse (`{success, data, error, meta}`):** Phase 7 `05-smoke-e2e.sh` step-by-step assert.
7. **5-doc closeout template:** Plan 07-05 closeout — 5 file (CLAUDE.md + STATE.md + REQUIREMENTS.md + ROADMAP.md + README.md) modify đồng nhất pattern Phase 3/4/5/6 carry forward.

---

*Phase: 07-migration-smoke-e2e*
*Pattern mapping date: 2026-05-23 via gsd-pattern-mapper (Auto Mode `--auto`)*
*Source: CONTEXT.md `<canonical_refs>` + `<specifics>` 5-plan structure preview + 14 file mapping*
*Next: `/gsd-plan-phase 7 --auto` — generates 5-plan structure aligned with MIGRATE-01..05*
