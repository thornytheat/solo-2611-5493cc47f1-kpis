"""认证 schema。"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    role_label: str
    channel_scope: str | None = None
    permissions: list[str] = []


class TokenOut(BaseModel):
    token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class MeOut(BaseModel):
    user: UserOut
