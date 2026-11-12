"""渠道对比与导出。"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.templates import ACTION_EXPORT
from src.models.user import User
from src.services import audit_service, channel_service, export_service, ltv_service
from src.utils.errors import AppError


def comparison(db: Session, user: User) -> dict:
    return channel_service.comparison(db, user)


def _source_results(db: Session, report_id: str | None) -> tuple[dict, str | None]:
    if report_id:
        from src.models.ltv_report import LtvReport

        report = db.get(LtvReport, report_id)
        if report is None:
            raise AppError(codes.REPORT_NOT_FOUND)
        return report.results or {}, report.name
    report = ltv_service.latest_published(db)
    if report is not None:
        return report.results or {}, report.name
    return ltv_service.compute_results(db), "现场测算"


def export_csv(db: Session, user: User, request: Request, report_id: str | None = None) -> Response:
    results, name = _source_results(db, report_id)
    body, rows = export_service.channels_csv(results)
    audit_service.record(
        db, ACTION_EXPORT, user=user, entity="channels", entity_id=report_id or "latest",
        detail=f"csv rows={rows}", request=request,
    )
    db.commit()
    filename = f"cohortltv-channels-{results.get('snapshot_month', 'snapshot')}.csv"
    return Response(
        content="\ufeff" + body,
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


def export_md(db: Session, user: User, request: Request, report_id: str | None = None) -> Response:
    results, name = _source_results(db, report_id)
    body = export_service.report_md(results, name or "LTV 测算说明")
    audit_service.record(
        db, ACTION_EXPORT, user=user, entity="report", entity_id=report_id or "latest",
        detail=f"md chars={len(body)}", request=request,
    )
    db.commit()
    filename = f"cohortltv-report-{results.get('snapshot_month', 'snapshot')}.md"
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )
