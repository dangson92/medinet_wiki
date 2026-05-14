"""File store — local backend mặc định cho Plan 04-02 Task 03.

Save uploaded file vào `settings.file_store_dir / <uuid>.<ext>`.
GDrive backend defer v4.0 (D3 + R6 sidecar — KHÔNG M2 scope).

Plan 04-04 (router /api/documents/upload) gọi FileStore.save() rồi insert
documents row với file_path = path đã lưu. Plan 04-03 cocoindex flow extract
đọc qua FileStore.load(path) hoặc trực tiếp Path.read_bytes (extract_text
nhận Path argument).

Tham chiếu:
- PROJECT.md D3 — Postgres pgvector thay ChromaDB; FileStore local cho M2.
- CLAUDE.md section 3 — file storage convention.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from app.config import get_settings


class FileStore:
    """Local filesystem backend — `<file_store_dir>/<uuid>.<ext>`.

    Constructor mkdir(parents=True, exist_ok=True) base_dir → caller KHÔNG
    cần manually tạo dir trước.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or get_settings().file_store_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes, original_filename: str) -> Path:
        """Lưu content vào file UUID4 mới. Return Path tuyệt đối.

        Args:
            content: bytes nội dung file.
            original_filename: filename gốc (chỉ dùng để lấy extension; tránh
                               path traversal — KHÔNG lưu basename gốc).

        Returns:
            Path đến file đã lưu (UUID4 + ext gốc lowercase) — resolve absolute.
        """
        ext = Path(original_filename).suffix.lower()  # "" nếu không có ext
        uid = uuid.uuid4()
        target = self.base_dir / f"{uid}{ext}"
        target.write_bytes(content)
        return target.resolve()

    def load(self, path: Path) -> bytes:
        """Đọc file bytes — proxy qua Path.read_bytes."""
        return path.read_bytes()

    def delete(self, path: Path) -> bool:
        """Xoá file. Idempotent — return True nếu xoá, False nếu KHÔNG tồn tại.

        KHÔNG raise FileNotFoundError → caller (Plan 04-05 watchdog cleanup +
        Plan 04-06 audit DELETE) gọi delete an toàn nhiều lần.
        """
        if not path.exists():
            return False
        path.unlink()
        return True
