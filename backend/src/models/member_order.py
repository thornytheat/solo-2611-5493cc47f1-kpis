"""MemberOrder：会员订单事实（重建矩阵的唯一原料）。

订单按「数据版本」组织：
- order_no 是业务自然键，但同一订单号允许在补录/更正批次里重复出现，
  唯一性约束在 (version_id, order_no) —— 同版本内重复导入不会新增记录；
- 每次整批切换产生新版本，旧版本订单整体保留（可追溯），矩阵与报告只引用当前版本；
- source_batch_id / updated_by_seq 记录每行是被哪个批次写入/最后更正的，
  支撑「晚到旧批次不能盖掉新校正」的审计追查。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, TimestampMixin, new_uuid, utcnow


class MemberOrder(Base, TimestampMixin):
    __tablename__ = "member_orders"
    __table_args__ = (
        UniqueConstraint("version_id", "order_no", name="uq_member_orders_version_order_no"),
        Index("ix_member_orders_cohort_month", "cohort_month", "month_index"),
        Index("ix_member_orders_channel", "channel"),
        Index("ix_member_orders_version", "version_id"),
        {"schema": settings.db_schema},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{settings.db_schema}.data_versions.id"),
        nullable=False,
    )
    order_no: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
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
    # 本行由哪个导入批次写入（seed 基线行可为 None）
    source_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{settings.db_schema}.import_batches.id"),
        nullable=True,
    )
    # 该订单号最后一次被更正时的数据版本序号；未更正为 None
    updated_by_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
