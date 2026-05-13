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
