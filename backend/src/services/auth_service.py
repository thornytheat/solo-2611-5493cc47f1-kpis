"""登录与用户序列化。"""
from __future__ import annotations

from typing import Any

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.roles import ROLE_LABELS, role_permissions
from src.models.user import User
from src.utils.errors import AppError
from src.utils.jwt import create_access_token, create_refresh_token

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return _pwd.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _pwd.verify(raw, hashed)
    except Exception:
        return False


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email.lower().strip())).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AppError(codes.AUTH_INVALID, "邮箱或密码不正确", f"email={email}")
    return user


def issue_tokens(user: User) -> dict[str, Any]:
    return {
        "token": create_access_token(str(user.id), user.role, user.email),
        "refresh_token": create_refresh_token(str(user.id), user.role, user.email),
        "token_type": "bearer",
        "user": serialize(user),
    }


def serialize(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "channel_scope": user.channel_scope,
        "permissions": role_permissions(user.role),
    }
