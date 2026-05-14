"""Integration tests: chunks HNSW vector_cosine_ops + documents.status enum.

Verify ROADMAP Phase 2 success criteria #2 (HNSW vector_cosine_ops) + #4
(documents.status enum bao gom failed_unsupported).

Mitigations:
- R1 (HIGH): pgvector dim 1536 — chong 2000-dim index limit.
- R4 (HIGH): scanned PDF silent fail — CHECK enum bao gom failed_unsupported.
- P17 (MED): HNSW vector_cosine_ops (KHONG vector_l2_ops / vector_ip_ops) —
  Tranh mismatch khi embed bang OpenAI/Gemini (normalize cosine).

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
def test_chunks_vector_hnsw_uses_cosine_ops(
    postgres_container: PostgresContainer,
    alembic_cfg: Config,
) -> None:
    """Index ix_chunks_vector_hnsw PHAI dung vector_cosine_ops (P17 + R1).

    pg_indexes.indexdef tra ve full DDL string sau khi parse — verify
    `USING hnsw` + `vector_cosine_ops` literal trong text.
    """
    command.upgrade(alembic_cfg, "head")

    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    eng = create_engine(sync_url)
    with eng.connect() as conn:
        row = conn.execute(text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND indexname='ix_chunks_vector_hnsw'"
        )).first()
    eng.dispose()

    assert row is not None, "Index ix_chunks_vector_hnsw KHONG ton tai"
    indexdef = row[0]
    assert "USING hnsw" in indexdef, f"Index khong dung HNSW: {indexdef}"
    assert "vector_cosine_ops" in indexdef, (
        f"P17 violation: index KHONG dung vector_cosine_ops: {indexdef}"
    )


@pytest.mark.critical
@pytest.mark.integration
def test_chunks_vector_column_is_1536_dim(
    postgres_container: PostgresContainer,
    alembic_cfg: Config,
) -> None:
    """chunks.vector PHAI la vector(1536) (R1 pin dim).

    format_type(atttypid, atttypmod) decode kiem `vector(N)` tu pg_attribute —
    KHONG dung information_schema.columns vi nguoi nay tra ve `USER-DEFINED`.
    """
    command.upgrade(alembic_cfg, "head")

    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    eng = create_engine(sync_url)
    with eng.connect() as conn:
        row = conn.execute(text(
            "SELECT format_type(atttypid, atttypmod) "
            "FROM pg_attribute "
            "WHERE attrelid = 'public.chunks'::regclass "
            "AND attname = 'vector'"
        )).first()
    eng.dispose()

    assert row is not None, "Column chunks.vector KHONG ton tai"
    type_str = row[0]
    assert "vector(1536)" in type_str, (
        f"R1 violation: type khong phai vector(1536): {type_str}"
    )


@pytest.mark.critical
@pytest.mark.integration
def test_documents_status_enum_includes_failed_unsupported(
    postgres_container: PostgresContainer,
    alembic_cfg: Config,
) -> None:
    """CHECK constraint tren documents.status PHAI bao gom 'failed_unsupported' (R4).

    pg_get_constraintdef(oid) sinh constraint expression dang
    `CHECK ((status = ANY (ARRAY['pending'::text, ...])))`. Verify ca 5 status
    value cho R4 mitigation hard guarantee.

    NOTE (deviation Rule 1): Query bang conrelid='public.documents'::regclass +
    contype='c' thay vi conname='ck_documents_status_enum'. Ly do:
    NAMING_CONVENTION 'ck': 'ck_%(table_name)s_%(constraint_name)s' trong
    Plan 02-01 ap dung len explicit name 'ck_documents_status_enum' Plan 02-04
    -> double-prefix thanh 'ck_documents_ck_documents_status_enum'. Bug nay
    cu the documented trong SUMMARY 02-05 Deferred Issues — fix tai Plan 03-XX
    bang cach rename explicit name thanh 'status_enum' (de naming convention
    tu bac 'ck_documents_' prefix). Test nay verify SPEC R4 (CHECK exist +
    co failed_unsupported), KHONG verify constraint name pattern.
    """
    command.upgrade(alembic_cfg, "head")

    sync_url = postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    eng = create_engine(sync_url)
    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT conname, pg_get_constraintdef(oid) "
            "FROM pg_constraint "
            "WHERE conrelid = 'public.documents'::regclass "
            "AND contype = 'c'"
        )).all()
    eng.dispose()

    assert len(rows) > 0, "Khong tim thay CHECK constraint nao tren bang documents"

    # Tim CHECK constraint chua 'status' va 'failed_unsupported' — match bang content
    matching_check = None
    for conname, condef in rows:
        if "status" in condef and "failed_unsupported" in condef:
            matching_check = (conname, condef)
            break

    assert matching_check is not None, (
        f"R4 violation: KHONG co CHECK constraint tren documents.status chua 'failed_unsupported'. "
        f"Cac CHECK constraints tim thay: {[(c, d) for c, d in rows]}"
    )
    conname, constraint_def = matching_check
    # Bonus: verify ca 5 status values
    for status_val in ("pending", "processing", "completed", "failed", "failed_unsupported"):
        assert status_val in constraint_def, (
            f"Status enum thieu '{status_val}' trong constraint '{conname}': {constraint_def}"
        )
