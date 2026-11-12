"""worker 侧 Celery 应用：消费 backend 投递的矩阵重建任务 + 心跳。"""
from __future__ import annotations

from celery import Celery
from celery.schedules import schedule

from src.config.settings import settings

celery_app = Celery(
    "cohortltv-worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker_src.tasks.matrix", "worker_src.tasks.heartbeat"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    result_expires=1800,
    broker_connection_retry_on_startup=True,
    worker_max_tasks_per_child=200,
    beat_schedule={
        "cohortltv-heartbeat": {
            "task": "cohortltv.heartbeat",
            "schedule": schedule(run_every=20.0),
        }
    },
)
