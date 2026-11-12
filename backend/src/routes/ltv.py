from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import ltv_controller
from src.middlewares.rbac import require_permission
from src.middlewares.rate_limit import rate_limit
from src.models.user import User
from src.schemas.ltv import LtvRunRequest, SensitivityOut

router = APIRouter(prefix="/ltv", tags=["ltv"])


@router.get("/reports")
def list_reports(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ltv:read")),
) -> dict:
    return ltv_controller.list_reports(db, user)


@router.post("/reports")
def run_report(
    payload: LtvRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ltv:run")),
    _: None = rate_limit("ltv"),
) -> dict:
    return ltv_controller.run(db, payload, user, request)


@router.get("/reports/{report_id}")
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ltv:read")),
) -> dict:
    return ltv_controller.get_report(db, report_id, user)


@router.post("/reports/{report_id}/publish")
def publish_report(
    report_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ltv:publish")),
) -> dict:
    return ltv_controller.publish(db, report_id, user, request)


@router.post("/reports/{report_id}/recompute")
def recompute_report(
    report_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ltv:recompute")),
    _: None = rate_limit("ltv"),
) -> dict:
    return ltv_controller.recompute(db, report_id, user, request)


@router.get("/reports/{report_id}/sensitivity", response_model=SensitivityOut)
def report_sensitivity(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("ltv:sensitivity")),
    delta: float = Query(default=0.03, ge=0.005, le=0.15),
) -> dict:
    return ltv_controller.sensitivity(db, report_id, user, delta)
