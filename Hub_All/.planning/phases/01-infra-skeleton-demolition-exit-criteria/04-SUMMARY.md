---
plan: 04
phase: 1
wave: 2
status: complete
executed_at: 2026-05-13
---

# Plan 04 SUMMARY — JWT keypair generation + verify scripts

## Mục tiêu (recap)
Cung cấp script sinh JWT RSA 4096-bit keypair format **PKCS#8** sẵn từ Phase 1 — tránh convert PKCS#1→PKCS#8 ở Phase 3 (AUTH-06 + PITFALLS#P6/R6 mapping). Bake `make keys` + `make keys-verify` vào Makefile để dev workflow nhất quán.

## Tasks completed: 4/4

| # | Action | Output | Acceptance |
|---|--------|--------|------------|
| 01 | Tạo `api/scripts/generate_keys.sh` | `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096` (PKCS#8 native), `chmod 600` private + `chmod 644` public, fail-fast nếu keypair tồn tại | 8/8 PASS |
| 02 | Tạo `api/scripts/verify_keys.sh` | 3 check: header PKCS#8 (`BEGIN PRIVATE KEY`), size 4096-bit, header SPKI public — exit code phân biệt (2/3/4) | 7/7 PASS |
| 03 | Tạo `api/Makefile` | 7 target: install / keys / keys-verify / lint / test / test-cov / clean — `UV ?= uv` override | 8/8 PASS |
| 04 | Append section `## JWT Keys` vào `api/README.md` | Workflow `make keys` + cảnh báo `keys/` gitignored + KHÔNG commit private key + production keypair mount qua volume read-only | 6/6 PASS |

## Verification

### Acceptance criteria (8/8)
- `generate_keys.sh` mode `100755` (exec bit ghi trong git index, cross-platform).
- `verify_keys.sh` mode `100755`.
- `grep -c "BEGIN PRIVATE KEY" verify_keys.sh` = 1 (PKCS#8 header check bake sẵn).
- `grep -c "openssl genpkey" generate_keys.sh` = 1 (PKCS#8 native, KHÔNG `genrsa` vốn sinh PKCS#1).
- `grep -c "rsa_keygen_bits:4096" generate_keys.sh` = 1 (4096-bit pin).
- `grep -c "chmod 600" generate_keys.sh` = 1 (private key permissions).
- `grep -c "^keys:" Makefile` = 1 (target có sẵn).
- `grep -c "JWT Keys" README.md` = 1 (section đã append).

### End-to-end test (Git Bash + openssl available trên Windows)
- Generate: `bash scripts/generate_keys.sh` → exit 0, sinh `keys/private.pem` (3324 bytes, mode 644 trên Windows do filesystem không enforce 600 nhưng git index respect) + `keys/public.pem` (814 bytes).
- Header private: `-----BEGIN PRIVATE KEY-----` (PKCS#8 confirmed, KHÔNG `BEGIN RSA PRIVATE KEY` aka PKCS#1).
- Header public: `-----BEGIN PUBLIC KEY-----` (SPKI confirmed).
- Key size: `openssl rsa -in keys/private.pem -text -noout | grep "Private-Key"` trả `Private-Key: (4096 bit, 2 primes)`.
- Verify: `bash scripts/verify_keys.sh` → exit 0, output cuối `keypair PKCS#8 RSA 4096-bit hợp lệ cho RS256 JWT (PyJWT-ready)`.
- Idempotency: chạy `generate_keys.sh` lần 2 → exit 1 với message `LỖI: keypair đã tồn tại` (chống ghi đè key production).
- Gitignore: `git check-ignore Hub_All/api/keys/private.pem` exit 0 — đã ignore từ Plan 01.

### Files created (4)
- `Hub_All/api/scripts/generate_keys.sh` (mode 755, 37 dòng) — PKCS#8 native via `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096`.
- `Hub_All/api/scripts/verify_keys.sh` (mode 755, 40 dòng) — format check + 4096-bit + SPKI public.
- `Hub_All/api/Makefile` (26 dòng) — 7 target dev workflow.
- `Hub_All/api/README.md` (append section "## JWT Keys", +14 dòng).

## Commits

| SHA | Message |
|-----|---------|
| 6746ad1 (existing) | `feat(phase-01): pkg.response envelope helpers match Go cũ contract` — generate_keys.sh đã được include vào commit này (xem Deviations) |
| 732d17f | `feat(phase-01): script verify_keys.sh check PKCS#8 + 4096-bit (Plan 04 task 02)` |
| 1779282 | `feat(phase-01): Makefile dev tasks cho api Python (Plan 04 task 03)` |
| 6d17e6b | `docs(phase-01): README append section JWT Keys (Plan 04 task 04)` |

## Deviations

1. **Task 01 commit bundling:** `generate_keys.sh` (Task 01) cuối cùng được include vào commit `6746ad1` (Plan 03 task 02 — pkg.response) do tooling interleaving giữa parallel executors (Plan 03 + Plan 04 chạy song song theo Wave 2 design). File content **identical** với spec Plan 04 task 01 — verify qua `git show 6746ad1:Hub_All/api/scripts/generate_keys.sh | diff -` (no diff). End-to-end functionality test PASSED (sinh 4096-bit PKCS#8 + verify exit 0). Atomic commit principle bị nhẹ vi phạm nhưng KHÔNG ảnh hưởng artifact correctness; Task 02-04 commit atomic chuẩn.
2. **Generated `keys/` directory:** Theo execution rule #9, KHÔNG commit thư mục `api/keys/`. Sau end-to-end test (sinh `private.pem` + `public.pem` để verify openssl chain hoạt động), `keys/` ở local working tree được giữ nguyên nhưng đã gitignored (`api/keys/` + `api/keys/*.pem` trong `.gitignore` từ Plan 01) — `git status` clean, `git check-ignore` confirm. Executor deploy time sẽ tự chạy `make keys` để sinh keypair env-specific.

## Notes về Phase 3 (AUTH-06) handover

- Phase 3 chỉ cần: `private_key = pathlib.Path(settings.jwt_private_key_path).read_bytes()` → pass thẳng vào `jwt.encode(payload, private_key, algorithm="RS256")`. PyJWT detect PKCS#8 header tự động, KHÔNG cần `serialization.load_pem_private_key()` wrapper.
- Verify side: `jwt.decode(token, public_key, algorithms=["RS256"])` — public key SPKI `BEGIN PUBLIC KEY` cũng được PyJWT load thẳng.
- Cross-compat với Go-signed token (R6/AUTH-06 carry-over): defer test sang Phase 3. Phase 1 chỉ verify format chuẩn để Phase 3 KHÔNG phải debug format mismatch.

## Self-Check
- ✓ 4/4 tasks completed.
- ✓ 8/8 acceptance criteria PASS.
- ✓ End-to-end gen + verify test PASS (openssl available qua Git Bash trên Windows).
- ✓ Files KHÔNG được sửa ngoài scope Plan 04: STATE.md, ROADMAP.md, backend/, frontend/, docling-pipeline/, app/main.py, config.py, response.py, tests/ — confirmed via `git diff --stat` chỉ thấy 4 file mục tiêu.
- ✓ Commit prefix Vietnamese body + Co-Authored-By.

**Status:** PLAN 04 COMPLETE.
