"""Cohort：同期群 = 首单月 × 规模 × 渠道构成。

自然键 month（'YYYY-MM'），seed 与重建都以它为幂等键。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, TimestampMixin, new_uuid, utcnow


class Cohort(Base, TimestampMixin):
    __tablename__ = "cohorts"
    __table_args__ = {"schema": settings.db_schema}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    month: Mapped[str] = mapped_column(String(7), unique=True, nullable=False, index=True)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # {"private": {"members": 95, "cac": 38.0}, ...}
    channel_mix: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # 最近一次矩阵重建时间（口径是否过期看它和 cells 的 updated_at）
    rebuilt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
