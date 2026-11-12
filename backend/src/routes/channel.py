from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import channel_controller
from src.middlewares.rbac import require_permission
from src.models.user import User
from src.schemas.channel import ChannelComparisonOut

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/comparison", response_model=ChannelComparisonOut)
def comparison(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("channels:read")),
) -> dict:
    return channel_controller.comparison(db, user)
