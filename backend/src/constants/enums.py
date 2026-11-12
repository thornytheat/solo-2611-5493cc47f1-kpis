"""共享枚举（后端）：渠道 / 留存格状态 / 报告状态 / 任务状态 / 衰减模型。

前端同名枚举在 frontend/src/constants/enums.ts，README「枚举出现位置」列出全部落点。
"""
from __future__ import annotations

from enum import StrEnum


class Channel(StrEnum):
    PRIVATE = "private"        # 私域社群
    PAID_FEED = "paid_feed"    # 信息流投放
    STORE = "store"            # 门店自然流
    PARTNER = "partner"        # 异业合作
    ALL = "all"                # 汇总行（仅 RetentionCell 使用）


class CellState(StrEnum):
    OBSERVED = "observed"
    RIGHT_CENSORED = "right_censored"


class ReportStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    # 已发布的旧版本：被同血缘的新版本替代，但结果快照与导出仍可查看
    SUPERSEDED = "superseded"


class ReviewState(StrEnum):
    """测算页复核状态（与发布状态正交：stale 描述数据新旧，review 描述复核进度）。"""

    DRAFT = "draft"                    # 草稿，待复核
    PUBLISHED = "published"            # 已发布，渠道/导出口径冻结在此版本
    SUPERSEDED = "superseded"          # 已被同血缘新版本替代
    STALE_DRAFT = "stale_draft"        # 草稿基于的源数据已更新，需重算
    STALE_PUBLISHED = "stale_published"  # 已发布但源数据已更新，等待新版本接管口径


class ImportBatchStatus(StrEnum):
    VALIDATED = "validated"            # 仅校验通过（dry_run），未落库
    APPLIED = "applied"                # 整批已切换为当前数据版本
    FAILED = "failed"                  # 校验失败，订单与矩阵均未改动
    REJECTED = "rejected"              # 晚到旧批次，被挡在切换之前


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DecayModel(StrEnum):
    EXPONENTIAL = "exponential"   # R_m = a * exp(-lambda * m)


CHANNEL_VALUES: tuple[str, ...] = (
    Channel.PRIVATE, Channel.PAID_FEED, Channel.STORE, Channel.PARTNER, Channel.ALL,
)
COHORT_CHANNELS: tuple[str, ...] = (
    Channel.PRIVATE, Channel.PAID_FEED, Channel.STORE, Channel.PARTNER,
)
