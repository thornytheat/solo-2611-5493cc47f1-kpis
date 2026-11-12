"""算法 2：LTV 与回本周期测算（数据库加载 + `ltv_core` 纯函数）。

口径（README「算法口径」与前端口径提示同源）：
- ARPU₀   = 各群 M0 营收 / 各群规模（全渠道加权）
- 拟合     R_m = a·exp(-λm)，对有效（非右删失）格子做加权最小二乘，权重 = 群规模
- 历史 LTV = 观察期内群累计营收 / 群规模，跨群按会员数加权
- 预测 12 月 LTV = ARPU₀ × Σ_{m=0..11} a·exp(-λm)
- 回本周期 = CAC / 月均毛利贡献，月均毛利贡献 = 观察期人均月营收 × 毛利率
- 群或「群×渠道」样本 <30 标 low_sample，不进入渠道排行

版本与复核（与数据版本联动）：
- 每份报告快照化保存 source_data_seq；源数据更新后旧报告判定 stale，但结果永不被覆盖；
- 重算 = 同血缘（lineage_id）下 version_no+1 的新报告，旧版本及其导出仍可查看；
- 发布新版本时同血缘旧 published 转 superseded，渠道页与导出口径随之一起切换；
- 已过期（stale）报告不允许发布，必须先重算，避免把旧口径冻结成新基线。

数值逻辑全部在 `src/services/ltv_core.py`（无 Session 依赖，可用 unittest 直接测）。
"""
from __future__ import annotations

import uuid
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
from src.services import version_service
from src.services.ltv_core import CoreError, LtvParams, compute_ltv, sensitivity
from src.services.review_core import derive_review_state, ensure_publishable, next_version_no
from src.utils.errors import AppError


def _load(db: Session) -> list[Cohort]:
    cohorts = db.execute(select(Cohort).order_by(Cohort.month)).scalars().all()
    if not cohorts:
        raise AppError(codes.MATRIX_EMPTY)
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
    version = version_service.current_version(db)
    if version is None:
        raise AppError(codes.MATRIX_EMPTY, "还没有数据版本，请先导入订单或重建矩阵")
    cohorts = _load(db)
    cells = db.execute(
        select(RetentionCell).where(RetentionCell.version_id == version.id)
    ).scalars().all()
    if not cells:
        raise AppError(codes.MATRIX_EMPTY, "留存矩阵还没有数据，请先重建矩阵")

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
        results = compute_ltv(cohort_inputs, cell_inputs, snapshot, params)
    except CoreError as exc:
        raise AppError(exc.code, exc.message, exc.detail) from exc
    results["data_version_seq"] = version.seq
    results["data_version_id"] = str(version.id)
    return results


# --------------------------------------------------------------- 血缘与复核状态


def _latest_in_lineage(db: Session, lineage_id) -> LtvReport | None:
    return db.execute(
        select(LtvReport)
        .where(LtvReport.lineage_id == lineage_id)
        .order_by(LtvReport.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()


def _find_lineage(db: Session, name: str) -> LtvReport | None:
    """按名称定位血缘：同名报告视为一条复核链（重算的天然入口）。"""
    return db.execute(
        select(LtvReport)
        .where(LtvReport.name == name)
        .order_by(LtvReport.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()


def review_state(report: LtvReport, current_data_seq: int) -> str:
    """复核状态：发布进度（draft/published/superseded）× 数据新旧（stale 前缀）。"""
    return derive_review_state(report.status, report.source_data_seq, current_data_seq)


def _stale_reason(report: LtvReport, current_data_seq: int) -> str:
    """过期提示文案（控制器/日志可复用）。"""
    gap = int(current_data_seq) - int(report.source_data_seq)
    if gap <= 0:
        return ""
    return (
        f"源数据已更新到 v{current_data_seq}（报告基于 v{report.source_data_seq}），"
        f"本版本结果已过期，请重算生成新版本"
    )


# --------------------------------------------------------------- 创建 / 重算


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
    current_seq = version_service.current_seq(db)
    name = payload.get("name") or f"{results['snapshot_month']} 测算口径"

    previous = _find_lineage(db, name)
    if previous is None:
        lineage_id = uuid.uuid4()
        version_no = 1
        supersedes_id = None
    else:
        lineage_id = previous.lineage_id
        latest = _latest_in_lineage(db, lineage_id)
        version_no = next_version_no(latest.version_no)
        supersedes_id = latest.id

    report = LtvReport(
        name=name,
        status=ReportStatus.DRAFT.value,
        params=results["params"],
        results=results,
        note=payload.get("note") or "",
        created_by=user.id if user is not None else None,
        lineage_id=lineage_id,
        version_no=version_no,
        source_data_seq=current_seq,
        supersedes_id=supersedes_id,
    )
    db.add(report)
    db.flush()
    return report


def recompute_report(db: Session, report_id, user) -> LtvReport:
    """基于同血缘上一版本的口径参数，在当前数据版本上重算为 v(n+1)。

    旧版本一行不改：结果快照、发布状态与当时的导出链接全部保留可追溯。
    """
    previous = db.get(LtvReport, report_id)
    if previous is None:
        raise AppError(codes.REPORT_NOT_FOUND)

    latest = _latest_in_lineage(db, previous.lineage_id)
    current_seq = version_service.current_seq(db)
    if latest is not None and int(latest.source_data_seq) >= current_seq:
        raise AppError(
            codes.REPORT_STALE,
            "最新版本已基于当前数据，无需重算",
            f"latest_v{latest.version_no} seq={latest.source_data_seq} current={current_seq}",
        )

    old_params = previous.params or {}
    payload = {
        "name": previous.name,
        "note": f"重算自 {previous.name} v{previous.version_no}（源 v{previous.source_data_seq}）",
        "observed_months": old_params.get("observed_months"),
        "lambda_min": old_params.get("lambda_min"),
        "lambda_max": old_params.get("lambda_max"),
        "margin_rate": old_params.get("margin_rate"),
        "forecast_months": old_params.get("forecast_months"),
        "channel_cac": old_params.get("channel_cac"),
    }
    return create_report(db, payload, user)


def publish_report(db: Session, report_id, user) -> LtvReport:
    report = db.get(LtvReport, report_id)
    if report is None:
        raise AppError(codes.REPORT_NOT_FOUND)

    current_seq = version_service.current_seq(db)
    # 发布门禁：重复发布 / 已替代 / 数据过期统一在 review_core 判定
    ensure_publishable(report.status, report.source_data_seq, current_seq)

    # 同血缘旧发布版本让位：渠道页 / 导出随后一起切到新 published
    siblings = db.execute(
        select(LtvReport)
        .where(
            LtvReport.lineage_id == report.lineage_id,
            LtvReport.id != report.id,
            LtvReport.status == ReportStatus.PUBLISHED.value,
        )
    ).scalars().all()
    for old in siblings:
        old.status = ReportStatus.SUPERSEDED.value

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
    "recompute_report",
    "review_state",
    "sensitivity",
    "stale_reason",
]


def stale_reason(report: LtvReport, current_data_seq: int) -> str:
    return _stale_reason(report, current_data_seq)
