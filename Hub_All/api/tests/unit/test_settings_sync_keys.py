"""Unit test Phase 6 Plan 06-01 Task 2 — settings_sync.keys module constants + helper.

6 test case (per PLAN <behavior>):
1. SETTINGS_INVALIDATE_CHANNEL == "settings:invalidate" exact match (D-V3-Phase6-C LOCKED).
2. RAG_CONFIG_KEY_PREFIX == "settings:rag_config:" exact match.
3. HUB_REGISTRY_KEY == "settings:hub_registry" exact match (singleton, KHONG per-hub).
4. APIKEY_VERIFY_KEY_PREFIX == "apikey:verify:" exact match.
5. make_apikey_cache_key deterministic + SHA-256 hex prefix 16 char.
6. make_apikey_cache_key KHONG contain plaintext (T-06-04-02 mitigation).

Pattern carry forward: search_cache.py:30-35 (M2 pub/sub channel + key prefix
constants) + sync/keys.py (Phase 4 SQL constants module-level).
"""
from __future__ import annotations

import hashlib


def test_settings_invalidate_channel_constant() -> None:
    """SETTINGS_INVALIDATE_CHANNEL == "settings:invalidate" exact match.

    D-V3-Phase6-C LOCKED: 1 channel duy nhat cho ca 3 category (rag_config /
    hub_registry / apikey). Subscriber pattern `redis.pubsub().subscribe(channel)`.
    """
    from app.settings_sync.keys import SETTINGS_INVALIDATE_CHANNEL

    assert SETTINGS_INVALIDATE_CHANNEL == "settings:invalidate"


def test_rag_config_key_prefix_constant() -> None:
    """RAG_CONFIG_KEY_PREFIX == "settings:rag_config:" exact match.

    SETTINGS-01 — Cache key prefix per-hub rag_config (TTL 60s default).
    Hub con cache key = "settings:rag_config:<hub_name>".
    """
    from app.settings_sync.keys import RAG_CONFIG_KEY_PREFIX

    assert RAG_CONFIG_KEY_PREFIX == "settings:rag_config:"


def test_hub_registry_key_constant_singleton() -> None:
    """HUB_REGISTRY_KEY == "settings:hub_registry" exact match (singleton, KHONG per-hub).

    SETTINGS-04 — hub_registry rare-change global config (TTL 300s); 1 key cho
    all hub con KHONG cần per-hub split (hub con đọc list hub_id + subpath + active).
    """
    from app.settings_sync.keys import HUB_REGISTRY_KEY

    assert HUB_REGISTRY_KEY == "settings:hub_registry"
    # Verify KHONG có dấu colon cuối — singleton key not prefix.
    assert not HUB_REGISTRY_KEY.endswith(":")


def test_apikey_verify_key_prefix_constant() -> None:
    """APIKEY_VERIFY_KEY_PREFIX == "apikey:verify:" exact match.

    SETTINGS-03 — Cache key prefix apikey verify (TTL 60s). Plaintext key
    SHA-256 hash hex prefix 16 char appended (T-06-04-02 mitigation —
    KHONG plaintext trong Redis key).
    """
    from app.settings_sync.keys import APIKEY_VERIFY_KEY_PREFIX

    assert APIKEY_VERIFY_KEY_PREFIX == "apikey:verify:"


def test_make_apikey_cache_key_deterministic_sha256_prefix() -> None:
    """make_apikey_cache_key("mdk_abc123") == "apikey:verify:" + sha256(...).hexdigest()[:16].

    Deterministic + 16 char hex prefix (T-06-04-02 — KHONG plaintext key trong
    Redis key/value). Independent call same input → same output.
    """
    from app.settings_sync.keys import APIKEY_VERIFY_KEY_PREFIX, make_apikey_cache_key

    api_key = "mdk_abc123"
    expected_digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    expected_full = f"{APIKEY_VERIFY_KEY_PREFIX}{expected_digest}"

    result1 = make_apikey_cache_key(api_key)
    result2 = make_apikey_cache_key(api_key)

    assert result1 == expected_full
    assert result1 == result2  # deterministic
    # Verify hex prefix length exactly 16 char (32 hex char = 16 byte; SHA-256
    # full = 64 char, prefix [:16] = 16 char = 64 bit collision space đủ unique).
    digest_part = result1.removeprefix(APIKEY_VERIFY_KEY_PREFIX)
    assert len(digest_part) == 16
    # Verify hex format (only [0-9a-f]).
    assert all(c in "0123456789abcdef" for c in digest_part)


def test_make_apikey_cache_key_does_not_contain_plaintext() -> None:
    """make_apikey_cache_key("plaintext_key") KHONG contain substring "plaintext_key".

    T-06-04-02 Information Disclosure mitigation — apikey hash trong Redis cache
    key, KHONG plaintext leak qua MONITOR / SCAN / RDB dump. Verify substring
    check chống regression future ai đó đổi sang plaintext concatenation.
    """
    from app.settings_sync.keys import make_apikey_cache_key

    plaintext = "plaintext_key_should_not_leak"
    result = make_apikey_cache_key(plaintext)

    assert plaintext not in result
    # Verify KHONG có substring 5+ char common với input (defense in depth).
    assert "plaintext" not in result
    assert "should_not_leak" not in result
