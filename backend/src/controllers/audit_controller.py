"""审计日志查询（admin only）。"""
from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog


def list_logs(db: Session, limit: int = 50) -> dict:
    total = db.execute(select(func.count()).select_from(AuditLog)).scalar_one()
    rows = db.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    ).scalars().all()
    return {
        "total": int(total),
        "items": [
            {
                "id": str(row.id),
                "actor_email": row.actor_email,
                "role": row.role,
                "action": row.action,
                "entity": row.entity,
                "entity_id": row.entity_id,
                "detail": row.detail,
                "status_code": row.status_code,
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
            for row in rows
        ],
    }
