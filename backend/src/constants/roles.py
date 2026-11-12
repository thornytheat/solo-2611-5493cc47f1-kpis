"""RBAC 角色与能力矩阵（前后端各一份：src/constants/roles.py / frontend/src/constants/roles.ts）"""
from __future__ import annotations

ROLE_ADMIN = "admin"
ROLE_ANALYST = "analyst"
ROLE_VIEWER = "viewer"

ALL_ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER)

PERMISSIONS: dict[str, tuple[str, ...]] = {
    "matrix:read": ALL_ROLES,
    "matrix:rebuild": (ROLE_ADMIN, ROLE_ANALYST),
    "cohorts:read": ALL_ROLES,
    "ltv:read": ALL_ROLES,
    "ltv:run": (ROLE_ADMIN, ROLE_ANALYST),
    "ltv:sensitivity": (ROLE_ADMIN, ROLE_ANALYST),
    "ltv:publish": (ROLE_ADMIN,),
    "channels:read": ALL_ROLES,
    "channels:export": (ROLE_ADMIN, ROLE_ANALYST),
    "audit:read": (ROLE_ADMIN,),
}

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: "增长负责人",
    ROLE_ANALYST: "增长分析师",
    ROLE_VIEWER: "渠道与门店（只读）",
}


def role_can(role: str, action: str) -> bool:
    return role in PERMISSIONS.get(action, ())


def role_permissions(role: str) -> list[str]:
    return [action for action, roles in PERMISSIONS.items() if role in roles]
