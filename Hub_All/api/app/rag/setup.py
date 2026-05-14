"""Cocoindex setup helper — Plan 04-01 (INGEST-01 prerequisite).

Chạy MỘT LẦN sau alembic upgrade head để cocoindex 1.0.3 tự tạo internal state
tables (schema `cocoindex` — P7 mitigation isolate khỏi schema `public` app data).

Sequence (cocoindex 1.0.3 actual API):
    1. Set env vars (COCOINDEX_DATABASE_URL + APP_NAMESPACE + COCOINDEX_DB_SCHEMA)
       để cocoindex.Settings.from_env() đọc khi default_env() khởi tạo.
    2. import app.rag.flow (nếu module tồn tại — Plan 04-02 sẽ tạo) để
       flow decorator register flow vào cocoindex registry tại import time.
    3. cocoindex.start_blocking() — start default environment (đồng bộ).
       Cocoindex Rust core tạo connection pool nội bộ, mở LMDB local,
       initialize global execution scheduler, và apply schema cho mọi
       flow đã register (auto-create internal state tables prefix
       `medinet_prod__*` trong schema `cocoindex`).

Plan 04-01 ship setup helper RỖNG (skip flow import nếu chưa có).
Plan 04-02 sau khi tạo app/rag/flow.py: chạy lại `make cocoindex-setup` để
cocoindex tạo bảng `cocoindex.medinet_prod__medinet_wiki_ingest__*`.

Lý do isolation schema:
- Pitfall P7 — cocoindex internal tables (lineage, fingerprint, memo cache)
  KHÔNG trộn schema `public` để Alembic env.py include_object filter
  (Plan 02-03 line 40-55) loại trừ chính xác.

Lý do APP_NAMESPACE cố định:
- Pitfall P2 / R5 — APP_NAMESPACE đổi giữa env = re-index toàn bộ corpus.
  M2 PIN "medinet_prod" mọi env (xem CONVENTIONS.md section 3).

Deviation note (Rule 1 — Plan 04-01 paste-ready vs actual API):
- Plan 04-01 PASTE-READY code reference `cocoindex.init()` + `cocoindex.setup_flow()`.
  Hai hàm này KHÔNG tồn tại trong cocoindex 1.0.3 đã pin (pyproject.toml line 15).
  Verified `dir(cocoindex)` không liệt kê `init` hay `setup_flow`.
- Cocoindex 1.0.3 API tương đương: `cocoindex.start_blocking()` (sync, đồng bộ
  init default environment + apply registered flow schema). API async tương đương
  là `await cocoindex.start()`. Plan executor (sync CLI script) dùng sync version.
- `cocoindex.Settings.from_env()` đọc env COCOINDEX_DATABASE_URL/APP_NAMESPACE/
  COCOINDEX_DB_SCHEMA + COCOINDEX_LMDB_* — pattern os.environ.setdefault giữ.
- Document Rule 1 deviation đầy đủ trong SUMMARY.md để Plan 04-02 (flow definition)
  biết phải dùng API nào (likely `cocoindex.mount` / `cocoindex.lifespan` decorator
  thay vì `@cocoindex.flow_def`).
"""
from __future__ import annotations

import logging
import os

from app.config import Settings

logger = logging.getLogger(__name__)


def setup_cocoindex(settings: Settings) -> None:
    """Init cocoindex 1.0.3 + apply flow schema.

    Idempotent: chạy nhiều lần OK (cocoindex tự skip nếu schema đã match).

    Raises:
        RuntimeError: cocoindex.start_blocking() fail (Postgres không lên hoặc DSN sai).
    """
    # Cocoindex 1.0.3 đọc env vars qua os.environ tại thời điểm Settings.from_env().
    # Set lại để đảm bảo Settings → env (settings có thể override .env mặc định).
    os.environ.setdefault("COCOINDEX_DATABASE_URL", settings.cocoindex_database_url)
    os.environ.setdefault("APP_NAMESPACE", settings.app_namespace)
    os.environ.setdefault("COCOINDEX_DB_SCHEMA", settings.cocoindex_db_schema)

    import cocoindex

    logger.info(
        "cocoindex_setup_start: namespace=%s schema=%s",
        settings.app_namespace,
        settings.cocoindex_db_schema,
    )

    # 1) Import flow module (Plan 04-02 sẽ tạo app/rag/flow.py).
    #    Decorator chạy ở import time → register flow vào cocoindex registry
    #    TRƯỚC khi start_blocking() apply schema.
    try:
        # Plan 04-02 sẽ tạo app/rag/flow.py; mypy strict báo missing attr cho
        # intentional optional import này — type: ignore inline.
        from app.rag import flow as _flow  # type: ignore[attr-defined]  # noqa: F401

        logger.info("cocoindex_flow_imported: %s", _flow.__name__)
    except ImportError as e:
        logger.warning(
            "cocoindex_flow_skip: flow module chưa tồn tại (Plan 04-02 sẽ tạo) — %s",
            e,
        )

    # 2) start_blocking() = sync init default environment + apply schema cho mọi
    #    flow đã register. Idempotent — chạy lại không tạo trùng bảng.
    #    (Plan PASTE-READY ghi cocoindex.init() + cocoindex.setup_flow() — Rule 1
    #     deviation: API này KHÔNG tồn tại cocoindex 1.0.3, dùng start_blocking().)
    cocoindex.start_blocking()
    logger.info("cocoindex.start_blocking() OK")
