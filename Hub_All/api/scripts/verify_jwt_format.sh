#!/usr/bin/env bash
# Verify JWT private key format — AUTH-06 mitigation.
#
# PyJWT (cryptography backend) HỖ TRỢ cả PKCS#1 và PKCS#8 nhưng test cross-compat
# với Go (golang-jwt/jwt v5) chuẩn xác hơn khi dùng PKCS#8. Phase 1 đã sinh PKCS#8
# qua `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096` (xem
# scripts/generate_keys.sh). Script này chỉ verify hiện trạng + hướng dẫn convert
# nếu lỡ có dev sinh PKCS#1.
#
# Khác với scripts/verify_keys.sh: script đó check đủ 3 thứ (PKCS#8 + 4096-bit +
# SPKI public). Script này focus AUTH-06: chỉ detect PKCS#1 vs PKCS#8 cho private
# key + in lệnh convert chính xác nếu cần. Plan 03-02 yêu cầu tách riêng để Plan
# 03-04 (router) có thể gọi `bash scripts/verify_jwt_format.sh` ở healthcheck mà
# không cần openssl rsa parse text.
#
# Usage: bash scripts/verify_jwt_format.sh [path/to/private.pem]
# Exit codes: 0 = PKCS#8 OK, 1 = PKCS#1 (cần convert), 2 = format không hỗ trợ.

set -euo pipefail

KEY="${1:-keys/private.pem}"

if [[ ! -f "$KEY" ]]; then
  echo "ERROR: không tìm thấy $KEY. Chạy 'make keys' để sinh."
  exit 2
fi

HEADER=$(head -1 "$KEY")

case "$HEADER" in
  "-----BEGIN PRIVATE KEY-----")
    echo "PKCS#8 OK ($KEY)"
    openssl pkey -in "$KEY" -text -noout 2>&1 | head -3
    exit 0
    ;;
  "-----BEGIN RSA PRIVATE KEY-----")
    cat <<EOF
PKCS#1 phát hiện — cần convert sang PKCS#8 để Go-compat ổn định:

  openssl pkcs8 -topk8 -nocrypt -in $KEY -out ${KEY}.new
  mv ${KEY}.new $KEY

EOF
    exit 1
    ;;
  *)
    echo "ERROR: format không hỗ trợ. Header: $HEADER"
    echo "Hỗ trợ: PKCS#8 ('-----BEGIN PRIVATE KEY-----') hoặc PKCS#1 ('-----BEGIN RSA PRIVATE KEY-----')."
    exit 2
    ;;
esac
