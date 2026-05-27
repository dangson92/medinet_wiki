"""Pydantic schemas cho /api/guides — tài liệu hướng dẫn sử dụng public."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GuideCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(default="", max_length=200_000)


class GuideUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(default="", max_length=200_000)


class GuideResponse(BaseModel):
    id: UUID
    title: str
    content: str
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime


class GuideListItemResponse(BaseModel):
    id: UUID
    title: str
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime
