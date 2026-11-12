"""Cohort / MemberOrder / RetentionCell 的对外 schema。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChannelMixEntry(BaseModel):
    members: int = 0
    cac: float = 0.0


class CohortOut(BaseModel):
    month: str = Field(description="首单月 YYYY-MM")
    size: int
    observed_months: int
    cumulative_revenue: float
    arpu: float
    avg_active_ratio: float
    low_sample: bool
    channel_mix: dict[str, ChannelMixEntry] = {}


class RetentionCellOut(BaseModel):
    m: int
    active: int
    rate: float | None = None
    rate_label: str = "—"
    state: Literal["observed", "right_censored"] = "observed"
    revenue: float = 0.0


class MatrixRowOut(BaseModel):
    month: str
    size: int
    observed_months: int
    low_sample: bool
    cells: list[RetentionCellOut]


class MatrixColumnOut(BaseModel):
    m: int
    active: int
    base: int
    rate: float | None = None
    rate_label: str = "—"


class MatrixStatsOut(BaseModel):
    cohorts: int
    cells_total: int
    cells_observed: int
    cells_censored: int
    low_sample_cells: int
    orders: int
    members: int
    revenue_total: float
    cumulative_arpu: float


class MatrixOut(BaseModel):
    snapshot_month: str
    data_version_seq: int | None = None
    data_version_id: str | None = None
    data_version_label: str | None = None
    months: int
    cohorts: list[MatrixRowOut]
    columns: list[MatrixColumnOut]
    stats: MatrixStatsOut
    notes: dict[str, str]


class MemberOrderOut(BaseModel):
    order_no: str
    member_code: str
    cohort_month: str
    channel: str
    store_code: str
    order_month: str
    month_index: int
    amount: float
    is_first_order: bool


class RebuildRequest(BaseModel):
    snapshot_month: str | None = Field(default=None, pattern=r"^\d{4}-(?:0[1-9]|1[0-2])$")
    months: int | None = Field(default=None, ge=2, le=24)


class RebuildJobOut(BaseModel):
    job_id: str
    status: str
    submitted_at: str | None = None
    finished_at: str | None = None
    summary: dict | None = None
    detail: str | None = None
