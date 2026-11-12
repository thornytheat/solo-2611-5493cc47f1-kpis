"""同期群读取：矩阵、群详情（留存曲线 + 金额分布 + 渠道拆分）。"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants import error_codes as codes
from src.constants.channels import CHANNEL_LABELS, CHANNEL_NOTES, CHANNEL_SHORT
from src.constants.enums import COHORT_CHANNELS, Channel
from src.models.cohort import Cohort
from src.models.member_order import MemberOrder
from src.models.retention_cell import RetentionCell
from src.services import version_service
from src.utils.aggregates import AMOUNT_BUCKETS, bucket_amounts
from src.utils.errors import AppError, not_found
from src.utils.months import observed_months

def _rate_str(rate: float | None) -> str:
    return "—" if rate is None else f"{rate * 100:.1f}%"


def list_cohorts(db: Session) -> list[dict]:
    version = version_service.current_version(db)
    cohorts = db.execute(select(Cohort).order_by(Cohort.month)).scalars().all()
    revenue_rows = db.execute(
        select(
            RetentionCell.cohort_id,
            func.sum(RetentionCell.revenue),
            func.sum(RetentionCell.active_members),
        )
        .where(
            RetentionCell.channel == Channel.ALL.value,
            RetentionCell.version_id == version.id if version else False,
        )
        .group_by(RetentionCell.cohort_id)
    ).all()
    agg = {row[0]: (float(row[1] or 0), int(row[2] or 0)) for row in revenue_rows}
    out = []
    for cohort in cohorts:
        total_rev, active_sum = agg.get(cohort.id, (0.0, 0))
        obs = observed_months(cohort.month, settings.snapshot_month, settings.matrix_months)
        out.append(
            {
                "month": cohort.month,
                "size": cohort.size,
                "observed_months": obs,
                "cumulative_revenue": round(total_rev, 2),
                "arpu": round(total_rev / cohort.size, 2) if cohort.size else 0.0,
                "avg_active_ratio": round(active_sum / cohort.size / max(obs, 1), 4)
                if cohort.size
                else 0.0,
                "low_sample": cohort.size < settings.low_sample_threshold,
                "channel_mix": cohort.channel_mix or {},
            }
        )
    return out


def build_matrix(db: Session) -> dict:
    version = version_service.current_version(db)
    if version is None:
        raise AppError(codes.MATRIX_EMPTY)
    cohorts = db.execute(select(Cohort).order_by(Cohort.month)).scalars().all()
    if not cohorts:
        raise AppError(codes.MATRIX_EMPTY)
    cells = db.execute(
        select(RetentionCell)
        .where(
            RetentionCell.channel == Channel.ALL.value,
            RetentionCell.version_id == version.id,
        )
        .order_by(RetentionCell.month_index)
    ).scalars().all()
    if not cells:
        raise AppError(codes.MATRIX_EMPTY, "留存矩阵还没有数据，请先重建矩阵")

    by_cohort: dict[str, dict[int, RetentionCell]] = defaultdict(dict)
    for cell in cells:
        by_cohort[str(cell.cohort_id)][cell.month_index] = cell

    months = settings.matrix_months
    rows = []
    column_active = [0] * months
    column_base = [0] * months
    censored_total = 0
    observed_total = 0
    revenue_total = 0.0

    for cohort in cohorts:
        obs = observed_months(cohort.month, settings.snapshot_month, months)
        cells_out = []
        for m in range(months):
            cell = by_cohort[str(cohort.id)].get(m)
            censored = cell.right_censored if cell else m >= obs
            active = cell.active_members if cell and not censored else 0
            revenue = float(cell.revenue) if cell and not censored else 0.0
            rate = cell.retention_rate if cell and not censored else None
            if censored:
                censored_total += 1
            else:
                observed_total += 1
                revenue_total += revenue
                column_active[m] += active
                column_base[m] += cohort.size
            cells_out.append(
                {
                    "m": m,
                    "active": active,
                    "rate": float(rate) if rate is not None else None,
                    "rate_label": _rate_str(float(rate) if rate is not None else None),
                    "state": "right_censored" if censored else "observed",
                    "revenue": round(revenue, 2),
                }
            )
        rows.append(
            {
                "month": cohort.month,
                "size": cohort.size,
                "observed_months": obs,
                "low_sample": cohort.size < settings.low_sample_threshold,
                "cells": cells_out,
            }
        )

    columns = [
        {
            "m": m,
            "active": column_active[m],
            "base": column_base[m],
            "rate": round(column_active[m] / column_base[m], 6) if column_base[m] else None,
            "rate_label": _rate_str(
                column_active[m] / column_base[m] if column_base[m] else None
            ),
        }
        for m in range(months)
    ]

    # 低样本按「群×渠道」格统计（矩阵行是汇总格，本身不会 <30）
    low_sample_cells = int(
        db.execute(
            select(func.count())
            .select_from(RetentionCell)
            .where(
                RetentionCell.low_sample.is_(True),
                RetentionCell.right_censored.is_(False),
                RetentionCell.version_id == version.id,
            )
        ).scalar_one()
    )
    order_count = db.execute(
        select(func.count())
        .select_from(MemberOrder)
        .where(MemberOrder.version_id == version.id)
    ).scalar_one()
    member_count = db.execute(
        select(func.count(func.distinct(MemberOrder.member_code)))
        .where(MemberOrder.version_id == version.id)
    ).scalar_one()

    return {
        "snapshot_month": settings.snapshot_month,
        "data_version_seq": version.seq,
        "data_version_id": str(version.id),
        "data_version_label": version.label,
        "months": months,
        "cohorts": rows,
        "columns": columns,
        "stats": {
            "cohorts": len(rows),
            "cells_total": len(rows) * months,
            "cells_observed": observed_total,
            "cells_censored": censored_total,
            "low_sample_cells": low_sample_cells,
            "orders": int(order_count),
            "members": int(member_count),
            "revenue_total": round(revenue_total, 2),
            "cumulative_arpu": round(revenue_total / member_count, 2) if member_count else 0.0,
        },
        "notes": {
            "matrix": "M0 = 首单月（全员活跃）；Mn = 第 n 个月有过订单的会员数 / 群规模。",
            "censor": "灰色斜纹格 = 右删失（快照月尚未走到），不进入 λ 拟合与 LTV 测算。",
            "low_sample": f"样本 <{settings.low_sample_threshold} 的群或群×渠道不进入渠道排行。",
        },
    }


def build_detail(db: Session, month: str) -> dict:
    version = version_service.current_version(db)
    if version is None:
        raise AppError(codes.MATRIX_EMPTY)
    cohort = db.execute(select(Cohort).where(Cohort.month == month)).scalar_one_or_none()
    if cohort is None:
        raise not_found("同期群", month)
    obs = observed_months(cohort.month, settings.snapshot_month, settings.matrix_months)

    cells = db.execute(
        select(RetentionCell)
        .where(
            RetentionCell.cohort_id == cohort.id,
            RetentionCell.version_id == version.id,
        )
        .order_by(RetentionCell.month_index)
    ).scalars().all()
    all_cells = sorted(
        [c for c in cells if c.channel == Channel.ALL.value], key=lambda c: c.month_index
    )

    curve = []
    for cell in all_cells:
        if cell.right_censored:
            continue
        curve.append(
            {
                "m": cell.month_index,
                "active": cell.active_members,
                "rate": float(cell.retention_rate) if cell.retention_rate is not None else 0.0,
                "rate_label": _rate_str(
                    float(cell.retention_rate) if cell.retention_rate is not None else None
                ),
                "revenue": float(cell.revenue),
            }
        )

    # 订单金额分布（该群当前版本全部订单）
    amounts = db.execute(
        select(MemberOrder.amount).where(
            MemberOrder.cohort_month == cohort.month,
            MemberOrder.version_id == version.id,
        )
    ).scalars().all()
    amount_distribution = bucket_amounts(amounts)

    # 渠道拆分：观察期内各渠道贡献与 M1/M3/M6 留存
    channel_rows = []
    mix = cohort.channel_mix or {}
    for channel in COHORT_CHANNELS:
        ch_cells = {c.month_index: c for c in cells if c.channel == channel}
        members = int((mix.get(channel) or {}).get("members", 0))
        revenue = sum(float(c.revenue) for c in ch_cells.values() if not c.right_censored)
        marks = {}
        for m in (1, 3, 6):
            cell = ch_cells.get(m)
            marks[f"m{m}"] = (
                float(cell.retention_rate)
                if cell is not None and not cell.right_censored and cell.retention_rate is not None
                else None
            )
        channel_rows.append(
            {
                "channel": channel,
                "label": CHANNEL_LABELS.get(channel, channel),
                "short": CHANNEL_SHORT.get(channel, channel),
                "note": CHANNEL_NOTES.get(channel, ""),
                "members": members,
                "sample_size": members,
                "low_sample": members < settings.low_sample_threshold,
                "revenue": round(revenue, 2),
                "revenue_per_member": round(revenue / members, 2) if members else 0.0,
                "m1": marks["m1"],
                "m3": marks["m3"],
                "m6": marks["m6"],
            }
        )

    cumulative = sum(float(c.revenue) for c in all_cells if not c.right_censored)
    return {
        "month": cohort.month,
        "size": cohort.size,
        "observed_months": obs,
        "snapshot_month": settings.snapshot_month,
        "data_version_seq": version.seq,
        "low_sample": cohort.size < settings.low_sample_threshold,
        "note": cohort.note,
        "curve": curve,
        "amount_distribution": amount_distribution,
        "channels": channel_rows,
        "summary": {
            "cumulative_revenue": round(cumulative, 2),
            "arpu": round(cumulative / cohort.size, 2) if cohort.size else 0.0,
            "m1": curve[1]["rate"] if len(curve) > 1 else None,
            "m6": curve[6]["rate"] if len(curve) > 6 else None,
            "m12": curve[12]["rate"] if len(curve) > 12 else None,
        },
    }
