"""算法 B（指数衰减拟合 / LTV 预测 / CAC 回本 / 敏感性）单元测试。

测 `decay_fit.fit_exponential` 与 `ltv_core.compute_ltv / sensitivity`，
全部手算期望值 + `pytest.approx`。
"""
from __future__ import annotations

import math

import pytest

from src.services.decay_fit import fit_exponential
from src.services.ltv_core import CoreError, compute_ltv, fit_arpu_retention, sensitivity
from support import cell, cohort, ltv_params

SNAPSHOT = "2026-11"


# ---------------------------------------------------------------- 正常路径


def test_fit_recovers_known_exponential() -> None:
    """y = exp(-0.3m) 的精确数据 → λ=0.300、a=1、R²=1。"""
    rows = [(m, math.exp(-0.3 * m), 100.0) for m in range(4)]
    fit = fit_exponential(rows)
    assert fit.lam == pytest.approx(0.300, abs=0.001)
    assert fit.a == pytest.approx(1.0, abs=1e-6)
    assert fit.r2 == pytest.approx(1.0, abs=1e-9)
    assert fit.cells_used == 4
    assert [point.month_index for point in fit.points] == [0, 1, 2, 3]
    assert fit.predict(12) == pytest.approx(3.7528729068, abs=1e-6)


def test_compute_ltv_known_lambda_and_ltv() -> None:
    """单群 ARPU 留存 = 100·exp(-0.3m)：λ / 历史 LTV / 预测 12 月 LTV 全部手算。"""
    cohorts = [cohort("c1", "2026-07", 100)]
    cells = [
        cell("c1", 0, "all", 10000.00),
        cell("c1", 1, "all", 7408.18),
        cell("c1", 2, "all", 5488.12),
        cell("c1", 3, "all", 4065.70),
    ]
    res = compute_ltv(cohorts, cells, SNAPSHOT, ltv_params(months=4))

    assert res["arpu0"] == pytest.approx(100.0)
    assert res["fit"]["lambda"] == pytest.approx(0.300, abs=0.001)
    assert res["fit"]["a"] == pytest.approx(1.0, abs=1e-3)
    assert res["fit"]["r2"] == 1.0
    assert res["fit"]["cells_used"] == 4
    assert res["fit"]["cells_censored"] == 0
    assert res["fit"]["decay_factor_12m"] == pytest.approx(3.7529, abs=1e-3)

    assert res["totals"]["members"] == 100
    assert res["totals"]["observed_cells"] == 4
    assert res["totals"]["censored_cells"] == 0
    assert res["totals"]["revenue"] == pytest.approx(26962.00)

    assert res["ltv_hist_exact"] == pytest.approx(269.62)
    assert res["ltv_hist"] == 270.0
    assert res["ltv_pred12_exact"] == pytest.approx(375.29, abs=0.01)
    assert res["ltv_pred12"] == 375.0
    assert res["lift_ratio"] == pytest.approx(1.3919, abs=1e-3)

    assert res["params"]["margin_rate"] == 0.5
    assert res["params"]["forecast_months"] == 12
    assert res["params"]["channel_cac"]["private"] == 38.0
    assert res["params"]["channel_cac"]["paid_feed"] == 126.0
    assert res["notes"]["low_sample"] == "样本 <30 的群×渠道不进入渠道排行。"


def test_channel_payback_and_ranking() -> None:
    """渠道 CAC / 月均毛利 / 回本周期 / 排名逐项手算（样本 ≥30 才入排行）。"""
    cohorts = [
        cohort(
            "c1",
            "2026-09",
            100,
            {"private": {"members": 60}, "paid_feed": {"members": 40}},
        )
    ]
    cells = []
    for m, revenue in enumerate((10000.0, 5000.0, 2500.0)):
        cells.append(cell("c1", m, "all", revenue))
    for m, revenue in enumerate((6000.0, 3000.0, 1500.0)):
        cells.append(cell("c1", m, "private", revenue))
    for m, revenue in enumerate((4000.0, 2000.0, 1000.0)):
        cells.append(cell("c1", m, "paid_feed", revenue))

    res = compute_ltv(cohorts, cells, SNAPSHOT, ltv_params(months=3))

    assert res["arpu0"] == pytest.approx(100.0)
    assert [row["channel"] for row in res["channels"]] == ["private", "paid_feed"]
    private, feed = res["channels"]

    # 私域：CAC 38 / 月均毛利 29.17 → 回本 1.3 月
    assert private["rank"] == 1
    assert private["members"] == 60
    assert private["observed_months"] == pytest.approx(3.0)
    assert private["cum_per_member"] == pytest.approx(175.0)
    assert private["monthly_revenue"] == pytest.approx(58.33)
    assert private["monthly_margin"] == pytest.approx(29.17)
    assert private["cac"] == 38.0
    assert private["payback_months"] == pytest.approx(1.3)
    assert private["payback_exact"] == pytest.approx(1.3029, abs=1e-4)
    assert private["arpu0"] == pytest.approx(100.0)
    assert private["ltv_hist"] == pytest.approx(175.0)
    assert private["ltv_pred12"] == pytest.approx(214.76, abs=0.01)

    # 信息流：CAC 126 → 回本 4.3 月，排在私域之后
    assert feed["rank"] == 2
    assert feed["cac"] == 126.0
    assert feed["monthly_margin"] == pytest.approx(29.17)
    assert feed["payback_months"] == pytest.approx(4.3)
    assert feed["payback_exact"] == pytest.approx(4.32, abs=1e-4)

    # 样本 <30 的渠道（0 人）不进排行，但要在 low_sample 里明示
    assert {item["channel"] for item in res["low_sample"]["channel_cells"]} == {
        "store",
        "partner",
    }
    assert res["low_sample"]["cohorts"] == []
    assert res["fit"]["lambda"] == pytest.approx(0.6)  # 真衰减 0.693 超上界 → 命中上界


def test_sensitivity_hand_computed() -> None:
    """λ ±0.03 的预测 LTV 与 CAC ×0.8/1.0/1.2 的回本周期，全部手算。"""
    base = {
        "fit": {"lambda_exact": 0.2, "a_exact": 1.0},
        "arpu0": 100.0,
        "params": {"forecast_months": 12},
        "channels": [
            {"channel": "private", "short": "私域", "cac": 38.0, "arpu0": 100.0,
             "monthly_margin": 29.1667},
        ],
    }
    out = sensitivity(base, delta_lambda=0.03)

    assert out["lambda_base"] == 0.2
    assert out["lambda_variants"] == [0.17, 0.2, 0.23]
    assert out["forecast_months"] == 12
    assert out["arpu0"] == 100.0

    assert [item["ltv_pred12"] for item in out["rows"][0]["cells"]] == [556.0, 502.0, 456.0]
    assert [item["lambda"] for item in out["rows"][0]["cells"]] == [0.17, 0.2, 0.23]

    assert [item["cac"] for item in out["cac_rows"][0]["cells"]] == [30.0, 38.0, 46.0]
    assert [item["payback_months"] for item in out["cac_rows"][0]["cells"]] == [1.0, 1.3, 1.6]
    assert out["cac_scales"] == [0.8, 1.0, 1.2]


# ---------------------------------------------------------------- 边界 / 降级


def test_empty_fit_rows_rejected() -> None:
    with pytest.raises(ValueError, match="no observed cells"):
        fit_exponential([])


def test_single_cell_degenerates_to_min_lambda() -> None:
    """单条样本无法定 λ：网格首点 + a=y，R² 无方差按 0 处理（文档化降级）。"""
    fit = fit_exponential([(0, 1.0, 100.0)])
    assert fit.lam == pytest.approx(0.02)
    assert fit.a == pytest.approx(1.0)
    assert fit.r2 == 0.0
    assert fit.sst == 0.0
    assert fit.cells_used == 1
    assert len(fit.points) == 1


def test_constant_series_zero_variance() -> None:
    """每月留存全相同（零方差）：sst=0 → R² 记 0；λ 命中网格下界 0.02。

    单指数模型没有截距项，λ→0 时 a 收敛到常数；网格不含 0，故 a≈0.5099。
    """
    fit = fit_exponential([(m, 0.5, 10.0) for m in range(3)])
    assert fit.lam == pytest.approx(0.02)
    assert fit.a == pytest.approx(0.509897, abs=1e-5)
    assert fit.r2 == 0.0
    assert fit.sst == 0.0
    assert fit.predict(1) == pytest.approx(0.509897, abs=1e-5)


def test_low_sample_cohort_excluded_from_channel_ranking() -> None:
    """群规模与群×渠道都 <30：渠道排行必须为空，且 low_sample 明示原因。"""
    cohorts = [cohort("tiny", "2026-09", 20, {"private": {"members": 20}})]
    cells = [
        cell("tiny", m, "all", 2000.0) for m in range(3)
    ] + [
        cell("tiny", m, "private", 1000.0) for m in range(3)
    ]
    res = compute_ltv(cohorts, cells, SNAPSHOT, ltv_params(months=3))
    assert res["channels"] == []
    assert res["low_sample"]["cohorts"] == [{"month": "2026-09", "size": 20}]
    assert any(item["channel"] == "private" for item in res["low_sample"]["channel_cells"])
    # 阈值降到 10 后同一份数据即可入排行
    res2 = compute_ltv(
        cohorts, cells, SNAPSHOT, ltv_params(months=3, low_sample_threshold=10)
    )
    assert [row["channel"] for row in res2["channels"]] == ["private"]
    assert res2["low_sample"]["cohorts"] == []


def test_no_observed_cells_raises_core_error() -> None:
    cohorts = [cohort("c1", "2026-09", 100)]
    with pytest.raises(CoreError) as exc:
        compute_ltv(cohorts, [], SNAPSHOT, ltv_params(months=3))
    assert exc.value.code == "NO_OBSERVED_CELLS"


def test_zero_m0_revenue_raises_core_error() -> None:
    """有格子但营收为 0 → 明确报错，不返回 ARPU₀=0 的脏结果。"""
    cohorts = [cohort("c1", "2026-09", 100)]
    cells = [cell("c1", m, "all", 0.0) for m in range(3)]
    with pytest.raises(CoreError) as exc:
        compute_ltv(cohorts, cells, SNAPSHOT, ltv_params(months=3))
    assert exc.value.code == "NO_OBSERVED_CELLS"
    assert "M0 营收为空" in str(exc.value)


def test_observed_months_override_caps_fit_window() -> None:
    """观察期覆盖到 2 个月：第 3 个月起按删失剔除，cells_censored 增加。"""
    cohorts = [cohort("c1", "2026-07", 100)]
    cells = [
        cell("c1", 0, "all", 10000.00),
        cell("c1", 1, "all", 7408.18),
        cell("c1", 2, "all", 5488.12),
        cell("c1", 3, "all", 4065.70),
    ]
    res = compute_ltv(
        cohorts, cells, SNAPSHOT, ltv_params(months=4, observed_months_override=2)
    )
    assert res["fit"]["cells_used"] == 2
    assert res["fit"]["cells_censored"] == 2
    assert res["params"]["observed_months"] == 2
    assert res["totals"]["revenue"] == pytest.approx(17408.18)


# ---------------------------------------------------------------- 异常输入


def test_inverted_lambda_bounds_fail_explicitly() -> None:
    """λ 上下界颠倒 → 网格为空 → 明确 FIT_FAILED，而不是静默返回默认曲线。"""
    cohorts = [cohort("c1", "2026-07", 100)]
    cells = [cell("c1", m, "all", 10000.0 * math.exp(-0.3 * m)) for m in range(4)]
    with pytest.raises(CoreError) as exc:
        compute_ltv(
            cohorts,
            cells,
            SNAPSHOT,
            ltv_params(months=4, lambda_min=0.6, lambda_max=0.02),
        )
    assert exc.value.code == "FIT_FAILED"


def test_zero_weight_rows_are_degenerate() -> None:
    with pytest.raises(CoreError) as exc:
        fit_arpu_retention([(0, 1.0, 0.0)], ltv_params(months=1))
    assert exc.value.code == "FIT_FAILED"
    assert "degenerate fit" in exc.value.detail
