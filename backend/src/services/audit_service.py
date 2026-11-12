"""审计日志写入：controller/service 显式调用，失败不阻断业务。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.models.audit_log import AuditLog
from src.models.user import User
from src.utils.logger import get_logger

logger = get_logger("cohortltv.audit")


def record(
    db: Session,
    action: str,
    *,
    user: User | None = None,
    entity: str = "",
    entity_id: str = "",
    detail: str = "",
    status_code: int = 200,
    request: Any = None,
) -> None:
    try:
        ip = ""
        trace_id = ""
        if request is not None:
            ip = getattr(request.state, "client_ip", "") or ""
            trace_id = getattr(request.state, "trace_id", "") or ""
        db.add(
            AuditLog(
                actor_email=user.email if user else "",
                role=user.role if user else "",
                action=action,
                entity=entity,
                entity_id=str(entity_id)[:80],
                detail=detail[:2000],
                client_ip=ip[:64],
                trace_id=trace_id[:40],
                status_code=status_code,
            )
        )
        db.flush()
    except Exception as exc:  # noqa: BLE001 - 审计失败不能影响主流程
        logger.warning("audit write failed action=%s error=%s", action, exc)
