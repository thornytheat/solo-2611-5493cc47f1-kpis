"""ImportBatch：一次订单导入批次的全生命周期留痕。

批次状态机：
- validated：dry_run 校验通过，一行未写库；
- applied：  整批校验通过并完成切换（upsert 订单 → 重建矩阵 → 翻转 DataVersion）；
- failed：   校验失败，订单与矩阵均未改动（事务整体回滚）；
- rejected： 批次号重复或晚到旧批次（batch_seq 不大于当前版本），拒绝切换。

同一批次号（外部系统的投递编号）只能成功应用一次；晚到的旧批次即使订单号不同，
也不允许用更小的 seq 盖掉新校正。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, TimestampMixin, new_uuid, utcnow


class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batches"
    __table_args__ = {"schema": settings.db_schema}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    # 外部批次号（投递系统生成），成功应用的唯一性由 service 层 + 唯一索引共同保证
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # 应用成功后分配的批次序号 = 新 DataVersion.seq；未应用为 None
    batch_seq: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    # 投递方声明的「依据版本」：用于晚到旧批次识别（不传则只做重复批次号拦截）
    source_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 失败明细（截断到 IMPORT_MAX_ERROR_DETAIL 条），全量计数看 rejected_count
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    data_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{settings.db_schema}.data_versions.id"),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{settings.db_schema}.users.id"),
        nullable=True,
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
