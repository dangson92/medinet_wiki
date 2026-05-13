# CHECK — Phase 4: Config Hot-Swap & Circuit Breaker (ROUND 2)

**Verdict:** PASS
**Ngày:** 2026-04-29
**Round:** 2 (sau revise của planner)
**Số plan:** 4 (04-01..04-04)
**Blockers:** 0 · **Warnings critical:** 0 · **Info:** 2 (carry-over không chặn)

---

## Tổng quan dimension

| # | Dimension | Round 1 | Round 2 |
|---|-----------|---------|---------|
| 1 | Requirement Coverage (CFG-01..05) | PASS | PASS |
| 2 | Task Completeness | PASS | PASS |
| 3 | Dependency Correctness | REVISE (B1) | PASS (B1 cleared) |
| 4 | Key Links Planned | PASS | PASS |
| 5 | Scope Sanity | PASS | PASS |
| 6 | Verification Derivation | PASS | PASS |
| 7 | Context Compliance | PASS | PASS |
| 7b | Scope Reduction Detection | PASS | PASS |
| 7c | Architectural Tier | SKIPPED | SKIPPED |
| 8 | Nyquist Compliance | REVISE (B3, W6) | PASS (B3 + W6 fixed) |
| 9 | Cross-Plan Data Contracts | REVISE (B2) | PASS (B2 cleared — pipeline.go single-owner) |
| 10 | CLAUDE.md Compliance | PASS | PASS |
| 11 | Research Resolution | SKIPPED | SKIPPED |
| 12 | Pattern Compliance | SKIPPED | SKIPPED |
---

## Đánh giá từng fix Round 1

### B1 — Plan 04-03 meta-discussion wave/depends_on — CLEARED

- Plan 04-03 frontmatter: wave: 3, depends_on: [04-01, 04-02] đúng.
- Task 1 step 1 chỉ mô tả extend signature router.Setup() thuần tuý.
- KHÔNG còn đoạn meta-discussion mâu thuẫn frontmatter wave gây nhiễu executor.
- **Verdict:** PASS.

### B2 — Phân chia trách nhiệm pipeline.go — CLEARED

- **Plan 04-02 files_modified:** [backend/internal/rag/pipeline.go, backend/cmd/server/main.go]. Toàn bộ struct change + 4 setter (SetDoclingCircuit, SetAuditInserter, SetExtractorMode, SetDoclingOCRLangs) + interface AuditInserter + field doclingOCRLangs + 2 dòng WithOCRLangs ở branch auto/docling đã gom hết vào Task 1 Plan 02.
- **Plan 04-03 files_modified:** [backend/internal/router/router.go, backend/cmd/server/main.go, backend/internal/rag/extractor/docling.go] — KHÔNG có pipeline.go.
- Plan 03 objective + Task 1/2/3 + success_criteria + done của Task 2 đều khẳng định Plan này KHÔNG sửa pipeline.go + assert git diff backend/internal/rag/pipeline.go trống cho commit Plan 03.
- pipeline.go = single-writer ở Plan 02. Cross-plan data contract đã rõ.
- **Verdict:** PASS.

### B3 — Cooldown test wall-clock — CLEARED

- Plan 04-04 Task 1 step 4 lock: cooldown = 100*time.Millisecond, sleep 120*time.Millisecond, assertion elapsed > 200ms thì fail.
- KHÔNG còn time.Sleep(1100*time.Millisecond).
- Truth thứ 8 must_haves ghi rõ: Test cooldown deterministic — config cooldown 100ms, sleep 120ms, total transition < 200ms; KHÔNG dùng wall-clock 1s+.
- Done criterion: Test B chạy total < 200ms (cooldown 100ms + sleep 120ms — không flaky).
- **Verdict:** PASS.

### W1 — requestid.From(ctx) thay raw ctx.Value — FIXED

- Plan 04-02 Task 1 step 1 import github.com/medinet/hub-all-backend/internal/pkg/requestid.
- Trong auditFallback: reqID := requestid.From(ctx) + comment inline cảnh báo W1.
- KHÔNG còn helper requestIDFromCtx().
- Lưu ý cuối Task 1 nhắc lại bắt buộc dùng requestid.From(ctx).
- **Verdict:** FIXED.

### W4 — settingsRepo scope — FIXED

- Plan 04-03 Task 1 step 2 yêu cầu executor chạy grep -n settingsRepo trong backend/internal/router/router.go TRƯỚC khi viết PUT handler.
- 2 lựa chọn rõ ràng:
  - (a) Thêm settingsRepo *repository.SettingsRepo vào router.Setup signature + Task 2 pass từ main.go.
  - (b) Bỏ persistence — chỉ update cfg.RAG.Extractor in-memory + audit, comment // TODO(hardening): persist RAG_EXTRACTOR vào settings_repo khi available.
- Khuyến nghị (a) nếu settingsRepo đã có ở main.go scope.
- Plan 03 Task 2 step 2 + success_criteria #5 + SUMMARY output đều bắt buộc ghi rõ quyết định.
- **Verdict:** FIXED.

### W5 — JWT strategy — FIXED (LOCKED)

- Plan 04-04 Task 3 mở đầu LOCKED: dùng JWT thật ký bằng test jwtManager instance qua helper loginAdmin(t, jwtManager) string. KHÔNG dùng env-bypass middleware.
- Helper loginAdmin + newTestJWTManager chi tiết: sign jwtpkg.Claims{Role: admin} với key RSA generated runtime, role=admin chạy qua middleware JWTAuth + RequireRole(admin) thật.
- Nếu jwtpkg.NewWithGeneratedKey() chưa có thì inline rsa.GenerateKey(rand.Reader, 2048) + jwtpkg.NewWithKeys(...).
- Lưu ý cuối task: W5 LOCKED — KHÔNG dùng env-bypass; KHÔNG comment alternative env-bypass. Chỉ JWT thật.
- **Verdict:** FIXED (LOCKED).

### W6 — Verify commands -race flag — FIXED

- Plan 04-04 verify command từng task đều có -race:
  - Task 1: go test -race -run TestPipelineCircuit/TestExtractAndChunkAuto -v -timeout 30s ./internal/rag/
  - Task 2: go test -race -run TestHealthProbe -v -timeout 30s ./internal/rag/extractor/
  - Task 3: go test -race -run TestRagConfig -v -timeout 30s ./internal/router/
- Verify cuối block verification: cd backend && go test -race -timeout 60s ./internal/rag/... ./internal/router/... confirm không race + toàn bộ test mới PASS.
- Truth thứ 9 must_haves: Tất cả test PASS với go test -race (no data race).
- Done criteria mỗi task có với -race flag.
- **Verdict:** FIXED.
---

## Coverage REQ-ID (5/5 — không đổi)

| REQ | Plan(s) | OK |
|-----|---------|----|
| CFG-01 | 04-01 (env+circuit), 04-02 (pipeline auto), 04-04 (test) | YES |
| CFG-02 | 04-01 (.env.example), 04-02 (WithOCRLangs invoke), 04-03 (docling.go propagate) | YES |
| CFG-03 | 04-03 (admin GET/PUT), 04-04 (test) | YES |
| CFG-04 | 04-01 (Redis state), 04-03 (PUT reset), 04-04 (test) | YES |
| CFG-05 | 04-02 (auditFallback) | YES |

---

## Mapping 5 ROADMAP success criteria — vẫn đảm bảo

| # | Success criterion | Plan cover | OK |
|---|-------------------|-----------|----|
| 1 | Tắt Docling -> fallback auto + threshold trigger open | 04-02 + 04-04 Test A/D | OK |
| 2 | Cooldown half-open retry close lại | 04-04 Test B/C (cooldown 100ms) | OK |
| 3 | GET /api/rag-config 5 field mới | 04-03 + 04-04 Task 3 | OK |
| 4 | PUT extractor_mode runtime + reset Redis circuit | 04-03 PUT + 04-04 Test PUT_ValidMode | OK |
| 5 | Audit rag_fallback row khi fallback | 04-02 auditFallback + 04-04 Test D | OK |

Smoke end-to-end Docker thật defer sang /gsd-verify-work 4 — chấp nhận.

---

## INFO carry-over (không chặn)

### I1 — miniredis pin version (W3 round 1, demoted)

- Plan 04-01 Task 2 vẫn go get github.com/alicebob/miniredis/v2 không pin tag. Reproducible build có rủi ro nhỏ.
- **Suggestion:** Executor pin @v2.33.0 khi go get — không bắt buộc, không chặn.

### I2 — last_fallback_at full-scan audit_logs (W3 round 1, demoted)

- audit_logs.action không có index — GET /api/rag-config có thể slow khi audit lớn.
- Plan 04-03 Task 1 step 3 đã dùng auditRepo.List(... LIMIT 1) — Postgres scan reverse theo timestamp index có sẵn. Acceptable cho M1.
- **Suggestion:** Defer index action sang milestone hardening — đã ghi nhận ở CONTEXT Rủi ro 3.

---

## Trả lời 10 câu hỏi check (Round 2)

| # | Câu hỏi | Đáp |
|---|---------|-----|
| 1 | 5/5 REQ-ID covered (CFG-01..05)? | YES |
| 2 | Wave dependency đúng + nội dung Plan 03 đồng bộ frontmatter? | YES (B1 cleared) |
| 3 | pipeline.go single-writer ở Plan 02? | YES (B2 cleared) |
| 4 | Cooldown test < 200ms wall-clock? | YES (B3 cleared — 100ms + sleep 120ms) |
| 5 | requestid.From(ctx) thay raw ctx.Value? | YES (W1 fixed) |
| 6 | settingsRepo handling rõ (a/b decision)? | YES (W4 fixed — executor verify + decide + SUMMARY) |
| 7 | JWT thật ở admin endpoint test? | YES (W5 locked — loginAdmin helper) |
| 8 | Verify command có -race? | YES (W6 fixed — toàn bộ task + verify cuối) |
| 9 | Audit JSONB schema rõ? | YES — 7+ field |
| 10 | Plans honor CONTEXT.md decisions? | YES |

---

## Recommendation

**Verdict: PASS Round 2.**

Tất cả 3 blocker (B1, B2, B3) Round 1 đã clear:
- B1: Plan 04-03 không còn meta-discussion mâu thuẫn frontmatter wave.
- B2: pipeline.go single-writer Plan 02; Plan 03 chỉ touch router.go + main.go + docling.go.
- B3: Cooldown test 100ms + sleep 120ms (deterministic, < 200ms wall-clock).

4 warning critical (W1, W4, W5, W6) đã fix với hướng dẫn rõ ràng cho executor.

2 info carry-over (miniredis pin, audit index) là suggestions không chặn, defer hardening.

**Có thể chạy /gsd-execute-phase 4 ngay.** Wave order:
- Wave 1: Plan 04-01 (foundation: dep + circuit.go + health.go + config + .env).
- Wave 2: Plan 04-02 (pipeline branch auto + main.go wire circuit/audit/OCR).
- Wave 3: Plan 04-03 (router admin endpoint + docling.go OCR multipart + main.go pass router param).
- Wave 4: Plan 04-04 (TDD: pipeline_circuit_test + health_test + rag_config_test với JWT thật + -race).

Smoke end-to-end Docker thật để dành cho /gsd-verify-work 4 sau khi execute xong.
