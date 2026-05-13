---
plan: 04
phase: 1
wave: 2
depends_on: [01]
files_modified:
  - Hub_All/api/scripts/generate_keys.sh
  - Hub_All/api/scripts/verify_keys.sh
  - Hub_All/api/Makefile
  - Hub_All/api/README.md
autonomous: true
requirements: [CORE-01]
---

# Plan 04: JWT keypair generation + verify scripts (chuẩn bị cho AUTH-06 Phase 3)

## Objective
Cung cấp script sinh JWT RSA 4096-bit keypair ở format PKCS#8 sẵn từ Phase 1 (tránh convert PKCS#1→PKCS#8 ở Phase 3 — xem AUTH-06 + PITFALLS#P6/AUTH-06 mapping). Bake target `make keys` + `make keys-verify` vào Makefile để dev workflow nhất quán.

## Must-Haves
- `Hub_All/api/scripts/generate_keys.sh` sinh `private.pem` (PKCS#8, RSA 4096-bit) + `public.pem` vào `Hub_All/api/keys/`.
- `Hub_All/api/scripts/verify_keys.sh` xác nhận format PKCS#8 bằng `openssl rsa -in private.pem -text -noout`.
- `Hub_All/api/Makefile` có 4 target: `install`, `keys`, `keys-verify`, `lint`.
- README section "JWT Keys" giải thích workflow generate + cảnh báo `api/keys/` đã gitignored.

## Tasks

<task id="01">
<action>
Tạo `Hub_All/api/scripts/generate_keys.sh` — shell script sinh RSA 4096-bit keypair ở format PKCS#8 (private) + SPKI (public). Sử dụng `openssl genpkey` (PKCS#8 format mặc định, KHÔNG `openssl genrsa` vốn sinh PKCS#1). Output vào `Hub_All/api/keys/private.pem` + `public.pem`. Fail nếu file đã tồn tại (tránh ghi đè key production).

Nội dung paste-ready:

```bash
#!/usr/bin/env bash
# Medinet Wiki — Generate JWT RS256 keypair (PKCS#8 format, 4096-bit).
# Output: api/keys/private.pem (PKCS#8) + api/keys/public.pem (SPKI)
# Format PKCS#8 chuẩn cho PyJWT (Phase 3 AUTH-06) — KHÔNG cần convert.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
KEYS_DIR="${SCRIPT_DIR}/../keys"

mkdir -p "${KEYS_DIR}"

PRIV="${KEYS_DIR}/private.pem"
PUB="${KEYS_DIR}/public.pem"

if [[ -f "${PRIV}" || -f "${PUB}" ]]; then
    echo "[generate_keys] LỖI: keypair đã tồn tại tại ${KEYS_DIR}. Xoá thủ công trước khi sinh mới." >&2
    exit 1
fi

echo "[generate_keys] (1/2) Sinh private key RSA 4096-bit PKCS#8..."
openssl genpkey -algorithm RSA \
    -pkeyopt rsa_keygen_bits:4096 \
    -out "${PRIV}"

chmod 600 "${PRIV}"

echo "[generate_keys] (2/2) Trích public key SPKI..."
openssl rsa -in "${PRIV}" -pubout -out "${PUB}"

chmod 644 "${PUB}"

echo "[generate_keys] DONE."
echo "  Private: ${PRIV} (PKCS#8, 4096-bit, mode 600)"
echo "  Public:  ${PUB} (SPKI, mode 644)"
echo ""
echo "Verify bằng: bash ${SCRIPT_DIR}/verify_keys.sh"
```
</action>
<read_first>
- Hub_All/.planning/research/PITFALLS.md
- Hub_All/.gitignore
</read_first>
<acceptance_criteria>
- File `Hub_All/api/scripts/generate_keys.sh` tồn tại.
- `grep -c 'openssl genpkey -algorithm RSA' Hub_All/api/scripts/generate_keys.sh` ≥ 1.
- `grep -c 'rsa_keygen_bits:4096' Hub_All/api/scripts/generate_keys.sh` ≥ 1 (RSA 4096-bit pin).
- `grep -c 'set -euo pipefail' Hub_All/api/scripts/generate_keys.sh` ≥ 1 (fail-fast).
- `grep -c 'chmod 600' Hub_All/api/scripts/generate_keys.sh` ≥ 1 (private key permissions).
- `grep -c 'openssl rsa -in' Hub_All/api/scripts/generate_keys.sh` ≥ 1 (extract public).
- `head -1 Hub_All/api/scripts/generate_keys.sh` trả `#!/usr/bin/env bash`.
- `bash Hub_All/api/scripts/generate_keys.sh` (lần đầu, chưa có keys) exits 0 và sinh ra 2 file `private.pem` + `public.pem` trong `Hub_All/api/keys/`.
- `bash Hub_All/api/scripts/generate_keys.sh` (lần 2 sau khi đã có keys) exits 1 với message `LỖI: keypair đã tồn tại`.
</acceptance_criteria>
</task>

<task id="02">
<action>
Tạo `Hub_All/api/scripts/verify_keys.sh` — script verify keypair vừa sinh đúng format PKCS#8 (BEGIN PRIVATE KEY header, KHÔNG `BEGIN RSA PRIVATE KEY` — đó là PKCS#1). Đồng thời check key size = 4096 bits.

Nội dung paste-ready:

```bash
#!/usr/bin/env bash
# Medinet Wiki — Verify JWT keypair format PKCS#8 + 4096-bit (R6/AUTH-06 prep).

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
KEYS_DIR="${SCRIPT_DIR}/../keys"
PRIV="${KEYS_DIR}/private.pem"
PUB="${KEYS_DIR}/public.pem"

if [[ ! -f "${PRIV}" ]]; then
    echo "[verify_keys] LỖI: không tìm thấy ${PRIV}. Chạy generate_keys.sh trước." >&2
    exit 1
fi

echo "[verify_keys] (1/3) Check private key header (PKCS#8)..."
HEADER=$(head -1 "${PRIV}")
if [[ "${HEADER}" != "-----BEGIN PRIVATE KEY-----" ]]; then
    echo "[verify_keys] LỖI: private key KHÔNG phải PKCS#8 (header='${HEADER}'). Convert bằng: openssl pkcs8 -topk8 -nocrypt -in ${PRIV} -out ${PRIV}.pkcs8" >&2
    exit 2
fi
echo "  OK — header: ${HEADER}"

echo "[verify_keys] (2/3) Check private key size = 4096-bit..."
BITS=$(openssl rsa -in "${PRIV}" -text -noout 2>/dev/null | grep -E 'Private-Key:|RSA Private-Key:' | grep -oE '[0-9]+ bit' | grep -oE '[0-9]+')
if [[ "${BITS}" != "4096" ]]; then
    echo "[verify_keys] LỖI: key size = ${BITS} bit, expected 4096." >&2
    exit 3
fi
echo "  OK — size: ${BITS}-bit"

echo "[verify_keys] (3/3) Check public key (SPKI)..."
PUB_HEADER=$(head -1 "${PUB}")
if [[ "${PUB_HEADER}" != "-----BEGIN PUBLIC KEY-----" ]]; then
    echo "[verify_keys] LỖI: public key KHÔNG phải SPKI (header='${PUB_HEADER}')." >&2
    exit 4
fi
echo "  OK — header: ${PUB_HEADER}"

echo "[verify_keys] DONE — keypair PKCS#8 RSA 4096-bit hợp lệ cho RS256 JWT (PyJWT-ready)."
```
</action>
<read_first>
- Hub_All/api/scripts/generate_keys.sh
- Hub_All/.planning/research/PITFALLS.md
</read_first>
<acceptance_criteria>
- File `Hub_All/api/scripts/verify_keys.sh` tồn tại.
- `grep -c 'BEGIN PRIVATE KEY' Hub_All/api/scripts/verify_keys.sh` ≥ 1 (PKCS#8 check).
- `grep -c 'BEGIN PUBLIC KEY' Hub_All/api/scripts/verify_keys.sh` ≥ 1 (SPKI check).
- `grep -c '"4096"' Hub_All/api/scripts/verify_keys.sh` ≥ 1 (4096-bit check).
- `grep -c 'set -euo pipefail' Hub_All/api/scripts/verify_keys.sh` ≥ 1.
- `head -1 Hub_All/api/scripts/verify_keys.sh` trả `#!/usr/bin/env bash`.
- Sau khi `generate_keys.sh` đã chạy: `bash Hub_All/api/scripts/verify_keys.sh` exits 0 và output có `DONE — keypair PKCS#8 RSA 4096-bit hợp lệ`.
</acceptance_criteria>
</task>

<task id="03">
<action>
Tạo `Hub_All/api/Makefile` với 4 target tối thiểu. Lệnh tương thích Windows (qua Git Bash / WSL) + Linux/macOS.

Nội dung paste-ready:

```makefile
# Medinet Wiki API — dev tasks
.PHONY: install keys keys-verify lint test test-cov clean

UV ?= uv

install:
	$(UV) sync --extra dev

keys:
	bash scripts/generate_keys.sh

keys-verify:
	bash scripts/verify_keys.sh

lint:
	$(UV) run ruff check app tests
	$(UV) run mypy app

test:
	$(UV) run pytest -v

test-cov:
	$(UV) run pytest --cov=app --cov-report=term-missing

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .venv
```
</action>
<read_first>
- Hub_All/api/pyproject.toml
- Hub_All/api/scripts/generate_keys.sh
- Hub_All/api/scripts/verify_keys.sh
</read_first>
<acceptance_criteria>
- File `Hub_All/api/Makefile` tồn tại.
- `grep -c '^install:' Hub_All/api/Makefile` ≥ 1.
- `grep -c '^keys:' Hub_All/api/Makefile` ≥ 1.
- `grep -c '^keys-verify:' Hub_All/api/Makefile` ≥ 1.
- `grep -c '^lint:' Hub_All/api/Makefile` ≥ 1.
- `grep -c '^test:' Hub_All/api/Makefile` ≥ 1.
- `grep -c '\.PHONY:' Hub_All/api/Makefile` ≥ 1.
- `grep -c 'bash scripts/generate_keys.sh' Hub_All/api/Makefile` ≥ 1.
- `grep -c 'bash scripts/verify_keys.sh' Hub_All/api/Makefile` ≥ 1.
</acceptance_criteria>
</task>

<task id="04">
<action>
Cập nhật `Hub_All/api/README.md` (đã tạo ở Plan 01) — APPEND thêm section `## JWT Keys` vào cuối file. Section này giải thích workflow generate + cảnh báo gitignored. Vietnamese có dấu.

Nội dung append (giữ nguyên 4 section đã có từ Plan 01, thêm section thứ 5):

```markdown

## JWT Keys

JWT RS256 yêu cầu RSA keypair PKCS#8 (PyJWT-compatible). Dùng script đi kèm:

```bash
make keys           # Sinh keypair RSA 4096-bit PKCS#8 vào api/keys/
make keys-verify    # Verify format PKCS#8 + 4096-bit
```

CẢNH BÁO:
- Thư mục `api/keys/` đã được gitignore — KHÔNG bao giờ commit private key.
- Mỗi môi trường (dev/staging/prod) phải có keypair RIÊNG. Production keypair sinh trong build pipeline, mount vào container qua volume read-only `./api/keys:/keys:ro` (xem `docker-compose.yml`).
- Script generate sẽ fail nếu keypair đã tồn tại (chống ghi đè key production). Xoá thủ công nếu cần regenerate.
```
</action>
<read_first>
- Hub_All/api/README.md
- Hub_All/api/scripts/generate_keys.sh
</read_first>
<acceptance_criteria>
- `grep -c '## JWT Keys' Hub_All/api/README.md` ≥ 1.
- `grep -c 'make keys' Hub_All/api/README.md` ≥ 1.
- `grep -c 'make keys-verify' Hub_All/api/README.md` ≥ 1.
- `grep -c 'PKCS#8' Hub_All/api/README.md` ≥ 1.
- `grep -c 'gitignore' Hub_All/api/README.md` ≥ 1.
- `grep -c 'KHÔNG bao giờ commit private key' Hub_All/api/README.md` ≥ 1.
</acceptance_criteria>
</task>

## Verification
- `cd Hub_All/api && make keys` exits 0; file `Hub_All/api/keys/private.pem` + `public.pem` tồn tại.
- `cd Hub_All/api && make keys-verify` exits 0 với output cuối `keypair PKCS#8 RSA 4096-bit hợp lệ`.
- `openssl rsa -in Hub_All/api/keys/private.pem -text -noout 2>&1 | grep -c '4096 bit'` ≥ 1.
- `head -1 Hub_All/api/keys/private.pem` trả `-----BEGIN PRIVATE KEY-----` (KHÔNG `-----BEGIN RSA PRIVATE KEY-----`).
- `head -1 Hub_All/api/keys/public.pem` trả `-----BEGIN PUBLIC KEY-----`.
- `git check-ignore Hub_All/api/keys/private.pem` exits 0 (ignored).
- `cd Hub_All/api && make keys` lần 2 exits 1 (chống ghi đè).
