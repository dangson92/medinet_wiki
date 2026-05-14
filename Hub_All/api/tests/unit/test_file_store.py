"""Unit test FileStore — Plan 04-02 Task 03 (INGEST-02 prerequisite).

Test 5 case: save UUID + ext / load round-trip / delete idempotent / UTF-8 VN
filename / default base_dir từ settings.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.file_store import FileStore


@pytest.fixture
def fs(tmp_path: Path) -> FileStore:
    """FileStore với base_dir tạm để tránh ghi vào file_store/ thật."""
    return FileStore(base_dir=tmp_path)


def test_file_store_save_uuid_filename(fs: FileStore, tmp_path: Path) -> None:
    """save() → file UUID4.<ext> trong base_dir, original_filename giữ ext."""
    path = fs.save(b"hello world", "Khám bệnh.txt")
    assert path.exists()
    assert path.suffix == ".txt"
    # UUID4 format trong stem.
    stem = path.stem
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        stem,
    ), f"stem KHÔNG phải UUID4: {stem!r}"
    assert path.parent == tmp_path.resolve()


def test_file_store_load_roundtrip(fs: FileStore) -> None:
    """load() round-trip bytes intact (kể cả null byte + UTF-8 VN)."""
    content = b"\x00\x01nh\xc3\xa1n d\xe1\xbb\xa9"  # bytes UTF-8 "nhán dứ"
    path = fs.save(content, "test.bin")
    assert fs.load(path) == content


def test_file_store_delete_idempotent(fs: FileStore) -> None:
    """delete() True lần 1, False lần 2 (idempotent — KHÔNG raise)."""
    path = fs.save(b"x", "x.txt")
    assert path.exists()
    assert fs.delete(path) is True
    assert path.exists() is False
    # Idempotent — gọi lại KHÔNG raise FileNotFoundError.
    assert fs.delete(path) is False


def test_file_store_utf8_vn_filename(fs: FileStore) -> None:
    """Filename UTF-8 VN có dấu — ext .docx preserved (lowercase)."""
    path = fs.save(b"docx content", "Khám bệnh đa khoa.DOCX")
    assert path.suffix == ".docx", f"ext phải lowercase: {path.suffix}"
    assert path.exists()


def test_file_store_no_extension(fs: FileStore) -> None:
    """Filename không có extension → file lưu KHÔNG có suffix."""
    path = fs.save(b"raw", "noext")
    assert path.exists()
    assert path.suffix == ""


def test_file_store_creates_base_dir(tmp_path: Path) -> None:
    """Constructor tạo base_dir nếu chưa tồn tại (mkdir parents=True)."""
    new_dir = tmp_path / "deep" / "nested" / "store"
    assert not new_dir.exists()
    fs = FileStore(base_dir=new_dir)
    assert new_dir.exists()
    # Verify save vẫn work.
    p = fs.save(b"x", "x.txt")
    assert p.exists()
