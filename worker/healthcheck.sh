#!/bin/sh
# worker 健康检查：Redis 心跳（beat 每 20s 写）优先，兜底 celery inspect ping。
cd /app || exit 1
python - <<'PY'
import os
import sys
import time

os.environ.setdefault("PYTHONPATH", "/app:/app/backend")

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


def heartbeat_ok() -> bool:
    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        value = client.get("cohortltv:worker:heartbeat")
        if not value:
            return False
        return (time.time() - float(value)) < 90
    except Exception:
        return False


def celery_ok() -> bool:
    try:
        from worker_src.config.celery_app import celery_app

        return bool(celery_app.control.ping(timeout=3))
    except Exception:
        return False


if heartbeat_ok():
    print("worker healthy: heartbeat")
    sys.exit(0)
if celery_ok():
    print("worker healthy: celery ping")
    sys.exit(0)
print("worker unhealthy: no heartbeat and no celery pong")
sys.exit(1)
PY
