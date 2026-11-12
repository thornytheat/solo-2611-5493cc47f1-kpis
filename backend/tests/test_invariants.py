"""性质 / 不变量测试：确定性、顺序无关、取值范围、计数守恒、阈值单调。"""
from __future__ import annotations

import math
import random

import pytest

from src.services.decay_fit import fit_exponential
from src.services.ltv_core import compute_ltv, sensitivity
from src.services.retention_core import CohortInput, build_retention_cells
from support import cell, cohort, ltv_params

SNAPSHOT = "2026-11"


def _case() -> tuple[list[dict], list[dict]]:
    """3 群 × 4 月（最后一群 M3 右删失）的确定性小矩阵。"""
    cohorts = [
        cohort("a", "2026-07", 60, {"private": {"members": 60}}),
        cohort("b", "2026-08", 80, {"private": {"members": 80}}),
        cohort("c", "2026-09", 40, {"private": {"members": 40}}),
    ]
    cells = []
    for key, size in (("a", 60), ("b", 80), ("c", 40)):
        for m in range(4):
            revenue = round(size * 100 * math.exp(-0.25 * m), 2)
            cells.append(cell(key, m, "all", revenue))
            cells.append(cell(key, m, "private", round(revenue * 0.5, 2)))
    return cohorts, cells


def test_deterministic_same_input_twice() -> None:
    cohorts, cells = _case()
    params = ltv_params(months=4)
    first = compute_ltv(cohorts, cells, SNAPSHOT, params)
    second = compute_ltv(cohorts, cells, SNAPSHOT, params)
    assert first == second
    assert first["fit"]["lambda_exact"] == 0.25
    assert first["totals"]["observed_cells"] == 11
    assert first["totals"]["censored_cells"] == 1


def test_fit_is_order_independent() -> None:
    """同一批 (m, y, w) 打乱顺序，拟合结果必须一致（聚合与顺序无关）。"""
    rows = []
    for m in range(6):
        for weight, jitter in ((50.0, 1.0), (70.0, 0.98)):
            rows.append((m, jitter * math.exp(-0.2 * m), weight))
    shuffled_a = list(rows)
    shuffled_b = list(rows)
    random.Random(7).shuffle(shuffled_a)
    random.Random(11).shuffle(shuffled_b)

    fit_a = fit_exponential(shuffled_a)
    fit_b = fit_exponential(shuffled_b)
    assert fit_a.lam == fit_b.lam
    assert fit_a.a == pytest.approx(fit_b.a, abs=1e-12)
    assert fit_a.r2 == pytest.approx(fit_b.r2, abs=1e-12)
    assert fit_a.cells_used == fit_b.cells_used == len(rows)


def test_ranges_and_count_conservation() -> None:
    cohorts, cells = _case()
    res = compute_ltv(cohorts, cells, SNAPSHOT, ltv_params(months=4))

    assert res["totals"]["observed_cells"] + res["totals"]["censored_cells"] == 3 * 4
    assert res["totals"]["members"] == 180
    assert res["params"]["lambda_min"] <= res["fit"]["lambda_exact"] <= res["params"]["lambda_max"]
    assert res["fit"]["a_exact"] > 0
    assert 0.0 <= res["fit"]["r2_exact"] <= 1.0
    assert res["arpu0"] == pytest.approx(100.0)
    assert res["ltv_hist_exact"] >= 0
    assert res["ltv_pred12_exact"] >= 0

    paybacks = [row["payback_months"] for row in res["channels"]]
    assert paybacks == sorted(paybacks)  # 排行按回本周期升序
    assert [row["rank"] for row in res["channels"]] == list(range(1, len(paybacks) + 1))

    # 留存率恒在 [0,1]，且活跃数不超过分母
    channel_aggs = []
    for key, month, size in (
        ("a", "2026-07", 60),
        ("b", "2026-08", 80),
        ("c", "2026-09", 40),
    ):
        for m in range(4):
            active = min(size, round(size * math.exp(-0.25 * m)))
            channel_aggs.append((month, m, "private", active, active * 30.0, active))
    build = build_retention_cells(
        [
            CohortInput("a", "2026-07", 60),
            CohortInput("b", "2026-08", 80),
            CohortInput("c", "2026-09", 40),
        ],
        channel_aggs,
        [("2026-07", "private", 60), ("2026-08", "private", 80), ("2026-09", "private", 40)],
        SNAPSHOT,
        4,
        30,
    )
    for row in build.rows:
        if row["retention_rate"] is not None:
            assert 0.0 <= row["retention_rate"] <= 1.0
        assert row["active_members"] <= row["sample_size"]


def test_sensitivity_threshold_monotonic() -> None:
    """λ 越大预测 LTV 越低；CAC 越大回本越久（单调，不翻转）。"""
    base = {
        "fit": {"lambda_exact": 0.21, "a_exact": 1.0},
        "arpu0": 100.0,
        "params": {"forecast_months": 12},
        "channels": [
            {"channel": "private", "short": "私域", "cac": 38.0, "arpu0": 100.0,
             "monthly_margin": 30.0},
            {"channel": "paid_feed", "short": "信息流", "cac": 126.0, "arpu0": 100.0,
             "monthly_margin": 25.0},
        ],
    }
    out = sensitivity(base, delta_lambda=0.03)
    assert out["lambda_variants"] == sorted(out["lambda_variants"])

    for row in out["rows"]:
        ltv_values = [item["ltv_pred12"] for item in row["cells"]]
        assert ltv_values[0] > ltv_values[1] > ltv_values[2]

    for row in out["cac_rows"]:
        paybacks = [item["payback_months"] for item in row["cells"]]
        assert paybacks[0] < paybacks[1] < paybacks[2]
        cacs = [item["cac"] for item in row["cells"]]
        assert cacs == sorted(cacs)


def test_censored_cells_never_enter_fit_or_revenue() -> None:
    """右删失格即使带巨额营收也必须被完全剔除（营收/拟合/计数都不受影响）。"""
    cohorts, cells = _case()
    params = ltv_params(months=4)
    baseline = compute_ltv(cohorts, cells, SNAPSHOT, params)
    removed = round(60 * 100 * math.exp(-0.25 * 2), 2)  # a 群 M2 的 all 行营收

    noisy = [
        cell("a", 2, "all", 1_000_000_000.0, right_censored=True)
        if (item["cohort_key"], item["month_index"], item["channel"]) == ("a", 2, "all")
        else item
        for item in cells
    ]
    after = compute_ltv(cohorts, noisy, SNAPSHOT, params)

    assert after["totals"]["revenue"] == pytest.approx(
        baseline["totals"]["revenue"] - removed, abs=0.01
    )
    assert after["totals"]["revenue"] < 10_000_000  # 巨额删失营收没有混进来
    assert after["totals"]["censored_cells"] == baseline["totals"]["censored_cells"] + 1
    assert after["fit"]["cells_used"] == baseline["fit"]["cells_used"] - 1
    assert after["ltv_pred12_exact"] == pytest.approx(baseline["ltv_pred12_exact"], abs=0.01)
