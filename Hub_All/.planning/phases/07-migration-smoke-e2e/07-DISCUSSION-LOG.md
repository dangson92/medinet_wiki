# Phase 7: Migration + Smoke E2E - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 07-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-23
**Phase:** 07-migration-smoke-e2e
**Mode:** Auto (`--auto`) — all gray areas auto-resolved using recommended seed defaults
**Areas discussed:** GA-V3-D Snapshot Mechanism, Migration Window, MCP Strategy, Post-migration Verification

---

## Area 1: Snapshot Mechanism (GA-V3-D part 2)

| Option | Description | Selected |
|--------|-------------|----------|
| **a) pg_dump --where** | `pg_dump --data-only --table=... --where="hub_id = '<uuid>'"` — fast, schema-match via Alembic, preserves vector column 1536-dim binary | ✓ (recommended seed) |
| b) Cocoindex replay | Snapshot + replay cocoindex flow rebuild from `file_store/` — re-embed cost $500/3hub, slow 30-60min × 3, chunks `id` non-idempotent | (backup-only reserved) |

**User's choice (auto-mode):** Option a — pg_dump --where

**Rationale auto-applied:**
- Speed: ~5-10 min/hub vs 30-60 min cocoindex replay
- Cost: $0 vs $500 LLM/embedding API
- Schema compatibility: per-hub Alembic 0001..0005 already upgraded Phase 4
- Idempotency: chunks `id` (UUID5 stable) preserved exactly
- Failure backup: cocoindex replay reserved as fallback via `/api/documents/reindex` admin endpoint M2

---

## Area 2: Migration Window

| Option | Description | Selected |
|--------|-------------|----------|
| **Blue/green per-hub zero-downtime** | Snapshot → restore green → smoke → switch Caddy upstream → repeat for 3 hubs. Caddy reload ~50-100ms negligible | ✓ (recommended seed + REQUIREMENTS.md MIGRATE-02 explicit) |
| Full downtime weekend | Stop all traffic + bulk migrate + restore — simpler but UX impact + Slack/Email broadcast ops cost | |

**User's choice (auto-mode):** Blue/green per-hub zero-downtime

**Rationale auto-applied:**
- REQUIREMENTS.md MIGRATE-02 explicit "blue/green per-hub"
- R-V3-4 mitigation
- Caddy reload pattern carry forward Phase 5 PROXY-01 hub-add.sh step 9 (~50-100ms HTTP/2 keep-alive resume)
- Per-hub iteration enables go/no-go decision per hub (yte first lowest risk)
- Rollback granularity: snapshot file 30-day retention enables per-hub revert

---

## Area 3: MCP Strategy (re-confirm D-V3-02)

| Option | Description | Selected |
|--------|-------------|----------|
| **Central aggregate (re-point API_BASE_URL)** | MCP service `API_BASE_URL = https://central/api` — cross-hub search via `medinet_central.chunks` aggregated table; `search_wiki(hub_id?)` optional param | ✓ (recommended — D-V3-02 LOCKED + Phase 4 Plan 04-05 confirm) |
| Fan-out N hub | MCP service calls each hub container directly + Python merge sort — N× latency, rejected D-V3-02 Phase 1 | |

**User's choice (auto-mode):** Central aggregate

**Rationale auto-applied:**
- D-V3-02 LOCKED Phase 1 — cross-hub aggregate at central
- Phase 4 Plan 04-05 — 1 SQL aggregated `WHERE hub_id = ANY($N::uuid[])` (D-V3-Phase4-D1)
- Phase 8.3 v2.0 — mcp_service 135/135 OAuth flow stable baseline
- MCP tools signature unchanged — `hub_id` optional
- Smoke via Claude Inspector OAuth flow `wiki.domain.com/mcp/auth/v2/authorize`

---

## Area 4: Post-migration Verification Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| **Automated mandatory + human supplement** | `05-smoke-e2e.sh` 3 hub × 7 step automated (login + upload + status + search + ask + citation) BLOCKING + manual visual 4 hub × 11 page ADVISORY supplement | ✓ (recommended seed) |
| Automated only | Skip human visual smoke entirely — risk visual regression undetected v3.1 follow-up | |
| Human UAT mandatory | Skip automated — risk human error + non-reproducibility + Phase 7 endless cycle waiting on humans | |

**User's choice (auto-mode):** Automated mandatory + human supplement (advisory)

**Rationale auto-applied:**
- Automated: reproducible + exit-code clear + Prometheus assertion (cross-hub p95 < 1.5s, sync_lag < 30s, apikey cache hit, drift < 1%)
- Human supplement: catches visual regression (per-hub branding, Login state machine, M2 COMPAT-01 11 page)
- Advisory not blocking: v3.0 milestone close MUST proceed if automated PASS — visual regressions become v3.1 follow-up issues
- Resume signal: per v3.0-b precedent (Plan 03-05/04-07/05-06/06-05 — 4 phases pre-resolved skip), in --auto chain mode human checkpoint auto-fallbacks gracefully

---

## Claude's Discretion (planner decides)

- Plan numbering structure: 5 plan match MIGRATE-01..05 1:1 vs 5-7 plan decomposition by task granularity
- Specific `pg_dump` flags: `--data-only --no-owner --no-acl --column-inserts` (planner chốt)
- Snapshot retention enforcement: cron `find -mtime +30 -delete` vs manual operator
- Per-hub migration order: alphabetical (yte → duoc → hcns) vs lowest-risk-first (hcns → duoc → yte)
- Audit log format during truncate: `action='migrate.truncate_hub'` + `actor='system'` + metadata field structure
- Migration dry-run flag default: `--dry-run` default ON for truncate vs explicit `--apply`
- Smoke test data: `scripts/migrate/fixtures/sample-document.docx` content + format
- Caddy switch script scope: sed edit vs verify-only (Phase 5 `path_regexp` dynamic capture may make sed redundant)

## Deferred Ideas (NOT Phase 7 scope)

### v4.0 backlog
- Sub-hub split (v3.0 multi_hub_split per user seed memory 2026-05-21)
- Adaptive sync TTL
- HA Redis cluster + HA Postgres replica (R-V3-6 LOW)
- Snapshot encryption at-rest (`pg_dump | gpg`)
- Replay log JSON state (`migrate-state.json` resume-after-failure)
- Parallel hub migration via `xargs -P 3`

### Separate commands
- `/gsd-complete-milestone v3.0` — milestone archive trigger from STATE.md Next Action
- Production deploy actual — ops handover separate runbook
- v3.1 hot-fixes (visual regression follow-ups, if any from manual smoke)

---

*Audit log written: 2026-05-23 via /gsd-discuss-phase 7 --auto*
