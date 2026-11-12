"""MemberOrder：会员订单事实（24,000 行，seed 生成，重建矩阵的唯一原料）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, TimestampMixin, new_uuid, utcnow


class MemberOrder(Base, TimestampMixin):
    __tablename__ = "member_orders"
    __table_args__ = (
        Index("ix_member_orders_cohort_month", "cohort_month", "month_index"),
        Index("ix_member_orders_channel", "channel"),
        {"schema": settings.db_schema},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    order_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    member_code: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    cohort_month: Mapped[str] = mapped_column(String(7), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    store_code: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    order_month: Mapped[str] = mapped_column(String(7), nullable=False)
    month_index: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_first_order: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ordered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
