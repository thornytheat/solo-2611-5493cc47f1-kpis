"""LtvReport：一次 LTV 测算（参数 + 结果快照 + 发布状态）。

params 里是口径（观察期/λ 范围/毛利率/CAC 覆盖），results 里是拟合与渠道行，
发布后结果冻结，渠道页与导出都读这一份。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, TimestampMixin, new_uuid, utcnow


class LtvReport(Base, TimestampMixin):
    __tablename__ = "ltv_reports"
    __table_args__ = {"schema": settings.db_schema}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{settings.db_schema}.users.id"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
