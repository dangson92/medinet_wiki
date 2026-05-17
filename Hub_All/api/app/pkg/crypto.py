"""AES-GCM encrypt/decrypt helper — API key encryption-at-rest (Plan 05-05, AUX-02).

`key_hash` trong bảng `api_keys` lưu output của `encrypt_secret()` — plaintext API
key được mã hóa AES-256-GCM at-rest (T-05-05-01 Information Disclosure mitigation).
DB compromise → attacker chỉ thấy ciphertext, không đọc được plaintext key.

Verify X-API-Key flow (AUX-02): `ApiKeyService.verify_key()` decrypt `key_hash` rồi
so sánh exact với plaintext input client gửi.

AES_KEY (T-05-05-06):
- Lấy từ env `AES_KEY` qua `get_settings().aes_key` — 32-byte AES-256 key base64.
- Sinh local: `python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`.
- KHÔNG hard-code / commit vào git — `.env` gitignored.

Token format: `base64url(nonce[12B] || ciphertext)`. Nonce random 12-byte mỗi lần
encrypt (AES-GCM yêu cầu nonce unique per key) — prepend vào ciphertext để decrypt
tách ra được.
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

# AES-GCM nonce — 12 byte là kích thước khuyến nghị (NIST SP 800-38D).
_NONCE_LEN = 12


def _load_key() -> bytes:
    """Đọc AES_KEY từ settings, base64url-decode → 32-byte key.

    Raises:
        ValueError: AES_KEY không phải 32-byte sau decode (AES-256 yêu cầu).
    """
    raw = base64.urlsafe_b64decode(get_settings().aes_key)
    if len(raw) != 32:
        raise ValueError(
            "AES_KEY phải là 32-byte base64 "
            "(sinh: base64.urlsafe_b64encode(os.urandom(32)))"
        )
    return raw


def encrypt_secret(plaintext: str) -> str:
    """Mã hóa `plaintext` bằng AES-256-GCM → token base64url.

    Token = base64url(nonce[12B] || ciphertext). Nonce random mỗi lần gọi nên
    cùng plaintext encrypt 2 lần cho 2 token khác nhau.
    """
    aes = AESGCM(_load_key())
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = aes.encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt_secret(token: str) -> str:
    """Giải mã token (output của `encrypt_secret`) → plaintext gốc.

    Raises:
        cryptography.exceptions.InvalidTag: token bị sửa đổi / sai key.
    """
    raw = base64.urlsafe_b64decode(token)
    nonce, ciphertext = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
    return AESGCM(_load_key()).decrypt(nonce, ciphertext, None).decode()
