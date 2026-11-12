"""单测用的纯数据构造器（不触碰 DB / 网络）。"""
from __future__ import annotations

from typing import Mapping

from src.constants.channels import DEFAULT_CAC
from src.services.ltv_core import LtvParams


def cohort(
    key: str,
    month: str,
    size: int,
    channel_mix: Mapping[str, Mapping[str, int]] | None = None,
) -> dict:
    return {
        "key": key,
        "month": month,
        "size": size,
        "channel_mix": dict(channel_mix or {}),
    }


def cell(
    cohort_key: str,
    month_index: int,
    channel: str,
    revenue: float,
    *,
    right_censored: bool = False,
) -> dict:
    return {
        "cohort_key": cohort_key,
        "month_index": month_index,
        "channel": channel,
        "revenue": float(revenue),
        "right_censored": right_censored,
    }


def ltv_params(
    *,
    months: int = 3,
    forecast_months: int = 12,
    margin_rate: float = 0.5,
    lambda_min: float = 0.02,
    lambda_max: float = 0.60,
    lambda_step: float = 0.001,
    low_sample_threshold: int = 30,
    channel_cac: Mapping[str, float] | None = None,
    observed_months_override: int | None = None,
) -> LtvParams:
    return LtvParams(
        months=months,
        forecast_months=forecast_months,
        margin_rate=margin_rate,
        lambda_min=lambda_min,
        lambda_max=lambda_max,
        lambda_step=lambda_step,
        low_sample_threshold=low_sample_threshold,
        default_cac=dict(DEFAULT_CAC),
        channel_cac=channel_cac,
        observed_months_override=observed_months_override,
    )
