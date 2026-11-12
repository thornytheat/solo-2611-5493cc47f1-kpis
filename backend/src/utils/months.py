"""月份序号与差值的纯函数（观察期口径统一走这里）。"""
from __future__ import annotations

from datetime import date


def month_index(month: str) -> int:
    """'YYYY-MM' -> 年月序号 year*12 + (month-1)（`month_label` 的逆运算）。

    非法格式（非 YYYY-MM）或非法月份（00 / 13..99）抛 ValueError，
    不允许把 "2026-13" 静默归一成 "2027-01"。
    """
    parts = str(month).split("-")
    if (
        len(parts) != 2
        or len(parts[0]) != 4
        or len(parts[1]) != 2
        or not parts[0].isdigit()
        or not parts[1].isdigit()
    ):
        raise ValueError(f"invalid month: {month!r} (expected YYYY-MM)")
    year, mon = int(parts[0]), int(parts[1])
    if not 1 <= mon <= 12:
        raise ValueError(f"invalid month: {month!r} (month must be 01..12)")
    return year * 12 + mon - 1


def month_label(index: int) -> str:
    year, mon = divmod(index, 12)
    return f"{year:04d}-{mon + 1:02d}"


def add_months(month: str, delta: int) -> str:
    return month_label(month_index(month) + delta)


def month_span(start: str, end: str) -> int:
    """end 相对 start 的月差（含 0）。"""
    return month_index(end) - month_index(start)


def observed_months(cohort_month: str, snapshot_month: str, cap: int) -> int:
    """该群在快照月为止可观察的月数，上限 cap（=13 即 M0..M12）。"""
    return max(0, min(cap, month_span(cohort_month, snapshot_month) + 1))


def current_snapshot() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"
