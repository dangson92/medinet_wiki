---
plan: 06
phase: 1
wave: 4
status: completed
completed_at: 2026-05-13
commit: a4231e2
---

# Plan 06 — SUMMARY

## Objective hoàn thành
Tạo `Hub_All/.planning/CONVENTIONS.md` mới cho stack Python M2 với 5 section bắt buộc theo CORE-05. Tài liệu là source of truth chuẩn code cho Phase 2-10.

## Files created
- `Hub_All/.planning/CONVENTIONS.md` — 364 lines (~12 KB) — 5 section + Reference Documents

## Files NOT modified (per execution_rules)
- `Hub_All/.planning/codebase/CONVENTIONS.md` — Go historical, giữ làm tham chiếu khi port
- `Hub_All/.planning/STATE.md` — orchestrator owns
- `Hub_All/.planning/ROADMAP.md` — orchestrator owns
- `Hub_All/CLAUDE.md` — Plan 05 đã rewrite, không touch
- `Hub_All/api/*` — Plan 03/04 đã hoàn tất

## Commit
- `a4231e2` docs(phase-01): tạo .planning/CONVENTIONS.md cho stack Python M2

## Verification results

### Structural checks (PASSED)
- File tồn tại tại `.planning/CONVENTIONS.md`: OK
- Total H2 headings: 6 (≥6 required: 5 numbered + Reference Documents)
- 5 numbered headings `## 1.` … `## 5.`: 5 (≥5 required)
- Python fenced code blocks: 10 (≥3 required)
- DON'T anti-patterns: 5 (≥3 required)
- PITFALLS.md references: 5 (≥2 required)
- Line count: 364 (≥200 required)

### Section heading checks (PASSED)
- `## 1. Test Strategy` → 1
- `## 2. Naming Conventions` → 1
- `## 3. APP_NAMESPACE Policy` → 1
- `## 4. FastAPI Middleware Order` → 1
- `## 5. Logging Fields` → 1

### Content keyword checks (PASSED — all targets met)
| Keyword | Required | Actual |
|---|---|---|
| `medinet_prod` | ≥2 | 7 |
| `snake_case` | ≥3 | 12 |
| `medinet_wiki_ingest` | ≥1 | 6 |
| `request_id` | ≥2 | 7 |
| `P9` (test coverage) | ≥1 | 1 |
| `P11` (middleware) | ≥1 | 1 |
| `P2` (cocoindex naming) | ≥1 | 2 |
| `P7` (schema isolation) | ≥1 | 2 |
| `P17` (cosine vs L2) | ≥1 | 2 |
| `P19` (cocoindex pin) | ≥1 | 1 |
| `vector_cosine_ops` | ≥1 | 1 |
| `E1` (EXIT criteria) | ≥1 | 4 |
| `EXIT criteria E1-E5` | ≥1 | 2 |
| `M2a EXIT GATE` | ≥1 | 1 |
| `@cocoindex.flow_def` | ≥1 | 3 |
| `structlog` | ≥2 | 9 |
| `X-Request-Id` | ≥1 | 6 |
| `REVERSED` | ≥1 | 3 |
| `cocoindex==1.0.3` | ≥1 | 1 |

## Key content delivered

### Section 1: Test Strategy
- Critical-path mandatory testing model (target ≥50%, not comprehensive >80%)
- Bảng 6 critical module với test scenario (Auth, RBAC, Hub isolation, Ingest, Search, Ask)
- Tooling stack: pytest>=8, pytest-asyncio, httpx.AsyncClient + ASGITransport, asgi-lifespan, testcontainers
- `@pytest.mark.critical` marker + CI gate
- DO/DON'T example cho hub isolation test
- Reference: Pitfall P9, HARD-03 Phase 10

### Section 2: Naming Conventions
- Bảng 11-row covering Python (package/class/function/constant/file/test) + CocoIndex (flow/target) + Postgres (table/column) + REQ-ID
- CocoIndex lowercase rule chi tiết — table format `<APP_NAMESPACE>__<flow_name>__<target_name>`
- Vector index ops pin `vector_cosine_ops`
- DO/DON'T flow definition example
- Reference: Pitfall P2, P17, P19

### Section 3: APP_NAMESPACE Policy
- `APP_NAMESPACE=medinet_prod` cố định mọi env (KHÔNG dùng để env-separate)
- Env separation qua 3 lớp: database logical / schema / container instance
- Bảng thực tế: `cocoindex.medinet_prod__medinet_wiki_ingest__chunks`
- DO/DON'T `.env` + `\dt cocoindex.medinet_prod__*` query example
- Reference: Pitfall P2, P7, R5

### Section 4: FastAPI Middleware Order (REVERSED từ Go Gin)
- "Onion model" rule — add CUỐI execute ĐẦU TIÊN
- Bảng so sánh Go Gin order vs FastAPI order
- DO example: 5 middleware đúng order (RateLimit → CORS → SecurityHeaders → RequestId → ErrorHandler)
- DON'T example: port thẳng từ Go → ErrorHandler trở thành innermost
- CORS production check validator code (P12 mitigation)
- Reference: Pitfall P11, P12

### Section 5: Logging Fields
- structlog JSON output match Go `log/slog` semantic
- Bảng 10 required fields (level/msg/ts/request_id/user_id/hub_id/latency_ms/path/method/status)
- X-Request-Id middleware implementation
- DO: structlog.get_logger với PII-safe email hash
- DON'T: f-string logging, log password raw
- Reference: HARD-01 Phase 10, STACK.md structlog 25.x

### Reference Documents section
- Link 8 docs (PROJECT/REQUIREMENTS/ROADMAP + 4 research + Go legacy CONVENTIONS)
- Bảng EXIT criteria E1-E5 (R3 mitigation)
- M2a EXIT GATE marker giữa Phase 4 và Phase 5

## Phase 1 final state

**6/6 plans complete:**
- Plan 01: ✓ (Wave 1)
- Plan 02: ✓ (Wave 1)
- Plan 03: ✓ (Wave 2 — `api/app/main.py` skeleton)
- Plan 04: ✓ (Wave 2 — RSA key generation script)
- Plan 05: ✓ (Wave 3 — `docling-pipeline/` demolition + CLAUDE.md M2 rewrite)
- Plan 06: ✓ (Wave 4 — this plan — CONVENTIONS.md)

**Wave 4 (final wave) status:** COMPLETED

Phase 1 (Infra Skeleton + Demolition + Exit Criteria) hoàn tất. Sẵn sàng tiến vào Phase 2 (Schema & Migrations) theo ROADMAP.

## Deviations
None — content followed paste-ready spec từ Plan 06 exact.
