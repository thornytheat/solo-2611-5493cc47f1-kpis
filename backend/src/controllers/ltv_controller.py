"""LTV 测算：运行、列表、详情、发布、敏感性。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import ReportStatus
from src.constants.templates import ACTION_LTV_PUBLISH, ACTION_LTV_RUN
from src.models.ltv_report import LtvReport
from src.models.user import User
from src.services import audit_service, ltv_service
from src.utils.errors import AppError, not_found


def _serialize(report: LtvReport) -> dict:
    return {
        "id": str(report.id),
        "name": report.name,
        "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else "",
        "published_at": report.published_at.isoformat() if report.published_at else None,
        "params": report.params or {},
        "results": report.results or {},
    }


def _summary(report: LtvReport) -> dict:
    results = report.results or {}
    fit = results.get("fit") or {}
    return {
        "id": str(report.id),
        "name": report.name,
        "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else "",
        "published_at": report.published_at.isoformat() if report.published_at else None,
        "ltv_hist": results.get("ltv_hist"),
        "ltv_pred12": results.get("ltv_pred12"),
        "lam": fit.get("lambda"),
        "r2": fit.get("r2"),
    }


def list_reports(db: Session, user: User) -> dict:
    rows = db.execute(select(LtvReport).order_by(LtvReport.created_at.desc())).scalars().all()
    if user.role not in ("admin", "analyst"):
        rows = [r for r in rows if r.status == ReportStatus.PUBLISHED.value]
    return {"total": len(rows), "items": [_summary(r) for r in rows]}


def get_report(db: Session, report_id, user: User) -> dict:
    report = db.get(LtvReport, report_id)
    if report is None:
        raise AppError(codes.REPORT_NOT_FOUND)
    if user.role == "viewer" and report.status != ReportStatus.PUBLISHED.value:
        raise AppError(codes.REPORT_NOT_PUBLISHED)
    return _serialize(report)


def run(db: Session, payload, user: User, request: Request) -> dict:
    report = ltv_service.create_report(db, payload.model_dump(), user)
    audit_service.record(
        db, ACTION_LTV_RUN, user=user, entity="ltv_report", entity_id=str(report.id),
        detail=(
            f"lambda={(report.results.get('fit') or {}).get('lambda')} "
            f"ltv12={report.results.get('ltv_pred12')}"
        ),
        request=request,
    )
    db.commit()
    db.refresh(report)
    return _serialize(report)


def publish(db: Session, report_id, user: User, request: Request) -> dict:
    report = ltv_service.publish_report(db, report_id, user)
    audit_service.record(
        db, ACTION_LTV_PUBLISH, user=user, entity="ltv_report", entity_id=str(report.id),
        detail=f"name={report.name}", request=request,
    )
    db.commit()
    db.refresh(report)
    return _serialize(report)


def sensitivity(db: Session, report_id, user: User, delta_lambda: float = 0.03) -> dict:
    report = db.get(LtvReport, report_id)
    if report is None:
        raise AppError(codes.REPORT_NOT_FOUND)
    return ltv_service.sensitivity(report.results or {}, delta_lambda=delta_lambda)
