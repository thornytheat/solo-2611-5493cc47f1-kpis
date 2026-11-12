"""LTV 测算：运行、列表、详情、重算新版本、发布、敏感性。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import ReportStatus
from src.constants.templates import (
    ACTION_LTV_PUBLISH,
    ACTION_LTV_RECOMPUTE,
    ACTION_LTV_RUN,
)
from src.models.ltv_report import LtvReport
from src.models.user import User
from src.services import audit_service, ltv_service, version_service
from src.utils.errors import AppError


def _review(report: LtvReport, current_seq: int) -> dict:
    return {
        "review_state": ltv_service.review_state(report, current_seq),
        "stale": int(report.source_data_seq) < current_seq,
        "source_data_seq": report.source_data_seq,
        "current_data_seq": current_seq,
        "lineage_id": str(report.lineage_id),
        "version_no": report.version_no,
        "supersedes_id": str(report.supersedes_id) if report.supersedes_id else None,
    }


def _serialize(report: LtvReport, current_seq: int) -> dict:
    return {
        "id": str(report.id),
        "name": report.name,
        "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else "",
        "published_at": report.published_at.isoformat() if report.published_at else None,
        "params": report.params or {},
        "results": report.results or {},
        **_review(report, current_seq),
    }


def _summary(report: LtvReport, current_seq: int) -> dict:
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
        **_review(report, current_seq),
    }


def list_reports(db: Session, user: User) -> dict:
    current_seq = version_service.current_seq(db)
    rows = db.execute(
        select(LtvReport).order_by(
            LtvReport.lineage_id, LtvReport.version_no.desc(), LtvReport.created_at.desc()
        )
    ).scalars().all()
    if user.role not in ("admin", "analyst"):
        # 只读角色可见「曾经发布」的版本（published + 被替代的 superseded），草稿不可见
        rows = [
            r
            for r in rows
            if r.status in (ReportStatus.PUBLISHED.value, ReportStatus.SUPERSEDED.value)
        ]
    lineages: dict[str, list] = {}
    for report in rows:
        lineages.setdefault(str(report.lineage_id), []).append(_summary(report, current_seq))
    return {
        "total": len(rows),
        "current_data_seq": current_seq,
        "items": [_summary(r, current_seq) for r in rows],
        "lineages": [
            {"lineage_id": lineage_id, "versions": versions}
            for lineage_id, versions in lineages.items()
        ],
    }


def get_report(db: Session, report_id, user: User) -> dict:
    report = db.get(LtvReport, report_id)
    if report is None:
        raise AppError(codes.REPORT_NOT_FOUND)
    if user.role == "viewer" and report.status not in (
        ReportStatus.PUBLISHED.value,
        ReportStatus.SUPERSEDED.value,
    ):
        raise AppError(codes.REPORT_NOT_PUBLISHED)
    current_seq = version_service.current_seq(db)
    payload = _serialize(report, current_seq)
    # 同血缘版本链（可追溯入口）：只读角色同样只暴露曾发布的版本
    siblings = db.execute(
        select(LtvReport)
        .where(LtvReport.lineage_id == report.lineage_id)
        .order_by(LtvReport.version_no.desc())
    ).scalars().all()
    if user.role == "viewer":
        siblings = [
            item
            for item in siblings
            if item.status in (ReportStatus.PUBLISHED.value, ReportStatus.SUPERSEDED.value)
        ]
    payload["lineage_versions"] = [_summary(item, current_seq) for item in siblings]
    return payload


def run(db: Session, payload, user: User, request: Request) -> dict:
    report = ltv_service.create_report(db, payload.model_dump(), user)
    audit_service.record(
        db, ACTION_LTV_RUN, user=user, entity="ltv_report", entity_id=str(report.id),
        detail=(
            f"v{report.version_no} seq=v{report.source_data_seq} "
            f"lambda={(report.results.get('fit') or {}).get('lambda')} "
            f"ltv12={report.results.get('ltv_pred12')}"
        ),
        request=request,
    )
    db.commit()
    db.refresh(report)
    return _serialize(report, version_service.current_seq(db))


def recompute(db: Session, report_id, user: User, request: Request) -> dict:
    report = ltv_service.recompute_report(db, report_id, user)
    audit_service.record(
        db, ACTION_LTV_RECOMPUTE, user=user, entity="ltv_report", entity_id=str(report.id),
        detail=(
            f"lineage={report.lineage_id} new_v{report.version_no} "
            f"based_on_v{report_id} data=v{report.source_data_seq}"
        ),
        request=request,
    )
    db.commit()
    db.refresh(report)
    return _serialize(report, version_service.current_seq(db))


def publish(db: Session, report_id, user: User, request: Request) -> dict:
    report = ltv_service.publish_report(db, report_id, user)
    audit_service.record(
        db, ACTION_LTV_PUBLISH, user=user, entity="ltv_report", entity_id=str(report.id),
        detail=f"name={report.name} v{report.version_no} data=v{report.source_data_seq}",
        request=request,
    )
    db.commit()
    db.refresh(report)
    return _serialize(report, version_service.current_seq(db))


def sensitivity(db: Session, report_id, user: User, delta_lambda: float = 0.03) -> dict:
    report = db.get(LtvReport, report_id)
    if report is None:
        raise AppError(codes.REPORT_NOT_FOUND)
    return ltv_service.sensitivity(report.results or {}, delta_lambda=delta_lambda)
