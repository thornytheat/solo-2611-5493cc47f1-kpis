"""RetentionCell：留存格（群 × 月序 × 渠道）。

channel='all' 是矩阵用汇总格；四个渠道格给渠道对比用。
右删失 = 快照月尚未走到的月序：active=0，retention 为空，标记 right_censored。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config.settings import settings
from src.models.base import Base, new_uuid, utcnow


class RetentionCell(Base):
    __tablename__ = "retention_cells"
    __table_args__ = (
        UniqueConstraint("cohort_id", "month_index", "channel", name="uq_cell"),
        {"schema": settings.db_schema},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    cohort_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{settings.db_schema}.cohorts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    month_index: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    active_members: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retention_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    right_censored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    low_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    cohort = relationship("Cohort", lazy="joined")
