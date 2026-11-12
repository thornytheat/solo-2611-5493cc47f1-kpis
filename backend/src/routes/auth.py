from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import auth_controller
from src.middlewares.auth import get_current_user
from src.models.user import User
from src.schemas.auth import LoginRequest, MeOut, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    return auth_controller.login(db, payload, request)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> dict:
    return auth_controller.me(user)


@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return auth_controller.logout(db, user, request)
