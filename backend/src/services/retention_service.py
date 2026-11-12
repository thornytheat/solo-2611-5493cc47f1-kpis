"""算法 1：同期群留存矩阵重建（订单事实 → 留存格）。

口径见 `retention_core`（纯函数）；本模块只负责读订单聚合、整表重建与落库。

- 按首单月分群（cohorts.month = 会员首个订单月），群规模 N；
- M0 = 首单月（按定义全员活跃）；
- Mn = 该月有 ≥1 单的去重会员数 / N；
- 快照月尚未走到的月序标 right_censored，active=0、retention 为空，不参与拟合；
- 每个格子按渠道拆一份（channel=all 是矩阵汇总）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants import error_codes as codes
from src.constants.enums import COHORT_CHANNELS, CellState
from src.models.cohort import Cohort
from src.models.member_order import MemberOrder
from src.models.retention_cell import RetentionCell
from src.services.retention_core import CohortInput, build_retention_cells
from src.utils.errors import AppError
from src.utils.logger import get_logger

logger = get_logger("cohortltv.retention")


def rebuild_matrix(
    db: Session,
    snapshot_month: str | None = None,
    months: int | None = None,
) -> dict:
    snapshot = snapshot_month or settings.snapshot_month
    months = months or settings.matrix_months
    cohorts = db.execute(select(Cohort).order_by(Cohort.month)).scalars().all()
    if not cohorts:
        raise AppError(codes.MATRIX_EMPTY, "还没有同期群数据，无法重建矩阵")

    channel_aggs = db.execute(
        select(
            MemberOrder.cohort_month,
            MemberOrder.month_index,
            MemberOrder.channel,
            func.count(distinct(MemberOrder.member_code)),
            func.sum(MemberOrder.amount),
            func.count(),
        ).group_by(MemberOrder.cohort_month, MemberOrder.month_index, MemberOrder.channel)
    ).all()

    member_aggs = db.execute(
        select(
            MemberOrder.cohort_month,
            MemberOrder.channel,
            func.count(distinct(MemberOrder.member_code)),
        ).group_by(MemberOrder.cohort_month, MemberOrder.channel)
    ).all()

    build = build_retention_cells(
        [
            CohortInput(
                key=str(cohort.id),
                month=cohort.month,
                size=int(cohort.size or 0),
                channel_mix=cohort.channel_mix or {},
            )
            for cohort in cohorts
        ],
        channel_aggs,
        member_aggs,
        snapshot,
        months,
        settings.low_sample_threshold,
    )

    # 矩阵是纯派生数据：整表重建（幂等）
    db.execute(delete(RetentionCell))
    now = datetime.now(timezone.utc)
    cohort_ids = {str(cohort.id): cohort.id for cohort in cohorts}
    rows = [
        RetentionCell(
            cohort_id=cohort_ids[row["cohort_key"]],
            month_index=row["month_index"],
            channel=row["channel"],
            active_members=row["active_members"],
            sample_size=row["sample_size"],
            retention_rate=row["retention_rate"],
            revenue=row["revenue"],
            order_count=row["order_count"],
            right_censored=row["right_censored"],
            low_sample=row["low_sample"],
            updated_at=now,
        )
        for row in build.rows
    ]

    db.bulk_save_objects(rows)
    db.flush()

    for cohort in cohorts:
        cohort.rebuilt_at = now
        if cohort.channel_mix:
            mix = dict(cohort.channel_mix)
            for channel in COHORT_CHANNELS:
                entry = mix.get(channel) or {}
                entry["members"] = build.channel_members.get((cohort.month, channel), 0)
                mix[channel] = entry
            cohort.channel_mix = mix

    db.commit()
    summary = {**build.summary, "rebuilt_at": now.isoformat()}
    logger.info("matrix rebuilt %s", summary)
    return summary


def cell_state(cell: RetentionCell) -> str:
    return CellState.RIGHT_CENSORED if cell.right_censored else CellState.OBSERVED
