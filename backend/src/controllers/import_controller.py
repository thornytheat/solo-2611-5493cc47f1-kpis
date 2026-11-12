"""订单导入控制器：HTTP 编排 + 审计留痕。

业务事务在 import_service 内整体提交/回滚；控制器只负责审计记录与响应序列化。
"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.templates import (
    ACTION_IMPORT_APPLY,
    ACTION_IMPORT_VALIDATE,
)
from src.models.user import User
from src.services import audit_service, import_service, version_service


def import_orders(db: Session, payload, user: User, request: Request) -> dict:
    rows = [row.model_dump() for row in payload.rows]
    result = import_service.import_orders(
        db,
        batch_no=payload.batch_no,
        rows=rows,
        source_seq=payload.source_seq,
        dry_run=payload.dry_run,
        note=payload.note,
        user=user,
    )
    action = ACTION_IMPORT_VALIDATE if payload.dry_run else ACTION_IMPORT_APPLY
    audit_service.record(
        db,
        action,
        user=user,
        entity="import_batch",
        entity_id=result["batch_id"],
        detail=(
            f"batch_no={payload.batch_no} rows={result['row_count']} "
            f"insert={result.get('inserted', 0)} update={result.get('updated', 0)} "
            f"unchanged={result.get('unchanged', 0)} seq={result.get('batch_seq')}"
        ),
        request=request,
    )
    db.commit()
    return result


def list_batches(db: Session) -> list[dict]:
    return [import_service.serialize_batch(batch) for batch in import_service.list_batches(db)]


def get_batch(db: Session, batch_id: str) -> dict:
    return import_service.serialize_batch(import_service.get_batch(db, batch_id))


def list_versions(db: Session) -> list[dict]:
    return [_serialize_version(version) for version in version_service.list_versions(db)]


def current_version(db: Session) -> dict:
    version = version_service.current_version(db)
    if version is None:
        return {
            "id": "",
            "seq": 0,
            "label": "尚未初始化",
            "snapshot_month": "",
            "orders_count": 0,
            "members_count": 0,
            "cohorts_count": 0,
            "cells_count": 0,
            "change_note": "",
            "source_batch_id": None,
            "activated_at": None,
            "created_at": None,
        }
    return _serialize_version(version)


def _serialize_version(version) -> dict:
    return {
        "id": str(version.id),
        "seq": version.seq,
        "label": version.label,
        "snapshot_month": version.snapshot_month,
        "orders_count": version.orders_count,
        "members_count": version.members_count,
        "cohorts_count": version.cohorts_count,
        "cells_count": version.cells_count,
        "change_note": version.change_note,
        "source_batch_id": str(version.source_batch_id) if version.source_batch_id else None,
        "activated_at": version.activated_at.isoformat() if version.activated_at else None,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }
