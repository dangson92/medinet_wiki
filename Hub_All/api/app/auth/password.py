"""Argon2id password hashing — port từ Go `internal/pkg/hash/argon2.go`.

R6 mitigation: cross-compat với Go `golang.org/x/crypto/argon2` để hash do
Go cũ sinh (seed.sql production) verify được bằng Python pwdlib không cần
re-hash.

PARAMS — LẤY TỪ GO SOURCE (KHÔNG từ REQUIREMENTS.md doc):
    memory_cost  = 65536   (Go argonMemory     = 64 * 1024)
    time_cost    = 3       (Go argonIterations = 3)
    parallelism  = 4       (Go argonParallel   = 4)
    salt_len     = 16      (Go argonSaltLen    = 16)
    hash_len     = 32      (Go argonKeyLen     = 32)

⚠ DOC-BUG: REQUIREMENTS.md AUTH-05 + PITFALLS.md P6 ghi `t=1, p=2`. Source code
Go (git tag `m1-go-archived` · `backend/internal/pkg/hash/argon2.go` line 13-19) là single source of truth khi port — Go source đã xoá khỏi working tree 2026-05-14 (TEARDOWN-01 pull-in).
Seed hash production `$argon2id$v=19$m=65536,t=3,p=4$...` confirm Go source
đúng. Sẽ tạo follow-up commit để fix REQUIREMENTS.md + PITFALLS.md sau Plan 03-03
ship.

Hash string format (cùng cả Go + Python):
    $argon2id$v=19$m=65536,t=3,p=4$<salt_b64>$<hash_b64>
"""
from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# Params bake constant — sửa = re-hash toàn bộ user (R6 risk re-emerge).
ARGON2_MEMORY_COST = 65_536  # KB → 64 MB
ARGON2_TIME_COST = 3
ARGON2_PARALLELISM = 4
ARGON2_SALT_LEN = 16
ARGON2_HASH_LEN = 32

_password_hash = PasswordHash(
    (
        Argon2Hasher(
            memory_cost=ARGON2_MEMORY_COST,
            time_cost=ARGON2_TIME_COST,
            parallelism=ARGON2_PARALLELISM,
            salt_len=ARGON2_SALT_LEN,
            hash_len=ARGON2_HASH_LEN,
        ),
    )
)


def hash_password(plaintext: str) -> str:
    """Hash plaintext → string format $argon2id$v=19$m=65536,t=3,p=4$...

    Cùng format Go alexedwards/argon2id → verify được giữa 2 stack.
    """
    return _password_hash.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify plaintext vs hash. Trả False thay vì raise nếu hash format sai.

    pwdlib `verify()` raise `pwdlib.exceptions.UnknownHashError` nếu prefix
    KHÔNG phải Argon2id — wrap catch để KHÔNG leak chi tiết format cho caller
    (Plan 03-04 router chỉ cần True/False).
    """
    try:
        return _password_hash.verify(plaintext, hashed)
    except Exception:  # noqa: BLE001 — wrap mọi parse error thành False
        return False
