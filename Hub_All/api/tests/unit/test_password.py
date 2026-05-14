"""Unit test password hashing — Plan 03-03 (AUTH-05).

Test pure Python, KHÔNG cần Postgres. Cross-compat với hash Go sinh sẽ test
ở `tests/integration/test_argon2_cross_compat.py`.
"""
from __future__ import annotations

from app.auth import (
    ARGON2_HASH_LEN,
    ARGON2_MEMORY_COST,
    ARGON2_PARALLELISM,
    ARGON2_SALT_LEN,
    ARGON2_TIME_COST,
    hash_password,
    verify_password,
)


def test_hash_password_returns_argon2id_prefix() -> None:
    h = hash_password("Admin@123")
    assert h.startswith("$argon2id$v=19$m=65536,t=3,p=4$"), (
        f"prefix sai — không match Go format. Got: {h[:50]}"
    )


def test_round_trip_verify_true() -> None:
    plain = "Mật khẩu Tiếng Việt 1234!@#"
    h = hash_password(plain)
    assert verify_password(plain, h) is True


def test_verify_rejects_wrong_password() -> None:
    h = hash_password("right-password")
    assert verify_password("wrong-password", h) is False


def test_verify_returns_false_on_garbage_hash() -> None:
    # KHÔNG raise — caller (Plan 03-04 router) chỉ cần True/False.
    assert verify_password("anything", "not-a-hash-at-all") is False
    assert verify_password("anything", "") is False
    assert verify_password("anything", "$bcrypt$v=2b$10$...") is False


def test_hash_is_different_each_call() -> None:
    """Salt random — 2 hash của cùng 1 plaintext PHẢI khác nhau."""
    a = hash_password("same-plain")
    b = hash_password("same-plain")
    assert a != b


def test_params_constants_match_go_source() -> None:
    """Guard regression — đổi 1 const = re-hash toàn bộ user → R6 trigger."""
    assert ARGON2_MEMORY_COST == 65_536
    assert ARGON2_TIME_COST == 3
    assert ARGON2_PARALLELISM == 4
    assert ARGON2_SALT_LEN == 16
    assert ARGON2_HASH_LEN == 32
