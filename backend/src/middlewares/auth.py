"""认证依赖：Bearer → request.state.user。"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants import error_codes as codes
from src.models.user import User
from src.utils.errors import AppError
from src.utils.jwt import decode_token


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_bearer(request)
    if not token:
        raise AppError(codes.AUTH_REQUIRED)
    payload = decode_token(token)
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise AppError(codes.AUTH_INVALID)
    request.state.user = user
    request.state.actor_kind = "user"
    return user


def current_user_payload(user: User) -> dict[str, Any]:
    from src.services.auth_service import serialize

    return serialize(user)
