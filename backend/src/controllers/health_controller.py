"""健康检查：db + redis + 版本。"""
from __future__ import annotations

from src.config.database import ping_db
from src.config.settings import settings
from src.utils.redis_client import ping_redis


def health() -> dict:
    return {
        "status": "ok",
        "brand": settings.brand,
        "database": ping_db(),
        "redis": ping_redis(),
        "version": "1.0.0",
        "snapshot_month": settings.snapshot_month,
    }
