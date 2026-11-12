"""LtvReport schema（测算参数 + 结果）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LtvRunRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    observed_months: int | None = Field(default=None, ge=2, le=13)
    lambda_min: float | None = Field(default=None, ge=0.001, le=0.6)
    lambda_max: float | None = Field(default=None, ge=0.02, le=1.0)
    margin_rate: float | None = Field(default=None, ge=0.05, le=1.0)
    forecast_months: int | None = Field(default=None, ge=3, le=24)
    channel_cac: dict[str, float] | None = None
    note: str = Field(default="", max_length=400)


class FitOut(BaseModel):
    model: str
    lambda_: float = Field(alias="lambda")
    a: float
    r2: float
    cells_used: int
    cells_censored: int
    decay_factor_12m: float
    curve: list[dict[str, float]] = []

    model_config = {"populate_by_name": True}


class ChannelRowOut(BaseModel):
    channel: str
    label: str
    short: str
    cac: float
    members: int
    observed_months: float
    cum_per_member: float
    monthly_revenue: float
    monthly_margin: float
    payback_months: float
    ltv_hist: float
    ltv_pred12: float
    rank: int = 0
    low_sample: bool = False


class LtvReportOut(BaseModel):
    id: str
    name: str
    status: str
    created_at: str
    published_at: str | None = None
    params: dict[str, Any]
    results: dict[str, Any]
    review_state: str
    stale: bool
    source_data_seq: int
    current_data_seq: int
    lineage_id: str
    version_no: int
    supersedes_id: str | None = None
    lineage_versions: list[dict[str, Any]] = []


class LtvReportSummaryOut(BaseModel):
    id: str
    name: str
    status: str
    created_at: str
    published_at: str | None = None
    ltv_hist: int | None = None
    ltv_pred12: int | None = None
    lam: float | None = None
    r2: float | None = None
    review_state: str
    stale: bool
    source_data_seq: int
    current_data_seq: int
    lineage_id: str
    version_no: int
    supersedes_id: str | None = None


class SensitivityOut(BaseModel):
    lambda_base: float
    lambda_variants: list[float]
    delta_lambda: float
    rows: list[dict[str, Any]]
    cac_scales: list[float]
    cac_rows: list[dict[str, Any]]
    forecast_months: int
    arpu0: float
