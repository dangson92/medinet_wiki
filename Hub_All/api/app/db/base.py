"""SQLAlchemy 2.0 declarative base — chung cho toàn bộ ORM model M2.

Naming convention cho constraint deterministic — bắt buộc để Alembic autogenerate
KHÔNG báo drift sai (Pitfalls #P20). Mọi FK/UQ/CK/IX/PK sẽ có tên đoán được:
- ix_<table>_<column>      — index
- uq_<table>_<column>      — unique
- ck_<table>_<rule>        — check
- fk_<table>_<col>_<ref>   — foreign key
- pk_<table>               — primary key

Mọi model M2 PHẢI inherit `Base` từ file này.
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base cho mọi model — gắn MetaData với naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
