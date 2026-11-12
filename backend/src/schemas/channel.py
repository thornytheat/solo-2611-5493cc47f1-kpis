"""渠道对比 schema。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ChannelComparisonOut(BaseModel):
    source: str
    report_id: str | None = None
    report_name: str
    published_at: str | None = None
    snapshot_month: str
    fit: dict[str, Any]
    ltv_hist: int
    ltv_pred12: int
    arpu0: float
    margin_rate: float
    rows: list[dict[str, Any]]
    totals: dict[str, Any]
    scope: dict[str, Any]
    low_sample: dict[str, Any]
    notes: dict[str, str]
