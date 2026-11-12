"""登录 / 当前用户。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.templates import ACTION_LOGIN, ACTION_LOGIN_FAILED
from src.models.user import User
from src.schemas.auth import LoginRequest
from src.services import audit_service, auth_service
from src.utils.errors import AppError


def login(db: Session, payload: LoginRequest, request: Request) -> dict:
    try:
        user = auth_service.authenticate(db, payload.email, payload.password)
    except AppError:
        audit_service.record(
            db, ACTION_LOGIN_FAILED,
            entity="user", entity_id=payload.email,
            detail="invalid credentials", status_code=401, request=request,
        )
        db.commit()
        raise
    audit_service.record(
        db, ACTION_LOGIN,
        user=user, entity="user", entity_id=str(user.id),
        detail=f"role={user.role}", request=request,
    )
    db.commit()
    return auth_service.issue_tokens(user)


def me(user: User) -> dict:
    return {"user": auth_service.serialize(user)}


def logout(db: Session, user: User, request: Request) -> dict:
    audit_service.record(
        db, "auth.logout", user=user, entity="user", entity_id=str(user.id), request=request
    )
    db.commit()
    return {"ok": True, "code": codes.AUTH_INVALID, "message": "已退出登录"}
