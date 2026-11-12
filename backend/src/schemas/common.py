"""通用响应/错误结构。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: str = ""
    trace_id: str | None = None
    extra: dict[str, Any] | None = None


class PageMeta(BaseModel):
    total: int = 0
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = 0


class HealthOut(BaseModel):
    status: str
    brand: str
    database: bool
    redis: bool
    version: str
    snapshot_month: str
