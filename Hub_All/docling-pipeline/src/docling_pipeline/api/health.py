"""GET /healthz (liveness) + GET /readyz (readiness — Docling library + models warm).

B5 semantics (chốt trong Plan 06):
- /healthz luôn 200 nếu process còn sống (liveness).
- /readyz 200 khi `_models_ready=True`:
  - Library Docling đã import OK (lifespan B5).
  - Warm dummy fail transient vẫn được coi là ready (sẽ chậm request đầu).
- /readyz 503 chỉ khi `_models_ready=False`:
  - ImportError docling → env hỏng, user phải fix (pip install docling==2.91.0).
"""

from __future__ import annotations

from fastapi import APIRouter, Response

router = APIRouter(tags=["health"])

# Module-level state — set qua set_models_ready() từ FastAPI lifespan (main.py).
# Giá trị mặc định False = chưa chạy lifespan / Docling chưa import OK.
_models_ready: bool = False


def set_models_ready(ready: bool) -> None:
    """Update readiness state — gọi từ lifespan main.py."""
    global _models_ready
    _models_ready = ready


def get_models_ready() -> bool:
    """Đọc readiness state — dùng cho test + introspection."""
    return _models_ready


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness — luôn trả 200 nếu process còn sống."""
    return {"status": "healthy"}


@router.get("/readyz")
def readyz(response: Response) -> dict[str, str]:
    """Readiness — chỉ OK khi Docling library đã import OK (B5)."""
    if not _models_ready:
        response.status_code = 503
        return {
            "status": "not_ready",
            "reason": "docling_library_unavailable",
        }
    return {"status": "ready"}


__all__ = ["router", "set_models_ready", "get_models_ready"]
