"""渠道字典：中文名、默认 CAC、营收系数、会员占比。

CAC 是业务输入（增长组维护），默认值随 seed 落库到 cohort.channel_mix，
LTV 报告可在 params 里覆盖（渠道预算评审时用）。
"""
from __future__ import annotations

from src.constants.enums import Channel

CHANNEL_LABELS: dict[str, str] = {
    Channel.PRIVATE: "私域社群",
    Channel.PAID_FEED: "信息流投放",
    Channel.STORE: "门店自然流",
    Channel.PARTNER: "异业合作",
    Channel.ALL: "全渠道",
}

CHANNEL_SHORT: dict[str, str] = {
    Channel.PRIVATE: "私域",
    Channel.PAID_FEED: "信息流",
    Channel.STORE: "门店",
    Channel.PARTNER: "异业",
    Channel.ALL: "汇总",
}

CHANNEL_NOTES: dict[str, str] = {
    Channel.PRIVATE: "社群券 + 到店核销，客单低、频次高",
    Channel.PAID_FEED: "效果广告落地页开卡，CAC 最高",
    Channel.STORE: "到店扫码开卡，礼盒/咖啡豆占比高",
    Channel.PARTNER: "写字楼/健身房联名卡，量小质优",
}

DEFAULT_CAC: dict[str, float] = {
    Channel.PRIVATE: 38.0,
    Channel.PAID_FEED: 126.0,
    Channel.STORE: 16.0,
    Channel.PARTNER: 58.0,
}

# seed 用的会员占比（四个渠道合计 1.0）
CHANNEL_SHARE: dict[str, float] = {
    Channel.PRIVATE: 0.34,
    Channel.PAID_FEED: 0.30,
    Channel.STORE: 0.22,
    Channel.PARTNER: 0.14,
}

# 单会员营收系数：私域以券为主客单低，门店礼盒客单高
CHANNEL_REVENUE_MULT: dict[str, float] = {
    Channel.PRIVATE: 1.0000,
    Channel.PAID_FEED: 0.9474,
    Channel.STORE: 1.6000,
    Channel.PARTNER: 1.0914,
}
