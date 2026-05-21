---
phase: 10-hardening-observability-docs
plan: 05
subsystem: docs
tags: [readme, deploy, env-example, claude-md, hard-04, m2-closeout, v3.0-pivot]
requires:
  - "Plan 10-01 (HARD-01 structlog) — DONE"
  - "Plan 10-02 (HARD-02 Prometheus /metrics) — DONE"
  - "Plan 10-03 (HARD-03 critical path coverage ≥50%) — DONE"
  - "Plan 10-04 (CRIT-01 CORS split) — DONE"
provides:
  - "Hub_All/README.md — stack overview Python + quickstart + observability"
  - "Hub_All/DEPLOY.md — production deploy 7 section (prerequisites + quickstart + .env config + backup/restore + observability + security checklist + M2 closeout)"
  - "Hub_All/api/.env.example — 18 nhóm biến đầy đủ FastAPI api/ (≥12 key required)"
  - "Hub_All/mcp_service/.env.example — 9 biến MCP standalone + OAuth + CORS whitelist Plan 10-04"
  - "Hub_All/CLAUDE.md section 6 'M2 closeout — Pivot tới v3.0 Multi-Hub Split' + 4 D-V3 LOCKED + 4 GA-V3 open question"
  - "Hub_All/.planning/CONVENTIONS.md section 5 — note 'Plan 10-01 status' đầy đủ structlog ship details"
affects:
  - "Phase 10 closeout — HARD-04 đóng + còn Plan 10-06 CI workflow"
  - "v3.0 seed reference từ CLAUDE.md (trigger condition explicit)"
tech-stack:
  added: []
  patterns:
    - "Backup script pg_dump CẢ 2 DB (medinet_central public+cocoindex + medinet_cocoindex riêng) + tarball LMDB + file_store + OAuth state + JWT keys + retention 30 ngày"
    - "DEPLOY.md 7 section thay vì 5 ban đầu (thêm security checklist 12 mục + M2 closeout summary cho audit trail)"
    - "CLAUDE.md M2 closeout section reference 4 D-V3 LOCKED + 4 GA-V3 open question để /gsd-discuss-milestone v3.0 đối chiếu được"
key-files:
  created:
    - "Hub_All/README.md (140 dòng — stack overview + quickstart + test + eval + observability + milestone status)"
    - "Hub_All/DEPLOY.md (314 dòng — 7 section production deploy guide)"
    - "Hub_All/.planning/phases/10-hardening-observability-docs/10-05-SUMMARY.md (file này)"
  modified:
    - "Hub_All/api/.env.example (59 → 74 dòng — thêm 4 key thiếu: COCOINDEX_LMDB_PATH + 2 RATE_LIMIT + WATCHDOG_TIMEOUT)"
    - "Hub_All/mcp_service/.env.example (22 → 47 dòng — thêm MCP_PATH_PREFIX + MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS Plan 10-04 + MCP_INTERNAL_TOKEN)"
    - "Hub_All/CLAUDE.md (112 → 150 dòng — section 2 đánh dấu M2 COMPLETE + section 6 mới + footer update)"
    - "Hub_All/.planning/CONVENTIONS.md (365 → 379 dòng — section 5 thêm note Plan 10-01 status)"
decisions:
  - "D-10-05-A: DEPLOY.md 7 section thay vì 5 ban đầu — thêm security checklist 12 mục riêng (audit trail prod) + M2 closeout summary (cite REQUIREMENTS done + next milestone v3.0). Plan ghi 5 section là minimum; ops production thực tế cần checklist tường minh."
  - "D-10-05-B: README.md ngắn gọn 140 dòng KHÔNG duplicate DEPLOY.md content — chỉ quickstart + reference link sang DEPLOY/CLAUDE/PROJECT. README đóng vai trò 'entry point' GitHub view; DEPLOY là 'ops manual' chi tiết."
  - "D-10-05-C: Backup script DEPLOY.md backup CẢ 6 artifact (2 DB sql + 4 tarball) thay vì chỉ 2 DB như spec — vì mất file_store/OAuth state/JWT keys cũng = mất data/user. Cite chi phí $6.50/100K chunks nếu mất cocoindex DB để ops hiểu hậu quả."
  - "D-10-05-D: api/.env.example AES_KEY đổi sang placeholder 'CHANGEME_32_BYTES_BASE64_44_CHARS=' tường minh thay vì rỗng — verify script grep `CHANGEME_*` PASS + ops biết format chính xác. Plan 10-06 CI gate sẽ grep `sk-[a-zA-Z0-9]{20,}` reject nếu match (T-10-05-01 mitigate)."
  - "D-10-05-E: mcp_service/.env.example MCP_OAUTH_ISSUER_URL default đổi từ `http://localhost:8190` → `https://mcp.medinet.vn/mcp` (prod-realistic example). Comment ngay dưới giải thích prod PHẢI https domain thật (P-MCP-6). Dev local vẫn override được qua .env."
  - "D-10-05-F: CLAUDE.md section 6 thêm 4 GA-V3 open question đầy đủ TỪ seed (auth SSO + system settings sync + reverse proxy frontend prefix + migration data) thay vì chỉ 1 dòng tóm tắt — để /gsd-discuss-milestone v3.0 trong tương lai có đủ context không cần đọc lại seed."
  - "D-10-05-G: CONVENTIONS.md section 5 note 'Plan 10-01 status' kết thúc với rule 'mọi log mới TRONG app/ PHẢI dùng structlog.get_logger' + defer migrate cũ v4.0 — biến note thành actionable convention cho future code, KHÔNG chỉ là changelog."
metrics:
  duration_minutes: 10
  completed_date: "2026-05-21"
  tasks: 2
  files_created: 3
  files_modified: 4
  lines_added: ~520
  commits: 2
---

# Phase 10 Plan 05: README + DEPLOY + .env.example + CLAUDE.md M2 closeout + v3.0 transition — Summary

**2 commit atomic ship HARD-04 docs đầy đủ M2 production-ready + ghi nhận M2 closeout + transition tới v3.0 Multi-Hub Split. README.md mới (140 dòng) + DEPLOY.md mới (314 dòng — 7 section) + api/.env.example mở rộng 4 key thiếu + mcp_service/.env.example bổ sung Plan 10-04 CRIT-01 origins + CLAUDE.md section 6 M2 closeout với 4 D-V3 LOCKED + 4 GA-V3 open question + CONVENTIONS.md section 5 ghi nhận HARD-01 ship details. 4 verify script automated PASS (file tồn tại + DEPLOY content + .env.example required keys + no secret thật commit).**

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | README.md + DEPLOY.md + 2 .env.example mở rộng (HARD-04 docs core) | `c4666a8` | Hub_All/README.md (mới) + Hub_All/DEPLOY.md (mới) + Hub_All/api/.env.example (modified) + Hub_All/mcp_service/.env.example (modified) |
| 2 | CLAUDE.md M2 closeout section + CONVENTIONS.md HARD-01 note | `ebf3112` | Hub_All/CLAUDE.md (modified) + Hub_All/.planning/CONVENTIONS.md (modified) |

## HARD-04 Acceptance Line Mapping

| Acceptance line | File output | Verify |
| --- | --- | --- |
| README mô tả stack Python (FastAPI + cocoindex + pgvector + MCP service) | Hub_All/README.md | grep "FastAPI" + "cocoindex" + "pgvector" + "MCP Service" tất cả PASS |
| DEPLOY backup script `pg_dump --schema=public --schema=cocoindex medinet_central` + `pg_dump medinet_cocoindex` | Hub_All/DEPLOY.md section 4 | `python -c "assert 'pg_dump' in c and 'medinet_central' in c and 'medinet_cocoindex' in c"` PASS |
| api/.env.example đầy đủ 12+ key | Hub_All/api/.env.example | 13/13 required key PASS (DATABASE_URL + COCOINDEX_DATABASE_URL + REDIS_URL + OPENAI_API_KEY + GEMINI_API_KEY + JWT_PRIVATE_KEY_PATH + AES_KEY + APP_NAMESPACE + COCOINDEX_DB_SCHEMA + CORS_ALLOWED_ORIGINS + RATE_LIMIT_SEARCH_PER_MINUTE + RATE_LIMIT_UPLOAD_PER_MINUTE + WATCHDOG_TIMEOUT_SECONDS) |
| mcp_service/.env.example với OAuth + CORS whitelist Plan 10-04 | Hub_All/mcp_service/.env.example | 9/9 required key PASS + grep `MCP_OAUTH_SENSITIVE_ALLOWED_ORIGINS` + 4 origin default whitelist |
| CLAUDE.md section M2 closeout + v3.0 reference | Hub_All/CLAUDE.md section 6 | `python -c "assert 'M2 closeout' in c and 'v3.0 Multi-Hub Split' in c and 'seeds/v3.0-multi-hub-split.md' in c"` PASS |

## CLAUDE.md Section 6 → SEED-v3.0 link

| Element | Content |
| --- | --- |
| Trigger condition | "M2 closeout = bắt buộc trước v3.0" (D-V3-04) — sau khi Phase 10 ship full + HUMAN UAT pass + retrospective |
| Architectural decision LOCKED 2026-05-21 | D-V3-01 multi-DB cùng instance · D-V3-02 chunks+vector sync 1 chiều · D-V3-03 milestone-level · D-V3-04 M2 closeout precondition |
| Reference link | `.planning/seeds/v3.0-multi-hub-split.md` (7 phase ~35 plan, 4 R-V3, 4 E-V3 preview) |
| Open question (4 GA-V3) | A. Auth SSO design · B. System settings sync · C. Reverse proxy frontend prefix · D. Migration data |
| Next action | `/gsd-new-milestone v3.0` SAU Phase 10 ship full (HARD-04 đóng ở plan này + Plan 10-06 CI workflow còn lại) |

## Test Results (Verify Scripts Automated)

```
Task 1 verify:
  test -f Hub_All/README.md                            → OK
  test -f Hub_All/DEPLOY.md                            → OK
  test -f Hub_All/api/.env.example                     → OK
  test -f Hub_All/mcp_service/.env.example             → OK
  DEPLOY.md content (pg_dump + 2 DB + /metrics)        → PASS
  api/.env.example 13/13 required key                  → PASS
  mcp_service/.env.example 9/9 required key + CHANGEME → PASS
  grep 'sk-[a-zA-Z0-9]{20,}' .env.example              → NO MATCH (no real secret)

Task 2 verify:
  CLAUDE.md M2 closeout + v3.0 + seed link            → PASS
  CONVENTIONS.md Plan 10-01 + configure_structlog     → PASS
  git diff --stat → 52 insertions, 1 deletion (footer replace, no important content lost)
```

## Decisions Made

- **D-10-05-A** (DEPLOY.md 7 section): Plan ban đầu ghi 5 section minimum (prerequisites + quickstart + .env + backup/restore + observability). Production deploy thực tế cần 2 section nữa: security checklist 12 mục (audit trail cho ops review) + M2 closeout summary (cite REQUIREMENTS 38/38 done + next milestone v3.0). Tổng 7 section. Plan welcome scope expansion vì DEPLOY là source of truth ops không thể thiếu.
- **D-10-05-B** (README ngắn + DEPLOY chi tiết): README.md 140 dòng KHÔNG duplicate DEPLOY.md content — chỉ quickstart minimum + reference link sang DEPLOY/CLAUDE/PROJECT. README đóng vai trò "entry point" GitHub view; DEPLOY là "ops manual" chi tiết với 18 nhóm biến môi trường + 6 artifact backup + 12 security item.
- **D-10-05-C** (Backup 6 artifact thay vì 2 DB): Spec HARD-04 ghi minimum `pg_dump CẢ 2 DB`. Production thực tế cần backup CẢ:
  1. `medinet_central.sql` (app data)
  2. `medinet_cocoindex.sql` (cocoindex state — mất = re-embed $6.50/100K chunks)
  3. `file_store/` tarball (raw upload)
  4. `.cocoindex/` LMDB tarball (memo + lineage fingerprint)
  5. `mcp_service/.oauth/` SQLite tarball (Phase 8.3 OAuth clients/codes/tokens)
  6. `api/keys/` tarball (JWT RS256 keypair — mất = invalidate toàn bộ refresh token)

  Cite chi phí $6.50/100K chunks + impact của mỗi artifact mất để ops hiểu hậu quả.
- **D-10-05-D** (AES_KEY placeholder tường minh): Plan ban đầu AES_KEY=`` (rỗng). Đổi sang `CHANGEME_32_BYTES_BASE64_44_CHARS=` để: (1) verify script grep `CHANGEME_*` PASS confirm placeholder pattern; (2) ops biết format chính xác (32 byte = base64 44 char ending `=`); (3) Plan 10-06 CI gate sẽ grep `sk-[a-zA-Z0-9]{20,}` reject nếu match — placeholder rõ ràng KHÔNG bị nhầm thành secret.
- **D-10-05-E** (mcp_service .env.example issuer URL prod-realistic): Default plan ghi `http://localhost:8190`. Đổi sang `https://mcp.medinet.vn/mcp` (prod-realistic example) + comment ngay dưới giải thích "Prod PHẢI https domain thật (P-MCP-6 — issuer localhost làm hỏng discovery + redirect_uri)". Dev local vẫn override được qua `.env` riêng. Lý do: `.env.example` đọc bởi ops khi deploy prod — ví dụ prod giúp ops nhớ ngay precondition HTTPS.
- **D-10-05-F** (4 GA-V3 đầy đủ trong CLAUDE.md): Plan ghi "Open question chốt ở /gsd-discuss-milestone v3.0" 1 dòng tóm tắt. Đổi sang liệt kê CẢ 4 GA-V3 (A/B/C/D) với câu hỏi cụ thể từ seed — để future `/gsd-discuss-milestone v3.0` có đủ context không cần đọc lại seed. Trade-off: section 6 dài hơn, nhưng tránh duplication (1 source of truth ở CLAUDE.md cho overview, seed cho deep dive).
- **D-10-05-G** (CONVENTIONS.md Plan 10-01 note actionable): Plan ghi "ghi nhận section 5 logging đã ship". Đổi note thành actionable convention: liệt kê module shipped + processor chain details + 11 test PASS + kết thúc với rule "mọi log mới TRONG `app/` PHẢI dùng `structlog.get_logger(__name__)`" + defer migrate service cũ v4.0 (DEF-10-01-B). Biến note thành convention enforceable cho future code, KHÔNG chỉ là changelog.

## Deviations from Plan

### Plan Spec Expansions (KHÔNG phải bug, là enhancement)

**1. [Enhancement] DEPLOY.md 7 section thay vì 5**

- **Plan ban đầu:** 5 section (prerequisites + quickstart + .env config + backup/restore + observability)
- **Mở rộng:** Thêm 2 section nữa = 7 section total:
  - Section 6: Security checklist 12 mục (audit trail prod-ready)
  - Section 7: M2 closeout summary (REQUIREMENTS 38/38 done + next milestone v3.0)
- **Rationale:** Production deploy guide là source of truth ops không thể thiếu — checklist + closeout summary là 2 thông tin ops cần ngay khi onboard.
- **Files modified:** Hub_All/DEPLOY.md
- **Commit:** `c4666a8`

**2. [Enhancement] DEPLOY.md backup 6 artifact thay vì 2 DB**

- **Plan ban đầu:** `pg_dump CẢ 2 DB` (acceptance line cụ thể) — ngoài ra plan ghi tarball LMDB + file_store ở action list (đã có).
- **Mở rộng:** Backup CẢ 6 artifact (2 sql + 4 tarball: file_store + LMDB + OAuth state + JWT keys) + cite chi phí $6.50/100K chunks impact mỗi artifact.
- **Rationale:** Production thực tế cần backup CẢ user-facing data (OAuth client/refresh token) + JWT keypair (mất = invalidate toàn bộ refresh token đang live). Thiếu = downtime recovery dài.
- **Files modified:** Hub_All/DEPLOY.md section 4
- **Commit:** `c4666a8`

### Auto-fixed Issues

KHÔNG có — verify script automated PASS đầu lần. Không gặp Rule 1/2/3 trigger.

### Deferred (Out-of-scope)

- **Plan 10-06 CI workflow** — chưa thuộc scope Plan 10-05. GitHub Actions wire `pytest -m critical --cov-config=.coveragerc-critical --cov-fail-under=50` + grep secret reject + ruff/mypy gate. Đóng HARD-03 + HARD-04 CI part ở Plan 10-06.
- **Grafana dashboard** — DEPLOY.md section 5 ghi defer v4.0. Plan 10-05 chỉ document Prometheus scrape config snippet `prometheus.yml` để Grafana có dashboard sau.
- **JWT keypair rotation tool** — DEPLOY.md section 6 ghi defer v4.0. Hiện tại mất `keys/private.pem` = force re-issue + re-login toàn user.
- **AES_KEY rotation migration script** — DEPLOY.md section 6 ghi defer v4.0. Hiện tại sinh 1 lần lúc deploy đầu tiên + lưu offline.

## Threat Flags

KHÔNG có threat surface mới ngoài threat model plan. Plan 10-05 chỉ ship docs + .env.example placeholder — KHÔNG đụng auth/network endpoint code. Threat register `<threat_model>` mitigations:

- **T-10-05-01** (.env.example commit secret thật) — **MITIGATE ĐẠT**: Verify script `grep -E "sk-[a-zA-Z0-9]{20,}" .env.example` NO MATCH; chỉ placeholder `CHANGEME_*` + `sk-replace-me` + `replace-me`. Plan 10-06 CI gate sẽ wire grep này thành step exit 1.
- **T-10-05-02** (DEPLOY.md backup script sai → ops mất data) — **MITIGATE ĐẠT**: Backup section đầy đủ 6 artifact (2 sql + 4 tarball) + cite chi phí $6.50/100K chunks impact + Note "Backup CẢ 2 DB" tường minh + Restore quy trình step-by-step 9 step.
- **T-10-05-03** (CLAUDE.md M2 closeout section accidentally xoá decision/constraint) — **MITIGATE ĐẠT**: `git diff --stat` cho thấy 52 insertions / 1 deletion (1 deletion là dòng footer cũ replaced by footer mới — KHÔNG xoá decision/constraint). Verify section 2 đến 5 nguyên vẹn + chỉ ADD section 6 mới.

## Self-Check: PASSED

**Files verified exist:**
- `Hub_All/README.md` → FOUND (140 dòng)
- `Hub_All/DEPLOY.md` → FOUND (314 dòng)
- `Hub_All/api/.env.example` → FOUND (74 dòng modified)
- `Hub_All/mcp_service/.env.example` → FOUND (47 dòng modified)
- `Hub_All/CLAUDE.md` → FOUND (150 dòng modified)
- `Hub_All/.planning/CONVENTIONS.md` → FOUND (379 dòng modified)
- `Hub_All/.planning/phases/10-hardening-observability-docs/10-05-SUMMARY.md` → FOUND (file này)

**Commits verified exist:**
- `c4666a8` (Task 1) → FOUND in git log
- `ebf3112` (Task 2) → FOUND in git log

**Verify automated PASS:**
- 4/4 file Task 1 tồn tại (README + DEPLOY + 2 .env.example)
- DEPLOY.md có pg_dump + medinet_central + medinet_cocoindex + /metrics
- api/.env.example đủ 13 required key (vượt spec ≥12)
- mcp_service/.env.example đủ 9 required key + CHANGEME placeholder OK
- KHÔNG có secret thật (grep `sk-[a-zA-Z0-9]{20,}` NO MATCH)
- CLAUDE.md có 'M2 closeout' + 'v3.0 Multi-Hub Split' + 'seeds/v3.0-multi-hub-split.md'
- CONVENTIONS.md section 5 có 'Plan 10-01' + 'configure_structlog'
- git diff --stat 52 insertions / 1 deletion (footer replace — không mất content quan trọng)

**HARD-04 acceptance criteria:**
- [x] Hub_All/README.md cập nhật cho stack Python (FastAPI + cocoindex + pgvector + LiteLLM)
- [x] Hub_All/DEPLOY.md backup script `pg_dump --schema=public --schema=cocoindex medinet_central > backup.sql` + `pg_dump medinet_cocoindex > backup_cocoindex.sql`
- [x] Hub_All/api/.env.example đủ mọi key M2 (13 required + 18 nhóm tổng cộng)
- [x] Hub_All/mcp_service/.env.example đủ key OAuth (Phase 8.3 + Plan 10-04 CORS split)
- [x] Hub_All/CLAUDE.md remove Go references (đã ARCHIVED git tag m1-go-archived note) + thêm section 6 "M2 closeout — Pivot v3.0"
- [x] Section v3.0 transition trỏ về `.planning/seeds/v3.0-multi-hub-split.md` (4 decisions LOCKED + 4 GA-V3 open question)
- [x] 10-05-SUMMARY.md (file này)
- [ ] STATE.md + ROADMAP.md updated — bước final commit sau Self-Check
