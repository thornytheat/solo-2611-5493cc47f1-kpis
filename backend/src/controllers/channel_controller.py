"""渠道对比与导出。

导出始终绑定具体报告版本：
- 不传 report_id 时取当前 published（渠道页冻结口径）；
- 传旧版本 report_id 时导出该版本当时的结果快照（旧版本及其导出仍可查看）；
- 文件名带报告版本号与源数据版本，保证下载件可追溯、不会和新版本混淆。
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.templates import ACTION_EXPORT
from src.models.ltv_report import LtvReport
from src.models.user import User
from src.services import audit_service, export_service, ltv_service
from src.utils.errors import AppError


def comparison(db: Session, user: User) -> dict:
    from src.services import channel_service

    return channel_service.comparison(db, user)


def _source_results(db: Session, report_id: str | None) -> tuple[dict, str, LtvReport | None]:
    if report_id:
        report = db.get(LtvReport, report_id)
        if report is None:
            raise AppError(codes.REPORT_NOT_FOUND)
        return report.results or {}, report.name, report
    report = ltv_service.latest_published(db)
    if report is not None:
        return report.results or {}, report.name, report
    return ltv_service.compute_results(db), "现场测算", None


def _file_stem(results: dict, report: LtvReport | None) -> str:
    snapshot = results.get("snapshot_month", "snapshot")
    if report is None:
        return f"cohortltv-channels-{snapshot}"
    return f"cohortltv-channels-{snapshot}-v{report.version_no}-data{report.source_data_seq}"


def export_csv(db: Session, user: User, request: Request, report_id: str | None = None) -> Response:
    results, name, report = _source_results(db, report_id)
    body, rows = export_service.channels_csv(results)
    audit_service.record(
        db, ACTION_EXPORT, user=user, entity="channels",
        entity_id=str(report.id) if report else "latest",
        detail=(
            f"csv rows={rows} "
            f"version=v{report.version_no if report else 'live'} "
            f"data=v{report.source_data_seq if report else results.get('data_version_seq')}"
        ),
        request=request,
    )
    db.commit()
    filename = f"{_file_stem(results, report)}.csv"
    return Response(
        content="﻿" + body,
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


def export_md(db: Session, user: User, request: Request, report_id: str | None = None) -> Response:
    results, name, report = _source_results(db, report_id)
    report_meta = (
        {
            "version_label": f"{report.name} v{report.version_no}",
            "source_data_seq": report.source_data_seq,
        }
        if report is not None
        else None
    )
    body = export_service.report_md(
        results, name or "LTV 测算说明",
        published_at=report.published_at.isoformat() if report and report.published_at else None,
        report_meta=report_meta,
    )
    audit_service.record(
        db, ACTION_EXPORT, user=user, entity="report",
        entity_id=str(report.id) if report else "latest",
        detail=(
            f"md chars={len(body)} "
            f"version=v{report.version_no if report else 'live'} "
            f"data=v{report.source_data_seq if report else results.get('data_version_seq')}"
        ),
        request=request,
    )
    db.commit()
    filename = f"{_file_stem(results, report)}.md"
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )
