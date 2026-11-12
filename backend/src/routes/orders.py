"""订单导入、导入批次与数据版本路由。

权限：
- orders:import（admin/analyst）发起校验与导入；
- orders:read / versions:read 全角色可读（viewer 也能看到当前数据版本与复核状态）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import import_controller
from src.middlewares.rbac import require_permission
from src.middlewares.rate_limit import rate_limit
from src.models.user import User
from src.schemas.import_schema import (
    DataVersionOut,
    ImportBatchOut,
    ImportRequest,
    ImportResultOut,
)

router = APIRouter(tags=["orders"])


@router.post("/orders/import", response_model=ImportResultOut)
def import_orders(
    payload: ImportRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders:import")),
    _: None = rate_limit("import"),
) -> dict:
    return import_controller.import_orders(db, payload, user, request)


@router.get("/orders/import/batches", response_model=list[ImportBatchOut])
def list_batches(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders:read")),
) -> list[dict]:
    return import_controller.list_batches(db)


@router.get("/orders/import/batches/{batch_id}", response_model=ImportBatchOut)
def get_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("orders:read")),
) -> dict:
    return import_controller.get_batch(db, batch_id)


@router.get("/data-versions", response_model=list[DataVersionOut])
def list_versions(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("versions:read")),
) -> list[dict]:
    return import_controller.list_versions(db)


@router.get("/data-versions/current", response_model=DataVersionOut)
def current_version(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("versions:read")),
) -> dict:
    return import_controller.current_version(db)
