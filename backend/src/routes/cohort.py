from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import cohort_controller
from src.middlewares.rbac import require_permission
from src.models.user import User
from src.schemas.cohort import MatrixOut, RebuildJobOut, RebuildRequest

router = APIRouter(tags=["cohorts"])


@router.get("/matrix", response_model=MatrixOut)
def matrix(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("matrix:read")),
) -> dict:
    return cohort_controller.matrix(db)


@router.get("/cohorts")
def list_cohorts(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("cohorts:read")),
) -> dict:
    return cohort_controller.list_cohorts(db)


@router.post("/cohorts/rebuild", response_model=RebuildJobOut)
def rebuild(
    payload: RebuildRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("matrix:rebuild")),
) -> dict:
    return cohort_controller.rebuild(db, user, payload, request)


@router.get("/cohorts/rebuild/{job_id}", response_model=RebuildJobOut)
def rebuild_status(
    job_id: str,
    user: User = Depends(require_permission("matrix:read")),
) -> dict:
    return cohort_controller.rebuild_status(job_id)


@router.get("/cohorts/{month}")
def cohort_detail(
    month: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("cohorts:read")),
) -> dict:
    return cohort_controller.detail(db, month)
