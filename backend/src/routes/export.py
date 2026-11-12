from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from src.config.database import get_db
from src.controllers import channel_controller
from src.middlewares.rbac import require_permission
from src.models.user import User
from sqlalchemy.orm import Session

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/channels.csv")
def export_channels(
    request: Request,
    report_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("channels:export")),
) -> Response:
    return channel_controller.export_csv(db, user, request, report_id)


@router.get("/report.md")
def export_report(
    request: Request,
    report_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("channels:export")),
) -> Response:
    return channel_controller.export_md(db, user, request, report_id)
