"""AuditLog：审计日志（登录、重建、测算、发布、导出、越权）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.config.settings import settings
from src.models.base import Base, new_uuid, utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": settings.db_schema}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    actor_email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
