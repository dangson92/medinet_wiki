"""Sync router — COMPAT STUB cho endpoint Go-era `/api/sync/*` (D6) +
Phase 4 Plan 04-06 admin replay endpoint (SYNC-04 / D-V3-Phase4-C2).

Bối cảnh: frontend React 19 (D6 — KHÔNG sửa trong M2) vẫn gọi nhóm endpoint
`/api/sync/*` của backend Go cũ (hàng đợi duyệt batch đồng bộ tri thức từ Hub
Dự Án). M2 Full RAG Rewrite KHÔNG port feature này — ROADMAP M2 (10 phase,
38 REQ-ID) không có sync-queue, ingestion M2 = upload document trực tiếp →
cocoindex. Không route `/api/sync/*` → frontend nhận 404 → Dashboard.tsx +
SyncQueue.tsx log lỗi `Failed to fetch`.

Stub này trả envelope hợp lệ với dữ liệu RỖNG (hàng đợi vĩnh viễn trống vì M2
không có nguồn sync) → Dashboard + SyncQueue render trạng thái empty bình
thường, KHÔNG còn 404. Endpoint thao tác (submit/approve/reject) + xem chi
tiết batch trả `404 NOT_FOUND` envelope sạch — không có batch nào để thao tác.

Phase 4 Plan 04-06 (SYNC-04 / D-V3-Phase4-C2) — Append admin endpoint
POST /api/sync/replay cho dead row recovery. M2 COMPAT stub endpoints
(/stats, /batches, ...) giữ NGUYÊN — endpoint mới này central-only theo
mount conditional của `sync_router` ở `main.py` (entire sync_router là
central-only, hub con strip).
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.auth.dependencies import get_current_user, require_role
from app.config import get_settings
from app.db.dsn import _to_asyncpg_dsn  # W3 fix shared module — Plan 04-04 carry forward
from app.models.auth import User
from app.pkg import response as resp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


# ────────────────────────────────────────────────────────────────────
# Phase 4 Plan 04-06 (SYNC-04 / D-V3-Phase4-C2) — Pydantic schema + SQL
# ────────────────────────────────────────────────────────────────────


_HUB_ID_REGEX = re.compile(r"^[a-z][a-z0-9_]{0,15}$")


class SyncReplayRequest(BaseModel):
    """Payload POST /api/sync/replay — Plan 04-06 D-V3-Phase4-C2.

    `hub_id` la hub_name string (KHONG UUID — la key cua Settings.checksum_hub_dsns).
    Validator regex trung voi Settings.hub_name format (Phase 2 FACTOR-04).
    """

    hub_id: str = Field(
        ...,
        description=(
            "Hub name (vd 'yte', 'duoc') — key cua Settings.checksum_hub_dsns. "
            "Format regex ^[a-z][a-z0-9_]{0,15}$ trung Phase 2 FACTOR-04."
        ),
    )
    since: datetime = Field(
        ...,
        description=(
            "ISO datetime — replay dead rows trong sync_outbox WHERE "
            "status='dead' AND created_at >= since."
        ),
    )

    @field_validator("hub_id", mode="after")
    @classmethod
    def _validate_hub_id_format(cls, v: str) -> str:
        """Enforce hub_name regex format (T-04-06-02 mitigation)."""
        if not _HUB_ID_REGEX.fullmatch(v):
            raise ValueError(
                f"hub_id format invalid: {v!r} — phai khop regex "
                "^[a-z][a-z0-9_]{0,15}$"
            )
        return v


# UPDATE sync_outbox SQL — reset 4 field cua dead row de worker re-pickup.
# WHERE status='dead' AND created_at >= $1 — atomic, idempotent.
REPLAY_SQL = """
    UPDATE sync_outbox
    SET status = 'pending',
        attempt_count = 0,
        last_error = NULL,
        next_retry_at = NULL
    WHERE status = 'dead' AND created_at >= $1
    RETURNING id
"""

_STUB_MSG = (
    "Hàng đợi Sync không khả dụng ở M2 — feature chưa được port từ backend Go cũ."
)


@router.get("/stats")
async def sync_stats(
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """GET /api/sync/stats — compat stub. Hàng đợi luôn trống ở M2.

    Dashboard.tsx gọi endpoint này cho mọi user đã đăng nhập → chỉ yêu cầu
    authenticated (KHÔNG admin-only) để không sinh lỗi 403 ở trang landing.
    """
    _ = user
    return resp.ok(data={"pending_batches": 0, "pending_pages": 0})


@router.get("/batches")
async def list_sync_batches(
    hub_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1),
    per_page: int = Query(20),
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """GET /api/sync/batches — compat stub. Trả list rỗng + meta.total=0."""
    _ = (user, hub_id, status)
    return resp.paginated(items=[], page=page, per_page=per_page, total=0)


@router.get("/batches/{batch_id}")
async def get_sync_batch(
    batch_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """GET /api/sync/batches/{id} — compat stub. Không có batch nào → 404."""
    _ = (user, batch_id)
    return resp.not_found(_STUB_MSG, code="SYNC_NOT_AVAILABLE")


@router.post("/batches")
async def submit_sync_batch(
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """POST /api/sync/batches — compat stub. M2 không nhận batch sync mới."""
    _ = user
    return resp.not_found(_STUB_MSG, code="SYNC_NOT_AVAILABLE")


@router.post("/batches/{batch_id}/pages/{page_id}/approve")
async def approve_sync_page(
    batch_id: str,
    page_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """POST .../approve — compat stub. Không có batch/page nào để duyệt → 404."""
    _ = (user, batch_id, page_id)
    return resp.not_found(_STUB_MSG, code="SYNC_NOT_AVAILABLE")


@router.post("/batches/{batch_id}/pages/{page_id}/reject")
async def reject_sync_page(
    batch_id: str,
    page_id: str,
    user: User = Depends(get_current_user),  # noqa: B008
) -> JSONResponse:
    """POST .../reject — compat stub. Không có batch/page nào để từ chối → 404."""
    _ = (user, batch_id, page_id)
    return resp.not_found(_STUB_MSG, code="SYNC_NOT_AVAILABLE")


# ────────────────────────────────────────────────────────────────────
# Phase 4 Plan 04-06 (SYNC-04 / D-V3-Phase4-C2) — Admin replay endpoint
# ────────────────────────────────────────────────────────────────────


@router.post("/replay")
async def replay_dead_outbox(
    request: Request,
    body: SyncReplayRequest,
    user: User = Depends(require_role("admin")),  # noqa: B008 — Phase 3 SSO-04 carry forward
) -> JSONResponse:
    """POST /api/sync/replay — Plan 04-06 (SYNC-04 / D-V3-Phase4-C2).

    Admin endpoint reset dead rows trong `sync_outbox` hub con qua remote DSN.
    Connect tu central → hub con DB qua Settings.checksum_hub_dsns[hub_id] (
    same DSN dict ma checksum_scheduler dung).

    `sync_router` ENTIRE mount conditional ở `main.py` block central-only
    (FACTOR-02 — Plan 02-01 carry forward). Hub con strip → 404 envelope D6.

    Reset SQL: status='pending', attempt_count=0, last_error=NULL,
    next_retry_at=NULL WHERE status='dead' AND created_at >= $1. Worker
    re-pickup ngay khi tick ke tiep (D-V3-Phase4-A5 poll 5s).

    W8 fix (T-04-06-03 mitigation): INSERT audit_logs row sau khi replay
    (action='sync.replay', target_type='sync_outbox', target_id=hub_id,
    payload={since, rows_replayed}). Audit fail KHONG block replay (defensive
    inner try/except — log warning).

    Response envelope D6: {success, data:{hub_id, replayed_count, since},
    error, meta}.
    """
    settings = get_settings()
    hub_dsns: dict[str, str] = settings.checksum_hub_dsns
    if body.hub_id not in hub_dsns:
        return resp.bad_request(
            message=(
                f"hub_id={body.hub_id!r} KHONG co trong CHECKSUM_HUB_DSNS_JSON. "
                f"Available: {sorted(hub_dsns.keys())}."
            ),
            code="HUB_NOT_REGISTERED",
        )

    dsn = hub_dsns[body.hub_id]
    asyncpg_dsn = _to_asyncpg_dsn(dsn)

    try:
        conn = await asyncpg.connect(asyncpg_dsn)
        try:
            replayed_rows = await conn.fetch(REPLAY_SQL, body.since)
            replayed_count = len(replayed_rows)
        finally:
            await conn.close()
    except Exception as exc:  # noqa: BLE001 — log + envelope 503
        logger.exception(
            "sync_replay_failed: hub=%s err=%s", body.hub_id, exc
        )
        return resp.service_unavailable(
            message=f"Replay failed cho hub {body.hub_id!r}: {exc!s}",
            code="REPLAY_FAILED",
        )

    # W8 fix (T-04-06-03 reinforced) — admin audit trail cho replay action.
    # Audit failure KHONG block replay — inner try/except defensive log only.
    try:
        central_pool = getattr(request.app.state, "db_pool", None)
        if central_pool is not None:
            async with central_pool.acquire() as audit_conn:
                await audit_conn.execute(
                    """
                    INSERT INTO audit_logs
                        (user_id, action, target_type, target_id, payload)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                    """,
                    user.id,
                    "sync.replay",
                    "sync_outbox",
                    body.hub_id,
                    json.dumps(
                        {
                            "since": body.since.isoformat(),
                            "rows_replayed": replayed_count,
                        }
                    ),
                )
    except Exception as audit_exc:  # noqa: BLE001 — audit fail KHONG block replay
        logger.warning("sync_replay_audit_log_failed: %s", audit_exc)

    logger.info(
        "sync_replay_completed: hub=%s replayed_count=%d since=%s",
        body.hub_id,
        replayed_count,
        body.since.isoformat(),
    )
    return resp.ok(
        data={
            "hub_id": body.hub_id,
            "replayed_count": replayed_count,
            "since": body.since.isoformat(),
        }
    )


# Defensive — uuid import alias may be unused if endpoint stays as-is; mark
# explicit reference (used in tests + future expansion to UUID hub_id).
_ = uuid  # noqa: F841 — placeholder for future UUID hub_id expansion
