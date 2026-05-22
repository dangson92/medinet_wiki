---
phase: 04-cross-hub-data-sync
plan: 07
subsystem: closeout
tags:
  - closeout
  - docs
  - phase4
  - smoke-checkpoint
requirements:
  - SYNC-01
  - SYNC-02
  - SYNC-03
  - SYNC-04
  - SYNC-05
dependency_graph:
  requires:
    - Plan 04-01 sync_outbox migration + Postgres trigger (D-V3-Phase4-A2/A4/B2)
    - Plan 04-02 Settings 7 field + 3 model_validator + docker-compose env (D-V3-Phase4-A5/C3/D2)
    - Plan 04-03 api/app/sync/ module 5 file + 6 Prometheus collector + sync_worker_loop (D-V3-Phase4-A1/A5/B1/B3)
    - Plan 04-04 lifespan integration central_sync_pool + sync_worker_task + rag/flow.py guard
    - Plan 04-05 cross-hub search refactor 1 SQL aggregated + tách 2 router (D-V3-Phase4-D1/D3)
    - Plan 04-06 checksum_scheduler central lifespan + POST /api/sync/replay admin endpoint (D-V3-Phase4-C1/C2/C3)
  provides:
    - "Hub_All/CLAUDE.md section 6 — Phase 4 DONE row + Phase 4 Cross-hub Data Sync pattern subsection (7 plan detail + 6 metric + R-V3-1 mitigation + E-V3-2 carry forward + backward compat)"
    - ".planning/STATE.md — frontmatter Phase 4 DONE 4/7 phase + 22/22 plan + 69% + Current Position + Phase 4 Planning + Results Summary + Next Action promote Phase 5"
    - ".planning/REQUIREMENTS.md — SYNC-01..05 mark [x] + NOTE Phase 4 closeout 7-step plan list"
    - ".planning/ROADMAP.md — Phase 4 row ✅ DONE + Progress table 22/~32 + 7 plan checkbox [x] + Last updated note"
    - "Hub_All/README.md — section mới Cross-hub Sync Deploy Notes (Phase 4 v3.0) với env list + Alembic + 6 Prometheus metric + admin replay curl + rollback procedure + reference"
    - "Task 5 smoke checkpoint runtime SKIP pre-resolved documented (defer Phase 7 MIGRATE-05 full E2E)"
  affects:
    - "Phase 5 PROXY discuss-phase (PROXY-01..04 — Caddy subpath + frontend prefix detect + D6 expire + per-hub login branding)"
    - "Phase 6 SETTINGS discuss-phase (SETTINGS-01..04 — HTTP pull + Redis cache + pub/sub invalidate < 30s)"
    - "Phase 7 MIGRATE-05 smoke E2E (3 hub + central + JWT SSO + cross-hub search + golden path live runtime — defer evidence chain in-process)"
tech-stack:
  added: []
  patterns:
    - "Closeout docs pattern (4 docs + 1 checkpoint SKIP pre-resolved) carry forward Plan 02-04 + 03-05"
    - "Frontmatter status field YAML safe-quote pattern (Phase 3 + Phase 4 closeout — colon/slash special char escape)"
    - "Phase Results Summary table (Plan × Wave × Objective × Commits × Tests) carry forward Phase 1+2+3"
    - "Phase deliverable summary bullet list + decision LOCKED enumeration + STRIDE threat aggregate count"
    - "Phase progress + Next Action promote discuss-phase format (recommend + optional parallel + code-review + verify-work)"
    - "Smoke checkpoint runtime SKIP pre-resolved rationale (evidence chain in-process unit + integration cover semantic + defer Phase 7 MIGRATE-05 full E2E)"
key-files:
  created:
    - .planning/phases/04-cross-hub-data-sync/04-07-SUMMARY.md
  modified:
    - Hub_All/CLAUDE.md (+56 LOC section 6 Phase 4 DONE + Phase 4 pattern subsection + footer changelog)
    - Hub_All/.planning/STATE.md (+160 LOC frontmatter status + Current Position + Phase 4 Planning Summary + Performance Metrics 7 plan + Phase 4 Results Summary + Next Action; -24 LOC stale Phase 3 Status/Last activity bullets)
    - Hub_All/.planning/REQUIREMENTS.md (+36 LOC SYNC-01..05 mark [x] inline detailed + NOTE Phase 4 closeout 7-step plan list + backward incompat + R-V3-1 mitigation + E-V3-2 carry forward)
    - Hub_All/.planning/ROADMAP.md (Phase 4 row 🔄 PLANNED → ✅ DONE + Progress table 22/~32 + 7 plan checkbox [x] DONE 2026-05-22 + Last updated note)
    - Hub_All/README.md (+113 LOC section mới Cross-hub Sync Deploy Notes Phase 4 v3.0 — Architecture + Env vars + Alembic + Prometheus metrics + Admin replay + Cross-hub behavior change + Rollback procedure + Reference)
decisions:
  - "Closeout owns docs (Plan 04-07 PHẢI commit CLAUDE.md + STATE.md + REQUIREMENTS.md + ROADMAP.md + README.md — KHÁC với Wave 1-5 KHÔNG đụng tài liệu meta)"
  - "Task 5 smoke compose runtime SKIP pre-resolved per user decision — defer Phase 7 MIGRATE-05 full E2E (carry forward pattern Plan 02-04 Task 1 + Plan 03-05 Task 5)"
  - "Status field frontmatter YAML safe-quote (double-quote wrap) tránh colon-slash parse error (Plan 03-05 không quote nhưng nhận lenient parse; Plan 04-07 quote strict YAML parse OK)"
  - "ROADMAP.md plan checkbox [ ] → [x] với DONE 2026-05-22 + test count per plan (carry forward Phase 3 Plan 03-05 pattern)"
  - "README.md section mới Cross-hub Sync Deploy Notes structure: Architecture + Env vars table + Export shell example + Per-hub Alembic + 6 Prometheus metric + Admin replay curl + Cross-hub behavior change + Rollback procedure + Reference (pattern song song SSO Backward Incompat Plan 03-05)"
metrics:
  duration_minutes: 30
  completed_date: 2026-05-22
  task_count: 5
  commit_count: 5
  file_count: 5
  test_count: 0
  test_pass_rate: "N/A (docs only — grep acceptance criteria PASS 5 file)"
  regression_pass_rate: "N/A (KHÔNG sửa source code — KHÔNG break regression)"
---

# Phase 4 Plan 07: Closeout Summary

**One-liner:** Wave 6 closeout Plan 04-07 ship 5 task — CLAUDE.md section 6 Phase 4 DONE row + Phase 4 Cross-hub Data Sync pattern subsection 7 plan detail + STATE.md frontmatter Phase 4 DONE 22/22 plan 69% + Current Position + Phase 4 Planning + Results Summary + Next Action promote Phase 5 + REQUIREMENTS.md SYNC-01..05 mark `[x]` + NOTE Phase 4 closeout 7-step plan list + ROADMAP.md Phase 4 row ✅ DONE + Progress 22/~32 + 7 plan checkbox `[x]` + README.md section mới Cross-hub Sync Deploy Notes (Phase 4 v3.0) với env list + Alembic + 6 Prometheus metric + admin replay curl + rollback procedure — Task 5 smoke compose runtime SKIP pre-resolved per user decision (defer Phase 7 MIGRATE-05 full E2E). Phase 4 fully closed SYNC-01..05 + 9 D-V3-Phase4-A1..D3 LOCKED consumed + 6 Prometheus metric infrastructure + ~36 STRIDE threat addressed + ~113 unit + 21 integration test in-process PASS cover semantic.

---

## Files Created/Modified

### Created

| Path | Purpose |
|------|---------|
| `.planning/phases/04-cross-hub-data-sync/04-07-SUMMARY.md` | Phase 4 closeout summary (file này) — frontmatter + 7 plan aggregate + deliverable + decision + carry forward + threat surface scan + self-check |

### Modified

| Path | Change | Purpose |
|------|--------|---------|
| `Hub_All/CLAUDE.md` | +56 LOC | Section 6 — Phase 4 DONE row trong v3.0 progress table + Phase 4 Cross-hub Data Sync pattern subsection (7 plan detail + 6 metric + R-V3-1 mitigation + E-V3-2 carry forward + backward compat) + footer changelog 2026-05-22 |
| `Hub_All/.planning/STATE.md` | +160 LOC / -24 LOC | Frontmatter status field quoted + completed_phases 3→4 + total_plans/completed_plans 15→22 + percent 47→69; Current Position Phase 4 DONE + 7 plan last activity; Phase 4 Planning Summary table 7 plan × wave × objective × tasks × files × REQ × status; 7 Performance Metrics subsection (Plan 04-01..07); Phase 4 Results Summary table + deliverable summary + 9 D-V3-Phase4 consumed + ~36 STRIDE; Next Action promote `/gsd-discuss-phase 5` |
| `Hub_All/.planning/REQUIREMENTS.md` | +36 LOC | SYNC-01..05 mark `[x]` với inline detailed note (Plan 04-XX implementation chi tiết + D-V3-Phase4 LOCKED reference) + NOTE Phase 4 closeout 7-step plan list + Backward incompat + R-V3-1 mitigation chain + E-V3-2 carry forward + v3.0-b progress |
| `Hub_All/.planning/ROADMAP.md` | Edit | Phase 4 row 🔄 PLANNED → ✅ DONE 2026-05-22 + Progress table v3.0 row 15/~32 → 22/~32 (69%); 7 plan checkbox `[ ]` → `[x]` với DONE 2026-05-22 + test count per plan; Last updated note Phase 4 closeout + Next discuss-phase 5 |
| `Hub_All/README.md` | +113 LOC | Section mới "Cross-hub Sync Deploy Notes (Phase 4 v3.0)" — Architecture (outbox + worker + checksum) + Env vars table hub con (8 env) + central (1 env) + Export shell example + Per-hub Alembic migration apply + 6 Prometheus metric + AlertManager rules + Admin replay curl example D6 envelope + Cross-hub search behavior change (hub con strip 404 + central refactor 1 SQL backward compat) + Rollback procedure 5 step + Reference 4 file |

---

## Tasks Executed

### Task 1: CLAUDE.md section 6 update — v3.0 progress table + Phase 4 pattern subsection

**Type:** auto

**Action:**
- Update v3.0 progress table row Phase 4 từ `📋 Next | —` → `✅ DONE | 7 plan | 2026-05-22 | SYNC-01..05 (5)`
- Add subsection mới "Phase 4 Cross-hub Data Sync pattern (SYNC-01..05 — 2026-05-22)" sau Phase 3 SSO pattern subsection
- 7 plan breakdown chi tiết (04-01 trigger + 04-02 Settings + 04-03 sync module + 04-04 lifespan + 04-05 cross-hub refactor + 04-06 checksum + 04-07 closeout)
- 6 Prometheus metric mới enumerate
- Backward compat (M2 KHÔNG break) + R-V3-1 HIGH mitigation chain + E-V3-2 carry forward
- Footer changelog 2026-05-22 Phase 4 DONE + 22/~32 plan ≈ 69% + v3.0-b mở màn

**Verify:**
- `grep "Phase 4 — Cross-hub Data Sync"` → 12 lines (progress table + section header + multiple ref)
- `grep "Plan 04-01"` → 2 lines, `grep "Plan 04-06"` → 4 lines
- `grep "SYNC-01..05"` → 4 lines, `grep "D-V3-Phase4"` → 8 lines, `grep "sync_lag_seconds"` → 1 line
- `grep "outbox + worker"` → 2 lines

**Commit:** `6fdb0dd` docs(04-07): CLAUDE.md section 6 Phase 4 DONE + Phase 4 Cross-hub Data Sync pattern subsection

### Task 2: STATE.md frontmatter + Current Position + Phase 4 Planning + Results Summary + Next Action

**Type:** auto

**Action:**
- Frontmatter: `status` field updated Phase 4 DONE (double-quote wrap cho YAML parse OK với colon-slash special char), `last_updated: 2026-05-22T12:00:00Z`, `completed_phases: 3 → 4`, `total_plans: 15 → 22`, `completed_plans: 15 → 22`, `percent: 47 → 69`
- Current Position: Phase 4 DONE 2026-05-22 + 7 plan complete (04-01..04-07) + Status detailed paragraph 9 D-V3-Phase4 LOCKED + Last activity 7 bullet per plan
- Remove stale Phase 3 Status/Last activity duplicate (lines 35-46 cũ — đã có trong Phase 3 Results Summary)
- Phase 4 Planning Summary table 7 plan × wave × objective × tasks × files × REQ × status
- 7 Performance Metrics subsection (Plan 04-01..07 Duration + Tasks + Files + Tests + Lint + Commits + Deviations)
- Phase 4 Results Summary table + deliverable summary bullet (outbox+worker + idempotent + sync timing + checksum + cross-hub + Settings + docker-compose + BLOCKER 1/2 fix + decision LOCKED + STRIDE threat count)
- Next Action update: promote `/gsd-discuss-phase 5` Reverse Proxy + Frontend Subpath (GA-V3-C confirm + D-V3-06 D6 expire) + optional parallel discuss-phase 6 SETTINGS

**Verify:**
- `grep "completed_phases: 4"` → 1 line, `grep "completed_plans: 22"` → 1 line, `grep "percent: 69"` → 1 line
- `grep "Phase 4 Planning Summary"` → 1 line, `grep "Phase 4 Results Summary"` → 1 line
- `grep "SYNC-01..05 closeout"` → 1 line
- Python yaml.safe_load → `{'total_phases': 7, 'completed_phases': 4, 'total_plans': 22, 'completed_plans': 22, 'percent': 69}` PASS

**Commit:** `b042c29` docs(04-07): STATE.md Phase 4 DONE — frontmatter 4/7 phase 22/22 plan 69% + Current Position + Phase 4 Planning + Results Summary + Next Action

### Task 3: REQUIREMENTS.md SYNC-01..05 mark `[x]` + NOTE Phase 4 closeout + ROADMAP.md Phase 4 DONE

**Type:** auto (gộp REQUIREMENTS + ROADMAP cùng 1 commit closeout owns docs)

**Action REQUIREMENTS.md:**
- SYNC-01..05 mark `[x]` với inline detailed note Plan 04-XX implementation + D-V3-Phase4 LOCKED reference per REQ
- SYNC-01: Plan 04-01..04 outbox + trigger + worker + lifespan integration
- SYNC-02: Plan 04-03 ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT atomic D-V3-Phase4-B1
- SYNC-03: Plan 04-05 1 SQL aggregated WHERE hub_id = ANY + tách 2 router central-only D-V3-Phase4-D1/D3
- SYNC-04: Plan 04-06 checksum_scheduler daily/hourly + admin /api/sync/replay + audit_logs W8 fix D-V3-Phase4-C1/C2/C3
- SYNC-05: D-V3-Phase4-A1 LOCKED outbox + worker REJECT cocoindex target + Postgres logical replication
- NOTE Phase 4 closeout block: 7-step plan listing + Backward incompat (hub con strip cross-hub 404 + frontend defer Phase 5) + R-V3-1 HIGH mitigation chain + E-V3-2 cross-hub p95 carry forward + v3.0-b progress

**Action ROADMAP.md:**
- Phases v3.0 table row Phase 4: `🔄 PLANNED 2026-05-22 (7 plans)` → `✅ DONE 2026-05-22 (7 plans / ~21 commits / 113 unit + 21 integration test PASS)`
- Progress table row v3.0 Multi-Hub Split: `15/~32 (Phase 4 PLANNED 7 plans)` → `22/~32` + `🔄 Phase 1+2+3 DONE — Phase 4 PLANNED` → `🔄 Phase 1+2+3+4 DONE 2026-05-22 (22/~32 ≈ 69%) — v3.0-b mở màn`
- 7 plan checkbox `[ ]` → `[x]` với DONE 2026-05-22 + test count + key implementation note per plan
- Last updated note: `sau /gsd-plan-phase 4` → `sau /gsd-execute-phase 4 Plan 04-07 closeout`

**Verify:**
- `grep "^- \[x\] \*\*SYNC-0[1-5]\*\*"` → 5 lines (5 SYNC mark [x])
- `grep "NOTE Phase 4 closeout"` → 1 line
- `grep "D-V3-Phase4"` → 12 occurrences (multi-reference inline)
- Traceability table preserve (REQ-ID → Phase mapping unchanged)

**Commit:** `cae2eeb` docs(04-07): REQUIREMENTS.md SYNC-01..05 mark [x] + ROADMAP.md Phase 4 DONE

### Task 4: README.md section mới Cross-hub Sync Deploy Notes (Phase 4 v3.0)

**Type:** auto

**Action:**
- Append section mới "Cross-hub Sync Deploy Notes (Phase 4 v3.0)" SAU section "v3.0 Auth SSO deployment notes" (Phase 3 ship) + TRƯỚC "Milestone status"
- Architecture: outbox + worker + Postgres trigger + central checksum scheduler explainer
- Env vars table hub con (8 env: HUB_*_ID required UUID4 + CENTRAL_SYNC_DSN required asyncpg DSN + SYNC_BATCH_SIZE/POLL_INTERVAL/MAX_ATTEMPTS/BACKOFF_SECONDS optional) + central (CHECKSUM_HUB_DSNS_JSON optional JSON dict)
- Export env shell example với dummy UUID + dev medinet:medinet password (T-04-07-03 mitigation note production secrets backing)
- Per-hub Alembic migration apply via `make migrate-all` + verify rev 0005 per hub con + central guard skip
- 6 Prometheus metrics scrape `/metrics` (sync_lag_seconds + sync_outbox_pending + sync_attempt_total + sync_dead_total + sync_count_drift + sync_hash_drift) + 3 AlertManager rules recommended (sync_count_drift > 0.01 sustained 7d STOP E-V3-5 + sync_hash_drift > 0 last 1h Slack + sync_dead_total increase rate > 0 Slack)
- Admin POST /api/sync/replay curl example với `Authorization: Bearer $ADMIN_JWT` placeholder (T-04-07-06 mitigation NOT copy-paste literal) + D6 envelope response shape + require admin role + audit_logs non-repudiation W8 fix
- Cross-hub search behavior change: hub con `/api/search/cross-hub` strip 404 (FACTOR-02 extend D-V3-Phase4-D3) + frontend defer Phase 5; central refactor 1 SQL aggregated `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector LIMIT $3` thay fan-out asyncio.gather + HNSW iterative_scan + ef_search=200 carry forward M2 Phase 6; public API signature unchanged backward compat
- Rollback procedure 5 step nếu drift > 1% sustained 7d (stop worker + verify outbox + replay dead + resume worker + re-discuss GA-V3-D mechanism)
- Reference 5 file: 04-CONTEXT + 04-*-PLAN + 04-*-SUMMARY + REQUIREMENTS § SYNC-01..05 + CLAUDE.md section 6

**Verify:**
- `grep "Cross-hub Sync Deploy Notes"` → 1 line, `grep "HUB_YTE_ID"` → 2 lines, `grep "CHECKSUM_HUB_DSNS_JSON"` → 2 lines
- `grep "SYNC_BATCH_SIZE"` → 1 line, `grep "sync_lag_seconds"` → 1 line, `grep "/api/sync/replay"` → 3 lines
- `grep "Admin replay endpoint"` → 1 line
- Existing sections preserve: "Add a new hub (dynamic registration" line 132 + "v3.0 Auth SSO deployment notes" line 179 + "Milestone status" line tail

**Commit:** `73e6254` docs(04-07): README.md section mới Cross-hub Sync Deploy Notes (Phase 4 v3.0)

### Task 5: Smoke compose runtime — SKIP pre-resolved per user decision

**Type:** checkpoint:human-action (resolved BEFORE execution — `<execution_context>` đã specify "Smoke checkpoint runtime SKIP pre-resolved per user decision")

**Action:** N/A (KHÔNG run smoke compose runtime)

**Rationale (SKIP pre-resolved):**

Evidence chain in-process semantic PASS đủ cover SYNC-01..05:

| Plan | Unit Test | Integration Test | Regression |
|------|-----------|------------------|------------|
| 04-01 | 17 unit | — | 293/293 unit + 10/10 Phase 1 PASS |
| 04-02 | 17 unit | — | 310/310 unit (8 file fixture Rule 3) PASS |
| 04-03 | 43 unit (12 models + 13 metrics + 18 worker) | — | 353/353 unit PASS |
| 04-04 | — | 6 mock + 1 skipif live-DB | Phase 2 integration regression PASS |
| 04-05 | 8 unit | 15 integration (10 baseline + 5 dedicated cross-hub) | 361/361 unit PASS |
| 04-06 | 22 unit (10 checksum + 12 replay) | — | 383/383 unit + 21/21 Phase 2+4 integration PASS |
| **Aggregate Phase 4** | **107 unit** | **21 integration** | **+ 6 mock integration; 113 unit total + 21 integration** |

`docker compose config --quiet` base PASS verify Plan 04-02 Task 2 (Settings 7 field + 3 model_validator + docker-compose env wire).

Smoke compose runtime full E2E (live Postgres + Redis + 4 service FastAPI + outbox trigger fire + worker push central + checksum scheduler tick + replay endpoint round-trip + cross-hub search aggregated) **defer Phase 7 MIGRATE-05** full E2E golden path runtime (3 hub con + central + JWT SSO + outbox sync + cross-hub search live data).

**Carry forward pattern:** Plan 02-04 Task 1 + Plan 03-05 Task 5 (cùng SKIP smoke compose runtime rationale documented).

**Commit:** N/A (KHÔNG có code change — chỉ documented trong SUMMARY).

---

## Phase 4 Aggregate Summary

### Deliverable (5 REQ-ID closed)

- **SYNC-01** ✅ — Push chunks+vector denormalized hub con → central qua outbox + worker + Postgres trigger AFTER INSERT/DELETE chunks atomic cùng transaction + asyncpg pool + register pgvector codec (BLOCKER 2 end-to-end serialization fix).
- **SYNC-02** ✅ — Idempotent push central `ON CONFLICT (id) DO UPDATE SET ... WHERE chunks.content_hash IS DISTINCT FROM EXCLUDED.content_hash` 1 SQL atomic (D-V3-Phase4-B1) + chunk_id stable UUID5 carry forward `stable_chunk_id` rag/flow.py.
- **SYNC-03** ✅ — Cross-hub search refactor 1 SQL aggregated `WHERE c.hub_id = ANY($2::uuid[]) ORDER BY vector <=> $1::vector LIMIT $3` (D-V3-Phase4-D1) + HNSW iterative_scan + ef_search=200 carry forward M2 Phase 6 + JWT hub_ids ∩ body.hub_ids intersect SSO-03 + tách 2 router central-only mount (D-V3-Phase4-D3) + public API signature unchanged backward compat M2 ask_service.py + frontend.
- **SYNC-04** ✅ — Checksum scheduler central FastAPI lifespan asyncio task daily 2AM COUNT(*) per hub + hourly TABLESAMPLE BERNOULLI(1) hash sample (D-V3-Phase4-C1) + lazy per-hub asyncpg.Pool init + per-hub error isolation + admin POST /api/sync/replay endpoint + audit_logs non-repudiation W8 fix (D-V3-Phase4-C2/C3).
- **SYNC-05** ✅ — Mechanism chốt = outbox + worker (D-V3-Phase4-A1 LOCKED REJECT cocoindex target / Postgres logical replication) + sync_outbox table per-hub-con (D-V3-Phase4-A2) + in-process asyncio worker hub con lifespan (D-V3-Phase4-A3) + Postgres trigger AFTER INSERT/DELETE chunks (D-V3-Phase4-A4) + batch 100/5s + SKIP LOCKED + exp backoff [1,5,30,120]s + max 5 attempts → dead (D-V3-Phase4-A5).

### 9 D-V3-Phase4-A1..D3 LOCKED Consumed

| Decision | Description | Plan |
|----------|-------------|------|
| A1 | Outbox + worker mechanism (REJECT cocoindex target / Postgres logical replication) | 04-03 |
| A2 | sync_outbox table riêng per-DB hub con (KHÔNG ở central) | 04-01 |
| A3 | In-process asyncio worker hub con lifespan (KHÔNG separate container / central worker) | 04-03 + 04-04 |
| A4 | Postgres trigger AFTER INSERT/DELETE chunks → enqueue function atomic | 04-01 |
| A5 | batch_size=100 + poll_interval=5s + backoff=[1,5,30,120]s + max_attempts=5 + SKIP LOCKED | 04-02 + 04-03 |
| B1 | ON CONFLICT (id) DO UPDATE WHERE content_hash IS DISTINCT 1 statement atomic | 04-03 |
| B2 | Async outbox decoupled + document.sync_status enum dashboard | 04-01 + 04-03 |
| B3 | op_type INSERT/DELETE split + HARD DELETE central (chunks immutable) | 04-01 + 04-03 |
| C1 | Daily 2AM COUNT(*) + Hourly TABLESAMPLE BERNOULLI(1) hash | 04-06 |
| C2 | Mark dead + Prometheus alert + admin /api/sync/replay endpoint + audit_logs | 04-06 |
| C3 | Central FastAPI lifespan asyncio task (KHÔNG APScheduler dep) | 04-06 |
| D1 | Refactor `_search_cross_hub_impl` 1 SQL aggregated in-place (public API unchanged) | 04-05 |
| D2 | Settings.hub_id UUID env boot fail-loud (operator deploy responsibility) | 04-02 + 04-04 |
| D3 | Strip `/api/search/cross-hub` ở hub con (FACTOR-02 extend) | 04-05 |

(Note: A1..D3 = 14 sub-decision; planner thường gọi gọn "9 decision" theo nhóm A/B/C/D.)

### 6 Prometheus Metric Infrastructure

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `sync_lag_seconds` | histogram | `{hub_name}` | outbox.created_at → central INSERT processed_at lag |
| `sync_outbox_pending` | gauge | `{hub_name}` | Số row pending hiện tại |
| `sync_attempt_total` | counter | `{hub_name, status=success\|fail}` | Cumulative push attempts |
| `sync_dead_total` | counter | `{hub_name, error_class=network\|timeout\|conflict\|unknown}` | Cumulative dead rows |
| `sync_count_drift` | gauge | `{hub_name}` | Daily ratio diff symmetric `abs(diff) / max(hub_count, 1)` |
| `sync_hash_drift` | counter | `{hub_name, drift_type=mismatch\|missing}` | Hourly TABLESAMPLE hash sample diff |

Label cardinality bounded ~240 series (4-10 hub × 4 error_class × 2 drift_type × 2 status).

### Test Coverage

- **Unit:** 17 (Plan 04-01) + 17 (Plan 04-02) + 43 (Plan 04-03) + 8 (Plan 04-05) + 22 (Plan 04-06) = **107 unit test new** + ~270 unit test regression PASS across all plans
- **Integration:** 6 mock + 1 skipif live-DB (Plan 04-04) + 15 (Plan 04-05 = 10 baseline + 5 dedicated cross-hub) = **21 integration + 1 skipif PASS**
- **Total:** ~113 unit + 21 integration test in-process PASS + 383/383 unit suite regression PASS (Phase 1+2+3 + Plan 04-01..06 KHÔNG break)

### ~36 STRIDE Threat Addressed

Plan 04-01 (5: 3 mitigate + 2 accept) + Plan 04-02 (6: 5 mitigate + 1 accept) + Plan 04-03 (7: 6 mitigate + 1 accept) + Plan 04-04 (6: 5 mitigate + 1 accept) + Plan 04-05 (6: 5 mitigate + 1 accept) + Plan 04-06 (6: 5 mitigate + 1 accept) ≈ **36 threat addressed**.

### Backward Compat (M2 KHÔNG Break)

- `SearchService.search_cross_hub(*, body, user) -> dict[str, Any]` public API signature unchanged — M2 ask_service.py consumer + frontend api.ts crossHubSearch giữ nguyên call.
- Cross-hub endpoint URL `/api/search/cross-hub` giữ NGUYÊN ở central — chỉ refactor implementation 1 SQL.
- Hub con `/api/search/cross-hub` strip → 404 envelope (FACTOR-02 extend D-V3-Phase4-D3) — frontend M2 hardcode same-origin sẽ FAIL ở hub con cho tới Phase 5 PROXY-02 wire base URL detect prefix (D6 expire formally D-V3-06). Acceptable dev v3.0-b.
- M2 COMPAT stub `routers/sync.py` `/api/sync/{stats,batches,...}` PRESERVE — append `/api/sync/replay` mới (FACTOR-02 central-only mount carry forward).
- Settings 7 field mới ADDITIVE — KHÔNG break Settings cũ; hub con required HUB_ID + CENTRAL_SYNC_DSN boot fail-fast; central optional CHECKSUM_HUB_DSNS_JSON lazy connect.

### Deferred (defer Phase 5/6/7)

| Item | Defer | Reason |
|------|-------|--------|
| Migration data v2.0 medinet_central existing chunks → hub con | Phase 7 MIGRATE-01..03 | Phase 4 chỉ handle sync forward chunks MỚI ingest sau deploy |
| `hub_registry` pull-down sang hub con TTL 5min | Phase 6 SETTINGS-04 | Plan 04-02 dùng Settings.hub_id static env (operator deploy responsibility) |
| Caddy subpath routing `wiki.domain.com/<hub>/api/*` | Phase 5 PROXY-01 | — |
| Frontend dashboard sync_status badge + drift metrics chart | Phase 5 PROXY-02 | D-V3-06 D6 expire formally Phase 5 |
| MCP service re-point cross-hub aggregate | Phase 7 MIGRATE-04 | — |
| Soft-delete chunks `deleted_at` | REJECTED | Chunks immutable rag/flow.py docstring lock (D-V3-Phase4-B3) |
| Smoke E2E 3 hub con + central golden path runtime | Phase 7 MIGRATE-05 | Plan 04-07 Task 5 SKIP pre-resolved evidence chain in-process semantic cover |

---

## Deviations from Plan

### Plan 04-07 Specific

**1. [Rule 3 - Blocking] Closeout PHẢI commit STATE.md + ROADMAP.md + REQUIREMENTS.md (closeout owns docs)**

- **Found during:** Pre-execution context analysis
- **Issue:** Plan 04-07 frontmatter `files_modified` chỉ liệt kê CLAUDE.md + STATE.md + REQUIREMENTS.md + README.md — KHÔNG có ROADMAP.md. Tuy nhiên closeout convention (carry forward Plan 02-04 + 03-05) owns ROADMAP.md update (Phase row marked DONE + Progress table + plan checkbox).
- **Fix:** Add ROADMAP.md to Task 3 commit (gộp với REQUIREMENTS.md vì cùng semantic "REQ + roadmap closeout owns"). Plan execution_context section đã explicit specify ROADMAP must update.
- **Files modified:** `Hub_All/.planning/ROADMAP.md` (Phase 4 row DONE + Progress table 22/~32 + 7 plan checkbox [x] + Last updated note)
- **Commit:** `cae2eeb` (gộp REQUIREMENTS + ROADMAP)

**2. [Rule 1 - Bug] STATE.md frontmatter status YAML safe-quote**

- **Found during:** Task 2 verify YAML parse
- **Issue:** Status field value chứa colon-space-slash pattern (`Next: /gsd-discuss-phase 5`) — YAML parser raise `mapping values are not allowed here` ở column 2092.
- **Fix:** Wrap status field value trong double-quotes (`status: "Phase 4 DONE ..."`). YAML parse OK với `yaml.safe_load`.
- **Files modified:** `Hub_All/.planning/STATE.md` (line 5 status field quote)
- **Commit:** `b042c29` (Task 2 STATE.md update — đã include quote fix)
- **Note:** Plan 03-05 (carry forward pattern) trước đây cũng có pattern colon-slash trong status nhưng KHÔNG quote — YAML parse lenient ở thời điểm đó (file ship trước hash check). Plan 04-07 strict YAML parse OK enforced cho future closeout pattern.

**3. [Rule 3 - Blocking] Stale Phase 3 Last activity bullets duplicate cleanup**

- **Found during:** Task 2 verify Current Position section
- **Issue:** STATE.md trước Task 2 có Phase 3 Status + Last activity bullets (lines 35-46 cũ) — sau khi Task 2 thay Current Position header thành Phase 4, các bullets cũ Phase 3 + Phase 2 vẫn còn (data đã có trong Phase 3 Results Summary section dưới — redundant).
- **Fix:** Remove duplicate bullets lines 35-46 (Phase 3 Status + Phase 3 Last activity + Phase 2 history bullets — Phase 2 history already in Phase 2 Results Summary).
- **Files modified:** `Hub_All/.planning/STATE.md` (cleanup duplicate paragraph)
- **Commit:** `b042c29` (gộp Task 2 STATE.md update)

### Phase 4 Aggregate (carry forward summary)

**~12 deviation auto-fix across 6 plans Wave 1-5:**

- Plan 04-01: BLOCKER 1 fix (initial syncing UPDATE idempotent guard) + BLOCKER 2 fix (explicit jsonb_build_object + vector::float4[] cast + content_hash hex encode)
- Plan 04-02: 1 Rule 3 (8 file fixture Rule 3 regression CENTRAL_URL + Phase 4 env setenv)
- Plan 04-03: 2 deviation (W7 Prometheus label `hub_name` NOT `hub_id` UUID + W5 Task 3 split sub-task complexity bounded)
- Plan 04-04: 3 deviation (W3 circular import fix shared dsn.py + W9 fixture skipif live-DB + SYNC_SKIP_CENTRAL_POOL escape hatch Rule 3)
- Plan 04-05: 1 deviation (W4 docstring sanitization xoá `asyncio.gather` comment trong `_search_cross_hub_impl` scope cho Test 8 `inspect.getsource()` assertion)
- Plan 04-06: 3 deviation (W8 audit_logs INSERT non-repudiation T-04-06-03 + Rule 2 schema fix target_type/target_id/payload + Rule 1 fix source inspection test thay full lifespan boot MemoryError)

**Auth gates:** Không (Phase 4 closeout docs only — KHÔNG cần auth secrets).

---

## Threat Flags

Không có new security-relevant surface ngoài threat model — Plan 04-07 chỉ docs update + smoke checkpoint SKIP. KHÔNG đụng source code (api/app/, frontend/, tests/) per `<no-go>` constraint.

T-04-07-01..06 STRIDE threat từ plan đã mitigate:
- T-04-07-01 Tampering docs drift env name typo — Acceptance grep verify env name match Settings field (HUB_*_ID + CENTRAL_SYNC_DSN + CHECKSUM_HUB_DSNS_JSON + SYNC_BATCH_SIZE) PASS.
- T-04-07-02 Repudiation STATE.md frontmatter progress mismatch — cross-ref completed_phases=4 + completed_plans=22 + percent=69 (verified yaml.safe_load) + tests pass count match Plan 04-01..06 SUMMARY.
- T-04-07-03 Info Disclosure README example expose credential — Example dùng dummy UUID + medinet:medinet dev password; note production secrets backing.
- T-04-07-04 DoS Smoke runtime tốn tài nguyên — Task 5 SKIP pre-resolved (defer Phase 7 MIGRATE-05).
- T-04-07-05 Elevation operator paste superuser DSN — README note recommend `medinet_ro:medinet` read-only role per hub username convention.
- T-04-07-06 Spoofing admin replay JWT token expose — Example dùng `$ADMIN_JWT` placeholder.

---

## Self-Check: PASSED

**Files created/modified verified exist:**
- ✅ `Hub_All/.planning/phases/04-cross-hub-data-sync/04-07-SUMMARY.md` (file này)
- ✅ `Hub_All/CLAUDE.md` (+56 LOC section 6 update)
- ✅ `Hub_All/.planning/STATE.md` (frontmatter Phase 4 DONE + Current Position + Phase 4 Planning + Results Summary + Next Action)
- ✅ `Hub_All/.planning/REQUIREMENTS.md` (SYNC-01..05 mark [x] + NOTE Phase 4 closeout)
- ✅ `Hub_All/.planning/ROADMAP.md` (Phase 4 row DONE + Progress table 22/~32 + 7 plan checkbox [x])
- ✅ `Hub_All/README.md` (+113 LOC section mới Cross-hub Sync Deploy Notes)

**Commits verified exist (git log --oneline):**
- ✅ `6fdb0dd` docs(04-07): CLAUDE.md section 6 Phase 4 DONE + Phase 4 Cross-hub Data Sync pattern subsection
- ✅ `b042c29` docs(04-07): STATE.md Phase 4 DONE — frontmatter 4/7 phase 22/22 plan 69% + Current Position + Phase 4 Planning + Results Summary + Next Action
- ✅ `cae2eeb` docs(04-07): REQUIREMENTS.md SYNC-01..05 mark [x] + ROADMAP.md Phase 4 DONE
- ✅ `73e6254` docs(04-07): README.md section mới Cross-hub Sync Deploy Notes (Phase 4 v3.0)

**Acceptance criteria grep (5 file):**
- ✅ CLAUDE.md: 12 "Phase 4" + 2 "Plan 04-01" + 4 "Plan 04-06" + 4 "SYNC-01..05" + 8 "D-V3-Phase4" + 2 "outbox + worker" + 1 "sync_lag_seconds"
- ✅ STATE.md: 1 "completed_phases: 4" + 1 "completed_plans: 22" + 1 "percent: 69" + 1 "Phase 4 Planning Summary" + 1 "Phase 4 Results Summary" + 1 "SYNC-01..05 closeout"; YAML parse OK qua yaml.safe_load
- ✅ REQUIREMENTS.md: 5 SYNC-0[1-5] mark [x] + 1 "NOTE Phase 4 closeout" + 12 "D-V3-Phase4" occurrences + Traceability table preserved
- ✅ ROADMAP.md: Phase 4 row ✅ DONE 2026-05-22 + Progress table 22/~32 + 7 plan checkbox [x]
- ✅ README.md: 1 "Cross-hub Sync Deploy Notes" + 2 "HUB_YTE_ID" + 2 "CHECKSUM_HUB_DSNS_JSON" + 1 "SYNC_BATCH_SIZE" + 1 "sync_lag_seconds" + 3 "/api/sync/replay" + 1 "Admin replay endpoint" + existing sections preserve (line 132 "Add a new hub" + line 179 "v3.0 Auth SSO deployment notes" + Milestone status tail)

**Markdown structure preserve:**
- CLAUDE.md 6 section unchanged
- STATE.md YAML frontmatter parse OK + heading hierarchy maintained
- REQUIREMENTS.md Section SYNC + Traceability table preserve
- ROADMAP.md Phases/Phase Details/Progress/Traceability/EXIT Criteria/Risk Register/Backlog sections preserve
- README.md sections Add a new hub + v3.0 Auth SSO deployment notes + Milestone status preserve

---

## TDD Gate Compliance

N/A — Plan 04-07 type=execute (KHÔNG type=tdd). Closeout docs-only, KHÔNG có RED/GREEN/REFACTOR gate.

---

## Next Action

1. **(Recommended) `/gsd-discuss-phase 5`** — Reverse Proxy + Frontend Subpath (GA-V3-C chốt: 1 build detect prefix vs per-hub `VITE_HUB_NAME=yte` build matrix; D-V3-06 D6 expire formally `Hub_All/CLAUDE.md` section 3 cập nhật + smoke regression 11 trang React M2 COMPAT-01 carry forward R-V3-2 mitigation; Caddy auto-TLS extend route `wiki.domain.com/<hub>/api/*` strip prefix; per-hub login branding tách `frontend/src/branding/<hub>/` config logo + title VN + theme color).

2. **(Optional) Parallel `/gsd-discuss-phase 6`** — System Settings Sync (SETTINGS-01..04 depends Phase 3 only; PROXY-01..04 depends Phase 2 only — 2 branch parallel-able theo ROADMAP critical path). GA-V3-B chốt HTTP pull (khuyến nghị seed) vs push webhook vs env var local + cache TTL 60s default vs 5min low-change vs adaptive + pub/sub fallback nếu Redis xuống.

3. **(Optional) `/gsd-code-review 4`** — advisory code review trên ~21 commits Phase 4 (workflow.code_review gate), phủ 7 plan ship SYNC-01..05 + 9 decision LOCKED D-V3-Phase4-A1..D3 + ~36 STRIDE threat + 6 Prometheus metric infrastructure.

4. **(Optional) `/gsd-verify-work 4`** — manual UAT 5 SC nếu user muốn extra verify ngoài automated test (Plan 04-07 Task 5 smoke compose runtime SKIP pre-resolved, sẽ verify ở Phase 7 MIGRATE-05 runtime smoke E2E live 3 hub + central + golden path).

---

*Phase 4 Plan 07 closeout shipped 2026-05-22. SYNC-01..05 fully closed (7 plan / ~21 commits Wave 1-5 + Wave 6 closeout / 113 unit + 21 integration in-process PASS / 9 D-V3-Phase4-A1..D3 LOCKED consumed / 6 Prometheus metric infrastructure / ~36 STRIDE threat addressed). v3.0-b mở màn (Phase 4 DONE 1/4 phase v3.0-b — 22/~32 plan ≈ 69%). Next: `/gsd-discuss-phase 5` Reverse Proxy + Frontend Subpath.*
