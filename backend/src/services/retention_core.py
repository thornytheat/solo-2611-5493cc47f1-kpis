"""算法 1 的纯函数核心：订单聚合 → 同期群留存格（无 ORM / Session 依赖）。

口径（与 README / 前端「口径提示」同源）：
- 按首单月分群（cohort.month = 会员首个订单月），群规模 N；
- M0 = 首单月（按定义全员活跃）；
- Mn = 该月有 ≥1 单的去重会员数 / N；
- 快照月尚未走到的月序标 right_censored，active=0、retention 为空，不参与拟合；
- 每个格子按渠道拆一份（channel=all 是矩阵汇总）。

本模块只吃普通 dict / tuple，不做任何数据库读写；持久化由 retention_service 负责，
因此算法可以脱离 PostgreSQL 做单元测试。
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from src.constants.enums import COHORT_CHANNELS, Channel
from src.utils.months import observed_months


@dataclass(frozen=True)
class CohortInput:
    """一个同期群的输入事实（来自 cohorts 表）。"""

    key: str
    month: str
    size: int
    channel_mix: Mapping[str, object] = field(default_factory=dict)


@dataclass
class RetentionBuild:
    """重建结果：待落库的格子 + 汇总 + 各渠道真实会员数。"""

    rows: list[dict]
    summary: dict
    channel_members: dict[tuple[str, str], int]


def normalize_channel_aggs(
    rows: Iterable[Sequence],
) -> dict[tuple[str, int, str], tuple[int, float, int]]:
    """(cohort_month, m, channel, active, revenue, orders) → 查找表。

    缺省值统一按 0 处理，与 SQL 聚合的 NULL 语义一致。
    """
    cell_map: dict[tuple[str, int, str], tuple[int, float, int]] = {}
    for row in rows:
        cohort_month, m_idx, channel, active, revenue, order_count = row
        cell_map[(str(cohort_month), int(m_idx), str(channel))] = (
            int(active or 0),
            float(revenue or 0),
            int(order_count or 0),
        )
    return cell_map


def build_retention_cells(
    cohorts: Sequence[CohortInput],
    channel_aggs: Iterable[Sequence],
    member_aggs: Iterable[Sequence],
    snapshot_month: str,
    months: int,
    low_sample_threshold: int = 30,
) -> RetentionBuild:
    """纯函数：把订单聚合与同期群规模展开成「群 × 月序 × 渠道」留存格。

    - 分母：all 行取群规模；渠道行取该「群 × 渠道」的真实会员数（来自订单事实）；
    - 右删失格：active/revenue/order_count 归零，retention_rate 为 None；
    - 低样本：样本数 < low_sample_threshold 标 low_sample（不剔除，只标记）。
    """
    cell_map = normalize_channel_aggs(channel_aggs)
    channel_members: dict[tuple[str, str], int] = {
        (str(row[0]), str(row[1])): int(row[2]) for row in member_aggs
    }

    rows: list[dict] = []
    censored = observed = 0
    low_sample_cells = 0

    for cohort in cohorts:
        obs = observed_months(cohort.month, snapshot_month, months)
        size = int(cohort.size or 0)
        for m in range(months):
            is_censored = m >= obs
            if is_censored:
                censored += 1
            else:
                observed += 1
            for channel in (Channel.ALL.value, *COHORT_CHANNELS):
                if channel == Channel.ALL.value:
                    parts = [
                        cell_map.get((cohort.month, m, ch), (0, 0.0, 0))
                        for ch in COHORT_CHANNELS
                    ]
                    active = sum(p[0] for p in parts)
                    revenue = sum(p[1] for p in parts)
                    order_count = sum(p[2] for p in parts)
                    sample = size
                    low = size < low_sample_threshold
                else:
                    active, revenue, order_count = cell_map.get(
                        (cohort.month, m, channel), (0, 0.0, 0)
                    )
                    sample = channel_members.get((cohort.month, channel), 0)
                    low = sample < low_sample_threshold
                if is_censored:
                    active, revenue, order_count = 0, 0.0, 0
                rate = None
                if not is_censored and sample > 0:
                    rate = round(active / sample, 6)
                if low:
                    low_sample_cells += 1
                rows.append(
                    {
                        "cohort_key": cohort.key,
                        "cohort_month": cohort.month,
                        "month_index": m,
                        "channel": channel,
                        "active_members": int(active),
                        "sample_size": int(sample),
                        "retention_rate": rate,
                        "revenue": round(float(revenue), 2),
                        "order_count": int(order_count),
                        "right_censored": is_censored,
                        "low_sample": low,
                    }
                )

    summary = {
        "snapshot_month": snapshot_month,
        "cohorts": len(cohorts),
        "months": months,
        "cells": len(rows),
        "cells_observed": observed,
        "cells_censored": censored,
        "low_sample_cells": low_sample_cells,
    }
    return RetentionBuild(rows=rows, summary=summary, channel_members=channel_members)
