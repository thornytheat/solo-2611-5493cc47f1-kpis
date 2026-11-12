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
