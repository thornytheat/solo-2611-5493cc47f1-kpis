"""LtvReport：一次 LTV 测算（参数 + 结果快照 + 发布状态 + 血缘版本）。

params 里是口径（观察期/λ 范围/毛利率/CAC 覆盖），results 里是拟合与渠道行，
创建后结果快照不再被任何后续操作覆盖 —— 源数据更新走「重算生成新版本」。

版本与复核：
- lineage_id 标识同一条报告血缘（同一口径名称下的 v1/v2/...），version_no 从 1 递增；
- source_data_seq 是测算时的源数据版本；当前 DataVersion.seq 更大时报告判定为 stale，
  测算页据此显示复核状态（待重算 / 已过期）；
- 发布新版本时同血缘旧 published 报告转 superseded；渠道页与导出永远只认当前
  published 版本，旧版本与其当时导出仍可通过报告详情回看。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, TimestampMixin, new_uuid, utcnow


class LtvReport(Base, TimestampMixin):
    __tablename__ = "ltv_reports"
    __table_args__ = (
        UniqueConstraint("lineage_id", "version_no", name="uq_ltv_lineage_version"),
        {"schema": settings.db_schema},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{settings.db_schema}.users.id"), nullable=True
    )
    # 报告血缘：同 name 下重算产生的新版本共用一个 lineage_id
    lineage_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=new_uuid, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 测算依据的源数据版本序号（DataVersion.seq）
    source_data_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 同血缘上一版本（追溯链），v1 为 None
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{settings.db_schema}.ltv_reports.id"),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
