"""RBAC：require_role(*roles) / require_permission(action)。越权抛 403 并写审计。"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants import error_codes as codes
from src.constants.roles import role_can
from src.constants.templates import ACTION_FORBIDDEN
from src.middlewares.auth import get_current_user
from src.models.user import User
from src.services import audit_service
from src.utils.errors import AppError


def require_role(*roles: str) -> Callable[..., User]:
    allowed = tuple(roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise AppError(
                codes.FORBIDDEN,
                f"当前角色（{user.role}）无权执行该操作",
                f"role={user.role} allowed={allowed}",
            )
        return user

    return dependency


def require_permission(action: str) -> Callable[..., User]:
    def dependency(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not role_can(user.role, action):
            audit_service.record(
                db,
                ACTION_FORBIDDEN,
                user=user,
                entity="permission",
                entity_id=action,
                detail=f"{request.method} {request.url.path}",
                status_code=403,
                request=request,
            )
            db.commit()
            raise AppError(
                codes.FORBIDDEN,
                f"当前角色（{user.role}）无 {action} 权限",
                f"role={user.role} action={action}",
            )
        return user

    return dependency
