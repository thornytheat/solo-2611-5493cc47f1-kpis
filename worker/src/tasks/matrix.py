"""矩阵重建任务：与 backend 共用同一份 retention_service（真正算在 worker）。"""
from __future__ import annotations

import json
import time

from src.config.celery_app import HEARTBEAT_KEY, JOB_KEY_PREFIX
from src.config.database import session_scope
from src.services import retention_service
from src.utils.logger import get_logger
from src.utils.redis_client import get_redis
from worker_src.config.celery_app import celery_app

logger = get_logger("cohortltv.worker.matrix")


def _update_job(job_id: str | None, patch: dict) -> None:
    if not job_id:
        return
    try:
        client = get_redis()
        key = f"{JOB_KEY_PREFIX}{job_id}"
        raw = client.get(key)
        payload = json.loads(raw) if raw else {"job_id": job_id}
        payload.update(patch)
        client.setex(key, 1800, json.dumps(payload))
    except Exception as exc:  # noqa: BLE001
        logger.warning("job status update failed job=%s error=%s", job_id, exc)


@celery_app.task(name="cohortltv.rebuild_matrix", bind=True, max_retries=0)
def rebuild_matrix_task(self, job_id: str | None = None, snapshot_month: str | None = None,
                        months: int | None = None) -> dict:
    started = time.perf_counter()
    _update_job(job_id, {"status": "running", "started_at": _now()})
    try:
        with session_scope() as db:
            summary = retention_service.rebuild_matrix(
                db, snapshot_month=snapshot_month, months=months
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("rebuild failed job=%s error=%s", job_id, exc)
        _update_job(job_id, {"status": "failed", "detail": str(exc), "finished_at": _now()})
        raise
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    _update_job(
        job_id,
        {
            "status": "succeeded",
            "finished_at": _now(),
            "elapsed_ms": elapsed_ms,
            "summary": summary,
        },
    )
    try:
        get_redis().set(HEARTBEAT_KEY, time.time())
    except Exception:  # noqa: BLE001
        pass
    logger.info("rebuild done job=%s cells=%s elapsed=%sms", job_id, summary["cells"], elapsed_ms)
    return {"job_id": job_id, "elapsed_ms": elapsed_ms, **summary}


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
