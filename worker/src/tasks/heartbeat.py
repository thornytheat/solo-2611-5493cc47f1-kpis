"""worker 心跳：beat 每 20s 写一次 Redis，供容器 healthcheck 判定。"""
from __future__ import annotations

import time

from src.config.celery_app import HEARTBEAT_KEY
from src.utils.logger import get_logger
from src.utils.redis_client import get_redis
from worker_src.config.celery_app import celery_app

logger = get_logger("cohortltv.worker.heartbeat")


@celery_app.task(name="cohortltv.heartbeat")
def heartbeat() -> float:
    now = time.time()
    try:
        get_redis().set(HEARTBEAT_KEY, now)
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat write failed: %s", exc)
    return now
