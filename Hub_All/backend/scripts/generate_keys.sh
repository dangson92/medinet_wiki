#!/bin/bash
# ─────────────────────────────────────────────────
# Generate RSA-2048 keypair for JWT RS256 signing
# Usage: bash scripts/generate_keys.sh [output_dir]
# ─────────────────────────────────────────────────

set -euo pipefail

OUTPUT_DIR="${1:-./keys}"

mkdir -p "$OUTPUT_DIR"

PRIVATE_KEY="$OUTPUT_DIR/private.pem"
PUBLIC_KEY="$OUTPUT_DIR/public.pem"

if [ -f "$PRIVATE_KEY" ] && [ -f "$PUBLIC_KEY" ]; then
    echo "⚠ Keys already exist in $OUTPUT_DIR"
    read -p "Overwrite? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Aborted."
        exit 0
    fi
fi

echo "Generating RSA-2048 keypair..."

# Generate private key
openssl genrsa -out "$PRIVATE_KEY" 2048

# Extract public key
openssl rsa -in "$PRIVATE_KEY" -pubout -out "$PUBLIC_KEY"

# Set restrictive permissions
chmod 600 "$PRIVATE_KEY"
chmod 644 "$PUBLIC_KEY"

echo ""
echo "Keys generated successfully:"
echo "  Private key: $PRIVATE_KEY"
echo "  Public key:  $PUBLIC_KEY"
echo ""
echo "IMPORTANT: Never commit private.pem to version control!"
