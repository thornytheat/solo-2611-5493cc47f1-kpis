"""订单导入与数据版本的对外 schema。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.constants.limits import IMPORT_MAX_ROWS


class ImportOrderRow(BaseModel):
    order_no: str = Field(min_length=1, max_length=40)
    member_code: str = Field(min_length=1, max_length=24)
    cohort_month: str = Field(pattern=r"^\d{4}-(?:0[1-9]|1[0-2])$")
    order_month: str = Field(pattern=r"^\d{4}-(?:0[1-9]|1[0-2])$")
    channel: str = Field(min_length=1, max_length=20)
    amount: float = Field(gt=0, lt=10_000_000)
    store_code: str = Field(default="", max_length=16)
    is_first_order: bool = False
    ordered_at: str | None = None


class ImportRequest(BaseModel):
    batch_no: str = Field(min_length=2, max_length=64, description="外部投递批次号，全局唯一")
    # 投递方声明的依据版本序号；不传则只做批次号幂等拦截
    source_seq: int | None = Field(default=None, ge=1)
    dry_run: bool = Field(default=False, description="true=只整批校验，不写库不切换")
    note: str = Field(default="", max_length=400)
    rows: list[ImportOrderRow] = Field(min_length=1, max_length=IMPORT_MAX_ROWS)


class ImportErrorItem(BaseModel):
    index: int
    order_no: str = ""
    field: str
    message: str


class ImportResultOut(BaseModel):
    batch_id: str
    batch_no: str
    status: str
    dry_run: bool
    batch_seq: int | None = None
    data_version_id: str | None = None
    row_count: int
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected_count: int = 0
    errors: list[dict[str, Any]] = []
    would_activate_seq: int | None = None
    matrix: dict[str, Any] | None = None


class ImportBatchOut(BaseModel):
    id: str
    batch_no: str
    status: str
    batch_seq: int | None = None
    source_seq: int | None = None
    dry_run: bool
    row_count: int
    inserted_count: int
    updated_count: int
    unchanged_count: int
    rejected_count: int
    errors: list[dict[str, Any]]
    data_version_id: str | None = None
    applied_at: str | None = None
    created_at: str | None = None


class DataVersionOut(BaseModel):
    id: str
    seq: int
    label: str
    snapshot_month: str
    orders_count: int
    members_count: int
    cohorts_count: int
    cells_count: int
    change_note: str
    source_batch_id: str | None = None
    activated_at: str | None = None
    created_at: str | None = None
