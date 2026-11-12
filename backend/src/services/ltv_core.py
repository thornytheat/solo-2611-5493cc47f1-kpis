"""算法 2 的纯函数核心：LTV 测算、指数衰减拟合、CAC 回本与敏感性。

口径（README「算法口径」与前端口径提示同源）：
- ARPU₀   = 各群 M0 营收 / 各群规模（全渠道加权）
- 拟合     R_m = a·exp(-λm)，对有效（非右删失）格子的 ARPU 留存做加权最小二乘，
           λ∈[0.02, 0.60] 步长 0.001 网格搜索，权重 = 群规模，a 为闭式解
- 历史 LTV = 观察期内群累计营收 / 群规模，跨群按会员数加权
- 预测 12 月 LTV = ARPU₀ × Σ_{m=0..11} a·exp(-λm)
- 回本周期 = CAC / 月均毛利贡献，月均毛利贡献 = 观察期人均月营收 × 毛利率
- 群或「群×渠道」样本 <30 标 low_sample，不进入渠道排行

本模块只吃普通 dict / list，不做数据库读写；加载与持久化由 ltv_service 负责，
因此算法可以脱离 PostgreSQL 做单元测试。
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from src.constants import error_codes as codes
from src.constants.channels import CHANNEL_LABELS, CHANNEL_NOTES, CHANNEL_SHORT
from src.constants.enums import COHORT_CHANNELS, Channel
from src.services.decay_fit import FitResult, fit_exponential
from src.utils.months import observed_months
from src.utils.numbers import round_half_up, safe_div


class CoreError(ValueError):
    """核心算法的明确输入错误；由 service 层翻译成 AppError（保持原错误码/文案）。"""

    def __init__(self, code: str, message: str | None = None, detail: str = "") -> None:
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message or code)


@dataclass(frozen=True)
class LtvParams:
    """一次测算的全部口径参数（由 settings + 请求覆盖合并后传入）。"""

    months: int
    forecast_months: int
    margin_rate: float
    lambda_min: float
    lambda_max: float
    lambda_step: float
    low_sample_threshold: int
    default_cac: Mapping[str, float]
    channel_cac: Mapping[str, float] | None = None
    observed_months_override: int | None = None


def normalize_cac_map(
    defaults: Mapping[str, float],
    overrides: Mapping[str, float] | None,
) -> dict[str, float]:
    """渠道 CAC 归一：未知渠道忽略；None / ≤0 保留默认值；合法值转 float。"""
    cac_map = dict(defaults)
    if overrides:
        for key, value in overrides.items():
            if key in cac_map and value is not None and value > 0:
                cac_map[key] = float(value)
    return cac_map


def normalize_observed_cap(override: int | None, months: int) -> int | None:
    """观察期覆盖值归一：假值视为不覆盖，否则截断到 [1, months]。"""
    if not override:
        return None
    return max(1, min(months, int(override)))


def _index_cells(cells: Sequence[Mapping]) -> dict[str, dict[str, dict[int, Mapping]]]:
    by_cohort: dict[str, dict[str, dict[int, Mapping]]] = {}
    for cell in cells:
        by_cohort.setdefault(str(cell["cohort_key"]), {}).setdefault(
            str(cell["channel"]), {}
        )[int(cell["month_index"])] = cell
    return by_cohort


def fit_arpu_retention(
    rows: list[tuple[int, float, float]],
    params: LtvParams,
) -> FitResult:
    """对有效格子的 ARPU 留存做加权最小二乘（λ 网格 + a 闭式解）。"""
    try:
        return fit_exponential(
            rows,
            lambda_min=params.lambda_min,
            lambda_max=params.lambda_max,
            step=params.lambda_step,
        )
    except ValueError as exc:
        raise CoreError(codes.FIT_FAILED, detail=str(exc)) from exc


def compute_ltv(
    cohorts: Sequence[Mapping],
    cells: Sequence[Mapping],
    snapshot_month: str,
    params: LtvParams,
) -> dict:
    """纯函数：同期群 + 留存格 → LTV 测算结果（与 GET/POST /ltv/reports 响应同构）。"""
    months = params.months
    forecast = params.forecast_months
    margin = float(params.margin_rate)
    cac_map = normalize_cac_map(params.default_cac, params.channel_cac)

    obs = {
        str(cohort["key"]): observed_months(str(cohort["month"]), snapshot_month, months)
        for cohort in cohorts
    }
    cap = normalize_observed_cap(params.observed_months_override, months)
    if cap is not None:
        obs = {key: min(value, cap) for key, value in obs.items()}

    by_cohort = _index_cells(cells)
    total_members = sum(int(c["size"]) for c in cohorts)
    m0_revenue = 0.0
    total_revenue = 0.0
    observed_cells = 0
    censored = 0

    for cohort in cohorts:
        cid = str(cohort["key"])
        all_cells = by_cohort.get(cid, {}).get(Channel.ALL.value, {})
        size = int(cohort["size"])
        window = obs[cid]
        for m in range(months):
            cell = all_cells.get(m)
            if m >= window or cell is None or cell["right_censored"]:
                censored += 1
                continue
            revenue = float(cell["revenue"])
            total_revenue += revenue
            if m == 0:
                m0_revenue += revenue
            if size > 0:
                observed_cells += 1

    if observed_cells == 0:
        raise CoreError(codes.NO_OBSERVED_CELLS)

    arpu0 = safe_div(m0_revenue, total_members)
    if arpu0 <= 0:
        raise CoreError(codes.NO_OBSERVED_CELLS, "M0 营收为空，无法测算 ARPU₀")

    rows: list[tuple[int, float, float]] = []
    for cohort in cohorts:
        cid = str(cohort["key"])
        all_cells = by_cohort.get(cid, {}).get(Channel.ALL.value, {})
        size = int(cohort["size"])
        window = obs[cid]
        for m in range(min(window, months)):
            cell = all_cells.get(m)
            if cell is None or cell["right_censored"] or size <= 0:
                continue
            rows.append((m, safe_div(float(cell["revenue"]), size) / arpu0, float(size)))

    fit = fit_arpu_retention(rows, params)
    factor = fit.predict(forecast)
    ltv_pred = arpu0 * factor
    ltv_hist = safe_div(total_revenue, total_members)

    threshold = params.low_sample_threshold
    channel_rows = []
    low_sample_channel_cells = []
    for channel in COHORT_CHANNELS:
        members = 0
        month_weight = 0.0
        revenue = 0.0
        arpu0_ch = 0.0
        for cohort in cohorts:
            cid = str(cohort["key"])
            size = int(cohort["size"])
            mix = (cohort.get("channel_mix") or {}).get(channel) or {}
            ch_members = int(mix.get("members", 0))
            if ch_members < threshold:
                if ch_members > 0 or size > 0:
                    low_sample_channel_cells.append(
                        {"month": cohort["month"], "channel": channel, "members": ch_members}
                    )
                continue
            window = obs[cid]
            members += ch_members
            month_weight += ch_members * window
            channel_cells = by_cohort.get(cid, {}).get(channel, {})
            for m in range(min(window, months)):
                cell = channel_cells.get(m)
                if cell is None or cell["right_censored"]:
                    continue
                revenue += float(cell["revenue"])
                if m == 0:
                    arpu0_ch += float(cell["revenue"])
        if members <= 0:
            continue
        mean_months = safe_div(month_weight, members)
        cum_per_member = safe_div(revenue, members)
        monthly_revenue = safe_div(cum_per_member, mean_months)
        monthly_margin = monthly_revenue * margin
        cac = cac_map.get(channel, 0.0)
        payback = safe_div(cac, monthly_margin, default=0.0)
        channel_rows.append(
            {
                "channel": channel,
                "label": CHANNEL_LABELS.get(channel, channel),
                "short": CHANNEL_SHORT.get(channel, channel),
                "note": CHANNEL_NOTES.get(channel, ""),
                "cac": round(cac, 2),
                "members": members,
                "observed_months": round(mean_months, 3),
                "cum_per_member": round(cum_per_member, 2),
                "monthly_revenue": round(monthly_revenue, 2),
                "monthly_margin": round(monthly_margin, 2),
                "payback_months": round_half_up(payback, 1),
                "payback_exact": round(payback, 4),
                "arpu0": round(safe_div(arpu0_ch, members), 2),
                "ltv_hist": round(cum_per_member, 2),
                "ltv_pred12": round(safe_div(arpu0_ch, members) * factor, 2),
                "low_sample": False,
            }
        )

    channel_rows.sort(key=lambda r: r["payback_months"])
    for idx, row in enumerate(channel_rows, start=1):
        row["rank"] = idx

    cohorts_low_sample = [
        {"month": cohort["month"], "size": int(cohort["size"])}
        for cohort in cohorts
        if int(cohort["size"]) < threshold
    ]
    curve = [
        {
            "m": point.month_index,
            "observed": round(point.observed, 6),
            "fitted": round(point.fitted, 6),
            "weight": point.weight,
        }
        for point in fit.points
    ]

    return {
        "snapshot_month": snapshot_month,
        "params": {
            "observed_months": params.observed_months_override,
            "lambda_min": params.lambda_min,
            "lambda_max": params.lambda_max,
            "lambda_step": params.lambda_step,
            "margin_rate": margin,
            "channel_cac": {k: round(v, 2) for k, v in cac_map.items()},
            "forecast_months": forecast,
            "low_sample_threshold": threshold,
            "weighting": "cohort_size",
            "model": "exponential",
        },
        "fit": {
            "model": "R_m = a·exp(-λm)",
            "lambda": round(fit.lam, 3),
            "lambda_exact": round(fit.lam, 6),
            "a": round(fit.a, 4),
            "a_exact": round(fit.a, 6),
            "r2": round_half_up(fit.r2, 2),
            "r2_exact": round(fit.r2, 4),
            "cells_used": observed_cells,
            "cells_censored": censored,
            "decay_factor_12m": round(factor, 4),
            "curve": curve,
        },
        "arpu0": round(arpu0, 2),
        "ltv_hist": round_half_up(ltv_hist, 0),
        "ltv_hist_exact": round(ltv_hist, 2),
        "ltv_pred12": round_half_up(ltv_pred, 0),
        "ltv_pred12_exact": round(ltv_pred, 2),
        "lift_ratio": round(safe_div(ltv_pred, ltv_hist), 4),
        "totals": {
            "cohorts": len(cohorts),
            "members": total_members,
            "observed_cells": observed_cells,
            "censored_cells": censored,
            "revenue": round(total_revenue, 2),
        },
        "channels": channel_rows,
        "low_sample": {
            "cohorts": cohorts_low_sample,
            "channel_cells": low_sample_channel_cells,
        },
        "notes": {
            "fit": "拟合对象是 ARPU 留存（金额留存），人数留存矩阵单独展示；λ 为网格搜索解。",
            "payback": "回本周期 = CAC / 月均毛利贡献（观察期人均月营收 × 毛利率）。",
            "low_sample": f"样本 <{threshold} 的群×渠道不进入渠道排行。",
        },
    }


def sensitivity(
    results: dict,
    *,
    delta_lambda: float = 0.03,
    cac_scales: tuple[float, ...] = (0.8, 1.0, 1.2),
) -> dict:
    """敏感性：λ 上下浮动对预测 LTV 的影响；CAC 缩放对回本周期的影响。"""
    lam = float(results["fit"]["lambda_exact"])
    a = float(results["fit"]["a_exact"])
    arpu0 = float(results["arpu0"])
    forecast = int(results["params"]["forecast_months"])
    variants = [
        max(0.02, round(lam - delta_lambda, 3)),
        round(lam, 3),
        min(0.60, round(lam + delta_lambda, 3)),
    ]
    rows = []
    for row in results["channels"]:
        cells = []
        for value in variants:
            factor = sum(a * math.exp(-value * m) for m in range(forecast))
            cells.append(
                {
                    "lambda": value,
                    "ltv_pred12": round_half_up(float(row["arpu0"]) * factor, 0),
                }
            )
        rows.append(
            {"channel": row["channel"], "short": row["short"], "cac": row["cac"], "cells": cells}
        )
    cac_rows = []
    for row in results["channels"]:
        cells = []
        for scale in cac_scales:
            cac = float(row["cac"]) * scale
            payback = safe_div(cac, float(row["monthly_margin"]), default=0.0)
            cells.append(
                {
                    "scale": scale,
                    "cac": round_half_up(cac, 0),
                    "payback_months": round_half_up(payback, 1),
                }
            )
        cac_rows.append(
            {"channel": row["channel"], "short": row["short"], "cells": cells}
        )
    return {
        "lambda_base": round(lam, 3),
        "lambda_variants": variants,
        "delta_lambda": delta_lambda,
        "rows": rows,
        "cac_scales": list(cac_scales),
        "cac_rows": cac_rows,
        "forecast_months": forecast,
        "arpu0": arpu0,
    }


__all__ = [
    "CoreError",
    "LtvParams",
    "compute_ltv",
    "fit_arpu_retention",
    "normalize_cac_map",
    "normalize_observed_cap",
    "sensitivity",
]
