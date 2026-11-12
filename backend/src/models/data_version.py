"""DataVersion：源数据（订单事实）的版本指针。

每次整批导入校验通过并完成切换时产生一个新版本，seq 单调递增；
留存矩阵、渠道回本与导出口径的「一起切换」都以这个版本为边界：
矩阵重建与版本翻转在同一个事务里提交，失败则整批回滚，外部继续读到上一版。

LTV 报告用 source_data_seq 记录自己基于哪一版数据；当前版本 seq 变大后，
旧报告即判定为 stale（过期），但报告结果快照本身永不被覆盖。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, TimestampMixin, new_uuid, utcnow


class DataVersion(Base, TimestampMixin):
    __tablename__ = "data_versions"
    __table_args__ = {"schema": settings.db_schema}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    # 单调递增的版本序号（1 起），晚到批次判定与报告过期判定都比较它
    seq: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    source_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{settings.db_schema}.import_batches.id"),
        nullable=True,
    )
    snapshot_month: Mapped[str] = mapped_column(String(7), nullable=False)
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    members_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cohorts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cells_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
