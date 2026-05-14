"""Integration test Argon2 cross-compat — Plan 03-03 (AUTH-05 / R6).

Mục đích: verify hash do Go `alexedwards/argon2id` sinh trong seed.sql production
được pwdlib Python verify lại bằng `verify_password()` mà KHÔNG cần re-hash
toàn bộ user.

R6 critical proof: 1 hash thật từ seed.sql + 4 hash Python sinh = đủ confirm
pwdlib + argon2-cffi cùng format binary với golang.org/x/crypto/argon2 khi
params (m,t,p,saltLen,keyLen) trùng nhau.

KHÔNG cần testcontainers Postgres — chỉ cần Python pwdlib + hash string literal.
Marker `critical` cho CI gate HARD-03 `pytest -m critical`.
"""
from __future__ import annotations

import pytest

from app.auth import hash_password, verify_password

# Hash thật từ Go seed.sql (admin@medinet.vn) — KHÔNG sửa, KHÔNG paraphrase.
# Plaintext: "Admin@123" (xem comment line 3-7 của seed.sql).
# Sinh bởi: backend/internal/pkg/hash/argon2.go::HashPassword qua Go alexedwards.
GO_SEED_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4"
    "$gpKFndFoG6bcXrx7R60sag"
    "$uhxmJMX03O6QlL0WZS+WdRhCOnGEoIpzUrL2vBzRN+c"
)
GO_SEED_PLAINTEXT = "Admin@123"


@pytest.mark.critical
@pytest.mark.integration
def test_pwdlib_verify_go_seed_admin_hash() -> None:
    """R6 CORE — pwdlib verify Go-generated hash production."""
    assert verify_password(GO_SEED_PLAINTEXT, GO_SEED_HASH) is True, (
        "Cross-compat FAIL — pwdlib KHÔNG verify được hash do Go sinh. "
        "Kiểm tra lại ARGON2_* params trong app/auth/password.py có match "
        "backend/internal/pkg/hash/argon2.go line 13-19 không."
    )


@pytest.mark.critical
@pytest.mark.integration
def test_pwdlib_reject_go_seed_with_wrong_password() -> None:
    """Phản chứng — verify KHÔNG always-True."""
    assert verify_password("WrongPassword!@#", GO_SEED_HASH) is False
    assert verify_password("admin@123", GO_SEED_HASH) is False  # case-sensitive
    assert verify_password("", GO_SEED_HASH) is False


@pytest.mark.critical
@pytest.mark.integration
def test_round_trip_python_to_python_5_samples() -> None:
    """Sinh 5 hash Python với 5 plaintext khác → verify lại cả 5."""
    samples = [
        "Editor@Pass123",
        "Viewer@2026",
        "Mật khẩu có dấu tiếng Việt",
        "P@ssw0rd!#$%^&*()",
        "x" * 64,  # max length stress
    ]
    for plain in samples:
        h = hash_password(plain)
        assert h.startswith("$argon2id$v=19$m=65536,t=3,p=4$"), (
            f"Format prefix wrong for plaintext {plain!r}: {h[:50]}"
        )
        assert verify_password(plain, h) is True, f"Round-trip fail for {plain!r}"
        assert verify_password(plain + "x", h) is False


@pytest.mark.critical
@pytest.mark.integration
def test_python_generated_hash_format_matches_go() -> None:
    """Hash Python sinh PHẢI có prefix byte-identical Go format."""
    h = hash_password("any-plain")
    # Expected: $argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>
    parts = h.split("$")
    assert len(parts) == 6, (
        f"Hash phải có 6 segment (split bằng $), nhận {len(parts)}: {parts}"
    )
    assert parts[0] == ""  # leading $
    assert parts[1] == "argon2id"
    assert parts[2] == "v=19"
    assert parts[3] == "m=65536,t=3,p=4"
    # parts[4] = salt b64, parts[5] = hash b64 — chỉ check không rỗng
    assert len(parts[4]) > 0
    assert len(parts[5]) > 0
