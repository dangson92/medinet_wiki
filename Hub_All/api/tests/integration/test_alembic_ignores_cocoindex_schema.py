"""Integration test: Alembic include_object filter ignore schema 'cocoindex' (P7).

Verify ROADMAP Phase 2 success criteria #5 — Alembic KHONG touch schema cocoindex
(do cocoindex Phase 4 tu quan, KHONG cho Alembic drop/alter).

Mitigations:
- P7 (MED): cocoindex shared schema isolation. env.py include_object filter
  return False neu object.schema == 'cocoindex'.
- P20 (MED): Alembic drift detection — compare_type=True + compare_server_default=True.

Fixture postgres_container + alembic_cfg lay tu tests/integration/conftest.py
qua dependency injection — KHONG redeclare trong file nay.
"""
from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer


@pytest.mark.critical
@pytest.mark.integration
def test_upgrade_does_not_touch_cocoindex_schema(
    postgres_container: PostgresContainer,
    alembic_cfg: Config,
) -> None:
    """Sau upgrade head, schema cocoindex gia lap VAN nguyen (env.py filter P7).

    Test flow:
    1. Manual create schema cocoindex + table cocoindex.fake_state(id, val).
    2. Run alembic upgrade head — KHONG duoc touch schema cocoindex.
    3. Verify cocoindex.fake_state van ton tai + row 'baseline' van nguyen.
    """
    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    eng = create_engine(sync_url)

    # 1) Manual setup schema cocoindex gia lap (mo phong Phase 4 cocoindex auto-create)
    with eng.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS cocoindex"))
        conn.execute(text(
            "CREATE TABLE cocoindex.fake_state (id int primary key, val text)"
        ))
        conn.execute(text(
            "INSERT INTO cocoindex.fake_state (id, val) VALUES (1, 'baseline')"
        ))

    # 2) Chay alembic upgrade head — KHONG duoc touch schema cocoindex
    command.upgrade(alembic_cfg, "head")

    # 3) Verify bang cocoindex.fake_state van nguyen + row van con
    with eng.connect() as conn:
        row = conn.execute(text(
            "SELECT val FROM cocoindex.fake_state WHERE id=1"
        )).first()

        cocoindex_tables = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='cocoindex'"
        )).all()

    assert row is not None, "P7 violation: cocoindex.fake_state bi xoa boi Alembic"
    assert row[0] == "baseline", "P7 violation: cocoindex.fake_state.val bi thay doi"
    table_names = [r[0] for r in cocoindex_tables]
    assert "fake_state" in table_names, f"P7 violation: bang missing: {table_names}"

    eng.dispose()


@pytest.mark.critical
@pytest.mark.integration
def test_alembic_check_no_drift_after_upgrade(
    postgres_container: PostgresContainer,
    alembic_cfg: Config,
) -> None:
    """Sau upgrade head, alembic check KHONG bao drift (P20 baseline correct).

    Defense: neu naming convention sai hoac model khac schema thuc, alembic check
    se raise CommandError. P20 mitigation: convention tu Plan 01 + migration
    paste-ready Plan 04 sinh dung -> check PASS.
    """
    command.upgrade(alembic_cfg, "head")

    # alembic command.check raise CommandError neu co drift; return None neu clean.
    # Wrap try/except de co message ro rang khi fail.
    try:
        command.check(alembic_cfg)
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"P20 drift detected sau upgrade head: {e}")
