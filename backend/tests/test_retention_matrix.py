"""算法 A（同期群留存矩阵，右删失）单元测试。

只测纯函数 `retention_core.build_retention_cells`：输入订单聚合与群规模，
输出「群 × 月序 × 渠道」留存格。手算期望值 + 真实 seed 切片。
"""
from __future__ import annotations

import pytest

from scripts import fixtures
from src.constants.enums import COHORT_CHANNELS
from src.services.retention_core import CohortInput, build_retention_cells

SNAPSHOT = "2026-11"


# ---------------------------------------------------------------- 正常路径


def test_hand_computed_cells() -> None:
    """2 个月观察 + 1 个月右删失，逐格手算。"""
    build = build_retention_cells(
        [CohortInput(key="c1", month="2026-10", size=10)],
        channel_aggs=[
            ("2026-10", 0, "private", 3, 300.0, 6),
            ("2026-10", 0, "store", 1, 100.0, 2),
            ("2026-10", 1, "private", 1, 90.0, 1),
            ("2026-10", 1, "store", 1, 110.0, 3),
        ],
        member_aggs=[("2026-10", "private", 4), ("2026-10", "store", 6)],
        snapshot_month=SNAPSHOT,
        months=3,
        low_sample_threshold=5,
    )
    assert len(build.rows) == 3 * 5  # 3 月 × (all + 4 渠道)
    by_key = {(row["month_index"], row["channel"]): row for row in build.rows}

    all_m0 = by_key[(0, "all")]
    assert all_m0["active_members"] == 4
    assert all_m0["revenue"] == pytest.approx(400.00)
    assert all_m0["retention_rate"] == pytest.approx(0.4, abs=1e-6)
    assert all_m0["sample_size"] == 10
    assert all_m0["order_count"] == 8
    assert all_m0["right_censored"] is False

    all_m1 = by_key[(1, "all")]
    assert all_m1["active_members"] == 2
    assert all_m1["retention_rate"] == pytest.approx(0.2, abs=1e-6)

    all_m2 = by_key[(2, "all")]
    assert all_m2["right_censored"] is True
    assert all_m2["active_members"] == 0
    assert all_m2["revenue"] == 0.0
    assert all_m2["retention_rate"] is None

    private_m0 = by_key[(0, "private")]
    assert private_m0["retention_rate"] == pytest.approx(3 / 4, abs=1e-6)
    assert private_m0["low_sample"] is True  # 4 < 5

    store_m0 = by_key[(0, "store")]
    assert store_m0["retention_rate"] == pytest.approx(1 / 6, abs=1e-6)
    assert store_m0["low_sample"] is False  # 6 >= 5

    feed_m0 = by_key[(0, "paid_feed")]
    assert feed_m0["active_members"] == 0
    assert feed_m0["sample_size"] == 0
    assert feed_m0["retention_rate"] is None  # 无分母，降级为 None 而不是 0

    assert build.summary == {
        "snapshot_month": SNAPSHOT,
        "cohorts": 1,
        "months": 3,
        "cells": 15,
        "cells_observed": 2,
        "cells_censored": 1,
        "low_sample_cells": 9,
    }


def test_real_seed_2025_11_slice() -> None:
    """用 seed 真实设计值复算 2025-11 基准群：M1=122/280、M6=60/280。"""
    month = fixtures.COHORT_MONTHS[0]
    size = fixtures.COHORT_SIZES[0]
    plan = fixtures.build_cells()
    shares = fixtures.monthly_channel_split()[0]

    channel_aggs = []
    for m in range(len(fixtures.BASE_RETENTION)):
        for channel in COHORT_CHANNELS:
            part = plan[(0, m)].channels[channel]
            channel_aggs.append((month, m, channel, part["active"], part["revenue"], 0))
    member_aggs = [(month, channel, shares[channel]) for channel in COHORT_CHANNELS]

    build = build_retention_cells(
        [CohortInput(key="c0", month=month, size=size)],
        channel_aggs,
        member_aggs,
        fixtures.SNAPSHOT_MONTH,
        len(fixtures.BASE_RETENTION),
        30,
    )
    all_cells = {row["month_index"]: row for row in build.rows if row["channel"] == "all"}
    assert all_cells[0]["active_members"] == 280
    assert all_cells[0]["retention_rate"] == pytest.approx(1.0)

    assert all_cells[1]["active_members"] == 122
    assert all_cells[1]["retention_rate"] == pytest.approx(122 / 280, abs=1e-6)

    assert all_cells[6]["active_members"] == 60
    assert all_cells[6]["retention_rate"] == pytest.approx(60 / 280, abs=1e-6)
    assert build.summary["cells_observed"] == 13
    assert build.summary["cells_censored"] == 0


def test_censoring_windows_per_cohort() -> None:
    """不同首单月在同一快照下的观察窗口：13 / 7 / 2，删失 0 / 6 / 11。"""
    build = build_retention_cells(
        [
            CohortInput(key="a", month="2025-11", size=100),
            CohortInput(key="b", month="2026-05", size=100),
            CohortInput(key="c", month="2026-10", size=100),
        ],
        channel_aggs=[],
        member_aggs=[],
        snapshot_month=SNAPSHOT,
        months=13,
        low_sample_threshold=30,
    )
    assert build.summary["cells_observed"] == 13 + 7 + 2
    assert build.summary["cells_censored"] == 0 + 6 + 11
    assert len(build.rows) == 3 * 13 * 5

    by_key = {(row["cohort_key"], row["month_index"], row["channel"]): row for row in build.rows}
    assert by_key[("b", 6, "all")]["right_censored"] is False
    assert by_key[("b", 7, "all")]["right_censored"] is True
    assert by_key[("b", 7, "all")]["active_members"] == 0
    assert by_key[("b", 7, "private")]["retention_rate"] is None
    assert by_key[("c", 1, "all")]["right_censored"] is False
    assert by_key[("c", 2, "all")]["right_censored"] is True


# ---------------------------------------------------------------- 边界 / 降级


def test_empty_cohorts_returns_empty_matrix() -> None:
    build = build_retention_cells([], [], [], SNAPSHOT, 13, 30)
    assert build.rows == []
    assert build.channel_members == {}
    assert build.summary["cohorts"] == 0
    assert build.summary["cells"] == 0
    assert build.summary["cells_observed"] == 0
    assert build.summary["cells_censored"] == 0
    assert build.summary["low_sample_cells"] == 0


def test_no_orders_degrades_to_zero_rates() -> None:
    """有群无订单：all 行 rate=0.0（分母存在），渠道行 rate=None（无分母）。"""
    build = build_retention_cells(
        [CohortInput(key="c1", month="2026-10", size=100)],
        channel_aggs=[],
        member_aggs=[],
        snapshot_month=SNAPSHOT,
        months=2,
        low_sample_threshold=30,
    )
    by_key = {(row["month_index"], row["channel"]): row for row in build.rows}
    for m in (0, 1):
        assert by_key[(m, "all")]["active_members"] == 0
        assert by_key[(m, "all")]["retention_rate"] == pytest.approx(0.0)
        assert by_key[(m, "all")]["sample_size"] == 100
        for channel in COHORT_CHANNELS:
            assert by_key[(m, channel)]["retention_rate"] is None
            assert by_key[(m, channel)]["low_sample"] is True


def test_single_cohort_single_observed_month() -> None:
    """最小非空输入：1 群 × 1 月 × 5 渠道，且无删失。"""
    build = build_retention_cells(
        [CohortInput(key="only", month="2026-11", size=50)],
        channel_aggs=[],
        member_aggs=[],
        snapshot_month="2026-11",
        months=1,
        low_sample_threshold=30,
    )
    assert len(build.rows) == 5
    assert build.summary["cells_observed"] == 1
    assert build.summary["cells_censored"] == 0
    assert all(row["right_censored"] is False for row in build.rows)
    assert all(row["month_index"] == 0 for row in build.rows)


def test_low_sample_marks_without_dropping_rows() -> None:
    """样本 <30 只打标、不删行；渠道分母取「群×渠道」真实会员数。"""
    build = build_retention_cells(
        [CohortInput(key="c1", month="2026-10", size=20)],
        channel_aggs=[("2026-10", 0, "private", 5, 50.0, 5)],
        member_aggs=[("2026-10", "private", 100)],
        snapshot_month=SNAPSHOT,
        months=2,
        low_sample_threshold=30,
    )
    assert len(build.rows) == 2 * 5
    by_key = {(row["month_index"], row["channel"]): row for row in build.rows}
    assert by_key[(0, "all")]["low_sample"] is True  # 群规模 20 < 30
    assert by_key[(0, "private")]["low_sample"] is False  # 渠道样本 100
    assert by_key[(0, "private")]["sample_size"] == 100
    assert by_key[(0, "private")]["retention_rate"] == pytest.approx(0.05)
    assert by_key[(0, "paid_feed")]["low_sample"] is True  # 无订单 → 样本 0
    assert build.summary["low_sample_cells"] > 0
