"""算法 2：LTV 与回本周期测算（数据库加载 + `ltv_core` 纯函数）。

口径（README「算法口径」与前端口径提示同源）：
- ARPU₀   = 各群 M0 营收 / 各群规模（全渠道加权）
- 拟合     R_m = a·exp(-λm)，对有效（非右删失）格子做加权最小二乘，权重 = 群规模
- 历史 LTV = 观察期内群累计营收 / 群规模，跨群按会员数加权
- 预测 12 月 LTV = ARPU₀ × Σ_{m=0..11} a·exp(-λm)
- 回本周期 = CAC / 月均毛利贡献，月均毛利贡献 = 观察期人均月营收 × 毛利率
- 群或「群×渠道」样本 <30 标 low_sample，不进入渠道排行

数值逻辑全部在 `src/services/ltv_core.py`（无 Session 依赖，可用 pytest 直接测）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants import error_codes as codes
from src.constants.channels import DEFAULT_CAC
from src.constants.enums import ReportStatus
from src.models.cohort import Cohort
from src.models.ltv_report import LtvReport
from src.models.retention_cell import RetentionCell
from src.services.ltv_core import CoreError, LtvParams, compute_ltv, sensitivity
from src.utils.errors import AppError


def _load(db: Session) -> list[Cohort]:
    cohorts = db.execute(select(Cohort).order_by(Cohort.month)).scalars().all()
    if not cohorts:
        raise AppError(codes.MATRIX_EMPTY)
    cells = db.execute(select(RetentionCell)).scalars().all()
    if not cells:
        raise AppError(codes.MATRIX_EMPTY, "留存矩阵还没有数据，请先重建矩阵")
    return list(cohorts)


def compute_results(
    db: Session,
    *,
    observed_months_override: int | None = None,
    lambda_min: float | None = None,
    lambda_max: float | None = None,
    margin_rate: float | None = None,
    channel_cac: dict[str, float] | None = None,
    snapshot_month: str | None = None,
    forecast_months: int | None = None,
) -> dict:
    snapshot = snapshot_month or settings.snapshot_month
    months = settings.matrix_months
    cohorts = _load(db)
    cells = db.execute(select(RetentionCell)).scalars().all()

    params = LtvParams(
        months=months,
        forecast_months=forecast_months or settings.forecast_months,
        margin_rate=settings.gross_margin_rate if margin_rate is None else float(margin_rate),
        lambda_min=lambda_min if lambda_min is not None else settings.fit_lambda_min,
        lambda_max=lambda_max if lambda_max is not None else settings.fit_lambda_max,
        lambda_step=settings.fit_lambda_step,
        low_sample_threshold=settings.low_sample_threshold,
        default_cac=dict(DEFAULT_CAC),
        channel_cac=channel_cac,
        observed_months_override=observed_months_override,
    )
    cohort_inputs = [
        {
            "key": str(cohort.id),
            "month": cohort.month,
            "size": int(cohort.size),
            "channel_mix": cohort.channel_mix or {},
        }
        for cohort in cohorts
    ]
    cell_inputs = [
        {
            "cohort_key": str(cell.cohort_id),
            "month_index": int(cell.month_index),
            "channel": cell.channel,
            "revenue": float(cell.revenue),
            "right_censored": bool(cell.right_censored),
            "sample_size": int(cell.sample_size),
        }
        for cell in cells
    ]

    try:
        return compute_ltv(cohort_inputs, cell_inputs, snapshot, params)
    except CoreError as exc:
        raise AppError(exc.code, exc.message, exc.detail) from exc


def create_report(db: Session, payload: dict, user) -> LtvReport:
    results = compute_results(
        db,
        observed_months_override=payload.get("observed_months"),
        lambda_min=payload.get("lambda_min"),
        lambda_max=payload.get("lambda_max"),
        margin_rate=payload.get("margin_rate"),
        channel_cac=payload.get("channel_cac"),
        snapshot_month=payload.get("snapshot_month"),
        forecast_months=payload.get("forecast_months"),
    )
    report = LtvReport(
        name=payload.get("name") or f"{results['snapshot_month']} 测算口径",
        status=ReportStatus.DRAFT.value,
        params=results["params"],
        results=results,
        note=payload.get("note") or "",
        created_by=user.id if user is not None else None,
    )
    db.add(report)
    db.flush()
    return report


def publish_report(db: Session, report_id, user) -> LtvReport:
    report = db.get(LtvReport, report_id)
    if report is None:
        raise AppError(codes.REPORT_NOT_FOUND)
    if report.status == ReportStatus.PUBLISHED.value:
        raise AppError(codes.REPORT_ALREADY_PUBLISHED)
    report.status = ReportStatus.PUBLISHED.value
    report.published_at = datetime.now(timezone.utc)
    db.flush()
    return report


def latest_published(db: Session) -> LtvReport | None:
    return db.execute(
        select(LtvReport)
        .where(LtvReport.status == ReportStatus.PUBLISHED.value)
        .order_by(LtvReport.published_at.desc())
    ).scalars().first()


__all__ = [
    "compute_results",
    "create_report",
    "latest_published",
    "publish_report",
    "sensitivity",
]
