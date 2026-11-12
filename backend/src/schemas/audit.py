"""审计日志 schema。"""
from __future__ import annotations

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    actor_email: str
    role: str
    action: str
    entity: str
    entity_id: str
    detail: str
    status_code: int
    created_at: str


class AuditListOut(BaseModel):
    total: int
    items: list[AuditLogOut]
