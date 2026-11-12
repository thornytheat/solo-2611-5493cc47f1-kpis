"""同期群：矩阵、列表、详情、重建任务。"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session

from src.config.celery_app import JOB_KEY_PREFIX, TASK_REBUILD_MATRIX, celery_app
from src.constants import error_codes as codes
from src.constants.templates import ACTION_REBUILD
from src.models.user import User
from src.services import audit_service, cohort_service, retention_service
from src.utils.errors import AppError
from src.utils.logger import get_logger
from src.config.settings import settings
from src.utils.redis_client import get_redis

logger = get_logger("cohortltv.cohort")


def matrix(db: Session) -> dict:
    return cohort_service.build_matrix(db)


def list_cohorts(db: Session) -> dict:
    rows = cohort_service.list_cohorts(db)
    return {"total": len(rows), "items": rows, "snapshot_month": settings.snapshot_month}


def detail(db: Session, month: str) -> dict:
    return cohort_service.build_detail(db, month)


def rebuild(db: Session, user: User, payload, request: Request) -> dict:
    job_id = uuid.uuid4().hex[:12]
    submitted = datetime.now(timezone.utc).isoformat()
    meta = {
        "job_id": job_id,
        "status": "queued",
        "submitted_at": submitted,
        "requested_by": user.email,
        "snapshot_month": payload.snapshot_month,
        "months": payload.months,
    }
    try:
        get_redis().setex(f"{JOB_KEY_PREFIX}{job_id}", 1800, json.dumps(meta))
        celery_app.send_task(
            TASK_REBUILD_MATRIX,
            kwargs={
                "job_id": job_id,
                "snapshot_month": payload.snapshot_month,
                "months": payload.months,
            },
            queue="celery",
        )
        audit_service.record(
            db, ACTION_REBUILD, user=user, entity="matrix", entity_id=job_id,
            detail=f"enqueued snapshot={payload.snapshot_month or 'default'}", request=request,
        )
        db.commit()
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001 - worker/redis 不可用时降级为同步重建
        logger.warning("enqueue rebuild failed, fallback to sync: %s", exc)
        summary = retention_service.rebuild_matrix(
            db, snapshot_month=payload.snapshot_month, months=payload.months
        )
        meta.update(
            status="succeeded",
            finished_at=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            detail="worker 不可用，已同步重建",
        )
        try:
            get_redis().setex(f"{JOB_KEY_PREFIX}{job_id}", 1800, json.dumps(meta))
        except Exception:  # noqa: BLE001
            pass
        audit_service.record(
            db, ACTION_REBUILD, user=user, entity="matrix", entity_id=job_id,
            detail=f"sync rebuild cells={summary['cells']}", request=request,
        )
        db.commit()
    return meta


def rebuild_status(job_id: str) -> dict:
    try:
        raw = get_redis().get(f"{JOB_KEY_PREFIX}{job_id}")
    except Exception as exc:  # noqa: BLE001
        raise AppError(codes.JOB_NOT_FOUND, detail=f"redis unavailable: {exc}") from exc
    if not raw:
        raise AppError(codes.JOB_NOT_FOUND)
    return json.loads(raw)
