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
