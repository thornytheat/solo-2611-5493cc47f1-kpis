"""Demo fixture：沐野咖啡连锁 2025-11 ~ 2026-10 的会员开卡与订单事实。

数据是"设计出来的真实分布"，不是随机噪声：
- 12 个自然月同期群，规模逐月增长（2026-10 是未完整月，样本 210）；
- 人数留存按 BASE_RETENTION 曲线（2025-11 基准群：M1 43.6%、M6 21.4%，
  M6 台阶对应「储值权益到期」这一已知业务事件）；
- ARPU 留存按 exp(-GEN_LAMBDA·m) 衰减并带 ±20% 的月份/群波动，
  后端的加权最小二乘会把它还原成 λ≈0.213、R²≈0.94；
- 订单数由「格内营收 / 订单除数」推出，除数用二分法解到总量恰好 24,000 单，
  保证 SEED_SUMMARY 的 orders=24000 是真实行数。

所有随机量来自 sha256(key) 的确定性哈希，同参数重跑结果完全一致。
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from src.constants.channels import CHANNEL_REVENUE_MULT, CHANNEL_SHARE
from src.constants.enums import COHORT_CHANNELS

COHORT_MONTHS: list[str] = [
    "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04",
    "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10",
]
COHORT_SIZES: list[int] = [280, 314, 352, 394, 441, 494, 553, 620, 694, 777, 871, 210]
COHORT_NOTES: list[str] = [
    "冬季开卡，储值卡主推", "双十二拉新", "年货节礼盒", "春节返乡礼盒",
    "春季上新", "储值权益升级", "M6 台阶群（权益到期）", "夏季冰饮旺季",
    "毕业季联名", "门店扫码开卡", "开学季高峰", "未完整月（快照 11-30）",
]
BASE_RETENTION: list[float] = [
    1.000, 0.436, 0.381, 0.338, 0.301, 0.268, 0.214, 0.193,
    0.174, 0.158, 0.144, 0.131, 0.119,
]
GEN_LAMBDA = 0.2260
REV_AMP = 0.200
SALT = 11
ARPU0 = 116.5291
TOTAL_ORDERS = 24000
SNAPSHOT_MONTH = "2026-11"
DEMO_PASSWORD = "Demo@2026"

STORE_PREFIX = "MY"
STORE_COUNT = 380

USERS = [
    {
        "email": "admin@cohortltv.io",
        "display_name": "陈可 · 增长负责人",
        "role": "admin",
        "channel_scope": None,
    },
    {
        "email": "analyst@cohortltv.io",
        "display_name": "林知遥 · 增长分析师",
        "role": "analyst",
        "channel_scope": None,
    },
    {
        "email": "viewer@cohortltv.io",
        "display_name": "周明 · 门店运营（只读）",
        "role": "viewer",
        "channel_scope": "store",
    },
]


@dataclass
class CellPlan:
    cohort_index: int
    month_index: int
    active: int
    revenue: float
    channels: dict[str, dict]


def h01(*parts: object) -> float:
    key = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(key.encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def split_counts(total: int, weights: list[float]) -> list[int]:
    """最大余数法按权重拆整数，和恰好等于 total。"""
    weight_sum = sum(weights)
    raw = [total * w / weight_sum for w in weights]
    out = [int(math.floor(x)) for x in raw]
    remain = total - sum(out)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - out[i], reverse=True)
    for i in order[:remain]:
        out[i] += 1
    return out


def monthly_channel_split() -> list[dict[str, int]]:
    weights = [CHANNEL_SHARE[ch] for ch in COHORT_CHANNELS]
    return [
        dict(zip(COHORT_CHANNELS, split_counts(size, weights))) for size in COHORT_SIZES
    ]


def build_cells(arpu0: float = ARPU0) -> dict[tuple[int, int], CellPlan]:
    """设计每个（群，月）的有效会员数、营收与渠道拆分。"""
    norm = sum(CHANNEL_SHARE[ch] * CHANNEL_REVENUE_MULT[ch] for ch in COHORT_CHANNELS)
    shares = [CHANNEL_SHARE[ch] for ch in COHORT_CHANNELS]
    cells: dict[tuple[int, int], CellPlan] = {}
    for i, size in enumerate(COHORT_SIZES):
        observed = len(BASE_RETENTION) - i  # M0..M(12-i)，快照 2026-11 时 2025-11 群满 13 格
        for m in range(observed):
            if m == 0:
                active = size
            elif i == 0:
                active = int(round(size * BASE_RETENTION[m]))
            else:
                factor = 1.0 + (h01("ret", SALT, i, m) * 2 - 1) * 0.05
                active = max(1, min(size, int(round(size * BASE_RETENTION[m] * factor))))
            revenue = round(
                arpu0 * size * math.exp(-GEN_LAMBDA * m)
                * (1.0 + (h01("rev", SALT, i, m) * 2 - 1) * REV_AMP),
                2,
            )
            per_channel_active = split_counts(active, shares)
            channels: dict[str, dict] = {}
            for channel, ch_active in zip(COHORT_CHANNELS, per_channel_active):
                channels[channel] = {
                    "active": ch_active,
                    "revenue": round(
                        revenue * CHANNEL_SHARE[channel] * CHANNEL_REVENUE_MULT[channel] / norm, 2
                    ),
                }
            cells[(i, m)] = CellPlan(
                cohort_index=i, month_index=m, active=active, revenue=revenue, channels=channels
            )
    return cells


def solve_order_divisor(cells: dict[tuple[int, int], CellPlan], target: int = TOTAL_ORDERS) -> float:
    """二分出订单除数 W，使 Σ max(active_ch, round(rev_ch / W)) == target。"""

    def total_for(divisor: float) -> int:
        total = 0
        for cell in cells.values():
            for plan in cell.channels.values():
                total += max(plan["active"], int(round(plan["revenue"] / divisor)))
        return total

    low, high = 40.0, 400.0
    for _ in range(90):
        mid = (low + high) / 2
        if total_for(mid) > target:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def cell_order_counts(cell: CellPlan, divisor: float) -> dict[str, int]:
    return {
        channel: max(plan["active"], int(round(plan["revenue"] / divisor)))
        for channel, plan in cell.channels.items()
    }


def solve_order_counts(
    cells: dict[tuple[int, int], CellPlan], target: int = TOTAL_ORDERS
) -> dict[tuple[int, int, str], int]:
    """先二分订单除数，再把取整漂移摊到最大的格子上，保证总量恰好等于 target。"""
    divisor = solve_order_divisor(cells, target)
    counts: dict[tuple[int, int, str], int] = {}
    for (i, m), cell in cells.items():
        for channel, count in cell_order_counts(cell, divisor).items():
            counts[(i, m, channel)] = count
    total = sum(counts.values())
    keys = sorted(counts, key=lambda k: (-counts[k], k))
    guard = 0
    index = 0
    while total != target:
        guard += 1
        if guard > 20000:
            raise RuntimeError(f"order count adjustment did not converge total={total}")
        key = keys[index % len(keys)]
        index += 1
        if total < target:
            counts[key] += 1
            total += 1
        else:
            active = cells[(key[0], key[1])].channels[key[2]]["active"]
            if counts[key] > active:
                counts[key] -= 1
                total -= 1
    return counts


def split_amounts(revenue: float, count: int, key: str) -> list[int]:
    """把格内营收（元）拆成 count 笔订单金额（分），和精确等于 round(revenue*100)。"""
    cents = int(round(revenue * 100))
    if count <= 0:
        return []
    base = max(1200, cents // count)
    out: list[int] = []
    remain = cents
    for j in range(count - 1):
        jitter = 1.0 + (h01("amt", SALT, key, j) * 2 - 1) * 0.26
        value = max(1200, int(round(base * jitter)))
        left = count - j - 1
        if remain - value < 1200 * left:
            value = max(1200, remain - 1200 * left)
        out.append(value)
        remain -= value
    out.append(remain)
    return out


def member_codes(cohort_index: int, size: int) -> list[str]:
    return [f"M{cohort_index:02d}-{idx:04d}" for idx in range(size)]


def channel_member_pools(cohort_index: int) -> dict[str, list[str]]:
    """每个渠道的会员编号池（顺序固定，保证重建矩阵可复现）。"""
    codes = member_codes(cohort_index, COHORT_SIZES[cohort_index])
    split = monthly_channel_split()[cohort_index]
    pools: dict[str, list[str]] = {}
    cursor = 0
    for channel in COHORT_CHANNELS:
        count = split[channel]
        pools[channel] = codes[cursor:cursor + count]
        cursor += count
    return pools


def order_month(cohort_month: str, month_index: int) -> str:
    from src.utils.months import add_months

    return add_months(cohort_month, month_index)


def order_timestamp(month: str, key: str) -> datetime:
    year, mon = (int(part) for part in month.split("-"))
    day = 1 + int(h01("day", key) * 26)
    hour = int(h01("hour", key) * 12) + 8
    return datetime(year, mon, day, hour, 0, tzinfo=timezone.utc)


def iter_orders(
    cells: dict[tuple[int, int], CellPlan],
    counts_map: dict[tuple[int, int, str], int],
) -> list[dict]:
    """展开成订单行（与 SEED_SUMMARY 的 orders=24000 严格一致）。"""
    rows: list[dict] = []
    pools = {i: channel_member_pools(i) for i in range(len(COHORT_MONTHS))}
    for (i, m), cell in sorted(cells.items()):
        cohort_month = COHORT_MONTHS[i]
        counts = {ch: counts_map[(i, m, ch)] for ch in COHORT_CHANNELS}
        for channel in COHORT_CHANNELS:
            plan = cell.channels[channel]
            active_pool = pools[i][channel][: plan["active"]]
            if not active_pool:
                continue
            count = counts[channel]
            key = f"{i}-{m}-{channel}"
            amounts = split_amounts(plan["revenue"], count, key)
            month = order_month(cohort_month, m)
            for j, amount_cents in enumerate(amounts):
                member = active_pool[j % len(active_pool)]
                order_no = f"MO{i:02d}{m:02d}{COHORT_CHANNELS.index(channel) + 1}{j:05d}"
                store_index = 1 + int(h01("store", key, j) * STORE_COUNT)
                rows.append(
                    {
                        "order_no": order_no,
                        "member_code": member,
                        "cohort_month": cohort_month,
                        "channel": channel,
                        "store_code": f"{STORE_PREFIX}{store_index:03d}",
                        "order_month": month,
                        "month_index": m,
                        "amount": Decimal(amount_cents) / Decimal(100),
                        # 首轮订单覆盖每个活跃会员一次，这一轮才是「首单」
                        "is_first_order": m == 0 and j < len(active_pool),
                        "ordered_at": order_timestamp(month, order_no),
                    }
                )
    return rows


def demo_plan() -> tuple[dict[tuple[int, int], CellPlan], dict, list[dict]]:
    cells = build_cells()
    counts = solve_order_counts(cells)
    rows = iter_orders(cells, counts)
    return cells, counts, rows


def cohort_seed_rows() -> list[dict]:
    from src.constants.channels import DEFAULT_CAC

    splits = monthly_channel_split()
    out = []
    for i, month in enumerate(COHORT_MONTHS):
        mix = {
            channel: {"members": splits[i][channel], "cac": DEFAULT_CAC[channel]}
            for channel in COHORT_CHANNELS
        }
        out.append(
            {
                "month": month,
                "size": COHORT_SIZES[i],
                "channel_mix": mix,
                "note": COHORT_NOTES[i],
            }
        )
    return out


if __name__ == "__main__":  # 本地自检：不连库也能验证设计值
    cells, counts, rows = demo_plan()
    total = sum(row["amount"] for row in rows)
    print("orders", len(rows), "cells", len(counts))
    print("revenue", float(total), "per member", float(total) / sum(COHORT_SIZES))
    print("M1", cells[(0, 1)].active, "/", COHORT_SIZES[0])
    print("M6", cells[(0, 6)].active, "/", COHORT_SIZES[0])
