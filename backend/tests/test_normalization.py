"""解析 / 归一工具单元测试：月份序号、数值归一、金额分桶、CAC 与观察期归一。"""
from __future__ import annotations

import pytest

from src.constants.channels import DEFAULT_CAC
from src.services.ltv_core import normalize_cac_map, normalize_observed_cap
from src.utils.aggregates import bucket_amounts
from src.utils.months import add_months, month_index, month_label, month_span, observed_months
from src.utils.numbers import as_int, round_half_up, safe_div


@pytest.mark.parametrize(
    ("month", "expected"),
    [("1970-01", 23640), ("2025-11", 24310), ("2025-12", 24311), ("2026-11", 24322)],
)
def test_month_index(month: str, expected: int) -> None:
    assert month_index(month) == expected


@pytest.mark.parametrize(
    ("index", "expected"),
    [(23640, "1970-01"), (24310, "2025-11"), (24322, "2026-11"), (24323, "2026-12")],
)
def test_month_label(index: int, expected: str) -> None:
    assert month_label(index) == expected


@pytest.mark.parametrize(
    ("month", "delta", "expected"),
    [
        ("2025-11", 2, "2026-01"),
        ("2026-01", -2, "2025-11"),
        ("2025-12", 12, "2026-12"),
        ("2026-11", 0, "2026-11"),
    ],
)
def test_add_months(month: str, delta: int, expected: str) -> None:
    assert add_months(month, delta) == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2025-11", "2026-02", 3),
        ("2025-11", "2025-11", 0),
        ("2025-11", "2026-11", 12),
    ],
)
def test_month_span(start: str, end: str, expected: int) -> None:
    assert month_span(start, end) == expected


@pytest.mark.parametrize(
    ("cohort_month", "snapshot", "cap", "expected"),
    [
        ("2026-10", "2026-11", 13, 2),
        ("2025-11", "2026-11", 13, 13),
        ("2025-11", "2026-11", 100, 13),
        ("2025-11", "2026-11", 5, 5),
        ("2026-12", "2026-11", 13, 0),  # 未来群：0 个月可观察
    ],
)
def test_observed_months(cohort_month: str, snapshot: str, cap: int, expected: int) -> None:
    assert observed_months(cohort_month, snapshot, cap) == expected


@pytest.mark.parametrize(
    ("numerator", "denominator", "default", "expected"),
    [
        (10.0, 4.0, 0.0, 2.5),
        (10.0, 0.0, 0.0, 0.0),
        (10.0, 0.0, -1.0, -1.0),
        (-9.0, 3.0, 0.0, -3.0),
    ],
)
def test_safe_div(numerator: float, denominator: float, default: float, expected: float) -> None:
    assert safe_div(numerator, denominator, default) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [
        (2.5, 0, 3.0),      # 显式 half-up，区别于 Python round() 的银行家舍入
        (412.5, 0, 413.0),
        (1.005, 2, 1.01),
        (-2.5, 0, -3.0),
        (1.234, 1, 1.2),
    ],
)
def test_round_half_up(value: float, digits: int, expected: float) -> None:
    assert round_half_up(value, digits) == pytest.approx(expected)


@pytest.mark.parametrize(("value", "expected"), [(2.5, 3), (2.4, 2), (-2.5, -3)])
def test_as_int(value: float, expected: int) -> None:
    assert as_int(value) == expected


def test_amount_bucket_boundaries() -> None:
    """左闭右开边界：0/19.99 → 第 1 桶；20/39.99 → 第 2 桶；……；300 → 最后一桶。"""
    amounts = [0, 19.99, 20, 39.99, 40, 79.99, 80, 149.99, 150, 299.99, 300, 1000]
    out = bucket_amounts(amounts)
    assert [row["count"] for row in out["buckets"]] == [2, 2, 2, 2, 2, 2]
    assert [row["label"] for row in out["buckets"]] == [
        "<¥20", "¥20-40", "¥40-80", "¥80-150", "¥150-300", "≥¥300",
    ]
    assert out["orders"] == 12
    assert out["total"] == pytest.approx(2179.95)
    assert out["avg_ticket"] == pytest.approx(181.66)


def test_amount_bucket_empty_input() -> None:
    out = bucket_amounts([])
    assert out["orders"] == 0
    assert out["total"] == 0.0
    assert out["avg_ticket"] == 0.0
    assert [row["count"] for row in out["buckets"]] == [0, 0, 0, 0, 0, 0]


def test_normalize_cac_map() -> None:
    defaults = dict(DEFAULT_CAC)
    out = normalize_cac_map(
        defaults,
        {"private": 50, "paid_feed": 0, "store": -5, "partner": None, "unknown": 99},
    )
    assert out["private"] == pytest.approx(50.0)
    assert out["paid_feed"] == pytest.approx(126.0)  # 非法 0 → 保留默认
    assert out["store"] == pytest.approx(16.0)       # 负值 → 保留默认
    assert out["partner"] == pytest.approx(58.0)     # None → 保留默认
    assert "unknown" not in out                      # 未知渠道忽略
    assert defaults["private"] == 38.0               # 不修改入参


@pytest.mark.parametrize(
    ("override", "months", "expected"),
    [(None, 13, None), (0, 13, None), (-3, 13, 1), (5, 13, 5), (99, 13, 13)],
)
def test_normalize_observed_cap(override, months: int, expected) -> None:
    assert normalize_observed_cap(override, months) == expected


@pytest.mark.parametrize("bad", ["2026-13", "2026-00", "2026-1", "26-01", "2026-1a", "2026/01"])
def test_invalid_month_raises(bad: str) -> None:
    """非法月份必须显式报错，不允许把 2026-13 静默归一成 2027-01。"""
    with pytest.raises(ValueError):
        month_index(bad)
    with pytest.raises(ValueError):
        observed_months("2025-11", bad, 13)
